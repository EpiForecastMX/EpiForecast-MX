"""Covid-19 es el último bloque de un cuadro cuyo ancho cambia entre años."""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast import registry
from epiforecast.data.extraction import cuadro_extractor as ce
from epiforecast.runner.policy import load_policy


def _tabla(n_cols: int) -> pd.DataFrame:
    filas = [[f"Estado {i}", *[str(i * 10 + c) for c in range(n_cols)]] for i in range(1, 33)]
    return pd.DataFrame(filas)


@pytest.mark.unit
@pytest.mark.parametrize(("total", "layout"), [(11, "3col_noprev"), (12, "4col_prev")])
def test_toma_solo_el_ultimo_bloque(monkeypatch, tmp_path, total, layout):
    pdf = tmp_path / "2021_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    tabla = _tabla(total)
    tablas = [type("T", (), {"df": tabla})()]
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 7)
    monkeypatch.setattr(ce.camelot, "read_pdf", lambda *_a, **_k: tablas)
    monkeypatch.setattr(ce, "clean_df", lambda df: df)
    monkeypatch.setattr(ce, "_restrict_to_states", lambda df: df)
    salida = ce.extract_cuadro_from_pdf(str(pdf), "enfermedades_respiratorias", "covid_19")
    assert salida["layout"] == layout
    assert salida["valid"]
    primera = 10 + (total - (3 if total == 11 else 4))
    assert salida["df"]["Casos_semana"].iloc[0] == primera


@pytest.mark.unit
def test_ancho_desconocido_falla_cerrado(monkeypatch, tmp_path):
    pdf = tmp_path / "2021_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    tablas = [type("T", (), {"df": _tabla(9)})()]
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 7)
    monkeypatch.setattr(ce.camelot, "read_pdf", lambda *_a, **_k: tablas)
    monkeypatch.setattr(ce, "clean_df", lambda df: df)
    monkeypatch.setattr(ce, "_restrict_to_states", lambda df: df)
    salida = ce.extract_cuadro_from_pdf(str(pdf), "enfermedades_respiratorias", "covid_19")
    assert not salida["valid"]
    assert "columnas inesperadas" in salida["reason"]


@pytest.mark.unit
def test_politica_de_historia_corta_conserva_la_aceptacion():
    corta = load_policy("rolling_cv_historia_corta_v1")
    base = load_policy("rolling_cv_baja_incidencia_v1")
    assert corta.min_train_weeks == 104
    assert [f.fold_id for f in corta.development_folds()] == [
        "development_2023",
        "development_2024",
    ]
    assert corta.seed == base.seed
    assert corta.candidate_engines == base.candidate_engines


@pytest.mark.unit
@pytest.mark.parametrize("disease", ["covid_19"])
def test_rechazados_en_2025_siguen_invisibles(disease):
    spec = registry.require(disease)
    assert spec.lifecycle == "trained"
    assert list(spec.channels) == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("grupo", "disease", "total", "al_final"),
    [
        ("infecciosas_respiratorias_agudas", "ira_j00", 8, False),
        ("infecciosas_respiratorias_agudas", "ira_j00", 11, False),
        ("infecciosas_respiratorias_agudas", "ira_j00", 12, False),
        ("no_transmisibles_ulceras", "ulceras_k25", 12, False),
        ("infecciosas_digestivas_intestinales", "intestinales_a04", 11, True),
        ("vigilancia_sindromatica_ivu", "ivu_n39", 9, True),
        ("no_transmisibles_gingivitis", "gingivitis_k05", 12, True),
    ],
)
def test_toma_el_primer_o_ultimo_bloque_de_cuatro(
    monkeypatch, tmp_path, grupo, disease, total, al_final
):
    pdf = tmp_path / "2021_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    tablas = [type("T", (), {"df": _tabla(total)})()]
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 7)
    monkeypatch.setattr(ce.camelot, "read_pdf", lambda *_a, **_k: tablas)
    monkeypatch.setattr(ce, "clean_df", lambda df: df)
    monkeypatch.setattr(ce, "_restrict_to_states", lambda df: df)
    salida = ce.extract_cuadro_from_pdf(str(pdf), grupo, disease)
    assert salida["valid"]
    assert salida["layout"] == "4col_prev"
    primera = 10 + (total - 4 if al_final else 0)
    assert salida["df"]["Casos_semana"].iloc[0] == primera


@pytest.mark.unit
def test_primer_bloque_con_ancho_desconocido_falla_cerrado(monkeypatch, tmp_path):
    pdf = tmp_path / "2021_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    tablas = [type("T", (), {"df": _tabla(10)})()]
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 7)
    monkeypatch.setattr(ce.camelot, "read_pdf", lambda *_a, **_k: tablas)
    monkeypatch.setattr(ce, "clean_df", lambda df: df)
    monkeypatch.setattr(ce, "_restrict_to_states", lambda df: df)
    salida = ce.extract_cuadro_from_pdf(str(pdf), "no_transmisibles_ulceras", "ulceras_k25")
    assert not salida["valid"]
    assert "columnas inesperadas" in salida["reason"]


@pytest.mark.unit
def test_entidad_con_llamada_de_nota_se_reconoce():
    tabla = pd.DataFrame([["Michoacán *", "1"], ["Sonora§", "2"], ["Jalisco", "3"]])
    limpia = ce._restrict_to_states(ce.sin_llamadas(tabla))
    assert limpia[0].tolist() == ["Michoacán", "Sonora", "Jalisco"]


@pytest.mark.unit
@pytest.mark.parametrize("total", [11, 12])
def test_toma_el_bloque_intermedio_de_asma(monkeypatch, tmp_path, total):
    pdf = tmp_path / "2021_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    tablas = [type("T", (), {"df": _tabla(total)})()]
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 7)
    monkeypatch.setattr(ce.camelot, "read_pdf", lambda *_a, **_k: tablas)
    monkeypatch.setattr(ce, "clean_df", lambda df: df)
    monkeypatch.setattr(ce, "_restrict_to_states", lambda df: df)
    salida = ce.extract_cuadro_from_pdf(str(pdf), "no_transmisibles_asma", "asma_j45")
    assert salida["valid"]
    assert salida["layout"] == "4col_prev"
    # Las cuatro columnas previas al último bloque de cuatro: nunca las de gingivitis.
    assert salida["df"]["Casos_semana"].iloc[0] == 10 + (total - 8)
    assert salida["df"]["Acumulado_anio_anterior"].iloc[0] == 10 + (total - 5)


@pytest.mark.unit
def test_bloque_intermedio_con_ancho_desconocido_falla_cerrado(monkeypatch, tmp_path):
    pdf = tmp_path / "2021_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    tablas = [type("T", (), {"df": _tabla(8)})()]
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 7)
    monkeypatch.setattr(ce.camelot, "read_pdf", lambda *_a, **_k: tablas)
    monkeypatch.setattr(ce, "clean_df", lambda df: df)
    monkeypatch.setattr(ce, "_restrict_to_states", lambda df: df)
    salida = ce.extract_cuadro_from_pdf(str(pdf), "no_transmisibles_asma", "asma_j45")
    assert not salida["valid"]
    assert "columnas inesperadas" in salida["reason"]


@pytest.mark.unit
def test_despega_el_valor_pegado_al_nombre():
    tabla = pd.DataFrame(
        [
            ["FEDERATIVA", "", ""],
            ["53\nAguascalientes", "570", "1 862"],
            ["-\nColima", "4", "5"],
            ["San Luis Potosí\nChiapas", "924", "3 318"],
            ["Yucatán\n  28", "340", "991"],
        ]
    )
    limpia = ce.despega_primera_columna(tabla)
    assert limpia.shape == (5, 4)
    assert limpia[0].tolist() == ["FEDERATIVA", "Aguascalientes", "Colima", "Chiapas", "Yucatán"]
    # El valor ilegible de Chiapas queda vacío: nunca se inventa.
    assert limpia[1].tolist() == ["", "53", "-", "", "28"]
    assert limpia[2].tolist() == ["", "570", "4", "924", "340"]


@pytest.mark.unit
def test_la_reparacion_no_aplica_a_un_primer_bloque(monkeypatch, tmp_path):
    pdf = tmp_path / "2021_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    llamadas = []

    def tabla(_pdf, _page, **kw):
        llamadas.append(kw)
        return _tabla(12).iloc[:5]

    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 7)
    monkeypatch.setattr(ce, "_tabla_estatal", tabla)
    salida = ce.extract_cuadro_from_pdf(str(pdf), "no_transmisibles_ulceras", "ulceras_k25")
    assert not salida["valid"]
    assert all("despegar" not in kw for kw in llamadas)
