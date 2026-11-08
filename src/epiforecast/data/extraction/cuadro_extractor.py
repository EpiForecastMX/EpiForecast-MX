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
import pandas as pd
from pypdf import PdfReader

from epiforecast import registry
from epiforecast.data.extraction.dengue_extractor import (
    _restrict_to_states,
    _year_week_from_filename,
)
from epiforecast.data.extraction.pdf_extractor import (
    build_column_map,
    clean_df,
    normalize_number,
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


def source_exclusion(
    spec: dict[str, Any], filename: str, disease_id: str
) -> dict[str, Any] | None:
    """Entrada de ``source_exclusions`` si el boletín es errata de fuente para el padecimiento."""
    for exc in spec.get("source_exclusions") or []:
        if exc["file"] == filename and disease_id in exc["diseases"]:
            return cast("dict[str, Any]", exc)
    return None


def alinea_renglones(df: pd.DataFrame) -> pd.DataFrame:
    """Une el renglón de valores con el nombre de la entidad cuando camelot los separa.

    En 68 boletines de 2014-2015 cada entidad sale en dos renglones: los valores sin nombre y,
    debajo, el nombre sin valores. Sin esto, ``reshape`` los lee como ceros con estado ``ok``.
    Sólo actúa sobre ese patrón exacto; cualquier otra tabla pasa igual.
    """
    filas = df.astype(str).to_numpy(copy=True)
    vacio = filas[:, 1:] == ""
    for i in range(1, len(filas)):
        con_nombre = filas[i, 0].strip() != "" and bool(vacio[i].all())
        previa_sin_nombre = filas[i - 1, 0].strip() == "" and not bool(vacio[i - 1].all())
        if con_nombre and previa_sin_nombre:
            filas[i, 1:] = filas[i - 1, 1:]
            filas[i - 1, 1:] = ""
            vacio[i - 1] = True
            vacio[i] = False
    return pd.DataFrame(filas, index=df.index, columns=df.columns)


def sin_llamadas(df: pd.DataFrame) -> pd.DataFrame:
    """Quita las llamadas de nota (``*``, ``§``) al final del nombre de la entidad.

    En 2014_sem28-31 el Cuadro 5.1 imprime «Michoacán *» por una fe de erratas: sin esto la
    entidad no se reconoce y el boletín queda con 31 estados aunque el PDF trae las 32 filas.
    """
    df = df.copy()
    df[df.columns[0]] = df[df.columns[0]].astype(str).str.replace(r"[\s*§]+$", "", regex=True)
    return df


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

    excluded = source_exclusion(spec, Path(pdf_path).name, disease_id)
    if excluded is not None:
        out["reason"] = f"excluido: {excluded['reason']}"
        out["excluded"] = True
        out["keep_period"] = bool(excluded.get("keep_period", False))
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
    df_clean = _restrict_to_states(sin_llamadas(clean_df(alinea_renglones(df_raw))))

    # Cuadro cuyo bloque objetivo es el primero o el último y comparte página con bloques de
    # otro ancho o en otro número según el año: se recorta por el conteo real de columnas.
    for clave, al_final in (("first_block_columns", False), ("last_block_columns", True)):
        anchos = spec.get(clave)
        if not anchos:
            continue
        total = df_clean.shape[1] - 1
        width = anchos.get(total)
        if width is None:
            out["reason"] = f"columnas inesperadas: {total} (esperaba {sorted(anchos)})"
            return out
        inicio = total + 1 - width if al_final else 1
        df_clean = df_clean.iloc[:, [0, *range(inicio, inicio + width)]]
        df_clean = df_clean.set_axis(list(range(width + 1)), axis=1)

    keywords = [d["keyword"] for d in spec["diseases"]]
    n_dis = len(keywords)
    data_cols = df_clean.shape[1] - 1
    if not registry.require(disease_id).sex_breakdown:
        return _sin_sexo(out, df_clean, spec, disease_id, year, week)
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


def _sin_sexo(
    out: dict[str, Any],
    df_clean: pd.DataFrame,
    spec: dict[str, Any],
    disease_id: str,
    year: int,
    week: int,
) -> dict[str, Any]:
    """Bloque sin desglose por sexo: Sem, acumulado del año y acumulado del anterior."""
    if df_clean.shape[1] - 1 != 3:
        out["reason"] = f"columnas inesperadas: {df_clean.shape[1] - 1} (esperaba 3, sin sexo)"
        return out
    out["layout"] = "3col_total"
    df_dis = pd.DataFrame(
        {
            "Anio": year,
            "Semana": f"{week:02d}",
            "Entidad": df_clean[0].to_numpy(),
            "Padecimiento": registry.require(disease_id).data_name,
            "Casos_semana": [normalize_number(v) for v in df_clean[1]],
            "Acumulado_total": [normalize_number(v) for v in df_clean[2]],
            "Acumulado_anio_anterior": [normalize_number(v) for v in df_clean[3]],
        }
    )
    n_states = int(df_dis["Entidad"].nunique())
    out["df"] = df_dis.reset_index(drop=True)
    out["n_states"] = n_states
    out["valid"] = n_states == int(spec.get("n_states_expected", 32))
    out["reason"] = "ok" if out["valid"] else f"{n_states} estados (esperaba 32)"
    return out
