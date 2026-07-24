"""F2/C2 — gate de INTEGRACIÓN: agregación 64→111 sobre el dataset base E66 real.

Reconstruye el dataset base (41,792) desde el raw E66 + CPV 2020 reales y deriva los 111
productos. La construcción de ``build_products`` valida internamente (tolerancia cero); un
retorno exitoso ES el gate. Marcado ``integration`` → excluido de CI; skip si faltan datos.
"""

from __future__ import annotations

import pytest

from epiforecast.data import epi_aggregate as agg
from epiforecast.data import epi_dataset as ed
from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data.epi_geo_exposure import load_geo_catalog

pytestmark = pytest.mark.integration

_ROOT = ed._ROOT
_RAW = _ROOT / "data" / "raw" / "data_raw_Obesidad.csv"
_INEGI = _ROOT / "data" / "utils" / "inegi.csv"


def _require_data() -> None:
    if not _RAW.exists() or not _INEGI.exists():
        pytest.skip("datos locales E66/INEGI no disponibles (DVC no restaurado)")


@pytest.fixture(scope="module")
def aggregated(tmp_path_factory):
    _require_data()
    built = ed.build_epi_dataset_v2("Obesidad", runs_root=tmp_path_factory.mktemp("runs"))
    return built, agg.build_products(built.dataset, load_geo_catalog(), "obesidad")


def test_gate_conteos_exactos(aggregated):
    _, res = aggregated
    assert res.counts == {
        "products": 111,
        "base": 64,
        "derived": 47,
        "periods": 653,
        "rows": 72_483,
    }
    assert len(res.products) == 72_483  # 111 × 653
    assert len(res.products) - 64 * 653 == 47 * 653 == 30_691  # filas derivadas


def test_gate_sin_duplicados(aggregated):
    _, res = aggregated
    assert res.products.duplicated(list(spec.PRODUCT_KEY)).sum() == 0
    assert res.products.groupby([spec.COL_GEO_LEVEL, spec.COL_GEO_ID, spec.COL_SEX]).ngroups == 111


def test_gate_nacional_conserva_gran_total(aggregated):
    built, res = aggregated
    p = res.products
    nat_gen = p[(p[spec.COL_GEO_LEVEL] == "nacional") & (p[spec.COL_SEX] == "general")][
        spec.COL_Y_CASES
    ].sum()
    assert int(nat_gen) == int(
        built.dataset[spec.COL_Y_CASES].sum()
    )  # suma directa de las 64 bases


def test_gate_lineage_completo(aggregated):
    _, res = aggregated
    assert len(res.lineage) == 47
    assert len(res.lineage["obesidad/nacional/mx/general"]) == 64
    assert all(len(v) >= 2 for v in res.lineage.values())


def test_gate_particion_regional(aggregated):
    built, res = aggregated
    catalog = load_geo_catalog()
    p = res.products
    # Σ estados-general de una región (todos los periodos) == región-general de esa región.
    for mr in catalog.macroregion_ids():
        states = catalog.states_in_macroregion(mr)
        sg = p[
            (p[spec.COL_GEO_LEVEL] == "estado")
            & (p[spec.COL_SEX] == "general")
            & (p[spec.COL_GEO_ID].isin(states))
        ][spec.COL_Y_CASES].sum()
        rg = p[
            (p[spec.COL_GEO_LEVEL] == "region")
            & (p[spec.COL_SEX] == "general")
            & (p[spec.COL_GEO_ID] == mr)
        ][spec.COL_Y_CASES].sum()
        assert int(sg) == int(rg)
