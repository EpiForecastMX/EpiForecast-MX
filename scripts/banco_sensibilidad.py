"""Sensibilidad a quitar 2020–2021 de la historia (desarrollo 2022–2024; no publica nada).

Uso:
    python -m scripts.banco_sensibilidad [--workers N]

Lee ``runs/banco_optuna/v2/datos.pkl`` (``make banco-optuna`` o ``banco_optuna datos``) y los
parámetros globales de nivel × perfil de esa búsqueda. Escribe en runs/banco_sensibilidad/v1/:
- ``por_pliegue.csv``: sMAPE nacional por padecimiento, variante, pliegue y configuración.
- ``resumen.csv``: por configuración y variante, mejora mediana contra el naive completo con IC
  bootstrap, victorias y Wilcoxon; en todos los pliegues y sólo en 2023–2024.
- ``pruebas_holm.csv``: cada variante recortada contra la completa, misma configuración (Holm en
  una sola familia), y cada configuración contra el naive.
- ``procedencia.json``.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import pickle
from typing import Any

import numpy as np
import pandas as pd
from scripts import banco_optuna

from epiforecast.banco import ajuste_flujo as af
from epiforecast.banco import estadistica, sensibilidad

_ROOT = Path(__file__).resolve().parents[1]
OUT = _ROOT / "runs" / "banco_sensibilidad" / "v1"
TRAMOS = {"2022_2024": (2022, 2023, 2024), "2023_2024": (2023, 2024)}


def _globales() -> dict[int, dict[str, Any]]:
    out = {}
    for anio in (2023, 2024):
        ruta = banco_optuna.OUT / "global" / f"nivel_x_perfil__{anio}.json"
        if ruta.exists():
            out[anio] = json.loads(ruta.read_text())["params"]
    return out


def _uno(args: tuple[af.Padecimiento, dict[str, Any]]) -> list[dict[str, Any]]:
    banco_optuna._hilos()
    np.seterr(all="ignore")
    return sensibilidad.filas(*args)


def _bootstrap(lr: np.ndarray[Any, Any]) -> tuple[float, float]:
    rng = np.random.default_rng(banco_optuna.SEMILLA)
    meds = np.median(rng.choice(lr, size=(10_000, len(lr)), replace=True), axis=1)
    lo, hi = np.percentile(meds, [2.5, 97.5])
    return float(np.expm1(lo) * 100), float(np.expm1(hi) * 100)


def resumir(t: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    filas, pruebas = [], []
    for tramo, anios in TRAMOS.items():
        sub = t[t["pliegue"].isin(anios)]
        # padecimientos con los mismos pliegues en todas las variantes (pareo estricto)
        n_pl = sub.groupby(["disease_id", "variante", "config"])["pliegue"].nunique()
        completos = n_pl.unstack("variante").dropna()
        completos = completos[completos.nunique(axis=1) == 1]
        piv = sub.groupby(["disease_id", "config", "variante"])["log_ratio"].mean().unstack()
        piv = piv.loc[piv.index.intersection(completos.index)]
        for config, g in piv.groupby(level="config"):
            for variante in sensibilidad.VARIANTES:
                lr = g[variante].dropna().to_numpy()
                if len(lr) < 6:
                    continue
                lo, hi = _bootstrap(lr)
                w = estadistica.wilcoxon_pareado(lr, np.zeros_like(lr))
                fila = {
                    "tramo": tramo,
                    "config": config,
                    "variante": variante,
                    "padecimientos": len(lr),
                    "mejora_mediana_pct": float(np.expm1(np.median(lr)) * 100),
                    "ic_bajo": lo,
                    "ic_alto": hi,
                    "gana_al_naive": int((lr < 0).sum()),
                    "p_vs_naive": w["p"],
                }
                filas.append(fila)
                pruebas.append(
                    {
                        "tramo": tramo,
                        "comparacion": f"{config} [{variante}] vs naive completo",
                        "padecimientos": len(lr),
                        "dif_mediana_log": w["mediana_dif"],
                        "r_rb": w["r_rb"],
                        "p": w["p"],
                    }
                )
                if variante == "completa":
                    continue
                x = g[[variante, "completa"]].dropna()
                w2 = estadistica.wilcoxon_pareado(x[variante].to_numpy(), x["completa"].to_numpy())
                pruebas.append(
                    {
                        "tramo": tramo,
                        "comparacion": f"{config}: {variante} vs completa",
                        "padecimientos": len(x),
                        "dif_mediana_log": w2["mediana_dif"],
                        "cambio_mediano_pct": float(np.expm1(w2["mediana_dif"]) * 100)
                        if np.isfinite(w2["mediana_dif"])
                        else np.nan,
                        "mejora_con_recorte": int((x[variante] < x["completa"]).sum()),
                        "r_rb": w2["r_rb"],
                        "p": w2["p"],
                    }
                )
    res, pr = pd.DataFrame(filas), pd.DataFrame(pruebas)
    ok = pr["p"].notna()
    pr.loc[ok, "p_holm"] = estadistica.holm(pr.loc[ok, "p"].tolist())
    return res.sort_values(["tramo", "variante", "mejora_mediana_pct"]), pr


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args(argv)
    ps: list[af.Padecimiento] = pickle.loads((banco_optuna.OUT / "datos.pkl").read_bytes())
    largos = [p for p in ps if set(sensibilidad.PLIEGUES) & set(p.desarrollo)]
    largos = [p for p in largos if int(p.anios[0]) < 2020]  # historia previa a la pandemia
    configs = sensibilidad.configuraciones(_globales())
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        bloques = list(ex.map(_uno, [(p, configs) for p in largos]))
    t = pd.DataFrame([f for b in bloques for f in b])
    OUT.mkdir(parents=True, exist_ok=True)
    t.to_csv(OUT / "por_pliegue.csv", index=False)
    res, pr = resumir(t)
    res.to_csv(OUT / "resumen.csv", index=False)
    pr.to_csv(OUT / "pruebas_holm.csv", index=False)
    proc = banco_optuna.procedencia() | {
        "padecimientos": len(largos),
        "variantes": {k: list(v) for k, v in sensibilidad.VARIANTES.items()},
        "pliegues": list(sensibilidad.PLIEGUES),
        "referencia": "naive lag 52 con historia completa",
    }
    (OUT / "procedencia.json").write_text(json.dumps(proc, ensure_ascii=False, indent=1) + "\n")
    cols = ["tramo", "config", "variante", "padecimientos", "mejora_mediana_pct", "ic_bajo"]
    cols += ["ic_alto", "gana_al_naive"]
    print(res[cols].round(2).to_string(index=False))
    sel = pr[pr["comparacion"].str.contains("vs completa")]
    print(sel.drop(columns=["r_rb"]).round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
