from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import typer
from src.extraccion.pipeline import run_pipeline
import shutil
import pandas as pd
import re

app = typer.Typer(add_completion=False)

DEFAULT_INPUT_DIR = Path("data/update/")
DEFAULT_OUTPUT_DIR = Path("data/update/output")
DEFAULT_KEYWORDS = ["Depresión", "Parkinson", "Alzheimer"]
DEFAULT_FILENAME = "dataset_boletin_epidemiologico.csv"
_TIMESTAMP_RE = re.compile(r".*_\d{8}_\d{6}\.csv$")


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

def merge_csv(
    input_dir: str | Path,
    target_csv: str | Path,
    output_dir: str | Path,
    output_filename: str,
    preview_rows: int = 8,
    log_fn=typer.echo,
) -> None:
    """
    - Busca EXACTAMENTE un CSV en input_dir con nombre *_YYYYMMDD_HHMMSS.csv
    - Compara contra target_csv
    - Agrega filas faltantes (fila completa, columna por columna)
    - Guarda resultado en output_dir / output_filename
    """

    input_dir = Path(input_dir)
    target_csv = Path(target_csv)
    output_dir = Path(output_dir)
    output_csv = output_dir / output_filename

    # --- Validaciones de input ---
    if not input_dir.exists():
        log_fn(f"❌ Directorio de entrada no existe: {input_dir}", err=True)
        raise typer.Exit(1)

    csv_candidates = [
        p for p in input_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".csv"
        and _TIMESTAMP_RE.match(p.name)
    ]

    if len(csv_candidates) == 0:
        log_fn(
            "❌ No se encontró ningún CSV con formato *_YYYYMMDD_HHMMSS.csv "
            f"en {input_dir}",
            err=True,
        )
        raise typer.Exit(1)

    if len(csv_candidates) > 1:
        log_fn(
            f"❌ Se encontró más de un CSV válido en {input_dir}. "
            "Debe existir solo uno.",
            err=True,
        )
        for p in csv_candidates:
            log_fn(f"   - {p.name}", err=True)
        raise typer.Exit(1)

    source_csv = csv_candidates[0]
    log_fn(f"📄 CSV de entrada detectado: {source_csv.name}")

    if not target_csv.exists():
        log_fn(f"❌ No existe el CSV target: {target_csv}", err=True)
        raise typer.Exit(1)

    # --- Leer CSV ---
    try:
        df_source = pd.read_csv(source_csv, encoding="utf-8")
        df_target = pd.read_csv(target_csv, encoding="utf-8")
    except Exception as e:
        log_fn(f"❌ Error leyendo CSV: {e}", err=True)
        raise typer.Exit(1)

    # --- Verificar formato ---
    if list(df_source.columns) != list(df_target.columns):
        log_fn("❌ Formato de tabla diferente: columnas u orden no coincide.", err=True)
        log_fn(f"   Source: {list(df_source.columns)}", err=True)
        log_fn(f"   Target: {list(df_target.columns)}", err=True)
        raise typer.Exit(1)

    log_fn("✅ Formato de tabla verificado.")

    # Copias SOLO para comparar (no cambian lo que guardas)
    df_source_cmp = df_source.copy()
    df_target_cmp = df_target.copy()

    # Semana: igualar "02" y "2" solo para la comparación
    # (convierte a número y regresa como string sin ceros a la izquierda)
    df_source_cmp["Semana"] = pd.to_numeric(df_source_cmp["Semana"], errors="coerce").astype("Int64").astype("string")
    df_target_cmp["Semana"] = pd.to_numeric(df_target_cmp["Semana"], errors="coerce").astype("Int64").astype("string")

    # IMPORTANTE: no hagas astype(str) a todo el DF
    merged_check = df_source_cmp.merge(
        df_target_cmp,
        how="left",
        on=list(df_source_cmp.columns),
        indicator=True,
    )

    missing_mask = merged_check["_merge"] == "left_only"
    missing_rows = df_source.loc[missing_mask]  # agregas las filas originales, intactas



    # --- Comparar fila completa ---
    merged_check = df_source.merge(
        df_target,
        how="left",
        on=list(df_source.columns),
        indicator=True,
    )

    missing_mask = merged_check["_merge"] == "left_only"
    missing_rows = df_source.loc[missing_mask]
    missing_count = int(missing_mask.sum())

    if missing_count == 0:
        log_fn("✅ No se encontraron diferencias en los archivos.")
        output_dir.mkdir(parents=True, exist_ok=True)
        df_target.to_csv(output_csv, index=False, encoding="utf-8")
        log_fn(f"✅ Completado. Archivo generado: {output_csv}")
        return

    log_fn(f"⚠️ Se van a agregar {missing_count} filas nuevas.")

    preview_n = min(preview_rows, missing_count)
    if preview_n > 0:
        log_fn(f"\n📌 Preview de filas a agregar (primeras {preview_n}):")
        log_fn(missing_rows.head(preview_n).to_string(index=False))

    # --- Merge final ---
    df_final = pd.concat([df_target, missing_rows], ignore_index=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(output_csv, index=False, encoding="utf-8")

    log_fn(
        f"\n✅ Completado. Filas agregadas: {missing_count}. "
        f"Total final: {len(df_final)}. "
        f"Archivo: {output_csv}"
    )

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
        #ensure_empty_dir_or_exit(output_dir) for debugging, deshabilitado por el momento
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
    
    merge_csv(
    input_dir="data/update/output",
    target_csv="data/processed/dataset_boletin_epidemiologico.csv",
    output_dir="data/update/output",
    output_filename="dataset_boletin_epidemiologico_merged.csv",
    log_fn=typer.echo,
    )


if __name__ == "__main__":
    app()