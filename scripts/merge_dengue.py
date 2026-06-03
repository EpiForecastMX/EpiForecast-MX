#!/usr/bin/env python
"""merge_dengue.py — Integra la serie de Dengue al dataset consolidado (reproducible).

Mergea ``data/interim/dengue_boletin.csv`` (producido por ``scripts/extrae_dengue.py``,
ya con las correcciones de fuente) dentro del dataset consolidado
``data/processed/dataset_boletin_epidemiologico.csv``. Es **idempotente**: elimina las
filas de Dengue previas del consolidado antes de reinsertar, así re-correrlo no duplica
ni acumula.

Tras correrlo, versionar en DVC (no rompe el CI: push ANTES del commit del .dvc):
    dvc add data/processed/dataset_boletin_epidemiologico.csv
    dvc push data/processed/dataset_boletin_epidemiologico.csv
    git add data/processed/dataset_boletin_epidemiologico.csv.dvc && git commit ...

Flujo canónico Dengue:
    python scripts/extrae_dengue.py          # serie validada + correcciones de fuente
    python scripts/merge_dengue.py           # integra al consolidado  (este script)
    # dvc add + push + commit .dvc
    # prep:  make filter/clean/transform/mapper con padecimiento.tipo='Dengue' y
    #        data.raw_data_file apuntando al consolidado

Uso:
    python scripts/merge_dengue.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from epiforecast.utils.config import logger as log

ROOT = Path(__file__).resolve().parent.parent
DENGUE = ROOT / "data" / "interim" / "dengue_boletin.csv"
CONSOLIDADO = ROOT / "data" / "processed" / "dataset_boletin_epidemiologico.csv"
PADECIMIENTO = "Dengue"
KEY = ["Anio", "Semana", "Entidad", "Padecimiento"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dengue", default=str(DENGUE))
    parser.add_argument("--consolidado", default=str(CONSOLIDADO))
    args = parser.parse_args()

    den = pd.read_csv(args.dengue)
    cons = pd.read_csv(args.consolidado)
    # Alinear dtypes flotantes con el consolidado.
    for col in ("Casos_semana", "Acumulado_anio_anterior"):
        if col in cons.columns and col in den.columns:
            den[col] = den[col].astype(cons[col].dtype)

    n0 = len(cons)
    n_neuro = int((~cons["Padecimiento"].eq(PADECIMIENTO)).sum())
    # Idempotente: descarta Dengue previo del consolidado antes de reinsertar.
    cons = cons[cons["Padecimiento"] != PADECIMIENTO]
    merged = pd.concat([cons, den], ignore_index=True)
    dups = int(merged.duplicated(KEY).sum())
    merged = (
        merged.drop_duplicates(KEY)
        .sort_values(["Padecimiento", "Anio", "Semana", "Entidad"])
        .reset_index(drop=True)
    )
    merged.to_csv(args.consolidado, index=False, encoding="utf-8")

    log.info(
        "Merge Dengue: consolidado {} -> {} filas | neuro={} (intacto) | dengue={} | dups_clave={}",
        n0,
        len(merged),
        n_neuro,
        int(merged["Padecimiento"].eq(PADECIMIENTO).sum()),
        dups,
    )
    log.info("Recuerda: dvc add + dvc push + commit del .dvc (push ANTES del commit).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
