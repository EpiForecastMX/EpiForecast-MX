"""Gate de aprobacion, tarjeta de resultado y barra de progreso."""

from datetime import timedelta

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ..engine import EpiEngine
from ..theme import RISK_COLORS, RISK_ICONS, RISK_LABELS


def show_approval_gate(
    console: Console,
    engine: EpiEngine,
    commands: list[str],
    explanation: str = "",
) -> bool:
    """Gate de aprobacion visual con analisis de riesgo."""
    console.print()
    console.print(Rule("[dorado]SOLICITUD DE APROBACIÓN[/dorado]", style="dorado"))
    console.print()

    if explanation:
        console.print(f"  [info]{explanation}[/info]")
        console.print()

    table = Table(
        show_header=True,
        header_style="dorado",
        box=box.SIMPLE_HEAVY,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("#", width=3, justify="center", style="gris")
    table.add_column("Comando", style="blanco")
    table.add_column("Riesgo", justify="center", width=10)
    table.add_column("Categoría", width=14, style="gris")

    overall_risk = "low"
    for i, cmd in enumerate(commands, 1):
        risk = engine.assess_risk(cmd)
        if risk == "high":
            overall_risk = "high"
        elif risk == "medium" and overall_risk != "high":
            overall_risk = "medium"

        risk_display = (
            f"{RISK_ICONS[risk]} [{RISK_COLORS[risk]}]{RISK_LABELS[risk]}[/{RISK_COLORS[risk]}]"
        )
        category = "Lectura" if risk == "low" else "Proceso" if risk == "medium" else "Destructivo"
        table.add_row(str(i), f"[exito]{cmd}[/exito]", risk_display, category)

    console.print(table)
    console.print()

    risk_bar = (
        f"  {RISK_ICONS[overall_risk]} Riesgo general: "
        f"[{RISK_COLORS[overall_risk]}]{RISK_LABELS[overall_risk]}"
        f"[/{RISK_COLORS[overall_risk]}]"
    )
    console.print(risk_bar)

    if overall_risk == "high":
        console.print()
        console.print(
            Panel(
                "[guinda]Este plan incluye operaciones destructivas.\n"
                "   Los datos eliminados podrían no ser recuperables.[/guinda]",
                border_style="guinda",
                padding=(0, 2),
            )
        )

    console.print()

    if overall_risk == "high":
        confirm_text = Text(
            "Confirmar ejecución? Escribe 'EJECUTAR' para proceder: ",
            style="guinda",
        )
        response = Prompt.ask(confirm_text)
        return response.strip().upper() == "EJECUTAR"
    return Confirm.ask(
        Text("Aprobar ejecución?", style="dorado"),
        default=False,
    )


def show_execution_progress(
    console: Console,
    cmd: str,
    index: int,
    total: int,
) -> None:
    """Header visual para cada comando en ejecucion."""
    console.print()
    console.print(f"  [dorado]\u25b6 [{index}/{total}][/dorado] [blanco]{cmd}[/blanco]")
    console.print(f"  [sutil]{'\u2500' * 50}[/sutil]")


def show_result_card(
    console: Console,
    cmd: str,
    returncode: int,
    stdout: str,
    stderr: str,
    duration: timedelta,
) -> None:
    """Tarjeta de resultado post-ejecucion."""
    success = returncode == 0
    dur_str = f"{duration.total_seconds():.1f}s"

    if success:
        header = f"[verde]\u2714 COMPLETADO[/verde] [sutil]({dur_str})[/sutil]"
        border = "verde"
        max_lines = 8
    else:
        header = f"[guinda]\u2716 ERROR (código {returncode})[/guinda] [sutil]({dur_str})[/sutil]"
        border = "guinda"
        max_lines = 30

    content_parts = [header]

    def _format_output(text: str, style: str, limit: int) -> list[str]:
        lines = [ln for ln in text.strip().split("\n") if ln.strip()]
        if not lines:
            return []
        parts: list[str] = []
        truncated = len(lines) > limit
        shown = lines[-limit:] if truncated else lines
        if truncated:
            parts.append(
                f"  [sutil]... {len(lines) - limit} líneas anteriores ocultas[/sutil]",
            )
        for line in shown:
            display = line[:120] + "..." if len(line) > 120 else line
            parts.append(f"  [{style}]{display}[/{style}]")
        return parts

    if success:
        output = stdout.strip() or stderr.strip()
        if output:
            formatted = _format_output(output, "gris", max_lines)
            if formatted:
                content_parts.append("")
                content_parts.extend(formatted)
    else:
        if stdout.strip():
            content_parts.append("")
            content_parts.append("  [dorado]--- Salida ---[/dorado]")
            content_parts.extend(_format_output(stdout, "gris", max_lines))
        if stderr.strip():
            content_parts.append("")
            content_parts.append("  [guinda]--- Errores ---[/guinda]")
            content_parts.extend(_format_output(stderr, "guinda", max_lines))
        if not stdout.strip() and not stderr.strip():
            content_parts.append("")
            content_parts.append("  [gris]Sin salida capturada.[/gris]")

    console.print(
        Panel(
            "\n".join(content_parts),
            border_style=border,
            padding=(0, 1),
        )
    )
