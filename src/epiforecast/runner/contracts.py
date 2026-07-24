"""F2/C2 — contratos tipados del runner: claves/specs congeladas + frames con validador de esquema.

Reutiliza el ÚNICO ``SeriesKey`` (``epi_dataset_spec``); no crea otra definición paralela.
- ``TrainingSpec`` (frozen): lo que un adapter de motor necesita para entrenar una serie.
- ``ForecastFrame`` / ``EvaluationFrame``: son DataFrames con un validador de esquema (no subclases),
  con columnas/tipos/invariantes exactos. Sin dependencias nuevas (solo pandas).

Los adapters aún no existen (C2): estos contratos fijan la forma; el runner los exige cuando haya
motor. Metadata de artefacto NUNCA re-infiere el padecimiento por ``stem.split('_')``.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from epiforecast.data.epi_dataset_spec import (
    COL_DS,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_FREQUENCY,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    FREQ_EPI_WEEK,
    GEO_LEVEL_ESTADO,
    GEO_LEVEL_NACIONAL,
    GEO_LEVEL_REGION,
    SeriesKey,
)

# Nombres de schema para la metadata de artefactos del manifiesto.
SCHEMA_DATASET = "epi_dataset_v2"
SCHEMA_PRODUCTS = "products.v1"
SCHEMA_FORECAST = "forecast.v1"
SCHEMA_EVALUATION = "evaluation.v1"

_GEO_LEVELS: frozenset[str] = frozenset({GEO_LEVEL_ESTADO, GEO_LEVEL_REGION, GEO_LEVEL_NACIONAL})
_SEXES: frozenset[str] = frozenset({"hombres", "mujeres", "general"})

# Columnas de identidad compartidas por todos los frames de productos/pronóstico/evaluación.
IDENTITY_COLUMNS: tuple[str, ...] = (COL_GEO_LEVEL, COL_GEO_ID, COL_SEX)

COL_ENGINE = "engine"
COL_YHAT = "yhat"
COL_YHAT_LOWER = "yhat_lower"
COL_YHAT_UPPER = "yhat_upper"
COL_FOLD = "fold"
COL_N_TEST = "n_test"
# Métricas de evaluación (sMAPE principal; selector sMAPE→MASE→RMSE es política de C3).
COL_SMAPE = "smape"
COL_MASE = "mase"
COL_RMSE = "rmse"
COL_MAE = "mae"
EVAL_METRICS: tuple[str, ...] = (COL_SMAPE, COL_MASE, COL_RMSE, COL_MAE)

FORECAST_COLUMNS: tuple[str, ...] = (
    COL_GEO_LEVEL,
    COL_GEO_ID,
    COL_SEX,
    COL_FREQUENCY,
    COL_EPI_YEAR,
    COL_EPI_WEEK,
    COL_DS,
    COL_ENGINE,
    COL_YHAT,
    COL_YHAT_LOWER,
    COL_YHAT_UPPER,
)
EVALUATION_COLUMNS: tuple[str, ...] = (
    COL_GEO_LEVEL,
    COL_GEO_ID,
    COL_SEX,
    COL_ENGINE,
    COL_FOLD,
    COL_N_TEST,
    *EVAL_METRICS,
)


class ContractError(ValueError):
    """Un frame no cumple el contrato de esquema (columnas/tipos/invariantes)."""


@dataclass(frozen=True)
class TrainingSpec:
    """Especificación congelada para entrenar UNA serie con UN motor (la consume un adapter)."""

    key: SeriesKey
    engine: str
    horizon_weeks: int
    profile_id: str
    profile_digest: str  # digest del perfil efectivo (reproducibilidad)
    transformations: tuple[str, ...] = ()  # transformaciones efectivas (log1p, tasa/100k, …)
    train_cutoff_ds: str | None = None  # origen OOS (ds ISO); None = serie completa

    def __post_init__(self) -> None:
        if self.key.frequency != FREQ_EPI_WEEK:
            raise ContractError(f"frecuencia no soportada: {self.key.frequency!r}")
        if not self.engine:
            raise ContractError("engine vacío")
        if self.horizon_weeks <= 0 or isinstance(self.horizon_weeks, bool):
            raise ContractError(f"horizon_weeks debe ser entero positivo: {self.horizon_weeks!r}")


@dataclass(frozen=True)
class ArtifactMeta:
    """Metadata de un artefacto de modelo: identidad EXPLÍCITA, nunca inferida del nombre."""

    artifact_schema_version: str
    disease_id: str
    key: SeriesKey
    engine: str
    profile_digest: str
    transformations: tuple[str, ...] = ()


def series_key_str(key: SeriesKey) -> str:
    """Clave canónica estable ``disease/level/geo/sex`` (coincide con el lineage de agregación)."""
    return f"{key.disease_id}/{key.geography_level}/{key.geography_id}/{key.sex}"


def _require_columns(df: pd.DataFrame, columns: tuple[str, ...], what: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ContractError(f"{what}: faltan columnas {missing}")


def _require_finite_nonneg(df: pd.DataFrame, cols: tuple[str, ...], what: str) -> None:
    for c in cols:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.isna().any():
            raise ContractError(f"{what}: {c} con valores no numéricos/NaN")
        if (s < 0).any() or not s.map(math.isfinite).all():
            raise ContractError(f"{what}: {c} con valores negativos o no finitos")


def _require_valid_identity(df: pd.DataFrame, what: str) -> None:
    bad_lvl = set(df[COL_GEO_LEVEL].unique()) - _GEO_LEVELS
    if bad_lvl:
        raise ContractError(f"{what}: geography_level inválido {sorted(bad_lvl)}")
    bad_sex = set(df[COL_SEX].unique()) - _SEXES
    if bad_sex:
        raise ContractError(f"{what}: sex inválido {sorted(bad_sex)}")


def validate_forecast_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Valida un ``ForecastFrame`` (schema ``forecast.v1``). Devuelve el frame o levanta."""
    what = "ForecastFrame"
    _require_columns(df, FORECAST_COLUMNS, what)
    _require_valid_identity(df, what)
    if (df[COL_FREQUENCY] != FREQ_EPI_WEEK).any():
        raise ContractError(f"{what}: frequency debe ser {FREQ_EPI_WEEK!r}")
    if df[COL_ENGINE].astype(str).str.len().eq(0).any():
        raise ContractError(f"{what}: engine vacío")
    for c in (COL_YHAT, COL_YHAT_LOWER, COL_YHAT_UPPER):
        s = pd.to_numeric(df[c], errors="coerce")
        if s.isna().any() or not s.map(math.isfinite).all():
            raise ContractError(f"{what}: {c} con NaN/no finito")
    lo = pd.to_numeric(df[COL_YHAT_LOWER])
    hi = pd.to_numeric(df[COL_YHAT_UPPER])
    yh = pd.to_numeric(df[COL_YHAT])
    if not ((lo <= yh) & (yh <= hi)).all():
        raise ContractError(f"{what}: se viola yhat_lower <= yhat <= yhat_upper")
    key = [*IDENTITY_COLUMNS, COL_ENGINE, COL_EPI_YEAR, COL_EPI_WEEK]
    if df.duplicated(key).any():
        raise ContractError(f"{what}: filas duplicadas por {key}")
    return df


def validate_evaluation_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Valida un ``EvaluationFrame`` (schema ``evaluation.v1``). Devuelve el frame o levanta."""
    what = "EvaluationFrame"
    _require_columns(df, EVALUATION_COLUMNS, what)
    _require_valid_identity(df, what)
    if df[COL_ENGINE].astype(str).str.len().eq(0).any():
        raise ContractError(f"{what}: engine vacío")
    n = pd.to_numeric(df[COL_N_TEST], errors="coerce")
    if n.isna().any() or (n < 1).any():
        raise ContractError(f"{what}: n_test debe ser >= 1")
    _require_finite_nonneg(df, EVAL_METRICS, what)
    key = [*IDENTITY_COLUMNS, COL_ENGINE, COL_FOLD]
    if df.duplicated(key).any():
        raise ContractError(f"{what}: filas duplicadas por {key}")
    return df
