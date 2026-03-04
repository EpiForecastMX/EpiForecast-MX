"""Panel de salud del sistema al arranque."""

from pathlib import Path
import shutil

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..theme import ICO_FAIL, ICO_OK


def show_health_dashboard(
    console: Console,
    errors: list[str],
    warnings_list: list[str],
    n_targets: int,
    has_api_key: bool,
) -> None:
    """Panel de salud del sistema al arranque."""
    checks = [
        ("GNU Make", shutil.which("make") is not None),
        ("Python", bool(shutil.which("python3") or shutil.which("python"))),
        ("Git", shutil.which("git") is not None),
        ("Makefile", Path("Makefile").exists()),
        ("Gemini API", has_api_key),
        ("DVC", shutil.which("dvc") is not None),
        ("Pytest", shutil.which("pytest") is not None),
    ]

    table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    table.add_column("Componente", min_width=14)
    table.add_column("Estado", min_width=4)

    for name, ok in checks:
        icon = ICO_OK if ok else ICO_FAIL
        label = f"[blanco]{name}[/blanco]" if ok else f"[gris]{name}[/gris]"
        table.add_row(label, icon)

    targets_text = (
        f"[dorado]{n_targets}[/dorado] targets detectados"
        if n_targets
        else "[guinda]Sin targets[/guinda]"
    )

    health_panel = Panel(
        table,
        title="[dorado]DIAGNÓSTICO DEL SISTEMA[/dorado]",
        subtitle=targets_text,
        border_style="verde",
        padding=(1, 2),
    )
    console.print(health_panel)

    if warnings_list:
        for w in warnings_list:
            console.print(f"  [alerta]{w}[/alerta]")
        console.print()
