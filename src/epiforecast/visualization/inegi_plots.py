"""INEGI geographic and demographic visualization plots."""

import matplotlib.pyplot as plt
import pandas as pd


def barras_inegi(df: pd.DataFrame):
    """Genera panel de gráficos de barras demográficos INEGI por entidad federativa.

    Args:
        df: DataFrame INEGI con columnas de población, superficie, densidad y clasificaciones.
    """
    dfp = df.sort_values("Entidad federativa").reset_index(drop=True)

    # helper colores
    def colors_for(series_cat):
        """Asigna colores tab10 a una serie categórica y retorna handles para leyenda."""

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
    orden_region = [
        "Metropolitana alta",
        "Urbana media",
        "Rural / dispersa",
        "Sur-Sureste vulnerable",
    ]

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
        """Dibuja barras verticales coloreadas por categoría con leyenda."""

        x = list(range(len(dfx)))
        estados = dfx["Entidad federativa"]
        c, h, l = colors_for(dfx[catcol])
        ax.bar(x, dfx[ycol], color=c)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(estados, rotation=90)
        ax.legend(h, l, fontsize=8, loc="upper right")

    plot_bar(
        axes[0, 0],
        df_total,
        "Total",
        "tamano_poblacional_grupo_percentil",
        "Población total (color: tamaño percentil)",
    )
    plot_bar(
        axes[0, 1],
        df_sup,
        "Superficie_km2",
        "extension_territorial_percentil",
        "Superficie km² (color: extensión percentil)",
    )
    plot_bar(
        axes[1, 0],
        df_den,
        "densidad_poblacion",
        "densidad_poblacional_percentil",
        "Densidad poblacional (color: densidad percentil)",
    )
    plot_bar(
        axes[1, 1], df_ratio, "ratio_h_m", "ratio_h_m_cat", "Ratio H/M (color: categoría ratio)"
    )
    plot_bar(axes[2, 0], df_h, "Hombres", "ratio_h_m_cat", "Hombres (color: categoría ratio)")
    plot_bar(axes[2, 1], df_m, "Mujeres", "ratio_h_m_cat", "Mujeres (color: categoría ratio)")

    if df_total_region is not None:
        plot_bar(
            axes[3, 0],
            df_total_region,
            "Total",
            "region_salud_mental",
            "Población total (color: región)",
        )
        plot_bar(
            axes[3, 1],
            df_total_region,
            "densidad_poblacion",
            "region_salud_mental",
            "Densidad (color: región)",
        )

    plt.tight_layout()
    plt.show()


def boxplots_inegi(df):
    """Genera panel de boxplots demográficos INEGI por categoría de clasificación.

    Args:
        df: DataFrame INEGI con columnas de población, superficie, densidad y clasificaciones.
    """
    import matplotlib.pyplot as plt
    import pandas as pd

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
        grid=False,
    )
    axes[0, 0].set_yscale("log")
    axes[0, 0].set_title("Densidad por extensión territorial (escala log)")
    axes[0, 0].set_xlabel("")
    axes[0, 0].set_ylabel("hab/km²")

    # 2) Población total por tamaño poblacional (LOG)
    dfp.boxplot(column="Total", by="tamano_poblacional_grupo_percentil", ax=axes[0, 1], grid=False)
    axes[0, 1].set_yscale("log")
    axes[0, 1].set_title("Población total por tamaño (escala log)")
    axes[0, 1].set_xlabel("")
    axes[0, 1].set_ylabel("Población")

    # 3) Superficie por extensión (LINEAL)
    dfp.boxplot(
        column="Superficie_km2", by="extension_territorial_percentil", ax=axes[1, 0], grid=False
    )
    axes[1, 0].set_title("Superficie por extensión territorial")
    axes[1, 0].set_xlabel("")
    axes[1, 0].set_ylabel("km²")

    # 4) Ratio H/M por categoría (LINEAL)
    if "ratio_h_m" not in dfp.columns and {"Hombres", "Mujeres"}.issubset(dfp.columns):
        dfp["ratio_h_m"] = dfp["Hombres"] / dfp["Mujeres"].replace({0: pd.NA})

    dfp.boxplot(column="ratio_h_m", by="ratio_h_m_cat", ax=axes[1, 1], grid=False)
    axes[1, 1].set_title("Ratio H/M por categoría")
    axes[1, 1].set_xlabel("")
    axes[1, 1].set_ylabel("Ratio H/M")

    if tiene_region:
        dfp.boxplot(
            column="densidad_poblacion", by="region_salud_mental", ax=axes[2, 0], grid=False
        )
        axes[2, 0].set_yscale("log")
        axes[2, 0].set_title("Densidad por región salud mental (escala log)")
        axes[2, 0].set_xlabel("")
        axes[2, 0].set_ylabel("hab/km²")

        dfp.boxplot(column="Total", by="region_salud_mental", ax=axes[2, 1], grid=False)
        axes[2, 1].set_yscale("log")
        axes[2, 1].set_title("Población total por región salud mental (escala log)")
        axes[2, 1].set_xlabel("")
        axes[2, 1].set_ylabel("Población")

    plt.suptitle("")
    plt.tight_layout()
    plt.show()
