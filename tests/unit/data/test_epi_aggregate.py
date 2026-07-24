"""F2/C2 — agregación 64→111: unidades SINTÉTICAS (catálogo trackeado, sin datos gitignored).

Construye una base sintética de 32 estados × 2 sexos × N periodos usando el catálogo real
(CI-safe) y verifica conteos, identidades aritméticas, observed=all(), unión de flags y lineage.
El gate real E66 (72,483/111/47) vive en integration.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from epiforecast.data import epi_aggregate as agg
from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data.epi_geo_exposure import load_geo_catalog

_PERIODS = [
    (2026, 1, date(2026, 1, 5), date(2026, 1, 5)),
    (2026, 2, date(2026, 1, 12), date(2026, 1, 12)),
    (2026, 3, date(2026, 1, 19), date(2026, 1, 19)),
]


@pytest.fixture(scope="module")
def catalog():
    return load_geo_catalog()  # config trackeado → CI-safe


def _base(catalog) -> pd.DataFrame:
    """64 series base (32 estados × 2 sexos) × 3 periodos, medidas deterministas."""
    rows: list[dict[str, object]] = []
    for i, cve in enumerate(catalog.cve_ents()):
        for j, sexo in enumerate(spec.BASE_SEXES):
            expo = 1000 + i * 10 + j  # estática por (cve, sexo)
            for yy, ww, ps, ds in _PERIODS:
                rows.append(
                    {
                        spec.COL_DISEASE_ID: "obesidad",
                        spec.COL_CVE_ENT: cve,
                        spec.COL_SEXO: sexo,
                        spec.COL_EPI_YEAR: yy,
                        spec.COL_EPI_WEEK: ww,
                        spec.COL_PERIOD_START: ps,
                        spec.COL_DS: ds,
                        spec.COL_Y_CASES: i + j + ww,
                        spec.COL_EXPOSURE: expo,
                        spec.COL_OBSERVED: True,
                        spec.COL_QUALITY_FLAGS: "",
                    }
                )
    return pd.DataFrame(rows)


def test_merge_quality_flags_orden_canonico():
    # Unión ordenada por QUALITY_FLAG_ORDER; dedup; desconocidas al final alfabéticas; '' vacío.
    assert spec.merge_quality_flags(["", None]) == ""  # type: ignore[list-item]
    out = spec.merge_quality_flags(["total_imputed|sex_fallback_half", "source_missing", "zzz"])
    assert out == "source_missing|total_imputed|sex_fallback_half|zzz"


def test_conteos_y_esquema(catalog):
    res = agg.build_products(_base(catalog), catalog, "obesidad")
    assert res.counts == {"products": 111, "base": 64, "derived": 47, "periods": 3, "rows": 333}
    assert len(res.products) == 333
    assert list(res.products.columns) == list(spec.PRODUCT_COLUMNS)
    assert res.products.duplicated(list(spec.PRODUCT_KEY)).sum() == 0
    # 47 derivados × 3 periodos = 141 filas derivadas.
    assert len(res.products) - 64 * 3 == 47 * 3


def test_niveles_y_sexos(catalog):
    p = agg.build_products(_base(catalog), catalog, "obesidad").products
    series = p.groupby([spec.COL_GEO_LEVEL, spec.COL_GEO_ID, spec.COL_SEX]).ngroups
    assert series == 111
    counts = p.groupby(spec.COL_GEO_LEVEL)[[spec.COL_GEO_ID, spec.COL_SEX]].apply(
        lambda d: d.drop_duplicates().shape[0]
    )
    assert counts["estado"] == 96 and counts["region"] == 12 and counts["nacional"] == 3  # 32×3
    assert set(p[spec.COL_SEX].unique()) == {"hombres", "mujeres", "general"}
    assert set(p[p[spec.COL_GEO_LEVEL] == "region"][spec.COL_GEO_ID]) == {
        "norte",
        "occidente",
        "centro",
        "sureste",
    }
    assert set(p[p[spec.COL_GEO_LEVEL] == "nacional"][spec.COL_GEO_ID]) == {"mx"}


def test_identidades_aritmeticas(catalog):
    base = _base(catalog)
    p = agg.build_products(base, catalog, "obesidad").products

    def val(level, geo, sex, ww, col=spec.COL_Y_CASES):
        m = p[
            (p[spec.COL_GEO_LEVEL] == level)
            & (p[spec.COL_GEO_ID] == geo)
            & (p[spec.COL_SEX] == sex)
            & (p[spec.COL_EPI_WEEK] == ww)
        ]
        return int(m[col].iloc[0])

    # Nacional general (semana 1) == suma directa de las 64 bases (semana 1).
    total_w1 = int(base[base[spec.COL_EPI_WEEK] == 1][spec.COL_Y_CASES].sum())
    assert val("nacional", "mx", "general", 1) == total_w1
    # general == H + M en nacional y en un estado.
    assert val("nacional", "mx", "general", 1) == val("nacional", "mx", "hombres", 1) + val(
        "nacional", "mx", "mujeres", 1
    )
    assert val("estado", "05", "general", 2) == val("estado", "05", "hombres", 2) + val(
        "estado", "05", "mujeres", 2
    )
    # Región norte H (semana 1) == suma de las bases H de sus estados.
    norte = catalog.states_in_macroregion("norte")
    expected = int(
        base[
            (base[spec.COL_EPI_WEEK] == 1)
            & (base[spec.COL_SEXO] == "hombres")
            & (base[spec.COL_CVE_ENT].isin(norte))
        ][spec.COL_Y_CASES].sum()
    )
    assert val("region", "norte", "hombres", 1) == expected
    # Exposición: nacional general == suma de todas las exposiciones base (una semana).
    expo_total = int(base[base[spec.COL_EPI_WEEK] == 1][spec.COL_EXPOSURE].sum())
    assert val("nacional", "mx", "general", 1, spec.COL_EXPOSURE) == expo_total


def test_observed_all_y_flags_union(catalog):
    base = _base(catalog)
    # Un contribuyente base no observado + con bandera en (cve 01, hombres, semana 1).
    mask = (
        (base[spec.COL_CVE_ENT] == "01")
        & (base[spec.COL_SEXO] == "hombres")
        & (base[spec.COL_EPI_WEEK] == 1)
    )
    base.loc[mask, spec.COL_OBSERVED] = False
    base.loc[mask, spec.COL_QUALITY_FLAGS] = "total_imputed"
    p = agg.build_products(base, catalog, "obesidad").products

    def row(level, geo, sex, ww):
        return p[
            (p[spec.COL_GEO_LEVEL] == level)
            & (p[spec.COL_GEO_ID] == geo)
            & (p[spec.COL_SEX] == sex)
            & (p[spec.COL_EPI_WEEK] == ww)
        ].iloc[0]

    # observed se propaga como all(): el nacional general y hombres (semana 1) quedan no-observados.
    assert row("nacional", "mx", "general", 1)[spec.COL_OBSERVED] == False  # noqa: E712
    assert row("nacional", "mx", "hombres", 1)[spec.COL_OBSERVED] == False  # noqa: E712
    # ...pero la semana 2 (sin el contribuyente marcado) permanece observada.
    assert row("nacional", "mx", "general", 2)[spec.COL_OBSERVED] == True  # noqa: E712
    # La bandera aparece en la unión ordenada del agregado.
    assert "total_imputed" in row("nacional", "mx", "general", 1)[spec.COL_QUALITY_FLAGS]
    assert row("estado", "01", "general", 1)[spec.COL_QUALITY_FLAGS] == "total_imputed"


def test_lineage(catalog):
    lin = agg.build_products(_base(catalog), catalog, "obesidad").lineage
    assert len(lin) == 47  # solo derivados, no las 64 bases
    assert lin["obesidad/estado/05/general"] == [
        "obesidad/estado/05/hombres",
        "obesidad/estado/05/mujeres",
    ]
    assert lin["obesidad/nacional/mx/general"] == [
        f"obesidad/estado/{c}/{s}" for c in catalog.cve_ents() for s in spec.BASE_SEXES
    ]
    assert len(lin["obesidad/nacional/mx/hombres"]) == 32
    norte = catalog.states_in_macroregion("norte")
    assert lin["obesidad/region/norte/hombres"] == [f"obesidad/estado/{c}/hombres" for c in norte]
    assert len(lin["obesidad/region/norte/general"]) == len(norte) * 2


def test_base_incompleta_levanta(catalog):
    base = _base(catalog)
    base = base[base[spec.COL_CVE_ENT] != "32"]  # falta un estado → 62 series base
    with pytest.raises(agg.AggregateError):
        agg.build_products(base, catalog, "obesidad")


def test_validate_detecta_inconsistencia(catalog):
    # _validate debe atrapar una violación aritmética inyectada en el frame de productos.
    p = agg.build_products(_base(catalog), catalog, "obesidad").products
    p = p.copy()
    idx = p[(p[spec.COL_GEO_LEVEL] == "nacional") & (p[spec.COL_SEX] == "general")].index[0]
    p.loc[idx, spec.COL_Y_CASES] = int(p.loc[idx, spec.COL_Y_CASES]) + 7
    with pytest.raises(agg.AggregateError):
        agg._validate(p, catalog)
