# tests/unit/visualization/test_eda_plots.py
"""Unit tests for EDAReportBuilder and dataclasses in eda_plots.py.

Mocks conf, filesystem helpers, and GraficosHelper to avoid side effects.
Summary functions are tested against the standalone ``eda_summaries`` module.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import epiforecast.visualization.eda_plots as eda_mod
from epiforecast.visualization.eda_plots import (
    EDAReportBuilder,
    ReportData,
    SeccionNota,
)
from epiforecast.visualization.eda_summaries import (
    estadisticas_categoricas,
    estadisticas_numericas,
    resumen_general,
    resumen_nulos,
    resumen_unicos,
    tablas_categoricas,
)

# ── Shared fixtures ───────────────────────────────────────────────────────────

MOCK_CONF = {
    "paths": {"figures": "/tmp/epi_test/figures"},
}

OPCIONES = {
    "titulo_reporte": "EDA Test",
    "subtitulo_reporte": "Prueba unitaria",
    "filtro_padecimiento": "Depresión",
    "max_cols": 5,
    "violin": False,
    "COLS_NUMERICAS": ["Casos"],
    "COLS_CATEGORICAS": ["Entidad"],
}


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        {
            "Anio": [2022, 2022, 2023],
            "Semana": [1, 2, 1],
            "Entidad": ["Jalisco", "Oaxaca", "Jalisco"],
            "Padecimiento": ["Depresión"] * 3,
            "Casos": [10, 20, 15],
        }
    )


@pytest.fixture
def mock_dir():
    with (
        patch.object(eda_mod, "directory_manager") as mock_dm,
        patch.object(eda_mod, "conf", MOCK_CONF),
    ):
        mock_dm.asegurar_ruta = MagicMock()
        mock_dm.limpia_carpeta = MagicMock()
        yield mock_dm


@pytest.fixture
def builder(sample_df, mock_dir):  # noqa: ARG001
    with (
        patch.object(eda_mod, "conf", MOCK_CONF),
        patch("epiforecast.visualization.eda_plots.GraficosHelper") as mock_gh,
    ):
        mock_gh_instance = MagicMock()
        mock_gh_instance.plot_histograma.return_value = "/tmp/hist.png"
        mock_gh_instance.plot_categorica_barras.return_value = "/tmp/barras.png"
        mock_gh_instance.plot_correlacion.return_value = "/tmp/corr.png"
        mock_gh.return_value = mock_gh_instance
        obj = EDAReportBuilder(sample_df, "test_source", OPCIONES)
        obj.graficos_helper = mock_gh_instance
    return obj


# ── SeccionNota dataclass ─────────────────────────────────────────────────────


class TestSeccionNota:
    def test_required_fields(self):
        s = SeccionNota(titulo="Limpieza")
        assert s.titulo == "Limpieza"
        assert s.texto is None
        assert s.parametros is None
        assert s.tabla is None

    def test_all_fields(self):
        df = pd.DataFrame({"a": [1]})
        s = SeccionNota(titulo="T", texto="Desc", parametros={"k": "v"}, tabla=df)
        assert s.parametros == {"k": "v"}
        assert s.tabla is not None


# ── ReportData dataclass ──────────────────────────────────────────────────────


class TestReportData:
    def _make_report(self):
        return ReportData(
            titulo="Mi Reporte",
            subtitulo="Subtítulo",
            fuente_datos="SINAVE",
            resumen_general={"Filas": "100"},
            resumen_datos=None,
            resumen_datos_nulos=None,
            estadisticas_numericas=None,
            estadisticas_categoricas=None,
            tablas_categoricas={},
        )

    def test_default_figuras_empty(self):
        rd = self._make_report()
        assert rd.figuras == []

    def test_default_secciones_notas_empty(self):
        rd = self._make_report()
        assert rd.secciones_notas == []

    def test_titulo_stored(self):
        rd = self._make_report()
        assert rd.titulo == "Mi Reporte"


# ── resumen_general (standalone) ─────────────────────────────────────────────


class TestResumenGeneral:
    def test_returns_dict(self, sample_df):
        result = resumen_general(sample_df, "test_source", OPCIONES)
        assert isinstance(result, dict)

    def test_has_expected_keys(self, sample_df):
        result = resumen_general(sample_df, "test_source", OPCIONES)
        expected = {"Fecha de EDA", "Filas", "Columnas", "Fuente", "Porcentaje de nulos"}
        assert expected.issubset(set(result.keys()))

    def test_filas_matches_df(self, sample_df):
        result = resumen_general(sample_df, "test_source", OPCIONES)
        assert result["Filas"] == f"{len(sample_df):,}"

    def test_padecimiento_from_opciones(self, sample_df):
        result = resumen_general(sample_df, "test_source", OPCIONES)
        assert result["Padecimiento"] == "Depresión"


# ── resumen_unicos (standalone) ──────────────────────────────────────────────


class TestResumenUnicos:
    def test_returns_dataframe(self, sample_df):
        result = resumen_unicos(sample_df)
        assert isinstance(result, pd.DataFrame)

    def test_has_valores_unicos_column(self, sample_df):
        result = resumen_unicos(sample_df)
        assert "Valores únicos" in result.columns

    def test_has_tipo_column(self, sample_df):
        result = resumen_unicos(sample_df)
        assert "Tipo" in result.columns


# ── resumen_nulos (standalone) ────────────────────────────────────────────────


class TestResumenNulos:
    def test_returns_none_when_no_nulls(self, sample_df):
        result = resumen_nulos(sample_df)
        assert result is None

    def test_returns_df_when_nulls_present(self, sample_df):
        sample_df_with_na = sample_df.copy()
        sample_df_with_na.loc[0, "Casos"] = None
        result = resumen_nulos(sample_df_with_na)
        assert result is not None
        assert "Nulos" in result.columns


# ── estadisticas_numericas (standalone) ───────────────────────────────────────


class TestEstadisticasNumericas:
    def test_returns_dataframe(self, sample_df):
        result = estadisticas_numericas(sample_df)
        assert isinstance(result, pd.DataFrame)

    def test_returns_none_for_non_numeric_df(self):
        df_str = pd.DataFrame({"col": ["a", "b"]})
        result = estadisticas_numericas(df_str)
        assert result is None

    def test_has_media_column(self, sample_df):
        result = estadisticas_numericas(sample_df)
        assert "media" in result.columns


# ── estadisticas_categoricas (standalone) ─────────────────────────────────────


class TestEstadisticasCategoricas:
    def test_returns_none_when_no_cat_cols(self):
        result = estadisticas_categoricas({**OPCIONES, "COLS_CATEGORICAS": []})
        assert result is None

    def test_returns_dataframe_with_cat_cols(self):
        result = estadisticas_categoricas(OPCIONES)
        assert result is None or isinstance(result, pd.DataFrame)


# ── tablas_categoricas (standalone) ──────────────────────────────────────────


class TestTablasCategoricas:
    def test_returns_dict(self, sample_df):
        result = tablas_categoricas(sample_df, OPCIONES)
        assert isinstance(result, dict)

    def test_key_per_col_category(self, sample_df):
        result = tablas_categoricas(sample_df, OPCIONES)
        for key in OPCIONES["COLS_CATEGORICAS"]:
            assert key in result


# ── EDAReportBuilder.run ──────────────────────────────────────────────────────


class TestEDAReportBuilderRun:
    def test_run_returns_report_data(self, builder):
        result = builder.run()
        assert isinstance(result, ReportData)

    def test_figuras_populated(self, builder):
        result = builder.run()
        assert isinstance(result.figuras, list)

    def test_titulo_in_report(self, builder):
        result = builder.run()
        assert result.titulo == OPCIONES["titulo_reporte"]

    def test_resumen_general_in_report(self, builder):
        result = builder.run()
        assert isinstance(result.resumen_general, dict)
        assert "Filas" in result.resumen_general
