from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import typer
from src.extraccion.pipeline import run_pipeline
import shutil

app = typer.Typer(add_completion=False)

DEFAULT_INPUT_DIR = Path("data/include/")
DEFAULT_OUTPUT_DIR = Path("data/include/output")
DEFAULT_KEYWORDS = ["Depresión", "Parkinson", "Alzheimer"]
DEFAULT_FILENAME = "dataset_boletin_epidemiologico.csv"


def _has_tty() -> bool:
    # True si stdin y stdout son interactivos (terminal real)
    return sys.stdin.isatty() and sys.stdout.isatty()

def _pick_directory_gui() -> Optional[Path]:
    try:
        from tkinter import Tk, filedialog
    except Exception:
        return None

    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update
        folder = filedialog.askdirectory()
        root.destroy()
        return Path(folder) if folder else None
    except Exception:
        return None


def ensure_empty_dir_or_exit(path: Path, *, interactive: bool = True) -> None:
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

def rename_csv_with_timestamp(csv_path: str | Path) -> Path:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {csv_path}")
    if csv_path.suffix.lower() != ".csv":
        raise ValueError("El archivo no es .csv")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_path = csv_path.with_name(f"{csv_path.stem}_{timestamp}.csv")
    csv_path.rename(new_path)
    return new_path

@app.command()
def main(
    input_dir: Path = typer.Option(DEFAULT_INPUT_DIR, "--input", "-i", file_okay=False, dir_okay=True),
    output_dir: Path = typer.Option(DEFAULT_OUTPUT_DIR, "--output", "-o", file_okay=False, dir_okay=True),
    keywords: List[str] = typer.Option(DEFAULT_KEYWORDS, "--kw"),
    save_matched_pages: bool = typer.Option(False, "--save-matched-pages"),
    save_individual_tables: bool = typer.Option(False, "--save-individual-tables"),
):
    # "Smart": solo pregunta si hay terminal interactiva
    if _has_tty():
        if typer.confirm(f"¿Deseas cambiar la carpeta por defecto? ({input_dir})", default=False):
            picked = _pick_directory_gui()
            if picked:
                input_dir = picked
            else:
                typer.echo("⚠️ No se pudo abrir el selector o no se eligió carpeta. Se usa la carpeta actual.")
    # Si no hay TTY, no preguntamos nada y usamos defaults o flags

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
        ensure_empty_dir_or_exit(output_dir)
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
    
    output_file = str(DEFAULT_OUTPUT_DIR) + "/" + DEFAULT_FILENAME
    typer.echo("\n>> Renombrando archivo de salida: {output_file}")
    
    try:
        rename_csv_with_timestamp(output_file)
    except Exception as e:
        typer.echo(f"\n❌ Error en renombrar archivo: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()