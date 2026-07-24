"""F2/C4.3 — motores Prophet del runner genérico: ``prophet_count_log1p`` y ``prophet_rate_log1p``.

Dos perfiles FIJOS que se diferencian ÚNICAMENTE en su ``TransformContract`` (conteo+log1p frente a
tasa/100k+log1p). No reutilizan nada del ``ProphetForecaster`` legacy —ni su CV, ni sus pesos, ni
sus fallbacks— y no tocan el pipeline neuro/Dengue.

Contrato (declarado en ``config/engines/prophet.yaml``):
- Ajuste MAP (``uncertainty_samples=0``, ``mcmc_samples=0``), crecimiento lineal.
- Estacionalidades nativas de Prophet DESACTIVADAS; una sola estacionalidad declarada,
  ``annual_mmwr`` de 365.25 días sobre el ``ds`` MMWR. Sin ENSO, holidays COVID ni regresores.
- El ``TransformContract`` es la ÚNICA autoridad del log1p/expm1 y de tasa↔casos: el motor pasa la
  exposición del periodo y el contrato hace la conversión. Nada de expm1 ni divisiones sueltas.
- Los hiperparámetros vienen CONGELADOS del comando ``tune`` (clave ``frozen`` del YAML). Durante el
  benchmark no se reabre la rejilla: si el perfil no está congelado, el job falla cerrado.
- Sin clipping, sin redondeo y sin fallback: predicción negativa, no finita o ajuste fallido
  terminan el job con rc≠0.

``supports()``: ``tune`` (rejilla completa sobre centinelas) y ``benchmark`` (configuración fija).
"""

from __future__ import annotations

import itertools
import logging
from pathlib import Path
from typing import Any, cast
import warnings

import numpy as np
from omegaconf import OmegaConf
import pandas as pd

from epiforecast.data.epi_calendar import ds_for
from epiforecast.runner import contracts as ct
from epiforecast.runner import tuning
from epiforecast.runner.adapters import register_adapter
from epiforecast.runner.engines import harness
from epiforecast.runner.manifest import ArtifactRecord

_ROOT = Path(__file__).resolve().parents[4]
_CONFIG = _ROOT / "config" / "engines" / "prophet.yaml"
_SUPPORTED = frozenset({"benchmark", "tune"})
_TRANSFORMS: dict[str, harness.TransformFactory] = {
    "log1p": ct.log1p_transform,
    "rate_log1p": ct.rate_log1p_transform,
}


class ProphetEngineError(RuntimeError):
    """El perfil Prophet no puede ejecutarse (sin congelar) o su ajuste no es utilizable."""


def load_prophet_config() -> dict[str, Any]:
    return cast("dict[str, Any]", OmegaConf.to_container(OmegaConf.load(_CONFIG), resolve=True))


def build_grid(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Producto cartesiano en el orden declarado (determinista y reproducible)."""
    grid = cfg["grid"]
    keys = list(grid)
    return [dict(zip(keys, values, strict=True)) for values in itertools.product(*grid.values())]


def _versions() -> dict[str, str]:
    """Versiones EFECTIVAS del stack de ajuste (entran al spec.json y al config_digest)."""
    from importlib.metadata import version

    return {"prophet_version": version("prophet"), "cmdstanpy_version": version("cmdstanpy")}


def _exposure_for(request: harness.SeriesRequest, periods: list[tuple[int, int]]) -> Any:
    """Exposición de los periodos SOLO si el contrato la requiere (si no, el contrato la rechaza)."""
    if not request.spec.transform.requires_exposure:
        return None
    source = request.train_exposure if periods[0] <= request.origin else request.holdout_exposure
    return np.asarray([source[p] for p in periods], dtype=float)


def _fit_forecast(
    frame: pd.DataFrame, future: pd.DataFrame, config: dict[str, Any], common: dict[str, Any]
) -> np.ndarray[Any, Any]:
    """Un ajuste MAP de Prophet en espacio transformado (sin intervalos, sin regresores)."""
    from prophet import Prophet

    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
    logging.getLogger("prophet").setLevel(logging.WARNING)
    model = Prophet(
        growth=str(common["growth"]),
        yearly_seasonality=bool(common["yearly_seasonality"]),
        weekly_seasonality=bool(common["weekly_seasonality"]),
        daily_seasonality=bool(common["daily_seasonality"]),
        n_changepoints=int(common["n_changepoints"]),
        changepoint_range=float(common["changepoint_range"]),
        seasonality_mode=str(config["seasonality_mode"]),
        changepoint_prior_scale=float(config["changepoint_prior_scale"]),
        seasonality_prior_scale=float(config["seasonality_prior_scale"]),
        uncertainty_samples=int(common["uncertainty_samples"]),
        mcmc_samples=int(common["mcmc_samples"]),
    )
    model.add_seasonality(
        name=str(common["seasonality_name"]),
        period=float(common["seasonality_period_days"]),
        fourier_order=int(config["fourier_order"]),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(frame)
        forecast = model.predict(future)
    return np.asarray(forecast["yhat"].to_numpy(), dtype=float)


def make_predictor(common: dict[str, Any], config: dict[str, Any]) -> harness.PredictFn:
    """Predictor Prophet con UNA configuración fija (la congelada, o una de la rejilla en tune)."""

    def predict(request: harness.SeriesRequest) -> harness.SeriesForecast:
        periods, counts = harness.train_series(request)
        transform = request.spec.transform
        y = transform.apply_forward(counts, exposure=_exposure_for(request, periods))
        frame = pd.DataFrame({"ds": [pd.Timestamp(ds_for(*p)) for p in periods], "y": y})
        holdout = list(request.holdout)
        future = pd.DataFrame({"ds": [pd.Timestamp(ds_for(*p)) for p in holdout]})

        who = f"{ct.series_key_str(request.spec.key)}/{request.spec.fold_id}"
        try:
            yhat = _fit_forecast(frame, future, config, common)
            forecast = transform.apply_inverse(yhat, exposure=_exposure_for(request, holdout))
        except Exception as exc:  # noqa: BLE001 — se propaga como fallo del job, nunca un fallback
            raise ProphetEngineError(f"{who}: ajuste Prophet fallido ({exc})") from exc
        if not np.isfinite(forecast).all() or (forecast < 0).any():
            raise ProphetEngineError(
                f"{who}: pronóstico inutilizable tras la inversa (min={forecast.min():.6g})"
            )
        return harness.SeriesForecast(
            dict(zip(request.holdout, (float(v) for v in forecast), strict=True)),
            diagnostics={**config, "n_changepoints": int(common["n_changepoints"])},
        )

    return predict


class ProphetProfileAdapter:
    """Un perfil Prophet (conteo o tasa): mismo motor, distinto TransformContract."""

    def __init__(self, name: str, cfg: dict[str, Any]) -> None:
        self.name = name
        self._cfg = cfg
        self._profile = cfg["engines"][name]
        self._transform = _TRANSFORMS[str(self._profile["transform"])]

    def supports(self, command: str) -> bool:
        return command in _SUPPORTED

    def _params(self, extra: dict[str, Any]) -> dict[str, Any]:
        return {
            **self._cfg["common"],
            "transform": self._profile["transform"],
            **_versions(),
            **extra,
        }

    def _frozen(self) -> dict[str, Any]:
        frozen = self._profile.get("frozen")
        if not frozen:
            raise ProphetEngineError(
                f"{self.name}: sin configuración congelada. Corre `disease_run tune` y escribe el "
                "ganador en config/engines/prophet.yaml (el benchmark nunca reabre la rejilla)."
            )
        return dict(frozen)

    def run(self, command: str, run_dir: str) -> list[ArtifactRecord]:
        limits = dict(self._cfg["resource_limits"])
        if command == "tune":
            return tuning.run_tuning(
                self.name,
                build_grid(self._cfg),
                lambda config: make_predictor(self._cfg["common"], config),
                run_dir,
                dict(self._cfg["selection"]),
                transform=self._transform,
                resource_limits=limits,
                params=self._params({"grid": self._cfg["grid"]}),
            )
        frozen = self._frozen()
        return harness.run_benchmark(
            self.name,
            make_predictor(self._cfg["common"], frozen),
            run_dir,
            self._params({"frozen": frozen}),
            transform=self._transform,
            resource_limits=limits,
        )


def _register_all() -> None:
    cfg = load_prophet_config()
    for name in cfg["engines"]:
        register_adapter(name, ProphetProfileAdapter(name, cfg))


_register_all()
