"""F2/C5.3 — driver del refit final: ajusta SOLO las series que la selección aceptada le asignó.

Un motor no decide qué series entrena: las lee de ``final_selection.csv`` (copiado al run desde el
run de aceptación). Entrena con TODA la historia disponible, escribe un modelo final por serie
(envelope + estado sellados) y un ``model_index.json`` por motor. Cero modelos para general, región
o nacional: los 47 derivados se reconstruyen al pronosticar, sumando las bases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any

import pandas as pd

from epiforecast.artifacts.transforms import TransformContract
from epiforecast.data.epi_dataset_spec import COL_GEO_ID, COL_SEX, GEO_LEVEL_ESTADO, SeriesKey
from epiforecast.runner import contracts as ct
from epiforecast.runner import final_models as fm
from epiforecast.runner.manifest import ArtifactRecord

SELECTION_FILE = "final_selection.csv"


@dataclass(frozen=True)
class FinalContext:
    """Identidad y procedencia del refit final; materializa el ``TrainingSpec`` de cada serie."""

    engine: str
    disease_id: str
    dataset_digest: str
    policy_name: str
    policy_digest: str
    seed: int
    horizon: int
    transform: TransformContract
    params: dict[str, Any] = field(default_factory=dict)
    resource_limits: dict[str, Any] = field(default_factory=dict)

    def spec_for(self, geography_id: str, sex: str) -> ct.TrainingSpec:
        return ct.TrainingSpec(
            key=SeriesKey(self.disease_id, GEO_LEVEL_ESTADO, geography_id, sex),
            engine=self.engine,
            dataset_digest=self.dataset_digest,
            policy_name=self.policy_name,
            policy_digest=self.policy_digest,
            fold_id=fm.FINAL_FOLD_ID,
            seed=self.seed,
            horizon=self.horizon,
            transform=self.transform,
            engine_params=dict(self.params),
            resource_limits=dict(self.resource_limits),
        )


def assigned_series(run_dir: Path, engine: str) -> set[tuple[str, str]]:
    """Series que la selección ACEPTADA asignó a este motor (nunca una lista manual)."""
    sel = pd.read_csv(run_dir / SELECTION_FILE, dtype={COL_GEO_ID: str})
    mine = sel[sel["selected_engine"] == engine]
    return {(str(r[COL_GEO_ID]), str(r[COL_SEX])) for _, r in mine.iterrows()}


def run_refit(
    engine: str,
    fit_fn: fm.FinalFitFn,
    run_dir: str,
    params: dict[str, Any] | None = None,
    *,
    transform: Any = ct.identity_transform,
    resource_limits: dict[str, Any] | None = None,
    versions: dict[str, str] | None = None,
) -> list[ArtifactRecord]:
    """Ajusta y serializa los modelos finales de este motor. Un solo artefacto: su model_index."""
    rd = Path(run_dir)
    job = json.loads((rd / "job_context.json").read_text(encoding="utf-8"))
    disease_id = str(job["disease_id"])
    products = pd.read_csv(Path(job["dataset_dir"]) / "products.csv", dtype={COL_GEO_ID: str})
    ctx = FinalContext(
        engine=engine,
        disease_id=disease_id,
        dataset_digest=str(job["dataset_digest"]),
        policy_name=str(job["policy_name"]),
        policy_digest=str(job["policy_digest"]),
        seed=int(job["seed"]),
        horizon=int(job["horizon"]),
        transform=transform(disease_id, engine),
        params=dict(params or {}),
        resource_limits=dict(resource_limits or {}),
    )
    provenance = {
        "dataset_id": job["dataset_id"],
        "dataset_digest": job["dataset_digest"],
        "policy_name": job["policy_name"],
        "policy_digest": job["policy_digest"],
        "selection_run_id": job["selection_run_id"],
        "selection_digest": job["selection_digest"],
        "acceptance_run_id": job["acceptance_run_id"],
        "acceptance_digest": job["acceptance_digest"],
        "code_commit": job.get("code_commit"),
    }

    assigned = assigned_series(rd, engine)
    windows = fm.final_windows(products, assigned, ctx)
    models_dir = rd / "models" / engine
    entries: list[dict[str, Any]] = []
    timing: list[dict[str, Any]] = []
    for window in windows:
        started = time.perf_counter()
        state = fit_fn(window)
        elapsed = time.perf_counter() - started
        envelope, digests = fm.write_model(
            models_dir, window, state, provenance, dict(versions or {})
        )
        entries.append(
            {
                COL_GEO_ID: window.spec.key.geography_id,
                COL_SEX: window.spec.key.sex,
                "n_train": envelope["n_train"],
                "train_start": envelope["train_start"],
                "train_end": envelope["train_end"],
                "state_format": envelope["state_format"],
                **digests,
            }
        )
        timing.append(
            {
                COL_GEO_ID: window.spec.key.geography_id,
                COL_SEX: window.spec.key.sex,
                "fit_seconds": round(elapsed, 6),
            }
        )

    jobs_dir = rd / "jobs"  # telemetría wall-clock, fuera de los artefactos con digest
    jobs_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(timing).to_csv(jobs_dir / f"{engine}.refit_timing.csv", index=False)

    train_ends = {tuple(e["train_end"]) for e in entries}
    n_trains = {int(e["n_train"]) for e in entries}
    summary = {
        "disease_id": disease_id,
        "final_refit": True,
        "n_assigned": len(assigned),
        "train_end": sorted(train_ends)[-1] if train_ends else None,
        "n_train_values": sorted(n_trains),
        "transform": ctx.transform.to_dict(),
        "transform_digest": ctx.transform.digest(),
        "engine_params": ctx.params,
        "resource_limits": ctx.resource_limits,
        "library_versions": dict(versions or {}),
        "provenance": provenance,
    }
    if len(entries) != len(assigned):
        raise fm.FinalModelError(f"{engine}: {len(entries)} modelos para {len(assigned)} series")
    return [fm.write_index(rd, engine, entries, summary)]


def write_summary(
    run_dir: Path,
    man: Any,
    final_sel: pd.DataFrame,
    provenance: dict[str, Any],
    code_commit: str | None,
) -> None:
    """``refit_summary.json``: demuestra 64 estados finales, sin derivadas y con el último periodo."""
    indexes = {
        engine: json.loads(
            (run_dir / "models" / engine / "model_index.json").read_text(encoding="utf-8")
        )
        for engine in man.engines
    }
    models = [(engine, m) for engine, ix in indexes.items() for m in ix["models"]]
    train_ends = {tuple(m["train_end"]) for _, m in models}
    n_trains = {int(m["n_train"]) for _, m in models}
    if len(models) != 64:
        raise fm.FinalModelError(f"refit final: {len(models)} modelos, se esperan 64")
    if len(train_ends) != 1:
        raise fm.FinalModelError(f"refit final: train_end heterogéneo {sorted(train_ends)}")
    summary = {
        "schema": "refit_summary.v1",
        "run_id": man.run_id,
        "disease_id": man.disease_id,
        "code_commit": code_commit,
        "final_refit": True,
        "n_models": len(models),
        "n_series_selected": int(len(final_sel)),
        "distribution": {
            str(k): int(v)
            for k, v in final_sel["selected_engine"].value_counts().sort_index().items()
        },
        "train_end": list(next(iter(train_ends))),
        "n_train_values": sorted(n_trains),
        "geography_levels": sorted({GEO_LEVEL_ESTADO}),  # cero modelos para derivados
        "provenance": provenance,
        "engines": {engine: ix["n_models"] for engine, ix in indexes.items()},
    }
    path = run_dir / "refit_summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    man.artifacts = [*man.artifacts, fm.write_artifact_record(run_dir, path, "refit_summary.v1")]
    man.write(run_dir)
