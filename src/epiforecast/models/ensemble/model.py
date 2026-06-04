"""Ensemble forecasting model: Prophet base + XGBoost residual correction."""

from __future__ import annotations

import logging
from pathlib import Path
import pickle
import time
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from epiforecast.constants import RANDOM_SEED
from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.utils.cohorts import is_count_log_cohort

if TYPE_CHECKING:
    from prophet import Prophet
    from xgboost import XGBRegressor

from epiforecast.models.base import ForecastModel
from epiforecast.models.ensemble.feature_builder import (
    FEATURE_NAMES,
    construir_features_xgb,
    construir_holidays,
)
from epiforecast.models.ensemble.helpers import (
    _predecir_test_recursivo,
    calcular_metricas_ensemble,
    calcular_metricas_prophet_base,
    generar_prediccion_completa,
    generar_predicciones_insample,
    preparar_datos_ensemble,
)
from epiforecast.models.ensemble.oof_residuals import generate_oof_residuals
from epiforecast.models.ensemble.parallel_engine import ParallelEngine
from epiforecast.models.factory import register_model
from epiforecast.utils.config import conf, logger

logging.getLogger("cmdstanpy").disabled = True


@register_model("ensemble")
class EnsembleForecaster(ForecastModel):
    """Ensemble: Prophet base + XGBoost sobre residuos (ForecastModel/LSP)."""

    def __init__(
        self,
        df: pd.DataFrame | None = None,
        sexo: str = "incrementos_total",
        entidad: str | None = None,
        padecimiento: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        self._conf = config if config is not None else conf
        self.df = df.copy() if df is not None else pd.DataFrame()
        self.sexo, self.entidad, self.padecimiento = sexo, entidad, padecimiento
        self.cutoff: str = self._conf.get(
            "FECHA_CORTE_ENTRENAMIENTO_ENSEMBLE",
            self._conf.get("FECHA_CORTE_ENTRENAMIENTO", "2025-01-01"),
        )
        self.horizon: int = self._conf.get("HORIZON_ENSEMBLE", 52)
        pb = self._conf.get("prophet_base", {})
        self._prophet_hp: dict[str, Any] = {
            "changepoint_prior_scale": pb.get("changepoint_prior_scale", 0.05),
            "seasonality_prior_scale": pb.get("seasonality_prior_scale", 0.1),
            "seasonality_mode": pb.get("seasonality_mode", "additive"),
        }
        yc = pb.get("yearly_custom", {})
        self._yearly_period: float = yc.get("period", 365.25)
        self._yearly_fourier: int = yc.get("fourier_order", 10)
        self._oof_residual_folds: int = int(self._conf.get("oof_residual_folds", 0))
        xgb_hp = self._conf.get("xgboost", {})
        self._xgb_hp: dict[str, Any] = {
            "n_estimators": xgb_hp.get("n_estimators", 200),
            "max_depth": xgb_hp.get("max_depth", 3),
            "learning_rate": xgb_hp.get("learning_rate", 0.03),
            "subsample": xgb_hp.get("subsample", 0.8),
            "colsample_bytree": xgb_hp.get("colsample_bytree", 0.7),
            "min_child_weight": xgb_hp.get("min_child_weight", 5),
            "reg_alpha": xgb_hp.get("reg_alpha", 0.1),
            "reg_lambda": xgb_hp.get("reg_lambda", 1.0),
        }
        self._ensemble_mode: str = str(self._conf.get("ensemble_mode", "parallel"))
        self._holidays: pd.DataFrame = construir_holidays(self._conf, self.padecimiento)
        self._prophet: Prophet | None = None
        self._xgb: XGBRegressor | None = None
        self._feature_names: list[str] = list(FEATURE_NAMES)
        self._parallel_engine: ParallelEngine | None = (
            ParallelEngine(
                self._prophet_hp,
                self._yearly_period,
                self._yearly_fourier,
                self._holidays,
                self._xgb_hp,
                float(self._conf.get("parallel_alpha", 1.0)),
                int(self._conf.get("parallel_oof_folds", 4)),
                str(self._conf.get("parallel_oof_cutoff", "2024-01-01")),
                int(self._conf.get("parallel_min_train_weeks", 104)),
            )
            if self._ensemble_mode == "parallel"
            else None
        )
        self.serie: pd.DataFrame = pd.DataFrame()
        self.train_data: pd.DataFrame = pd.DataFrame()
        self.test_data: pd.DataFrame = pd.DataFrame()
        self.pred_train: pd.DataFrame = pd.DataFrame()
        self.pred_test: pd.DataFrame = pd.DataFrame()
        self._t_prophet: float = 0.0
        self._t_ensemble: float = 0.0

    def fit(self, train_data: pd.DataFrame) -> None:
        """Entrena Prophet base + XGBoost (sequential o parallel segun modo)."""
        self._fit_prophet(train_data)
        if self._ensemble_mode == "parallel" and self._parallel_engine is not None:
            self._parallel_engine.fit(self._prophet, train_data)
            self._t_ensemble = self._parallel_engine.t_ensemble
        else:
            self._fit_xgboost(train_data)

    def _fit_prophet(self, train_data: pd.DataFrame) -> None:
        from prophet import Prophet as _Prophet

        t0 = time.perf_counter()
        np.random.seed(RANDOM_SEED)
        self._prophet = _Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            holidays=self._holidays if not self._holidays.empty else None,
            **self._prophet_hp,
        )
        self._prophet.add_seasonality(
            name="yearly_custom",
            period=self._yearly_period,
            fourier_order=self._yearly_fourier,
        )
        self._prophet.fit(train_data)
        self._t_prophet = time.perf_counter() - t0
        logger.debug("  Prophet base entrenado en {:.1f}s", self._t_prophet)

    def _insample_residuals(
        self, train_data: pd.DataFrame
    ) -> tuple[pd.DataFrame, npt.NDArray[np.floating[Any]]]:
        phat = self._prophet.predict(train_data[["ds"]])["yhat"].values  # type: ignore[union-attr]
        feats = construir_features_xgb(
            train_data["y"].reset_index(drop=True), train_data["ds"].reset_index(drop=True)
        )
        return feats, train_data["y"].values - phat

    def _fit_xgboost(self, train_data: pd.DataFrame) -> None:
        from xgboost import XGBRegressor as _XGBRegressor

        if self._prophet is None:
            raise RuntimeError("Prophet debe entrenarse antes de XGBoost.")
        t1 = time.perf_counter()
        if self._oof_residual_folds > 0:
            feats_train, residuos = generate_oof_residuals(
                train_data,
                self._prophet_hp,
                self._yearly_period,
                self._yearly_fourier,
                self._holidays,
                n_folds=self._oof_residual_folds,
            )
            if feats_train.empty:
                logger.warning("OOF residuos vacio, fallback a in-sample")
                feats_train, residuos = self._insample_residuals(train_data)
        else:
            feats_train, residuos = self._insample_residuals(train_data)
        vm = feats_train.notna().all(axis=1)
        fv, rv = feats_train[vm], residuos[vm.to_numpy()]
        nv = max(int(len(fv) * 0.2), 1)
        self._xgb = _XGBRegressor(**self._xgb_hp, n_jobs=-1, random_state=RANDOM_SEED)
        self._xgb.fit(
            fv.iloc[: len(fv) - nv],
            rv[: len(fv) - nv],
            eval_set=[(fv.iloc[len(fv) - nv :], rv[len(fv) - nv :])],
            verbose=False,
        )
        self._t_ensemble = time.perf_counter() - t1
        logger.debug("  XGBoost residual entrenado en {:.1f}s", self._t_ensemble)

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        if self._ensemble_mode == "parallel" and self._parallel_engine is not None:
            if self._prophet is None:
                raise RuntimeError("Modelo no entrenado. Ejecutar fit() primero.")
            serie = self.serie if not self.serie.empty else self._prophet.history[["ds", "y"]]
            out = self._parallel_engine.predict(self._prophet, serie, horizon)
        else:
            if self._prophet is None or self._xgb is None:
                raise RuntimeError("Modelo no entrenado. Ejecutar fit() primero.")
            serie = self.serie if not self.serie.empty else self._prophet.history[["ds", "y"]]
            out = generar_prediccion_completa(self._prophet, self._xgb, serie, horizon)
        # Guard de plausibilidad para la cohorte de conteos-log (Dengue): XGBoost diverge al
        # extrapolar; se acota a la envolvente estacional histórica (no afecta neuro).
        if is_count_log_cohort(self.padecimiento):
            from epiforecast.models.forecast_guards import clamp_seasonal_envelope

            out = clamp_seasonal_envelope(
                out, serie[["ds", "y"]], cols=("yhat", "yhat_lower", "yhat_upper", "yhat_ensemble")
            )
        return out

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        test_df = data if ("y" in data.columns and not data.empty) else self.test_data
        if test_df.empty:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}
        if self._ensemble_mode == "parallel" and self._parallel_engine is not None:
            return self._parallel_engine.cross_validate(self._prophet, test_df, self.train_data)
        if self._prophet is None or self._xgb is None:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}
        p_pred = self._prophet.predict(test_df[["ds"]])
        xgb_adj = _predecir_test_recursivo(
            self._xgb, p_pred["yhat"].values, self.train_data, test_df
        )
        m = compute_forecast_metrics(
            test_df["y"].to_numpy(),
            p_pred["yhat"].values + xgb_adj,
            self.train_data["y"].to_numpy(),
        )
        return {
            "rmse": m["rmse"] or 0.0,
            "mae": m["mae"] or 0.0,
            "smape": m["smape"] or 0.0,
            "mase": m["mase"] if m["mase"] is not None else 0.0,
        }

    def save(self, path: Path) -> None:
        from epiforecast.utils.model_metadata import build_model_metadata

        if self._ensemble_mode == "parallel":
            if self._prophet is None or self._parallel_engine is None:
                raise RuntimeError("No hay modelo para guardar. Ejecutar fit() primero.")
        elif self._prophet is None or self._xgb is None:
            raise RuntimeError("No hay modelo para guardar. Ejecutar fit() primero.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump(
                {
                    "prophet": self._prophet,
                    "xgb": self._xgb,
                    "params": self.get_params(),
                    "features": self._feature_names,
                    "serie": self.serie,
                    "ensemble_mode": self._ensemble_mode,
                    "parallel_engine": self._parallel_engine,
                    "_metadata": build_model_metadata(),
                },
                f,
            )
        if not self.serie.empty:
            csv_path = path.with_suffix(".csv")
            self.serie.to_csv(csv_path, index=False, encoding="utf-8")
            logger.debug("Serie sidecar guardada: {}", csv_path.name)
        logger.debug("Modelo ensemble guardado: {}", path)

    def load(self, path: Path) -> None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")
        with path.open("rb") as f:
            p = pickle.load(f)  # noqa: S301
        self._prophet = p["prophet"]
        self._xgb = p.get("xgb")
        self._feature_names = p.get("features", list(FEATURE_NAMES))
        self._ensemble_mode = p.get("ensemble_mode", "sequential")
        self._parallel_engine = p.get("parallel_engine")
        if self._parallel_engine is None and p.get("xgb_direct") is not None:
            self._parallel_engine = ParallelEngine(
                {}, 365.25, 10, pd.DataFrame(), {}, 1.0, 4, "2024-01-01", 104
            )
            self._parallel_engine._xgb_direct = p["xgb_direct"]
            self._parallel_engine._ensemble_weights = p.get("ensemble_weights")
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            self.serie = pd.read_csv(csv_path)
            self.serie["ds"] = pd.to_datetime(self.serie["ds"])
        else:
            self.serie = p.get("serie", pd.DataFrame())
            if not self.serie.empty:
                self.serie["ds"] = pd.to_datetime(self.serie["ds"])
        logger.info("Modelo ensemble cargado: {}", path)

    def get_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "prophet": self._prophet_hp,
            "xgboost": self._xgb_hp,
            "yearly_period": self._yearly_period,
            "yearly_fourier": self._yearly_fourier,
            "cutoff": self.cutoff,
            "horizon": self.horizon,
            "oof_residual_folds": self._oof_residual_folds,
            "ensemble_mode": self._ensemble_mode,
        }
        if self._parallel_engine is not None:
            params.update(self._parallel_engine.get_params())
        return params

    def run(self) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        self.serie, self.train_data, self.test_data = preparar_datos_ensemble(
            self.df, self.padecimiento, self.sexo, self.cutoff
        )
        self._fit_prophet(self.train_data)
        if self._ensemble_mode == "parallel" and self._parallel_engine is not None:
            self._parallel_engine.fit(self._prophet, self.train_data)
            self._t_ensemble = self._parallel_engine.t_ensemble
        else:
            from epiforecast.models.ensemble.xgb_tuner import EnsembleXGBTuner

            tuner = EnsembleXGBTuner(self._prophet, self.train_data, self._conf, self.padecimiento)
            best_params, _ = tuner.run()
            if best_params:
                self._xgb_hp.update(best_params)
                self._xgb_hp["n_estimators"] = int(self._conf.get("xgb_n_estimators_max", 500))
            self._fit_xgboost(self.train_data)
        if self._ensemble_mode == "parallel" and self._parallel_engine is not None:
            self.pred_train, self.pred_test = self._parallel_engine.gen_insample_preds(
                self._prophet, self.train_data, self.test_data
            )
        else:
            self.pred_train, self.pred_test = generar_predicciones_insample(
                self._prophet, self._xgb, self.train_data, self.test_data
            )
        metrics = calcular_metricas_ensemble(
            self.test_data,
            self.pred_test,
            self.train_data,
            "Ensemble (Prophet + XGBoost)",
            self.tiempo_total,
        )

        # Metricas in-sample (train) para deteccion de overfitting/leakage
        if not self.pred_train.empty and "yhat_ensemble" in self.pred_train.columns:
            y_tr = self.train_data["y"].to_numpy(dtype=float)
            yhat_tr = self.pred_train["yhat_ensemble"].to_numpy(dtype=float)
            train_m = compute_forecast_metrics(y_tr, yhat_tr, y_tr)
            metrics["rmse_train"] = train_m.get("rmse")
            metrics["smape_train"] = train_m.get("smape")

        return self._prophet, metrics, self.get_params()

    @property
    def prophet_model(self) -> Prophet:
        if self._prophet is None:
            raise RuntimeError("Prophet no entrenado.")
        return self._prophet

    @property
    def xgb_model(self) -> XGBRegressor:
        if self._xgb is None:
            raise RuntimeError("XGBoost no entrenado.")
        return self._xgb

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    @property
    def tiempo_prophet(self) -> float:
        return self._t_prophet

    @property
    def tiempo_total(self) -> float:
        return self._t_prophet + self._t_ensemble

    def get_prophet_metrics(self) -> dict[str, Any]:
        return calcular_metricas_prophet_base(
            self.test_data, self.pred_test, self.train_data, self._t_prophet
        )

    @property
    def _xgb_direct(self) -> Any:
        return self._parallel_engine.xgb_direct if self._parallel_engine else None

    @_xgb_direct.setter
    def _xgb_direct(self, value: Any) -> None:
        if self._parallel_engine is not None:
            self._parallel_engine._xgb_direct = value

    @property
    def _ensemble_weights(self) -> npt.NDArray[np.floating[Any]] | None:
        return self._parallel_engine.weights if self._parallel_engine else None

    @_ensemble_weights.setter
    def _ensemble_weights(self, value: npt.NDArray[np.floating[Any]] | None) -> None:
        if self._parallel_engine is not None:
            self._parallel_engine._ensemble_weights = value
