"""Bloque por estadios clínicos (VIH, Cuadro 6.3 desde 2020_sem28): suma de estadios por sexo.

El cuadro imprime ``Sem.``, los acumulados del año en pares H/M por estadio (1 a 4) y el año
anterior (``Sem.`` y ``Acum.`` hasta 2024; sólo ``Acum.`` desde 2025), sin acumulado por sexo. La
conversión es opt-in (``estadios_por_sexo``) y se valida contra el TOTAL impreso.
"""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.data.extraction import cuadro_extractor as ce
from epiforecast.data.extraction.cuadro_estadios import convierte_estadios, suma_estadios

pytestmark = pytest.mark.unit

GRUPO = "b44_vih_b20"
DISEASE = "vih_b20"
ESTADOS = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Coahuila", "Colima",
    "Chiapas", "Chihuahua", "Ciudad de México", "Durango", "Guanajuato", "Guerrero", "Hidalgo",
    "Jalisco", "México", "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla",
    "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas",
    "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas",
]  # fmt: skip


def _fila(i: int) -> list[int]:
    """Sem y 8 acumulados de estadio (H1, M1, ..., H4, M4) distintos por entidad."""
    return [i % 7, 10 + i, i % 3, 20 + 2 * i, i % 5, 1_000 + i, i % 2, 30 + i, i % 4]


def _cruda(anterior_sem: bool, total: list[str] | None = None) -> pd.DataFrame:
    filas = [["FEDERATIVA", *[""] * (11 if anterior_sem else 10)]]
    for i, estado in enumerate(ESTADOS):
        valores = [str(v) if v else "-" for v in _fila(i)]
        valores[5] = f"1 {i:03d}"  # separador de miles impreso con espacio
        cola = [str(i), str(500 + i)] if anterior_sem else [str(500 + i)]
        filas.append([estado, *valores, *cola])
    sumas = [str(sum(_fila(i)[j] for i in range(32))) for j in range(9)]
    impreso = total if total is not None else sumas
    filas.append(
        [
            "TOTAL",
            *impreso,
            *(["n.a.", "n.a."] if anterior_sem else [str(sum(500 + i for i in range(32)))]),
        ]
    )
    return pd.DataFrame(filas)


def _extrae(monkeypatch, tmp_path, cruda: pd.DataFrame, archivo: str) -> dict:
    pdf = tmp_path / archivo
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 27)
    monkeypatch.setattr(ce.camelot, "read_pdf", lambda *_a, **_k: [type("T", (), {"df": cruda})()])
    return ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)


@pytest.mark.parametrize(
    ("archivo", "anterior_sem"), [("2020_sem28.pdf", True), ("2026_sem44.pdf", False)]
)
def test_suma_estadios_por_sexo_y_cuadra_con_el_total(
    monkeypatch, tmp_path, archivo, anterior_sem
):
    salida = _extrae(monkeypatch, tmp_path, _cruda(anterior_sem), archivo)
    assert salida["valid"], salida["reason"]
    assert salida["reparacion"] == "suma_estadios"
    assert "cuadra con el TOTAL impreso" in salida["reason"]
    df = salida["df"].set_index("Entidad")
    assert len(df) == 32
    for i, estado in enumerate(ESTADOS):
        v = _fila(i)
        assert df.loc[estado, "Casos_semana"] == v[0]
        assert df.loc[estado, "Acumulado_hombres"] == v[1] + v[3] + 1_000 + i + v[7]
        assert df.loc[estado, "Acumulado_mujeres"] == v[2] + v[4] + v[6] + v[8]
        # El año anterior es siempre el último acumulado, nunca su columna Sem.
        assert df.loc[estado, "Acumulado_anio_anterior"] == 500 + i


def test_total_que_no_cuadra_falla_cerrado(monkeypatch, tmp_path):
    sumas = [str(sum(_fila(i)[j] for i in range(32))) for j in range(9)]
    sumas[4] = str(int(sumas[4]) + 1)
    salida = _extrae(monkeypatch, tmp_path, _cruda(False, total=sumas), "2026_sem44.pdf")
    assert not salida["valid"]
    assert salida["df"] is None
    assert "no es el TOTAL impreso (columna 5)" in salida["reason"]


def test_celda_no_numerica_falla_cerrado(monkeypatch, tmp_path):
    cruda = _cruda(False)
    cruda.iloc[3, 6] = "n.e."
    salida = _extrae(monkeypatch, tmp_path, cruda, "2026_sem44.pdf")
    assert not salida["valid"]
    assert "celda no numérica" in salida["reason"]


def test_ancho_no_declarado_falla_cerrado(monkeypatch, tmp_path):
    cruda = _cruda(False).iloc[:, :-1]  # 9 columnas: sin año anterior
    salida = _extrae(monkeypatch, tmp_path, cruda, "2026_sem44.pdf")
    assert not salida["valid"]
    assert "estadios: columnas inesperadas 9" in salida["reason"]


def test_sin_total_impreso_falla_cerrado():
    tabla = pd.DataFrame([["Colima", "1", "2", "-", "-", "-", "-", "-", "-", "-", "5"]])
    convertida, motivo = convierte_estadios(tabla, None, 4, [10])
    assert convertida is None
    assert "TOTAL impreso" in motivo


def test_sin_opt_in_no_toca_la_tabla():
    tabla = pd.DataFrame([["Colima", "1", "2", "3", "4"]])
    out: dict = {}
    assert suma_estadios(tabla, "x.pdf", 1, {"page_anchors": []}, out) is tabla
    assert out == {}


def test_celdas_vacias_no_cuentan_como_cero(monkeypatch, tmp_path):
    """Filas estatales vacías con TOTAL vacío (2025_sem14 con row_tol=2) no dan una semana de ceros."""
    cruda = _cruda(False)
    cruda.iloc[1:, 1:] = ""
    salida = _extrae(monkeypatch, tmp_path, cruda, "2026_sem44.pdf")
    assert not salida["valid"]
    assert salida["df"] is None


def test_total_se_lee_con_el_row_tol_del_reintento(monkeypatch, tmp_path):
    """Con row_tol=2 los valores salen sin nombre; el reintento con row_tol=4 y su TOTAL cuadran."""
    buena = _cruda(False)
    partida = buena.copy()
    partida.iloc[1:, 1:] = ""
    pdf = tmp_path / "2025_sem14.pdf"
    pdf.write_bytes(b"%PDF")
    llamadas: list[dict] = []

    def lee(*_a, **kw):
        llamadas.append(kw)
        return [type("T", (), {"df": buena if kw.get("row_tol") == 4 else partida})()]

    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 33)
    monkeypatch.setattr(ce, "_area_pagina", lambda *_a: None)
    monkeypatch.setattr(ce.camelot, "read_pdf", lee)
    salida = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert salida["valid"], salida["reason"]
    assert salida["reparacion"] == "row_tol=4+suma_estadios"
    assert llamadas[-1].get("row_tol") == 4  # el TOTAL de la conversión usa la misma lectura


def test_celda_de_estadio_vacia_falla_aunque_el_total_cuadre_como_cero():
    tabla = pd.DataFrame([["Colima", "1", "2", "", "-", "-", "-", "-", "-", "-", "5"]])
    total = ["1", "2", "", "-", "-", "-", "-", "-", "-", "5"]
    convertida, motivo = convierte_estadios(tabla, total, 4, [10])
    assert convertida is None
    assert "celda" in motivo
