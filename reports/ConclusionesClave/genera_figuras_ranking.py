"""Genera figuras de ranking de motores para el reporte LaTeX.

Figuras generadas:
  0. fig_distribucion_motores.png   — Donut chart de distribucion de motores ganadores
  1. fig_boxplot_smape_motores.png  — Box plot SMAPE por motor, faceteado por padecimiento
  2. fig_barras_mase_motores.png    — % series con MASE < 1 por motor
  3. fig_mapa_smape_depresion.png   — Mapa coroplético SMAPE Depresión por estado
  4. fig_heatmap_smape_estado_pad.png — Heatmap SMAPE por estado y padecimiento
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paleta IMSS 2026
# ---------------------------------------------------------------------------
COLORS = {
    "Prophet": "#004d40",
    "DeepAR": "#880e4f",
    "Ensemble": "#FF6F00",
    "Stacking": "#1A237E",
}
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

OUT_DIR = Path(__file__).parent
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

MOTORS = ["DeepAR", "Prophet", "Ensemble", "Stacking"]


def load_data() -> pd.DataFrame:
    """Carga la tabla de 333 modelos de producción."""
    return pd.read_excel(PROD_XLSX, sheet_name="Producción")


def _motor_order_color(motors: list[str]) -> list[str]:
    return [COLORS.get(m, GRIS) for m in motors]


# ═══════════════════════════════════════════════════════════════════════════
# Figura 0: Donut chart de distribución de motores ganadores
# ═══════════════════════════════════════════════════════════════════════════
def fig_distribucion_motores(df: pd.DataFrame) -> None:
    """Donut chart con la distribucion de motores ganadores (333 series)."""
    if "modelo_produccion" not in df.columns:
        print("  [SKIP] fig_distribucion_motores.png — columna modelo_produccion no encontrada")
        return

    mc = df["modelo_produccion"].value_counts()
    # Ordenar segun MOTORS para consistencia visual
    labels = [m for m in MOTORS if m in mc.index]
    sizes = [mc[m] for m in labels]
    colors = [COLORS.get(m, GRIS) for m in labels]
    total = sum(sizes)

    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor(BG_COLOR)

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        colors=colors,
        autopct=lambda pct: f"{pct:.1f}%\n({int(round(pct * total / 100))})",
        startangle=90,
        pctdistance=0.78,
        wedgeprops={"width": 0.45, "edgecolor": "white", "linewidth": 2},
    )

    for at in autotexts:
        at.set_fontsize(10)
        at.set_fontweight("bold")
        at.set_color("white")

    # Centro del donut
    ax.text(
        0,
        0,
        f"{total}\nmodelos",
        ha="center",
        va="center",
        fontsize=18,
        fontweight="bold",
        color=NEGRO,
    )

    # Leyenda
    legend_labels = [f"{m} ({mc[m]})" for m in labels]
    ax.legend(
        wedges,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
        ncol=2,
        frameon=False,
        fontsize=11,
        handlelength=1.5,
        columnspacing=2,
    )

    ax.set_title(
        "Distribucion de series ganadas por motor\nSeleccion automatica por SMAPE + MASE + RMSE",
        fontweight="bold",
        color=VERDE_IMSS,
        fontsize=13,
        pad=15,
    )

    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_distribucion_motores.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_distribucion_motores.png")


# ═══════════════════════════════════════════════════════════════════════════
# Figura 1: Box plot SMAPE por motor, faceteado por padecimiento
# ═══════════════════════════════════════════════════════════════════════════
def fig_boxplot_smape(df: pd.DataFrame) -> None:
    pads = ["Depresión", "Parkinson", "Alzheimer"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=False)

    for ax, pad in zip(axes, pads, strict=False):
        sub = df[df["padecimiento"] == pad]
        data = []
        labels = []
        colors = []
        for motor in MOTORS:
            col = f"{motor.lower()}_smape"
            if col in sub.columns:
                vals = sub[col].dropna()
                if not vals.empty:
                    data.append(vals.values)
                    labels.append(motor)
                    colors.append(COLORS[motor])

        bp = ax.boxplot(
            data,
            tick_labels=labels,
            patch_artist=True,
            widths=0.6,
            medianprops={"color": NEGRO, "linewidth": 1.5},
            whiskerprops={"color": GRIS},
            capprops={"color": GRIS},
            flierprops={"marker": "o", "markersize": 3, "alpha": 0.4},
        )
        for patch, color in zip(bp["boxes"], colors, strict=False):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_title(pad, fontweight="bold", color=PAD_COLORS.get(pad, NEGRO))
        ax.set_ylabel("SMAPE (%)" if ax == axes[0] else "")
        ax.tick_params(axis="x", rotation=30)
        ax.set_ylim(bottom=0)

    fig.suptitle(
        "Distribución de SMAPE por motor de pronóstico",
        fontsize=13,
        fontweight="bold",
        color=VERDE_IMSS,
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_boxplot_smape_motores.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_boxplot_smape_motores.png")


# ═══════════════════════════════════════════════════════════════════════════
# Figura 2: Barras MASE < 1 por motor
# ═══════════════════════════════════════════════════════════════════════════
def fig_barras_mase(df: pd.DataFrame) -> None:
    results = {}
    for motor in MOTORS:
        col = f"{motor.lower()}_mase"
        if col in df.columns:
            vals = df[col].dropna()
            if not vals.empty:
                pct = (vals < 1).sum() / len(vals) * 100
                results[motor] = pct

    motors_sorted = sorted(results, key=lambda m: results[m], reverse=True)
    pcts = [results[m] for m in motors_sorted]
    colors = [COLORS[m] for m in motors_sorted]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.barh(motors_sorted, pcts, color=colors, edgecolor="white", height=0.55)

    for bar, pct in zip(bars, pcts, strict=False):
        ax.text(
            bar.get_width() + 0.8,
            bar.get_y() + bar.get_height() / 2,
            f"{pct:.1f}%",
            va="center",
            fontweight="bold",
            fontsize=11,
            color=NEGRO,
        )

    ax.set_xlabel("Series con MASE < 1 (%)")
    ax.set_title(
        "Porcentaje de series que superan al naive estacional",
        fontweight="bold",
        color=VERDE_IMSS,
    )
    ax.set_xlim(0, 105)
    ax.invert_yaxis()

    # Linea de referencia al 50%
    ax.axvline(50, color=GRIS, linestyle="--", alpha=0.5, linewidth=0.8)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_barras_mase_motores.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_barras_mase_motores.png")


# ═══════════════════════════════════════════════════════════════════════════
# Figura 3: Mapa coroplético SMAPE Depresión
# ═══════════════════════════════════════════════════════════════════════════
def fig_mapa_smape(df: pd.DataFrame) -> None:
    """Genera mapa coroplético de México con SMAPE de Depresión por estado."""
    try:
        import geopandas as gpd
    except ImportError:
        _fig_mapa_fallback(df)
        return

    # Filtrar Depresión + sexo general + solo estados (no regiones ni Nacional)
    dep = df[(df["padecimiento"] == "Depresión") & (df["sexo"].str.lower() == "general")].copy()

    regiones = {
        "Nacional",
        "Region Metropolitana alta",
        "Region Rural - dispersa",
        "Region Sur-Sureste vulnerable",
        "Region Urbana media",
    }
    dep = dep[~dep["entidad"].isin(regiones)]

    # Cargar geojson local de México (32 estados)
    geo_path = OUT_DIR / "mexico_states.json"
    if not geo_path.exists():
        _fig_mapa_fallback(df)
        return

    try:
        gdf = gpd.read_file(geo_path)
    except Exception:
        _fig_mapa_fallback(df)
        return

    # Nombres coinciden directamente (Ciudad de México, Michoacán, etc.)
    merged = gdf.merge(
        dep[["entidad", "smape_prod"]],
        left_on="name",
        right_on="entidad",
        how="left",
    )

    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list(
        "imss_semaforo",
        ["#2E7D32", "#F9A825", "#E65100", "#B71C1C"],
        N=256,
    )

    fig, ax = plt.subplots(1, 1, figsize=(10, 7))
    merged.plot(
        column="smape_prod",
        ax=ax,
        legend=True,
        cmap=cmap,
        vmin=0,
        vmax=25,
        missing_kwds={"color": "#E0E0E0", "label": "Sin datos"},
        edgecolor="#555555",
        linewidth=0.4,
        legend_kwds={
            "label": "SMAPE (%)",
            "orientation": "horizontal",
            "shrink": 0.6,
            "pad": 0.02,
        },
    )

    # Anotar nombre de estado + SMAPE sobre el mapa
    for _, row in merged.iterrows():
        if pd.notna(row.get("smape_prod")):
            centroid = row.geometry.centroid
            ax.annotate(
                f"{row['smape_prod']:.0f}%",
                xy=(centroid.x, centroid.y),
                ha="center",
                va="center",
                fontsize=6,
                fontweight="bold",
                color=NEGRO,
                bbox={
                    "boxstyle": "round,pad=0.15",
                    "facecolor": "white",
                    "alpha": 0.7,
                    "edgecolor": "none",
                },
            )

    ax.set_title(
        "Calidad del pronóstico de Depresión por entidad federativa\n(modo general, SMAPE del modelo de producción)",
        fontweight="bold",
        color=VERDE_IMSS,
        fontsize=12,
    )
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_mapa_smape_depresion.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_mapa_smape_depresion.png")


def _fig_mapa_fallback(df: pd.DataFrame) -> None:
    """Fallback: tabla visual con barras de color si geopandas no está."""
    dep = df[(df["padecimiento"] == "Depresión") & (df["sexo"].str.lower() == "general")].copy()
    regiones = {
        "Nacional",
        "Region Metropolitana alta",
        "Region Rural - dispersa",
        "Region Sur-Sureste vulnerable",
        "Region Urbana media",
    }
    dep = dep[~dep["entidad"].isin(regiones)].sort_values("smape_prod")

    fig, ax = plt.subplots(figsize=(8, 10))
    colors = []
    for s in dep["smape_prod"]:
        if s < 5:
            colors.append("#2E7D32")  # verde
        elif s < 10:
            colors.append("#F9A825")  # amarillo
        elif s < 20:
            colors.append("#E65100")  # naranja
        else:
            colors.append("#B71C1C")  # rojo

    bars = ax.barh(dep["entidad"], dep["smape_prod"], color=colors, edgecolor="white", height=0.7)
    for bar, val in zip(bars, dep["smape_prod"], strict=False):
        ax.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%",
            va="center",
            fontsize=8,
            color=NEGRO,
        )

    ax.set_xlabel("SMAPE (%)")
    ax.set_title(
        "Calidad del pronóstico de Depresión por entidad federativa\n(modo general)",
        fontweight="bold",
        color=VERDE_IMSS,
        fontsize=12,
    )
    ax.invert_yaxis()

    # Leyenda semáforo
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor="#2E7D32", label="Excelente (< 5%)"),
        Patch(facecolor="#F9A825", label="Bueno (5-10%)"),
        Patch(facecolor="#E65100", label="Moderado (10-20%)"),
        Patch(facecolor="#B71C1C", label="Alto (> 20%)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_mapa_smape_depresion.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_mapa_smape_depresion.png (fallback barras)")


# ═══════════════════════════════════════════════════════════════════════════
# Figura 4: Heatmap SMAPE por estado y padecimiento
# ═══════════════════════════════════════════════════════════════════════════
def fig_heatmap_smape(df: pd.DataFrame) -> None:
    # Filtrar solo sexo general + solo estados (no regiones ni Nacional)
    gen = df[df["sexo"].str.lower() == "general"].copy()
    regiones = {
        "Nacional",
        "Region Metropolitana alta",
        "Region Rural - dispersa",
        "Region Sur-Sureste vulnerable",
        "Region Urbana media",
    }
    gen = gen[~gen["entidad"].isin(regiones)]

    pivot = gen.pivot_table(
        index="entidad", columns="padecimiento", values="smape_prod", aggfunc="first"
    )

    # Ordenar por SMAPE promedio ascendente
    pivot["_mean"] = pivot.mean(axis=1)
    pivot = pivot.sort_values("_mean")
    pivot = pivot.drop(columns=["_mean"])

    # Reordenar columnas
    col_order = [c for c in ["Depresión", "Parkinson", "Alzheimer"] if c in pivot.columns]
    pivot = pivot[col_order]

    fig, ax = plt.subplots(figsize=(8, 10))

    # Crear heatmap manual con colores IMSS
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list(
        "imss_semaforo",
        ["#2E7D32", "#F9A825", "#E65100", "#B71C1C"],
        N=256,
    )

    data = pivot.values
    im = ax.imshow(data, aspect="auto", cmap=cmap, vmin=0, vmax=200)

    # Etiquetas
    ax.set_xticks(range(len(col_order)))
    ax.set_xticklabels(col_order, fontweight="bold")
    ax.set_yticks(range(len(pivot)))
    ax.set_yticklabels(pivot.index, fontsize=8)

    # Colorear etiquetas de padecimiento
    for i, pad in enumerate(col_order):
        ax.get_xticklabels()[i].set_color(PAD_COLORS.get(pad, NEGRO))

    # Anotar valores
    for i in range(len(pivot)):
        for j in range(len(col_order)):
            val = data[i, j]
            if not np.isnan(val):
                text_color = "white" if val > 100 else NEGRO
                ax.text(
                    j,
                    i,
                    f"{val:.0f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color=text_color,
                    fontweight="bold",
                )

    cbar = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cbar.set_label("SMAPE (%)", fontsize=9)

    ax.set_title(
        "SMAPE por entidad federativa y padecimiento\n(modo general, modelo de producción)",
        fontweight="bold",
        color=VERDE_IMSS,
        fontsize=12,
    )

    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_heatmap_smape_estado_pad.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_heatmap_smape_estado_pad.png")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generando figuras de ranking de motores...")
    df = load_data()
    print(f"  Datos: {len(df)} modelos cargados")

    fig_distribucion_motores(df)
    fig_boxplot_smape(df)
    fig_barras_mase(df)
    fig_mapa_smape(df)
    fig_heatmap_smape(df)

    print("\nListo. Figuras en:", OUT_DIR)
