import pandas as pd
import matplotlib.pyplot as plt
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def _fmt(v, nd=2):
    if pd.isna(v):
        return ""
    if isinstance(v, (int, float)) and float(v).is_integer():
        return f"{int(v):,}"
    if isinstance(v, (int, float)):
        return f"{v:,.{nd}f}"
    return str(v)

def _print_df(df: pd.DataFrame, title: str, max_rows: int = 10, nd: int = 2):
    dfx = df.head(max_rows).copy()
    t = Table(title=title, show_lines=False)
    for c in dfx.columns:
        justify = "right" if pd.api.types.is_numeric_dtype(dfx[c]) else "left"
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

def barras_inegi(df: pd.DataFrame):
    dfp = df.sort_values("Entidad federativa").reset_index(drop=True)

    # helper colores
    def colors_for(series_cat):
        cats = pd.Series(series_cat).astype("category")
        codes = cats.cat.codes
        cmap = plt.get_cmap("tab10")
        colors = [cmap(int(c) % 10) if c >= 0 else (0.7, 0.7, 0.7, 1.0) for c in codes]
        labels = list(cats.cat.categories)
        handles = [
            plt.Line2D([0], [0], marker="s", linestyle="", color=cmap(i % 10), markersize=10)
            for i in range(len(labels))
        ]
        return colors, handles, labels

    # órdenes
    orden_ratio = ["Mayormente mujeres", "Balanceado", "Mayormente hombres"]
    orden_tamano = ["Población baja", "Media-baja", "Media-alta", "Alta"]
    orden_extension = ["Territorio pequeño", "Medio-pequeño", "Medio-grande", "Grande"]
    orden_densidad = ["Baja", "Media-baja", "Media-alta", "Alta"]
    orden_region = ["Metropolitana alta", "Urbana media", "Rural / dispersa", "Sur-Sureste vulnerable"]

    map_ratio = {k: i for i, k in enumerate(orden_ratio)}
    map_tamano = {k: i for i, k in enumerate(orden_tamano)}
    map_extension = {k: i for i, k in enumerate(orden_extension)}
    map_densidad = {k: i for i, k in enumerate(orden_densidad)}
    map_region = {k: i for i, k in enumerate(orden_region)}

    # ordenados
    df_total = dfp.sort_values(
        by=["tamano_poblacional_grupo_percentil", "Total"],
        key=lambda s: s.map(map_tamano) if s.name == "tamano_poblacional_grupo_percentil" else s,
        ascending=[True, False],
    )
    df_sup = dfp.sort_values(
        by=["extension_territorial_percentil", "Superficie_km2"],
        key=lambda s: s.map(map_extension) if s.name == "extension_territorial_percentil" else s,
        ascending=[True, False],
    )
    df_den = dfp.sort_values(
        by=["densidad_poblacional_percentil", "densidad_poblacion"],
        key=lambda s: s.map(map_densidad) if s.name == "densidad_poblacional_percentil" else s,
        ascending=[True, False],
    )
    df_ratio = dfp.sort_values(
        by=["ratio_h_m_cat", "ratio_h_m"],
        key=lambda s: s.map(map_ratio) if s.name == "ratio_h_m_cat" else s,
        ascending=[True, False],
    )
    df_h = dfp.sort_values(
        by=["ratio_h_m_cat", "Hombres"],
        key=lambda s: s.map(map_ratio) if s.name == "ratio_h_m_cat" else s,
        ascending=[True, False],
    )
    df_m = dfp.sort_values(
        by=["ratio_h_m_cat", "Mujeres"],
        key=lambda s: s.map(map_ratio) if s.name == "ratio_h_m_cat" else s,
        ascending=[True, False],
    )

    df_total_region = None
    if "region_salud_mental" in dfp.columns:
        df_total_region = dfp.sort_values(
            by=["region_salud_mental", "Total"],
            key=lambda s: s.map(map_region) if s.name == "region_salud_mental" else s,
            ascending=[True, False],
        )

    # figura
    if df_total_region is not None:
        fig, axes = plt.subplots(4, 2, figsize=(20, 18))
    else:
        fig, axes = plt.subplots(3, 2, figsize=(20, 14))

    def plot_bar(ax, dfx, ycol, catcol, title):
        x = list(range(len(dfx)))
        estados = dfx["Entidad federativa"]
        c, h, l = colors_for(dfx[catcol])
        ax.bar(x, dfx[ycol], color=c)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(estados, rotation=90)
        ax.legend(h, l, fontsize=8, loc="upper right")

    plot_bar(axes[0, 0], df_total, "Total", "tamano_poblacional_grupo_percentil",
             "Población total (color: tamaño percentil)")
    plot_bar(axes[0, 1], df_sup, "Superficie_km2", "extension_territorial_percentil",
             "Superficie km² (color: extensión percentil)")
    plot_bar(axes[1, 0], df_den, "densidad_poblacion", "densidad_poblacional_percentil",
             "Densidad poblacional (color: densidad percentil)")
    plot_bar(axes[1, 1], df_ratio, "ratio_h_m", "ratio_h_m_cat",
             "Ratio H/M (color: categoría ratio)")
    plot_bar(axes[2, 0], df_h, "Hombres", "ratio_h_m_cat",
             "Hombres (color: categoría ratio)")
    plot_bar(axes[2, 1], df_m, "Mujeres", "ratio_h_m_cat",
             "Mujeres (color: categoría ratio)")

    if df_total_region is not None:
        plot_bar(axes[3, 0], df_total_region, "Total", "region_salud_mental",
                 "Población total (color: región)")
        plot_bar(axes[3, 1], df_total_region, "densidad_poblacion", "region_salud_mental",
                 "Densidad (color: región)")

    plt.tight_layout()
    plt.show()


def boxplots_inegi(df):
    import pandas as pd
    import matplotlib.pyplot as plt

    # Si existe region_salud_mental: agregamos 1 fila extra (3x2). Si no: 2x2 como antes.
    tiene_region = "region_salud_mental" in df.columns

    if tiene_region:
        fig, axes = plt.subplots(3, 2, figsize=(14, 14))
    else:
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    dfp = df.copy()

    # Log solo funciona con valores > 0
    for col in ["densidad_poblacion", "Total"]:
        if col in dfp.columns:
            dfp.loc[dfp[col] <= 0, col] = pd.NA

    # 1) Densidad por extensión (LOG)
    dfp.boxplot(
        column="densidad_poblacion",
        by="extension_territorial_percentil",
        ax=axes[0, 0],
        grid=False
    )
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_title("Densidad por extensión territorial (escala log)")
    axes[0, 0].set_xlabel("")
    axes[0, 0].set_ylabel("hab/km²")

    # 2) Población total por tamaño poblacional (LOG)
    dfp.boxplot(
        column="Total",
        by="tamano_poblacional_grupo_percentil",
        ax=axes[0, 1],
        grid=False
    )
    axes[0, 1].set_yscale("log")
    axes[0, 1].set_title("Población total por tamaño (escala log)")
    axes[0, 1].set_xlabel("")
    axes[0, 1].set_ylabel("Población")

    # 3) Superficie por extensión (LINEAL)
    dfp.boxplot(
        column="Superficie_km2",
        by="extension_territorial_percentil",
        ax=axes[1, 0],
        grid=False
    )
    axes[1, 0].set_title("Superficie por extensión territorial")
    axes[1, 0].set_xlabel("")
    axes[1, 0].set_ylabel("km²")

    # 4) Ratio H/M por categoría (LINEAL)
    if "ratio_h_m" not in dfp.columns and {"Hombres", "Mujeres"}.issubset(dfp.columns):
        dfp["ratio_h_m"] = dfp["Hombres"] / dfp["Mujeres"].replace({0: pd.NA})

    dfp.boxplot(
        column="ratio_h_m",
        by="ratio_h_m_cat",
        ax=axes[1, 1],
        grid=False
    )
    axes[1, 1].set_title("Ratio H/M por categoría")
    axes[1, 1].set_xlabel("")
    axes[1, 1].set_ylabel("Ratio H/M")

    if tiene_region:
        dfp.boxplot(
            column="densidad_poblacion",
            by="region_salud_mental",
            ax=axes[2, 0],
            grid=False
        )
        axes[2, 0].set_yscale("log")
        axes[2, 0].set_title("Densidad por región salud mental (escala log)")
        axes[2, 0].set_xlabel("")
        axes[2, 0].set_ylabel("hab/km²")

        dfp.boxplot(
            column="Total",
            by="region_salud_mental",
            ax=axes[2, 1],
            grid=False
        )
        axes[2, 1].set_yscale("log")
        axes[2, 1].set_title("Población total por región salud mental (escala log)")
        axes[2, 1].set_xlabel("")
        axes[2, 1].set_ylabel("Población")

    plt.suptitle("")
    plt.tight_layout()
    plt.show()


def eda_inegi(df: pd.DataFrame):
    nan = df.isna().sum().sort_values(ascending=False)
    nan = nan[nan > 0]
    if len(nan) == 0:
        console.print(Panel("Sin valores NaN.", title="NaN", expand=False))
    else:
        _print_series(nan, "Valores NaN por columna", nd=0)

    if "region_salud_mental" in df.columns:
        faltantes = sorted(df.loc[df["region_salud_mental"].isna(), "Entidad federativa"].dropna().unique())
        if faltantes:
            console.print(Panel(", ".join(faltantes), title="⚠️ Estados sin region_salud_mental", expand=False))

    dfp = df.sort_values("Entidad federativa").reset_index(drop=True)

    _print_df(dfp, "Vista general (head)", max_rows=8, nd=2)

    cols_num = ["Hombres", "Mujeres", "Total", "Superficie_km2", "densidad_poblacion", "ratio_h_m"]
    cols_num = [c for c in cols_num if c in dfp.columns]
    desc = dfp[cols_num].describe().T.reset_index().rename(columns={"index": "variable"})
    _print_df(desc, "Descriptivos numéricos", max_rows=50, nd=2)

    if "Total" in dfp.columns:
        _print_df(dfp.sort_values("Total", ascending=False)[["Entidad federativa", "Total"]],
                  "Top 5: Población total", max_rows=5, nd=0)

    if "densidad_poblacion" in dfp.columns:
        _print_df(dfp.sort_values("densidad_poblacion", ascending=False)[["Entidad federativa", "densidad_poblacion"]],
                  "Top 5: Densidad poblacional (hab/km²)", max_rows=5, nd=2)

    if "Superficie_km2" in dfp.columns:
        _print_df(dfp.sort_values("Superficie_km2", ascending=False)[["Entidad federativa", "Superficie_km2"]],
                  "Top 5: Superficie (km²)", max_rows=5, nd=0)

    if "region_salud_mental" in dfp.columns:
        _print_series(dfp["region_salud_mental"].value_counts(dropna=False), "Conteo: Región salud mental", nd=0)

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
