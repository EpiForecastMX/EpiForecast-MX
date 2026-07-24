"""F2/C3b — reporte comparativo de un run multi-motor (mediana sMAPE/MASE + mejora vs baseline).

Lee los MetricFrame de cada motor de un run de benchmark y resume: mediana sMAPE/MASE sobre las 64
bases, sobre los 111 productos y sobre nacional General, más el runtime por job. Muestra la mejora
relativa de sMAPE (todos los productos) frente al baseline Seasonal Naive — NO selecciona ganador.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from epiforecast.runner.manifest import STATUS_SUCCEEDED, JobRecord, RunManifest

BASELINE_ENGINE = "seasonal_naive_lag52"


def _summary(mf: pd.DataFrame) -> dict[str, float]:
    base = mf[(mf["geography_level"] == "estado") & mf["sex"].isin(["hombres", "mujeres"])]
    nat_gen = mf[(mf["geography_level"] == "nacional") & (mf["sex"] == "general")]
    return {
        "smape_bases": float(base["smape"].median()),
        "mase_bases": float(base["mase"].median()),  # median ignora NaN
        "smape_all": float(mf["smape"].median()),
        "mase_all": float(mf["mase"].median()),
        "smape_nacional_general": float(nat_gen["smape"].median()),
        "mase_nacional_general": float(nat_gen["mase"].median()),
    }


def _runtime_s(job: JobRecord | None) -> float:
    if job is None or not job.started_at or not job.finished_at:
        return float("nan")
    delta = datetime.fromisoformat(job.finished_at) - datetime.fromisoformat(job.started_at)
    return delta.total_seconds()


def comparative_report(run_dir: Path, baseline: str = BASELINE_ENGINE) -> pd.DataFrame:
    """Resumen comparativo de los motores exitosos del run; escribe ``comparison.csv``."""
    run_dir = Path(run_dir)
    man = RunManifest.read(run_dir)
    rows: list[dict[str, object]] = []
    for engine in man.engines:
        job = man.jobs.get(engine)
        if job is None or job.status != STATUS_SUCCEEDED:
            continue
        mf = pd.read_csv(run_dir / "artifacts" / engine / "metrics.csv")
        rows.append({"engine": engine, **_summary(mf), "runtime_s": _runtime_s(job)})

    df = pd.DataFrame(rows)
    # Mejora relativa de sMAPE (todos los productos) vs baseline; NO selecciona ganador.
    base_row = df[df["engine"] == baseline]
    if len(base_row):
        base_smape = float(base_row["smape_all"].iloc[0])
        df["smape_all_impr_pct_vs_baseline"] = (
            (base_smape - df["smape_all"]) / base_smape * 100.0 if base_smape else float("nan")
        )
    df.to_csv(run_dir / "comparison.csv", index=False)
    return df
