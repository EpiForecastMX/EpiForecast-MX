"""Cohorte de padecimientos — shims respaldados por el registry (EPIC 1).

``is_neuro`` / ``is_count_log_cohort`` / ``filter_neuro`` ahora leen del registry central
(``config/padecimientos.yaml``) en vez de literales (``NEURO_CONDITIONS`` /
``frozenset({"Dengue"})``). Comportamiento byte-idéntico para los padecimientos vigentes
(probado por tests/unit/test_golden_cohortes.py y test_registry.py), incluidos los bordes:
``None`` y padecimiento desconocido -> ``False``; ``filter_neuro`` no-op si falta la columna.

Se conservan como shims públicos porque decenas de call sites los usan; los gates de modelo
migran a ``registry.trait(disease, engine, key)`` (per-motor) por separado.
"""

import pandas as pd

from epiforecast import registry


def _neuro_names() -> list[str]:
    return [
        d.data_name for d in registry.get_registry().diseases if d.profile.cohorte_id == "neuro"
    ]


def is_neuro(padecimiento: str | None) -> bool:
    """``True`` si el padecimiento pertenece a la cohorte neuro de producción."""
    return registry.cohorte_id(padecimiento) == "neuro"


def is_count_log_cohort(padecimiento: str | None) -> bool:
    """``True`` si se modela en log1p de conteos crudos (sin normalizar a tasa): activa
    log_transform, desactiva normalizar_tasa (Prophet), acota árboles con la envolvente
    estacional e invierte el log en predict. Hoy aplica solo a Dengue."""
    return registry.cohorte_id(padecimiento) == "conteos"


def filter_neuro(df: pd.DataFrame, col: str = "Padecimiento") -> pd.DataFrame:
    """Restringe el DataFrame a la cohorte neuro de producción.

    No-op (devuelve el df sin cambios) si la columna de padecimiento no existe, para
    no romper consumidores con esquemas distintos.
    """
    if col not in df.columns:
        return df
    return df[df[col].isin(_neuro_names())]
