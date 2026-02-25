"""Tests for series_plots.py — time-series aggregation charts."""

import os

import pandas as pd

from epiforecast.visualization.series_plots import serie_tiempo

_PALETTE = {"cool_gray": "#999999"}
_PALETTE_SEXO = {"Hombres": "#0000FF", "Mujeres": "#FF0000"}


def _make_df() -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=20, freq="W")
    return pd.DataFrame(
        {
            "Fecha": list(dates) * 2,
            "incrementos_hombres": [5] * 40,
            "incrementos_mujeres": [3] * 40,
            "region_salud_mental": (["Metropolitana alta"] * 20 + ["Rural / dispersa"] * 20),
        }
    )


class TestSerieTiempoSexo:
    def test_returns_path_string(self, tmp_path):
        df = _make_df()
        ruta = serie_tiempo(
            df,
            "Depresión",
            str(tmp_path),
            72,
            _PALETTE,
            _PALETTE_SEXO,
            agrupamiento_sexo=True,
            agrupamiento_entidad=False,
        )
        assert isinstance(ruta, str)

    def test_file_created_on_disk(self, tmp_path):
        df = _make_df()
        ruta = serie_tiempo(
            df,
            "Depresión",
            str(tmp_path),
            72,
            _PALETTE,
            _PALETTE_SEXO,
            agrupamiento_sexo=True,
            agrupamiento_entidad=False,
        )
        assert os.path.isfile(ruta)

    def test_filename_contains_padecimiento(self, tmp_path):
        df = _make_df()
        ruta = serie_tiempo(
            df,
            "Parkinson",
            str(tmp_path),
            72,
            _PALETTE,
            _PALETTE_SEXO,
            agrupamiento_sexo=True,
            agrupamiento_entidad=False,
        )
        assert "Parkinson" in os.path.basename(ruta)

    def test_file_is_png(self, tmp_path):
        df = _make_df()
        ruta = serie_tiempo(
            df,
            "Alzheimer",
            str(tmp_path),
            72,
            _PALETTE,
            _PALETTE_SEXO,
            agrupamiento_sexo=True,
            agrupamiento_entidad=False,
        )
        assert ruta.endswith(".png")


class TestSerieTiempoEntidad:
    def test_returns_path_entidad_branch(self, tmp_path):
        df = _make_df()
        ruta = serie_tiempo(
            df,
            "Depresión",
            str(tmp_path),
            72,
            _PALETTE,
            _PALETTE_SEXO,
            agrupamiento_sexo=False,
            agrupamiento_entidad=True,
        )
        assert ruta is not None

    def test_file_created_entidad_branch(self, tmp_path):
        df = _make_df()
        ruta = serie_tiempo(
            df,
            "Depresión",
            str(tmp_path),
            72,
            _PALETTE,
            _PALETTE_SEXO,
            agrupamiento_sexo=False,
            agrupamiento_entidad=True,
        )
        assert os.path.isfile(ruta)

    def test_neither_branch_still_returns(self, tmp_path):
        df = _make_df()
        ruta = serie_tiempo(
            df,
            "Depresión",
            str(tmp_path),
            72,
            _PALETTE,
            _PALETTE_SEXO,
            agrupamiento_sexo=False,
            agrupamiento_entidad=False,
        )
        assert ruta is not None and os.path.isfile(ruta)

    def test_low_dpi(self, tmp_path):
        df = _make_df()
        ruta = serie_tiempo(
            df,
            "Parkinson",
            str(tmp_path),
            50,
            _PALETTE,
            _PALETTE_SEXO,
            agrupamiento_sexo=True,
            agrupamiento_entidad=False,
        )
        assert os.path.isfile(ruta)
