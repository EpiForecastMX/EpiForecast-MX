"""F2/C3c — motor ``ets_add_damped_log1p``: Holt-Winters aditivo amortiguado sobre log1p.

Primer motor del carril E66 que AJUSTA de verdad: un ajuste independiente por serie base y fold
(64 × 4 = 256 ajustes OOS en el stage full). Solo aporta su ``PredictFn``; folds, derivación
64→111, métricas y artefactos siguen siendo del harness compartido.

Contrato (declarado en ``config/engines/ets.yaml``):
- statsmodels Holt-Winters sobre log1p de los conteos; la inversa expm1 la gobierna el
  ``TransformContract`` del ``TrainingSpec``, nunca un ``expm1`` suelto en el motor.
- Variante primaria: tendencia aditiva AMORTIGUADA + estacionalidad aditiva de periodo 52,
  inicialización estimada, ajuste optimizado y SIN corrección de bias.
- Si la primaria no converge (o emite ConvergenceWarning, o su pronóstico no es utilizable) se
  reintenta UNA vez con ETS aditivo estacional SIN tendencia. Si el retry también falla o produce
  negativos/no finitos, el job entero termina rc≠0 conservando el diagnóstico.
- Sin clipping, sin redondeo y sin fallback a cero ni a Seasonal Naive: un motor que no puede
  ajustar falla en voz alta (el ``ETSExpert`` legacy hace lo contrario; por eso NO se reutiliza).

Limitación declarada: el periodo estacional es 52 fijo, así que los años MMWR de 53 semanas
(2014, 2020, 2025) desplazan la fase una semana dentro del train. Es una propiedad del motor.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
import warnings

import numpy as np
from omegaconf import OmegaConf

from epiforecast.artifacts.transforms import TransformContractError
from epiforecast.data.epi_calendar import shift
from epiforecast.runner import contracts as ct
from epiforecast.runner.adapters import register_adapter
from epiforecast.runner.engines import harness
from epiforecast.runner.manifest import ArtifactRecord

ENGINE = "ets_add_damped_log1p"
_ROOT = Path(__file__).resolve().parents[4]
_CONFIG = _ROOT / "config" / "engines" / "ets.yaml"
_SUPPORTED = frozenset({"benchmark"})
_MIN_SEASONS = 2  # statsmodels exige ≥ 2 estaciones completas para inicializar la estacionalidad


class EtsFitError(RuntimeError):
    """El ajuste ETS no es utilizable en ninguna variante: el job termina rc≠0 (nunca ceros)."""


@dataclass(frozen=True)
class Variant:
    """Una variante declarada del ajuste; ``strict`` exige convergencia limpia del optimizador."""

    name: str
    strict: bool
    trend: str | None
    damped_trend: bool
    seasonal: str | None
    seasonal_periods: int
    initialization_method: str


def load_ets_config() -> dict[str, Any]:
    return cast("dict[str, Any]", OmegaConf.to_container(OmegaConf.load(_CONFIG), resolve=True))


def _variants(cfg: dict[str, Any]) -> tuple[Variant, ...]:
    return tuple(
        Variant(
            name=str(v["name"]),
            strict=bool(v["strict"]),
            trend=None if v["trend"] is None else str(v["trend"]),
            damped_trend=bool(v["damped_trend"]),
            seasonal=None if v["seasonal"] is None else str(v["seasonal"]),
            seasonal_periods=int(v["seasonal_periods"]),
            initialization_method=str(v["initialization_method"]),
        )
        for v in cfg["variants"]
    )


def _fit_forecast(
    y: np.ndarray[Any, Any], horizon: int, variant: Variant, cfg: dict[str, Any]
) -> tuple[np.ndarray[Any, Any], bool, list[str], float]:
    """Ajusta UNA variante y pronostica en espacio transformado. Devuelve (fc, converged, warns, aic)."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        res = ExponentialSmoothing(
            y,
            trend=variant.trend,
            damped_trend=variant.damped_trend,
            seasonal=variant.seasonal,
            seasonal_periods=variant.seasonal_periods,
            initialization_method=variant.initialization_method,
            use_boxcox=bool(cfg["use_boxcox"]),
        ).fit(optimized=bool(cfg["optimized"]), remove_bias=bool(cfg["remove_bias"]))
        forecast = np.asarray(res.forecast(horizon), dtype=float)
    names = sorted({type(w.message).__name__ for w in caught})
    converged = bool((res.mle_retvals or {}).get("success", False))
    return forecast, converged, names, float(res.aic)


def _attempt(
    request: harness.SeriesRequest,
    y: np.ndarray[Any, Any],
    variant: Variant,
    cfg: dict[str, Any],
) -> tuple[np.ndarray[Any, Any] | None, dict[str, Any]]:
    """Intenta una variante; devuelve (casos, info) o (None, info) con el motivo del rechazo."""
    info: dict[str, Any] = {
        "variant": variant.name,
        "converged": False,
        "warnings": "",
        "aic": float("nan"),
    }
    try:
        fc, converged, names, aic = _fit_forecast(y, len(request.holdout), variant, cfg)
        info.update(converged=converged, warnings="|".join(names), aic=aic)
        counts = request.spec.transform.apply_inverse(fc)  # expm1 gobernado por el contrato
    except (ValueError, TypeError, np.linalg.LinAlgError, TransformContractError) as exc:
        info["rejected"] = f"{type(exc).__name__}: {exc}"
        return None, info
    if not np.isfinite(counts).all() or (counts < 0).any():
        info["rejected"] = f"pronóstico inutilizable (min={counts.min():.6g})"
        return None, info
    if variant.strict and (not converged or "ConvergenceWarning" in names):
        info["rejected"] = "no convergió" if not converged else "ConvergenceWarning"
        return None, info
    info["rejected"] = ""
    return counts, info


def _train_array(request: harness.SeriesRequest, seasonal_periods: int) -> np.ndarray[Any, Any]:
    """Serie de train contigua y con historia suficiente (fail-closed; nunca rellena huecos)."""
    periods = sorted(request.train)
    who = ct.series_key_str(request.spec.key)
    for prev, cur in zip(periods, periods[1:], strict=False):
        if shift(prev[0], prev[1], 1) != cur:
            raise EtsFitError(
                f"{who}/{request.spec.fold_id}: hueco en el train entre {prev} y {cur}"
            )
    if len(periods) < _MIN_SEASONS * seasonal_periods:
        raise EtsFitError(
            f"{who}/{request.spec.fold_id}: {len(periods)} semanas de train "
            f"(< {_MIN_SEASONS} estaciones de {seasonal_periods})"
        )
    return np.asarray([request.train[p] for p in periods], dtype=float)


def make_predictor(cfg: dict[str, Any]) -> harness.PredictFn:
    """Predictor ETS: ajuste por serie/fold, reintento único declarado y diagnóstico por ajuste."""
    variants = _variants(cfg)

    def predict(request: harness.SeriesRequest) -> harness.SeriesForecast:
        counts = _train_array(request, variants[0].seasonal_periods)
        y = request.spec.transform.apply_forward(counts)  # log1p gobernado por el contrato
        attempts: list[dict[str, Any]] = []
        for variant in variants:
            preds, info = _attempt(request, y, variant, cfg)
            attempts.append(info)
            if preds is not None:
                diagnostics = {
                    **info,
                    "n_attempts": len(attempts),
                    "primary_rejected": attempts[0]["rejected"] if len(attempts) > 1 else "",
                }
                return harness.SeriesForecast(
                    dict(zip(request.holdout, (float(v) for v in preds), strict=True)),
                    diagnostics=diagnostics,
                )
        raise EtsFitError(
            f"{ct.series_key_str(request.spec.key)}/{request.spec.fold_id}: ninguna variante ETS "
            f"produjo un pronóstico utilizable ({attempts})"
        )

    return predict


class EtsAdapter:
    """Adapter del motor ETS; delega todo el flujo común al harness (solo aporta su PredictFn)."""

    name = ENGINE

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._cfg = cfg
        self._predict = make_predictor(cfg)

    def supports(self, command: str) -> bool:
        return command in _SUPPORTED

    def run(self, command: str, run_dir: str) -> list[ArtifactRecord]:
        return harness.run_benchmark(
            self.name,
            self._predict,
            run_dir,
            {
                "implementation": self._cfg["implementation"],
                "target_transform": self._cfg["target_transform"],
                "optimized": self._cfg["optimized"],
                "remove_bias": self._cfg["remove_bias"],
                "use_boxcox": self._cfg["use_boxcox"],
                "variants": self._cfg["variants"],
            },
            transform=ct.log1p_transform,
            resource_limits=dict(self._cfg["resource_limits"]),
        )


register_adapter(ENGINE, EtsAdapter(load_ets_config()))
