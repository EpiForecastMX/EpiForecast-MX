# src/utils/graficos.py
import os
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from scipy.stats import gaussian_kde
from src.configuraciones.config_params import conf


class GraficosHelper:
    def __init__(self, carpeta_salida: str, numero_top_columnas: int):
        self.carpeta_salida = carpeta_salida
        self.numero_top_columnas = numero_top_columnas
        self.conf_paleta = conf['IMSS_COLORS']
        self.conf_paleta_secuencial = conf['PALETTE_MAIN']
        self.conf_paleta_sexo = conf['PALETTE_SEXO']

    def _guardar_figura(self, nombre: str) -> str:
        ruta = os.path.join(self.carpeta_salida, nombre)
        plt.tight_layout()
        plt.savefig(ruta, dpi=150)
        plt.close()
        return ruta

    def plot_histograma(self, serie, col: str,tono: int = 0) -> Optional[str]:
        
        serie = serie.dropna()
        if serie.empty:
            return None

        plt.hist(
            serie,
            bins=50,
            density=True,
            alpha=0.6,
            color=self.conf_paleta_secuencial[tono],
            edgecolor="white",
            linewidth=0.5
        )

        try:
            kde = gaussian_kde(serie)
            x_vals = np.linspace(serie.min(), serie.max(), 300)
            plt.plot(x_vals, kde(x_vals), color=self.conf_paleta['neutral_black'], linewidth=2)
        except Exception:
            pass

        plt.axvline(serie.mean(),
                    color=self.conf_paleta['burgundy'],
                    linestyle="--",
                    linewidth=1.2, 
                    label=f"Media: {serie.mean():,.0f}"
                    )
        
        plt.axvline(serie.median(),
                    color=self.conf_paleta['teal'],
                    linestyle="-.",
                    linewidth=1.2, 
                    label=f"Mediana: {serie.median():,.0f}"
                    )
        

        plt.title(f"Histograma de {col}")
        plt.legend(fontsize=8, loc="upper right")
        plt.ylabel("Densidad")

        return self._guardar_figura(f"hist_{col}.png")

    def plot_categorica_barras(self, serie, col: str) -> Optional[str]:
        
        serie = serie.dropna()
        if serie.empty:
            return None

        conteos = serie.value_counts().head(self.numero_top_columnas)
        top_real = min(self.numero_top_columnas, len(serie.value_counts()))

        porcentajes = (conteos / conteos.sum() * 100).round(1)

        porcentajes_recortados = porcentajes.copy()
        porcentajes_recortados.index = [
            str(lbl)[:25] + ("..." if len(str(lbl)) > 25 else "")
            for lbl in porcentajes_recortados.index
        ]

        ax = sns.barplot(
            x=porcentajes_recortados.values,
            y=porcentajes_recortados.index,
            hue=porcentajes_recortados.index,
            dodge=False,
            palette="muted",
            legend=False
        )

        titulo = f"Distribución porcentual de {col} - Top {top_real}"
        ax.set_title(titulo)
        ax.set_xlabel(None)
        ax.set_ylabel(None)

        plt.xticks(rotation=45, ha='right')

        for i, v in enumerate(porcentajes_recortados.values):
            ax.text(v + 0.5, i, f"{v}%", va="center")

        return self._guardar_figura(f"barras_{col}.png")

    def plot_violin(self, df, col, padecimiento) -> Optional[str]:
        
        plt.figure(figsize=(12,6))
        sns.violinplot(
            x="Anio",
            y=col,
            hue="Anio",
            data=df,
            palette="viridis",
            inner=None,
            cut=0
        )

        plt.title(f"Distribución de Casos por Semana - {padecimiento} ({col})")
        plt.xlabel(None)
        plt.ylabel("Casos por semana")
        plt.xticks(rotation=45)
        plt.legend().remove()

        return self._guardar_figura(f"violin_{col}.png")

    def plot_correlacion(self, df) -> Optional[str]:
        num = df.dropna()
        corr = num.corr()

        if num.shape[1] < 2: return None
        fig, ax = plt.subplots(figsize=(9, 7))
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
        sns.heatmap(
            corr, mask=mask, annot=True, fmt=".2f", cmap="RdYlGn",
            center=0, vmin=-1, vmax=1, square=True, linewidths=0.8,
            cbar_kws={"label": "Correlacion de Pearson", "shrink": 0.8},
            annot_kws={"size": 10, "fontweight": "bold"}, ax=ax
        )
        plt.title("Matriz de correlación")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()

        return self._guardar_figura("correlacion.png")
    
    def plot_box(self, serie, col: str, col_comparativa: str) -> Optional[str]:

        if col == col_comparativa:
            return None

        sns.boxplot(x=col, y=col_comparativa,
                    data=serie,
                    palette="Set2",
                    hue=col,
                    legend=False,
                    notch=True,
                    fliersize=1,
                    boxprops=dict(alpha=0.7))
        plt.title(f"Distribución de Valor por {col}")
        plt.xlabel("")
        plt.xticks(rotation=90)

        return self._guardar_figura(f"box_{col}.png")
    
    
    def serie_tiempo(self,df:pd.DataFrame ,padecimiento: str) -> Optional[str]:

        serie_tiempo = df.groupby("Fecha")[["incrementos_hombres", "incrementos_mujeres"]].sum()
        plt.figure(figsize=(16,4))
        
        plt.plot(serie_tiempo.index,serie_tiempo['incrementos_hombres'],
                 linewidth=1.2, alpha=0.8, color=self.conf_paleta_sexo["Hombres"], label="Hombres")
        plt.plot(serie_tiempo.index,serie_tiempo['incrementos_mujeres'],
                 linewidth=1.2, alpha=0.8, color=self.conf_paleta_sexo["Mujeres"], label="Mujeres")
        
        try:
            covid_start = pd.Timestamp("2020-03-01")
            covid_end = pd.Timestamp("2021-06-01")
            plt.axvspan(covid_start, covid_end, alpha=0.1, color="red", label="Covid")
        except Exception:
            pass

        plt.xlabel("Fecha")
        plt.ylabel("Incrementos semanales")
        plt.title(f"Evolución semanal nacional de {padecimiento}")
        plt.legend(fontsize=10)
        plt.tight_layout()
        plt.grid(True,color="gray", alpha=0.3, linestyle="--",linewidth=0.5)

        return self._guardar_figura(f"serie_tiempo_{padecimiento}.png")

        

