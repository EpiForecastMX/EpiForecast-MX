"""F1/C1 — especificación TIPADA de EpiDatasetV2 (schema, quality flags, claves, config).

Sin I/O ni lógica de reconciliación: solo tipos, constantes y contenedores inmutables que comparten
la reconciliación pura, la capa de exposición/geografía y la orquestación. Es el carril NUEVO de
Obesidad/E66; no toca el pipeline productivo (neuro/Dengue byte-idéntico).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

# ── Sexos base (se entrenan 32 estados × 2 sexos = 64 series) ──
SEX_HOMBRES = "hombres"
SEX_MUJERES = "mujeres"
BASE_SEXES: tuple[str, str] = (SEX_HOMBRES, SEX_MUJERES)

# El mapeo sexo → columna de exposición NO se hard-codea aquí: vive en config/exposicion.yaml
# (``columns_by_sex``) y viaja en ``ExposureSnapshot.columns_by_sex``.


# ── Quality flags (causales; se acumulan por observación como conjunto ordenado) ──
class QualityFlag:
    """Marcas de calidad reproducibles. Nunca se borra evidencia: se anota."""

    SOURCE_MISSING = "source_missing"  # periodo fuente ausente (colapso 32/32 en cero)
    TOTAL_IMPUTED = "total_imputed"  # Casos_semana imputado causalmente
    PREDECESSOR_SNAPSHOT_INVALID = "predecessor_snapshot_invalid"  # baseline previo inválido
    SEX_DELTA_TOTAL_MISMATCH = "sex_delta_total_mismatch"  # dH+dM != Casos_semana
    SEX_FALLBACK_STATE_13W = "sex_fallback_state_13w"  # mediana 13 sem del estado
    SEX_FALLBACK_NATIONAL = "sex_fallback_national"  # proporción nacional previa
    SEX_FALLBACK_HALF = "sex_fallback_half"  # 0.5 sin historia
    NEGATIVE_SOURCE = "negative_source"  # valor fuente negativo (revisión) conservado
    NOT_SPECIFIED = "not_specified"  # n.e. en la fuente


# Orden canónico de las banderas para la unión ordenada de los agregados (F2/C2).
QUALITY_FLAG_ORDER: tuple[str, ...] = (
    QualityFlag.SOURCE_MISSING,
    QualityFlag.TOTAL_IMPUTED,
    QualityFlag.PREDECESSOR_SNAPSHOT_INVALID,
    QualityFlag.SEX_DELTA_TOTAL_MISMATCH,
    QualityFlag.SEX_FALLBACK_STATE_13W,
    QualityFlag.SEX_FALLBACK_NATIONAL,
    QualityFlag.SEX_FALLBACK_HALF,
    QualityFlag.NEGATIVE_SOURCE,
    QualityFlag.NOT_SPECIFIED,
)
_FLAG_RANK: dict[str, int] = {f: i for i, f in enumerate(QUALITY_FLAG_ORDER)}


def merge_quality_flags(flag_strings: Iterable[str]) -> str:
    """Unión ORDENADA (canónica) de banderas '|'-separadas de varios contribuyentes.

    Deduplica, ordena las conocidas por ``QUALITY_FLAG_ORDER`` y agrega cualquier bandera
    desconocida al final en orden alfabético (determinista). '' si no hay banderas.
    """
    seen: set[str] = set()
    for s in flag_strings:
        if not s:
            continue
        for tok in str(s).split("|"):
            t = tok.strip()
            if t:
                seen.add(t)
    known = sorted((f for f in seen if f in _FLAG_RANK), key=lambda f: _FLAG_RANK[f])
    unknown = sorted(f for f in seen if f not in _FLAG_RANK)
    return "|".join([*known, *unknown])


# ── Nombres de columnas del dataset base (largo) ──
COL_DISEASE_ID = "disease_id"
COL_CVE_ENT = "cve_ent"
COL_ENTIDAD_CANONICA = "entidad_canonica"
COL_ENTIDAD_INEGI = "entidad_inegi"
COL_SOURCE_YEAR = "source_year"
COL_SOURCE_WEEK = "source_week"
COL_EPI_YEAR = "epi_year"
COL_EPI_WEEK = "epi_week"
COL_PERIOD_START = "period_start"
COL_DS = "ds"
COL_SEXO = "sexo"
COL_Y_CASES = "y_cases"
COL_EXPOSURE = "exposure"
COL_OBSERVED = "observed"
COL_TOTAL_SOURCE = "total_source"
COL_TOTAL_RECONCILED = "total_reconciled"
COL_SEX_PROP_SOURCE = "sex_prop_source"
COL_SEX_PROP_APPLIED = "sex_prop_applied"
COL_SEX_DELTA_TOTAL = "sex_delta_total"
COL_SEX_DELTA_RESIDUAL = "sex_delta_residual"
COL_QUALITY_FLAGS = "quality_flags"

# Claves de identidad (nunca deben duplicarse).
STATE_KEY: tuple[str, ...] = (COL_EPI_YEAR, COL_EPI_WEEK, COL_CVE_ENT)
BASE_KEY: tuple[str, ...] = (COL_EPI_YEAR, COL_EPI_WEEK, COL_CVE_ENT, COL_SEXO)

# ── Productos derivados (F2/C2): niveles/identidad geográfica y sexo agregado ──
SEX_GENERAL = "general"  # H + M (nivel agregado; nunca se entrena directo)
ALL_SEXES: tuple[str, str, str] = (SEX_HOMBRES, SEX_MUJERES, SEX_GENERAL)

GEO_LEVEL_ESTADO = "estado"
GEO_LEVEL_REGION = "region"  # macrorregión (norte|occidente|centro|sureste)
GEO_LEVEL_NACIONAL = "nacional"
NATIONAL_GEO_ID = "mx"
FREQ_EPI_WEEK = "epi_week"

# Columnas del frame de PRODUCTOS: SeriesKey + tiempo + medidas. Sin columnas de
# reconciliación (viven en el dataset base) ni lineage por fila (va en el manifest).
COL_GEO_LEVEL = "geography_level"
COL_GEO_ID = "geography_id"
COL_SEX = "sex"
COL_FREQUENCY = "frequency"

PRODUCT_KEY: tuple[str, ...] = (COL_GEO_LEVEL, COL_GEO_ID, COL_SEX, COL_EPI_YEAR, COL_EPI_WEEK)
PRODUCT_COLUMNS: tuple[str, ...] = (
    COL_DISEASE_ID,
    COL_GEO_LEVEL,
    COL_GEO_ID,
    COL_SEX,
    COL_FREQUENCY,
    COL_EPI_YEAR,
    COL_EPI_WEEK,
    COL_PERIOD_START,
    COL_DS,
    COL_Y_CASES,
    COL_EXPOSURE,
    COL_OBSERVED,
    COL_QUALITY_FLAGS,
)

BASE_COLUMNS: tuple[str, ...] = (
    COL_DISEASE_ID,
    COL_CVE_ENT,
    COL_ENTIDAD_CANONICA,
    COL_ENTIDAD_INEGI,
    COL_SOURCE_YEAR,
    COL_SOURCE_WEEK,
    COL_EPI_YEAR,
    COL_EPI_WEEK,
    COL_PERIOD_START,
    COL_DS,
    COL_SEXO,
    COL_Y_CASES,
    COL_EXPOSURE,
    COL_OBSERVED,
    COL_TOTAL_SOURCE,
    COL_TOTAL_RECONCILED,
    COL_SEX_PROP_SOURCE,
    COL_SEX_PROP_APPLIED,
    COL_SEX_DELTA_TOTAL,
    COL_SEX_DELTA_RESIDUAL,
    COL_QUALITY_FLAGS,
)


@dataclass(frozen=True)
class SeriesKey:
    """Identidad de una serie (F2 la reutiliza). Para las 64 base: geography_level='estado'."""

    disease_id: str
    geography_level: str  # estado | region | nacional
    geography_id: str  # cve_ent para estado
    sex: str  # hombres | mujeres | general
    frequency: str = "epi_week"


@dataclass(frozen=True)
class GeoEntity:
    """Entrada del catálogo geográfico trackeado (join estricto 1:1, sin fuzzy)."""

    cve_ent: str  # "01".."32"
    nombre_canonico: str
    nombre_inegi: str
    macroregion_id: str  # IDENTIDAD (norte|occidente|centro|sureste) → SeriesKey.geography_id
    macroregion_name: str  # display (Norte|Occidente|Centro|Sureste); no se deriva por slugify
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ExposureSnapshot:
    """Snapshot estático de exposición (CPV 2020) con su procedencia y digest."""

    source_id: str  # "inegi_cpv2020_static"
    reference: str  # "CPV 2020"
    cutoff: date  # 2020-03-15
    columns_by_sex: dict[str, str]  # {"hombres":"Hombres","mujeres":"Mujeres"}
    total_column: str | None  # "Total" (para verificar H+M=Total)
    digest: str  # sha256 del archivo fuente
    by_cve_ent: dict[str, dict[str, int]]  # cve_ent -> {"Hombres":int,"Mujeres":int,"Total":int}

    def exposure_for(self, cve_ent: str, sexo: str) -> int:
        """Exposición del ``(cve_ent, sexo)`` vía ``columns_by_sex`` (no hard-code)."""
        return self.by_cve_ent[cve_ent][self.columns_by_sex[sexo]]


@dataclass(frozen=True)
class EpiDatasetConfig:
    """Config del carril EpiDatasetV2 leída del registry/cuadros (no hard-code)."""

    disease_id: str
    observation_lag_weeks: int
    exposure_source_id: str
    expected_n_states: int
