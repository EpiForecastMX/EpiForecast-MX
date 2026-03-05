"""Tests for chart_annotations.py — forecast chart decoration helpers."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import epiforecast.visualization.chart_annotations as ca_mod
from epiforecast.visualization.chart_annotations import (
    _anotar_divisores,
    _anotar_zona_cv,
    _render_ficha_tecnica,
)


@pytest.fixture
def mock_ax():
    return MagicMock()


@pytest.fixture
def mock_fig():
    return MagicMock()


_CONF_WITH_FECHA = {"FECHA_CORTE_ENTRENAMIENTO": "2022-01-01"}


class TestAnotarDivisores:
    def test_axvline_called_once(self, mock_ax):
        _anotar_divisores(mock_ax, pd.Timestamp("2024-01-01"), "#333", "#666")
        mock_ax.axvline.assert_called_once()

    def test_annotate_called_twice(self, mock_ax):
        _anotar_divisores(mock_ax, pd.Timestamp("2024-01-01"), "#333", "#666")
        assert mock_ax.annotate.call_count == 2

    def test_axvline_receives_fecha(self, mock_ax):
        fecha = pd.Timestamp("2024-06-01")
        _anotar_divisores(mock_ax, fecha, "blue", "red")
        call_args = mock_ax.axvline.call_args
        # positional or keyword
        pos_arg = call_args[0][0] if call_args[0] else call_args[1].get("x")
        assert pos_arg == fecha

    def test_axvline_color_is_c_div(self, mock_ax):
        _anotar_divisores(mock_ax, pd.Timestamp("2024-01-01"), "#AABBCC", "#999")
        kwargs = mock_ax.axvline.call_args[1]
        assert kwargs.get("color") == "#AABBCC"

    def test_historical_annotation_ha_right(self, mock_ax):
        _anotar_divisores(mock_ax, pd.Timestamp("2024-01-01"), "#333", "#666")
        first_call = mock_ax.annotate.call_args_list[0]
        assert first_call[1].get("ha") == "right"

    def test_forecast_annotation_ha_left(self, mock_ax):
        _anotar_divisores(mock_ax, pd.Timestamp("2024-01-01"), "#333", "#666")
        second_call = mock_ax.annotate.call_args_list[1]
        assert second_call[1].get("ha") == "left"


class TestAnotarZonaCV:
    def test_axvspan_called(self, mock_ax):
        with patch.object(ca_mod, "conf", _CONF_WITH_FECHA):
            _anotar_zona_cv(mock_ax, pd.Timestamp("2024-01-01"), "gray")
        mock_ax.axvspan.assert_called_once()

    def test_axvline_dotted_called(self, mock_ax):
        with patch.object(ca_mod, "conf", _CONF_WITH_FECHA):
            _anotar_zona_cv(mock_ax, pd.Timestamp("2024-01-01"), "gray")
        mock_ax.axvline.assert_called_once()

    def test_annotate_called_twice(self, mock_ax):
        with patch.object(ca_mod, "conf", _CONF_WITH_FECHA):
            _anotar_zona_cv(mock_ax, pd.Timestamp("2024-01-01"), "gray")
        assert mock_ax.annotate.call_count == 2

    def test_axvline_linestyle_dotted(self, mock_ax):
        with patch.object(ca_mod, "conf", _CONF_WITH_FECHA):
            _anotar_zona_cv(mock_ax, pd.Timestamp("2024-01-01"), "gray")
        kwargs = mock_ax.axvline.call_args[1]
        assert kwargs.get("ls") == ":"


class TestRenderFichaTecnica:
    """fig.text is called twice: ficha tecnica (1st) + timestamp CDMX (2nd)."""

    @staticmethod
    def _ficha_text(mock_fig: MagicMock) -> str:
        """Extract the ficha tecnica text (first fig.text call)."""
        return mock_fig.text.call_args_list[0][0][2]

    def test_fig_text_called_twice(self, mock_fig):
        _render_ficha_tecnica(mock_fig, {"mase": 0.8, "rmse": 0.5})
        assert mock_fig.text.call_count == 2

    def test_mase_label_in_text(self, mock_fig):
        _render_ficha_tecnica(mock_fig, {"mase": 0.75, "rmse": 0.1})
        assert "MASE" in self._ficha_text(mock_fig)

    def test_rmse_label_in_text(self, mock_fig):
        _render_ficha_tecnica(mock_fig, {"mase": 0.75, "rmse": 0.1})
        assert "RMSE" in self._ficha_text(mock_fig)

    def test_fallback_regional_in_text(self, mock_fig):
        _render_ficha_tecnica(
            mock_fig, {"es_fallback": True, "modelo_usado": "region_metropolitana_alta_hombres"}
        )
        assert "Regional" in self._ficha_text(mock_fig)

    def test_estatal_label_when_confianza_normal(self, mock_fig):
        _render_ficha_tecnica(mock_fig, {"confianza": "normal", "es_fallback": False})
        assert "Estatal" in self._ficha_text(mock_fig)

    def test_mase_above_threshold_no_supera(self, mock_fig):
        _render_ficha_tecnica(mock_fig, {"mase": 1.5})
        assert "no supera" in self._ficha_text(mock_fig)

    def test_mase_below_threshold_supera(self, mock_fig):
        _render_ficha_tecnica(mock_fig, {"mase": 0.5})
        assert "supera" in self._ficha_text(mock_fig)

    def test_seasonality_mode_in_text(self, mock_fig):
        _render_ficha_tecnica(
            mock_fig, {"seasonality_mode": "multiplicative", "meta_modelo": "prophet"}
        )
        assert "multiplicative" in self._ficha_text(mock_fig)

    def test_empty_metrics_still_calls_text(self, mock_fig):
        _render_ficha_tecnica(mock_fig, {})
        assert mock_fig.text.call_count == 2
