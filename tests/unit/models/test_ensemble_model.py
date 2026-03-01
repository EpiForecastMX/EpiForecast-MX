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
from tests.unit.models.conftest import make_epi_df as _make_df

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
        "learning_rate": 0.03,
        "subsample": 0.8,
        "colsample_bytree": 0.7,
        "min_child_weight": 5,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────


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
            "lag_8",
            "lag_13",
            "lag_26",
            "lag_52",
            "roll_4",
            "roll_8",
            "roll_12",
            "roll_26",
            "roll_52",
            "roll_std_13",
            "month",
            "week_of_year",
            "sin_week",
            "cos_week",
            "roc_4",
            "roc_52",
            "covid_flag",
        }
        assert set(feats.columns) == expected

    def test_returns_19_features(self):
        rng = np.random.default_rng(42)
        y = pd.Series(rng.integers(10, 50, 100))
        dates = pd.Series(pd.date_range("2020-01-06", periods=100, freq="W-MON"))
        feats = construir_features_xgb(y, dates)
        assert feats.shape[1] == 20

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

    def test_covid_flag_values(self):
        dates = pd.Series(pd.to_datetime(["2019-01-07", "2020-06-01", "2021-03-15", "2023-01-02"]))
        y = pd.Series([10, 20, 30, 40])
        feats = construir_features_xgb(y, dates)
        assert feats["covid_flag"].iloc[0] == 0  # before COVID
        assert feats["covid_flag"].iloc[1] == 1  # during COVID
        assert feats["covid_flag"].iloc[2] == 1  # during COVID
        assert feats["covid_flag"].iloc[3] == 0  # after COVID

    def test_cyclic_encoding_range(self):
        rng = np.random.default_rng(42)
        y = pd.Series(rng.integers(10, 50, 60))
        dates = pd.Series(pd.date_range("2020-01-06", periods=60, freq="W-MON"))
        feats = construir_features_xgb(y, dates)
        assert feats["sin_week"].min() >= -1.0
        assert feats["sin_week"].max() <= 1.0
        assert feats["cos_week"].min() >= -1.0
        assert feats["cos_week"].max() <= 1.0

    def test_rate_of_change_computed(self):
        """roc_4 usa shifted (y_series.shift(1)) para evitar leakage."""
        y = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0])
        dates = pd.Series(pd.date_range("2020-01-06", periods=8, freq="W-MON"))
        feats = construir_features_xgb(y, dates)
        assert feats["roc_4"].iloc[5] == pytest.approx(1.5)

    def test_roc_no_leakage(self):
        """Verifica que roc_4 no usa y[t] (el target actual)."""
        y = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0])
        dates = pd.Series(pd.date_range("2020-01-06", periods=8, freq="W-MON"))
        feats = construir_features_xgb(y, dates)
        assert feats["roc_4"].iloc[5] != pytest.approx(2.0)
        assert feats["roc_4"].iloc[5] == pytest.approx(1.5)


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
        forecaster._xgb_direct = {"mock": "xgb_direct"}
        forecaster._ensemble_weights = np.array([0.6, 0.4])
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


# ── OOF Residuals ────────────────────────────────────────────────────────────


class TestOOFResiduals:
    def test_oof_residuals_backward_compatible(self, forecaster):
        """Con oof_residual_folds=0, comportamiento identico al actual (in-sample)."""
        forecaster._oof_residual_folds = 0
        mock_prophet = MagicMock()
        mock_prophet.predict.return_value = pd.DataFrame({"yhat": np.ones(100)})
        forecaster._prophet = mock_prophet

        train = pd.DataFrame(
            {
                "ds": pd.date_range("2020-01-06", periods=100, freq="W-MON"),
                "y": np.random.default_rng(42).integers(5, 30, 100).astype(float),
            }
        )
        with (
            patch.object(ensemble_mod, "logger", MagicMock()),
            patch("xgboost.XGBRegressor") as mock_xgb_cls,
        ):
            mock_xgb_inst = MagicMock()
            mock_xgb_cls.return_value = mock_xgb_inst
            forecaster._fit_xgboost(train)

        mock_xgb_inst.fit.assert_called_once()

    def test_oof_residuals_uses_oof_when_enabled(self, forecaster):
        """Con oof_residual_folds > 0, llama a generate_oof_residuals."""
        forecaster._oof_residual_folds = 3
        forecaster._prophet = MagicMock()

        train = pd.DataFrame(
            {
                "ds": pd.date_range("2020-01-06", periods=200, freq="W-MON"),
                "y": np.random.default_rng(42).integers(5, 30, 200).astype(float),
            }
        )
        from epiforecast.models.ensemble.feature_builder import FEATURE_NAMES

        feats = pd.DataFrame({name: np.ones(100) for name in FEATURE_NAMES})
        residuos = np.random.default_rng(42).normal(0, 5, 100)

        with (
            patch.object(ensemble_mod, "logger", MagicMock()),
            patch(
                "epiforecast.models.ensemble.model.generate_oof_residuals",
                return_value=(feats, residuos),
            ) as mock_oof,
            patch("xgboost.XGBRegressor") as mock_xgb_cls,
        ):
            mock_xgb_inst = MagicMock()
            mock_xgb_cls.return_value = mock_xgb_inst
            forecaster._fit_xgboost(train)

        mock_oof.assert_called_once()
        mock_xgb_inst.fit.assert_called_once()

    def test_oof_residuals_empty_fallback(self, forecaster):
        """Datos insuficientes -> fallback a in-sample."""
        forecaster._oof_residual_folds = 3
        mock_prophet = MagicMock()
        mock_prophet.predict.return_value = pd.DataFrame({"yhat": np.ones(50)})
        forecaster._prophet = mock_prophet

        train = pd.DataFrame(
            {
                "ds": pd.date_range("2020-01-06", periods=50, freq="W-MON"),
                "y": np.random.default_rng(42).integers(5, 30, 50).astype(float),
            }
        )
        with (
            patch.object(ensemble_mod, "logger", MagicMock()),
            patch(
                "epiforecast.models.ensemble.model.generate_oof_residuals",
                return_value=(pd.DataFrame(), np.array([])),
            ),
            patch("xgboost.XGBRegressor") as mock_xgb_cls,
        ):
            mock_xgb_inst = MagicMock()
            mock_xgb_cls.return_value = mock_xgb_inst
            forecaster._fit_xgboost(train)

        mock_prophet.predict.assert_called_once()
        mock_xgb_inst.fit.assert_called_once()


# ── Parallel Mode ────────────────────────────────────────────────────────────

MOCK_CONF_PARALLEL = {
    **MOCK_CONF,
    "ensemble_mode": "parallel",
    "parallel_alpha": 1.0,
    "parallel_oof_folds": 2,
    "parallel_oof_cutoff": "2022-06-01",
    "parallel_min_train_weeks": 50,
}


@pytest.fixture
def forecaster_parallel():
    """EnsembleForecaster in parallel mode."""
    df = _make_df()
    with (
        patch.object(ensemble_mod, "conf", MOCK_CONF_PARALLEL),
        patch.object(ensemble_mod, "logger", MagicMock()),
    ):
        return EnsembleForecaster(
            df=df,
            sexo="incrementos_total",
            padecimiento="Alzheimer",
            config=MOCK_CONF_PARALLEL,
        )


class TestParallelMode:
    def test_parallel_mode_stored(self, forecaster_parallel):
        assert forecaster_parallel._ensemble_mode == "parallel"

    def test_parallel_weights_start_none(self, forecaster_parallel):
        assert forecaster_parallel._ensemble_weights is None

    def test_parallel_xgb_direct_start_none(self, forecaster_parallel):
        assert forecaster_parallel._xgb_direct is None

    def test_get_params_includes_mode(self, forecaster_parallel):
        params = forecaster_parallel.get_params()
        assert params["ensemble_mode"] == "parallel"

    def test_sequential_backward_compat(self):
        conf_seq = {**MOCK_CONF, "ensemble_mode": "sequential"}
        df = _make_df()
        with (
            patch.object(ensemble_mod, "conf", conf_seq),
            patch.object(ensemble_mod, "logger", MagicMock()),
        ):
            f = EnsembleForecaster(
                df=df, sexo="incrementos_total", padecimiento="Alzheimer", config=conf_seq
            )
        assert f._ensemble_mode == "sequential"

    def test_default_mode_is_parallel(self):
        """No ensemble_mode in config -> defaults to parallel."""
        conf_no_mode = {k: v for k, v in MOCK_CONF.items() if k != "ensemble_mode"}
        df = _make_df()
        with (
            patch.object(ensemble_mod, "conf", conf_no_mode),
            patch.object(ensemble_mod, "logger", MagicMock()),
        ):
            f = EnsembleForecaster(
                df=df, sexo="incrementos_total", padecimiento="Alzheimer", config=conf_no_mode
            )
        assert f._ensemble_mode == "parallel"


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
