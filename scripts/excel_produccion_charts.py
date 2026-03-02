"""Generador de graficos embebidos para el Excel de produccion.

Crea 6 graficos con estilo IMSS 2026 y los devuelve como bytes PNG
para incrustar en la hoja 'Analisis Visual' del workbook.
"""

from __future__ import annotations

from io import BytesIO

from matplotlib.patches import FancyBboxPatch
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paleta IMSS 2026
# ---------------------------------------------------------------------------
_VERDE_IMSS = "#006847"
_VERDE_OSCURO = "#004D40"
_ROJO_IMSS = "#CE1126"
_GRIS_OSCURO = "#212121"
_GRIS_MEDIO = "#757575"
_GRIS_CLARO = "#F5F5F5"

_MODEL_COLORS = {
    "Prophet": "#004D40",
    "DeepAR": "#880E4F",
    "Ensemble": "#FF6F00",
    "Stacking": "#1A237E",
}

_PAD_COLORS = {
    "Depresion": "#1565C0",
    "Parkinson": "#2E7D32",
    "Alzheimer": "#E65100",
}

_DPI = 150
_BG_COLOR = "#FAFAFA"


def _setup_ax(ax: plt.Axes, title: str) -> None:
    """Estilo base para un eje."""
    ax.set_facecolor(_BG_COLOR)
    ax.set_title(title, fontsize=13, fontweight="bold", color=_GRIS_OSCURO, pad=14)
    ax.tick_params(colors=_GRIS_MEDIO, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#E0E0E0")
        spine.set_linewidth(0.5)


def _fig_to_bytes(fig: plt.Figure) -> BytesIO:
    """Convierte figura a BytesIO PNG."""
    buf = BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=_DPI,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
        edgecolor="none",
    )
    plt.close(fig)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Chart 1: Distribucion de modelos (donut con detalle por padecimiento)
# ---------------------------------------------------------------------------


def chart_model_distribution(df: pd.DataFrame) -> BytesIO:
    """Donut chart: proporcion de cada modelo en produccion."""
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5), facecolor=_BG_COLOR)

    datasets = [("Global (333 series)", df)]
    for pad in ["Depresion", "Parkinson", "Alzheimer"]:
        pad_accent = next(
            (p for p in df["padecimiento"].unique() if pad.lower() in p.lower()), pad
        )
        datasets.append((pad_accent, df[df["padecimiento"] == pad_accent]))

    for ax, (title, sub) in zip(axes, datasets, strict=False):
        counts = sub["modelo_produccion"].value_counts()
        colors = [_MODEL_COLORS.get(m, "#999") for m in counts.index]
        wedges, texts, autotexts = ax.pie(
            counts.values,
            labels=None,
            colors=colors,
            autopct="%1.0f%%",
            startangle=90,
            pctdistance=0.78,
            wedgeprops={"width": 0.45, "edgecolor": "white", "linewidth": 1.5},
        )
        for at in autotexts:
            at.set_fontsize(8)
            at.set_fontweight("bold")
            at.set_color("white")
        ax.set_title(title, fontsize=10, fontweight="bold", color=_GRIS_OSCURO, pad=8)

    # Leyenda global
    from matplotlib.patches import Patch

    legend_elements = [Patch(facecolor=c, label=m) for m, c in _MODEL_COLORS.items()]
    fig.legend(
        handles=legend_elements,
        loc="lower center",
        ncol=4,
        fontsize=9,
        frameon=False,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.suptitle(
        "Distribucion de Modelos de Produccion",
        fontsize=14,
        fontweight="bold",
        color=_VERDE_IMSS,
        y=1.02,
    )
    fig.tight_layout()
    return _fig_to_bytes(fig)


# ---------------------------------------------------------------------------
# Chart 2: SMAPE promedio por modelo y padecimiento
# ---------------------------------------------------------------------------


def chart_smape_comparison(df: pd.DataFrame) -> BytesIO:
    """Barras agrupadas: SMAPE promedio de cada algoritmo por padecimiento."""
    fig, ax = plt.subplots(figsize=(12, 5), facecolor=_BG_COLOR)
    _setup_ax(ax, "SMAPE Promedio por Algoritmo y Padecimiento")

    models = ["Prophet", "DeepAR", "Ensemble", "Stacking"]
    model_keys = ["prophet", "deepar", "ensemble", "stacking"]
    pads = sorted(df["padecimiento"].unique())

    x = np.arange(len(pads))
    width = 0.18
    offsets = np.arange(len(models)) - (len(models) - 1) / 2

    for i, (mk, ml) in enumerate(zip(model_keys, models, strict=True)):
        col = f"{mk}_smape"
        vals = [
            pd.to_numeric(df[df["padecimiento"] == p][col], errors="coerce").median() for p in pads
        ]
        bars = ax.bar(
            x + offsets[i] * width,
            vals,
            width * 0.9,
            label=ml,
            color=_MODEL_COLORS[ml],
            alpha=0.9,
            edgecolor="white",
            linewidth=0.5,
        )
        for bar, v in zip(bars, vals, strict=True):
            if pd.notna(v):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 1,
                    f"{v:.0f}",
                    ha="center",
                    va="bottom",
                    fontsize=7,
                    color=_GRIS_MEDIO,
                )

    ax.set_xticks(x)
    ax.set_xticklabels(pads, fontsize=10)
    ax.set_ylabel("SMAPE (%) - mediana", fontsize=9, color=_GRIS_MEDIO)
    ax.legend(fontsize=9, framealpha=0.8)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)
    fig.tight_layout()
    return _fig_to_bytes(fig)


# ---------------------------------------------------------------------------
# Chart 3: Top 15 entidades por casos proyectados
# ---------------------------------------------------------------------------


def chart_top_entities(df: pd.DataFrame) -> BytesIO:
    """Barras horizontales: top 15 entidades por casos futuros (modo general)."""
    fig, ax = plt.subplots(figsize=(12, 6), facecolor=_BG_COLOR)
    _setup_ax(ax, "Top 15 Entidades por Casos Proyectados (52 semanas, modo general)")

    gen = df[
        (df["sexo"] == "general")
        & (~df["entidad"].astype(str).str.startswith("region_"))
        & (df["entidad"] != "Nacional")
    ].copy()
    gen["casos_52_semanas_futuro"] = pd.to_numeric(gen["casos_52_semanas_futuro"], errors="coerce")
    top = gen.nlargest(15, "casos_52_semanas_futuro")
    top = top.sort_values("casos_52_semanas_futuro")

    pad_labels = top["padecimiento"].apply(
        lambda x: next((k for k, v in _PAD_COLORS.items() if k.lower() in str(x).lower()), "")
    )
    colors = [_PAD_COLORS.get(p, _GRIS_MEDIO) for p in pad_labels]

    bars = ax.barh(
        range(len(top)),
        top["casos_52_semanas_futuro"].values,
        color=colors,
        edgecolor="white",
        linewidth=0.5,
        height=0.7,
    )

    for i, (bar, row) in enumerate(zip(bars, top.itertuples(), strict=False)):
        label = f"{row.entidad} ({row.padecimiento})"
        ax.text(
            bar.get_width() + 50,
            i,
            f" {int(bar.get_width()):,}",
            va="center",
            fontsize=8,
            color=_GRIS_OSCURO,
            fontweight="bold",
        )
        ax.text(10, i, label, va="center", fontsize=8, color="white", fontweight="bold")

    ax.set_yticks([])
    ax.set_xlabel("Casos proyectados (52 semanas)", fontsize=9, color=_GRIS_MEDIO)
    ax.set_xlim(0, top["casos_52_semanas_futuro"].max() * 1.2)

    from matplotlib.patches import Patch

    legend_elements = [Patch(facecolor=c, label=p) for p, c in _PAD_COLORS.items()]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=9, framealpha=0.8)
    fig.tight_layout()
    return _fig_to_bytes(fig)


# ---------------------------------------------------------------------------
# Chart 4: Precision historica (distribucion)
# ---------------------------------------------------------------------------


def chart_precision_distribution(df: pd.DataFrame) -> BytesIO:
    """Histograma + KDE de precision historica por padecimiento."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), facecolor=_BG_COLOR, sharey=True)

    pads = sorted(df["padecimiento"].unique())
    for ax, pad in zip(axes, pads, strict=False):
        sub = df[df["padecimiento"] == pad].copy()
        prec = sub["precision_historica"].apply(
            lambda x: float(str(x).replace("%", "")) if isinstance(x, str) and x != "0%" else 0
        )
        # Clip outliers for visualization
        prec_clip = prec.clip(0, 200)
        pad_key = next((k for k in _PAD_COLORS if k.lower() in pad.lower()), "")
        color = _PAD_COLORS.get(pad_key, _GRIS_MEDIO)

        ax.hist(prec_clip, bins=25, color=color, alpha=0.7, edgecolor="white", linewidth=0.5)
        ax.axvline(
            100,
            color=_ROJO_IMSS,
            linewidth=1.5,
            linestyle="--",
            alpha=0.8,
            label="100% (perfecto)",
        )
        median_val = prec_clip.median()
        ax.axvline(
            median_val,
            color=_GRIS_OSCURO,
            linewidth=1.2,
            linestyle=":",
            label=f"Mediana: {median_val:.0f}%",
        )

        _setup_ax(ax, pad)
        ax.set_xlabel("Precision historica (%)", fontsize=8, color=_GRIS_MEDIO)
        ax.legend(fontsize=7, framealpha=0.7)
        ax.grid(axis="y", alpha=0.3, linewidth=0.5)

    axes[0].set_ylabel("Frecuencia", fontsize=9, color=_GRIS_MEDIO)
    fig.suptitle(
        "Distribucion de Precision Historica (pronostico / realidad)",
        fontsize=13,
        fontweight="bold",
        color=_VERDE_IMSS,
        y=1.02,
    )
    fig.tight_layout()
    return _fig_to_bytes(fig)


# ---------------------------------------------------------------------------
# Chart 5: Scatter SMAPE vs Casos (tamano = MASE)
# ---------------------------------------------------------------------------


def chart_smape_vs_cases(df: pd.DataFrame) -> BytesIO:
    """Scatter: SMAPE del modelo produccion vs casos proyectados, color por padecimiento."""
    fig, ax = plt.subplots(figsize=(12, 6), facecolor=_BG_COLOR)
    _setup_ax(ax, "SMAPE vs Casos Proyectados (tamano = MASE)")

    for pad in sorted(df["padecimiento"].unique()):
        sub = df[df["padecimiento"] == pad].copy()
        smape = pd.to_numeric(sub["smape_prod"], errors="coerce")
        cases = pd.to_numeric(sub["casos_52_semanas_futuro"], errors="coerce")
        mase = pd.to_numeric(sub["mase_prod"], errors="coerce").fillna(0.5)
        sizes = mase.clip(0.1, 3) * 40

        pad_key = next((k for k in _PAD_COLORS if k.lower() in pad.lower()), "")
        color = _PAD_COLORS.get(pad_key, _GRIS_MEDIO)
        ax.scatter(
            cases, smape, s=sizes, c=color, alpha=0.5, edgecolors="white", linewidth=0.3, label=pad
        )

    ax.set_xlabel("Casos proyectados (52 semanas)", fontsize=9, color=_GRIS_MEDIO)
    ax.set_ylabel("SMAPE (%)", fontsize=9, color=_GRIS_MEDIO)
    ax.set_xscale("symlog", linthresh=10)
    ax.legend(fontsize=9, framealpha=0.8, markerscale=1.5)
    ax.grid(alpha=0.3, linewidth=0.5)

    # Zona de alta confianza
    ax.axhspan(0, 30, color=_VERDE_IMSS, alpha=0.05)
    ax.text(
        ax.get_xlim()[1] * 0.5,
        15,
        "Zona de alta confianza (SMAPE < 30%)",
        fontsize=8,
        color=_VERDE_IMSS,
        ha="center",
        alpha=0.7,
        fontstyle="italic",
    )

    fig.tight_layout()
    return _fig_to_bytes(fig)


# ---------------------------------------------------------------------------
# Chart 6: Dashboard resumen (KPIs + mini-charts)
# ---------------------------------------------------------------------------


def chart_executive_dashboard(df: pd.DataFrame) -> BytesIO:
    """Dashboard ejecutivo con KPIs y mini-graficos."""
    fig = plt.figure(figsize=(16, 7), facecolor=_BG_COLOR)

    # KPIs row (top)
    kpi_data = _compute_kpis(df)

    # 4 KPI boxes
    for i, (label, value, sub_text, color) in enumerate(kpi_data):
        ax_kpi = fig.add_axes([0.02 + i * 0.245, 0.72, 0.22, 0.24])
        ax_kpi.set_xlim(0, 1)
        ax_kpi.set_ylim(0, 1)
        ax_kpi.axis("off")
        ax_kpi.set_facecolor("white")
        # Box border
        rect = FancyBboxPatch(
            (0.02, 0.02),
            0.96,
            0.96,
            boxstyle="round,pad=0.03",
            facecolor="white",
            edgecolor=color,
            linewidth=2,
        )
        ax_kpi.add_patch(rect)
        ax_kpi.text(
            0.5, 0.7, value, ha="center", va="center", fontsize=22, fontweight="bold", color=color
        )
        ax_kpi.text(
            0.5,
            0.38,
            label,
            ha="center",
            va="center",
            fontsize=9,
            color=_GRIS_OSCURO,
            fontweight="bold",
        )
        ax_kpi.text(0.5, 0.15, sub_text, ha="center", va="center", fontsize=7, color=_GRIS_MEDIO)

    # Bottom left: Model reliability (MASE < 1 %)
    ax_rel = fig.add_axes([0.05, 0.08, 0.42, 0.55])
    ax_rel.set_facecolor(_BG_COLOR)
    _chart_reliability(ax_rel, df)

    # Bottom right: Real vs Pronostico aggregated
    ax_comp = fig.add_axes([0.55, 0.08, 0.42, 0.55])
    ax_comp.set_facecolor(_BG_COLOR)
    _chart_real_vs_forecast(ax_comp, df)

    fig.suptitle(
        "EpiForecast-MX | Resumen Ejecutivo de Produccion",
        fontsize=15,
        fontweight="bold",
        color=_VERDE_IMSS,
        y=0.99,
    )
    return _fig_to_bytes(fig)


def _compute_kpis(df: pd.DataFrame) -> list[tuple[str, str, str, str]]:
    """Calcula 4 KPIs principales."""
    total_cases = pd.to_numeric(df["casos_52_semanas_futuro"], errors="coerce").sum()
    smape_med = pd.to_numeric(df["smape_prod"], errors="coerce").median()
    mase = pd.to_numeric(df["mase_prod"], errors="coerce")
    pct_beat_naive = (mase < 1.0).sum() / max(len(mase.dropna()), 1) * 100
    modelo_top = df["modelo_produccion"].value_counts().index[0]
    modelo_top_pct = df["modelo_produccion"].value_counts().iloc[0] / len(df) * 100

    return [
        (
            "Casos Proyectados 52 sem",
            f"{int(total_cases):,}",
            "Suma total 333 series",
            _VERDE_IMSS,
        ),
        ("SMAPE Mediano", f"{smape_med:.1f}%", "Error simetrico mediano", "#1565C0"),
        (
            "Superan Naive Seasonal",
            f"{pct_beat_naive:.0f}%",
            f"{int(mase[mase < 1].count())}/333 series con MASE < 1",
            "#E65100",
        ),
        (
            "Modelo Dominante",
            modelo_top,
            f"{modelo_top_pct:.0f}% de las 333 series",
            _MODEL_COLORS.get(modelo_top, _GRIS_OSCURO),
        ),
    ]


def _chart_reliability(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Mini-chart: % de series que superan naive por padecimiento."""
    _setup_ax(ax, "Fiabilidad del Modelo (MASE < 1 = supera naive)")
    pads = sorted(df["padecimiento"].unique())
    for pad in pads:
        sub = df[df["padecimiento"] == pad]
        mase = pd.to_numeric(sub["mase_prod"], errors="coerce").dropna()
        bins = [0, 0.5, 0.75, 1.0, 1.5, 3.0]
        labels_b = [
            "Excelente\n(<0.5)",
            "Bueno\n(0.5-0.75)",
            "Aceptable\n(0.75-1.0)",
            "Debil\n(1.0-1.5)",
            "Malo\n(>1.5)",
        ]
        counts, _ = np.histogram(mase.clip(0, 3), bins=bins)
        pad_key = next((k for k in _PAD_COLORS if k.lower() in pad.lower()), "")
        color = _PAD_COLORS.get(pad_key, _GRIS_MEDIO)
        x = np.arange(len(labels_b))
        offset = (pads.index(pad) - 1) * 0.25
        ax.bar(
            x + offset,
            counts,
            0.22,
            label=pad,
            color=color,
            alpha=0.8,
            edgecolor="white",
            linewidth=0.5,
        )

    ax.set_xticks(np.arange(len(labels_b)))
    ax.set_xticklabels(labels_b, fontsize=7)
    ax.set_ylabel("N. de series", fontsize=8, color=_GRIS_MEDIO)
    ax.legend(fontsize=7, framealpha=0.7)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)


def _chart_real_vs_forecast(ax: plt.Axes, df: pd.DataFrame) -> None:
    """Mini-chart: Real vs Pronostico agregado por padecimiento."""
    _setup_ax(ax, "Historico: Real vs Pronostico (52 semanas)")
    pads = sorted(df["padecimiento"].unique())
    # Solo modo general, no regiones ni Nacional
    gen = df[
        (df["sexo"] == "general")
        & (~df["entidad"].astype(str).str.startswith("region_"))
        & (df["entidad"] != "Nacional")
    ]

    real_totals = []
    fc_totals = []
    for pad in pads:
        sub = gen[gen["padecimiento"] == pad]
        real_totals.append(pd.to_numeric(sub["casos_prev_52_semanas_real"], errors="coerce").sum())
        fc_totals.append(pd.to_numeric(sub["casos_prev_52_semanas_pronos"], errors="coerce").sum())

    x = np.arange(len(pads))
    ax.bar(
        x - 0.15,
        real_totals,
        0.28,
        label="Realidad",
        color=_VERDE_IMSS,
        alpha=0.8,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.bar(
        x + 0.15,
        fc_totals,
        0.28,
        label="Pronostico",
        color="#1565C0",
        alpha=0.8,
        edgecolor="white",
        linewidth=0.5,
    )

    for i in range(len(pads)):
        if real_totals[i] > 0:
            pct = fc_totals[i] / real_totals[i] * 100
            ax.text(
                i,
                max(real_totals[i], fc_totals[i]) * 1.02,
                f"{pct:.0f}%",
                ha="center",
                fontsize=8,
                color=_GRIS_OSCURO,
                fontweight="bold",
            )

    ax.set_xticks(x)
    ax.set_xticklabels(pads, fontsize=9)
    ax.set_ylabel("Total de casos", fontsize=8, color=_GRIS_MEDIO)
    ax.legend(fontsize=8, framealpha=0.7)
    ax.grid(axis="y", alpha=0.3, linewidth=0.5)
    # Format y-axis with thousands separator
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------


def generate_all_charts(df: pd.DataFrame) -> list[tuple[str, BytesIO]]:
    """Genera los 6 graficos y retorna lista de (nombre, BytesIO PNG)."""
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
            "axes.unicode_minus": False,
        }
    )

    return [
        ("dashboard_ejecutivo", chart_executive_dashboard(df)),
        ("distribucion_modelos", chart_model_distribution(df)),
        ("smape_por_modelo", chart_smape_comparison(df)),
        ("top_entidades_casos", chart_top_entities(df)),
        ("precision_historica", chart_precision_distribution(df)),
        ("smape_vs_casos", chart_smape_vs_cases(df)),
    ]
