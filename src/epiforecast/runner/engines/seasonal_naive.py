"""F2/C3.4 — motor ``seasonal_naive_lag52``: baseline estacional (lag-52) sobre el harness común.

Para cada semana objetivo del holdout, reutiliza el valor de 52 semanas atrás (calendario MMWR).
Si el origen del salto cae DENTRO del holdout (folds de 53 semanas: 2020/2025), continúa
RECURSIVAMENTE con la predicción previa — nunca consulta valores reales posteriores al origen.

Su artefacto es la especificación reproducible + predicciones + métricas (NO un .pkl). Solo aporta
su predictor; el harness gestiona datos/folds, 64 bases, derivación 64→111, eval/métricas y specs.
"""

from __future__ import annotations

from epiforecast.data.epi_calendar import shift
from epiforecast.runner.adapters import register_adapter
from epiforecast.runner.engines import harness
from epiforecast.runner.manifest import ArtifactRecord

ENGINE = "seasonal_naive_lag52"
_LAG = 52
# Hasta implementar refit/forecast, este motor SOLO acepta benchmark (fail-closed honesto).
_SUPPORTED = frozenset({"benchmark"})


def predict_series(
    truth_map: dict[tuple[int, int], float], holdout: list[tuple[int, int]]
) -> dict[tuple[int, int], float]:
    """Seasonal naive lag-52 para una serie. Recursivo si el origen del salto cae en el holdout."""
    holdout_set = set(holdout)
    preds: dict[tuple[int, int], float] = {}
    for y, w in holdout:  # holdout en orden creciente → los recursivos ya están calculados
        src = shift(y, w, -_LAG)
        preds[(y, w)] = preds[src] if src in holdout_set else truth_map[src]
    return preds


def _predict(
    truth_map: dict[tuple[int, int], float], holdout: list[tuple[int, int]]
) -> tuple[dict[tuple[int, int], float], int]:
    return predict_series(truth_map, holdout), 0  # el baseline nunca hace fallback


class SeasonalNaiveLag52Adapter:
    """Adapter genérico (Protocol ``EngineAdapter``) ejecutado dentro del subprocess limpio."""

    name = ENGINE

    def supports(self, command: str) -> bool:
        return command in _SUPPORTED

    def run(self, command: str, run_dir: str) -> list[ArtifactRecord]:
        return harness.run_benchmark(self.name, _predict, run_dir, {"seasonal_lag": _LAG})


register_adapter(ENGINE, SeasonalNaiveLag52Adapter())
