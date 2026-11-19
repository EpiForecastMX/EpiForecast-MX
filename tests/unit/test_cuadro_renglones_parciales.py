"""Entidad partida en dos renglones con valores complementarios (Cuadro 18.1, 2019-2024).

En las mordeduras por perro y por otros mamíferos camelot deja, para algunas entidades, el nombre
con los valores de un bloque y debajo, sin nombre, los de otro bloque. Sin reparar, ``reshape`` lee
el bloque vacío como ceros con estado ``ok``. La reparación es opt-in por grupo
(``une_renglones_parciales: true``); sin la clave, la salida no cambia.
"""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.data.extraction import cuadro_extractor as ce
from epiforecast.data.extraction.cuadro_reparaciones import (
    alinea_renglones,
    opciones_tabla,
    une_renglones_parciales,
)

pytestmark = pytest.mark.unit

ESTADOS = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Coahuila", "Colima",
    "Chiapas", "Chihuahua", "Ciudad de México", "Durango", "Guanajuato", "Guerrero", "Hidalgo",
    "Jalisco", "México", "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla",
    "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas",
    "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas",
]  # fmt: skip
PARTIDAS = {"Ciudad de México", "México", "Nuevo León"}
DISEASE = "mordedura_perro_w54"


def _cruda() -> pd.DataFrame:
    """Dos bloques de 4 columnas; tres entidades partidas: nombre con el 2.º bloque, debajo el 1.º."""
    filas = [["ENTIDAD", "Sem.", "H", "M", "Ant.", "Sem.", "H", "M", "Ant."]]
    for i, estado in enumerate(ESTADOS):
        propio = [str(100 + i), str(1000 + i), str(2000 + i), str(3000 + i)]
        vecino = [str(5 + i), str(50 + i), str(60 + i), str(110 + i)]
        if estado in PARTIDAS:
            filas.append([estado, "", "", "", "", *vecino])
            filas.append(["", *propio, "", "", "", ""])
        else:
            filas.append([estado, *propio, *vecino])
    return pd.DataFrame(filas)


def _spec(opt_in: bool) -> dict:
    spec = {
        "page_anchors": ["w54"],
        "state_markers": ["zacatecas"],
        "first_block_columns": {8: 4},
        "diseases": [{"id": DISEASE, "keyword": "Mordedura_Perro_W54", "block_index": 0}],
        "n_states_expected": 32,
    }
    if opt_in:
        spec["une_renglones_parciales"] = True
    return spec


def _extrae(monkeypatch, tmp_path, opt_in: bool) -> dict:
    pdf = tmp_path / "2020_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(ce, "load_group", lambda _g: _spec(opt_in))
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 62)
    monkeypatch.setattr(
        ce.camelot, "read_pdf", lambda *_a, **_k: [type("T", (), {"df": _cruda()})()]
    )
    return ce.extract_cuadro_from_pdf(str(pdf), "grupo_sintetico", DISEASE)


def test_con_la_clave_las_entidades_partidas_conservan_sus_valores(monkeypatch, tmp_path):
    salida = _extrae(monkeypatch, tmp_path, opt_in=True)
    assert salida["valid"], salida["reason"]
    df = salida["df"].set_index("Entidad")
    assert len(df) == 32
    for i, estado in enumerate(ESTADOS):
        assert df.loc[estado, "Casos_semana"] == 100 + i
        assert df.loc[estado, "Acumulado_hombres"] == 1000 + i
        assert df.loc[estado, "Acumulado_anio_anterior"] == 3000 + i


def test_sin_la_clave_la_salida_no_cambia(monkeypatch, tmp_path):
    """Comportamiento previo intacto: las partidas siguen saliendo vacías (sin la clave)."""
    salida = _extrae(monkeypatch, tmp_path, opt_in=False)
    df = salida["df"].set_index("Entidad")
    for estado in PARTIDAS:
        assert not (df.loc[estado, "Casos_semana"] or 0)
    assert df.loc["Aguascalientes", "Casos_semana"] == 100


def test_une_renglon_con_nombre_y_el_siguiente_sin_nombre():
    df = pd.DataFrame([["Nuevo León", "", "", "7", "8"], ["", "1", "2", "", ""]])
    out = une_renglones_parciales(df)
    assert out.iloc[0].tolist() == ["Nuevo León", "1", "2", "7", "8"]
    assert out.iloc[1].tolist() == ["", "", "", "", ""]
    assert alinea_renglones(df, parciales=True).equals(out)


def test_no_une_si_los_valores_se_solapan_ni_si_el_siguiente_tiene_nombre():
    solapados = pd.DataFrame([["Nuevo León", "5", "", "7"], ["", "1", "2", ""]])
    assert une_renglones_parciales(solapados).equals(solapados.astype(str))
    con_nombre = pd.DataFrame([["Nuevo León", "", "", "7"], ["Oaxaca", "1", "2", ""]])
    assert une_renglones_parciales(con_nombre).equals(con_nombre.astype(str))
    alineada = pd.DataFrame([["ENTIDAD", "Sem.", "Acum."], ["Aguascalientes", "194", "766"]])
    assert une_renglones_parciales(alineada).equals(alineada)


def test_alinea_renglones_por_omision_no_une_parciales():
    df = pd.DataFrame([["Nuevo León", "", "", "7", "8"], ["", "1", "2", "", ""]])
    assert alinea_renglones(df).equals(df)


def test_opciones_tabla_es_opt_in():
    assert opciones_tabla({}) == {"valor_en_nombre": False, "parciales": False}
    assert opciones_tabla({"une_renglones_parciales": True})["parciales"] is True
