"""Banco de rescate de controles: compuerta completa en desarrollo (no publica nada).

Uso:
    python -m scripts.banco_rescate [--workers N] [--disease ID ...]

Escribe en runs/banco_rescate/v1/:
- ``por_pliegue.csv``: por padecimiento, año de desarrollo y motor (control y variantes del naive
  coherente), los tres ámbitos de la compuerta, su ``worse_pct`` contra el control y si pasa.
- ``externo.csv``: selección anidada (años externos 2023 y 2024, y transferencia a historia corta).
- ``veredictos.csv``: por padecimiento, si pasa la compuerta en todos sus años externos y mejora el
  nacional (rescatado en desarrollo), con su desenlace publicado.
- ``fijo.csv``: lo mismo con la variante congelada para la sombra (``naive_coherente_f4``).
- ``resumen.json`` y ``procedencia.json``.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from epiforecast.banco import flujo, rescate
from epiforecast.data.epi_geo_exposure import load_geo_catalog

_ROOT = Path(__file__).resolve().parents[1]
OUT = _ROOT / "runs" / "banco_rescate" / "v1"
FIJO = "f4|ent"
DESENLACES = _ROOT / "docs" / "paper_comia2027" / "evidencia" / "padecimientos.csv"


def _uno(disease: str) -> list[dict[str, Any]]:
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[var] = "1"
    np.seterr(all="ignore")
    import warnings

    warnings.simplefilter("ignore")
    p = flujo.cargar_config()["parametros"]
    return rescate.filas(rescate.cargar(disease), load_geo_catalog(), p)


def _publicados() -> list[str]:
    raiz = _ROOT / "config" / "publication"
    return sorted(
        d.name
        for d in raiz.iterdir()
        if (d / "public_release_pointer.json").exists()
        and (d / "prospective_status.json").exists()
    )


def _resumen(v: pd.DataFrame, ext: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for grupo, sub in v.groupby("grupo"):
        e = ext[ext["disease_id"].isin(sub["disease_id"])]
        lr = np.log1p(e.groupby("disease_id")["peor_smape_nacional_general"].mean() / 100)
        out[str(grupo)] = {
            "padecimientos": int(len(sub)),
            "rescatados": int(sub["rescatado"].sum()),
            "pasan_sin_mejora": int((sub["pasa"] & ~sub["rescatado"]).sum()),
            "no_pasan": int((~sub["pasa"]).sum()),
            "pliegues_externos": int(len(e)),
            "pliegues_pasan": int(e["pasa"].sum()),
            "pliegues_positivos": int(e["positivo"].sum()),
            "mejora_nacional_mediana_pct": float(e["peor_smape_nacional_general"].median()),
            "peor_bases_mediana_pct": float(e["peor_smape_bases"].median()),
            "peor_all_mediana_pct": float(e["peor_smape_all"].median()),
            "wilcoxon_p_nacional": float(stats.wilcoxon(lr).pvalue) if len(lr) > 5 else None,
        }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--disease", nargs="*")
    a = ap.parse_args(argv)
    ids = a.disease or _publicados()
    with ProcessPoolExecutor(a.workers) as ex:
        df = pd.DataFrame([f for fs in ex.map(_uno, ids) for f in fs])
    OUT.mkdir(parents=True, exist_ok=True)
    g = rescate.compuerta(df)
    des = pd.read_csv(DESENLACES).set_index("disease_id")["desenlace"]
    grupo = des.map(lambda x: "controles" if str(x).startswith("control") else "aceptados")
    df.to_csv(OUT / "por_pliegue.csv", index=False)
    ext, elegidas = rescate.anidado(g)
    ext.to_csv(OUT / "externo.csv", index=False)
    salida: dict[str, Any] = {"elegidas_por_externo": elegidas}
    for nombre, e in {"anidado": ext, "fijo": None}.items():
        if e is None:
            fijo = g[g["motor"] == FIJO]
            ultimos = fijo.groupby("disease_id")["anio"].transform(
                lambda s: s.isin(sorted(s.unique())[-2:])
            )
            e = fijo[ultimos.astype(bool)]
        v = rescate.veredictos(e)
        v["desenlace"] = v["disease_id"].map(des)
        v["grupo"] = v["disease_id"].map(grupo)
        v.to_csv(OUT / ("veredictos.csv" if nombre == "anidado" else "fijo.csv"), index=False)
        salida[nombre] = _resumen(v, e)
    (OUT / "resumen.json").write_text(json.dumps(salida, indent=1, ensure_ascii=False) + "\n")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=_ROOT
    )
    (OUT / "procedencia.json").write_text(
        json.dumps(
            {"commit": commit.stdout.strip(), "padecimientos": len(ids), "variante_fija": FIJO},
            indent=1,
        )
        + "\n"
    )
    print(json.dumps(salida, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
