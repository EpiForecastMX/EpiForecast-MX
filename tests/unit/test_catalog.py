"""E0-S1: catálogo canónico de producción (baseline 432, no el 435 inflado)."""

from __future__ import annotations

import pytest

from epiforecast import catalog
from epiforecast.catalog import DENGUE_ELIGIBLE, build_production_catalog, validate_catalog


def _sources_present() -> bool:
    return catalog._neuro_table_path().exists() and catalog._dengue_table_path().exists()


pytestmark = pytest.mark.skipif(
    not _sources_present(),
    reason="requiere reports/ProdDetails/{tabla_333_modelos_produccion.xlsx,produccion_dengue.csv}",
)


@pytest.fixture(scope="module")
def catalog_data():
    return build_production_catalog()


def test_sin_duplicados_ni_motores_invalidos(catalog_data):
    df, _ = catalog_data
    assert validate_catalog(df) == []


def test_clave_unica_disease_entidad_sexo(catalog_data):
    df, _ = catalog_data
    assert not df.duplicated(subset=["disease_id", "entidad", "sexo"]).any()


def test_cohorte_neuro_es_333(catalog_data):
    _, counts = catalog_data
    assert counts.por_cohorte["neuro"] == 333
    # 3 padecimientos × 37 geografías × 3 sexos
    for pad in ("Alzheimer", "Depresion", "Parkinson"):
        assert counts.por_padecimiento[pad] == 111


def test_dengue_autoritativo_99_solo_motores_elegibles(catalog_data):
    df, counts = catalog_data
    assert counts.por_cohorte["dengue"] == 99
    den_engines = set(df[df["cohorte"] == "dengue"]["motor_productivo"])
    assert den_engines <= set(DENGUE_ELIGIBLE)


def test_produccion_es_432_no_435(catalog_data):
    _, counts = catalog_data
    assert counts.production_series_count == 432
    assert counts.production_series_count != 435  # el inflado con dup + inválidos


def test_gallery_distinto_de_produccion(catalog_data):
    _, counts = catalog_data
    # galería = 333 neuro + 111 Dengue (incluye las 4 regiones no productivas)
    assert counts.gallery_item_count == 444
    assert counts.gallery_item_count > counts.production_series_count


def test_diagnostico_documenta_dengue_stale(catalog_data):
    _, counts = catalog_data
    d = counts.diagnostics
    # el Dengue de tabla_333 trae 102 con 3 dup nacionales y sin NBGLM
    assert d.get("dengue_en_tabla_333") == 102
    assert d.get("nacionales_duplicados") == 3
    assert d.get("tiene_nbglm") is False
