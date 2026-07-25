"""F2/C3b — familia genérica de ventanas estacionales: mean/median × 3/5 años (sobre el harness).

Un SOLO predictor configurable, cuatro registros (seasonal_{mean,median}_{3,5}y). Para cada
(año, semana) consulta la MISMA semana epidemiológica en los N años anteriores, usando solo periodos
existentes (estrictamente previos al origen; nunca fuera de la ventana declarada). Con >= min_obs
valores → media o mediana; sin suficientes (p.ej. W53) → fallback seasonal_naive_lag52 recursivo,
registrado. Pronósticos flotantes NO negativos; no se redondea ni recorta. Sin nombre de padecimiento.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
import statistics
from typing import Any, cast

from omegaconf import OmegaConf

from epiforecast.data.epi_calendar import shift
from epiforecast.runner import final_models as fm
from epiforecast.runner import forecasting, refit
from epiforecast.runner.adapters import register_adapter
from epiforecast.runner.engines import harness
from epiforecast.runner.engines.seasonal_state import seasonal_history, seasonal_state
from epiforecast.runner.manifest import ArtifactRecord

_ROOT = Path(__file__).resolve().parents[4]
_CONFIG = _ROOT / "config" / "engines" / "seasonal_windows.yaml"
_LAG = 52
_SUPPORTED = frozenset({"benchmark", "refit", "forecast"})
_STATISTICS: dict[str, Callable[[Sequence[float]], float]] = {
    "mean": lambda v: statistics.fmean(v),
    "median": lambda v: float(statistics.median(v)),
}


class WindowConfigError(ValueError):
    """Configuración de ventanas estacionales inválida."""


def load_window_config() -> dict[str, dict[str, Any]]:
    raw = cast("dict[str, Any]", OmegaConf.to_container(OmegaConf.load(_CONFIG), resolve=True))
    return {str(k): dict(v) for k, v in raw["engines"].items()}


WindowFn = Callable[
    [dict[tuple[int, int], float], list[tuple[int, int]]],
    tuple[dict[tuple[int, int], float], int],
]


def make_predictor(years: int, statistic: str, min_obs: int) -> WindowFn:
    """Predictor de ventana: media/mediana de la misma semana en ``years`` años previos; fallback naive."""
    if statistic not in _STATISTICS:
        raise WindowConfigError(f"estadístico no soportado: {statistic!r}")
    stat = _STATISTICS[statistic]

    def predict(
        train_map: dict[tuple[int, int], float], holdout: list[tuple[int, int]]
    ) -> tuple[dict[tuple[int, int], float], int]:
        holdout_set = set(holdout)
        preds: dict[tuple[int, int], float] = {}
        n_fallback = 0
        for y, w in holdout:
            # Misma semana epidemiológica en los N años previos; solo periodos existentes.
            vals = [train_map[(y - k, w)] for k in range(1, years + 1) if (y - k, w) in train_map]
            if len(vals) >= min_obs:
                preds[(y, w)] = float(stat(vals))
            else:  # sin historial en la ventana (p.ej. W53) → seasonal_naive_lag52 recursivo
                src = shift(y, w, -_LAG)
                preds[(y, w)] = preds[src] if src in holdout_set else train_map[src]
                n_fallback += 1
        return preds, n_fallback

    return predict


def _as_predict_fn(window: WindowFn) -> harness.PredictFn:
    """Adapta el predictor de ventana (puro) al contrato ``PredictFn`` del harness."""

    def predict(request: harness.SeriesRequest) -> harness.SeriesForecast:
        preds, n_fallback = window(request.train, list(request.holdout))
        return harness.SeriesForecast(preds, n_fallback)

    return predict


class SeasonalWindowAdapter:
    """Adapter de una ventana concreta; delega todo el flujo común al harness."""

    def __init__(self, name: str, years: int, statistic: str, min_obs: int, fallback: str) -> None:
        self.name = name
        self._years = years
        self._statistic = statistic
        self._min_obs = min_obs
        self._fallback = fallback
        self._predict = _as_predict_fn(make_predictor(years, statistic, min_obs))

    def supports(self, command: str) -> bool:
        return command in _SUPPORTED

    @property
    def _params(self) -> dict[str, Any]:
        return {
            "family": "seasonal_window",
            "statistic": self._statistic,
            "years": self._years,
            "min_obs": self._min_obs,
            "fallback": self._fallback,
        }

    @property
    def _history_weeks(self) -> int:
        """Cola mínima: la misma semana en los ``years`` años previos al último año pronosticable."""
        return (self._years + 1) * 53

    def fit_final(self, window: fm.FinalWindow) -> fm.FinalState:
        return seasonal_state(window.train, self._history_weeks, self._params)

    def forecast_final(
        self, state: fm.FinalState, request: fm.ForecastRequest
    ) -> dict[tuple[int, int], float]:
        window_fn = make_predictor(self._years, self._statistic, self._min_obs)
        preds, _ = window_fn(seasonal_history(state), list(request.periods))
        return preds

    def forecast_state(
        self, state: fm.FinalState, request: fm.ForecastRequest
    ) -> dict[tuple[int, int], float]:
        """Capacidad R15.4: delega en ``forecast_final`` (una sola implementación)."""
        return self.forecast_final(state, request)

    def run(self, command: str, run_dir: str) -> list[ArtifactRecord]:
        if command == "refit":
            return refit.run_refit(self.name, self.fit_final, run_dir, self._params)
        if command == "forecast":
            return forecasting.run_forecast(self.name, self.forecast_final, run_dir)
        return harness.run_benchmark(self.name, self._predict, run_dir, self._params)


def _register_all() -> None:
    for name, cfg in load_window_config().items():
        register_adapter(
            name,
            SeasonalWindowAdapter(
                name=name,
                years=int(cfg["years"]),
                statistic=str(cfg["statistic"]),
                min_obs=int(cfg["min_obs"]),
                fallback=str(cfg["fallback"]),
            ),
        )


_register_all()
