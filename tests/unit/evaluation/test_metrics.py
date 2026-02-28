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

from epiforecast.evaluation.metrics import compute_forecast_metrics, mae, mape, mase, rmse, smape

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

    def test_constant_training_series_returns_none(self):
        """MASE returns None when naive seasonal baseline is perfect (mae_naive=0)."""
        # Constant series → naive baseline has zero error → division by zero → None
        y_train = np.full(60, 500.0)
        y_true = np.array([500.0, 500.0, 500.0])
        y_pred = np.array([501.0, 499.0, 500.0])
        result = mase(y_true, y_pred, y_train, season=52)
        assert result is None


# ── SMAPE Tests ──────────────────────────────────────────────────────────────


class TestSMAPE:
    def test_perfect_predictions(self, perfect):
        y_true, y_pred = perfect
        assert smape(y_true, y_pred) == 0.0

    def test_known_error(self, known_error):
        y_true, y_pred = known_error
        # SMAPE = 100/n * sum(2*|y-yhat| / (|y|+|yhat|))
        # Pair 1: 2*10/(100+110) = 20/210
        # Pair 2: 2*10/(200+190) = 20/390
        # Pair 3: 2*10/(300+310) = 20/610
        expected = (20 / 210 + 20 / 390 + 20 / 610) / 3 * 100
        assert smape(y_true, y_pred) == pytest.approx(expected, rel=1e-3)

    def test_symmetric(self, known_error):
        """SMAPE should be symmetric: smape(y, yhat) == smape(yhat, y)."""
        y_true, y_pred = known_error
        assert smape(y_true, y_pred) == pytest.approx(smape(y_pred, y_true))

    def test_both_zero_excluded(self):
        """Pairs where both y_true and y_pred are 0 should be excluded."""
        y_true = np.array([0.0, 0.0, 100.0])
        y_pred = np.array([0.0, 0.0, 100.0])
        assert smape(y_true, y_pred) == 0.0

    def test_all_zero_returns_zero(self):
        """When all pairs are (0,0), SMAPE is 0.0 (no valid terms)."""
        y_true = np.array([0.0, 0.0])
        y_pred = np.array([0.0, 0.0])
        assert smape(y_true, y_pred) == 0.0

    def test_max_smape(self):
        """When y_pred is opposite sign, SMAPE approaches 200."""
        y_true = np.array([100.0])
        y_pred = np.array([-100.0])
        assert smape(y_true, y_pred) == pytest.approx(200.0)

    def test_range_zero_to_200(self):
        """SMAPE should always be in [0, 200]."""
        rng = np.random.default_rng(42)
        y_true = rng.uniform(0, 100, 50)
        y_pred = rng.uniform(0, 100, 50)
        result = smape(y_true, y_pred)
        assert 0.0 <= result <= 200.0


# ── compute_forecast_metrics Tests ───────────────────────────────────────────


class TestComputeForecastMetrics:
    def test_returns_all_keys(self, perfect):
        y_true, y_pred = perfect
        y_train = np.tile(y_true, 20)
        result = compute_forecast_metrics(y_true, y_pred, y_train)
        assert set(result.keys()) == {"rmse", "mae", "mape", "smape", "mase"}

    def test_perfect_predictions_all_zero(self, perfect):
        y_true, y_pred = perfect
        y_train = np.tile(y_true, 20)
        result = compute_forecast_metrics(y_true, y_pred, y_train)
        assert result["rmse"] == 0.0
        assert result["mae"] == 0.0
        assert result["smape"] == 0.0

    def test_mape_capped_at_999(self):
        """MAPE should be capped at 999.0."""
        y_true = np.array([0.001, 0.001])
        y_pred = np.array([100.0, 100.0])
        y_train = np.ones(100)
        result = compute_forecast_metrics(y_true, y_pred, y_train)
        assert result["mape"] == 999.0

    def test_handles_nan_in_inputs(self):
        """NaN values should be filtered out before computing metrics."""
        y_true = np.array([100.0, np.nan, 300.0])
        y_pred = np.array([110.0, 200.0, 310.0])
        y_train = np.ones(100)
        result = compute_forecast_metrics(y_true, y_pred, y_train)
        assert np.isfinite(result["rmse"])

    def test_short_train_mase_none(self):
        """MASE should be None if y_train is too short."""
        y_true = np.array([100.0, 200.0])
        y_pred = np.array([110.0, 190.0])
        y_train = np.ones(10)
        result = compute_forecast_metrics(y_true, y_pred, y_train)
        assert result["mase"] is None


# ── MAPE edge cases ───────────────────────────────────────────────────────────


class TestMAPEEdgeCases:
    def test_all_zero_actuals_returns_zero(self):
        """When every y_true is 0, MAPE is defined as 0.0 (no valid terms)."""
        y_true = np.array([0.0, 0.0, 0.0])
        y_pred = np.array([1.0, 2.0, 3.0])
        result = mape(y_true, y_pred)
        assert result == 0.0
