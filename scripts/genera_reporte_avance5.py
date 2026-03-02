"""Genera el reporte completo del Avance 5: Modelo Final.

Carga metricas de los 4 modelos, genera 18 graficos y un Markdown con tablas,
interpretacion y seleccion del modelo final.

Uso:
    python -m scripts.genera_reporte_avance5
"""

from __future__ import annotations

from pathlib import Path
import pickle

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import logger
from epiforecast.visualization.avance5_charts import (
    DPI,
    build_error_boxplots,
    build_feature_importance,
    build_metric_bars,
    build_residual_analysis,
    build_trend_prediction,
    build_win_rate_heatmap,
)
from epiforecast.visualization.avance5_tables import (
    cargar_completos,
    generar_markdown,
    merge_all_models,
    win_rate_by_state,
)
from epiforecast.visualization.comparison_config import MODEL_STYLES

matplotlib.use("Agg")

_PADECIMIENTOS = ["Depresión", "Parkinson", "Alzheimer"]
_MODELS = ["prophet", "deepar", "ensemble", "stacking"]

# Mapa para nombres de archivo sin acentos
_NOMBRE_ARCHIVO: dict[str, str] = {
    "Depresión": "depresion",
    "Parkinson": "parkinson",
    "Alzheimer": "alzheimer",
}


def _pad_filename(pad: str) -> str:
    """Nombre de archivo sin acentos para un padecimiento."""
    return _NOMBRE_ARCHIVO.get(pad, pad.lower())


def _save(fig: plt.Figure, path: Path) -> None:
    """Guarda figura y cierra."""
    directory_manager.asegurar_ruta(path.parent)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("  Guardado: {}", path)


def _load_forecasts(model_key: str) -> pd.DataFrame | None:
    """Carga all_forecast_{model}.csv si existe."""
    path = Path("reports") / "forecasts" / model_key / f"all_forecast_{model_key}.csv"
    if not path.exists():
        logger.warning("No encontrado: {}", path)
        return None
    return pd.read_csv(path, parse_dates=["ds"])


def _load_real_data() -> pd.DataFrame | None:
    """Carga datos reales de data/processed/data_inegi_General.csv."""
    path = Path("data") / "processed" / "data_inegi_General.csv"
    if not path.exists():
        logger.warning("No encontrado: {}", path)
        return None
    return pd.read_csv(path, parse_dates=["Fecha"])


def _build_serie_real(
    real_data: pd.DataFrame, padecimiento: str, modo: str = "incrementos_total"
) -> pd.DataFrame | None:
    """Extrae serie real nacional para un padecimiento."""
    sub = real_data[real_data["Padecimiento"] == padecimiento].copy()
    if sub.empty:
        return None
    # Agregar a nivel nacional (suma de todas las entidades por fecha)
    return (
        sub.groupby("Fecha")[modo]
        .sum()
        .reset_index()
        .rename(columns={"Fecha": "ds", modo: "y"})
        .sort_values("ds")
    )


def _filter_forecast(
    fc: pd.DataFrame, padecimiento: str, entidad: str = "", modo: str = "general"
) -> pd.DataFrame:
    """Filtra forecast por padecimiento, entidad y modo."""
    mask = fc["meta_padecimiento"] == padecimiento
    if entidad:
        mask &= fc["meta_entidad"] == entidad
    else:
        # Nacional: tomar todas las entidades y promediar, o la primera disponible
        pass
    mask &= fc["meta_modo"] == modo
    sub = fc[mask].copy()
    if sub.empty:
        return sub
    # Agregar por fecha (media de yhat sobre entidades)
    agg = (
        sub.groupby("ds")
        .agg(
            yhat=("yhat", "mean"),
            yhat_lower=("yhat_lower", "mean") if "yhat_lower" in sub.columns else ("yhat", "mean"),
            yhat_upper=("yhat_upper", "mean") if "yhat_upper" in sub.columns else ("yhat", "mean"),
        )
        .reset_index()
    )
    agg["ds"] = pd.to_datetime(agg["ds"])
    return agg.sort_values("ds")


def _load_xgb_importances() -> tuple[np.ndarray, list[str]] | None:
    """Carga feature importances del XGBoost del Ensemble."""
    pkl_path = Path("models") / "ensemble" / "Depresion" / "Ensemble_Depresion_general.pkl"
    if not pkl_path.exists():
        logger.warning("Pickle Ensemble no encontrado: {}", pkl_path)
        return None
    try:
        with open(pkl_path, "rb") as f:
            payload = pickle.load(f)  # noqa: S301
        features = payload.get("features", [])
        engine = payload.get("parallel_engine")
        if engine is not None and hasattr(engine, "_xgb_direct"):
            xgb_model = engine._xgb_direct._model
            return np.array(xgb_model.feature_importances_), list(features)
        xgb = payload.get("xgb")
        if xgb is not None:
            return np.array(xgb.feature_importances_), list(features)
    except Exception as exc:
        logger.warning("Error cargando XGBoost importances: {}", exc)
    return None


def _load_stacking_weights() -> tuple[np.ndarray, list[str]] | None:
    """Carga pesos de expertos del Stacking."""
    pkl_path = Path("models") / "stacking" / "Depresion" / "Stacking_Depresion_general.pkl"
    if not pkl_path.exists():
        logger.warning("Pickle Stacking no encontrado: {}", pkl_path)
        return None
    try:
        with open(pkl_path, "rb") as f:
            payload = pickle.load(f)  # noqa: S301
        weights = payload.get("weights")
        if weights is not None:
            return np.array(weights), ["Prophet", "ETS", "LightGBM"]
    except Exception as exc:
        logger.warning("Error cargando Stacking weights: {}", exc)
    return None


def main() -> None:
    """Orquestador principal del reporte Avance 5."""
    logger.info("=== Reporte Avance 5: Modelo Final ===")

    fig_dir = Path("reports") / "figures" / "ModeloFinal"
    report_dir = Path("reports") / "ProdDetails"
    directory_manager.asegurar_ruta(fig_dir)
    directory_manager.asegurar_ruta(report_dir)

    # 1. Cargar metricas
    logger.info("Cargando metricas de los 4 modelos...")
    data = cargar_completos()
    if not data:
        logger.error("No se encontraron CSVs de metricas. Ejecute 'make train-all' primero.")
        return

    model_keys = [mk for mk in _MODELS if mk in data]
    logger.info("Modelos disponibles: {}", model_keys)

    # 2. Merge N-way
    merged = merge_all_models(data)
    logger.info("Merge completado: {} filas x {} columnas", len(merged), len(merged.columns))

    # Determinar ganador global
    if "ganador_rmse" in merged.columns:
        ganador = merged["ganador_rmse"].value_counts().index[0]
    else:
        ganador = model_keys[0]
    ganador_style = MODEL_STYLES.get(ganador, MODEL_STYLES["stacking"])
    logger.info("Modelo ganador (RMSE): {}", ganador_style.label)

    # 3. Cargar forecasts y datos reales
    forecasts: dict[str, pd.DataFrame] = {}
    for mk in model_keys:
        fc = _load_forecasts(mk)
        if fc is not None:
            forecasts[mk] = fc

    real_data = _load_real_data()

    # 4. Chart 1: Tendencia + prediccion (3 PNGs)
    logger.info("Generando graficos de tendencia...")
    if real_data is not None and ganador in forecasts and "prophet" in forecasts:
        for pad in _PADECIMIENTOS:
            serie_real = _build_serie_real(real_data, pad)
            fc_winner = _filter_forecast(forecasts[ganador], pad)
            fc_prophet = _filter_forecast(forecasts["prophet"], pad)
            if serie_real is not None and not fc_winner.empty and not fc_prophet.empty:
                cutoff = serie_real["ds"].max()
                fig = build_trend_prediction(
                    serie_real, fc_winner, fc_prophet, pad, ganador, cutoff
                )
                _save(fig, fig_dir / f"tendencia_prediccion_{_pad_filename(pad)}.png")
    else:
        logger.warning("Datos insuficientes para graficos de tendencia.")

    # 5. Chart 2: Residuales (3 PNGs)
    logger.info("Generando graficos de residuales...")
    if real_data is not None and ganador in forecasts:
        for pad in _PADECIMIENTOS:
            serie_real = _build_serie_real(real_data, pad)
            fc_winner = _filter_forecast(forecasts[ganador], pad)
            if serie_real is not None and not fc_winner.empty:
                # Merge real con prediccion
                fc_aligned = fc_winner.merge(
                    serie_real.rename(columns={"y": "y_real"}), on="ds", how="inner"
                )
                if not fc_aligned.empty:
                    residuals = fc_aligned["y_real"].values - fc_aligned["yhat"].values
                    fig = build_residual_analysis(
                        residuals,
                        fc_aligned["ds"],
                        ganador_style.label,
                        ganador_style.color,
                        pad,
                    )
                    _save(fig, fig_dir / f"residuos_{_pad_filename(pad)}.png")
    else:
        logger.warning("Datos insuficientes para graficos de residuales.")

    # 6. Chart 3: Feature importance (1 PNG)
    logger.info("Generando grafico de importancia de features...")
    xgb_data = _load_xgb_importances()
    stacking_data = _load_stacking_weights()
    if xgb_data is not None and stacking_data is not None:
        fig = build_feature_importance(
            xgb_data[0], xgb_data[1], stacking_data[0], stacking_data[1]
        )
        _save(fig, fig_dir / "importancia_features.png")
    else:
        logger.warning("Datos insuficientes para grafico de importancia de features.")

    # 7. Chart 4: Barras de metricas (4 PNGs)
    logger.info("Generando graficos de barras de metricas...")
    fig = build_metric_bars(merged, model_keys)
    _save(fig, fig_dir / "comparacion_metricas_global.png")
    for pad in _PADECIMIENTOS:
        fig = build_metric_bars(merged, model_keys, padecimiento=pad)
        _save(fig, fig_dir / f"comparacion_metricas_{_pad_filename(pad)}.png")

    # 8. Chart 5: Boxplots (4 PNGs)
    logger.info("Generando boxplots de errores...")
    fig = build_error_boxplots(merged, model_keys)
    _save(fig, fig_dir / "distribucion_errores_global.png")
    for pad in _PADECIMIENTOS:
        fig = build_error_boxplots(merged, model_keys, padecimiento=pad)
        _save(fig, fig_dir / f"distribucion_errores_{_pad_filename(pad)}.png")

    # 9. Chart 6: Heatmap win rate (3 PNGs)
    logger.info("Generando heatmaps de win rate...")
    win_rates = win_rate_by_state(merged, model_keys)
    for pad in _PADECIMIENTOS:
        if pad in win_rates:
            fig = build_win_rate_heatmap(win_rates[pad], pad, model_keys)
            _save(fig, fig_dir / f"heatmap_winrate_{_pad_filename(pad)}.png")

    # 10. Generar Markdown
    logger.info("Generando reporte Markdown...")
    md_content = generar_markdown(merged, model_keys, fig_rel="../figures/ModeloFinal")
    md_path = report_dir / "avance5_modelo_final.md"
    md_path.write_text(md_content, encoding="utf-8")
    logger.success("Reporte generado: {}", md_path)

    logger.info("=== Reporte Avance 5 completado ===")
    logger.info("  Figuras: {}/", fig_dir)
    logger.info("  Markdown: {}", md_path)


if __name__ == "__main__":
    main()
