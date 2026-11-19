"""Bloque por estadios clínicos: suma de los estadios por sexo (opt-in por grupo de cuadro).

Desde 2020_sem28 el Cuadro 6.3 imprime la infección por VIH (B20-B24, Z21) como ``Sem.``, los
acumulados del año en pares H/M por estadio clínico (1 a 4) y el año anterior: hasta 2024 con dos
columnas (``Sem.`` y ``Acum.``) y desde 2025 sólo ``Acum.``. No hay acumulado por sexo impreso.
Un grupo que declara ``estadios_por_sexo: {estadios: N, anchos: [...]}`` convierte ese bloque al
esquema común de 4 columnas (``Sem.``, acumulado de hombres, de mujeres y año anterior), sumando
los estadios de cada sexo. Falla cerrado si el ancho no es uno de los declarados, si una celda de
``Sem.`` o de estadio está vacía o no es numérica (el PDF imprime «-» para cero: una celda vacía es
una lectura fallida, no un cero) o si la suma de las entidades no es el renglón TOTAL impreso en
``Sem.`` y en cada columna de estadio.
"""

from __future__ import annotations

from typing import Any

import camelot
import pandas as pd
from pypdf import PdfReader

from epiforecast.data.extraction.cuadro_reparaciones import fila_total
from epiforecast.data.extraction.pdf_extractor import normalize_number

ETIQUETA = "suma_estadios"


def _entero(valor: Any) -> int | None:
    """Entero de la celda; None si está vacía (el PDF imprime «-» para cero) o no es numérica."""
    if str(valor).strip() == "":
        return None
    numero = normalize_number(valor)
    return None if numero is pd.NA else int(numero)


def _total_impreso(pdf_path: str, page: int, reparacion: str | None) -> list[str] | None:
    """Celdas del TOTAL con la lectura que dio la tabla (``row_tol`` del reintento, si lo hubo).

    Si el renglón no sale con la página detectada, reintenta con el área de la página completa.
    """
    kw: dict[str, Any] = {}
    if reparacion and reparacion.startswith("row_tol="):
        kw["row_tol"] = int(reparacion.removeprefix("row_tol="))
    intentos = [kw]
    try:
        caja = PdfReader(pdf_path).pages[page - 1].mediabox
        intentos.append({**kw, "table_areas": [f"0,{float(caja.height)},{float(caja.width)},0"]})
    except Exception:  # noqa: BLE001 - un PDF ilegible deja sólo la primera lectura
        pass
    for params in intentos:
        tablas = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream", **params)
        total = fila_total(max((t.df for t in tablas), key=len)) if tablas else None
        if total is not None and any(str(v).strip() for v in total):
            return total
    return None


def convierte_estadios(
    df: pd.DataFrame, total: list[str] | None, estadios: int, anchos: list[int]
) -> tuple[pd.DataFrame | None, str]:
    """Bloque por estadios a 4 columnas (Sem., hombres, mujeres, año anterior), o None y motivo.

    Columnas de ``df``: entidad, ``Sem.``, ``2 * estadios`` columnas en pares (hombres, mujeres)
    y, al final, el acumulado del año anterior; entre ambos puede ir el ``Sem.`` del año anterior,
    que se descarta. ``total`` son las celdas del renglón TOTAL con las mismas columnas.
    """
    ancho = df.shape[1] - 1
    if ancho not in anchos or ancho < 2 + 2 * estadios:
        return None, f"estadios: columnas inesperadas {ancho} (esperaba {sorted(anchos)})"
    columnas = range(1, 2 + 2 * estadios)
    celdas = [[_entero(v) for v in df.iloc[:, c]] for c in columnas]
    if any(v is None for col in celdas for v in col):
        return None, "estadios: celda no numérica en Sem. o en un estadio"
    if total is None or len(total) != ancho:
        return None, "estadios: renglón TOTAL impreso ausente o de otro ancho"
    for c, col in zip(columnas, celdas, strict=True):
        if _entero(total[c - 1]) != sum(v or 0 for v in col):
            return None, f"estadios: la suma de entidades no es el TOTAL impreso (columna {c})"
    hombres = [
        sum(celdas[i][r] or 0 for i in range(1, 1 + 2 * estadios, 2)) for r in range(len(df))
    ]
    mujeres = [
        sum(celdas[i][r] or 0 for i in range(2, 2 + 2 * estadios, 2)) for r in range(len(df))
    ]
    salida = pd.DataFrame(
        {
            0: df.iloc[:, 0].to_numpy(),
            1: df.iloc[:, 1].to_numpy(),
            2: [str(v) for v in hombres],
            3: [str(v) for v in mujeres],
            4: df.iloc[:, ancho].to_numpy(),
        }
    )
    return salida, ""


def suma_estadios(
    df: pd.DataFrame, pdf_path: str, page: int, spec: dict[str, Any], out: dict[str, Any]
) -> pd.DataFrame | None:
    """``df`` intacta sin ``estadios_por_sexo``; con él, el bloque convertido o None (``out``)."""
    conf = spec.get("estadios_por_sexo")
    if not conf:
        return df
    convertida, motivo = convierte_estadios(
        df,
        _total_impreso(pdf_path, page, out.get("reparacion")),
        int(conf["estadios"]),
        [int(a) for a in conf["anchos"]],
    )
    if convertida is None:
        out["reason"] = motivo
        return None
    previa = out.get("reparacion")
    out["reparacion"] = f"{previa}+{ETIQUETA}" if previa else ETIQUETA
    return convertida
