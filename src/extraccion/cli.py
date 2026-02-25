#!/usr/bin/env python
"""
CLI para ejecutar el pipeline de extracción de tablas epidemiológicas.

Uso:
    python -m src.extraccion.cli --sync              # Sincroniza DVC y ejecuta
    python -m src.extraccion.cli                     # Solo ejecuta (asume datos locales)
    python -m src.extraccion.cli --keywords "Depresión,Parkinson,Alzheimer"
    python -m src.extraccion.cli --help
"""

from pathlib import Path
import subprocess

import typer

from src.extraccion.pipeline import run_pipeline

app = typer.Typer(help="Pipeline de extracción de boletines epidemiológicos SINAVE")

# Defaults
DEFAULT_INPUT_DIR = "data/raw_PDFs"
DEFAULT_OUTPUT_DIR = "data/processed"
DEFAULT_KEYWORDS = ["Depresión", "Parkinson", "Alzheimer"]


def dvc_pull() -> bool:
    """Ejecuta dvc pull y retorna True si fue exitoso."""
    typer.echo("🔄 Sincronizando datos desde S3 (dvc pull)...")
    result = subprocess.run(["dvc", "pull"], capture_output=True, text=True)

    if result.returncode != 0:
        typer.echo(f"❌ Error en dvc pull: {result.stderr}", err=True)
        return False

    typer.echo("✅ Datos sincronizados.")
    return True


def dvc_status() -> bool:
    """Verifica si los datos están actualizados."""
    result = subprocess.run(["dvc", "status"], capture_output=True, text=True)
    # Si no hay output, todo está sincronizado
    return "changed" not in result.stdout.lower()


@app.command()
def run(
    input_dir: str = typer.Option(DEFAULT_INPUT_DIR, "--input", "-i", help="Directorio de PDFs"),
    output_dir: str = typer.Option(
        DEFAULT_OUTPUT_DIR, "--output", "-o", help="Directorio de salida"
    ),
    keywords: str = typer.Option(
        ",".join(DEFAULT_KEYWORDS), "--keywords", "-k", help="Keywords separadas por coma"
    ),
    sync: bool = typer.Option(False, "--sync", "-s", help="Ejecutar dvc pull antes de procesar"),
    save_pages: bool = typer.Option(False, "--save-pages", help="Guardar páginas PDF extraídas"),
    save_tables: bool = typer.Option(
        False, "--save-tables", help="Guardar CSVs individuales por semana"
    ),
):
    """
    Ejecuta el pipeline de extracción de tablas epidemiológicas.

    Por defecto lee de data/raw_PDFs (sincronizado via DVC desde S3).
    """
    # Validar directorios
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists():
        typer.echo(f"❌ Directorio de entrada no existe: {input_dir}", err=True)
        typer.echo("💡 Tip: Usa --sync para descargar datos desde S3", err=True)
        raise typer.Exit(1)

    # Sincronizar si se pidió
    if sync:
        if not dvc_pull():
            raise typer.Exit(1)
    else:
        # Verificar si datos están actualizados
        if not dvc_status():
            typer.echo("⚠️  Los datos locales pueden estar desactualizados.")
            typer.echo("💡 Tip: Usa --sync para sincronizar con S3")

    # Crear output dir si no existe
    output_path.mkdir(parents=True, exist_ok=True)

    # Parsear keywords
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]

    if not kw_list:
        typer.echo("❌ Debe especificar al menos una keyword", err=True)
        raise typer.Exit(1)

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
            save_matched_pages=save_pages,
            save_individual_tables=save_tables,
            log_fn=typer.echo,
        )
        typer.echo("\n✅ Pipeline completado exitosamente.")
    except Exception as e:
        typer.echo(f"\n❌ Error en pipeline: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def status():
    """Muestra el estado de sincronización de DVC."""
    typer.echo("📊 Estado de DVC:")
    subprocess.run(["dvc", "status"])


@app.command()
def pull():
    """Descarga datos desde S3 (equivalente a dvc pull)."""
    if dvc_pull():
        raise typer.Exit(0)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
