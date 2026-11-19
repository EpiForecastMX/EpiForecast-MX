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
    AMBIGUO,
    alinea_renglones,
    motivo_ambiguo,
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


def _cruda(
    solapa: str | None = None, ajena: str | None = None, partidas: set[str] = PARTIDAS
) -> pd.DataFrame:
    """Dos bloques de 4 columnas; tres entidades partidas: nombre con el 2.º bloque, debajo el 1.º.

    ``solapa`` añade al renglón complementario de esa entidad una celda que se solapa con su
    renglón con nombre (el caso ambiguo reproducido por la auditoría). ``ajena`` deja a esa entidad
    con su bloque completo y la ambigüedad sólo en el bloque vecino (2019_sem35 y 2019_sem39).
    ``partidas`` elige qué entidades salen partidas (la re-auditoría las parte todas).
    """
    filas = [["ENTIDAD", "Sem.", "H", "M", "Ant.", "Sem.", "H", "M", "Ant."]]
    for i, estado in enumerate(ESTADOS):
        propio = [str(100 + i), str(1000 + i), str(2000 + i), str(3000 + i)]
        vecino = [str(5 + i), str(50 + i), str(60 + i), str(110 + i)]
        if estado in partidas:
            filas.append([estado, "", "", "", "", *vecino])
            filas.append(["", *propio, "9" if estado == solapa else "", "", "", ""])
        elif estado == ajena:
            filas.append([estado, *propio, *vecino[:3], ""])
            filas.append(["", "", "", "", "", "", "", "3", "4"])
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


def _extrae(
    monkeypatch,
    tmp_path,
    opt_in: bool,
    solapa: str | None = None,
    ajena: str | None = None,
    partidas: set[str] = PARTIDAS,
) -> dict:
    pdf = tmp_path / "2020_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(ce, "load_group", lambda _g: _spec(opt_in))
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 62)
    monkeypatch.setattr(
        ce.camelot,
        "read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": _cruda(solapa, ajena, partidas)})()],
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


def test_ambiguedad_en_el_bloque_propio_invalida_la_tabla(monkeypatch, tmp_path):
    """Una celda solapada en el renglón complementario no puede dejar ceros con ``ok``."""
    salida = _extrae(monkeypatch, tmp_path, opt_in=True, solapa="Ciudad de México")
    assert salida["valid"] is False and salida["df"] is None
    assert "renglones partidos ambiguos" in salida["reason"]
    assert "Ciudad de México" in salida["reason"]


def test_todas_partidas_y_solapamiento_solo_en_cdmx_invalida_la_tabla(monkeypatch, tmp_path):
    """Variante de la re-auditoría: las 32 entidades partidas y una sola celda solapada en CDMX.

    Ninguna entidad con nombre usa las columnas del bloque propio (sólo aparecen en los renglones
    complementarios), así que el código anterior no marcaba nada y CDMX salía con
    108/1008/2008/3008 convertidos en ceros con ``valid=True``.
    """
    todas = set(ESTADOS)
    unida = _extrae(monkeypatch, tmp_path, opt_in=True, partidas=todas)
    assert unida["valid"], unida["reason"]
    assert unida["df"].set_index("Entidad").loc["Ciudad de México", "Casos_semana"] == 108
    salida = _extrae(monkeypatch, tmp_path, opt_in=True, solapa="Ciudad de México", partidas=todas)
    assert salida["valid"] is False and salida["df"] is None
    assert "renglones partidos ambiguos" in salida["reason"]
    assert "Ciudad de México" in salida["reason"]


def test_solapamiento_que_pierde_un_valor_del_bloque_propio_se_marca():
    """El valor del renglón complementario que no se une se pierde: su columna queda marcada."""
    df = pd.DataFrame([["Nuevo León", "", "", "7", "8"], ["", "1", "2", "3", ""]])
    out = une_renglones_parciales(df)
    assert out.iloc[0].tolist() == ["Nuevo León", AMBIGUO, AMBIGUO, AMBIGUO, "8"]
    assert motivo_ambiguo(out.iloc[:, [0, 4]]) is None  # sólo pierde valores fuera del bloque
    assert "Nuevo León" in (motivo_ambiguo(out.iloc[:, [0, 3]]) or "")


def test_ambiguedad_solo_en_otro_bloque_no_invalida(monkeypatch, tmp_path):
    salida = _extrae(monkeypatch, tmp_path, opt_in=True, ajena="Aguascalientes")
    assert salida["valid"], salida["reason"]
    df = salida["df"].set_index("Entidad")
    assert df.loc["Aguascalientes", "Casos_semana"] == 100
    assert df.loc["Aguascalientes", "Acumulado_anio_anterior"] == 3000


def test_parcial_con_valores_solapados_se_marca_y_no_se_une():
    solapados = pd.DataFrame(
        [["Oaxaca", "4", "4", "4"], ["Nuevo León", "5", "", "7"], ["", "1", "2", ""]]
    )
    out = une_renglones_parciales(solapados).iloc[1:]
    # «5» frente a «1» es ambiguo y «2» se perdería: ambas columnas quedan marcadas.
    assert out.iloc[0].tolist() == ["Nuevo León", AMBIGUO, AMBIGUO, "7"]
    assert out.iloc[1].tolist() == ["", "1", "2", ""]
    assert "Nuevo León" in (motivo_ambiguo(out) or "")
    assert motivo_ambiguo(out.iloc[:, [0, 3]]) is None  # la marca quedó fuera del bloque


def test_encabezado_y_total_partidos_no_son_entidades_y_pasan_igual():
    """Falsos positivos medidos en 2018-2019 («FEDERATIVA») y 2024 («TOTAL»): no son entidades."""
    for nombre in ("FEDERATIVA", "TOTAL"):
        df = pd.DataFrame(
            [["Aguascalientes", "1", "2", "3"], [nombre, "Sem.", "", "Acum."], ["", "H", "M", "A"]]
        )
        assert une_renglones_parciales(df).equals(df.astype(str))


def test_entidad_con_llamada_de_nota_tambien_se_marca():
    solapados = pd.DataFrame(
        [["Oaxaca", "4", "4", "4"], ["Michoacán *", "5", "", "7"], ["", "1", "2", ""]]
    )
    assert une_renglones_parciales(solapados).iloc[1, 2] == AMBIGUO


def test_no_une_si_el_renglon_esta_completo_ni_si_el_siguiente_tiene_nombre():
    completo = pd.DataFrame([["Nuevo León", "5", "6", "7"], ["", "1", "2", ""]])
    out = une_renglones_parciales(completo)
    assert out.iloc[1].tolist() == ["", "1", "2", ""]  # no se une
    # «1» y «2» se perderían frente a «5» y «6»: el renglón completo también queda marcado.
    assert out.iloc[0].tolist() == ["Nuevo León", AMBIGUO, AMBIGUO, "7"]
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
