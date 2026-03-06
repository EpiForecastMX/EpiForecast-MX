"""PDF table extractor: parse SINAVE epidemiological bulletins using Camelot."""

import re
from typing import Any

import pandas as pd
from pypdf import PdfReader, PdfWriter

SEMANA_REGEX = re.compile(r"Semana\s+(\d{1,2}).*?(\d{4})", re.IGNORECASE)
SEMANA_REGEX_2 = re.compile(
    r"semana\s+epidemiol[oó]gica\s+(\d{1,2})\s+del\s+(\d{4})", re.IGNORECASE
)


def build_column_map(
    keywords: list[str], start_col: int = 1, step: int = 4
) -> dict[str, dict[str, int]]:
    """Construye mapa de columnas por padecimiento para las tablas de boletines SINAVE.

    Args:
        keywords:  Lista de nombres de padecimiento.
        start_col: Índice de la primera columna de datos (default 1, tras Entidad).
        step:      Número de columnas por padecimiento (total, hombres, mujeres, año anterior).

    Returns:
        Dict ``{padecimiento: {total: idx, hombres: idx, mujeres: idx, total_prev: idx}}``.
    """
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


def find_page_and_week(
    pdf_path: str, KEYWORDS: list[str]
) -> tuple[int | None, int | None, int | None]:
    """
    Busca la página del PDF que contiene todas las keywords
    y extrae el año y la semana epidemiológica.
    """
    reader = PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        # Verifica que todas las palabras clave estén presentes
        if all(k.lower() in text.lower() for k in KEYWORDS):
            match = SEMANA_REGEX.search(text)  # Opción 1: "Semana 12 2024"
            if match:
                week, year = match.groups()
                return i + 1, int(year), int(week)
            match2 = SEMANA_REGEX_2.search(text)  # Opción 2: "semana epidemiológica 42 del 2024"
            if match2:
                week2, year2 = match2.groups()
                return i + 1, int(year2), int(week2) + 1
            # Si encontró keywords pero no pudo sacar semana/año, dar valores de error 8888 y 99
            return i + 1, 8888, 99
    return None, None, None


def extract_matched_page(pdf_path: str, page_index_0: int, out_pdf_path: str) -> None:
    """Extrae una página específica de un PDF y la guarda en un nuevo archivo.

    Args:
        pdf_path:      Ruta del PDF fuente.
        page_index_0:  Índice de la página (base 0).
        out_pdf_path:  Ruta del PDF de salida.
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.add_page(reader.pages[page_index_0])
    with open(out_pdf_path, "wb") as f:
        writer.write(f)


def eliminar_columnas_vacias(
    df: pd.DataFrame, start_state: str = "Aguascalientes", end_state: str = "Zacatecas"
) -> pd.DataFrame:
    """Elimina columnas vacías dentro del rango de filas de entidades federativas.

    Args:
        df:          DataFrame con columna 0 conteniendo nombres de estados.
        start_state: Nombre del primer estado del rango (default Aguascalientes).
        end_state:   Nombre del último estado del rango (default Zacatecas).

    Returns:
        DataFrame sin columnas que estén 100%% vacías en el rango indicado.
    """
    """
    Elimina columnas que estén completamente vacías ("")  dentro del rango
    de filas entre start_state y end_state (incluyéndolos).
    """
    df = df.copy()
    df.columns = pd.RangeIndex(df.shape[1])  # columnas 0..N-1

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

    is_blank = sub.astype(str).apply(
        lambda col: col.str.strip().eq("")
    )  # True si vacío o espacios
    keep_cols = (
        is_blank.mean(axis=0) < 1.0
    )  # conserva columnas que no son 100% vacías en ese rango

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

    out: dict[int, Any] = {}
    out[0] = df[0]  # Entidad

    for i, kw in enumerate(keywords):
        old_base = 1 + i * 3
        new_base = 1 + i * 4
        out[new_base + 0] = df[old_base + 0]  # total semana
        out[new_base + 1] = df[old_base + 1]  # hombres
        out[new_base + 2] = df[old_base + 2]  # mujeres
        out[new_base + 3] = pd.NA  # año anterior (faltante)

    return pd.DataFrame(out)


def clean_df(df: pd.DataFrame, min_numeric_cells: int = 2) -> pd.DataFrame:
    """
    Limpia la tabla extraída por Camelot dejando solo filas que parecen "estado + datos".

    Regla:
    - Conserva filas donde la columna 0 tiene texto (nombre del estado)
    - y donde existan al menos `min_numeric_cells` valores numéricos enteros en columnas 1..N
    """
    # 1) Elimina columnas completamente vacías en el intervalo Aguascalientes..Zacatecas
    df = eliminar_columnas_vacias(df)

    # 2) Normaliza primera columna (estado)
    df.columns = pd.RangeIndex(df.shape[1])
    df[0] = df[0].astype(str).str.strip()

    # 3) Quita filas basura
    df = df[df[0].ne("")]
    df = df[
        ~df[0].str.match(r"^(ENTIDAD|FEDERATIVA|TOTAL.*|FUENTE.*|NOTA.*)$", case=False, na=False)
    ]

    # 4) Normaliza celdas numéricas SOLO para validar filas (no conviertas todo a 0 aquí)
    num_cols = [c for c in df.columns if c != 0]
    cells = df[num_cols].astype(str).apply(lambda col: col.str.strip())

    # limpia miles para conteo: "1 450" / "1,450" -> "1450"
    cells_clean = cells.replace(r"[ ,]", "", regex=True)

    # para el conteo, "-" y "" cuentan como numéricos (porque serán 0)
    is_zeroish = cells.apply(lambda col: col.eq("-") | col.eq(""))
    is_int = cells_clean.apply(lambda col: col.str.fullmatch(r"\d+").fillna(False))

    numeric_like = is_int | is_zeroish
    numeric_count = numeric_like.sum(axis=1)

    df = df[numeric_count >= min_numeric_cells]

    return df.reset_index(drop=True)


def normalize_number(x: Any) -> Any:
    """Normaliza un valor extraído de tabla PDF a entero o ``pd.NA``.

    Interpreta guiones y cadenas vacías como 0, elimina separadores
    de miles (espacios y comas), y retorna ``pd.NA`` para texto no numérico.

    Args:
        x: Valor crudo de celda (str, int, float o NA).

    Returns:
        Entero normalizado, 0 para valores vacíos, o ``pd.NA`` para texto.
    """
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


def reshape(
    df: pd.DataFrame, year: int, week: int, col_map: dict[str, dict[str, int]]
) -> pd.DataFrame:
    """Transforma tabla ancha extraída del boletín a formato largo (tidy).

    Args:
        df:      DataFrame limpio con una fila por entidad.
        year:    Año epidemiológico del boletín.
        week:    Semana epidemiológica del boletín.
        col_map: Mapa de columnas por padecimiento (de ``build_column_map``).

    Returns:
        DataFrame en formato largo con columnas: Anio, Semana, Entidad, Padecimiento, etc.
    """
    records = []
    for _, row in df.iterrows():
        estado = row[0]
        for disease, cols in col_map.items():
            records.append(
                {
                    "Anio": year,
                    "Semana": f"{week:02d}",
                    "Entidad": estado,
                    "Padecimiento": disease,
                    "Casos_semana": normalize_number(row[cols["total"]]),
                    "Acumulado_hombres": normalize_number(row[cols["hombres"]]),
                    "Acumulado_mujeres": normalize_number(row[cols["mujeres"]]),
                    "Acumulado_anio_anterior": normalize_number(row[cols["total_prev"]]),
                }
            )
    return pd.DataFrame(records)


def reshape_wide(
    df: pd.DataFrame, year: int, week: int, col_map: dict[str, dict[str, int]]
) -> pd.DataFrame:
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


def print_run_summary(run_log: list[dict[str, Any]], log_fn: Any = print) -> None:
    """Imprime tabla resumen del pipeline de extracción con estadísticas de éxito.

    Args:
        run_log: Lista de dicts con claves file, year, week, page, rows.
        log_fn:  Función de logging (default: print).
    """
    headers = ["Nombre del archivo", "Anio", "Semana", "Pagina match", "Filas"]
    rows = []

    for r in run_log:
        rows.append(
            [
                str(r.get("file", "")),
                "" if r.get("year") is None else str(r.get("year")),
                "" if r.get("week") is None else f"{int(r['week']):02d}",
                "" if r.get("page") is None else str(r.get("page")),
                "" if r.get("rows") is None else str(r.get("rows")),
            ]
        )

    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))

    def fmt(row: list[str]) -> str:
        """Formatea una fila con anchos de columna alineados."""
        return " | ".join(val.ljust(widths[i]) for i, val in enumerate(row))

    log_fn(fmt(headers))
    log_fn("-" * (sum(widths) + 3 * (len(headers) - 1)))

    for row in rows:
        log_fn(fmt(row))

    total = len(run_log)
    ok = sum(1 for r in run_log if (r.get("page") is not None) and (r.get("rows") == 32))
    pct = (ok / total * 100) if total else 0.0
    log_fn(f"\nExito: {ok}/{total} = {pct:.1f}% (match y 32 filas)")
