"""Interactive utilities for the merger CLI: TTY detection, GUI picker, dir cleanup."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

import typer


def _has_tty() -> bool:
    """Detecta si la sesión tiene una terminal interactiva (TTY) disponible."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _pick_directory_gui() -> Path | None:
    try:
        from tkinter import Tk, filedialog
    except ImportError:
        return None

    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update
        folder = filedialog.askdirectory()
        root.destroy()
        return Path(folder) if folder else None
    except (RuntimeError, OSError):
        return None  # Falla si no hay display gráfico disponible


def ensure_empty_dir_or_exit(path: Path, *, interactive: bool = True) -> None:
    """Verifica que el directorio esté vacío; solicita confirmación o aborta.

    Args:
        path:        Directorio a verificar.
        interactive: Si True y hay TTY, solicita confirmación al usuario.

    Raises:
        typer.Exit: Si el usuario cancela o no hay TTY y el directorio no está vacío.
    """
    path.mkdir(parents=True, exist_ok=True)
    has_contents = any(path.iterdir())
    if not has_contents:
        return
    if interactive and sys.stdin.isatty() and sys.stdout.isatty():
        ok = typer.confirm(
            f"⚠️ La carpeta de salida no está vacía: {path}\n¿Quieres borrar su contenido y continuar?",
            default=False,
        )
        if not ok:
            typer.echo("⛔ Cancelado por el usuario. No se ejecutó el pipeline.")
            raise typer.Exit(0)

        for p in path.iterdir():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        typer.echo("🧹 Contenido borrado.")
        return

    typer.echo(f"❌ La carpeta no está vacía y no hay modo interactivo: {path}", err=True)
    raise typer.Exit(1)
