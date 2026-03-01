"""Tests para eda_summaries: funciones standalone de resumen EDA."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from epiforecast.visualization.eda_summaries import (
    estadisticas_numericas,
    resumen_general,
    resumen_nulos,
    resumen_unicos,
    tablas_categoricas,
)


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "edad": [25, 30, np.nan, 40, 50],
            "nombre": ["Ana", "Luis", "Ana", "Carlos", "Ana"],
            "peso": [60.5, 75.0, 80.2, np.nan, 65.3],
        }
    )


class TestResumenGeneral:
    def test_returns_dict_with_expected_keys(self):
        df = _sample_df()
        opciones = {
            "COLS_NUMERICAS": ["edad", "peso"],
            "COLS_CATEGORICAS": ["nombre"],
            "filtro_padecimiento": "Alzheimer",
        }
        with patch("epiforecast.visualization.eda_summaries.logger", MagicMock()):
            result = resumen_general(df, "test_source", opciones)

        assert isinstance(result, dict)
        assert "Filas" in result
        assert "Columnas" in result
        assert "Porcentaje de nulos" in result
        assert "Fuente" in result
        assert result["Fuente"] == "test_source"


class TestResumenUnicos:
    def test_returns_dataframe(self):
        df = _sample_df()
        with patch("epiforecast.visualization.eda_summaries.logger", MagicMock()):
            result = resumen_unicos(df)

        assert isinstance(result, pd.DataFrame)
        assert "Valores únicos" in result.columns
        assert len(result) > 0


class TestResumenNulos:
    def test_returns_none_if_no_nulls(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        with patch("epiforecast.visualization.eda_summaries.logger", MagicMock()):
            result = resumen_nulos(df)
        assert result is None

    def test_returns_dataframe_with_nulls(self):
        df = _sample_df()
        with patch("epiforecast.visualization.eda_summaries.logger", MagicMock()):
            result = resumen_nulos(df)
        assert isinstance(result, pd.DataFrame)
        assert "Nulos" in result.columns


class TestEstadisticasNumericas:
    def test_returns_stats_for_numeric_columns(self):
        df = _sample_df()
        with patch("epiforecast.visualization.eda_summaries.logger", MagicMock()):
            result = estadisticas_numericas(df)
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert "media" in result.columns

    def test_returns_none_for_no_numeric(self):
        df = pd.DataFrame({"a": ["x", "y"], "b": ["z", "w"]})
        with patch("epiforecast.visualization.eda_summaries.logger", MagicMock()):
            result = estadisticas_numericas(df)
        assert result is None


class TestTablasCategoricas:
    def test_returns_dict_with_top_n(self):
        df = _sample_df()
        opciones = {"COLS_CATEGORICAS": ["nombre"]}
        with patch("epiforecast.visualization.eda_summaries.logger", MagicMock()):
            result = tablas_categoricas(df, opciones, n_top=2)
        assert isinstance(result, dict)
        assert "nombre" in result
        assert len(result["nombre"]) <= 2
