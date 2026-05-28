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

# Rutas derivadas de la ubicacion del script (portables, independientes del cwd).
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(OUT_DIR))
os.makedirs(OUT_DIR, exist_ok=True)

# Fijar el cwd a la raiz del proyecto: la deserializacion de los modelos Ensemble
# (paso 16) importa epiforecast.utils.config, que busca config/base.yaml relativo
# al cwd. Sin esto, ejecutar desde otra carpeta mata el proceso con exit 1.
os.chdir(PROJECT)

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


def fig_comparativo_smape():
    """Comparativo SMAPE brutal: boxplots + jitter + KPI por motor y padecimiento."""
    from matplotlib.lines import Line2D

    excel_path = os.path.join(PROJECT, "reports/ProdDetails/tabla_333_modelos_produccion.xlsx")
    df = pd.read_excel(excel_path, sheet_name=0)

    engines = ["DeepAR", "Prophet", "Ensemble", "Stacking"]
    smape_cols = {
        "DeepAR": "deepar_smape",
        "Prophet": "prophet_smape",
        "Ensemble": "ensemble_smape",
        "Stacking": "stacking_smape",
    }
    diseases_raw = ["Depresi\u00f3n", "Parkinson", "Alzheimer"]
    diseases_display = ["Depresi\u00f3n (F32)", "Parkinson (G20)", "Alzheimer (G30)"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 6.5), sharey=True, gridspec_kw={"wspace": 0.08})

    # Zonas de rendimiento (fondo)
    for ax in axes:
        ax.axhspan(0, 20, color="#E6F4EA", alpha=0.4, zorder=0)  # excelente
        ax.axhspan(20, 50, color="#FEF7E0", alpha=0.3, zorder=0)  # aceptable
        ax.axhspan(50, 100, color="#FDE8E8", alpha=0.2, zorder=0)  # pobre
        ax.axhline(y=20, color=TEAL, linewidth=0.5, linestyle=":", alpha=0.4)
        ax.axhline(y=50, color=GOLD, linewidth=0.5, linestyle=":", alpha=0.4)
        ax.axhline(y=100, color=BURGUNDY, linewidth=0.8, linestyle="--", alpha=0.5)

    for d_idx, (d_raw, d_disp) in enumerate(zip(diseases_raw, diseases_display)):
        ax = axes[d_idx]
        sub = df[df["padecimiento"] == d_raw]

        box_data = []
        medians = []
        for eng in engines:
            col = smape_cols[eng]
            vals = sub[col].dropna().values
            # Clip at 200 for visualization (outliers still counted)
            box_data.append(np.clip(vals, 0, 200))
            medians.append(np.median(vals) if len(vals) > 0 else 0)

        positions = np.arange(len(engines))
        colors_list = [MODEL_COLORS[e] for e in engines]

        # Boxplots
        bp = ax.boxplot(
            box_data,
            positions=positions,
            widths=0.5,
            patch_artist=True,
            showfliers=False,
            zorder=3,
            medianprops=dict(color="white", linewidth=2),
            whiskerprops=dict(color=COOL_GRAY, linewidth=0.8),
            capprops=dict(color=COOL_GRAY, linewidth=0.8),
        )
        for patch, color in zip(bp["boxes"], colors_list):
            patch.set_facecolor(color)
            patch.set_alpha(0.85)
            patch.set_edgecolor("white")
            patch.set_linewidth(0.8)

        # Jitter points
        rng = np.random.default_rng(42)
        for e_idx, eng in enumerate(engines):
            col = smape_cols[eng]
            vals = sub[col].dropna().values
            jitter = rng.uniform(-0.15, 0.15, size=len(vals))
            ax.scatter(
                positions[e_idx] + jitter,
                np.clip(vals, 0, 200),
                s=8,
                color=colors_list[e_idx],
                alpha=0.3,
                edgecolors="none",
                zorder=2,
            )

        # Median labels with white background for readability
        for e_idx, (eng, med) in enumerate(zip(engines, medians)):
            ax.text(
                positions[e_idx],
                min(med, 200) + 4,
                f"{med:.0f}%",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color=colors_list[e_idx],
                zorder=5,
                bbox=dict(
                    boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85
                ),
            )

        # Winner badge (lowest median)
        best_idx = int(np.argmin(medians))
        best_val = medians[best_idx]
        ax.annotate(
            f"\u2605 {best_val:.0f}%",
            xy=(positions[best_idx], min(best_val, 200)),
            xytext=(positions[best_idx], min(best_val, 200) - 18),
            ha="center",
            fontsize=11,
            fontweight="bold",
            color=GOLD,
            arrowprops=dict(arrowstyle="-", color=GOLD, lw=1.5),
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=GOLD, linewidth=1.5),
            zorder=6,
        )

        ax.set_title(d_disp, fontsize=12, fontweight="bold", color=TEAL_DARK, pad=10)
        ax.set_xticks(positions)
        ax.set_xticklabels(engines, fontsize=9, fontweight="bold")
        ax.tick_params(axis="y", labelsize=8, colors=COOL_GRAY)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        if d_idx > 0:
            ax.spines["left"].set_visible(False)
            ax.tick_params(left=False)

    axes[0].set_ylabel("SMAPE (%)", fontsize=11, fontweight="bold", color=TEAL_DARK)
    axes[0].set_ylim(0, 210)

    # Zone labels on the right edge
    axes[2].text(
        3.7,
        10,
        "Excelente\n(<20%)",
        fontsize=7,
        color=TEAL_DARK,
        ha="left",
        va="center",
        fontstyle="italic",
    )
    axes[2].text(
        3.7,
        35,
        "Aceptable\n(20-50%)",
        fontsize=7,
        color=GOLD,
        ha="left",
        va="center",
        fontstyle="italic",
    )
    axes[2].text(
        3.7,
        75,
        "Pobre\n(50-100%)",
        fontsize=7,
        color=BURGUNDY,
        ha="left",
        va="center",
        fontstyle="italic",
        alpha=0.7,
    )
    axes[2].text(
        3.7,
        150,
        ">100%\n(peor que\nazar)",
        fontsize=7,
        color=BURGUNDY,
        ha="left",
        va="center",
        fontstyle="italic",
        alpha=0.5,
    )

    # KPI strip at the top
    global_med = df["smape_prod"].median()
    pct_30 = (df["smape_prod"] < 30).mean() * 100
    deepar_med = df["deepar_smape"].median()
    fig.text(
        0.14,
        0.95,
        f"SMAPE global: {global_med:.0f}%",
        fontsize=11,
        fontweight="bold",
        color=TEAL_DARK,
        ha="left",
    )
    fig.text(
        0.40,
        0.95,
        f"Modelos <30%: {pct_30:.0f}%",
        fontsize=11,
        fontweight="bold",
        color=TEAL,
        ha="left",
    )
    fig.text(
        0.66,
        0.95,
        f"Mejor motor (DeepAR): mediana {deepar_med:.0f}%",
        fontsize=11,
        fontweight="bold",
        color=MODEL_COLORS["DeepAR"],
        ha="left",
    )

    fig.suptitle(
        "Comparativo SMAPE por motor y padecimiento (333 modelos)",
        fontsize=14,
        fontweight="bold",
        color=TEAL_DARK,
        y=1.02,
    )

    fig.subplots_adjust(top=0.88, bottom=0.08, left=0.06, right=0.92)
    path = os.path.join(OUT_DIR, "modelos_comparativo_smape.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"    -> {path} ({os.path.getsize(path) / 1024:.0f} KB)")


# ============================================================================
# FIGURE 3: Serie temporal emblemática -- Depresión Nacional
# ============================================================================
def _eda_large(padecimiento_raw, padecimiento_tableau, title, out_name):
    """Genera una figura EDA grande con leyenda al pie (fuera del area de datos)."""
    boletin_path = os.path.join(PROJECT, "data/processed/dataset_boletin_epidemiologico.csv")
    boletin = pd.read_csv(boletin_path)

    sub = boletin[boletin["Padecimiento"] == padecimiento_raw]
    if len(sub) == 0:
        sub = boletin[
            boletin["Padecimiento"].str.contains(padecimiento_raw[:5], case=False, na=False)
        ]
    nac = sub.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    nac = nac.sort_values(["Anio", "Semana"])
    nac["ds"] = pd.to_datetime(
        nac["Anio"].astype(str) + "-W" + nac["Semana"].astype(str).str.zfill(2) + "-1",
        format="%G-W%V-%u",
    )
    nac = nac.sort_values("ds")

    tableau = pd.read_csv(os.path.join(PROJECT, "data/processed/tableau.csv"))
    fc = tableau[
        (tableau["padecimiento"] == padecimiento_tableau)
        & (tableau["meta_modo"] == "general")
        & (tableau["entidad"] == "Nacional")
    ].sort_values("ds")
    fc["ds"] = pd.to_datetime(fc["ds"])
    fc_tail = fc.tail(52)

    fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
    ax.plot(
        nac["ds"],
        nac["Casos_semana"],
        color=BURGUNDY,
        linewidth=1.0,
        alpha=0.85,
        label="Incidencia real (SINAVE)",
    )
    if len(nac) > 12:
        ma = nac["Casos_semana"].rolling(window=12, center=True).mean()
        ax.plot(
            nac["ds"], ma, color=GOLD, linewidth=2.0, alpha=0.8, label="Media movil (12 semanas)"
        )
    ax.plot(
        fc_tail["ds"],
        fc_tail["yhat"],
        color=TEAL,
        linewidth=2.0,
        linestyle="--",
        alpha=0.9,
        label="Pronostico (modelo productivo)",
    )

    covid_start = pd.Timestamp("2020-03-15")
    covid_end = pd.Timestamp("2022-09-22")
    ax.axvspan(covid_start, covid_end, alpha=0.10, color=COOL_GRAY, label="Periodo COVID-19")

    ax.set_title(title, fontsize=14, fontweight="bold", color=TEAL_DARK, pad=12)
    ax.set_xlabel("")
    ax.set_ylabel("Casos semanales", fontsize=11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))

    # Legend well below the plot area — no overlap with axis
    ax.legend(
        fontsize=9,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.10),
        ncol=4,
        frameon=True,
        fancybox=True,
        shadow=False,
    )
    fig.subplots_adjust(bottom=0.20)
    path = os.path.join(OUT_DIR, out_name)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


def fig3_time_series():
    _eda_large(
        "Depresión",
        "Depresión",
        "Incidencia semanal de Depresion (F32) -- Serie Nacional",
        "eda_serie_temporal.png",
    )


def fig3b_parkinson():
    _eda_large(
        "Parkinson",
        "Parkinson",
        "Incidencia semanal de Parkinson (G20) -- Serie Nacional",
        "eda_serie_parkinson.png",
    )


def fig3c_alzheimer():
    _eda_large(
        "Alzheimer",
        "Alzheimer",
        "Incidencia semanal de Alzheimer (G30) -- Serie Nacional",
        "eda_serie_alzheimer.png",
    )


# ============================================================================
# HELPER: Serie temporal compacta (para layout horizontal 1/3 de pagina)
# ============================================================================
def _eda_compact(padecimiento_raw, padecimiento_tableau, code, color_accent, out_name):
    """Genera una figura EDA compacta para un padecimiento."""
    boletin_path = os.path.join(PROJECT, "data/processed/dataset_boletin_epidemiologico.csv")
    boletin = pd.read_csv(boletin_path)

    sub = boletin[boletin["Padecimiento"] == padecimiento_raw]
    if len(sub) == 0:
        sub = boletin[
            boletin["Padecimiento"].str.contains(padecimiento_raw[:5], case=False, na=False)
        ]
    nac = sub.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    nac = nac.sort_values(["Anio", "Semana"])
    nac["ds"] = pd.to_datetime(
        nac["Anio"].astype(str) + "-W" + nac["Semana"].astype(str).str.zfill(2) + "-1",
        format="%G-W%V-%u",
    )
    nac = nac.sort_values("ds")

    tableau = pd.read_csv(os.path.join(PROJECT, "data/processed/tableau.csv"))
    fc = tableau[
        (tableau["padecimiento"] == padecimiento_tableau)
        & (tableau["meta_modo"] == "general")
        & (tableau["entidad"] == "Nacional")
    ].sort_values("ds")
    fc["ds"] = pd.to_datetime(fc["ds"])
    fc_tail = fc.tail(52)

    fig, ax = plt.subplots(figsize=(6, 4), dpi=300)
    ax.plot(nac["ds"], nac["Casos_semana"], color=BURGUNDY, linewidth=0.8, alpha=0.8)
    if len(nac) > 12:
        ma = nac["Casos_semana"].rolling(window=12, center=True).mean()
        ax.plot(nac["ds"], ma, color=GOLD, linewidth=1.8, alpha=0.8)
    ax.plot(fc_tail["ds"], fc_tail["yhat"], color=TEAL, linewidth=1.8, linestyle="--", alpha=0.9)

    covid_start = pd.Timestamp("2020-03-15")
    covid_end = pd.Timestamp("2022-09-22")
    ax.axvspan(covid_start, covid_end, alpha=0.08, color=COOL_GRAY)

    ax.set_title(
        f"{padecimiento_tableau} ({code})",
        fontsize=12,
        fontweight="bold",
        color=color_accent,
        pad=8,
    )
    ax.set_xlabel("")
    ax.set_ylabel("Casos/semana", fontsize=9)
    ax.tick_params(axis="both", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))

    # Leyenda compacta solo en la primera figura
    if "epresi" in padecimiento_raw:
        from matplotlib.lines import Line2D

        handles = [
            Line2D([0], [0], color=BURGUNDY, lw=1, label="Real"),
            Line2D([0], [0], color=GOLD, lw=1.8, label="Media movil"),
            Line2D([0], [0], color=TEAL, lw=1.8, ls="--", label="Pronostico"),
            mpatches.Patch(color=COOL_GRAY, alpha=0.15, label="COVID-19"),
        ]
        ax.legend(
            handles=handles, fontsize=7, loc="upper left", frameon=True, fancybox=True, ncol=2
        )

    fig.tight_layout()
    path = os.path.join(OUT_DIR, out_name)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


def fig3_eda_compact():
    """Genera las 3 figuras EDA compactas para layout horizontal."""
    _eda_compact("Depresión", "Depresión", "F32", BURGUNDY, "eda_compact_depresion.png")
    _eda_compact("Parkinson", "Parkinson", "G20", TEAL_DARK, "eda_compact_parkinson.png")
    _eda_compact("Alzheimer", "Alzheimer", "G30", GOLD, "eda_compact_alzheimer.png")


# ============================================================================
# FIGURE EDA-GENERO: Distribucion por sexo -- datos reales del boletin SINAVE
# ============================================================================
def fig_eda_genero():
    """Butterfly chart con datos REALES del boletin (Acumulado_hombres/mujeres 2025)."""
    boletin_path = os.path.join(PROJECT, "data/processed/dataset_boletin_epidemiologico.csv")
    df = pd.read_csv(boletin_path)

    pads = ["Depresion", "Parkinson", "Alzheimer"]
    codes = ["F32", "G20", "G30"]
    pad_names_raw = ["Depresion", "Parkinson", "Alzheimer"]
    hombres = []
    mujeres = []
    pct_mujeres = []

    anio = 2025
    for pad in pad_names_raw:
        sub = df[(df["Padecimiento"] == pad) & (df["Anio"] == anio)]
        if len(sub) == 0:
            sub = df[
                df["Padecimiento"].str.contains(pad[:5], case=False, na=False)
                & (df["Anio"] == anio)
            ]
        # Acumulado is cumulative — max per state = annual total
        by_state = sub.groupby("Entidad")[["Acumulado_hombres", "Acumulado_mujeres"]].max()
        h = by_state["Acumulado_hombres"].sum()
        m = by_state["Acumulado_mujeres"].sum()
        hombres.append(h)
        mujeres.append(m)
        pct_mujeres.append(m / (h + m) * 100 if (h + m) > 0 else 50)

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    y = np.arange(len(pads))
    bar_h = 0.35

    bars_h = ax.barh(
        y + bar_h / 2,
        [-v for v in hombres],
        bar_h,
        color=TEAL,
        edgecolor="white",
        linewidth=0.5,
        label="Hombres",
    )
    bars_m = ax.barh(
        y - bar_h / 2,
        mujeres,
        bar_h,
        color=BURGUNDY,
        edgecolor="white",
        linewidth=0.5,
        label="Mujeres",
    )

    for i, (h, m, pct) in enumerate(zip(hombres, mujeres, pct_mujeres)):
        ax.text(
            -h - max(hombres) * 0.02,
            i + bar_h / 2,
            f"{int(h):,}",
            ha="right",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=TEAL_DARK,
        )
        ax.text(
            m + max(mujeres) * 0.02,
            i - bar_h / 2,
            f"{int(m):,}  ({pct:.0f}%)",
            ha="left",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=BURGUNDY,
        )

    ax.axvline(0, color="#333333", linewidth=1.2)
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{p}\n({c})" for p, c in zip(pads, codes)], fontsize=11, fontweight="bold"
    )
    ax.set_title(
        f"Distribucion de casos por sexo -- Datos reales del boletin SINAVE ({anio})",
        fontsize=13,
        fontweight="bold",
        color=TEAL_DARK,
        pad=15,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{abs(int(x)):,}"))
    ax.set_xlabel("")

    ax.legend(
        fontsize=10,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=2,
        frameon=True,
        fancybox=True,
    )
    fig.subplots_adjust(bottom=0.18)
    path = os.path.join(OUT_DIR, "eda_genero_butterfly.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE EDA-MAPA: Mapa coropletico de Mexico -- datos reales del boletin
# ============================================================================
def fig_eda_mapa():
    """Mapa de la Republica Mexicana con incidencia real por entidad (boletin 2025)."""
    import geopandas as gpd
    from matplotlib.colors import LinearSegmentedColormap

    boletin_path = os.path.join(PROJECT, "data/processed/dataset_boletin_epidemiologico.csv")
    df = pd.read_csv(boletin_path)
    geojson_path = os.path.join(PROJECT, "data/utils/mexico_states.geojson")
    gdf = gpd.read_file(geojson_path)

    # Map: "Distrito Federal" -> "Ciudad de México" in boletin data
    df["Entidad"] = df["Entidad"].replace({"Distrito Federal": "Ciudad de Mexico"})

    # Aggregate the 3 diseases for 2025 (annual total = max of cumulative per state)
    anio = 2025
    sub = df[df["Anio"] == anio]
    by_state = sub.groupby("Entidad")[["Acumulado_hombres", "Acumulado_mujeres"]].max()
    by_state["total"] = by_state.sum(axis=1)
    state_totals = by_state["total"].to_dict()

    # Match GeoJSON names to boletin — "Ciudad de México" matches both
    gdf["casos"] = gdf["name"].map(state_totals).fillna(0)

    vmin = gdf["casos"].min()
    vmax = gdf["casos"].max()
    cmap = LinearSegmentedColormap.from_list("imss", ["#E6F4EA", "#8DC9C3", TEAL, GOLD, BURGUNDY])

    fig, ax = plt.subplots(figsize=(14, 9), dpi=300)
    gdf.plot(
        column="casos",
        cmap=cmap,
        edgecolor="#FFFFFF",
        linewidth=0.6,
        ax=ax,
        legend=False,
        vmin=vmin,
        vmax=vmax,
    )

    # State labels with abbreviations
    abbrevs = {
        "Baja California": "BC",
        "Baja California Sur": "BCS",
        "Ciudad de Mexico": "CDMX",
        "San Luis Potosi": "SLP",
        "Nuevo Leon": "NL",
        "Quintana Roo": "QR",
        "Aguascalientes": "AGS",
        "Chihuahua": "CHIH",
        "Coahuila": "COAH",
        "Tamaulipas": "TAM",
        "Guanajuato": "GTO",
        "Michoacan": "MICH",
        "Queretaro": "QRO",
        "Veracruz": "VER",
        "Guerrero": "GRO",
        "Mexico": "MEX",
        "Tlaxcala": "TLAX",
        "Morelos": "MOR",
        "Tabasco": "TAB",
        "Campeche": "CAM",
        "Yucatan": "YUC",
        "Chiapas": "CHIS",
        "Oaxaca": "OAX",
        "Puebla": "PUE",
        "Hidalgo": "HGO",
        "Colima": "COL",
        "Nayarit": "NAY",
        "Sinaloa": "SIN",
        "Sonora": "SON",
        "Durango": "DGO",
        "Zacatecas": "ZAC",
        "Jalisco": "JAL",
        "Durango": "DGO",
    }

    for _, row in gdf.iterrows():
        name = row["name"]
        # Normalize name for abbreviation lookup (strip accents)
        import unicodedata

        name_norm = unicodedata.normalize("NFD", name)
        name_norm = "".join(c for c in name_norm if unicodedata.category(c) != "Mn")
        ab = abbrevs.get(name_norm, name[:3].upper())
        centroid = row.geometry.centroid
        val = int(row["casos"])
        # Only label states large enough
        ax.annotate(
            f"{ab}\n{val:,}",
            xy=(centroid.x, centroid.y),
            ha="center",
            va="center",
            fontsize=5.5,
            fontweight="bold",
            color="#222222",
            path_effects=[
                __import__("matplotlib.patheffects", fromlist=["withStroke"]).withStroke(
                    linewidth=2, foreground="white"
                )
            ],
        )

    ax.axis("off")
    ax.set_title(
        "Incidencia acumulada por entidad federativa (3 padecimientos)\n"
        f"Datos reales del boletin SINAVE -- {anio}",
        fontsize=14,
        fontweight="bold",
        color=TEAL_DARK,
        pad=15,
    )

    # Colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.035, pad=0.02, aspect=45)
    cbar.set_label("Casos acumulados anuales (todos los padecimientos)", fontsize=10)
    cbar.ax.tick_params(labelsize=8)
    cbar.ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{int(x):,}"))

    path = os.path.join(OUT_DIR, "eda_mapa_mexico.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE EDA-ALERTA: Estados con reporte intermitente (semanas en cero)
# ============================================================================
def fig_eda_alerta_ceros():
    """Tabla visual de estados con reporte intermitente o bajo volumen."""
    boletin_path = os.path.join(PROJECT, "data/processed/dataset_boletin_epidemiologico.csv")
    df = pd.read_csv(boletin_path)
    df["Entidad"] = df["Entidad"].replace({"Distrito Federal": "Ciudad de Mexico"})

    anio = 2025
    max_sem = df[df["Anio"] == anio]["Semana"].max()

    rows = []
    for pad in ["Parkinson", "Alzheimer"]:
        sub = df[
            (df["Padecimiento"].str.contains(pad[:5], case=False, na=False)) & (df["Anio"] == anio)
        ]
        by_ent = sub.groupby("Entidad").agg(
            total=("Casos_semana", "sum"),
            semanas_cero=("Casos_semana", lambda x: (x == 0).sum()),
        )
        by_ent["pct_cero"] = (by_ent["semanas_cero"] / max_sem * 100).round(1)
        # Flag states with >50% zero-weeks
        alertas = by_ent[by_ent["pct_cero"] > 50].sort_values("pct_cero", ascending=False)
        for ent, row in alertas.iterrows():
            rows.append(
                {
                    "Padecimiento": pad,
                    "Entidad": ent,
                    "Casos anuales": int(row["total"]),
                    "Semanas en cero": int(row["semanas_cero"]),
                    "% semanas sin reporte": row["pct_cero"],
                }
            )

    if not rows:
        print("  [SKIP] No hay alertas de reporte intermitente")
        return

    alert_df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(12, max(4, 0.5 * len(rows) + 2.5)), dpi=300)
    ax.axis("off")

    # Title
    ax.set_title(
        f"Alerta de calidad: entidades con reporte intermitente ({anio})\n"
        f"Estados con mas del 50% de semanas sin casos reportados ({max_sem} semanas epidemiologicas)",
        fontsize=13,
        fontweight="bold",
        color=BURGUNDY,
        pad=20,
        loc="left",
    )

    col_labels = [
        "Padecimiento",
        "Entidad",
        "Casos\nanuales",
        "Semanas\nen cero",
        f"% sin reporte\n(de {max_sem} sem.)",
    ]
    col_widths = [0.15, 0.25, 0.15, 0.15, 0.20]

    # Build cell text
    cell_text = []
    cell_colors = []
    for _, r in alert_df.iterrows():
        pct = r["% semanas sin reporte"]
        if pct >= 80:
            bg = LIGHT_RED
        elif pct >= 65:
            bg = LIGHT_YELLOW
        else:
            bg = "#FFF8E1"
        cell_text.append(
            [
                r["Padecimiento"],
                r["Entidad"],
                f"{r['Casos anuales']:,}",
                f"{r['Semanas en cero']}/{max_sem}",
                f"{pct:.0f}%",
            ]
        )
        cell_colors.append([bg] * 5)

    table = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        colWidths=col_widths,
        cellColours=cell_colors,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.6)

    # Style header
    for j in range(len(col_labels)):
        cell = table[0, j]
        cell.set_facecolor(TEAL_DARK)
        cell.set_text_props(color="white", fontweight="bold", fontsize=9)
        cell.set_edgecolor("white")

    # Style body cells
    for i in range(1, len(cell_text) + 1):
        for j in range(len(col_labels)):
            cell = table[i, j]
            cell.set_edgecolor("#E0E0E0")
            if j == 4:  # % column — bold red for high values
                pct_val = alert_df.iloc[i - 1]["% semanas sin reporte"]
                if pct_val >= 80:
                    cell.set_text_props(fontweight="bold", color=BURGUNDY)
                elif pct_val >= 65:
                    cell.set_text_props(fontweight="bold", color="#B8860B")

    # Footer note
    fig.text(
        0.05,
        0.02,
        "Fuente: Boletin Epidemiologico SINAVE. El reporte intermitente puede indicar "
        "subregistro o baja prevalencia real en la entidad.",
        fontsize=8,
        color=COOL_GRAY,
        style="italic",
    )

    path = os.path.join(OUT_DIR, "eda_alerta_ceros.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 4: Barras horizontales -- Incidencia real por entidad (boletin)
# ============================================================================
def fig4_geo_bars():
    """Top 15 entidades por incidencia real de Depresion (boletin SINAVE 2025)."""
    boletin_path = os.path.join(PROJECT, "data/processed/dataset_boletin_epidemiologico.csv")
    df = pd.read_csv(boletin_path)
    df["Entidad"] = df["Entidad"].replace({"Distrito Federal": "Ciudad de Mexico"})

    anio = 2025
    dep = df[
        (df["Padecimiento"].str.contains("epresi", case=False, na=False)) & (df["Anio"] == anio)
    ]
    # Acumulado is cumulative — max per state = annual total
    by_state = dep.groupby("Entidad")[["Acumulado_hombres", "Acumulado_mujeres"]].max()
    by_state["total"] = by_state.sum(axis=1)
    by_state = by_state["total"].sort_values(ascending=True)
    top15 = by_state.tail(15)

    fig, ax = plt.subplots(figsize=(10, 7), dpi=300)

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
    ylabels = [e if e != "Mexico" else "Estado de Mexico" for e in top15.index]
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
        f"Top 15 entidades por incidencia de Depresion (F32) -- Boletin SINAVE {anio}",
        fontsize=13,
        fontweight="bold",
        color=TEAL_DARK,
        pad=12,
    )
    ax.set_xlabel("Casos acumulados anuales", fontsize=11)
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
# FIGURE 11: Feature Engineering Pipeline Diagram
# ============================================================================
def fig_feature_pipeline():
    fig, ax = plt.subplots(figsize=(14, 6), dpi=300)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6)
    ax.axis("off")

    # ---- Main flow (top row) ----
    main_boxes = [
        (0.3, 4.2, "Serie Temporal\nCruda", BURGUNDY),
        (3.6, 4.2, "Limpieza\ny Outliers", TEAL),
        (6.9, 4.2, "Features\nTemporales", GOLD),
        (10.8, 4.2, "20 Features\n(conteos)", TEAL_DARK),
    ]
    box_w, box_h = 2.4, 1.2

    for x, y, label, color in main_boxes:
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

    # Arrows between main boxes
    arrow_props = dict(
        arrowstyle="-|>",
        color=COOL_GRAY,
        linewidth=2.0,
        mutation_scale=18,
    )
    for i in range(len(main_boxes) - 1):
        x1 = main_boxes[i][0] + box_w
        x2 = main_boxes[i + 1][0]
        y = main_boxes[i][1]
        ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops=arrow_props)

    # Sub-items below "Features Temporales"
    sub_text = "7 lags, 5 rolling means, volatilidad,\ncalendario, ciclicos, COVID flag"
    ax.text(
        6.9 + box_w / 2,
        4.2 - box_h / 2 - 0.2,
        sub_text,
        ha="center",
        va="top",
        fontsize=8,
        color=GOLD,
        style="italic",
        linespacing=1.4,
    )

    # ---- Second row ----
    # Box A: INEGI Demograficos
    bx_a = (1.5, 2.0)
    rect_a = FancyBboxPatch(
        (bx_a[0], bx_a[1] - 0.6),
        2.4,
        1.2,
        boxstyle="round,pad=0.15",
        facecolor=IMSS_BLUE,
        edgecolor="white",
        linewidth=2,
        alpha=0.92,
    )
    ax.add_patch(rect_a)
    ax.text(
        bx_a[0] + 1.2,
        bx_a[1],
        "INEGI\nDemograficos",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color="white",
        linespacing=1.3,
    )

    # Arrow from INEGI up to "Limpieza y Outliers"
    ax.annotate(
        "",
        xy=(3.6 + box_w / 2, 4.2 - box_h / 2),
        xytext=(bx_a[0] + 1.2, bx_a[1] + 0.6),
        arrowprops=dict(
            arrowstyle="-|>",
            color=IMSS_BLUE,
            linewidth=1.8,
            mutation_scale=16,
            connectionstyle="arc3,rad=-0.15",
        ),
    )
    ax.text(
        bx_a[0] + 1.2,
        bx_a[1] - 0.6 - 0.15,
        "Contexto demografico por entidad",
        ha="center",
        va="top",
        fontsize=7.5,
        color=IMSS_BLUE,
        style="italic",
    )

    # Box B: 4 Regiones Geograficas
    bx_b_x, bx_b_y = 6.0, 2.0
    rect_b = FancyBboxPatch(
        (bx_b_x, bx_b_y - 0.6),
        2.4,
        1.2,
        boxstyle="round,pad=0.15",
        facecolor=BURGUNDY,
        edgecolor="white",
        linewidth=2,
        alpha=0.85,
    )
    ax.add_patch(rect_b)
    ax.text(
        bx_b_x + 1.2,
        bx_b_y,
        "4 Regiones\nGeograficas",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color="white",
        linespacing=1.3,
    )
    ax.text(
        bx_b_x + 1.2,
        bx_b_y - 0.6 - 0.15,
        "Norte, Occidente, Centro, Sureste",
        ha="center",
        va="top",
        fontsize=7.5,
        color=BURGUNDY,
        style="italic",
    )

    # Box C: Agrupacion Regional
    bx_c_x, bx_c_y = 9.8, 2.0
    rect_c = FancyBboxPatch(
        (bx_c_x, bx_c_y - 0.6),
        2.8,
        1.2,
        boxstyle="round,pad=0.15",
        facecolor=TEAL_DARK,
        edgecolor="white",
        linewidth=2,
        alpha=0.85,
    )
    ax.add_patch(rect_c)
    ax.text(
        bx_c_x + 1.4,
        bx_c_y,
        "Agrupacion\nRegional",
        ha="center",
        va="center",
        fontsize=11,
        fontweight="bold",
        color="white",
        linespacing=1.3,
    )

    # Arrow from Regiones to Agrupacion Regional
    ax.annotate(
        "",
        xy=(bx_c_x, bx_c_y),
        xytext=(bx_b_x + 2.4, bx_b_y),
        arrowprops=dict(
            arrowstyle="-|>",
            color=COOL_GRAY,
            linewidth=1.8,
            mutation_scale=16,
        ),
    )

    # Arrow from Agrupacion Regional up to "20 Features XGBoost"
    ax.annotate(
        "",
        xy=(10.8 + box_w / 2, 4.2 - box_h / 2),
        xytext=(bx_c_x + 1.4, bx_c_y + 0.6),
        arrowprops=dict(
            arrowstyle="-|>",
            color=TEAL_DARK,
            linewidth=1.8,
            mutation_scale=16,
            connectionstyle="arc3,rad=-0.15",
        ),
    )

    ax.set_title(
        "Pipeline de Feature Engineering -- EpiForecast-MX",
        fontsize=14,
        fontweight="bold",
        color=TEAL_DARK,
        pad=15,
    )
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "feature_engineering_pipeline.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {path}")


# ============================================================================
# FIGURE 12: 4-Model Architecture Comparison (2x2 grid)
# ============================================================================
def fig_model_comparison():
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), dpi=300)
    fig.patch.set_facecolor("white")

    panels = [
        {
            "ax": axes[0, 0],
            "name": "Prophet",
            "color": MODEL_COLORS["Prophet"],
            "formula": "y(t) = g(t) + s(t) + h(t) + e(t)",
            "desc": "Tendencia + Estacionalidad\n+ Regimen COVID",
            "tag": "Estadistico | CPU",
        },
        {
            "ax": axes[0, 1],
            "name": "DeepAR",
            "color": MODEL_COLORS["DeepAR"],
            "formula": "LSTM Autoregresivo",
            "desc": "Entrenamiento global\nsobre 333 series",
            "tag": "Deep Learning | GPU",
        },
        {
            "ax": axes[1, 0],
            "name": "Ensemble",
            "color": MODEL_COLORS["Ensemble"],
            "formula": "Prophet -> Residuos -> XGBoost",
            "desc": "20 features +\ncorreccion no lineal",
            "tag": "Hibrido | CPU",
        },
        {
            "ax": axes[1, 1],
            "name": "Stacking",
            "color": MODEL_COLORS["Stacking"],
            "formula": "Prophet + ETS + LightGBM -> Ridge",
            "desc": "3 expertos +\nmeta-learner",
            "tag": "Meta-learning | CPU",
        },
    ]

    for p in panels:
        ax = p["ax"]
        color = p["color"]
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 8)
        ax.axis("off")

        # Background card
        card = FancyBboxPatch(
            (0.3, 0.3),
            9.4,
            7.4,
            boxstyle="round,pad=0.25",
            facecolor="white",
            edgecolor=color,
            linewidth=2.5,
        )
        ax.add_patch(card)

        # Colored header band
        header = FancyBboxPatch(
            (0.3, 5.8),
            9.4,
            1.9,
            boxstyle="round,pad=0.15",
            facecolor=color,
            edgecolor=color,
            linewidth=0,
            alpha=0.92,
        )
        ax.add_patch(header)

        # Model name
        ax.text(
            5.0,
            6.75,
            p["name"],
            ha="center",
            va="center",
            fontsize=18,
            fontweight="bold",
            color="white",
        )

        # Formula box
        formula_box = FancyBboxPatch(
            (1.0, 3.8),
            8.0,
            1.5,
            boxstyle="round,pad=0.2",
            facecolor="#F5F5F5",
            edgecolor=color,
            linewidth=1.5,
            alpha=0.8,
        )
        ax.add_patch(formula_box)
        ax.text(
            5.0,
            4.55,
            p["formula"],
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
            color=color,
            family="monospace",
        )

        # Description
        ax.text(
            5.0,
            2.8,
            p["desc"],
            ha="center",
            va="center",
            fontsize=10.5,
            color="#444444",
            linespacing=1.5,
        )

        # Tag badge
        tag_box = FancyBboxPatch(
            (2.5, 0.7),
            5.0,
            0.8,
            boxstyle="round,pad=0.15",
            facecolor=color,
            edgecolor="white",
            linewidth=0,
            alpha=0.15,
        )
        ax.add_patch(tag_box)
        ax.text(
            5.0,
            1.1,
            p["tag"],
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=color,
        )

    fig.suptitle(
        "Comparativa de Arquitecturas -- 4 Motores de Pronostico",
        fontsize=15,
        fontweight="bold",
        color=TEAL_DARK,
        y=0.98,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    path = os.path.join(OUT_DIR, "model_comparison_4panel.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
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
# FIGURE 16: Feature importance heatmap (XGBoost Ensemble)
# ============================================================================
def fig_feature_importance_heatmap():
    """Heatmap de importancia de features por padecimiento (ganancia relativa XGBoost)."""
    import pickle
    import glob as globmod
    from matplotlib.colors import LinearSegmentedColormap

    # --- Extract real feature importances from trained models ---
    feature_keys = [
        "lag_1",
        "lag_2",
        "lag_4",
        "lag_8",
        "lag_13",
        "lag_26",
        "lag_52",
        "rolling_mean_4",
        "rolling_mean_8",
        "rolling_mean_12",
        "rolling_mean_26",
        "rolling_mean_52",
        "rolling_std_13",
        # Orden posicional debe coincidir con FEATURE_NAMES del modelo: month, week_of_year
        "mes",
        "semana_del_anio",
        "sin_sem",
        "cos_sem",
        "momentum_4",
        "momentum_52",
        "covid_indicator",
    ]

    display_names = {
        "lag_1": "lag 1 sem",
        "lag_2": "lag 2 sem",
        "lag_4": "lag 4 sem",
        "lag_8": "lag 8 sem",
        "lag_13": "lag 13 sem",
        "lag_26": "lag 26 sem",
        "lag_52": "lag 52 sem (anual)",
        "rolling_mean_4": "media m\u00f3vil 4",
        "rolling_mean_8": "media m\u00f3vil 8",
        "rolling_mean_12": "media m\u00f3vil 12",
        "rolling_mean_26": "media m\u00f3vil 26",
        "rolling_mean_52": "media m\u00f3vil 52",
        "rolling_std_13": "volatilidad 13 sem",
        "semana_del_anio": "semana del a\u00f1o",
        "mes": "mes",
        "sin_sem": "sin(2\u03c0\u00b7sem/52)",
        "cos_sem": "cos(2\u03c0\u00b7sem/52)",
        "momentum_4": "momentum 4 sem",
        "momentum_52": "momentum 52 sem",
        "covid_indicator": "indicador COVID-19",
    }

    # Family membership for label coloring
    family_color = {}
    for k in ["lag_1", "lag_2", "lag_4", "lag_8", "lag_13", "lag_26", "lag_52"]:
        family_color[k] = BURGUNDY
    for k in [
        "rolling_mean_4",
        "rolling_mean_8",
        "rolling_mean_12",
        "rolling_mean_26",
        "rolling_mean_52",
    ]:
        family_color[k] = TEAL_DARK
    family_color["rolling_std_13"] = GOLD
    for k in ["semana_del_anio", "mes"]:
        family_color[k] = IMSS_BLUE
    for k in ["sin_sem", "cos_sem"]:
        family_color[k] = "#2E7D32"  # green
    for k in ["momentum_4", "momentum_52"]:
        family_color[k] = "#E65100"  # orange
    family_color["covid_indicator"] = "#C62828"  # red

    # Directory names (no accent) -> display names (with accent)
    diseases_dirs = ["Depresion", "Parkinson", "Alzheimer"]
    col_labels = ["Depresi\u00f3n", "Parkinson", "Alzheimer"]

    data = {}
    for disease_dir, col_label in zip(diseases_dirs, col_labels):
        pkls = globmod.glob(os.path.join(PROJECT, f"models/ensemble/{disease_dir}/*.pkl"))
        all_imp = []
        for p in pkls:
            try:
                with open(p, "rb") as f:
                    payload = pickle.load(f)
                model = payload["parallel_engine"]._xgb_direct._model
                imp = model.feature_importances_
                total = imp.sum()
                if total > 0:
                    all_imp.append(imp / total * 100)
            except Exception:
                pass
        if all_imp:
            avg = np.mean(all_imp, axis=0)
            data[col_label] = {k: v for k, v in zip(feature_keys, avg)}

    if not data:
        print("    [WARN] No se pudieron extraer importancias de features")
        return

    # Sort features by average importance across diseases (descending)
    avg_importance = []
    for feat in feature_keys:
        avg_val = np.mean([data[d].get(feat, 0) for d in col_labels])
        avg_importance.append((feat, avg_val))
    sorted_features = [f for f, _ in sorted(avg_importance, key=lambda x: -x[1])]

    # Build matrix (rows = features sorted, cols = diseases)
    matrix = np.array([[data[d].get(f, 0) for d in col_labels] for f in sorted_features])
    n_rows = len(sorted_features)
    n_cols = len(col_labels)

    # --- Custom colormap: light teal to dark burgundy ---
    cmap = LinearSegmentedColormap.from_list(
        "imss_heat", ["#F0F9F7", TEAL_DARK, DARK_BURGUNDY], N=256
    )

    # --- Figure setup: fixed size, NO bbox_inches='tight' ---
    # All positioning via figure fractions for pixel-perfect centering.
    cell_h = 0.42
    cell_w = 3.8
    label_w = 2.6
    table_total_w = n_cols * cell_w
    table_center_data = label_w + table_total_w / 2

    fig_w = 12.0  # fixed width in inches
    fig_h = 12.5  # fixed height

    # The axes fraction where the table center should land = 0.5 (center of figure)
    # label_w occupies some fraction of data range; table occupies the rest.
    # We want: (label_w + table_total_w/2) / data_range = axes_center
    # And axes_center should be at fig x=0.5
    # So: left_margin = 0.5 - (table_total_w/2) / data_range * axes_width
    data_range = label_w + table_total_w
    table_frac = table_center_data / data_range  # where table center is in 0-1 of data

    # We want table_frac * axes_width + left_margin = 0.5
    axes_width = 0.88  # use 88% of figure width for axes
    left_margin = 0.5 - table_frac * axes_width
    right_margin = 1.0 - left_margin - axes_width

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.subplots_adjust(left=left_margin, right=left_margin + axes_width, top=0.92, bottom=0.08)
    ax.set_xlim(0, data_range)
    ax.set_ylim(-0.3, n_rows * cell_h + 0.5)
    ax.axis("off")

    vmin, vmax = matrix.min(), matrix.max()

    # --- Draw cells ---
    for i, feat in enumerate(sorted_features):
        y = (n_rows - 1 - i) * cell_h
        for j in range(n_cols):
            val = matrix[i, j]
            norm_val = (val - vmin) / (vmax - vmin) if vmax > vmin else 0
            color = cmap(norm_val)
            rect = plt.Rectangle(
                (label_w + j * cell_w, y),
                cell_w - 0.15,
                cell_h - 0.04,
                facecolor=color,
                edgecolor="white",
                linewidth=1.5,
            )
            ax.add_patch(rect)
            lum = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
            txt_color = "white" if lum < 0.55 else "#333333"
            fontweight = "bold" if val >= 8 else "normal"
            ax.text(
                label_w + j * cell_w + (cell_w - 0.15) / 2,
                y + (cell_h - 0.04) / 2,
                f"{val:.1f}%",
                ha="center",
                va="center",
                fontsize=10,
                fontweight=fontweight,
                color=txt_color,
            )

    # --- Row labels ---
    for i, feat in enumerate(sorted_features):
        y = (n_rows - 1 - i) * cell_h
        ax.text(
            label_w - 0.15,
            y + (cell_h - 0.04) / 2,
            display_names.get(feat, feat),
            ha="right",
            va="center",
            fontsize=9.5,
            fontweight="bold",
            color=family_color.get(feat, "#333333"),
        )

    # --- Column headers ---
    for j, col in enumerate(col_labels):
        ax.text(
            label_w + j * cell_w + (cell_w - 0.15) / 2,
            n_rows * cell_h + 0.15,
            col,
            ha="center",
            va="bottom",
            fontsize=13,
            fontweight="bold",
            color="#333333",
        )

    # --- Title and subtitle: at fig x=0.5 (true center of image) ---
    fig.text(
        0.5,
        0.97,
        "Importancia de features por padecimiento",
        ha="center",
        va="top",
        fontsize=16,
        fontweight="bold",
        color="#1a1a1a",
    )
    fig.text(
        0.5,
        0.935,
        "(ganancia relativa \u2014 XGBoost del motor Ensemble)",
        ha="center",
        va="top",
        fontsize=10.5,
        color=COOL_GRAY,
        style="italic",
    )

    # --- Legend card: centered at fig x=0.5 ---
    legend_items = [
        ("Lags (7)", BURGUNDY),
        ("Medias m\u00f3viles (5)", TEAL_DARK),
        ("Volatilidad (1)", GOLD),
        ("Calendario (2)", IMSS_BLUE),
        ("C\u00edclicas (2)", "#2E7D32"),
        ("Momentum (2)", "#E65100"),
        ("R\u00e9gimen (1)", "#C62828"),
    ]
    handles = []
    labels = []
    for label, color in legend_items:
        handles.append(mpatches.Patch(facecolor=color, edgecolor="none"))
        labels.append(label)

    leg = fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.065),
        ncol=4,
        fontsize=8.5,
        frameon=True,
        fancybox=True,
        shadow=False,
        edgecolor=COOL_GRAY,
        facecolor="#FAFAFA",
        handlelength=1.0,
        handletextpad=0.4,
        columnspacing=1.2,
        borderpad=0.6,
    )
    leg.get_frame().set_linewidth(0.6)
    leg.get_frame().set_alpha(0.95)
    for txt, (_, color) in zip(leg.get_texts(), legend_items):
        txt.set_color(color)
        txt.set_fontweight("bold")

    # Source footnote
    fig.text(
        0.5,
        0.008,
        "Fuente: Modelos Ensemble entrenados en producci\u00f3n (EpiForecast-MX, 333 series).",
        ha="center",
        va="bottom",
        fontsize=7.5,
        color=COOL_GRAY,
        style="italic",
    )

    path = os.path.join(OUT_DIR, "feature_importance_heatmap_v2.png")
    fig.savefig(path, dpi=300, facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"    -> {path} ({os.path.getsize(path) / 1024:.0f} KB)")


# ============================================================================
# [17] Comparativo 4 motores x 4 series (casos de estudio)
# ============================================================================
def fig_comparativo_4x4():
    """Grafico comparativo de SMAPE y MASE para los 4 casos de estudio."""

    # --- Datos reales verificados del Excel de produccion ---
    # P4: Labels sin abreviaciones confusas
    series = [
        "Depresi\u00f3n\nCDMX, General",
        "Alzheimer\nCoahuila, General",
        "Parkinson\nNacional, General",
        "Alzheimer\nReg. Metropolitana, Mujeres",
    ]
    motors = ["DeepAR", "Prophet", "Ensemble", "Stacking"]

    # P1: Mapeo EXPLICITO por nombre, no por indice
    COLOR_MAP = {
        "deepar": "#880E4F",
        "prophet": "#004D40",
        "ensemble": "#FF6F00",
        "stacking": "#1A237E",
    }

    # SMAPE por [serie][motor] en orden DeepAR, Prophet, Ensemble, Stacking
    smape = np.array(
        [
            [3.48, 15.95, 11.19, 23.70],  # Depresion CDMX
            [98.91, 89.43, 108.63, 115.12],  # Alzheimer Coahuila
            [52.91, 22.39, 16.19, 25.48],  # Parkinson Nacional
            [44.78, 40.91, 43.38, 42.96],  # Alzheimer Reg Metro
        ]
    )
    mase = np.array(
        [
            [0.159, 0.732, 0.579, 1.147],
            [0.881, 0.807, 1.129, 1.091],
            [1.358, 0.761, 0.551, 0.773],
            [0.595, 0.676, 0.570, 0.557],
        ]
    )
    # Indice del ganador por serie
    winners = [0, 1, 2, 3]  # DeepAR, Prophet, Ensemble, Stacking

    n_series = len(series)
    n_motors = len(motors)
    bar_h = 0.18
    group_gap = 0.35

    fig, (ax_smape, ax_mase) = plt.subplots(
        1, 2, figsize=(14, 5.5), gridspec_kw={"width_ratios": [1.2, 1]}
    )

    # P1: Verificar mapeo de colores
    for motor in motors:
        c = COLOR_MAP[motor.lower()]
        print(f"  [color-check] {motor}: {c}")

    # P3: Pre-compute which labels must go outside even if val > 80
    # (when two inside labels would overlap)
    force_outside = set()  # (serie_idx, motor_idx) tuples
    for i in range(n_series):
        inside_vals = [(j, smape[i, j]) for j in range(n_motors) if smape[i, j] > 80]
        inside_vals.sort(key=lambda x: x[1])
        for k in range(len(inside_vals)):
            for l in range(k + 1, len(inside_vals)):
                if abs(inside_vals[k][1] - inside_vals[l][1]) < 8:
                    force_outside.add((i, inside_vals[k][0]))

    # --- Panel izquierdo: SMAPE ---
    for i in range(n_series):
        for j in range(n_motors):
            y = (n_series - 1 - i) * (n_motors * bar_h + group_gap) + (n_motors - 1 - j) * bar_h
            val = smape[i, j]
            is_winner = j == winners[i]
            color = COLOR_MAP[motors[j].lower()]
            ax_smape.barh(
                y,
                val,
                height=bar_h * 0.9,
                color=color,
                alpha=1.0,
                edgecolor="white",
                linewidth=0.5,
                zorder=3,
            )
            if is_winner:
                ax_smape.barh(
                    y,
                    val,
                    height=bar_h * 0.9,
                    color="none",
                    edgecolor=GOLD,
                    linewidth=2.0,
                    zorder=4,
                )
            # Decide inside vs outside BEFORE drawing label
            inside = val > 80 and (i, j) not in force_outside
            if inside:
                label_x = val - 2
                ha = "right"
                txt_color = "white"
            else:
                label_x = val + 1.5
                ha = "left"
                txt_color = color if is_winner else COOL_GRAY
            ax_smape.text(
                label_x,
                y,
                f"{val:.1f}%",
                va="center",
                ha=ha,
                fontsize=7.5,
                fontweight="bold" if is_winner else "normal",
                color=txt_color,
                zorder=5,
            )
            # P2: Estrella a la IZQUIERDA de la barra
            if is_winner:
                ax_smape.text(
                    -2,
                    y,
                    "\u2605",
                    fontsize=10,
                    color=GOLD,
                    va="center",
                    ha="right",
                    fontweight="bold",
                    zorder=5,
                )

    # Y-ticks = series labels
    yticks = []
    for i in range(n_series):
        center = (n_series - 1 - i) * (n_motors * bar_h + group_gap) + (n_motors - 1) * bar_h / 2
        yticks.append(center)
    ax_smape.set_yticks(yticks)
    ax_smape.set_yticklabels(series, fontsize=9, fontweight="bold")
    ax_smape.set_xlabel("SMAPE (%)", fontsize=10, fontweight="bold", color=TEAL_DARK)
    ax_smape.set_title(
        "Error porcentual sim\u00e9trico (SMAPE)",
        fontsize=12,
        fontweight="bold",
        color=TEAL_DARK,
        pad=12,
    )
    # P5: Linea 100% en gris, no en color casi invisible
    ax_smape.axvline(x=100, color=COOL_GRAY, linestyle=":", linewidth=0.8, alpha=0.7, zorder=1)
    ax_smape.text(101, yticks[0] + bar_h * 2, "100%", fontsize=7, color=COOL_GRAY, alpha=0.9)
    ax_smape.set_xlim(0, 125)
    ax_smape.spines["top"].set_visible(False)
    ax_smape.spines["right"].set_visible(False)
    ax_smape.grid(axis="x", alpha=0.15, zorder=0)

    # --- Panel derecho: MASE ---
    for i in range(n_series):
        for j in range(n_motors):
            y = (n_series - 1 - i) * (n_motors * bar_h + group_gap) + (n_motors - 1 - j) * bar_h
            val = mase[i, j]
            is_winner = j == winners[i]
            # P1: color explicito por nombre, SIN alpha < 1.0
            color = COLOR_MAP[motors[j].lower()]
            ax_mase.barh(
                y,
                val,
                height=bar_h * 0.9,
                color=color,
                alpha=1.0,
                edgecolor="white",
                linewidth=0.5,
                zorder=3,
            )
            if is_winner:
                ax_mase.barh(
                    y,
                    val,
                    height=bar_h * 0.9,
                    color="none",
                    edgecolor=GOLD,
                    linewidth=2.0,
                    zorder=4,
                )
            label_x = val + 0.02
            ax_mase.text(
                label_x,
                y,
                f"{val:.2f}",
                va="center",
                ha="left",
                fontsize=7.5,
                fontweight="bold" if is_winner else "normal",
                color=color if is_winner else COOL_GRAY,
                zorder=5,
            )
            # P2: Estrella a la IZQUIERDA de la barra en MASE tambien
            if is_winner:
                ax_mase.text(
                    -0.03,
                    y,
                    "\u2605",
                    fontsize=10,
                    color=GOLD,
                    va="center",
                    ha="right",
                    fontweight="bold",
                    zorder=5,
                )

    ax_mase.set_yticks(yticks)
    ax_mase.set_yticklabels([""] * n_series)
    ax_mase.set_xlabel("MASE", fontsize=10, fontweight="bold", color=TEAL_DARK)
    ax_mase.set_title(
        "Error escalado vs. naive (MASE)", fontsize=12, fontweight="bold", color=TEAL_DARK, pad=12
    )
    # P7: Linea Naive=1.0 en gris, no rosa/magenta
    ax_mase.axvline(x=1.0, color=COOL_GRAY, linestyle="--", linewidth=1.2, alpha=0.7, zorder=1)
    ax_mase.text(
        1.02,
        yticks[0] + bar_h * 2,
        "Naive = 1.0",
        fontsize=7,
        color=COOL_GRAY,
        alpha=0.9,
        fontstyle="italic",
    )
    ax_mase.set_xlim(0, 1.6)
    ax_mase.spines["top"].set_visible(False)
    ax_mase.spines["right"].set_visible(False)
    ax_mase.grid(axis="x", alpha=0.15, zorder=0)

    # --- Leyenda comun ---
    handles = []
    for m in motors:
        handles.append(
            mpatches.Patch(
                facecolor=COLOR_MAP[m.lower()],
                edgecolor="white",
                label=m,
            )
        )
    handles.append(
        mpatches.Patch(facecolor="white", edgecolor=GOLD, linewidth=1.5, label="Motor ganador")
    )
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=5,
        fontsize=9,
        frameon=True,
        fancybox=True,
        edgecolor=COOL_GRAY,
        bbox_to_anchor=(0.5, -0.02),
    )

    fig.suptitle(
        "Comparativo de motores: 4 casos de estudio con datos reales",
        fontsize=13,
        fontweight="bold",
        color=TEAL_DARK,
        y=0.98,
    )

    plt.tight_layout(rect=[0, 0.06, 1, 0.95])
    path = os.path.join(OUT_DIR, "comparativo_4x4_motores.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"    -> {path} ({os.path.getsize(path) / 1024:.0f} KB)")


def _load_real_series():
    """Carga datos reales desde data_prepare y agrega Nacional / Regional."""
    dep = pd.read_csv(
        os.path.join(PROJECT, "data", "processed", "data_prepare_Depresión.csv"),
        parse_dates=["Fecha"],
    )
    gen = pd.read_csv(
        os.path.join(PROJECT, "data", "processed", "data_prepare_General.csv"),
        parse_dates=["Fecha"],
    )
    raw = pd.concat([dep, gen], ignore_index=True)
    raw.rename(
        columns={"Fecha": "ds", "Entidad": "entidad", "Padecimiento": "padecimiento"}, inplace=True
    )
    # Depresion existe en ambos archivos con valores identicos: deduplicar para no
    # contar filas dobles (rompe el suavizado de la tendencia de 13 semanas).
    raw = raw.drop_duplicates(subset=["ds", "entidad", "padecimiento"], keep="first")
    return raw


def fig_series_4casos():
    """Series temporales reales de los 4 casos de estudio para ver diferencias visuales."""
    raw = _load_real_series()
    tableau = pd.read_csv(
        os.path.join(PROJECT, "data", "processed", "tableau.csv"),
        parse_dates=["ds"],
    )

    # Estados que forman Region Metropolitana alta
    METRO_STATES = ["Ciudad de M\u00e9xico", "Jalisco", "M\u00e9xico", "Nuevo Le\u00f3n"]

    # P5: Color explícito por nombre de motor
    MOTOR_COLOR = {
        "DeepAR": "#880E4F",
        "Prophet": "#004D40",
        "Ensemble": "#FF6F00",
        "Stacking": "#1A237E",
    }

    cases = [
        {
            "title": "Depresi\u00f3n, CDMX (General)",
            "winner": "DeepAR",
            "smape": "3.48",
            "filter": lambda d: d[
                (d["entidad"] == "Ciudad de M\u00e9xico") & (d["padecimiento"] == "Depresi\u00f3n")
            ],
            "y_col": "incrementos_total",
            "tableau_filter": {
                "entidad": "Ciudad de M\u00e9xico",
                "padecimiento": "Depresi\u00f3n",
                "meta_modo": "general",
            },
        },
        {
            "title": "Alzheimer, Coahuila (General)",
            "winner": "Prophet",
            "smape": "89.43",
            "filter": lambda d: d[
                (d["entidad"] == "Coahuila") & (d["padecimiento"] == "Alzheimer")
            ],
            "y_col": "incrementos_total",
            "tableau_filter": {
                "entidad": "Coahuila",
                "padecimiento": "Alzheimer",
                "meta_modo": "general",
            },
        },
        {
            "title": "Parkinson, Nacional (General)",
            "winner": "Ensemble",
            "smape": "16.19",
            "filter": lambda d: d[d["padecimiento"] == "Parkinson"]
            .groupby("ds", as_index=False)["incrementos_total"]
            .sum(),
            "y_col": "incrementos_total",
            "tableau_filter": {
                "entidad": "Nacional",
                "padecimiento": "Parkinson",
                "meta_modo": "general",
            },
        },
        {
            "title": "Alzheimer, Reg. Metropolitana (Mujeres)",
            "winner": "Stacking",
            "smape": "42.96",
            "filter": lambda d: d[
                (d["entidad"].isin(METRO_STATES)) & (d["padecimiento"] == "Alzheimer")
            ]
            .groupby("ds", as_index=False)["incrementos_mujeres"]
            .sum(),
            "y_col": "incrementos_mujeres",
            "tableau_filter": {
                "entidad": "Region Metropolitana alta",
                "padecimiento": "Alzheimer",
                "meta_modo": "mujeres",
            },
        },
    ]

    # P8: Spacing general
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.subplots_adjust(top=0.88, bottom=0.08, left=0.06, right=0.97, hspace=0.40, wspace=0.20)
    axes = axes.ravel()

    from matplotlib.lines import Line2D

    for idx, case in enumerate(cases):
        ax = axes[idx]
        y_col = case["y_col"]

        # Obtener datos reales
        real = case["filter"](raw).sort_values("ds").copy()
        real = real.dropna(subset=[y_col])

        # Obtener forecast del ganador desde tableau
        tf = case["tableau_filter"]
        tab_mask = (
            (tableau["entidad"] == tf["entidad"])
            & (tableau["padecimiento"] == tf["padecimiento"])
            & (tableau["meta_modo"] == tf["meta_modo"])
        )
        tab_sub = tableau.loc[tab_mask].sort_values("ds")

        # Determinar horizonte futuro (ds > ultimo dato real)
        last_real_date = real["ds"].max()
        future = tab_sub[tab_sub["ds"] > last_real_date]

        # Franja COVID (config/visualization/plots.yaml)
        covid_start = pd.Timestamp("2020-03-15")
        covid_end = pd.Timestamp("2022-09-22")
        ax.axvspan(covid_start, covid_end, color=BURGUNDY, alpha=0.06, zorder=0)

        # Serie real como fondo sutil
        ax.plot(real["ds"], real[y_col], color="#BFBFBF", linewidth=0.4, alpha=0.5, zorder=2)
        ax.fill_between(real["ds"], 0, real[y_col], color=COOL_GRAY, alpha=0.04, zorder=1)

        # Outliers IQR
        vals = real[y_col].dropna()
        q1, q3 = vals.quantile(0.25), vals.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            out_mask = (real[y_col] < low) | (real[y_col] > high)
            outliers = real[out_mask]
            if len(outliers) > 0:
                ax.scatter(
                    outliers["ds"],
                    outliers[y_col],
                    marker="^",
                    s=18,
                    color=BURGUNDY,
                    edgecolors="white",
                    linewidths=0.4,
                    alpha=0.7,
                    zorder=5,
                )

        # Tendencia 13 semanas como protagonista
        if len(real) > 13:
            ma = real[y_col].rolling(13, min_periods=1).mean()
            ax.plot(real["ds"], ma, color=TEAL, linewidth=1.5, zorder=3)

        # Pronostico del ganador con color explicito
        winner_col = f"yhat_{case['winner'].lower()}"
        motor_color = MOTOR_COLOR[case["winner"]]
        if winner_col in tab_sub.columns and len(future) > 0:
            ax.plot(
                future["ds"],
                future[winner_col],
                color=motor_color,
                linewidth=2.0,
                linestyle="--",
                zorder=4,
            )
            ax.axvline(
                x=last_real_date,
                color=COOL_GRAY,
                linestyle=":",
                linewidth=1.0,
                alpha=0.8,
                zorder=3,
            )

        # P2-Alzheimer Coahuila: anotacion de pronostico plano (verificado)
        if case["winner"] == "Prophet" and "Coahuila" in case["title"]:
            if len(future) > 0:
                mid_date = future["ds"].iloc[len(future) // 2]
                ax.annotate(
                    "Pron\u00f3stico estable\n(baja incidencia)",
                    xy=(mid_date, 2.0),
                    fontsize=7,
                    color=COOL_GRAY,
                    ha="center",
                    fontstyle="italic",
                    xytext=(mid_date, 5.5),
                    arrowprops=dict(
                        arrowstyle="->", color=COOL_GRAY, lw=0.6, connectionstyle="arc3,rad=0.2"
                    ),
                )

        # Badge de ganador integrado en el titulo
        title_line1 = case["title"]
        title_line2 = f"Ganador: {case['winner']} (SMAPE {case['smape']}%)"
        ax.set_title(
            f"{title_line1}\n{title_line2}", fontsize=10, fontweight="bold", color=TEAL_DARK, pad=6
        )

        # COVID-19 label (after data plotted so ylim is correct)
        ax.set_ylim(bottom=0)
        ymax = ax.get_ylim()[1]
        covid_mid = covid_start + (covid_end - covid_start) / 2
        ax.text(
            covid_mid,
            ymax * 0.95,
            "COVID-19",
            fontsize=7,
            color=BURGUNDY,
            alpha=0.5,
            ha="center",
            va="top",
            fontstyle="italic",
            zorder=1,
        )

        # Formato
        ax.set_ylabel("Casos semanales", fontsize=8, color=COOL_GRAY)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(COOL_GRAY)
        ax.spines["bottom"].set_color(COOL_GRAY)
        ax.tick_params(labelsize=7.5, colors=COOL_GRAY)
        ax.grid(axis="y", alpha=0.15, zorder=0)

    # Leyenda compartida con los 4 motores individuales y sus colores
    legend_handles = [
        Line2D([0], [0], color="#BFBFBF", linewidth=1.5, alpha=0.5, label="Real"),
        Line2D([0], [0], color=TEAL, linewidth=2.0, label="Tendencia (13 sem.)"),
        Line2D(
            [0],
            [0],
            marker="^",
            color="none",
            markerfacecolor=BURGUNDY,
            markeredgecolor="white",
            markersize=5,
            label="Outlier IQR",
        ),
        mpatches.Patch(facecolor=BURGUNDY, alpha=0.12, edgecolor="none", label="COVID-19"),
        Line2D([0], [0], color="#880E4F", linewidth=2.0, linestyle="--", label="DeepAR"),
        Line2D([0], [0], color="#004D40", linewidth=2.0, linestyle="--", label="Prophet"),
        Line2D([0], [0], color="#FF6F00", linewidth=2.0, linestyle="--", label="Ensemble"),
        Line2D([0], [0], color="#1A237E", linewidth=2.0, linestyle="--", label="Stacking"),
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=8,
        fontsize=8,
        frameon=True,
        fancybox=True,
        edgecolor="#E0E0E0",
        bbox_to_anchor=(0.5, -0.01),
    )

    # P2: Titulo principal con mas espacio
    fig.suptitle(
        "Series temporales reales: los 4 casos de estudio",
        fontsize=14,
        fontweight="bold",
        color=TEAL_DARK,
        y=0.97,
    )

    path = os.path.join(OUT_DIR, "series_temporales_4casos.png")
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"    -> {path} ({os.path.getsize(path) / 1024:.0f} KB)")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("Generando figuras para Resumen Ejecutivo - Avance 7\n")

    print("[1/20] Distribucion de motores (donut)...")
    fig1_donut()

    print("[2/20] Comparativo MASE por motor...")
    fig2_mase()

    print("[3/20] Serie temporal Depresion Nacional...")
    fig3_time_series()

    print("[4/20] Serie temporal Parkinson Nacional...")
    fig3b_parkinson()

    print("[5/20] Serie temporal Alzheimer Nacional...")
    fig3c_alzheimer()

    print("[6/20] Distribucion por sexo (boletin real)...")
    fig_eda_genero()

    print("[7/20] Mapa coropletico de Mexico (boletin real)...")
    fig_eda_mapa()

    print("[8/20] Alerta de reporte intermitente...")
    fig_eda_alerta_ceros()

    print("[9/20] Pronostico por entidad (barras)...")
    fig4_geo_bars()

    print("[10/20] Waterfall CRISP-ML(Q)...")
    fig5_waterfall()

    print("[11/20] Costos vs Beneficios...")
    fig6_cost_benefit()

    print("[12/20] Matriz de riesgos...")
    fig7_risk_heatmap()

    print("[13/20] Arquitectura simplificada...")
    fig8_architecture()

    print("[14/20] EpiBot showcase (mockup)...")
    fig9_epibot()

    print("[15/20] Consola showcase (mockup)...")
    fig10_consola()

    print("[16/20] Heatmap de importancia de features...")
    fig_feature_importance_heatmap()

    print("[17/20] Comparativo 4x4 motores (casos de estudio)...")
    fig_comparativo_4x4()

    print("[18/20] Comparativo SMAPE por motor y padecimiento...")
    fig_comparativo_smape()

    print("[19/20] Series temporales de los 4 casos de estudio...")
    fig_series_4casos()

    print("\n[+] Copiando screenshots existentes...")
    copy_screenshots()

    print("\n" + "=" * 60)
    print("Verificacion final de archivos:")
    print("=" * 60)
    expected = [
        "modelos_distribucion_motores.png",
        "modelos_comparativo_mase.png",
        "eda_serie_temporal.png",
        "eda_serie_parkinson.png",
        "eda_serie_alzheimer.png",
        "eda_genero_butterfly.png",
        "eda_mapa_mexico.png",
        "eda_alerta_ceros.png",
        "eda_heatmap_geografico.png",
        "costos_waterfall_crispml.png",
        "costos_vs_beneficios.png",
        "riesgos_heatmap.png",
        "arquitectura_simplificada.png",
        "epibot_showcase.png",
        "consola_showcase.png",
        "dashboard_showcase.png",
        "feature_importance_heatmap_v2.png",
        "comparativo_4x4_motores.png",
        "series_temporales_4casos.png",
        "modelos_comparativo_smape.png",
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
