"""Banco ampliado: motores locales (una serie a la vez), sin estado ni lectura de archivos.

Contrato: ``fn(y, train, holdout, p) -> np.ndarray`` con ``y`` la historia contigua (orden MMWR),
``train`` sus periodos, ``holdout`` los periodos a pronosticar (contiguos tras el train) y ``p`` los
parámetros de ``config/banco/banco_ampliado_v1.yaml``. Devuelve conteos en el orden del holdout; el
recorte de negativos y el control de no finitos los hace el flujo, no el motor.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any
import warnings

import numpy as np
import pandas as pd

from epiforecast.data.epi_calendar import ds_for
from epiforecast.runner.engines import seasonal_naive, seasonal_window

Period = tuple[int, int]
Arr = np.ndarray[Any, Any]
Motor = Callable[[Arr, list[Period], list[Period], dict[str, Any]], Arr]


def _ventana(years: int, stat: str) -> Motor:
    fn = seasonal_window.make_predictor(years, stat, 1)

    def motor(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
        preds, _ = fn(dict(zip(train, y.tolist(), strict=True)), hold)
        return np.array([preds[h] for h in hold], dtype=float)

    return motor


def naive_lag52(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    preds = seasonal_naive.predict_series(dict(zip(train, y.tolist(), strict=True)), hold)
    return np.array([preds[h] for h in hold], dtype=float)


def media_52s(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    return np.full(len(hold), float(y[-52:].mean()))


def ultimo_valor(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    return np.full(len(hold), float(y[-1]))


_ESTACIONALES = [
    naive_lag52,
    _ventana(3, "mean"),
    _ventana(3, "median"),
    _ventana(5, "mean"),
    _ventana(5, "median"),
]


def promedio_estacionales(
    y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]
) -> Arr:
    return np.asarray(np.mean([m(y, train, hold, p) for m in _ESTACIONALES], axis=0), dtype=float)


def _factor_nivel(y: Arr, p: dict[str, Any]) -> float:
    w = int(p["nivel_ventana"])
    lo, hi = p["nivel_limites"]
    if len(y) < 52 + w:
        return 1.0
    reciente, previo = y[-w:].sum(), y[-52 - w : -52].sum()
    return float(np.clip((reciente + 1.0) / (previo + 1.0), lo, hi))


def _con_nivel(base: Motor) -> Motor:
    def motor(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
        return base(y, train, hold, p) * _factor_nivel(y, p)

    return motor


def _fourier(periods: list[Period], t0: int, k: int, escala: float) -> Arr:
    dias = np.array([ds_for(*q).toordinal() for q in periods], dtype=float)
    t = (np.arange(t0, t0 + len(periods), dtype=float)) / escala
    cols = [t]
    for j in range(1, k + 1):
        ang = 2 * np.pi * j * dias / 365.25
        cols += [np.sin(ang), np.cos(ang)]
    return np.column_stack(cols)


def ridge_fourier_log1p(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    from sklearn.linear_model import Ridge

    k, n = int(p["fourier_k"]), len(y)
    modelo = Ridge(alpha=float(p["ridge_alpha"]), solver="svd")
    modelo.fit(_fourier(train, 0, k, n), np.log1p(y))
    return np.asarray(np.expm1(modelo.predict(_fourier(hold, n, k, n))), dtype=float)


def poisson_fourier(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    from sklearn.linear_model import PoissonRegressor

    k, n = int(p["fourier_k"]), len(y)
    if y.sum() == 0:
        return np.zeros(len(hold))
    modelo = PoissonRegressor(alpha=float(p["poisson_alpha"]), max_iter=500)
    modelo.fit(_fourier(train, 0, k, n), y)
    return np.asarray(modelo.predict(_fourier(hold, n, k, n)), dtype=float)


def ets_amortiguado_log1p(
    y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]
) -> Arr:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    z = np.log1p(y)
    if len(z) < 104:
        raise ValueError("menos de dos estaciones completas")
    if np.ptp(z) == 0:
        return np.full(len(hold), float(y[-1]))  # serie constante: el pronóstico exacto
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(
            z,
            trend="add",
            damped_trend=True,
            seasonal="add",
            seasonal_periods=52,
            initialization_method="estimated",
        ).fit()
    return np.asarray(np.expm1(np.asarray(fit.forecast(len(hold)), dtype=float)), dtype=float)


def theta_log1p(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    from statsmodels.tsa.forecasting.theta import ThetaModel

    z = np.log1p(y)
    if len(z) < 104:
        raise ValueError("menos de dos estaciones completas")
    if np.ptp(z) == 0:
        return np.full(len(hold), float(y[-1]))  # serie constante: el pronóstico exacto
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ThetaModel(z, period=52, deseasonalize=True, method="additive").fit()
    return np.asarray(np.expm1(np.asarray(fit.forecast(len(hold)), dtype=float)), dtype=float)


def croston_sba(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    a = float(p["croston_alpha"])
    nz = np.flatnonzero(y > 0)
    if len(nz) == 0:
        return np.zeros(len(hold))
    z, x, q = float(y[nz[0]]), 1.0, 1
    for i in range(nz[0] + 1, len(y)):
        if y[i] > 0:
            z += a * (y[i] - z)
            x += a * (q - x)
            q = 1
        else:
            q += 1
    return np.full(len(hold), (1 - a / 2) * z / x)


def tsb(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    a, b = float(p["tsb_alpha"]), float(p["tsb_beta"])
    nz = np.flatnonzero(y > 0)
    if len(nz) == 0:
        return np.zeros(len(hold))
    prob, z = float((y > 0).mean()), float(y[nz].mean())
    for v in y:
        if v > 0:
            prob += b * (1 - prob)
            z += a * (v - z)
        else:
            prob += b * (0 - prob)
    return np.full(len(hold), prob * z)


def prophet_log1p(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    from prophet import Prophet

    for nombre in ("cmdstanpy", "prophet"):
        logging.getLogger(nombre).setLevel(logging.ERROR)
    if np.ptp(y) == 0:
        return np.full(len(hold), float(y[-1]))
    m = Prophet(
        growth="linear",
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.01,
        uncertainty_samples=0,
        seasonality_mode="additive",
    )
    m.add_seasonality(name="annual_mmwr", period=365.25, fourier_order=5, prior_scale=0.5)
    m.fit(pd.DataFrame({"ds": [pd.Timestamp(ds_for(*q)) for q in train], "y": np.log1p(y)}))
    fut = pd.DataFrame({"ds": [pd.Timestamp(ds_for(*q)) for q in hold]})
    return np.asarray(np.expm1(np.asarray(m.predict(fut)["yhat"], dtype=float)), dtype=float)


MOTORES: dict[str, Motor] = {
    "naive_lag52": naive_lag52,
    "media_3y": _ventana(3, "mean"),
    "mediana_3y": _ventana(3, "median"),
    "media_5y": _ventana(5, "mean"),
    "mediana_5y": _ventana(5, "median"),
    "media_2y": _ventana(2, "mean"),
    "media_52s": media_52s,
    "ultimo_valor": ultimo_valor,
    "promedio_estacionales": promedio_estacionales,
    "naive_nivel_13s": _con_nivel(naive_lag52),
    "media_3y_nivel_13s": _con_nivel(_ventana(3, "mean")),
    "ets_amortiguado_log1p": ets_amortiguado_log1p,
    "theta_log1p": theta_log1p,
    "ridge_fourier_log1p": ridge_fourier_log1p,
    "poisson_fourier": poisson_fourier,
    "croston_sba": croston_sba,
    "tsb": tsb,
    "prophet_log1p": prophet_log1p,
}
