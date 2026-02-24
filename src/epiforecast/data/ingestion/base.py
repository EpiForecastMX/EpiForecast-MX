"""Abstract base class for data ingestion (SRP + ISP)."""

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class DataIngestor(ABC):
    """Interface for data ingestion from external sources.

    Implementations: SinaveIngestor, InegiIngestor.
    """

    @abstractmethod
    def fetch(self, **kwargs) -> pd.DataFrame:
        """Fetch data from external source."""

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> bool:
        """Validate fetched data quality."""

    @abstractmethod
    def save(self, df: pd.DataFrame, path: Path) -> None:
        """Save fetched data to disk."""
