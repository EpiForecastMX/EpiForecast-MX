from dataclasses import dataclass, field
from typing import List, Dict, Optional
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import MaxNLocator
from datetime import datetime
from loguru import logger

from src.configuraciones.config_params import conf
from src.utils import DirectoryManager
from scipy.stats import gaussian_kde
import numpy as np


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
    
    histograma: List[str] = field(default_factory=list)
    barras_categoricas: List[str] = field(default_factory=list)

    notas: Optional[str] = None


class EDAReportBuilder:
    """Genera insumos de un reporte EDA a partir de un DataFrame."""

    def __init__(self, df: pd.DataFrame, titulo: str, subtitulo: str, fuente_datos: str,
                 numero_cols_numericas: int = 8, numero_cols_categoricas: int = 10):
        self.df = df.copy()
        self.titulo, self.subtitulo, self.fuente_datos = titulo, subtitulo, fuente_datos
        self.numero_cols_numericas, self.numero_cols_categoricas = numero_cols_numericas, numero_cols_categoricas

        self.carpeta_salida = conf["paths"]["figures"]
        DirectoryManager.asegurar_ruta(self.carpeta_salida)
        logger.info(f"Las imágenes se guardarán en: {self.carpeta_salida}")

        plt.rcParams.update({
            'font.family': conf["reporte_EDA"]["estilo_fuente"],
            'axes.titlesize': 12,
            'axes.labelsize': 10
        })

    def _resumen_general(self) -> Dict[str, str]:

        return {
            "Fecha de EDA": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Fuente": self.fuente_datos,
            "Filas": f"{len(self.df):,}",
            "Columnas": f"{self.df.shape[1]:,}",
            "Porcentaje de nulos": f"{self.df.isna().mean().mean() * 100:.2f}%",
        }
    
    def _resumen_datos_unicos(self) -> pd.DataFrame:
        """
        Genera un resumen con la cantidad de valores únicos por columna.
        """
        tipos = self.df.dtypes.astype(str)
        unicos = self.df.nunique(dropna=True)

        df_info = pd.DataFrame({
            "Tipo de dato": tipos,
            "Valores únicos": unicos
        })

        df_info = df_info[df_info["Valores únicos"] > 0]

        return df_info.sort_values(by="Valores únicos", ascending=False)

    
    def _resumen_datos_nulos(self) -> pd.DataFrame:
        """
        Genera un resumen con la cantidad de valores nulos por columna.
        """
        tipos = self.df.dtypes.astype(str)
        nulos = self.df.isna().sum()
        df_info = pd.DataFrame({
            "Tipo de dato": tipos,
            "Nulos": nulos
        })

        df_info = df_info[df_info["Nulos"] > 0]

        return df_info.sort_values(by="Nulos", ascending=False)


    def _estadisticas_numericas(self) -> Optional[pd.DataFrame]:
        num = self.df.select_dtypes(include='number')
        if num.empty: return None
        desc = num.iloc[:, :self.numero_cols_numericas].describe().T.rename(columns={
            "count": "conteo", "mean": "media", "std": "desv_est",
            "min": "mín", "25%": "p25", "50%": "p50", "75%": "p75", "max": "máx"
        })
        return desc.round(3)
    
    def _estadisticas_categoricas(self) -> Optional[pd.DataFrame]:
        """
        Genera un resumen estadístico para variables categóricas:
        - Conteo total
        - Valores únicos
        - Moda (valor más frecuente)
        - Frecuencia de la moda
        - % de la moda sobre el total
        """
        cat = self.df.select_dtypes(include=['object', 'category'])
        if cat.empty:
            return None

        resumen = []
        for col in cat.columns:
            serie = cat[col].dropna()
            conteo = len(serie)
            unicos = serie.nunique()
            moda = serie.mode().iloc[0] if not serie.mode().empty else "N/A"
            freq_moda = serie.value_counts().iloc[0] if not serie.value_counts().empty else 0
            porcentaje_moda = (freq_moda / conteo * 100) if conteo > 0 else 0

            resumen.append({
                "columna": col,
                "conteo": conteo,
                "valores_únicos": unicos,
                "moda": moda,
                "freq_moda": freq_moda,
                "%_moda": round(porcentaje_moda, 2)
            })

        df_resumen = pd.DataFrame(resumen).set_index("columna")
        return df_resumen




    def _tablas_categoricas(self) -> Dict[str, pd.DataFrame]:
        cat = self.df.select_dtypes(include=['object', 'category'])
        tablas = {}
        for col in cat.columns:
            tabla = (
                cat[col]
                .fillna("N/A")
                .value_counts()
                .head(self.numero_cols_categoricas)
                .to_frame("frecuencia")
            )
            tabla.index.name = col 
            tablas[col] = tabla
        return tablas


    def _guardar_figura(self, nombre: str) -> str:
        ruta = os.path.join(self.carpeta_salida, nombre)
        plt.tight_layout()
        plt.savefig(ruta, dpi=150)
        plt.close()
        return ruta

    def _plot_histogramas(self) -> List[str]:
        rutas = []
        for col in self.df.select_dtypes(include='number'):
            serie = self.df[col].dropna()

            if serie.empty:
                continue

            plt.figure(figsize=(6, 4))
            plt.hist(serie, bins=20, color="#2a9d8f", edgecolor="white", alpha=0.6, density=True)

            # Línea de tendencia (KDE)
            kde = gaussian_kde(serie)
            x_vals = np.linspace(serie.min(), serie.max(), 200)
            plt.plot(x_vals, kde(x_vals), color="red", linewidth=2, label="Tendencia")

            plt.title(f"Histograma de {col}")
            plt.ylabel("Densidad")
            plt.xlabel("")
            plt.legend()

            rutas.append(self._guardar_figura(f"hist_{col}.png"))
        return rutas
    

    def _plot_categoricas(self) -> List[str]:
        rutas: List[str] = []
        cat = self.df.select_dtypes(include=['object', 'category', 'bool'])

        top_k = 20  # ✅ Top máximo a mostrar (20)

        for col in cat.columns:
            serie = self.df[col]

            # Convertir booleanos a texto para evitar rarezas
            if pd.api.types.is_bool_dtype(serie):
                serie = serie.astype('object')

            # Nulos a "N/A"
            serie = serie.fillna("N/A")

            # Conteos ordenados desc
            conteos = serie.value_counts()

            # Tomar solo el Top-20 (SIN agrupar "Otros")
            if len(conteos) > top_k:
                conteos = conteos.head(top_k)

            # --- Porcentajes ---
            # Porcentaje sobre el total del Top-20 mostrado:
            total_top = int(conteos.sum())
            if total_top == 0:
                continue

            porcentajes = (conteos / total_top * 100).round(1)

            # --- Graficar ---
            plt.figure(figsize=(9, 5))
            plt.bar(porcentajes.index, porcentajes.values,
                    color="#2a9d8f", alpha=0.85, edgecolor="white")

            plt.title(f"Distribución de {col} (Top {min(top_k, len(porcentajes))})")
            plt.ylabel("Porcentaje (%)")
            plt.xlabel("")

            # Rotar etiquetas si son largas o demasiadas
            if len(porcentajes) > 12 or max(map(lambda s: len(str(s)), porcentajes.index)) > 10:
                plt.xticks(rotation=45, ha="right")

            # Etiquetas encima de cada barra con '%'
            ymax = porcentajes.max()
            for i, v in enumerate(porcentajes.values):
                plt.text(i, v + ymax * 0.01, f"{v}%", ha="center", fontsize=9)

            plt.tight_layout()
            rutas.append(self._guardar_figura(f"barras_{col}.png"))

        return rutas


    def _plot_correlacion(self) -> Optional[str]:
        # Seleccionar solo columnas numéricas
        num = self.df.select_dtypes(include='number')

        # 👇 Filtrar columnas que tienen al menos un valor no nulo
        num = num.dropna(axis=1, how="all")

        # Si quedan menos de 2 columnas válidas, no tiene sentido graficar
        if num.shape[1] < 2:
            return None

        plt.figure(figsize=(6, 5))
        im = plt.imshow(num.corr(numeric_only=True), cmap="viridis", aspect="auto")
        plt.colorbar(im, fraction=0.046, pad=0.04)
        plt.xticks(range(len(num.columns)), num.columns, rotation=45, ha="right")
        plt.yticks(range(len(num.columns)), num.columns)
        plt.title("Matriz de correlación (numérica)")

        return self._guardar_figura("correlacion.png")
    

    def _plot_box_plot(self) -> Optional[str]:

        top_k = 20  # ✅ Top máximo a mostrar (20)
        tipo: str = "violin"
        rutas: List[str] = []

        if self.df is None or self.df.empty:
            return rutas

        # Detectar numéricas y categóricas
        cols_num = list(self.df.select_dtypes(include="number").columns)
        cols_cat = list(self.df.select_dtypes(include=["object", "category", "bool"]).columns)

        if not cols_num or not cols_cat:
            return rutas  # no hay columnas para graficar

        sns.set_theme(style="whitegrid")

        # Iterar sobre todas las combinaciones categórica-numérica
        for cat_col in cols_cat:
            cat_series = self.df[cat_col].copy()
            if pd.api.types.is_bool_dtype(cat_series):
                cat_series = cat_series.astype("object")
            cat_series = cat_series.fillna("N/A")

            # Limitar al Top-k categorías por frecuencia
            conteo_cat = cat_series.value_counts()
            categorias_top = list(conteo_cat.head(top_k).index)

            # Subconjunto del DF con solo las categorías top
            df_plot = self.df.copy()
            df_plot[cat_col] = cat_series
            df_plot = df_plot[df_plot[cat_col].isin(categorias_top)]

            if df_plot.empty:
                continue

            for col_num in cols_num:
                serie_num = df_plot[col_num].dropna()
                if serie_num.empty:
                    continue

                plt.figure(figsize=(10, 6))

                # Construir el gráfico según 'tipo'
                if tipo.lower() == "violin":
                    ax = sns.violinplot(
                        x=cat_col,
                        y=col_num,
                        data=df_plot,
                        inner="box",
                        palette="Set2",
                        cut=0,
                        linewidth=1,
                    )
                    titulo_tipo = "Violín (inner=box)"
                else:
                    ax = sns.boxplot(
                        x=cat_col,
                        y=col_num,
                        data=df_plot,
                        palette="Set2",
                        showfliers=True,
                    )
                    titulo_tipo = "Caja (Boxplot)"

                # Títulos y etiquetas
                ax.set_title(f"{titulo_tipo}: {col_num} por {cat_col} (Top {len(categorias_top)})", fontsize=12)
                ax.set_xlabel("")  # sin etiqueta en eje X
                ax.set_ylabel(col_num)

                # Rotar etiquetas del eje X si son largas/muchas
                ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")

                plt.tight_layout()

                # Guardar figura
                nombre_archivo = f"{tipo.lower()}_{col_num}_por_{cat_col}.png"
                rutas.append(self._guardar_figura(nombre_archivo))

        return rutas





    def _plot_serie_temporal(self) -> Optional[str]:
        fechas = self.df.select_dtypes(include='datetime64[ns]')
        num = self.df.select_dtypes(include='number')
        if fechas.empty or num.empty: return None

        tmp = self.df[[fechas.columns[0], num.columns[0]]].dropna().sort_values(fechas.columns[0])
        if tmp.empty: return None

        tmp['periodo'] = tmp[fechas.columns[0]].dt.to_period('W').dt.start_time
        serie = tmp.groupby('periodo')[num.columns[0]].mean()

        plt.figure(figsize=(7, 3.8))
        plt.plot(serie.index, serie.values, color="#e76f51", linewidth=2)
        plt.title(f"Serie temporal (promedio semanal de {num.columns[0]})")
        plt.xlabel("Periodo"); plt.ylabel(num.columns[0]); plt.grid(alpha=0.3)
        return self._guardar_figura("serie_temporal.png")

    def _filtrar_padecimiento(self, padecimiento: str) -> None:
        if 'Padecimiento' in self.df.columns:
            self.df = self.df[self.df['Padecimiento'].astype(str).str.contains(padecimiento, case=False, na=False)]

    def run(self) -> ReportData:
        self._filtrar_padecimiento(conf["reporte_EDA"]["filtro_padecimiento"])
        
        plot_histogramas = self._plot_histogramas()
        plot_barras_categoricas = self._plot_categoricas()
        plot_violin = self._plot_box_plot()

        for plot_func in [self._plot_correlacion, self._plot_serie_temporal]:
            ruta = plot_func()
            if ruta: plot_histogramas.append(ruta)

            return ReportData(
            titulo=self.titulo,
            subtitulo=self.subtitulo,
            fuente_datos=self.fuente_datos,
            resumen_general=self._resumen_general(),
            resumen_datos=self._resumen_datos_unicos(),
            resumen_datos_nulos=self._resumen_datos_nulos(),
            estadisticas_numericas=self._estadisticas_numericas(),
            estadisticas_categoricas=self._estadisticas_categoricas(),
            tablas_categoricas=self._tablas_categoricas(),
            histograma = plot_histogramas,
            barras_categoricas= plot_barras_categoricas,
            notas="Generado automáticamente por EDAReportBuilder."
        )