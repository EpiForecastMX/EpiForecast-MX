"""Extraction pipeline: orchestrate multi-PDF processing and emit combined CSV."""

from collections.abc import Callable
import os
from typing import Any

import camelot
import pandas as pd

from epiforecast.data.extraction.pdf_extractor import (
    build_column_map,
    clean_df,
    extract_matched_page,
    find_page_and_week,
    pad_prev_year_cols,
    print_run_summary,
    reshape,
    reshape_wide,
)


def run_pipeline(
    input_dir: str,
    output_dir: str,
    keywords: list[str],
    save_matched_pages: bool = False,
    save_individual_tables: bool = False,
    log_fn: Callable[..., None] = print,
    on_file: Callable[[str], None] | None = None,
) -> None:
    """Ejecuta el pipeline de extracción de tablas desde boletines PDF de SINAVE.

    Args:
        input_dir:            Directorio con los PDFs de entrada.
        output_dir:           Directorio donde se guardan los resultados.
        keywords:             Lista de padecimientos a buscar en las tablas.
        save_matched_pages:   Si True, guarda las páginas PDF que contienen las tablas.
        save_individual_tables: Si True, guarda CSVs individuales por boletín.
        log_fn:               Función de logging (default: print).
        on_file:              Callback invocado con el nombre de cada archivo procesado.

    Raises:
        ValueError: Si el directorio de entrada/salida no existe o keywords está vacío.
    """
    if not os.path.isdir(input_dir):
        raise ValueError("Input dir inválido.")
    if not os.path.isdir(output_dir):
        raise ValueError("Output dir inválido.")
    if not keywords:
        raise ValueError("KEYWORDS vacías.")

    dirs = _setup_directories(output_dir, save_matched_pages, save_individual_tables)
    pdf_files = sorted(f for f in os.listdir(input_dir) if f.lower().endswith(".pdf"))
    total_pdfs = len(pdf_files)
    log_fn(f"PDFs detectados: {total_pdfs}")

    col_map = build_column_map(keywords)
    all_rows = []
    run_log = []
    failed_files = []

    for idx, file in enumerate(pdf_files, start=1):
        if on_file:
            on_file(file)

        result = _process_single_pdf(
            file,
            idx,
            total_pdfs,
            input_dir,
            keywords,
            col_map,
            dirs,
            log_fn,
            save_matched_pages,
            save_individual_tables,
        )

        run_log.append(result["log_entry"])
        if result.get("df") is not None:
            all_rows.append(result["df"])
        if result.get("failed"):
            failed_files.append(file)

    _write_results(
        all_rows,
        failed_files,
        run_log,
        output_dir,
        dirs["output_csv"],
        total_pdfs,
        log_fn,
    )


def _setup_directories(
    output_dir: str, save_matched_pages: bool, save_individual_tables: bool
) -> dict[str, str]:
    """Crea subdirectorios necesarios y retorna dict de rutas."""
    os.makedirs(output_dir, exist_ok=True)
    output_csv = os.path.join(output_dir, "dataset_boletin_epidemiologico.csv")
    pages_dir = os.path.join(output_dir, "pdf_matched_pages")
    tablas_dir = os.path.join(output_dir, "csv_tablas_individuales")
    if save_matched_pages:
        os.makedirs(pages_dir, exist_ok=True)
    if save_individual_tables:
        os.makedirs(tablas_dir, exist_ok=True)
    return {"output_csv": output_csv, "pages_dir": pages_dir, "tablas_dir": tablas_dir}


def _process_single_pdf(
    file: str,
    idx: int,
    total_pdfs: int,
    input_dir: str,
    keywords: list[str],
    col_map: dict[str, dict[str, int]],
    dirs: dict[str, str],
    log_fn: Callable[..., None],
    save_matched_pages: bool,
    save_individual_tables: bool,
) -> dict[str, Any]:
    """Procesa un PDF individual: busca página, extrae tabla, genera registros."""
    pct = (idx / total_pdfs * 100) if total_pdfs else 100.0
    pdf_path = os.path.join(input_dir, file)
    log_entry: dict[str, Any] = {
        "file": file,
        "year": None,
        "week": None,
        "page": None,
        "rows": None,
    }

    try:
        page, year, week = find_page_and_week(pdf_path, keywords)
        log_entry.update(year=year, week=week, page=page)

        if not page:
            log_fn("  ‼️ No se encontró página válida")
            log_fn(f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | - | - | ‼️")
            return {"log_entry": log_entry, "df": None}

        assert year is not None and week is not None  # guaranteed by find_page_and_week

        if save_matched_pages:
            out_pdf = os.path.join(dirs["pages_dir"], f"{os.path.splitext(file)[0]}_p{page}.pdf")
            extract_matched_page(pdf_path, page - 1, out_pdf)

        tables = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream")
        if tables.n == 0:
            log_fn(
                f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | p{page} | "
                f"{year} W{week:02d} | sin tabla ⚠️ "
            )
            return {"log_entry": log_entry, "df": None}

        df_raw = tables[0].df
        df_clean = clean_df(df_raw)
        df_clean = pad_prev_year_cols(df_clean, keywords)
        filas_base = len(df_clean)
        log_entry["rows"] = filas_base
        status = "✅" if filas_base == 32 else "⚠️"

        if save_individual_tables:
            wide_df = reshape_wide(df_clean, year, week, col_map)
            per_page_csv = os.path.join(dirs["tablas_dir"], f"{year}_W{week:02d}_P{page}.csv")
            wide_df.to_csv(per_page_csv, index=False, encoding="utf-8")

        df_long = reshape(df_clean, year, week, col_map)
        log_fn(
            f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | p{page} | "
            f"{year} W{week:02d} | filas={filas_base} {status}"
        )
        return {"log_entry": log_entry, "df": df_long}

    except (OSError, RuntimeError, ValueError, KeyError, IndexError, pd.errors.ParserError) as e:
        log_fn(
            f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | ERROR ({type(e).__name__}): {e}"
        )
        return {"log_entry": log_entry, "df": None, "failed": True}


def _write_results(
    all_rows: list[pd.DataFrame],
    failed_files: list[str],
    run_log: list[dict[str, Any]],
    output_dir: str,
    output_csv: str,
    total_pdfs: int,
    log_fn: Callable[..., None],
) -> None:
    """Escribe CSV final, lista de fallidos y resumen del pipeline."""
    if failed_files:
        failed_txt = os.path.join(output_dir, "failed_files.txt")
        with open(failed_txt, "w", encoding="utf-8") as f:
            for name in failed_files:
                f.write(name + "\n")

    page_found = sum(1 for r in run_log if r.get("page") is not None)
    log_fn("\n=== Resumen ===")
    log_fn(f"PDFs procesados: {total_pdfs}")
    log_fn(f"PDFs con página válida: {page_found}")
    log_fn("\n=== Resumen por archivo ===")
    print_run_summary(run_log, log_fn=log_fn)

    if not all_rows:
        log_fn("No se generaron datos. Archivo final no creado.")
        return

    final_df = pd.concat(all_rows, ignore_index=True)
    final_df.to_csv(output_csv, index=False, encoding="utf-8")
    log_fn(f"Archivo final generado: {output_csv}")
    log_fn(f"Total de filas: {len(final_df)}")
