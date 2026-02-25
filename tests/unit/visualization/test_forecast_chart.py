"""Tests for forecast_chart.py — graficar_pronostico."""

import os
from unittest.mock import patch

import pandas as pd
import pytest

import epiforecast.visualization.chart_annotations as ca_mod
from epiforecast.visualization.forecast_chart import graficar_pronostico

# Patch FECHA_CORTE_ENTRENAMIENTO into chart_annotations.conf for all tests in this module
_CONF_PATCH = {"FECHA_CORTE_ENTRENAMIENTO": "2022-01-01"}


@pytest.fixture(autouse=True)
def patch_ca_conf():
    """Inject FECHA_CORTE_ENTRENAMIENTO so _anotar_zona_cv does not KeyError."""
    with patch.object(ca_mod, "conf", _CONF_PATCH):
        yield


_PALETTE = {
    "teal": "#007A8A",
    "burgundy": "#8C1515",
    "cool_gray": "#999999",
    "neutral_black": "#222222",
}
_PALETTE_PAD = {
    "Depresion": {"c1": "#8C1515", "cl": "#D4758B"},
    "Parkinson": {"c1": "#005B82", "cl": "#7AB4CC"},
    "Alzheimer": {"c1": "#3B5E2B", "cl": "#9DBE8F"},
}
_COVID = {"inicio": "2020-03-01", "fin": "2021-06-01"}


def _make_serie(n: int = 60) -> pd.DataFrame:
    dates = pd.date_range("2019-01-01", periods=n, freq="W")
    return pd.DataFrame({"ds": dates, "y": [5.0] * n})


def _make_forecast(n: int = 20) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="W")
    return pd.DataFrame(
        {
            "ds": dates,
            "yhat": [6.0] * n,
            "yhat_lower": [4.0] * n,
            "yhat_upper": [8.0] * n,
        }
    )


class TestGraficarPronostico:
    def test_returns_path_string(self, tmp_path):
        ruta = graficar_pronostico(
            forecast=_make_forecast(),
            serie=_make_serie(),
            titulo="Depresion · Jalisco · hombres",
            padecimiento="Depresion",
            nombre_archivo="test_chart",
            carpeta_salida=str(tmp_path),
            conf_paleta=_PALETTE,
            conf_paleta_padecimiento=_PALETTE_PAD,
            conf_covid=_COVID,
        )
        assert isinstance(ruta, str)

    def test_png_created_on_disk(self, tmp_path):
        ruta = graficar_pronostico(
            forecast=_make_forecast(),
            serie=_make_serie(),
            titulo="Parkinson · Nacional · todos",
            padecimiento="Parkinson",
            nombre_archivo="parkinson_nacional",
            carpeta_salida=str(tmp_path),
            conf_paleta=_PALETTE,
            conf_paleta_padecimiento=_PALETTE_PAD,
            conf_covid=_COVID,
        )
        assert os.path.isfile(ruta)

    def test_file_is_png(self, tmp_path):
        ruta = graficar_pronostico(
            forecast=_make_forecast(),
            serie=_make_serie(),
            titulo="Alzheimer · Oaxaca · mujeres",
            padecimiento="Alzheimer",
            nombre_archivo="alzheimer_oaxaca",
            carpeta_salida=str(tmp_path),
            conf_paleta=_PALETTE,
            conf_paleta_padecimiento=_PALETTE_PAD,
            conf_covid=_COVID,
        )
        assert ruta.endswith(".png")

    def test_with_metricas(self, tmp_path):
        metricas = {
            "mase": 0.75,
            "rmse": 0.12,
            "confianza": "normal",
            "es_fallback": False,
            "modelo_usado": "Prophet_Depresion_Jalisco_hombres.pkl",
            "seasonality_mode": "additive",
        }
        ruta = graficar_pronostico(
            forecast=_make_forecast(),
            serie=_make_serie(),
            titulo="Depresion · Jalisco · hombres",
            padecimiento="Depresion",
            nombre_archivo="chart_with_metricas",
            carpeta_salida=str(tmp_path),
            conf_paleta=_PALETTE,
            conf_paleta_padecimiento=_PALETTE_PAD,
            conf_covid=_COVID,
            metricas=metricas,
        )
        assert os.path.isfile(ruta)

    def test_with_none_metricas(self, tmp_path):
        ruta = graficar_pronostico(
            forecast=_make_forecast(),
            serie=_make_serie(),
            titulo="Depresion · Jalisco · hombres",
            padecimiento="Depresion",
            nombre_archivo="chart_no_metricas",
            carpeta_salida=str(tmp_path),
            conf_paleta=_PALETTE,
            conf_paleta_padecimiento=_PALETTE_PAD,
            conf_covid=_COVID,
            metricas=None,
        )
        assert os.path.isfile(ruta)

    def test_with_outliers_in_serie(self, tmp_path):
        serie = _make_serie(60)
        serie.loc[0, "y"] = 10000.0  # extreme outlier
        ruta = graficar_pronostico(
            forecast=_make_forecast(),
            serie=serie,
            titulo="Depresion · Jalisco · todos",
            padecimiento="Depresion",
            nombre_archivo="chart_outlier",
            carpeta_salida=str(tmp_path),
            conf_paleta=_PALETTE,
            conf_paleta_padecimiento=_PALETTE_PAD,
            conf_covid=_COVID,
        )
        assert os.path.isfile(ruta)

    def test_unknown_padecimiento_uses_fallback_palette(self, tmp_path):
        ruta = graficar_pronostico(
            forecast=_make_forecast(),
            serie=_make_serie(),
            titulo="General · Nacional · todos",
            padecimiento="General",
            nombre_archivo="chart_general",
            carpeta_salida=str(tmp_path),
            conf_paleta=_PALETTE,
            conf_paleta_padecimiento=_PALETTE_PAD,
            conf_covid=_COVID,
        )
        assert os.path.isfile(ruta)

    def test_titulo_without_dots_parsed_safely(self, tmp_path):
        ruta = graficar_pronostico(
            forecast=_make_forecast(),
            serie=_make_serie(),
            titulo="SinPuntos",
            padecimiento="Depresion",
            nombre_archivo="chart_sinpuntos",
            carpeta_salida=str(tmp_path),
            conf_paleta=_PALETTE,
            conf_paleta_padecimiento=_PALETTE_PAD,
            conf_covid=_COVID,
        )
        assert os.path.isfile(ruta)
