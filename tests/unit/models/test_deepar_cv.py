"""Tests for DeepAR cross-validator (metric computation and aggregation)."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from epiforecast.models.deepar.cross_validator import DeepARCrossValidator


@pytest.fixture()
def mock_forecaster() -> MagicMock:
    f = MagicMock()
    f.epochs = 100
    f.cv_n_splits_override = None
    f.cv_test_size_override = None
    f.train_data = MagicMock()
    f.train_data.empty = True
    f._is_multi_series = False
    f.train_data_multi = MagicMock()
    f.train_data_multi.empty = True
    return f


class TestDeepARCVInit:
    def test_default_config(self, mock_forecaster: MagicMock) -> None:
        config = {"TS_SPLITS": 3, "TEST_SIZE": 26}
        cv = DeepARCrossValidator(mock_forecaster, config=config)
        assert cv.n_splits == 3
        assert cv.test_size == 26
        assert cv.cv_epochs == max(25, 100 // 4)

    def test_short_series_cohort_overrides_cv(self) -> None:
        """Cohortes de historia corta (p.ej. Dengue) imponen CV mas ligera."""
        f = MagicMock()
        f.epochs = 100
        f.cv_n_splits_override = 2
        f.cv_test_size_override = 26
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(f, config=config)
        assert cv.n_splits == 2
        assert cv.test_size == 26

    def test_cv_epochs_at_least_25(self) -> None:
        f = MagicMock()
        f.epochs = 40  # 40 // 4 = 10 < 25
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(f, config=config)
        assert cv.cv_epochs == 25

    def test_high_epochs(self) -> None:
        f = MagicMock()
        f.epochs = 400  # 400 // 4 = 100
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(f, config=config)
        assert cv.cv_epochs == 100


class TestComputeMetrics:
    def test_basic_metrics(self, mock_forecaster: MagicMock) -> None:
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(mock_forecaster, config=config)
        y_true = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        yhat = np.array([12.0, 18.0, 33.0, 38.0, 55.0])
        y_train = np.array([5.0, 8.0, 15.0, 22.0, 28.0])
        result = cv._compute_metrics(y_true, yhat, y_train)
        assert "rmse" in result
        assert "mae" in result
        assert "mape" in result
        assert "smape" in result
        assert "mase" in result
        assert result["rmse"] > 0
        assert result["mae"] > 0


class TestAggregateFoldMetrics:
    def test_average_metrics(self, mock_forecaster: MagicMock) -> None:
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(mock_forecaster, config=config)
        result = cv._aggregate_fold_metrics(
            rmse_folds=[1.0, 2.0, 3.0],
            mae_folds=[0.5, 1.5, 2.5],
            mape_folds=[10.0, 20.0, 30.0],
            smape_folds=[8.0, 18.0, 28.0],
            mase_folds=[0.5, 1.0, 1.5],
        )
        assert result["rmse"] == pytest.approx(2.0)
        assert result["mae"] == pytest.approx(1.5)
        assert result["mape"] == pytest.approx(20.0)
        assert result["smape"] == pytest.approx(18.0)
        assert result["mase"] == pytest.approx(1.0)

    def test_empty_folds_returns_none(self, mock_forecaster: MagicMock) -> None:
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(mock_forecaster, config=config)
        result = cv._aggregate_fold_metrics([], [], [], [], [])
        assert result["rmse"] is None
        assert result["mae"] is None
        assert result["mase"] is None

    def test_none_mase_folds(self, mock_forecaster: MagicMock) -> None:
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(mock_forecaster, config=config)
        result = cv._aggregate_fold_metrics(
            rmse_folds=[1.0],
            mae_folds=[0.5],
            mape_folds=[10.0],
            smape_folds=[8.0],
            mase_folds=[None, None],
        )
        assert result["mase"] is None
        assert result["rmse"] == pytest.approx(1.0)

    def test_mixed_mase_folds(self, mock_forecaster: MagicMock) -> None:
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(mock_forecaster, config=config)
        result = cv._aggregate_fold_metrics(
            rmse_folds=[1.0, 2.0],
            mae_folds=[0.5, 1.0],
            mape_folds=[10.0, 20.0],
            smape_folds=[8.0, 16.0],
            mase_folds=[None, 0.8],
        )
        assert result["mase"] == pytest.approx(0.8)


class TestRunInsufficient:
    def test_insufficient_data_returns_none(self) -> None:
        import pandas as pd

        f = MagicMock()
        f.epochs = 100
        f.cv_n_splits_override = None
        f.cv_test_size_override = None
        f.train_data = pd.DataFrame(
            {"ds": pd.Series(dtype="datetime64[ns]"), "y": pd.Series(dtype=float)}
        )
        f._is_multi_series = False
        f.train_data_multi = pd.DataFrame()
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(f, config=config)
        result = cv.run()
        assert result["rmse"] is None

    def test_short_data_returns_none(self) -> None:
        import pandas as pd

        dates = pd.date_range("2024-01-01", periods=10, freq="W-MON")
        f = MagicMock()
        f.epochs = 100
        f.cv_n_splits_override = None
        f.cv_test_size_override = None
        f.train_data = pd.DataFrame({"ds": dates, "y": range(10)})
        f._is_multi_series = False
        f.train_data_multi = pd.DataFrame()
        config = {"TS_SPLITS": 4, "TEST_SIZE": 53}
        cv = DeepARCrossValidator(f, config=config)
        result = cv.run()
        assert result["rmse"] is None
