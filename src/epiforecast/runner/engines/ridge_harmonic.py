"""F2/C3d — motor ``ridge_harmonic_log1p``: Ridge sobre tendencia + armónicos de Fourier.

Segundo motor que AJUSTA de verdad y el primero que **selecciona hiperparámetros**, siempre dentro
del train exterior. Solo aporta su ``PredictFn``; folds, derivación 64→111, métricas y artefactos
siguen siendo del harness compartido.

Contrato (declarado en ``config/engines/ridge_harmonic.yaml``):
- ``sklearn.linear_model.Ridge`` con solver ``svd`` (cerrado y determinista, sin iteraciones).
- Objetivo log1p de los conteos; la inversa expm1 la gobierna el ``TransformContract``.
- Diseño: tendencia lineal estandarizada + pares seno/coseno de orden 1..K sobre el **ds
  epidemiológico** (calendario MMWR, no semana ISO), periodo anual de 365.25 días. Sin lags.
- Selección temporal INTERNA: las últimas ``inner_validation_weeks`` del train exterior son
  inner-validation y el resto inner-train. Se ajusta la rejilla completa (orders × alphas) sobre el
  inner-train, se puntúa con sMAPE en CASOS (misma fórmula del MetricFrame) y se desempata por
  menor orden de Fourier y luego mayor alpha. El holdout NUNCA participa en la selección.
- Con la combinación elegida se refitea sobre TODO el train exterior y se pronostica el holdout.
- Un modelo independiente por serie base y fold; nunca para agregados (eso lo deriva el harness).
- Sin clipping, sin redondeo y sin fallback: un candidato que produzca conteos negativos o no
  finitos queda inválido, y si no queda ninguno válido el job entero termina rc≠0.

El escalador de la tendencia se ajusta con el set de ajuste de CADA ajuste (inner-train en la
selección, train exterior en el refit): ni el inner-validation ni el holdout tocan los estadísticos.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
from omegaconf import OmegaConf

from epiforecast.artifacts.transforms import TransformContractError
from epiforecast.data.epi_calendar import ds_for
from epiforecast.runner import contracts as ct
from epiforecast.runner import final_models as fm
from epiforecast.runner import forecasting, refit
from epiforecast.runner.adapters import register_adapter
from epiforecast.runner.engines import harness
from epiforecast.runner.evaluation import smape_percent
from epiforecast.runner.manifest import ArtifactRecord

ENGINE = "ridge_harmonic_log1p"
_ROOT = Path(__file__).resolve().parents[4]
_CONFIG = _ROOT / "config" / "engines" / "ridge_harmonic.yaml"
_SUPPORTED = frozenset({"benchmark", "refit", "forecast"})


class RidgeFitError(RuntimeError):
    """Ningún candidato Ridge es utilizable: el job termina rc≠0 (nunca recorta ni inventa ceros)."""


@dataclass(frozen=True)
class Candidate:
    """Una combinación de la rejilla declarada."""

    fourier_order: int
    alpha: float


def load_ridge_config() -> dict[str, Any]:
    return cast("dict[str, Any]", OmegaConf.to_container(OmegaConf.load(_CONFIG), resolve=True))


def candidates(cfg: dict[str, Any]) -> tuple[Candidate, ...]:
    """Rejilla en orden declarado (el desempate no depende de este orden, sino de la clave)."""
    return tuple(
        Candidate(int(order), float(alpha))
        for order in cfg["fourier_orders"]
        for alpha in cfg["alphas"]
    )


def design_matrix(
    days: np.ndarray[Any, Any], order: int, center: float, scale: float, period_days: float
) -> np.ndarray[Any, Any]:
    """Tendencia estandarizada + armónicos de Fourier; ``days`` son ordinales del ds MMWR."""
    columns = [(days - center) / scale]
    for k in range(1, order + 1):
        angle = (2.0 * np.pi * k / period_days) * days
        columns.append(np.sin(angle))
        columns.append(np.cos(angle))
    return np.column_stack(columns)


def _days(periods: list[tuple[int, int]]) -> np.ndarray[Any, Any]:
    """Ordinales del ``ds`` epidemiológico (MMWR); nunca ``date.fromisocalendar``."""
    return np.asarray([ds_for(y, w).toordinal() for y, w in periods], dtype=float)


def fit_coefficients(
    days_fit: np.ndarray[Any, Any],
    y_fit: np.ndarray[Any, Any],
    cand: Candidate,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Ajusta un Ridge y devuelve su estado PORTABLE (coeficientes + escalador + diseño)."""
    from sklearn.linear_model import Ridge

    center = float(days_fit.mean())
    scale = float(days_fit.std()) or 1.0
    period = float(cfg["seasonal_period_days"])
    model = Ridge(
        alpha=cand.alpha, solver=str(cfg["solver"]), fit_intercept=bool(cfg["fit_intercept"])
    )
    model.fit(design_matrix(days_fit, cand.fourier_order, center, scale, period), y_fit)
    return {
        "coef": [float(c) for c in np.asarray(model.coef_).ravel()],
        "intercept": float(model.intercept_),
        "center": center,
        "scale": scale,
        "fourier_order": cand.fourier_order,
        "alpha": cand.alpha,
        "seasonal_period_days": period,
        "solver": str(cfg["solver"]),
    }


def predict_from_state(state: dict[str, Any], days: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Predicción en espacio transformado desde el estado portable (sin sklearn en la carga)."""
    design = design_matrix(
        days,
        int(state["fourier_order"]),
        float(state["center"]),
        float(state["scale"]),
        float(state["seasonal_period_days"]),
    )
    return np.asarray(design @ np.asarray(state["coef"], dtype=float) + state["intercept"])


def _fit_predict(
    days_fit: np.ndarray[Any, Any],
    y_fit: np.ndarray[Any, Any],
    days_target: np.ndarray[Any, Any],
    cand: Candidate,
    cfg: dict[str, Any],
) -> tuple[np.ndarray[Any, Any], float, float]:
    """Ajusta un Ridge y predice en espacio transformado. Escalador SOLO del set de ajuste."""
    state = fit_coefficients(days_fit, y_fit, cand, cfg)
    predicted = predict_from_state(state, days_target)
    return predicted, float(np.linalg.norm(state["coef"])), float(state["intercept"])


def _to_counts(transform: Any, values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any] | None:
    """Invierte al espacio de conteos; ``None`` si el resultado no es utilizable (sin recortar)."""
    try:
        with np.errstate(over="ignore"):  # el desbordamiento de expm1 es una condición MANEJADA
            counts = transform.apply_inverse(values)
    except (ValueError, TransformContractError):
        return None
    if not np.isfinite(counts).all() or (counts < 0).any():
        return None
    return cast("np.ndarray[Any, Any]", counts)


def _select(
    who: str,
    transform: Any,
    days: np.ndarray[Any, Any],
    y: np.ndarray[Any, Any],
    counts: np.ndarray[Any, Any],
    cfg: dict[str, Any],
) -> tuple[Candidate, float, int]:
    """Selección temporal interna: rejilla completa sobre inner-train, sMAPE en inner-validation."""
    n_val = int(cfg["inner_validation_weeks"])
    split = len(y) - n_val
    if split < int(cfg["min_inner_train_weeks"]):
        raise RidgeFitError(
            f"{who}: inner-train de {split} semanas (< {cfg['min_inner_train_weeks']})"
        )

    scored: list[tuple[float, int, float, Candidate]] = []
    for cand in candidates(cfg):
        predicted, _, _ = _fit_predict(days[:split], y[:split], days[split:], cand, cfg)
        val_counts = _to_counts(transform, predicted)
        if val_counts is None:
            continue  # candidato inválido: no se recorta, se descarta
        # Desempate declarado: menor sMAPE → menor orden de Fourier → mayor alpha.
        scored.append(
            (smape_percent(counts[split:], val_counts), cand.fourier_order, -cand.alpha, cand)
        )
    if not scored:
        raise RidgeFitError(f"{who}: ningún candidato Ridge produjo conteos utilizables")
    best = min(scored, key=lambda row: (row[0], row[1], row[2]))
    return best[3], best[0], len(scored)


def make_predictor(cfg: dict[str, Any]) -> harness.PredictFn:
    """Predictor Ridge: selección interna + refit sobre el train exterior + forecast del holdout."""

    def predict(request: harness.SeriesRequest) -> harness.SeriesForecast:
        periods, counts = harness.train_series(request)  # contiguo y ordenado
        transform = request.spec.transform
        y = transform.apply_forward(counts)  # log1p gobernado por el contrato
        days = _days(periods)

        who = f"{ct.series_key_str(request.spec.key)}/{request.spec.fold_id}"
        cand, inner_smape, n_valid = _select(who, transform, days, y, counts, cfg)
        predicted, coef_norm, intercept = _fit_predict(
            days, y, _days(list(request.holdout)), cand, cfg
        )
        forecast = _to_counts(transform, predicted)
        if forecast is None:
            raise RidgeFitError(
                f"{ct.series_key_str(request.spec.key)}/{request.spec.fold_id}: el refit "
                f"(order={cand.fourier_order}, alpha={cand.alpha}) produjo conteos inutilizables"
            )
        n_val = int(cfg["inner_validation_weeks"])
        return harness.SeriesForecast(
            dict(zip(request.holdout, (float(v) for v in forecast), strict=True)),
            diagnostics={
                "fourier_order": cand.fourier_order,
                "alpha": cand.alpha,
                "inner_smape": inner_smape,
                "n_inner_train": len(y) - n_val,
                "n_inner_validation": n_val,
                "n_candidates": len(candidates(cfg)),
                "n_candidates_valid": n_valid,
                "coef_norm": coef_norm,
                "intercept": intercept,
            },
        )

    return predict


def fit_final(cfg: dict[str, Any], window: fm.FinalWindow) -> fm.FinalState:
    """Refit final: misma selección interna, sobre TODA la historia; estado portable en JSON."""
    periods = sorted(window.train)
    counts = np.asarray([window.train[p] for p in periods], dtype=float)
    transform = window.spec.transform
    y = transform.apply_forward(counts)
    days = _days(periods)
    who = ct.series_key_str(window.spec.key)
    cand, inner_smape, n_valid = _select(who, transform, days, y, counts, cfg)
    state = fit_coefficients(days, y, cand, cfg)
    if _to_counts(transform, predict_from_state(state, days[-1:])) is None:
        raise RidgeFitError(f"{who}: el refit final produjo conteos inutilizables")
    return fm.FinalState(
        fmt=fm.FMT_JSON,
        text=json.dumps(state, sort_keys=True, separators=(",", ":")),
        config={
            "fourier_order": cand.fourier_order,
            "alpha": cand.alpha,
            "inner_smape": inner_smape,
            "n_candidates_valid": n_valid,
            "solver": str(cfg["solver"]),
        },
    )


def forecast_final(
    state: fm.FinalState, request: fm.ForecastRequest
) -> dict[tuple[int, int], float]:
    """Pronostica desde los coeficientes serializados; NO reajusta ni necesita sklearn."""
    payload = json.loads(state.text or "{}")
    predicted = predict_from_state(payload, _days(list(request.periods)))
    counts = _to_counts(request.transform, predicted)
    if counts is None:
        raise RidgeFitError("forecast final Ridge inutilizable tras la inversa")
    return dict(zip(request.periods, (float(v) for v in counts), strict=True))


class RidgeHarmonicAdapter:
    """Adapter del motor Ridge armónico; delega todo el flujo común al harness."""

    name = ENGINE

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._cfg = cfg
        self._predict = make_predictor(cfg)

    def supports(self, command: str) -> bool:
        return command in _SUPPORTED

    def run(self, command: str, run_dir: str) -> list[ArtifactRecord]:
        import sklearn  # versión efectiva → entra al spec.json y al config_digest

        params = {k: v for k, v in self._cfg.items() if k != "resource_limits"}
        if command == "refit":
            return refit.run_refit(
                self.name,
                lambda w: fit_final(self._cfg, w),
                run_dir,
                {**params, "sklearn_version": sklearn.__version__},
                transform=ct.log1p_transform,
                resource_limits=dict(self._cfg["resource_limits"]),
                versions={"sklearn_version": sklearn.__version__},
            )
        if command == "forecast":
            return forecasting.run_forecast(self.name, forecast_final, run_dir)
        return harness.run_benchmark(
            self.name,
            self._predict,
            run_dir,
            {**params, "sklearn_version": sklearn.__version__},
            transform=ct.log1p_transform,
            resource_limits=dict(self._cfg["resource_limits"]),
        )


register_adapter(ENGINE, RidgeHarmonicAdapter(load_ridge_config()))
