# tests/unit/test_bases.py
"""Unit tests for abstract base classes.

Creates minimal concrete implementations and verifies the interface contracts,
covering all abstract method bodies (docstrings) via super() calls so that
every statement in the base modules is counted by coverage.py.
"""

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from epiforecast.data.ingestion.base import DataIngestor
from epiforecast.data.preprocessing.base import DataPreprocessor
from epiforecast.models.base import ForecastModel
from epiforecast.pipelines.base import Pipeline

# ── Concrete implementations ───────────────────────────────────────────────────


class _ConcretePreprocessor(DataPreprocessor):
    """Minimal concrete DataPreprocessor that delegates to super()."""

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        super().transform(df)  # covers abstract method body
        return df

    def validate(self, df: pd.DataFrame) -> bool:
        super().validate(df)  # covers abstract method body
        return not df.empty


class _ConcreteModel(ForecastModel):
    """Minimal concrete ForecastModel that delegates to super()."""

    def fit(self, train_data: pd.DataFrame) -> None:
        super().fit(train_data)

    def predict(self, horizon: int) -> pd.DataFrame:
        super().predict(horizon)
        return pd.DataFrame({"ds": [], "yhat": []})

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        super().cross_validate(data)
        return {"rmse": 0.0, "mae": 0.0, "mape": 0.0, "smape": 0.0, "mase": 0.0}

    def save(self, path: Path) -> None:
        super().save(path)

    def load(self, path: Path) -> None:
        super().load(path)

    def get_params(self) -> dict[str, Any]:
        super().get_params()
        return {}

    def run(self) -> tuple[Any, dict, dict]:
        super().run()
        return None, {}, {}


class _ConcretePipeline(Pipeline):
    """Minimal concrete Pipeline that delegates to super()."""

    def run(self, **kwargs: Any) -> Any:
        super().run(**kwargs)
        return None

    def validate_inputs(self) -> bool:
        super().validate_inputs()
        return True


class _ConcreteIngestor(DataIngestor):
    """Minimal concrete DataIngestor that delegates to super()."""

    def fetch(self, **kwargs: Any) -> pd.DataFrame:
        super().fetch(**kwargs)
        return pd.DataFrame()

    def validate(self, df: pd.DataFrame) -> bool:
        super().validate(df)
        return True

    def save(self, df: pd.DataFrame, path: Path) -> None:
        super().save(df, path)


# ── DataPreprocessor ───────────────────────────────────────────────────────────


class TestDataPreprocessor:
    """DataPreprocessor interface contract."""

    def test_is_abstract(self):
        """Cannot instantiate directly — must be subclassed."""
        with pytest.raises(TypeError):
            DataPreprocessor()  # type: ignore[abstract]

    def test_concrete_instantiates(self):
        """Concrete subclass can be instantiated."""
        obj = _ConcretePreprocessor()
        assert isinstance(obj, DataPreprocessor)

    def test_transform_returns_dataframe(self):
        """transform() must return a DataFrame."""
        df = pd.DataFrame({"x": [1, 2, 3]})
        result = _ConcretePreprocessor().transform(df)
        assert isinstance(result, pd.DataFrame)

    def test_validate_returns_bool(self):
        """validate() must return a bool."""
        df = pd.DataFrame({"x": [1]})
        result = _ConcretePreprocessor().validate(df)
        assert isinstance(result, bool)

    def test_validate_empty_df(self):
        """Empty DataFrame must return False from validate()."""
        result = _ConcretePreprocessor().validate(pd.DataFrame())
        assert result is False


# ── ForecastModel ──────────────────────────────────────────────────────────────


class TestForecastModel:
    """ForecastModel interface contract."""

    def test_is_abstract(self):
        """Cannot instantiate directly."""
        with pytest.raises(TypeError):
            ForecastModel()  # type: ignore[abstract]

    def test_concrete_instantiates(self):
        """Concrete subclass must be instantiable."""
        obj = _ConcreteModel()
        assert isinstance(obj, ForecastModel)

    def test_fit_callable(self):
        """fit() must accept a DataFrame and return None."""
        result = _ConcreteModel().fit(pd.DataFrame({"y": [1, 2, 3]}))
        assert result is None

    def test_predict_returns_dataframe(self):
        """predict() must return a DataFrame."""
        result = _ConcreteModel().predict(10)
        assert isinstance(result, pd.DataFrame)

    def test_cross_validate_returns_dict(self):
        """cross_validate() must return a dict with the four metric keys."""
        result = _ConcreteModel().cross_validate(pd.DataFrame({"y": [1, 2, 3]}))
        assert isinstance(result, dict)
        assert {"rmse", "mae", "mape", "smape", "mase"} == set(result.keys())

    def test_save_callable(self, tmp_path: Path):
        """save() must be callable without error."""
        _ConcreteModel().save(tmp_path / "model.pkl")

    def test_load_callable(self, tmp_path: Path):
        """load() must be callable without error."""
        _ConcreteModel().load(tmp_path / "model.pkl")

    def test_get_params_returns_dict(self):
        """get_params() must return a dict."""
        result = _ConcreteModel().get_params()
        assert isinstance(result, dict)


# ── Pipeline ───────────────────────────────────────────────────────────────────


class TestPipeline:
    """Pipeline interface contract."""

    def test_is_abstract(self):
        with pytest.raises(TypeError):
            Pipeline()  # type: ignore[abstract]

    def test_concrete_instantiates(self):
        obj = _ConcretePipeline()
        assert isinstance(obj, Pipeline)

    def test_run_callable(self):
        result = _ConcretePipeline().run()
        assert result is None

    def test_validate_inputs_returns_bool(self):
        result = _ConcretePipeline().validate_inputs()
        assert isinstance(result, bool)


# ── DataIngestor ───────────────────────────────────────────────────────────────


class TestDataIngestor:
    """DataIngestor interface contract."""

    def test_is_abstract(self):
        with pytest.raises(TypeError):
            DataIngestor()  # type: ignore[abstract]

    def test_concrete_instantiates(self):
        obj = _ConcreteIngestor()
        assert isinstance(obj, DataIngestor)

    def test_fetch_returns_dataframe(self):
        result = _ConcreteIngestor().fetch()
        assert isinstance(result, pd.DataFrame)

    def test_validate_returns_bool(self):
        result = _ConcreteIngestor().validate(pd.DataFrame())
        assert isinstance(result, bool)

    def test_save_callable(self, tmp_path: Path):
        _ConcreteIngestor().save(pd.DataFrame(), tmp_path / "out.csv")
