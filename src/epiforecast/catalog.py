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

  production_series_count = 432 (333 + 99)
  gallery_item_count       = 432 en la ronda W37: se CUENTA en el inventario que la galería
  publica (la lista ``DATA`` de ``Reports/index.html``), no se supone. Hasta W33 la galería de
  Dengue traía además sus 4 regiones (111 gráficos, total 444); en W37 salen porque no forman
  parte de las 99 series de la asignación (hallazgo C). Sin inventario el conteo es ``None``.

Los conteos derivados (dashboard, stats) deben leer de aquí; NO se renombra ni se
reescribe ningún artefacto legacy (tabla_333, produccion_dengue.csv, punteros DVC).
En EPIC 1 la lista de cohorte neuro pasará a venir del registry
(``registry.production_cohort()``); hoy se congela el baseline con el literal actual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
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


# Raíz del dashboard cuya galería se cuenta. El productor apunta aquí su staging; sin la variable
# se usa el repo hermano ``../EpiForecast-IMSS-Dashboard``.
DASHBOARD_ENV = "EPIFORECAST_DASHBOARD"
_RE_DATA_GALERIA = re.compile(r"^const DATA = (\[.*\]);$", re.MULTILINE)


def _dashboard_dir() -> Path:
    env = os.environ.get(DASHBOARD_ENV)
    if env:
        return Path(env)
    return _reports_dir().resolve().parent.parent / "EpiForecast-IMSS-Dashboard"


def galeria_publicada(dashboard: Path | None = None) -> list[dict[str, str]] | None:
    """Los gráficos que la galería pinta: la lista ``DATA`` de ``Reports/index.html``.

    ``None`` si no hay galería que leer. Es el inventario que ve el público; contar en otro sitio
    (el ``_gallery_items.json`` de Dengue antes de regenerarlo, o un 111 supuesto cuando faltaba)
    publicó 444 cuando la galería ya tenía 432.
    """
    index = (dashboard or _dashboard_dir()) / "Reports" / "index.html"
    if not index.is_file():
        return None
    m = _RE_DATA_GALERIA.search(index.read_text(encoding="utf-8"))
    if m is None:
        raise ValueError(f"{index} sin la línea `const DATA = [...]` de la galería")
    items: list[dict[str, str]] = json.loads(m.group(1))
    return items


@dataclass(frozen=True)
class CatalogCounts:
    """Conteos derivados del catálogo canónico (para tests y para el manifiesto web)."""

    production_series_count: int
    gallery_item_count: int | None
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
            "Se usa produccion_dengue.csv (99, la asignación autoritativa); el Dengue de "
            "tabla_333 es stale (Ensemble/Stacking no elegibles"
            + (", dup nacionales" if dup else "")
            + ")."
        ),
    }


def _gallery_item_count() -> int | None:
    """Gráficos publicados, contados en el inventario de la galería (``None`` si no hay)."""
    items = galeria_publicada()
    return None if items is None else len(items)


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
        gallery_item_count=_gallery_item_count(),
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
