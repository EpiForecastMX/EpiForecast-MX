"""Prophet data preparation: aggregation, train/test split, quick evaluation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.utils.cohorts import is_neuro
from epiforecast.utils.config import logger


def agrupa(
    df: pd.DataFrame,
    sexo: str | None,
    normalizar_tasa: bool,
    col_poblacion: str,
) -> pd.DataFrame:
    """Aggregate data by date, summing target column and optionally population."""
    agg_dict: dict[str | None, str] = {sexo: "sum"}
    if normalizar_tasa and col_poblacion in df.columns:
        agg_dict[col_poblacion] = "sum"
    return df.groupby("Fecha").agg(agg_dict)


def crea_train_test(
    serie: pd.DataFrame,
    sexo: str | None,
    normalizar_tasa: bool,
    col_poblacion: str,
    log_transform: bool,
    tasa_por: int,
    fecha_corte: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, float | None]:
    """Create train/test split with rate normalization and log-transform.

    Returns:
        (serie, train_data, test_data, poblacion_valor)
    """
    serie = serie.rename_axis("ds").reset_index()
    poblacion_valor: float | None = None

    if normalizar_tasa and col_poblacion in serie.columns:
        poblacion_valor = serie[col_poblacion].iloc[0]
        serie["y_original"] = serie[sexo]
        serie["y"] = (serie[sexo] / poblacion_valor) * tasa_por
        serie = serie.drop(columns=[sexo])
        logger.debug(
            "Normalizado a tasa por {:,.0f} hab. (poblaci\u00f3n: {:,.0f})",
            tasa_por,
            poblacion_valor,
        )
    else:
        serie = serie.rename(columns={sexo: "y"})

    if log_transform:
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
    tasa_por: int,
    entidad: str | None,
    sexo: str | None,
) -> dict[str, Any]:
    """Evaluacion rapida post-entrenamiento (sin reentrenar).

    Predice sobre test_data con el modelo ya entrenado en serie completa
    y compara contra valores reales. Metricas en espacio tasa (como CV).
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

        if normalizar_tasa and poblacion_valor and "y_original" in test_data.columns:
            merged_orig = test_data[["ds", "y_original"]].merge(forecast[["ds", "yhat"]], on="ds")
            y_true = merged_orig["y_original"].to_numpy()
            yhat_tasa = merged_orig["yhat"].to_numpy()
            if log_transform:
                yhat_tasa = np.expm1(yhat_tasa)
            y_pred = (yhat_tasa * poblacion_valor) / tasa_por
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
