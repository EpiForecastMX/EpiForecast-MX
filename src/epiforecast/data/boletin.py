"""Carga del boletín de Dengue desde la FUENTE ÚNICA de producción.

Todos los generadores web/charts de Dengue (``build_dengue_web``, ``eda_dengue_charts``,
``dengue_showcase_charts``, ``build_dengue_forecast_web``) deben leer la misma serie para
no divergir. La fuente canónica es el dataset consolidado (``conf["data"]["boletin"]``),
el mismo sobre el que entrenan los modelos; el interim (``dengue_boletin.csv``) es solo el
intermedio de extracción y se mantiene en sync vía ``make dengue-merge``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from epiforecast.utils.config import conf

PADECIMIENTO = "Dengue"


def cargar_boletin_dengue(csv: str | Path | None = None) -> pd.DataFrame:
    """Devuelve el boletín de Dengue (todas las entidades/semanas), filtrado a Dengue.

    Args:
        csv: ruta opcional a un CSV explícito (override). Por defecto, el consolidado de
            producción de ``conf["data"]["boletin"]``.
    """
    path = Path(csv) if csv is not None else Path(conf["data"]["boletin"])
    df = pd.read_csv(path)
    if "Padecimiento" in df.columns:
        df = df[df["Padecimiento"] == PADECIMIENTO].reset_index(drop=True)
    return df
