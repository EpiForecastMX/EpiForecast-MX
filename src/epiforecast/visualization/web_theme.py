"""Tema oscuro 'Clinical Indigo' para los gráficos web de Dengue.

Paleta y helper de ejes compartidos por ``scripts/build_dengue_web.py`` y
``scripts/eda_dengue_charts.py`` (misma colorimetría que el landing y el EpiBot),
para no duplicar las constantes ni el styling de Axes en cada script.
"""

from matplotlib.axes import Axes
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# Paleta Clinical Indigo (alineada con el landing / EpiBot).
BG = "#131C30"
BG_DEEP = "#0E1424"
GRID = "#243150"
TEXT = "#E7ECF5"
MUTED = "#9DB0D0"
AMBER = "#F59E0B"  # acento Dengue
MINT = "#2DD4BF"
PINK = "#F472B6"

SEMANAS_ANIO = 52
DPI = 150  # resolución estándar de los charts web (fuente única; usar en plt.subplots directos)


def dark_fig(
    figsize: tuple[float, float], dpi: int = DPI, grid: bool = False
) -> tuple[Figure, Axes]:
    """Crea (fig, ax) con fondo índigo y ejes/etiquetas en la paleta Clinical Indigo."""
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(TEXT)
    if grid:
        ax.grid(True, color=GRID, linewidth=0.6, alpha=0.6)
    return fig, ax
