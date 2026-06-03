"""Validación de la extracción de Dengue (SRP, separado de ``dengue_extractor.py``).

Define la estructura esperada de la tabla de Dengue por entidad y las comprobaciones de
calidad: parseo del renglón ``TOTAL`` impreso, discrepancia contra la suma de las 32
entidades, y detección del artefacto de columna duplicada de Camelot.
"""

import re

import pandas as pd

from epiforecast.data.extraction.pdf_extractor import normalize_number

# Estructura de la tabla de Dengue por entidad: 3 severidades x 4 columnas
# (idéntica a la tabla neuro): Sem, Acum_hombres, Acum_mujeres, Acum_anio_anterior.
N_SEVERITIES = 3
COLS_PER_SEVERITY = 4
N_DATA_COLS = N_SEVERITIES * COLS_PER_SEVERITY  # 12
N_STATES_EXPECTED = 32

# Tolerancia de validación: discrepancia absoluta total admisible entre la suma de las
# 32 entidades y el renglón TOTAL impreso. Cubre erratas tipográficas del boletín y
# lecturas de una sola celda; rechaza desalineaciones estructurales (miles de casos).
TOTAL_ABS_TOLERANCE = 10

# Mínimo de entidades con dos columnas adyacentes idénticas para declarar el artefacto.
_DUP_MIN_STATES = 16


def as_int(value: object) -> int:
    """Normaliza una celda a entero, tratando ``-``/vacío/NA como 0."""
    norm = normalize_number(value)
    return 0 if pd.isna(norm) else int(norm)


def parse_total_row(page_text: str, n_expected: int = N_DATA_COLS) -> list[int] | None:
    """Extrae los valores del renglón ``TOTAL`` desde el texto de la página.

    SINAVE mezcla separadores de miles: coma (``1,332``) y espacio (``7 655``), a veces
    en el mismo renglón. Se eliminan comas y se colapsan los espacios de miles (un solo
    espacio + grupo de 3 dígitos); las columnas van separadas por 2+ espacios, que no se
    colapsan. Los guiones cuentan como 0.

    Args:
        page_text: Texto plano de la página de la tabla.
        n_expected: Número mínimo de valores esperados (12 en el layout de producción
            2020+, 10 en el layout histórico 2018-2019). El renglón se acepta si tiene
            al menos esa cantidad.
    """
    for line in page_text.splitlines():
        if not line.strip().upper().startswith("TOTAL"):
            continue
        body = line.strip()[len("TOTAL") :]
        body = body.replace(",", "")
        prev = None
        while prev != body:
            prev = body
            body = re.sub(r"(\d) (\d{3})(?!\d)", r"\1\2", body)
        tokens = re.findall(r"-|\d+", body)
        vals = [0 if t == "-" else int(t) for t in tokens]
        return vals if len(vals) >= n_expected else None
    return None


def total_discrepancy(df_states: pd.DataFrame, page_text: str) -> int | None:
    """Discrepancia absoluta total entre la suma de las 12 columnas y el renglón TOTAL.

    Retorna ``None`` si no se puede parsear el renglón TOTAL.
    """
    total = parse_total_row(page_text)
    if total is None:
        return None
    df = df_states.copy()
    df.columns = pd.RangeIndex(df.shape[1])
    sums = [int(df[c].map(as_int).sum()) for c in range(1, 1 + N_DATA_COLS)]
    return sum(abs(a - b) for a, b in zip(sums, total[:N_DATA_COLS], strict=True))


def duplicated_adjacent_column(
    df_states: pd.DataFrame, min_states: int = _DUP_MIN_STATES, n_data_cols: int = N_DATA_COLS
) -> int | None:
    """Detecta el artefacto de Camelot donde una columna duplica a su vecina.

    En algunos boletines (p.ej. 2024_sem29) Camelot copia el valor de una columna en la
    celda adyacente vacía, desalineando la fila. Si dos columnas de datos contiguas son
    idénticas (con valor no trivial) en al menos ``min_states`` entidades, la extracción
    no es confiable y el boletín debe descartarse.

    Returns:
        Índice (1-based, en el espacio de columnas de datos) de la primera columna
        duplicada, o ``None`` si no se detecta el artefacto.
    """
    df = df_states.copy()
    df.columns = pd.RangeIndex(df.shape[1])
    for col in range(1, n_data_cols):
        left = df[col].astype(str).str.strip()
        right = df[col + 1].astype(str).str.strip()
        equal_nonblank = (left == right) & left.ne("-") & left.ne("")
        if int(equal_nonblank.sum()) >= min_states:
            return col
    return None
