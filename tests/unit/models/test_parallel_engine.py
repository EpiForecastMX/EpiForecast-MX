"""Tests para ParallelEngine: motor de prediccion paralela Prophet + XGBDirect."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from epiforecast.models.ensemble.parallel_engine import ParallelEngine


def _make_train(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2019-01-07", periods=n, freq="W-MON")
    return pd.DataFrame({"ds": dates, "y": rng.integers(5, 30, n).astype(float)})


def _engine() -> ParallelEngine:
    return ParallelEngine(
        prophet_hp={"changepoint_prior_scale": 0.05},
        yearly_period=365.25,
        yearly_fourier=10,
        holidays=pd.DataFrame(),
        xgb_hp={"n_estimators": 50, "max_depth": 3},
        parallel_alpha=1.0,
        parallel_oof_folds=4,
        parallel_oof_cutoff="2023-01-01",
        parallel_min_train_weeks=104,
    )


# ── fit delega a XGBDirect + WeightOptimizer ──────────────────────────────


class TestFit:
    def test_fit_sets_xgb_direct(self):
        engine = _engine()
        train = _make_train()

        mock_xgb = MagicMock()
        mock_opt = MagicMock()
        mock_opt.fit_oof.return_value = np.array([0.6, 0.4])

        with (
            patch(
                "epiforecast.models.ensemble.xgb_direct.XGBDirectForecaster",
                return_value=mock_xgb,
            ),
            patch(
                "epiforecast.models.ensemble.weight_optimizer.EnsembleWeightOptimizer",
                return_value=mock_opt,
            ),
            patch("epiforecast.models.ensemble.parallel_engine.logger", MagicMock()),
        ):
            prophet_mock = MagicMock()
            engine.fit(prophet_mock, train)

        assert engine.xgb_direct is mock_xgb
        mock_xgb.fit.assert_called_once_with(train)

    def test_fit_learns_weights(self):
        engine = _engine()
        train = _make_train()

        mock_xgb = MagicMock()
        mock_opt = MagicMock()
        expected_w = np.array([0.7, 0.3])
        mock_opt.fit_oof.return_value = expected_w

        with (
            patch(
                "epiforecast.models.ensemble.xgb_direct.XGBDirectForecaster",
                return_value=mock_xgb,
            ),
            patch(
                "epiforecast.models.ensemble.weight_optimizer.EnsembleWeightOptimizer",
                return_value=mock_opt,
            ),
            patch("epiforecast.models.ensemble.parallel_engine.logger", MagicMock()),
        ):
            engine.fit(MagicMock(), train)

        np.testing.assert_array_equal(engine.weights, expected_w)

    def test_fit_records_timing(self):
        engine = _engine()
        train = _make_train()

        mock_xgb = MagicMock()
        mock_opt = MagicMock()
        mock_opt.fit_oof.return_value = np.array([0.5, 0.5])

        with (
            patch(
                "epiforecast.models.ensemble.xgb_direct.XGBDirectForecaster",
                return_value=mock_xgb,
            ),
            patch(
                "epiforecast.models.ensemble.weight_optimizer.EnsembleWeightOptimizer",
                return_value=mock_opt,
            ),
            patch("epiforecast.models.ensemble.parallel_engine.logger", MagicMock()),
        ):
            engine.fit(MagicMock(), train)

        assert engine.t_ensemble > 0


# ── predict combina pesos ─────────────────────────────────────────────────


class TestPredict:
    def test_predict_raises_when_not_fitted(self):
        engine = _engine()
        with pytest.raises(RuntimeError, match="no entrenado"):
            engine.predict(MagicMock(), pd.DataFrame(), horizon=4)

    def test_predict_combines_weights(self):
        engine = _engine()
        rng = np.random.default_rng(7)

        # Mock state: fitted engine
        engine._ensemble_weights = np.array([0.6, 0.4])
        mock_xgb = MagicMock()
        mock_xgb.predict_insample.return_value = rng.normal(15, 2, 10)
        mock_xgb.predict_recursive.return_value = rng.normal(15, 2, 5)
        engine._xgb_direct = mock_xgb

        train = _make_train(10)
        prophet_mock = MagicMock()
        prophet_mock.history = {"ds": train["ds"]}
        # Prophet full prediction
        future_dates = pd.date_range(train["ds"].iloc[0], periods=15, freq="W-MON")
        prophet_full = pd.DataFrame({"ds": future_dates, "yhat": rng.normal(14, 2, 15)})
        prophet_mock.make_future_dataframe.return_value = pd.DataFrame({"ds": future_dates})
        prophet_mock.predict.return_value = prophet_full

        result = engine.predict(prophet_mock, train, horizon=5)
        assert "yhat" in result.columns
        assert "yhat_prophet" in result.columns
        assert (result["yhat"] >= 0).all()


# ── cross_validate metricas ───────────────────────────────────────────────


class TestCrossValidate:
    def test_returns_zeros_when_not_fitted(self):
        engine = _engine()
        metrics = engine.cross_validate(
            prophet=MagicMock(),
            test_df=_make_train(20),
            train_data=_make_train(100),
        )
        assert metrics["rmse"] == 0.0
        assert metrics["smape"] == 0.0

    def test_returns_dict_with_expected_keys(self):
        engine = _engine()
        rng = np.random.default_rng(42)
        engine._ensemble_weights = np.array([0.5, 0.5])
        mock_xgb = MagicMock()
        mock_xgb.predict_recursive.return_value = rng.normal(15, 2, 20)
        engine._xgb_direct = mock_xgb

        train = _make_train(100)
        test_df = _make_train(20)
        prophet_mock = MagicMock()
        prophet_mock.predict.return_value = pd.DataFrame({"yhat": rng.normal(15, 2, 20)})

        metrics = engine.cross_validate(prophet_mock, test_df, train)
        assert set(metrics.keys()) == {"rmse", "mae", "smape", "mase"}


# ── gen_insample_preds ────────────────────────────────────────────────────


class TestGenInsamplePreds:
    def test_returns_empty_when_not_fitted(self):
        engine = _engine()
        pred_train, pred_test = engine.gen_insample_preds(
            MagicMock(), _make_train(50), _make_train(10)
        )
        assert pred_train.empty
        assert pred_test.empty

    def test_shapes_match_input(self):
        engine = _engine()
        rng = np.random.default_rng(42)
        engine._ensemble_weights = np.array([0.5, 0.5])
        mock_xgb = MagicMock()
        mock_xgb.predict_insample.return_value = rng.normal(15, 2, 50)
        mock_xgb.predict_recursive.return_value = rng.normal(15, 2, 10)
        engine._xgb_direct = mock_xgb

        train = _make_train(50)
        test = _make_train(10)
        prophet_mock = MagicMock()
        prophet_mock.predict.side_effect = lambda x: pd.DataFrame(
            {"yhat": rng.normal(15, 2, len(x))}
        )

        pred_train, pred_test = engine.gen_insample_preds(prophet_mock, train, test)
        assert len(pred_train) == 50
        assert len(pred_test) == 10
        assert "yhat_ensemble" in pred_train.columns


# ── get_params reporta pesos ─────────────────────────────────────────────


class TestGetParams:
    def test_empty_when_not_fitted(self):
        engine = _engine()
        assert engine.get_params() == {}

    def test_reports_weights(self):
        engine = _engine()
        engine._ensemble_weights = np.array([0.7, 0.3])
        params = engine.get_params()
        assert params["w_prophet"] == pytest.approx(0.7, abs=1e-3)
        assert params["w_xgb"] == pytest.approx(0.3, abs=1e-3)
