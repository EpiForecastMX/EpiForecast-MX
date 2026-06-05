# src/epiforecast/models/deepar/model.py
"""DeepAR forecasting model implementation (GluonTS + PyTorch).

Real implementation using GluonTS DeepAREstimator with PyTorch backend.
Uses CUDA automatically if available, falls back to CPU otherwise.
All GluonTS/torch imports are lazy (inside methods) to avoid import-time
side effects and allow the module to load even without GluonTS installed.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import pickle
import tempfile
from typing import Any
import warnings

# MPS (Apple Silicon) no soporta todos los ops de PyTorch (e.g. _standard_gamma
# para Student-t).  Con este flag, las ops faltantes caen a CPU automáticamente.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

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
warnings.filterwarnings("ignore", message=".*not currently supported on the MPS backend.*")

from epiforecast.constants import RANDOM_SEED  # noqa: E402
from epiforecast.models.base import ForecastModel  # noqa: E402
from epiforecast.models.factory import register_model  # noqa: E402
from epiforecast.utils.cohorts import is_neuro  # noqa: E402
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

    class _RichEpochProgress(Callback):  # type: ignore[misc]
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
        config: dict[str, Any] | None = None,
    ):
        self._conf = config if config is not None else conf
        self.df = df.copy() if df is not None else pd.DataFrame()
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        # DeepAR hyperparameters (from config/models/deepar.yaml → deepar: key)
        self.deepar_conf: dict[str, Any] = self._conf.get("deepar", {})
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
        # Flag de normalización a tasa centralizado (predict/CV usan el mismo). Dengue conserva
        # tasa+student-t: se probó NegBin en conteos enteros y empeoró (ver deepar.yaml).
        self.normalizar: bool = bool(self._conf.get("normalizar_tasa", True))

        # Cohort-aware short-series overrides (p.ej. Dengue: historia desde 2020).
        # Las series cortas no admiten la memoria/lags de la config neuro; ver deepar.yaml.
        # No se fabrica historia: solo se acorta el contexto del modelo y se aligera la CV.
        self.short_max_lag: int | None = None  # None => lags por defecto de la frecuencia
        self.gap_fill: str = (
            "zero"  # "zero" (neuro, conteos reales) | "interpolate" (huecos de boletin)
        )
        self.cv_n_splits_override: int | None = None
        self.cv_test_size_override: int | None = None
        short_cfg: dict[str, Any] = self.deepar_conf.get("short_series", {})
        if (
            short_cfg.get("enabled", False)
            and self.padecimiento
            and not is_neuro(self.padecimiento)
        ):
            self.context_length = int(short_cfg.get("context_length", self.context_length))
            self.short_max_lag = int(short_cfg.get("max_lag", 53))
            self.gap_fill = str(short_cfg.get("gap_fill", "interpolate"))
            self.cv_n_splits_override = int(short_cfg.get("cv_n_splits", 2))
            self.cv_test_size_override = int(short_cfg.get("cv_test_size", 26))
            # Cohortes no-neuro (p.ej. Dengue) entrenan a nivel nacional sobre la serie
            # AGREGADA, no multi-series por 32 estados: muchos estados tienen incidencia
            # casi-cero y su CV multi-series promedia/escala ruido, dando métricas no
            # comparables con los otros 3 motores (que corren single-series nacional).
            self.multi_series = bool(short_cfg.get("multi_series", False))

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
        normalizar = self.normalizar
        col_pob = self._conf.get("columna_poblacion", "Total")
        tasa_por = self._conf.get("tasa_por", 100000)

        if self._is_multi_series and "Entidad" in self.df.columns:
            # Multi-series: one series per state
            agg_dict = {col: "sum"}
            if normalizar and col_pob in self.df.columns:
                agg_dict[col_pob] = "sum"

            self.serie_multi = (
                self.df.groupby(["Fecha", "Entidad"])
                .agg(agg_dict)
                .reset_index()
                .rename(columns={"Fecha": "ds", "Entidad": "item_id"})
            )

            if normalizar and col_pob in self.serie_multi.columns:
                self.serie_multi["y_original"] = self.serie_multi[col]
                self.serie_multi["y"] = (
                    self.serie_multi[col] / self.serie_multi[col_pob]
                ) * tasa_por
                if col_pob != "Total":
                    self.serie_multi = self.serie_multi.rename(columns={col_pob: "Total"})
            else:
                self.serie_multi = self.serie_multi.rename(columns={col: "y"})

            self.serie_multi = self.serie_multi.sort_values(["item_id", "ds"]).reset_index(
                drop=True
            )

            # Aggregated national series (sum of originals, then re-calculate rate)
            agg_cols = (
                ["y_original", "Total"] if "y_original" in self.serie_multi.columns else ["y"]
            )
            self.serie = self.serie_multi.groupby("ds")[agg_cols].sum().reset_index()

            if "y_original" in self.serie.columns:
                self.serie["y"] = (self.serie["y_original"] / self.serie["Total"]) * tasa_por

            self.serie = self.serie.sort_values("ds").reset_index(drop=True)

            n_states = self.serie_multi["item_id"].nunique()
            logger.info(
                "Multi-series: {} estados, {} fechas, {} puntos totales (normalizado: {})",
                n_states,
                self.serie_multi["ds"].nunique(),
                len(self.serie_multi),
                normalizar,
            )
        else:
            # Single-series: original behavior
            agg_dict = {col: "sum"}
            if normalizar and col_pob in self.df.columns:
                agg_dict[col_pob] = "sum"

            self.serie = self.df.groupby("Fecha").agg(agg_dict).reset_index()
            self.serie = self.serie.rename(columns={"Fecha": "ds"})

            if normalizar and col_pob in self.serie.columns:
                self.serie["y_original"] = self.serie[col]
                self.serie["y"] = (self.serie[col] / self.serie[col_pob]) * tasa_por
                if col_pob != "Total":
                    self.serie = self.serie.rename(columns={col_pob: "Total"})
            else:
                self.serie = self.serie.rename(columns={col: "y"})

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
        """Return weekly average of counts (y_original if exists)."""
        if self.train_data.empty:
            return 0.0
        if "y_original" in self.train_data.columns:
            return float(self.train_data["y_original"].mean())
        return float(self.train_data["y"].mean())

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _resample_fill(self, ts: pd.Series) -> pd.Series:
        """Reindexa a la frecuencia ``self.freq`` y rellena semanas faltantes.

        - ``gap_fill="zero"`` (neuro): comportamiento historico, huecos → 0.
        - ``gap_fill="interpolate"`` (cohortes de historia corta, p.ej. Dengue): los
          huecos son semanas sin boletin, no semanas con cero casos, por lo que se
          interpolan linealmente. ``min_count=1`` distingue el hueco real (→ NaN) de
          una semana presente con valor 0; el NaN inicial restante se fija en 0.
        """
        ts.index = pd.DatetimeIndex(ts.index)
        if self.gap_fill == "interpolate":
            ts = ts.resample(self.freq).sum(min_count=1)
            return ts.interpolate(method="linear", limit_direction="both").fillna(0)
        return ts.resample(self.freq).sum().fillna(0)

    def _build_dataset(self, df: pd.DataFrame) -> Any:
        """Convert a [ds, y] DataFrame to a GluonTS PandasDataset.

        Resamples to fill any gaps (missing weeks) so the DatetimeIndex
        has a consistent frequency that GluonTS requires.
        """
        from gluonts.dataset.pandas import PandasDataset

        ts = self._resample_fill(df.set_index("ds")["y"].copy())
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
            ts = self._resample_fill(group.set_index("ds")["y"].copy())
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

        # Selección de acelerador: CUDA (SageMaker/GPU) > CPU. MPS (Apple Silicon) queda
        # DESHABILITADO por defecto: PyTorch no implementa varios ops de muestreo de
        # distribuciones en MPS (p.ej. ``aten::_standard_gamma`` que usa la salida StudentT),
        # lo que aborta el entrenamiento local con NotImplementedError; además dos procesos
        # DeepAR concurrentes sobre el mismo dispositivo MPS pueden bloquearse (deadlock).
        # CPU es determinista y suficiente para el entrenamiento local (producción usa CUDA
        # en SageMaker). Se puede forzar MPS con ``deepar.allow_mps: true`` (activa también el
        # fallback de ops no soportados a CPU).
        allow_mps = bool(self.deepar_conf.get("allow_mps", False))
        if torch.cuda.is_available():
            accelerator = "cuda"
            torch.set_float32_matmul_precision("high")
        elif allow_mps and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            accelerator = "mps"
        else:
            accelerator = "cpu"
        logger.debug("DeepAR accelerator: {}", accelerator)

        # Silence Lightning sub-loggers created during import
        self._silence_lightning()

        # Cohort-aware: cohortes de historia corta usan lags acotados (1 año) para que
        # past_length (context_length + max_lag) quepa en la serie disponible.
        extra: dict[str, Any] = {}
        if self.short_max_lag is not None:
            from gluonts.time_feature.lag import get_lags_for_frequency

            extra["lags_seq"] = [
                lag for lag in get_lags_for_frequency(self.freq) if lag <= self.short_max_lag
            ]

        # Rich progress bar per training run
        entity_label = self.entidad or "Nacional"
        phase = overrides.pop("phase", "")
        parts = [self.padecimiento or "DeepAR", entity_label]
        if phase:
            parts.append(phase)
        label = " | ".join(parts)
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
            **extra,
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

        estimator = self._create_estimator(phase="Final")
        self._predictor = estimator.train(dataset)

    def predict(self, horizon: int = 52) -> pd.DataFrame:
        """Generate predictions using the trained DeepAR predictor."""
        if self._predictor is None:
            raise RuntimeError("Modelo no entrenado. Llama a fit() primero.")

        if self._is_multi_series and not self.serie_multi.empty:
            return self._predict_multi(horizon)
        return self._predict_single(horizon)

    def _backtest_fitted(self, context_data: pd.DataFrame, horizon: int) -> pd.DataFrame:
        """Fitted values via expanding-window backtest (single series).

        Generates honest historical predictions by sliding a window:
        - First ``prediction_length`` points: copy ``y_original`` (no backtest)
        - Remaining points: predict in ``prediction_length``-sized chunks
        """
        pred_len = self.prediction_length
        n = len(context_data)
        target_col = "y_original" if "y_original" in context_data.columns else "y"

        # Start with real y as fallback (first pred_len points stay as-is)
        yhat_arr = context_data[target_col].to_numpy(dtype=float).copy()
        yhat_lower = yhat_arr.copy()
        yhat_upper = yhat_arr.copy()

        # Denormalization params
        normalizar = self.normalizar
        has_pop = normalizar and "Total" in self.serie.columns
        if has_pop:
            pob = float(self.serie["Total"].iloc[-1])
            tasa_por = float(self._conf.get("tasa_por", 100000))

        logger.debug("Backtest fitted: {} semanas historicas", n)

        # Expanding-window: predict from pred_len onwards in chunks
        cursor = pred_len
        while cursor < n:
            end = min(cursor + pred_len, n)
            window = context_data.iloc[:cursor]

            try:
                dataset = self._build_dataset(window)
                forecasts = list(self._predictor.predict(dataset, num_samples=self.num_samples))
                fc = forecasts[0]
                length = end - cursor
                raw_mean = fc.mean[:length]
                raw_lower = fc.quantile(0.05)[:length]
                raw_upper = fc.quantile(0.95)[:length]

                if has_pop:
                    raw_mean = (raw_mean * pob) / tasa_por
                    raw_lower = (raw_lower * pob) / tasa_por
                    raw_upper = (raw_upper * pob) / tasa_por

                yhat_arr[cursor:end] = raw_mean
                yhat_lower[cursor:end] = raw_lower
                yhat_upper[cursor:end] = raw_upper
            except (RuntimeError, ValueError, IndexError) as e:
                logger.warning(
                    "Backtest window [{}-{}] failed ({}), keeping y",
                    cursor,
                    end,
                    e,
                )

            cursor = end

        return pd.DataFrame(
            {
                "ds": context_data["ds"].values,
                "yhat": yhat_arr,
                "yhat_lower": yhat_lower,
                "yhat_upper": yhat_upper,
            }
        )

    def _backtest_fitted_multi(self, horizon: int) -> pd.DataFrame:
        """Fitted values for multi-series: backtest last prediction_length weeks.

        Full expanding-window backtest for 32 states is too expensive.
        Instead, copy real ``y`` for most of the history and run a single
        backtest pass for the last ``prediction_length`` weeks.
        """
        pred_len = self.prediction_length
        target_col = "y_original" if "y_original" in self.serie.columns else "y"
        n = len(self.serie)

        yhat_arr = self.serie[target_col].to_numpy(dtype=float).copy()
        yhat_lower = yhat_arr.copy()
        yhat_upper = yhat_arr.copy()

        if n > pred_len:
            cutoff_date = self.serie["ds"].iloc[n - pred_len]
            context_multi = self.serie_multi[self.serie_multi["ds"] < cutoff_date]

            if not context_multi.empty:
                try:
                    dataset = self._build_multi_dataset(context_multi)
                    forecasts = list(
                        self._predictor.predict(dataset, num_samples=self.num_samples)
                    )
                    all_samples = np.stack([fc.samples for fc in forecasts], axis=0)

                    normalizar = self.normalizar
                    if normalizar and "Total" in self.serie_multi.columns:
                        tasa_por = float(self._conf.get("tasa_por", 100000))
                        mapa_pob = self.serie_multi.groupby("item_id")["Total"].last().to_dict()
                        items = [fc.item_id for fc in forecasts]
                        for i, item_id in enumerate(items):
                            pob = mapa_pob.get(item_id, 0)
                            if pob > 0:
                                all_samples[i] = (all_samples[i] * pob) / tasa_por

                    national_samples = all_samples.sum(axis=0)
                    raw_mean = national_samples.mean(axis=0)
                    raw_lower = np.quantile(national_samples, 0.05, axis=0)
                    raw_upper = np.quantile(national_samples, 0.95, axis=0)

                    length = min(len(raw_mean), pred_len)
                    yhat_arr[n - length :] = raw_mean[:length]
                    yhat_lower[n - length :] = raw_lower[:length]
                    yhat_upper[n - length :] = raw_upper[:length]
                except (RuntimeError, ValueError, IndexError) as e:
                    logger.warning("Multi-series backtest failed ({}), keeping y", e)

        return pd.DataFrame(
            {
                "ds": self.serie["ds"].values,
                "yhat": yhat_arr,
                "yhat_lower": yhat_lower,
                "yhat_upper": yhat_upper,
            }
        )

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

        # Desnormalizar si aplica (tasa -> conteo)
        normalizar = self.normalizar
        if normalizar and "Total" in self.serie.columns:
            pob = self.serie["Total"].iloc[-1]
            tasa_por = self._conf.get("tasa_por", 100000)
            yhat = (yhat * pob) / tasa_por
            yhat_lower = (yhat_lower * pob) / tasa_por
            yhat_upper = (yhat_upper * pob) / tasa_por

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
            df_history = self._backtest_fitted(context_data, horizon)
            return pd.concat([df_history, df_future], ignore_index=True)

        return df_future

    def _predict_multi(self, horizon: int) -> pd.DataFrame:
        """Multi-series prediction: forecast 32 states, sum to national."""
        context_data = self.serie_multi
        dataset = self._build_multi_dataset(context_data)
        forecasts = list(self._predictor.predict(dataset, num_samples=self.num_samples))

        if not forecasts:
            raise RuntimeError("DeepAR no genero pronosticos para ninguna serie.")

        all_samples = np.stack([fc.samples for fc in forecasts], axis=0)

        # Desnormalizar cada estado ANTES de sumar para el nacional real
        normalizar = self.normalizar
        if normalizar and "Total" in self.serie_multi.columns:
            tasa_por = self._conf.get("tasa_por", 100000)
            # Mapa de poblacion por item_id (estado)
            mapa_pob = self.serie_multi.groupby("item_id")["Total"].last().to_dict()
            items = [fc.item_id for fc in forecasts]

            for i, item_id in enumerate(items):
                pob = mapa_pob.get(item_id, 0)
                if pob > 0:
                    all_samples[i] = (all_samples[i] * pob) / tasa_por

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

        if not self.serie.empty:
            df_history = self._backtest_fitted_multi(horizon)
            return pd.concat([df_history, df_future], ignore_index=True)

        return df_future

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        """Run cross-validation. Delegates to DeepARCrossValidator."""
        from epiforecast.models.deepar.cross_validator import DeepARCrossValidator

        cv = DeepARCrossValidator(self, config=self._conf)
        return cv.run()

    def save(self, path: Path) -> None:
        """Serialize predictor to disk as pickle + sidecar CSVs."""
        import torch

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "predictor": self._predictor,
            "config": self.get_params(),
            "freq": self.freq,
            "prediction_length": self.prediction_length,
            "multi_series": self._is_multi_series,
        }
        torch.save(payload, path)

        # Save multi-series sidecar (needed for predict at load time)
        if self._is_multi_series and not self.serie_multi.empty:
            csv_multi = path.with_name(path.stem + "_multi.csv")
            self.serie_multi.to_csv(csv_multi, index=False, encoding="utf-8")
            logger.debug("Serie multi-series guardada: {}", csv_multi.name)

        logger.debug("Modelo DeepAR guardado: {}", path)

    @staticmethod
    def _load_pickle_cpu(path: Path) -> Any:
        """Load a pickle file, remapping any CUDA tensors to CPU.

        Intenta primero torch.load (maneja persistent IDs de PyTorch
        correctamente en todos los entornos, incluyendo CUDA).
        Si falla (e.g. macOS sin CUDA intentando leer un .pkl CUDA),
        usa un unpickler custom que redirige torch.cuda.* a CPU.
        """
        import io

        import torch

        # Intento 1: torch.load nativo (funciona en CUDA y CPU)
        try:
            return torch.load(path, map_location="cpu", weights_only=False)
        except (RuntimeError, pickle.UnpicklingError):
            pass

        # Intento 2: unpickler custom para macOS sin CUDA
        class _CpuUnpickler(pickle.Unpickler):
            def find_class(self, module: str, name: str) -> Any:
                # Intercept _load_from_bytes -> nested CPU-safe load
                if module == "torch.storage" and name == "_load_from_bytes":
                    return _CpuUnpickler._load_bytes_cpu
                # Redirect torch.cuda.* -> torch.* (CPU storage)
                if "cuda" in module:
                    module = module.replace(".cuda", "").replace("cuda.", "")
                return super().find_class(module, name)

            @staticmethod
            def _load_bytes_cpu(b: bytes) -> Any:
                try:
                    return torch.load(io.BytesIO(b), map_location="cpu", weights_only=False)
                except RuntimeError:
                    return _CpuUnpickler(io.BytesIO(b)).load()

        with path.open("rb") as f:
            return _CpuUnpickler(f).load()

    def load(self, path: Path) -> None:
        """Load predictor from pickle and sidecar CSVs for historical series."""
        import torch

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")

        # Siempre cargar a CPU via _load_pickle_cpu.  Soporta archivos guardados
        # con pickle.dump (version anterior) y torch.save (version actual).
        # Evita device mismatch de GluonTS en predict (bug: no mueve todos los
        # tensores de entrada al device CUDA).
        payload = self._load_pickle_cpu(path)

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

        # Predict siempre en CPU/MPS (entrenamiento usa CUDA via _create_estimator).
        # GluonTS tiene un bug donde no mueve todos los inputs al device CUDA,
        # pero inferencia en CPU es rapida (< 1s por modelo).
        if self._predictor is not None and hasattr(self._predictor, "device"):
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                target = torch.device("mps")
            else:
                target = torch.device("cpu")
            self._predictor.device = target
            if hasattr(self._predictor, "prediction_net"):
                self._predictor.prediction_net.to(target)

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

    # ── Quick evaluation ────────────────────────────────────────────────────

    def _eval_rapida(self) -> dict[str, Any]:
        """Evaluacion honesta por hold-out (un solo split).

        Entrena un modelo SOLO con ``train_data`` (pre-cutoff, epochs reducidas) y lo evalua
        contra el tramo post-cutoff que NO vio. Antes se reusaba ``self._predictor`` (entrenado
        sobre la serie completa, incluido el test), lo que daba metricas optimistas in-sample;
        al compararlas con la CV honesta de Prophet/Ensemble/Stacking, ``reselect_motor_2026``
        favorecia injustamente a DeepAR. Esta version produce una metrica out-of-sample
        comparable. Es mas barata que la CV multi-fold (que ``skip_cv_estatal`` omite).
        """
        cutoff = pd.Timestamp(self.FECHA_CORTE_ENTRENAMIENTO)
        test_data = self.serie[self.serie["ds"] >= cutoff]
        null_metrics: dict[str, Any] = {
            "rmse": None,
            "mae": None,
            "mape": None,
            "smape": None,
            "mase": None,
        }

        if test_data.empty or len(test_data) < 4:
            logger.debug("eval_rapida: test_data insuficiente ({} filas), skip", len(test_data))
            return null_metrics

        # Contexto = datos pre-cutoff (train_data); se entrena un modelo hold-out con ellos.
        context = self.train_data
        if context.empty:
            return null_metrics

        try:
            import numpy as np
            import torch

            torch.manual_seed(RANDOM_SEED)
            np.random.seed(RANDOM_SEED)
            eval_min = int(self.deepar_conf.get("eval_epochs_min", 25))
            eval_div = int(self.deepar_conf.get("eval_epochs_divisor", 4))
            eval_epochs = max(eval_min, self.epochs // eval_div)
            estimator = self._create_estimator(
                epochs=eval_epochs,
                prediction_length=len(test_data),
                early_stopping=False,
                phase="hold-out",
            )
            dataset = self._build_dataset(context)
            predictor = estimator.train(dataset)
            forecasts = list(predictor.predict(dataset, num_samples=self.num_samples))
            fc = forecasts[0]
            yhat_raw = fc.mean[: len(test_data)]

            # Metricas en espacio de conteos reales (desnormalizar tasa)
            normalizar = self.normalizar
            if normalizar and "y_original" in test_data.columns and "Total" in self.serie.columns:
                pob = self.serie["Total"].iloc[-1]
                tasa_por = self._conf.get("tasa_por", 100000)
                y_true = test_data["y_original"].to_numpy()[: len(yhat_raw)]
                yhat = (yhat_raw * pob) / tasa_por
                y_train = self.train_data["y_original"].to_numpy()
            else:
                y_true = test_data["y"].to_numpy()[: len(yhat_raw)]
                yhat = yhat_raw
                y_train = self.train_data["y"].to_numpy()

            from epiforecast.evaluation.metrics import compute_forecast_metrics

            metrics = compute_forecast_metrics(y_true, yhat, y_train)

            logger.info(
                "eval_rapida {} | {} | RMSE={:.4f} MAE={:.4f} MAPE={:.2f}%{}",
                self.entidad or "Nacional",
                self.sexo,
                metrics["rmse"],
                metrics["mae"],
                metrics["mape"],
                f" MASE={metrics['mase']:.3f}" if metrics.get("mase") is not None else "",
            )
            return metrics

        except Exception as e:  # noqa: BLE001 — eval opcional, nunca debe romper run()
            # Series estatales muy cortas/casi-cero pueden no entrenar (idle transformation
            # de GluonTS); se reporta métrica nula sin abortar el combo.
            logger.warning("eval_rapida (hold-out) fallo para {}: {}", self.entidad, e)
            return null_metrics

    # ── Orchestration ─────────────────────────────────────────────────────────

    def run(self) -> tuple[Any, dict[str, Any], dict[str, Any]]:
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

        # skip_cv_estatal: en SageMaker, CV estatal no aporta (DeepAR no hace HP tuning)
        skip_cv = self.deepar_conf.get("skip_cv_estatal", False) and self.entidad is not None

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
        elif skip_cv:
            confianza = "normal"
            best_metrics = {
                "rmse": None,
                "mae": None,
                "mape": None,
                "smape": None,
                "mase": None,
            }
            logger.debug(
                "skip_cv_estatal: omitiendo CV para {} | {} | {}",
                self.padecimiento,
                self.entidad,
                self.sexo,
            )
        else:
            confianza = "normal"
            best_metrics = self.cross_validate(self.train_data)

        # Train on full series
        self.fit(self.serie)

        # Evaluacion rapida post-entrenamiento para modelos que no hicieron CV completo
        if skip_cv or es_insuficiente:
            eval_metrics = self._eval_rapida()
            best_metrics.update(eval_metrics)

        best_metrics["confianza"] = confianza
        best_metrics["promedio_semanal"] = promedio

        # Metricas in-sample (train) para deteccion de overfitting/leakage
        if self._predictor is not None and not self.train_data.empty:
            try:
                from epiforecast.evaluation.metrics import compute_forecast_metrics

                ds_train = self._build_dataset(self.train_data)
                fc_train = list(self._predictor.predict(ds_train, num_samples=self.num_samples))
                yhat_tr = fc_train[0].mean[: len(self.train_data)]
                y_tr = self.train_data["y"].to_numpy(dtype=float)[: len(yhat_tr)]
                train_m = compute_forecast_metrics(y_tr, yhat_tr, y_tr)
                best_metrics["rmse_train"] = train_m.get("rmse")
                best_metrics["smape_train"] = train_m.get("smape")
            except (ValueError, KeyError, RuntimeError) as e:
                logger.warning("No se pudieron calcular metricas train (DeepAR): {}", e)

        return self._predictor, best_metrics, self.get_params()
