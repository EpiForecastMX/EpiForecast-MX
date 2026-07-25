"""F2/C3.4 — motor ``seasonal_naive_lag52``: baseline estacional (lag-52) sobre el harness común.

Para cada semana objetivo del holdout, reutiliza el valor de 52 semanas atrás (calendario MMWR).
Si el origen del salto cae DENTRO del holdout (folds de 53 semanas: 2020/2025), continúa
RECURSIVAMENTE con la predicción previa — nunca consulta valores reales posteriores al origen (el
harness ya solo le entrega el train del fold; la recursión mantiene la propiedad para h>52).

Su artefacto es la especificación reproducible + predicciones + métricas (NO un .pkl). Solo aporta
su predictor; el harness gestiona datos/folds, 64 bases, derivación 64→111, eval/métricas y specs.
"""

from __future__ import annotations

from epiforecast.data.epi_calendar import shift
from epiforecast.runner import final_models as fm
from epiforecast.runner import forecasting, refit
from epiforecast.runner.adapters import register_adapter
from epiforecast.runner.engines import harness
from epiforecast.runner.engines.seasonal_state import seasonal_history, seasonal_state
from epiforecast.runner.manifest import ArtifactRecord

ENGINE = "seasonal_naive_lag52"
_LAG = 52
_SUPPORTED = frozenset({"benchmark", "refit", "forecast"})
# Historia MÍNIMA que el estado final necesita: el salto lag-52 más la semana 53 de los años largos.
_HISTORY_WEEKS = 53


def predict_series(
    train_map: dict[tuple[int, int], float], holdout: list[tuple[int, int]]
) -> dict[tuple[int, int], float]:
    """Seasonal naive lag-52 para una serie. Recursivo si el origen del salto cae en el holdout."""
    holdout_set = set(holdout)
    preds: dict[tuple[int, int], float] = {}
    for y, w in holdout:  # holdout en orden creciente → los recursivos ya están calculados
        src = shift(y, w, -_LAG)
        preds[(y, w)] = preds[src] if src in holdout_set else train_map[src]
    return preds


def _predict(request: harness.SeriesRequest) -> harness.SeriesForecast:
    # El baseline nunca hace fallback ni emite diagnóstico de ajuste (no ajusta nada).
    return harness.SeriesForecast(predict_series(request.train, list(request.holdout)))


def fit_final(window: fm.FinalWindow) -> fm.FinalState:
    """El "ajuste" del baseline es su historia mínima: no hay parámetros que estimar."""
    return seasonal_state(window.train, _HISTORY_WEEKS, {"seasonal_lag": _LAG})


def forecast_final(
    state: fm.FinalState, request: fm.ForecastRequest
) -> dict[tuple[int, int], float]:
    return predict_series(seasonal_history(state), list(request.periods))


class SeasonalNaiveLag52Adapter:
    """Adapter genérico (Protocol ``EngineAdapter``) ejecutado dentro del subprocess limpio."""

    name = ENGINE

    def supports(self, command: str) -> bool:
        return command in _SUPPORTED

    def forecast_state(
        self, state: fm.FinalState, request: fm.ForecastRequest
    ) -> dict[tuple[int, int], float]:
        """Capacidad R15.4: delega en ``forecast_final`` (una sola implementación)."""
        return forecast_final(state, request)

    def run(self, command: str, run_dir: str) -> list[ArtifactRecord]:
        params = {"seasonal_lag": _LAG, "history_weeks": _HISTORY_WEEKS}
        if command == "refit":
            return refit.run_refit(self.name, fit_final, run_dir, params)
        if command == "forecast":
            return forecasting.run_forecast(self.name, forecast_final, run_dir)
        return harness.run_benchmark(self.name, _predict, run_dir, {"seasonal_lag": _LAG})


register_adapter(ENGINE, SeasonalNaiveLag52Adapter())
