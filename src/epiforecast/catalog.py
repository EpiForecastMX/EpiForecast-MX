"""Catálogo canónico de series productivas (baseline EPIC 0 / E0-S1).

Fuente única y CORREGIDA del inventario de series en producción. Reemplaza el conteo
inflado "435 / Dengue 102" que circula en ``tabla_333_modelos_produccion.xlsx`` y en
``knowledge.json``: ese 102 arrastra 3 nacionales duplicados (Prophet + DeepAR por sexo)
y 13 selecciones inválidas de Ensemble/Stacking (motores no elegibles para Dengue), y
NO contiene NBGLM (es una selección stale previa al selector NBGLM).

El catálogo autoritativo es:
  * neuro (Depresión/Parkinson/Alzheimer): 333 filas desde el workbook de producción,
    filtrado a la cohorte neuro. 37 geografías × 3 sexos × 3 padecimientos.
  * Dengue: 99 filas desde ``produccion_dengue.csv`` (selector cohorte-aware, motores
    elegibles Prophet/DeepAR/NBGLM). (Nacional + 32 estados) × 3 sexos; SIN fallback
    regional (por eso 99 y no 111).

  production_series_count = 432 (333 + 99)   ← distinto de
  gallery_item_count       = 444 (333 + 111) ← la galería de Dengue sí incluye las 4
  regiones (37 geo × 3 = 111), aunque no sean productivas.

Los conteos derivados (dashboard, stats) deben leer de aquí; NO se renombra ni se
reescribe ningún artefacto legacy (tabla_333, produccion_dengue.csv, punteros DVC).
En EPIC 1 la lista de cohorte neuro pasará a venir del registry
(``registry.production_cohort()``); hoy se congela el baseline con el literal actual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import unicodedata

import pandas as pd

from epiforecast.utils.config import conf

# Cohorte neuro de producción (baseline). EPIC 1 lo sustituye por registry.production_cohort().
NEURO_NAMES: tuple[str, ...] = ("Alzheimer", "Depresion", "Parkinson")

# Motores elegibles por cohorte (para validar que no se cuelen selecciones inválidas).
DENGUE_ELIGIBLE: frozenset[str] = frozenset({"Prophet", "DeepAR", "NBGLM"})

# Esquema unificado del catálogo.
CATALOG_COLUMNS: tuple[str, ...] = (
    "disease_id",
    "data_name",
    "cohorte",
    "entidad",
    "sexo",
    "motor_productivo",
    "source",
)


def _slug(name: str) -> str:
    """``"Depresión"`` -> ``"depresion"`` (NFKD-fold + lower + espacios a ``_``)."""
    folded = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return folded.strip().lower().replace(" ", "_")


def _reports_dir() -> Path:
    # Resiliente: bajo pytest ``conf`` es un mock cuyo ``paths`` puede no traer "reports".
    # Cae a "./reports" (misma resolución que el CLI con la config real).
    reports = (conf.get("paths", {}) if hasattr(conf, "get") else {}).get("reports") or "./reports"
    return Path(reports)


def _proddetails_dir() -> Path:
    return _reports_dir() / "ProdDetails"


def _neuro_table_path() -> Path:
    return _proddetails_dir() / "tabla_333_modelos_produccion.xlsx"


def _dengue_table_path() -> Path:
    return _proddetails_dir() / "produccion_dengue.csv"


def _dengue_gallery_items_path() -> Path:
    # ../EpiForecast-IMSS-Dashboard/Reports/dengue/_gallery_items.json (repo del dashboard)
    return (
        _reports_dir().resolve().parent.parent
        / "EpiForecast-IMSS-Dashboard"
        / "Reports"
        / "dengue"
        / "_gallery_items.json"
    )


@dataclass(frozen=True)
class CatalogCounts:
    """Conteos derivados del catálogo canónico (para tests y para el manifiesto web)."""

    production_series_count: int
    gallery_item_count: int
    por_cohorte: dict[str, int]
    por_padecimiento: dict[str, int]
    motor_dist: dict[str, dict[str, int]]
    nacional_por_cohorte: dict[str, int]
    diagnostics: dict[str, object] = field(default_factory=dict)


def _load_neuro(neuro_names: tuple[str, ...]) -> pd.DataFrame:
    df = pd.read_excel(_neuro_table_path(), sheet_name="Produccion")
    df = df[df["padecimiento"].isin(neuro_names)].copy()
    return pd.DataFrame(
        {
            "disease_id": df["padecimiento"].map(_slug),
            "data_name": df["padecimiento"].astype(str),
            "cohorte": "neuro",
            "entidad": df["entidad"].astype(str),
            "sexo": df["sexo"].astype(str),
            "motor_productivo": df["modelo_produccion"].astype(str),
            "source": "tabla_333",
        }
    )


def _load_dengue() -> pd.DataFrame:
    df = pd.read_csv(_dengue_table_path())
    return pd.DataFrame(
        {
            "disease_id": df["padecimiento"].map(_slug),
            "data_name": df["padecimiento"].astype(str),
            "cohorte": "dengue",
            "entidad": df["entidad"].astype(str),
            "sexo": df["sexo"].astype(str),
            "motor_productivo": df["motor_productivo"].astype(str),
            "source": "produccion_dengue",
        }
    )


def _dengue_stale_diagnostics(neuro_names: tuple[str, ...]) -> dict[str, object]:
    """Documenta por qué el Dengue de tabla_333 (102) NO se usa: dup nacionales + motores
    inválidos + cero NBGLM. Solo informativo; no modifica el workbook legacy."""
    try:
        df = pd.read_excel(_neuro_table_path(), sheet_name="Produccion")
    except Exception:  # pragma: no cover - defensivo
        return {}
    den = df[~df["padecimiento"].isin(neuro_names)].copy()
    if den.empty:
        return {"dengue_en_tabla_333": 0}
    dup = int(den.duplicated(subset=["entidad", "sexo"]).sum())
    invalid = den[~den["modelo_produccion"].isin(DENGUE_ELIGIBLE)]
    return {
        "dengue_en_tabla_333": int(len(den)),
        "nacionales_duplicados": dup,
        "selecciones_invalidas_ensemble_stacking": int(len(invalid)),
        "tiene_nbglm": bool((den["modelo_produccion"] == "NBGLM").any()),
        "motivo_descartado": (
            "Se usa produccion_dengue.csv (99, con NBGLM); el Dengue de tabla_333 "
            "es stale (dup nacionales + Ensemble/Stacking no elegibles, sin NBGLM)."
        ),
    }


def _gallery_item_count(neuro_count: int) -> int:
    """Galería = neuro (== producción neuro) + items de galería de Dengue (incluye las 4
    regiones). Si no está el json del dashboard, cae al invariante conocido 111."""
    import json

    p = _dengue_gallery_items_path()
    try:
        dengue_items = len(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        dengue_items = 111
    return neuro_count + dengue_items


def build_production_catalog(
    neuro_names: tuple[str, ...] = NEURO_NAMES,
) -> tuple[pd.DataFrame, CatalogCounts]:
    """Construye el catálogo canónico de producción (432 series) y sus conteos.

    Returns:
        (df, counts). ``df`` tiene columnas ``CATALOG_COLUMNS`` con clave única
        ``(disease_id, entidad, sexo)``. ``counts`` incluye los conteos derivados.
    """
    neuro = _load_neuro(neuro_names)
    dengue = _load_dengue()
    df = pd.concat([neuro, dengue], ignore_index=True)[list(CATALOG_COLUMNS)]

    por_cohorte = {str(c): int(n) for c, n in df.groupby("cohorte").size().items()}
    por_padecimiento = {str(p): int(n) for p, n in df.groupby("data_name").size().items()}
    motor_dist = {
        str(c): {str(m): int(n) for m, n in g.groupby("motor_productivo").size().items()}
        for c, g in df.groupby("cohorte")
    }
    nac = df[df["entidad"].str.strip().str.lower() == "nacional"]
    nacional_por_cohorte = {str(c): int(n) for c, n in nac.groupby("cohorte").size().items()}

    counts = CatalogCounts(
        production_series_count=int(len(df)),
        gallery_item_count=_gallery_item_count(len(neuro)),
        por_cohorte=por_cohorte,
        por_padecimiento=por_padecimiento,
        motor_dist=motor_dist,
        nacional_por_cohorte=nacional_por_cohorte,
        diagnostics=_dengue_stale_diagnostics(neuro_names),
    )
    return df, counts


def validate_catalog(df: pd.DataFrame) -> list[str]:
    """Devuelve una lista de problemas (vacía = OK). No lanza, para uso en tests/CLI."""
    problems: list[str] = []
    dup = df.duplicated(subset=["disease_id", "entidad", "sexo"]).sum()
    if dup:
        problems.append(f"{dup} claves (disease_id, entidad, sexo) duplicadas")
    bad = df[(df["cohorte"] == "dengue") & (~df["motor_productivo"].isin(DENGUE_ELIGIBLE))]
    if len(bad):
        problems.append(
            f"{len(bad)} filas Dengue con motor no elegible {sorted(set(bad['motor_productivo']))}"
        )
    if (df["motor_productivo"].isin(["", "nan", "None"])).any():
        problems.append("motor_productivo vacío en alguna fila")
    return problems
