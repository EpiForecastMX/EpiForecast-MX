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


# Cohorte no-neuro modelada en log1p de CONTEOS crudos (hoy: Dengue). Centraliza el literal
# para no repetirlo en los motores: Prophet (log on / tasa off), Ensemble/Stacking (clamp
# estacional), y la inversión del log en predict (ForecastModelLoader). Un padecimiento
# futuro con la misma naturaleza se agrega aquí, en un solo lugar.
_COUNT_LOG_COHORT = frozenset({"Dengue"})


def is_count_log_cohort(padecimiento: str | None) -> bool:
    """``True`` si el padecimiento se modela en log1p de conteos crudos (sin normalizar a
    tasa). Implica: activar log_transform, desactivar normalizar_tasa, acotar la
    extrapolación de árboles con la envolvente estacional, e invertir el log (expm1) en
    predict. Hoy aplica solo a Dengue."""
    return padecimiento in _COUNT_LOG_COHORT


def filter_neuro(df: pd.DataFrame, col: str = "Padecimiento") -> pd.DataFrame:
    """Restringe el DataFrame a la cohorte neuro de producción.

    No-op (devuelve el df sin cambios) si la columna de padecimiento no existe, para
    no romper consumidores con esquemas distintos.
    """
    if col not in df.columns:
        return df
    return df[df[col].isin(NEURO_CONDITIONS)]
