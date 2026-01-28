from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer

from src.extraccion.pipeline import run_pipeline


app = typer.Typer(add_completion=False)

DEFAULT_INPUT_DIR = Path("data/include/")
DEFAULT_OUTPUT_DIR = Path("data/include/output")
DEFAULT_KEYWORDS = ["Depresión", "Parkinson", "Alzheimer"]


def _pick_directory_gui() -> Optional[str]:
    """Return a directory path chosen via GUI, or None if cancelled/unavailable."""
    try:
        from tkinter import Tk, filedialog  # lazy import
    except Exception:
        return None

    try:
        root = Tk()
        root.withdraw()
        folder = filedialog.askdirectory()
        root.destroy()
        return folder or None
    except Exception:
        return None


@app.command()
def main(
    input_dir: Path = typer.Option(DEFAULT_INPUT_DIR, "--input", "-i", exists=False, file_okay=False, dir_okay=True),
    output_dir: Path = typer.Option(DEFAULT_OUTPUT_DIR, "--output", "-o", file_okay=False, dir_okay=True),
    keywords: List[str] = typer.Option(DEFAULT_KEYWORDS, "--kw", help="Repite --kw para varias keywords."),
    gui: bool = typer.Option(False, "--gui", help="Abrir selector de carpeta (Tkinter)."),
    save_matched_pages: bool = typer.Option(False, "--save-matched-pages"),
    save_individual_tables: bool = typer.Option(False, "--save-individual-tables"),
):
    # GUI selection overrides input_dir if requested
    if gui:
        picked = _pick_directory_gui()
        if picked:
            input_dir = Path(picked)
        else:
            typer.echo("⚠️ No se seleccionó directorio (o no hay GUI). Se usa --input.")

    if not input_dir.exists():
        typer.echo(f"❌ Directorio de entrada no existe: {input_dir}", err=True)
        raise typer.Exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    typer.echo("\n" + "=" * 60)
    typer.echo("🚀 Iniciando pipeline de extracción")
    typer.echo("=" * 60)
    typer.echo(f"📁 Input:    {input_dir}")
    typer.echo(f"📁 Output:   {output_dir}")
    typer.echo(f"🔑 Keywords: {keywords}")
    typer.echo("=" * 60 + "\n")

    try:
        run_pipeline(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            keywords=keywords,
            save_matched_pages=save_matched_pages,
            save_individual_tables=save_individual_tables,
            log_fn=typer.echo,
        )
        typer.echo("\n✅ Pipeline completado exitosamente.")
    except Exception as e:
        typer.echo(f"\n❌ Error en pipeline: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()