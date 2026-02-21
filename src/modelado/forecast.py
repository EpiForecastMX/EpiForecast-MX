# src/modelado/forecast.py
import pickle
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager
from src.utils.graficos import GraficosHelper


def _normalizar_nombre(s: str) -> str:
    """Normaliza para nombres de archivo: elimina acentos y reemplaza espacios con '_'.

    Debe coincidir con la función normalizar() de scripts/entrena.py.
    """
    sin_acento = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    sin_acento = sin_acento.replace("/", "-")
    return re.sub(r"\s+", "_", sin_acento)


def generar_graficos_pronostico() -> None:
    """Genera una gráfica de pronóstico por modelo desde all_forecast.csv.

    Estructura de salida:
        forecast/
          {padecimiento}/
            {entidad | Nacional}/
              {nombre_archivo}.png

    Lee el CSV consolidado de predicciones y el CSV de entrenamiento guardado
    junto a cada .pkl, luego llama a GraficosHelper.graficar_pronostico()
    por cada combinación única (meta_padecimiento, meta_entidad, meta_modo).
    """
    forecast_file = Path(conf["data"]["forecast"])
    models_root = Path(conf["paths"]["models"])
    forecast_root = Path(conf["paths"]["forecast"])
    train_root = models_root

    df_forecast = pd.read_csv(forecast_file)
    df_forecast["ds"] = pd.to_datetime(df_forecast["ds"], errors="coerce")
    df_forecast = df_forecast.dropna(subset=["ds"])

    graficos = GraficosHelper(carpeta_salida="", numero_top_columnas=10)

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

        # CSV de entrenamiento: mismo nombre que el .pkl, con extensión .csv
        pad_norm = _normalizar_nombre(padecimiento)
        entidad_norm = _normalizar_nombre(entidad) if entidad else ""
        csv_name = (
            f"Prophet_{pad_norm}_{entidad_norm}_{modo}.csv"
            if entidad_norm
            else f"Prophet_{pad_norm}_{modo}.csv"
        )
        csv_path = train_root / pad_norm / csv_name

        if not csv_path.exists():
            logger.warning("CSV de entrenamiento no encontrado, omitiendo: {}", csv_path)
            continue

        serie = pd.read_csv(csv_path)
        serie["ds"] = pd.to_datetime(serie["ds"], errors="coerce")
        serie = serie.dropna(subset=["ds"])

        # Carpeta de salida: forecast/{padecimiento}/{entidad | Nacional}/
        nivel_dir = entidad.replace(" ", "_") if entidad else "Nacional"
        carpeta = forecast_root / padecimiento / nivel_dir
        directory_manager.asegurar_ruta(carpeta)
        graficos.carpeta_salida = str(carpeta)

        # Forecast de este modelo
        mask_fc = (
            (df_forecast["meta_padecimiento"] == padecimiento)
            & (df_forecast["meta_entidad"].fillna("") == entidad)
            & (df_forecast["meta_modo"] == modo)
        )
        forecast = df_forecast[mask_fc][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()

        nivel_label = entidad if entidad else "Nacional"
        titulo = f"{padecimiento} · {nivel_label} · {modo}"
        nombre_archivo = f"{padecimiento}_{nivel_dir}_{modo}"

        ruta = graficos.graficar_pronostico(
            forecast=forecast,
            serie=serie,
            titulo=titulo,
            padecimiento=padecimiento,
            nombre_archivo=nombre_archivo,
        )
        logger.info("[{}/{}] Guardado: {}", i + 1, total, Path(ruta).name)

    logger.success("Gráficos generados: {} → {}", total, forecast_root)


class ForecastModelLoader:

    def __init__(self, periodo: int, model_path: Path):
        self.model_path = Path(model_path)
        self.model = None
        self.periodo = periodo
        self.poblacion = None
        self.normalizar_tasa = conf.get('normalizar_tasa', False)
        self.tasa_por = conf.get('tasa_por', 100000)
        self.log_transform = conf.get('log_transform', False)

    def load(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {self.model_path}")

        with open(self.model_path, "rb") as f:
            self.model = pickle.load(f)

        # Leer población del CSV de entrenamiento (sidecar del .pkl)
        csv_path = self.model_path.with_suffix('.csv')
        if self.normalizar_tasa and csv_path.exists():
            train_csv = pd.read_csv(csv_path, nrows=1)
            if 'Total' in train_csv.columns:
                self.poblacion = train_csv['Total'].iloc[0]

    def predict(self) -> pd.DataFrame:
        future = self.model.make_future_dataframe(periods=self.periodo, freq="W-MON")
        forecast = self.model.predict(future)

        # Revertir log-transform: exp(yhat) - 1
        if self.log_transform:
            for col in ['yhat', 'yhat_lower', 'yhat_upper']:
                forecast[col] = np.expm1(forecast[col])

        # Desnormalizar si el modelo fue entrenado con tasa por 100K
        if self.normalizar_tasa and self.poblacion:
            forecast['yhat_tasa'] = forecast['yhat']
            forecast['yhat'] = forecast['yhat'] * self.poblacion / self.tasa_por
            forecast['yhat_lower'] = forecast['yhat_lower'] * self.poblacion / self.tasa_por
            forecast['yhat_upper'] = forecast['yhat_upper'] * self.poblacion / self.tasa_por

        return forecast

    def run(self) -> pd.DataFrame:
        self.load()
        return self.predict()
