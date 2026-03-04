"""Vistas comunes: log viewer, pipeline, stats, history, scripts."""

from collections import defaultdict
from pathlib import Path
import re

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..engine import EpiEngine


def show_log_viewer(console: Console, log_file: Path, n: int = 20) -> None:
    """Visor integrado del log de sesion."""
    if not log_file.exists():
        console.print("[gris]  No hay logs disponibles.[/gris]")
        return
    try:
        lines = log_file.read_text().strip().split("\n")
        recent = lines[-n:]
        table = Table(
            title=f"[dorado]ÚLTIMAS {len(recent)} ENTRADAS DEL LOG[/dorado]",
            show_header=True,
            header_style="dorado",
            box=box.SIMPLE,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("Timestamp", style="sutil", width=20)
        table.add_column("Nivel", width=8)
        table.add_column("Mensaje", style="blanco")
        for line in recent:
            parts = line.split("\u2502", 2)
            if len(parts) == 3:
                ts = parts[0].strip()
                level = parts[1].strip()
                msg = parts[2].strip()
                level_style = (
                    "verde" if level == "INFO" else "guinda" if level == "ERROR" else "dorado"
                )
                table.add_row(ts, f"[{level_style}]{level}[/{level_style}]", msg)
            else:
                table.add_row("", "", line)
        console.print()
        console.print(table)
        console.print()
    except Exception as e:
        console.print(f"[error]Error leyendo logs: {e}[/error]")


def show_pipeline_status(console: Console, engine: EpiEngine) -> None:
    """Visualizacion del estado del pipeline MLOps."""
    stages = [
        ("1. Extracción", "SINAVE PDF --> CSV", "extract"),
        ("2. Validación", "Calidad de datos", "validate"),
        ("3. Transformación", "Feature engineering", "transform"),
        ("4. Entrenamiento", "Prophet x 297 modelos", "train"),
        ("5. Evaluación", "MAPE / RMSE / MAE", "evaluate"),
        ("6. Pronóstico", "Predicción semanal", "forecast"),
        ("7. Visualización", "Gráficas + Tableau", "report"),
    ]
    console.print()
    console.print(Align.center("[dorado]PIPELINE MLOps · EpiForecast-MX[/dorado]"))
    console.print()
    for i, (name, desc, key) in enumerate(stages):
        has_target = any(key in t for t in engine.targets)
        icon = "[verde]\u25cf[/verde]" if has_target else "[gris]\u25cb[/gris]"
        connector = "  [verde.dim]\u2502[/verde.dim]" if i < len(stages) - 1 else ""
        console.print(f"  {icon} [blanco]{name}[/blanco] [sutil]-- {desc}[/sutil]")
        if connector:
            console.print(connector)
    console.print()


def show_session_stats(console: Console, engine: EpiEngine) -> None:
    """Dashboard de estadisticas de la sesion activa."""
    s = engine.stats
    table = Table(show_header=False, box=None, padding=(0, 3))
    table.add_column("Métrica", style="gris")
    table.add_column("Valor", style="blanco")
    table.add_row("Tiempo activo", f"[dorado]{s.uptime}[/dorado]")
    table.add_row("Comandos ejecutados", f"[blanco]{s.total}[/blanco]")
    table.add_row("Exitosos", f"[verde]{s.successes}[/verde]")
    table.add_row("Fallidos", f"[guinda]{s.failures}[/guinda]")
    table.add_row("Cancelados", f"[gris]{s.cancelled}[/gris]")
    if s.total > 0:
        rate = (s.successes / s.total) * 100
        rate_color = "verde" if rate >= 80 else "dorado" if rate >= 50 else "guinda"
        table.add_row("Tasa de éxito", f"[{rate_color}]{rate:.0f}%[/{rate_color}]")
        avg = s.total_duration / s.total
        table.add_row("Duración promedio", f"[blanco]{avg.total_seconds():.1f}s[/blanco]")
    if s.commands_run:
        table.add_row("", "")
        table.add_row("[dorado]Últimos comandos[/dorado]", "")
        for entry in s.commands_run[-5:]:
            icon = "[verde]\u2714[/verde]" if entry["success"] else "[guinda]\u2716[/guinda]"
            ts = entry["timestamp"].strftime("%H:%M:%S")
            table.add_row(
                f"  [sutil]{ts}[/sutil]",
                f"{icon} {entry['cmd']} [sutil]({entry['duration'].total_seconds():.1f}s)[/sutil]",
            )
    panel = Panel(
        table,
        title="[dorado]ESTADÍSTICAS DE SESIÓN[/dorado]",
        border_style="verde.dim",
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


def show_history(console: Console, engine: EpiEngine) -> None:
    """Muestra historial de comandos de la sesion."""
    if not engine.history:
        console.print("[gris]  Sin historial en esta sesión.[/gris]")
        return
    console.print()
    console.print("[dorado]HISTORIAL DE LA SESIÓN[/dorado]")
    console.print()
    for i, cmd in enumerate(engine.history, 1):
        console.print(f"  [gris]{i:>3}.[/gris] [blanco]{cmd}[/blanco]")
    console.print()


def show_python_scripts(
    console: Console,
    folder_filter: str | None = None,
) -> None:
    """Escanea el proyecto y lista archivos .py."""
    project_root = Path()
    skip_dirs = {
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        "egg-info",
        ".eggs",
        "build",
        "dist",
    }
    all_scripts: dict[str, list[tuple[str, int, str, bool]]] = defaultdict(list)

    for py_file in sorted(project_root.rglob("*.py")):
        if any(part in skip_dirs or part.startswith(".") for part in py_file.parts[:-1]):
            continue
        if py_file.name.startswith("__") or py_file.name == "conftest.py":
            continue
        try:
            content = py_file.read_text(errors="ignore")
            lines = len(content.splitlines())
            is_entry = (
                "if __name__" in content
                or "typer" in content
                or "click" in content
                or "argparse" in content
            )
            desc = ""
            doc_match = re.search(r'^"""(.*?)"""', content, re.DOTALL)
            if not doc_match:
                doc_match = re.search(r"^'''(.*?)'''", content, re.DOTALL)
            if doc_match:
                first_line = doc_match.group(1).strip().split("\n")[0].strip()
                if len(first_line) < 80:
                    desc = first_line
            folder = str(py_file.parent) if str(py_file.parent) != "." else "raíz"
            all_scripts[folder].append((str(py_file), lines, desc, is_entry))
        except Exception:
            continue

    if not all_scripts:
        console.print("[gris]  No se encontraron scripts Python en el proyecto.[/gris]")
        return

    if folder_filter:
        filtered = {}
        ff = folder_filter.strip("/").lower()
        for folder, items in all_scripts.items():
            if ff in folder.lower() or folder.lower().startswith(ff):
                filtered[folder] = items
        if not filtered:
            available = sorted(all_scripts.keys())
            console.print(
                f"\n  [alerta]No se encontró la carpeta "
                f"'[blanco]{folder_filter}[/blanco]'.[/alerta]",
            )
            console.print("  [sutil]Carpetas disponibles:[/sutil]")
            for f in available:
                count = len(all_scripts[f])
                console.print(f"    [dorado]{f}/[/dorado] [gris]({count} archivos)[/gris]")
            console.print()
            return
        scripts = filtered
    else:
        scripts = all_scripts

    total_files = sum(len(v) for v in scripts.values())
    total_entry = sum(1 for v in scripts.values() for _, _, _, e in v if e)

    table = Table(
        title="[dorado]SCRIPTS PYTHON[/dorado]",
        show_header=True,
        header_style="dorado",
        box=box.ROUNDED,
        border_style="verde.dim",
        padding=(0, 1),
        expand=True,
    )
    table.add_column("", width=3, justify="center")
    table.add_column("Archivo", style="blanco", min_width=35)
    table.add_column("Líneas", justify="right", width=7, style="gris")
    table.add_column("Descripción", style="sutil")

    for folder in sorted(scripts.keys()):
        table.add_row("", f"[dorado]{folder}/[/dorado]", "", "")
        for filepath, lines, desc, is_entry in scripts[folder]:
            icon = "[verde]\u25b6[/verde]" if is_entry else "[gris]\u00b7[/gris]"
            name_style = "exito" if is_entry else "blanco"
            table.add_row(
                icon,
                f"[{name_style}]{filepath}[/{name_style}]",
                str(lines),
                desc or "",
            )

    console.print()
    console.print(table)
    console.print(
        f"\n  [sutil]{total_files} archivos · [verde]\u25b6[/verde] {total_entry} "
        f"ejecutables · [gris]\u00b7[/gris] {total_files - total_entry} módulos[/sutil]\n",
    )
