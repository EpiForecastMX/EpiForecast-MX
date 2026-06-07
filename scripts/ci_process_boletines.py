#!/usr/bin/env python
"""
ci_process_boletines.py — Procesamiento automático de boletines nuevos.

Ubicación: scripts/ci_process_boletines.py

Detecta PDFs en data/raw_PDFs/ que aún no están reflejados en el dataset
consolidado, ejecuta el pipeline de extracción (camelot) y hace merge
incremental con data/processed/dataset_boletin_epidemiologico.csv.

Diseñado para correr en GitHub Actions (headless, sin TTY) pero también
funciona en local.

Uso:
    # Automático: detecta PDFs faltantes comparando dataset vs raw_PDFs
    python scripts/ci_process_boletines.py

    # Explícito: procesar solo estos archivos (viene del scraper)
    python scripts/ci_process_boletines.py --new-files "2026_sem04.pdf,2026_sem05.pdf"

Variables de entorno (opcionales, para CI/CD):
    SNS_TOPIC_ARN   - ARN del topic SNS para notificaciones
    AWS_REGION       - Región AWS (default: us-east-1)

Exit codes:
    0 - Éxito (con o sin archivos nuevos)
    1 - Error en el procesamiento
"""

from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import re
import shutil
import sys

import pandas as pd

# ──────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_PDFS_DIR = PROJECT_ROOT / "data" / "raw_PDFs"
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "dataset_boletin_epidemiologico.csv"
UPDATE_DIR = PROJECT_ROOT / "data" / "_ci_update"
UPDATE_OUTPUT_DIR = UPDATE_DIR / "output"
KEYWORDS = ["Depresión", "Parkinson", "Alzheimer"]

# Regex para nombres de PDF del scraper: 2026_sem03.pdf
PDF_NAME_RE = re.compile(r"(\d{4})_sem(\d{2})\.pdf", re.IGNORECASE)

# Boletines que NUNCA producen filas procesables (formato/tabla distinta) y por eso el
# autodetect los re-intenta en cada corrida sin agregar nada. Se omiten explicitamente.
#   (2014, "01"): el boletin de la semana 1 de 2014 no trae la tabla de padecimientos neuro
#                 en el formato esperado; el dataset arranca en la semana 2 de 2014.
SKIP_YEAR_WEEKS: set[tuple[int, str]] = {(2014, "01")}

# AWS (solo para SNS)
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────
# 1. Detección de boletines faltantes
# ──────────────────────────────────────────────────
def get_existing_year_weeks(dataset_path: Path) -> set[tuple[int, str]]:
    """Lee el dataset actual y devuelve pares (año, semana) ya presentes."""
    if not dataset_path.exists():
        log.warning("Dataset no existe aún: %s", dataset_path)
        return set()

    df = pd.read_csv(dataset_path)
    pairs = set()
    for _, row in df[["Anio", "Semana"]].drop_duplicates().iterrows():
        year = int(row["Anio"])
        week = f"{int(row['Semana']):02d}"
        pairs.add((year, week))
    return pairs


def find_new_pdfs(
    raw_dir: Path,
    existing: set[tuple[int, str]],
    explicit_files: list[str] | None = None,
) -> list[Path]:
    """
    Encuentra PDFs que no están reflejados en el dataset.

    Si explicit_files se proporciona (viene del scraper), solo revisa esos.
    Si no, escanea todo raw_PDFs/ y compara contra el dataset.
    """
    new = []

    if explicit_files:
        for fname in explicit_files:
            pdf_path = raw_dir / fname.strip()
            if pdf_path.exists():
                new.append(pdf_path)
            else:
                log.warning("Archivo explícito no encontrado: %s", pdf_path)
        return sorted(new)

    # Escaneo completo: cualquier PDF cuyo (año, semana) no esté en el dataset
    for pdf_path in sorted(raw_dir.glob("*.pdf")):
        match = PDF_NAME_RE.match(pdf_path.name)
        if not match:
            continue
        year = int(match.group(1))
        week = match.group(2)
        if (year, week) in SKIP_YEAR_WEEKS:
            log.info("Omitido (lista de exclusión, nunca agrega filas): %s", pdf_path.name)
            continue
        if (year, week) not in existing:
            new.append(pdf_path)

    return new


# ──────────────────────────────────────────────────
# 2. Merge incremental
# ──────────────────────────────────────────────────
def merge_into_dataset(extracted_csv: Path, target_csv: Path) -> int:
    """
    Agrega filas faltantes del CSV extraído al dataset principal.
    Replica la lógica de merge_datasets.merge_csv de Luis.
    Retorna la cantidad de filas nuevas agregadas.
    """
    df_new = pd.read_csv(extracted_csv, encoding="utf-8")

    if not target_csv.exists():
        log.info("Dataset no existía, se crea desde cero.")
        target_csv.parent.mkdir(parents=True, exist_ok=True)
        df_new.to_csv(target_csv, index=False, encoding="utf-8")
        return len(df_new)

    df_target = pd.read_csv(target_csv, encoding="utf-8")

    # Verificar columnas
    if list(df_new.columns) != list(df_target.columns):
        raise ValueError(
            f"Columnas no coinciden.\n"
            f"  Extraído: {list(df_new.columns)}\n"
            f"  Dataset:  {list(df_target.columns)}"
        )

    # Normalizar Semana para comparación (iguala "02" y "2")
    df_new_cmp = df_new.copy()
    df_target_cmp = df_target.copy()
    df_new_cmp["Semana"] = (
        pd.to_numeric(df_new_cmp["Semana"], errors="coerce").astype("Int64").astype("string")
    )
    df_target_cmp["Semana"] = (
        pd.to_numeric(df_target_cmp["Semana"], errors="coerce").astype("Int64").astype("string")
    )

    # Left join para encontrar filas que faltan en target
    merged = df_new_cmp.merge(
        df_target_cmp,
        how="left",
        on=list(df_new_cmp.columns),
        indicator=True,
    )
    missing_mask = merged["_merge"] == "left_only"
    # Usamos las filas originales (sin normalizar) para el append
    missing_rows = df_new.loc[missing_mask]
    n_missing = int(missing_mask.sum())

    if n_missing == 0:
        log.info("No hay filas nuevas para agregar (ya existían).")
        return 0

    df_final = pd.concat([df_target, missing_rows], ignore_index=True)
    df_final.to_csv(target_csv, index=False, encoding="utf-8")
    log.info(
        "Dataset actualizado: %d filas nuevas, %d total.",
        n_missing,
        len(df_final),
    )
    return n_missing


# ──────────────────────────────────────────────────
# 3. Notificación SNS
# ──────────────────────────────────────────────────
def notify_sns(new_files: list[str], rows_added: int) -> None:
    """Envía alerta SNS con resumen del procesamiento."""
    if not SNS_TOPIC_ARN:
        log.info("SNS_TOPIC_ARN no configurado, skip notificación.")
        return

    import boto3

    sns = boto3.client("sns", region_name=AWS_REGION)
    file_list = "\n".join(f"  • {f}" for f in new_files)

    message = (
        f"📊 Pipeline de extracción completado\n"
        f"({datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')})\n\n"
        f"Boletines procesados:\n{file_list}\n\n"
        f"Filas nuevas agregadas al dataset: {rows_added}\n"
        f"Dataset: data/processed/dataset_boletin_epidemiologico.csv\n\n"
        f"Versionado en EpiForecast-MX."
    )

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"EpiForecast-MX: {len(new_files)} boletín(es) procesado(s) → {rows_added} filas nuevas",
        Message=message,
    )
    log.info("Notificación SNS enviada.")


# ──────────────────────────────────────────────────
# 4. GitHub Actions outputs
# ──────────────────────────────────────────────────
def write_github_outputs(new_pdfs: list[Path], rows_added: int) -> None:
    """Escribe outputs para GitHub Actions."""
    github_output = os.getenv("GITHUB_OUTPUT")
    if not github_output:
        return

    with open(github_output, "a") as f:
        f.write(f"rows_added={rows_added}\n")
        f.write(f"files_processed={len(new_pdfs)}\n")
        names = ",".join(p.name for p in new_pdfs)
        f.write(f"processed_files={names}\n")


# ──────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────
def main(explicit_files: list[str] | None = None) -> int:
    log.info("=" * 60)
    log.info("Inicio: Procesamiento automático de boletines SINAVE")
    log.info("=" * 60)
    log.info("Proyecto raíz: %s", PROJECT_ROOT)

    # Validar que existe el directorio de PDFs
    if not RAW_PDFS_DIR.exists():
        log.error("Directorio de PDFs no existe: %s", RAW_PDFS_DIR)
        log.error("¿Olvidaste correr 'dvc pull'?")
        return 1

    # 1. ¿Qué ya está en el dataset?
    existing = get_existing_year_weeks(DATASET_PATH)
    log.info("Pares (año, semana) en dataset actual: %d", len(existing))

    # 2. ¿Qué PDFs son nuevos?
    new_pdfs = find_new_pdfs(RAW_PDFS_DIR, existing, explicit_files)
    if not new_pdfs:
        log.info("✅ No hay boletines nuevos para procesar. Todo al día.")
        write_github_outputs([], 0)
        return 0

    log.info("Boletines nuevos a procesar: %d", len(new_pdfs))
    for p in new_pdfs:
        log.info("  → %s", p.name)

    # 3. Preparar directorio temporal de trabajo
    if UPDATE_DIR.exists():
        shutil.rmtree(UPDATE_DIR)
    UPDATE_DIR.mkdir(parents=True)
    UPDATE_OUTPUT_DIR.mkdir(parents=True)

    for pdf in new_pdfs:
        shutil.copy2(pdf, UPDATE_DIR / pdf.name)
    log.info("PDFs copiados a: %s", UPDATE_DIR)

    # 4. Ejecutar pipeline de extracción (camelot)
    log.info("Ejecutando pipeline de extracción...")
    from epiforecast.data.extraction.extraction_pipeline import run_pipeline

    try:
        run_pipeline(
            input_dir=str(UPDATE_DIR),
            output_dir=str(UPDATE_OUTPUT_DIR),
            keywords=KEYWORDS,
            save_matched_pages=False,
            save_individual_tables=False,
            log_fn=log.info,
        )
    except Exception as e:
        log.error("Error en pipeline de extracción: %s", e)
        shutil.rmtree(UPDATE_DIR, ignore_errors=True)
        return 1

    # 5. Verificar que se generó el CSV y tiene datos
    extracted_csv = UPDATE_OUTPUT_DIR / "dataset_boletin_epidemiologico.csv"
    if not extracted_csv.exists():
        log.warning("Pipeline no generó CSV de salida en: %s", extracted_csv)
        log.info("Posible causa: PDFs con formato antiguo o incompatible (0 filas extraídas).")
        shutil.rmtree(UPDATE_DIR, ignore_errors=True)
        write_github_outputs(new_pdfs, 0)
        return 0

    # Verificar que el CSV no esté vacío (solo headers o 0 filas)
    try:
        df_check = pd.read_csv(extracted_csv)
        if df_check.empty:
            log.warning("CSV extraído tiene 0 filas. PDFs incompatibles o formato antiguo.")
            shutil.rmtree(UPDATE_DIR, ignore_errors=True)
            write_github_outputs(new_pdfs, 0)
            return 0
    except Exception:
        log.warning("CSV extraído no se pudo leer. Saltando merge.")
        shutil.rmtree(UPDATE_DIR, ignore_errors=True)
        write_github_outputs(new_pdfs, 0)
        return 0

    log.info("CSV extraído: %s (%d filas)", extracted_csv, len(df_check))

    # 6. Merge incremental con dataset principal
    try:
        DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
        rows_added = merge_into_dataset(extracted_csv, DATASET_PATH)
    except Exception as e:
        log.error("Error en merge: %s", e)
        shutil.rmtree(UPDATE_DIR, ignore_errors=True)
        return 1

    # 7. Limpiar directorio temporal
    shutil.rmtree(UPDATE_DIR, ignore_errors=True)

    # 8. Outputs y notificación
    write_github_outputs(new_pdfs, rows_added)
    notify_sns([p.name for p in new_pdfs], rows_added)

    log.info("=" * 60)
    log.info(
        "✅ Fin: %d boletines procesados, %d filas agregadas al dataset.",
        len(new_pdfs),
        rows_added,
    )
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    files = None
    if "--new-files" in sys.argv:
        idx = sys.argv.index("--new-files")
        if idx + 1 < len(sys.argv):
            files = [f.strip() for f in sys.argv[idx + 1].split(",") if f.strip()]

    sys.exit(main(explicit_files=files))
