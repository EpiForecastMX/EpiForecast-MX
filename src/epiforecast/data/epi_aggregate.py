"""F2/C2 — derivación de los 111 productos desde las 64 series base (agregación aritmética pura).

TODO se deriva DIRECTAMENTE de las 64 bases (32 estados × 2 sexos); nunca de otro agregado:

- Estado general   = H + M del estado.                         (32 productos)
- Región H/M       = suma de las bases de los estados de la región, por sexo.
- Región general   = suma de las bases H/M de la región.       (4 regiones × 3 sexos = 12)
- Nacional H/M/gen = suma DIRECTA de las 64 bases.             (3 productos)

Más las 64 bases re-expresadas en el esquema de productos → 64 + 47 = **111 productos**.

La suma por regiones se usa como VALIDACIÓN del nacional, no como fuente primaria. ``observed`` se
deriva con ``all()`` de los contribuyentes; ``quality_flags`` como unión ordenada. El lineage
(qué bases componen cada derivado) va en el manifest, NO como lista repetida por fila.

Sin train, sin publicación, sin I/O de producción: frame de productos + lineage + validación con
tolerancia cero. Carril nuevo de Obesidad/E66; no toca el pipeline neuro/Dengue.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from epiforecast.data.epi_dataset_spec import (
    BASE_SEXES,
    COL_CVE_ENT,
    COL_DISEASE_ID,
    COL_DS,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_EXPOSURE,
    COL_FREQUENCY,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_OBSERVED,
    COL_PERIOD_START,
    COL_QUALITY_FLAGS,
    COL_SEX,
    COL_SEXO,
    COL_Y_CASES,
    FREQ_EPI_WEEK,
    GEO_LEVEL_ESTADO,
    GEO_LEVEL_NACIONAL,
    GEO_LEVEL_REGION,
    NATIONAL_GEO_ID,
    PRODUCT_COLUMNS,
    PRODUCT_KEY,
    SEX_GENERAL,
    SEX_HOMBRES,
    SEX_MUJERES,
    merge_quality_flags,
)
from epiforecast.data.epi_geo_exposure import GeoCatalog

_MACROREGION = "macroregion_id"
_TIME_COLS: list[str] = [COL_EPI_YEAR, COL_EPI_WEEK, COL_PERIOD_START, COL_DS]

# Conteos esperados de la partición (invariantes del carril E66).
N_BASE = 64
N_STATE_GENERAL = 32
N_REGIONAL = 12  # 4 macrorregiones × 3 sexos
N_NATIONAL = 3
N_DERIVED = N_STATE_GENERAL + N_REGIONAL + N_NATIONAL  # 47
N_PRODUCTS = N_BASE + N_DERIVED  # 111


class AggregateError(ValueError):
    """La agregación 64→111 violó una identidad aritmética o de conteo (tolerancia cero)."""


@dataclass(frozen=True)
class AggregateResult:
    """Productos derivados + lineage (para el manifest) + conteos de la partición."""

    products: pd.DataFrame  # 111 productos × periodos, esquema ``PRODUCT_COLUMNS``
    lineage: dict[str, list[str]]  # clave de producto derivado → claves base contribuyentes
    counts: dict[str, int]


def _combine(df: pd.DataFrame, id_cols: list[str]) -> pd.DataFrame:
    """Agrega ``df`` por ``id_cols`` + tiempo: y_cases/exposure = suma, observed = all(),
    quality_flags = unión ordenada. Devuelve las columnas de id + tiempo + medidas."""
    grouped = df.groupby([*id_cols, *_TIME_COLS], sort=False)
    out = grouped.agg(
        _y=(COL_Y_CASES, "sum"),
        _e=(COL_EXPOSURE, "sum"),
        _o=(COL_OBSERVED, "all"),
        _f=(COL_QUALITY_FLAGS, merge_quality_flags),
    ).reset_index()
    return out.rename(
        columns={
            "_y": COL_Y_CASES,
            "_e": COL_EXPOSURE,
            "_o": COL_OBSERVED,
            "_f": COL_QUALITY_FLAGS,
        }
    )


def _tier(
    df: pd.DataFrame,
    id_cols: list[str],
    level: str,
    geo_id: Callable[[pd.DataFrame], Any],
    sex: Callable[[pd.DataFrame], Any],
) -> pd.DataFrame:
    """Un nivel de agregación → filas en el esquema de productos."""
    out = _combine(df, id_cols)
    out[COL_GEO_LEVEL] = level
    out[COL_GEO_ID] = geo_id(out)
    out[COL_SEX] = sex(out)
    out[COL_FREQUENCY] = FREQ_EPI_WEEK
    return out[list(PRODUCT_COLUMNS)]


def _key(disease_id: str, level: str, geo_id: str, sex: str) -> str:
    return f"{disease_id}/{level}/{geo_id}/{sex}"


def _lineage(catalog: GeoCatalog, disease_id: str) -> dict[str, list[str]]:
    """Composición determinista de los 47 derivados (desde el catálogo, no desde datos)."""

    def base_key(cve: str, sx: str) -> str:
        return _key(disease_id, GEO_LEVEL_ESTADO, cve, sx)

    lin: dict[str, list[str]] = {}
    for cve in catalog.cve_ents():  # 32 estado-general
        lin[_key(disease_id, GEO_LEVEL_ESTADO, cve, SEX_GENERAL)] = [
            base_key(cve, SEX_HOMBRES),
            base_key(cve, SEX_MUJERES),
        ]
    for mr in catalog.macroregion_ids():  # 4 regiones × 3 sexos = 12
        states = catalog.states_in_macroregion(mr)
        for sx in BASE_SEXES:
            lin[_key(disease_id, GEO_LEVEL_REGION, mr, sx)] = [base_key(c, sx) for c in states]
        lin[_key(disease_id, GEO_LEVEL_REGION, mr, SEX_GENERAL)] = [
            base_key(c, sx) for c in states for sx in BASE_SEXES
        ]
    for sx in BASE_SEXES:  # 3 nacional
        lin[_key(disease_id, GEO_LEVEL_NACIONAL, NATIONAL_GEO_ID, sx)] = [
            base_key(c, sx) for c in catalog.cve_ents()
        ]
    lin[_key(disease_id, GEO_LEVEL_NACIONAL, NATIONAL_GEO_ID, SEX_GENERAL)] = [
        base_key(c, sx) for c in catalog.cve_ents() for sx in BASE_SEXES
    ]
    return lin


def build_products(base: pd.DataFrame, catalog: GeoCatalog, disease_id: str) -> AggregateResult:
    """Deriva los 111 productos desde las 64 bases y valida con tolerancia cero."""
    if base.groupby([COL_CVE_ENT, COL_SEXO]).ngroups != N_BASE:
        raise AggregateError(
            f"se esperaban {N_BASE} series base (32 estados × 2 sexos), "
            f"hay {base.groupby([COL_CVE_ENT, COL_SEXO]).ngroups}"
        )
    base_r = base.copy()
    base_r[_MACROREGION] = base[COL_CVE_ENT].map(catalog.macroregion_of)

    # 64 bases re-expresadas en el esquema de productos (estado, cve, sexo base).
    base_products = base.copy()
    base_products[COL_GEO_LEVEL] = GEO_LEVEL_ESTADO
    base_products[COL_GEO_ID] = base[COL_CVE_ENT]
    base_products[COL_SEX] = base[COL_SEXO]
    base_products[COL_FREQUENCY] = FREQ_EPI_WEEK
    base_products = base_products[list(PRODUCT_COLUMNS)]

    tiers = [
        base_products,
        _tier(  # 32 estado-general (H + M)
            base,
            [COL_DISEASE_ID, COL_CVE_ENT],
            GEO_LEVEL_ESTADO,
            lambda o: o[COL_CVE_ENT],
            lambda o: SEX_GENERAL,
        ),
        _tier(  # 8 región H/M (suma de estados de la región)
            base_r,
            [COL_DISEASE_ID, _MACROREGION, COL_SEXO],
            GEO_LEVEL_REGION,
            lambda o: o[_MACROREGION],
            lambda o: o[COL_SEXO],
        ),
        _tier(  # 4 región general (suma de las bases H/M de la región)
            base_r,
            [COL_DISEASE_ID, _MACROREGION],
            GEO_LEVEL_REGION,
            lambda o: o[_MACROREGION],
            lambda o: SEX_GENERAL,
        ),
        _tier(  # 2 nacional H/M (suma directa de las 64 bases)
            base,
            [COL_DISEASE_ID, COL_SEXO],
            GEO_LEVEL_NACIONAL,
            lambda o: NATIONAL_GEO_ID,
            lambda o: o[COL_SEXO],
        ),
        _tier(  # 1 nacional general (suma directa de las 64 bases)
            base,
            [COL_DISEASE_ID],
            GEO_LEVEL_NACIONAL,
            lambda o: NATIONAL_GEO_ID,
            lambda o: SEX_GENERAL,
        ),
    ]
    products = (
        pd.concat(tiers, ignore_index=True)
        .sort_values(
            [COL_DISEASE_ID, COL_GEO_LEVEL, COL_GEO_ID, COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK]
        )
        .reset_index(drop=True)
    )
    counts = _validate(products, catalog)
    return AggregateResult(products=products, lineage=_lineage(catalog, disease_id), counts=counts)


def _assert_equal(left: pd.Series, right: pd.Series, ctx: str) -> None:
    """Igualdad EXACTA (entera, tolerancia cero) alineada por índice; alineación completa."""
    aligned = pd.concat([left.rename("l"), right.rename("r")], axis=1)
    if aligned.isna().any().any():
        raise AggregateError(f"{ctx}: claves sin contraparte (alineación incompleta)")
    bad = aligned[aligned["l"] != aligned["r"]]
    if len(bad):
        raise AggregateError(
            f"{ctx}: {len(bad)} identidades no reconcilian (p.ej. {bad.index[0]})"
        )


def _sum_over(df: pd.DataFrame, group: list[str], value: str) -> pd.Series:
    return df.groupby(group, sort=True)[value].sum()


def _validate(products: pd.DataFrame, catalog: GeoCatalog) -> dict[str, int]:
    """Verifica partición, unicidad e identidades aritméticas de y_cases y exposición."""
    # Partición y unicidad de claves.
    if products.duplicated(list(PRODUCT_KEY)).any():
        raise AggregateError("claves de producto duplicadas")
    n_products = products.groupby([COL_GEO_LEVEL, COL_GEO_ID, COL_SEX]).ngroups
    if n_products != N_PRODUCTS:
        raise AggregateError(f"se esperaban {N_PRODUCTS} productos, hay {n_products}")
    per_series = products.groupby([COL_GEO_LEVEL, COL_GEO_ID, COL_SEX]).size().unique()
    if len(per_series) != 1:
        raise AggregateError(f"los productos no comparten el mismo nº de periodos: {per_series}")
    n_periods = int(per_series[0])

    # Exposición estática: constante por serie a lo largo de los periodos.
    if (
        not products.groupby([COL_GEO_LEVEL, COL_GEO_ID, COL_SEX])[COL_EXPOSURE]
        .nunique()
        .eq(1)
        .all()
    ):
        raise AggregateError("exposición no estática (varía dentro de una serie)")

    for value in (COL_Y_CASES, COL_EXPOSURE):
        # (a) Identidad de sexo en TODO nivel: general == hombres + mujeres.
        piv = products.pivot_table(
            index=[COL_GEO_LEVEL, COL_GEO_ID, COL_EPI_YEAR, COL_EPI_WEEK],
            columns=COL_SEX,
            values=value,
            aggfunc="sum",
        )
        _assert_equal(
            piv[SEX_GENERAL], piv[SEX_HOMBRES] + piv[SEX_MUJERES], f"{value}: general==H+M"
        )

        # (b) Estados de una región suman su región (estado-general → región-general).
        sg = products[
            (products[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO) & (products[COL_SEX] == SEX_GENERAL)
        ].assign(**{_MACROREGION: lambda d: d[COL_GEO_ID].map(catalog.macroregion_of)})
        rg = products[
            (products[COL_GEO_LEVEL] == GEO_LEVEL_REGION) & (products[COL_SEX] == SEX_GENERAL)
        ]
        _assert_equal(
            _sum_over(sg, [_MACROREGION, COL_EPI_YEAR, COL_EPI_WEEK], value),
            _sum_over(
                rg.rename(columns={COL_GEO_ID: _MACROREGION}),
                [_MACROREGION, COL_EPI_YEAR, COL_EPI_WEEK],
                value,
            ),
            f"{value}: Σ estados-región == región",
        )

        # (c) Las regiones suman el nacional, por sexo (VALIDACIÓN del nacional).
        reg = products[products[COL_GEO_LEVEL] == GEO_LEVEL_REGION]
        nat = products[products[COL_GEO_LEVEL] == GEO_LEVEL_NACIONAL]
        _assert_equal(
            _sum_over(reg, [COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK], value),
            _sum_over(nat, [COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK], value),
            f"{value}: Σ regiones == nacional",
        )

    return {
        "products": n_products,
        "base": N_BASE,
        "derived": N_DERIVED,
        "periods": n_periods,
        "rows": int(len(products)),
    }
