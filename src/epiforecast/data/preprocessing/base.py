"""Abstract base class for data preprocessing steps (SRP + ISP)."""

from abc import ABC, abstractmethod

import pandas as pd


class DataPreprocessor(ABC):
    """Interface for preprocessing steps.

    Each implementation handles exactly one transformation (SRP).
    """

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply transformation and return new DataFrame."""

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> bool:
        """Validate that input meets preconditions."""
