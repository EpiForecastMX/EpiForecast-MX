# tests/unit/models/test_prediction.py
"""Unit tests for ForecastModelLoader (src/epiforecast/models/prediction.py).

Uses a pickled mock model so no real Prophet model is required.
conf is patched per-test to control normalizar_tasa / log_transform / tasa_por.
"""

from pathlib import Path
import pickle
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import epiforecast.models.prediction as prediction_mod
from epiforecast.models.prediction import ForecastModelLoader

# ── Mock model for pickling ────────────────────────────────────────────────────

_WEEKS = 10


class _MockProphetModel:
    """Minimal Prophet stand-in: make_future_dataframe + predict only."""

    def make_future_dataframe(self, periods: int, freq: str = "W-MON") -> pd.DataFrame:
        dates = pd.date_range("2024-01-01", periods=periods, freq="W-MON")
        return pd.DataFrame({"ds": dates})

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["yhat"] = 1.0
        df["yhat_lower"] = 0.5
        df["yhat_upper"] = 1.5
        return df


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def pkl_path(tmp_path: Path) -> Path:
    """Write a pickled _MockProphetModel to a temp file and return the path."""
    path = tmp_path / "Prophet_test.pkl"
    with path.open("wb") as f:
        pickle.dump(_MockProphetModel(), f)
    return path


@pytest.fixture
def csv_path(pkl_path: Path) -> Path:
    """Write a population CSV sidecar next to the pkl and return its path."""
    csv = pkl_path.with_suffix(".csv")
    pd.DataFrame({"Total": [1_000_000], "y_original": [50]}).to_csv(csv, index=False)
    return csv


# ── __init__ ───────────────────────────────────────────────────────────────────


class TestForecastModelLoaderInit:
    """Constructor reads conf defaults via conf.get()."""

    def test_default_flags_from_empty_conf(self, pkl_path: Path):
        """With empty conf mock, all boolean flags default to False."""
        loader = ForecastModelLoader(52, pkl_path)
        assert loader.normalizar_tasa is False
        assert loader.log_transform is False

    def test_default_tasa_por(self, pkl_path: Path):
        """tasa_por defaults to 100_000 when conf is empty."""
        loader = ForecastModelLoader(52, pkl_path)
        assert loader.tasa_por == 100_000

    def test_model_starts_none(self, pkl_path: Path):
        """model attribute must be None before load() is called."""
        loader = ForecastModelLoader(52, pkl_path)
        assert loader.model is None

    def test_periodo_stored(self, pkl_path: Path):
        """periodo is stored on the instance."""
        loader = ForecastModelLoader(26, pkl_path)
        assert loader.periodo == 26

    def test_conf_override_normalizar_tasa(self, pkl_path: Path):
        """patching conf allows normalizar_tasa=True."""
        with patch.object(prediction_mod, "conf", {"normalizar_tasa": True, "tasa_por": 100_000}):
            loader = ForecastModelLoader(52, pkl_path)
        assert loader.normalizar_tasa is True


# ── load() ─────────────────────────────────────────────────────────────────────


class TestForecastModelLoaderLoad:
    """load() deserialises the model from disk."""

    def test_missing_file_raises_file_not_found(self, tmp_path: Path):
        """FileNotFoundError must be raised for non-existent pkl path."""
        loader = ForecastModelLoader(52, tmp_path / "ghost.pkl")
        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_load_sets_model_attribute(self, pkl_path: Path):
        """After a successful load(), model must not be None."""
        loader = ForecastModelLoader(_WEEKS, pkl_path)
        loader.load()
        assert loader.model is not None

    def test_load_skips_csv_when_normalizar_tasa_false(self, pkl_path: Path):
        """With normalizar_tasa=False, poblacion must remain None."""
        loader = ForecastModelLoader(_WEEKS, pkl_path)
        loader.load()
        assert loader.poblacion is None

    def test_load_reads_population_from_csv(self, pkl_path: Path, csv_path: Path):  # noqa: ARG002
        """With normalizar_tasa=True and CSV present, poblacion must be set."""
        with patch.object(
            prediction_mod,
            "conf",
            {"normalizar_tasa": True, "tasa_por": 100_000, "log_transform": False},
        ):
            loader = ForecastModelLoader(_WEEKS, pkl_path)
        loader.load()
        assert loader.poblacion == pytest.approx(1_000_000)


# ── predict() ─────────────────────────────────────────────────────────────────


class TestForecastModelLoaderPredict:
    """predict() generates forecasts and applies inverse transforms."""

    def test_predict_raises_when_model_not_loaded(self, pkl_path: Path):
        """RuntimeError must be raised before load() is called."""
        loader = ForecastModelLoader(52, pkl_path)
        with pytest.raises(RuntimeError, match="load()"):
            loader.predict()

    def test_predict_returns_dataframe(self, pkl_path: Path):
        """predict() must return a non-empty DataFrame."""
        loader = ForecastModelLoader(_WEEKS, pkl_path)
        loader.load()
        result = loader.predict()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == _WEEKS

    def test_predict_contains_yhat(self, pkl_path: Path):
        """Result DataFrame must contain the yhat column."""
        loader = ForecastModelLoader(_WEEKS, pkl_path)
        loader.load()
        assert "yhat" in loader.predict().columns

    def test_log_transform_inverted(self, pkl_path: Path):
        """With log_transform=True, yhat must be exp-transformed."""
        with patch.object(
            prediction_mod,
            "conf",
            {"log_transform": True, "normalizar_tasa": False, "tasa_por": 100_000},
        ):
            loader = ForecastModelLoader(_WEEKS, pkl_path)
        loader.load()
        result = loader.predict()
        # Mock model predicts yhat=1.0; after expm1: exp(1)-1 ≈ 1.718
        assert result["yhat"].iloc[0] == pytest.approx(np.expm1(1.0))

    def test_rate_desnormalized_to_counts(self, pkl_path: Path, csv_path: Path):  # noqa: ARG002
        """With normalizar_tasa=True and poblacion set, yhat becomes a count."""
        with patch.object(
            prediction_mod,
            "conf",
            {"normalizar_tasa": True, "log_transform": False, "tasa_por": 100_000},
        ):
            loader = ForecastModelLoader(_WEEKS, pkl_path)
        loader.load()
        result = loader.predict()
        # yhat=1.0 * 1_000_000 / 100_000 = 10.0
        assert result["yhat"].iloc[0] == pytest.approx(10.0)
        assert "yhat_tasa" in result.columns


# ── run() ──────────────────────────────────────────────────────────────────────


class TestForecastModelLoaderRun:
    """run() is a convenience wrapper for load() + predict()."""

    def test_run_returns_dataframe(self, pkl_path: Path):
        """run() must return the same result as load() + predict()."""
        loader = ForecastModelLoader(_WEEKS, pkl_path)
        result = loader.run()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == _WEEKS

    def test_run_raises_on_missing_file(self, tmp_path: Path):
        """run() must propagate FileNotFoundError from load()."""
        loader = ForecastModelLoader(52, tmp_path / "missing.pkl")
        with pytest.raises(FileNotFoundError):
            loader.run()
