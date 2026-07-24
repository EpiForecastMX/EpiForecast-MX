"""F2/C4.2 — tuning reproducible y GENÉRICO, sobre el MISMO corte causal del backtest.

Un motor no elige sus hiperparámetros dentro del benchmark: los congela antes, con este comando.
El tuning reutiliza ``harness.series_requests`` (mismo train cortado en el origen, misma exposición,
mismas validaciones), así que no existe una segunda materialización de datos que pueda divergir.

- **Centinelas deterministas**: se ordenan las 64 bases por media semanal del TRAIN del fold de
  tuning (nunca el holdout) y, por sexo, se toman mínimo, mediana superior y máximo. Con la misma
  entrada siempre salen las mismas 6 series.
- **Rejilla completa** por motor: cada configuración se evalúa en los 6 centinelas contra el
  holdout del fold. Una configuración es VÁLIDA solo si las 6 producen un pronóstico utilizable
  (cobertura exacta, finito y no negativo); si falla una, la configuración entera queda descartada.
- **Selección declarativa**: agregados (mediana y media de sMAPE) y desempates por parámetro se
  declaran en el YAML del motor; aquí no hay preferencias en código.
- Si ninguna configuración es válida, el job termina rc≠0 (nunca se congela un default silencioso).

Artefactos con digest bajo ``artifacts/<engine>/``: ``sentinels.csv``, ``tuning_results.csv``
(una fila por configuración × centinela), ``selected_config.json`` (ganadora + ranking completo) y
``tuning_spec.json``. La duración por ajuste es telemetría → ``jobs/<engine>.tuning_timing.csv``.
"""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import time
from typing import Any

import pandas as pd

from epiforecast.data.epi_dataset_spec import (
    BASE_SEXES,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    COL_Y_CASES,
    GEO_LEVEL_ESTADO,
)
from epiforecast.runner import contracts as ct
from epiforecast.runner.engines import harness
from epiforecast.runner.evaluation import smape_percent
from epiforecast.runner.manifest import ArtifactRecord
from epiforecast.runner.policy import Fold, load_policy

SCHEMA_SENTINELS = "sentinels.v1"
SCHEMA_TUNING_RESULTS = "tuning_results.v1"
SCHEMA_SELECTED_CONFIG = "selected_config.v1"
SCHEMA_TUNING_SPEC = "tuning_spec.v1"

# Posiciones dentro del orden ascendente de media semanal (mediana SUPERIOR para n par).
_POSITIONS: tuple[str, ...] = ("min", "median_upper", "max")

PredictFactory = Callable[[dict[str, Any]], harness.PredictFn]


class TuningError(ValueError):
    """El tuning no pudo congelar una configuración (o su declaración es inválida)."""


def select_sentinels(base_truth: pd.DataFrame, fold: Fold) -> list[dict[str, Any]]:
    """Centinelas deterministas por sexo (mín / mediana superior / máx de la media semanal train)."""
    train = base_truth[
        base_truth[COL_EPI_YEAR] * 100 + base_truth[COL_EPI_WEEK]
        <= fold.train_end[0] * 100 + fold.train_end[1]
    ]
    chosen: list[dict[str, Any]] = []
    for sex in BASE_SEXES:
        means = (
            train[train[COL_SEX] == sex]
            .groupby(COL_GEO_ID)[COL_Y_CASES]
            .mean()
            .reset_index()
            .sort_values([COL_Y_CASES, COL_GEO_ID], kind="mergesort")  # estable y total
            .reset_index(drop=True)
        )
        n = len(means)
        if n < len(_POSITIONS):
            raise TuningError(f"sexo {sex!r}: {n} series, insuficientes para elegir centinelas")
        for position, idx in zip(_POSITIONS, (0, n // 2, n - 1), strict=True):
            row = means.iloc[idx]
            chosen.append(
                {
                    COL_SEX: sex,
                    "position": position,
                    COL_GEO_ID: str(row[COL_GEO_ID]),
                    "train_mean_cases": float(row[COL_Y_CASES]),
                }
            )
    return chosen


def _sort_key(
    row: dict[str, Any], config: dict[str, Any], tie_break: list[dict[str, Any]]
) -> tuple[Any, ...]:
    """Clave de orden DECLARADA: agregados primero, luego los desempates del YAML del motor."""
    key: list[Any] = [row["median_smape"], row["mean_smape"]]
    for rule in tie_break:
        param = str(rule["param"])
        if param not in config:
            raise TuningError(f"desempate por {param!r}: no es un parámetro de la rejilla")
        value = config[param]
        order = rule.get("order", "asc")
        if isinstance(order, list):  # categórico: el orden declarado manda
            if value not in order:
                raise TuningError(f"desempate por {param!r}: valor {value!r} no declarado")
            key.append(order.index(value))
        elif order == "asc":
            key.append(value)
        elif order == "desc":
            key.append(-float(value))
        else:
            raise TuningError(f"desempate por {param!r}: orden {order!r} no soportado")
    return tuple(key)


def _evaluate(
    config: dict[str, Any],
    predict_factory: PredictFactory,
    requests: list[tuple[dict[str, Any], harness.SeriesRequest, list[float]]],
    config_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Evalúa UNA configuración en todos los centinelas. Devuelve (filas, telemetría)."""
    predict = predict_factory(config)
    rows: list[dict[str, Any]] = []
    timing: list[dict[str, Any]] = []
    for sentinel, request, truth in requests:
        identity = {
            "config_id": config_id,
            COL_GEO_ID: sentinel[COL_GEO_ID],
            COL_SEX: sentinel[COL_SEX],
            "position": sentinel["position"],
        }
        started = time.perf_counter()
        smape: float | None = None
        status, error = "ok", ""
        try:
            out = predict(request)
            harness.validate_predictions(out, request)
            smape = smape_percent(truth, [out.predictions[p] for p in request.holdout])
        except Exception as exc:  # noqa: BLE001 — configuración inválida, nunca un fallback mudo
            status, error = "failed", f"{type(exc).__name__}: {exc}"
        timing.append({**identity, "fit_seconds": round(time.perf_counter() - started, 6)})
        rows.append(
            {
                **identity,
                **{f"param_{k}": v for k, v in config.items()},
                "n_train": len(request.train),
                "smape": smape,
                "status": status,
                "error": error,
            }
        )
    return rows, timing


def run_tuning(
    engine: str,
    grid: list[dict[str, Any]],
    predict_factory: PredictFactory,
    run_dir: str,
    selection: dict[str, Any],
    *,
    transform: harness.TransformFactory = ct.identity_transform,
    resource_limits: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> list[ArtifactRecord]:
    """Congela UNA configuración por motor: centinelas + rejilla completa + selección declarada."""
    rd = Path(run_dir)
    job = json.loads((rd / "job_context.json").read_text(encoding="utf-8"))
    disease_id = str(job["disease_id"])
    products = pd.read_csv(Path(job["dataset_dir"]) / "products.csv", dtype={COL_GEO_ID: str})
    policy = load_policy(job["policy_name"])
    fold = policy.folds_for_stage(job["stage"])[-1]  # el ÚLTIMO fold del stage puntúa el tuning
    ctx = harness.EngineContext(
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

    sentinels = select_sentinels(base_truth, fold)
    wanted = {(s[COL_GEO_ID], s[COL_SEX]): s for s in sentinels}
    holdout_truth = {
        (str(cve), str(sex)): grp.set_index([COL_EPI_YEAR, COL_EPI_WEEK])[COL_Y_CASES]
        for (cve, sex), grp in base_truth.groupby([COL_GEO_ID, COL_SEX], sort=False)
    }
    requests: list[tuple[dict[str, Any], harness.SeriesRequest, list[float]]] = []
    for cve, sex, request in harness.series_requests(base_truth, fold, ctx):
        sentinel = wanted.get((cve, sex))
        if sentinel is None:
            continue
        truth = holdout_truth[(cve, sex)]
        requests.append((sentinel, request, [float(truth.loc[p]) for p in request.holdout]))
    if len(requests) != len(sentinels):
        raise TuningError(f"centinelas no resueltos: {len(requests)} de {len(sentinels)}")

    rows: list[dict[str, Any]] = []
    timing: list[dict[str, Any]] = []
    ranking: list[dict[str, Any]] = []
    for config_id, config in enumerate(grid):
        cfg_rows, cfg_timing = _evaluate(config, predict_factory, requests, config_id)
        rows.extend(cfg_rows)
        timing.extend(cfg_timing)
        scores = [r["smape"] for r in cfg_rows if r["status"] == "ok"]
        valid = len(scores) == len(requests)  # una serie fallida invalida la configuración entera
        summary = {
            "config_id": config_id,
            **config,
            "valid": valid,
            "n_ok": len(scores),
            "median_smape": float(pd.Series(scores).median()) if valid else None,
            "mean_smape": float(pd.Series(scores).mean()) if valid else None,
        }
        ranking.append(summary)

    tie_break = list(selection.get("tie_break", []))
    valid_rank = [r for r in ranking if r["valid"]]
    if not valid_rank:
        raise TuningError(
            f"motor {engine!r}: ninguna configuración válida en {len(grid)} candidatas "
            "(perfil rechazado; no se congela ningún default)"
        )
    valid_rank.sort(key=lambda r: _sort_key(r, grid[int(r["config_id"])], tie_break))
    winner = valid_rank[0]

    jobs_dir = rd / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(timing).to_csv(jobs_dir / f"{engine}.tuning_timing.csv", index=False)

    adir = rd / "artifacts" / engine
    adir.mkdir(parents=True, exist_ok=True)
    arts: list[ArtifactRecord] = []
    for payload, fname, schema in (
        (pd.DataFrame(sentinels), "sentinels.csv", SCHEMA_SENTINELS),
        (pd.DataFrame(rows), "tuning_results.csv", SCHEMA_TUNING_RESULTS),
    ):
        path = adir / fname
        payload.to_csv(path, index=False)
        arts.append(harness.artifact_record(rd, path, schema))

    selected = {
        "engine": engine,
        "fold_id": fold.fold_id,
        "selection": selection,
        "winner": grid[int(winner["config_id"])],
        "winner_summary": winner,
        "ranking": valid_rank + [r for r in ranking if not r["valid"]],
    }
    spec = {
        "engine": engine,
        "disease_id": disease_id,
        "command": "tune",
        "policy_name": job["policy_name"],
        "policy_digest": policy.digest,
        "seed": ctx.seed,
        "fold_id": fold.fold_id,
        "n_sentinels": len(sentinels),
        "n_configs": len(grid),
        "n_configs_valid": len(valid_rank),
        "n_fits": len(rows),
        "engine_params": ctx.params,
        "resource_limits": ctx.resource_limits,
        "transform": ctx.transform.to_dict(),
        "transform_digest": ctx.transform.digest(),
        "config_digest": ctx.config_digest(),
    }
    for payload_json, fname, schema in (
        (selected, "selected_config.json", SCHEMA_SELECTED_CONFIG),
        (spec, "tuning_spec.json", SCHEMA_TUNING_SPEC),
    ):
        path = adir / fname
        path.write_text(json.dumps(payload_json, indent=2, sort_keys=True), encoding="utf-8")
        arts.append(harness.artifact_record(rd, path, schema))
    return arts
