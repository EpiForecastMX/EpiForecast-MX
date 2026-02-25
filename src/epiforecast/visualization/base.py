"""Base visualization helpers: charts, forecast plots, and IMSS styling."""

# src/utils/graficos.py
from abc import ABC
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
import seaborn as sns

from epiforecast.utils.config import conf


class GraficosHelper(ABC):
    def __init__(self, carpeta_salida: str, numero_top_columnas: int) -> None:
        self.carpeta_salida = carpeta_salida
        self.numero_top_columnas = numero_top_columnas
        self.conf_paleta = conf["IMSS_COLORS"]
        self.conf_paleta_secuencial = conf["PALETTE_MAIN"]
        self.conf_paleta_sexo = conf["PALETTE_SEXO"]
        self.conf_paleta_padecimiento = conf["PALETTE_PADECIMIENTO"]
        self.conf_covid = conf["COVID"]

        # Aplicar rcParams IMSS globalmente (excluye savefig.* — se manejan en _guardar_figura)
        self._dpi: int = int(conf.get("matplotlib_rcParams", {}).get("savefig.dpi", 150))
        _rc = {
            k: v
            for k, v in conf.get("matplotlib_rcParams", {}).items()
            if not k.startswith("savefig.")
        }
        mpl.rcParams.update(_rc)

    # ---------- Helpers internos ---------- #

    def _guardar_figura(self, fig: plt.Figure, nombre: str) -> str:
        """Guarda la figura con configuración IMSS y cierra el objeto."""
        ruta = os.path.join(self.carpeta_salida, nombre)
        fig.tight_layout()
        fig.savefig(ruta, dpi=self._dpi, facecolor="white", edgecolor="none", bbox_inches="tight")
        plt.close(fig)
        return ruta

    def _aplicar_estilo_ax(self, ax: plt.Axes) -> None:
        """Estilo minimalista IMSS: sin espinas sup/der, grid horizontal suave."""
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            ax.spines[spine].set_color(self.conf_paleta["cool_gray"])
            ax.spines[spine].set_linewidth(0.6)
        ax.yaxis.grid(
            True, alpha=0.25, color=self.conf_paleta["cool_gray"], linestyle="--", linewidth=0.5
        )
        ax.xaxis.grid(False)

    # ---------- Gráficos EDA ---------- #

    def plot_histograma(self, serie: pd.Series, col: str, tono: int = 0) -> str | None:
        """Histograma de densidad con curva KDE y líneas de media/mediana."""
        serie = serie.dropna()
        if serie.empty:
            return None

        color = self.conf_paleta_secuencial[tono % len(self.conf_paleta_secuencial)]
        fig, ax = plt.subplots(figsize=(10, 5))

        ax.hist(
            serie, bins=50, density=True, alpha=0.65, color=color, edgecolor="white", linewidth=0.5
        )

        try:
            kde = gaussian_kde(serie)
            x_vals = np.linspace(serie.min(), serie.max(), 300)
            ax.plot(x_vals, kde(x_vals), color=self.conf_paleta["neutral_black"], linewidth=2)
        except Exception:
            pass

        ax.axvline(
            serie.mean(),
            color=self.conf_paleta["burgundy"],
            linestyle="--",
            linewidth=1.5,
            label=f"Media: {serie.mean():,.1f}",
        )
        ax.axvline(
            serie.median(),
            color=self.conf_paleta["teal"],
            linestyle="-.",
            linewidth=1.5,
            label=f"Mediana: {serie.median():,.1f}",
        )

        ax.set_title(f"Distribución de {col}", fontsize=13, fontweight="bold")
        ax.set_xlabel(col, fontsize=11)
        ax.set_ylabel("Densidad", fontsize=11)
        ax.legend(fontsize=9, loc="upper right", framealpha=0.7)
        self._aplicar_estilo_ax(ax)

        return self._guardar_figura(fig, f"hist_{col}.png")

    def plot_categorica_barras(self, serie: pd.Series, col: str) -> str | None:
        """Barras horizontales con porcentajes y paleta IMSS secuencial."""
        serie = serie.dropna()
        if serie.empty:
            return None

        conteos = serie.value_counts().head(self.numero_top_columnas)
        top_real = len(conteos)
        porcentajes: pd.Series = (conteos / conteos.sum() * 100).round(1)

        etiquetas = [
            str(lbl)[:30] + ("…" if len(str(lbl)) > 30 else "") for lbl in porcentajes.index
        ]

        fig, ax = plt.subplots(figsize=(10, max(4, top_real * 0.45)))

        n_paleta = len(self.conf_paleta_secuencial)
        colores = (self.conf_paleta_secuencial * -(-top_real // n_paleta))[:top_real]
        bars = ax.barh(
            etiquetas,
            porcentajes.values,  # type: ignore[arg-type]
            color=colores,
            edgecolor="white",
            height=0.65,
        )

        for bar, v in zip(bars, porcentajes.values):
            ax.text(
                v + 0.3,
                bar.get_y() + bar.get_height() / 2,
                f"{v:.1f}%",
                va="center",
                ha="left",
                fontsize=9,
                color=self.conf_paleta["neutral_black"],
            )

        ax.set_title(f"Top {top_real} — {col}", fontsize=13, fontweight="bold")
        ax.set_xlabel("Porcentaje (%)", fontsize=10)
        ax.invert_yaxis()
        self._aplicar_estilo_ax(ax)
        # Para barras horizontales: grid vertical, no horizontal
        ax.yaxis.grid(False)
        ax.xaxis.grid(True, alpha=0.25, linestyle="--", color=self.conf_paleta["cool_gray"])

        return self._guardar_figura(fig, f"barras_{col}.png")

    def plot_violin(self, df: pd.DataFrame, col: str, padecimiento: str) -> str | None:
        """Violín por año con cuartiles visibles y paleta IMSS."""
        if col not in df.columns or df[col].dropna().empty:
            return None

        anios = sorted(df["Anio"].unique())
        n = len(anios)
        n_paleta = len(self.conf_paleta_secuencial)
        colores = (self.conf_paleta_secuencial * -(-n // n_paleta))[:n]

        fig, ax = plt.subplots(figsize=(14, 6))
        sns.violinplot(
            x="Anio",
            y=col,
            hue="Anio",
            data=df,
            palette=colores,
            inner="quart",
            cut=0,
            legend=False,
            ax=ax,
        )

        sexo_label = col.replace("Acumulado_", "").capitalize()
        ax.set_title(
            f"Distribución semanal de casos — {padecimiento} ({sexo_label})",
            fontsize=13,
            fontweight="bold",
        )
        ax.set_xlabel("Año", fontsize=11)
        ax.set_ylabel("Casos acumulados", fontsize=11)
        ax.tick_params(axis="x", rotation=45)
        self._aplicar_estilo_ax(ax)

        return self._guardar_figura(fig, f"violin_{col}.png")

    def plot_correlacion(self, df: pd.DataFrame) -> str | None:
        """Heatmap triangular inferior de correlación de Pearson."""
        num = df.dropna()
        if num.shape[1] < 2:
            return None

        corr = num.corr()
        fig, ax = plt.subplots(figsize=(9, 7))
        # k=1 → oculta triángulo superior estricto; diagonal (auto-correlación) queda visible
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)

        sns.heatmap(
            corr,
            mask=mask,
            annot=True,
            fmt=".2f",
            cmap="RdYlGn",
            center=0,
            vmin=-1,
            vmax=1,
            square=True,
            linewidths=0.8,
            cbar_kws={"label": "Correlación de Pearson", "shrink": 0.8},
            annot_kws={"size": 10, "fontweight": "bold"},
            ax=ax,
        )
        ax.set_title("Matriz de correlación", fontsize=13, fontweight="bold")
        ax.tick_params(axis="x", rotation=45)

        return self._guardar_figura(fig, "correlacion.png")

    # ---------- Gráficos de análisis complementarios ---------- #

    def plot_box(self, serie: pd.DataFrame, col: str, col_comparativa: str) -> str | None:
        if col == col_comparativa:
            return None

        fig, ax = plt.subplots()
        sns.boxplot(
            x=col,
            y=col_comparativa,
            data=serie,
            palette="Set2",
            hue=col,
            legend=False,
            notch=True,
            fliersize=1,
            boxprops=dict(alpha=0.7),
            ax=ax,
        )
        ax.set_title(f"Distribución de {col_comparativa} por {col}")
        ax.set_xlabel("")
        ax.tick_params(axis="x", rotation=90)
        self._aplicar_estilo_ax(ax)

        return self._guardar_figura(fig, f"box_{col}.png")

    def serie_tiempo(
        self,
        df: pd.DataFrame,
        padecimiento: str,
        agrupamiento_sexo: bool = True,
        agrupamiento_entidad: bool = False,
    ) -> str | None:
        from epiforecast.visualization.series_plots import serie_tiempo as _serie_tiempo

        return _serie_tiempo(
            df,
            padecimiento,
            self.carpeta_salida,
            self._dpi,
            self.conf_paleta,
            self.conf_paleta_sexo,
            agrupamiento_sexo,
            agrupamiento_entidad,
        )

    def graficar_pronostico(
        self,
        forecast: pd.DataFrame,
        serie: pd.DataFrame,
        titulo: str,
        padecimiento: str,
        nombre_archivo: str,
        metricas: dict | None = None,
    ) -> str:
        """Gráfico de pronóstico IMSS. Delegado a forecast_chart.graficar_pronostico."""
        from epiforecast.visualization.forecast_chart import (
            graficar_pronostico as _graficar_pronostico,
        )

        return _graficar_pronostico(
            forecast,
            serie,
            titulo,
            padecimiento,
            nombre_archivo,
            self.carpeta_salida,
            self.conf_paleta,
            self.conf_paleta_padecimiento,
            self.conf_covid,
            metricas,
        )
