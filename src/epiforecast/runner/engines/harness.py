"""F2/C3b — harness compartido de motores de backtest OOS (una sola implementación, no 4 copias).

Gestiona lo común a todos los motores estacionales: lectura de dataset+folds, ejecución de las 64
bases, derivación 64→111 (lineage C2), EvaluationFrame + MetricFrame, artefactos con digests y
spec.json. Cada motor SOLO aporta su ``PredictFn`` (predictor por serie) y sus parámetros.

``PredictFn(truth_map, holdout) -> (preds, n_fallback)``: ``truth_map`` mapea (epi_year, epi_week)→
valor real de la serie (todos los periodos); ``holdout`` son los periodos objetivo en orden. Devuelve
las predicciones y cuántas usaron fallback. El disease_id viene del contexto; nunca hardcode.
"""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from epiforecast.data.epi_calendar import ds_for
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
)
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner import contracts as ct
from epiforecast.runner.evaluation import (
    build_evaluation_frame,
    build_metric_frame,
    derive_forecast_products,
)
from epiforecast.runner.manifest import ArtifactRecord
from epiforecast.runner.policy import load_policy

SCHEMA_ENGINE_SPEC = "engine_spec.v1"

# (truth_map, holdout) -> (preds, n_fallback)
PredictFn = Callable[
    [dict[tuple[int, int], float], list[tuple[int, int]]],
    tuple[dict[tuple[int, int], float], int],
]


def _rec(run_dir: Path, path: Path, schema: str) -> ArtifactRecord:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRecord(str(path.relative_to(run_dir)), digest, schema, validated=True)


def _predict_fold(
    base_truth: pd.DataFrame,
    fold: Any,
    run_id: str,
    disease_id: str,
    engine: str,
    predict_fn: PredictFn,
) -> tuple[pd.DataFrame, int]:
    holdout = list(fold.holdout)
    oy, ow = fold.train_end
    rows: list[dict[str, Any]] = []
    n_fallback = 0
    for (cve, sexo), grp in base_truth.groupby([COL_GEO_ID, COL_SEX], sort=False):
        tmap = {
            (int(y), int(w)): float(v)
            for y, w, v in zip(grp[COL_EPI_YEAR], grp[COL_EPI_WEEK], grp[COL_Y_CASES], strict=True)
        }
        preds, nfb = predict_fn(tmap, holdout)
        n_fallback += nfb
        for h, (y, w) in enumerate(holdout, start=1):
            rows.append(
                {
                    ct.COL_RUN_ID: run_id,
                    ct.COL_ENGINE: engine,
                    ct.COL_FOLD: fold.fold_id,
                    ct.COL_ORIGIN_EPI_YEAR: oy,
                    ct.COL_ORIGIN_EPI_WEEK: ow,
                    ct.COL_HORIZON: h,
                    "disease_id": disease_id,
                    COL_GEO_LEVEL: GEO_LEVEL_ESTADO,
                    COL_GEO_ID: cve,
                    COL_SEX: sexo,
                    COL_EPI_YEAR: y,
                    COL_EPI_WEEK: w,
                    COL_DS: ds_for(y, w),
                    ct.COL_Y_PRED: preds[(y, w)],
                    ct.COL_YHAT_LOWER: None,
                    ct.COL_YHAT_UPPER: None,
                }
            )
    return pd.DataFrame(rows), n_fallback


def run_benchmark(
    engine: str, predict_fn: PredictFn, run_dir: str, extra_spec: dict[str, Any] | None = None
) -> list[ArtifactRecord]:
    """Ejecuta el backtest OOS de un motor: 64 bases → 111 productos → eval + métricas + artefactos."""
    rd = Path(run_dir)
    ctx = json.loads((rd / "job_context.json").read_text(encoding="utf-8"))
    disease_id = str(ctx["disease_id"])  # SIEMPRE del contexto; nunca hardcode
    products = pd.read_csv(Path(ctx["dataset_dir"]) / "products.csv")
    catalog = load_geo_catalog()
    policy = load_policy(ctx["policy_name"])
    folds = policy.folds_for_stage(ctx["stage"])

    base_truth = products[
        (products[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO) & products[COL_SEX].isin(BASE_SEXES)
    ]

    fc_parts, ev_parts = [], []
    n_base_predictions = 0
    n_fallback = 0
    for fold in folds:
        base_fc, nfb = _predict_fold(base_truth, fold, rd.name, disease_id, engine, predict_fn)
        n_base_predictions += len(base_fc)
        n_fallback += nfb
        full_fc = derive_forecast_products(base_fc, catalog)
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

    spec = {
        "engine": engine,
        "disease_id": disease_id,
        "policy_name": ctx["policy_name"],
        "policy_digest": policy.digest,
        "seed": ctx["seed"],
        "fold_ids": [f.fold_id for f in folds],
        "n_series_modeled": int(base_truth.groupby([COL_GEO_ID, COL_SEX]).ngroups),
        "base_predictions": int(n_base_predictions),
        "derived_eval_rows": int(len(eval_all)),
        "n_fallback": int(n_fallback),
        **(extra_spec or {}),
    }
    spec_path = adir / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2, sort_keys=True), encoding="utf-8")
    arts.append(_rec(rd, spec_path, SCHEMA_ENGINE_SPEC))
    return arts
