"""ENSO / El Niño (índice ONI) como covariable exógena para Dengue.

El ciclo inter-anual del dengue en México sigue a El Niño/ENSO (brotes 2014, 2019, 2024),
señal que NO vive en los conteos recientes y que los modelos autorregresivos no pueden ver.
Este módulo entrega el índice ONI (NOAA CPC) alineado a semana ISO y rezagado (el clima
precede al dengue ~3-6 meses), con una estrategia DESPLEGABLE para el futuro:

- Pasado/observado: ONI real de NOAA.
- Futuro (horizonte de pronóstico): para una semana objetivo t se usa ONI(t - lag). Si
  t - lag aún es futuro respecto al último ONI conocido, se extrapola con **persistencia
  amortiguada hacia neutral** (ENSO decae a 0 con un e-folding ~ por defecto 40 semanas),
  o, si se provee, un pronóstico ENSO externo (IRI/CPC) en ``data/external/oni_forecast.csv``.

Es cohort-only: solo lo usa la cohorte de conteos (Dengue); neuro nunca lo toca.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import urllib.request

import numpy as np
import pandas as pd

ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
ONI_PATH = Path("data/external/oni.ascii.txt")
ONI_FORECAST_PATH = Path("data/external/oni_forecast.csv")  # opcional: IRI/CPC (cols ds,oni)
_SEAS_TO_MONTH = {
    "DJF": 1,
    "JFM": 2,
    "FMA": 3,
    "MAM": 4,
    "AMJ": 5,
    "MJJ": 6,
    "JJA": 7,
    "JAS": 8,
    "ASO": 9,
    "SON": 10,
    "OND": 11,
    "NDJ": 12,
}
DEFAULT_LAG_WEEKS = 16
_DECAY_EFOLD_WEEKS = 40.0  # ENSO decae a neutral con este e-folding (persistencia amortiguada)


def _ensure_oni() -> None:
    if not ONI_PATH.exists():
        ONI_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(ONI_URL, str(ONI_PATH))  # noqa: S310


def load_oni_weekly() -> pd.DataFrame:
    """ONI mensual (trimestre móvil) -> semanal interpolado. Columnas: ds (W-MON), oni."""
    _ensure_oni()
    rows = []
    with ONI_PATH.open() as f:
        next(f)
        for line in f:
            p = line.split()
            if len(p) == 4 and p[0] in _SEAS_TO_MONTH:
                rows.append((int(p[1]), _SEAS_TO_MONTH[p[0]], float(p[3])))
    o = pd.DataFrame(rows, columns=["yr", "mo", "oni"])
    o["ds"] = pd.to_datetime({"year": o.yr, "month": o.mo, "day": 1})
    weekly = o.set_index("ds").resample("W-MON")["oni"].mean().interpolate().reset_index()
    if ONI_FORECAST_PATH.exists():  # pronóstico ENSO externo (IRI/CPC), si está disponible
        fc = pd.read_csv(ONI_FORECAST_PATH, parse_dates=["ds"])[["ds", "oni"]]
        weekly = (
            pd.concat([weekly[weekly["ds"] < fc["ds"].min()], fc])
            .drop_duplicates("ds")
            .sort_values("ds")
            .reset_index(drop=True)
        )
    return weekly


def _future_oni(known: pd.DataFrame, until: pd.Timestamp) -> pd.DataFrame:
    """Extiende ONI hasta ``until`` con persistencia amortiguada hacia neutral (0)."""
    last_ds = known["ds"].max()
    if until <= last_ds:
        return known
    last_val = float(known.loc[known["ds"] == last_ds, "oni"].iloc[0])
    fut_ds = pd.date_range(last_ds + pd.Timedelta(weeks=1), until, freq="W-MON")
    k = np.arange(1, len(fut_ds) + 1)
    fut_oni = last_val * np.exp(-k / _DECAY_EFOLD_WEEKS)
    fut = pd.DataFrame({"ds": fut_ds, "oni": fut_oni})
    return pd.concat([known, fut], ignore_index=True)


def oni_for_dates(
    ds: pd.Series, lag_weeks: int = DEFAULT_LAG_WEEKS, as_of: pd.Timestamp | None = None
) -> np.ndarray[Any, Any]:
    """Valor del regresor ONI para cada fecha objetivo en ``ds`` (rezagado ``lag_weeks``).

    Para la fecha objetivo t se usa ONI(t - lag_weeks). ``as_of`` acota qué ONI se considera
    "conocido" (para validación honesta / despliegue): el ONI posterior a ``as_of`` se
    extrapola con persistencia amortiguada en vez de leerse del futuro observado.
    """
    oni = load_oni_weekly()
    if as_of is not None:
        oni = oni[oni["ds"] <= as_of].reset_index(drop=True)
    target = pd.to_datetime(pd.Series(ds)).reset_index(drop=True)
    need_until = target.max()  # la fecha-fuente más tardía requerida
    oni = _future_oni(oni, need_until)
    series = oni.set_index("ds")["oni"].sort_index()
    src_dates = pd.DatetimeIndex(target - pd.Timedelta(weeks=lag_weeks))
    vals = series.reindex(series.index.union(src_dates)).interpolate().reindex(src_dates)
    return vals.ffill().bfill().to_numpy(dtype=float)
