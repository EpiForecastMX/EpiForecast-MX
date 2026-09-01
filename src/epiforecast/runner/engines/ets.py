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
import io
from pathlib import Path
import pickle
from typing import Any, cast
import warnings

import numpy as np
from omegaconf import OmegaConf

from epiforecast.artifacts.transforms import TransformContractError
from epiforecast.runner import contracts as ct
from epiforecast.runner import final_models as fm
from epiforecast.runner import forecasting, refit
from epiforecast.runner.adapters import register_adapter
from epiforecast.runner.engines import harness
from epiforecast.runner.manifest import ArtifactRecord

ENGINE = "ets_add_damped_log1p"
_ROOT = Path(__file__).resolve().parents[4]
_CONFIG = _ROOT / "config" / "engines" / "ets.yaml"
_SUPPORTED = frozenset({"benchmark", "refit", "forecast"})
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


def _fit_result(
    y: np.ndarray[Any, Any], variant: Variant, cfg: dict[str, Any]
) -> tuple[Any, bool, list[str], float]:
    """Ajusta UNA variante y devuelve el RESULTADO de statsmodels (+ convergencia, warnings, AIC)."""
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
    names = sorted({type(w.message).__name__ for w in caught})
    converged = bool((res.mle_retvals or {}).get("success", False))
    return res, converged, names, float(res.aic)


def _fit_forecast(
    y: np.ndarray[Any, Any], horizon: int, variant: Variant, cfg: dict[str, Any]
) -> tuple[np.ndarray[Any, Any], bool, list[str], float]:
    """Ajusta UNA variante y pronostica en espacio transformado. Devuelve (fc, converged, warns, aic)."""
    res, converged, names, aic = _fit_result(y, variant, cfg)
    return np.asarray(res.forecast(horizon), dtype=float), converged, names, aic


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
    """Serie de train contigua (harness) y con historia suficiente para inicializar la estación."""
    periods, counts = harness.train_series(request)  # contigüidad: invariante compartido
    if len(periods) < _MIN_SEASONS * seasonal_periods:
        raise EtsFitError(
            f"{ct.series_key_str(request.spec.key)}/{request.spec.fold_id}: {len(periods)} "
            f"semanas de train (< {_MIN_SEASONS} estaciones de {seasonal_periods})"
        )
    return counts


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


def fit_final(cfg: dict[str, Any], window: fm.FinalWindow) -> fm.FinalState:
    """Refit final: misma política de variantes, sobre TODA la historia; estado = pickle versionado."""
    periods = sorted(window.train)
    counts = np.asarray([window.train[p] for p in periods], dtype=float)
    variants = _variants(cfg)
    if len(periods) < _MIN_SEASONS * variants[0].seasonal_periods:
        raise EtsFitError(f"{ct.series_key_str(window.spec.key)}: historia insuficiente")
    transform = window.spec.transform
    y = transform.apply_forward(counts)
    rejections: list[str] = []
    for variant in variants:
        try:
            res, converged, names, aic = _fit_result(y, variant, cfg)
            fc = transform.apply_inverse(
                np.asarray(res.forecast(window.spec.horizon), dtype=float)
            )
        except (ValueError, TypeError, np.linalg.LinAlgError, TransformContractError) as exc:
            rejections.append(f"{variant.name}: {type(exc).__name__}")
            continue
        if not np.isfinite(fc).all() or (fc < 0).any():
            rejections.append(f"{variant.name}: pronóstico inutilizable")
            continue
        if variant.strict and (not converged or "ConvergenceWarning" in names):
            rejections.append(f"{variant.name}: sin convergencia limpia")
            continue
        import pickle  # el estado se sella con digest y solo lo lee este runner

        return fm.FinalState(
            fmt=fm.FMT_STATSMODELS_PICKLE,
            data=pickle.dumps(res, protocol=pickle.HIGHEST_PROTOCOL),
            config={
                "variant": variant.name,
                "trend": variant.trend,
                "damped_trend": variant.damped_trend,
                "seasonal": variant.seasonal,
                "seasonal_periods": variant.seasonal_periods,
                "converged": converged,
                "warnings": "|".join(names),
                "aic": aic,
            },
        )
    raise EtsFitError(
        f"{ct.series_key_str(window.spec.key)}: refit final sin variante utilizable ({rejections})"
    )


def forecast_final(
    state: fm.FinalState, request: fm.ForecastRequest
) -> dict[tuple[int, int], float]:
    """Pronostica desde el resultado serializado; NO reajusta."""
    res = _load_statsmodels_state(state.data or b"")
    fc = np.asarray(res.forecast(len(request.periods)), dtype=float)
    counts = request.transform.apply_inverse(fc)
    if not np.isfinite(counts).all() or (counts < 0).any():
        raise EtsFitError("forecast final ETS inutilizable tras la inversa")
    return dict(zip(request.periods, (float(v) for v in counts), strict=True))


def _load_statsmodels_state(data: bytes) -> Any:
    """Carga un estado sellado y soporta el cambio `_xp` introducido por SciPy 1.18.

    Los pickles creados antes de ese cambio contienen un ``LbfgsInvHessProduct`` sin la
    nueva clave privada. El loader normal sigue siendo la primera ruta. Sólo ante ese
    ``KeyError`` exacto se usa un unpickler local que completa el namespace NumPy del
    operador; no parchea clases globales ni silencia ningún otro error de deserialización.
    """
    try:
        return pickle.loads(data)  # noqa: S301 — estado propio, verificado antes por digest
    except KeyError as exc:
        if exc.args != ("_xp",):
            raise

    from scipy.optimize._lbfgsb_py import LbfgsInvHessProduct
    from scipy.sparse.linalg import aslinearoperator

    numpy_namespace = aslinearoperator(np.empty((0, 0)))._xp

    class LegacyScipyUnpickler(pickle.Unpickler):
        def __init__(self, stream: io.BytesIO) -> None:
            super().__init__(stream)
            self._compat_class: type[Any] | None = None

        def find_class(self, module: str, name: str) -> Any:
            cls = super().find_class(module, name)
            if cls is not LbfgsInvHessProduct:
                return cls
            if self._compat_class is None:
                original_setstate = cls.__setstate__

                def setstate(instance: Any, state: dict[str, Any]) -> None:
                    if "_xp" in state:
                        original_setstate(instance, state)
                        return
                    instance.__dict__.update(state)
                    instance._xp = numpy_namespace

                self._compat_class = type(
                    "LegacyLbfgsInvHessProduct",
                    (cls,),
                    {"__setstate__": setstate},
                )
            return self._compat_class

    return LegacyScipyUnpickler(io.BytesIO(data)).load()  # noqa: S301


def _statsmodels_version() -> str:
    from importlib.metadata import version

    return version("statsmodels")


class EtsAdapter:
    """Adapter del motor ETS; delega todo el flujo común al harness (solo aporta su PredictFn)."""

    name = ENGINE

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._cfg = cfg
        self._predict = make_predictor(cfg)

    def supports(self, command: str) -> bool:
        return command in _SUPPORTED

    def forecast_state(
        self, state: fm.FinalState, request: fm.ForecastRequest
    ) -> dict[tuple[int, int], float]:
        """Capacidad R15.4: delega en ``forecast_final`` (una sola implementación)."""
        return forecast_final(state, request)

    def _engine_params(self) -> dict[str, Any]:
        return {
            "implementation": self._cfg["implementation"],
            "target_transform": self._cfg["target_transform"],
            "optimized": self._cfg["optimized"],
            "remove_bias": self._cfg["remove_bias"],
            "use_boxcox": self._cfg["use_boxcox"],
            "variants": self._cfg["variants"],
        }

    def run(self, command: str, run_dir: str) -> list[ArtifactRecord]:
        if command == "refit":
            return refit.run_refit(
                self.name,
                lambda w: fit_final(self._cfg, w),
                run_dir,
                self._engine_params(),
                transform=ct.log1p_transform,
                resource_limits=dict(self._cfg["resource_limits"]),
                versions={"statsmodels_version": _statsmodels_version()},
            )
        if command == "forecast":
            return forecasting.run_forecast(self.name, forecast_final, run_dir)
        return harness.run_benchmark(
            self.name,
            self._predict,
            run_dir,
            self._engine_params(),
            transform=ct.log1p_transform,
            resource_limits=dict(self._cfg["resource_limits"]),
        )


register_adapter(ENGINE, EtsAdapter(load_ets_config()))
