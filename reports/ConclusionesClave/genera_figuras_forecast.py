"""Genera figuras de pronóstico nacional por padecimiento.

Figuras generadas:
  7. fig_forecast_depresion_nacional.png
  8. fig_forecast_parkinson_nacional.png
  9. fig_forecast_alzheimer_nacional.png
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paleta IMSS 2026
# ---------------------------------------------------------------------------
PAD_COLORS = {
    "Depresión": "#9B2242",
    "Parkinson": "#00524E",
    "Alzheimer": "#B58500",
}
REAL_COLOR = "#1B2A4A"  # azul oscuro para datos reales
VERDE_IMSS = "#00524E"
GRIS = "#97999B"
NEGRO = "#231F20"
BG_COLOR = "#FAFAFA"

OUT_DIR = Path(__file__).parent
TABLEAU_XLSX = Path("data/processed/tableau_model.xlsx")

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "figure.facecolor": BG_COLOR,
        "axes.facecolor": "white",
        "axes.edgecolor": GRIS,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.color": GRIS,
    }
)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carga datos reales y pronóstico del tableau."""
    real = pd.read_excel(TABLEAU_XLSX, sheet_name="real")
    forecast = pd.read_excel(TABLEAU_XLSX, sheet_name="forecast")
    real["ds"] = pd.to_datetime(real["ds"])
    forecast["ds"] = pd.to_datetime(forecast["ds"])
    return real, forecast


def fig_forecast_nacional(
    real: pd.DataFrame,
    forecast: pd.DataFrame,
    padecimiento: str,
) -> None:
    """Genera figura de pronóstico nacional para un padecimiento."""
    pad_lower = padecimiento.lower().replace("ó", "o").replace("é", "e")
    color = PAD_COLORS[padecimiento]

    # Filtrar datos reales (Nacional)
    r = (
        real[(real["padecimiento"] == padecimiento) & (real["entidad"] == "Nacional")]
        .sort_values("ds")
        .copy()
    )

    # Filtrar pronóstico (Nacional, general)
    f = (
        forecast[
            (forecast["padecimiento"] == padecimiento)
            & (forecast["entidad"] == "Nacional")
            & (forecast["meta_modo"] == "general")
        ]
        .sort_values("ds")
        .copy()
    )

    if r.empty or f.empty:
        print(f"  [SKIP] fig_forecast_{pad_lower}_nacional.png — sin datos")
        return

    # Determinar fecha de corte (última fecha con datos reales)
    last_real_date = r["ds"].max()

    # Serie real: desde 2018 para mejor visualización
    r = r[r["ds"] >= "2018-01-01"]

    # Pronóstico: separar histórico (overlap con real) y futuro
    f_hist = f[f["ds"] <= last_real_date]
    f_future = f[f["ds"] > last_real_date]

    # Para zoom: incluir pronóstico desde 2018
    f_hist = f_hist[f_hist["ds"] >= "2018-01-01"]

    fig, ax = plt.subplots(figsize=(14, 5.5))

    # --- Banda de confianza simulada (±20% del yhat para futuro) ---
    if not f_future.empty:
        yhat_future = f_future["yhat"].values.astype(float)
        dates_future = f_future["ds"].values

        # Banda que crece gradualmente
        n = len(yhat_future)
        spread = np.linspace(0.10, 0.25, n)  # 10% → 25%
        upper = yhat_future * (1 + spread)
        lower = yhat_future * (1 - spread)
        lower = np.maximum(lower, 0)

        ax.fill_between(
            dates_future,
            lower,
            upper,
            alpha=0.15,
            color=color,
            label="Banda de confianza (~80%)",
            zorder=1,
        )

    # --- Serie real ---
    ax.plot(
        r["ds"],
        r["incrementos_total"],
        color=REAL_COLOR,
        linewidth=1.0,
        alpha=0.7,
        label="Datos reales (SINAVE)",
        zorder=2,
    )

    # --- Media móvil de datos reales ---
    r_ma = r.set_index("ds")["incrementos_total"].rolling(8, center=True, min_periods=4).mean()
    ax.plot(
        r_ma.index,
        r_ma.values,
        color=REAL_COLOR,
        linewidth=2.0,
        alpha=0.9,
        label="Tendencia real (MA-8)",
        zorder=3,
    )

    # --- Pronóstico histórico (overlay con real) ---
    if not f_hist.empty:
        ax.plot(
            f_hist["ds"],
            f_hist["yhat"],
            color=color,
            linewidth=1.0,
            alpha=0.4,
            linestyle="--",
            zorder=2,
        )

    # --- Pronóstico futuro ---
    if not f_future.empty:
        # Conectar último punto real con primer punto futuro
        connect_dates = [last_real_date, f_future["ds"].iloc[0]]
        last_real_val = (
            r["incrementos_total"].iloc[-1] if not r.empty else f_future["yhat"].iloc[0]
        )
        connect_vals = [last_real_val, f_future["yhat"].iloc[0]]
        ax.plot(
            connect_dates,
            connect_vals,
            color=color,
            linewidth=2,
            alpha=0.6,
            zorder=3,
        )

        ax.plot(
            f_future["ds"],
            f_future["yhat"],
            color=color,
            linewidth=2.2,
            label=f"Pronóstico ({padecimiento})",
            zorder=4,
        )

    # --- Línea divisoria: corte real/pronóstico ---
    ax.axvline(
        last_real_date,
        color=GRIS,
        linestyle=":",
        linewidth=1,
        alpha=0.7,
        zorder=1,
    )
    y_top = ax.get_ylim()[1]
    ax.text(
        last_real_date,
        y_top * 0.95,
        "  Inicio pronóstico",
        fontsize=8,
        color=GRIS,
        va="top",
    )

    # --- Zona COVID (solo si visible) ---
    covid_start = pd.Timestamp("2020-03-15")
    covid_end = pd.Timestamp("2021-06-30")
    if r["ds"].min() < covid_end:
        ax.axvspan(covid_start, covid_end, alpha=0.06, color=GRIS, zorder=0)

    # --- Formato ---
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Casos semanales")
    ax.set_title(
        f"Pronóstico de {padecimiento} a nivel nacional (52 semanas)\n"
        f"Modelo de producción · Datos reales vs pronóstico",
        fontweight="bold",
        color=VERDE_IMSS,
        fontsize=12,
    )

    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.10),
        ncol=4,
        frameon=False,
        fontsize=9,
        columnspacing=2,
    )

    fig.tight_layout()
    fname = f"fig_forecast_{pad_lower}_nacional.png"
    fig.savefig(OUT_DIR / fname, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {fname}")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generando figuras de pronóstico nacional...")
    real, forecast = load_data()
    print(f"  Real: {len(real):,} rows | Forecast: {len(forecast):,} rows")

    for pad in ["Depresión", "Parkinson", "Alzheimer"]:
        fig_forecast_nacional(real, forecast, pad)

    print("\nListo. Figuras en:", OUT_DIR)
