"""F1/C1 — EpiDatasetV2: unidades SINTÉTICAS (sin datos gitignored). El gate real → integration.

No leen ``data/raw`` ni ``data/utils`` (gitignored, ausentes en un clon de CI). El catálogo
geográfico vive en ``config/`` (trackeado), así que ``load_geo_catalog`` es CI-safe.
"""

from __future__ import annotations

from datetime import date
import hashlib

import pandas as pd
import pytest

from epiforecast.data import epi_dataset as ed
from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data.epi_dataset_spec import ExposureSnapshot
from epiforecast.data.epi_geo_exposure import load_geo_catalog


@pytest.fixture(scope="module")
def catalog():
    return load_geo_catalog()  # config trackeado → CI-safe


# ── build_prep: calendario + geo (fuente sintética) ──
def test_build_prep_calendario_y_geo(catalog):
    raw = pd.DataFrame(
        {
            "Anio": [2026, 2026],
            "Semana": [2, 2],
            "Entidad": ["Coahuila", "Veracruz"],
            "Casos_semana": [10, 20],
            "Acumulado_hombres": [6, 12],
            "Acumulado_mujeres": [4, 8],
        }
    )
    prep = ed.build_prep(raw, catalog, 1)  # lag 1: 2026-W02 → 2026-W01, ds 2026-01-05
    assert prep["epi_year"].tolist() == [2026, 2026]
    assert prep["epi_week"].tolist() == [1, 1]
    assert prep["ds"].tolist() == [date(2026, 1, 5), date(2026, 1, 5)]
    assert set(prep["cve_ent"]) == {"05", "30"}  # Coahuila, Veracruz


def test_build_prep_casos_na(catalog):
    raw = pd.DataFrame(
        {
            "Anio": [2026],
            "Semana": [2],
            "Entidad": ["Coahuila"],
            "Casos_semana": [float("nan")],
            "Acumulado_hombres": [6],
            "Acumulado_mujeres": [4],
        }
    )
    assert pd.isna(ed.build_prep(raw, catalog, 1)["casos_source"].iloc[0])


# ── explode_base: 2 sexos + exposición por sexo + y_cases ──
def _snapshot():
    return ExposureSnapshot(
        source_id="syn",
        reference="r",
        cutoff=date(2020, 1, 1),
        columns_by_sex={"hombres": "Hombres", "mujeres": "Mujeres"},
        total_column="Total",
        digest="d",
        by_cve_ent={"05": {"Hombres": 100, "Mujeres": 120, "Total": 220}},
    )


def _state_row(**kw):
    base = {
        "cve_ent": "05",
        "source_year": 2026,
        "source_week": 2,
        "epi_year": 2026,
        "epi_week": 1,
        "period_start": date(2026, 1, 4),
        "ds": date(2026, 1, 5),
        "total_source": 10,
        "total_reconciled": 10,
        "observed": True,
        "y_hombres": 6,
        "y_mujeres": 4,
        "sex_prop_source": 0.6,
        "sex_prop_applied": 0.6,
        "sex_delta_total": 10.0,
        "sex_delta_residual": 0.0,
        "quality_flags": "",
    }
    base.update(kw)
    return base


def test_explode_base_dos_sexos_exposicion(catalog):
    base = ed.explode_base(pd.DataFrame([_state_row()]), _snapshot(), catalog, "obesidad")
    assert len(base) == 2
    assert list(base.columns) == list(spec.BASE_COLUMNS)
    h = base[base.sexo == "hombres"].iloc[0]
    m = base[base.sexo == "mujeres"].iloc[0]
    assert (h.y_cases, h.exposure) == (6, 100) and h.entidad_canonica == "Coahuila"
    assert (m.y_cases, m.exposure) == (4, 120) and m.entidad_inegi == "Coahuila de Zaragoza"
    assert h.disease_id == "obesidad"


# ── digest / orden canónico ──
def test_canonical_csv_determinista_y_order_invariante():
    df = pd.DataFrame(
        {
            "cve_ent": ["05", "05", "30"],
            "sexo": ["mujeres", "hombres", "hombres"],
            "epi_year": [2026, 2026, 2026],
            "epi_week": [1, 1, 1],
            "y_cases": [4, 6, 20],
        }
    )
    a = ed._canonical_csv(df)
    b = ed._canonical_csv(df.sample(frac=1.0, random_state=3))
    assert a == b
    assert hashlib.sha256(a.encode()).hexdigest() == hashlib.sha256(b.encode()).hexdigest()


# ── config (registry + cuadros trackeados, sin datos) ──
def test_load_config_obesidad_valida():
    cfg = ed.load_config("Obesidad")
    assert cfg.disease_id == "obesidad"  # registry.id, no slug
    assert cfg.observation_lag_weeks == 1 and not isinstance(cfg.observation_lag_weeks, bool)
    assert cfg.exposure_source_id == "inegi_cpv2020_static" and cfg.expected_n_states == 32


def test_load_config_exige_exposure_source_id():
    with pytest.raises(ed.EpiDatasetError):
        ed.load_config("Dengue")  # legacy sin exposure_source_id
