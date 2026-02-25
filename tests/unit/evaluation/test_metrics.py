# tests/unit/evaluation/test_metrics.py
"""Unit tests for evaluation metrics (RMSE, MAE, MAPE, MASE).

These are the first tests in the project — the foundation of
the testing pyramid. Each metric is tested with:
- Perfect predictions (error = 0)
- Known error values (hand-calculated)
- Edge cases (zeros, constant series)
"""

import numpy as np
import pytest

from epiforecast.evaluation.metrics import mae, mape, mase, rmse

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def perfect():
    """Perfect predictions: y_true == y_pred."""
    y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    return y, y.copy()


@pytest.fixture
def known_error():
    """Known error: easy to verify by hand.

    y_true = [100, 200, 300]
    y_pred = [110, 190, 310]
    errors = [10, 10, 10]  → MAE = 10, RMSE = 10
    pct_errors = [10%, 5%, 3.33%]  → MAPE = 6.11%
    """
    y_true = np.array([100.0, 200.0, 300.0])
    y_pred = np.array([110.0, 190.0, 310.0])
    return y_true, y_pred


@pytest.fixture
def seasonal_series():
    """Series with clear seasonal pattern for MASE testing.

    52-week repeating pattern + 12 weeks of test data.
    """
    rng = np.random.default_rng(42)
    pattern = np.sin(np.linspace(0, 2 * np.pi, 52)) * 100 + 500
    y_train = np.tile(pattern, 3)  # 156 weeks
    y_train += rng.normal(0, 5, len(y_train))  # small noise
    return y_train


# ── RMSE Tests ────────────────────────────────────────────────────────────────


class TestRMSE:
    def test_perfect_predictions(self, perfect):
        y_true, y_pred = perfect
        assert rmse(y_true, y_pred) == 0.0

    def test_known_error(self, known_error):
        y_true, y_pred = known_error
        # errors = [10, 10, 10] → MSE = 100 → RMSE = 10
        assert rmse(y_true, y_pred) == pytest.approx(10.0)

    def test_single_value(self):
        assert rmse(np.array([5.0]), np.array([8.0])) == pytest.approx(3.0)

    def test_negative_values(self):
        y_true = np.array([-10.0, -20.0])
        y_pred = np.array([-13.0, -16.0])
        # errors = [3, 4] → MSE = (9+16)/2 = 12.5 → RMSE = 3.5355
        assert rmse(y_true, y_pred) == pytest.approx(np.sqrt(12.5))


# ── MAE Tests ─────────────────────────────────────────────────────────────────


class TestMAE:
    def test_perfect_predictions(self, perfect):
        y_true, y_pred = perfect
        assert mae(y_true, y_pred) == 0.0

    def test_known_error(self, known_error):
        y_true, y_pred = known_error
        # |errors| = [10, 10, 10] → MAE = 10
        assert mae(y_true, y_pred) == pytest.approx(10.0)

    def test_symmetric(self, known_error):
        """MAE should be the same regardless of over/under prediction."""
        y_true, y_pred = known_error
        assert mae(y_true, y_pred) == mae(y_pred, y_true)


# ── MAPE Tests ────────────────────────────────────────────────────────────────


class TestMAPE:
    def test_perfect_predictions(self, perfect):
        y_true, y_pred = perfect
        assert mape(y_true, y_pred) == 0.0

    def test_known_error(self, known_error):
        y_true, y_pred = known_error
        # pct_errors = [10/100, 10/200, 10/300] = [0.1, 0.05, 0.0333]
        # MAPE = mean * 100 = 6.111%
        expected = (0.1 + 0.05 + 10 / 300) / 3 * 100
        assert mape(y_true, y_pred) == pytest.approx(expected, rel=1e-3)

    def test_zero_actuals_handled(self):
        """MAPE with zeros in y_true should not raise or return inf."""
        y_true = np.array([0.0, 100.0, 200.0])
        y_pred = np.array([5.0, 110.0, 190.0])
        result = mape(y_true, y_pred)
        assert np.isfinite(result)


# ── MASE Tests ────────────────────────────────────────────────────────────────


class TestMASE:
    def test_perfect_predictions(self, seasonal_series):
        """MASE = 0 when predictions are perfect."""
        y_train = seasonal_series
        y_true = np.array([500.0, 510.0, 520.0])
        result = mase(y_true, y_true.copy(), y_train, season=52)
        assert result == pytest.approx(0.0)

    def test_naive_predictions_mase_one(self, seasonal_series):
        """MASE ≈ 1 when model error equals naive seasonal error."""
        y_train = seasonal_series
        # Naive seasonal: predict y[t] = y[t-52]
        y_true = y_train[-12:]
        y_naive = y_train[-64:-52]  # lag 52
        result = mase(y_true, y_naive, y_train, season=52)
        assert result == pytest.approx(1.0, rel=0.15)

    def test_better_than_naive(self, seasonal_series):
        """Good model should have MASE < 1."""
        y_train = seasonal_series
        y_true = y_train[-12:]
        # Very good predictions: true + small noise
        rng = np.random.default_rng(99)
        y_pred = y_true + rng.normal(0, 1, len(y_true))
        result = mase(y_true, y_pred, y_train, season=52)
        assert result < 1.0

    def test_short_train_raises(self):
        """MASE needs len(y_train) > season. Should handle gracefully."""
        y_train = np.array([1.0, 2.0, 3.0])  # only 3 points, season=52
        y_true = np.array([4.0, 5.0])
        y_pred = np.array([4.5, 5.5])
        result = mase(y_true, y_pred, y_train, season=52)
        assert result is None or np.isnan(result)
