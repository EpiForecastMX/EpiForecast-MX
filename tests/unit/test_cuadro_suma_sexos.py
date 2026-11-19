"""Bloque que pasa de sin sexo a H/M (paludismo por P. vivax, Cuadro 7.4 desde 2021_sem01).

Hasta 2020 el bloque trae ``Sem.``, acumulado del año y del anterior; desde 2021 ``Sem.``,
acumulados de hombres y de mujeres y año anterior. Con ``suma_sexos: true`` (opt-in por periodo)
el bloque H/M se lee como sin sexo, con acumulado total = H + M, validado contra el TOTAL impreso.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from epiforecast.data.extraction import cuadro_extractor as ce
from epiforecast.data.extraction.cuadro_suma_sexos import (
    columnas_del_bloque,
    convierte_suma_sexos,
    suma_sexos,
)

pytestmark = pytest.mark.unit

SIN_SEXO = "cancer_cuello_utero_c53"  # registry con sex_breakdown: false
CON_SEXO = "obesidad"
ESTADOS = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Coahuila", "Colima",
    "Chiapas", "Chihuahua", "Ciudad de México", "Durango", "Guanajuato", "Guerrero", "Hidalgo",
    "Jalisco", "México", "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla",
    "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas",
    "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas",
]  # fmt: skip


def _spec(disease: str) -> dict[str, Any]:
    return {
        "page_anchors": ["vivax"],
        "state_markers": ["zacatecas"],
        "year_week_source": "filename",
        "last_block_columns": {6: 3, 8: 4},
        "periodos": [{"desde": "2021_sem01", "suma_sexos": True}],
        "diseases": [{"id": disease, "keyword": "Vivax", "block_index": 0, "onboard": True}],
        "n_states_expected": 32,
    }


def _vecino(i: int, ancho: int) -> list[int]:
    """Bloque vecino (falciparum) que no debe leerse."""
    return [(i * 7 + j) % 11 + 900 for j in range(ancho)]


def _propio(i: int, con_sexo: bool) -> list[int]:
    return [i % 4, 10 + i, i % 3, 50 + i] if con_sexo else [i % 4, 10 + i, 50 + i]


def _cruda(con_sexo: bool, total: list[str] | None = None) -> pd.DataFrame:
    ancho = 4 if con_sexo else 3
    filas = [["FEDERATIVA", *[""] * (2 * ancho)]]
    for i, estado in enumerate(ESTADOS):
        valores = [str(v) if v else "-" for v in (*_vecino(i, ancho), *_propio(i, con_sexo))]
        filas.append([estado, *valores])
    sumas = [
        str(sum(fila[j] for fila in (_vecino(i, ancho) + _propio(i, con_sexo) for i in range(32))))
        for j in range(2 * ancho)
    ]
    filas.append(["TOTAL", *(total if total is not None else sumas)])
    return pd.DataFrame(filas)


def _extrae(monkeypatch, tmp_path, cruda, archivo, disease=SIN_SEXO) -> dict:
    pdf = tmp_path / archivo
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(ce, "load_group", lambda _g: _spec(disease))
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 33)
    monkeypatch.setattr(ce.camelot, "read_pdf", lambda *_a, **_k: [type("T", (), {"df": cruda})()])
    return ce.extract_cuadro_from_pdf(str(pdf), "grupo_sintetico", disease)


def test_desde_2021_suma_hombres_y_mujeres_y_cuadra_con_el_total(monkeypatch, tmp_path):
    salida = _extrae(monkeypatch, tmp_path, _cruda(True), "2021_sem01.pdf")
    assert salida["valid"], salida["reason"]
    assert salida["reparacion"] == "suma_sexos"
    assert salida["layout"] == "4col_suma_sexos"
    assert "cuadra con el TOTAL impreso" in salida["reason"]
    df = salida["df"].set_index("Entidad")
    assert len(df) == 32
    assert "Acumulado_hombres" not in df.columns
    for i, estado in enumerate(ESTADOS):
        sem, h, m, anterior = _propio(i, True)
        assert df.loc[estado, "Casos_semana"] == sem
        assert df.loc[estado, "Acumulado_total"] == h + m
        assert df.loc[estado, "Acumulado_anio_anterior"] == anterior


def test_antes_del_periodo_lee_el_bloque_sin_sexo_igual(monkeypatch, tmp_path):
    salida = _extrae(monkeypatch, tmp_path, _cruda(False), "2020_sem53.pdf")
    assert salida["valid"], salida["reason"]
    assert salida["reason"] == "ok"
    assert salida["layout"] == "3col_total"
    assert "reparacion" not in salida
    df = salida["df"].set_index("Entidad")
    assert df.loc["Zacatecas", "Acumulado_total"] == _propio(31, False)[1]


def test_total_que_no_cuadra_falla_cerrado(monkeypatch, tmp_path):
    cruda = _cruda(True)
    cruda.iloc[-1, 7] = str(int(cruda.iloc[-1, 7]) + 1)  # columna M del bloque propio
    salida = _extrae(monkeypatch, tmp_path, cruda, "2026_sem44.pdf")
    assert not salida["valid"]
    assert salida["df"] is None
    assert "no es el TOTAL impreso (columna 3)" in salida["reason"]


def test_total_del_vecino_no_se_confunde_con_el_propio(monkeypatch, tmp_path):
    cruda = _cruda(True)
    cruda.iloc[-1, 1] = "0"  # TOTAL del bloque vecino alterado: no afecta al propio
    salida = _extrae(monkeypatch, tmp_path, cruda, "2026_sem44.pdf")
    assert salida["valid"], salida["reason"]


def test_celda_vacia_falla_cerrado(monkeypatch, tmp_path):
    cruda = _cruda(True)
    cruda.iloc[5, 6] = ""
    salida = _extrae(monkeypatch, tmp_path, cruda, "2026_sem44.pdf")
    assert not salida["valid"]
    assert "celda vacía o no numérica" in salida["reason"]


def test_padecimiento_con_sexo_falla_cerrado(monkeypatch, tmp_path):
    salida = _extrae(monkeypatch, tmp_path, _cruda(True), "2026_sem44.pdf", disease=CON_SEXO)
    assert not salida["valid"]
    assert "sex_breakdown: false" in salida["reason"]


def test_sin_total_impreso_falla_cerrado():
    tabla = pd.DataFrame([["Colima", "1", "2", "3", "4"]])
    convertida, motivo = convierte_suma_sexos(tabla, None)
    assert convertida is None
    assert "TOTAL impreso" in motivo


def test_sin_opt_in_no_toca_la_tabla():
    tabla = pd.DataFrame([["Colima", "1", "2", "3", "4"]])
    out: dict = {}
    salida = suma_sexos(
        tabla, "x.pdf", 1, {"page_anchors": []}, out, disease_id=SIN_SEXO, ancho_tabla=4
    )
    assert salida is tabla
    assert out == {}


def test_columnas_del_bloque_repite_el_recorte():
    assert columnas_del_bloque({"last_block_columns": {8: 4}}, 8) == [4, 5, 6, 7]
    assert columnas_del_bloque({"first_block_columns": {8: 4}}, 8) == [0, 1, 2, 3]
    assert columnas_del_bloque({}, 4) == [0, 1, 2, 3]
    assert columnas_del_bloque({"last_block_columns": {8: 4}}, 9) is None
    assert columnas_del_bloque({"inner_block_columns": {12: [8, 4]}}, 12) is None
