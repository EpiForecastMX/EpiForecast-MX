# src/epiforecast/models/deepar/model.py
"""DeepAR forecasting model implementation (GluonTS + PyTorch).

Real implementation using GluonTS DeepAREstimator with PyTorch backend.
Uses CUDA automatically if available, falls back to CPU otherwise.
All GluonTS/torch imports are lazy (inside methods) to avoid import-time
side effects and allow the module to load even without GluonTS installed.
"""

from __future__ import annotations

import logging
from pathlib import Path
import pickle
import tempfile
from typing import Any
import warnings

import numpy as np
import pandas as pd

# Suppress verbose Lightning GPU/TPU/HPU info lines.
# Lightning re-initializes its loggers on Trainer creation, so setLevel alone is
# not enough — we also cut propagation so messages never reach the root handler.
for _ln in ("lightning", "lightning.pytorch"):
    _lg = logging.getLogger(_ln)
    _lg.setLevel(logging.ERROR)
    _lg.propagate = False

warnings.filterwarnings(
    "ignore",
    message="Using a non-tuple sequence for multidimensional indexing",
    category=UserWarning,
    module="gluonts",
)
warnings.filterwarnings(
    "ignore",
    message="You defined a `validation_step` but have no `val_dataloader`",
    category=UserWarning,
    module="lightning",
)
warnings.filterwarnings("ignore", message=".*Tensor Cores.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*float32_matmul_precision.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*LeafSpec.*")
warnings.filterwarnings("ignore", message=".*Checkpoint directory.*exists and is not empty.*")

from epiforecast.constants import RANDOM_SEED  # noqa: E402
from epiforecast.models.base import ForecastModel  # noqa: E402
from epiforecast.models.factory import register_model  # noqa: E402
from epiforecast.utils.config import conf, logger  # noqa: E402


def _resolve_distr_output(name: str) -> Any:
    """Map a distribution name string to a GluonTS DistributionOutput instance."""
    from gluonts.torch.distributions import (
        NegativeBinomialOutput,
        NormalOutput,
        StudentTOutput,
    )

    distributions: dict[str, Any] = {
        "negative-binomial": NegativeBinomialOutput,
        "normal": NormalOutput,
        "student-t": StudentTOutput,
    }
    cls = distributions.get(name)
    if cls is None:
        raise ValueError(f"Distribución desconocida: '{name}'. Opciones: {list(distributions)}")
    return cls()


def _make_progress_callback(total_epochs: int, description: str = "DeepAR") -> Any:
    """Factory: Lightning Callback that renders a Rich progress bar per training run."""
    from lightning.pytorch.callbacks import Callback
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
    )

    class _RichEpochProgress(Callback):
        def __init__(self) -> None:
            self._progress: Progress | None = None
            self._task: Any = None

        def on_train_start(self, trainer: Any, pl_module: Any) -> None:
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}[/bold blue]"),
                BarColumn(bar_width=32),
                MofNCompleteColumn(),
                TextColumn("epochs  loss [green]{task.fields[loss]}[/green]"),
                TimeRemainingColumn(),
                transient=True,
            )
            self._progress.start()
            self._task = self._progress.add_task(description, total=total_epochs, loss="—")

        def on_train_epoch_end(self, trainer: Any, pl_module: Any) -> None:
            if self._progress is not None and self._task is not None:
                loss = trainer.callback_metrics.get("train_loss")
                loss_str = f"{loss:.4f}" if loss is not None else "—"
                self._progress.update(self._task, advance=1, loss=loss_str)

        def on_train_end(self, trainer: Any, pl_module: Any) -> None:
            if self._progress is not None:
                self._progress.stop()
                self._progress = None

    return _RichEpochProgress()


@register_model("deepar")
class DeepARForecaster(ForecastModel):
    """DeepAR-based time series forecaster using GluonTS + PyTorch (CUDA/CPU)."""

    def __init__(
        self,
        df: pd.DataFrame | None = None,
        sexo: str | None = None,
        entidad: str | None = None,
        padecimiento: str | None = None,
        config: dict | None = None,
    ):
        self._conf = config if config is not None else conf
        self.df = df.copy() if df is not None else pd.DataFrame()
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        # DeepAR hyperparameters (from config/models/deepar.yaml → deepar: key)
        self.deepar_conf: dict = self._conf.get("deepar", {})
        self.epochs: int = self.deepar_conf.get("epochs", 300)
        self.context_length: int = self.deepar_conf.get("context_length", 104)
        self.prediction_length: int = self.deepar_conf.get("prediction_length", 52)
        self.num_layers: int = self.deepar_conf.get("num_layers", 2)
        self.num_cells: int = self.deepar_conf.get("num_cells", 80)
        self.dropout_rate: float = self.deepar_conf.get("dropout_rate", 0.15)
        self.learning_rate: float = self.deepar_conf.get("learning_rate", 5e-4)
        self.weight_decay: float = self.deepar_conf.get("weight_decay", 1e-6)
        self.batch_size: int = self.deepar_conf.get("batch_size", 32)
        self.scaling: bool = self.deepar_conf.get("scaling", True)
        self.distr_output: str = self.deepar_conf.get("distr_output", "student-t")
        self.num_samples: int = self.deepar_conf.get("num_samples", 200)
        self.freq: str = self.deepar_conf.get("freq", "W-MON")
        self.nonnegative_pred_samples: bool = self.deepar_conf.get(
            "nonnegative_pred_samples", True
        )
        self.num_batches_per_epoch: int = self.deepar_conf.get("num_batches_per_epoch", 50)
        self.early_stopping_patience: int = self.deepar_conf.get("early_stopping_patience", 15)
        self.multi_series: bool = self.deepar_conf.get("multi_series", True)

        # Train/test config
        self.FECHA_CORTE_ENTRENAMIENTO: str = self._conf.get(
            "FECHA_CORTE_ENTRENAMIENTO", "2025-01-01"
        )

        # GluonTS predictor (set after training)
        self._predictor: Any = None

        # Data placeholders
        self.serie: pd.DataFrame = pd.DataFrame()
        self.train_data: pd.DataFrame = pd.DataFrame()
        # Multi-series data (long format: [ds, y, item_id])
        self.serie_multi: pd.DataFrame = pd.DataFrame()
        self.train_data_multi: pd.DataFrame = pd.DataFrame()

        if not self.df.empty and "Fecha" in self.df.columns:
            self.df["Fecha"] = pd.to_datetime(self.df["Fecha"])

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def _is_multi_series(self) -> bool:
        """True cuando aplica multi-series (nivel nacional + flag activo)."""
        return self.multi_series and self.entidad is None

    # ── Data Preparation ──────────────────────────────────────────────────────

    def agrupa(self) -> None:
        """Aggregate data by date, optionally keeping per-state series.

        When _is_multi_series (national + flag), each state becomes a separate
        item_id for GluonTS multi-series training.  Also builds the aggregated
        national ``self.serie`` for compatibility (promedio_semanal, sidecar CSV).
        """
        col: str = self.sexo or "general"

        if self._is_multi_series and "Entidad" in self.df.columns:
            # Multi-series: one series per state
            self.serie_multi = (
                self.df.groupby(["Fecha", "Entidad"])[col]
                .sum()
                .reset_index()
                .rename(columns={"Fecha": "ds", col: "y", "Entidad": "item_id"})
                .sort_values(["item_id", "ds"])
                .reset_index(drop=True)
            )
            # Aggregated national series (backward compat)
            self.serie = (
                self.serie_multi.groupby("ds")["y"]
                .sum()
                .reset_index()
                .sort_values("ds")
                .reset_index(drop=True)
            )
            n_states = self.serie_multi["item_id"].nunique()
            logger.info(
                "Multi-series: {} estados, {} fechas, {} puntos totales",
                n_states,
                self.serie_multi["ds"].nunique(),
                len(self.serie_multi),
            )
        else:
            # Single-series: original behavior
            self.serie = self.df.groupby("Fecha")[col].sum().reset_index()
            self.serie = self.serie.rename(columns={"Fecha": "ds", col: "y"})
            self.serie = self.serie.sort_values("ds").reset_index(drop=True)

    def crea_train_test(self) -> None:
        """Split data by FECHA_CORTE_ENTRENAMIENTO."""
        self.serie["ds"] = pd.to_datetime(self.serie["ds"])
        self.train_data = self.serie[
            self.serie["ds"] < self.FECHA_CORTE_ENTRENAMIENTO
        ].reset_index(drop=True)

        if self._is_multi_series and not self.serie_multi.empty:
            self.serie_multi["ds"] = pd.to_datetime(self.serie_multi["ds"])
            self.train_data_multi = self.serie_multi[
                self.serie_multi["ds"] < self.FECHA_CORTE_ENTRENAMIENTO
            ].reset_index(drop=True)

    def promedio_semanal(self) -> float:
        """Return weekly average of counts."""
        return float(self.train_data["y"].mean()) if not self.train_data.empty else 0.0

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _build_dataset(self, df: pd.DataFrame) -> Any:
        """Convert a [ds, y] DataFrame to a GluonTS PandasDataset.

        Resamples to fill any gaps (missing weeks → 0) so the DatetimeIndex
        has a consistent frequency that GluonTS requires.
        """
        from gluonts.dataset.pandas import PandasDataset

        ts = df.set_index("ds")["y"].copy()
        ts.index = pd.DatetimeIndex(ts.index)
        # Fill gaps (missing weeks) with 0 and enforce freq
        ts = ts.resample(self.freq).sum()
        ts = ts.fillna(0)
        return PandasDataset.from_long_dataframe(
            pd.DataFrame({"target": ts, "item_id": 0}),
            target="target",
            item_id="item_id",
        )

    def _build_multi_dataset(self, df: pd.DataFrame) -> Any:
        """Convert a [ds, y, item_id] long DataFrame to a GluonTS PandasDataset.

        Each unique item_id becomes a separate time series.  Missing weeks are
        filled with 0 and frequency is enforced per series.
        """
        from gluonts.dataset.pandas import PandasDataset

        frames: list[pd.DataFrame] = []
        for item_id, group in df.groupby("item_id"):
            ts = group.set_index("ds")["y"].copy()
            ts.index = pd.DatetimeIndex(ts.index)
            ts = ts.resample(self.freq).sum().fillna(0)
            frames.append(pd.DataFrame({"target": ts, "item_id": item_id}))

        long_df = pd.concat(frames)
        return PandasDataset.from_long_dataframe(
            long_df,
            target="target",
            item_id="item_id",
        )

    @staticmethod
    def _silence_lightning() -> None:
        """Set all lightning.* loggers to ERROR after Lightning has been imported."""
        for name, obj in logging.root.manager.loggerDict.items():
            if name.startswith("lightning") and isinstance(obj, logging.Logger):
                obj.setLevel(logging.ERROR)
                obj.propagate = False

    def _create_estimator(self, **overrides: Any) -> Any:
        """Create a GluonTS DeepAREstimator with configured hyperparameters."""
        import torch  # noqa: I001
        from gluonts.torch.model.deepar import DeepAREstimator

        epochs = overrides.pop("epochs", self.epochs)
        context_length = overrides.pop("context_length", self.context_length)
        prediction_length = overrides.pop("prediction_length", self.prediction_length)
        use_early_stopping = overrides.pop("early_stopping", True)

        # Callbacks: early stopping (skip for CV folds with few epochs)
        callbacks: list[Any] = []
        if use_early_stopping and self.early_stopping_patience > 0:
            from lightning.pytorch.callbacks import EarlyStopping

            callbacks.append(
                EarlyStopping(
                    monitor="train_loss",
                    patience=self.early_stopping_patience,
                    mode="min",
                )
            )

        # CUDA auto-detection (Windows GPU) or CPU fallback (macOS)
        accelerator = "cuda" if torch.cuda.is_available() else "cpu"
        if accelerator == "cuda":
            torch.set_float32_matmul_precision("high")
        logger.debug("DeepAR accelerator: {}", accelerator)

        # Silence Lightning sub-loggers created during import
        self._silence_lightning()

        # Rich progress bar per training run
        label = self.padecimiento or "DeepAR"
        callbacks.append(_make_progress_callback(epochs, description=label))

        return DeepAREstimator(
            freq=self.freq,
            prediction_length=prediction_length,
            context_length=context_length,
            num_layers=overrides.pop("num_layers", self.num_layers),
            hidden_size=overrides.pop("num_cells", self.num_cells),
            dropout_rate=overrides.pop("dropout_rate", self.dropout_rate),
            lr=overrides.pop("learning_rate", self.learning_rate),
            weight_decay=overrides.pop("weight_decay", self.weight_decay),
            batch_size=self.batch_size,
            scaling=overrides.pop("scaling", self.scaling),
            distr_output=_resolve_distr_output(overrides.pop("distr_output", self.distr_output)),
            nonnegative_pred_samples=overrides.pop(
                "nonnegative_pred_samples", self.nonnegative_pred_samples
            ),
            num_batches_per_epoch=overrides.pop(
                "num_batches_per_epoch", self.num_batches_per_epoch
            ),
            trainer_kwargs={
                "max_epochs": epochs,
                "accelerator": accelerator,
                "enable_progress_bar": False,
                "logger": False,
                "callbacks": callbacks,
                "default_root_dir": tempfile.mkdtemp(),
            },
        )

    # ── ForecastModel Interface ───────────────────────────────────────────────

    def fit(self, train_data: pd.DataFrame) -> None:
        """Train DeepAR model on provided data using GluonTS."""
        import torch

        logger.info(
            "DeepAR fit() | {} | Epochs: {} | Context: {} | Hidden: {} | Distr: {} | ES: {}",
            "Multi-series" if self._is_multi_series else "Single-series",
            self.epochs,
            self.context_length,
            self.num_cells,
            self.distr_output,
            self.early_stopping_patience,
        )

        # Fix seeds for reproducibility
        torch.manual_seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

        if self._is_multi_series and not self.serie_multi.empty:
            dataset = self._build_multi_dataset(self.serie_multi)
        else:
            dataset = self._build_dataset(train_data)

        estimator = self._create_estimator()
        self._predictor = estimator.train(dataset)

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Generate predictions using the trained DeepAR predictor."""
        if self._predictor is None:
            raise RuntimeError("Modelo no entrenado. Llama a fit() primero.")

        if self._is_multi_series and not self.serie_multi.empty:
            return self._predict_multi(horizon)
        return self._predict_single(horizon)

    def _predict_single(self, horizon: int) -> pd.DataFrame:
        """Single-series prediction (original behavior)."""
        context_data = self.serie if not self.serie.empty else self.train_data
        if context_data.empty:
            raise RuntimeError("No hay datos de contexto para generar predicciones.")

        dataset = self._build_dataset(context_data)
        forecasts = list(self._predictor.predict(dataset, num_samples=self.num_samples))
        fc = forecasts[0]

        yhat = fc.mean
        yhat_lower = fc.quantile(0.05)
        yhat_upper = fc.quantile(0.95)

        last_date = context_data["ds"].max()
        dates_future = pd.date_range(
            start=last_date + pd.Timedelta(weeks=1),
            periods=len(yhat),
            freq=self.freq,
        )

        df_future = pd.DataFrame(
            {
                "ds": dates_future,
                "yhat": yhat,
                "yhat_lower": yhat_lower,
                "yhat_upper": yhat_upper,
            }
        )

        if not self.serie.empty:
            df_history = self.serie[["ds", "y"]].copy()
            df_history = df_history.rename(columns={"y": "yhat"})
            df_history["yhat_lower"] = df_history["yhat"]
            df_history["yhat_upper"] = df_history["yhat"]
            return pd.concat([df_history, df_future], ignore_index=True)

        return df_future

    def _predict_multi(self, horizon: int) -> pd.DataFrame:
        """Multi-series prediction: forecast 32 states, sum to national.

        Sums Monte Carlo samples across states before computing quantiles,
        preserving cross-series correlation in the uncertainty estimate.
        """
        context_data = self.serie_multi
        dataset = self._build_multi_dataset(context_data)
        forecasts = list(self._predictor.predict(dataset, num_samples=self.num_samples))

        if not forecasts:
            raise RuntimeError("DeepAR no genero pronosticos para ninguna serie.")

        # Stack all state samples and sum per sample to preserve correlation
        # Shape: (n_states, num_samples, prediction_length) -> sum -> (num_samples, H)
        all_samples = np.stack([fc.samples for fc in forecasts], axis=0)
        national_samples = all_samples.sum(axis=0)

        yhat = national_samples.mean(axis=0)
        yhat_lower = np.quantile(national_samples, 0.05, axis=0)
        yhat_upper = np.quantile(national_samples, 0.95, axis=0)

        last_date = self.serie["ds"].max()
        dates_future = pd.date_range(
            start=last_date + pd.Timedelta(weeks=1),
            periods=len(yhat),
            freq=self.freq,
        )

        df_future = pd.DataFrame(
            {
                "ds": dates_future,
                "yhat": yhat,
                "yhat_lower": yhat_lower,
                "yhat_upper": yhat_upper,
            }
        )

        # Prepend historical data (aggregated national)
        if not self.serie.empty:
            df_history = self.serie[["ds", "y"]].copy()
            df_history = df_history.rename(columns={"y": "yhat"})
            df_history["yhat_lower"] = df_history["yhat"]
            df_history["yhat_upper"] = df_history["yhat"]
            return pd.concat([df_history, df_future], ignore_index=True)

        return df_future

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Run cross-validation. Delegates to DeepARCrossValidator."""
        from epiforecast.models.deepar.cross_validator import DeepARCrossValidator

        cv = DeepARCrossValidator(self, config=self._conf)
        return cv.run()

    def save(self, path: Path) -> None:
        """Serialize predictor to disk as pickle + sidecar CSVs."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "predictor": self._predictor,
            "config": self.get_params(),
            "freq": self.freq,
            "prediction_length": self.prediction_length,
            "multi_series": self._is_multi_series,
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)

        # Save multi-series sidecar (needed for predict at load time)
        if self._is_multi_series and not self.serie_multi.empty:
            csv_multi = path.with_name(path.stem + "_multi.csv")
            self.serie_multi.to_csv(csv_multi, index=False, encoding="utf-8")
            logger.debug("Serie multi-series guardada: {}", csv_multi.name)

        logger.debug("Modelo DeepAR guardado: {}", path)

    def load(self, path: Path) -> None:
        """Load predictor from pickle and sidecar CSVs for historical series."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")

        with path.open("rb") as f:
            payload = pickle.load(f)

        # Backward-compatible: old stub format was {"config": {...}}
        if isinstance(payload, dict) and "predictor" in payload:
            self._predictor = payload["predictor"]
            # Restore multi_series flag from saved model
            if payload.get("multi_series", False):
                self.multi_series = True
                self.entidad = None  # Ensure _is_multi_series returns True
        elif isinstance(payload, dict):
            logger.warning("Formato de pickle antiguo (stub). _predictor = None")
            self._predictor = None
        else:
            self._predictor = payload

        # Load sidecar CSV for historical context (needed for predict)
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            self.serie = pd.read_csv(csv_path)
            self.serie["ds"] = pd.to_datetime(self.serie["ds"])

        # Load multi-series sidecar if available
        csv_multi = path.with_name(path.stem + "_multi.csv")
        if csv_multi.exists():
            self.serie_multi = pd.read_csv(csv_multi)
            self.serie_multi["ds"] = pd.to_datetime(self.serie_multi["ds"])

    def get_params(self) -> dict[str, Any]:
        """Return current model hyperparameters as flat dict."""
        return {
            "epochs": self.epochs,
            "context_length": self.context_length,
            "prediction_length": self.prediction_length,
            "num_layers": self.num_layers,
            "num_cells": self.num_cells,
            "dropout_rate": self.dropout_rate,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "batch_size": self.batch_size,
            "scaling": self.scaling,
            "distr_output": self.distr_output,
            "nonnegative_pred_samples": self.nonnegative_pred_samples,
            "multi_series": self._is_multi_series,
        }

    # ── Orchestration ─────────────────────────────────────────────────────────

    def run(self) -> tuple[Any, dict, dict]:
        """Full pipeline: prepare data, cross-validate (optional), train final model.

        Returns:
            (predictor, metrics_dict, params_dict)
        """
        logger.info("DeepAR run() | {}-{}", self.entidad or "Nacional", self.padecimiento)

        if self.df.empty or not self.sexo or self.sexo not in self.df.columns:
            logger.warning("Sin datos para entrenar DeepAR")
            metrics: dict[str, Any] = {
                "rmse": None,
                "mae": None,
                "mape": None,
                "smape": None,
                "mase": None,
                "confianza": "insuficiente",
                "promedio_semanal": 0,
            }
            return None, metrics, self.get_params()

        self.agrupa()
        self.crea_train_test()

        promedio = self.promedio_semanal()
        umbral = self._conf.get("umbral_minimo_semanal", 0)
        es_insuficiente = umbral and promedio < umbral

        if es_insuficiente:
            confianza = "insuficiente"
            best_metrics: dict[str, Any] = {
                "rmse": None,
                "mae": None,
                "mape": None,
                "smape": None,
                "mase": None,
            }
            logger.debug(
                "Baja confianza: skip CV | {:.2f} casos/sem | {} | {} | {}",
                promedio,
                self.padecimiento,
                self.entidad or "Nacional",
                self.sexo,
            )
        else:
            confianza = "normal"
            best_metrics = self.cross_validate(self.train_data)

        # Train on full series
        self.fit(self.serie)

        best_metrics["confianza"] = confianza
        best_metrics["promedio_semanal"] = promedio

        return self._predictor, best_metrics, self.get_params()
