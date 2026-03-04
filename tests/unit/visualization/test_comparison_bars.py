"""Tests for comparison_bars helper functions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from epiforecast.visualization.comparison_bars import (
    _detect_scale,
    _month_ticks,
    _prepare_bars,
    _stamp,
)

# ---------------------------------------------------------------------------
# _detect_scale
# ---------------------------------------------------------------------------


class TestDetectScale:
    def test_normal_ratio_returns_one(self) -> None:
        assert _detect_scale(100.0, 95.0) == 1.0

    def test_small_ratio_returns_scale(self) -> None:
        # yhat median is much smaller than y_real median → normalized
        scale = _detect_scale(1000.0, 0.05)
        assert scale == pytest.approx(1000.0 / 0.05)

    def test_zero_real_returns_one(self) -> None:
        assert _detect_scale(0.0, 50.0) == 1.0

    def test_zero_yhat_returns_one(self) -> None:
        assert _detect_scale(50.0, 0.0) == 1.0

    def test_negative_real_returns_one(self) -> None:
        assert _detect_scale(-10.0, 50.0) == 1.0

    def test_both_zero_returns_one(self) -> None:
        assert _detect_scale(0.0, 0.0) == 1.0

    def test_ratio_exactly_at_boundary(self) -> None:
        # ratio = 0.1 → should return 1.0 (not less than 0.1)
        assert _detect_scale(100.0, 10.0) == 1.0

    def test_ratio_just_below_boundary(self) -> None:
        scale = _detect_scale(100.0, 9.9)
        assert scale > 1.0


# ---------------------------------------------------------------------------
# _prepare_bars
# ---------------------------------------------------------------------------


def _make_real(n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="W-MON")
    return pd.DataFrame({"ds": dates, "y": np.arange(n, dtype=float) + 10})


def _make_pred(n: int = 104, start: str = "2024-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=n, freq="W-MON")
    return pd.DataFrame(
        {
            "ds": dates,
            "yhat": np.random.default_rng(42).uniform(5, 50, n),
            "yhat_lower": np.random.default_rng(42).uniform(2, 40, n),
            "yhat_upper": np.random.default_rng(42).uniform(50, 80, n),
        }
    )


class TestPrepareBars:
    def test_returns_three_elements(self) -> None:
        real = _make_real()
        pred = _make_pred(n=104)
        cutoff = real["ds"].max()
        hist, future, scale = _prepare_bars(real, pred, cutoff)
        assert isinstance(hist, pd.DataFrame)
        assert isinstance(future, pd.DataFrame)
        assert isinstance(scale, float)

    def test_hist_has_expected_columns(self) -> None:
        real = _make_real()
        pred = _make_pred(n=104)
        cutoff = real["ds"].max()
        hist, _, _ = _prepare_bars(real, pred, cutoff)
        for col in ("ds", "y_real", "yhat", "yhat_lower", "yhat_upper"):
            assert col in hist.columns

    def test_hist_max_52_rows(self) -> None:
        real = _make_real(n=100)
        pred = _make_pred(n=200)
        cutoff = real["ds"].max()
        hist, _, _ = _prepare_bars(real, pred, cutoff)
        assert len(hist) <= 52

    def test_future_after_cutoff(self) -> None:
        real = _make_real(n=60)
        pred = _make_pred(n=120)
        cutoff = real["ds"].max()
        _, future, _ = _prepare_bars(real, pred, cutoff)
        if not future.empty:
            assert (future["ds"] > cutoff).all()

    def test_yhat_clamped_non_negative(self) -> None:
        real = _make_real()
        pred = _make_pred(n=104)
        # Force some negative predictions
        pred["yhat"] = -10.0
        cutoff = real["ds"].max()
        hist, future, _ = _prepare_bars(real, pred, cutoff)
        assert (hist["yhat"] >= 0).all()

    def test_uses_y_original_if_present(self) -> None:
        real = _make_real()
        real["y_original"] = real["y"] * 2
        pred = _make_pred()
        cutoff = real["ds"].max()
        hist, _, _ = _prepare_bars(real, pred, cutoff)
        # y_real should come from y_original, not y
        assert hist["y_real"].iloc[0] == pytest.approx(real["y_original"].iloc[real.index[-52]])


# ---------------------------------------------------------------------------
# _month_ticks
# ---------------------------------------------------------------------------


class TestMonthTicks:
    def test_returns_positions_and_labels(self) -> None:
        dates_hist = pd.Series(pd.date_range("2024-01-01", periods=10, freq="W-MON"))
        dates_fut = pd.Series(pd.date_range("2024-03-15", periods=10, freq="W-MON"))
        positions, labels = _month_ticks(dates_hist, dates_fut)
        assert len(positions) == len(labels)
        assert len(positions) > 0

    def test_labels_are_spanish(self) -> None:
        dates_hist = pd.Series(pd.date_range("2024-01-01", periods=5, freq="W-MON"))
        dates_fut = pd.Series(pd.date_range("2024-06-01", periods=5, freq="W-MON"))
        _, labels = _month_ticks(dates_hist, dates_fut)
        valid_months = {
            "Ene",
            "Feb",
            "Mar",
            "Abr",
            "May",
            "Jun",
            "Jul",
            "Ago",
            "Sep",
            "Oct",
            "Nov",
            "Dic",
        }
        for lbl in labels:
            month_part = lbl.split("'")[0]
            assert month_part in valid_months

    def test_no_consecutive_duplicates(self) -> None:
        dates_hist = pd.Series(pd.date_range("2024-01-01", periods=52, freq="W-MON"))
        dates_fut = pd.Series(pd.date_range("2025-01-01", periods=52, freq="W-MON"))
        _, labels = _month_ticks(dates_hist, dates_fut)
        for i in range(1, len(labels)):
            assert labels[i] != labels[i - 1]

    def test_empty_future(self) -> None:
        dates_hist = pd.Series(pd.date_range("2024-01-01", periods=10, freq="W-MON"))
        dates_fut = pd.Series(dtype="datetime64[ns]")
        positions, labels = _month_ticks(dates_hist, dates_fut)
        assert len(positions) > 0


# ---------------------------------------------------------------------------
# _stamp
# ---------------------------------------------------------------------------


class TestStamp:
    def test_adds_text_to_figure(self) -> None:
        import matplotlib.pyplot as plt

        fig = plt.figure()
        _stamp(fig)
        texts = fig.texts
        assert len(texts) >= 1
        assert "EpiForecast-MX" in texts[-1].get_text()
        plt.close(fig)
