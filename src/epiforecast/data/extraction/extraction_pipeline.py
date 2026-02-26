"""Extraction pipeline: orchestrate multi-PDF processing and emit combined CSV."""

import os

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
    input_dir,
    output_dir,
    keywords,
    save_matched_pages=False,
    save_individual_tables=False,
    log_fn=print,
    on_file=None,
):
    """Ejecuta el pipeline de extracción de tablas desde boletines PDF de SINAVE.

    Procesa todos los PDF del directorio de entrada, extrae tablas con Camelot,
    y genera un CSV consolidado con los datos epidemiológicos.

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

    os.makedirs(output_dir, exist_ok=True)

    output_csv = os.path.join(output_dir, "dataset_boletin_epidemiologico.csv")
    pages_dir = os.path.join(output_dir, "pdf_matched_pages")
    tablas_dir = os.path.join(output_dir, "csv_tablas_individuales")

    if save_matched_pages:
        os.makedirs(pages_dir, exist_ok=True)

    if save_individual_tables:
        os.makedirs(tablas_dir, exist_ok=True)

    pdf_files = sorted(f for f in os.listdir(input_dir) if f.lower().endswith(".pdf"))
    total_pdfs = len(pdf_files)

    log_fn(f"PDFs detectados: {total_pdfs}")

    col_map = build_column_map(keywords)

    all_rows = []
    page_found = 0
    run_log = []
    failed_files = []

    for idx, file in enumerate(pdf_files, start=1):
        if on_file:
            on_file(file)
        pct = (idx / total_pdfs * 100) if total_pdfs else 100.0
        pdf_path = os.path.join(input_dir, file)
        try:
            page, year, week = find_page_and_week(pdf_path, keywords)
            filas_base = None
            status = "‼️"

            if not page:
                log_fn("  ‼️ No se encontró página válida")
                run_log.append(
                    {"file": file, "year": year, "week": week, "page": page, "rows": filas_base}
                )
                log_fn(f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | - | - | {status}")
                continue

            page_found += 1

            if save_matched_pages:
                out_pdf = os.path.join(pages_dir, f"{os.path.splitext(file)[0]}_p{page}.pdf")
                extract_matched_page(pdf_path, page - 1, out_pdf)

            tables = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream")

            if tables.n == 0:
                log_fn("  ⚠️ Camelot no detectó tablas")
                status = "⚠️"
                run_log.append(
                    {"file": file, "year": year, "week": week, "page": page, "rows": filas_base}
                )
                log_fn(
                    f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | p{page} | {year} W{week:02d} | sin tabla {status} "
                )
                continue

            df_raw = tables[0].df
            df_clean = clean_df(df_raw)
            df_clean = pad_prev_year_cols(df_clean, keywords)
            filas_base = len(df_clean)
            status = "✅" if filas_base == 32 else "⚠️"

            if save_individual_tables:
                wide_df = reshape_wide(df_clean, year, week, col_map)
                per_page_csv = os.path.join(tablas_dir, f"{year}_W{week:02d}_P{page}.csv")
                wide_df.to_csv(per_page_csv, index=False, encoding="utf-8")

            df_long = reshape(df_clean, year, week, col_map)
            all_rows.append(df_long)

            run_log.append(
                {"file": file, "year": year, "week": week, "page": page, "rows": filas_base}
            )
            log_fn(
                f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | p{page} | {year} W{week:02d} | filas={filas_base} {status}"
            )

        except Exception as e:
            failed_files.append(file)
            run_log.append({"file": file, "year": None, "week": None, "page": None, "rows": None})
            log_fn(
                f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | ERROR ({type(e).__name__}): {e}"
            )
            continue

    if failed_files:
        failed_txt = os.path.join(output_dir, "failed_files.txt")
        with open(failed_txt, "w", encoding="utf-8") as f:
            for name in failed_files:
                f.write(name + "\n")

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
