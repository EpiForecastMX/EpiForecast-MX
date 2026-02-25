"""Outlier detection and imputation routines for epidemiological time series."""

from loguru import logger
import numpy as np
import pandas as pd

from epiforecast.utils.dataframe_helpers import OperacionesDatos


def ajusta_outliers(df: pd.DataFrame, columnas: list, agrupacion: list) -> pd.DataFrame:
    """Detect and clip IQR-based outliers per padecimiento group.

    Args:
        df:         DataFrame with columns including those in columnas and agrupacion.
        columnas:   List of column names to apply IQR clipping to.
        agrupacion: List of groupby columns for computing IQR statistics.

    Returns:
        DataFrame with outlier values clipped to IQR bounds.
    """
    for columna in columnas:
        stats = (
            df.groupby(agrupacion, sort=False)
            .apply(  # type: ignore[call-overload]
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
        df = df.merge(
            stats[["Padecimiento", "q1", "q3", "iqr", "lim_inf", "lim_sup"]],
            on="Padecimiento",
            how="left",
        )

        for pade, sub in df.groupby("Padecimiento", sort=False):
            iqr = sub["iqr"].iloc[0]
            q1 = sub["q1"].iloc[0]
            q3 = sub["q3"].iloc[0]
            lim_inf = sub["lim_inf"].iloc[0]
            lim_sup = sub["lim_sup"].iloc[0]

            mascara_inf = sub[columna] < lim_inf
            mascara_sup = sub[columna] > lim_sup
            total_inf = int(mascara_inf.sum())
            total_sup = int(mascara_sup.sum())

            logger.info(
                f"[{pade}] Rangos intercuartiles para '{columna}': IQR={iqr}, Q1={q1}, Q3={q3}"
            )
            logger.info(
                f"[{pade}] Límite inferior: {lim_inf} | Registros por debajo del límite: {total_inf}"
            )
            logger.info(
                f"[{pade}] Límite superior: {lim_sup} | Registros por encima del límite: {total_sup}"
            )

        x = df[columna].to_numpy()
        lo = df["lim_inf"].to_numpy()
        hi = df["lim_sup"].to_numpy()

        x_clipped = np.clip(x, lo, hi)

        df[columna] = pd.Series(x_clipped, index=df.index).round(0).astype("Int64")

        df = df.drop(columns=["q1", "q3", "iqr", "lim_inf", "lim_sup"])

    return df


def ajusta_outliers_zscore(
    df: pd.DataFrame,
    columnas: list,
    agrupacion: list,
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
