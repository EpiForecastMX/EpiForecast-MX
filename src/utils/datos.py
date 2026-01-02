
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np

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
