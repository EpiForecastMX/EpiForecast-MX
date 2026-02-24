# src/utils/graficos.py
import os
from typing import Optional

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import gaussian_kde

from src.configuraciones.config_params import conf


class GraficosHelper:
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
        _rc = {k: v for k, v in conf.get("matplotlib_rcParams", {}).items()
               if not k.startswith("savefig.")}
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
        ax.yaxis.grid(True, alpha=0.25, color=self.conf_paleta["cool_gray"],
                      linestyle="--", linewidth=0.5)
        ax.xaxis.grid(False)

    # ---------- Gráficos EDA ---------- #

    def plot_histograma(self, serie: pd.Series, col: str, tono: int = 0) -> Optional[str]:
        """Histograma de densidad con curva KDE y líneas de media/mediana."""
        serie = serie.dropna()
        if serie.empty:
            return None

        color = self.conf_paleta_secuencial[tono % len(self.conf_paleta_secuencial)]
        fig, ax = plt.subplots(figsize=(10, 5))

        ax.hist(serie, bins=50, density=True, alpha=0.65,
                color=color, edgecolor="white", linewidth=0.5)

        try:
            kde = gaussian_kde(serie)
            x_vals = np.linspace(serie.min(), serie.max(), 300)
            ax.plot(x_vals, kde(x_vals), color=self.conf_paleta["neutral_black"], linewidth=2)
        except Exception:
            pass

        ax.axvline(serie.mean(), color=self.conf_paleta["burgundy"], linestyle="--",
                   linewidth=1.5, label=f"Media: {serie.mean():,.1f}")
        ax.axvline(serie.median(), color=self.conf_paleta["teal"], linestyle="-.",
                   linewidth=1.5, label=f"Mediana: {serie.median():,.1f}")

        ax.set_title(f"Distribución de {col}", fontsize=13, fontweight="bold")
        ax.set_xlabel(col, fontsize=11)
        ax.set_ylabel("Densidad", fontsize=11)
        ax.legend(fontsize=9, loc="upper right", framealpha=0.7)
        self._aplicar_estilo_ax(ax)

        return self._guardar_figura(fig, f"hist_{col}.png")

    def plot_categorica_barras(self, serie: pd.Series, col: str) -> Optional[str]:
        """Barras horizontales con porcentajes y paleta IMSS secuencial."""
        serie = serie.dropna()
        if serie.empty:
            return None

        conteos = serie.value_counts().head(self.numero_top_columnas)
        top_real = len(conteos)
        porcentajes = (conteos / conteos.sum() * 100).round(1)

        etiquetas = [
            str(lbl)[:30] + ("…" if len(str(lbl)) > 30 else "")
            for lbl in porcentajes.index
        ]

        fig, ax = plt.subplots(figsize=(10, max(4, top_real * 0.45)))

        n_paleta = len(self.conf_paleta_secuencial)
        colores = (self.conf_paleta_secuencial * -(-top_real // n_paleta))[:top_real]
        bars = ax.barh(etiquetas, porcentajes.values, color=colores,
                       edgecolor="white", height=0.65)

        for bar, v in zip(bars, porcentajes.values):
            ax.text(v + 0.3, bar.get_y() + bar.get_height() / 2,
                    f"{v:.1f}%", va="center", ha="left", fontsize=9,
                    color=self.conf_paleta["neutral_black"])

        ax.set_title(f"Top {top_real} — {col}", fontsize=13, fontweight="bold")
        ax.set_xlabel("Porcentaje (%)", fontsize=10)
        ax.invert_yaxis()
        self._aplicar_estilo_ax(ax)
        # Para barras horizontales: grid vertical, no horizontal
        ax.yaxis.grid(False)
        ax.xaxis.grid(True, alpha=0.25, linestyle="--",
                      color=self.conf_paleta["cool_gray"])

        return self._guardar_figura(fig, f"barras_{col}.png")

    def plot_violin(self, df: pd.DataFrame, col: str, padecimiento: str) -> Optional[str]:
        """Violín por año con cuartiles visibles y paleta IMSS."""
        if col not in df.columns or df[col].dropna().empty:
            return None

        anios = sorted(df["Anio"].unique())
        n = len(anios)
        n_paleta = len(self.conf_paleta_secuencial)
        colores = (self.conf_paleta_secuencial * -(-n // n_paleta))[:n]

        fig, ax = plt.subplots(figsize=(14, 6))
        sns.violinplot(
            x="Anio", y=col, hue="Anio",
            data=df, palette=colores,
            inner="quart", cut=0, legend=False, ax=ax,
        )

        sexo_label = col.replace("Acumulado_", "").capitalize()
        ax.set_title(f"Distribución semanal de casos — {padecimiento} ({sexo_label})",
                     fontsize=13, fontweight="bold")
        ax.set_xlabel("Año", fontsize=11)
        ax.set_ylabel("Casos acumulados", fontsize=11)
        ax.tick_params(axis="x", rotation=45)
        self._aplicar_estilo_ax(ax)

        return self._guardar_figura(fig, f"violin_{col}.png")

    def plot_correlacion(self, df: pd.DataFrame) -> Optional[str]:
        """Heatmap triangular inferior de correlación de Pearson."""
        num = df.dropna()
        if num.shape[1] < 2:
            return None

        corr = num.corr()
        fig, ax = plt.subplots(figsize=(9, 7))
        # k=1 → oculta triángulo superior estricto; diagonal (auto-correlación) queda visible
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)

        sns.heatmap(
            corr, mask=mask, annot=True, fmt=".2f", cmap="RdYlGn",
            center=0, vmin=-1, vmax=1, square=True, linewidths=0.8,
            cbar_kws={"label": "Correlación de Pearson", "shrink": 0.8},
            annot_kws={"size": 10, "fontweight": "bold"}, ax=ax,
        )
        ax.set_title("Matriz de correlación", fontsize=13, fontweight="bold")
        ax.tick_params(axis="x", rotation=45)

        return self._guardar_figura(fig, "correlacion.png")

    # ---------- Gráficos de análisis complementarios ---------- #

    def plot_box(self, serie: pd.DataFrame, col: str, col_comparativa: str) -> Optional[str]:
        if col == col_comparativa:
            return None

        fig, ax = plt.subplots()
        sns.boxplot(
            x=col, y=col_comparativa, data=serie,
            palette="Set2", hue=col, legend=False,
            notch=True, fliersize=1, boxprops=dict(alpha=0.7),
            ax=ax,
        )
        ax.set_title(f"Distribución de {col_comparativa} por {col}")
        ax.set_xlabel("")
        ax.tick_params(axis="x", rotation=90)
        self._aplicar_estilo_ax(ax)

        return self._guardar_figura(fig, f"box_{col}.png")

    def serie_tiempo(self, df: pd.DataFrame, padecimiento: str,
                     agrupamiento_sexo: bool = True,
                     agrupamiento_entidad: bool = False) -> Optional[str]:

        fig, ax = plt.subplots(figsize=(16, 4))
        subtitulo = ""

        if agrupamiento_sexo and not agrupamiento_entidad:
            st = df.groupby("Fecha")[["incrementos_hombres", "incrementos_mujeres"]].sum()
            ax.plot(st.index, st["incrementos_hombres"], linewidth=1.2, alpha=0.8,
                    color=self.conf_paleta_sexo["Hombres"], label="Hombres")
            ax.plot(st.index, st["incrementos_mujeres"], linewidth=1.2, alpha=0.8,
                    color=self.conf_paleta_sexo["Mujeres"], label="Mujeres")
            subtitulo = "por sexo"

        elif not agrupamiento_sexo and agrupamiento_entidad:
            col_region = "region_salud_mental"
            st = (
                df.groupby(["Fecha", col_region])[["incrementos_hombres", "incrementos_mujeres"]]
                .sum()
                .assign(incrementos_totales=lambda g: g["incrementos_hombres"] + g["incrementos_mujeres"])
                .reset_index()
            )
            for region, datos in st.groupby(col_region):
                ax.plot(datos["Fecha"], datos["incrementos_totales"],
                        linewidth=1.2, alpha=0.8, label=region)
            subtitulo = f"por {col_region}"

        try:
            covid_start = pd.Timestamp("2020-03-01")
            covid_end = pd.Timestamp("2021-06-01")
            ax.axvspan(covid_start, covid_end, alpha=0.1, color="red", label="Covid")
        except Exception:
            pass

        ax.set_xlabel("Fecha", fontsize=11)
        ax.set_ylabel("Incrementos semanales", fontsize=11)
        ax.set_title(f"Evolución semanal nacional de {padecimiento} {subtitulo}".strip())
        ax.legend(fontsize=10)
        self._aplicar_estilo_ax(ax)
        ax.yaxis.grid(True, alpha=0.3, color="gray", linestyle="--", linewidth=0.5)

        return self._guardar_figura(fig, f"serie_tiempo_{padecimiento}.png")

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
        fig.subplots_adjust(bottom=0.13, top=0.89, left=0.055, right=0.975)

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
        ax.axvspan(covid_ini, covid_fin, alpha=0.07, color="#E53935", zorder=0)
        mid_covid = covid_ini + (covid_fin - covid_ini) / 2
        ax.annotate(
            "COVID-19",
            xy=(mid_covid, 1.0),
            xycoords=("data", "axes fraction"),
            fontsize=7, fontweight="bold", color="#C62828",
            ha="center", va="top",
            bbox=dict(
                boxstyle="round,pad=0.25", fc="#FFEBEE", ec="#EF9A9A",
                alpha=0.85, lw=0.6,
            ),
        )

        # ── 3. Banda de predicción ──────────────────────────────────────
        ax.fill_between(
            forecast["ds"], forecast["yhat_lower"], forecast["yhat_upper"],
            alpha=0.20, color=c_band, zorder=1,
            label="Intervalo 80 %",
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
            label="Pronóstico Prophet",
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

        # ── 8. Zona de prueba CV (sombra gris + etiquetas) ─────────────
        fecha_corte = pd.Timestamp(conf["FECHA_CORTE_ENTRENAMIENTO"])

        ax.axvspan(
            fecha_corte, fecha_max_datos,
            alpha=0.06, color=c_gray, zorder=0,
        )
        ax.axvline(
            fecha_corte, color=c_gray, ls=":", lw=1.2, alpha=0.6, zorder=6,
        )
        ax.annotate(
            "Entrenamiento",
            xy=(fecha_corte, 0.88),
            xycoords=("data", "axes fraction"),
            fontsize=7.5, color=c_gray,
            ha="right", va="top",
        )
        ax.annotate(
            "Prueba CV",
            xy=(fecha_corte, 0.88),
            xycoords=("data", "axes fraction"),
            fontsize=7.5, color=c_gray,
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

        # ── Leyenda + ficha: banda compacta bajo el eje X ───────────────
        handles, labels = ax.get_legend_handles_labels()
        fig.legend(
            handles, labels,
            loc="lower center", bbox_to_anchor=(0.515, 0.04),
            ncol=len(handles), fontsize=9.5,
            frameon=False, handlelength=1.8,
            handletextpad=0.4, columnspacing=2.0,
        )

        # Ficha técnica: una linea justo debajo de la leyenda
        if metricas:
            mase_v = metricas.get("mase")
            rmse_v = metricas.get("rmse")
            confianza = metricas.get("confianza", "normal")
            es_fallback = metricas.get("es_fallback", False)
            modelo_usado = metricas.get("modelo_usado", "")

            tokens = ["Prophet (Meta/Facebook)", "IC 80 %"]

            if mase_v is not None and mase_v < 100:
                tag = "supera naive" if mase_v < 1 else "no supera naive"
                tokens.append(f"MASE: {mase_v:.2f} ({tag})")
            if rmse_v is not None and rmse_v < 100:
                tokens.append(f"RMSE: {rmse_v:.4f}")

            if es_fallback:
                region = ""
                if "region_" in modelo_usado:
                    region = modelo_usado.split("region_")[1].rsplit("_", 1)[0]
                    region = region.replace("_", " ").replace("-", "/")
                tokens.append(
                    f"Modelo: Regional ({region})"
                    if region else "Modelo: Regional (respaldo)"
                )
            elif confianza == "normal":
                tokens.append("Modelo: Estatal propio")

            if metricas.get("seasonality_mode"):
                tokens.append(f"Estac: {metricas['seasonality_mode']}")
            if metricas.get("changepoint_prior_scale") is not None:
                tokens.append(f"CP: {metricas['changepoint_prior_scale']}")
            if metricas.get("seasonality_prior_scale") is not None:
                tokens.append(f"SP: {metricas['seasonality_prior_scale']}")

            ficha = "  |  ".join(tokens)
            fig.text(
                0.515, 0.008, ficha,
                ha="center", va="bottom",
                fontsize=8.5, family="sans-serif",
                color="#999",
            )

        # ── Guardar ──────────────────────────────────────────────────────
        ruta = os.path.join(self.carpeta_salida, f"{nombre_archivo}.png")
        fig.savefig(ruta, dpi=150, facecolor="white", edgecolor="none")
        plt.close(fig)
        return ruta
