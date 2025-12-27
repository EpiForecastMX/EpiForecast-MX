from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
from loguru import logger

from src.configuraciones.config_params import conf
from src.utils import DirectoryManager
from src.utils.graficos import GraficosHelper


@dataclass
class ReportData:
    titulo: str
    subtitulo: Optional[str]
    fuente_datos: Optional[str]
    resumen_general: Dict[str, str]
    resumen_datos: Optional[pd.DataFrame]
    resumen_datos_nulos: Optional[pd.DataFrame]
    estadisticas_numericas: Optional[pd.DataFrame]
    estadisticas_categoricas: Optional[pd.DataFrame]
    tablas_categoricas: Dict[str, pd.DataFrame]
    figuras: List[str] = field(default_factory=list)
    notas: Optional[str] = None


class EDAReportBuilder:
    """Genera insumos de un reporte EDA a partir de un DataFrame."""

    def __init__(self, df: pd.DataFrame, titulo: str, subtitulo: str, fuente_datos: str,
                 numero_top_columnas: int = 8):
        
        self.df = df.copy()
        self.titulo, self.subtitulo, self.fuente_datos = titulo, subtitulo, fuente_datos
        self.numero_top_columnas = numero_top_columnas
        self.carpeta_salida = conf["paths"]["figures"]
        self.graficos_helper = GraficosHelper(self.carpeta_salida, self.numero_top_columnas)

        DirectoryManager.asegurar_ruta(self.carpeta_salida)
        DirectoryManager.limpia_carpeta(self.carpeta_salida)
        logger.debug(f"El reporte se generará con título: {self.titulo}")
        logger.debug(f"El subtítulo del reporte es: {self.subtitulo}")
        logger.debug(f"La fuente de datos es: {self.fuente_datos}")
        logger.debug(f"Número máximo de columnas a mostrar: {self.numero_top_columnas}")
        logger.info(f"Las imágenes se guardarán en: {self.carpeta_salida}")

        plt.rcParams.update({
            'font.family': conf["reporte_EDA"]["estilo_fuente"],
            'axes.titlesize': 12,
            'axes.labelsize': 10
        })

    # ------------------ Filtrar padecimiento ------------------

    def _filtrar_padecimiento(self, padecimiento: str) -> None:
        
        logger.info(f"Filtrando datos por padecimiento: {padecimiento}")
        if "Padecimiento" in self.df.columns and padecimiento:
            self.df = self.df[self.df["Padecimiento"]
                            .astype(str)
                            .str.contains(padecimiento, case=False, na=False)]

    # ------------------ Resúmenes ------------------
    def resumen_general(self) -> Dict[str, str]:

        logger.debug("Generando resumen general de los datos...")

        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
        fuente = self.fuente_datos if self.fuente_datos else "Desconocida"
        filas = f"{len(self.df):,}"
        columnas = f"{self.df.shape[1]:,}"
        porcentaje_nulos = f"{self.df.isna().mean().mean() * 100:.2f}%"
        columnas_numericas = self.df.select_dtypes(include='number').shape[1]
        columnas_categoricas = self.df.select_dtypes(include=['object', 'category']).shape[1]
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

        logger.debug("Generando resumen de valores únicos por columna...")

        df_unicos = self.df.nunique(dropna=True).to_frame("Valores únicos") \
                .assign(Tipo=self.df.dtypes.astype(str)) \
                .query("`Valores únicos` > 0") \
                .sort_values("Valores únicos", ascending=False)

        logger.debug( f"Dataframe de valores únicos generado | filas = {len(df_unicos):,} | columnas = {df_unicos.shape[1]:,} | formato de salida = {type(df_unicos)}")
        return df_unicos


    # ------------------ Resumen de valores nulos ------------------
    def resumen_nulos(self) -> pd.DataFrame:

        logger.debug("Generando resumen de valores nulos por columna...")

        df_nulos = self.df.isna().sum().to_frame("Nulos") \
                .assign(Tipo=self.df.dtypes.astype(str)) \
                .query("Nulos > 0") \
                .sort_values("Nulos", ascending=False)

        logger.debug(f"Dataframe de valores nulos generado | filas = {len(df_nulos):,} | columnas = {df_nulos.shape[1]:,} | formato de salida = {type(df_nulos)}")
        return df_nulos if not df_nulos.empty else None


    # ------------------ Estadísticas de valores numéricos ------------------
    def estadisticas_numericas(self) -> Optional[pd.DataFrame]:

        logger.debug("Generando estadísticas de columnas numéricas...")

        # Seleccionar solo columnas numéricas
        num = self.df.select_dtypes(include='number')
        
        if num.empty: return None

        estadisticas_numericas = (
        num.describe()
           .T
           .rename(columns={
               "count": "conteo", "mean": "media", "std": "desv_est",
               "min": "mín", "25%": "p25", "50%": "p50",
               "75%": "p75", "max": "máx"
           })
           .round(3)
    )

        logger.debug( f"Dataframe de estadísticas numéricas generado | filas = {len(estadisticas_numericas):,} | columnas = {estadisticas_numericas.shape[1]:,}"
                      f" | columnas consideradas = {num.shape[1]} de {self.df.shape[1]} | formato de salida = {type(estadisticas_numericas)}")
        return (estadisticas_numericas)
    

    # ------------------ Estadísticas de valores categoricos ------------------
    def estadisticas_categoricas(self) -> Optional[pd.DataFrame]:
        
        logger.debug("Generando estadísticas de columnas categóricas...")
        
        # Seleccionar solo columnas categóricas de tipo object o category
        cat = self.df.select_dtypes(include=['object', 'category'])

        if cat.empty: return None

        # Crear el resumen de estadísticas categóricas
        resumen = [{
            "columna": col,
            "conteo": serie.size,
            "valores_únicos": serie.nunique(),
            "moda": serie.mode().iloc[0] if not serie.mode().empty else "N/A",
            "freq_moda": serie.value_counts().iloc[0],
            "%_moda": round(serie.value_counts().iloc[0] / serie.size * 100, 2)
        } for col, serie in cat.items() if not serie.empty]

        logger.debug( f"Dataframe de estadísticas categóricas generado | filas = {len(resumen):,} | columnas = {len(resumen[0].keys())} "
                      f" | columnas consideradas = {cat.shape[1]} de {self.df.shape[1]}| formato de salida = {type(resumen)}")
        return pd.DataFrame(resumen).set_index("columna")

    def tablas_categoricas(self) -> Dict[str, pd.DataFrame]:
        cat = self.df.select_dtypes(include=['object', 'category'])
        return {col: serie.fillna("N/A").value_counts().head(self.numero_top_columnas).to_frame("frecuencia")
                for col, serie in cat.items()}

    # ------------------ Gráficos ------------------
    def plot_histograma(self, col: str) -> Optional[str]:
        return self.graficos_helper.plot_histograma(self.df[col], col)

    def plot_categorica_barras(self, col: str) -> Optional[str]:
        return self.graficos_helper.plot_categorica_barras(self.df[col], col)
    
    def plot_violin(self, col: str) -> Optional[str]:
        return self.graficos_helper.plot_violin(self.df[col], col)
    
    def plot_correlacion(self) -> Optional[str]:
        return self.graficos_helper.plot_correlacion(self.df)

    # ------------------ Ejecución ------------------
    def run(self) -> ReportData:
        figuras = []
        padecimiento = conf["reporte_EDA"]["filtro_padecimiento"]

        self._filtrar_padecimiento(padecimiento)

        for col in self.df.select_dtypes(include='number').columns:
            logger.debug(f"Generando histograma para la columna numérica: {col}")
            ruta = self.plot_histograma(col)
            if ruta: figuras.append(ruta)

        for col in self.df.select_dtypes(include=['object', 'category']).columns:
            logger.debug(f"Generando gráfico de barras para la columna categórica: {col}")
            ruta = self.plot_categorica_barras(col)
            if ruta: figuras.append(ruta)
        
        for col in self.df.columns:
            logger.debug(f"Generando gráfico de violín para la columna numérica: {col}")
            ruta = self.plot_violin(col)
            if ruta: figuras.append(ruta)

        corr = self.plot_correlacion()
        logger.debug("Generando matriz de correlación para columnas numéricas.")
        if corr: figuras.append(corr)

        return ReportData(
            titulo=self.titulo,
            subtitulo=self.subtitulo,
            fuente_datos=self.fuente_datos,
            resumen_general=self.resumen_general(),
            resumen_datos=self.resumen_unicos(),
            resumen_datos_nulos=self.resumen_nulos(),
            estadisticas_numericas=self.estadisticas_numericas(),
            estadisticas_categoricas=self.estadisticas_categoricas(),
            tablas_categoricas=self.tablas_categoricas(),
            figuras=figuras,
            notas="Generado automáticamente por EDAReportBuilder."
        )