"""F2/C3c — harness compartido de motores de backtest OOS (una sola implementación, no N copias).

Gestiona lo común a todos los motores: lectura de dataset+folds, materialización del ``TrainingSpec``
de cada serie/fold, ejecución de las 64 bases, derivación 64→111 (lineage C2), EvaluationFrame +
MetricFrame, diagnósticos de ajuste y artefactos con digests + spec.json. Cada motor SOLO aporta su
``PredictFn``, su ``TransformContract`` y sus parámetros declarativos.

Contrato del predictor (``PredictFn(SeriesRequest) -> SeriesForecast``):
- ``request.train`` mapea (epi_year, epi_week)→casos reales ESTRICTAMENTE anteriores al origen del
  fold, en orden ascendente. Ningún predictor recibe la verdad del holdout: la invariancia
  post-origen es estructural, no una convención del motor.
- ``request.spec`` es el ``TrainingSpec`` real (SeriesKey, fold, digests de dataset/política, seed,
  horizonte, ``TransformContract``, parámetros del motor y límites de recursos).
- ``SeriesForecast.predictions`` debe cubrir EXACTAMENTE el holdout, en CASOS (ya invertida
  cualquier transformación) y con valores finitos no negativos; si no, el job termina rc≠0.
- ``SeriesForecast.diagnostics`` (opcional) emite UNA fila por serie/fold en ``fit_diagnostics.csv``.

El disease_id viene del contexto; nunca hardcode. La duración por serie es telemetría wall-clock (no
reproducible byte a byte): va a ``jobs/<engine>.fit_timing.csv`` y NO es un artefacto con digest.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any

import pandas as pd

from epiforecast.artifacts.transforms import TransformContract
from epiforecast.data.epi_calendar import ds_for, shift
from epiforecast.data.epi_dataset_spec import (
    BASE_SEXES,
    COL_DS,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    COL_Y_CASES,
    GEO_LEVEL_ESTADO,
    SeriesKey,
)
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner import contracts as ct
from epiforecast.runner.evaluation import (
    build_evaluation_frame,
    build_metric_frame,
    derive_forecast_products,
)
from epiforecast.runner.manifest import ArtifactRecord
from epiforecast.runner.policy import Fold, load_policy

SCHEMA_ENGINE_SPEC = "engine_spec.v1"
SCHEMA_FIT_DIAGNOSTICS = "fit_diagnostics.v1"

Period = tuple[int, int]
TransformFactory = Callable[[str, str], TransformContract]


class HarnessError(ValueError):
    """Un motor violó el contrato del harness (cobertura o validez de sus predicciones)."""


@dataclass(frozen=True)
class SeriesRequest:
    """Lo que recibe un predictor para UNA serie base y UN fold. ``train`` nunca incluye holdout."""

    spec: ct.TrainingSpec
    train: dict[Period, float]  # periodos <= origin, ascendentes
    holdout: tuple[Period, ...]
    origin: Period


@dataclass(frozen=True)
class SeriesForecast:
    """Lo que devuelve un predictor: casos por periodo del holdout (+ fallbacks y diagnóstico)."""

    predictions: dict[Period, float]
    n_fallback: int = 0
    diagnostics: dict[str, Any] = field(default_factory=dict)


PredictFn = Callable[[SeriesRequest], SeriesForecast]


@dataclass(frozen=True)
class EngineContext:
    """Identidad y procedencia del motor; materializa el ``TrainingSpec`` de cada serie/fold."""

    engine: str
    disease_id: str
    dataset_digest: str
    policy_name: str
    policy_digest: str
    seed: int
    transform: TransformContract
    params: dict[str, Any] = field(default_factory=dict)
    resource_limits: dict[str, Any] = field(default_factory=dict)

    def spec_for(self, geography_id: str, sex: str, fold: Fold) -> ct.TrainingSpec:
        return ct.TrainingSpec(
            key=SeriesKey(self.disease_id, GEO_LEVEL_ESTADO, geography_id, sex),
            engine=self.engine,
            dataset_digest=self.dataset_digest,
            policy_name=self.policy_name,
            policy_digest=self.policy_digest,
            fold_id=fold.fold_id,
            seed=self.seed,
            horizon=len(fold.holdout),
            transform=self.transform,
            engine_params=dict(self.params),
            resource_limits=dict(self.resource_limits),
        )

    def config_digest(self) -> str:
        """Digest de la configuración EFECTIVA del motor (params + límites + transform)."""
        payload = {
            "engine": self.engine,
            "engine_params": self.params,
            "resource_limits": self.resource_limits,
            "transform": self.transform.to_dict(),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class _FoldOutcome:
    forecast: pd.DataFrame
    n_fallback: int
    diagnostics: list[dict[str, Any]]
    timing: list[dict[str, Any]]


def _rec(run_dir: Path, path: Path, schema: str) -> ArtifactRecord:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRecord(str(path.relative_to(run_dir)), digest, schema, validated=True)


def _validate_predictions(out: SeriesForecast, request: SeriesRequest) -> None:
    """El predictor cubre EXACTAMENTE el holdout con casos finitos no negativos (o rc≠0)."""
    who = f"{request.spec.engine}/{ct.series_key_str(request.spec.key)}/{request.spec.fold_id}"
    holdout, got = set(request.holdout), set(out.predictions)
    if got != holdout:
        raise HarnessError(
            f"{who}: las predicciones no cubren el holdout "
            f"(faltan {sorted(holdout - got)[:3]}, sobran {sorted(got - holdout)[:3]})"
        )
    for period, value in out.predictions.items():
        if not math.isfinite(value) or value < 0:
            raise HarnessError(f"{who}: predicción inválida en {period}: {value!r}")
    if out.n_fallback < 0:
        raise HarnessError(f"{who}: n_fallback negativo ({out.n_fallback})")


def _predict_fold(
    base_truth: pd.DataFrame, fold: Fold, run_id: str, ctx: EngineContext, predict_fn: PredictFn
) -> _FoldOutcome:
    """Ejecuta las 64 bases de UN fold: train cortado en el origen, predicciones validadas."""
    holdout = tuple(fold.holdout)
    origin = fold.train_end
    if shift(origin[0], origin[1], 1) != holdout[0]:
        raise HarnessError(f"fold {fold.fold_id}: el holdout no arranca justo después del origen")

    out = _FoldOutcome(pd.DataFrame(), 0, [], [])
    rows: list[dict[str, Any]] = []
    for (cve, sexo), grp in base_truth.groupby([COL_GEO_ID, COL_SEX], sort=False):
        train = {
            (int(y), int(w)): float(v)
            for y, w, v in zip(grp[COL_EPI_YEAR], grp[COL_EPI_WEEK], grp[COL_Y_CASES], strict=True)
            if (int(y), int(w)) <= origin  # verdad ESTRICTAMENTE anterior al holdout
        }
        spec = ctx.spec_for(str(cve), str(sexo), fold)
        request = SeriesRequest(spec, dict(sorted(train.items())), holdout, origin)

        started = time.perf_counter()
        result = predict_fn(request)
        elapsed = time.perf_counter() - started

        _validate_predictions(result, request)
        out.n_fallback += result.n_fallback
        identity = {
            ct.COL_FOLD: fold.fold_id,
            "disease_id": ctx.disease_id,
            COL_GEO_LEVEL: GEO_LEVEL_ESTADO,
            COL_GEO_ID: cve,
            COL_SEX: sexo,
        }
        out.timing.append({**identity, "fit_seconds": round(elapsed, 6)})
        if result.diagnostics:
            out.diagnostics.append(
                {
                    **identity,
                    "n_train": len(request.train),
                    **result.diagnostics,
                    "transform_digest": ctx.transform.digest(),
                    "config_digest": ctx.config_digest(),
                }
            )
        for h, (y, w) in enumerate(holdout, start=1):
            rows.append(
                {
                    ct.COL_RUN_ID: run_id,
                    ct.COL_ENGINE: ctx.engine,
                    ct.COL_FOLD: fold.fold_id,
                    ct.COL_ORIGIN_EPI_YEAR: origin[0],
                    ct.COL_ORIGIN_EPI_WEEK: origin[1],
                    ct.COL_HORIZON: h,
                    "disease_id": ctx.disease_id,
                    COL_GEO_LEVEL: GEO_LEVEL_ESTADO,
                    COL_GEO_ID: cve,
                    COL_SEX: sexo,
                    COL_EPI_YEAR: y,
                    COL_EPI_WEEK: w,
                    COL_DS: ds_for(y, w),
                    ct.COL_Y_PRED: result.predictions[(y, w)],
                    ct.COL_YHAT_LOWER: None,
                    ct.COL_YHAT_UPPER: None,
                }
            )
    out.forecast = pd.DataFrame(rows)
    return out


def run_benchmark(
    engine: str,
    predict_fn: PredictFn,
    run_dir: str,
    params: dict[str, Any] | None = None,
    *,
    transform: TransformFactory = ct.identity_transform,
    resource_limits: dict[str, Any] | None = None,
) -> list[ArtifactRecord]:
    """Ejecuta el backtest OOS de un motor: 64 bases → 111 productos → eval + métricas + artefactos."""
    rd = Path(run_dir)
    job = json.loads((rd / "job_context.json").read_text(encoding="utf-8"))
    disease_id = str(job["disease_id"])  # SIEMPRE del contexto; nunca hardcode
    products = pd.read_csv(Path(job["dataset_dir"]) / "products.csv")
    catalog = load_geo_catalog()
    policy = load_policy(job["policy_name"])
    folds = policy.folds_for_stage(job["stage"])
    ctx = EngineContext(
        engine=engine,
        disease_id=disease_id,
        dataset_digest=str(job["dataset_digest"]),
        policy_name=str(job["policy_name"]),
        policy_digest=policy.digest,
        seed=int(job["seed"]),
        transform=transform(disease_id, engine),
        params=dict(params or {}),
        resource_limits=dict(resource_limits or {}),
    )

    base_truth = products[
        (products[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO) & products[COL_SEX].isin(BASE_SEXES)
    ]

    fc_parts, ev_parts = [], []
    diagnostics: list[dict[str, Any]] = []
    timing: list[dict[str, Any]] = []
    n_base_predictions = 0
    n_fallback = 0
    for fold in folds:
        outcome = _predict_fold(base_truth, fold, rd.name, ctx, predict_fn)
        n_base_predictions += len(outcome.forecast)
        n_fallback += outcome.n_fallback
        diagnostics.extend(outcome.diagnostics)
        timing.extend(outcome.timing)
        full_fc = derive_forecast_products(outcome.forecast, catalog)
        weeks = {w for (_, w) in fold.holdout}  # el holdout = las semanas del año del fold
        truth_holdout = products[
            (products[COL_EPI_YEAR] == fold.epi_year) & products[COL_EPI_WEEK].isin(weeks)
        ]
        ev_parts.append(build_evaluation_frame(full_fc, truth_holdout, fold.group))
        fc_parts.append(full_fc)

    forecast_all = pd.concat(fc_parts, ignore_index=True)
    eval_all = pd.concat(ev_parts, ignore_index=True)
    ct.validate_forecast_frame(forecast_all)
    ct.validate_evaluation_frame(eval_all)
    metric_frame = build_metric_frame(eval_all, products, policy.mase_seasonal_lag)
    ct.validate_metric_frame(metric_frame)

    # Telemetría (wall-clock, NO reproducible byte a byte) → jobs/, nunca artefacto con digest.
    jobs_dir = rd / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(timing).to_csv(jobs_dir / f"{engine}.fit_timing.csv", index=False)

    adir = rd / "artifacts" / engine
    adir.mkdir(parents=True, exist_ok=True)
    arts: list[ArtifactRecord] = []
    for df, fname, schema in (
        (forecast_all, "forecast.csv", ct.SCHEMA_FORECAST),
        (eval_all, "evaluation.csv", ct.SCHEMA_EVALUATION),
        (metric_frame, "metrics.csv", ct.SCHEMA_METRICS),
    ):
        path = adir / fname
        df.to_csv(path, index=False)
        arts.append(_rec(rd, path, schema))
    if diagnostics:  # motores sin diagnóstico de ajuste (estacionales) no emiten el artefacto
        diag_path = adir / "fit_diagnostics.csv"
        pd.DataFrame(diagnostics).to_csv(diag_path, index=False)
        arts.append(_rec(rd, diag_path, SCHEMA_FIT_DIAGNOSTICS))

    spec = {
        "engine": engine,
        "disease_id": disease_id,
        "policy_name": job["policy_name"],
        "policy_digest": policy.digest,
        "seed": ctx.seed,
        "fold_ids": [f.fold_id for f in folds],
        "n_series_modeled": int(base_truth.groupby([COL_GEO_ID, COL_SEX]).ngroups),
        "base_predictions": int(n_base_predictions),
        "derived_eval_rows": int(len(eval_all)),
        "n_fallback": int(n_fallback),
        "n_diagnostics": len(diagnostics),
        "engine_params": ctx.params,
        "resource_limits": ctx.resource_limits,
        "transform": ctx.transform.to_dict(),
        "transform_digest": ctx.transform.digest(),
        "config_digest": ctx.config_digest(),
    }
    spec_path = adir / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2, sort_keys=True), encoding="utf-8")
    arts.append(_rec(rd, spec_path, SCHEMA_ENGINE_SPEC))
    return arts
