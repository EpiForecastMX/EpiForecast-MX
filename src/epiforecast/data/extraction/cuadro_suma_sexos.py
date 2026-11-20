"""Bloque con acumulados por sexo leído sin sexo: suma H+M (opt-in por grupo o periodo).

El Cuadro 7.4 imprime el paludismo por P. vivax sin desglose por sexo hasta 2020 (``Sem.``,
acumulado del año y del anterior) y desde 2021_sem01 con ``Sem.``, acumulados de hombres y de
mujeres y año anterior. Para modelar la serie completa sin sexo, un grupo (o un periodo) que
declara ``suma_sexos: true`` convierte ese bloque de 4 columnas al esquema sin sexo de 3
columnas: ``Sem.``, acumulado total = hombres + mujeres y año anterior. Sólo vale para un
padecimiento con ``sex_breakdown: false``. Falla cerrado si el bloque no tiene 4 columnas, si una
celda está vacía o no es numérica (el PDF imprime «-» para cero: una celda vacía es una lectura
fallida, no un cero), si no se localiza el bloque en el renglón TOTAL impreso o si la suma de las
entidades no es ese TOTAL en cada una de las 4 columnas.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from epiforecast import registry
from epiforecast.data.extraction.cuadro_estadios import _entero, _total_impreso

ETIQUETA = "suma_sexos"
LAYOUT = "4col_suma_sexos"


def columnas_del_bloque(spec: dict[str, Any], ancho_tabla: int) -> list[int] | None:
    """Posiciones (0-based, sin la entidad) del bloque en una tabla de ``ancho_tabla`` columnas.

    Repite el recorte del extractor por conteo real: ``last_block_columns`` toma las últimas,
    ``first_block_columns`` las primeras y, sin ninguno, la tabla debe ser el bloque de 4.
    """
    for clave, al_final in (("first_block_columns", False), ("last_block_columns", True)):
        anchos = spec.get(clave)
        if anchos:
            width = anchos.get(ancho_tabla)
            if width is None:
                return None
            inicio = ancho_tabla - width if al_final else 0
            return list(range(inicio, inicio + width))
    if spec.get("inner_block_columns"):
        return None
    return list(range(ancho_tabla))


def convierte_suma_sexos(
    df: pd.DataFrame, total: list[str] | None
) -> tuple[pd.DataFrame | None, str]:
    """Bloque (entidad, Sem., H, M, año anterior) a (entidad, Sem., H+M, año anterior).

    ``total`` son las 4 celdas del bloque en el renglón TOTAL impreso. None y motivo si falla.
    """
    if df.shape[1] - 1 != 4:
        return None, f"suma_sexos: columnas inesperadas {df.shape[1] - 1} (esperaba 4)"
    celdas = [[_entero(v) for v in df.iloc[:, c]] for c in range(1, 5)]
    if any(v is None for col in celdas for v in col):
        return None, "suma_sexos: celda vacía o no numérica en el bloque"
    if total is None or len(total) != 4:
        return None, "suma_sexos: bloque ausente en el renglón TOTAL impreso"
    for c, col in enumerate(celdas, start=1):
        impreso = _entero(total[c - 1])
        if impreso is None or impreso != sum(v or 0 for v in col):
            return None, f"suma_sexos: la suma de entidades no es el TOTAL impreso (columna {c})"
    suma = [(h or 0) + (m or 0) for h, m in zip(celdas[1], celdas[2], strict=True)]
    salida = pd.DataFrame(
        {
            0: df.iloc[:, 0].to_numpy(),
            1: df.iloc[:, 1].to_numpy(),
            2: [str(v) for v in suma],
            3: df.iloc[:, 4].to_numpy(),
        }
    )
    return salida, ""


def suma_sexos(
    df: pd.DataFrame,
    pdf_path: str,
    page: int,
    spec: dict[str, Any],
    out: dict[str, Any],
    *,
    disease_id: str,
    ancho_tabla: int,
) -> pd.DataFrame | None:
    """``df`` intacta sin ``suma_sexos``; con él, el bloque convertido o None (motivo en ``out``).

    ``ancho_tabla`` es el conteo de columnas de la tabla antes de recortar el bloque.
    """
    if not spec.get("suma_sexos"):
        return df
    if registry.require(disease_id).sex_breakdown:
        out["reason"] = "suma_sexos: sólo para un padecimiento con sex_breakdown: false"
        return None
    posiciones = columnas_del_bloque(spec, ancho_tabla)
    if posiciones is None:
        out["reason"] = f"suma_sexos: no se localiza el bloque en {ancho_tabla} columnas"
        return None
    total = _total_impreso(pdf_path, page, out.get("reparacion"))
    bloque = (
        [total[i] for i in posiciones] if total is not None and len(total) == ancho_tabla else None
    )
    convertida, motivo = convierte_suma_sexos(df, bloque)
    if convertida is None:
        out["reason"] = motivo
        return None
    previa = out.get("reparacion")
    out["reparacion"] = f"{previa}+{ETIQUETA}" if previa else ETIQUETA
    return convertida


def marca_suma_sexos(out: dict[str, Any]) -> dict[str, Any]:
    """Rotula en el manifiesto una lectura válida convertida (layout y motivo); el resto, igual."""
    if out.get("valid") and ETIQUETA in str(out.get("reparacion") or "").split("+"):
        out["layout"] = LAYOUT
        out["reason"] = f"ok; reparación {out['reparacion']} (cuadra con el TOTAL impreso)"
    return out
