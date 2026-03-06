# src/epiforecast/visualization/forecast_plots.py
"""Forecast visualization: generate PNG charts per model (SRP: charts only).

Reads all_forecast.csv + training CSVs, generates one PNG per
(padecimiento, entidad, modo) combination using GraficosHelper.
"""

from pathlib import Path
import re
from typing import Any
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


def generar_graficos_pronostico(config: dict[str, Any] | None = None) -> None:
    """Generate one forecast chart per model from all_forecast.csv.

    Args:
        config: Dict de configuración (default: conf global de YAML).

    Output structure:
        reports/forecasts/{padecimiento}/{entidad|Nacional}/{nombre}.png
    """
    _conf = config if config is not None else conf
    forecast_file = Path(_conf["data"]["forecast"])
    models_root = Path(_conf["paths"]["models"])
    forecast_root = Path(_conf["paths"]["forecast"])

    df_forecast = pd.read_csv(forecast_file)
    df_forecast["ds"] = pd.to_datetime(df_forecast["ds"], errors="coerce")
    df_forecast = df_forecast.dropna(subset=["ds"])

    graficos = GraficosHelper(carpeta_salida="", numero_top_columnas=10)
    df_hp_all = _load_hp_data(models_root)

    modelos = (
        df_forecast[["meta_padecimiento", "meta_entidad", "meta_modo"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    total = len(modelos)
    logger.info("Generando {} gráficos de pronóstico...", total)

    for i, (_, row) in enumerate(modelos.iterrows()):
        padecimiento = str(row["meta_padecimiento"])
        entidad = "" if pd.isna(row["meta_entidad"]) else str(row["meta_entidad"])
        modo = str(row["meta_modo"])

        serie = _load_training_series(padecimiento, entidad, modo, models_root)
        if serie is None:
            continue

        nivel_dir = _nivel_directory(entidad)
        carpeta = forecast_root / padecimiento / nivel_dir
        directory_manager.asegurar_ruta(carpeta)
        graficos.carpeta_salida = str(carpeta)

        mask_fc = (
            (df_forecast["meta_padecimiento"] == padecimiento)
            & (df_forecast["meta_entidad"].fillna("") == entidad)
            & (df_forecast["meta_modo"] == modo)
        )
        forecast = df_forecast[mask_fc][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        metricas = _extract_metricas(df_forecast, mask_fc, df_hp_all)

        titulo = f"{padecimiento} · {entidad or 'Nacional'} · {modo}"
        nombre_archivo = f"{padecimiento}_{nivel_dir}_{modo}"

        ruta = graficos.graficar_pronostico(
            forecast=forecast,
            serie=serie,
            titulo=titulo,
            padecimiento=padecimiento,
            nombre_archivo=nombre_archivo,
            metricas=metricas,
        )
        logger.info("[{}/{}] Guardado: {}", i + 1, total, Path(ruta).name)

    logger.success("Gráficos generados: {} → {}", total, forecast_root)


def _load_hp_data(models_root: Path) -> pd.DataFrame:
    """Carga hiperparámetros desde CSVs *_completo.csv."""
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
        except (KeyError, ValueError, FileNotFoundError):
            pass
    if hp_frames:
        return (
            pd.concat(hp_frames, ignore_index=True)
            .drop_duplicates("archivo_modelo")
            .set_index("archivo_modelo")
        )
    return pd.DataFrame()


def _build_csv_path(padecimiento: str, entidad: str, modo: str, models_root: Path) -> Path:
    """Construye la ruta del CSV de entrenamiento (sidecar del .pkl)."""
    modelo_activo = conf.get("modelo_activo", "prophet").capitalize()
    pad_norm = _normalizar_nombre(padecimiento)

    if not entidad or entidad.lower() == "nacional":
        csv_name = f"{modelo_activo}_{pad_norm}_{modo}.csv"
    elif entidad.startswith("Region "):
        region_norm = _normalizar_nombre(entidad[len("Region ") :])
        csv_name = f"{modelo_activo}_{pad_norm}_region_{region_norm}_{modo}.csv"
    else:
        entidad_norm = _normalizar_nombre(entidad)
        csv_name = f"{modelo_activo}_{pad_norm}_{entidad_norm}_{modo}.csv"
    return models_root / pad_norm / csv_name


def _load_training_series(
    padecimiento: str,
    entidad: str,
    modo: str,
    models_root: Path,
) -> pd.DataFrame | None:
    """Carga y prepara la serie de entrenamiento desde CSV."""
    csv_path = _build_csv_path(padecimiento, entidad, modo, models_root)
    if not csv_path.exists():
        logger.warning("CSV de entrenamiento no encontrado: {}", csv_path)
        return None

    serie = pd.read_csv(csv_path)
    serie["ds"] = pd.to_datetime(serie["ds"], errors="coerce")
    serie = serie.dropna(subset=["ds"])

    if "y_original" in serie.columns:
        return serie[["ds", "y_original"]].rename(columns={"y_original": "y"})
    return serie[["ds", "y"]]


def _nivel_directory(entidad: str) -> str:
    """Determina el nombre del subdirectorio según nivel geográfico."""
    if not entidad or entidad.lower() == "nacional":
        return "Nacional"
    return entidad.replace("/", "-").replace(" ", "_")


def _extract_metricas(
    df_forecast: pd.DataFrame,
    mask: pd.Series,
    df_hp_all: pd.DataFrame,
) -> dict[str, Any]:
    """Extract model metrics and HP for chart annotation."""
    # Extraer la primera fila que coincide con la máscara
    subset = df_forecast.loc[mask]
    if subset.empty:
        return {
            "mase": None,
            "rmse": None,
            "confianza": "normal",
            "es_fallback": False,
            "modelo_usado": "N/A",
        }

    row = subset.iloc[0]

    # Extraer valores con seguridad (maneja columnas faltantes)
    m_orig = row.get("archivo_modelo_original", "N/A")
    m_used = row.get("archivo_modelo_usado", "N/A")
    es_fallback = str(m_orig) != str(m_used)

    metricas = {
        "mase": float(row["mase_usado"])
        if "mase_usado" in row and pd.notna(row["mase_usado"])
        else None,
        "rmse": float(row["rmse_usado"])
        if "rmse_usado" in row and pd.notna(row["rmse_usado"])
        else None,
        "smape": float(row["smape_usado"])
        if "smape_usado" in row and pd.notna(row["smape_usado"])
        else None,
        "mae": float(row["mae_usado"])
        if "mae_usado" in row and pd.notna(row["mae_usado"])
        else None,
        "mape": float(row["mape_usado"])
        if "mape_usado" in row and pd.notna(row["mape_usado"])
        else None,
        "confianza": str(row["confianza_original"])
        if "confianza_original" in row and pd.notna(row["confianza_original"])
        else "normal",
        "es_fallback": es_fallback,
        "modelo_usado": str(m_used),
        "meta_modelo": str(row.get("meta_modelo", "")),
    }

    # Add HP from complete CSV
    modelo_key = str(m_used)
    if not df_hp_all.empty and modelo_key in df_hp_all.index:
        hp = df_hp_all.loc[modelo_key]
        metricas["seasonality_mode"] = str(hp["seasonality_mode"])
        metricas["changepoint_prior_scale"] = float(hp["changepoint_prior_scale"])
        metricas["seasonality_prior_scale"] = float(hp["seasonality_prior_scale"])

    return metricas
