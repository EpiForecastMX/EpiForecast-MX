"""Reparto en orden de lectura del primer bloque (meningitis, 2014_sem02-03, Cuadro 12).

En esos boletines el PDF imprime cada guion corrido unos 40 pt a la izquierda, junto al valor de
la columna anterior: camelot pega «- -» o «1 -» y el bloque de 4 valores ocupa 5 columnas. La
reparación es opt-in (``primer_bloque_por_orden``) y se valida contra el TOTAL impreso.
"""

from __future__ import annotations

from omegaconf import OmegaConf
import pandas as pd
import pytest

from epiforecast.data.extraction import cuadro_extractor as ce
from epiforecast.data.extraction.cuadro_reparaciones import (
    _tokens_en_orden,
    primer_bloque_por_orden,
)

pytestmark = pytest.mark.unit

GRUPO = "alta20c_sindrome_meningeo_g00"
DISEASE = "sindrome_meningeo_g00"
ESTADOS = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Coahuila", "Colima",
    "Chiapas", "Chihuahua", "Distrito Federal", "Durango", "Guanajuato", "Guerrero", "Hidalgo",
    "Jalisco", "México", "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla",
    "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas",
    "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas",
]  # fmt: skip
# Celdas del bloque de meningitis tal como las deja camelot en 2014_sem02 (5 columnas) y los
# valores que imprime el PDF (Sem, Acum H, Acum M, año anterior).
PATRONES = [
    (["-", "-", "-", "", "-"], [0, 0, 0, 0]),  # Aguascalientes: sin guiones corridos
    (["3", "2", "1", "", "3"], [3, 2, 1, 3]),  # Baja California
    (["- -", "-", "", "", "1"], [0, 0, 0, 1]),  # Baja California Sur
    (["- -", "-", "", "-", ""], [0, 0, 0, 0]),  # Campeche
    (["1 -", "", "1 -", "", ""], [1, 0, 1, 0]),  # Distrito Federal
    (["1", "1 -", "", "", "3"], [1, 1, 0, 3]),  # Guanajuato
]


def _cruda(total: list[str] | None = None) -> tuple[pd.DataFrame, list[list[int]]]:
    """Tabla cruda de camelot: 1 + 5 columnas del bloque + 4 de vías urinarias, con TOTAL."""
    filas = [["FEDERATIVA", *[""] * 9], ["", "Sem.", "", "", "", "Acum.", "Sem.", "", "", ""]]
    esperados = []
    for i, estado in enumerate(ESTADOS):
        celdas, valores = PATRONES[i % len(PATRONES)]
        filas.append([estado, *celdas, str(900 + i), "200", "700", f"1 {i:03d}"])
        esperados.append(valores)
    sumas = [str(sum(v[j] for v in esperados)) for j in range(4)]
    impreso = total if total is not None else [sumas[0], sumas[1], sumas[2], "", sumas[3]]
    filas.append(["TOTAL", *impreso, "47 008", "12 625", "34 383", "47 067"])
    return pd.DataFrame(filas), esperados


def _extrae(monkeypatch, tmp_path, cruda: pd.DataFrame, archivo: str, grupo: str = GRUPO,
            disease: str = DISEASE) -> tuple[dict, list]:  # fmt: skip
    pdf = tmp_path / archivo
    pdf.write_bytes(b"%PDF")
    llamadas: list[dict] = []

    def lee(*_a, **kw):
        llamadas.append(kw)
        return [type("T", (), {"df": cruda})()]

    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 39)
    monkeypatch.setattr(ce.camelot, "read_pdf", lee)
    return ce.extract_cuadro_from_pdf(str(pdf), grupo, disease), llamadas


@pytest.mark.parametrize("archivo", ["2014_sem02.pdf", "2014_sem03.pdf"])
def test_reparte_en_orden_y_cuadra_con_el_total(monkeypatch, tmp_path, archivo):
    cruda, esperados = _cruda()
    salida, _ = _extrae(monkeypatch, tmp_path, cruda, archivo)
    assert salida["valid"], salida["reason"]
    assert salida["layout"] == "4col_prev"
    assert salida["reparacion"] == "primer_bloque_por_orden"
    assert "cuadra con el TOTAL impreso" in salida["reason"]
    df = salida["df"].set_index("Entidad")
    cols = ["Casos_semana", "Acumulado_hombres", "Acumulado_mujeres", "Acumulado_anio_anterior"]
    assert len(df) == 32
    assert df[cols].isna().sum().sum() == 0
    canon = {"Distrito Federal": "Ciudad de México"}
    for estado, valores in zip(ESTADOS, esperados, strict=True):
        assert df.loc[canon.get(estado, estado), cols].tolist() == valores
    # Nunca se toma un valor del bloque vecino (vías urinarias empieza en 900).
    assert df["Casos_semana"].max() < 900


def test_total_que_no_cuadra_falla_cerrado(monkeypatch, tmp_path):
    cruda, _ = _cruda(total=["99", "3", "5", "", "15"])
    salida, _ = _extrae(monkeypatch, tmp_path, cruda, "2014_sem02.pdf")
    assert not salida["valid"]
    assert salida["df"] is None
    assert "distinta del TOTAL impreso" in salida["reason"]


def test_renglon_con_un_valor_de_menos_falla_cerrado(monkeypatch, tmp_path):
    cruda, _ = _cruda()
    cruda.iloc[5, 1:6] = ["- -", "", "", "", ""]  # Campeche con 2 valores en vez de 4
    salida, _ = _extrae(monkeypatch, tmp_path, cruda, "2014_sem02.pdf")
    assert not salida["valid"]
    assert "Campeche no trae 4 valores" in salida["reason"]


def test_sin_total_impreso_falla_cerrado():
    tabla = pd.DataFrame([["Colima", "- -", "-", "", "2", "", "9", "9", "9", "9"]])
    reparada, motivo = primer_bloque_por_orden(tabla, None, 5, 4)
    assert reparada is None
    assert "TOTAL impreso" in motivo


@pytest.mark.parametrize(
    ("celdas", "esperado"),
    [
        (["- -", "-", "", "1", ""], ["-", "-", "-", "1"]),
        (["1 070", "2", "", "", ""], None),  # separador de miles: nunca se parte
        (["- -", "-", "", "", ""], None),  # faltan valores
        (["- -", "-", "-", "1", ""], None),  # sobran valores
        (["- -", "n.e.", "", "1", ""], None),  # texto no numérico
    ],
)
def test_tokens_en_orden(celdas, esperado):
    assert _tokens_en_orden(celdas, 4) == esperado


def test_fuera_del_periodo_no_repara(monkeypatch, tmp_path):
    # Desde 2014_sem04 el bloque vuelve a 4 columnas: 9 columnas fallan cerradas como antes.
    cruda, _ = _cruda()
    salida, llamadas = _extrae(monkeypatch, tmp_path, cruda, "2014_sem04.pdf")
    assert not salida["valid"]
    assert salida["reason"] == "columnas inesperadas: 9 (esperaba [8])"
    assert "reparacion" not in salida
    assert len(llamadas) == 1


def test_grupo_sin_opt_in_no_cambia(monkeypatch, tmp_path):
    # Vías urinarias comparte la página: con la misma tabla toma su último bloque, sin reparto
    # ni segunda lectura de camelot.
    cruda, _ = _cruda()
    salida, llamadas = _extrae(
        monkeypatch, tmp_path, cruda, "2014_sem02.pdf", "vigilancia_sindromatica_ivu", "ivu_n39"
    )
    assert salida["valid"]
    assert "reparacion" not in salida
    assert salida["reason"] == "ok"
    assert salida["df"].set_index("Entidad").loc["Aguascalientes", "Casos_semana"] == 900
    assert len(llamadas) == 1


def test_solo_sindrome_meningeo_declara_el_reparto_y_conserva_2016_sem20():
    grupos = OmegaConf.to_container(OmegaConf.load(ce._cuadros_path()))["cuadro_groups"]
    declaran = sorted(g for g, s in grupos.items() if "primer_bloque_por_orden" in str(s))
    assert declaran == [GRUPO]
    excluidos = {e["file"]: e for e in grupos[GRUPO]["source_exclusions"]}
    assert sorted(excluidos) == ["2014_sem01.pdf", "2016_sem20.pdf"]
    assert excluidos["2016_sem20.pdf"]["keep_period"] is True
    assert ce.spec_del_periodo(ce.load_group(GRUPO), 2014, 3)["primer_bloque_por_orden"]
    assert "primer_bloque_por_orden" not in ce.spec_del_periodo(ce.load_group(GRUPO), 2014, 4)
