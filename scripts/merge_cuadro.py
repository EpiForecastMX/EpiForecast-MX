"""merge_cuadro.py — Integra la serie de un padecimiento al consolidado (EPIC 2).

Clon genérico de merge_dengue.py, parametrizado por ``--disease`` (resuelto vía registry).
Idempotente en la clave de 4 (``Anio, Semana, Entidad, Padecimiento``): descarta las filas
del padecimiento objetivo y reinserta. Valida esquema, escribe de forma atómica (temp +
replace) y verifica que la proyección NO-objetivo (neuro + Dengue) queda byte-idéntica.

Uso: .venv/bin/python -m scripts.merge_cuadro --disease Obesidad
Tras correrlo: dvc add + dvc push + commit del .dvc (push ANTES del commit).
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd

from epiforecast import registry
from epiforecast.utils.config import logger as log

ROOT = Path(__file__).resolve().parent.parent
CONSOLIDADO = ROOT / "data" / "processed" / "dataset_boletin_epidemiologico.csv"
KEY = ["Anio", "Semana", "Entidad", "Padecimiento"]
SCHEMA = [
    "Anio",
    "Semana",
    "Entidad",
    "Padecimiento",
    "Casos_semana",
    "Acumulado_hombres",
    "Acumulado_mujeres",
    "Acumulado_anio_anterior",
]


def _semantic_hash(df: pd.DataFrame) -> str:
    rows = sorted("|".join(str(r[c]) for c in SCHEMA) for _, r in df[SCHEMA].iterrows())
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--disease", required=True)
    ap.add_argument("--consolidado", default=str(CONSOLIDADO))
    args = ap.parse_args()

    d = registry.require(args.disease)
    serie_path = ROOT / "data" / "interim" / f"{d.slug}_boletin.csv"
    if not serie_path.exists():
        log.error("No existe {} — corre extrae_cuadro primero.", serie_path)
        return 1

    nueva = pd.read_csv(serie_path)
    cons = pd.read_csv(args.consolidado)

    # Validación de esquema y padecimiento único en la serie nueva.
    if list(nueva.columns) != SCHEMA:
        log.error("Esquema inesperado en {}: {}", serie_path, list(nueva.columns))
        return 1
    if set(nueva["Padecimiento"].unique()) != {d.data_name}:
        log.error(
            "La serie contiene más de un padecimiento: {}", set(nueva["Padecimiento"].unique())
        )
        return 1

    for col in ("Casos_semana", "Acumulado_anio_anterior"):
        if col in cons.columns and col in nueva.columns:
            nueva[col] = nueva[col].astype(cons[col].dtype)

    # Proyección NO-objetivo antes del merge (debe quedar idéntica después).
    otros_antes = cons[cons["Padecimiento"] != d.data_name]
    hash_antes = _semantic_hash(otros_antes)

    n0 = len(cons)
    cons_sin = cons[cons["Padecimiento"] != d.data_name]
    merged = pd.concat([cons_sin, nueva], ignore_index=True)
    dups = int(merged.duplicated(KEY).sum())
    merged = (
        merged.drop_duplicates(KEY)
        .sort_values(["Padecimiento", "Anio", "Semana", "Entidad"])
        .reset_index(drop=True)
    )

    # Verificación: la proyección no-objetivo no cambió.
    hash_despues = _semantic_hash(merged[merged["Padecimiento"] != d.data_name])
    if hash_antes != hash_despues:
        log.error("ABORTO: la proyección no-{} cambió (hash difiere). No se escribe.", d.data_name)
        return 1

    # Escritura atómica.
    tmp = Path(args.consolidado).with_suffix(".csv.tmp")
    merged.to_csv(tmp, index=False, encoding="utf-8")
    tmp.replace(args.consolidado)

    log.success(
        "Merge {}: consolidado {} -> {} filas | no-{}={} (intacto) | {}={} | dups_clave={}",
        d.data_name,
        n0,
        len(merged),
        d.data_name,
        len(otros_antes),
        d.data_name,
        int(merged["Padecimiento"].eq(d.data_name).sum()),
        dups,
    )
    log.info("Recuerda: dvc add + dvc push + commit del .dvc (push ANTES del commit).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
