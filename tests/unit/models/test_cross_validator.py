"""Tests for cross_validator.py — ProphetCrossValidator."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

import epiforecast.models.prophet.cross_validator as cv_mod
from epiforecast.models.prophet.cross_validator import ProphetCrossValidator

_MOCK_CONF = {
    "TS_SPLITS": 3,
    "TEST_SIZE": 5,
    "cv_weights": [0.5, 0.75, 1.0, 1.25],
    "cv_timeout_por_fold": 0,
}


def _make_forecaster(n_points: int = 60) -> MagicMock:
    """Minimal mock forecaster with sensible train_data."""
    dates = pd.date_range("2018-01-01", periods=n_points, freq="W")
    forecaster = MagicMock()
    forecaster.padecimiento = "Depresión"  # cohorte neuro: cv_weights aplican
    forecaster.train_data = pd.DataFrame({"ds": dates, "y": np.ones(n_points) * 5})
    forecaster._create_prophet.return_value = MagicMock()
    return forecaster


def _make_cv(n_points: int = 60) -> ProphetCrossValidator:
    forecaster = _make_forecaster(n_points)
    with patch.object(cv_mod, "conf", _MOCK_CONF):
        cv = ProphetCrossValidator(forecaster)
    return cv


class TestInit:
    def test_n_splits_from_conf(self):
        cv = _make_cv()
        assert cv.n_splits == 3

    def test_test_size_from_conf(self):
        cv = _make_cv()
        assert cv.test_size == 5

    def test_cv_weights_loaded(self):
        cv = _make_cv()
        assert cv.cv_weights is not None
        assert len(cv.cv_weights) == 4

    def test_fold_timeout_zero_by_default(self):
        cv = _make_cv()
        assert cv.fold_timeout == 0


class TestAggregateFolds:
    def test_simple_mean_rmse(self):
        cv = _make_cv()
        cv.cv_weights = None
        metrics = cv._aggregate_folds(
            [0.1, 0.2, 0.3],
            [0.05, 0.1, 0.15],
            [10.0, 20.0, 30.0],
            [8.0, 16.0, 24.0],
            [None, 0.8, 0.9],
            [0, 1, 2],
        )
        assert abs(metrics["rmse"] - 0.2) < 1e-9

    def test_simple_mean_mae(self):
        cv = _make_cv()
        cv.cv_weights = None
        metrics = cv._aggregate_folds(
            [0.1, 0.2], [0.04, 0.06], [5.0, 15.0], [4.0, 12.0], [0.9, 0.8], [0, 1]
        )
        assert abs(metrics["mae"] - 0.05) < 1e-9

    def test_all_none_mase_returns_none(self):
        cv = _make_cv()
        cv.cv_weights = None
        metrics = cv._aggregate_folds(
            [0.1, 0.2], [0.05, 0.1], [10.0, 20.0], [8.0, 16.0], [None, None], [0, 1]
        )
        assert metrics["mase"] is None

    def test_mase_excludes_none(self):
        cv = _make_cv()
        cv.cv_weights = None
        metrics = cv._aggregate_folds(
            [0.1, 0.2], [0.05, 0.1], [10.0, 20.0], [8.0, 16.0], [None, 0.8], [0, 1]
        )
        assert abs(metrics["mase"] - 0.8) < 1e-9

    def test_weighted_rmse(self):
        cv = _make_cv()
        cv.cv_weights = [1.0, 2.0, 3.0, 4.0]
        cv.n_splits = 4
        # weights for folds [0, 1, 2] = [1, 2, 3] → weighted avg = (0+0+3)/6 = 0.5
        metrics = cv._aggregate_folds(
            [0.0, 0.0, 1.0],
            [0.0, 0.0, 0.6],
            [0.0, 0.0, 60.0],
            [0.0, 0.0, 50.0],
            [None, None, None],
            [0, 1, 2],
        )
        assert abs(metrics["rmse"] - 0.5) < 1e-9

    def test_returns_all_required_keys(self):
        cv = _make_cv()
        cv.cv_weights = None
        metrics = cv._aggregate_folds([0.1], [0.05], [10.0], [8.0], [0.8], [0])
        assert set(metrics.keys()) == {"rmse", "mae", "mape", "smape", "mase"}

    def test_single_fold(self):
        cv = _make_cv()
        cv.cv_weights = None
        metrics = cv._aggregate_folds([0.42], [0.21], [5.0], [4.0], [0.9], [0])
        assert abs(metrics["rmse"] - 0.42) < 1e-9


class TestFitWithTimeout:
    def test_successful_fit_returns_true(self):
        cv = _make_cv()
        model = MagicMock()
        model.fit.return_value = None
        result = cv._fit_with_timeout(model, pd.DataFrame({"ds": [], "y": []}), timeout_sec=10)
        assert result is True

    def test_timeout_returns_false(self):
        cv = _make_cv()
        model = MagicMock()

        def slow_fit(_data):
            time.sleep(5)

        model.fit.side_effect = slow_fit
        result = cv._fit_with_timeout(model, pd.DataFrame(), timeout_sec=0.01)
        assert result is False


class TestEvaluateCombo:
    def test_timed_out_fold_returns_inf(self):
        cv = _make_cv()
        cv.fold_timeout = 1
        params = {"seasonality_mode": "additive", "changepoint_prior_scale": 0.05}

        with patch.object(cv, "_fit_with_timeout", return_value=False):
            metrics, timed_out, newton_cp = cv.evaluate_combo(params)

        assert timed_out is True
        assert metrics["rmse"] == float("inf")
        assert newton_cp == 0.05

    def test_no_timeout_returns_finite_metrics(self):
        cv = _make_cv(n_points=80)
        cv.fold_timeout = 0
        params = {"seasonality_mode": "additive", "changepoint_prior_scale": 0.05}

        # Mock Prophet model: fit does nothing, predict returns constant yhat
        mock_model = MagicMock()

        def mock_predict(future_df):
            return pd.DataFrame(
                {
                    "ds": future_df["ds"],
                    "yhat": np.ones(len(future_df)),
                }
            )

        mock_model.predict.side_effect = mock_predict
        cv.forecaster._create_prophet.return_value = mock_model

        metrics, timed_out, newton_cp = cv.evaluate_combo(params)

        assert timed_out is False
        assert "rmse" in metrics
        assert metrics["rmse"] != float("inf")

    def test_empty_folds_returns_inf(self):
        cv = _make_cv(n_points=60)
        cv.fold_timeout = 0
        params = {"seasonality_mode": "additive", "changepoint_prior_scale": 0.05}

        # Force exception in each fold by making _create_prophet raise
        cv.forecaster._create_prophet.side_effect = RuntimeError("no data")

        metrics, timed_out, newton_cp = cv.evaluate_combo(params)
        assert metrics["rmse"] == float("inf")
