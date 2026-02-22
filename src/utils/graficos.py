# src/utils/graficos.py
import os
from typing import Optional

import matplotlib.dates as mdates
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
        self.conf_paleta_padecimiento = conf['PALETTE_PADECIMIENTO']
        self.conf_covid = conf['COVID']

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


    def serie_tiempo(self,df:pd.DataFrame ,padecimiento: str, agrupamiento_sexo: bool = True, agrupamiento_entidad: bool = False) -> Optional[str]:

        ancho = 16
        alto = 4

        plt.figure(figsize=(ancho,alto))

        if agrupamiento_sexo and not agrupamiento_entidad:

            serie_tiempo = df.groupby("Fecha")[["incrementos_hombres", "incrementos_mujeres"]].sum()

            plt.plot(serie_tiempo.index,serie_tiempo['incrementos_hombres'],
                 linewidth=1.2, alpha=0.8, color=self.conf_paleta_sexo["Hombres"], label="Hombres")
            plt.plot(serie_tiempo.index,serie_tiempo['incrementos_mujeres'],
                 linewidth=1.2, alpha=0.8, color=self.conf_paleta_sexo["Mujeres"], label="Mujeres")

        if not agrupamiento_sexo and agrupamiento_entidad:
            regiones = "region_salud_mental" # Parametrizar !!!!!!

            serie_tiempo = (
                df.groupby(["Fecha",regiones])[["incrementos_hombres", "incrementos_mujeres"]]
                .sum()
                .assign(incrementos_totales=lambda g: g["incrementos_hombres"] + g["incrementos_mujeres"])
                .reset_index()
            )

            for region, datos in serie_tiempo.groupby(regiones):
                plt.plot(
                    datos['Fecha'],
                    datos["incrementos_totales"],
                    linewidth=1.2,
                    alpha=0.8,
                    label=region
                )


        try:
            covid_start = pd.Timestamp("2020-03-01")
            covid_end = pd.Timestamp("2021-06-01")
            plt.axvspan(covid_start, covid_end, alpha=0.1, color="red", label="Covid")
        except Exception:
            pass

        plt.xlabel("Fecha")
        plt.ylabel("Incrementos semanales")
        plt.title(f"Evolución semanal nacional de {padecimiento} ({regiones})")
        plt.legend(fontsize=10)
        plt.tight_layout()
        plt.grid(True,color="gray", alpha=0.3, linestyle="--",linewidth=0.5)

        return self._guardar_figura(f"serie_tiempo_{padecimiento}.png")


    def graficar_pronostico(
        self,
        forecast: pd.DataFrame,
        serie: pd.DataFrame,
        titulo: str,
        padecimiento: str,
        nombre_archivo: str,
        metricas: Optional[dict] = None,
    ) -> str:
        """Gráfico de pronóstico estilo publicación IMSS con observaciones reales,
        banda de intervalo, franja COVID-19, outliers IQR y ficha técnica.

        Args:
            forecast:        DataFrame Prophet con ds, yhat, yhat_lower, yhat_upper.
            serie:           DataFrame con columnas ds (datetime) e y (observaciones).
            titulo:          Título del gráfico (formato: "Padecimiento · Nivel · Modo").
            padecimiento:    Nombre normalizado (Depresion / Parkinson / Alzheimer).
            nombre_archivo:  Nombre del PNG sin extensión.
            metricas:        Dict con mase, rmse, confianza del modelo (opcional).
        """
        # ── Preparación de datos ─────────────────────────────────────────
        forecast = forecast.dropna(subset=["ds", "yhat", "yhat_lower", "yhat_upper"]).copy()
        serie = serie.dropna(subset=["ds", "y"]).copy()
        y = serie["y"]
        Q1, Q3 = y.quantile(0.25), y.quantile(0.75)
        IQR = Q3 - Q1
        out_mask = (y < Q1 - 1.5 * IQR) | (y > Q3 + 1.5 * IQR)
        outliers = serie[out_mask]
        fecha_max_datos = serie["ds"].max()
        fecha_max_fc = forecast["ds"].max()

        # ── Paleta de colores ────────────────────────────────────────────
        pal = self.conf_paleta_padecimiento.get(
            padecimiento,
            {"c1": self.conf_paleta["burgundy"], "cl": "#D4758B"},
        )
        c_obs = self.conf_paleta["teal"]
        c_fc = pal["c1"]
        c_band = pal["cl"]
        c_outlier = "#D84315"               # naranja-rojo apagado (daltonism-friendly)
        c_div = "#555555"
        c_gray = self.conf_paleta["cool_gray"]
        c_text = self.conf_paleta["neutral_black"]

        # ── Parsear título → suptitle + subtitle ─────────────────────────
        parts = titulo.split(" · ")
        pad_display = (parts[0] if parts else padecimiento).replace(
            "Depresion", "Depresión"
        )
        nivel_label = parts[1] if len(parts) > 1 else ""
        modo_label = (parts[2] if len(parts) > 2 else "").capitalize()
        anio_ini = serie["ds"].min().year
        anio_fin = fecha_max_fc.year

        # ── Figura ───────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(18, 7.5))
        fig.subplots_adjust(bottom=0.22, top=0.88, left=0.06, right=0.97)

        # Título principal y subtítulo
        fig.suptitle(
            f"{pad_display} — Pronóstico Semanal",
            fontsize=16, fontweight="bold", color=c_text, y=0.96,
        )
        ax.set_title(
            f"{nivel_label}  ·  {modo_label}  ·  {anio_ini}–{anio_fin}",
            fontsize=11, color=c_gray, pad=10,
        )

        # ── 1. Zona de pronóstico (fondo tenue) ─────────────────────────
        ax.axvspan(
            fecha_max_datos, fecha_max_fc,
            alpha=0.04, color=c_fc, zorder=0,
        )

        # ── 2. Franja COVID-19 ──────────────────────────────────────────
        covid_ini = pd.Timestamp(self.conf_covid["inicio"])
        covid_fin = pd.Timestamp(self.conf_covid["fin"])
        mid_covid = covid_ini + (covid_fin - covid_ini) / 2
        ax.axvspan(covid_ini, covid_fin, alpha=0.07, color="#E53935", zorder=0)
        ax.annotate(
            "COVID-19",
            xy=(covid_ini, 0.97),
            xycoords=("data", "axes fraction"),
            fontsize=9, fontweight="bold", color="#C62828",
            ha="left", va="top", rotation=90,
            bbox=dict(
                boxstyle="round,pad=0.3", fc="white", ec="#C62828",
                alpha=0.92, lw=1.0,
            ),
        )

        # ── 3. Banda de predicción ──────────────────────────────────────
        ax.fill_between(
            forecast["ds"], forecast["yhat_lower"], forecast["yhat_upper"],
            alpha=0.20, color=c_band, zorder=1,
            label="Intervalo 80 % (se amplía con el horizonte)",
        )

        # ── 4. Observaciones reales (puntos pequeños) ────────────────────
        ax.scatter(
            serie["ds"], serie["y"],
            s=15, color=c_obs, alpha=0.45, zorder=3,
            label="Observaciones reales",
        )

        # ── 5. Línea de pronóstico Prophet (dominante) ───────────────────
        ax.plot(
            forecast["ds"], forecast["yhat"],
            color=c_fc, linewidth=2.2, zorder=4,
            label="Pronóstico Prophet (ŷ)",
        )

        # ── 6. Outliers (triángulos con borde blanco) ────────────────────
        if len(outliers) > 0:
            ax.scatter(
                outliers["ds"], outliers["y"],
                marker="^", s=45, color=c_outlier,
                edgecolors="white", linewidths=0.8, zorder=5,
                label=f"Outliers IQR (n = {len(outliers)})",
            )

        # ── 7. Divisor datos históricos / pronóstico ─────────────────────
        ax.axvline(
            fecha_max_datos, color=c_div, ls="--", lw=1.5, alpha=0.7, zorder=6,
        )
        ax.annotate(
            "← Datos históricos ",
            xy=(fecha_max_datos, 0.96),
            xycoords=("data", "axes fraction"),
            fontsize=9.5, fontweight="semibold", color=c_div,
            ha="right", va="top",
        )
        ax.annotate(
            " Pronóstico →",
            xy=(fecha_max_datos, 0.96),
            xycoords=("data", "axes fraction"),
            fontsize=9.5, fontweight="semibold", color=c_fc,
            ha="left", va="top",
        )

        # ── 8. Zona CV: último fold de prueba (banda visible) ────────────
        fecha_corte = pd.Timestamp(conf["FECHA_CORTE_ENTRENAMIENTO"])
        test_weeks = conf.get("TEST_SIZE", 53)
        fecha_cv_inicio = fecha_corte - pd.Timedelta(weeks=test_weeks)

        ax.axvspan(
            fecha_cv_inicio, fecha_corte,
            alpha=0.08, color=c_gray, zorder=0,
        )
        ax.axvline(
            fecha_cv_inicio, color=c_gray, ls=":", lw=1.2, alpha=0.6, zorder=6,
        )
        ax.annotate(
            "← Entrenamiento",
            xy=(fecha_cv_inicio, 0.88),
            xycoords=("data", "axes fraction"),
            fontsize=8.5, fontweight="semibold", color=c_gray,
            ha="right", va="top",
        )
        ax.annotate(
            "Prueba CV →",
            xy=(fecha_cv_inicio, 0.88),
            xycoords=("data", "axes fraction"),
            fontsize=8.5, fontweight="semibold", color=c_gray,
            ha="left", va="top",
        )

        # ── Formato de ejes ──────────────────────────────────────────────
        ax.set_xlabel("")
        ax.set_ylabel("Incrementos semanales", fontsize=11, color=c_text)
        ax.set_ylim(bottom=0)
        ax.yaxis.grid(True, alpha=0.25, color=c_gray, linestyle="-", linewidth=0.5)
        ax.xaxis.grid(False)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(axis="both", labelsize=10, colors=c_text)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            ax.spines[spine].set_color(c_gray)
            ax.spines[spine].set_linewidth(0.5)

        # ── Leyenda horizontal (debajo del gráfico) ──────────────────────
        handles, labels = ax.get_legend_handles_labels()
        fig.legend(
            handles, labels,
            loc="lower center", bbox_to_anchor=(0.5, 0.10),
            ncol=len(handles), fontsize=9,
            framealpha=0.90, fancybox=True, edgecolor="#ddd",
            borderpad=0.6, handletextpad=0.5, columnspacing=1.5,
        )

        # ── Ficha técnica (métricas del modelo) ──────────────────────────
        if metricas:
            mase_v = metricas.get("mase")
            rmse_v = metricas.get("rmse")
            confianza = metricas.get("confianza", "normal")

            es_fallback = metricas.get("es_fallback", False)
            modelo_usado = metricas.get("modelo_usado", "")

            partes_m = ["Prophet (Meta/Facebook)", "IC 80 %"]
            if mase_v is not None and mase_v < 100:
                interp = "supera naive" if mase_v < 1 else "no supera naive"
                partes_m.append(f"MASE: {mase_v:.2f} ({interp})")
            if rmse_v is not None and rmse_v < 100:
                partes_m.append(f"RMSE: {rmse_v:.4f}")
            if es_fallback:
                # Extraer nombre de región del .pkl usado
                region = ""
                if "region_" in modelo_usado:
                    region = modelo_usado.split("region_")[1].rsplit("_", 1)[0]
                    region = region.replace("_", " ").replace("-", "/")
                partes_m.append(
                    f"Modelo regional ({region})"
                    if region else "Modelo regional de respaldo"
                )
            elif confianza == "normal":
                partes_m.append("Modelo estatal propio")

            fig.text(
                0.5, 0.03,
                "  ·  ".join(partes_m),
                ha="center", va="center", fontsize=9,
                color=c_text, fontstyle="italic",
                bbox=dict(
                    boxstyle="round,pad=0.5", fc="#F5F5F5", ec="#ddd",
                    alpha=0.9, lw=0.5,
                ),
            )

        # ── Guardar ──────────────────────────────────────────────────────
        ruta = os.path.join(self.carpeta_salida, f"{nombre_archivo}.png")
        fig.savefig(ruta, dpi=150, facecolor="white", edgecolor="none")
        plt.close(fig)
        return ruta
