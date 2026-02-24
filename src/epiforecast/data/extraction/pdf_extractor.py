import os
import re
import camelot
import pandas as pd
from pypdf import PdfReader, PdfWriter

SEMANA_REGEX = re.compile(
    r"Semana\s+(\d{1,2}).*?(\d{4})",
    re.IGNORECASE
)
SEMANA_REGEX_2 = re.compile(
    r"semana\s+epidemiol[oó]gica\s+(\d{1,2})\s+del\s+(\d{4})",
    re.IGNORECASE
)

def build_column_map(keywords: list[str], start_col: int = 1, step: int = 4):
    col_map = {}
    for i, disease in enumerate(keywords):
        base = start_col + i * step
        col_map[disease] = {
            "total": base,
            "hombres": base + 1,
            "mujeres": base + 2,
            "total_prev": base + 3,
        }
    return col_map

def find_page_and_week(pdf_path, KEYWORDS):
    """
    Busca la página del PDF que contiene todas las keywords
    y extrae el año y la semana epidemiológica.
    """
    reader = PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        # Verifica que todas las palabras clave estén presentes
        if all(k.lower() in text.lower() for k in KEYWORDS):
            match = SEMANA_REGEX.search(text) # Opción 1: "Semana 12 2024"
            if match:
                week, year = match.groups()
                return i + 1, int(year), int(week)
            match2 = SEMANA_REGEX_2.search(text) # Opción 2: "semana epidemiológica 42 del 2024"
            if match2:
                week2, year2 = match2.groups()
                return i + 1, int(year2), int(week2) + 1
            # Si encontró keywords pero no pudo sacar semana/año, dar valores de error 8888 y 99
            return i + 1, 8888, 99
    return None, None, None

def extract_matched_page(pdf_path: str, page_index_0: int, out_pdf_path: str):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.add_page(reader.pages[page_index_0])
    with open(out_pdf_path, "wb") as f:
        writer.write(f)

def eliminar_columnas_vacias(df, start_state="Aguascalientes", end_state="Zacatecas"):
    """
    Elimina columnas que estén completamente vacías ("")  dentro del rango
    de filas entre start_state y end_state (incluyéndolos).
    """
    df = df.copy()
    df.columns = range(df.shape[1])  # columnas 0..N-1

    col0 = df[0].astype(str).str.strip()

    try:
        i_start = col0[col0.eq(start_state)].index[0]
        i_end = col0[col0.eq(end_state)].index[0]
    except IndexError:
        # Si no encuentra alguno, no toca nada
        return df

    if i_start > i_end:
        i_start, i_end = i_end, i_start

    sub = df.loc[i_start:i_end, :]  # solo filas Aguascalientes..Zacatecas

    is_blank = sub.astype(str).apply(lambda col: col.str.strip().eq(""))  # True si vacío o espacios
    keep_cols = is_blank.mean(axis=0) < 1.0  # conserva columnas que no son 100% vacías en ese rango

    return df.loc[:, keep_cols]

def pad_prev_year_cols(df: pd.DataFrame, keywords: list[str]) -> pd.DataFrame:
    """
    Si df viene SIN 'año anterior' (1 + 3*k columnas),
    lo convierte al esquema CON 'año anterior' (1 + 4*k columnas),
    poniendo pd.NA en la columna faltante de cada padecimiento.
    """
    df = df.copy()
    k = len(keywords)
    no_prev = 1 + 3 * k
    with_prev = 1 + 4 * k

    if df.shape[1] != no_prev:
        return df  # ya trae año anterior, o viene raro (lo manejas aparte)

    out = {}
    out[0] = df[0]  # Entidad

    for i, kw in enumerate(keywords):
        old_base = 1 + i * 3
        new_base = 1 + i * 4
        out[new_base + 0] = df[old_base + 0]  # total semana
        out[new_base + 1] = df[old_base + 1]  # hombres
        out[new_base + 2] = df[old_base + 2]  # mujeres
        out[new_base + 3] = pd.NA            # año anterior (faltante)

    return pd.DataFrame(out)

def clean_df(df, min_numeric_cells=2):
    """
    Limpia la tabla extraída por Camelot dejando solo filas que parecen "estado + datos".

    Regla:
    - Conserva filas donde la columna 0 tiene texto (nombre del estado)
    - y donde existan al menos `min_numeric_cells` valores numéricos enteros en columnas 1..N
    """
    # 1) Elimina columnas completamente vacías en el intervalo Aguascalientes..Zacatecas
    df = eliminar_columnas_vacias(df)

    # 2) Normaliza primera columna (estado)
    df.columns = range(df.shape[1])
    df[0] = df[0].astype(str).str.strip()

    # 3) Quita filas basura
    df = df[df[0].ne("")]
    df = df[~df[0].str.match(r"^(ENTIDAD|FEDERATIVA|TOTAL.*|FUENTE.*|NOTA.*)$", case=False, na=False)]

    # 4) Normaliza celdas numéricas SOLO para validar filas (no conviertas todo a 0 aquí)
    num_cols = [c for c in df.columns if c != 0]
    cells = df[num_cols].astype(str).apply(lambda col: col.str.strip())

    # limpia miles para conteo: "1 450" / "1,450" -> "1450"
    cells_clean = cells.replace(r"[ ,]", "", regex=True)

    # para el conteo, "-" y "" cuentan como numéricos (porque serán 0)
    is_zeroish = cells.apply(lambda col: col.eq("-") | col.eq(""))
    is_int = cells_clean.apply(lambda col: col.str.fullmatch(r"\d+").fillna(False))

    numeric_like = (is_int | is_zeroish)
    numeric_count = numeric_like.sum(axis=1)

    df = df[numeric_count >= min_numeric_cells]

    return df.reset_index(drop=True)

def normalize_number(x):
    if pd.isna(x):
        return pd.NA

    s = str(x).strip()
    if s == "" or s == "-":
        return 0

    # quita separadores de miles: espacios y comas
    s2 = s.replace(" ", "").replace(",", "")

    # si queda número entero válido, regresa int
    if re.fullmatch(r"\d+", s2):
        return int(s2)

    # cualquier otra cosa (n.e., texto, etc.) => NA
    return pd.NA

def reshape(df: pd.DataFrame, year: int, week: int, col_map: dict) -> pd.DataFrame:
    records = []
    for _, row in df.iterrows():
        estado = row[0]
        for disease, cols in col_map.items():
            records.append({
                "Anio": year,
                "Semana": f"{week:02d}",
                "Entidad": estado,
                "Padecimiento": disease,
                "Casos_semana": normalize_number(row[cols["total"]]),
                "Acumulado_hombres": normalize_number(row[cols["hombres"]]),
                "Acumulado_mujeres": normalize_number(row[cols["mujeres"]]),
                "Acumulado_anio_anterior": normalize_number(row[cols["total_prev"]]),
            })
    return pd.DataFrame(records)

def reshape_wide(df: pd.DataFrame, year: int, week: int, col_map: dict) -> pd.DataFrame:
    """
    Devuelve un DF "ancho":
    1 fila por entidad y 4 columnas por keyword (semana, hombres, mujeres, año anterior).
    """
    records = []
    for _, row in df.iterrows():
        estado = row[0]
        rec = {
            "Anio": year,
            "Semana": f"{week:02d}",
            "Entidad": estado,
        }
        for kw, cols in col_map.items():
            rec[f"Casos_semana_{kw}"] = normalize_number(row[cols["total"]])
            rec[f"Acumulado_hombres_{kw}"] = normalize_number(row[cols["hombres"]])
            rec[f"Acumulado_mujeres_{kw}"] = normalize_number(row[cols["mujeres"]])
            rec[f"Acumulado_anio_anterior_{kw}"] = normalize_number(row[cols["total_prev"]])
        records.append(rec)
    return pd.DataFrame(records)

def print_run_summary(run_log, log_fn=print):
    headers = ["Nombre del archivo", "Anio", "Semana", "Pagina match", "Filas"]
    rows = []

    for r in run_log:
        rows.append([
            str(r.get("file", "")),
            "" if r.get("year") is None else str(r.get("year")),
            "" if r.get("week") is None else f"{int(r.get('week')):02d}",
            "" if r.get("page") is None else str(r.get("page")),
            "" if r.get("rows") is None else str(r.get("rows")),
        ])

    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    def fmt(row):
        return " | ".join(val.ljust(widths[i]) for i, val in enumerate(row))

    log_fn(fmt(headers))
    log_fn("-" * (sum(widths) + 3 * (len(headers) - 1)))

    for row in rows:
        log_fn(fmt(row))

    total = len(run_log)
    ok = sum(1 for r in run_log if (r.get("page") is not None) and (r.get("rows") == 32))
    pct = (ok / total * 100) if total else 0.0
    log_fn(f"\nExito: {ok}/{total} = {pct:.1f}% (match y 32 filas)")

def run_pipeline(input_dir, output_dir, keywords, save_matched_pages=False, save_individual_tables=False, log_fn=print, on_file=None):
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
    failed_files=[]

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
                run_log.append({"file": file, "year": year, "week": week, "page": page, "rows": filas_base})
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
                run_log.append({"file": file, "year": year, "week": week, "page": page, "rows": filas_base})
                log_fn(f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | p{page} | {year} W{week:02d} | sin tabla {status} ")
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

            run_log.append({"file": file, "year": year, "week": week, "page": page, "rows": filas_base})
            log_fn(f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | p{page} | {year} W{week:02d} | filas={filas_base} {status}")

        except Exception as e:
            failed_files.append(file)
            run_log.append({"file": file, "year": None, "week": None, "page": None, "rows": None})
            log_fn(f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | ERROR ({type(e).__name__}): {e}")
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