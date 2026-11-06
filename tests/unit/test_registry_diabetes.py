"""N+1: Diabetes tipo I/II se registran por CONFIGURACIÓN (cuadro 13) y nacen invisibles."""

from __future__ import annotations

import pandas as pd
import pytest
from scripts.extrae_cuadro import CONSOLIDATED_COLS, _empty_periods

from epiforecast import registry
from epiforecast.data.extraction import cuadro_extractor

_GRUPO = "enfermedades_no_transmisibles"


@pytest.mark.parametrize(
    ("disease_id", "cie", "alias"),
    [("diabetes_t1", ("E10",), "dm1"), ("diabetes_t2", ("E11", "E12", "E13", "E14"), "diabetes")],
)
def test_identidad_e_invisibilidad(disease_id: str, cie: tuple[str, ...], alias: str) -> None:
    spec = registry.require(disease_id)
    assert spec.cie_codes == cie
    assert registry.require(alias).id == disease_id
    assert spec.extraction_group == _GRUPO
    assert spec.exposure_source_id == "inegi_cpv2020_static"
    assert spec.lifecycle == "configured"
    assert spec.channels == () or list(spec.channels) == []
    assert not spec.gallery_enabled


def test_bloques_del_cuadro_13() -> None:
    grupo = cuadro_extractor.load_group(_GRUPO)
    bloques = {d["id"]: (d["block_index"], d["onboard"]) for d in grupo["diseases"]}
    assert bloques == {
        "bocio_e01": (0, False),
        "diabetes_t1": (1, True),
        "diabetes_t2": (2, True),
    }
    assert grupo["observation_lag_weeks"] == 1 and grupo["n_states_expected"] == 32


def test_exclusiones_de_fuente_apuntan_a_bloques_declarados() -> None:
    grupo = cuadro_extractor.load_group(_GRUPO)
    ids = {d["id"] for d in grupo["diseases"]}
    for exc in grupo["source_exclusions"]:
        assert set(exc["diseases"]) <= ids and exc["reason"]


def test_source_exclusion_es_por_boletin_y_padecimiento() -> None:
    grupo = cuadro_extractor.load_group(_GRUPO)
    exc = cuadro_extractor.source_exclusion(grupo, "2016_sem20.pdf", "diabetes_t2")
    assert exc is not None and exc["keep_period"] is True
    # El mismo boletín es válido para E10: la errata sólo afecta al bloque E11-E14.
    assert cuadro_extractor.source_exclusion(grupo, "2016_sem20.pdf", "diabetes_t1") is None
    anual = cuadro_extractor.source_exclusion(grupo, "2014_sem01.pdf", "diabetes_t1")
    assert anual is not None and not anual.get("keep_period", False)
    assert cuadro_extractor.source_exclusion(grupo, "2016_sem21.pdf", "diabetes_t2") is None


def test_periodo_conservado_sale_vacio_con_las_entidades_del_extractor() -> None:
    like = pd.DataFrame({"Entidad": ["Colima", "Aguascalientes", "Colima"]})
    out = _empty_periods([(2016, 20)], like, "Diabetes tipo II")
    assert list(out.columns) == CONSOLIDATED_COLS
    assert out["Entidad"].tolist() == ["Aguascalientes", "Colima"]
    assert (out["Padecimiento"] == "Diabetes tipo II").all()
    datos = ["Casos_semana", "Acumulado_hombres", "Acumulado_mujeres", "Acumulado_anio_anterior"]
    assert out[datos].isna().all().all()
