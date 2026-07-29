"""F1/C1 — orquestación EpiDatasetV2 (carril nuevo E66; legacy intacto).

Ensambla el dataset base semanal de un padecimiento del boletín a partir del raw extraído + el
calendario epidemiológico + la reconciliación causal + la exposición estática, y lo versiona en un
run local ``runs/<run_id>/`` con digests separados (raw / exposición / config / dataset) y copia de
los INSUMOS efectivos. NO reemplaza el dataset productivo ni toca DVC/legacy.

Pipeline: raw → ``target_period`` (lag) + geo → ``reconcile_state`` (estatal, 20,896) → explode a 64
series base × 653 periodos = 41,792 filas con exposición por sexo (``columns_by_sex``, no hard-code).
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, SupportsFloat, SupportsInt, cast

from omegaconf import OmegaConf
import pandas as pd

from epiforecast import registry
from epiforecast.data import epi_calendar as ec
from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data.epi_dataset_spec import ExposureSnapshot
from epiforecast.data.epi_geo_exposure import (
    GeoCatalog,
    geo_catalog_path,
    load_exposure_snapshot,
    load_geo_catalog,
)
from epiforecast.data.epi_reconcile import reconcile_state

_ROOT = Path(__file__).resolve().parents[3]
# Orden canónico ESTABLE (serie contigua) antes de digestar.
_CANONICAL_ORDER = [spec.COL_CVE_ENT, spec.COL_SEXO, spec.COL_EPI_YEAR, spec.COL_EPI_WEEK]


class EpiDatasetError(ValueError):
    """Config o insumos inválidos para EpiDatasetV2."""


@dataclass(frozen=True)
class EpiDatasetV2Result:
    run_id: str
    run_dir: Path
    dataset: pd.DataFrame  # 41,792 filas base (orden canónico)
    state: pd.DataFrame  # 20,896 filas estatales reconciliadas
    config: spec.EpiDatasetConfig
    snapshot: ExposureSnapshot
    digests: dict[str, str]  # raw / exposure / config / dataset


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
    lag = group.get("observation_lag_weeks")
    if isinstance(lag, bool) or not isinstance(lag, int) or lag < 0:
        raise EpiDatasetError(f"observation_lag_weeks inválido (entero >=0, no bool): {lag!r}")
    n_states = group.get("n_states_expected")
    if isinstance(n_states, bool) or not isinstance(n_states, int) or n_states <= 0:
        raise EpiDatasetError(f"n_states_expected inválido: {n_states!r}")
    return spec.EpiDatasetConfig(
        disease_id=d.id,  # id del registry (invariante N+1); NO el slug (coinciden en Obesidad)
        observation_lag_weeks=lag,
        exposure_source_id=d.exposure_source_id,
        expected_n_states=n_states,
    )


def raw_path_for(disease: str) -> Path:
    """Ruta canónica del raw de un padecimiento.

    El constructor acepta además una ruta explícita para snapshots de observación semanales. La
    ruta canónica sigue siendo el default para no cambiar el carril de entrenamiento ni sus
    digests históricos.
    """
    return _ROOT / "data" / "raw" / f"data_raw_{registry.require(disease).artifact_key}.csv"


def build_prep(raw: pd.DataFrame, catalog: GeoCatalog, lag: int) -> pd.DataFrame:
    """raw E66 → prep (calendario objetivo + cve_ent), listo para ``reconcile_state``."""
    recs: list[dict[str, object]] = []
    for r in raw.itertuples(index=False):
        tp = ec.target_period(_i(r.Anio), _i(r.Semana), lag)
        recs.append(
            {
                "cve_ent": catalog.resolve(str(r.Entidad)),
                "source_year": _i(r.Anio),
                "source_week": _i(r.Semana),
                "epi_year": tp.epi_year,
                "epi_week": tp.epi_week,
                "period_start": tp.period_start,
                "ds": tp.ds,
                "casos_source": (float("nan") if pd.isna(r.Casos_semana) else _f(r.Casos_semana)),
                "acum_h": _f(r.Acumulado_hombres),
                "acum_m": _f(r.Acumulado_mujeres),
            }
        )
    return pd.DataFrame(recs)


def explode_base(
    state: pd.DataFrame, snapshot: ExposureSnapshot, catalog: GeoCatalog, disease_id: str
) -> pd.DataFrame:
    """Frame estatal (20,896) → base largo (41,792): una fila por sexo con exposición y y_cases."""
    rows: list[dict[str, object]] = []
    for r in state.itertuples(index=False):
        cve = str(r.cve_ent)
        ent = catalog.entity(cve)
        for sexo in spec.BASE_SEXES:
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
                    spec.COL_EXPOSURE: snapshot.exposure_for(cve, sexo),
                    spec.COL_OBSERVED: bool(r.observed),
                    spec.COL_TOTAL_SOURCE: r.total_source,
                    spec.COL_TOTAL_RECONCILED: _i(r.total_reconciled),
                    spec.COL_SEX_PROP_SOURCE: r.sex_prop_source,
                    spec.COL_SEX_PROP_APPLIED: _f(r.sex_prop_applied),
                    spec.COL_SEX_DELTA_TOTAL: r.sex_delta_total,
                    spec.COL_SEX_DELTA_RESIDUAL: r.sex_delta_residual,
                    spec.COL_QUALITY_FLAGS: r.quality_flags,
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

    effective_raw_path = (raw_path or raw_path_for(disease)).resolve()
    if not effective_raw_path.is_file():
        raise EpiDatasetError(f"raw explícito inexistente o no regular: {effective_raw_path}")
    raw = pd.read_csv(effective_raw_path, low_memory=False)
    raw_digest = _sha256_bytes(effective_raw_path.read_bytes())

    prep = build_prep(raw, catalog, cfg.observation_lag_weeks)
    state = reconcile_state(prep, set(catalog.cve_ents()))
    base = explode_base(state, snapshot, catalog, cfg.disease_id)
    base = base.sort_values(_CANONICAL_ORDER).reset_index(drop=True)

    catalog_path = geo_catalog_path()
    catalog_digest = _sha256_bytes(catalog_path.read_bytes())
    dataset_digest = _sha256_bytes(_canonical_csv(base).encode("utf-8"))
    config_payload = {
        "disease_id": cfg.disease_id,
        "calendar": {"kind": "epi_mmwr", "observation_lag_weeks": cfg.observation_lag_weeks},
        "expected_n_states": cfg.expected_n_states,
        "exposure": {
            "source_id": cfg.exposure_source_id,
            "reference": snapshot.reference,
            "cutoff": str(snapshot.cutoff),
            "columns_by_sex": snapshot.columns_by_sex,
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
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    # Insumos efectivos: raw, catálogo geográfico, exposición canónica y config.
    shutil.copy2(effective_raw_path, inputs_dir / effective_raw_path.name)
    shutil.copy2(catalog_path, inputs_dir / catalog_path.name)
    exp_proj = pd.DataFrame(
        [{"cve_ent": c, **snapshot.by_cve_ent[c]} for c in sorted(snapshot.by_cve_ent)]
    )
    exp_proj.to_csv(inputs_dir / f"exposure_{cfg.exposure_source_id}.csv", index=False)
    (inputs_dir / "config_effective.json").write_text(
        json.dumps(config_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Dataset + manifest.
    base.to_csv(run_dir / "epi_dataset_v2.csv", index=False)
    manifest = {
        "run_id": run_id,
        "disease_id": cfg.disease_id,
        "digests": digests,
        "exposure": {
            "source_id": snapshot.source_id,
            "reference": snapshot.reference,
            "cutoff": str(snapshot.cutoff),
        },
        "counts": {
            "base_rows": int(len(base)),
            "state_rows": int(len(state)),
            "series": int(base.groupby([spec.COL_CVE_ENT, spec.COL_SEXO]).ngroups),
            "periods": int(state.groupby([spec.COL_EPI_YEAR, spec.COL_EPI_WEEK]).ngroups),
            "imputed_totals": int((~state["observed"]).sum()),
        },
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
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
