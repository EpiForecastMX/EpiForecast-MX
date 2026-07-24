"""F2/C2 — contratos del runner: TrainingSpec + validadores de ForecastFrame/EvaluationFrame."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from epiforecast.data.epi_dataset_spec import SeriesKey
from epiforecast.runner import contracts as c


def _key() -> SeriesKey:
    return SeriesKey("obesidad", "nacional", "mx", "general")


def test_training_spec_valido_y_key_str():
    spec = c.TrainingSpec(
        key=_key(),
        engine="prophet",
        horizon_weeks=52,
        profile_id="obesidad_cronica",
        profile_digest="abc",
        transformations=("log1p", "rate_per_100k"),
    )
    assert spec.horizon_weeks == 52 and spec.key.geography_id == "mx"
    assert c.series_key_str(_key()) == "obesidad/nacional/mx/general"


@pytest.mark.parametrize("horizon", [0, -1, True])
def test_training_spec_horizon_invalido(horizon):
    with pytest.raises(c.ContractError):
        c.TrainingSpec(_key(), "prophet", horizon, "p", "d")


def test_training_spec_engine_vacio_y_frecuencia():
    with pytest.raises(c.ContractError):
        c.TrainingSpec(_key(), "", 52, "p", "d")
    with pytest.raises(c.ContractError):
        c.TrainingSpec(
            SeriesKey("obesidad", "nacional", "mx", "general", "daily"), "prophet", 52, "p", "d"
        )


def _forecast_df(**over) -> pd.DataFrame:
    base = {
        c.COL_GEO_LEVEL: "nacional",
        c.COL_GEO_ID: "mx",
        c.COL_SEX: "general",
        c.COL_FREQUENCY: "epi_week",
        c.COL_EPI_YEAR: 2026,
        c.COL_EPI_WEEK: 1,
        c.COL_DS: date(2026, 1, 5),
        c.COL_ENGINE: "prophet",
        c.COL_YHAT: 10.0,
        c.COL_YHAT_LOWER: 8.0,
        c.COL_YHAT_UPPER: 12.0,
    }
    base.update(over)
    return pd.DataFrame([base])


def test_forecast_frame_valido():
    df = _forecast_df()
    assert c.validate_forecast_frame(df) is df


def test_forecast_frame_columna_faltante():
    with pytest.raises(c.ContractError):
        c.validate_forecast_frame(_forecast_df().drop(columns=[c.COL_YHAT_UPPER]))


@pytest.mark.parametrize(
    "over",
    [
        {c.COL_YHAT: float("nan")},
        {c.COL_YHAT_LOWER: 11.0},  # lower > yhat
        {c.COL_YHAT_UPPER: 9.0},  # upper < yhat
        {c.COL_GEO_LEVEL: "planeta"},
        {c.COL_SEX: "otro"},
        {c.COL_FREQUENCY: "daily"},
        {c.COL_ENGINE: ""},
    ],
)
def test_forecast_frame_invariantes(over):
    with pytest.raises(c.ContractError):
        c.validate_forecast_frame(_forecast_df(**over))


def test_forecast_frame_duplicados():
    df = pd.concat([_forecast_df(), _forecast_df()], ignore_index=True)
    with pytest.raises(c.ContractError):
        c.validate_forecast_frame(df)


def _eval_df(**over) -> pd.DataFrame:
    base = {
        c.COL_GEO_LEVEL: "nacional",
        c.COL_GEO_ID: "mx",
        c.COL_SEX: "general",
        c.COL_ENGINE: "prophet",
        c.COL_FOLD: 0,
        c.COL_N_TEST: 52,
        c.COL_SMAPE: 12.3,
        c.COL_MASE: 0.8,
        c.COL_RMSE: 3.1,
        c.COL_MAE: 2.0,
    }
    base.update(over)
    return pd.DataFrame([base])


def test_evaluation_frame_valido():
    df = _eval_df()
    assert c.validate_evaluation_frame(df) is df


@pytest.mark.parametrize(
    "over",
    [
        {c.COL_N_TEST: 0},
        {c.COL_SMAPE: -1.0},
        {c.COL_MASE: float("inf")},
        {c.COL_GEO_LEVEL: "planeta"},
    ],
)
def test_evaluation_frame_invariantes(over):
    with pytest.raises(c.ContractError):
        c.validate_evaluation_frame(_eval_df(**over))


def test_evaluation_frame_duplicados_y_columna():
    with pytest.raises(c.ContractError):
        c.validate_evaluation_frame(pd.concat([_eval_df(), _eval_df()], ignore_index=True))
    with pytest.raises(c.ContractError):
        c.validate_evaluation_frame(_eval_df().drop(columns=[c.COL_MASE]))
