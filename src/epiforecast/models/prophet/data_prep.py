"""Prophet data preparation: aggregation, train/test split, quick evaluation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from epiforecast.artifacts import TransformContract
from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.utils.cohorts import is_neuro
from epiforecast.utils.config import logger


def _positive_exposure(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return a finite, positive exposure column or fail before transforming counts."""
    if column not in frame.columns:
        raise ValueError(f"falta la columna de exposición requerida: {column}")
    exposure = pd.to_numeric(frame[column], errors="coerce").astype(float)
    values = exposure.to_numpy()
    if values.size == 0 or not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError(f"la exposición '{column}' debe ser finita y estrictamente positiva")
    return exposure


def agrupa(
    df: pd.DataFrame,
    sexo: str | None,
    normalizar_tasa: bool,
    col_poblacion: str,
) -> pd.DataFrame:
    """Aggregate data by date, summing target column and optionally population."""
    working = df
    agg_dict: dict[str | None, str] = {sexo: "sum"}
    if normalizar_tasa:
        working = df.copy()
        working[col_poblacion] = _positive_exposure(working, col_poblacion)
        agg_dict[col_poblacion] = "sum"
    return working.groupby("Fecha").agg(agg_dict)


def crea_train_test(
    serie: pd.DataFrame,
    sexo: str | None,
    normalizar_tasa: bool,
    col_poblacion: str,
    log_transform: bool,
    tasa_por: float,
    fecha_corte: str,
    transform_contract: TransformContract | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, float | None]:
    """Create train/test split with rate normalization and log-transform.

    Returns:
        (serie, train_data, test_data, poblacion_valor)
    """
    serie = serie.rename_axis("ds").reset_index()
    poblacion_valor: float | None = None

    if transform_contract is not None:
        exposure: pd.Series | None = None
        if transform_contract.requires_exposure:
            exposure = _positive_exposure(serie, col_poblacion)
            # El horizonte usa la exposición más reciente. El forward histórico sí usa
            # la exposición correspondiente a cada fecha.
            poblacion_valor = float(exposure.iloc[-1])
            serie["y_original"] = serie[sexo]
        serie["y"] = transform_contract.apply_forward(
            serie[sexo],
            exposure=None if exposure is None else exposure.to_numpy(),
        )
        serie = serie.drop(columns=[sexo])
        logger.debug(
            "TransformContract v{} aplicado: {}",
            transform_contract.schema_version,
            [step.value for step in transform_contract.forward_steps],
        )
    elif normalizar_tasa:
        exposure = _positive_exposure(serie, col_poblacion)
        poblacion_valor = float(exposure.iloc[-1])
        serie["y_original"] = serie[sexo]
        serie["y"] = (serie[sexo] / exposure) * tasa_por
        serie = serie.drop(columns=[sexo])
        logger.debug(
            "Normalizado a tasa por {:,.0f} hab. (poblaci\u00f3n: {:,.0f})",
            tasa_por,
            poblacion_valor,
        )
    else:
        serie = serie.rename(columns={sexo: "y"})

    if transform_contract is None and log_transform:
        serie["y"] = np.log1p(serie["y"])
        logger.debug("Log-transform aplicado: y = log(1 + y)")

    train_data = serie[serie["ds"] < fecha_corte]
    test_data = serie[serie["ds"] >= fecha_corte]

    logger.debug("Train: {} semanas (hasta {})", len(train_data), train_data["ds"].max().date())
    logger.debug("Test: {} semanas (desde {})", len(test_data), test_data["ds"].min().date())

    return serie, train_data, test_data, poblacion_valor


def promedio_semanal(train_data: pd.DataFrame) -> float:
    """Return weekly average of original count (before transforms)."""
    if "y_original" in train_data.columns:
        return float(train_data["y_original"].mean())
    return float(train_data["y"].mean())


def eval_rapida(
    model: Any,
    test_data: pd.DataFrame,
    train_data: pd.DataFrame,
    normalizar_tasa: bool,
    poblacion_valor: float | None,
    log_transform: bool,
    tasa_por: float,
    entidad: str | None,
    sexo: str | None,
    col_poblacion: str = "Total",
    transform_contract: TransformContract | None = None,
) -> dict[str, Any]:
    """Evaluacion rapida post-entrenamiento (sin reentrenar).

    Predice sobre un holdout con el modelo ajustado solo en ``train_data`` y
    compara en casos absolutos. El caller puede hacer el refit final después.
    """
    null_metrics: dict[str, Any] = {
        "rmse": None,
        "mae": None,
        "mape": None,
        "smape": None,
        "mase": None,
    }

    if model is None or test_data.empty or len(test_data) < 4:
        return null_metrics

    try:
        pred_cols = ["ds", "oni"] if "oni" in test_data.columns else ["ds"]
        forecast = model.predict(test_data[pred_cols])
        merged = test_data[["ds", "y"]].merge(forecast[["ds", "yhat"]], on="ds")

        if transform_contract is not None:
            if transform_contract.requires_exposure:
                if "y_original" not in test_data.columns or "y_original" not in train_data.columns:
                    raise ValueError("faltan conteos originales para evaluar un contrato de tasa")
                merged_orig = test_data[["ds", "y_original"]].merge(
                    forecast[["ds", "yhat"]], on="ds"
                )
                y_true = merged_orig["y_original"].to_numpy(dtype=float)
                if col_poblacion not in test_data.columns:
                    raise ValueError("falta exposición por fecha en evaluación rápida")
                exposure_by_date = test_data[["ds", col_poblacion]].drop_duplicates("ds")
                aligned = merged_orig[["ds"]].merge(exposure_by_date, on="ds", how="left")
                exposure = pd.to_numeric(aligned[col_poblacion], errors="coerce").to_numpy(
                    dtype=float
                )
                y_pred = transform_contract.apply_inverse(
                    merged_orig["yhat"].to_numpy(dtype=float),
                    exposure=exposure,
                )
                y_train = train_data["y_original"].to_numpy(dtype=float)
            else:
                y_true = transform_contract.apply_inverse(merged["y"].to_numpy(dtype=float))
                y_pred = transform_contract.apply_inverse(merged["yhat"].to_numpy(dtype=float))
                y_train = transform_contract.apply_inverse(train_data["y"].to_numpy(dtype=float))
        elif normalizar_tasa and poblacion_valor and "y_original" in test_data.columns:
            merged_orig = test_data[["ds", "y_original"]].merge(forecast[["ds", "yhat"]], on="ds")
            y_true = merged_orig["y_original"].to_numpy()
            yhat_tasa = merged_orig["yhat"].to_numpy()
            if log_transform:
                yhat_tasa = np.expm1(yhat_tasa)
            exposure_factor: Any
            if col_poblacion in test_data.columns:
                exposure_by_date = test_data[["ds", col_poblacion]].drop_duplicates("ds")
                aligned = merged_orig[["ds"]].merge(exposure_by_date, on="ds", how="left")
                exposure_factor = pd.to_numeric(aligned[col_poblacion], errors="coerce").to_numpy()
                if not np.isfinite(exposure_factor).all() or (exposure_factor <= 0).any():
                    raise ValueError("exposición inválida en evaluación rápida")
            else:
                exposure_factor = poblacion_valor
            y_pred = (yhat_tasa * exposure_factor) / tasa_por
            y_train = train_data["y_original"].to_numpy()
        else:
            y_true = merged["y"].to_numpy()
            y_pred = merged["yhat"].to_numpy()
            y_train = train_data["y"].to_numpy()

        metrics = compute_forecast_metrics(y_true, y_pred, y_train)

        logger.info(
            "eval_rapida {} | {} | RMSE={:.4f} MAE={:.4f} SMAPE={:.2f}%{}",
            entidad or "Nacional",
            sexo,
            metrics["rmse"],
            metrics["mae"],
            metrics["smape"],
            f" MASE={metrics['mase']:.3f}" if metrics["mase"] is not None else "",
        )
        return metrics

    except (RuntimeError, ValueError, KeyError) as e:
        logger.warning("eval_rapida fallo para {}: {}", entidad, e)
        return null_metrics


def build_holidays(
    conf: dict[str, Any],
    entidad: str | None,
    padecimiento: str | None,
) -> pd.DataFrame:
    """Build holidays DataFrame from atypical periods + regime changes."""
    # Padecimientos fuera de la cohorte neuro (p.ej. Dengue) NO usan los periodos atípicos
    # (holiday COVID): 2020-2022 no fue una disrupción para una arbovirosis, siguió su ciclo.
    periodos = conf["peridos_atipicos"] if is_neuro(padecimiento) else []
    holidays = pd.DataFrame(periodos, columns=["holiday", "ds", "lower_window", "upper_window"])
    if not holidays.empty:
        holidays["ds"] = pd.to_datetime(holidays["ds"])

    cambios = conf.get("cambios_regimen", [])
    if cambios and entidad:
        filtrados = [
            c
            for c in cambios
            if c.get("entidad") == entidad
            and (not c.get("padecimiento") or c.get("padecimiento") == padecimiento)
        ]
        if filtrados:
            df_cambios = pd.DataFrame(filtrados)
            df_cambios["ds"] = pd.to_datetime(df_cambios["ds"])
            cols = ["holiday", "ds", "lower_window", "upper_window"]
            holidays = pd.concat([holidays, df_cambios[cols]], ignore_index=True)
            logger.debug(
                "Cambios de r\u00e9gimen para {}: {}",
                entidad,
                [c["holiday"] for c in filtrados],
            )

    return holidays


def build_seasonality_params(conf: dict[str, Any], modelado_estados: bool) -> dict[str, Any]:
    """Build seasonality params, applying regional fourier_order if needed."""
    raw = dict(conf["add_seasonality"])
    fourier_regional = raw.pop("fourier_order_regional", None)
    if modelado_estados and fourier_regional is not None:
        raw["fourier_order"] = fourier_regional
        logger.debug("fourier_order_regional={} aplicado", fourier_regional)
    return raw


def apply_regional_params(
    param_model: dict[str, Any],
    conf: dict[str, Any],
    modelado_estados: bool,
) -> None:
    """Apply regional overrides for state-level models (shorter series)."""
    n_cp_regional = conf.get("n_changepoints_regional")
    if modelado_estados and n_cp_regional is not None:
        param_model["n_changepoints"] = n_cp_regional
        logger.debug("n_changepoints_regional={} aplicado", n_cp_regional)
