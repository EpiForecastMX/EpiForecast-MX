"""INEGI tabular summaries and EDA console output using Rich."""

from typing import Literal

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from epiforecast.visualization.inegi_plots import barras_inegi, boxplots_inegi

console = Console()


def _fmt(v, nd=2):
    if pd.isna(v):
        return ""
    if isinstance(v, int | float) and float(v).is_integer():
        return f"{int(v):,}"
    if isinstance(v, int | float):
        return f"{v:,.{nd}f}"
    return str(v)


def _print_df(df: pd.DataFrame, title: str, max_rows: int = 10, nd: int = 2):
    dfx = df.head(max_rows).copy()
    t = Table(title=title, show_lines=False)
    for c in dfx.columns:
        justify: Literal["default", "left", "center", "right", "full"] = (
            "right" if pd.api.types.is_numeric_dtype(dfx[c]) else "left"
        )
        t.add_column(str(c), justify=justify, overflow="fold")
    for _, row in dfx.iterrows():
        t.add_row(*[_fmt(row[c], nd=nd) for c in dfx.columns])
    console.print(t)


def _print_series(s: pd.Series, title: str, nd: int = 2):
    t = Table(title=title)
    t.add_column("Categoría", justify="left", overflow="fold")
    t.add_column("Conteo", justify="right")
    for idx, val in s.items():
        t.add_row(str(idx), _fmt(val, nd=nd))
    console.print(t)


def eda_inegi(df: pd.DataFrame):
    """Ejecuta EDA interactivo de datos INEGI con tablas Rich y gráficos matplotlib.

    Args:
        df: DataFrame INEGI con datos demográficos y clasificaciones por estado.
    """
    nan = df.isna().sum().sort_values(ascending=False)
    nan = nan[nan > 0]
    if len(nan) == 0:
        console.print(Panel("Sin valores NaN.", title="NaN", expand=False))
    else:
        _print_series(nan, "Valores NaN por columna", nd=0)

    if "region_salud_mental" in df.columns:
        faltantes = sorted(
            df.loc[df["region_salud_mental"].isna(), "Entidad federativa"].dropna().unique()
        )
        if faltantes:
            console.print(
                Panel(
                    ", ".join(faltantes), title="⚠️ Estados sin region_salud_mental", expand=False
                )
            )

    dfp = df.sort_values("Entidad federativa").reset_index(drop=True)

    _print_df(dfp, "Vista general (head)", max_rows=8, nd=2)

    cols_num = ["Hombres", "Mujeres", "Total", "Superficie_km2", "densidad_poblacion", "ratio_h_m"]
    cols_num = [c for c in cols_num if c in dfp.columns]
    desc = dfp[cols_num].describe().T.reset_index().rename(columns={"index": "variable"})
    _print_df(desc, "Descriptivos numéricos", max_rows=50, nd=2)

    if "Total" in dfp.columns:
        _print_df(
            dfp.sort_values("Total", ascending=False)[["Entidad federativa", "Total"]],
            "Top 5: Población total",
            max_rows=5,
            nd=0,
        )

    if "densidad_poblacion" in dfp.columns:
        _print_df(
            dfp.sort_values("densidad_poblacion", ascending=False)[
                ["Entidad federativa", "densidad_poblacion"]
            ],
            "Top 5: Densidad poblacional (hab/km²)",
            max_rows=5,
            nd=2,
        )

    if "Superficie_km2" in dfp.columns:
        _print_df(
            dfp.sort_values("Superficie_km2", ascending=False)[
                ["Entidad federativa", "Superficie_km2"]
            ],
            "Top 5: Superficie (km²)",
            max_rows=5,
            nd=0,
        )

    if "region_salud_mental" in dfp.columns:
        _print_series(
            dfp["region_salud_mental"].value_counts(dropna=False),
            "Conteo: Región salud mental",
            nd=0,
        )

    for col, title in [
        ("tamano_poblacional_predefinido", "Conteo: Tamaño poblacional (rangos fijos)"),
        ("tamano_poblacional_grupo_percentil", "Conteo: Tamaño poblacional (percentiles)"),
        ("extension_territorial_percentil", "Conteo: Extensión territorial (percentiles)"),
        ("densidad_poblacional_percentil", "Conteo: Densidad poblacional (percentiles)"),
        ("ratio_h_m_cat", "Conteo: Ratio H/M (categoría)"),
    ]:
        if col in dfp.columns:
            _print_series(dfp[col].value_counts(dropna=False), title, nd=0)

    barras_inegi(dfp)
    boxplots_inegi(dfp)
