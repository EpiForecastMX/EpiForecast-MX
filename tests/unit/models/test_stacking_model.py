# tests/unit/models/test_stacking_model.py
"""Unit tests for StackingForecaster (Prophet + ETS + LightGBM + Ridge meta-learner).

Mocks heavy ML dependencies so no real training occurs. Tests the data pipeline,
expert dispatch, meta-learner, serialization, and factory registration.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from epiforecast.models.stacking.experts import ETSExpert, LGBMExpert, ProphetExpert
from epiforecast.models.stacking.meta_learner import StackingMetaLearner
import epiforecast.models.stacking.model as stacking_mod
from epiforecast.models.stacking.model import StackingForecaster
from tests.unit.models.conftest import make_epi_df as _make_df
from tests.unit.models.conftest import make_train_series as _make_series

# ── Mock conf ─────────────────────────────────────────────────────────────────

MOCK_CONF = {
    "padecimiento": {
        "modelado_estados": False,
        "entrena_modelo": True,
    },
    "paths": {"models": "/tmp/epi_test/models"},
    "data": {"model_train": "/tmp/epi_test/train"},
    "peridos_atipicos": [
        {"holiday": "COVID", "ds": "2020-03-23", "lower_window": 0, "upper_window": 913}
    ],
    "FECHA_CORTE_ENTRENAMIENTO_STACKING": "2023-06-01",
    "HORIZON_STACKING": 52,
    "stacking": {
        "oof_cutoff": "2023-01-01",
        "prophet": {
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 0.1,
            "seasonality_mode": "additive",
            "yearly_custom": {"period": 365.25, "fourier_order": 10},
        },
        "ets": {"seasonal_periods": 52, "trend": "add", "seasonal": "add"},
        "lgbm": {"n_estimators": 50, "max_depth": 3, "learning_rate": 0.05},
        "meta_learner": {
            "type": "elasticnet",
            "alpha": 1.0,
            "l1_ratio": 0.5,
            "add_temporal_features": True,
        },
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────


@pytest.fixture
def forecaster():
    """StackingForecaster with mocked conf."""
    df = _make_df()
    with (
        patch.object(stacking_mod, "conf", MOCK_CONF),
        patch.object(stacking_mod, "logger", MagicMock()),
    ):
        return StackingForecaster(
            df=df,
            sexo="incrementos_total",
            padecimiento="Alzheimer",
            config=MOCK_CONF,
        )


# ── __init__ ──────────────────────────────────────────────────────────────────


class TestStackingInit:
    def test_df_copied(self, forecaster):
        assert not forecaster.df.empty

    def test_sexo_stored(self, forecaster):
        assert forecaster.sexo == "incrementos_total"

    def test_padecimiento_stored(self, forecaster):
        assert forecaster.padecimiento == "Alzheimer"

    def test_weights_starts_none(self, forecaster):
        assert forecaster._weights is None

    def test_serie_starts_empty(self, forecaster):
        assert forecaster.serie.empty

    def test_config_keys_loaded(self, forecaster):
        assert forecaster.cutoff == "2023-06-01"
        assert forecaster.horizon == 52

    def test_three_experts_created(self, forecaster):
        assert len(forecaster._experts) == 3

    def test_expert_types(self, forecaster):
        assert isinstance(forecaster._experts[0], ProphetExpert)
        assert isinstance(forecaster._experts[1], ETSExpert)
        assert isinstance(forecaster._experts[2], LGBMExpert)


# ── get_params ────────────────────────────────────────────────────────────────


class TestGetParams:
    def test_returns_dict(self, forecaster):
        result = forecaster.get_params()
        assert isinstance(result, dict)

    def test_has_expected_keys(self, forecaster):
        result = forecaster.get_params()
        assert "cutoff" in result
        assert "horizon" in result
        assert "oof_cutoff" in result
        assert "meta_type" in result
        assert "alpha" in result
        assert "l1_ratio" in result
        assert "add_temporal_features" in result
        assert "peso_prophet" in result

    def test_weights_none_before_fit(self, forecaster):
        params = forecaster.get_params()
        assert params["peso_prophet"] is None
        assert params["peso_ets"] is None
        assert params["peso_lgbm"] is None


# ── save / load ───────────────────────────────────────────────────────────────


class TestSaveLoad:
    def test_save_raises_when_no_model(self, forecaster, tmp_path):
        with pytest.raises(RuntimeError, match="No hay modelo"):
            forecaster.save(tmp_path / "model.pkl")

    def test_save_creates_file(self, forecaster, tmp_path):
        forecaster._weights = np.array([0.5, 0.3, 0.2])
        forecaster._ridge = None
        # Replace experts with simple dicts (pickle-safe)
        forecaster._experts = [{"type": "prophet"}, {"type": "ets"}, {"type": "lgbm"}]
        path = tmp_path / "model.pkl"
        with patch.object(stacking_mod, "logger", MagicMock()):
            forecaster.save(path)
        assert path.exists()

    def test_save_creates_sidecar_csv(self, forecaster, tmp_path):
        forecaster._weights = np.array([0.5, 0.3, 0.2])
        forecaster._ridge = None
        forecaster._experts = [{"type": "prophet"}, {"type": "ets"}, {"type": "lgbm"}]
        forecaster.serie = _make_series(50)
        path = tmp_path / "model.pkl"
        with patch.object(stacking_mod, "logger", MagicMock()):
            forecaster.save(path)
        assert path.with_suffix(".csv").exists()

    def test_load_raises_file_not_found(self, forecaster, tmp_path):
        with pytest.raises(FileNotFoundError):
            forecaster.load(tmp_path / "ghost.pkl")

    def test_load_restores_weights(self, forecaster, tmp_path):
        import pickle

        path = tmp_path / "model.pkl"
        payload = {
            "experts": [{"m": 1}, {"m": 2}, {"m": 3}],
            "ridge": None,
            "weights": np.array([0.5, 0.3, 0.2]),
            "params": {},
            "n_train": 100,
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)

        with patch.object(stacking_mod, "logger", MagicMock()):
            forecaster.load(path)
        assert forecaster._weights is not None
        assert len(forecaster._weights) == 3

    def test_load_restores_from_sidecar_csv(self, forecaster, tmp_path):
        import pickle

        path = tmp_path / "model.pkl"
        csv_path = path.with_suffix(".csv")

        # Write pickle
        payload = {
            "experts": [{"m": 1}, {"m": 2}, {"m": 3}],
            "ridge": None,
            "weights": np.array([0.4, 0.4, 0.2]),
            "params": {},
            "n_train": 50,
            "serie": pd.DataFrame(),
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)

        # Write sidecar CSV
        serie = _make_series(30)
        serie.to_csv(csv_path, index=False)

        with patch.object(stacking_mod, "logger", MagicMock()):
            forecaster.load(path)
        assert not forecaster.serie.empty
        assert len(forecaster.serie) == 30

    def test_load_fallback_to_pickle_serie(self, forecaster, tmp_path):
        import pickle

        path = tmp_path / "model.pkl"
        serie = _make_series(20)
        payload = {
            "experts": [{"m": 1}, {"m": 2}, {"m": 3}],
            "ridge": None,
            "weights": np.array([0.3, 0.3, 0.4]),
            "params": {},
            "n_train": 20,
            "serie": serie,
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)

        with patch.object(stacking_mod, "logger", MagicMock()):
            forecaster.load(path)
        assert not forecaster.serie.empty


# ── predict ───────────────────────────────────────────────────────────────────


class TestPredict:
    def test_predict_raises_when_not_fitted(self, forecaster):
        with pytest.raises(RuntimeError, match="no entrenado"):
            forecaster.predict()

    def test_predict_raises_when_no_serie(self, forecaster):
        forecaster._weights = np.array([0.5, 0.3, 0.2])
        with pytest.raises(RuntimeError, match="No hay serie"):
            forecaster.predict()

    def test_predict_returns_dataframe(self, forecaster):
        n = 100
        serie = _make_series(n)
        forecaster.serie = serie
        forecaster._weights = np.array([0.5, 0.3, 0.2])
        forecaster._n_train = n

        mock_prophet = MagicMock()
        mock_prophet.predict.return_value = np.arange(n + 52, dtype=float)

        mock_ets = MagicMock(spec=ETSExpert)
        mock_ets.predict_full.return_value = (
            np.ones(n, dtype=float),
            np.ones(52, dtype=float),
        )

        mock_lgbm = MagicMock(spec=LGBMExpert)
        mock_lgbm.predict.return_value = np.ones(n + 52, dtype=float)

        forecaster._experts = [mock_prophet, mock_ets, mock_lgbm]
        result = forecaster.predict(horizon=52)

        assert isinstance(result, pd.DataFrame)
        assert "ds" in result.columns
        assert "yhat" in result.columns
        assert "yhat_lower" in result.columns
        assert "yhat_upper" in result.columns
        assert len(result) == n + 52

    def test_predict_values_nonnegative(self, forecaster):
        n = 50
        serie = _make_series(n)
        forecaster.serie = serie
        forecaster._weights = np.array([0.5, 0.3, 0.2])
        forecaster._n_train = n

        mock_prophet = MagicMock()
        mock_prophet.predict.return_value = np.ones(n + 52, dtype=float) * 5.0

        mock_ets = MagicMock(spec=ETSExpert)
        mock_ets.predict_full.return_value = (
            np.ones(n, dtype=float) * 3.0,
            np.ones(52, dtype=float) * 3.0,
        )

        mock_lgbm = MagicMock(spec=LGBMExpert)
        mock_lgbm.predict.return_value = np.ones(n + 52, dtype=float) * 2.0

        forecaster._experts = [mock_prophet, mock_ets, mock_lgbm]
        result = forecaster.predict(horizon=52)
        assert (result["yhat"] >= 0).all()


# ── cross_validate ────────────────────────────────────────────────────────────


class TestCrossValidate:
    def test_returns_zeros_when_not_fitted(self, forecaster):
        result = forecaster.cross_validate(pd.DataFrame())
        assert result["rmse"] == 0.0

    def test_returns_dict_with_expected_keys(self, forecaster):
        forecaster._weights = np.array([0.5, 0.3, 0.2])
        forecaster.train_data = _make_series(100)
        test_df = _make_series(20)

        # Mock experts to return predictions
        for exp in forecaster._experts:
            exp.predict = MagicMock(return_value=test_df["y"].values)

        result = forecaster.cross_validate(test_df)
        assert "rmse" in result
        assert "mae" in result
        assert "smape" in result
        assert "mase" in result

    def test_perfect_prediction_low_error(self, forecaster):
        forecaster.train_data = _make_series(100)
        test_df = _make_series(20)
        forecaster._weights = np.array([1.0, 0.0, 0.0])

        # All experts return perfect prediction
        for exp in forecaster._experts:
            exp.predict = MagicMock(return_value=test_df["y"].values)

        result = forecaster.cross_validate(test_df)
        assert result["rmse"] == pytest.approx(0.0, abs=1e-6)


# ── Factory registration ─────────────────────────────────────────────────────


class TestFactoryRegistration:
    def test_registered_in_factory(self):
        from epiforecast.models.factory import list_models

        assert "stacking" in list_models()

    def test_create_model_returns_stacking(self):
        from epiforecast.models.factory import create_model

        df = _make_df()
        with (
            patch.object(stacking_mod, "conf", MOCK_CONF),
            patch.object(stacking_mod, "logger", MagicMock()),
        ):
            obj = create_model(
                "stacking",
                df=df,
                sexo="incrementos_total",
                padecimiento="Alzheimer",
                config=MOCK_CONF,
            )
        assert isinstance(obj, StackingForecaster)


# ── ETSExpert ─────────────────────────────────────────────────────────────────


class TestETSExpert:
    def test_short_series_falls_back(self):
        """ETS with series shorter than 2*seasonal_periods falls back gracefully."""
        ets = ETSExpert({"seasonal_periods": 52, "trend": "add", "seasonal": "add"})
        short = _make_series(50)  # < 2*52
        with patch("epiforecast.models.stacking.experts.logger", MagicMock()):
            ets.fit(short)
        assert ets._failed is True

    def test_predict_returns_zeros_on_failure(self):
        ets = ETSExpert({"seasonal_periods": 52})
        ets._failed = True
        dates = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=10, freq="W-MON")})
        result = ets.predict(dates)
        assert len(result) == 10
        assert (result == 0).all()

    def test_predict_full_returns_zeros_on_failure(self):
        ets = ETSExpert({"seasonal_periods": 52})
        ets._failed = True
        fitted, fwd = ets.predict_full(10)
        assert fitted is None
        assert len(fwd) == 10

    def test_predict_full_zero_forward(self):
        ets = ETSExpert({"seasonal_periods": 52})
        ets._failed = True
        _, fwd = ets.predict_full(0)
        assert len(fwd) == 0

    def test_predict_full_with_fitted_model(self):
        """predict_full returns fitted values and forward forecast when model is fitted."""
        ets = ETSExpert({"seasonal_periods": 52, "trend": "add", "seasonal": "add"})
        mock_model = MagicMock()
        mock_model.fittedvalues = np.array([10.0, 12.0, 8.0])
        mock_model.forecast.return_value = np.array([11.0, 13.0])
        ets._model = mock_model
        ets._failed = False

        fitted, fwd = ets.predict_full(2)
        assert fitted is not None
        assert len(fitted) == 3
        assert len(fwd) == 2
        assert (fitted >= 0).all()
        assert (fwd >= 0).all()

    def test_predict_negative_clipped_to_zero(self):
        """predict clips negative values to zero."""
        ets = ETSExpert({"seasonal_periods": 52})
        mock_model = MagicMock()
        mock_model.forecast.return_value = np.array([-5.0, 3.0, -1.0])
        ets._model = mock_model
        ets._failed = False

        dates = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=3, freq="W-MON")})
        result = ets.predict(dates)
        assert (result >= 0).all()


# ── ProphetExpert ─────────────────────────────────────────────────────────────


class TestProphetExpert:
    def test_predict_raises_when_not_fitted(self):
        pe = ProphetExpert({"changepoint_prior_scale": 0.05})
        with pytest.raises(RuntimeError, match="no entrenado"):
            pe.predict(pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=5)}))


# ── LGBMExpert ────────────────────────────────────────────────────────────────


class TestLGBMExpert:
    def test_predict_raises_when_not_fitted(self):
        le = LGBMExpert({"n_estimators": 50})
        with pytest.raises(RuntimeError, match="no entrenado"):
            le.predict(pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=5)}))

    def test_build_features_shape(self):
        le = LGBMExpert({})
        dates = pd.Series(pd.date_range("2024-01-01", periods=20, freq="W-MON"))
        feats = le._build_features(dates)
        assert feats.shape == (20, 3)
        assert list(feats.columns) == ["sin_sem", "cos_sem", "trend"]

    def test_build_features_with_offset(self):
        le = LGBMExpert({})
        dates = pd.Series(pd.date_range("2024-01-01", periods=5, freq="W-MON"))
        feats = le._build_features(dates, offset=100)
        assert feats["trend"].iloc[0] == 100.0
        assert feats["trend"].iloc[4] == 104.0

    def test_predict_uses_train_len_as_offset(self):
        """predict uses _train_len as default offset for trend continuation."""
        le = LGBMExpert({"n_estimators": 10})
        le._train_len = 200
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([5.0, 6.0, 7.0])
        le._model = mock_model

        dates = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=3, freq="W-MON")})
        result = le.predict(dates)
        assert len(result) == 3
        assert (result >= 0).all()


# ── StackingMetaLearner ──────────────────────────────────────────────────────


class TestStackingMetaLearner:
    def test_equal_weights_when_few_oof_samples(self):
        experts = [MagicMock(), MagicMock(), MagicMock()]
        ml = StackingMetaLearner(experts, alpha=1.0)
        # Only 2 rows after cutoff (< 4 minimum)
        train = pd.DataFrame(
            {
                "ds": pd.date_range("2023-01-01", periods=5, freq="W-MON"),
                "y": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )
        with patch("epiforecast.models.stacking.meta_learner.logger", MagicMock()):
            weights, ridge = ml.fit_oof(train, "2023-02-01")  # Only 2 rows after cutoff
        assert ridge is None
        assert len(weights) == 3
        assert weights.sum() == pytest.approx(1.0)

    def test_fit_oof_returns_weights_and_ridge(self):
        n_train = 100
        n_val = 20
        rng = np.random.default_rng(42)
        dates = pd.date_range("2022-01-03", periods=n_train + n_val, freq="W-MON")
        y_values = rng.integers(5, 30, n_train + n_val).astype(float)
        train = pd.DataFrame({"ds": dates, "y": y_values})
        cutoff = str(dates[n_train].date())

        mock_experts = []
        for _i in range(3):
            exp = MagicMock()
            exp.predict.side_effect = lambda df: rng.normal(15, 2, len(df))
            mock_experts.append(exp)

        ml = StackingMetaLearner(mock_experts, alpha=1.0, n_folds=2, min_train_weeks=50)
        with patch("epiforecast.models.stacking.meta_learner.logger", MagicMock()):
            weights, ridge = ml.fit_oof(train, cutoff)

        assert ridge is not None
        assert len(weights) == 3
        assert (weights >= 0).all()  # Ridge(positive=True)

    def test_expanding_window_multiple_folds(self):
        """Serie larga: expertos se entrenan multiples veces, pesos suman ~1.0."""
        import copy

        n = 350
        rng = np.random.default_rng(42)
        dates = pd.date_range("2017-01-02", periods=n, freq="W-MON")
        y_values = rng.integers(5, 30, n).astype(float)
        train = pd.DataFrame({"ds": dates, "y": y_values})
        cutoff = str(dates[n - 50].date())

        mock_experts = []
        for _i in range(3):
            exp = MagicMock()
            exp.predict.side_effect = lambda df: rng.normal(15, 2, len(df))
            mock_experts.append(exp)

        # deepcopy must work on mocks
        with patch("epiforecast.models.stacking.meta_learner.copy") as mock_copy:
            mock_copy.deepcopy = copy.deepcopy
            ml = StackingMetaLearner(mock_experts, alpha=1.0, n_folds=4, min_train_weeks=104)
            with patch("epiforecast.models.stacking.meta_learner.logger", MagicMock()):
                weights, ridge = ml.fit_oof(train, cutoff)

        assert ridge is not None
        assert len(weights) == 3
        assert weights.sum() == pytest.approx(1.0, abs=0.01)

    def test_compute_oof_folds_returns_correct_count(self):
        """_compute_oof_folds generates correct number of folds for long series."""
        experts = [MagicMock(), MagicMock(), MagicMock()]
        ml = StackingMetaLearner(experts, n_folds=4, min_train_weeks=52)
        dates = pd.date_range("2017-01-02", periods=350, freq="W-MON")
        rng = np.random.default_rng(42)
        train = pd.DataFrame({"ds": dates, "y": rng.normal(15, 2, 350)})
        cutoff = str(dates[300].date())

        folds = ml._compute_oof_folds(train, cutoff)
        assert len(folds) > 0
        # Each fold has (train, val) tuple
        for fold_train, fold_val in folds:
            assert "ds" in fold_train.columns
            assert "y" in fold_val.columns
            assert len(fold_val) >= 4

    def test_fallback_datos_insuficientes(self):
        """Serie corta: retorna pesos iguales (fallback)."""
        n = 50
        rng = np.random.default_rng(42)
        dates = pd.date_range("2023-01-02", periods=n, freq="W-MON")
        y_values = rng.integers(5, 30, n).astype(float)
        train = pd.DataFrame({"ds": dates, "y": y_values})
        cutoff = str(dates[n - 5].date())

        mock_experts = [MagicMock() for _ in range(3)]
        ml = StackingMetaLearner(mock_experts, alpha=1.0, n_folds=4, min_train_weeks=104)
        with patch("epiforecast.models.stacking.meta_learner.logger", MagicMock()):
            weights, ridge = ml.fit_oof(train, cutoff)

        assert ridge is None
        assert len(weights) == 3
        assert weights.sum() == pytest.approx(1.0)


# ── ElasticNet + Temporal Features ────────────────────────────────────────


class TestElasticNetMetaLearner:
    def test_elasticnet_config_loaded(self, forecaster):
        assert forecaster._meta_type == "elasticnet"
        assert forecaster._l1_ratio == 0.5
        assert forecaster._add_temporal_features is True

    def test_ridge_backward_compat(self):
        """meta_type='ridge' still works."""
        conf_ridge = {
            **MOCK_CONF,
            "stacking": {
                **MOCK_CONF["stacking"],
                "meta_learner": {"type": "ridge", "alpha": 1.0, "add_temporal_features": False},
            },
        }
        df = _make_df()
        with (
            patch.object(stacking_mod, "conf", conf_ridge),
            patch.object(stacking_mod, "logger", MagicMock()),
        ):
            f = StackingForecaster(
                df=df, sexo="incrementos_total", padecimiento="Alzheimer", config=conf_ridge
            )
        assert f._meta_type == "ridge"
        assert f._add_temporal_features is False

    def test_temporal_augmentation(self):
        """_augment_with_temporal adds 2 columns."""
        x = np.ones((10, 3))
        dates = pd.Series(pd.date_range("2024-01-01", periods=10, freq="W-MON"))
        result = StackingMetaLearner._augment_with_temporal(x, dates)
        assert result.shape == (10, 5)

    def test_load_backward_compat_defaults(self, forecaster, tmp_path):
        """Load old pickle without meta_type defaults to ridge."""
        import pickle

        path = tmp_path / "model.pkl"
        payload = {
            "experts": [{"m": 1}, {"m": 2}, {"m": 3}],
            "ridge": None,
            "weights": np.array([0.5, 0.3, 0.2]),
            "params": {},
            "n_train": 100,
        }
        with path.open("wb") as f:
            pickle.dump(payload, f)

        with patch.object(stacking_mod, "logger", MagicMock()):
            forecaster.load(path)
        assert forecaster._meta_type == "ridge"
        assert forecaster._add_temporal_features is False


# ── prophet/data_prep ─────────────────────────────────────────────────────────


class TestProphetDataPrep:
    def test_agrupa_sums_target(self):
        from epiforecast.models.prophet.data_prep import agrupa

        df = pd.DataFrame(
            {
                "Fecha": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-08"]),
                "incrementos_total": [10, 20, 15],
            }
        )
        result = agrupa(df, "incrementos_total", normalizar_tasa=False, col_poblacion="Total")
        assert result["incrementos_total"].iloc[0] == 30
        assert len(result) == 2

    def test_agrupa_with_poblacion(self):
        from epiforecast.models.prophet.data_prep import agrupa

        df = pd.DataFrame(
            {
                "Fecha": pd.to_datetime(["2024-01-01", "2024-01-01"]),
                "incrementos_total": [10, 20],
                "Total": [1000, 1000],
            }
        )
        result = agrupa(df, "incrementos_total", normalizar_tasa=True, col_poblacion="Total")
        assert "Total" in result.columns

    def test_crea_train_test_splits(self):
        from epiforecast.models.prophet.data_prep import crea_train_test

        n = 100
        dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
        rng = np.random.default_rng(42)
        df = pd.DataFrame({"ds": dates, "incrementos_total": rng.integers(5, 30, n)})
        df = df.set_index("ds")

        with patch("epiforecast.models.prophet.data_prep.logger", MagicMock()):
            serie, train, test, pob = crea_train_test(
                df,
                "incrementos_total",
                normalizar_tasa=False,
                col_poblacion="Total",
                log_transform=False,
                tasa_por=100_000,
                fecha_corte="2021-06-01",
            )
        assert len(train) + len(test) == n
        assert pob is None
        assert "y" in train.columns

    def test_crea_train_test_with_log_transform(self):
        from epiforecast.models.prophet.data_prep import crea_train_test

        n = 50
        dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
        df = pd.DataFrame({"ds": dates, "incrementos_total": [10.0] * n})
        df = df.set_index("ds")

        with patch("epiforecast.models.prophet.data_prep.logger", MagicMock()):
            serie, _, _, _ = crea_train_test(
                df,
                "incrementos_total",
                normalizar_tasa=False,
                col_poblacion="Total",
                log_transform=True,
                tasa_por=100_000,
                fecha_corte="2020-07-01",
            )
        assert serie["y"].iloc[0] == pytest.approx(np.log1p(10.0))

    def test_crea_train_test_with_tasa(self):
        from epiforecast.models.prophet.data_prep import crea_train_test

        n = 50
        dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
        df = pd.DataFrame(
            {
                "ds": dates,
                "incrementos_total": [100.0] * n,
                "Total": [50000.0] * n,
            }
        )
        df = df.set_index("ds")

        with patch("epiforecast.models.prophet.data_prep.logger", MagicMock()):
            serie, _, _, pob = crea_train_test(
                df,
                "incrementos_total",
                normalizar_tasa=True,
                col_poblacion="Total",
                log_transform=False,
                tasa_por=100_000,
                fecha_corte="2020-07-01",
            )
        assert pob == 50000.0
        assert "y_original" in serie.columns
        expected_tasa = (100.0 / 50000.0) * 100_000
        assert serie["y"].iloc[0] == pytest.approx(expected_tasa)

    def test_promedio_semanal(self):
        from epiforecast.models.prophet.data_prep import promedio_semanal

        df = pd.DataFrame({"y": [10.0, 20.0, 30.0]})
        assert promedio_semanal(df) == pytest.approx(20.0)

    def test_promedio_semanal_with_original(self):
        from epiforecast.models.prophet.data_prep import promedio_semanal

        df = pd.DataFrame({"y": [0.1, 0.2, 0.3], "y_original": [100.0, 200.0, 300.0]})
        assert promedio_semanal(df) == pytest.approx(200.0)

    def test_build_holidays(self):
        from epiforecast.models.prophet.data_prep import build_holidays

        conf = {
            "peridos_atipicos": [
                {"holiday": "COVID", "ds": "2020-03-23", "lower_window": 0, "upper_window": 913}
            ],
        }
        result = build_holidays(conf, entidad=None, padecimiento="Depresión")
        assert isinstance(result, pd.DataFrame)
        assert "COVID" in result["holiday"].values

    def test_build_holidays_no_neuro_sin_covid(self):
        """Padecimientos fuera de la cohorte neuro (Dengue) no usan el holiday COVID."""
        from epiforecast.models.prophet.data_prep import build_holidays

        conf = {
            "peridos_atipicos": [
                {"holiday": "COVID", "ds": "2020-03-23", "lower_window": 0, "upper_window": 913}
            ],
        }
        result = build_holidays(conf, entidad=None, padecimiento="Dengue")
        assert result.empty

    def test_build_holidays_with_regime_changes(self):
        from epiforecast.models.prophet.data_prep import build_holidays

        conf = {
            "peridos_atipicos": [
                {"holiday": "COVID", "ds": "2020-03-23", "lower_window": 0, "upper_window": 913}
            ],
            "cambios_regimen": [
                {
                    "holiday": "cambio_CDMX",
                    "ds": "2022-01-01",
                    "lower_window": -2,
                    "upper_window": 2,
                    "entidad": "Ciudad de Mexico",
                    "padecimiento": "Depresión",
                }
            ],
        }
        with patch("epiforecast.models.prophet.data_prep.logger", MagicMock()):
            result = build_holidays(conf, entidad="Ciudad de Mexico", padecimiento="Depresión")
        assert len(result) == 2
        assert "cambio_CDMX" in result["holiday"].values

    def test_build_seasonality_params(self):
        from epiforecast.models.prophet.data_prep import build_seasonality_params

        conf = {
            "add_seasonality": {
                "name": "yearly_custom",
                "period": 365.25,
                "fourier_order": 10,
                "fourier_order_regional": 6,
            },
        }
        with patch("epiforecast.models.prophet.data_prep.logger", MagicMock()):
            result = build_seasonality_params(conf, modelado_estados=False)
        assert result["fourier_order"] == 10
        assert "fourier_order_regional" not in result

    def test_build_seasonality_params_regional(self):
        from epiforecast.models.prophet.data_prep import build_seasonality_params

        conf = {
            "add_seasonality": {
                "name": "yearly_custom",
                "period": 365.25,
                "fourier_order": 10,
                "fourier_order_regional": 6,
            },
        }
        with patch("epiforecast.models.prophet.data_prep.logger", MagicMock()):
            result = build_seasonality_params(conf, modelado_estados=True)
        assert result["fourier_order"] == 6

    def test_apply_regional_params(self):
        from epiforecast.models.prophet.data_prep import apply_regional_params

        param = {"n_changepoints": 25}
        conf = {"n_changepoints_regional": 10}
        with patch("epiforecast.models.prophet.data_prep.logger", MagicMock()):
            apply_regional_params(param, conf, modelado_estados=True)
        assert param["n_changepoints"] == 10

    def test_apply_regional_params_noop_without_estados(self):
        from epiforecast.models.prophet.data_prep import apply_regional_params

        param = {"n_changepoints": 25}
        conf = {"n_changepoints_regional": 10}
        apply_regional_params(param, conf, modelado_estados=False)
        assert param["n_changepoints"] == 25
