"""F2/C3.3 — evaluación OOS: métricas zero-safe, derivación 64→111 y alineación (CI-safe)."""

from __future__ import annotations

from datetime import date
import math

import numpy as np
import pandas as pd
import pytest

from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner import contracts as ct
from epiforecast.runner import evaluation as ev


@pytest.fixture(scope="module")
def catalog():
    return load_geo_catalog()


# ── series_metrics: zero-safe, nunca inf ──
def test_metrics_perfectas():
    m, flags = ev.series_metrics([10, 20, 30], [10, 20, 30], [1, 2, 3, 4], mase_lag=1)
    assert m[ct.COL_SMAPE] == 0.0 and m[ct.COL_MAE] == 0.0 and m[ct.COL_RMSE] == 0.0
    assert m[ct.COL_BIAS] == 0.0 and m[ct.COL_MASE] == 0.0 and m[ct.COL_WAPE] == 0.0
    assert flags == []


def test_metrics_zero_denominador_flags_no_inf():
    m, flags = ev.series_metrics([0, 0], [0, 0], [0, 0, 0], mase_lag=1)
    assert m[ct.COL_SMAPE] == 0.0  # ambos cero → sMAPE 0 (no 0/0)
    assert math.isnan(m[ct.COL_WAPE]) and "wape_zero_denom" in flags
    assert math.isnan(m[ct.COL_MASE]) and "mase_zero_denom" in flags
    assert all(v == v or k in (ct.COL_MASE, ct.COL_WAPE) for k, v in m.items())  # sin inf


def test_metrics_mase_train_only_y_bias_firmado():
    # bias firmado: sobreestima → positivo.
    m, _ = ev.series_metrics([10, 10], [12, 14], [10, 12, 8, 10], mase_lag=1)
    assert m[ct.COL_BIAS] == 3.0  # media de (2, 4)
    # denom MASE = mean(|10-12|,|12-8|,|8-10|)=mean(2,4,2)=2.6667; mae=mean(2,4)=3
    assert m[ct.COL_MASE] == pytest.approx(3.0 / (8 / 3))


def test_metrics_lag_mayor_que_train_null():
    m, flags = ev.series_metrics([5, 5], [5, 5], [1, 2, 3], mase_lag=52)
    assert math.isnan(m[ct.COL_MASE]) and "mase_zero_denom" in flags


# ── Derivación 64→111 de pronósticos ──
def _base_fc(catalog, y=lambda i, j: 1.0 + i + j) -> pd.DataFrame:
    rows = []
    for i, cve in enumerate(catalog.cve_ents()):
        for j, sexo in enumerate(spec.BASE_SEXES):
            rows.append(
                {
                    ct.COL_RUN_ID: "r",
                    ct.COL_ENGINE: "seasonal_naive_lag52",
                    ct.COL_FOLD: "development_2024",
                    ct.COL_ORIGIN_EPI_YEAR: 2023,
                    ct.COL_ORIGIN_EPI_WEEK: 52,
                    ct.COL_HORIZON: 1,
                    "disease_id": "obesidad",
                    ct.COL_GEO_LEVEL: "estado",
                    ct.COL_GEO_ID: cve,
                    ct.COL_SEX: sexo,
                    ct.COL_EPI_YEAR: 2024,
                    ct.COL_EPI_WEEK: 1,
                    ct.COL_DS: date(2024, 1, 1),
                    ct.COL_Y_PRED: y(i, j),
                    ct.COL_YHAT_LOWER: np.nan,
                    ct.COL_YHAT_UPPER: np.nan,
                }
            )
    return pd.DataFrame(rows)


def test_derive_forecast_products_111_y_reconciliacion(catalog):
    base = _base_fc(catalog)
    full = ev.derive_forecast_products(base, catalog)
    ct.validate_forecast_frame(full)  # cumple el contrato forecast.v1
    assert full.groupby([ct.COL_GEO_LEVEL, ct.COL_GEO_ID, ct.COL_SEX]).ngroups == 111
    nat_gen = full[(full[ct.COL_GEO_LEVEL] == "nacional") & (full[ct.COL_SEX] == "general")][
        ct.COL_Y_PRED
    ].iloc[0]
    assert nat_gen == pytest.approx(base[ct.COL_Y_PRED].sum())  # suma directa de las 64 bases


def test_derive_rechaza_no_base(catalog):
    base = _base_fc(catalog)
    base.loc[0, ct.COL_GEO_LEVEL] = "nacional"
    with pytest.raises(ev.EvaluationError):
        ev.derive_forecast_products(base, catalog)


# ── Alineación + MetricFrame end-to-end (pequeño) ──
def _truth(level, geo, sex, weeks, values, disease="obesidad") -> list[dict]:
    return [
        {
            "disease_id": disease,
            ct.COL_GEO_LEVEL: level,
            ct.COL_GEO_ID: geo,
            ct.COL_SEX: sex,
            ct.COL_EPI_YEAR: 2024,
            ct.COL_EPI_WEEK: w,
            ct.COL_DS: date(2024, 1, w),
            spec.COL_Y_CASES: v,
        }
        for w, v in zip(weeks, values, strict=True)
    ]


def test_build_evaluation_frame_alinea_y_exige_verdad():
    fc = pd.DataFrame(
        [
            {
                ct.COL_RUN_ID: "r",
                ct.COL_ENGINE: "e",
                ct.COL_FOLD: "development_2024",
                ct.COL_ORIGIN_EPI_YEAR: 2023,
                ct.COL_ORIGIN_EPI_WEEK: 52,
                ct.COL_HORIZON: 1,
                "disease_id": "obesidad",
                ct.COL_GEO_LEVEL: "nacional",
                ct.COL_GEO_ID: "mx",
                ct.COL_SEX: "general",
                ct.COL_EPI_YEAR: 2024,
                ct.COL_EPI_WEEK: 1,
                ct.COL_DS: date(2024, 1, 1),
                ct.COL_Y_PRED: 10.0,
                ct.COL_YHAT_LOWER: np.nan,
                ct.COL_YHAT_UPPER: np.nan,
            }
        ]
    )
    truth = pd.DataFrame(_truth("nacional", "mx", "general", [1], [9]))
    frame = ev.build_evaluation_frame(fc, truth, "development")
    ct.validate_evaluation_frame(frame)
    assert frame[ct.COL_Y_TRUE].iloc[0] == 9 and frame[ct.COL_Y_PRED].iloc[0] == 10.0
    # Sin verdad → error de alineación.
    with pytest.raises(ev.EvaluationError):
        ev.build_evaluation_frame(fc, truth.iloc[0:0], "development")


def test_build_metric_frame_end_to_end():
    # 1 producto, holdout 2 semanas + verdad de train para MASE lag-1.
    eval_frame = pd.DataFrame(
        [
            {
                ct.COL_RUN_ID: "r",
                ct.COL_ENGINE: "e",
                ct.COL_FOLD: "development_2024",
                ct.COL_SPLIT: "development",
                ct.COL_HORIZON: h,
                "disease_id": "obesidad",
                ct.COL_GEO_LEVEL: "nacional",
                ct.COL_GEO_ID: "mx",
                ct.COL_SEX: "general",
                ct.COL_EPI_YEAR: 2024,
                ct.COL_EPI_WEEK: h,
                ct.COL_DS: date(2024, 1, h),
                ct.COL_Y_TRUE: 10,
                ct.COL_Y_PRED: 12.0,
            }
            for h in (1, 2)
        ]
    )
    # verdad completa (train antes de 2024-W01 + holdout).
    truth_full = pd.DataFrame(
        _truth("nacional", "mx", "general", [1, 2], [10, 10])
        + [
            {
                "disease_id": "obesidad",
                ct.COL_GEO_LEVEL: "nacional",
                ct.COL_GEO_ID: "mx",
                ct.COL_SEX: "general",
                ct.COL_EPI_YEAR: 2023,
                ct.COL_EPI_WEEK: w,
                ct.COL_DS: date(2023, 1, 1),
                spec.COL_Y_CASES: v,
            }
            for w, v in [(51, 8), (52, 12)]
        ]
    )
    mf = ev.build_metric_frame(eval_frame, truth_full, mase_lag=1)
    ct.validate_metric_frame(mf)
    assert len(mf) == 1 and int(mf[ct.COL_N_OBS].iloc[0]) == 2
    assert mf[ct.COL_MAE].iloc[0] == pytest.approx(2.0) and mf[ct.COL_BIAS].iloc[
        0
    ] == pytest.approx(2.0)
