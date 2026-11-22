"""Predictores de la sombra: los del runner (motores estacionales) o los del banco ampliado."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np

from epiforecast.runner.engines import seasonal_naive, seasonal_window

Period = tuple[int, int]
Predictor = Callable[[dict[Period, float], list[Period]], dict[Period, float]]

__all__ = ["SombraError", "predicciones_base", "predictor"]


class SombraError(ValueError):
    """La sombra violó una regla declarada (datos, cobertura o configuración)."""


def predictor(engine: str) -> Predictor:
    """El predictor puro del motor, el mismo que usa el runner (sin ajuste ni estado)."""
    if engine == seasonal_naive.ENGINE:
        return seasonal_naive.predict_series
    cfg = seasonal_window.load_window_config().get(engine)
    if cfg is None:
        raise SombraError(f"motor sin predictor puro: {engine}")
    fn = seasonal_window.make_predictor(
        int(cfg["years"]), str(cfg["statistic"]), int(cfg["min_obs"])
    )
    return lambda train, periods: fn(train, periods)[0]


def predicciones_base(
    trains: Mapping[tuple[str, str], dict[Period, float]],
    engine: str,
    periodos: list[Period],
    fuente: str,
) -> dict[tuple[str, str], dict[Period, float]]:
    """Pronóstico base de cada serie con el predictor del runner o con el del banco ampliado."""
    if fuente == "benchmark":
        fn = predictor(engine)
        return {k: fn(dict(t), periodos) for k, t in trains.items()}
    from epiforecast.banco import flujo as banco

    params = banco.cargar_config()["parametros"]
    tr = sorted(next(iter(trains.values())))
    arrays = {k: np.array([t[q] for q in tr], dtype=float) for k, t in trains.items()}
    if engine in banco.GLOBALES:
        crudo = banco.GLOBALES[engine](arrays, tr, periodos, params)
    elif engine in banco.LOCALES:
        crudo = {k: banco.LOCALES[engine](a, tr, periodos, params) for k, a in arrays.items()}
    else:
        raise SombraError(f"motor desconocido en el banco: {engine}")
    out = {}
    for k, v in crudo.items():
        v = np.asarray(v, dtype=float)
        if len(v) != len(periodos) or not np.isfinite(v).all():
            raise SombraError(f"{engine} {k}: pronóstico no finito")
        out[k] = dict(zip(periodos, np.maximum(v, 0.0).tolist(), strict=True))
    return out
