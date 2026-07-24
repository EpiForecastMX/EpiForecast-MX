"""F1/C1 — gate de INTEGRACIÓN: EpiDatasetV2 sobre el raw E66 real + exposición CPV 2020 real.

Requiere ``data/raw/data_raw_Obesidad.csv`` y ``data/utils/inegi.csv`` (gitignored, restaurados por
DVC). Marcado ``integration`` → CI (``-m "not integration"``) lo excluye; corre localmente y vía
``disease_run validate-data``. Si los datos locales no están, se hace **skip explícito**.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from epiforecast.data import epi_dataset as ed
from epiforecast.data.epi_geo_exposure import load_exposure_snapshot, load_geo_catalog

pytestmark = pytest.mark.integration

_ROOT = ed._ROOT
_RAW = _ROOT / "data" / "raw" / "data_raw_Obesidad.csv"
_INEGI = _ROOT / "data" / "utils" / "inegi.csv"


def _require_data() -> None:
    if not _RAW.exists() or not _INEGI.exists():
        pytest.skip("datos locales E66/INEGI no disponibles (DVC no restaurado)")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    _require_data()
    return ed.build_epi_dataset_v2("Obesidad", runs_root=tmp_path_factory.mktemp("runs"))


def test_gate_conteos_exactos(built):
    b, s = built.dataset, built.state
    assert len(b) == 41_792 and len(s) == 20_896
    assert b.groupby(["cve_ent", "sexo"]).ngroups == 64
    assert set(b.groupby(["cve_ent", "sexo"]).size().unique()) == {653}
    assert s.groupby(["epi_year", "epi_week"]).ngroups == 653


def test_gate_sin_duplicados_ni_negativos(built):
    b = built.dataset
    assert b.duplicated(["epi_year", "epi_week", "cve_ent", "sexo"]).sum() == 0
    assert (b["y_cases"] < 0).sum() == 0 and (b["exposure"] > 0).all()


def test_gate_33_imputaciones(built):
    assert int((~built.state["observed"]).sum()) == 33  # 32 colapso 2016-W19 + Querétaro 2016-W49


def test_gate_reconciliacion_exacta(built):
    b, s = built.dataset, built.state
    piv = b.pivot_table(
        index=["epi_year", "epi_week", "cve_ent"], columns="sexo", values="y_cases", aggfunc="sum"
    )
    merged = piv.join(s.set_index(["epi_year", "epi_week", "cve_ent"])["total_reconciled"])
    assert (merged["hombres"] + merged["mujeres"] == merged["total_reconciled"]).all()


def test_gate_exposicion_por_sexo(built):
    b = built.dataset
    h = b[(b.cve_ent == "09") & (b.sexo == "hombres")]["exposure"].iloc[0]
    m = b[(b.cve_ent == "09") & (b.sexo == "mujeres")]["exposure"].iloc[0]
    assert (int(h), int(m)) == (4_404_927, 4_805_017)
    assert b.groupby(["cve_ent", "sexo"])["exposure"].nunique().eq(1).all()


def test_gate_rango_periodos(built):
    s = built.state.sort_values(["epi_year", "epi_week"])
    assert (int(s.iloc[0].epi_year), int(s.iloc[0].epi_week)) == (2014, 1)
    assert (int(s.iloc[-1].epi_year), int(s.iloc[-1].epi_week)) == (2026, 26)


def test_gate_digests_y_reproducible(built, tmp_path):
    assert set(built.digests) == {"raw", "exposure", "config", "dataset"}
    assert len(set(built.digests.values())) == 4
    again = ed.build_epi_dataset_v2("Obesidad", runs_root=tmp_path)
    assert again.digests["dataset"] == built.digests["dataset"]


def test_gate_insumos_efectivos_y_manifest(built):
    inp = built.run_dir / "inputs"
    names = {p.name for p in inp.iterdir()}
    assert "data_raw_Obesidad.csv" in names
    assert "entidades_mx.csv" in names  # catálogo geográfico efectivo
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
    assert cfg["calendar"] == {"kind": "epi_mmwr", "observation_lag_weeks": 1}
    assert cfg["exposure"]["source_id"] == "inegi_cpv2020_static"
    assert cfg["exposure"]["total_column"] == "Total"
    assert cfg["geo_catalog"]["digest"]  # digest del catálogo presente


def test_exposicion_real_digest_y_sumas():
    _require_data()
    snap = load_exposure_snapshot("inegi_cpv2020_static", load_geo_catalog())
    assert snap.digest == "d1453197abfc18b52955fbc7e86c4750e4f1ec9f1c9987a02a293139d70be3e2"
    h = sum(v["Hombres"] for v in snap.by_cve_ent.values())
    m = sum(v["Mujeres"] for v in snap.by_cve_ent.values())
    t = sum(v["Total"] for v in snap.by_cve_ent.values())
    assert (h, m, t) == (61_473_390, 64_540_634, 126_014_024)


def test_todas_las_entidades_del_raw_e66_resuelven():
    _require_data()
    catalog = load_geo_catalog()
    raw = pd.read_csv(_RAW, usecols=["Entidad"])
    for e in raw["Entidad"].dropna().unique():
        assert catalog.resolve(e) in catalog._by_cve
