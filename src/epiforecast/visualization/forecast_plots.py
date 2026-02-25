# src/epiforecast/visualization/forecast_plots.py
"""Forecast visualization: generate PNG charts per model (SRP: charts only).

Reads all_forecast.csv + training CSVs, generates one PNG per
(padecimiento, entidad, modo) combination using GraficosHelper.
"""

from pathlib import Path
import re
import unicodedata

import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger
from epiforecast.visualization.base import GraficosHelper


def _normalizar_nombre(s: str) -> str:
    """Normalize string for filenames: remove accents, replace spaces with '_'.

    Must match normalizar() in scripts/entrena.py.
    """
    sin_acento = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    sin_acento = sin_acento.replace("/", "-")
    return re.sub(r"\s+", "_", sin_acento)


def generar_graficos_pronostico() -> None:
    """Generate one forecast chart per model from all_forecast.csv.

    Output structure:
        forecast/{padecimiento}/{entidad|Nacional}/{nombre}.png
    """
    forecast_file = Path(conf["data"]["forecast"])
    models_root = Path(conf["paths"]["models"])
    forecast_root = Path(conf["paths"]["forecast"])

    df_forecast = pd.read_csv(forecast_file)
    df_forecast["ds"] = pd.to_datetime(df_forecast["ds"], errors="coerce")
    df_forecast = df_forecast.dropna(subset=["ds"])

    graficos = GraficosHelper(carpeta_salida="", numero_top_columnas=10)

    # Load hyperparameters from complete CSVs
    hp_frames = []
    for csv_hp in models_root.rglob("*_completo.csv"):
        try:
            df_hp = pd.read_csv(
                csv_hp,
                usecols=[
                    "archivo_modelo",
                    "seasonality_mode",
                    "changepoint_prior_scale",
                    "seasonality_prior_scale",
                ],
            )
            hp_frames.append(df_hp)
        except Exception:
            pass
    df_hp_all = (
        pd.concat(hp_frames, ignore_index=True)
        .drop_duplicates("archivo_modelo")
        .set_index("archivo_modelo")
        if hp_frames
        else pd.DataFrame()
    )

    modelos = (
        df_forecast[["meta_padecimiento", "meta_entidad", "meta_modo"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    total = len(modelos)
    logger.info("Generando {} gráficos de pronóstico...", total)

    for i, row in modelos.iterrows():
        padecimiento = str(row["meta_padecimiento"])
        entidad = "" if pd.isna(row["meta_entidad"]) else str(row["meta_entidad"])
        modo = str(row["meta_modo"])

        # Build CSV path for training data (sidecar of .pkl)
        pad_norm = _normalizar_nombre(padecimiento)

        if not entidad or entidad.lower() == "nacional":
            csv_name = f"Prophet_{pad_norm}_{modo}.csv"
            entidad_norm = ""
        elif entidad.startswith("Region "):
            region_part = entidad[len("Region ") :]
            region_norm = _normalizar_nombre(region_part)
            csv_name = f"Prophet_{pad_norm}_region_{region_norm}_{modo}.csv"
            entidad_norm = _normalizar_nombre(entidad)
        else:
            entidad_norm = _normalizar_nombre(entidad)
            csv_name = f"Prophet_{pad_norm}_{entidad_norm}_{modo}.csv"

        csv_path = models_root / pad_norm / csv_name
        if not csv_path.exists():
            logger.warning("CSV de entrenamiento no encontrado: {}", csv_path)
            continue

        serie = pd.read_csv(csv_path)
        serie["ds"] = pd.to_datetime(serie["ds"], errors="coerce")
        serie = serie.dropna(subset=["ds"])

        if "y_original" in serie.columns:
            serie = serie[["ds", "y_original"]].rename(columns={"y_original": "y"})
        else:
            serie = serie[["ds", "y"]]

        # Output directory
        if not entidad or entidad.lower() == "nacional":
            nivel_dir = "Nacional"
        else:
            nivel_dir = entidad.replace("/", "-").replace(" ", "_")
        carpeta = forecast_root / padecimiento / nivel_dir
        directory_manager.asegurar_ruta(carpeta)
        graficos.carpeta_salida = str(carpeta)

        # Filter forecast rows for this model
        mask_fc = (
            (df_forecast["meta_padecimiento"] == padecimiento)
            & (df_forecast["meta_entidad"].fillna("") == entidad)
            & (df_forecast["meta_modo"] == modo)
        )
        forecast = df_forecast[mask_fc][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()

        # Extract metrics for chart annotation
        metricas = _extract_metricas(df_forecast, mask_fc, df_hp_all)

        nivel_label = entidad if entidad else "Nacional"
        titulo = f"{padecimiento} · {nivel_label} · {modo}"
        nombre_archivo = f"{padecimiento}_{nivel_dir}_{modo}"

        ruta = graficos.graficar_pronostico(
            forecast=forecast,
            serie=serie,
            titulo=titulo,
            padecimiento=padecimiento,
            nombre_archivo=nombre_archivo,
            metricas=metricas,
        )
        logger.info("[{}/{}] Guardado: {}", i + 1, total, Path(ruta).name)  # type: ignore[operator]

    logger.success("Gráficos generados: {} → {}", total, forecast_root)


def _extract_metricas(
    df_forecast: pd.DataFrame,
    mask: pd.Series,
    df_hp_all: pd.DataFrame,
) -> dict:
    """Extract model metrics and HP for chart annotation."""
    row = df_forecast.loc[
        mask,
        [
            "mase_usado",
            "rmse_usado",
            "confianza_original",
            "archivo_modelo_original",
            "archivo_modelo_usado",
        ],
    ].iloc[0]

    es_fallback = str(row["archivo_modelo_original"]) != str(row["archivo_modelo_usado"])

    metricas = {
        "mase": float(row["mase_usado"]) if pd.notna(row["mase_usado"]) else None,
        "rmse": float(row["rmse_usado"]) if pd.notna(row["rmse_usado"]) else None,
        "confianza": str(row["confianza_original"])
        if pd.notna(row["confianza_original"])
        else "normal",
        "es_fallback": es_fallback,
        "modelo_usado": str(row["archivo_modelo_usado"]),
    }

    # Add HP from complete CSV
    modelo_key = str(row["archivo_modelo_usado"])
    if not df_hp_all.empty and modelo_key in df_hp_all.index:
        hp = df_hp_all.loc[modelo_key]
        metricas["seasonality_mode"] = str(hp["seasonality_mode"])
        metricas["changepoint_prior_scale"] = float(hp["changepoint_prior_scale"])
        metricas["seasonality_prior_scale"] = float(hp["seasonality_prior_scale"])

    return metricas
