# tests/unit/models/test_factory.py
"""Unit tests for the model factory (src/epiforecast/models/factory.py).

Tests the decorator-based registry and factory functions without requiring
any real model implementations.
"""

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from epiforecast.models.base import ForecastModel
from epiforecast.models.factory import create_model, list_models, register_model

# ── Helpers ────────────────────────────────────────────────────────────────────


class _DummyModel(ForecastModel):
    """Stub model that satisfies the ForecastModel interface."""

    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs

    def fit(self, train_data: pd.DataFrame) -> None:
        pass

    def predict(self, horizon: int) -> pd.DataFrame:
        return pd.DataFrame()

    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]:
        return {"rmse": 0.0, "mae": 0.0, "mape": 0.0, "smape": 0.0, "mase": 0.0}

    def save(self, path: Path) -> None:
        pass

    def load(self, path: Path) -> None:
        pass

    def get_params(self) -> dict[str, Any]:
        return {}

    def run(self) -> tuple[Any, dict, dict]:
        return None, {}, {}


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestListModels:
    """list_models() returns the current registry contents."""

    def test_returns_list(self):
        """Return type must always be a list."""
        result = list_models()
        assert isinstance(result, list)

    def test_registered_model_appears(self):
        """A model registered via @register_model must show up in list_models()."""
        register_model("_test_list_sentinel")(_DummyModel)
        assert "_test_list_sentinel" in list_models()


class TestRegisterModel:
    """register_model() decorates and registers a model class."""

    def test_decorator_returns_original_class(self):
        """The decorator must return the unmodified class."""

        @register_model("_test_identity")
        class _MyModel(_DummyModel):
            pass

        assert _MyModel is not None
        assert issubclass(_MyModel, ForecastModel)

    def test_registered_class_is_stored(self):
        """After decoration, the class is accessible via create_model()."""
        register_model("_test_stored")(_DummyModel)
        instance = create_model("_test_stored")
        assert isinstance(instance, _DummyModel)


class TestCreateModel:
    """create_model() instantiates models from the registry."""

    def test_unknown_name_raises_value_error(self):
        """Requesting an unregistered name must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown model"):
            create_model("__does_not_exist__")

    def test_known_name_returns_instance(self):
        """Registered model name must produce a model instance."""
        register_model("_test_create")(_DummyModel)
        instance = create_model("_test_create")
        assert isinstance(instance, _DummyModel)

    def test_kwargs_passed_to_constructor(self):
        """Extra keyword arguments must be forwarded to the model constructor."""
        register_model("_test_kwargs")(_DummyModel)
        instance = create_model("_test_kwargs", foo="bar")
        assert instance.kwargs == {"foo": "bar"}
