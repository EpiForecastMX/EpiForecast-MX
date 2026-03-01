# tests/unit/models/test_weight_optimizer.py
"""Unit tests for EnsembleWeightOptimizer."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from epiforecast.models.ensemble.weight_optimizer import EnsembleWeightOptimizer


def _make_train(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2018-01-01", periods=n, freq="W-MON")
    return pd.DataFrame({"ds": dates, "y": rng.integers(5, 30, n).astype(float)})


class TestEnsembleWeightOptimizer:
    def test_weights_sum_to_one(self):
        train = _make_train(300)
        rng = np.random.default_rng(42)

        def mock_prophet_builder(df):
            m = MagicMock()
            m.predict.side_effect = lambda x: pd.DataFrame({"yhat": rng.normal(15, 2, len(x))})
            return m

        def mock_xgb_builder(df):
            xgb = MagicMock()
            xgb.predict_recursive.side_effect = lambda hist, dates: rng.normal(15, 2, len(dates))
            return xgb

        opt = EnsembleWeightOptimizer(alpha=1.0, n_folds=3, min_train_weeks=100)
        with patch("epiforecast.models.ensemble.weight_optimizer.logger", MagicMock()):
            weights = opt.fit_oof(train, mock_prophet_builder, mock_xgb_builder, "2023-06-01")

        assert len(weights) == 2
        assert weights.sum() == pytest.approx(1.0, abs=0.01)
        assert (weights >= 0).all()

    def test_fallback_equal_weights(self):
        # Very short series -> no valid folds
        train = _make_train(30)

        opt = EnsembleWeightOptimizer(alpha=1.0, n_folds=4, min_train_weeks=104)
        with patch("epiforecast.models.ensemble.weight_optimizer.logger", MagicMock()):
            weights = opt.fit_oof(
                train, lambda df: MagicMock(), lambda df: MagicMock(), "2018-06-01"
            )

        assert len(weights) == 2
        assert weights[0] == pytest.approx(0.5)
        assert weights[1] == pytest.approx(0.5)

    def test_weights_nonnegative(self):
        train = _make_train(250)
        rng = np.random.default_rng(42)

        def mock_prophet_builder(df):
            m = MagicMock()
            m.predict.side_effect = lambda x: pd.DataFrame({"yhat": rng.normal(15, 2, len(x))})
            return m

        def mock_xgb_builder(df):
            xgb = MagicMock()
            xgb.predict_recursive.side_effect = lambda hist, dates: rng.normal(15, 2, len(dates))
            return xgb

        opt = EnsembleWeightOptimizer(alpha=1.0, n_folds=2, min_train_weeks=80)
        with patch("epiforecast.models.ensemble.weight_optimizer.logger", MagicMock()):
            weights = opt.fit_oof(train, mock_prophet_builder, mock_xgb_builder, "2022-06-01")

        assert (weights >= 0).all()
