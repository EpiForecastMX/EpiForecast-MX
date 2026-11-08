"""Esquema de sexo de un padecimiento, desde el registry (única fuente de verdad)."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from epiforecast import registry
from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data.epi_dataset_spec import (
    SCHEME_POR_SEXO,
    SCHEME_TOTAL,
    ExposureSnapshot,
    SexScheme,
)


def scheme_for(disease: str) -> SexScheme:
    """``SCHEME_TOTAL`` si el registry declara ``sex_breakdown: false``; si no, por sexo."""
    return SCHEME_POR_SEXO if registry.require(disease).sex_breakdown else SCHEME_TOTAL


_SEX_FLAGS = frozenset(
    {
        spec.QualityFlag.SEX_DELTA_TOTAL_MISMATCH,
        spec.QualityFlag.SEX_FALLBACK_STATE_13W,
        spec.QualityFlag.SEX_FALLBACK_NATIONAL,
        spec.QualityFlag.SEX_FALLBACK_HALF,
    }
)


def sin_banderas_de_sexo(flags: str) -> str:
    """Quita las banderas de reparto por sexo, que no aplican a una serie sin desglose."""
    return "|".join(f for f in str(flags).split("|") if f and f not in _SEX_FLAGS)


def exposure_for_sex(snapshot: ExposureSnapshot, cve: str, sexo: str) -> int:
    """Exposición de la serie; «general» sin columna propia usa la columna total del snapshot."""
    if sexo == spec.SEX_GENERAL and sexo not in snapshot.columns_by_sex:
        if not snapshot.total_column:
            raise ValueError("sin columna total de exposición para una serie sin sexo")
        return snapshot.by_cve_ent[cve][snapshot.total_column]
    return snapshot.exposure_for(cve, sexo)


def base_sexes_of(sexes: Iterable[object]) -> tuple[str, ...]:
    """Sexos base de un conjunto observado: hombres y mujeres si aparecen; si no, «general»."""
    vistos = {str(s) for s in sexes}
    return spec.BASE_SEXES if vistos & set(spec.BASE_SEXES) else (spec.SEX_GENERAL,)


def base_mask(
    frame: pd.DataFrame,
    level_col: str = spec.COL_GEO_LEVEL,
    sex_col: str = spec.COL_SEX,
) -> pd.Series:
    """Filas de series base (estado × sexo base) de un frame de productos, sea cual sea el esquema."""
    estado = frame[level_col] == spec.GEO_LEVEL_ESTADO
    return estado & frame[sex_col].isin(base_sexes_of(frame.loc[estado, sex_col].unique()))


def n_bases_of(sexes: Iterable[object], n_states: int = 32) -> int:
    """Número de series base esperado para los sexos observados."""
    return n_states * len(base_sexes_of(sexes))


def scheme_of(sexes: Iterable[object]) -> SexScheme:
    """Esquema a partir de los sexos base observados (sin consultar el registry)."""
    return spec.scheme_from_sexes(base_sexes_of(sexes))
