# Mensaje inicial para saber que el script arrancó
print("Importando librerías")

# Librerías estándar
import os              # Manejo de archivos y directorios
import re              # Expresiones regulares

# Librerías externas
import camelot         # Extracción de tablas desde PDF
import pandas as pd    # Manipulación de datos
from pypdf import PdfReader  # Lectura de texto en PDFs

print("Iniciando script...")

# Directorio donde están los PDFs de entrada
INPUT_DIR = "data/raw_PDFs"

# Archivo CSV final consolidado
OUTPUT_FILE = "data/processed/consolidado.csv"

# Palabras clave que deben aparecer juntas en la página correcta
KEYWORDS = ["Depresión", "Parkinson", "Alzheimer"]

# Regex para extraer semana y año del texto del PDF
# Busca textos que contengan la palabra "Semana" seguida de:
# - un número de semana (1 o 2 dígitos) → grupo 1
# - cualquier texto intermedio
# - un año de 4 dígitos → grupo 2
# No distingue entre mayúsculas y minúsculas
# Ejemplo esperado: "Semana 12 2024"
SEMANA_REGEX = re.compile(
    r"Semana\s+(\d{1,2}).*?(\d{4})",
    re.IGNORECASE
)
SEMANA_REGEX_2 = re.compile(
    r"semana\s+epidemiol[oó]gica\s+(\d{1,2})\s+del\s+(\d{4})",
    re.IGNORECASE
)

# Mapeo fijo de columnas según la estructura de la tabla del PDF
COLUMN_MAP = {
    "Depresión": {"total": 1, "hombres": 2, "mujeres": 3, "total_prev": 4},
    "Parkinson": {"total": 5, "hombres": 6, "mujeres": 7, "total_prev": 8},
    "Alzheimer": {"total": 9, "hombres": 10, "mujeres": 11, "total_prev": 12},
}

def find_page_and_week(pdf_path):
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

def clean_df(df, min_numeric_cells=2):
    """
    Limpia la tabla extraída por Camelot dejando solo filas que parecen "estado + datos".

    Regla:
    - Conserva filas donde la columna 0 tiene texto (nombre del estado)
    - y donde existan al menos `min_numeric_cells` valores numéricos enteros en columnas 1..N
    """
    df = df.copy()

    # Renombra columnas con índices numéricos
    df.columns = range(df.shape[1])

    # Normaliza texto en columna 0 (estado / etiquetas)
    df[0] = df[0].astype(str).str.strip()

    # Elimina filas donde la primera columna está vacía
    df = df[df[0].ne("")]

    # Elimina filas obvias de encabezado / pie
    df = df[~df[0].str.match(r"^(ENTIDAD|FEDERATIVA|TOTAL|FUENTE|NOTA)$", case=False, na=False)]

    # Toma todas las columnas excepto la 0 (las numéricas)
    num_cols = [c for c in df.columns if c != 0]

    # Normaliza celdas: quita espacios de millares y convierte "-" en vacío
    cells = df[num_cols].astype(str)
    cells = cells.replace(r"\s+", "", regex=True)
    cells = cells.replace("-", "", regex=False)

    # Cuenta cuántas celdas son enteros válidos por fila
    is_int = cells.apply(lambda s: s.str.fullmatch(r"\d+").fillna(False))
    numeric_count = is_int.sum(axis=1)

    # Conserva solo filas con suficientes números
    df = df[numeric_count >= min_numeric_cells]

    return df.reset_index(drop=True)

def normalize_number(x):
    """
    Convierte valores numéricos a entero.
    Maneja guiones, vacíos y NaN.
    """
    if pd.isna(x):
        return pd.NA

    x = str(x).strip()

    if x in ("-", ""):
        return pd.NA

    # Quita espacios antes de convertir
    return int(x.replace(" ", ""))

def reshape(df, year, week):
    """
    Convierte la tabla ancha en formato largo:
    una fila por estado y enfermedad.
    """
    records = []

    for _, row in df.iterrows():
        estado = row[0]

        for disease, cols in COLUMN_MAP.items():
            records.append({
                "anio": year,
                "semana": f"{week:02d}",
                "estado": estado,
                "enfermedad": disease,
                "casos_semana": normalize_number(row[cols["total"]]),
                "acumulado_hombres": normalize_number(row[cols["hombres"]]),
                "acumulado_mujeres": normalize_number(row[cols["mujeres"]]),
                "acumulado_anio_anterior": normalize_number(row[cols["total_prev"]]),
            })

    return pd.DataFrame(records)

def print_run_summary(run_log):
    """
    Imprime un resumen por PDF y calcula % de éxito.
    Éxito = hubo match de página y la tabla limpia tuvo 32 filas.
    """
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

    # Anchos para impresión alineada
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    def fmt(row):
        return " | ".join(val.ljust(widths[i]) for i, val in enumerate(row))

    print(fmt(headers))
    print("-" * (sum(widths) + 3 * (len(headers) - 1)))

    for row in rows:
        print(fmt(row))

    total = len(run_log)
    ok = sum(1 for r in run_log if (r.get("page") is not None) and (r.get("rows") == 32))
    pct = (ok / total * 100) if total else 0.0
    print(f"\nExito: {ok}/{total} = {pct:.1f}% (match y 32 filas)")

def main():
    """
    Función principal:
    - Recorre PDFs
    - Detecta página correcta
    - Extrae tabla
    - Limpia y normaliza datos
    - Consolida todo en un CSV
    """
    pdf_files = sorted(
        f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")
    )
    total_pdfs = len(pdf_files)

    print("=== Inicio ===")
    print(f"PDFs detectados: {total_pdfs}")
    all_rows = []
    page_found = 0
    run_log = []

    for idx, file in enumerate(pdf_files, start=1):
        pct = (idx / total_pdfs * 100) if total_pdfs else 100.0
        pdf_path = os.path.join(INPUT_DIR, file)

        # Defaults para el log
        page, year, week = None, None, None
        filas_base = None
        status = "‼️"

        page, year, week = find_page_and_week(pdf_path)

        # ‼️ No match
        if not page:
            print("  ‼️ No se encontró página válida")
            run_log.append({"file": file, "year": year, "week": week, "page": page, "rows": filas_base})
            print(f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | - | - | {status}")
            continue

        page_found += 1

        tables = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream")

        # ⚠️ Match pero sin tabla
        if tables.n == 0:
            print("  ⚠️ Camelot no detectó tablas")
            status = "⚠️"
            run_log.append({"file": file, "year": year, "week": week, "page": page, "rows": filas_base})
            print(f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | p{page} | {year} W{week:02d} | sin tabla {status} ")
            continue

        df_raw = tables[0].df
        df_clean = clean_df(df_raw)
        filas_base = len(df_clean)
        status = "✅" if filas_base == 32 else "⚠️"
        df_long = reshape(df_clean, year, week)
        all_rows.append(df_long)
        run_log.append({"file": file, "year": year, "week": week, "page": page, "rows": filas_base})
        print(f"{idx:>3}/{total_pdfs:<3} | {pct:>6.1f}% | {file} | p{page} | {year} W{week:02d} | filas={filas_base} {status}")

    print("\n=== Resumen ===")
    print(f"PDFs procesados: {total_pdfs}")
    print(f"PDFs con página válida: {page_found}")
    print("\n=== Resumen por archivo ===")
    print_run_summary(run_log)

    if not all_rows:
        print("No se generaron datos. Archivo final no creado.")
        return

    # Concatenación final
    final_df = pd.concat(all_rows, ignore_index=True)

    # Escritura del CSV consolidado
    final_df.to_csv(OUTPUT_FILE, index=False)

    print(f"Archivo final generado: {OUTPUT_FILE}")
    print(f"Total de filas: {len(final_df)}")
    print("=== Fin ===")

# Punto de entrada del script
if __name__ == "__main__":
    main()
