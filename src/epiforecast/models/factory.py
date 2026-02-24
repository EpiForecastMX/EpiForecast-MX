"""Model factory: instantiate models from config (Open/Closed + Dependency Inversion)."""

from typing import Any

from src.epiforecast.models.base import ForecastModel


# Registry of available models — add new models here without modifying existing code (OCP)
_MODEL_REGISTRY: dict[str, type[ForecastModel]] = {}


def register_model(name: str):
    """Decorator to register a model class in the factory."""
    def decorator(cls: type[ForecastModel]):
        _MODEL_REGISTRY[name] = cls
        return cls
    return decorator


def create_model(name: str, **kwargs: Any) -> ForecastModel:
    """Create a model instance by name from config (DIP).

    Args:
        name: Model identifier (e.g., 'prophet', 'deepar', 'xgboost').
        **kwargs: Model-specific parameters from YAML config.

    Raises:
        ValueError: If model name is not registered.
    """
    if name not in _MODEL_REGISTRY:
        available = ", ".join(_MODEL_REGISTRY.keys())
        raise ValueError(
            f"Unknown model '{name}'. Available: {available}"
        )
    return _MODEL_REGISTRY[name](**kwargs)


def list_models() -> list[str]:
    """Return list of registered model names."""
    return list(_MODEL_REGISTRY.keys())
