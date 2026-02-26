"""Exploratory Data Analysis plots and statistical summaries."""

# src/datos/EDA.py
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger
import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf
from epiforecast.visualization.base import GraficosHelper


@dataclass
class SeccionNota:
    """Sección estructurada del bloque de notas del reporte PDF.

    Cada proceso que construya un ReportData puede agregar una o varias
    SeccionNota con la información que considere relevante:

    Ejemplo::

        nota = SeccionNota(
            titulo="Proceso de limpieza",
            texto="Se eliminaron filas con nulos en columnas críticas.",
            parametros={"Filas antes": "10,000", "Filas después": "9,500"},
        )
        report_data.secciones_notas.append(nota)
    """

    titulo: str
    texto: str | None = None  # párrafo descriptivo libre
    parametros: dict[str, str] | None = None  # se renderiza como tabla clave-valor
    tabla: pd.DataFrame | None = None  # se renderiza como tabla de datos


@dataclass
class ReportData:
    titulo: str
    subtitulo: str | None
    fuente_datos: str | None
    resumen_general: dict[str, str]
    resumen_datos: pd.DataFrame | None
    resumen_datos_nulos: pd.DataFrame | None
    estadisticas_numericas: pd.DataFrame | None
    estadisticas_categoricas: pd.DataFrame | None
    tablas_categoricas: dict[str, pd.DataFrame]
    figuras: list[str] = field(default_factory=list)
    notas: str | None = None  # texto libre (compatibilidad)
    secciones_notas: list[SeccionNota] = field(default_factory=list)  # secciones estructuradas


class EDAReportBuilder:
    """Genera insumos de un reporte EDA a partir de un DataFrame."""

    def __init__(
        self, df: pd.DataFrame, fuente_datos: str, opciones: dict, config: dict | None = None
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

    # ------------------ Resúmenes ------------------
    def resumen_general(self) -> dict[str, str]:
        """Genera diccionario con metadatos generales del DataFrame: filas, columnas, nulos."""
        logger.debug("Generando resumen general de los datos...")

        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
        fuente = self.fuente_datos if self.fuente_datos else "Desconocida"
        filas = f"{len(self.df):,}"
        columnas = f"{self.df.shape[1]:,}"
        porcentaje_nulos = f"{self.df.isna().mean().mean() * 100:.2f}%"
        columnas_numericas = len(self.opciones_reporte["COLS_NUMERICAS"])
        columnas_categoricas = len(self.opciones_reporte["COLS_CATEGORICAS"])
        otros_columnas = self.df.shape[1] - (columnas_numericas + columnas_categoricas)

        logger.debug(
            f"Resumen del DataFrame : fecha= {fecha_actual} | fuente= {fuente} | "
            f"filas= {filas} | columnas= {columnas} | porcentaje_nulos= {porcentaje_nulos}"
        )
        logger.debug(
            f"Tipos de columnas : numéricas= {columnas_numericas} | categóricas= {columnas_categoricas} | otras= {otros_columnas}"
        )

        return {
            "Fecha de EDA": fecha_actual,
            "Padecimiento": self.opciones_reporte["filtro_padecimiento"],
            "Fuente": fuente,
            "Filas": filas,
            "Columnas": columnas,
            "Columnas numéricas": f"{columnas_numericas}",
            "Columnas categóricas": f"{columnas_categoricas}",
            "Otras columnas": f"{otros_columnas}",
            "Porcentaje de nulos": porcentaje_nulos,
        }

    # ------------------ Resumen de valores únicos ------------------
    def resumen_unicos(self) -> pd.DataFrame:
        """Genera DataFrame con conteo de valores únicos y tipo por columna."""

        logger.debug("Generando resumen de valores únicos por columna...")

        df_unicos = (
            self.df.nunique(dropna=True)
            .to_frame("Valores únicos")
            .assign(Tipo=self.df.dtypes.astype(str))
            .query("`Valores únicos` > 0")
            .sort_values("Valores únicos", ascending=False)
        )

        logger.debug(
            f"Dataframe de valores únicos generado | filas = {len(df_unicos):,} | columnas = {df_unicos.shape[1]:,} | formato de salida = {type(df_unicos)}"
        )
        return df_unicos

    # ------------------ Resumen de valores nulos ------------------
    def resumen_nulos(self) -> pd.DataFrame | None:
        """Genera DataFrame con conteo de valores nulos por columna, o None si no hay nulos."""

        logger.debug("Generando resumen de valores nulos por columna...")

        df_nulos = (
            self.df.isna()
            .sum()
            .to_frame("Nulos")
            .assign(Tipo=self.df.dtypes.astype(str))
            .query("Nulos > 0")
            .sort_values("Nulos", ascending=False)
        )

        logger.debug(
            f"Dataframe de valores nulos generado | filas = {len(df_nulos):,} | columnas = {df_nulos.shape[1]:,} | formato de salida = {type(df_nulos)}"
        )
        return df_nulos if not df_nulos.empty else None

    # ------------------ Estadísticas de valores numéricos ------------------
    def estadisticas_numericas(self) -> pd.DataFrame | None:
        """Genera tabla describe() transpuesta de columnas numéricas, o None si no hay."""
        logger.debug("Generando estadísticas de columnas numéricas...")

        # Seleccionar solo columnas numéricas
        num = self.df.select_dtypes(include="number")

        if num.empty:
            return None

        estadisticas_numericas = (
            num.describe()
            .T.rename(
                columns={
                    "count": "conteo",
                    "mean": "media",
                    "std": "desv_est",
                    "min": "mín",
                    "25%": "p25",
                    "50%": "p50",
                    "75%": "p75",
                    "max": "máx",
                }
            )
            .round(3)
        )

        logger.debug(
            f"Dataframe de estadísticas numéricas generado | filas = {len(estadisticas_numericas):,} | columnas = {estadisticas_numericas.shape[1]:,}"
            f" | columnas consideradas = {num.shape[1]} de {self.df.shape[1]} | formato de salida = {type(estadisticas_numericas)}"
        )
        return estadisticas_numericas

    # ------------------ Estadísticas de valores categoricos ------------------
    def estadisticas_categoricas(self) -> pd.DataFrame | None:
        """Genera tabla con conteo, moda y frecuencia de columnas categóricas, o None."""
        logger.debug("Generando estadísticas de columnas categóricas...")

        # Seleccionar solo columnas categóricas de tipo object o category
        cat = self.opciones_reporte["COLS_CATEGORICAS"]

        if not cat:
            return None

        # Crear el resumen de estadísticas categóricas
        resumen = [
            {
                "columna": f"col_{i}",
                "conteo": s.size,
                "valores_únicos": s.nunique(),
                "moda": s.mode().iloc[0] if not s.mode().empty else "N/A",
                "freq_moda": s.value_counts().iloc[0],
                "%_moda": round(s.value_counts().iloc[0] / s.size * 100, 2),
            }
            for i, serie in enumerate(cat)
            for s in [pd.Series(serie)]  # envolvemos cada lista en Series
            if not s.empty
        ]

        logger.debug(
            f"Dataframe de estadísticas categóricas generado | filas = {len(resumen):,} | columnas = {len(resumen[0].keys())} "
            f" | columnas consideradas = {len(cat)} de {self.df.shape[1]} | formato de salida = {type(resumen)}"
        )
        return pd.DataFrame(resumen).set_index("columna")

    def tablas_categoricas(self) -> dict[str, pd.DataFrame]:
        """Genera tablas de frecuencia para cada columna categórica configurada."""

        logger.debug("Generando tablas de frecuencias para columnas categóricas...")
        cat = self.opciones_reporte["COLS_CATEGORICAS"]
        resultados = {}

        n = getattr(self, "numero_top_columnas", 10)

        for col in cat:
            serie = self.df[col].fillna("N/A")  # tomar la columna del DataFrame
            vc = serie.value_counts(dropna=False)

            logger.debug(f"Columna: {col}, mostrando top {n} categorías")

            # limitar al top n
            df_out = vc.head(n).to_frame("frecuencia")
            df_out.index.name = col

            resultados[col] = df_out

        return resultados

    # ------------------ Gráficos ------------------
    def plot_histograma(self, col: str, tono: int) -> str | None:
        """Genera histograma de densidad con KDE para una columna numérica."""

        return self.graficos_helper.plot_histograma(self.df[col], col, tono)

    def plot_categorica_barras(self, col: str) -> str | None:
        """Genera gráfico de barras horizontales con porcentajes para una columna categórica."""

        return self.graficos_helper.plot_categorica_barras(self.df[col], col)

    def plot_violin(self, sexo, padecimiento) -> str | None:
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
            resumen_general=self.resumen_general(),
            resumen_datos=self.resumen_unicos(),
            resumen_datos_nulos=self.resumen_nulos(),
            estadisticas_numericas=self.estadisticas_numericas(),
            estadisticas_categoricas=self.estadisticas_categoricas(),
            tablas_categoricas=self.tablas_categoricas(),
            figuras=figuras,
            notas=self.notas,
        )
