"""F2/C3b — reporte comparativo: resumen por motor + mejora relativa vs baseline (sin elegir)."""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.runner.manifest import ArtifactRecord, RunManifest
from epiforecast.runner.report import comparative_report


def _metrics(engine: str, smape: float) -> pd.DataFrame:
    rows = [
        ("estado", "05", "hombres"),
        ("estado", "05", "mujeres"),
        ("nacional", "mx", "general"),
    ]
    return pd.DataFrame(
        [
            {
                "engine": engine,
                "fold": "development_2024",
                "split": "development",
                "disease_id": "obesidad",
                "geography_level": lvl,
                "geography_id": geo,
                "sex": sx,
                "n_obs": 52,
                "smape": smape,
                "mase": 0.8,
                "mae": 2.0,
                "rmse": 3.0,
                "wape": 20.0,
                "bias": -0.2,
                "flags": "",
            }
            for lvl, geo, sx in rows
        ]
    )


def test_comparative_report(tmp_path):
    engines = ["seasonal_naive_lag52", "seasonal_mean_3y"]
    man = RunManifest(
        run_id=tmp_path.name, disease_id="obesidad", command="benchmark", engines=engines
    )
    man.start()
    for e in engines:
        j = man.job(e)
        j.start()
        j.succeed(
            [ArtifactRecord(f"artifacts/{e}/metrics.csv", "d", "metrics.v1", validated=True)]
        )
    man.succeed()
    man.write(tmp_path)
    for e, smape in [("seasonal_naive_lag52", 50.0), ("seasonal_mean_3y", 40.0)]:
        d = tmp_path / "artifacts" / e
        d.mkdir(parents=True)
        _metrics(e, smape).to_csv(d / "metrics.csv", index=False)

    df = comparative_report(tmp_path)
    assert set(df["engine"]) == set(engines)
    assert {"smape_bases", "smape_all", "smape_nacional_general", "runtime_s"} <= set(df.columns)
    impr = df.set_index("engine")["smape_all_impr_pct_vs_baseline"]
    assert impr["seasonal_naive_lag52"] == 0.0  # baseline vs sí mismo
    assert impr["seasonal_mean_3y"] == pytest.approx(20.0)  # (50-40)/50 × 100
    assert (tmp_path / "comparison.csv").exists()
