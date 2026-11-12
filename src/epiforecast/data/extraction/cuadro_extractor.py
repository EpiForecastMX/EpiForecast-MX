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
from epiforecast.data.extraction.cuadro_reparaciones import (
    alinea_renglones,
    alinea_valor_en_nombre,
    despega_primera_columna,
    sin_llamadas,
    spec_del_periodo,
)
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


def find_cuadro_page(pdf_path: str, anchors: list[str], state_markers: list[str]) -> int | None:
    """Página (1-based) que contiene TODAS las anclas y los marcadores de estado."""
    reader = PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        low = (page.extract_text() or "").lower()
        if all(a in low for a in anchors) and all(m in low for m in state_markers):
            return i + 1
    return None


def _tabla_estatal(
    pdf_path: str,
    page: int,
    *,
    despegar: bool = False,
    valor_en_nombre: bool = False,
    **kw: Any,
) -> pd.DataFrame | None:
    """Tabla estatal limpia de la página (la de más filas), o None si camelot no detecta tabla."""
    tables = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream", **kw)
    if not tables or len(tables) == 0:
        return None
    df_raw = max((t.df for t in tables), key=len)
    if despegar:
        df_raw = despega_primera_columna(df_raw)
    if valor_en_nombre:
        df_raw = alinea_valor_en_nombre(df_raw)
    return _restrict_to_states(sin_llamadas(clean_df(alinea_renglones(df_raw))))


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

    spec = spec_del_periodo(spec, year, week)
    page = find_cuadro_page(pdf_path, spec["page_anchors"], spec["state_markers"])
    out["page"] = page
    if page is None:
        out["reason"] = "página del cuadro no encontrada"
        return out

    vn = bool(spec.get("valor_en_columna_nombre"))
    df_clean = _tabla_estatal(pdf_path, page, valor_en_nombre=vn)
    if df_clean is None:
        out["reason"] = "camelot no detectó tabla"
        return out
    esperados = int(spec.get("n_states_expected", 32))
    if len(df_clean) < esperados:
        # En algunas páginas camelot parte la tabla y pierde renglones de estados; con un margen
        # de borde amplio la lee completa. Sólo se reintenta cuando faltan estados, así que las
        # extracciones que ya funcionaban no cambian.
        amplia = _tabla_estatal(pdf_path, page, valor_en_nombre=vn, edge_tol=500)
        if amplia is not None and len(amplia) == esperados:
            df_clean = amplia
    bloque_posterior = bool(spec.get("last_block_columns") or spec.get("inner_block_columns"))
    if len(df_clean) < esperados and bloque_posterior and not spec.get("first_block_columns"):
        # Primer valor pegado al nombre: sólo se repara si el bloque objetivo no lo contiene.
        despegada = _tabla_estatal(pdf_path, page, despegar=True, valor_en_nombre=vn)
        if despegada is not None and len(despegada) == esperados:
            df_clean = despegada

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

    # Bloque intermedio (ni primero ni último): por conteo real de columnas se declara
    # ``[columnas desde el final hasta su inicio, ancho]``. Falla cerrado ante otro ancho.
    internos = spec.get("inner_block_columns")
    if internos:
        total = df_clean.shape[1] - 1
        corte = internos.get(total)
        if corte is None:
            out["reason"] = f"columnas inesperadas: {total} (esperaba {sorted(internos)})"
            return out
        desde_el_final, width = (int(v) for v in corte)
        inicio = total + 1 - desde_el_final
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
    """Bloques sin desglose por sexo: Sem, acumulado del año y acumulado del anterior.

    El cuadro puede traer varios padecimientos sin sexo en bloques de 3 columnas; se toma el bloque
    del padecimiento por su ``block_index``. ``anchos_sin_sexo`` declara otros anchos por bloque
    (2 = Sem y acumulado, sin año anterior, como en los boletines de 2014 del Cuadro 13.5).
    """
    bloques = spec.get("diseases") or [{"id": disease_id, "block_index": 0}]
    anchos = [int(a) for a in spec.get("anchos_sin_sexo") or [3] * len(bloques)]
    if len(anchos) != len(bloques) or any(a not in (2, 3) for a in anchos):
        out["reason"] = f"anchos_sin_sexo inválidos: {anchos} para {len(bloques)} bloques"
        return out
    if df_clean.shape[1] - 1 != sum(anchos):
        out["reason"] = (
            f"columnas inesperadas: {df_clean.shape[1] - 1} (esperaba {sum(anchos)}, sin sexo)"
        )
        return out
    bloque = next((int(d["block_index"]) for d in bloques if d["id"] == disease_id), 0)
    inicio = 1 + sum(anchos[:bloque])
    ancho = anchos[bloque]
    anterior = (
        [normalize_number(v) for v in df_clean.iloc[:, inicio + 2]]
        if ancho == 3
        else [None] * len(df_clean)
    )
    out["layout"] = "3col_total" if ancho == 3 else "2col_total_noprev"
    df_dis = pd.DataFrame(
        {
            "Anio": year,
            "Semana": f"{week:02d}",
            "Entidad": df_clean.iloc[:, 0].to_numpy(),
            "Padecimiento": registry.require(disease_id).data_name,
            "Casos_semana": [normalize_number(v) for v in df_clean.iloc[:, inicio]],
            "Acumulado_total": [normalize_number(v) for v in df_clean.iloc[:, inicio + 1]],
            "Acumulado_anio_anterior": anterior,
        }
    )
    n_states = int(df_dis["Entidad"].nunique())
    out["df"] = df_dis.reset_index(drop=True)
    out["n_states"] = n_states
    out["valid"] = n_states == int(spec.get("n_states_expected", 32))
    out["reason"] = "ok" if out["valid"] else f"{n_states} estados (esperaba 32)"
    return out
