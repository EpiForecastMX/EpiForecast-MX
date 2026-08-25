"""Cohorte de padecimientos — shims respaldados por el registry (EPIC 1).

``is_neuro`` / ``is_count_log_cohort`` / ``filter_neuro`` ahora leen del registry central
(``config/padecimientos.yaml``) en vez de literales (``NEURO_CONDITIONS`` /
``frozenset({"Dengue"})``). Comportamiento byte-idéntico para los padecimientos vigentes
(probado por tests/unit/test_golden_cohortes.py y test_registry.py), incluidos los bordes:
``None`` y padecimiento desconocido -> ``False``; ``filter_neuro`` no-op si falta la columna.

Se conservan como shims públicos porque decenas de call sites los usan; los gates de modelo
migran a ``registry.trait(disease, engine, key)`` (per-motor) por separado.
"""

import unicodedata

import pandas as pd

from epiforecast import registry


def _pliega(v: object) -> str:
    """Sin tildes, sin mayúsculas: para comparar nombres, no para mostrarlos.

    Los nombres canónicos del registry llevan tilde (``Depresión``) y
    ``tabla_333_modelos_produccion.xlsx`` los escribe sin ella (``Depresion``). Comparar
    literalmente habría descartado **las 111 filas de depresión** en silencio, que es peor
    que el no-op que este arreglo vino a corregir: en vez de 435 habrían salido 222.
    """
    t = unicodedata.normalize("NFKD", str(v))
    return "".join(c for c in t if not unicodedata.combining(c)).casefold().strip()


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

    El nombre de la columna se resuelve **sin distinguir mayúsculas**, y esa es la parte
    importante: el consolidado del boletín la escribe ``Padecimiento`` mientras
    ``tabla_333_modelos_produccion.xlsx`` y ``produccion_dengue.csv`` la escriben
    ``padecimiento``. Con la comparación exacta anterior, cualquier llamada sobre esas dos
    fuentes caía en la rama «la columna no existe» y **devolvía el frame entero sin
    filtrar**, silenciosamente. Ese no-op es el origen del 435 que publicaba el sitio: la
    llamada parecía filtrar y no filtraba (24-ago-2026).

    Sigue siendo no-op si no hay ninguna columna de padecimiento, para no romper
    consumidores con esquemas distintos —``publication.tableau_adapter`` es uno—, pero
    ahora eso sólo ocurre cuando de verdad no la hay.
    """
    real = col if col in df.columns else None
    if real is None:
        objetivo = _pliega(col)
        real = next((c for c in df.columns if _pliega(c) == objetivo), None)
    if real is None:
        return df
    validos = {_pliega(n) for n in _neuro_names()}
    return df[df[real].map(_pliega).isin(validos)]
