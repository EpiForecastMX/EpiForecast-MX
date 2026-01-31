# src/utils/graficos.py
import os
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from scipy.stats import gaussian_kde


class GraficosHelper:
    def __init__(self, carpeta_salida: str, numero_top_columnas: int):
        self.carpeta_salida = carpeta_salida
        self.numero_top_columnas = numero_top_columnas

    def _guardar_figura(self, nombre: str) -> str:
        ruta = os.path.join(self.carpeta_salida, nombre)
        plt.tight_layout()
        plt.savefig(ruta, dpi=150)
        plt.close()
        return ruta

    def plot_histograma(self, serie, col: str) -> Optional[str]:
        serie = serie.dropna()
        if serie.empty:
            return None

        plt.hist(
            serie,
            bins=20,
            color="#2a9d8f",
            edgecolor="white",
            alpha=0.6,
            density=True
        )

        kde = gaussian_kde(serie)
        x_vals = np.linspace(serie.min(), serie.max(), 200)
        plt.plot(x_vals, kde(x_vals), color="red", linewidth=2)
        plt.title(f"Histograma de {col}")
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

    def plot_correlacion(self, serie) -> Optional[str]:
        num = serie.select_dtypes(include='number').dropna(axis=1, how="all")
        if num.shape[1] < 2: return None
        sns.heatmap(num.corr(numeric_only=True), cmap="viridis", annot=True)
        plt.title("Matriz de correlación")
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