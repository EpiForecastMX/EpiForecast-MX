"""Abstract base class for pipeline stages."""

from abc import ABC, abstractmethod
from typing import Any


class Pipeline(ABC):
    """Interface for pipeline stages.

    Each pipeline chains multiple steps together.
    """

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """Execute the pipeline."""

    @abstractmethod
    def validate_inputs(self) -> bool:
        """Check that all required inputs are available."""
