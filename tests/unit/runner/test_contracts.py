"""F2/C3.2 — contratos definitivos: TrainingSpec (solo bases) + frames fila-a-fila validados."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from epiforecast.data.epi_dataset_spec import SeriesKey
from epiforecast.runner import contracts as c

_ENG = "seasonal_naive_lag52"


def _base_key() -> SeriesKey:
    return SeriesKey("obesidad", "estado", "05", "hombres")


def _spec(**over):
    args = dict(
        key=_base_key(),
        engine=_ENG,
        dataset_digest="dd",
        policy_name="rolling_cv_v1",
        policy_digest="pd",
        fold_id="development_2024",
        seed=42,
        horizon=52,
        transform=c.identity_transform("obesidad", _ENG),
    )
    args.update(over)
    return c.TrainingSpec(**args)


# ── TrainingSpec: SOLO las 64 bases estado×sexo ──
def test_training_spec_valido():
    spec = _spec()
    assert spec.horizon == 52 and spec.transform.target_space.value == "count"
    assert c.series_key_str(_base_key()) == "obesidad/estado/05/hombres"


@pytest.mark.parametrize(
    "key",
    [
        SeriesKey("obesidad", "nacional", "mx", "general"),
        SeriesKey("obesidad", "region", "norte", "hombres"),
        SeriesKey("obesidad", "estado", "05", "general"),  # general no es base
    ],
)
def test_training_spec_rechaza_no_base(key):
    with pytest.raises(c.ContractError):
        _spec(key=key)


@pytest.mark.parametrize("horizon", [0, -1, True])
def test_training_spec_horizon_invalido(horizon):
    with pytest.raises(c.ContractError):
        _spec(horizon=horizon)


def test_training_spec_transform_engine_mismatch():
    with pytest.raises(c.ContractError):
        _spec(transform=c.identity_transform("obesidad", "otro_motor"))


# ── ForecastFrame (forecast.v1): fila a fila, intervalos conjuntos, no negativos ──
def _fc(**over) -> pd.DataFrame:
    base = {
        c.COL_RUN_ID: "r",
        c.COL_ENGINE: _ENG,
        c.COL_FOLD: "development_2024",
        c.COL_ORIGIN_EPI_YEAR: 2023,
        c.COL_ORIGIN_EPI_WEEK: 52,
        c.COL_HORIZON: 1,
        "disease_id": "obesidad",
        c.COL_GEO_LEVEL: "estado",
        c.COL_GEO_ID: "05",
        c.COL_SEX: "hombres",
        c.COL_EPI_YEAR: 2024,
        c.COL_EPI_WEEK: 1,
        c.COL_DS: date(2024, 1, 1),
        c.COL_Y_PRED: 10.0,
        c.COL_YHAT_LOWER: 8.0,
        c.COL_YHAT_UPPER: 12.0,
    }
    base.update(over)
    return pd.DataFrame([base])


def test_forecast_frame_valido_y_intervalos_nulos():
    assert c.validate_forecast_frame(_fc()) is not None
    # intervalos conjuntamente nulos → válido.
    c.validate_forecast_frame(_fc(**{c.COL_YHAT_LOWER: None, c.COL_YHAT_UPPER: None}))


@pytest.mark.parametrize(
    "over",
    [
        {c.COL_Y_PRED: -1.0},  # negativo
        {c.COL_Y_PRED: float("inf")},  # no finito
        {c.COL_Y_PRED: float("nan")},  # NaN
        {c.COL_YHAT_LOWER: None},  # un intervalo nulo y el otro no
        {c.COL_YHAT_LOWER: 11.0},  # lower > y_pred
        {c.COL_YHAT_UPPER: 9.0},  # upper < y_pred
        {c.COL_YHAT_LOWER: -1.0},  # intervalo negativo
        {c.COL_GEO_LEVEL: "planeta"},
        {c.COL_SEX: "otro"},
        {c.COL_HORIZON: 0},
    ],
)
def test_forecast_frame_invariantes(over):
    with pytest.raises(c.ContractError):
        c.validate_forecast_frame(_fc(**over))


def test_forecast_frame_columna_faltante_y_duplicados():
    with pytest.raises(c.ContractError):
        c.validate_forecast_frame(_fc().drop(columns=[c.COL_Y_PRED]))
    with pytest.raises(c.ContractError):
        c.validate_forecast_frame(pd.concat([_fc(), _fc()], ignore_index=True))


# ── EvaluationFrame (evaluation.v1): unión verdad↔predicción fila a fila ──
def _ev(**over) -> pd.DataFrame:
    base = {
        c.COL_RUN_ID: "r",
        c.COL_ENGINE: _ENG,
        c.COL_FOLD: "development_2024",
        c.COL_SPLIT: "development",
        c.COL_HORIZON: 1,
        "disease_id": "obesidad",
        c.COL_GEO_LEVEL: "nacional",
        c.COL_GEO_ID: "mx",
        c.COL_SEX: "general",
        c.COL_EPI_YEAR: 2024,
        c.COL_EPI_WEEK: 1,
        c.COL_DS: date(2024, 1, 1),
        c.COL_Y_TRUE: 9,
        c.COL_Y_PRED: 10.0,
    }
    base.update(over)
    return pd.DataFrame([base])


def test_evaluation_frame_valido():
    assert c.validate_evaluation_frame(_ev()) is not None


@pytest.mark.parametrize(
    "over",
    [
        {c.COL_SPLIT: "otro"},
        {c.COL_Y_TRUE: -1},
        {c.COL_Y_PRED: float("nan")},
    ],
)
def test_evaluation_frame_invariantes(over):
    with pytest.raises(c.ContractError):
        c.validate_evaluation_frame(_ev(**over))


def test_evaluation_frame_duplicados():
    with pytest.raises(c.ContractError):
        c.validate_evaluation_frame(pd.concat([_ev(), _ev()], ignore_index=True))


# ── MetricFrame (metrics.v1): resumen; NaN OK (flag), nunca inf ──
def _mt(**over) -> pd.DataFrame:
    base = {
        c.COL_ENGINE: _ENG,
        c.COL_FOLD: "development_2024",
        c.COL_SPLIT: "development",
        "disease_id": "obesidad",
        c.COL_GEO_LEVEL: "nacional",
        c.COL_GEO_ID: "mx",
        c.COL_SEX: "general",
        c.COL_N_OBS: 52,
        c.COL_SMAPE: 12.3,
        c.COL_MASE: 0.8,
        c.COL_MAE: 2.0,
        c.COL_RMSE: 3.1,
        c.COL_WAPE: 0.5,
        c.COL_BIAS: -0.2,
        c.COL_FLAGS: "",
    }
    base.update(over)
    return pd.DataFrame([base])


def test_metric_frame_valido_con_nan_flag():
    # MASE con denominador cero → NaN + flag (válido; nunca inf).
    out = c.validate_metric_frame(
        _mt(**{c.COL_MASE: float("nan"), c.COL_FLAGS: "mase_zero_denom"})
    )
    assert out is not None
    assert c.validate_metric_frame(_mt()) is not None


@pytest.mark.parametrize(
    "over",
    [
        {c.COL_MASE: float("inf")},  # inf prohibido
        {c.COL_N_OBS: 0},
        {c.COL_GEO_LEVEL: "planeta"},
        {c.COL_SPLIT: "otro"},
    ],
)
def test_metric_frame_invariantes(over):
    with pytest.raises(c.ContractError):
        c.validate_metric_frame(_mt(**over))


def test_metric_frame_duplicados():
    with pytest.raises(c.ContractError):
        c.validate_metric_frame(pd.concat([_mt(), _mt()], ignore_index=True))
