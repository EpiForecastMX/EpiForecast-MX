"""Time-series aggregation charts: national weekly trend by sex or IMSS health region."""

import contextlib
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
        subtitulo = _plot_by_sex(ax, df, conf_paleta_sexo)
    elif not agrupamiento_sexo and agrupamiento_entidad:
        subtitulo = _plot_by_region(ax, df)

    _add_covid_band(ax)
    ax.set_xlabel("Fecha", fontsize=11)
    ax.set_ylabel("Incrementos semanales", fontsize=11)
    ax.set_title(f"Evolución semanal nacional de {padecimiento} {subtitulo}".strip())
    ax.legend(fontsize=10)
    _apply_imss_style(ax, conf_paleta["cool_gray"])

    nombre = f"serie_tiempo_{padecimiento}.png"
    ruta = os.path.join(carpeta_salida, nombre)
    fig.tight_layout()
    fig.savefig(ruta, dpi=dpi, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return ruta


def _plot_by_sex(ax: plt.Axes, df: pd.DataFrame, paleta_sexo: dict) -> str:
    """Dibuja líneas de serie de tiempo separadas por sexo."""
    st = df.groupby("Fecha")[["incrementos_hombres", "incrementos_mujeres"]].sum()
    ax.plot(
        st.index,
        st["incrementos_hombres"],
        linewidth=1.2,
        alpha=0.8,
        color=paleta_sexo["Hombres"],
        label="Hombres",
    )
    ax.plot(
        st.index,
        st["incrementos_mujeres"],
        linewidth=1.2,
        alpha=0.8,
        color=paleta_sexo["Mujeres"],
        label="Mujeres",
    )
    return "por sexo"


def _plot_by_region(ax: plt.Axes, df: pd.DataFrame) -> str:
    """Dibuja líneas de serie de tiempo separadas por región de salud mental."""
    col_region = "region_salud_mental"
    st = (
        df.groupby(["Fecha", col_region])[["incrementos_hombres", "incrementos_mujeres"]]
        .sum()
        .assign(incrementos_totales=lambda g: g["incrementos_hombres"] + g["incrementos_mujeres"])
        .reset_index()
    )
    for region, datos in st.groupby(col_region):
        ax.plot(
            datos["Fecha"], datos["incrementos_totales"], linewidth=1.2, alpha=0.8, label=region
        )
    return f"por {col_region}"


def _add_covid_band(ax: plt.Axes) -> None:
    """Agrega franja semitransparente del periodo COVID-19."""
    with contextlib.suppress(ValueError, TypeError):
        ax.axvspan(
            pd.Timestamp(COVID_START),
            pd.Timestamp(COVID_END),
            alpha=0.1,
            color="red",
            label="Covid",
        )  # type: ignore[arg-type]


def _apply_imss_style(ax: plt.Axes, c_gray: str) -> None:
    """Aplica estilo minimalista IMSS a los ejes."""
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(c_gray)
        ax.spines[spine].set_linewidth(0.6)
    ax.yaxis.grid(True, alpha=0.3, color="gray", linestyle="--", linewidth=0.5)
    ax.xaxis.grid(False)
