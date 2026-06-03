"""Parser del layout histórico A97.x de 2018 (sem 27+) y 2019.

A partir de la semana 27 de 2018 el boletín SINAVE adoptó la clasificación OMS 2009
(A97.0/A97.1/A97.2), **la misma taxonomía que producción (2020+)**, pero con un layout
de tabla distinto que ``clean_df`` + ``_restrict_to_states`` normaliza a **10 columnas de
datos** (no 12):

    A97.0 (no grave):            col 1=Sem, col 2=Hombres, col 3=Mujeres, col 4=Acum. año anterior
    A97.1 (signos de alarma):    col 5=Sem, col 6=Hombres, col 7=Mujeres
    A97.2 (grave):               col 8=Sem, col 9=Hombres, col 10=Mujeres

Diferencias vs el layout de producción (12 col): (1) la columna "acumulado año anterior"
solo aparece en la primera severidad; (2) las etiquetas de sexo son ``M``/``F``
(masculino/femenino) en vez de ``H``/``M`` — pero el **orden es el mismo** (hombre primero,
mujer después), así que el mapeo posicional coincide. Este módulo se aplica solo a años
< 2020; producción (2020+) sigue intacta en ``dengue_extractor``.
"""

import pandas as pd

from epiforecast.data.extraction.dengue_validation import as_int, parse_total_row

# Layout histórico de 10 columnas de datos (1-based sobre la tabla restringida a estados,
# donde la columna 0 es la entidad). Hombres = primera columna de sexo de cada severidad.
N_DATA_COLS_HIST = 10
_SEM_COLS = (1, 5, 8)
_HOMBRES_COLS = (2, 6, 9)
_MUJERES_COLS = (3, 7, 10)
_PREV_COL = 4  # acumulado año anterior, solo disponible en la primera severidad


def reshape_dengue_hist(df_clean: pd.DataFrame, year: int, week: int) -> pd.DataFrame:
    """Agrega las 3 severidades del layout histórico (10 col) en un único ``"Dengue"``.

    Args:
        df_clean: Tabla limpia restringida a entidades (1 + 10 columnas).
        year:     Año epidemiológico.
        week:     Semana epidemiológica.

    Returns:
        DataFrame largo (tidy) con el esquema de ``dataset_boletin_epidemiologico.csv``.

    Raises:
        ValueError: Si el número de columnas de datos no es 10.
    """
    n_data = df_clean.shape[1] - 1
    if n_data != N_DATA_COLS_HIST:
        raise ValueError(
            f"Layout histórico: se esperaban {N_DATA_COLS_HIST} columnas de datos, "
            f"se hallaron {n_data}."
        )

    df = df_clean.copy()
    df.columns = pd.RangeIndex(df.shape[1])

    records = []
    for _, row in df.iterrows():
        sem = sum(as_int(row[c]) for c in _SEM_COLS)
        hombres = sum(as_int(row[c]) for c in _HOMBRES_COLS)
        mujeres = sum(as_int(row[c]) for c in _MUJERES_COLS)
        prev = as_int(row[_PREV_COL])
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


def total_discrepancy_hist(df_states: pd.DataFrame, page_text: str) -> int | None:
    """Discrepancia absoluta entre la suma de las 10 columnas y el renglón TOTAL.

    Retorna ``None`` si no se puede parsear el renglón TOTAL.
    """
    total = parse_total_row(page_text, n_expected=N_DATA_COLS_HIST)
    if total is None:
        return None
    df = df_states.copy()
    df.columns = pd.RangeIndex(df.shape[1])
    sums = [int(df[c].map(as_int).sum()) for c in range(1, 1 + N_DATA_COLS_HIST)]
    return sum(abs(a - b) for a, b in zip(sums, total[:N_DATA_COLS_HIST], strict=True))
