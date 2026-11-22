"""Banco ampliado, ronda 2: más motores locales y combinaciones (mismo contrato que ``motores``).

- Medias móviles cortas y mediana de 52 semanas (simples).
- Suavizado exponencial simple optimizado (nivel, sin estacionalidad).
- Nivel × perfil estacional: media de 52 semanas por un índice estacional de 5 años, encogido.
- STL + ETS sobre log1p (descomposición estacional robusta, periodo 52).
- GLM binomial negativo con tendencia y Fourier (conteos sobredispersos).
- Combinaciones: media de los tres mejores de la ronda 1 y su mediana.
"""

from __future__ import annotations

from typing import Any
import warnings

import numpy as np

from epiforecast.banco import motores
from epiforecast.banco.motores import Arr, Motor, Period


def _media_ultimas(n: int) -> Motor:
    def motor(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
        return np.full(len(hold), float(y[-n:].mean()))

    return motor


def mediana_52s(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    return np.full(len(hold), float(np.median(y[-52:])))


def ses_optimizado(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing

    if np.ptp(y) == 0:
        return np.full(len(hold), float(y[-1]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = SimpleExpSmoothing(y, initialization_method="estimated").fit()
    return np.full(len(hold), float(np.asarray(fit.forecast(1))[0]))


def nivel_x_perfil_5y(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    """Media de 52 semanas × índice de la misma semana en 5 años, encogido hacia 1."""
    nivel = float(y[-52:].mean())
    k = float(p["perfil_encogimiento"])
    por_semana: dict[int, list[float]] = {}
    for (_anio, semana), v in zip(train[-5 * 52 :], y[-5 * 52 :], strict=True):
        por_semana.setdefault(semana, []).append(float(v))
    media_global = float(y[-5 * 52 :].mean())
    if media_global == 0:
        return np.full(len(hold), nivel)
    out = []
    for _, semana in hold:
        vals = por_semana.get(semana) or por_semana.get(52, [media_global])
        indice = float(np.mean(vals)) / media_global
        out.append(nivel * (1 + k * (indice - 1)))
    return np.array(out)


def stl_ets_log1p(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    from statsmodels.tsa.forecasting.stl import STLForecast
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    z = np.log1p(y)
    if len(z) < 104:
        raise ValueError("menos de dos estaciones completas")
    if np.ptp(z) == 0:
        return np.full(len(hold), float(y[-1]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = STLForecast(
            z,
            ExponentialSmoothing,
            model_kwargs={
                "trend": "add",
                "damped_trend": True,
                "initialization_method": "estimated",
            },
            period=52,
            robust=True,
        ).fit()
    return np.asarray(np.expm1(np.asarray(fit.forecast(len(hold)), dtype=float)), dtype=float)


def negbin_fourier(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
    import statsmodels.api as sm

    if y.sum() == 0:
        return np.zeros(len(hold))
    k, n = int(p["fourier_k"]), len(y)
    x_tr = sm.add_constant(motores._fourier(train, 0, k, n), has_constant="add")
    x_ho = sm.add_constant(motores._fourier(hold, n, k, n), has_constant="add")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = sm.GLM(
            y, x_tr, family=sm.families.NegativeBinomial(alpha=float(p["negbin_alpha"]))
        ).fit()
    return np.asarray(fit.predict(x_ho), dtype=float)


_TOP3 = ("media_52s", "ets_amortiguado_log1p", "tsb")


def _combinar(estadistico: str) -> Motor:
    def motor(y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]) -> Arr:
        preds = [np.maximum(motores.MOTORES[m](y, train, hold, p), 0.0) for m in _TOP3]
        agg = np.mean if estadistico == "media" else np.median
        return np.asarray(agg(preds, axis=0), dtype=float)

    return motor


MOTORES_EXTRA: dict[str, Motor] = {
    "media_26s": _media_ultimas(26),
    "media_13s": _media_ultimas(13),
    "mediana_52s": mediana_52s,
    "ses_optimizado": ses_optimizado,
    "nivel_x_perfil_5y": nivel_x_perfil_5y,
    "stl_ets_log1p": stl_ets_log1p,
    "negbin_fourier": negbin_fourier,
    "combo_media_top3": _combinar("media"),
    "combo_mediana_top3": _combinar("mediana"),
}
