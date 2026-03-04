"""Tabla de targets disponibles del Makefile."""

from rich import box
from rich.console import Console
from rich.table import Table

from ..engine import EpiEngine
from ..theme import RISK_COLORS, RISK_ICONS, RISK_LABELS


def show_targets(console: Console, engine: EpiEngine) -> None:
    """Tabla rica de targets disponibles con categorizacion por riesgo."""
    if not engine.targets:
        console.print("[gris]  No se encontraron targets en el Makefile.[/gris]")
        return

    table = Table(
        title="[dorado]DICCIONARIO DE OPERACIONES[/dorado]",
        show_header=True,
        header_style="dorado",
        border_style="verde.dim",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("", width=3, justify="center")
    table.add_column("Target", style="exito", min_width=20)
    table.add_column("Descripción", style="blanco")
    table.add_column("Riesgo", justify="center", width=8)

    for name, desc in sorted(engine.targets.items()):
        risk = engine.assess_risk(name)
        icon = RISK_ICONS[risk]
        risk_label = f"[{RISK_COLORS[risk]}]{RISK_LABELS[risk]}[/{RISK_COLORS[risk]}]"
        table.add_row(icon, f"make {name}", desc, risk_label)

    console.print()
    console.print(table)
    console.print()
