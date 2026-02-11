# src/utils/datos.py
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


class OperacionesDatos:

    @staticmethod
    def _validar_columna(df: pd.DataFrame, col: str) -> None:
        if col not in df.columns:
            raise KeyError(f"La columna '{col}' no existe en el DataFrame.")
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise TypeError(f"La columna '{col}' no es numérica. Tipo: {df[col].dtype}")

    @staticmethod
    def iqr(
        df: pd.DataFrame,
        col: str,
        factor: float = 1.5,
        interpolation: str = "linear",
    ) -> Dict[str, float]:
        """
        Calcula Q1, Q3, IQR y límites (inferior/superior) para una columna específica.
        Devuelve un dict con: {'q1','q3','iqr','lim_inf','lim_sup'}.
        """
        OperacionesDatos._validar_columna(df, col)

        serie = df[col].dropna()
        if serie.empty:
            # Si está vacía tras eliminar NaN, devuelve NaN en todo
            return {"q1": np.nan, "q3": np.nan, "iqr": np.nan, "lim_inf": np.nan, "lim_sup": np.nan}

        q1 = serie.quantile(0.25, interpolation=interpolation)
        q3 = serie.quantile(0.75, interpolation=interpolation)
        iqr = float(q3 - q1)
        lim_inf = float(q1 - factor * iqr)
        lim_sup = float(q3 + factor * iqr)

        return {"q1": float(q1), "q3": float(q3), "iqr": iqr, "lim_inf": lim_inf, "lim_sup": lim_sup}

    @staticmethod
    def outliers_iqr(
        df: pd.DataFrame,
        col: str,
        factor: float = 1.5,
        interpolation: str = "linear",
    ) -> Tuple[pd.DataFrame, List]:
        """
        Devuelve un DataFrame con las filas que son outliers por IQR en la columna 'col'.
        metadatos: lim_inf, lim_sup, q1, q3, iqr, col_origen.
        """
        OperacionesDatos._validar_columna(df, col)
        stats = OperacionesDatos.iqr(df, col, factor=factor, interpolation=interpolation)

        lim_inf, lim_sup = stats["lim_inf"], stats["lim_sup"]
        # Comparaciones con NaN dan False, por lo que NaN no se marcan como outliers
        mask = (df[col] < lim_inf) | (df[col] > lim_sup)
        df_out = df.loc[mask].copy()

        metadatos = [lim_inf, lim_sup, stats["q1"], stats["q3"], stats["iqr"], col]

        return df_out, metadatos
    

    def zscore(
        df: pd.DataFrame,
        columna: str,
        umbral: float = 3,
        reemplazo=None
    ):
            df = df.copy()

            # Calcular medias y desviaciones por grupo
            medias = df.groupby("Padecimiento")[columna].transform("mean").round().astype(int)
            desvios = df.groupby("Padecimiento")[columna].transform("std").round().astype(int)


            # Calcular Z-score y outliers
            df[f"Zscore_{columna}"] = (df[columna] - medias) / desvios
            df[f"Outlier_{columna}"] = df[f"Zscore_{columna}"].abs() > umbral

            if reemplazo is not None:
                if reemplazo.lower() == "media":
                    df.loc[df[f"Outlier_{columna}"], columna] = medias[df[f"Outlier_{columna}"]]

                elif reemplazo.lower() == "mediana":
                    medianas = df.groupby("Padecimiento")[columna].transform("median")
                    df.loc[df[f"Outlier_{columna}"], columna] = medianas[df[f"Outlier_{columna}"]]

                elif reemplazo.lower() == "cercano":
                    limite_inferior = medias - umbral * desvios
                    limite_superior = medias + umbral * desvios
                    df.loc[df[f"Outlier_{columna}"] & (df[columna] < limite_inferior), columna] = limite_inferior[df[f"Outlier_{columna}"] & (df[columna] < limite_inferior)]
                    df.loc[df[f"Outlier_{columna}"] & (df[columna] > limite_superior), columna] = limite_superior[df[f"Outlier_{columna}"] & (df[columna] > limite_superior)]

                else:
                    raise ValueError("reemplazo debe ser None, 'media', 'mediana' o 'cercano'")

            df[columna] = df[columna].round().astype(int)

            return df










