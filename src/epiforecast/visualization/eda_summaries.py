"""Standalone EDA summary functions (extracted from EDAReportBuilder — SRP)."""

from datetime import datetime
from typing import Any

from loguru import logger
import pandas as pd

_PCT = 100


# ── Resúmenes ─────────────────────────────────────────────────────────────────


def resumen_general(
    df: pd.DataFrame, fuente_datos: str, opciones: dict[str, Any]
) -> dict[str, str]:
    """Genera diccionario con metadatos generales del DataFrame: filas, columnas, nulos."""
    logger.debug("Generando resumen general de los datos...")

    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
    fuente = fuente_datos if fuente_datos else "Desconocida"
    filas = f"{len(df):,}"
    columnas = f"{df.shape[1]:,}"
    porcentaje_nulos = f"{df.isna().mean().mean() * _PCT:.2f}%"
    columnas_numericas = len(opciones["COLS_NUMERICAS"])
    columnas_categoricas = len(opciones["COLS_CATEGORICAS"])
    otros_columnas = df.shape[1] - (columnas_numericas + columnas_categoricas)

    logger.debug(
        f"Resumen del DataFrame : fecha= {fecha_actual} | fuente= {fuente} | "
        f"filas= {filas} | columnas= {columnas} | porcentaje_nulos= {porcentaje_nulos}"
    )
    logger.debug(
        f"Tipos de columnas : numéricas= {columnas_numericas} | "
        f"categóricas= {columnas_categoricas} | otras= {otros_columnas}"
    )

    return {
        "Fecha de EDA": fecha_actual,
        "Padecimiento": opciones["filtro_padecimiento"],
        "Fuente": fuente,
        "Filas": filas,
        "Columnas": columnas,
        "Columnas numéricas": f"{columnas_numericas}",
        "Columnas categóricas": f"{columnas_categoricas}",
        "Otras columnas": f"{otros_columnas}",
        "Porcentaje de nulos": porcentaje_nulos,
    }


def resumen_unicos(df: pd.DataFrame) -> pd.DataFrame:
    """Genera DataFrame con conteo de valores únicos y tipo por columna."""
    logger.debug("Generando resumen de valores únicos por columna...")

    df_unicos = (
        df.nunique(dropna=True)
        .to_frame("Valores únicos")
        .assign(Tipo=df.dtypes.astype(str))
        .query("`Valores únicos` > 0")
        .sort_values("Valores únicos", ascending=False)
    )

    logger.debug(
        f"Dataframe de valores únicos generado | filas = {len(df_unicos):,} "
        f"| columnas = {df_unicos.shape[1]:,}"
    )
    return df_unicos


def resumen_nulos(df: pd.DataFrame) -> pd.DataFrame | None:
    """Genera DataFrame con conteo de valores nulos por columna, o None si no hay nulos."""
    logger.debug("Generando resumen de valores nulos por columna...")

    df_nulos = (
        df.isna()
        .sum()
        .to_frame("Nulos")
        .assign(Tipo=df.dtypes.astype(str))
        .query("Nulos > 0")
        .sort_values("Nulos", ascending=False)
    )

    logger.debug(
        f"Dataframe de valores nulos generado | filas = {len(df_nulos):,} "
        f"| columnas = {df_nulos.shape[1]:,}"
    )
    return df_nulos if not df_nulos.empty else None


# ── Estadísticas ──────────────────────────────────────────────────────────────


def estadisticas_numericas(df: pd.DataFrame) -> pd.DataFrame | None:
    """Genera tabla describe() transpuesta de columnas numéricas, o None si no hay."""
    logger.debug("Generando estadísticas de columnas numéricas...")

    num = df.select_dtypes(include="number")
    if num.empty:
        return None

    stats = (
        num.describe()
        .T.rename(
            columns={
                "count": "conteo",
                "mean": "media",
                "std": "desv_est",
                "min": "mín",
                "25%": "p25",
                "50%": "p50",
                "75%": "p75",
                "max": "máx",
            }
        )
        .round(3)
    )

    logger.debug(
        f"Dataframe de estadísticas numéricas generado | filas = {len(stats):,} "
        f"| columnas consideradas = {num.shape[1]} de {df.shape[1]}"
    )
    return stats


def estadisticas_categoricas(opciones: dict[str, Any]) -> pd.DataFrame | None:
    """Genera tabla con conteo, moda y frecuencia de columnas categóricas, o None."""
    logger.debug("Generando estadísticas de columnas categóricas...")

    cat = opciones["COLS_CATEGORICAS"]
    if not cat:
        return None

    resumen = [
        {
            "columna": f"col_{i}",
            "conteo": s.size,
            "valores_únicos": s.nunique(),
            "moda": s.mode().iloc[0] if not s.mode().empty else "N/A",
            "freq_moda": s.value_counts().iloc[0],
            "%_moda": round(s.value_counts().iloc[0] / s.size * _PCT, 2),
        }
        for i, serie in enumerate(cat)
        for s in [pd.Series(serie)]
        if not s.empty
    ]

    logger.debug(
        f"Dataframe de estadísticas categóricas generado | filas = {len(resumen):,} "
        f"| columnas consideradas = {len(cat)}"
    )
    return pd.DataFrame(resumen).set_index("columna")


def tablas_categoricas(
    df: pd.DataFrame, opciones: dict[str, Any], n_top: int = 10
) -> dict[str, pd.DataFrame]:
    """Genera tablas de frecuencia para cada columna categórica configurada."""
    logger.debug("Generando tablas de frecuencias para columnas categóricas...")

    cat = opciones["COLS_CATEGORICAS"]
    resultados: dict[str, pd.DataFrame] = {}

    for col in cat:
        serie = df[col].fillna("N/A")
        vc = serie.value_counts(dropna=False)
        logger.debug(f"Columna: {col}, mostrando top {n_top} categorías")

        df_out = vc.head(n_top).to_frame("frecuencia")
        df_out.index.name = col
        resultados[col] = df_out

    return resultados
