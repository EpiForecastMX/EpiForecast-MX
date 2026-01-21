# src/datos/EDA.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
from loguru import logger

from src.configuraciones.config_params import conf
from src.utils import directory_manager
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

    def __init__(self,
                 df: pd.DataFrame,
                 fuente_datos: str,
                 opciones: dict):
        
        
        self.df = df.copy()
        self.df_raw = df.copy()
        self.carpeta_salida = conf["paths"]["figures"]
        self.titulo = opciones['titulo_reporte']
        self.subtitulo = opciones['subtitulo_reporte']
        self.fuente_datos = fuente_datos
        self.numero_top_columnas = opciones['max_cols']
        self.genera_boxplot = opciones['boxplot']
        self.genera_violin = opciones['violin']
        self.campo_comparativa = opciones['bp_comparativa'] 
        self.graficos_helper = GraficosHelper(self.carpeta_salida, self.numero_top_columnas)
        self.notas = None

        directory_manager.asegurar_ruta(self.carpeta_salida)
        directory_manager.limpia_carpeta(self.carpeta_salida)

        logger.debug(f"El reporte se generará con título: {self.titulo}")
        logger.debug(f"El subtítulo del reporte es: {self.subtitulo}")
        logger.debug(f"La fuente de datos es: {self.fuente_datos}")
        logger.debug(f"Número máximo de columnas a mostrar: {self.numero_top_columnas}")
        logger.info(f"Las imágenes se guardarán en: {self.carpeta_salida}")

    # ------------------ Filtrar padecimiento ------------------

    def _filtrar_padecimiento(self, padecimiento: str) -> None:

        if "Padecimiento" not in self.df.columns:
            logger.error("No se puede filtrar: la columna 'Padecimiento' no existe en el DataFrame.")
            return
        
        if self.df.empty:
            logger.error("No se puede filtrar, DataFrame vacío.")
            return

        logger.info(f"Filtrando datos por padecimiento: '{padecimiento}'")
        
        total_antes = len(self.df)

        if "Padecimiento" in self.df.columns and padecimiento:
            self.df = self.df[self.df["Padecimiento"]
                            .astype(str)
                            .str.contains(padecimiento, case=False, na=False)]
            
        total_despues = len(self.df)

        
        if total_despues == 0:
            logger.warning(f"No se encontraron registros relacionados con el padecimiento: '{padecimiento}'.")
            self.df = self.df_raw.copy()
            
            padecimientos = self.df["Padecimiento"].dropna().unique().tolist()
            lista_padecimientos = "<br/>".join(f"<b>{p}</b>" for p in padecimientos)
            
            self.notas = (
                        f"No se identificaron registros asociados al padecimiento <b>{padecimiento}</b>.<br/>"
                        "Se generó el reporte con los siguientes padecimientos detectados:<br/>"
                        f"{lista_padecimientos}"
            )

        else:
            logger.info(
            f"Filtrado aplicado: {total_despues} de {total_antes} registros corresponden a '{padecimiento}'."
            )
            
            self.notas = (
                f"El reporte se generó con registros asociados al padecimiento <b>{padecimiento}</b>."
                f"Del total de <strong>{total_antes:,}</strong> registros disponibles en el conjunto de datos, "
                f"se identificaron <strong>{total_despues:,}</strong> registros que coinciden con el padecimiento "
                f"<strong>{padecimiento}</strong>. "
                "Estos registros han sido utilizados para generar el análisis y la información presentada en este reporte."
            )



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
            "Padecimiento": conf["reporte_EDA"]["filtro_padecimiento"],
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
           }).round(3)
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
                      f" | columnas consideradas = {cat.shape[1]} de {self.df.shape[1]} | formato de salida = {type(resumen)}")
        return pd.DataFrame(resumen).set_index("columna")



    def tablas_categoricas(self) -> Dict[str, pd.DataFrame]:

        logger.debug("Generando tablas de frecuencias para columnas categóricas...")
        cat = self.df.select_dtypes(include=['object', 'category'])
        resultados: Dict[str, pd.DataFrame] = {}

        for col in cat.columns:
            serie = cat[col]
            vc = serie.fillna("N/A").value_counts(dropna=False)
            n = int(self.numero_top_columnas) if hasattr(self, "numero_top_columnas") else 10

            logger.debug(f"Generando tabla de frecuencias top para la columna: {col}, Número de categorías a mostrar: {n}")

            if n <= 0:
                resultados[col] = pd.DataFrame(columns=["frecuencia", "Observaciones"])
                continue

            if len(vc) <= n:
                df_out = vc.to_frame("frecuencia")

            else:
                
                logger.debug(f"La columna '{col}' tiene más de {n} categorías únicas. Generando tabla combinada de top máximos y mínimos.")
                half = n // 2
                if half == 0:
                    half = 1

                top_max = vc.sort_values(ascending=False).head(half)

                restantes = vc.drop(top_max.index, errors='ignore')
                top_min = restantes.sort_values(ascending=True).head(n - half)

                df_max = top_max.to_frame("frecuencia")
                df_max["Observaciones"] = "Valores más frecuentes"

                df_min = top_min.to_frame("frecuencia")
                df_min["Observaciones"] = "Valores menos frecuentes"

                separador = pd.DataFrame(
                    {"frecuencia": "...", "Observaciones": ["..."]},
                    index=["..."]
                )

                df_min = df_min.sort_values(by="frecuencia", ascending=False)
                df_out = pd.concat([df_max, separador, df_min])
            
            df_out.index.name = col
            resultados[col] = df_out

        return resultados

    # ------------------ Gráficos ------------------
    def plot_histograma(self, col: str) -> Optional[str]:
        return self.graficos_helper.plot_histograma(self.df[col], col)

    def plot_categorica_barras(self, col: str) -> Optional[str]:
        return self.graficos_helper.plot_categorica_barras(self.df[col], col)
    
    def plot_violin(self, col: str) -> Optional[str]:
        return self.graficos_helper.plot_violin(self.df[col], col)
    
    def plot_box(self, col: str, col_comparativa: str) -> Optional[str]:
        return self.graficos_helper.plot_box(self.df, col, col_comparativa)
    
    def plot_correlacion(self) -> Optional[str]:
        return self.graficos_helper.plot_correlacion(self.df)


    # ------------------ Ejecución ------------------
    def run(self) -> ReportData:
        figuras = []
        padecimiento = conf["reporte_EDA"]["filtro_padecimiento"]

        self._filtrar_padecimiento(padecimiento)

        for col in self.df.select_dtypes(include='number').columns:
            logger.debug(f"Generando histograma para la columna numérica: '{col}'")
            ruta = self.plot_histograma(col)
            if ruta: figuras.append(ruta)

        for col in self.df.select_dtypes(include=['object', 'category']).columns:
            logger.debug(f"Generando gráfico de barras para la columna categórica: '{col}'")
            ruta = self.plot_categorica_barras(col)
            if ruta: figuras.append(ruta)

        if self.genera_violin:
            for col in self.df.columns:
                logger.debug(f"Generando gráfico de violín para la columna numérica: '{col}'")
                ruta = self.plot_violin(col)
                if ruta: figuras.append(ruta)
        
        if self.genera_boxplot:
            for col in self.df.columns:
                logger.debug(f"Creando gráfico de caja para la columna '{col}' con referencia en '{self.campo_comparativa}'")
                ruta = self.plot_box(col,self.campo_comparativa)
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
            notas=self.notas
        )