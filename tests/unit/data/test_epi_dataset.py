"""F1/C1 — gate de EpiDatasetV2 sobre el raw E66 real (culminación de C1)."""

from __future__ import annotations

import json

import pytest

from epiforecast.data import epi_dataset as ed


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("runs")
    return ed.build_epi_dataset_v2("Obesidad", runs_root=root)


def test_gate_conteos_exactos(built):
    b, s = built.dataset, built.state
    assert len(b) == 41_792  # 32 estados × 2 sexos × 653 periodos
    assert len(s) == 20_896  # 32 × 653
    assert b.groupby(["cve_ent", "sexo"]).ngroups == 64
    assert set(b.groupby(["cve_ent", "sexo"]).size().unique()) == {653}
    assert s.groupby(["epi_year", "epi_week"]).ngroups == 653


def test_gate_sin_duplicados_ni_negativos(built):
    b = built.dataset
    assert b.duplicated(["epi_year", "epi_week", "cve_ent", "sexo"]).sum() == 0
    assert (b["y_cases"] < 0).sum() == 0
    assert (b["exposure"] > 0).all()


def test_gate_33_imputaciones(built):
    assert int((~built.state["observed"]).sum()) == 33  # 32 del colapso + Querétaro


def test_gate_reconciliacion_exacta(built):
    b, s = built.dataset, built.state
    piv = b.pivot_table(
        index=["epi_year", "epi_week", "cve_ent"], columns="sexo", values="y_cases", aggfunc="sum"
    )
    merged = piv.join(s.set_index(["epi_year", "epi_week", "cve_ent"])["total_reconciled"])
    assert (merged["hombres"] + merged["mujeres"] == merged["total_reconciled"]).all()


def test_gate_exposicion_por_sexo(built):
    b = built.dataset
    # CDMX (09): Hombres/Mujeres del CPV 2020.
    h = b[(b.cve_ent == "09") & (b.sexo == "hombres")]["exposure"].iloc[0]
    m = b[(b.cve_ent == "09") & (b.sexo == "mujeres")]["exposure"].iloc[0]
    assert (int(h), int(m)) == (4_404_927, 4_805_017)
    # Hombres usa exposición Hombres; mujeres usa Mujeres (constante por serie).
    assert b.groupby(["cve_ent", "sexo"])["exposure"].nunique().eq(1).all()


def test_gate_rango_periodos(built):
    s = built.state.sort_values(["epi_year", "epi_week"])
    assert (int(s.iloc[0].epi_year), int(s.iloc[0].epi_week)) == (2014, 1)
    assert (int(s.iloc[-1].epi_year), int(s.iloc[-1].epi_week)) == (2026, 26)


def test_gate_digests_separados_y_reproducibles(built, tmp_path):
    assert set(built.digests) == {"raw", "exposure", "config", "dataset"}
    assert len(set(built.digests.values())) == 4  # todos distintos
    assert built.digests["exposure"] == built.snapshot.digest
    # reproducible: un segundo build da el mismo digest de dataset.
    again = ed.build_epi_dataset_v2("Obesidad", runs_root=tmp_path)
    assert again.digests["dataset"] == built.digests["dataset"]


def test_gate_insumos_efectivos_y_manifest(built):
    inp = built.run_dir / "inputs"
    names = {p.name for p in inp.iterdir()}
    assert "data_raw_Obesidad.csv" in names
    assert any(n.startswith("exposure_") for n in names)
    assert "config_effective.json" in names
    assert (built.run_dir / "epi_dataset_v2.csv").exists()
    manifest = json.loads((built.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"] == {
        "base_rows": 41_792,
        "state_rows": 20_896,
        "series": 64,
        "periods": 653,
        "imputed_totals": 33,
    }
    cfg = json.loads((inp / "config_effective.json").read_text(encoding="utf-8"))
    assert cfg["observation_lag_weeks"] == 1
    assert cfg["exposure_source_id"] == "inegi_cpv2020_static"
    assert set(cfg["columns_by_sex"]) == {"hombres", "mujeres"}


def test_gate_orden_canonico_estable(built):
    # El dataset devuelto ya viene en orden canónico (idempotente reordenar).
    b = built.dataset
    reordered = b.sort_values(ed._CANONICAL_ORDER).reset_index(drop=True)
    assert b.reset_index(drop=True).equals(reordered)


# ── Validaciones de config ──
def test_load_config_obesidad_valida():
    cfg = ed.load_config("Obesidad")
    assert cfg.disease_id == "obesidad"
    assert cfg.observation_lag_weeks == 1 and not isinstance(cfg.observation_lag_weeks, bool)
    assert cfg.exposure_source_id == "inegi_cpv2020_static"
    assert cfg.expected_n_states == 32


def test_load_config_exige_exposure_source_id():
    # Dengue (legacy) no declara exposure_source_id → EpiDatasetV2 lo rechaza.
    with pytest.raises(ed.EpiDatasetError):
        ed.load_config("Dengue")
