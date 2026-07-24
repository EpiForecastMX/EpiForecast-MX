"""F2/C3.2 — contratos DEFINITIVOS del runner: specs congeladas + frames fila-a-fila validados.

Reutiliza el ÚNICO ``SeriesKey`` (``epi_dataset_spec``); no crea otra definición paralela.
- ``TrainingSpec`` (frozen): lo que un adapter necesita para entrenar/predecir UNA de las 64 bases
  (estado×sexo). Lleva dataset/policy digests, fold, seed, horizonte, ``TransformContract``,
  parámetros namespaced del motor y límites de recursos. SOLO admite claves estado×{hombres,mujeres}.
- ``ForecastFrame`` (``forecast.v1``): predicción FILA A FILA (run/motor/fold/origen/horizonte/
  SeriesKey/periodo/y_pred_cases); intervalos conjuntamente nulos o válidos, no negativos.
- ``EvaluationFrame`` (``evaluation.v1``): unión FILA A FILA verdad↔predicción (y_true/y_pred/split/
  procedencia).
- ``MetricFrame`` (``metrics.v1``): resumen SEPARADO por motor/fold/producto (sMAPE/MASE/MAE/RMSE/
  WAPE/bias); métricas con denominador cero quedan NaN + flag, nunca inf.

Negativos, no-finitos o duplicados invalidan el frame (→ motor/fold). Metadata de artefacto NUNCA
re-infiere el padecimiento por ``stem.split('_')``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

import pandas as pd

from epiforecast import registry
from epiforecast.artifacts.transforms import TargetSpace, TransformContract, TransformStep
from epiforecast.data.epi_dataset_spec import (
    BASE_SEXES,
    COL_DS,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    FREQ_EPI_WEEK,
    GEO_LEVEL_ESTADO,
    GEO_LEVEL_NACIONAL,
    GEO_LEVEL_REGION,
    SeriesKey,
)

# Schemas de artefactos (metadata del manifiesto).
SCHEMA_DATASET = "epi_dataset_v2"
SCHEMA_PRODUCTS = "products.v1"
SCHEMA_FORECAST = "forecast.v1"
SCHEMA_EVALUATION = "evaluation.v1"
SCHEMA_METRICS = "metrics.v1"

_GEO_LEVELS: frozenset[str] = frozenset({GEO_LEVEL_ESTADO, GEO_LEVEL_REGION, GEO_LEVEL_NACIONAL})
_SEXES: frozenset[str] = frozenset({"hombres", "mujeres", "general"})

# Splits de evaluación (grupos de folds de la política).
SPLIT_DEVELOPMENT = "development"
SPLIT_TEST = "test"
SPLIT_STRESS = "stress"
SPLIT_PROSPECTIVE = "prospective"
SPLITS: frozenset[str] = frozenset(
    {SPLIT_DEVELOPMENT, SPLIT_TEST, SPLIT_STRESS, SPLIT_PROSPECTIVE}
)

# Identidad (SeriesKey materializado en columnas).
IDENTITY_COLUMNS: tuple[str, ...] = (COL_GEO_LEVEL, COL_GEO_ID, COL_SEX)

COL_RUN_ID = "run_id"
COL_ENGINE = "engine"
COL_FOLD = "fold"
COL_SPLIT = "split"
COL_ORIGIN_EPI_YEAR = "origin_epi_year"
COL_ORIGIN_EPI_WEEK = "origin_epi_week"
COL_HORIZON = "horizon"
COL_Y_PRED = "y_pred_cases"
COL_Y_TRUE = "y_true_cases"
COL_YHAT_LOWER = "yhat_lower"
COL_YHAT_UPPER = "yhat_upper"
COL_N_OBS = "n_obs"
COL_FLAGS = "flags"

# Métricas (sMAPE principal; selector sMAPE→MASE→RMSE es política de C3+).
COL_SMAPE = "smape"
COL_MASE = "mase"
COL_MAE = "mae"
COL_RMSE = "rmse"
COL_WAPE = "wape"
COL_BIAS = "bias"
METRIC_COLUMNS_VALUES: tuple[str, ...] = (
    COL_SMAPE,
    COL_MASE,
    COL_MAE,
    COL_RMSE,
    COL_WAPE,
    COL_BIAS,
)

_PROVENANCE: tuple[str, ...] = (COL_RUN_ID, COL_ENGINE, COL_FOLD)
_IDENTITY_FULL: tuple[str, ...] = ("disease_id", COL_GEO_LEVEL, COL_GEO_ID, COL_SEX)
_PERIOD: tuple[str, ...] = (COL_EPI_YEAR, COL_EPI_WEEK, COL_DS)

FORECAST_COLUMNS: tuple[str, ...] = (
    *_PROVENANCE,
    COL_ORIGIN_EPI_YEAR,
    COL_ORIGIN_EPI_WEEK,
    COL_HORIZON,
    *_IDENTITY_FULL,
    *_PERIOD,
    COL_Y_PRED,
    COL_YHAT_LOWER,
    COL_YHAT_UPPER,
)
EVALUATION_COLUMNS: tuple[str, ...] = (
    *_PROVENANCE,
    COL_SPLIT,
    COL_HORIZON,
    *_IDENTITY_FULL,
    *_PERIOD,
    COL_Y_TRUE,
    COL_Y_PRED,
)
METRIC_COLUMNS: tuple[str, ...] = (
    COL_ENGINE,
    COL_FOLD,
    COL_SPLIT,
    *_IDENTITY_FULL,
    COL_N_OBS,
    *METRIC_COLUMNS_VALUES,
    COL_FLAGS,
)


class ContractError(ValueError):
    """Un spec o frame no cumple el contrato (columnas/tipos/invariantes)."""


def identity_transform(disease_id: str, engine: str) -> TransformContract:
    """TransformContract IDENTIDAD (count→count, sin pasos): predice conteos directos."""
    return TransformContract(
        disease_id=disease_id,
        engine_id=engine,
        source_space=TargetSpace.COUNT,
        target_space=TargetSpace.COUNT,
        forward_steps=(),
        inverse_steps=(),
        rate_scale=None,
    )


def log1p_transform(disease_id: str, engine: str) -> TransformContract:
    """TransformContract log1p (count→transformed); la inversa expm1 la gobierna el contrato."""
    return TransformContract(
        disease_id=disease_id,
        engine_id=engine,
        source_space=TargetSpace.COUNT,
        target_space=TargetSpace.TRANSFORMED,
        forward_steps=(TransformStep.LOG1P,),
        inverse_steps=(TransformStep.EXPM1,),
        rate_scale=None,
    )


def rate_log1p_transform(disease_id: str, engine: str) -> TransformContract:
    """TransformContract tasa+log1p (count→rate→transformed→expm1→count).

    La escala de tasa NO se hardcodea: sale del perfil del registry del padecimiento (única
    fuente de verdad, la misma que usa ``resolve_transform_contract``).
    """
    spec = registry.require(disease_id)
    if spec.profile.rate_scale is None:
        raise ContractError(f"perfil '{spec.profile_name}' no declara rate_scale (tasa imposible)")
    return TransformContract(
        disease_id=disease_id,
        engine_id=engine,
        source_space=TargetSpace.COUNT,
        target_space=TargetSpace.TRANSFORMED,
        forward_steps=(TransformStep.RATE_PER_EXPOSURE, TransformStep.LOG1P),
        inverse_steps=(TransformStep.EXPM1, TransformStep.RATE_TO_COUNT),
        rate_scale=float(spec.profile.rate_scale),
    )


@dataclass(frozen=True)
class TrainingSpec:
    """Spec congelada para UNA de las 64 bases (estado×sexo). La consume un adapter de motor."""

    key: SeriesKey
    engine: str
    dataset_digest: str
    policy_name: str
    policy_digest: str
    fold_id: str
    seed: int
    horizon: int
    transform: TransformContract
    engine_params: dict[str, Any] = field(default_factory=dict)  # namespaced por motor
    resource_limits: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.key.geography_level != GEO_LEVEL_ESTADO or self.key.sex not in BASE_SEXES:
            raise ContractError(
                "TrainingSpec SOLO admite las 64 claves estado×{hombres,mujeres}: "
                f"{self.key.geography_level}/{self.key.sex}"
            )
        if self.key.frequency != FREQ_EPI_WEEK:
            raise ContractError(f"frecuencia no soportada: {self.key.frequency!r}")
        if not self.engine:
            raise ContractError("engine vacío")
        if isinstance(self.horizon, bool) or self.horizon <= 0:
            raise ContractError(f"horizon debe ser entero positivo: {self.horizon!r}")
        if self.transform.engine_id != self.engine:
            raise ContractError(
                f"transform.engine_id ({self.transform.engine_id}) != engine ({self.engine})"
            )


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


# ── Helpers de validación de frames ──
def _require_columns(df: pd.DataFrame, columns: tuple[str, ...], what: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ContractError(f"{what}: faltan columnas {missing}")


def _require_valid_identity(df: pd.DataFrame, what: str) -> None:
    bad_lvl = set(df[COL_GEO_LEVEL].unique()) - _GEO_LEVELS
    if bad_lvl:
        raise ContractError(f"{what}: geography_level inválido {sorted(bad_lvl)}")
    bad_sex = set(df[COL_SEX].unique()) - _SEXES
    if bad_sex:
        raise ContractError(f"{what}: sex inválido {sorted(bad_sex)}")


def _num_finite_nonneg(df: pd.DataFrame, col: str, what: str) -> pd.Series:
    s = pd.to_numeric(df[col], errors="coerce")
    if s.isna().any() or not s.map(math.isfinite).all():
        raise ContractError(f"{what}: {col} con NaN/no finito")
    if (s < 0).any():
        raise ContractError(f"{what}: {col} negativo")
    return s


def _require_no_dupes(df: pd.DataFrame, key: list[str], what: str) -> None:
    if df.duplicated(key).any():
        raise ContractError(f"{what}: filas duplicadas por {key}")


def validate_forecast_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Valida un ``ForecastFrame`` (schema ``forecast.v1``). Devuelve el frame o levanta."""
    what = "ForecastFrame"
    _require_columns(df, FORECAST_COLUMNS, what)
    _require_valid_identity(df, what)
    if df[COL_ENGINE].astype(str).str.len().eq(0).any():
        raise ContractError(f"{what}: engine vacío")
    if (pd.to_numeric(df[COL_HORIZON], errors="coerce") < 1).any():
        raise ContractError(f"{what}: horizon debe ser >= 1")
    y_pred = _num_finite_nonneg(df, COL_Y_PRED, what)

    lo_null = df[COL_YHAT_LOWER].isna()
    hi_null = df[COL_YHAT_UPPER].isna()
    if (lo_null != hi_null).any():
        raise ContractError(f"{what}: intervalos deben ser conjuntamente nulos o presentes")
    present = ~lo_null
    if present.any():
        lo = _num_finite_nonneg(df[present], COL_YHAT_LOWER, what)
        hi = _num_finite_nonneg(df[present], COL_YHAT_UPPER, what)
        if not ((lo <= y_pred[present]) & (y_pred[present] <= hi)).all():
            raise ContractError(f"{what}: se viola yhat_lower <= y_pred_cases <= yhat_upper")

    _require_no_dupes(df, [*_PROVENANCE, *IDENTITY_COLUMNS, COL_EPI_YEAR, COL_EPI_WEEK], what)
    return df


def validate_evaluation_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Valida un ``EvaluationFrame`` (schema ``evaluation.v1``). Devuelve el frame o levanta."""
    what = "EvaluationFrame"
    _require_columns(df, EVALUATION_COLUMNS, what)
    _require_valid_identity(df, what)
    bad_split = set(df[COL_SPLIT].unique()) - SPLITS
    if bad_split:
        raise ContractError(f"{what}: split inválido {sorted(bad_split)}")
    _num_finite_nonneg(df, COL_Y_TRUE, what)
    _num_finite_nonneg(df, COL_Y_PRED, what)
    _require_no_dupes(
        df, [COL_ENGINE, COL_FOLD, *IDENTITY_COLUMNS, COL_EPI_YEAR, COL_EPI_WEEK], what
    )
    return df


def validate_metric_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Valida un ``MetricFrame`` (schema ``metrics.v1``). Métricas NaN OK (flag); nunca inf."""
    what = "MetricFrame"
    _require_columns(df, METRIC_COLUMNS, what)
    _require_valid_identity(df, what)
    bad_split = set(df[COL_SPLIT].unique()) - SPLITS
    if bad_split:
        raise ContractError(f"{what}: split inválido {sorted(bad_split)}")
    if (pd.to_numeric(df[COL_N_OBS], errors="coerce") < 1).any():
        raise ContractError(f"{what}: n_obs debe ser >= 1")
    for col in METRIC_COLUMNS_VALUES:
        s = pd.to_numeric(df[col], errors="coerce")
        # NaN permitido (denominador cero → null + flag); inf NO.
        if s.notna().any() and not s.dropna().map(math.isfinite).all():
            raise ContractError(f"{what}: {col} con valor no finito (usar NaN + flag, nunca inf)")
    _require_no_dupes(df, [COL_ENGINE, COL_FOLD, *IDENTITY_COLUMNS], what)
    return df
