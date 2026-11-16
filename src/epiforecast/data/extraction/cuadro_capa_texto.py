"""Reparaciones opt-in de layout y capa de texto para cuadros con renglones partidos o celdas en imagen.

Cubre dos defectos medidos en PDFs del boletín SINAVE (2025-2026, Cuadro 6):
1. ``reintento_row_tol``: con ``row_tol=2`` por omisión, Camelot separa los valores numéricos y el
   nombre de la entidad en dos renglones y deja las 32 entidades con todas las celdas vacías; al
   reintentar con ``row_tol`` explícito (p. ej. 4) se recuperan las 32 filas completas y se valida
   la suma estatal de todas las columnas contra la fila ``TOTAL`` impresa.
2. ``bloque_sin_prev_en_capa_texto``: en 12 boletines de 2025-2026 la columna ``Acum.`` del año
   anterior del bloque central está impresa como imágenes rasterizadas sin glifos en la capa de
   texto del PDF. Se verifica de forma cerrada la cuadratura de las 11 columnas de texto contra el
   ``TOTAL`` impreso y la presencia geométrica de las imágenes en esa banda antes de recortar las
   3 columnas con texto (``Sem, H, M``) bajo el contrato ``3col_noprev`` (``NA`` explícito).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import camelot
import pandas as pd
import pdfplumber

from epiforecast.data.extraction.cuadro_reparaciones import fila_total
from epiforecast.data.extraction.pdf_extractor import normalize_number

MOTIVO_SIN_PREV_TEXTO = (
    "ok; limitación capa de texto: Acumulado_anio_anterior impreso como imagen queda NA "
    "(11 col texto cuadran con el TOTAL impreso)"
)


def tiene_fila_estatal_vacia(df_clean: pd.DataFrame) -> bool:
    """True si la tabla carece de columnas de datos o alguna entidad tiene todas sus celdas vacías."""
    if df_clean.empty or df_clean.shape[1] < 2:
        return True
    vacias = df_clean.iloc[:, 1:].astype(str).apply(lambda col: col.str.strip().eq(""))
    return bool(vacias.all(axis=1).any())


def tiene_celda_vacia(df_clean: pd.DataFrame) -> bool:
    """True si alguna celda de datos está vacía ('') en lugar de guion o entero."""
    if df_clean.empty or df_clean.shape[1] < 2:
        return True
    vacias = df_clean.iloc[:, 1:].astype(str).apply(lambda col: col.str.strip().eq(""))
    return bool(vacias.any().any())


def total_impreso_pagina(
    pdf_path: str,
    page: int,
    *,
    row_tol: int | None = None,
    area_fn: Callable[[str, int], str | None],
) -> list[int] | None:
    """Enteros de la fila TOTAL impresa en la página (reintenta con área completa si queda fuera)."""
    kw: dict[str, Any] = {"row_tol": row_tol} if row_tol is not None else {}
    intentos: list[dict[str, Any]] = [kw]
    area = area_fn(pdf_path, page)
    if area is not None:
        intentos.append({**kw, "table_areas": [area]})

    for params in intentos:
        tablas = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream", **params)
        if not tablas:
            continue
        crudo = fila_total(max((t.df for t in tablas), key=len))
        if crudo is None:
            continue
        convertidos = [normalize_number(v) for v in crudo]
        if any(pd.isna(v) for v in convertidos):
            continue
        return [int(v) for v in convertidos]
    return None


def suma_columnas_cuadra_con_total(
    df_clean: pd.DataFrame, total_ints: list[int] | None
) -> tuple[bool, str]:
    """Comprueba que las 32 entidades tengan valores enteros/guion y sumen el TOTAL en cada columna."""
    n_cols = df_clean.shape[1] - 1
    if total_ints is None or len(total_ints) != n_cols:
        return False, f"TOTAL impreso ausente o con ancho distinto de {n_cols}"
    sumas: list[int] = []
    for col_idx in range(1, df_clean.shape[1]):
        norm_col = [normalize_number(v) for v in df_clean.iloc[:, col_idx]]
        if any(pd.isna(v) for v in norm_col):
            return False, f"celda no numérica en columna {col_idx} al validar contra TOTAL"
        sumas.append(sum(int(v) for v in norm_col))
    if sumas != total_ints:
        return False, f"suma estatal {sumas} distinta del TOTAL impreso {total_ints}"
    return True, "ok"


def verifica_columna_prev_en_imagen(
    pdf_path: str, page: int, *, esperados: int = 32
) -> tuple[bool, str]:
    """Verifica geométricamente que la 12ª columna faltante en texto sea Acum. prev del bloque central."""
    with pdfplumber.open(pdf_path) as pdf:
        if page < 1 or page > len(pdf.pages):
            return False, "página fuera de rango en geometría PDF"
        p = pdf.pages[page - 1]
        words = p.extract_words(x_tolerance=2, y_tolerance=2)
        ags = [w for w in words if str(w["text"]).startswith("Aguascalientes")]
        tot_w = [w for w in words if str(w["text"]).upper() == "TOTAL"]
        if not ags or not tot_w:
            return False, "sin fila Aguascalientes o TOTAL en capa de texto para validar geometría"
        y_ags = float(ags[0]["top"])
        y_tot = float(tot_w[-1]["top"])

        hdr = [w for w in words if y_ags - 65.0 <= float(w["top"]) < y_ags - 2.0]
        sem_h = sorted(
            (w for w in hdr if str(w["text"]).rstrip(".*§") == "Sem"),
            key=lambda w: float(w["x0"]),
        )
        h_h = sorted(
            (w for w in hdr if str(w["text"]).rstrip(".*§") == "H"),
            key=lambda w: float(w["x0"]),
        )
        m_h = sorted(
            (w for w in hdr if str(w["text"]).rstrip(".*§") == "M"),
            key=lambda w: float(w["x0"]),
        )
        if len(sem_h) != 3 or len(h_h) != 3 or len(m_h) != 3:
            return False, "encabezados Sem/H/M de los 3 bloques incompletos en capa de texto"

        x_izq = float(m_h[1]["x1"])
        x_der = float(sem_h[2]["x0"])
        if x_der - x_izq < 25.0:
            return False, "sin banda horizontal para Acum. año anterior del bloque central"

        y_sem = float(sem_h[1]["top"])
        acum_baja = [
            w
            for w in hdr
            if str(w["text"]).startswith("Acum") and abs(float(w["top"]) - y_sem) <= 6.0
        ]
        hay_acum_izq = any(
            float(m_h[0]["x1"]) <= float(w["x0"]) < float(sem_h[1]["x0"]) for w in acum_baja
        )
        hay_acum_cen = any(x_izq <= float(w["x0"]) < x_der for w in acum_baja)
        hay_acum_der = any(float(m_h[2]["x1"]) <= float(w["x0"]) for w in acum_baja)
        if not hay_acum_izq or hay_acum_cen or not hay_acum_der:
            return False, "patrón de encabezados Acum. no corresponde a omisión exclusiva central"

        body_imgs = [
            im for im in p.images if y_ags - 5.0 <= float(im.get("top", 0.0)) <= y_tot + 5.0
        ]
        en_banda = [
            im for im in body_imgs if x_izq < 0.5 * (float(im["x0"]) + float(im["x1"])) < x_der
        ]
        if len(en_banda) < esperados or len(en_banda) != len(body_imgs):
            return (
                False,
                f"imágenes de celda en banda central={len(en_banda)} (total cuerpo={len(body_imgs)})",
            )

        palabras_en_hueco = [
            w
            for w in words
            if y_ags - 2.0 <= float(w["top"]) <= y_tot + 4.0
            and (x_izq + 10.0) < 0.5 * (float(w["x0"]) + float(w["x1"])) < (x_der - 2.0)
        ]
        if palabras_en_hueco:
            return False, "existen tokens de texto dentro de la banda declarada como imagen"
    return True, "ok"


def reintenta_row_tol_si_vacia(
    df_clean: pd.DataFrame,
    pdf_path: str,
    page: int,
    spec: dict[str, Any],
    *,
    tabla_fn: Callable[..., pd.DataFrame | None],
    area_fn: Callable[[str, int], str | None],
) -> tuple[pd.DataFrame | None, str | None, str]:
    """Reintenta con ``reintento_row_tol`` sólo si faltan estados o quedan filas estatales vacías."""
    esperados = int(spec.get("n_states_expected", 32))
    if len(df_clean) == esperados and not tiene_fila_estatal_vacia(df_clean):
        return df_clean, None, "ok"

    rt = int(spec["reintento_row_tol"])
    vn = bool(spec.get("valor_en_columna_nombre"))
    candidata = tabla_fn(pdf_path, page, valor_en_nombre=vn, row_tol=rt)
    if candidata is None or len(candidata) != esperados or tiene_fila_estatal_vacia(candidata):
        return None, None, f"filas estatales sin valores o incompletas aun con row_tol={rt}"

    sin_prev_cfg = spec.get("bloque_sin_prev_en_capa_texto") or {}
    if (candidata.shape[1] - 1) not in sin_prev_cfg:
        tot = total_impreso_pagina(pdf_path, page, row_tol=rt, area_fn=area_fn)
        ok_tot, motivo = suma_columnas_cuadra_con_total(candidata, tot)
        if not ok_tot:
            return None, None, f"reparación row_tol={rt}: {motivo}"
    return candidata, f"row_tol={rt}", "ok"


def recorta_bloque_sin_prev_en_texto(
    df_clean: pd.DataFrame,
    pdf_path: str,
    page: int,
    reparto: list[int],
    *,
    esperados: int = 32,
    row_tol: int | None = None,
    area_fn: Callable[[str, int], str | None],
) -> tuple[pd.DataFrame | None, str]:
    """Valida TOTAL (11 col) y geometría de imagen antes de recortar las 3 columnas de texto."""
    if len(reparto) != 3:
        return None, f"bloque_sin_prev_en_capa_texto inválido: {reparto}"
    izq, propio, der = (int(v) for v in reparto)
    total = df_clean.shape[1] - 1
    if propio != 3 or izq + propio + der != total:
        return None, f"reparto {reparto} incompatible con {total} columnas"
    if (
        len(df_clean) != esperados
        or tiene_fila_estatal_vacia(df_clean)
        or tiene_celda_vacia(df_clean)
    ):
        return None, "tabla con celdas o filas vacías no admisible para recorte de 3 columnas"

    tot = total_impreso_pagina(pdf_path, page, row_tol=row_tol, area_fn=area_fn)
    ok_tot, motivo_tot = suma_columnas_cuadra_con_total(df_clean, tot)
    if not ok_tot:
        return None, f"sin_prev_en_capa_texto: {motivo_tot}"

    ok_geo, motivo_geo = verifica_columna_prev_en_imagen(pdf_path, page, esperados=esperados)
    if not ok_geo:
        return None, f"sin_prev_en_capa_texto: {motivo_geo}"

    inicio = 1 + izq
    recortada = df_clean.iloc[:, [0, *range(inicio, inicio + propio)]]
    return recortada.set_axis(list(range(propio + 1)), axis=1), "ok"


def recorta_bloque_interno(
    df_clean: pd.DataFrame,
    pdf_path: str,
    page: int,
    spec: dict[str, Any],
    *,
    esperados: int,
    area_fn: Callable[[str, int], str | None],
) -> tuple[pd.DataFrame | None, str | None, str]:
    """Recorta ``inner_block_columns`` o delega al recorte opt-in sin prev en capa de texto."""
    internos = spec["inner_block_columns"]
    total = df_clean.shape[1] - 1
    corte = internos.get(total)
    if corte is not None:
        desde_el_final, width = (int(v) for v in corte)
        inicio = total + 1 - desde_el_final
        recortada = df_clean.iloc[:, [0, *range(inicio, inicio + width)]]
        return recortada.set_axis(list(range(width + 1)), axis=1), None, "ok"

    sin_prev = (spec.get("bloque_sin_prev_en_capa_texto") or {}).get(total)
    if sin_prev is None:
        return None, None, f"columnas inesperadas: {total} (esperaba {sorted(internos)})"

    rt_opt = int(spec["reintento_row_tol"]) if spec.get("reintento_row_tol") else None
    recortada_sp, motivo_sp = recorta_bloque_sin_prev_en_texto(
        df_clean,
        pdf_path,
        page,
        list(sin_prev),
        esperados=esperados,
        row_tol=rt_opt,
        area_fn=area_fn,
    )
    if recortada_sp is None:
        return None, None, motivo_sp
    return recortada_sp, "sin_prev_en_capa_texto", "ok"
