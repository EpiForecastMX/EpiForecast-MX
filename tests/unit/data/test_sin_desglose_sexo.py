"""Padecimientos sin desglose por sexo: 32 bases «general», 5 derivados y 37 productos.

El boletín da sólo el total de cuello del útero, próstata u ovario. El runner los modela como 32
series estatales «general» sin inventar hombres ni mujeres, y los padecimientos con desglose
conservan su partición 64→111. Unidades sintéticas sobre el catálogo trackeado (CI-safe).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from epiforecast import registry
from epiforecast.data import epi_aggregate as agg
from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data import sex_scheme
from epiforecast.data.epi_dataset import build_prep, explode_base
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.data.epi_reconcile import reconcile_state
from epiforecast.runner import contracts as ct
from epiforecast.runner import evaluation as ev

pytestmark = pytest.mark.unit

_PERIODS = [
    (2026, 1, date(2026, 1, 5)),
    (2026, 2, date(2026, 1, 12)),
]


@pytest.fixture(scope="module")
def catalog():
    return load_geo_catalog()


def _base_general(catalog) -> pd.DataFrame:
    rows = []
    for i, cve in enumerate(catalog.cve_ents()):
        for yy, ww, ds in _PERIODS:
            rows.append(
                {
                    spec.COL_DISEASE_ID: "cancer_cuello_utero_c53",
                    spec.COL_CVE_ENT: cve,
                    spec.COL_SEXO: spec.SEX_GENERAL,
                    spec.COL_EPI_YEAR: yy,
                    spec.COL_EPI_WEEK: ww,
                    spec.COL_PERIOD_START: ds,
                    spec.COL_DS: ds,
                    spec.COL_Y_CASES: i + ww,
                    spec.COL_EXPOSURE: 1000 + i,
                    spec.COL_OBSERVED: True,
                    spec.COL_QUALITY_FLAGS: "",
                }
            )
    return pd.DataFrame(rows)


def test_conteos_de_los_dos_esquemas():
    assert spec.SCHEME_POR_SEXO.counts() == {
        "base": 64,
        "state_general": 32,
        "regional": 12,
        "national": 3,
        "derived": 47,
        "products": 111,
    }
    assert spec.SCHEME_TOTAL.counts() == {
        "base": 32,
        "state_general": 0,
        "regional": 4,
        "national": 1,
        "derived": 5,
        "products": 37,
    }
    assert spec.scheme_from_sexes(["general"]) is spec.SCHEME_TOTAL
    assert spec.scheme_from_sexes(["mujeres", "hombres"]) is spec.SCHEME_POR_SEXO
    with pytest.raises(ValueError):
        spec.scheme_from_sexes(["mujeres"])  # un sexo suelto no es un esquema


def test_el_registry_declara_quien_no_desglosa_sexo():
    assert registry.require("cancer_cuello_utero_c53").sex_breakdown is False
    assert sex_scheme.scheme_for("cancer_cuello_utero_c53") is spec.SCHEME_TOTAL
    for d in ("obesidad", "cancer_mama_c50", "ivu_n39"):
        assert sex_scheme.scheme_for(d) is spec.SCHEME_POR_SEXO


def test_productos_sin_sexo_37_y_sumas_exactas(catalog):
    base = _base_general(catalog)
    res = agg.build_products(base, catalog, "cancer_cuello_utero_c53")
    p = res.products
    assert res.counts["products"] == 37 and res.counts["base"] == 32 and res.counts["derived"] == 5
    assert set(p[spec.COL_SEX]) == {spec.SEX_GENERAL}
    nat = p[p[spec.COL_GEO_LEVEL] == spec.GEO_LEVEL_NACIONAL]
    assert list(nat[spec.COL_Y_CASES]) == list(
        base.groupby(spec.COL_EPI_WEEK)[spec.COL_Y_CASES].sum()
    )
    # El lineage no inventa sexos: sólo regiones y nacional.
    assert len(res.lineage) == 5
    assert all(k.endswith("/general") for k in res.lineage)


def test_una_base_sin_sexo_incompleta_falla(catalog):
    base = _base_general(catalog)
    base = base[base[spec.COL_CVE_ENT] != catalog.cve_ents()[0]]
    with pytest.raises(agg.AggregateError, match="32 series base"):
        agg.build_products(base, catalog, "cancer_cuello_utero_c53")


def test_mezclar_general_con_un_sexo_falla(catalog):
    base = _base_general(catalog)
    base.loc[base.index[0], spec.COL_SEXO] = spec.SEX_MUJERES
    with pytest.raises(agg.AggregateError):
        agg.build_products(base, catalog, "cancer_cuello_utero_c53")


def test_base_mask_elige_las_bases_de_cada_esquema(catalog):
    total = agg.build_products(_base_general(catalog), catalog, "x").products
    assert sex_scheme.base_mask(total).sum() == 32 * len(_PERIODS)
    assert sex_scheme.n_bases_of(total[spec.COL_SEX]) == 32


def _fc(catalog, sexos) -> pd.DataFrame:
    rows = []
    for i, cve in enumerate(catalog.cve_ents()):
        for j, sexo in enumerate(sexos):
            rows.append(
                {
                    ct.COL_RUN_ID: "r",
                    ct.COL_ENGINE: "seasonal_naive_lag52",
                    ct.COL_FOLD: "test_2025",
                    ct.COL_ORIGIN_EPI_YEAR: 2024,
                    ct.COL_ORIGIN_EPI_WEEK: 52,
                    ct.COL_HORIZON: 1,
                    "disease_id": "cancer_cuello_utero_c53",
                    ct.COL_GEO_LEVEL: "estado",
                    ct.COL_GEO_ID: cve,
                    ct.COL_SEX: sexo,
                    ct.COL_EPI_YEAR: 2025,
                    ct.COL_EPI_WEEK: 1,
                    ct.COL_DS: date(2024, 12, 29),
                    ct.COL_Y_PRED: 1.0 + i + j,
                    ct.COL_YHAT_LOWER: np.nan,
                    ct.COL_YHAT_UPPER: np.nan,
                }
            )
    return pd.DataFrame(rows)


def test_pronostico_sin_sexo_deriva_37_productos(catalog):
    base = _fc(catalog, [spec.SEX_GENERAL])
    full = ev.derive_forecast_products(base, catalog)
    ct.validate_forecast_frame(full)
    assert full.groupby([ct.COL_GEO_LEVEL, ct.COL_GEO_ID, ct.COL_SEX]).ngroups == 37
    nat = full[full[ct.COL_GEO_LEVEL] == "nacional"][ct.COL_Y_PRED].iloc[0]
    assert nat == pytest.approx(base[ct.COL_Y_PRED].sum())
    # Con desglose no cambia nada: 111.
    con_sexo = ev.derive_forecast_products(_fc(catalog, spec.BASE_SEXES), catalog)
    assert con_sexo.groupby([ct.COL_GEO_LEVEL, ct.COL_GEO_ID, ct.COL_SEX]).ngroups == 111


def test_training_spec_admite_estado_general():
    key = spec.SeriesKey("cancer_cuello_utero_c53", "estado", "05", "general")
    assert key.sex == "general"
    with pytest.raises(ct.ContractError):
        ct.TrainingSpec(
            key=spec.SeriesKey("x", "region", "norte", "general"),
            engine="seasonal_naive_lag52",
            dataset_digest="d",
            policy_name="p",
            policy_digest="p",
            fold_id="f",
            seed=1,
            horizon=1,
            transform=None,  # type: ignore[arg-type]
        )


def test_raw_sin_sexo_reconcilia_el_total_sin_banderas_de_sexo(catalog):
    filas = []
    for cve in catalog.cve_ents():
        nombre = catalog.entity(cve).nombre_canonico
        for semana, (casos, acum) in enumerate([(3, 3), (2, 5)], start=2):
            filas.append(
                {
                    "Anio": 2026,
                    "Semana": semana,
                    "Entidad": nombre,
                    "Padecimiento": "Tumor maligno del cuello del útero",
                    "Casos_semana": casos,
                    "Acumulado_total": acum,
                    "Acumulado_anio_anterior": 1,
                }
            )
    raw = pd.DataFrame(filas)
    prep = build_prep(raw, catalog, 1)
    state = reconcile_state(prep, set(catalog.cve_ents()))
    snapshot = type(
        "Snap",
        (),
        {
            "columns_by_sex": {"hombres": "Hombres", "mujeres": "Mujeres"},
            "total_column": "Total",
            "by_cve_ent": {
                c: {"Hombres": 1, "Mujeres": 2, "Total": 3} for c in catalog.cve_ents()
            },
            "exposure_for": lambda self, c, s: 0,
        },
    )()
    base = explode_base(state, snapshot, catalog, "cancer_cuello_utero_c53", spec.SCHEME_TOTAL)
    assert set(base[spec.COL_SEXO]) == {spec.SEX_GENERAL}
    assert len(base) == 32 * 2
    assert set(base[spec.COL_EXPOSURE]) == {3}  # columna total, no H ni M
    assert sorted(set(base[spec.COL_Y_CASES])) == [2, 3]
    assert not base[spec.COL_QUALITY_FLAGS].str.contains("sex_").any()
    assert base[spec.COL_SEX_PROP_APPLIED].isna().all()


def test_el_extractor_lee_el_bloque_sin_sexo():
    from epiforecast.data.extraction import cuadro_extractor as ce

    df = pd.DataFrame(
        {0: ["Aguascalientes", "Zacatecas"], 1: ["4", "-"], 2: ["35", "7"], 3: ["20", "1"]}
    )
    out = ce._sin_sexo(
        {"df": None}, df, {"n_states_expected": 2}, "cancer_cuello_utero_c53", 2026, 42
    )
    assert out["valid"] and out["layout"] == "3col_total"
    assert list(out["df"].columns) == [
        "Anio",
        "Semana",
        "Entidad",
        "Padecimiento",
        "Casos_semana",
        "Acumulado_total",
        "Acumulado_anio_anterior",
    ]
    assert out["df"]["Acumulado_total"].tolist() == [35, 7]
    ancho = pd.DataFrame({0: ["Aguascalientes"], 1: ["1"], 2: ["2"], 3: ["3"], 4: ["4"]})
    assert "columnas inesperadas" in ce._sin_sexo({}, ancho, {}, "x", 2026, 42)["reason"]
