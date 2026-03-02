"""Parchea los *_completo.csv con rmse_train / smape_train sin re-entrenar.

Carga cada .pkl existente, predice in-sample sobre train_data, computa
metricas y actualiza el CSV correspondiente.  DeepAR se omite por defecto
(requiere inicializar PyTorch); usar --include-deepar para incluirlo.

Uso:
    python -m scripts.patch_train_metrics               # prophet+ensemble+stacking
    python -m scripts.patch_train_metrics --include-deepar
    python -m scripts.patch_train_metrics --modelo stacking
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import pickle
import sys
import time

import numpy as np
import pandas as pd

from epiforecast.evaluation.metrics import compute_forecast_metrics
from epiforecast.utils.config import logger

logging.getLogger("cmdstanpy").disabled = True

MODELS_DIR = Path("models")
CUTOFF = "2025-01-01"


# ---------------------------------------------------------------------------
# Prediccion in-sample por tipo de modelo
# ---------------------------------------------------------------------------


def _train_metrics_prophet(pkl_path: Path, serie: pd.DataFrame) -> dict[str, float | None]:
    """Metricas train para Prophet: model.predict(train[['ds']])."""
    with pkl_path.open("rb") as f:
        payload = pickle.load(f)  # noqa: S301

    model = payload["model"] if isinstance(payload, dict) and "model" in payload else payload

    train = serie[serie["ds"] < CUTOFF]
    if train.empty or len(train) < 4:
        return {"rmse_train": None, "smape_train": None}

    fc = model.predict(train[["ds"]])
    yhat = fc["yhat"].to_numpy(dtype=float)
    y_tr = train["y"].to_numpy(dtype=float)

    m = compute_forecast_metrics(y_tr, yhat, y_tr)
    return {"rmse_train": m.get("rmse"), "smape_train": m.get("smape")}


def _train_metrics_ensemble(pkl_path: Path, serie: pd.DataFrame) -> dict[str, float | None]:
    """Metricas train para Ensemble: Prophet + XGB(parallel/sequential)."""
    from epiforecast.models.ensemble.helpers import construir_features_xgb

    with pkl_path.open("rb") as f:
        payload = pickle.load(f)  # noqa: S301

    prophet = payload["prophet"]
    pe = payload.get("parallel_engine")

    train = serie[serie["ds"] < CUTOFF]
    if train.empty or len(train) < 4:
        return {"rmse_train": None, "smape_train": None}

    y_tr = train["y"].to_numpy(dtype=float)
    phat = prophet.predict(train[["ds"]])["yhat"].values

    # Intentar prediccion ensemble completa (prophet + xgb)
    if pe is not None and pe._xgb_direct is not None and pe._ensemble_weights is not None:
        feats = construir_features_xgb(
            train["y"].reset_index(drop=True), train["ds"].reset_index(drop=True)
        )
        valid = feats.notna().all(axis=1)
        xgb_pred = np.zeros(len(train))
        if valid.any():
            xgb_pred[valid.to_numpy()] = pe._xgb_direct.predict_insample(train[valid.to_numpy()])
        w = pe._ensemble_weights
        ensemble_pred = np.clip(w[0] * phat + w[1] * xgb_pred, 0, None)
    elif payload.get("xgb") is not None:
        # Sequential mode: prophet + xgb residual
        ensemble_pred = phat  # Fallback a solo prophet
    else:
        ensemble_pred = phat

    m = compute_forecast_metrics(y_tr, ensemble_pred, y_tr)
    return {"rmse_train": m.get("rmse"), "smape_train": m.get("smape")}


def _train_metrics_stacking(pkl_path: Path, serie: pd.DataFrame) -> dict[str, float | None]:
    """Metricas train para Stacking: expertos + ridge meta-learner."""
    from epiforecast.models.stacking.meta_learner import StackingMetaLearner

    with pkl_path.open("rb") as f:
        payload = pickle.load(f)  # noqa: S301

    experts = payload["experts"]
    ridge = payload.get("ridge")
    weights = payload["weights"]
    add_temporal = payload.get("add_temporal_features", False)

    train = serie[serie["ds"] < CUTOFF]
    if train.empty or len(train) < 4:
        return {"rmse_train": None, "smape_train": None}

    y_tr = train["y"].to_numpy(dtype=float)

    preds = [e.predict(train[["ds"]]) for e in experts]
    x_stack = np.column_stack(preds)

    if ridge is not None:
        if add_temporal:
            x_input = StackingMetaLearner._augment_with_temporal(x_stack, train["ds"])
        else:
            x_input = x_stack
        yhat = np.clip(ridge.predict(x_input), 0, None)
    else:
        yhat = np.clip(x_stack @ weights, 0, None)

    m = compute_forecast_metrics(y_tr, yhat, y_tr)
    return {"rmse_train": m.get("rmse"), "smape_train": m.get("smape")}


def _train_metrics_deepar(pkl_path: Path, serie: pd.DataFrame) -> dict[str, float | None]:
    """Metricas train para DeepAR: carga via load() minimo + predict."""
    from epiforecast.models.deepar.model import DeepARForecaster

    train = serie[serie["ds"] < CUTOFF]
    if train.empty or len(train) < 4:
        return {"rmse_train": None, "smape_train": None}

    # Instanciar sin constructor completo (evita dependencia de config)
    forecaster = DeepARForecaster.__new__(DeepARForecaster)
    forecaster._conf = {}
    forecaster.deepar_conf = {}
    forecaster.normalizar_tasa = False
    forecaster.num_samples = 100
    forecaster.freq = "W-MON"
    forecaster.multi_series = False
    forecaster.entidad = "patch"  # _is_multi_series = False (entidad is not None)
    forecaster.serie = pd.DataFrame()
    forecaster.serie_multi = pd.DataFrame()
    forecaster.train_data = pd.DataFrame()
    forecaster.train_data_multi = pd.DataFrame()
    forecaster._predictor = None

    forecaster.load(pkl_path)

    if forecaster._predictor is None:
        return {"rmse_train": None, "smape_train": None}

    dataset = forecaster._build_dataset(train)
    forecasts = list(forecaster._predictor.predict(dataset, num_samples=100))
    yhat = forecasts[0].mean[: len(train)]
    y_tr = train["y"].to_numpy(dtype=float)[: len(yhat)]

    m = compute_forecast_metrics(y_tr, yhat, y_tr)
    return {"rmse_train": m.get("rmse"), "smape_train": m.get("smape")}


_HANDLERS = {
    "prophet": _train_metrics_prophet,
    "ensemble": _train_metrics_ensemble,
    "stacking": _train_metrics_stacking,
    "deepar": _train_metrics_deepar,
}


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------


def patch_csv(model_key: str) -> int:
    """Parchea todos los *_completo.csv de un modelo. Retorna filas actualizadas."""
    model_dir = MODELS_DIR / model_key
    if not model_dir.exists():
        logger.warning("Directorio no encontrado: {}", model_dir)
        return 0

    handler = _HANDLERS[model_key]
    csvs = sorted(model_dir.rglob("*_completo.csv"))
    total_updated = 0

    for csv_path in csvs:
        df = pd.read_csv(csv_path)

        if "archivo_modelo" not in df.columns:
            logger.warning("CSV sin columna archivo_modelo: {}", csv_path)
            continue

        # Inicializar columnas si no existen
        if "rmse_train" not in df.columns:
            df["rmse_train"] = np.nan
        if "smape_train" not in df.columns:
            df["smape_train"] = np.nan

        updated = 0
        pad_dir = csv_path.parent

        for idx, row in df.iterrows():
            # Solo parchear filas que no tienen metricas train
            if pd.notna(row.get("rmse_train")) and pd.notna(row.get("smape_train")):
                continue

            pkl_name = row["archivo_modelo"]
            pkl_path = pad_dir / pkl_name
            if not pkl_path.exists():
                continue

            # Buscar sidecar CSV
            csv_sidecar = pkl_path.with_suffix(".csv")
            if not csv_sidecar.exists():
                continue

            serie = pd.read_csv(csv_sidecar)
            serie["ds"] = pd.to_datetime(serie["ds"])

            try:
                metrics = handler(pkl_path, serie)
                df.at[idx, "rmse_train"] = metrics.get("rmse_train")
                df.at[idx, "smape_train"] = metrics.get("smape_train")
                updated += 1
            except Exception as e:
                logger.debug("Error procesando {}: {}", pkl_name, e)

        if updated > 0:
            df.to_csv(csv_path, index=False, encoding="utf-8")
            logger.info("  {} actualizado: {}/{} filas", csv_path.name, updated, len(df))
            total_updated += updated
        else:
            logger.debug("  {} sin cambios", csv_path.name)

    return total_updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Parchear CSVs con metricas train")
    parser.add_argument(
        "--modelo",
        choices=["prophet", "ensemble", "stacking", "deepar", "all"],
        default="all",
        help="Modelo a parchear (default: all sin deepar)",
    )
    parser.add_argument(
        "--include-deepar",
        action="store_true",
        help="Incluir DeepAR (requiere PyTorch, mas lento)",
    )
    args = parser.parse_args()

    t0 = time.time()

    if args.modelo == "all":
        models = ["prophet", "ensemble", "stacking"]
        if args.include_deepar:
            models.append("deepar")
    else:
        models = [args.modelo]

    total = 0
    for model_key in models:
        logger.info("Parcheando {}...", model_key)
        t1 = time.time()
        n = patch_csv(model_key)
        total += n
        logger.info("  {} completado: {} filas en {:.1f}s", model_key, n, time.time() - t1)

    elapsed = time.time() - t0
    logger.info("Total: {} filas parcheadas en {:.1f}s ({:.1f} min)", total, elapsed, elapsed / 60)

    if total == 0:
        logger.warning("No se parchearon filas. Verificar que existen los .pkl y sidecar .csv")
        sys.exit(1)


if __name__ == "__main__":
    main()
