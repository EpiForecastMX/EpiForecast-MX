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
"no grave/con signos de alarma", "severo" vs "grave").

Layouts soportados (misma taxonomía A97.x):
  - **Producción (2020+):** 12 columnas de datos (acum. año anterior por severidad).
  - **Histórico (2018 sem 27+ y 2019):** 10 columnas (ver ``dengue_historico``); SINAVE
    adoptó A97.x desde la sem 27 de 2018. El branch por año conmuta el reshape/validación.

El esquema OMS 1997 (A90/A91, boletines 2014 → 2018 sem 26) usa otra tabla (por estatus
de caso, SIN desglose por sexo) y NO es soportado por este extractor; se reporta como no
extraído. Su serie TOTAL nacional se maneja aparte (ver ``dengue_historico_a9091``).
"""

from pathlib import Path
import re
import unicodedata

import camelot
import pandas as pd
from pypdf import PdfReader

from epiforecast.constants import STATES
from epiforecast.data.extraction.dengue_historico import (
    N_DATA_COLS_HIST,
    reshape_dengue_hist,
    total_discrepancy_hist,
)
from epiforecast.data.extraction.dengue_validation import (
    COLS_PER_SEVERITY,
    N_DATA_COLS,
    N_SEVERITIES,
    N_STATES_EXPECTED,
    TOTAL_ABS_TOLERANCE,
    as_int,
    duplicated_adjacent_column,
    total_discrepancy,
)
from epiforecast.data.extraction.pdf_extractor import (
    SEMANA_REGEX,
    SEMANA_REGEX_2,
    clean_df,
)

# Códigos CIE-10 de las tres categorías de severidad (esquema OMS 2009).
DENGUE_CIE_CODES = ("a97.0", "a97.1", "a97.2")

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
            sem += as_int(row[base + 0])
            hombres += as_int(row[base + 1])
            mujeres += as_int(row[base + 2])
            prev += as_int(row[base + 3])
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

    # Layout histórico (2018 sem 27+ y 2019): misma taxonomía A97.x que producción pero
    # tabla de 10 columnas de datos (el "acum. año anterior" solo aparece en la 1ª
    # severidad). Producción (2020+) conserva el layout de 12 columnas intacto.
    is_hist = int(year) < 2020
    expected_cols = N_DATA_COLS_HIST if is_hist else N_DATA_COLS

    if df_states.shape[1] - 1 != expected_cols:
        out["reason"] = (
            f"columnas inesperadas: {df_states.shape[1] - 1} (esperado {expected_cols})"
        )
        return out
    if len(df_states) != N_STATES_EXPECTED:
        out["reason"] = (
            f"parse incompleto: {len(df_states)} entidades (esperado {N_STATES_EXPECTED})"
        )
        return out
    dup_col = duplicated_adjacent_column(df_states, n_data_cols=expected_cols)
    if dup_col is not None:
        out["reason"] = f"artefacto de columna duplicada (col {dup_col}); extraccion no confiable"
        return out

    assert year is not None and week is not None  # garantizado por los guards previos
    if is_hist:
        df_long = reshape_dengue_hist(df_states, int(year), int(week))
    else:
        df_long = reshape_dengue_aggregated(df_states, int(year), int(week))
    out["df"] = df_long

    # Validación: suma por categoría de las 32 entidades vs renglón TOTAL del boletín.
    page_text = PdfReader(pdf_path).pages[int(page) - 1].extract_text() or ""
    absdiff = (
        total_discrepancy_hist(df_states, page_text)
        if is_hist
        else total_discrepancy(df_states, page_text)
    )
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
