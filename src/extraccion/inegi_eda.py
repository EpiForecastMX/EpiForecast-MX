def eda_inegi(df):
    import pandas as pd
    import matplotlib.pyplot as plt

    # ===== Conteo de NaN =====
    print("\n=== Conteo de valores NaN por columna ===")
    print(df.isna().sum())

    # ===== Formato tablas (sin notación exponencial) =====
    pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
    pd.set_option("display.max_rows", 100)

    # ===== Orden base (para tablas) =====
    dfp = df.sort_values("Entidad federativa").reset_index(drop=True)

    # ===== Texto útil =====
    print("\n=== Vista general ===")
    print(dfp.head())

    print("\n=== Descriptivos numéricos ===")
    cols_num = ["Hombres", "Mujeres", "Total", "Superficie_km2", "densidad_poblacion", "ratio_h_m"]
    cols_num = [c for c in cols_num if c in dfp.columns]
    print(dfp[cols_num].describe())

    print("\n=== Rankings ===")
    print(dfp.sort_values("Total", ascending=False)[["Entidad federativa", "Total"]].head(5))
    print(dfp.sort_values("densidad_poblacion", ascending=False)[["Entidad federativa", "densidad_poblacion"]].head(5))
    print(dfp.sort_values("Superficie_km2", ascending=False)[["Entidad federativa", "Superficie_km2"]].head(5))

    print("\n=== Conteos categóricos ===")
    print("\nTamaño poblacional (rangos fijos):")
    print(dfp["tamano_poblacional_predefinido"].value_counts())
    print("\nTamaño poblacional (percentiles):")
    print(dfp["tamano_poblacional_grupo_percentil"].value_counts())
    print("\nExtensión territorial (percentiles):")
    print(dfp["extension_territorial_percentil"].value_counts())
    print("\nDensidad poblacional (percentiles):")
    print(dfp["densidad_poblacional_percentil"].value_counts())
    print("\nRatio H/M:")
    print(dfp["ratio_h_m_cat"].value_counts())

    # ===== Asegurar ratio_h_m si no existe =====
    if "ratio_h_m" not in dfp.columns:
        dfp["ratio_h_m"] = dfp["Hombres"] / dfp["Mujeres"].replace({0: pd.NA})

    # ===== Helper: colores por categoría (sin paleta fija) =====
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

    # ===== Ordenes definidos (categorías) =====
    orden_ratio = ["Mayormente mujeres", "Balanceado", "Mayormente hombres"]
    orden_tamano = ["Población baja", "Media-baja", "Media-alta", "Alta"]
    orden_extension = ["Territorio pequeño", "Medio-pequeño", "Medio-grande", "Grande"]
    orden_densidad = ["Baja", "Media-baja", "Media-alta", "Alta"]

    map_ratio = {k: i for i, k in enumerate(orden_ratio)}
    map_tamano = {k: i for i, k in enumerate(orden_tamano)}
    map_extension = {k: i for i, k in enumerate(orden_extension)}
    map_densidad = {k: i for i, k in enumerate(orden_densidad)}

    # ===== DataFrames por gráfica (ordenados por categoría y valor) =====
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

    # ===== Figura única (barras con color por categoría) =====
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

    plot_bar(
        axes[0, 0], df_total, "Total", "tamano_poblacional_grupo_percentil",
        "Población total (orden: tamaño percentil, color: tamaño percentil)"
    )
    plot_bar(
        axes[0, 1], df_sup, "Superficie_km2", "extension_territorial_percentil",
        "Superficie km² (orden: extensión percentil, color: extensión percentil)"
    )
    plot_bar(
        axes[1, 0], df_den, "densidad_poblacion", "densidad_poblacional_percentil",
        "Densidad poblacional (orden: densidad percentil, color: densidad percentil)"
    )
    plot_bar(
        axes[1, 1], df_ratio, "ratio_h_m", "ratio_h_m_cat",
        "Ratio H/M (orden: categoría ratio, color: categoría ratio)"
    )
    plot_bar(
        axes[2, 0], df_h, "Hombres", "ratio_h_m_cat",
        "Población hombres (orden: categoría ratio, color: categoría ratio)"
    )
    plot_bar(
        axes[2, 1], df_m, "Mujeres", "ratio_h_m_cat",
        "Población mujeres (orden: categoría ratio, color: categoría ratio)"
    )

    plt.tight_layout()
    plt.show()
