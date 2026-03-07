"""Genera figura radar comparativa de proveedores cloud.

Figura generada:
  fig_radar_cloud_providers.png — Radar de 8 factores x 4 proveedores
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Paleta IMSS 2026
# ---------------------------------------------------------------------------
VERDE_IMSS = "#00524E"
GRIS = "#97999B"
NEGRO = "#231F20"
BG_COLOR = "#FAFAFA"

# Colores por proveedor (distintos, institucionales)
PROVIDER_COLORS = {
    "AWS SageMaker": "#FF9900",  # naranja AWS oficial
    "Google Vertex AI": "#4285F4",  # azul Google oficial
    "Azure ML": "#0078D4",  # azul Microsoft oficial
    "IBM watsonx.ai": "#054ADA",  # azul IBM oficial
}

OUT_DIR = Path(__file__).parent

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "figure.facecolor": BG_COLOR,
        "axes.facecolor": BG_COLOR,
    }
)

# ---------------------------------------------------------------------------
# Datos de la tabla comparativa
# ---------------------------------------------------------------------------
FACTORS = [
    "Costo por\nentrenamiento",
    "Integración\nPyTorch",
    "AutoML /\nmanaged",
    "Escalabilidad\nGPU",
    "Ecosistema\nde datos",
    "Soporte\nen México",
    "Documentación\ny comunidad",
    "Seguridad y\ncompliance",
]

WEIGHTS = [0.20, 0.15, 0.15, 0.12, 0.12, 0.10, 0.08, 0.08]

SCORES = {
    "AWS SageMaker": [9, 10, 9, 10, 10, 8, 9, 9],
    "Google Vertex AI": [8, 9, 9, 9, 9, 8, 9, 9],
    "Azure ML": [7, 8, 8, 9, 8, 9, 8, 10],
    "IBM watsonx.ai": [6, 7, 7, 7, 7, 7, 7, 8],
}


# Puntajes ponderados de la tabla LaTeX (calculados con pesos exactos)
WEIGHTED_SCORES = {
    "AWS SageMaker": 9.29,
    "Google Vertex AI": 8.70,
    "Azure ML": 8.18,
    "IBM watsonx.ai": 6.88,
}


def fig_radar_cloud() -> None:
    """Genera radar chart elegante de proveedores cloud."""
    n = len(FACTORS)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]  # cerrar el polígono

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw={"polar": True})

    # Fondo del radar
    ax.set_facecolor("white")
    fig.patch.set_facecolor(BG_COLOR)

    # Gridlines circulares personalizadas
    ax.set_rgrids(
        [2, 4, 6, 8, 10],
        labels=["2", "4", "6", "8", "10"],
        angle=0,
        fontsize=8,
        color=GRIS,
        alpha=0.7,
    )
    ax.set_ylim(0, 10.5)

    # Gridlines radiales y circulares con estilo suave
    ax.yaxis.grid(True, color=GRIS, alpha=0.2, linewidth=0.5)
    ax.xaxis.grid(True, color=GRIS, alpha=0.3, linewidth=0.5)

    # Anillos de fondo sombreados (alternando)
    for r_inner, r_outer in [(0, 2), (4, 6), (8, 10)]:
        theta_fill = np.linspace(0, 2 * np.pi, 100)
        ax.fill_between(
            theta_fill,
            r_inner,
            r_outer,
            alpha=0.03,
            color=VERDE_IMSS,
            zorder=0,
        )

    # Dibujar cada proveedor
    line_widths = {
        "AWS SageMaker": 2.8,
        "Google Vertex AI": 2.0,
        "Azure ML": 2.0,
        "IBM watsonx.ai": 1.6,
    }
    fill_alphas = {
        "AWS SageMaker": 0.18,
        "Google Vertex AI": 0.10,
        "Azure ML": 0.08,
        "IBM watsonx.ai": 0.06,
    }
    line_styles = {
        "AWS SageMaker": "-",
        "Google Vertex AI": "-",
        "Azure ML": "--",
        "IBM watsonx.ai": ":",
    }
    z_orders = {"AWS SageMaker": 5, "Google Vertex AI": 4, "Azure ML": 3, "IBM watsonx.ai": 2}

    for provider, scores in SCORES.items():
        values = scores + scores[:1]  # cerrar
        color = PROVIDER_COLORS[provider]
        ws = WEIGHTED_SCORES[provider]

        ax.plot(
            angles,
            values,
            color=color,
            linewidth=line_widths[provider],
            linestyle=line_styles[provider],
            label=f"{provider} ({ws:.2f})",
            zorder=z_orders[provider],
        )
        ax.fill(
            angles,
            values,
            alpha=fill_alphas[provider],
            color=color,
            zorder=z_orders[provider] - 1,
        )

        # Puntos en cada vértice
        marker_size = 7 if provider == "AWS SageMaker" else 4
        ax.scatter(
            angles[:-1],
            scores,
            color=color,
            s=marker_size**2,
            zorder=z_orders[provider] + 1,
            edgecolors="white",
            linewidths=0.8,
        )

    # Valores numéricos de AWS en cada vértice (destacar al ganador)
    aws_scores = SCORES["AWS SageMaker"]
    for _i, (angle, score) in enumerate(zip(angles[:-1], aws_scores, strict=True)):
        # Offset radial para que no se encime con el punto
        offset = 0.65
        ax.text(
            angle,
            score + offset,
            str(score),
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color=PROVIDER_COLORS["AWS SageMaker"],
            zorder=10,
        )

    # Etiquetas de factores
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(FACTORS, fontsize=9, color=NEGRO, fontweight="bold")

    # Ajustar posición de etiquetas para que no se encimen
    for label, angle in zip(ax.get_xticklabels(), angles[:-1], strict=True):
        if angle in (0,):
            label.set_horizontalalignment("center")
        elif 0 < angle < np.pi:
            label.set_horizontalalignment("left")
        elif angle == np.pi:
            label.set_horizontalalignment("center")
        else:
            label.set_horizontalalignment("right")

    # Pesos debajo de cada factor
    for _i, (angle, weight) in enumerate(zip(angles[:-1], WEIGHTS, strict=True)):
        pct = f"({weight:.0%})"
        # Posicionar justo afuera del límite
        ax.text(
            angle,
            11.8,
            pct,
            ha="center",
            va="center",
            fontsize=7,
            color=GRIS,
            style="italic",
        )

    # Titulo
    ax.set_title(
        "Comparativa de proveedores cloud para EpiForecast-MX\n"
        "Puntuación ponderada en 8 factores de evaluación",
        fontsize=13,
        fontweight="bold",
        color=VERDE_IMSS,
        pad=35,
    )

    # Leyenda elegante abajo
    legend = ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.06),
        ncol=2,
        frameon=True,
        fontsize=10,
        handlelength=2.5,
        columnspacing=2.5,
        fancybox=True,
        shadow=False,
        edgecolor=GRIS,
        facecolor="white",
    )
    legend.get_frame().set_alpha(0.9)
    legend.get_frame().set_linewidth(0.5)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_radar_cloud_providers.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("  [OK] fig_radar_cloud_providers.png")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generando figura radar de proveedores cloud...")
    fig_radar_cloud()
    print("\nListo. Figura en:", OUT_DIR)
