"""F1/C1 — orquestación EpiDatasetV2 (carril de releases del boletín; legacy intacto).

Ensambla el dataset base semanal de un padecimiento del boletín a partir del raw extraído, el
calendario epidemiológico, la reconciliación causal y la exposición estática, versionándolo en
``runs/<run_id>/`` con digests separados (raw / exposición / config / dataset) e insumos efectivos.
Pipeline: raw → ``epi_lag_schedule.build_prep`` (rezago constante o por periodo) + geo →
``reconcile_state`` → ``explode_base`` con exposición por esquema de sexo (``columns_by_sex`` / ``total_column``, sin hard-code).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
from typing import Any, SupportsFloat, SupportsInt, cast

from omegaconf import OmegaConf
import pandas as pd

from epiforecast import registry
from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data.epi_dataset_io import assemble_dataset_artifacts, stage_dataset_run
from epiforecast.data.epi_dataset_spec import ExposureSnapshot
from epiforecast.data.epi_geo_exposure import (
    GeoCatalog,
    geo_catalog_path,
    load_exposure_snapshot,
    load_geo_catalog,
)
from epiforecast.data.epi_lag_schedule import (
    LagScheduleError,
    mark_gap_rows,
    schedule_from_group,
)
from epiforecast.data.epi_lag_schedule import (
    build_prep as build_prep,  # re-exportado: API histórica de este módulo
)
from epiforecast.data.epi_reconcile import reconcile_state
from epiforecast.data.sex_scheme import exposure_for_sex, scheme_for, sin_banderas_de_sexo

_ROOT = Path(__file__).resolve().parents[3]
# Orden canónico ESTABLE (serie contigua) antes de digestar.
_CANONICAL_ORDER = [spec.COL_CVE_ENT, spec.COL_SEXO, spec.COL_EPI_YEAR, spec.COL_EPI_WEEK]


class EpiDatasetError(ValueError):
    """Config o insumos inválidos para EpiDatasetV2."""


@dataclass(frozen=True)
class EpiDatasetV2Result:
    run_id: str
    run_dir: Path
    dataset: pd.DataFrame  # filas base en orden canónico
    state: pd.DataFrame  # filas estatales reconciliadas
    config: spec.EpiDatasetConfig
    snapshot: ExposureSnapshot
    digests: dict[str, str]  # raw / exposure / config / dataset


_NAN = float("nan")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _i(v: object) -> int:  # itertuples expone campos con tipo laxo
    return int(cast("SupportsInt", v))


def _f(v: object) -> float:
    return float(cast("SupportsFloat", v))


def _cuadros_group(group_id: str) -> dict[str, Any]:
    raw = cast(
        "dict[str, Any]",
        OmegaConf.to_container(
            OmegaConf.load(_ROOT / "config" / "data" / "cuadros.yaml"), resolve=True
        ),
    )
    groups = raw.get("cuadro_groups", {})
    if group_id not in groups:
        raise EpiDatasetError(f"grupo de cuadro desconocido: {group_id}")
    return cast("dict[str, Any]", groups[group_id])


def load_config(disease: str) -> spec.EpiDatasetConfig:
    """Config efectiva desde registry (exposure_source_id) + grupo de cuadro (lag, n_states)."""
    d = registry.require(disease)
    if not d.exposure_source_id:
        raise EpiDatasetError(
            f"{d.data_name}: EpiDatasetV2 exige exposure_source_id en el registry"
        )
    group = _cuadros_group(d.extraction_group)
    try:
        schedule = schedule_from_group(group)
    except LagScheduleError as exc:
        raise EpiDatasetError(str(exc)) from exc
    n_states = group.get("n_states_expected")
    if isinstance(n_states, bool) or not isinstance(n_states, int) or n_states <= 0:
        raise EpiDatasetError(f"n_states_expected inválido: {n_states!r}")
    return spec.EpiDatasetConfig(
        disease_id=d.id,  # id del registry (invariante N+1); NO el slug (coinciden en Obesidad)
        observation_lag_weeks=schedule.vigente,
        exposure_source_id=d.exposure_source_id,
        expected_n_states=n_states,
        lag_schedule=schedule if schedule.changes else None,
    )


def raw_path_for(disease: str) -> Path:
    """Ruta canónica del raw de un padecimiento.

    El constructor acepta además una ruta explícita para snapshots de observación semanales. La
    ruta canónica sigue siendo el default para no cambiar el carril de entrenamiento ni sus
    digests históricos.
    """
    return _ROOT / "data" / "raw" / f"data_raw_{registry.require(disease).artifact_key}.csv"


def explode_base(
    state: pd.DataFrame,
    snapshot: ExposureSnapshot,
    catalog: GeoCatalog,
    disease_id: str,
    scheme: spec.SexScheme = spec.SCHEME_POR_SEXO,
) -> pd.DataFrame:
    """Frame estatal → base largo: una fila por sexo base con exposición y y_cases.

    Sin desglose por sexo la única base es «general» (el total reconciliado) y las columnas de
    proporción sexual quedan vacías.
    """
    rows: list[dict[str, object]] = []
    total = not scheme.desglosado
    for r in state.itertuples(index=False):
        cve = str(r.cve_ent)
        ent = catalog.entity(cve)
        for sexo in scheme.base:
            if total:
                y = r.total_reconciled
            else:
                y = r.y_hombres if sexo == spec.SEX_HOMBRES else r.y_mujeres
            rows.append(
                {
                    spec.COL_DISEASE_ID: disease_id,
                    spec.COL_CVE_ENT: cve,
                    spec.COL_ENTIDAD_CANONICA: ent.nombre_canonico,
                    spec.COL_ENTIDAD_INEGI: ent.nombre_inegi,
                    spec.COL_SOURCE_YEAR: _i(r.source_year),
                    spec.COL_SOURCE_WEEK: _i(r.source_week),
                    spec.COL_EPI_YEAR: _i(r.epi_year),
                    spec.COL_EPI_WEEK: _i(r.epi_week),
                    spec.COL_PERIOD_START: r.period_start,
                    spec.COL_DS: r.ds,
                    spec.COL_SEXO: sexo,
                    spec.COL_Y_CASES: _i(y),
                    spec.COL_EXPOSURE: exposure_for_sex(snapshot, cve, sexo),
                    spec.COL_OBSERVED: bool(r.observed),
                    spec.COL_TOTAL_SOURCE: r.total_source,
                    spec.COL_TOTAL_RECONCILED: _i(r.total_reconciled),
                    spec.COL_SEX_PROP_SOURCE: _NAN if total else r.sex_prop_source,
                    spec.COL_SEX_PROP_APPLIED: _NAN if total else _f(r.sex_prop_applied),
                    spec.COL_SEX_DELTA_TOTAL: _NAN if total else r.sex_delta_total,
                    spec.COL_SEX_DELTA_RESIDUAL: _NAN if total else r.sex_delta_residual,
                    spec.COL_QUALITY_FLAGS: (
                        sin_banderas_de_sexo(str(r.quality_flags)) if total else r.quality_flags
                    ),
                }
            )
    return pd.DataFrame(rows, columns=list(spec.BASE_COLUMNS))


def _canonical_csv(df: pd.DataFrame) -> str:
    # Anotación (no cast): robusta a que pandas-stubs infiera str o Any para to_csv.
    csv: str = df.sort_values(_CANONICAL_ORDER).reset_index(drop=True).to_csv(index=False)
    return csv


def build_epi_dataset_v2(
    disease: str,
    runs_root: Path | None = None,
    run_id: str | None = None,
    *,
    raw_path: Path | None = None,
) -> EpiDatasetV2Result:
    """Construye EpiDatasetV2 y lo versiona en ``runs/<run_id>/`` con digests + insumos efectivos."""
    cfg = load_config(disease)
    catalog = load_geo_catalog()
    snapshot = load_exposure_snapshot(cfg.exposure_source_id, catalog)
    if set(snapshot.columns_by_sex) != set(spec.BASE_SEXES):
        raise EpiDatasetError(
            f"columns_by_sex debe ser exactamente {set(spec.BASE_SEXES)}: {set(snapshot.columns_by_sex)}"
        )
    scheme = scheme_for(cfg.disease_id)

    effective_raw_path = (raw_path or raw_path_for(disease)).resolve()
    if not effective_raw_path.is_file():
        raise EpiDatasetError(f"raw explícito inexistente o no regular: {effective_raw_path}")
    raw_bytes = effective_raw_path.read_bytes()
    raw = pd.read_csv(io.BytesIO(raw_bytes), low_memory=False)
    raw_digest = _sha256_bytes(raw_bytes)

    schedule = cfg.lag_schedule
    try:
        prep = build_prep(raw, catalog, schedule or cfg.observation_lag_weeks)
    except LagScheduleError as exc:
        raise EpiDatasetError(str(exc)) from exc
    state = reconcile_state(prep, set(catalog.cve_ents()))
    state = mark_gap_rows(state, schedule) if schedule else state
    base = explode_base(state, snapshot, catalog, cfg.disease_id, scheme)
    base = base.sort_values(_CANONICAL_ORDER).reset_index(drop=True)

    catalog_path = geo_catalog_path()
    catalog_bytes = catalog_path.read_bytes()
    catalog_digest = _sha256_bytes(catalog_bytes)
    dataset_bytes = _canonical_csv(base).encode("utf-8")
    dataset_digest = _sha256_bytes(dataset_bytes)
    config_payload = {
        "disease_id": cfg.disease_id,
        "calendar": {"kind": "epi_mmwr", "observation_lag_weeks": cfg.observation_lag_weeks}
        | ({"lag_schedule": schedule.payload()} if schedule else {}),
        "expected_n_states": cfg.expected_n_states,
        "exposure": {
            "source_id": cfg.exposure_source_id,
            "reference": snapshot.reference,
            "cutoff": str(snapshot.cutoff),
            "columns_by_sex": (
                snapshot.columns_by_sex
                if scheme.desglosado
                else {spec.SEX_GENERAL: str(snapshot.total_column)}
            ),
            "total_column": snapshot.total_column,
            "digest": snapshot.digest,
        },
        "geo_catalog": {"path": str(catalog_path.relative_to(_ROOT)), "digest": catalog_digest},
    }
    config_digest = _sha256_bytes(
        json.dumps(config_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )
    digests = {
        "raw": raw_digest,
        "exposure": snapshot.digest,
        "config": config_digest,
        "dataset": dataset_digest,
    }

    run_id = run_id or f"{cfg.disease_id}_{dataset_digest[:12]}"
    run_dir = (runs_root or (_ROOT / "runs")) / run_id
    artifacts = assemble_dataset_artifacts(
        run_id=run_id,
        cfg=cfg,
        effective_raw_path=effective_raw_path,
        raw_bytes=raw_bytes,
        raw_digest=raw_digest,
        catalog_path=catalog_path,
        catalog_bytes=catalog_bytes,
        catalog_digest=catalog_digest,
        snapshot=snapshot,
        config_payload=config_payload,
        digests=digests,
        base=base,
        state=state,
        dataset_bytes=dataset_bytes,
        dataset_digest=dataset_digest,
    )
    stage_dataset_run(
        run_dir=run_dir,
        run_id=run_id,
        disease_id=cfg.disease_id,
        digests=digests,
        artifacts=artifacts,
        error_cls=EpiDatasetError,
    )

    return EpiDatasetV2Result(
        run_id=run_id,
        run_dir=run_dir,
        dataset=base,
        state=state,
        config=cfg,
        snapshot=snapshot,
        digests=digests,
    )
