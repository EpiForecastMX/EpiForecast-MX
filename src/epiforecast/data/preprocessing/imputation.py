"""Outlier detection and imputation routines for epidemiological time series."""

from loguru import logger
import numpy as np
import pandas as pd

from epiforecast.utils.dataframe_helpers import OperacionesDatos


def ajusta_outliers(df: pd.DataFrame, columnas: list[str], agrupacion: list[str]) -> pd.DataFrame:
    """Detect and clip IQR-based outliers per padecimiento group.

    Args:
        df:         DataFrame with columns including those in columnas and agrupacion.
        columnas:   List of column names to apply IQR clipping to.
        agrupacion: List of groupby columns for computing IQR statistics.

    Returns:
        DataFrame with outlier values clipped to IQR bounds.
    """
    for columna in columnas:
        stats = _compute_iqr_stats(df, columna, agrupacion)
        df = df.merge(
            stats[["Padecimiento", "q1", "q3", "iqr", "lim_inf", "lim_sup"]],
            on="Padecimiento",
            how="left",
        )

        _log_iqr_stats(df, columna)

        x_clipped = np.clip(
            df[columna].to_numpy(), df["lim_inf"].to_numpy(), df["lim_sup"].to_numpy()
        )
        df[columna] = pd.Series(x_clipped, index=df.index).round(0).astype("Int64")
        df = df.drop(columns=["q1", "q3", "iqr", "lim_inf", "lim_sup"])

    return df


def _compute_iqr_stats(df: pd.DataFrame, columna: str, agrupacion: list[str]) -> pd.DataFrame:
    """Calcula estadísticas IQR por grupo de agrupación."""
    return (
        df.groupby(agrupacion, sort=False)
        .apply(
            lambda g: pd.Series(
                (
                    lambda met: {
                        "q1": met[2],
                        "q3": met[3],
                        "iqr": met[4],
                        "lim_inf": met[0],
                        "lim_sup": met[1],
                    }
                )(OperacionesDatos.outliers_iqr(g, columna)[1])
            ),
            include_groups=False,
        )
        .reset_index()
    )


def _log_iqr_stats(df: pd.DataFrame, columna: str) -> None:
    """Loggea estadísticas IQR y conteo de outliers por padecimiento."""
    for pade, sub in df.groupby("Padecimiento", sort=False):
        iqr, q1, q3 = sub["iqr"].iloc[0], sub["q1"].iloc[0], sub["q3"].iloc[0]
        lim_inf, lim_sup = sub["lim_inf"].iloc[0], sub["lim_sup"].iloc[0]
        total_inf = int((sub[columna] < lim_inf).sum())
        total_sup = int((sub[columna] > lim_sup).sum())

        logger.info(
            f"[{pade}] Rangos intercuartiles para '{columna}': IQR={iqr}, Q1={q1}, Q3={q3}"
        )
        logger.info(f"[{pade}] Límite inferior: {lim_inf} | Registros por debajo: {total_inf}")
        logger.info(f"[{pade}] Límite superior: {lim_sup} | Registros por encima: {total_sup}")


def ajusta_outliers_zscore(
    df: pd.DataFrame,
    columnas: list[str],
    agrupacion: list[str],
    umbral: int,
    reemplazo: str,
) -> pd.DataFrame:
    """Replace Z-score outliers via OperacionesDatos.zscore.

    Args:
        df:         Input DataFrame.
        columnas:   Columns to apply Z-score correction.
        agrupacion: Groupby columns for Z-score computation.
        umbral:     Z-score threshold (e.g. 3).
        reemplazo:  Replacement strategy ('media', 'mediana', 'zero').

    Returns:
        DataFrame with Z-score outliers replaced.
    """
    for col in columnas:
        df = OperacionesDatos.zscore(df, col, agrupacion, umbral, reemplazo)
    return df
