"""F2/C5.4 — driver del forecast preliminar: pronostica CARGANDO los modelos finales del refit.

Nunca reajusta nada ni permite sustituir motores a mano: cada motor carga sus modelos del run de
refit (envelope + estado sellados por ``model_index.json``), pronostica el horizonte declarado y
emite solo sus filas base. La derivación 64→111 y el reporte los hace el orquestador, después.

La exposición futura sale del snapshot estático declarado (``ExposureSnapshot.exposure_for``, que
resuelve la columna por ``columns_by_sex``): sin escalas ni nombres de columna en el código.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import time
from typing import Any

import pandas as pd

from epiforecast.artifacts.transforms import TransformContract
from epiforecast.data.epi_calendar import ds_for, shift
from epiforecast.data.epi_dataset_spec import (
    COL_DS,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_GEO_ID,
    COL_GEO_LEVEL,
    COL_SEX,
    GEO_LEVEL_ESTADO,
)
from epiforecast.data.epi_geo_exposure import load_exposure_snapshot, load_geo_catalog
from epiforecast.runner import contracts as ct
from epiforecast.runner import final_models as fm
from epiforecast.runner.manifest import ArtifactRecord

SCHEMA_FORECAST_BASE = "forecast_base.v1"

Period = tuple[int, int]


class ForecastError(ValueError):
    """El forecast preliminar violó su contrato (cobertura, validez o procedencia)."""


def horizon_periods(origin: Period, horizon: int) -> list[Period]:
    """Los ``horizon`` periodos MMWR consecutivos posteriores al origen (nunca incluye el origen)."""
    periods: list[Period] = []
    cur = origin
    for _ in range(horizon):
        cur = shift(cur[0], cur[1], 1)
        periods.append(cur)
    return periods


def run_forecast(
    engine: str, forecast_fn: fm.FinalForecastFn, run_dir: str
) -> list[ArtifactRecord]:
    """Carga los modelos finales de este motor y emite sus filas base del horizonte declarado."""
    rd = Path(run_dir)
    job = json.loads((rd / "job_context.json").read_text(encoding="utf-8"))
    refit_dir = Path(job["refit_dir"])
    origin: Period = (int(job["origin"][0]), int(job["origin"][1]))
    periods = tuple(horizon_periods(origin, int(job["horizon"])))
    # Exposición futura: el snapshot ESTÁTICO declarado en el contexto, resuelto por metadata.
    snapshot = load_exposure_snapshot(str(job["exposure_source_id"]), load_geo_catalog())

    models = fm.load_models(refit_dir, engine)  # verifica el sello del índice
    rows: list[dict[str, Any]] = []
    timing: list[dict[str, Any]] = []
    for envelope, state in models:
        key = envelope["series_key"]
        if key["geography_level"] != GEO_LEVEL_ESTADO:
            raise ForecastError(f"{engine}: modelo final para un producto derivado ({key})")
        if tuple(envelope["train_end"]) != origin:
            raise ForecastError(
                f"{engine}/{key['geography_id']}/{key['sex']}: train_end "
                f"{tuple(envelope['train_end'])} != origen del forecast {origin}"
            )
        transform = TransformContract.from_dict(envelope["transform"])
        exposure = {
            p: float(snapshot.exposure_for(key["geography_id"], key["sex"])) for p in periods
        }
        started = time.perf_counter()
        preds = forecast_fn(state, fm.ForecastRequest(transform, periods, exposure))
        timing.append(
            {
                COL_GEO_ID: key["geography_id"],
                COL_SEX: key["sex"],
                "forecast_seconds": round(time.perf_counter() - started, 6),
            }
        )
        if set(preds) != set(periods):
            raise ForecastError(
                f"{engine}/{key['geography_id']}: el forecast no cubre el horizonte"
            )
        for h, period in enumerate(periods, start=1):
            value = float(preds[period])
            if not math.isfinite(value) or value < 0:
                raise ForecastError(f"{engine}/{key['geography_id']}: valor inválido {value!r}")
            rows.append(
                {
                    ct.COL_RUN_ID: rd.name,
                    ct.COL_ENGINE: engine,
                    ct.COL_FOLD: fm.FINAL_FOLD_ID,
                    ct.COL_ORIGIN_EPI_YEAR: origin[0],
                    ct.COL_ORIGIN_EPI_WEEK: origin[1],
                    ct.COL_HORIZON: h,
                    "disease_id": envelope["disease_id"],
                    COL_GEO_LEVEL: GEO_LEVEL_ESTADO,
                    COL_GEO_ID: key["geography_id"],
                    COL_SEX: key["sex"],
                    COL_EPI_YEAR: period[0],
                    COL_EPI_WEEK: period[1],
                    COL_DS: ds_for(*period),
                    ct.COL_Y_PRED: value,
                    ct.COL_YHAT_LOWER: None,  # point-only: no se inventan intervalos
                    ct.COL_YHAT_UPPER: None,
                }
            )

    frame = pd.DataFrame(rows, columns=list(ct.FORECAST_COLUMNS))
    ct.validate_forecast_frame(frame)
    jobs_dir = rd / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(timing).to_csv(jobs_dir / f"{engine}.forecast_timing.csv", index=False)

    adir = rd / "artifacts" / engine
    adir.mkdir(parents=True, exist_ok=True)
    path = adir / "forecast_base.csv"
    frame.to_csv(path, index=False)
    return [fm.write_artifact_record(rd, path, SCHEMA_FORECAST_BASE)]


def finish_forecast(run_dir: Path, man: Any, refit_dir: Path, code_commit: str | None) -> None:
    """Une las 64 bases de los motores, deriva los 47 productos y emite el reporte preliminar."""
    from epiforecast.runner.evaluation import derive_forecast_products

    job = json.loads((run_dir / "job_context.json").read_text(encoding="utf-8"))
    etiqueta = job.get("disease_label") or man.disease_id
    exposure = job["exposure"]
    refit_digest = job["refit_digest"]

    parts = [
        pd.read_csv(run_dir / "artifacts" / e / "forecast_base.csv", dtype={COL_GEO_ID: str})
        for e in man.engines
    ]
    base = pd.concat(parts, ignore_index=True)
    base[ct.COL_ENGINE] = "portfolio"  # identidad del portafolio, no del motor donante
    keys = base.groupby([COL_GEO_ID, COL_SEX]).ngroups
    horizon = int(base[ct.COL_HORIZON].max())
    if keys != 64 or len(base) != 64 * horizon:
        raise ForecastError(f"forecast base incompleto: {len(base)} filas / {keys} series")
    ct.validate_forecast_frame(base)

    full = derive_forecast_products(base, load_geo_catalog())  # reconciliación exacta incluida
    if len(full) != 111 * horizon:
        raise ForecastError(f"forecast derivado incompleto: {len(full)} filas")
    ct.validate_forecast_frame(full)

    arts: list[ArtifactRecord] = []
    for frame, name, schema in (
        (base, "forecast_base.csv", SCHEMA_FORECAST_BASE),
        (full, "forecast.csv", ct.SCHEMA_FORECAST),
    ):
        path = run_dir / name
        frame.to_csv(path, index=False)
        arts.append(fm.write_artifact_record(run_dir, path, schema))

    inventory = pd.concat(
        [
            pd.DataFrame(
                json.loads(
                    (refit_dir / "models" / e / "model_index.json").read_text(encoding="utf-8")
                )["models"]
            ).assign(engine=e)
            for e in man.engines
        ],
        ignore_index=True,
    )[[COL_GEO_ID, COL_SEX, "engine", "n_train", "train_end", "state_format", "state_digest"]]
    inv_path = run_dir / "model_inventory.csv"
    inventory.to_csv(inv_path, index=False)
    arts.append(fm.write_artifact_record(run_dir, inv_path, "model_inventory.v1"))

    lineage = {
        "schema": "lineage.v1",
        "base_series": 64,
        "derived_products": 47,
        "products": 111,
        "horizon": horizon,
        "origin": [
            int(base[ct.COL_ORIGIN_EPI_YEAR].iloc[0]),
            int(base[ct.COL_ORIGIN_EPI_WEEK].iloc[0]),
        ],
        "rule": (
            "los 47 derivados se MATERIALIZAN sumando las 64 bases: general=H+M por estado, "
            "región=Σ estados de la macrorregión y nacional=Σ de los 32 estados. Que Σ regiones "
            "== nacional es una validación EQUIVALENTE, no la definición"
        ),
        "refit_run_id": refit_dir.name,
        "refit_digest": refit_digest,
        "engines": {e: int((inventory["engine"] == e).sum()) for e in man.engines},
    }
    lin_path = run_dir / "lineage.json"
    lin_path.write_text(json.dumps(lineage, indent=2, sort_keys=True), encoding="utf-8")
    arts.append(fm.write_artifact_record(run_dir, lin_path, "lineage.v1"))

    timing = pd.concat(
        [
            pd.read_csv(run_dir / "jobs" / f"{e}.forecast_timing.csv").assign(engine=e)
            for e in man.engines
        ],
        ignore_index=True,
    )
    first, last = (
        sorted(zip(full[COL_EPI_YEAR], full[COL_EPI_WEEK], strict=True))[0],
        sorted(zip(full[COL_EPI_YEAR], full[COL_EPI_WEEK], strict=True))[-1],
    )
    report = "\n".join(
        [
            f"# Forecast preliminar — {etiqueta}",
            "",
            f"- Run: `{man.run_id}` @ `{code_commit}` · refit `{refit_dir.name}`",
            f"- Origen `{lineage['origin']}` → horizonte {horizon} semanas "
            f"({first[0]}-W{first[1]:02d} … {last[0]}-W{last[1]:02d})",
            f"- {len(base)} predicciones base + derivación a {len(full)} filas de 111 productos",
            "",
            "## Modelos y tiempos por motor",
            "",
            "| motor | series | transform | ajuste | segundos |",
            "| --- | ---: | --- | --- | ---: |",
        ]
        + [
            f"| `{e}` | {int((inventory['engine'] == e).sum())} | "
            f"{json.loads((refit_dir / 'models' / e / 'model_index.json').read_text())['transform']['forward_steps']} | "
            f"{json.loads((refit_dir / 'models' / e / 'model_index.json').read_text())['models'][0]['state_format']} | "
            f"{timing[timing['engine'] == e]['forecast_seconds'].sum():.2f} |"
            for e in man.engines
        ]
        + [
            "",
            "## Anomalías e intervalos",
            "",
            "- Intervalos: **nulos en todo el frame** (point-only). Los motores del portafolio no",
            "  producen intervalos homogéneos y no se inventan.",
            f"- Valores negativos o no finitos: {int((full[ct.COL_Y_PRED] < 0).sum())} / "
            f"{int((~full[ct.COL_Y_PRED].apply(math.isfinite)).sum())}.",
            f"- Exposición futura: snapshot estático `{exposure['source_id']}` "
            f"({exposure['reference']}, corte {exposure['cutoff']}), resuelto por metadata.",
            "",
            f"**Preliminar y NO productivo**: {etiqueta} sigue NO-GO, fuera de todo canal público.",
        ]
    )
    rep_path = run_dir / "preliminary_report.md"
    rep_path.write_text(report + "\n", encoding="utf-8")
    arts.append(fm.write_artifact_record(run_dir, rep_path, "preliminary_report.v1"))

    man.artifacts = [*man.artifacts, *arts]
    man.counts = {**man.counts, "base_forecast": len(base), "products_forecast": len(full)}
    man.write(run_dir)
