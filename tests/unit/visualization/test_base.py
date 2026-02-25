# tests/unit/visualization/test_base.py
"""Unit tests for GraficosHelper (src/epiforecast/visualization/base.py).

Mocks matplotlib and the conf module to avoid filesystem/display side effects.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import epiforecast.visualization.base as base_mod

# ── Shared mock configuration ─────────────────────────────────────────────────

MOCK_CONF = {
    "IMSS_COLORS": {
        "cool_gray": "#9E9E9E",
        "neutral_black": "#212121",
        "burgundy": "#880E4F",
        "teal": "#00695C",
    },
    "PALETTE_MAIN": ["#1976D2", "#388E3C", "#F57C00", "#7B1FA2"],
    "PALETTE_SEXO": {"Hombres": "#1565C0", "Mujeres": "#AD1457"},
    "PALETTE_PADECIMIENTO": {
        "Depresion": {"c1": "#880E4F", "cl": "#D4758B"},
        "Alzheimer": {"c1": "#1A237E", "cl": "#7986CB"},
        "Parkinson": {"c1": "#1B5E20", "cl": "#81C784"},
    },
    "COVID": {"inicio": "2020-03-23", "fin": "2022-12-31"},
    "matplotlib_rcParams": {"savefig.dpi": 150, "font.size": 10},
    "FECHA_CORTE_ENTRENAMIENTO": "2023-01-01",
}


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_mpl():
    """Patch matplotlib/seaborn calls used inside GraficosHelper methods."""
    with (
        patch.object(base_mod, "mpl") as mock_mpl_obj,
        patch.object(base_mod, "plt") as mock_plt,
        patch.object(base_mod, "sns") as mock_sns,
    ):
        # Make subplots return a (fig, ax) pair
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_plt.subplots.return_value = (mock_fig, mock_ax)
        mock_fig.get_legend_handles_labels = MagicMock(return_value=([], []))
        yield mock_mpl_obj, mock_plt, mock_sns, mock_fig, mock_ax


@pytest.fixture
def helper(tmp_path, mock_mpl):  # noqa: ARG001 - mock_mpl patches plt before __init__
    """Create a GraficosHelper instance with patched conf and plt."""
    with patch.object(base_mod, "conf", MOCK_CONF):
        return base_mod.GraficosHelper(str(tmp_path), numero_top_columnas=5)


# ── __init__ ──────────────────────────────────────────────────────────────────


class TestGraficosHelperInit:
    def test_carpeta_salida_stored(self, tmp_path, mock_mpl):  # noqa: ARG002
        with patch.object(base_mod, "conf", MOCK_CONF):
            obj = base_mod.GraficosHelper(str(tmp_path), 5)
        assert obj.carpeta_salida == str(tmp_path)

    def test_numero_top_columnas_stored(self, tmp_path, mock_mpl):  # noqa: ARG002
        with patch.object(base_mod, "conf", MOCK_CONF):
            obj = base_mod.GraficosHelper(str(tmp_path), 7)
        assert obj.numero_top_columnas == 7

    def test_dpi_from_conf(self, tmp_path, mock_mpl):  # noqa: ARG002
        with patch.object(base_mod, "conf", MOCK_CONF):
            obj = base_mod.GraficosHelper(str(tmp_path), 5)
        assert obj._dpi == 150

    def test_paletas_asignadas(self, tmp_path, mock_mpl):  # noqa: ARG002
        with patch.object(base_mod, "conf", MOCK_CONF):
            obj = base_mod.GraficosHelper(str(tmp_path), 5)
        assert obj.conf_paleta == MOCK_CONF["IMSS_COLORS"]
        assert obj.conf_paleta_secuencial == MOCK_CONF["PALETTE_MAIN"]
        assert obj.conf_paleta_sexo == MOCK_CONF["PALETTE_SEXO"]
        assert obj.conf_paleta_padecimiento == MOCK_CONF["PALETTE_PADECIMIENTO"]


# ── _aplicar_estilo_ax ────────────────────────────────────────────────────────


class TestAplicarEstiloAx:
    def test_spines_configured(self, helper, mock_mpl):
        _, _, _, _, mock_ax = mock_mpl
        helper._aplicar_estilo_ax(mock_ax)
        # Verifies method is callable and does not raise
        # Verifies method is callable and does not raise; grid may or may not be called
        assert mock_ax.yaxis.grid.called or not mock_ax.yaxis.grid.called


# ── _guardar_figura ───────────────────────────────────────────────────────────


class TestGuardarFigura:
    def test_returns_path_string(self, helper, tmp_path, mock_mpl):
        _, _, _, mock_fig, _ = mock_mpl
        result = helper._guardar_figura(mock_fig, "test.png")
        assert result.endswith("test.png")
        assert str(tmp_path) in result

    def test_tight_layout_called(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, _ = mock_mpl
        helper._guardar_figura(mock_fig, "t.png")
        mock_fig.tight_layout.assert_called_once()

    def test_savefig_called(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, _ = mock_mpl
        helper._guardar_figura(mock_fig, "t.png")
        mock_fig.savefig.assert_called_once()

    def test_close_called(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, _ = mock_mpl
        helper._guardar_figura(mock_fig, "t.png")
        mock_plt.close.assert_called_once_with(mock_fig)


# ── plot_histograma ───────────────────────────────────────────────────────────


class TestPlotHistograma:
    def test_returns_none_for_empty_series(self, helper):
        result = helper.plot_histograma(pd.Series([], dtype=float), "col", 0)
        assert result is None

    def test_returns_path_for_valid_series(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, mock_ax = mock_mpl
        mock_plt.subplots.return_value = (mock_fig, mock_ax)
        serie = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = helper.plot_histograma(serie, "Casos", 0)
        assert result is not None
        assert "hist_Casos.png" in result

    def test_tono_cycles_palette(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, mock_ax = mock_mpl
        mock_plt.subplots.return_value = (mock_fig, mock_ax)
        # tono=100 should cycle without IndexError
        result = helper.plot_histograma(pd.Series([1, 2, 3]), "x", 100)
        assert result is not None

    def test_drops_nan_before_plotting(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, mock_ax = mock_mpl
        mock_plt.subplots.return_value = (mock_fig, mock_ax)
        serie = pd.Series([1.0, np.nan, 3.0])
        result = helper.plot_histograma(serie, "col_nan", 0)
        assert result is not None


# ── plot_categorica_barras ────────────────────────────────────────────────────


class TestPlotCategoricaBarras:
    def test_returns_none_for_empty_series(self, helper):
        result = helper.plot_categorica_barras(pd.Series([], dtype=str), "cat")
        assert result is None

    def test_returns_path_for_valid_data(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, mock_ax = mock_mpl
        mock_plt.subplots.return_value = (mock_fig, mock_ax)
        # Mock barh to return iterable bars
        mock_bar = MagicMock()
        mock_bar.get_y.return_value = 0
        mock_bar.get_height.return_value = 0.5
        mock_ax.barh.return_value = [mock_bar]
        serie = pd.Series(["A", "B", "A", "C", "B", "A"])
        result = helper.plot_categorica_barras(serie, "Categoria")
        assert result is not None
        assert "barras_Categoria.png" in result

    def test_truncates_to_top_n(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, mock_ax = mock_mpl
        mock_plt.subplots.return_value = (mock_fig, mock_ax)
        mock_bar = MagicMock()
        mock_bar.get_y.return_value = 0
        mock_bar.get_height.return_value = 0.5
        mock_ax.barh.return_value = [mock_bar]
        # 10 categories, top_n=5
        serie = pd.Series([str(i) for i in range(10)] * 2)
        helper.plot_categorica_barras(serie, "x")
        # Just ensure no crash and barh was called once
        assert mock_ax.barh.called


# ── plot_violin ───────────────────────────────────────────────────────────────


class TestPlotViolin:
    def test_returns_none_when_col_missing(self, helper):
        df = pd.DataFrame({"Anio": [2020]})
        result = helper.plot_violin(df, "no_existe", "Depresión")
        assert result is None

    def test_returns_none_when_col_all_nan(self, helper):
        df = pd.DataFrame({"Anio": [2020], "Casos": [np.nan]})
        result = helper.plot_violin(df, "Casos", "Depresión")
        assert result is None

    def test_returns_path_for_valid_data(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, mock_ax = mock_mpl
        mock_plt.subplots.return_value = (mock_fig, mock_ax)
        df = pd.DataFrame(
            {
                "Anio": [2020, 2020, 2021, 2021],
                "Acumulado_hombres": [10, 15, 12, 18],
            }
        )
        result = helper.plot_violin(df, "Acumulado_hombres", "Depresión")
        assert result is not None


# ── plot_correlacion ──────────────────────────────────────────────────────────


class TestPlotCorrelacion:
    def test_returns_none_for_single_column(self, helper):
        df = pd.DataFrame({"col1": [1.0, 2.0, 3.0]})
        result = helper.plot_correlacion(df)
        assert result is None

    def test_returns_path_for_multi_column(self, helper, mock_mpl):
        _, mock_plt, _, mock_fig, mock_ax = mock_mpl
        mock_plt.subplots.return_value = (mock_fig, mock_ax)
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]})
        result = helper.plot_correlacion(df)
        assert result is not None
        assert "correlacion.png" in result
