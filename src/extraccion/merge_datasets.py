import os
import typer
from pathlib import Path
from tkinter import Tk, filedialog, messagebox
from src.extraccion.pipeline import run_pipeline
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

DEFAULT_INPUT_DIR = "data/include/"
DEFAULT_OUTPUT_DIR = "data/include/output"
DEFAULT_OUTPUT_FILE = "merged_dataset_{timestamp}.csv"
DEFAULT_KEYWORDS = ["Depresión", "Parkinson", "Alzheimer"]



def pick_directory(default_dir: str = typer.Option(DEFAULT_INPUT_DIR, "--input", "-i", help="Directorio defailt: /data/include/")):
    root = Tk()
    root.withdraw() 
    folder = filedialog.askdirectory()
    root.destroy()
    if not folder:
        typer.echo(f"{'='*60}")
        typer.echo(f"❌ Directorio de entrada no seleccionado.\nSe usará directorio por defecto:\n{DEFAULT_INPUT_DIR}", err=True)
        typer.echo(f"{'='*60}")
        return DEFAULT_INPUT_DIR
    return folder

input_path = Path(pick_directory(DEFAULT_INPUT_DIR))
output_path = Path(DEFAULT_OUTPUT_DIR)
kw_list = DEFAULT_KEYWORDS

if not input_path.exists():
    typer.echo(f"❌ Directorio de entrada no existe: {input_dir}", err=True)
    raise typer.Exit(1)

# Crear output dir si no existe
output_path.mkdir(parents=True, exist_ok=True)
    
typer.echo(f"\n{'='*60}")
typer.echo("🚀 Iniciando pipeline de extracción")
typer.echo(f"{'='*60}")
typer.echo(f"📁 Input:    {input_dir}")
typer.echo(f"📁 Output:   {output_dir}")
typer.echo(f"🔑 Keywords: {kw_list}")
typer.echo(f"{'='*60}\n")

# Ejecutar pipeline
try:
    run_pipeline(
        input_dir=str(input_path),
        output_dir=str(output_path),
        keywords=kw_list,
        save_matched_pages=False,
        save_individual_tables=False,
        log_fn=typer.echo,
    )
    typer.echo("\n✅ Pipeline completado exitosamente.")
except Exception as e:
    typer.echo(f"\n❌ Error en pipeline: {e}", err=True)
    raise typer.Exit(1)