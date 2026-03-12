# ruff: noqa
"""
Generador de figuras para el Resumen Ejecutivo - Avance 7
EpiForecast-MX | IMSS 2026
"""

import os
import shutil
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paleta IMSS
# ---------------------------------------------------------------------------
BURGUNDY = "#9B2242"
DARK_BURGUNDY = "#6F1D46"
TEAL = "#3D8B84"
TEAL_DARK = "#00524E"
GOLD = "#B58500"
COOL_GRAY = "#97999B"
IMSS_BLUE = "#003A70"

MODEL_COLORS = {
    "Prophet": "#004D40",
    "DeepAR": "#880E4F",
    "Ensemble": "#FF6F00",
    "Stacking": "#1A237E",
}

# Fondos para riesgos (paleta IMSS)
LIGHT_GREEN = "#E6F4EA"
LIGHT_YELLOW = "#FEF7E0"
LIGHT_RED = "#FDE8E8"

OUT_DIR = "/Users/haowei/Documents/Integrador/EpiForecast-MX/reports/FigResumenEjecutivo"
PROJECT = "/Users/haowei/Documents/Integrador/EpiForecast-MX"
os.makedirs(OUT_DIR, exist_ok=True)

# Fuente
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Helvetica", "Arial"]
plt.rcParams["axes.unicode_minus"] = False


def fmt_thousands(x: float) -> str:
    """Formato con separador de miles."""
    return f"{int(x):,}"


# ============================================================================
# FIGURE 1: Donut chart -- distribución de motores
# ============================================================================
def fig1_donut():
    labels = ["DeepAR", "Prophet", "Ensemble", "Stacking"]
    sizes = [244, 55, 32, 2]
    colors = [MODEL_COLORS[l] for l in labels]
    explode = (0.03, 0.03, 0.03, 0.12)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=300)

    # Suppress autopct for tiny segments, annotate manually
    def make_autopct(sizes_list):
        def autopct(p):
            count = int(round(p * sum(sizes_list) / 100))
            if count < 5:
                return ""  # Skip — will annotate manually
            return f"{p:.1f}%\n({count})"

        return autopct

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        autopct=make_autopct(sizes),
        startangle=90,
        colors=colors,
        explode=explode,
        pctdistance=0.75,
        wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
    )
    for at in autotexts:
        at.set_fontsize(10)
        at.set_fontweight("bold")
        at.set_color("white")

    # Manual annotation for Stacking (tiny segment)
    stacking_idx = labels.index("Stacking")
    ang = (wedges[stacking_idx].theta2 + wedges[stacking_idx].theta1) / 2
    x_pt = np.cos(np.deg2rad(ang)) * 0.85
    y_pt = np.sin(np.deg2rad(ang)) * 0.85
    x_txt = np.cos(np.deg2rad(ang)) * 1.45
    y_txt = np.sin(np.deg2rad(ang)) * 1.45
    ax.annotate(
        "0.6%\n(2)",
        xy=(x_pt, y_pt),
        xytext=(x_txt, y_txt),
        fontsize=9,
        fontweight="bold",
        color=MODEL_COLORS["Stacking"],
        ha="center",
        va="center",
        arrowprops=dict(arrowstyle="-", color=COOL_GRAY, lw=1.0),
    )

    # Centro
    ax.text(
        0,
        0,
        "333\nModelos",
        ha="center",
        va="center",
        fontsize=20,
        fontweight="bold",
        color=TEAL_DARK,
    )

    # Leyenda
    legend_patches = [mpatches.Patch(color=c, label=l) for l, c in zip(labels, colors)]
    ax.legend(
        handles=legend_patches,
        loc="lower center",
        ncol=4,
        fontsize=10,
        frameon=False,
        bbox_to_anchor=(0.5, -0.05),
    )

    ax.set_title(
        "Distribución de motores de producción",
        fontsize=14,
        fontweight="bold",
        color=TEAL_DARK,
        pad=15,
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "modelos_distribucion_motores.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 2: MASE comparativo por motor y padecimiento
# ============================================================================
def fig2_mase():
    excel_path = os.path.join(PROJECT, "reports/ProdDetails/tabla_333_modelos_produccion.xlsx")
    df = pd.read_excel(excel_path, sheet_name=0)

    diseases_display = ["Depresión\n(F32)", "Parkinson\n(G20)", "Alzheimer\n(G30)"]
    engines = ["DeepAR", "Prophet", "Ensemble", "Stacking"]

    # Calcular mediana MASE por motor y padecimiento
    data = {}
    for eng in engines:
        data[eng] = []
        for dis_raw in df["padecimiento"].unique():
            sub = df[(df["padecimiento"] == dis_raw) & (df["modelo_produccion"] == eng)]
            if len(sub) > 0:
                data[eng].append(sub["mase_prod"].median())
            else:
                data[eng].append(0)

    x = np.arange(len(diseases_display))
    width = 0.18
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    for i, eng in enumerate(engines):
        bars = ax.bar(
            x + i * width,
            data[eng],
            width,
            label=eng,
            color=MODEL_COLORS[eng],
            edgecolor="white",
            linewidth=0.5,
        )
        for bar, val in zip(bars, data[eng]):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.02,
                    f"{val:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    fontweight="bold",
                )

    ax.axhline(y=1.0, color=COOL_GRAY, linestyle="--", linewidth=1.2, alpha=0.8)
    ax.text(
        len(diseases_display) - 0.5,
        1.03,
        "Línea base naive (MASE=1)",
        ha="right",
        va="bottom",
        fontsize=9,
        color=COOL_GRAY,
        style="italic",
    )

    ax.set_xlabel("Padecimiento", fontsize=11, fontweight="bold")
    ax.set_ylabel("MASE (mediana)", fontsize=11, fontweight="bold")
    ax.set_title(
        "Comparativo MASE por motor y padecimiento",
        fontsize=14,
        fontweight="bold",
        color=TEAL_DARK,
        pad=12,
    )
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(diseases_display, fontsize=10)
    ax.legend(fontsize=9, frameon=True, fancybox=True, shadow=False)
    ax.set_ylim(0, max(max(v) for v in data.values()) * 1.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "modelos_comparativo_mase.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 3: Serie temporal emblemática -- Depresión Nacional
# ============================================================================
def fig3_time_series():
    boletin_path = os.path.join(PROJECT, "data/processed/dataset_boletin_epidemiologico.csv")
    boletin = pd.read_csv(boletin_path)

    # Agregar a nivel nacional
    dep = boletin[boletin["Padecimiento"] == "Depresion"]
    if len(dep) == 0:
        dep = boletin[boletin["Padecimiento"] == "Depresión"]
    dep_nac = dep.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    dep_nac = dep_nac.sort_values(["Anio", "Semana"])

    # Crear fecha a partir de año y semana
    dep_nac["ds"] = pd.to_datetime(
        dep_nac["Anio"].astype(str) + "-W" + dep_nac["Semana"].astype(str).str.zfill(2) + "-1",
        format="%G-W%V-%u",
    )
    dep_nac = dep_nac.sort_values("ds")

    # También leer forecast del tableau
    tableau = pd.read_csv(os.path.join(PROJECT, "data/processed/tableau.csv"))
    forecast = tableau[
        (tableau["padecimiento"] == "Depresión")
        & (tableau["meta_modo"] == "general")
        & (tableau["entidad"] == "Nacional")
    ].sort_values("ds")
    forecast["ds"] = pd.to_datetime(forecast["ds"])
    # Last 52 rows are the actual forecast
    forecast_portion = forecast.tail(52)

    fig, ax = plt.subplots(figsize=(12, 5), dpi=300)

    # Datos reales
    ax.plot(
        dep_nac["ds"],
        dep_nac["Casos_semana"],
        color=BURGUNDY,
        linewidth=1.0,
        alpha=0.85,
        label="Incidencia real (SINAVE)",
    )

    # Media móvil (gold)
    if len(dep_nac) > 12:
        ma = dep_nac["Casos_semana"].rolling(window=12, center=True).mean()
        ax.plot(
            dep_nac["ds"],
            ma,
            color=GOLD,
            linewidth=2.0,
            alpha=0.8,
            label="Media móvil (12 semanas)",
        )

    # Forecast
    ax.plot(
        forecast_portion["ds"],
        forecast_portion["yhat"],
        color=TEAL,
        linewidth=2.0,
        linestyle="--",
        alpha=0.9,
        label="Pronóstico (modelo productivo)",
    )

    # COVID band
    covid_start = pd.Timestamp("2020-03-01")
    covid_end = pd.Timestamp("2021-12-31")
    ax.axvspan(covid_start, covid_end, alpha=0.10, color=COOL_GRAY, label="Periodo COVID-19")

    ax.set_title(
        "Incidencia semanal de Depresión (F32) -- Serie Nacional",
        fontsize=14,
        fontweight="bold",
        color=TEAL_DARK,
        pad=12,
    )
    ax.set_xlabel("Fecha", fontsize=11)
    ax.set_ylabel("Casos semanales", fontsize=11)
    ax.legend(fontsize=9, loc="upper left", frameon=True, fancybox=True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "eda_serie_temporal.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 4: Barras horizontales -- Pronóstico por entidad
# ============================================================================
def fig4_geo_bars():
    excel_path = os.path.join(PROJECT, "reports/ProdDetails/tabla_333_modelos_produccion.xlsx")
    df = pd.read_excel(excel_path, sheet_name=0)
    dep = df[(df["padecimiento"] == "Depresión") & (df["sexo"] == "general")]
    dep_states = dep[~dep["entidad"].str.contains("Nacional|region_", case=False, na=False)]
    by_state = (
        dep_states.groupby("entidad")["casos_52_semanas_futuro"].sum().sort_values(ascending=True)
    )
    top15 = by_state.tail(15)

    fig, ax = plt.subplots(figsize=(10, 7), dpi=300)

    # Gradient from teal to burgundy
    n = len(top15)
    cmap_colors = []
    for i in range(n):
        ratio = i / (n - 1) if n > 1 else 0
        r = int(int(TEAL[1:3], 16) * (1 - ratio) + int(BURGUNDY[1:3], 16) * ratio)
        g = int(int(TEAL[3:5], 16) * (1 - ratio) + int(BURGUNDY[3:5], 16) * ratio)
        b = int(int(TEAL[5:7], 16) * (1 - ratio) + int(BURGUNDY[5:7], 16) * ratio)
        cmap_colors.append(f"#{r:02x}{g:02x}{b:02x}")

    bars = ax.barh(range(n), top15.values, color=cmap_colors, edgecolor="white", height=0.7)
    ax.set_yticks(range(n))
    # Renombrar "México" a "Estado de México" para evitar confusión
    ylabels = [e if e != "México" else "Estado de México" for e in top15.index]
    ax.set_yticklabels(ylabels, fontsize=10)

    for bar, val in zip(bars, top15.values):
        ax.text(
            bar.get_width() + max(top15.values) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{int(val):,}",
            ha="left",
            va="center",
            fontsize=9,
            fontweight="bold",
        )

    ax.set_title(
        "Pronóstico de casos a 52 semanas por entidad -- Depresión (F32)",
        fontsize=13,
        fontweight="bold",
        color=TEAL_DARK,
        pad=12,
    )
    ax.set_xlabel("Casos pronosticados (52 semanas)", fontsize=11)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(0, max(top15.values) * 1.15)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "eda_heatmap_geografico.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 5: Waterfall CRISP-ML(Q) de costos
# ============================================================================
def fig5_waterfall():
    phases = [
        "Entendimiento del\nNegocio y Datos",
        "Preparación\nde Datos",
        "Modelado",
        "Evaluación",
        "Despliegue",
        "Monitoreo\nAnual",
        "TOTAL",
    ]
    costs = [2400, 1800, 3200, 800, 600, 500, 9300]
    is_total = [False, False, False, False, False, False, True]

    colors_bars = [TEAL, BURGUNDY, TEAL, BURGUNDY, TEAL, BURGUNDY, GOLD]

    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    # Waterfall: stacked from bottom
    bottoms = []
    running = 0
    for i, c in enumerate(costs):
        if is_total[i]:
            bottoms.append(0)
        else:
            bottoms.append(running)
            running += c

    for i, (phase, cost, bottom, color) in enumerate(zip(phases, costs, bottoms, colors_bars)):
        ax.bar(i, cost, bottom=bottom, color=color, edgecolor="white", width=0.6, linewidth=1.5)
        # Value label
        label_y = bottom + cost / 2
        ax.text(
            i,
            label_y,
            f"${cost:,}",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="white",
        )

    # Connectors between bars (not to total)
    for i in range(len(costs) - 2):
        top = bottoms[i] + costs[i]
        ax.plot(
            [i + 0.3, i + 0.7],
            [top, top],
            color=COOL_GRAY,
            linewidth=0.8,
            linestyle="--",
            alpha=0.5,
        )

    ax.set_xticks(range(len(phases)))
    ax.set_xticklabels(phases, fontsize=9, ha="center")
    ax.set_ylabel("Costo estimado (USD)", fontsize=11, fontweight="bold")
    ax.set_title(
        "Inversión por fase CRISP-ML(Q)", fontsize=14, fontweight="bold", color=TEAL_DARK, pad=12
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${int(x):,}"))
    ax.set_ylim(0, 11000)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "costos_waterfall_crispml.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 6: Costos vs Beneficios (referenciada en tex)
# ============================================================================
def fig6_cost_benefit():
    fig, ax = plt.subplots(figsize=(12, 7), dpi=300)

    cost_labels = [
        "Infraestructura AWS\n($506/año)",
        "Desarrollo\n($9,300 único)",
        "Monitoreo anual\n($500/año)",
    ]
    cost_values = [-506, -9300, -500]

    benefit_labels = [
        "Ahorro farmacéutico\nestimado (5%)",
        "Optimización de\nrecursos humanos",
        "Capacidad predictiva\n52 semanas",
    ]
    benefit_values = [15000, 10000, 8000]

    # Layout: benefits at top (y=6,5,4), gap at y=3, costs at (y=2,1,0)
    benefit_y = [6, 5, 4]
    cost_y = [2, 1, 0]

    # Draw benefit bars
    for yp, val, lab in zip(benefit_y, benefit_values, benefit_labels):
        ax.barh(yp, val, color=TEAL, edgecolor="white", height=0.65)
        ax.text(
            val + 250,
            yp,
            "Alto impacto",
            ha="left",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=TEAL_DARK,
        )

    # Draw cost bars
    for yp, val, lab in zip(cost_y, cost_values, cost_labels):
        ax.barh(yp, val, color=BURGUNDY, edgecolor="white", height=0.65)
        ax.text(
            val - 200,
            yp,
            f"${abs(val):,}",
            ha="right",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=BURGUNDY,
        )

    ax.axvline(x=0, color="#333333", linewidth=1.2)

    # Y-axis labels
    all_y = cost_y + benefit_y
    all_labels = cost_labels + benefit_labels
    ax.set_yticks(all_y)
    ax.set_yticklabels(all_labels, fontsize=10)

    # Section headers
    ax.text(
        -5500,
        3.2,
        "COSTOS",
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color=BURGUNDY,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=LIGHT_RED, edgecolor=BURGUNDY, alpha=0.7),
    )
    ax.text(
        8000,
        3.2,
        "BENEFICIOS",
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color=TEAL_DARK,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=LIGHT_GREEN, edgecolor=TEAL, alpha=0.7),
    )

    # Subtle divider line
    ax.axhline(
        y=3.2, color=COOL_GRAY, linewidth=0.5, linestyle=":", alpha=0.5, xmin=0.05, xmax=0.95
    )

    ax.set_title(
        "Análisis Costo-Beneficio del Sistema",
        fontsize=15,
        fontweight="bold",
        color=TEAL_DARK,
        pad=18,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False)
    ax.set_ylim(-0.8, 7.2)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${abs(int(x)):,}"))
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "costos_vs_beneficios.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 7: Heatmap de riesgos (13 riesgos del tex, paleta IMSS)
# ============================================================================
def fig7_risk_heatmap():
    fig, ax = plt.subplots(figsize=(11, 9), dpi=300)

    prob_labels = ["Baja", "Media", "Alta"]
    impact_labels = ["Alto", "Medio", "Bajo"]

    # Paleta IMSS para severidad
    severity_colors = [
        # Low prob        Med prob         High prob
        [LIGHT_GREEN, LIGHT_YELLOW, LIGHT_YELLOW],  # Low impact
        [LIGHT_YELLOW, LIGHT_YELLOW, LIGHT_RED],  # Med impact
        [LIGHT_YELLOW, LIGHT_RED, LIGHT_RED],  # High impact
    ]
    # Reverse rows so High impact is at top
    severity_colors = severity_colors[::-1]

    # 13 riesgos del tex organizados por (row, col)
    # Rows: 0=High impact, 1=Med impact, 2=Low impact
    # Cols: 0=Low prob, 1=Med prob, 2=High prob
    risks = {
        (0, 0): ["Data poisoning", "Acceso no\nautorizado"],
        (0, 1): ["Discontinuidad\nde boletines", "Validación clínica\npendiente"],
        (0, 2): ["Concept drift\npost-pandemia"],
        (1, 0): [
            "Cumplimiento\nnormativo",
            "Adversarial\ninputs",
            "Uso ético de\npredicciones",
            "Sesgo temporal\nCOVID-19",
        ],
        (1, 1): [
            "Sobreajuste series\nbaja incidencia",
            "Explicabilidad\nDeepAR",
            "Gobernanza\ndel modelo",
        ],
        (1, 2): ["Subregistro\nepidemiológico", "Calidad variable\nentre estados"],
        (2, 0): [],
        (2, 1): [],
        (2, 2): [],
    }

    # Draw cells
    cell_w, cell_h = 1, 1
    for row in range(3):
        for col in range(3):
            rect = FancyBboxPatch(
                (col * cell_w, (2 - row) * cell_h),
                cell_w,
                cell_h,
                boxstyle="round,pad=0.02",
                facecolor=severity_colors[row][col],
                edgecolor="#BDBDBD",
                linewidth=1.5,
            )
            ax.add_patch(rect)

            # Risk labels
            cell_risks = risks.get((row, col), [])
            if cell_risks:
                text = "\n\n".join(cell_risks)
                ax.text(
                    col * cell_w + cell_w / 2,
                    (2 - row) * cell_h + cell_h / 2,
                    text,
                    ha="center",
                    va="center",
                    fontsize=7,
                    fontweight="bold",
                    color="#333333",
                    linespacing=1.1,
                )

    # Axis labels
    for i, lab in enumerate(prob_labels):
        ax.text(
            i * cell_w + cell_w / 2,
            -0.15,
            lab,
            ha="center",
            va="top",
            fontsize=11,
            fontweight="bold",
            color="#333",
        )
    for i, lab in enumerate(impact_labels):
        ax.text(
            -0.15,
            (2 - i) * cell_h + cell_h / 2,
            lab,
            ha="right",
            va="center",
            fontsize=11,
            fontweight="bold",
            color="#333",
            rotation=0,
        )

    ax.text(
        1.5,
        -0.40,
        "Probabilidad",
        ha="center",
        va="top",
        fontsize=13,
        fontweight="bold",
        color=TEAL_DARK,
    )
    ax.text(
        -0.55,
        1.5,
        "Impacto",
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color=TEAL_DARK,
        rotation=90,
    )

    ax.set_xlim(-0.6, 3.1)
    ax.set_ylim(-0.55, 3.2)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        "Matriz de Riesgos del Sistema ML", fontsize=15, fontweight="bold", color=TEAL_DARK, pad=20
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "riesgos_heatmap.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 8: Arquitectura simplificada
# ============================================================================
def fig8_architecture():
    fig, ax = plt.subplots(figsize=(14, 5), dpi=300)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 5)
    ax.axis("off")

    boxes = [
        (0.5, 2.5, "SINAVE\n(Datos)", BURGUNDY),
        (2.8, 2.5, "ETL\nPipeline", TEAL),
        (5.1, 2.5, "4 Motores\nML", GOLD),
        (7.4, 2.5, "Selección\nAutomática", TEAL_DARK),
        (9.7, 2.5, "Dashboard\nTableau", BURGUNDY),
        (12.0, 2.5, "Decisiones\nIMSS", TEAL_DARK),
    ]

    box_w, box_h = 1.8, 1.6

    for x, y, label, color in boxes:
        rect = FancyBboxPatch(
            (x, y - box_h / 2),
            box_w,
            box_h,
            boxstyle="round,pad=0.15",
            facecolor=color,
            edgecolor="white",
            linewidth=2,
            alpha=0.92,
        )
        ax.add_patch(rect)
        ax.text(
            x + box_w / 2,
            y,
            label,
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color="white",
            linespacing=1.3,
        )

    # Arrows between boxes
    arrow_props = dict(
        arrowstyle="-|>",
        color=COOL_GRAY,
        linewidth=2.0,
        mutation_scale=18,
    )
    for i in range(len(boxes) - 1):
        x1 = boxes[i][0] + box_w
        x2 = boxes[i + 1][0]
        y = boxes[i][1]
        ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops=arrow_props)

    # Sub-labels for the 4 engines
    engines_text = "Prophet | DeepAR | Ensemble | Stacking"
    ax.text(
        5.1 + box_w / 2,
        2.5 - box_h / 2 - 0.25,
        engines_text,
        ha="center",
        va="top",
        fontsize=8.5,
        color=GOLD,
        style="italic",
    )

    # Bottom caption
    caption = "Ciclo: Reentrenamiento trimestral  |  Inferencia semanal  |  Monitoreo continuo"
    ax.text(
        7,
        0.5,
        caption,
        ha="center",
        va="center",
        fontsize=11,
        color=COOL_GRAY,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#F5F5F5", edgecolor=COOL_GRAY, alpha=0.5),
    )

    ax.set_title(
        "Arquitectura MLOps Simplificada -- EpiForecast-MX",
        fontsize=14,
        fontweight="bold",
        color=TEAL_DARK,
        pad=15,
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "arquitectura_simplificada.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 9: EpiBot showcase (chat mockup)
# ============================================================================
def fig9_epibot():
    fig, ax = plt.subplots(figsize=(8, 9), dpi=300)
    ax.set_xlim(0, 8)
    ax.set_ylim(0, 9)
    ax.axis("off")
    fig.patch.set_facecolor("#F0F0F0")

    # Phone/chat frame
    frame = FancyBboxPatch(
        (0.5, 0.3),
        7.0,
        8.4,
        boxstyle="round,pad=0.2",
        facecolor="white",
        edgecolor="#CCCCCC",
        linewidth=2,
    )
    ax.add_patch(frame)

    # Header bar
    header = FancyBboxPatch(
        (0.5, 7.7),
        7.0,
        1.0,
        boxstyle="round,pad=0.1",
        facecolor=TEAL_DARK,
        edgecolor=TEAL_DARK,
        linewidth=0,
    )
    ax.add_patch(header)
    ax.text(
        4.0,
        8.2,
        "EPI Web Bot - Asistente Epidemiológico",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="white",
    )
    ax.text(
        4.0, 7.9, "IMSS | EpiForecast-MX", ha="center", va="center", fontsize=8, color="#B0D4D0"
    )

    # User bubble
    user_bubble = FancyBboxPatch(
        (2.5, 6.3),
        4.8,
        0.9,
        boxstyle="round,pad=0.15",
        facecolor="#E8E8E8",
        edgecolor="#D0D0D0",
        linewidth=1,
    )
    ax.add_patch(user_bubble)
    ax.text(
        4.9,
        6.75,
        "¿Cuál es el pronóstico de depresión\nen Jalisco?",
        ha="center",
        va="center",
        fontsize=9.5,
        color="#333333",
    )
    ax.text(7.1, 6.35, "Usuario", ha="right", va="bottom", fontsize=7, color=COOL_GRAY)

    # Bot response bubble
    bot_bubble = FancyBboxPatch(
        (0.7, 3.4),
        5.5,
        2.5,
        boxstyle="round,pad=0.15",
        facecolor="#E8F5F3",
        edgecolor=TEAL,
        linewidth=1.2,
    )
    ax.add_patch(bot_bubble)

    bot_text = (
        "Según nuestros modelos, Jalisco presenta un\n"
        "pronóstico de 9,974 casos de depresión (F32)\n"
        "para las próximas 52 semanas.\n\n"
        "Motor seleccionado: DeepAR\n"
        "SMAPE de producción: 4.2%\n"
        "MASE: 0.19 (mejor que baseline naive)"
    )
    ax.text(
        3.45,
        4.65,
        bot_text,
        ha="center",
        va="center",
        fontsize=9,
        color="#1A3A36",
        linespacing=1.4,
        family="monospace",
    )
    ax.text(
        0.9, 3.5, "EPI Bot", ha="left", va="bottom", fontsize=7, color=TEAL_DARK, fontweight="bold"
    )

    # Second user message
    user_bubble2 = FancyBboxPatch(
        (3.0, 2.2),
        4.3,
        0.8,
        boxstyle="round,pad=0.15",
        facecolor="#E8E8E8",
        edgecolor="#D0D0D0",
        linewidth=1,
    )
    ax.add_patch(user_bubble2)
    ax.text(
        5.15,
        2.6,
        "¿Y cuál es la tendencia histórica?",
        ha="center",
        va="center",
        fontsize=9.5,
        color="#333333",
    )

    # Input area
    input_area = FancyBboxPatch(
        (0.7, 0.5),
        5.6,
        0.6,
        boxstyle="round,pad=0.1",
        facecolor="#F5F5F5",
        edgecolor="#CCCCCC",
        linewidth=1,
    )
    ax.add_patch(input_area)
    ax.text(
        3.5,
        0.8,
        "Escribe tu pregunta...",
        ha="center",
        va="center",
        fontsize=9,
        color="#AAAAAA",
        style="italic",
    )

    # Send button
    send_btn = FancyBboxPatch(
        (6.5, 0.5),
        1.0,
        0.6,
        boxstyle="round,pad=0.1",
        facecolor=TEAL,
        edgecolor=TEAL,
        linewidth=0,
    )
    ax.add_patch(send_btn)
    ax.text(
        7.0, 0.8, "Enviar", ha="center", va="center", fontsize=9, fontweight="bold", color="white"
    )

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "epibot_showcase.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="#F0F0F0")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 10: Consola showcase (terminal mockup)
# ============================================================================
def fig10_consola():
    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.axis("off")
    fig.patch.set_facecolor("#F0F0F0")

    # Terminal window
    terminal_bg = "#1a1a2e"
    frame = FancyBboxPatch(
        (0.3, 0.3),
        9.4,
        7.4,
        boxstyle="round,pad=0.15",
        facecolor=terminal_bg,
        edgecolor="#333355",
        linewidth=2,
    )
    ax.add_patch(frame)

    # Title bar
    title_bar = FancyBboxPatch(
        (0.3, 7.0),
        9.4,
        0.7,
        boxstyle="round,pad=0.08",
        facecolor=BURGUNDY,
        edgecolor=BURGUNDY,
        linewidth=0,
    )
    ax.add_patch(title_bar)
    ax.text(
        5.0,
        7.35,
        "EPI Consola v2.0 -- Centro de Comando IMSS",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="white",
        family="monospace",
    )

    # Traffic light dots
    for i, c in enumerate(["#FF5F56", "#FFBD2E", "#27C93F"]):
        ax.add_patch(plt.Circle((0.7 + i * 0.3, 7.35), 0.08, color=c))

    # Menu content
    y_start = 6.5
    sections = [
        (
            "Datos y preprocesamiento",
            TEAL,
            [
                ("get-dataset", "Descargar boletín SINAVE", "safe"),
                ("preprocess", "Pipeline completo de limpieza", "safe"),
                ("filter", "Filtrar por padecimiento", "safe"),
            ],
        ),
        (
            "Entrenamiento",
            GOLD,
            [
                ("train-all", "Entrenar los 4 motores", "modify"),
                ("train-sagemaker", "DeepAR en GPU (AWS)", "modify"),
            ],
        ),
        (
            "Predicción y reportes",
            "#FF6F00",
            [
                ("predict-all", "Generar pronósticos (4 motores)", "modify"),
                ("tableau", "Construir dataset Tableau", "safe"),
                ("compare", "Comparativa Real vs Modelos", "safe"),
            ],
        ),
        (
            "Monitoreo",
            "#880E4F",
            [
                ("data-push", "Subir datos a S3 (DVC)", "modify"),
                ("quality", "Lint + Typecheck + 855 tests", "safe"),
            ],
        ),
    ]

    risk_colors = {"safe": "#27C93F", "modify": "#FFBD2E", "destructive": "#FF5F56"}
    y = y_start

    for section_name, section_color, commands in sections:
        # Section header
        ax.text(
            0.8,
            y,
            f"  {section_name}",
            fontsize=10,
            fontweight="bold",
            color=section_color,
            family="monospace",
            va="center",
        )
        y -= 0.35

        for cmd, desc, risk in commands:
            dot_color = risk_colors[risk]
            ax.add_patch(plt.Circle((1.0, y), 0.06, color=dot_color))
            ax.text(
                1.3,
                y,
                f"make {cmd}",
                fontsize=8.5,
                color="#00FF88",
                family="monospace",
                va="center",
            )
            ax.text(5.5, y, desc, fontsize=8.5, color="#AAAACC", family="monospace", va="center")
            y -= 0.3
        y -= 0.15

    # Legend at bottom
    ax.text(
        1.0,
        0.8,
        "Clasificación de riesgo:",
        fontsize=8,
        color="#AAAACC",
        family="monospace",
        va="center",
    )
    for i, (label, color) in enumerate(
        [("Seguro", "#27C93F"), ("Modificador", "#FFBD2E"), ("Destructivo", "#FF5F56")]
    ):
        x_pos = 4.5 + i * 2.0
        ax.add_patch(plt.Circle((x_pos, 0.8), 0.06, color=color))
        ax.text(x_pos + 0.2, 0.8, label, fontsize=8, color=color, family="monospace", va="center")

    # Footer
    ax.text(
        5.0,
        0.45,
        "55+ targets | Branding IMSS 2026 | Aprobación por nivel de riesgo",
        ha="center",
        va="center",
        fontsize=7.5,
        color="#666688",
        family="monospace",
    )

    fig.tight_layout()
    path = os.path.join(OUT_DIR, "consola_showcase.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="#F0F0F0")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# COPIES: Screenshots existentes
# ============================================================================
def copy_screenshots():
    copies = [
        (
            os.path.join(
                PROJECT, "reports/ConclusionesClave/03_TableauDashboardTableroDeModelos.png"
            ),
            os.path.join(OUT_DIR, "dashboard_showcase.png"),
        ),
    ]
    for src, dst in copies:
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"  [OK] {dst} (copiado desde {os.path.basename(src)})")
        else:
            print(f"  [WARN] No encontrado: {src}")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("Generando figuras para Resumen Ejecutivo - Avance 7\n")

    print("[1/9] Distribución de motores (donut)...")
    fig1_donut()

    print("[2/9] Comparativo MASE por motor...")
    fig2_mase()

    print("[3/9] Serie temporal Depresión Nacional...")
    fig3_time_series()

    print("[4/9] Pronóstico por entidad (barras)...")
    fig4_geo_bars()

    print("[5/9] Waterfall CRISP-ML(Q)...")
    fig5_waterfall()

    print("[6/9] Costos vs Beneficios...")
    fig6_cost_benefit()

    print("[7/9] Matriz de riesgos...")
    fig7_risk_heatmap()

    print("[8/9] Arquitectura simplificada...")
    fig8_architecture()

    print("[9/10] EpiBot showcase (mockup)...")
    fig9_epibot()

    print("[10/10] Consola showcase (mockup)...")
    fig10_consola()

    print("\n[11] Copiando screenshots existentes...")
    copy_screenshots()

    print("\n" + "=" * 60)
    print("Verificación final de archivos:")
    print("=" * 60)
    expected = [
        "modelos_distribucion_motores.png",
        "modelos_comparativo_mase.png",
        "eda_serie_temporal.png",
        "eda_heatmap_geografico.png",
        "costos_waterfall_crispml.png",
        "costos_vs_beneficios.png",
        "riesgos_heatmap.png",
        "arquitectura_simplificada.png",
        "epibot_showcase.png",
        "consola_showcase.png",
        "dashboard_showcase.png",
    ]
    all_ok = True
    for fname in expected:
        fpath = os.path.join(OUT_DIR, fname)
        if os.path.exists(fpath):
            size_kb = os.path.getsize(fpath) / 1024
            print(f"  [OK] {fname:45s} {size_kb:8.1f} KB")
        else:
            print(f"  [MISSING] {fname}")
            all_ok = False

    if all_ok:
        print(f"\nTodas las {len(expected)} figuras generadas correctamente.")
    else:
        print("\nAlgunas figuras no se generaron.")
