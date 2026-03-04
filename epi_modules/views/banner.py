"""ASCII art y banner de bienvenida."""

from datetime import datetime
import os
import platform

from rich.align import Align
from rich.console import Console

from ..theme import VERSION

BANNER_ART = r"""
[verde]    ███████╗██████╗ ██╗███████╗ ██████╗ ██████╗ ███████╗ ██████╗ █████╗ ███████╗████████╗[/verde]
[verde]    ██╔════╝██╔══██╗██║██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔══██╗██╔════╝╚══██╔══╝[/verde]
[dorado]    █████╗  ██████╔╝██║█████╗  ██║   ██║██████╔╝█████╗  ██║     ███████║███████╗   ██║   [/dorado]
[dorado]    ██╔══╝  ██╔═══╝ ██║██╔══╝  ██║   ██║██╔══██╗██╔══╝  ██║     ██╔══██║╚════██║   ██║   [/dorado]
[guinda]    ███████╗██║     ██║██║     ╚██████╔╝██║  ██║███████╗╚██████╗██║  ██║███████║   ██║   [/guinda]
[guinda]    ╚══════╝╚═╝     ╚═╝╚═╝      ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   [/guinda]
[dorado]                          ───── ▪ M X ▪ ─────[/dorado]
"""

TAGLINE = (
    "[gris]Instituto Tecnológico de Monterrey · Maestría en Inteligencia Artificial Aplicada\n"
    "Proyecto Integrador · Instituto Mexicano del Seguro Social[/gris]"
)


def show_banner(console: Console) -> None:
    """Muestra el banner principal con arte ASCII."""
    os.system("cls" if os.name == "nt" else "clear")
    console.print(BANNER_ART)
    console.print(Align.center(TAGLINE))
    console.print(
        Align.center(
            f"[sutil]v{VERSION} · {platform.system()} {platform.machine()} · "
            f"Python {platform.python_version()} · "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M')}[/sutil]"
        )
    )
    console.print()
