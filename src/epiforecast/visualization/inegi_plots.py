"""INEGI geographic and demographic visualization plots."""

from typing import Any

from matplotlib.axes import Axes
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── Category orderings for INEGI demographic classifications ─────────


_ORDEN_RATIO = ["Mayormente mujeres", "Balanceado", "Mayormente hombres"]
_ORDEN_TAMANO = ["Población baja", "Media-baja", "Media-alta", "Alta"]
_ORDEN_EXTENSION = ["Territorio pequeño", "Medio-pequeño", "Medio-grande", "Grande"]
_ORDEN_DENSIDAD = ["Baja", "Media-baja", "Media-alta", "Alta"]
_ORDEN_REGION = [
    "Metropolitana alta",
    "Urbana media",
    "Rural / dispersa",
    "Sur-Sureste vulnerable",
]


def _make_order_map(orden: list[str]) -> dict[str, int]:
    """Crea mapa de orden {categoría: posición} para sorting personalizado."""
    return {k: i for i, k in enumerate(orden)}


def _colors_for(
    series_cat: Any,
) -> tuple[list[Any], list[Line2D], list[Any]]:
    """Asigna colores tab10 a una serie categórica y retorna handles para leyenda."""
    cats = pd.Series(series_cat).astype("category")
    codes = cats.cat.codes
    cmap = plt.get_cmap("tab10")
    colors = [cmap(int(c) % 10) if c >= 0 else (0.7, 0.7, 0.7, 1.0) for c in codes]
    labels = list(cats.cat.categories)
    handles = [
        Line2D([0], [0], marker="s", linestyle="", color=cmap(i % 10), markersize=10)
        for i in range(len(labels))
    ]
    return colors, handles, labels


def _plot_bar(ax: Axes, dfx: pd.DataFrame, ycol: str, catcol: str, title: str) -> None:
    """Dibuja barras verticales coloreadas por categoría con leyenda."""
    x = list(range(len(dfx)))
    estados = dfx["Entidad federativa"]
    c, h, lbl = _colors_for(dfx[catcol])
    ax.bar(x, dfx[ycol], color=c)
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(estados, rotation=90)
    ax.legend(h, lbl, fontsize=8, loc="upper right")


def _sort_by(
    dfp: pd.DataFrame, cat_col: str, val_col: str, order_map: dict[str, int]
) -> pd.DataFrame:
    """Ordena DataFrame por columna categórica (orden custom) y valor numérico."""
    return dfp.sort_values(
        by=[cat_col, val_col],
        key=lambda s: s.map(order_map) if s.name == cat_col else s,
        ascending=[True, False],
    )


# ── Public API ───────────────────────────────────────────────────────


def barras_inegi(df: pd.DataFrame) -> None:
    """Genera panel de gráficos de barras demográficos INEGI por entidad federativa.

    Args:
        df: DataFrame INEGI con columnas de población, superficie, densidad y clasificaciones.
    """
    dfp = df.sort_values("Entidad federativa").reset_index(drop=True)

    map_tamano = _make_order_map(_ORDEN_TAMANO)
    map_extension = _make_order_map(_ORDEN_EXTENSION)
    map_densidad = _make_order_map(_ORDEN_DENSIDAD)
    map_ratio = _make_order_map(_ORDEN_RATIO)
    map_region = _make_order_map(_ORDEN_REGION)

    sorted_views = [
        (
            _sort_by(dfp, "tamano_poblacional_grupo_percentil", "Total", map_tamano),
            "Total",
            "tamano_poblacional_grupo_percentil",
            "Población total (color: tamaño percentil)",
        ),
        (
            _sort_by(dfp, "extension_territorial_percentil", "Superficie_km2", map_extension),
            "Superficie_km2",
            "extension_territorial_percentil",
            "Superficie km² (color: extensión percentil)",
        ),
        (
            _sort_by(dfp, "densidad_poblacional_percentil", "densidad_poblacion", map_densidad),
            "densidad_poblacion",
            "densidad_poblacional_percentil",
            "Densidad poblacional (color: densidad percentil)",
        ),
        (
            _sort_by(dfp, "ratio_h_m_cat", "ratio_h_m", map_ratio),
            "ratio_h_m",
            "ratio_h_m_cat",
            "Ratio H/M (color: categoría ratio)",
        ),
        (
            _sort_by(dfp, "ratio_h_m_cat", "Hombres", map_ratio),
            "Hombres",
            "ratio_h_m_cat",
            "Hombres (color: categoría ratio)",
        ),
        (
            _sort_by(dfp, "ratio_h_m_cat", "Mujeres", map_ratio),
            "Mujeres",
            "ratio_h_m_cat",
            "Mujeres (color: categoría ratio)",
        ),
    ]

    has_region = "region_salud_mental" in dfp.columns
    if has_region:
        df_region = _sort_by(dfp, "region_salud_mental", "Total", map_region)
        sorted_views.append(
            (df_region, "Total", "region_salud_mental", "Población total (color: región)")
        )
        sorted_views.append(
            (df_region, "densidad_poblacion", "region_salud_mental", "Densidad (color: región)")
        )

    nrows = 4 if has_region else 3
    fig, axes = plt.subplots(nrows, 2, figsize=(20, nrows * 4.5))

    for idx, (dfx, ycol, catcol, title) in enumerate(sorted_views):
        row, col = divmod(idx, 2)
        _plot_bar(axes[row, col], dfx, ycol, catcol, title)

    plt.tight_layout()
    plt.close(fig)


def boxplots_inegi(df: pd.DataFrame) -> None:
    """Genera panel de boxplots demográficos INEGI por categoría de clasificación.

    Args:
        df: DataFrame INEGI con columnas de población, superficie, densidad y clasificaciones.
    """
    tiene_region = "region_salud_mental" in df.columns
    nrows = 3 if tiene_region else 2
    fig, axes = plt.subplots(nrows, 2, figsize=(14, nrows * 5))

    dfp = df.copy()
    for col in ["densidad_poblacion", "Total"]:
        if col in dfp.columns:
            dfp.loc[dfp[col] <= 0, col] = pd.NA

    _boxplot_panel = [
        (
            "densidad_poblacion",
            "extension_territorial_percentil",
            "Densidad por extensión territorial (escala log)",
            "hab/km²",
            True,
        ),
        (
            "Total",
            "tamano_poblacional_grupo_percentil",
            "Población total por tamaño (escala log)",
            "Población",
            True,
        ),
        (
            "Superficie_km2",
            "extension_territorial_percentil",
            "Superficie por extensión territorial",
            "km²",
            False,
        ),
        ("ratio_h_m", "ratio_h_m_cat", "Ratio H/M por categoría", "Ratio H/M", False),
    ]

    if tiene_region:
        _boxplot_panel.extend(
            [
                (
                    "densidad_poblacion",
                    "region_salud_mental",
                    "Densidad por región salud mental (escala log)",
                    "hab/km²",
                    True,
                ),
                (
                    "Total",
                    "region_salud_mental",
                    "Población total por región salud mental (escala log)",
                    "Población",
                    True,
                ),
            ]
        )

    # Ensure ratio exists
    if "ratio_h_m" not in dfp.columns and {"Hombres", "Mujeres"}.issubset(dfp.columns):
        dfp["ratio_h_m"] = dfp["Hombres"] / dfp["Mujeres"].replace(0, np.nan)

    for idx, (col, by_col, title, ylabel, use_log) in enumerate(_boxplot_panel):
        row, c = divmod(idx, 2)
        dfp.boxplot(column=col, by=by_col, ax=axes[row, c], grid=False)
        if use_log:
            axes[row, c].set_yscale("log")
        axes[row, c].set_title(title)
        axes[row, c].set_xlabel("")
        axes[row, c].set_ylabel(ylabel)

    plt.suptitle("")
    plt.tight_layout()
    plt.close(fig)
