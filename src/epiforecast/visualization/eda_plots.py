"""Exploratory Data Analysis plots and statistical summaries."""

# src/datos/EDA.py
from typing import Any

from loguru import logger
import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf
from epiforecast.visualization.base import GraficosHelper
from epiforecast.visualization.eda_summaries import (
    estadisticas_categoricas,
    estadisticas_numericas,
    resumen_general,
    resumen_nulos,
    resumen_unicos,
    tablas_categoricas,
)
from epiforecast.visualization.eda_types import ReportData, SeccionNota

__all__ = ["EDAReportBuilder", "ReportData", "SeccionNota"]


class EDAReportBuilder:
    """Genera insumos de un reporte EDA a partir de un DataFrame.

    Responsabilidad: orquestar gráficos y ensamblar ``ReportData``.
    Los resúmenes estadísticos se delegan a :mod:`eda_summaries`.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        fuente_datos: str,
        opciones: dict[str, Any],
        config: dict[str, Any] | None = None,
    ):
        """Inicializa el constructor de reportes EDA.

        Args:
            df:           DataFrame de datos epidemiológicos a analizar.
            fuente_datos: Descripción de la fuente de datos (para metadatos del reporte).
            opciones:     Dict con configuración del reporte (titulo, max_cols, violin, etc.).
            config:       Dict de configuración (default: conf global de YAML).
        """
        _conf = config if config is not None else conf
        self.df = df.copy()
        self.df_raw = df.copy()
        self.opciones_reporte = opciones
        self.carpeta_salida = _conf["paths"]["figures"]
        self.fuente_datos = fuente_datos
        self.numero_top_columnas = opciones["max_cols"]
        self.genera_violin = opciones["violin"]
        self.graficos_helper = GraficosHelper(self.carpeta_salida, self.numero_top_columnas)
        self.notas = None

        directory_manager.asegurar_ruta(self.carpeta_salida)
        directory_manager.limpia_carpeta(self.carpeta_salida)

        logger.debug(
            f"El reporte se generará con título: {self.opciones_reporte['titulo_reporte']}"
        )
        logger.debug(f"El subtítulo del reporte es: {self.opciones_reporte['subtitulo_reporte']}")
        logger.debug(f"La fuente de datos es: {self.fuente_datos}")
        logger.debug(f"Número máximo de columnas a mostrar: {self.numero_top_columnas}")
        logger.debug(f"Las imágenes se guardarán en: {self.carpeta_salida}")

    # ------------------ Gráficos ------------------

    def plot_histograma(self, col: str, tono: int) -> str | None:
        """Genera histograma de densidad con KDE para una columna numérica."""
        return self.graficos_helper.plot_histograma(self.df[col], col, tono)

    def plot_categorica_barras(self, col: str) -> str | None:
        """Genera gráfico de barras horizontales con porcentajes para una columna categórica."""
        return self.graficos_helper.plot_categorica_barras(self.df[col], col)

    def plot_violin(self, sexo: str, padecimiento: str) -> str | None:
        """Genera gráfico de violín por año para una columna de sexo."""
        return self.graficos_helper.plot_violin(self.df, sexo, padecimiento)

    def plot_correlacion(self) -> str | None:
        """Genera heatmap de correlación para columnas numéricas configuradas."""
        return self.graficos_helper.plot_correlacion(
            self.df[self.opciones_reporte["COLS_NUMERICAS"]]
        )

    # ------------------ Ejecución ------------------

    def run(self) -> ReportData:
        """Ejecuta el pipeline completo de EDA y retorna un objeto ReportData."""
        figuras = []

        for tono, col in enumerate(self.opciones_reporte["COLS_NUMERICAS"]):
            logger.debug(f"Generando histograma para la columna numérica: '{col}'")
            ruta = self.plot_histograma(col, tono)
            if ruta:
                figuras.append(ruta)

        for col in self.opciones_reporte["COLS_CATEGORICAS"]:
            logger.debug(f"Generando gráfico de barras para la columna categórica: '{col}'")
            ruta = self.plot_categorica_barras(col)
            if ruta:
                figuras.append(ruta)

        if self.genera_violin:
            for sexo in ["Acumulado_hombres", "Acumulado_mujeres"]:
                logger.debug(f"Generando gráfico de violín para la columna numérica: '{sexo}'")
                ruta = self.plot_violin(sexo, self.opciones_reporte["filtro_padecimiento"])
                if ruta:
                    figuras.append(ruta)

        corr = self.plot_correlacion()
        logger.debug("Generando matriz de correlación para columnas numéricas.")
        if corr:
            figuras.append(corr)

        return ReportData(
            titulo=self.opciones_reporte["titulo_reporte"],
            subtitulo=self.opciones_reporte["subtitulo_reporte"],
            fuente_datos=self.fuente_datos,
            resumen_general=resumen_general(self.df, self.fuente_datos, self.opciones_reporte),
            resumen_datos=resumen_unicos(self.df),
            resumen_datos_nulos=resumen_nulos(self.df),
            estadisticas_numericas=estadisticas_numericas(self.df),
            estadisticas_categoricas=estadisticas_categoricas(self.opciones_reporte),
            tablas_categoricas=tablas_categoricas(
                self.df, self.opciones_reporte, self.numero_top_columnas
            ),
            figuras=figuras,
            notas=self.notas,
        )
