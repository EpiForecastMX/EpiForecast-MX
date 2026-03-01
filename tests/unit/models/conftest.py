"""Shared helpers and fixtures for model unit tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

# ── Plain helper functions (importable from other test files) ────────────────


def make_epi_df(n_weeks: int = 200) -> pd.DataFrame:
    """DataFrame con columnas Fecha, Padecimiento, Entidad, incrementos_total."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2019-01-07", periods=n_weeks, freq="W-MON")
    return pd.DataFrame(
        {
            "Fecha": dates,
            "Padecimiento": ["Alzheimer"] * n_weeks,
            "Entidad": ["Nacional"] * n_weeks,
            "incrementos_total": rng.integers(5, 30, n_weeks),
        }
    )


def make_train_series(n: int = 200) -> pd.DataFrame:
    """DataFrame con columnas ds, y (serie temporal basica)."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2019-01-07", periods=n, freq="W-MON")
    return pd.DataFrame({"ds": dates, "y": rng.integers(5, 30, n).astype(float)})
