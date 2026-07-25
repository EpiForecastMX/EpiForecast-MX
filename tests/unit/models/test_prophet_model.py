# tests/unit/models/test_prophet_model.py
"""Unit tests for ProphetForecaster (src/epiforecast/models/prophet/model.py).

Mocks Prophet, conf, and logger so no real model training occurs.
"""

import pickle
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from epiforecast.artifacts import resolve_transform_contract
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
            "Total": [5_000_000] * n_weeks,
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

    def test_perfil_de_tasa_usa_contrato_tipado_aunque_config_plana_diga_lo_contrario(self):
        config = {
            **MOCK_CONF,
            "normalizar_tasa": False,
            "log_transform": False,
            "tasa_por": 17,
        }
        with patch("epiforecast.models.prophet.model.Prophet"):
            obj = ProphetForecaster(
                _make_df(padecimiento="Depresión"),
                sexo="incrementos_hombres",
                entidad="Jalisco",
                padecimiento="Depresión",
                config=config,
            )
        assert obj.normalizar_tasa is True
        assert obj.log_transform is True
        assert obj.tasa_por == 100_000

    def test_padecimiento_desconocido_no_cae_al_adaptador_legacy(self):
        with (
            patch.object(model_mod, "logger", MagicMock()),
            patch("epiforecast.models.prophet.model.Prophet"),
            pytest.raises(ValueError, match="padecimiento desconocido"),
        ):
            ProphetForecaster(
                _make_df(padecimiento="Obesdiad"),
                sexo="incrementos_hombres",
                entidad="Jalisco",
                padecimiento="Obesdiad",
                config=MOCK_CONF,
            )

    def test_normalizar_tasa_from_registered_contract(self, forecaster):
        assert forecaster.normalizar_tasa is True

    def test_log_transform_from_registered_contract(self, forecaster):
        assert forecaster.log_transform is True

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

    def test_registered_rate_rechaza_dataset_sin_exposure(self):
        df = _make_df(padecimiento="Depresión").drop(columns="Total")
        with patch("epiforecast.models.prophet.model.Prophet"):
            obj = ProphetForecaster(
                df,
                sexo="incrementos_hombres",
                entidad="Jalisco",
                padecimiento="Depresión",
                config=MOCK_CONF,
            )
        with pytest.raises(ValueError, match="exposición"):
            obj.agrupa()


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
        pd.DataFrame(
            {
                "ds": pd.date_range("2025-01-06", periods=2, freq="W-MON"),
                "Total": [4_900_000, 5_000_000],
            }
        ).to_csv(path.with_suffix(".csv"), index=False)
        forecaster.load(path)
        assert forecaster._model is not None
        assert forecaster.poblacion_valor == 5_000_000

    def test_rate_model_rechaza_sidecar_ausente(self, forecaster, tmp_path):
        path = tmp_path / "model.pkl"
        with path.open("wb") as f:
            pickle.dump({"mock": "model"}, f)
        with pytest.raises(ValueError, match="sidecar de exposición"):
            forecaster.load(path)


# ── predict ───────────────────────────────────────────────────────────────────


class TestPredict:
    def test_raises_when_not_fitted(self, forecaster):
        with pytest.raises(RuntimeError, match="fit()"):
            forecaster.predict()

    def test_perfil_de_tasa_invierte_log_y_tasa_desde_contrato(self):
        config = {
            **MOCK_CONF,
            "normalizar_tasa": False,
            "log_transform": False,
            "tasa_por": 17,
        }
        with patch("epiforecast.models.prophet.model.Prophet"):
            obj = ProphetForecaster(
                _make_df(padecimiento="Depresión"),
                sexo="incrementos_hombres",
                entidad="Jalisco",
                padecimiento="Depresión",
                config=config,
            )
        population = 126_014_024.0
        cases = 496.0
        model_value = np.log1p(cases / population * 100_000.0)
        model = MagicMock()
        dates = pd.date_range("2026-01-05", periods=1, freq="W-MON")
        model.make_future_dataframe.return_value = pd.DataFrame({"ds": dates})
        model.predict.return_value = pd.DataFrame(
            {
                "ds": dates,
                "yhat": [model_value],
                "yhat_lower": [model_value],
                "yhat_upper": [model_value],
            }
        )
        obj._model = model
        obj.poblacion_valor = population

        out = obj.predict(horizon=1)

        assert out["yhat"].iloc[0] == pytest.approx(cases)

    def test_perfil_de_tasa_no_emite_tasa_como_casos_si_falta_exposure(self):
        with patch("epiforecast.models.prophet.model.Prophet"):
            obj = ProphetForecaster(
                _make_df(padecimiento="Depresión"),
                sexo="incrementos_hombres",
                entidad="Jalisco",
                padecimiento="Depresión",
                config=MOCK_CONF,
            )
        obj._model = MagicMock()

        with pytest.raises(ValueError, match="requiere exposición"):
            obj.predict(horizon=1)

    def test_perfil_de_tasa_alinea_exposure_historica_y_futura_por_fecha(self):
        with patch("epiforecast.models.prophet.model.Prophet"):
            obj = ProphetForecaster(
                _make_df(padecimiento="Depresión"),
                sexo="incrementos_hombres",
                entidad="Jalisco",
                padecimiento="Depresión",
                config=MOCK_CONF,
            )
        dates = pd.date_range("2025-01-06", periods=3, freq="W-MON")
        obj._set_exposure_history(pd.DataFrame({"ds": dates[:2], "Total": [100_000.0, 200_000.0]}))
        model_values = np.log1p([100.0, 50.0, 50.0])
        model = MagicMock()
        model.make_future_dataframe.return_value = pd.DataFrame({"ds": dates})
        model.predict.return_value = pd.DataFrame(
            {
                "ds": dates,
                "yhat": model_values,
                "yhat_lower": model_values,
                "yhat_upper": model_values,
            }
        )
        obj._model = model

        out = obj.predict(horizon=1)

        np.testing.assert_allclose(out["yhat"], [100.0, 100.0, 100.0])

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
        forecaster.poblacion_valor = 5_000_000

        result = forecaster.predict(horizon=horizon)
        assert isinstance(result, pd.DataFrame)
        assert "yhat" in result.columns
        assert len(result) == horizon


def test_cv_alinea_exposure_por_fecha_y_evalua_en_casos():
    from epiforecast.models.prophet.cross_validator import _compute_fold_metrics

    dates = pd.date_range("2025-01-06", periods=2, freq="W-MON")
    exposure = np.array([100_000.0, 200_000.0])
    counts = np.array([100.0, 100.0])
    model_values = np.log1p(counts / exposure * 100_000.0)
    fold = pd.DataFrame(
        {
            "ds": dates,
            "y": model_values,
            "y_original": counts,
            "Total": exposure,
        }
    )
    model = MagicMock()
    model.predict.return_value = pd.DataFrame({"ds": dates, "yhat": model_values})

    metrics = _compute_fold_metrics(
        model,
        fold,
        fold,
        poblacion=200_000.0,
        tasa_por=100_000.0,
        log_transform=True,
        col_poblacion="Total",
        transform_contract=resolve_transform_contract("Depresión", "prophet"),
    )

    assert metrics["rmse"] == pytest.approx(0.0)
    assert metrics["mae"] == pytest.approx(0.0)


def test_cv_count_log_evalua_en_casos_absolutos():
    from epiforecast.models.prophet.cross_validator import _compute_fold_metrics

    dates = pd.date_range("2025-01-06", periods=2, freq="W-MON")
    truth = np.array([0.0, 100.0])
    prediction = np.array([0.0, 50.0])
    fold = pd.DataFrame({"ds": dates, "y": np.log1p(truth)})
    model = MagicMock()
    model.predict.return_value = pd.DataFrame({"ds": dates, "yhat": np.log1p(prediction)})

    metrics = _compute_fold_metrics(
        model,
        fold,
        fold,
        log_transform=True,
        transform_contract=resolve_transform_contract("Dengue", "prophet"),
    )

    assert metrics["rmse"] == pytest.approx(np.sqrt(1_250.0))
    assert metrics["mae"] == pytest.approx(25.0)


def test_eval_rapida_count_log_evalua_en_casos_absolutos():
    from epiforecast.models.prophet.data_prep import eval_rapida

    dates = pd.date_range("2025-01-06", periods=4, freq="W-MON")
    truth = np.array([0.0, 100.0, 0.0, 100.0])
    prediction = np.array([0.0, 50.0, 0.0, 50.0])
    fold = pd.DataFrame({"ds": dates, "y": np.log1p(truth)})
    model = MagicMock()
    model.predict.return_value = pd.DataFrame({"ds": dates, "yhat": np.log1p(prediction)})

    metrics = eval_rapida(
        model,
        fold,
        fold,
        normalizar_tasa=False,
        poblacion_valor=None,
        log_transform=True,
        tasa_por=100_000.0,
        entidad="Nacional",
        sexo="incrementos_hombres",
        transform_contract=resolve_transform_contract("Dengue", "prophet"),
    )

    assert metrics["rmse"] == pytest.approx(np.sqrt(1_250.0))
    assert metrics["mae"] == pytest.approx(25.0)


def test_eval_rapida_alinea_exposure_y_evalua_perfil_de_tasa_en_casos():
    from epiforecast.models.prophet.data_prep import eval_rapida

    dates = pd.date_range("2025-01-06", periods=4, freq="W-MON")
    exposure = np.array([100_000.0, 200_000.0, 300_000.0, 400_000.0])
    counts = np.full(4, 100.0)
    model_values = np.log1p(counts / exposure * 100_000.0)
    fold = pd.DataFrame(
        {
            "ds": dates,
            "y": model_values,
            "y_original": counts,
            "Total": exposure,
        }
    )
    model = MagicMock()
    model.predict.return_value = pd.DataFrame({"ds": dates, "yhat": model_values})

    metrics = eval_rapida(
        model,
        fold,
        fold,
        normalizar_tasa=True,
        poblacion_valor=400_000.0,
        log_transform=True,
        tasa_por=100_000.0,
        entidad="Nacional",
        sexo="incrementos_hombres",
        transform_contract=resolve_transform_contract("Depresión", "prophet"),
    )

    assert metrics["rmse"] == pytest.approx(0.0, abs=1e-12)
    assert metrics["mae"] == pytest.approx(0.0, abs=1e-12)


def test_baja_confianza_evalua_holdout_antes_del_refit_final():
    config = {**MOCK_CONF, "umbral_minimo_semanal": 100}
    with patch("epiforecast.models.prophet.model.Prophet"):
        obj = ProphetForecaster(
            _make_df(),
            sexo="incrementos_hombres",
            entidad="Jalisco",
            padecimiento=None,
            config=config,
        )

    dates = pd.date_range("2025-01-06", periods=8, freq="W-MON")
    obj.serie = pd.DataFrame({"ds": dates, "y": np.arange(8, dtype=float)})
    obj.train_data = obj.serie.iloc[:4].copy()
    obj.test_data = obj.serie.iloc[4:].copy()
    obj.agrupa = MagicMock()
    obj.crea_train_test = MagicMock()
    obj.promedio_semanal = MagicMock(return_value=1.0)

    events: list[str] = []
    obj.fit = MagicMock(
        side_effect=lambda data, _params: events.append(
            "fit_train" if data is obj.train_data else "fit_full"
        )
    )
    null_metrics = {
        "rmse": None,
        "mae": None,
        "mape": None,
        "smape": None,
        "mase": None,
    }
    with (
        patch(
            "epiforecast.models.prophet.prophet_compat.get_param_grid",
            return_value={"seasonality_mode": ["additive"]},
        ),
        patch.object(
            model_mod,
            "eval_rapida",
            side_effect=lambda *_args, **_kwargs: (events.append("eval_holdout") or null_metrics),
        ),
    ):
        obj.run()

    assert events == ["fit_train", "eval_holdout", "fit_full"]


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


class TestObesidadFueraDelCarrilLegacy:
    """C7.1: Obesidad no declara motores legacy, así que el entrenador legacy no la instancia."""

    def test_prophet_legacy_no_puede_construirse_para_obesidad(self):
        from epiforecast.artifacts.transforms import TransformContractError

        with (
            patch("epiforecast.models.prophet.model.Prophet"),
            pytest.raises(TransformContractError, match="no está declarado para entrenamiento"),
        ):
            ProphetForecaster(
                _make_df(padecimiento="Obesidad"),
                sexo="incrementos_hombres",
                entidad="Jalisco",
                padecimiento="Obesidad",
                config=MOCK_CONF,
            )
