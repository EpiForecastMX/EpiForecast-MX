"""Tests del parser histórico A90/A91 (OMS 1997, 2014→2018-W26) por posición."""

from __future__ import annotations

from epiforecast.data.extraction.dengue_historico_a9091 import (
    _band_of,
    _cells,
    _column_bands,
    _is_state_row,
    _to_int,
    _year_week_from_filename,
)


def _w(text: str, x0: float, x1: float) -> dict:
    return {"text": text, "x0": x0, "x1": x1, "top": 100.0, "bottom": 110.0}


def test_to_int_normaliza_miles_y_guiones() -> None:
    assert _to_int("3 473") == 3473  # separador de miles por espacio (ya concatenado)
    assert _to_int("3473") == 3473
    assert _to_int("-") == 0
    assert _to_int("") == 0
    assert _to_int("1,234") == 1234


def test_year_week_from_filename() -> None:
    assert _year_week_from_filename("data/raw_PDFs/2015_sem40.pdf") == (2015, 40)
    assert _year_week_from_filename("/x/2018_sem02.pdf") == (2018, 2)
    assert _year_week_from_filename("sin_patron.pdf") == (None, None)


def test_is_state_row_prefijo_mas_largo() -> None:
    """'Baja California Sur' no debe colapsar en 'Baja California'."""
    bcs = [_w("Baja", 50, 70), _w("California", 72, 110), _w("Sur", 112, 130)]
    assert _is_state_row(bcs) == "Baja California Sur"
    bc = [_w("Baja", 50, 70), _w("California", 72, 110), _w("5", 200, 205)]
    assert _is_state_row(bc) == "Baja California"
    assert _is_state_row([_w("FUENTE:", 50, 90)]) is None
    assert _is_state_row([]) is None


def test_column_bands_separa_por_hueco() -> None:
    # Dos columnas: centros ~100 (con miles cercanos) y ~140.
    bands = _column_bands([100.0, 104.0, 140.0, 142.0])
    assert len(bands) == 2
    assert bands[0][0] == 100.0 and bands[1][1] == 142.0


def test_cells_asigna_por_banda_y_concatena_miles() -> None:
    bands = [(95.0, 108.0), (135.0, 145.0)]
    # "1" y "326" caen en la banda 0 (miles) -> "1326"; "-" en banda 1.
    row = [_w("1", 96, 100), _w("326", 101, 108), _w("-", 138, 142)]
    cells = _cells(row, bands)
    assert _to_int(cells[0]) == 1326
    assert _to_int(cells[1]) == 0


def test_band_of_mas_cercana_fuera_de_rango() -> None:
    bands = [(100.0, 110.0), (200.0, 210.0)]
    assert _band_of(105.0, bands) == 0
    assert _band_of(205.0, bands) == 1
    assert _band_of(500.0, bands) == 1  # fuera de rango -> la más cercana
