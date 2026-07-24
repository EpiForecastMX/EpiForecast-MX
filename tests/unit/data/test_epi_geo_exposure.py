"""F1/C1 — catálogo geográfico + snapshot de exposición CPV 2020 (join estricto, digest)."""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.data import epi_geo_exposure as ge


@pytest.fixture(scope="module")
def catalog():
    return ge.load_geo_catalog()


def test_catalogo_32_entidades(catalog):
    assert len(catalog.entities) == 32
    assert catalog.cve_ents() == [f"{i:02d}" for i in range(1, 33)]


@pytest.mark.parametrize(
    "nombre,cve",
    [
        ("Coahuila", "05"),
        ("Coahuila de Zaragoza", "05"),
        ("Michoacán", "16"),
        ("Michoacán de Ocampo", "16"),
        ("Veracruz", "30"),
        ("Veracruz de Ignacio de la Llave", "30"),
        ("Ciudad de México", "09"),
        ("Distrito Federal", "09"),
        ("México", "15"),
        ("Estado de México", "15"),
    ],
)
def test_resolve_mappings_obligatorios(catalog, nombre, cve):
    assert catalog.resolve(nombre) == cve


def test_resolve_desconocido_levanta(catalog):
    with pytest.raises(ge.GeoExposureError):
        catalog.resolve("Narnia")


def test_todas_las_entidades_del_raw_e66_resuelven(catalog):
    raw = pd.read_csv("data/raw/data_raw_Obesidad.csv", usecols=["Entidad"])
    for e in raw["Entidad"].dropna().unique():
        assert catalog.resolve(e) in catalog._by_cve  # sin fuzzy: match exacto o alias


def test_exposicion_cpv2020_digest_y_sumas(catalog):
    snap = ge.load_exposure_snapshot("inegi_cpv2020_static", catalog)
    assert snap.source_id == "inegi_cpv2020_static"
    assert snap.reference == "CPV 2020"
    assert str(snap.cutoff) == "2020-03-15"
    assert snap.digest == "d1453197abfc18b52955fbc7e86c4750e4f1ec9f1c9987a02a293139d70be3e2"
    assert len(snap.by_cve_ent) == 32
    h = sum(v["Hombres"] for v in snap.by_cve_ent.values())
    m = sum(v["Mujeres"] for v in snap.by_cve_ent.values())
    t = sum(v["Total"] for v in snap.by_cve_ent.values())
    assert (h, m, t) == (61_473_390, 64_540_634, 126_014_024)
    for cve, v in snap.by_cve_ent.items():
        assert v["Hombres"] + v["Mujeres"] == v["Total"], cve
        assert all(x > 0 for x in v.values()), cve


def test_fuente_desconocida_levanta(catalog):
    with pytest.raises(ge.GeoExposureError):
        ge.load_exposure_snapshot("no_existe", catalog)


# ── Validaciones del catálogo con datos sintéticos ──
def _write_catalog(tmp_path, rows: list[str]):
    p = tmp_path / "cat.csv"
    p.write_text(
        "cve_ent,nombre_canonico,nombre_inegi,aliases\n" + "\n".join(rows) + "\n", "utf-8"
    )
    return p


def test_catalogo_menos_de_32_levanta(tmp_path):
    p = _write_catalog(tmp_path, ["01,Aguascalientes,Aguascalientes,Ags."])
    with pytest.raises(ge.GeoExposureError):
        ge.load_geo_catalog(p)


def test_digest_incorrecto_levanta(tmp_path, catalog, monkeypatch):
    # Config con sha256 esperado erróneo → debe abortar.
    cfg = tmp_path / "exposicion.yaml"
    cfg.write_text(
        "version: 1\n"
        "fuentes:\n"
        "  inegi_cpv2020_static:\n"
        "    path: data/utils/inegi.csv\n"
        '    reference: "CPV 2020"\n'
        '    cutoff: "2020-03-15"\n'
        '    entidad_column: "Entidad federativa"\n'
        "    columns: [Hombres, Mujeres, Total]\n"
        "    sha256: deadbeef\n",
        "utf-8",
    )
    with pytest.raises(ge.GeoExposureError, match="digest"):
        ge.load_exposure_snapshot("inegi_cpv2020_static", catalog, config_path=cfg)
