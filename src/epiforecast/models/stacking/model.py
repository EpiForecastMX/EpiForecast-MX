"""Stacking forecasting model: Prophet + ETS + LightGBM con Ridge meta-learner."""

from __future__ import annotations

import logging
from pathlib import Path
import pickle
import time
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.models.base import ForecastModel
from epiforecast.models.ensemble.feature_builder import construir_holidays
from epiforecast.models.ensemble.helpers import preparar_datos_ensemble
from epiforecast.models.factory import register_model
from epiforecast.models.stacking.experts import ETSExpert, LGBMExpert, ProphetExpert
from epiforecast.models.stacking.meta_learner import StackingMetaLearner
from epiforecast.utils.cohorts import is_count_log_cohort
from epiforecast.utils.config import conf, logger

logging.getLogger("cmdstanpy").disabled = True


@register_model("stacking")
class StackingForecaster(ForecastModel):
    """Stacking: Prophet + ETS + LightGBM con Ridge meta-learner (ForecastModel/LSP)."""

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

        # Stacking-specific config
        stk = self._conf.get("stacking", {})
        self.cutoff: str = self._conf.get(
            "FECHA_CORTE_ENTRENAMIENTO_STACKING",
            self._conf.get("FECHA_CORTE_ENTRENAMIENTO", "2025-01-01"),
        )
        self.horizon: int = int(self._conf.get("HORIZON_STACKING", 52))
        self._oof_cutoff: str = stk.get("oof_cutoff", "2024-01-01")
        ml_cfg = stk.get("meta_learner", {})
        self._meta_alpha: float = float(ml_cfg.get("alpha", 1.0))
        self._meta_type: str = str(ml_cfg.get("type", "ridge"))
        self._l1_ratio: float = float(ml_cfg.get("l1_ratio", 0.5))
        self._add_temporal_features: bool = bool(ml_cfg.get("add_temporal_features", False))
        self._max_iter: int = int(ml_cfg.get("max_iter", 10_000))
        self._tol: float = float(ml_cfg.get("tol", 1e-4))
        self._oof_n_folds: int = int(stk.get("oof_n_folds", 4))
        self._oof_min_train_weeks: int = int(stk.get("oof_min_train_weeks", 104))

        # Build holidays (reuse ensemble helper; cohort-aware: Dengue sin COVID)
        holidays = construir_holidays(self._conf, self.padecimiento)

        # Create experts
        self._experts: list[Any] = [
            ProphetExpert(stk.get("prophet", {}), holidays),
            ETSExpert(stk.get("ets", {})),
            LGBMExpert(stk.get("lgbm", {})),
        ]

        # Meta-learner state
        self._weights: npt.NDArray[np.floating[Any]] | None = None
        self._ridge: Any = None
        self._n_train: int = 0

        # Data placeholders (set during run())
        self.serie: pd.DataFrame = pd.DataFrame()
        self.train_data: pd.DataFrame = pd.DataFrame()
        self.test_data: pd.DataFrame = pd.DataFrame()
        self._t_total: float = 0.0

    # -- ForecastModel Interface ------------------------------------------------

    def fit(self, train_data: pd.DataFrame) -> None:
        """Entrena OOF meta-learner + expertos finales."""
        t0 = time.perf_counter()

        # 1) OOF: obtener pesos
        meta = StackingMetaLearner(
            self._experts,
            self._meta_alpha,
            n_folds=self._oof_n_folds,
            min_train_weeks=self._oof_min_train_weeks,
            meta_type=self._meta_type,
            l1_ratio=self._l1_ratio,
            add_temporal_features=self._add_temporal_features,
            max_iter=self._max_iter,
            tol=self._tol,
        )
        self._weights, self._ridge = meta.fit_oof(train_data, self._oof_cutoff)

        # 2) Re-entrenar expertos en train completo
        logger.debug("  Re-entrenando expertos en train completo ({} filas)...", len(train_data))
        for expert in self._experts:
            expert.fit(train_data)

        self._n_train = len(train_data)
        self._t_total = time.perf_counter() - t0
        logger.debug("  Stacking entrenado en {:.1f}s", self._t_total)

    def _predict_combined(
        self, x_stack: npt.NDArray[np.floating[Any]], dates: pd.Series
    ) -> npt.NDArray[np.floating[Any]]:
        """Combinacion ponderada: siempre via modelo cuando esta disponible."""
        if self._ridge is not None:
            if self._add_temporal_features:
                x_input = StackingMetaLearner._augment_with_temporal(x_stack, dates)
            else:
                x_input = x_stack
            return np.asarray(np.clip(self._ridge.predict(x_input), 0, None))
        # Fallback: pesos manuales (solo si ridge es None, i.e. OOF fallo)
        assert self._weights is not None
        return np.asarray(np.clip(x_stack @ self._weights, 0, None))

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Genera prediccion historica (in-sample) + futura."""
        if self._weights is None:
            raise RuntimeError("Modelo no entrenado. Ejecutar fit() o load() primero.")
        if self.serie.empty:
            raise RuntimeError("No hay serie para generar predicciones.")

        last_date = pd.Timestamp(self.serie["ds"].max())
        future_dates = pd.date_range(
            last_date + pd.Timedelta(weeks=1), periods=horizon, freq="W-MON"
        )
        all_dates = np.concatenate([self.serie["ds"].values, future_dates.values])
        all_dates_df = pd.DataFrame({"ds": all_dates})
        n_total = len(all_dates)
        n_forward = len(self.serie) - self._n_train + horizon

        # Prophet: predict all dates at once
        pred_prophet = self._experts[0].predict(all_dates_df)

        # ETS: fitted values + forecast
        ets: ETSExpert = self._experts[1]
        ets_fitted, ets_fwd = ets.predict_full(n_forward)
        if ets_fitted is not None:
            pred_ets = np.concatenate([ets_fitted, ets_fwd])
        else:
            pred_ets = np.zeros(n_total)

        # LightGBM: continuous trend from 0
        pred_lgbm = self._experts[2].predict(all_dates_df, trend_start=0)

        x_stack = np.column_stack([pred_prophet, pred_ets, pred_lgbm])
        yhat = self._predict_combined(x_stack, pd.Series(pd.to_datetime(all_dates)))

        out = pd.DataFrame({"ds": all_dates, "yhat": yhat, "yhat_lower": yhat, "yhat_upper": yhat})
        # Guard de plausibilidad para la cohorte de conteos-log (Dengue): LightGBM diverge al
        # extrapolar; se acota a la envolvente estacional histórica (no afecta neuro).
        if is_count_log_cohort(self.padecimiento) and not self.serie.empty:
            from epiforecast.models.forecast_guards import clamp_seasonal_envelope

            out = clamp_seasonal_envelope(out, self.serie[["ds", "y"]])
        return out

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Evalua stacking sobre data (hold-out temporal)."""
        if data.empty or self._weights is None:
            return {"rmse": 0.0, "mae": 0.0, "smape": 0.0, "mase": 0.0}

        preds = [e.predict(data[["ds"]]) for e in self._experts]
        x_stack = np.column_stack(preds)
        yhat = self._predict_combined(x_stack, data["ds"])

        y_train = (
            self.train_data["y"].to_numpy(dtype=float)
            if not self.train_data.empty
            else np.array([0.0])
        )
        raw = compute_forecast_metrics(data["y"].to_numpy(dtype=float), yhat, y_train)
        return {
            "rmse": float(raw.get("rmse") or 0.0),
            "mae": float(raw.get("mae") or 0.0),
            "smape": float(raw.get("smape") or 0.0),
            "mase": float(raw["mase"] or 0.0) if raw.get("mase") is not None else 0.0,
        }

    def save(self, path: Path) -> None:
        """Serializa expertos + modelo meta-learner + pesos a pickle."""
        from epiforecast.utils.model_metadata import build_model_metadata

        if self._weights is None:
            raise RuntimeError("No hay modelo para guardar. Ejecutar fit() primero.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "experts": self._experts,
            "ridge": self._ridge,
            "weights": self._weights,
            "params": self.get_params(),
            "serie": self.serie,
            "n_train": self._n_train,
            "meta_type": self._meta_type,
            "add_temporal_features": self._add_temporal_features,
            "_metadata": build_model_metadata(),
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)

        if not self.serie.empty:
            csv_path = path.with_suffix(".csv")
            self.serie.to_csv(csv_path, index=False, encoding="utf-8")
            logger.debug("Serie sidecar guardada: {}", csv_path.name)

        logger.debug("Modelo stacking guardado: {}", path)

    def load(self, path: Path) -> None:
        """Restaura desde pickle + sidecar CSV."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")
        with path.open("rb") as f:
            payload = pickle.load(f)  # noqa: S301

        self._experts = payload["experts"]
        self._ridge = payload.get("ridge")
        self._weights = payload["weights"]
        self._n_train = payload.get("n_train", 0)
        self._meta_type = payload.get("meta_type", "ridge")
        self._add_temporal_features = payload.get("add_temporal_features", False)

        # Restaurar serie: sidecar CSV (fresco) > pickle (fallback)
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            self.serie = pd.read_csv(csv_path)
            self.serie["ds"] = pd.to_datetime(self.serie["ds"])
        else:
            self.serie = payload.get("serie", pd.DataFrame())
            if not self.serie.empty:
                self.serie["ds"] = pd.to_datetime(self.serie["ds"])

        logger.info("Modelo stacking cargado: {}", path)

    def get_params(self) -> dict[str, Any]:
        """Retorna hiperparametros y pesos del meta-learner."""
        w = self._weights
        return {
            "cutoff": self.cutoff,
            "horizon": self.horizon,
            "oof_cutoff": self._oof_cutoff,
            "meta_type": self._meta_type,
            "alpha": self._meta_alpha,
            "l1_ratio": self._l1_ratio,
            "add_temporal_features": self._add_temporal_features,
            "peso_prophet": round(float(w[0]), 4) if w is not None else None,
            "peso_ets": round(float(w[1]), 4) if w is not None else None,
            "peso_lgbm": round(float(w[2]), 4) if w is not None else None,
        }

    # -- Orchestration ----------------------------------------------------------

    def run(self) -> tuple[Any, dict[str, Any], dict[str, Any]]:
        """Pipeline completo: preparar datos -> fit -> evaluar."""
        self.serie, self.train_data, self.test_data = preparar_datos_ensemble(
            self.df, self.padecimiento, self.sexo, self.cutoff
        )

        self.fit(self.train_data)

        metrics: dict[str, Any] = {
            "modelo": "Stacking (Prophet + ETS + LightGBM)",
            "rmse": 0.0,
            "mae": 0.0,
            "mape": 0.0,
            "smape": 0.0,
            "mase": None,
            "tiempo": self._t_total,
        }

        if not self.test_data.empty:
            preds = [e.predict(self.test_data[["ds"]]) for e in self._experts]
            x_test = np.column_stack(preds)
            yhat_test = self._predict_combined(x_test, self.test_data["ds"])
            raw = compute_forecast_metrics(
                self.test_data["y"].to_numpy(dtype=float),
                yhat_test,
                self.train_data["y"].to_numpy(dtype=float),
            )
            metrics.update(raw)
            metrics["modelo"] = "Stacking (Prophet + ETS + LightGBM)"
            metrics["tiempo"] = self._t_total

        # Metricas in-sample (train) para deteccion de overfitting/leakage
        if not self.train_data.empty and self._weights is not None:
            try:
                preds_tr = [e.predict(self.train_data[["ds"]]) for e in self._experts]
                x_train = np.column_stack(preds_tr)
                yhat_train = self._predict_combined(x_train, self.train_data["ds"])
                y_tr = self.train_data["y"].to_numpy(dtype=float)
                train_m = compute_forecast_metrics(y_tr, yhat_train, y_tr)
                metrics["rmse_train"] = train_m.get("rmse")
                metrics["smape_train"] = train_m.get("smape")
            except (ValueError, KeyError) as e:
                logger.warning("No se pudieron calcular metricas train (Stacking): {}", e)

        return self, metrics, self.get_params()
