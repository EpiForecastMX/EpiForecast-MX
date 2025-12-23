
# eda/eda.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from datetime import datetime
from loguru import logger

from src.configuraciones.config_params import conf

# ----- Objeto de datos para el reporte -----

@dataclass
class ReportData:
    titulo: str
    subtitulo: Optional[str]
    fuente_datos: Optional[str]

    # Resumen general
    resumen_general: Dict[str, str]

    # Estadísticas y tablas
    estadisticas_numericas: Optional[pd.DataFrame]  # describe() o similar
    tablas_categoricas: Dict[str, pd.DataFrame]     # top-K por columna categórica

    # Paths de figuras generadas por el EDA
    figuras: List[str] = field(default_factory=list)

    # Notas u observaciones
    notas: Optional[str] = None


# ----- Constructor del reporte desde un DataFrame -----

class EDAReportBuilder:
    """
    Construye los insumos de un reporte a partir de un DataFrame:
    - Resumen general (filas, columnas, tipos, nulos)
    - Estadísticas descriptivas numéricas
    - Tablas de top categorías por columnas categóricas
    - Figuras (histogramas, correlación, series temporales si aplica)
    """
    def __init__(
        self,
        df: pd.DataFrame,
        titulo: str = "Análisis Exploratorio de Datos",
        subtitulo: Optional[str] = None,
        fuente_datos: Optional[str] = None,
        carpeta_salida: str = "output",
        max_cols_numericas: int = 8,
        max_categorias_tabla: int = 10,
        estilo_fuente_figuras: str = "DejaVu Sans"
    ):
        self.df = df.copy()
        self.titulo = titulo
        self.subtitulo = subtitulo
        self.fuente_datos = fuente_datos

        self.carpeta_salida = carpeta_salida
    #*******cambiar la carpet de figuras por la de reports/figures**********#
        self.carpeta_figuras = os.path.join(carpeta_salida, "figuras")
        os.makedirs(self.carpeta_figuras, exist_ok=True)

        self.max_cols_numericas = max_cols_numericas
        self.max_categorias_tabla = max_categorias_tabla
        self.estilo_fuente_figuras = estilo_fuente_figuras

        # Configurar estilo de matplotlib (acentos, legibilidad)
        plt.rcParams['font.family'] = self.estilo_fuente_figuras
        plt.rcParams['axes.titlesize'] = 12
        plt.rcParams['axes.labelsize'] = 10

    def _resumen_general(self) -> Dict[str, str]:
        tipos = self.df.dtypes.astype(str)
        nulos = self.df.isna().sum()
        resumen = {
            "Fuente": self.fuente_datos,
            "Filas": f"{len(self.df):,}",
            "Columnas": f"{self.df.shape[1]:,}",
            "Porcentaje de nulos": f"{(self.df.isna().mean().mean() * 100):.2f}%",
            "Fecha de EDA": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        # Un pequeño resumen de tipos
        tipos_contados = tipos.value_counts()
        tipos_texto = ", ".join([f"{t}: {c}" for t, c in tipos_contados.items()])
        resumen["Tipos de datos"] = tipos_texto

#*************** crear una tabla para las columnas con nulos ***********************#
        top_nulos = nulos.sort_values(ascending=False).head(5)
        resumen["Top columnas con nulos"] = "; ".join([f"{col} ({val})" for col, val in top_nulos.items()])
        return resumen

    def _estadisticas_numericas(self) -> Optional[pd.DataFrame]:
        num = self.df.select_dtypes(include=['number'])
        if num.empty:
            return None
        # Limitar a max_cols_numericas para hacer el PDF manejable
        cols = num.columns.tolist()[:self.max_cols_numericas]
        desc = num[cols].describe().T
        desc = desc.rename(columns={
            "count": "conteo", "mean": "media", "std": "desv_est",
            "min": "mín", "25%": "p25", "50%": "p50", "75%": "p75", "max": "máx"
        })
        return desc.round(3)

    def _tablas_categoricas(self) -> Dict[str, pd.DataFrame]:
        cat = self.df.select_dtypes(include=['object', 'category'])
        tablas = {}
        for col in cat.columns:
            vc = cat[col].fillna("N/A").value_counts(dropna=False).head(self.max_categorias_tabla)
            tablas[col] = vc.rename("frecuencia").to_frame()
        return tablas

    def _plot_histogramas(self) -> List[str]:
        num = self.df.select_dtypes(include=['number'])
        rutas = []
        if num.empty:
            return rutas
        cols = num.columns.tolist()[:self.max_cols_numericas]
        for col in cols:
            plt.figure(figsize=(6, 4))
            ax = plt.gca()
            ax.hist(num[col].dropna(), bins=20, color="#2a9d8f", edgecolor="white")
            ax.set_title(f"Histograma de {col}")
            ax.set_xlabel(col)
            ax.set_ylabel("Frecuencia")
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ruta = os.path.join(self.carpeta_figuras, f"hist_{col}.png")
            plt.tight_layout()
            plt.savefig(ruta, dpi=140)
            plt.close()
            rutas.append(ruta)
        return rutas

    def _plot_correlacion(self) -> Optional[str]:
        num = self.df.select_dtypes(include=['number'])
        if num.shape[1] < 2:
            return None
        corr = num.corr(numeric_only=True)
        plt.figure(figsize=(6, 5))
        im = plt.imshow(corr, cmap="viridis", aspect="auto")
        plt.colorbar(im, fraction=0.046, pad=0.04)
        plt.xticks(ticks=range(len(corr.columns)), labels=corr.columns, rotation=45, ha="right")
        plt.yticks(ticks=range(len(corr.index)), labels=corr.index)
        plt.title("Matriz de correlación (numérica)")
        plt.tight_layout()
        ruta = os.path.join(self.carpeta_figuras, "correlacion.png")
        plt.savefig(ruta, dpi=150)
        plt.close()
        return ruta

    def _plot_serie_temporal(self) -> Optional[str]:
        """
        Si existe una columna de fecha (dtype datetime64) y una numérica,
        grafica una serie temporal agregada.
        """
        fechas = self.df.select_dtypes(include=['datetime64[ns]', 'datetime64[ns, UTC]'])
        num = self.df.select_dtypes(include=['number'])
        if fechas.shape[1] < 1 or num.shape[1] < 1:
            return None

        # Usar la primera fecha y primera numérica
        fcol = fechas.columns[0]
        ncol = num.columns[0]
        tmp = self.df[[fcol, ncol]].dropna().copy()
        if tmp.empty:
            return None

        # Agregar por periodo (semanal por defecto)
        tmp = tmp.sort_values(fcol)
        tmp['__periodo__'] = tmp[fcol].dt.to_period('W').dt.start_time
        serie = tmp.groupby('__periodo__')[ncol].mean()

        plt.figure(figsize=(7, 3.8))
        plt.plot(serie.index, serie.values, color="#e76f51", linewidth=2)
        plt.title(f"Serie temporal (promedio semanal de {ncol})")
        plt.xlabel("Periodo")
        plt.ylabel(ncol)
        plt.grid(alpha=0.3)
        plt.tight_layout()
        ruta = os.path.join(self.carpeta_figuras, "serie_temporal.png")
        plt.savefig(ruta, dpi=150)
        plt.close()
        return ruta

    def _filtrar_padecimiento(self, padecimiento: str) -> None:
        """
        Filtra el DataFrame para incluir solo filas con el padecimiento especificado.
        """
        #logger.info(f"Filtrando datos para el padecimiento: {padecimiento}")
        if 'Padecimiento' in self.df.columns:

            filtrado = self.df[self.df['Padecimiento'].astype(str).str.contains(padecimiento, case=False, na=False)].copy()
            self.df = filtrado
        
        



    def run(self) -> ReportData:
        """
        Ejecuta el EDA completo y retorna el ReportData a consumir por el generador de PDF.
        """

        padecimiento = conf["reporte_EDA"]["filtro_padecimiento"]

        self._filtrar_padecimiento(padecimiento)
        resumen = self._resumen_general()
        est_num = self._estadisticas_numericas()
        tablas_cat = self._tablas_categoricas()

        figuras = []
        figuras += self._plot_histogramas()
        corr_path = self._plot_correlacion()

        if corr_path:
            figuras.append(corr_path)
        serie_path = self._plot_serie_temporal()
        if serie_path:
            figuras.append(serie_path)

        return ReportData(
            titulo=self.titulo,
            subtitulo=self.subtitulo,
            fuente_datos=self.fuente_datos,
            resumen_general=resumen,
            estadisticas_numericas=est_num,
            tablas_categoricas=tablas_cat,
            figuras=figuras,
            notas="Generado automáticamente por EDAReportBuilder."
        )
