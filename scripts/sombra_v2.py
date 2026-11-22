"""Política v2 en sombra: retroprueba en desarrollo, emisión congelada y validación prospectiva.

No publica ni reentrena. Uso:
    python -m scripts.sombra_v2 retro [--disease ID ...]
    python -m scripts.sombra_v2 emite [--disease ID ...]
    python -m scripts.sombra_v2 valida EMISION_ID

La emisión vive en runs/sombra_v2/<emision>/ y su índice de hashes en docs/sombra_v2/emisiones/.
La validación sólo cuenta semanas posteriores al origen de cada padecimiento con verdad completa.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner import sombra_v2 as sv
from epiforecast.runner import sombra_v2_flujo as flujo

_ROOT = Path(__file__).resolve().parents[1]


def _resumen_retro(df: pd.DataFrame) -> dict[str, object]:
    por = df.groupby("disease_id")[
        ["smape_nacional_control", "smape_nacional_v2", "smape_nacional_v2_sin_margen"]
    ].mean()
    out: dict[str, object] = {"padecimientos": len(por), "pliegues": len(df)}
    for col in ["v2", "v2_sin_margen"]:
        s, c = por[f"smape_nacional_{col}"], por["smape_nacional_control"]
        out[col] = {
            "mediana": round(float(s.median()), 2),
            "mejor_que_control": int((s < c - 1e-9).sum()),
            "igual_al_control": int(((s - c).abs() <= 1e-9).sum()),
            "dentro_10pct": int((s <= c * 1.10).sum()),
        }
    out["control_mediana"] = round(float(por["smape_nacional_control"].median()), 2)
    for n in ("80", "95"):
        if f"cobertura_{n}" in df:
            out[f"cobertura_{n}_mediana"] = round(float(df[f"cobertura_{n}"].median()), 1)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre in ("retro", "emite"):
        p = sub.add_parser(nombre)
        p.add_argument("--disease", action="append", help="por defecto, todos los publicados")
    sub.add_parser("valida").add_argument("emision")
    args = ap.parse_args(argv)
    reglas, catalog = sv.cargar_reglas(), load_geo_catalog()

    if args.cmd == "valida":
        df = flujo.validar(args.emision, catalog, reglas, _ROOT)
        con = df[df["semanas"] > 0]
        print(df.to_string(index=False, max_rows=20))
        if not con.empty:
            resumen = {
                "padecimientos_con_semanas": len(con),
                "sombra_mejor_que_publicado": int(
                    (con["smape_nacional_sombra"] < con["smape_nacional_publicado"]).sum()
                ),
                "mediana_nacional": {
                    k: round(float(con[f"smape_nacional_{k}"].median()), 2)
                    for k in ("sombra", "publicado", "control")
                },
                "cobertura_mediana": {
                    str(c): round(float(con[c].median()), 1)
                    for c in con.columns
                    if str(c).startswith("cobertura_")
                },
            }
            print(json.dumps(resumen, ensure_ascii=False, indent=1))
        return 0

    diseases = args.disease or flujo.publicados()
    if args.cmd == "emite":
        indice = flujo.emitir(diseases, catalog, reglas, _ROOT)
        print(json.dumps({k: indice[k] for k in ("emision_id", "emitida_utc")}, indent=1))
        return 0

    filas = []
    for d in diseases:
        ev = flujo.desarrollo(d, reglas, _ROOT)
        for f in flujo.retro(ev, catalog, reglas):
            filas.append({"disease_id": d} | f)
        print(d, flush=True)
    df = pd.DataFrame(filas)
    destino = _ROOT / "runs" / "sombra_v2" / "retro.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, index=False)
    print(json.dumps(_resumen_retro(df), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
