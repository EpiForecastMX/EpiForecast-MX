"""Dengue table extractor: parse SINAVE per-entity Dengue tables (WHO 2009 / ICD A97.x).

A diferencia de las tablas neuro (Depresión/Parkinson/Alzheimer), el Dengue vive en
una tabla aparte del boletín SINAVE con TRES categorías de severidad:

    A97.0  Dengue no grave
    A97.1  Dengue con signos de alarma
    A97.2  Dengue grave

La estructura por entidad es idéntica a la tabla neuro: 4 columnas por categoría
``[Sem, Acumulado_hombres, Acumulado_mujeres, Acumulado_anio_anterior]`` (12 en total).

Siguiendo la recomendación basada en literatura (dengue grave ~0.1-0.2% de casos →
series casi-cero no pronosticables a nivel estatal), este extractor **agrega** las tres
categorías en un único padecimiento ``"Dengue"``, sumando columna por columna.

El localizador de página se ancla en los **códigos CIE A97.0/A97.1/A97.2** (más estables
entre semanas/años que la redacción, que varía: "sin/con datos de alarma" vs
"no grave/con signos de alarma", "severo" vs "grave"). El esquema OMS 1997 (A90/A91,
boletines pre-2019) NO es soportado por este extractor y se reporta como no extraído.
"""

from pathlib import Path
import re
import unicodedata

import camelot
import pandas as pd
from pypdf import PdfReader

from epiforecast.constants import STATES
from epiforecast.data.extraction.pdf_extractor import (
    SEMANA_REGEX,
    SEMANA_REGEX_2,
    clean_df,
    normalize_number,
)

# Códigos CIE-10 de las tres categorías de severidad (esquema OMS 2009).
DENGUE_CIE_CODES = ("a97.0", "a97.1", "a97.2")

# Categorías por severidad y columnas por categoría (idéntico a la tabla neuro).
N_SEVERITIES = 3
COLS_PER_SEVERITY = 4  # Sem, Acum_hombres, Acum_mujeres, Acum_anio_anterior
N_DATA_COLS = N_SEVERITIES * COLS_PER_SEVERITY  # 12
N_STATES_EXPECTED = 32

# Tolerancia de validación: discrepancia absoluta total admisible entre la suma de
# las 32 entidades y el renglón TOTAL impreso. Cubre erratas tipográficas del boletín
# y lecturas de una sola celda; rechaza desalineaciones estructurales (miles de casos).
TOTAL_ABS_TOLERANCE = 10

# Alias de entidades hacia el nombre canónico de ``STATES``.
_ENTITY_ALIASES = {
    "Distrito Federal": "Ciudad de México",
    "Estado de México": "México",
    "Edo. de México": "México",
    "Edo. México": "México",
}

# Nombre de archivo del scraper: ``YYYY_semNN.pdf`` (fuente autoritativa de año/semana).
_FILENAME_RE = re.compile(r"(\d{4})_sem(\d{2})", re.IGNORECASE)


def _norm_entity(name: str) -> str:
    """Normaliza un nombre de entidad para matching robusto (sin acentos, minúsculas)."""
    decomposed = unicodedata.normalize("NFKD", str(name))
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_only.strip().lower()


# Mapa normalizado -> nombre canónico (incluye estados y alias).
_STATE_LOOKUP: dict[str, str] = {_norm_entity(s): s for s in STATES}
_STATE_LOOKUP.update({_norm_entity(k): v for k, v in _ENTITY_ALIASES.items()})


def _year_week_from_filename(pdf_path: str) -> tuple[int | None, int | None]:
    """Extrae ``(anio, semana)`` del nombre de archivo ``YYYY_semNN.pdf``.

    Es la fuente autoritativa: el parseo del texto de la página es frágil (el formato
    "semana epidemiológica N del YYYY" dispara un ``+1`` erróneo en algunos boletines).
    """
    match = _FILENAME_RE.search(Path(pdf_path).name)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def find_dengue_page_and_week(pdf_path: str) -> tuple[int | None, int | None, int | None]:
    """Localiza la página de la tabla de Dengue por entidad y extrae año/semana.

    La página objetivo contiene los tres códigos CIE (A97.0/A97.1/A97.2) y filas por
    entidad federativa (se exige la presencia de Aguascalientes y Zacatecas como
    marcadores del rango de estados, para distinguir la tabla estatal del resumen
    nacional, que también lista los tres códigos pero con padecimientos como filas).

    Args:
        pdf_path: Ruta del boletín PDF.

    Returns:
        Tupla ``(pagina_1based, anio, semana)``; ``(None, None, None)`` si no se halla.
        Si la página existe pero no se puede parsear semana/año, retorna ``(pagina, 8888, 99)``.
    """
    reader = PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        low = text.lower()
        has_codes = all(code in low for code in DENGUE_CIE_CODES)
        has_states = "aguascalientes" in low and "zacatecas" in low
        if not (has_codes and has_states):
            continue

        match = SEMANA_REGEX.search(text)
        if match:
            week, year = match.groups()
            return i + 1, int(year), int(week)
        match2 = SEMANA_REGEX_2.search(text)
        if match2:
            week2, year2 = match2.groups()
            return i + 1, int(year2), int(week2) + 1
        return i + 1, 8888, 99
    return None, None, None


def _restrict_to_states(df: pd.DataFrame) -> pd.DataFrame:
    """Conserva solo las filas cuya columna 0 es una entidad federativa canónica.

    Descarta pies de página (``§FUENTE...``), filas ``TOTAL`` residuales y cualquier
    ruido que ``clean_df`` no haya filtrado. Normaliza alias (Distrito Federal).
    """
    df = df.copy()
    df.columns = pd.RangeIndex(df.shape[1])
    canon = df[0].astype(str).map(lambda x: _STATE_LOOKUP.get(_norm_entity(x)))
    keep = canon.notna()
    df = df[keep].copy()
    df[0] = canon[keep].to_numpy()
    return df.reset_index(drop=True)


def reshape_dengue_aggregated(df_clean: pd.DataFrame, year: int, week: int) -> pd.DataFrame:
    """Agrega las 3 categorías de severidad en un único padecimiento ``"Dengue"``.

    Espera un DataFrame con la columna 0 = entidad y exactamente 12 columnas de datos
    (3 severidades x 4 columnas). Suma, por entidad, las columnas homólogas de las tres
    severidades.

    Args:
        df_clean: Tabla limpia restringida a entidades (1 + 12 columnas).
        year:     Año epidemiológico.
        week:     Semana epidemiológica.

    Returns:
        DataFrame largo (tidy) con el esquema de ``dataset_boletin_epidemiologico.csv``.

    Raises:
        ValueError: Si el número de columnas de datos no es 12.
    """
    n_data = df_clean.shape[1] - 1
    if n_data != N_DATA_COLS:
        raise ValueError(f"Se esperaban {N_DATA_COLS} columnas de datos, se hallaron {n_data}.")

    df = df_clean.copy()
    df.columns = pd.RangeIndex(df.shape[1])

    records = []
    for _, row in df.iterrows():
        # Acumula las 3 severidades en los 4 campos homólogos.
        sem = hombres = mujeres = prev = 0
        for s in range(N_SEVERITIES):
            base = 1 + s * COLS_PER_SEVERITY
            sem += _as_int(row[base + 0])
            hombres += _as_int(row[base + 1])
            mujeres += _as_int(row[base + 2])
            prev += _as_int(row[base + 3])
        records.append(
            {
                "Anio": year,
                "Semana": f"{week:02d}",
                "Entidad": row[0],
                "Padecimiento": "Dengue",
                "Casos_semana": sem,
                "Acumulado_hombres": hombres,
                "Acumulado_mujeres": mujeres,
                "Acumulado_anio_anterior": prev,
            }
        )
    return pd.DataFrame(records)


def _as_int(value: object) -> int:
    """Normaliza una celda a entero, tratando ``-``/vacío/NA como 0."""
    norm = normalize_number(value)
    return 0 if pd.isna(norm) else int(norm)


def _parse_total_row(page_text: str) -> list[int] | None:
    """Extrae los 12 valores del renglón ``TOTAL`` desde el texto de la página.

    El renglón TOTAL del boletín usa el espacio como separador de miles (``1 582``),
    que se colapsa a ``1582`` antes de tokenizar. Los guiones cuentan como 0.
    """
    for line in page_text.splitlines():
        if not line.strip().upper().startswith("TOTAL"):
            continue
        body = line.strip()[len("TOTAL") :]
        # SINAVE mezcla separadores de miles: coma ("1,332") y espacio ("7 655"),
        # a veces en el mismo renglón. Se eliminan comas y se colapsan espacios de
        # miles (un solo espacio + grupo de 3 dígitos); las columnas van separadas
        # por 2+ espacios, que no se colapsan.
        body = body.replace(",", "")
        prev = None
        while prev != body:
            prev = body
            body = re.sub(r"(\d) (\d{3})(?!\d)", r"\1\2", body)
        tokens = re.findall(r"-|\d+", body)
        vals = [0 if t == "-" else int(t) for t in tokens]
        return vals if len(vals) >= N_DATA_COLS else None
    return None


def extract_dengue_from_pdf(pdf_path: str) -> dict[str, object]:
    """Extrae y agrega la tabla de Dengue por entidad de un boletín SINAVE.

    Args:
        pdf_path: Ruta del boletín PDF.

    Returns:
        Dict con claves:
          - ``df``:       DataFrame largo agregado, o ``None`` si falló.
          - ``page``, ``year``, ``week``: metadatos de localización.
          - ``n_states``: número de entidades extraídas.
          - ``valid``:    ``True`` si la suma por categoría cuadra con el renglón TOTAL.
          - ``reason``:   motivo del fallo/aviso (str) o ``""``.
    """
    out: dict[str, object] = {
        "df": None,
        "page": None,
        "year": None,
        "week": None,
        "n_states": 0,
        "valid": False,
        "absdiff": None,
        "reason": "",
    }

    page, page_year, page_week = find_dengue_page_and_week(pdf_path)
    out["page"] = page
    if not page:
        out["reason"] = "sin pagina A97.x (posible esquema OMS 1997 A90/A91 pre-2019)"
        return out

    # Año/semana autoritativos del nombre de archivo; el parseo de página solo es
    # respaldo (su rama "semana epidemiológica N del YYYY" suma +1 erróneamente,
    # lo que desfasaba semanas y generaba duplicados/huecos).
    file_year, file_week = _year_week_from_filename(pdf_path)
    year = file_year if file_year is not None else page_year
    week = file_week if file_week is not None else page_week
    out.update(year=year, week=week)
    if year is None or week is None or year == 8888 or week == 99:
        out["reason"] = "no se pudo determinar semana/anio"
        return out

    tables = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream")
    if tables.n == 0:
        out["reason"] = "camelot no detecto tabla"
        return out

    df_states = _restrict_to_states(clean_df(tables[0].df))
    out["n_states"] = len(df_states)

    if df_states.shape[1] - 1 != N_DATA_COLS:
        out["reason"] = f"columnas inesperadas: {df_states.shape[1] - 1} (esperado {N_DATA_COLS})"
        return out
    if len(df_states) != N_STATES_EXPECTED:
        out["reason"] = (
            f"parse incompleto: {len(df_states)} entidades (esperado {N_STATES_EXPECTED})"
        )
        return out
    dup_col = _duplicated_adjacent_column(df_states)
    if dup_col is not None:
        out["reason"] = f"artefacto de columna duplicada (col {dup_col}); extraccion no confiable"
        return out

    assert year is not None and week is not None  # garantizado por los guards previos
    df_long = reshape_dengue_aggregated(df_states, int(year), int(week))
    out["df"] = df_long

    # Validación: suma por categoría de las 32 entidades vs renglón TOTAL del boletín.
    page_text = PdfReader(pdf_path).pages[int(page) - 1].extract_text() or ""
    absdiff = _total_discrepancy(df_states, page_text)
    out["absdiff"] = absdiff
    if absdiff is None:
        out["reason"] = "no se hallo renglon TOTAL para validar"
        return out
    out["valid"] = absdiff <= TOTAL_ABS_TOLERANCE
    if not out["valid"]:
        out["reason"] = f"suma no cuadra con TOTAL (absdiff={absdiff})"
    elif absdiff > 0:
        out["reason"] = f"validado con tolerancia (absdiff={absdiff})"
    return out


def _duplicated_adjacent_column(df_states: pd.DataFrame, min_states: int = 16) -> int | None:
    """Detecta el artefacto de Camelot donde una columna duplica a su vecina.

    En algunos boletines (p.ej. 2024_sem29) Camelot copia el valor de una columna en
    la celda adyacente vacía, desalineando la fila. Si dos columnas de datos contiguas
    son idénticas (con valor no trivial) en al menos ``min_states`` entidades, la
    extracción no es confiable y el boletín debe descartarse.

    Returns:
        Índice (1-based, en el espacio de columnas de datos) de la primera columna
        duplicada, o ``None`` si no se detecta el artefacto.
    """
    df = df_states.copy()
    df.columns = pd.RangeIndex(df.shape[1])
    for col in range(1, N_DATA_COLS):
        left = df[col].astype(str).str.strip()
        right = df[col + 1].astype(str).str.strip()
        equal_nonblank = (left == right) & left.ne("-") & left.ne("")
        if int(equal_nonblank.sum()) >= min_states:
            return col
    return None


def _total_discrepancy(df_states: pd.DataFrame, page_text: str) -> int | None:
    """Discrepancia absoluta total entre la suma de las 12 columnas y el renglón TOTAL.

    Retorna ``None`` si no se puede parsear el renglón TOTAL.
    """
    total = _parse_total_row(page_text)
    if total is None:
        return None
    df = df_states.copy()
    df.columns = pd.RangeIndex(df.shape[1])
    sums = [int(df[c].map(_as_int).sum()) for c in range(1, 1 + N_DATA_COLS)]
    return sum(abs(a - b) for a, b in zip(sums, total[:N_DATA_COLS], strict=True))
