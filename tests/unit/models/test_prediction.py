# tests/unit/models/test_prediction.py
"""Unit tests for ForecastModelLoader (src/epiforecast/models/prediction.py).

Tests the delegation pattern: ForecastModelLoader delegates load/predict
to the factory-created forecaster.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import epiforecast.models.prediction as prediction_mod
from epiforecast.models.prediction import ForecastModelLoader

# ── Fixtures ───────────────────────────────────────────────────────────────────

_WEEKS = 10


@pytest.fixture
def mock_forecaster() -> MagicMock:
    """A mock ForecastModel that returns realistic data from predict()."""
    m = MagicMock()
    dates = pd.date_range("2024-01-01", periods=_WEEKS, freq="W-MON")
    m.predict.return_value = pd.DataFrame(
        {
            "ds": dates,
            "yhat": 1.0,
            "yhat_lower": 0.5,
            "yhat_upper": 1.5,
        }
    )
    return m


@pytest.fixture
def _patch_factory(mock_forecaster: MagicMock):
    """Patch create_model so ForecastModelLoader gets the mock forecaster."""
    with patch.object(prediction_mod, "create_model", return_value=mock_forecaster):
        with patch.object(prediction_mod, "conf", {"modelo_activo": "prophet"}):
            yield


# ── __init__ ───────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("_patch_factory")
class TestForecastModelLoaderInit:
    """Constructor stores periodo and delegates to create_model."""

    def test_periodo_stored(self, tmp_path: Path):
        loader = ForecastModelLoader(26, tmp_path / "model.pkl")
        assert loader.periodo == 26

    def test_model_path_stored(self, tmp_path: Path):
        path = tmp_path / "model.pkl"
        loader = ForecastModelLoader(52, path)
        assert loader.model_path == path

    def test_modelo_activo_defaults_to_prophet(self, tmp_path: Path):
        loader = ForecastModelLoader(52, tmp_path / "model.pkl")
        assert loader.modelo_activo == "prophet"

    def test_forecaster_created(self, tmp_path: Path):
        loader = ForecastModelLoader(52, tmp_path / "model.pkl")
        assert loader.forecaster is not None

    def test_config_override(self, tmp_path: Path, mock_forecaster: MagicMock):
        with patch.object(prediction_mod, "create_model", return_value=mock_forecaster):
            loader = ForecastModelLoader(
                52,
                tmp_path / "m.pkl",
                config={"modelo_activo": "deepar"},
            )
        assert loader.modelo_activo == "deepar"


# ── load() ─────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("_patch_factory")
class TestForecastModelLoaderLoad:
    """load() delegates to forecaster.load()."""

    def test_load_delegates_to_forecaster(self, tmp_path: Path, mock_forecaster: MagicMock):
        path = tmp_path / "model.pkl"
        loader = ForecastModelLoader(_WEEKS, path)
        loader.load()
        mock_forecaster.load.assert_called_once_with(path)

    def test_load_propagates_file_not_found(self, tmp_path: Path, mock_forecaster: MagicMock):
        mock_forecaster.load.side_effect = FileNotFoundError("Missing")
        loader = ForecastModelLoader(52, tmp_path / "ghost.pkl")
        with pytest.raises(FileNotFoundError):
            loader.load()


# ── predict() ─────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("_patch_factory")
class TestForecastModelLoaderPredict:
    """predict() delegates to forecaster.predict()."""

    def test_predict_returns_dataframe(self, tmp_path: Path):
        loader = ForecastModelLoader(_WEEKS, tmp_path / "model.pkl")
        result = loader.predict()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == _WEEKS

    def test_predict_contains_yhat(self, tmp_path: Path):
        loader = ForecastModelLoader(_WEEKS, tmp_path / "model.pkl")
        assert "yhat" in loader.predict().columns

    def test_predict_delegates_horizon(self, tmp_path: Path, mock_forecaster: MagicMock):
        loader = ForecastModelLoader(26, tmp_path / "model.pkl")
        loader.predict()
        mock_forecaster.predict.assert_called_once_with(26)


# ── run() ──────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures("_patch_factory")
class TestForecastModelLoaderRun:
    """run() is a convenience wrapper for load() + predict()."""

    def test_run_returns_dataframe(self, tmp_path: Path):
        loader = ForecastModelLoader(_WEEKS, tmp_path / "model.pkl")
        result = loader.run()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == _WEEKS

    def test_run_calls_load_then_predict(self, tmp_path: Path, mock_forecaster: MagicMock):
        loader = ForecastModelLoader(_WEEKS, tmp_path / "model.pkl")
        loader.run()
        mock_forecaster.load.assert_called_once()
        mock_forecaster.predict.assert_called_once()

    def test_run_propagates_load_error(self, tmp_path: Path, mock_forecaster: MagicMock):
        mock_forecaster.load.side_effect = FileNotFoundError("Missing")
        loader = ForecastModelLoader(52, tmp_path / "missing.pkl")
        with pytest.raises(FileNotFoundError):
            loader.run()
