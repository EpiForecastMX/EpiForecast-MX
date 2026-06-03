"""Parser histórico OMS 1997 (A90/A91) para Dengue: 2014 → 2018-W26.

A diferencia del esquema OMS 2009 (A97.x, ver ``dengue_extractor`` / ``dengue_historico``),
los boletines 2014→2018-W26 reportan Dengue bajo CIE A90/A91 en una tabla por **estatus de
caso** (Confirmados / En Estudio) y año (actual / anterior). Hay dos variantes de layout:

  - **Variante A (2014-2015):** 2 bloques de severidad (A90, A91), confirmados por sexo (M/F).
  - **Variante B (2016 → 2018-W26):** 3 bloques (Dengue no grave / con signos de alarma / grave),
    confirmados por sexo (M/F).

**Esta serie es independiente del pipeline neuro/A97.x por sexo de producción**: cambia la
taxonomía (A90/A91 vs A97.x) y mezcla definiciones (confirmado vs en estudio). Se extrae como
artefacto SEPARADO de contexto/EDA (``Padecimiento = "Dengue_A90A91"``), NO se mergea al
consolidado de producción.

Extracción robusta por **posición** (pdfplumber): ``camelot``/``extract_table`` fallan porque
SINAVE usa el espacio como separador de miles (``3 473`` = 3473), que confunden con el corte de
columna. Se agrupan las palabras por banda de coordenada x (las cifras de miles caen dentro de
su banda; entre columnas hay un hueco claro) y se suman SOLO las columnas con encabezado de sexo
(M/F) = confirmados del año en curso, excluyendo año anterior y "En Estudio". Cada boletín se
valida contra el renglón TOTAL impreso.
"""

from __future__ import annotations

import re
from typing import Any
import unicodedata

import pdfplumber
from pypdf import PdfReader

from epiforecast.constants import STATES

# Palabra de pdfplumber: dict con claves text/x0/x1/top/bottom (entre otras).
Word = dict[str, Any]

# Tolerancia de validación (suma de entidades vs TOTAL impreso), en casos absolutos.
TOTAL_ABS_TOLERANCE_A9091 = 15
# Hueco mínimo (pt) entre centros de palabra para separar columnas (calibrado: las cifras de
# miles intra-columna distan < ~10pt; entre columnas > ~14pt).
_MIN_COL_GAP = 14.0
_FILENAME_RE = re.compile(r"(\d{4})_sem(\d{2})", re.IGNORECASE)


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().strip().lower()


_STATE_NORMS = {_norm(s) for s in STATES} | {"distrito federal"}
_STATE_CANON = {_norm(s): s for s in STATES}
_STATE_CANON["distrito federal"] = "Ciudad de México"


def _year_week_from_filename(pdf_path: str) -> tuple[int | None, int | None]:
    m = _FILENAME_RE.search(pdf_path.rsplit("/", 1)[-1])
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def find_a9091_page(pdf_path: str) -> int | None:
    """Índice 0-based de la página con la tabla A90/A91 por entidad, o ``None``."""
    reader = PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        low = (page.extract_text() or "").lower()
        if ("a90" in low or "a91" in low) and "aguascalientes" in low and "zacatecas" in low:
            return i
    return None


def _column_bands(
    centers: list[float], min_gap: float = _MIN_COL_GAP
) -> list[tuple[float, float]]:
    """Agrupa centros-x en bandas de columna (corte donde el hueco supera ``min_gap``)."""
    if not centers:
        return []
    centers = sorted(centers)
    bands: list[tuple[float, float]] = []
    start = prev = centers[0]
    for x in centers[1:]:
        if x - prev > min_gap:
            bands.append((start, prev))
            start = x
        prev = x
    bands.append((start, prev))
    return bands


# Separación vertical (pt) para considerar dos palabras en renglones distintos. Los
# renglones de entidad distan ~9-12pt; la varianza intra-renglón es <2pt. Un umbral fijo
# por buckets (round(top/3)) partía algunas filas en su frontera (perdía los números de la
# entidad, p.ej. Sonora); el agrupamiento por hueco evita ese corte arbitrario.
_ROW_GAP = 5.0


def _extract_words_by_row(page: pdfplumber.page.Page) -> dict[int, list[Word]]:
    """Agrupa palabras en renglones por cercanía vertical (clustering por hueco en ``top``)."""
    words = sorted(page.extract_words(x_tolerance=1.5), key=lambda w: w["top"])
    rows: dict[int, list[Word]] = {}
    rid = 0
    prev_top: float | None = None
    for w in words:
        if prev_top is not None and w["top"] - prev_top > _ROW_GAP:
            rid += 1
        rows.setdefault(rid, []).append(w)
        prev_top = w["top"]
    return rows


# Nombres de entidad ordenados por longitud descendente: el match por prefijo más largo
# evita que "Baja California Sur" se confunda con "Baja California" (prefijo común).
_STATE_NORMS_BY_LEN = sorted(_STATE_CANON.items(), key=lambda kv: -len(kv[0]))


def _is_state_row(words_sorted: list[Word]) -> str | None:
    """Devuelve el nombre canónico si la fila empieza con una entidad, si no ``None``."""
    if not words_sorted:
        return None
    head = _norm(" ".join(w["text"] for w in words_sorted[:4]))
    for norm_name, canon in _STATE_NORMS_BY_LEN:
        if head.startswith(norm_name):
            return canon
    return None


def _xc(w: Word) -> float:
    return float((w["x0"] + w["x1"]) / 2.0)


def _band_of(xc: float, bands: list[tuple[float, float]]) -> int:
    """Índice de la banda cuyo rango contiene ``xc`` (o la más cercana)."""
    for i, (lo, hi) in enumerate(bands):
        if lo - _MIN_COL_GAP / 2 <= xc <= hi + _MIN_COL_GAP / 2:
            return i
    return min(range(len(bands)), key=lambda i: abs((bands[i][0] + bands[i][1]) / 2 - xc))


def _calibrate_bands(state_rows: list[list[Word]]) -> list[tuple[float, float]]:
    """Bandas de columna numérica a partir de los centros-x de TODAS las filas de estado."""
    centers: list[float] = []
    for ws in state_rows:
        for w in ws[1:]:
            if any(c.isdigit() for c in w["text"]):
                centers.append(_xc(w))
    return _column_bands(centers)


def _sex_bands(page: pdfplumber.page.Page, bands: list[tuple[float, float]]) -> set[int]:
    """Índices de banda con encabezado de sexo (M/F) = confirmados del año en curso.

    Excluye columnas de año anterior y "En Estudio" (sin encabezado M/F).
    """
    height = page.height
    sexed: set[int] = set()
    for w in page.extract_words(x_tolerance=1.5):
        # El encabezado M/F aparece en el tercio superior (varía 0.30-0.35 según el año).
        if w["top"] < height * 0.42 and w["text"].strip() in ("M", "F"):
            sexed.add(_band_of(_xc(w), bands))
    return sexed


def _cells(words: list[Word], bands: list[tuple[float, float]]) -> list[str]:
    """Concatena las palabras de una fila por banda.

    Cada palabra se asigna a su banda por la coordenada x de su centro y se concatena
    dentro de ella. Las cifras de miles (``1 326``) caen en la misma banda (su ancho
    abarca dígito líder y resto), por lo que se unen sin fusión previa; esto evita el
    sobre-merge de columnas contiguas en el renglón TOTAL (más denso)."""
    out = [""] * len(bands)
    for w in sorted(words, key=lambda x: x["x0"]):
        out[_band_of(_xc(w), bands)] += w["text"]
    return out


def _to_int(cell: str) -> int:
    digits = re.sub(r"[^\d]", "", cell)
    return int(digits) if digits else 0


def extract_a9091_from_pdf(pdf_path: str) -> dict[str, object]:
    """Extrae Dengue confirmado por sexo (A90/A91) de un boletín 2014→2018-W26.

    Returns dict con ``df`` (largo, Padecimiento="Dengue_A90A91"), ``year``, ``week``,
    ``n_states``, ``valid``, ``absdiff`` y ``reason`` (análogo a ``extract_dengue_from_pdf``).
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
    year, week = _year_week_from_filename(pdf_path)
    out.update(year=year, week=week)
    if year is None or week is None:
        out["reason"] = "sin año/semana en el nombre de archivo"
        return out

    pg = find_a9091_page(pdf_path)
    out["page"] = pg
    if pg is None:
        out["reason"] = "sin tabla A90/A91 (posible esquema A97.x)"
        return out

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[pg]
        rows = _extract_words_by_row(page)
        state_rows: list[tuple[str, list[Word]]] = []
        total_row: list[Word] | None = None
        for ws in rows.values():
            ws = sorted(ws, key=lambda x: x["x0"])
            canon = _is_state_row(ws)
            if canon:
                state_rows.append((canon, ws))
            elif ws and ws[0]["text"].upper().startswith("TOTAL"):
                total_row = ws
        if len(state_rows) < 30:
            out["reason"] = f"parse incompleto: {len(state_rows)} entidades"
            return out
        bands = _calibrate_bands([ws for _, ws in state_rows])
        if not bands:
            out["reason"] = "sin columnas numericas detectables"
            return out
        sex_idx = _sex_bands(page, bands)
        if not sex_idx:
            out["reason"] = "no se hallaron columnas de sexo (M/F)"
            return out
        # Las bandas de sexo deben venir en pares (M,F) por severidad: 2 bloques (variante A,
        # 2014-2015) o 3 (variante B, 2016-2018H1). Un número impar o inesperado significa que
        # _sex_bands detectó una M/F espuria o perdió una, lo que desfasaría el emparejamiento
        # por paridad ([0::2]/[1::2]) y CRUZARÍA hombres/mujeres en silencio (la validación
        # contra TOTAL no lo cacha porque reusa el mismo mapeo). Mejor rechazar el boletín.
        if len(sex_idx) not in (4, 6):
            out["reason"] = f"bandas de sexo inesperadas: {len(sex_idx)} (esperado 4 o 6)"
            return out

        import pandas as pd

        m_idx = sorted(sex_idx)[0::2]  # M (hombres) = 1ª de cada par confirmado
        f_idx = sorted(sex_idx)[1::2]  # F (mujeres) = 2ª de cada par
        records = []
        for canon, ws in state_rows:
            cells = _cells(ws, bands)
            hombres = sum(_to_int(cells[i]) for i in m_idx if i < len(cells))
            mujeres = sum(_to_int(cells[i]) for i in f_idx if i < len(cells))
            records.append(
                {
                    "Anio": year,
                    "Semana": f"{week:02d}",
                    "Entidad": canon,
                    "Padecimiento": "Dengue_A90A91",
                    "Acumulado_hombres": hombres,
                    "Acumulado_mujeres": mujeres,
                }
            )
        df = pd.DataFrame(records).drop_duplicates("Entidad").reset_index(drop=True)
        out["df"] = df
        out["n_states"] = len(df)

        # Validación: suma H+M de entidades vs columnas de sexo del renglón TOTAL.
        if total_row is not None:
            tcells = _cells(total_row, bands)
            tot_h = sum(_to_int(tcells[i]) for i in m_idx if i < len(tcells))
            tot_m = sum(_to_int(tcells[i]) for i in f_idx if i < len(tcells))
            absdiff = abs(int(df["Acumulado_hombres"].sum()) - tot_h) + abs(
                int(df["Acumulado_mujeres"].sum()) - tot_m
            )
            out["absdiff"] = absdiff
            out["valid"] = absdiff <= TOTAL_ABS_TOLERANCE_A9091
            if not out["valid"]:
                out["reason"] = f"suma no cuadra con TOTAL (absdiff={absdiff})"
        else:
            out["reason"] = "no se hallo renglon TOTAL para validar"
    return out
