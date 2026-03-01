"""Ensemble forecasting model: Prophet base + XGBoost residual correction."""

from __future__ import annotations

import logging
from pathlib import Path
import pickle
import time
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from epiforecast.constants import RANDOM_SEED
from epiforecast.evaluation.metrics import compute_forecast_metrics

if TYPE_CHECKING:
    from prophet import Prophet
    from xgboost import XGBRegressor
from epiforecast.models.base import ForecastModel
from epiforecast.models.ensemble.helpers import (
    FEATURE_NAMES,
    _predecir_test_recursivo,
    calcular_metricas_ensemble,
    calcular_metricas_prophet_base,
    construir_features_xgb,
    construir_holidays,
    generar_prediccion_completa,
    generar_predicciones_insample,
    preparar_datos_ensemble,
)
from epiforecast.models.ensemble.oof_residuals import generate_oof_residuals
from epiforecast.models.ensemble.weight_optimizer import EnsembleWeightOptimizer
from epiforecast.models.ensemble.xgb_direct import XGBDirectForecaster
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
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        # Config ensemble-specific
        self.cutoff: str = self._conf.get(
            "FECHA_CORTE_ENTRENAMIENTO_ENSEMBLE",
            self._conf.get("FECHA_CORTE_ENTRENAMIENTO", "2025-01-01"),
        )
        self.horizon: int = self._conf.get("HORIZON_ENSEMBLE", 52)

        # Prophet HP
        pb = self._conf.get("prophet_base", {})
        self._prophet_hp: dict[str, Any] = {
            "changepoint_prior_scale": pb.get("changepoint_prior_scale", 0.05),
            "seasonality_prior_scale": pb.get("seasonality_prior_scale", 0.1),
            "seasonality_mode": pb.get("seasonality_mode", "additive"),
        }
        yc = pb.get("yearly_custom", {})
        self._yearly_period: float = yc.get("period", 365.25)
        self._yearly_fourier: int = yc.get("fourier_order", 10)

        # OOF residual folds (0 = legacy in-sample)
        self._oof_residual_folds: int = int(self._conf.get("oof_residual_folds", 0))

        # XGBoost HP
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

        # Ensemble mode: "parallel" (Prophet + XGBDirect con pesos) o "sequential" (legacy)
        self._ensemble_mode: str = str(self._conf.get("ensemble_mode", "parallel"))

        # Parallel config
        self._parallel_alpha: float = float(self._conf.get("parallel_alpha", 1.0))
        self._parallel_oof_folds: int = int(self._conf.get("parallel_oof_folds", 4))
        self._parallel_oof_cutoff: str = str(self._conf.get("parallel_oof_cutoff", "2024-01-01"))
        self._parallel_min_train_weeks: int = int(self._conf.get("parallel_min_train_weeks", 104))

        # Holidays
        self._holidays: pd.DataFrame = construir_holidays(self._conf)

        # Internal state — sequential mode
        self._prophet: Prophet | None = None  # lazy import
        self._xgb: XGBRegressor | None = None  # lazy import
        self._feature_names: list[str] = list(FEATURE_NAMES)

        # Internal state — parallel mode
        self._xgb_direct: XGBDirectForecaster | None = None
        self._ensemble_weights: np.ndarray | None = None

        # Data placeholders (set during run())
        self.serie: pd.DataFrame = pd.DataFrame()
        self.train_data: pd.DataFrame = pd.DataFrame()
        self.test_data: pd.DataFrame = pd.DataFrame()
        self.pred_train: pd.DataFrame = pd.DataFrame()
        self.pred_test: pd.DataFrame = pd.DataFrame()
        self._t_prophet: float = 0.0
        self._t_ensemble: float = 0.0

    # ── ForecastModel Interface ────────────────────────────────────────

    def fit(self, train_data: pd.DataFrame) -> None:
        """Entrena Prophet base + XGBoost (sequential o parallel segun modo)."""
        self._fit_prophet(train_data)
        if self._ensemble_mode == "parallel":
            self._fit_parallel(train_data)
        else:
            self._fit_xgboost(train_data)

    def _fit_prophet(self, train_data: pd.DataFrame) -> None:
        """Entrena el modelo Prophet base."""
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

    def _insample_residuals(self, train_data: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
        """Calcula residuos in-sample de Prophet (legacy)."""
        prophet_train = self._prophet.predict(train_data[["ds"]])  # type: ignore[union-attr]
        residuos = train_data["y"].values - prophet_train["yhat"].values
        feats = construir_features_xgb(
            train_data["y"].reset_index(drop=True),
            train_data["ds"].reset_index(drop=True),
        )
        return feats, residuos

    def _fit_xgboost(self, train_data: pd.DataFrame) -> None:
        """Entrena XGBoost sobre residuos de Prophet con early stopping."""
        from xgboost import XGBRegressor as _XGBRegressor

        if self._prophet is None:
            raise RuntimeError("Prophet debe entrenarse antes de XGBoost.")

        t1 = time.perf_counter()

        feats_train: pd.DataFrame
        residuos: np.ndarray

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

        valid_mask = feats_train.notna().all(axis=1)
        feats_valid = feats_train[valid_mask]
        residuos_valid = residuos[valid_mask.to_numpy()]

        # Early stopping: ultimo 20% como eval_set
        n_val = max(int(len(feats_valid) * 0.2), 1)
        n_train = len(feats_valid) - n_val

        self._xgb = _XGBRegressor(**self._xgb_hp, n_jobs=-1, random_state=RANDOM_SEED)
        self._xgb.fit(
            feats_valid.iloc[:n_train],
            residuos_valid[:n_train],
            eval_set=[(feats_valid.iloc[n_train:], residuos_valid[n_train:])],
            verbose=False,
        )
        self._t_ensemble = time.perf_counter() - t1
        logger.debug("  XGBoost residual entrenado en {:.1f}s", self._t_ensemble)

    def _fit_parallel(self, train_data: pd.DataFrame) -> None:
        """Entrena XGBDirect + aprende pesos [w_prophet, w_xgb] via OOF."""
        t1 = time.perf_counter()

        # XGBDirect sobre y directamente
        self._xgb_direct = XGBDirectForecaster(self._xgb_hp)
        self._xgb_direct.fit(train_data)

        # Pesos via expanding-window OOF
        optimizer = EnsembleWeightOptimizer(
            alpha=self._parallel_alpha,
            n_folds=self._parallel_oof_folds,
            min_train_weeks=self._parallel_min_train_weeks,
        )
        self._ensemble_weights = optimizer.fit_oof(
            train_data,
            prophet_builder=self._build_prophet_temp,
            xgb_builder=self._build_xgb_direct_temp,
            oof_cutoff=self._parallel_oof_cutoff,
        )
        self._t_ensemble = time.perf_counter() - t1
        logger.debug("  Parallel ensemble entrenado en {:.1f}s", self._t_ensemble)

    def _build_prophet_temp(self, train_df: pd.DataFrame) -> Any:
        """Construye un Prophet temporal para OOF (no modifica self._prophet)."""
        from prophet import Prophet as _Prophet

        np.random.seed(RANDOM_SEED)
        m = _Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,
            holidays=self._holidays if not self._holidays.empty else None,
            **self._prophet_hp,
        )
        m.add_seasonality(
            name="yearly_custom",
            period=self._yearly_period,
            fourier_order=self._yearly_fourier,
        )
        m.fit(train_df)
        return m

    def _build_xgb_direct_temp(self, train_df: pd.DataFrame) -> XGBDirectForecaster:
        """Construye un XGBDirect temporal para OOF."""
        xgb = XGBDirectForecaster(self._xgb_hp)
        xgb.fit(train_df)
        return xgb

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Genera prediccion historica (in-sample) + futura."""
        if self._ensemble_mode == "parallel":
            return self._predict_parallel(horizon)
        if self._prophet is None or self._xgb is None:
            raise RuntimeError("Modelo no entrenado. Ejecutar fit() primero.")
        serie = self.serie if not self.serie.empty else self._prophet.history[["ds", "y"]]
        return generar_prediccion_completa(self._prophet, self._xgb, serie, horizon)

    def _predict_parallel(self, horizon: int = 52) -> pd.DataFrame:
        """Prediccion paralela: w[0]*prophet + w[1]*xgb_direct."""
        if self._prophet is None or self._xgb_direct is None or self._ensemble_weights is None:
            raise RuntimeError("Modelo no entrenado. Ejecutar fit() primero.")

        serie = self.serie if not self.serie.empty else self._prophet.history[["ds", "y"]]
        w = self._ensemble_weights

        last_train = pd.Timestamp(self._prophet.history["ds"].max())
        last_real = serie["ds"].max() if not serie.empty else last_train
        weeks_beyond = max(int(np.ceil((last_real - last_train).days / 7)), 0)

        future_df = self._prophet.make_future_dataframe(
            periods=weeks_beyond + horizon, freq="W-MON"
        )
        prophet_full = self._prophet.predict(future_df)

        # In-sample
        xgb_insample = self._xgb_direct.predict_insample(serie)
        prophet_in = prophet_full[prophet_full["ds"].isin(serie["ds"].values)]
        yhat_prophet_in = prophet_in["yhat"].values[: len(serie)]
        yhat_in = np.clip(w[0] * yhat_prophet_in + w[1] * xgb_insample, 0, None)

        # Out-of-sample
        mask_futuro = prophet_full["ds"] > last_real
        future_dates = prophet_full.loc[mask_futuro, "ds"].values
        yhat_prophet_future = prophet_full.loc[mask_futuro, "yhat"].values
        xgb_future = self._xgb_direct.predict_recursive(serie, future_dates)
        yhat_future = np.clip(w[0] * yhat_prophet_future + w[1] * xgb_future, 0, None)

        all_ds = np.concatenate([serie["ds"].values, future_dates])
        all_yhat = np.concatenate([yhat_in, yhat_future])
        return pd.DataFrame(
            {
                "ds": all_ds,
                "yhat": all_yhat,
                "yhat_lower": all_yhat,
                "yhat_upper": all_yhat,
                "yhat_prophet": np.concatenate([yhat_prophet_in, yhat_prophet_future]),
                "yhat_ensemble": all_yhat,
            }
        )

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Evalua ensemble sobre ``data`` (hold-out temporal)."""
        if "y" in data.columns and not data.empty:
            test_df = data
        elif not self.test_data.empty:
            test_df = self.test_data
        else:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}

        if self._ensemble_mode == "parallel":
            return self._cv_parallel(test_df)

        if self._prophet is None or self._xgb is None:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}

        prophet_pred = self._prophet.predict(test_df[["ds"]])
        xgb_adj = _predecir_test_recursivo(
            self._xgb, prophet_pred["yhat"].values, self.train_data, test_df
        )
        y_pred = prophet_pred["yhat"].values + xgb_adj

        metrics = compute_forecast_metrics(
            test_df["y"].to_numpy(), y_pred, self.train_data["y"].to_numpy()
        )
        return {
            "rmse": metrics["rmse"] or 0.0,
            "mae": metrics["mae"] or 0.0,
            "smape": metrics["smape"] or 0.0,
            "mase": metrics["mase"] if metrics["mase"] is not None else 0.0,
        }

    def _cv_parallel(self, test_df: pd.DataFrame) -> dict[str, float]:
        """Evalua modo paralelo sobre test_df."""
        if self._prophet is None or self._xgb_direct is None or self._ensemble_weights is None:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}

        w = self._ensemble_weights
        prophet_pred = self._prophet.predict(test_df[["ds"]])["yhat"].values
        xgb_pred = self._xgb_direct.predict_insample(test_df)
        y_pred = np.clip(w[0] * prophet_pred + w[1] * xgb_pred, 0, None)

        y_train = self.train_data["y"].to_numpy() if not self.train_data.empty else np.array([0.0])
        metrics = compute_forecast_metrics(test_df["y"].to_numpy(), y_pred, y_train)
        return {
            "rmse": metrics["rmse"] or 0.0,
            "mae": metrics["mae"] or 0.0,
            "smape": metrics["smape"] or 0.0,
            "mase": metrics["mase"] if metrics["mase"] is not None else 0.0,
        }

    def save(self, path: Path) -> None:
        """Serializa modelos a pickle."""
        if self._ensemble_mode == "parallel":
            if self._prophet is None or self._xgb_direct is None:
                raise RuntimeError("No hay modelo para guardar. Ejecutar fit() primero.")
        elif self._prophet is None or self._xgb is None:
            raise RuntimeError("No hay modelo para guardar. Ejecutar fit() primero.")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "prophet": self._prophet,
            "xgb": self._xgb,
            "params": self.get_params(),
            "features": self._feature_names,
            "serie": self.serie,
            "ensemble_mode": self._ensemble_mode,
            "xgb_direct": self._xgb_direct,
            "ensemble_weights": self._ensemble_weights,
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)

        if not self.serie.empty:
            csv_path = path.with_suffix(".csv")
            self.serie.to_csv(csv_path, index=False, encoding="utf-8")
            logger.debug("Serie sidecar guardada: {}", csv_path.name)

        logger.debug("Modelo ensemble guardado: {}", path)

    def load(self, path: Path) -> None:
        """Restaura modelos desde pickle."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")
        with path.open("rb") as f:
            payload = pickle.load(f)  # noqa: S301

        self._prophet = payload["prophet"]
        self._xgb = payload.get("xgb")
        self._feature_names = payload.get("features", list(FEATURE_NAMES))

        # Parallel mode fields (backward compat: default to sequential)
        self._ensemble_mode = payload.get("ensemble_mode", "sequential")
        self._xgb_direct = payload.get("xgb_direct")
        self._ensemble_weights = payload.get("ensemble_weights")

        # Restaurar serie: sidecar CSV (fresco) > pickle (fallback)
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            self.serie = pd.read_csv(csv_path)
            self.serie["ds"] = pd.to_datetime(self.serie["ds"])
        else:
            self.serie = payload.get("serie", pd.DataFrame())
            if not self.serie.empty:
                self.serie["ds"] = pd.to_datetime(self.serie["ds"])

        logger.info("Modelo ensemble cargado: {}", path)

    def get_params(self) -> dict[str, Any]:
        """Retorna hiperparametros de ambos sub-modelos."""
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
        if self._ensemble_weights is not None:
            params["w_prophet"] = round(float(self._ensemble_weights[0]), 4)
            params["w_xgb"] = round(float(self._ensemble_weights[1]), 4)
        return params

    # ── Orchestration ──────────────────────────────────────────────────

    def run(self) -> tuple[Any, dict, dict]:
        """Pipeline completo: preparar datos -> fit (con tuning) -> evaluar."""
        self.serie, self.train_data, self.test_data = preparar_datos_ensemble(
            self.df, self.padecimiento, self.sexo, self.cutoff
        )

        # 1) Prophet base
        self._fit_prophet(self.train_data)

        if self._ensemble_mode == "parallel":
            # 2) Parallel: XGBDirect + pesos OOF (skip tuner)
            self._fit_parallel(self.train_data)
        else:
            # 2) Sequential: Tunar XGBoost sobre residuos Prophet
            from epiforecast.models.ensemble.xgb_tuner import EnsembleXGBTuner

            tuner = EnsembleXGBTuner(self._prophet, self.train_data, self._conf)
            best_params, _ = tuner.run()
            if best_params:
                self._xgb_hp.update(best_params)
                self._xgb_hp["n_estimators"] = int(self._conf.get("xgb_n_estimators_max", 500))
            # 3) XGBoost con HP optimos
            self._fit_xgboost(self.train_data)

        # Generar predicciones in-sample para graficos y metricas
        if self._ensemble_mode == "parallel":
            self.pred_train, self.pred_test = self._gen_parallel_insample()
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
        return self._prophet, metrics, self.get_params()

    def _gen_parallel_insample(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Genera pred_train y pred_test para modo paralelo."""
        w = self._ensemble_weights
        if w is None or self._prophet is None or self._xgb_direct is None:
            return pd.DataFrame(), pd.DataFrame()

        # Train
        prophet_train = self._prophet.predict(self.train_data[["ds"]])
        yhat_p = prophet_train["yhat"].values
        yhat_x = self._xgb_direct.predict_insample(self.train_data)
        ensemble_train = np.clip(w[0] * yhat_p + w[1] * yhat_x, 0, None)
        pred_train = pd.DataFrame(
            {
                "ds": self.train_data["ds"].values,
                "yhat_prophet": yhat_p,
                "yhat_ensemble": ensemble_train,
            }
        )

        # Test
        pred_test = pd.DataFrame()
        if not self.test_data.empty:
            prophet_test = self._prophet.predict(self.test_data[["ds"]])
            yhat_p_t = prophet_test["yhat"].values
            yhat_x_t = self._xgb_direct.predict_insample(self.test_data)
            ensemble_test = np.clip(w[0] * yhat_p_t + w[1] * yhat_x_t, 0, None)
            pred_test = pd.DataFrame(
                {
                    "ds": self.test_data["ds"].values,
                    "yhat_prophet": yhat_p_t,
                    "yhat_ensemble": ensemble_test,
                }
            )

        return pred_train, pred_test

    # ── Accessors ──────────────────────────────────────────────────────

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
        """Metricas del Prophet base solo (sin XGBoost) sobre test set."""
        return calcular_metricas_prophet_base(
            self.test_data, self.pred_test, self.train_data, self._t_prophet
        )
