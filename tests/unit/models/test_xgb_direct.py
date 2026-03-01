# tests/unit/models/test_xgb_direct.py
"""Unit tests for XGBDirectForecaster."""

import pandas as pd
import pytest

from epiforecast.models.ensemble.xgb_direct import XGBDirectForecaster
from tests.unit.models.conftest import make_train_series as _make_train


class TestXGBDirectFit:
    def test_fit_creates_model(self):
        train = _make_train()
        hp = {"n_estimators": 50, "max_depth": 3, "learning_rate": 0.05}
        xgb = XGBDirectForecaster(hp)
        xgb.fit(train)
        assert xgb._model is not None

    def test_fit_with_short_series(self):
        train = _make_train(60)
        hp = {"n_estimators": 20, "max_depth": 2, "learning_rate": 0.1}
        xgb = XGBDirectForecaster(hp)
        xgb.fit(train)
        assert xgb._model is not None


class TestXGBDirectPredict:
    def test_predict_insample_shape(self):
        train = _make_train(150)
        hp = {"n_estimators": 30, "max_depth": 3, "learning_rate": 0.05}
        xgb = XGBDirectForecaster(hp)
        xgb.fit(train)
        result = xgb.predict_insample(train)
        assert len(result) == len(train)

    def test_predict_insample_raises_when_not_fitted(self):
        xgb = XGBDirectForecaster({})
        with pytest.raises(RuntimeError, match="no entrenado"):
            xgb.predict_insample(_make_train(10))

    def test_predict_recursive_shape(self):
        train = _make_train(150)
        hp = {"n_estimators": 30, "max_depth": 3, "learning_rate": 0.05}
        xgb = XGBDirectForecaster(hp)
        xgb.fit(train)
        future = pd.date_range(train["ds"].max() + pd.Timedelta(weeks=1), periods=5, freq="W-MON")
        result = xgb.predict_recursive(train, future.values)
        assert len(result) == 5

    def test_predict_recursive_raises_when_not_fitted(self):
        xgb = XGBDirectForecaster({})
        future = pd.date_range("2024-01-01", periods=3, freq="W-MON")
        with pytest.raises(RuntimeError, match="no entrenado"):
            xgb.predict_recursive(_make_train(10), future.values)
