"""Cohorte de padecimientos: neurológica de producción vs. otros (p.ej. Dengue).

Centraliza el criterio que distingue la cohorte neurológica/salud mental en producción
(Depresión, Parkinson, Alzheimer) de los padecimientos que se incorporan con su propio
pipeline (Dengue). Los flujos neuro deben usar estos helpers en vez de repetir
``df[...].isin(NEURO_CONDITIONS)`` o ``padecimiento in NEURO_CONDITIONS`` (que divergían
en el manejo de bordes: None, columna ausente, DataFrame vacío).
"""

import pandas as pd

from epiforecast.constants import NEURO_CONDITIONS


def is_neuro(padecimiento: str | None) -> bool:
    """``True`` si el padecimiento pertenece a la cohorte neuro de producción."""
    return padecimiento in NEURO_CONDITIONS


def filter_neuro(df: pd.DataFrame, col: str = "Padecimiento") -> pd.DataFrame:
    """Restringe el DataFrame a la cohorte neuro de producción.

    No-op (devuelve el df sin cambios) si la columna de padecimiento no existe, para
    no romper consumidores con esquemas distintos.
    """
    if col not in df.columns:
        return df
    return df[df[col].isin(NEURO_CONDITIONS)]
