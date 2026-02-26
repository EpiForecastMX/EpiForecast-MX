"""Time-series aggregation charts: national weekly trend by sex or IMSS health region."""

import os

import matplotlib.pyplot as plt
import pandas as pd

from epiforecast.constants import COVID_END, COVID_START


def serie_tiempo(
    df: pd.DataFrame,
    padecimiento: str,
    carpeta_salida: str,
    dpi: int,
    conf_paleta: dict,
    conf_paleta_sexo: dict,
    agrupamiento_sexo: bool = True,
    agrupamiento_entidad: bool = False,
) -> str | None:
    """Genera gráfico de serie de tiempo semanal nacional agrupada por sexo o región.

    Args:
        df:                   DataFrame con columnas Fecha, incrementos_hombres, incrementos_mujeres.
        padecimiento:         Nombre del padecimiento para el título y nombre de archivo.
        carpeta_salida:       Directorio donde se guarda el PNG.
        dpi:                  Resolución de guardado en puntos por pulgada.
        conf_paleta:          Dict de colores IMSS_COLORS (usa clave ``cool_gray``).
        conf_paleta_sexo:     Dict de colores por sexo (claves ``Hombres``, ``Mujeres``).
        agrupamiento_sexo:    Si True, grafica líneas separadas por sexo.
        agrupamiento_entidad: Si True, grafica líneas separadas por región de salud mental.

    Returns:
        Ruta del archivo PNG generado, o ``None`` si no se pudo crear.
    """
    fig, ax = plt.subplots(figsize=(16, 4))
    subtitulo = ""

    if agrupamiento_sexo and not agrupamiento_entidad:
        st = df.groupby("Fecha")[["incrementos_hombres", "incrementos_mujeres"]].sum()
        ax.plot(
            st.index,
            st["incrementos_hombres"],
            linewidth=1.2,
            alpha=0.8,
            color=conf_paleta_sexo["Hombres"],
            label="Hombres",
        )
        ax.plot(
            st.index,
            st["incrementos_mujeres"],
            linewidth=1.2,
            alpha=0.8,
            color=conf_paleta_sexo["Mujeres"],
            label="Mujeres",
        )
        subtitulo = "por sexo"

    elif not agrupamiento_sexo and agrupamiento_entidad:
        col_region = "region_salud_mental"
        st = (
            df.groupby(["Fecha", col_region])[["incrementos_hombres", "incrementos_mujeres"]]
            .sum()
            .assign(
                incrementos_totales=lambda g: g["incrementos_hombres"] + g["incrementos_mujeres"]
            )
            .reset_index()
        )
        for region, datos in st.groupby(col_region):
            ax.plot(
                datos["Fecha"],
                datos["incrementos_totales"],
                linewidth=1.2,
                alpha=0.8,
                label=region,
            )
        subtitulo = f"por {col_region}"

    try:
        covid_start = pd.Timestamp(COVID_START)
        covid_end = pd.Timestamp(COVID_END)
        ax.axvspan(covid_start, covid_end, alpha=0.1, color="red", label="Covid")  # type: ignore[arg-type]
    except (ValueError, TypeError):
        pass

    ax.set_xlabel("Fecha", fontsize=11)
    ax.set_ylabel("Incrementos semanales", fontsize=11)
    ax.set_title(f"Evolución semanal nacional de {padecimiento} {subtitulo}".strip())
    ax.legend(fontsize=10)

    # Estilo IMSS minimalista (equivalente a GraficosHelper._aplicar_estilo_ax)
    c_gray = conf_paleta["cool_gray"]
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(c_gray)
        ax.spines[spine].set_linewidth(0.6)
    ax.yaxis.grid(True, alpha=0.3, color="gray", linestyle="--", linewidth=0.5)
    ax.xaxis.grid(False)

    # Guardar
    nombre = f"serie_tiempo_{padecimiento}.png"
    ruta = os.path.join(carpeta_salida, nombre)
    fig.tight_layout()
    fig.savefig(ruta, dpi=dpi, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return ruta
