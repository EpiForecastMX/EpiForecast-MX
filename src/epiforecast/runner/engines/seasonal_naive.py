"""F2/C3.4 — adapter ``seasonal_naive_lag52``: baseline estacional cargable en el subprocess.

Para cada semana objetivo del holdout, reutiliza el valor de 52 semanas atrás (calendario MMWR).
Si el origen del salto cae DENTRO del holdout (folds de 53 semanas: 2020/2025), continúa
RECURSIVAMENTE con la predicción previa — nunca consulta valores reales posteriores al origen.

Su artefacto es la especificación reproducible + predicciones + métricas (NO un .pkl). Predice
EXCLUSIVAMENTE las 64 bases (estado×sexo); los 32+12+3 derivados salen de la agregación (C3.3).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

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
)
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner import contracts as ct
from epiforecast.runner.adapters import register_adapter
from epiforecast.runner.evaluation import (
    build_evaluation_frame,
    build_metric_frame,
    derive_forecast_products,
)
from epiforecast.runner.manifest import ArtifactRecord
from epiforecast.runner.policy import load_policy

ENGINE = "seasonal_naive_lag52"
SCHEMA_ENGINE_SPEC = "engine_spec.v1"
_LAG = 52


def predict_series(
    truth_map: dict[tuple[int, int], float], holdout: list[tuple[int, int]]
) -> dict[tuple[int, int], float]:
    """Seasonal naive lag-52 para una serie. Recursivo si el origen del salto cae en el holdout."""
    holdout_set = set(holdout)
    preds: dict[tuple[int, int], float] = {}
    for y, w in holdout:  # holdout en orden creciente → los recursivos ya están calculados
        src = shift(y, w, -_LAG)
        preds[(y, w)] = preds[src] if src in holdout_set else truth_map[src]
    return preds


class SeasonalNaiveLag52Adapter:
    """Adapter genérico (Protocol ``EngineAdapter``) ejecutado dentro del subprocess limpio."""

    name = ENGINE

    def run(self, command: str, run_dir: str) -> list[ArtifactRecord]:
        rd = Path(run_dir)
        ctx = json.loads((rd / "job_context.json").read_text(encoding="utf-8"))
        products = pd.read_csv(Path(ctx["dataset_dir"]) / "products.csv")
        catalog = load_geo_catalog()
        policy = load_policy(ctx["policy_name"])
        folds = policy.folds_for_stage(ctx["stage"])
        run_id = rd.name

        base_truth = products[
            (products[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO) & products[COL_SEX].isin(BASE_SEXES)
        ]

        fc_parts, ev_parts = [], []
        n_base_predictions = 0  # predicciones de las 64 bases (excluye derivados)
        for fold in folds:
            base_fc = self._predict_fold(base_truth, fold, run_id)
            n_base_predictions += len(base_fc)
            full_fc = derive_forecast_products(base_fc, catalog)
            # El holdout de un fold = todas las semanas de su año epidemiológico.
            weeks = {w for (_, w) in fold.holdout}
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

        adir = rd / "artifacts" / self.name
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
            "engine": self.name,
            "policy_name": ctx["policy_name"],
            "policy_digest": policy.digest,
            "seed": ctx["seed"],
            "seasonal_lag": _LAG,
            "fold_ids": [f.fold_id for f in folds],
            "n_series_modeled": int(base_truth.groupby([COL_GEO_ID, COL_SEX]).ngroups),
            "base_predictions": int(n_base_predictions),
            "derived_eval_rows": int(len(eval_all)),
        }
        spec_path = adir / "spec.json"
        spec_path.write_text(json.dumps(spec, indent=2, sort_keys=True), encoding="utf-8")
        arts.append(_rec(rd, spec_path, SCHEMA_ENGINE_SPEC))
        return arts

    def _predict_fold(self, base_truth: pd.DataFrame, fold: Any, run_id: str) -> pd.DataFrame:
        holdout = list(fold.holdout)
        oy, ow = fold.train_end
        rows: list[dict[str, Any]] = []
        for (cve, sexo), grp in base_truth.groupby([COL_GEO_ID, COL_SEX], sort=False):
            tmap = {
                (int(y), int(w)): float(v)
                for y, w, v in zip(
                    grp[COL_EPI_YEAR], grp[COL_EPI_WEEK], grp[COL_Y_CASES], strict=True
                )
            }
            preds = predict_series(tmap, holdout)
            for h, (y, w) in enumerate(holdout, start=1):
                rows.append(
                    {
                        ct.COL_RUN_ID: run_id,
                        ct.COL_ENGINE: self.name,
                        ct.COL_FOLD: fold.fold_id,
                        ct.COL_ORIGIN_EPI_YEAR: oy,
                        ct.COL_ORIGIN_EPI_WEEK: ow,
                        ct.COL_HORIZON: h,
                        "disease_id": "obesidad",
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
        return pd.DataFrame(rows)


def _rec(run_dir: Path, path: Path, schema: str) -> ArtifactRecord:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRecord(str(path.relative_to(run_dir)), digest, schema, validated=True)


register_adapter(ENGINE, SeasonalNaiveLag52Adapter())
