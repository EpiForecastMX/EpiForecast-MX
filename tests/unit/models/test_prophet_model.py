# tests/unit/models/test_prophet_model.py
"""Unit tests for ProphetForecaster (src/epiforecast/models/prophet/model.py).

Mocks Prophet, conf, and logger so no real model training occurs.
"""

import pickle
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import epiforecast.models.prophet.model as model_mod
from epiforecast.models.prophet.model import ProphetForecaster

# ── Mock conf ─────────────────────────────────────────────────────────────────

MOCK_CONF = {
    "padecimiento": {
        "modelado_estados": True,
        "entrena_modelo": True,
    },
    "paths": {"models": "/tmp/epi_test/models"},
    "data": {"model_train": "/tmp/epi_test/train"},
    "normalizar_tasa": False,
    "columna_poblacion": "Total",
    "tasa_por": 100_000,
    "log_transform": False,
    "param_model": {
        "weekly_seasonality": False,
        "daily_seasonality": False,
        "yearly_seasonality": True,
    },
    "add_seasonality": {
        "name": "monthly",
        "period": 30.5,
        "fourier_order": 5,
        "fourier_order_regional": 3,
    },
    "peridos_atipicos": [
        {"holiday": "COVID", "ds": "2020-03-23", "lower_window": 0, "upper_window": 913}
    ],
    "cambios_regimen": [],
    "FECHA_CORTE_ENTRENAMIENTO": "2023-01-01",
    "n_changepoints_regional": 12,
    "TS_SPLITS": 4,
    "TEST_SIZE": 52,
    "cv_weights": [0.5, 0.75, 1.0, 1.25],
    "cv_timeout_por_fold": 0,
    "cv_timeout_por_combo": 0,
    "param_grid_prophet": {
        "depresion": {
            "seasonality_mode": ["additive"],
            "changepoint_prior_scale": [0.05],
            "seasonality_prior_scale": [0.1],
        },
        "alzheimer": {
            "seasonality_mode": ["multiplicative"],
            "changepoint_prior_scale": [0.03],
            "seasonality_prior_scale": [0.05],
        },
        "parkinson": {
            "seasonality_mode": ["multiplicative"],
            "changepoint_prior_scale": [0.04],
            "seasonality_prior_scale": [0.1],
        },
    },
}


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_df(n_weeks: int = 60, padecimiento: str = "Depresión") -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2021-01-04", periods=n_weeks, freq="W-MON")
    return pd.DataFrame(
        {
            "Fecha": dates,
            "Padecimiento": [padecimiento] * n_weeks,
            "Entidad": ["Jalisco"] * n_weeks,
            "incrementos_hombres": rng.integers(10, 50, n_weeks),
            "incrementos_mujeres": rng.integers(15, 60, n_weeks),
        }
    )


@pytest.fixture
def forecaster():
    """ProphetForecaster instance with mocked conf."""
    df = _make_df()
    with (
        patch.object(model_mod, "conf", MOCK_CONF),
        patch.object(model_mod, "logger", MagicMock()),
        patch("epiforecast.models.prophet.model.Prophet") as mock_prophet_cls,
    ):
        mock_prophet_cls.return_value = MagicMock()
        return ProphetForecaster(
            df, sexo="incrementos_hombres", entidad="Jalisco", padecimiento="Depresión"
        )


# ── __init__ ──────────────────────────────────────────────────────────────────


class TestProphetForecasterInit:
    def test_df_copied(self):
        df = _make_df()
        with (
            patch.object(model_mod, "conf", MOCK_CONF),
            patch.object(model_mod, "logger", MagicMock()),
            patch("epiforecast.models.prophet.model.Prophet"),
        ):
            obj = ProphetForecaster(df.copy(), sexo="incrementos_hombres")
        assert len(obj.df) == len(df)

    def test_fecha_is_datetime(self, forecaster):
        assert pd.api.types.is_datetime64_any_dtype(forecaster.df["Fecha"])

    def test_sexo_stored(self, forecaster):
        assert forecaster.sexo == "incrementos_hombres"

    def test_entidad_stored(self, forecaster):
        assert forecaster.entidad == "Jalisco"

    def test_model_starts_none(self, forecaster):
        assert forecaster._model is None

    def test_serie_starts_empty(self, forecaster):
        assert forecaster.serie.empty

    def test_normalizar_tasa_from_conf(self, forecaster):
        assert forecaster.normalizar_tasa is False

    def test_log_transform_from_conf(self, forecaster):
        assert forecaster.log_transform is False

    def test_tasa_por_from_conf(self, forecaster):
        assert forecaster.tasa_por == 100_000

    def test_modelado_estados_from_conf(self, forecaster):
        assert forecaster.modelado_estados is True

    def test_n_changepoints_regional_applied(self, forecaster):
        # When modelado_estados=True and n_changepoints_regional is set
        assert forecaster.param_model.get("n_changepoints") == 12

    def test_fourier_order_regional_applied(self, forecaster):
        # With modelado_estados=True, fourier_order_regional=3 should override
        assert forecaster.add_seasonality_params["fourier_order"] == 3

    def test_holidays_dataframe(self, forecaster):
        assert isinstance(forecaster.fechas_atipicas, pd.DataFrame)
        assert "holiday" in forecaster.fechas_atipicas.columns

    def test_covid_holiday_present(self, forecaster):
        holidays = forecaster.fechas_atipicas
        assert "COVID" in holidays["holiday"].values


# ── agrupa ────────────────────────────────────────────────────────────────────


class TestAgrupa:
    def test_serie_populated(self, forecaster):
        forecaster.agrupa()
        assert not forecaster.serie.empty

    def test_serie_has_target_column(self, forecaster):
        forecaster.agrupa()
        assert "incrementos_hombres" in forecaster.serie.columns

    def test_serie_indexed_by_fecha(self, forecaster):
        forecaster.agrupa()
        assert forecaster.serie.index.name == "Fecha"

    def test_with_normalizacion(self):
        conf_norm = {**MOCK_CONF, "normalizar_tasa": True}
        df = _make_df()
        df["Total"] = 5_000_000
        with (
            patch.object(model_mod, "conf", conf_norm),
            patch.object(model_mod, "logger", MagicMock()),
            patch("epiforecast.models.prophet.model.Prophet"),
        ):
            obj = ProphetForecaster(df, sexo="incrementos_hombres")
        obj.agrupa()
        assert "Total" in obj.serie.columns


# ── crea_train_test ───────────────────────────────────────────────────────────


class TestCreaTrainTest:
    def test_creates_train_data(self, forecaster):
        forecaster.agrupa()
        forecaster.crea_train_test()
        assert not forecaster.train_data.empty

    def test_creates_test_data(self, forecaster):
        forecaster.agrupa()
        forecaster.crea_train_test()
        # test_data may be empty if all data is before the cutoff;
        # just verify it's a DataFrame with expected columns
        assert isinstance(forecaster.test_data, pd.DataFrame)

    def test_y_column_exists(self, forecaster):
        forecaster.agrupa()
        forecaster.crea_train_test()
        assert "y" in forecaster.serie.columns

    def test_ds_column_exists(self, forecaster):
        forecaster.agrupa()
        forecaster.crea_train_test()
        assert "ds" in forecaster.serie.columns

    def test_log_transform_applied(self):
        conf_log = {**MOCK_CONF, "log_transform": True}
        df = _make_df()
        with (
            patch.object(model_mod, "conf", conf_log),
            patch.object(model_mod, "logger", MagicMock()),
            patch("epiforecast.models.prophet.model.Prophet"),
        ):
            obj = ProphetForecaster(df, sexo="incrementos_hombres")
        obj.agrupa()
        obj.crea_train_test()
        # After log1p, all y values should be >= 0
        assert (obj.serie["y"] >= 0).all()

    def test_train_before_cutoff(self, forecaster):
        forecaster.agrupa()
        forecaster.crea_train_test()
        cutoff = pd.Timestamp(MOCK_CONF["FECHA_CORTE_ENTRENAMIENTO"])
        assert (forecaster.train_data["ds"] < cutoff).all()

    def test_test_on_or_after_cutoff(self, forecaster):
        forecaster.agrupa()
        forecaster.crea_train_test()
        cutoff = pd.Timestamp(MOCK_CONF["FECHA_CORTE_ENTRENAMIENTO"])
        if not forecaster.test_data.empty:
            assert (forecaster.test_data["ds"] >= cutoff).all()


# ── promedio_semanal ──────────────────────────────────────────────────────────


class TestPromedioSemanal:
    def test_returns_float(self, forecaster):
        forecaster.agrupa()
        forecaster.crea_train_test()
        result = forecaster.promedio_semanal()
        assert isinstance(result, float)

    def test_positive_value(self, forecaster):
        forecaster.agrupa()
        forecaster.crea_train_test()
        assert forecaster.promedio_semanal() > 0


# ── get_params ────────────────────────────────────────────────────────────────


class TestGetParams:
    def test_returns_dict(self, forecaster):
        result = forecaster.get_params()
        assert isinstance(result, dict)

    def test_has_expected_keys(self, forecaster):
        result = forecaster.get_params()
        assert "param_model" in result
        assert "normalizar_tasa" in result
        assert "log_transform" in result

    def test_tasa_por_value(self, forecaster):
        result = forecaster.get_params()
        assert result["tasa_por"] == 100_000


# ── save / load ───────────────────────────────────────────────────────────────


class TestSaveLoad:
    def test_save_raises_when_no_model(self, forecaster, tmp_path):
        with pytest.raises(RuntimeError, match="No model"):
            forecaster.save(tmp_path / "model.pkl")

    def test_save_creates_file(self, forecaster, tmp_path):
        # Use a real picklable object instead of MagicMock
        forecaster._model = {"mock": "model"}
        path = tmp_path / "model.pkl"
        forecaster.save(path)
        assert path.exists()

    def test_load_raises_file_not_found(self, forecaster, tmp_path):
        with pytest.raises(FileNotFoundError):
            forecaster.load(tmp_path / "ghost.pkl")

    def test_load_sets_model(self, forecaster, tmp_path):
        # Write a simple picklable object
        path = tmp_path / "model.pkl"
        with path.open("wb") as f:
            pickle.dump({"mock": "model"}, f)
        forecaster.load(path)
        assert forecaster._model is not None


# ── predict ───────────────────────────────────────────────────────────────────


class TestPredict:
    def test_raises_when_not_fitted(self, forecaster):
        with pytest.raises(RuntimeError, match="fit()"):
            forecaster.predict()

    def test_returns_dataframe_when_fitted(self, forecaster):
        mock_model = MagicMock()
        horizon = 10
        dates = pd.date_range("2024-01-01", periods=horizon, freq="W-MON")
        mock_fc = pd.DataFrame(
            {
                "ds": dates,
                "yhat": [1.0] * horizon,
                "yhat_lower": [0.5] * horizon,
                "yhat_upper": [1.5] * horizon,
            }
        )
        mock_model.make_future_dataframe.return_value = pd.DataFrame({"ds": dates})
        mock_model.predict.return_value = mock_fc
        forecaster._model = mock_model

        result = forecaster.predict(horizon=horizon)
        assert isinstance(result, pd.DataFrame)
        assert "yhat" in result.columns
        assert len(result) == horizon


# ── _build_holidays ───────────────────────────────────────────────────────────


class TestBuildHolidays:
    def test_holidays_has_holiday_col(self, forecaster):
        assert "holiday" in forecaster.fechas_atipicas.columns

    def test_holidays_has_ds_col(self, forecaster):
        assert "ds" in forecaster.fechas_atipicas.columns

    def test_entity_regime_change_added(self):
        """cambios_regimen for the matching entity should be included."""
        conf_cambios = {
            **MOCK_CONF,
            "cambios_regimen": [
                {
                    "entidad": "Jalisco",
                    "padecimiento": "Depresión",
                    "holiday": "cambio_jalisco",
                    "ds": "2023-01-09",
                    "lower_window": 0,
                    "upper_window": 365,
                }
            ],
        }
        df = _make_df()
        with (
            patch.object(model_mod, "conf", conf_cambios),
            patch.object(model_mod, "logger", MagicMock()),
            patch("epiforecast.models.prophet.model.Prophet"),
        ):
            obj = ProphetForecaster(
                df, sexo="incrementos_hombres", entidad="Jalisco", padecimiento="Depresión"
            )
        assert "cambio_jalisco" in obj.fechas_atipicas["holiday"].values

    def test_other_entity_regime_not_added(self):
        """cambios_regimen for a different entity should NOT be included."""
        conf_cambios = {
            **MOCK_CONF,
            "cambios_regimen": [
                {
                    "entidad": "Oaxaca",
                    "holiday": "cambio_oaxaca",
                    "ds": "2023-01-09",
                    "lower_window": 0,
                    "upper_window": 365,
                }
            ],
        }
        df = _make_df()
        with (
            patch.object(model_mod, "conf", conf_cambios),
            patch.object(model_mod, "logger", MagicMock()),
            patch("epiforecast.models.prophet.model.Prophet"),
        ):
            obj = ProphetForecaster(df, sexo="incrementos_hombres", entidad="Jalisco")
        assert "cambio_oaxaca" not in obj.fechas_atipicas["holiday"].values
