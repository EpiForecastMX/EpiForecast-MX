# tests/unit/models/test_ensemble_model.py
"""Unit tests for EnsembleForecaster (Prophet base + XGBoost residual correction).

Mocks Prophet and XGBoost so no real training occurs. Tests the data pipeline,
feature engineering, serialization, and factory registration.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from epiforecast.models.ensemble.helpers import construir_features_xgb, construir_holidays
import epiforecast.models.ensemble.model as ensemble_mod
from epiforecast.models.ensemble.model import EnsembleForecaster

# ── Mock conf ─────────────────────────────────────────────────────────────────

MOCK_CONF = {
    "padecimiento": {
        "modelado_estados": False,
        "entrena_modelo": True,
    },
    "paths": {"models": "/tmp/epi_test/models"},
    "data": {"model_train": "/tmp/epi_test/train"},
    "peridos_atipicos": [
        {"holiday": "COVID", "ds": "2020-03-23", "lower_window": 0, "upper_window": 913}
    ],
    "FECHA_CORTE_ENTRENAMIENTO_ENSEMBLE": "2023-06-01",
    "HORIZON_ENSEMBLE": 52,
    "prophet_base": {
        "changepoint_prior_scale": 0.05,
        "seasonality_prior_scale": 0.1,
        "seasonality_mode": "additive",
        "yearly_custom": {"period": 365.25, "fourier_order": 10},
    },
    "xgboost": {
        "n_estimators": 50,
        "max_depth": 3,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_df(n_weeks: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2019-01-07", periods=n_weeks, freq="W-MON")
    return pd.DataFrame(
        {
            "Fecha": dates,
            "Padecimiento": ["Alzheimer"] * n_weeks,
            "Entidad": ["Nacional"] * n_weeks,
            "incrementos_total": rng.integers(5, 30, n_weeks),
        }
    )


@pytest.fixture
def forecaster():
    """EnsembleForecaster with mocked conf and Prophet/XGBoost."""
    df = _make_df()
    with (
        patch.object(ensemble_mod, "conf", MOCK_CONF),
        patch.object(ensemble_mod, "logger", MagicMock()),
    ):
        return EnsembleForecaster(
            df=df,
            sexo="incrementos_total",
            padecimiento="Alzheimer",
        )


# ── __init__ ──────────────────────────────────────────────────────────────────


class TestEnsembleInit:
    def test_df_copied(self, forecaster):
        assert not forecaster.df.empty

    def test_sexo_stored(self, forecaster):
        assert forecaster.sexo == "incrementos_total"

    def test_padecimiento_stored(self, forecaster):
        assert forecaster.padecimiento == "Alzheimer"

    def test_prophet_starts_none(self, forecaster):
        assert forecaster._prophet is None

    def test_xgb_starts_none(self, forecaster):
        assert forecaster._xgb is None

    def test_serie_starts_empty(self, forecaster):
        assert forecaster.serie.empty

    def test_config_keys_loaded(self, forecaster):
        assert forecaster.cutoff == "2023-06-01"
        assert forecaster.horizon == 52


# ── construir_features_xgb ──────────────────────────────────────────────────


class TestConstruirFeaturesXgb:
    def test_returns_expected_columns(self):
        rng = np.random.default_rng(42)
        y = pd.Series(rng.integers(10, 50, 100))
        dates = pd.Series(pd.date_range("2020-01-06", periods=100, freq="W-MON"))
        feats = construir_features_xgb(y, dates)
        expected = {
            "lag_1",
            "lag_2",
            "lag_4",
            "roll_4",
            "roll_8",
            "roll_12",
            "month",
            "week_of_year",
        }
        assert set(feats.columns) == expected

    def test_lag_values_correct(self):
        y = pd.Series([10, 20, 30, 40, 50])
        dates = pd.Series(pd.date_range("2020-01-06", periods=5, freq="W-MON"))
        feats = construir_features_xgb(y, dates)
        assert feats["lag_1"].iloc[1] == 10.0
        assert feats["lag_2"].iloc[2] == 10.0

    def test_rolling_mean_computed(self):
        y = pd.Series([10.0] * 20)
        dates = pd.Series(pd.date_range("2020-01-06", periods=20, freq="W-MON"))
        feats = construir_features_xgb(y, dates)
        # Rolling mean of constant series should be constant
        assert feats["roll_4"].iloc[5] == pytest.approx(10.0)


# ── construir_holidays ──────────────────────────────────────────────────────


class TestConstruirHolidays:
    def test_returns_dataframe(self):
        result = construir_holidays(MOCK_CONF)
        assert isinstance(result, pd.DataFrame)
        assert "holiday" in result.columns

    def test_covid_present(self):
        result = construir_holidays(MOCK_CONF)
        assert "COVID" in result["holiday"].values

    def test_empty_config(self):
        result = construir_holidays({})
        assert len(result) == 0


# ── get_params ────────────────────────────────────────────────────────────────


class TestGetParams:
    def test_returns_dict(self, forecaster):
        result = forecaster.get_params()
        assert isinstance(result, dict)

    def test_has_prophet_and_xgb_keys(self, forecaster):
        result = forecaster.get_params()
        assert "prophet" in result
        assert "xgboost" in result


# ── save / load ───────────────────────────────────────────────────────────────


class TestSaveLoad:
    def test_save_raises_when_no_model(self, forecaster, tmp_path):
        with pytest.raises(RuntimeError, match="No hay modelo"):
            forecaster.save(tmp_path / "model.pkl")

    def test_save_creates_file(self, forecaster, tmp_path):
        forecaster._prophet = {"mock": "prophet"}
        forecaster._xgb = {"mock": "xgb"}
        path = tmp_path / "model.pkl"
        with patch.object(ensemble_mod, "logger", MagicMock()):
            forecaster.save(path)
        assert path.exists()

    def test_load_raises_file_not_found(self, forecaster, tmp_path):
        with pytest.raises(FileNotFoundError):
            forecaster.load(tmp_path / "ghost.pkl")

    def test_load_restores_models(self, forecaster, tmp_path):
        import pickle

        path = tmp_path / "model.pkl"
        payload = {
            "prophet": {"mock": True},
            "xgb": {"mock": True},
            "params": {},
            "features": ["lag_1"],
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)

        with patch.object(ensemble_mod, "logger", MagicMock()):
            forecaster.load(path)
        assert forecaster._prophet is not None
        assert forecaster._xgb is not None


# ── Factory registration ─────────────────────────────────────────────────────


class TestFactoryRegistration:
    def test_registered_in_factory(self):
        from epiforecast.models.factory import list_models

        assert "ensemble" in list_models()

    def test_create_model_returns_ensemble(self):
        from epiforecast.models.factory import create_model

        df = _make_df()
        with (
            patch.object(ensemble_mod, "conf", MOCK_CONF),
            patch.object(ensemble_mod, "logger", MagicMock()),
        ):
            obj = create_model(
                "ensemble", df=df, sexo="incrementos_total", padecimiento="Alzheimer"
            )
        assert isinstance(obj, EnsembleForecaster)
