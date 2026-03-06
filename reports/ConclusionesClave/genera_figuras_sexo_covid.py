"""Genera figuras de distribución por sexo e impacto COVID-19.

Figuras generadas:
  5. fig_distribucion_sexo.png       — Barras apiladas de incidencia por sexo y padecimiento
  6. fig_covid_impact_depresion.png  — Serie temporal semanal con zona COVID sombreada
"""

from pathlib import Path

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
VERDE_IMSS = "#00524E"
GUINDA = "#9B2242"
DORADO = "#B58500"
GRIS = "#97999B"
NEGRO = "#231F20"
BG_COLOR = "#FAFAFA"

# Colores por sexo (paleta IMSS)
COLOR_HOMBRES = "#00524E"  # verde/teal IMSS
COLOR_MUJERES = "#9B2242"  # guinda IMSS

OUT_DIR = Path(__file__).parent
BOLETIN_CSV = Path("data/processed/dataset_boletin_epidemiologico.csv")
PROD_XLSX = Path("reports/ProdDetails/tabla_333_modelos_produccion.xlsx")

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


def load_boletin() -> pd.DataFrame:
    """Carga el boletín epidemiológico."""
    return pd.read_csv(BOLETIN_CSV, low_memory=False)


# ═══════════════════════════════════════════════════════════════════════════
# Figura 5: Distribución de incidencia por sexo
# ═══════════════════════════════════════════════════════════════════════════
def fig_distribucion_sexo(df: pd.DataFrame) -> None:
    """Barras apiladas: proporción hombres vs mujeres por padecimiento."""
    pads = ["Depresión", "Parkinson", "Alzheimer"]

    # Calcular totales por padecimiento y sexo
    # Acumulado_hombres/mujeres son acumulados anuales por entidad;
    # tomar la última semana de cada año/entidad para obtener el total anual
    hombres_totals = []
    mujeres_totals = []

    for pad in pads:
        sub = df[df["Padecimiento"] == pad] if "Padecimiento" in df.columns else pd.DataFrame()
        if sub.empty or "Acumulado_hombres" not in sub.columns:
            hombres_totals.append(0)
            mujeres_totals.append(0)
            continue

        # Última semana por año/entidad = acumulado anual de esa entidad
        idx = sub.groupby(["Anio", "Entidad"])["Semana"].idxmax()
        last_weeks = sub.loc[idx]
        h_total = last_weeks["Acumulado_hombres"].sum()
        m_total = last_weeks["Acumulado_mujeres"].sum()

        hombres_totals.append(h_total)
        mujeres_totals.append(m_total)

    # Calcular porcentajes
    totals = [h + m for h, m in zip(hombres_totals, mujeres_totals, strict=False)]
    h_pcts = [h / t * 100 if t > 0 else 0 for h, t in zip(hombres_totals, totals, strict=False)]
    m_pcts = [m / t * 100 if t > 0 else 0 for m, t in zip(mujeres_totals, totals, strict=False)]

    fig, ax = plt.subplots(figsize=(8, 4.5))

    y_pos = np.arange(len(pads))
    bar_height = 0.5

    # Barras apiladas horizontales
    ax.barh(
        y_pos,
        h_pcts,
        height=bar_height,
        color=COLOR_HOMBRES,
        edgecolor="white",
        label="Hombres",
    )
    ax.barh(
        y_pos,
        m_pcts,
        height=bar_height,
        left=h_pcts,
        color=COLOR_MUJERES,
        edgecolor="white",
        label="Mujeres",
    )

    # Etiquetas con porcentaje y total
    for i, (hp, mp, total) in enumerate(zip(h_pcts, m_pcts, totals, strict=False)):
        # Hombres
        if hp > 10:
            ax.text(
                hp / 2,
                i,
                f"{hp:.0f}%",
                ha="center",
                va="center",
                fontweight="bold",
                fontsize=11,
                color="white",
            )
        # Mujeres
        if mp > 10:
            ax.text(
                hp + mp / 2,
                i,
                f"{mp:.0f}%",
                ha="center",
                va="center",
                fontweight="bold",
                fontsize=11,
                color="white",
            )
        # Total a la derecha
        ax.text(
            101,
            i,
            f"{total:,.0f}",
            ha="left",
            va="center",
            fontsize=9,
            color=GRIS,
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(pads, fontweight="bold")
    # Colorear etiquetas de padecimiento
    for i, pad in enumerate(pads):
        ax.get_yticklabels()[i].set_color(PAD_COLORS[pad])

    ax.set_xlabel("Distribución por sexo (%)")
    ax.set_xlim(0, 115)
    ax.set_title(
        "Distribución acumulada de incidencia por sexo y padecimiento\n(2014-2026)",
        fontweight="bold",
        color=VERDE_IMSS,
    )
    ax.invert_yaxis()

    # Línea de referencia al 50%
    ax.axvline(50, color=GRIS, linestyle="--", alpha=0.4, linewidth=0.8)

    # Leyenda horizontal debajo del gráfico
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=COLOR_HOMBRES, label="Hombres"),
        Patch(facecolor=COLOR_MUJERES, label="Mujeres"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        frameon=False,
        fontsize=10,
        handlelength=1.5,
        columnspacing=3,
    )

    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_distribucion_sexo.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_distribucion_sexo.png")


# ═══════════════════════════════════════════════════════════════════════════
# Figura 6: Impacto COVID-19 en Depresión (serie temporal semanal)
# ═══════════════════════════════════════════════════════════════════════════
def fig_covid_impact(df: pd.DataFrame) -> None:
    """Serie temporal semanal de Depresión con zona COVID sombreada."""
    # Filtrar Depresión y agregar a nivel nacional
    dep = df.copy()
    if "Padecimiento" in dep.columns:
        dep = dep[dep["Padecimiento"] == "Depresión"]

    # Detectar columnas de fecha
    date_col = None
    for candidate in ["Fecha", "fecha", "ds"]:
        if candidate in dep.columns:
            date_col = candidate
            break

    year_col = None
    for candidate in ["Anio", "anio", "year"]:
        if candidate in dep.columns:
            year_col = candidate
            break

    week_col = None
    for candidate in ["Semana", "semana", "week"]:
        if candidate in dep.columns:
            week_col = candidate
            break

    casos_col = "Casos_semana" if "Casos_semana" in dep.columns else None

    if casos_col is None:
        print("  [SKIP] fig_covid_impact_depresion.png — columna Casos_semana no encontrada")
        return

    # Construir serie temporal
    if date_col:
        dep[date_col] = pd.to_datetime(dep[date_col], errors="coerce")
        dep = dep.dropna(subset=[date_col])
        dep = dep.sort_values(date_col)
        # Agrupar por fecha (en caso de múltiples entidades)
        ts = dep.groupby(date_col)[casos_col].sum().reset_index()
        ts.columns = ["fecha", "casos"]
    elif year_col and week_col:
        # Construir fecha desde año + semana
        dep = dep.dropna(subset=[year_col, week_col, casos_col])
        # Agrupar por año-semana
        ts = dep.groupby([year_col, week_col])[casos_col].sum().reset_index()
        ts.columns = ["anio", "semana", "casos"]

        def _safe_iso_date(r: pd.Series) -> pd.Timestamp | None:
            y, w = int(r["anio"]), int(r["semana"])
            w = min(w, 52)  # clamp semana 53 → 52
            try:
                return pd.Timestamp.fromisocalendar(y, w, 1)
            except ValueError:
                return None

        ts["fecha"] = ts.apply(_safe_iso_date, axis=1)
        ts = ts.dropna(subset=["fecha"])
        ts = ts.sort_values("fecha")
    else:
        print("  [SKIP] fig_covid_impact_depresion.png — sin columnas de fecha")
        return

    # Filtrar 2016-2025
    ts = ts[(ts["fecha"].dt.year >= 2016) & (ts["fecha"].dt.year <= 2026)]

    if ts.empty:
        print("  [SKIP] fig_covid_impact_depresion.png — sin datos en rango 2016-2025")
        return

    fig, ax = plt.subplots(figsize=(14, 5))

    # Zona COVID sombreada
    covid_start = pd.Timestamp("2020-03-15")
    covid_end = pd.Timestamp("2021-06-30")
    ax.axvspan(covid_start, covid_end, alpha=0.12, color=GRIS, zorder=0)
    ax.text(
        covid_start + (covid_end - covid_start) / 2,
        ts["casos"].max() * 0.95,
        "COVID-19",
        ha="center",
        va="top",
        fontsize=10,
        fontweight="bold",
        color=GRIS,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.8, "edgecolor": GRIS},
    )

    # Serie principal
    ax.plot(
        ts["fecha"],
        ts["casos"],
        color=GUINDA,
        linewidth=1.2,
        alpha=0.85,
        zorder=2,
    )

    # Media móvil 12 semanas
    ts["ma12"] = ts["casos"].rolling(12, center=True, min_periods=6).mean()
    ax.plot(
        ts["fecha"],
        ts["ma12"],
        color=NEGRO,
        linewidth=2,
        alpha=0.9,
        label="Media móvil 12 sem",
        zorder=3,
    )

    # Encontrar el mínimo COVID y máximo post-COVID
    covid_data = ts[(ts["fecha"] >= covid_start) & (ts["fecha"] <= covid_end)]
    if not covid_data.empty:
        min_idx = covid_data["casos"].idxmin()
        min_row = ts.loc[min_idx]
        ax.annotate(
            f"Mínimo: {int(min_row['casos']):,}",
            xy=(min_row["fecha"], min_row["casos"]),
            xytext=(min_row["fecha"] + pd.Timedelta(days=60), min_row["casos"] * 0.6),
            fontsize=8,
            color=GUINDA,
            fontweight="bold",
            arrowprops={"arrowstyle": "->", "color": GUINDA, "lw": 1},
        )

    post_covid = ts[ts["fecha"] > covid_end]
    if not post_covid.empty:
        max_idx = post_covid["casos"].idxmax()
        max_row = ts.loc[max_idx]
        ax.annotate(
            f"Pico post-COVID: {int(max_row['casos']):,}",
            xy=(max_row["fecha"], max_row["casos"]),
            xytext=(max_row["fecha"] - pd.Timedelta(days=120), max_row["casos"] * 1.08),
            fontsize=8,
            color=VERDE_IMSS,
            fontweight="bold",
            arrowprops={"arrowstyle": "->", "color": VERDE_IMSS, "lw": 1},
        )

    ax.set_xlabel("Fecha")
    ax.set_ylabel("Casos semanales (Nacional)")
    ax.set_title(
        "Incidencia semanal de Depresión a nivel nacional (2016-2026)\nImpacto del periodo COVID-19",
        fontweight="bold",
        color=VERDE_IMSS,
        fontsize=12,
    )
    ax.legend(loc="upper left", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_covid_impact_depresion.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_covid_impact_depresion.png")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generando figuras de sexo e impacto COVID...")
    df = load_boletin()
    print(f"  Boletín: {len(df):,} registros")

    fig_distribucion_sexo(df)
    fig_covid_impact(df)

    print("\nListo. Figuras en:", OUT_DIR)
