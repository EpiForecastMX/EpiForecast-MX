"""F1/C1 — catálogo geográfico (trackeado) + loader de exposición con snapshot SINTÉTICO.

No lee ``data/utils/inegi.csv`` (gitignored). El snapshot real CPV 2020 (digest/sumas) → integration.
El catálogo (``config/geografia/entidades_mx.csv``) sí es trackeado y CI-safe.
"""

from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from epiforecast.data import epi_geo_exposure as ge


@pytest.fixture(scope="module")
def catalog():
    return ge.load_geo_catalog()


# ── Catálogo (trackeado) ──
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


def test_catalogo_menos_de_32_levanta(tmp_path):
    p = tmp_path / "cat.csv"
    p.write_text(
        "cve_ent,nombre_canonico,nombre_inegi,macroregion_id,macroregion_name,aliases\n"
        "01,Aguascalientes,Aguascalientes,occidente,Occidente,Ags.\n",
        encoding="utf-8",
    )
    with pytest.raises(ge.GeoExposureError):
        ge.load_geo_catalog(p)


# ── Membresía de macrorregiones (C2: datos trackeados, identidad != display) ──
def test_macrorregiones_membresia(catalog):
    assert catalog.macroregion_ids() == ["centro", "norte", "occidente", "sureste"]
    counts = {m: len(catalog.states_in_macroregion(m)) for m in catalog.macroregion_ids()}
    assert counts == {"norte": 9, "occidente": 8, "centro": 7, "sureste": 8}
    # Partición exacta de las 32 (sin solapes ni huecos).
    todos = [cve for m in catalog.macroregion_ids() for cve in catalog.states_in_macroregion(m)]
    assert sorted(todos) == catalog.cve_ents() and len(set(todos)) == 32


def test_macroregion_names(catalog):
    # ID (identidad, lowercase) desacoplado del nombre de display; no se deriva por slugify.
    assert {m: catalog.macroregion_name(m) for m in catalog.macroregion_ids()} == {
        "norte": "Norte",
        "occidente": "Occidente",
        "centro": "Centro",
        "sureste": "Sureste",
    }


@pytest.mark.parametrize(
    "cve,macroregion_id",
    [("05", "norte"), ("16", "occidente"), ("09", "centro"), ("30", "sureste")],
)
def test_macroregion_of(catalog, cve, macroregion_id):
    assert catalog.macroregion_of(cve) == macroregion_id


def test_macroregion_desconocida_levanta(catalog):
    with pytest.raises(ge.GeoExposureError):
        catalog.states_in_macroregion("bajio")
    with pytest.raises(ge.GeoExposureError):
        catalog.macroregion_name("bajio")


# ── Exposición: snapshot SINTÉTICO de 32 entidades (usa los nombres INEGI del catálogo) ──
def _synthetic_source(tmp_path, catalog, *, kind="ok"):
    rows = []
    for i, e in enumerate(catalog.entities):
        h, m = 100 + i, 120 + i
        if kind == "fractional" and i == 0:
            h = h + 0.5  # valor no entero → debe fallar el gate
        if kind == "nonpositive" and i == 0:
            h = 0
        t = h + m
        if kind == "break_total" and i == 0:
            t = t + 1
        rows.append({"Entidad federativa": e.nombre_inegi, "Hombres": h, "Mujeres": m, "Total": t})
    inegi = tmp_path / "inegi_syn.csv"
    pd.DataFrame(rows).to_csv(inegi, index=False)
    sha = "deadbeef" if kind == "bad_sha" else hashlib.sha256(inegi.read_bytes()).hexdigest()
    cfg = tmp_path / "exposicion.yaml"
    cfg.write_text(
        "version: 1\n"
        "fuentes:\n"
        "  syn:\n"
        f'    path: "{inegi}"\n'
        '    reference: "TEST"\n'
        '    cutoff: "2020-01-01"\n'
        '    entidad_column: "Entidad federativa"\n'
        "    columns_by_sex:\n"
        "      hombres: Hombres\n"
        "      mujeres: Mujeres\n"
        "    total_column: Total\n"
        f"    sha256: {sha}\n",
        encoding="utf-8",
    )
    return cfg


def test_exposicion_loader_ok(tmp_path, catalog):
    snap = ge.load_exposure_snapshot(
        "syn", catalog, config_path=_synthetic_source(tmp_path, catalog)
    )
    assert len(snap.by_cve_ent) == 32
    assert snap.columns_by_sex == {"hombres": "Hombres", "mujeres": "Mujeres"}
    assert snap.total_column == "Total"
    for v in snap.by_cve_ent.values():
        assert v["Hombres"] + v["Mujeres"] == v["Total"]
    assert snap.exposure_for("01", "hombres") == 100 and snap.exposure_for("01", "mujeres") == 120


def test_exposicion_fuente_desconocida(tmp_path, catalog):
    with pytest.raises(ge.GeoExposureError):
        ge.load_exposure_snapshot(
            "no_existe", catalog, config_path=_synthetic_source(tmp_path, catalog)
        )


@pytest.mark.parametrize(
    "kind,match", [("bad_sha", "digest"), ("break_total", "Total"), ("fractional", "entero")]
)
def test_exposicion_validaciones(tmp_path, catalog, kind, match):
    cfg = _synthetic_source(tmp_path, catalog, kind=kind)
    with pytest.raises(ge.GeoExposureError, match=match):
        ge.load_exposure_snapshot("syn", catalog, config_path=cfg)


def test_exposicion_no_positiva(tmp_path, catalog):
    cfg = _synthetic_source(tmp_path, catalog, kind="nonpositive")
    with pytest.raises(ge.GeoExposureError):
        ge.load_exposure_snapshot("syn", catalog, config_path=cfg)
