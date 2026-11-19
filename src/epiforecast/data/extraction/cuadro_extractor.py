"""Extractor genérico por grupo de cuadro (``config/data/cuadros.yaml``); el conteo real de
columnas fija el layout. Reutiliza ``pdf_extractor`` y ``dengue_extractor``."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any, cast

import camelot
from omegaconf import OmegaConf
import pandas as pd
from pypdf import PdfReader

from epiforecast import registry
from epiforecast.data.extraction.cuadro_capa_texto import (
    MOTIVO_SIN_PREV_TEXTO,
    recorta_bloque_interno,
    reintenta_row_tol_si_vacia,
)
from epiforecast.data.extraction.cuadro_estadios import suma_estadios
from epiforecast.data.extraction.cuadro_reparacion_serie import exclusion_por_inicio
from epiforecast.data.extraction.cuadro_reparaciones import (
    alinea_renglones,
    alinea_valor_en_nombre,
    despega_primera_columna,
    fila_total,
    motivo_ambiguo,
    opciones_tabla,
    primer_bloque_por_orden,
    sin_llamadas,
    spec_del_periodo,
)
from epiforecast.data.extraction.cuadro_sin_sexo import extrae_sin_sexo as _sin_sexo
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


def source_exclusion(
    spec: dict[str, Any], filename: str, disease_id: str
) -> dict[str, Any] | None:
    """Entrada de ``source_exclusions`` (errata de fuente) o de ``inicio_serie`` del padecimiento."""
    for exc in spec.get("source_exclusions") or []:
        if exc["file"] == filename and disease_id in exc["diseases"]:
            return cast("dict[str, Any]", exc)
    return exclusion_por_inicio(spec, filename, disease_id)


def find_cuadro_page(pdf_path: str, anchors: list[str], state_markers: list[str]) -> int | None:
    """Página (1-based) que contiene TODAS las anclas y los marcadores de estado."""
    reader = PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        low = (page.extract_text() or "").lower()
        if all(a in low for a in anchors) and all(m in low for m in state_markers):
            return i + 1
    return None


def _area_pagina(pdf_path: str, page: int) -> str | None:
    """Área de camelot (``x1,y1,x2,y2``) que cubre la página completa, o None si no se lee."""
    try:
        caja = PdfReader(pdf_path).pages[page - 1].mediabox
    except Exception:  # noqa: BLE001 - un PDF ilegible deja la lectura como estaba
        return None
    return f"0,{float(caja.height)},{float(caja.width)},0"


def _tabla_estatal(
    pdf_path: str,
    page: int,
    *,
    despegar: bool = False,
    valor_en_nombre: bool = False,
    parciales: bool = False,
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
    return _restrict_to_states(sin_llamadas(clean_df(alinea_renglones(df_raw, parciales))))


def extract_cuadro_from_pdf(pdf_path: str, group_id: str, disease_id: str) -> dict[str, Any]:
    """Extrae el bloque de un padecimiento del cuadro de un boletín. Devuelve un dict con ``df``
    (largo, 8 col del consolidado, o None), ``page``, ``year``, ``week``, ``n_states``, ``layout``,
    ``valid`` y ``reason``. Renglones partidos ambiguos en el bloque propio invalidan la tabla."""
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
    spec = load_group(group_id)
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

    tabla = partial(_tabla_estatal, **opciones_tabla(spec))
    df_clean = tabla(pdf_path, page)
    if df_clean is None:
        out["reason"] = "camelot no detectó tabla"
        return out
    esperados = int(spec.get("n_states_expected", 32))
    if len(df_clean) < esperados:
        # Margen amplio de borde sólo cuando faltan entidades: una lectura válida no cambia.
        amplia = tabla(pdf_path, page, edge_tol=500)
        if amplia is not None and len(amplia) == esperados:
            df_clean = amplia
    area = _area_pagina(pdf_path, page) if len(df_clean) < esperados else None
    if area is not None and len(df_clean) < esperados:
        # Área de página completa cuando camelot recorta la primera entidad (2024_sem09, 3.5).
        completa = tabla(pdf_path, page, table_areas=[area])
        if completa is not None and len(completa) == esperados:
            df_clean = completa
    bloque_posterior = bool(spec.get("last_block_columns") or spec.get("inner_block_columns"))
    if len(df_clean) < esperados and bloque_posterior and not spec.get("first_block_columns"):
        despegada = tabla(pdf_path, page, despegar=True)
        if despegada is not None and len(despegada) == esperados:
            df_clean = despegada
    if spec.get("reintento_row_tol") is not None:
        reparada_rt, etiqueta_rt, motivo_rt = reintenta_row_tol_si_vacia(
            df_clean, pdf_path, page, spec, tabla_fn=tabla, area_fn=_area_pagina
        )
        if reparada_rt is None:
            out["reason"] = motivo_rt
            return out
        df_clean = reparada_rt
        if etiqueta_rt:
            out["reparacion"] = etiqueta_rt

    # Opt-in (``primer_bloque_por_orden: {total: [columnas, ancho]}``): validado contra TOTAL.
    orden = (spec.get("primer_bloque_por_orden") or {}).get(df_clean.shape[1] - 1)
    if orden is not None:
        tablas = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream")
        impreso = fila_total(max((t.df for t in tablas), key=len)) if tablas else None
        reparada, motivo = primer_bloque_por_orden(df_clean, impreso, *(int(v) for v in orden))
        if reparada is None:
            out["reason"] = motivo
            return out
        df_clean, out["reparacion"] = reparada, "primer_bloque_por_orden"

    # Primer o último bloque con vecinos de ancho variable: recorte por conteo real de columnas.
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

    # Bloque intermedio: ``[columnas desde el final, ancho]`` o recorte 3col sin prev en texto.
    if spec.get("inner_block_columns"):
        recortada_in, etiqueta_in, motivo_in = recorta_bloque_interno(
            df_clean, pdf_path, page, spec, esperados=esperados, area_fn=_area_pagina
        )
        if recortada_in is None:
            out["reason"] = motivo_in
            return out
        df_clean = recortada_in
        if etiqueta_in:
            out["reparacion"] = etiqueta_in

    if (ambiguo := motivo_ambiguo(df_clean)) is not None:
        out["reason"] = ambiguo
        return out
    if (df_clean := suma_estadios(df_clean, pdf_path, page, spec, out)) is None:
        return out
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
    if out["valid"] and out.get("reparacion") == "sin_prev_en_capa_texto":
        out["reason"] = MOTIVO_SIN_PREV_TEXTO
    elif out["valid"] and out.get("reparacion"):
        out["reason"] = f"ok; reparación {out['reparacion']} (cuadra con el TOTAL impreso)"
    return out
