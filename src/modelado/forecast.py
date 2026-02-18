# src/modelado/forecast.py
import pickle
import re
import unicodedata
from pathlib import Path

import pandas as pd

from src.configuraciones.config_params import conf, logger
from src.utils import directory_manager
from src.utils.graficos import GraficosHelper


def _normalizar(s: str) -> str:
    """Elimina acentos y normaliza espacios para comparación tolerante."""
    sin_acento = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_acento).strip().lower()


def generar_graficos_pronostico() -> None:
    """Genera una gráfica de pronóstico por modelo desde all_forecast.csv.

    Estructura de salida:
        forecast/
          {padecimiento}/
            {entidad | Nacional}/
              {nombre_archivo}.png

    Lee el CSV consolidado de predicciones, cruza con data_inegi para obtener
    las observaciones reales y llama a GraficosHelper.graficar_pronostico()
    por cada combinación única (meta_padecimiento, meta_entidad, meta_modo).
    """
    forecast_file = Path(conf["data"]["forecast"])
    data_inegi_file = Path(conf["data"]["data_inegi"])
    forecast_root = Path(conf["paths"]["forecast"])

    # mapeo_columnas: {col_df: modo} → invertido: {modo: col_df}
    mapeo_inv = {v: k for k, v in conf["mapeo_columnas"].items()}
    agrupador = "Entidad" if conf["padecimiento"]["modelado_estados"] else "region_salud_mental"

    df_forecast = pd.read_csv(forecast_file)
    df_forecast["ds"] = pd.to_datetime(df_forecast["ds"], errors="coerce")
    df_forecast = df_forecast.dropna(subset=["ds"])
    df_data = pd.read_csv(data_inegi_file)
    df_data["Fecha"] = pd.to_datetime(df_data["Fecha"], errors="coerce")
    df_data = df_data.dropna(subset=["Fecha"])

    # GraficosHelper: carpeta_salida se actualiza por iteración
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

        # Carpeta: forecast/{padecimiento}/{entidad | Nacional}/
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

        # Serie real desde data_inegi
        col_sexo = mapeo_inv.get(modo)
        if col_sexo is None:
            logger.warning("Modo '{}' sin mapeo de columna, omitiendo gráfico.", modo)
            continue

        df_pad = df_data[df_data["Padecimiento"] == padecimiento]
        if entidad:
            entidad_norm = _normalizar(entidad)
            df_pad = df_pad[df_pad[agrupador].apply(_normalizar) == entidad_norm]

        serie = (
            df_pad.groupby("Fecha")[col_sexo]
            .sum()
            .rename_axis("ds")
            .reset_index()
            .rename(columns={col_sexo: "y"})
        )
        serie["ds"] = pd.to_datetime(serie["ds"], errors="coerce")
        serie = serie.dropna(subset=["ds"])

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

    def load(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {self.model_path}")

        with open(self.model_path, "rb") as f:
            self.model = pickle.load(f)

    def predict(self) -> pd.DataFrame:
        future = self.model.make_future_dataframe(periods=self.periodo, freq="W-MON")
        return self.model.predict(future)

    def run(self) -> pd.DataFrame:
        self.load()
        return self.predict()
