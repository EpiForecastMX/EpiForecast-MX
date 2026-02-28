# tests/unit/visualization/test_comparison_plots.py
"""Unit tests for comparison_plots.py (chart rendering)."""

from unittest.mock import MagicMock, patch

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

import epiforecast.visualization.comparison_plots as cmp_mod
from epiforecast.visualization.comparison_plots import _render_comparison

# ── _render_comparison ───────────────────────────────────────────────────────


class TestRenderComparison:
    @pytest.fixture()
    def sample_data(self):
        dates = pd.date_range("2020-01-06", periods=50, freq="W-MON")
        rng = np.random.default_rng(42)
        serie_real = pd.DataFrame({"ds": dates, "y": rng.integers(10, 50, 50)})
        target_y = serie_real["y"]
        group_p = pd.DataFrame({"ds": dates, "yhat": rng.integers(10, 50, 50)})
        group_d = pd.DataFrame({"ds": dates, "yhat": rng.integers(10, 50, 50)})
        return serie_real, target_y, group_p, group_d

    def test_returns_figure_and_axes(self, sample_data):
        serie_real, target_y, group_p, group_d = sample_data
        fig, ax = _render_comparison(
            serie_real, target_y, group_p, group_d, "Alzheimer", "Nacional", "total"
        )
        assert isinstance(fig, plt.Figure)
        assert isinstance(ax, plt.Axes)
        plt.close(fig)

    def test_has_legend(self, sample_data):
        serie_real, target_y, group_p, group_d = sample_data
        fig, ax = _render_comparison(
            serie_real, target_y, group_p, group_d, "Depresion", "", "total"
        )
        legend = ax.get_legend()
        assert legend is not None
        labels = [t.get_text() for t in legend.get_texts()]
        assert "Historial Real" in labels
        assert "Prophet" in labels
        assert "DeepAR" in labels
        plt.close(fig)

    def test_title_contains_padecimiento(self, sample_data):
        serie_real, target_y, group_p, group_d = sample_data
        fig, ax = _render_comparison(
            serie_real, target_y, group_p, group_d, "Parkinson", "Sonora", "hombres"
        )
        assert "Parkinson" in ax.get_title()
        assert "Sonora" in ax.get_title()
        plt.close(fig)

    def test_entidad_empty_shows_nacional(self, sample_data):
        serie_real, target_y, group_p, group_d = sample_data
        fig, ax = _render_comparison(
            serie_real, target_y, group_p, group_d, "Alzheimer", "", "total"
        )
        assert "Nacional" in ax.get_title()
        plt.close(fig)


# ── generar_graficos_comparativos ────────────────────────────────────────────


class TestGenerarGraficosComparativos:
    def test_missing_csv_logs_error(self, tmp_path):
        mock_conf = {
            "paths": {"reports": str(tmp_path), "models": str(tmp_path / "models")},
        }
        with (
            patch.object(cmp_mod, "conf", mock_conf),
            patch.object(cmp_mod, "logger", MagicMock()),
        ):
            cmp_mod.generar_graficos_comparativos(mock_conf)
        # Should not raise, just log error
