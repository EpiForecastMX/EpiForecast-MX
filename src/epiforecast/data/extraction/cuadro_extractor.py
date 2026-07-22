"""Extractor genérico por 'grupo de cuadro' (EPIC 2).

Generaliza el extractor de Dengue a cualquier cuadro del boletín descrito en
``config/data/cuadros.yaml``. Reutiliza la maquinaria neuro (``pdf_extractor``:
clean/pad/reshape/build_column_map) y la canonicalización de entidad de
``dengue_extractor`` (``_restrict_to_states``, ``_year_week_from_filename``).

El cuadro puede alojar varios padecimientos lado a lado (Obesidad + Anorexia F50); se
extraen todos los bloques con el layout compartido y se filtra al padecimiento objetivo.
El conteo REAL de columnas (camelot) determina la variante de layout (3col vs 4col), no
el año — más robusto que la heurística de texto.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import camelot
from omegaconf import OmegaConf
from pypdf import PdfReader

from epiforecast import registry
from epiforecast.data.extraction.dengue_extractor import (
    _restrict_to_states,
    _year_week_from_filename,
)
from epiforecast.data.extraction.pdf_extractor import (
    build_column_map,
    clean_df,
    pad_prev_year_cols,
    reshape,
)


def _cuadros_path() -> Path:
    packaged = Path(__file__).resolve().parents[3] / "config" / "data" / "cuadros.yaml"
    return packaged if packaged.exists() else Path("config/data/cuadros.yaml")


def load_group(group_id: str) -> dict[str, Any]:
    raw = cast(
        "dict[str, Any]", OmegaConf.to_container(OmegaConf.load(_cuadros_path()), resolve=True)
    )
    groups = raw.get("cuadro_groups", {})
    if group_id not in groups:
        raise KeyError(f"grupo de cuadro desconocido: {group_id}")
    return cast("dict[str, Any]", groups[group_id])


def find_cuadro_page(pdf_path: str, anchors: list[str], state_markers: list[str]) -> int | None:
    """Página (1-based) que contiene TODAS las anclas y los marcadores de estado."""
    reader = PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        low = (page.extract_text() or "").lower()
        if all(a in low for a in anchors) and all(m in low for m in state_markers):
            return i + 1
    return None


def extract_cuadro_from_pdf(pdf_path: str, group_id: str, disease_id: str) -> dict[str, Any]:
    """Extrae el bloque de un padecimiento del cuadro de un boletín.

    Returns dict: ``df`` (largo, 8 col del consolidado, o None), ``page``, ``year``,
    ``week``, ``n_states``, ``layout``, ``valid``, ``reason``.
    """
    spec = load_group(group_id)
    year, week = _year_week_from_filename(pdf_path)
    out: dict[str, Any] = {
        "df": None,
        "page": None,
        "year": year,
        "week": week,
        "n_states": 0,
        "layout": None,
        "valid": False,
        "reason": "",
    }
    if year is None or week is None:
        out["reason"] = "sin año/semana en filename"
        return out

    page = find_cuadro_page(pdf_path, spec["page_anchors"], spec["state_markers"])
    out["page"] = page
    if page is None:
        out["reason"] = "página del cuadro no encontrada"
        return out

    tables = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream")
    if not tables or len(tables) == 0:
        out["reason"] = "camelot no detectó tabla"
        return out
    # La tabla estatal es la de más filas.
    df_raw = max((t.df for t in tables), key=len)
    df_clean = _restrict_to_states(clean_df(df_raw))

    keywords = [d["keyword"] for d in spec["diseases"]]
    n_dis = len(keywords)
    data_cols = df_clean.shape[1] - 1
    if data_cols == n_dis * 3:
        df_clean = pad_prev_year_cols(df_clean, keywords)
        out["layout"] = "3col_noprev"
    elif data_cols == n_dis * 4:
        out["layout"] = "4col_prev"
    else:
        out["reason"] = f"columnas inesperadas: {data_cols} (esperaba {n_dis * 3} o {n_dis * 4})"
        return out

    col_map = build_column_map(keywords, start_col=1, step=4)
    df_long = reshape(df_clean, year, week, col_map)

    target = next(d for d in spec["diseases"] if d["id"] == disease_id)
    target_name = registry.require(disease_id).data_name
    df_dis = df_long[df_long["Padecimiento"] == target["keyword"]].copy()
    df_dis["Padecimiento"] = target_name

    n_states = int(df_dis["Entidad"].nunique())
    out["df"] = df_dis.reset_index(drop=True)
    out["n_states"] = n_states
    out["valid"] = n_states == int(spec.get("n_states_expected", 32))
    out["reason"] = "ok" if out["valid"] else f"{n_states} estados (esperaba 32)"
    return out
