"""Genera figura de proyección de costos AWS a 12 meses.

Figura generada:
  fig_costos_aws_12m.png — Barras horizontales con rangos min/max por componente
"""

from pathlib import Path

from matplotlib.patches import Patch
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------
# Paleta IMSS 2026
# ---------------------------------------------------------------------------
VERDE_IMSS = "#00524E"
GRIS = "#97999B"
NEGRO = "#231F20"
BG_COLOR = "#FAFAFA"
AWS_ORANGE = "#FF9900"
AWS_DARK = "#232F3E"

OUT_DIR = Path(__file__).parent

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "figure.facecolor": BG_COLOR,
        "axes.facecolor": "white",
        "axes.edgecolor": GRIS,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.color": GRIS,
    }
)

# ---------------------------------------------------------------------------
# Datos de la tabla LaTeX (costos anuales USD)
# ---------------------------------------------------------------------------
COMPONENTS = [
    "EC2 / Lambda\n(ETL pipeline semanal)",
    "SageMaker Batch\nInference (semanal)",
    "CloudWatch\n(logs + alarmas)",
    "Data Transfer",
    "SageMaker Training\n(1 reentrenamiento/trim.)",
    "S3 Storage\n(datos + modelos)",
    "ECR\n(imágenes Docker)",
]

COSTS = [  # [min_anual, max_anual]
    [120, 240],
    [60, 120],
    [24, 60],
    [12, 36],
    [14, 34],
    [6, 12],
    [3.60, 3.60],
]

# Colores degradados del más caro al más barato
PALETTE = [
    "#FF9900",  # naranja AWS fuerte
    "#FFB84D",
    "#FFCC80",
    "#FFE0B2",
    "#B2DFDB",
    "#80CBC4",
    "#4DB6AC",
]


def fig_costos_aws() -> None:
    """Genera barras horizontales con rangos de costo anual."""
    n = len(COMPONENTS)
    fig, ax = plt.subplots(figsize=(11, 5.5))

    y_pos = np.arange(n)
    mins = [c[0] for c in COSTS]
    maxs = [c[1] for c in COSTS]
    ranges = [mx - mn for mn, mx in zip(mins, maxs, strict=True)]

    # Barras base (mínimo)
    ax.barh(
        y_pos,
        mins,
        height=0.55,
        color=PALETTE,
        edgecolor="white",
        linewidth=0.8,
        zorder=3,
    )

    # Barras de rango (máximo - mínimo) encima
    ax.barh(
        y_pos,
        ranges,
        height=0.55,
        left=mins,
        color=PALETTE,
        edgecolor="white",
        linewidth=0.8,
        alpha=0.45,
        hatch="//",
        zorder=3,
    )

    # Etiquetas con rango de costo
    for i, (mn, mx) in enumerate(zip(mins, maxs, strict=True)):
        label = f"${mn:.2f}" if mn == mx else f"${mn:,.0f} - ${mx:,.0f}"
        ax.text(
            mx + 4,
            i,
            label,
            va="center",
            ha="left",
            fontsize=9.5,
            fontweight="bold",
            color=NEGRO,
        )

    # Total
    total_min = sum(mins)
    total_max = sum(maxs)

    # Línea separadora antes del total
    ax.axhline(y=n - 0.3, color=GRIS, linewidth=0.8, alpha=0.5, zorder=2)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(COMPONENTS, fontsize=9, color=NEGRO)
    ax.invert_yaxis()

    ax.set_xlabel("Costo anual estimado (USD)", fontsize=10, color=NEGRO)
    ax.set_xlim(0, max(maxs) + 80)

    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    # Total integrado centrado-derecha a media altura
    ax.text(
        0.97,
        0.45,
        f"Total anual:  ${total_min:,.0f} \u2013 ${total_max:,.0f} USD",
        transform=ax.transAxes,
        ha="right",
        va="center",
        fontsize=11,
        fontweight="bold",
        color=AWS_DARK,
        bbox={
            "boxstyle": "round,pad=0.4",
            "facecolor": "#FFF8E1",
            "edgecolor": AWS_ORANGE,
            "alpha": 0.9,
            "linewidth": 1.2,
        },
    )
    ax.text(
        0.97,
        0.38,
        "Reentrenamiento trimestral  |  Inferencia semanal",
        transform=ax.transAxes,
        ha="right",
        va="center",
        fontsize=8,
        style="italic",
        color=GRIS,
    )

    ax.set_title(
        "Proyección de costos AWS a 12 meses para EpiForecast-MX\n"
        "Desglose por componente con rangos mínimo-máximo",
        fontweight="bold",
        color=VERDE_IMSS,
        fontsize=12,
        pad=12,
    )

    # Leyenda
    legend_elements = [
        Patch(facecolor=AWS_ORANGE, alpha=0.9, label="Costo mínimo"),
        Patch(facecolor=AWS_ORANGE, alpha=0.45, hatch="//", label="Rango adicional (máximo)"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.10),
        ncol=2,
        frameon=False,
        fontsize=9,
        handlelength=2,
        columnspacing=3,
    )

    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_costos_aws_12m.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_costos_aws_12m.png")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generando figura de costos AWS...")
    fig_costos_aws()
    print("\nListo. Figura en:", OUT_DIR)
