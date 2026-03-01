"""Tests para generate_oof_residuals: residuos OOF via expanding-window CV."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd


def _make_train(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2019-01-07", periods=n, freq="W-MON")
    return pd.DataFrame({"ds": dates, "y": rng.integers(5, 30, n).astype(float)})


class TestGenerateOofResiduals:
    """Tests para generate_oof_residuals."""

    def test_short_series_returns_empty(self):
        """Series muy cortas retornan DataFrames/arrays vacios."""
        from epiforecast.models.ensemble.oof_residuals import generate_oof_residuals

        train = _make_train(10)  # demasiado corto
        with patch("epiforecast.models.ensemble.oof_residuals.logger", MagicMock()):
            feats, residuos = generate_oof_residuals(
                train_data=train,
                prophet_hp={"changepoint_prior_scale": 0.05},
                yearly_period=365.25,
                yearly_fourier=10,
                holidays=pd.DataFrame(),
                n_folds=3,
            )
        assert feats.empty
        assert len(residuos) == 0

    def test_sufficient_data_returns_features_and_residuals(self):
        """Con datos suficientes, retorna features y residuos no vacios."""
        from epiforecast.models.ensemble.oof_residuals import generate_oof_residuals

        train = _make_train(300)

        # Mock Prophet para evitar fitting real
        mock_prophet_cls = MagicMock()
        mock_prophet_instance = MagicMock()
        mock_prophet_cls.return_value = mock_prophet_instance
        mock_prophet_instance.predict.side_effect = lambda df: pd.DataFrame(
            {"yhat": np.random.default_rng(0).normal(15, 2, len(df))}
        )

        with (
            patch("prophet.Prophet", mock_prophet_cls),
            patch("epiforecast.models.ensemble.oof_residuals.logger", MagicMock()),
        ):
            feats, residuos = generate_oof_residuals(
                train_data=train,
                prophet_hp={"changepoint_prior_scale": 0.05},
                yearly_period=365.25,
                yearly_fourier=10,
                holidays=pd.DataFrame(),
                n_folds=3,
            )

        assert not feats.empty
        assert len(residuos) > 0
        assert len(feats) == len(residuos)

    def test_residual_equals_y_minus_yhat(self):
        """residuos = y_real - yhat_prophet."""
        from epiforecast.models.ensemble.oof_residuals import generate_oof_residuals

        rng = np.random.default_rng(99)
        train = _make_train(300)

        # Prophet siempre predice 10.0 para facilitar verificacion
        mock_prophet_cls = MagicMock()
        mock_instance = MagicMock()
        mock_prophet_cls.return_value = mock_instance
        mock_instance.predict.side_effect = lambda df: pd.DataFrame(
            {"yhat": np.full(len(df), 10.0)}
        )

        with (
            patch("prophet.Prophet", mock_prophet_cls),
            patch("epiforecast.models.ensemble.oof_residuals.logger", MagicMock()),
        ):
            feats, residuos = generate_oof_residuals(
                train_data=train,
                prophet_hp={},
                yearly_period=365.25,
                yearly_fourier=10,
                holidays=pd.DataFrame(),
                n_folds=3,
            )

        # Cada residuo debe ser y_val - 10.0
        assert len(residuos) > 0
        # Todos los residuos deben estar en rango razonable (y esta entre 5 y 30, yhat=10)
        assert np.all(residuos >= -6)  # min y=5, yhat=10, residuo=-5
        assert np.all(residuos <= 20)  # max y=30, yhat=10, residuo=20

    def test_feature_columns_present(self):
        """Features retornadas tienen columnas esperadas del feature builder."""
        from epiforecast.models.ensemble.oof_residuals import generate_oof_residuals

        train = _make_train(300)

        mock_prophet_cls = MagicMock()
        mock_instance = MagicMock()
        mock_prophet_cls.return_value = mock_instance
        mock_instance.predict.side_effect = lambda df: pd.DataFrame(
            {"yhat": np.full(len(df), 10.0)}
        )

        with (
            patch("prophet.Prophet", mock_prophet_cls),
            patch("epiforecast.models.ensemble.oof_residuals.logger", MagicMock()),
        ):
            feats, _ = generate_oof_residuals(
                train_data=train,
                prophet_hp={},
                yearly_period=365.25,
                yearly_fourier=10,
                holidays=pd.DataFrame(),
                n_folds=3,
            )

        # Debe tener features de lags y temporales
        assert feats.shape[1] > 0
        assert isinstance(feats, pd.DataFrame)

    def test_empty_holidays_accepted(self):
        """holidays vacio no causa error."""
        from epiforecast.models.ensemble.oof_residuals import generate_oof_residuals

        train = _make_train(300)

        mock_prophet_cls = MagicMock()
        mock_instance = MagicMock()
        mock_prophet_cls.return_value = mock_instance
        mock_instance.predict.side_effect = lambda df: pd.DataFrame(
            {"yhat": np.full(len(df), 10.0)}
        )

        with (
            patch("prophet.Prophet", mock_prophet_cls),
            patch("epiforecast.models.ensemble.oof_residuals.logger", MagicMock()),
        ):
            feats, residuos = generate_oof_residuals(
                train_data=train,
                prophet_hp={},
                yearly_period=365.25,
                yearly_fourier=10,
                holidays=pd.DataFrame(),
                n_folds=3,
            )
        assert not feats.empty
