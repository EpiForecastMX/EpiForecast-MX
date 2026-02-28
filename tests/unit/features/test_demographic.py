"""Tests for demographic.py — MapeaInegi population merge."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import epiforecast.features.demographic as dem_mod
from epiforecast.features.demographic import MapeaInegi

_MOCK_CONF = {
    "data": {
        "inegi": "/tmp/test_inegi.csv",
        "data_inegi": "/tmp/test_data_inegi.csv",
        "xlsx_inegi": "/tmp/test_data_inegi.xlsx",
    }
}


def _make_mapea(df: pd.DataFrame | None = None) -> MapeaInegi:
    if df is None:
        df = pd.DataFrame({"Entidad": ["Jalisco", "Oaxaca"], "Casos": [100, 50]})
    with patch.object(dem_mod, "conf", _MOCK_CONF):
        return MapeaInegi(df)


class TestInit:
    def test_df_copied(self):
        df = pd.DataFrame({"Entidad": ["Jalisco"], "Casos": [10]})
        mapea = _make_mapea(df)
        df["Casos"] = 999
        assert mapea.df["Casos"].iloc[0] == 10

    def test_paths_set_from_conf(self):
        mapea = _make_mapea()
        assert mapea.inegi_path == "/tmp/test_inegi.csv"
        assert mapea.final_path == "/tmp/test_data_inegi.csv"
        assert mapea.xlsx_path == "/tmp/test_data_inegi.xlsx"


class TestRenombra:
    def test_column_renamed_to_entidad(self):
        mapea = _make_mapea()
        mapea.inegi = pd.DataFrame({"Entidad federativa": ["Jalisco"], "Total": [1000]})
        mapea.renombra()
        assert "Entidad" in mapea.inegi.columns
        assert "Entidad federativa" not in mapea.inegi.columns

    def test_coahuila_renamed(self):
        mapea = _make_mapea()
        mapea.inegi = pd.DataFrame(
            {"Entidad federativa": ["Coahuila de Zaragoza"], "Total": [500]}
        )
        mapea.renombra()
        assert "Coahuila" in mapea.inegi["Entidad"].values
        assert "Coahuila de Zaragoza" not in mapea.inegi["Entidad"].values

    def test_michoacan_renamed(self):
        mapea = _make_mapea()
        mapea.inegi = pd.DataFrame({"Entidad federativa": ["Michoacán de Ocampo"], "Total": [700]})
        mapea.renombra()
        assert "Michoacán" in mapea.inegi["Entidad"].values

    def test_veracruz_renamed(self):
        mapea = _make_mapea()
        mapea.inegi = pd.DataFrame(
            {"Entidad federativa": ["Veracruz de Ignacio de la Llave"], "Total": [800]}
        )
        mapea.renombra()
        assert "Veracruz" in mapea.inegi["Entidad"].values

    def test_other_states_unchanged(self):
        mapea = _make_mapea()
        mapea.inegi = pd.DataFrame(
            {"Entidad federativa": ["Jalisco", "Oaxaca"], "Total": [1000, 500]}
        )
        mapea.renombra()
        assert "Jalisco" in mapea.inegi["Entidad"].values
        assert "Oaxaca" in mapea.inegi["Entidad"].values


class TestCombina:
    def test_merge_adds_inegi_columns(self):
        df = pd.DataFrame({"Entidad": ["Jalisco", "Oaxaca"], "Casos": [10, 5]})
        mapea = _make_mapea(df)
        mapea.inegi = pd.DataFrame(
            {"Entidad": ["Jalisco", "Oaxaca"], "Total": [7_000_000, 4_000_000]}
        )
        mapea.combina()
        assert not mapea.df_merge.empty
        assert "Total" in mapea.df_merge.columns

    def test_left_join_preserves_all_rows(self):
        df = pd.DataFrame({"Entidad": ["Jalisco", "EstadoFantasma"], "Casos": [10, 5]})
        mapea = _make_mapea(df)
        mapea.inegi = pd.DataFrame({"Entidad": ["Jalisco"], "Total": [7_000_000]})
        mapea.combina()
        assert len(mapea.df_merge) == 2

    def test_multiple_extra_columns_merged(self):
        df = pd.DataFrame({"Entidad": ["Jalisco"], "Casos": [10]})
        mapea = _make_mapea(df)
        mapea.inegi = pd.DataFrame(
            {
                "Entidad": ["Jalisco"],
                "Total": [7_000_000],
                "densidad_poblacion": [100.0],
                "Superficie_km2": [78_600.0],
            }
        )
        mapea.combina()
        assert "densidad_poblacion" in mapea.df_merge.columns
        assert "Superficie_km2" in mapea.df_merge.columns


class TestRun:
    def test_raises_if_inegi_file_missing(self):
        mapea = _make_mapea()
        with patch.object(dem_mod.directory_manager, "existe_archivo", return_value=False):
            with pytest.raises(FileNotFoundError):
                mapea.run()

    def test_exits_if_merge_is_empty(self):
        mapea = _make_mapea()
        empty_inegi = pd.DataFrame({"Entidad federativa": [], "Total": []})

        with (
            patch.object(dem_mod.directory_manager, "existe_archivo", return_value=True),
            patch("pandas.read_csv", return_value=empty_inegi),
        ):
            # renombra will set columns, combina will produce empty merge
            # force df_merge to empty after run
            original_combina = mapea.combina

            def patched_combina():
                original_combina()
                mapea.df_merge = pd.DataFrame()

            mapea.combina = patched_combina
            with pytest.raises(RuntimeError):
                mapea.run()

    def test_run_saves_csv_when_successful(self, tmp_path):
        df_epi = pd.DataFrame({"Entidad": ["Jalisco"], "Casos": [10]})
        mapea = _make_mapea(df_epi)
        mock_conf = {
            "data": {
                "inegi": str(tmp_path / "inegi.csv"),
                "data_inegi": str(tmp_path / "data_inegi.csv"),
                "xlsx_inegi": str(tmp_path / "data_inegi.xlsx"),
            }
        }
        with patch.object(dem_mod, "conf", mock_conf):
            mapea2 = MapeaInegi(df_epi)

        inegi_data = pd.DataFrame({"Entidad federativa": ["Jalisco"], "Total": [7_000_000]})
        inegi_data.to_csv(mock_conf["data"]["inegi"], index=False)

        with (
            patch.object(dem_mod.directory_manager, "existe_archivo", return_value=True),
            patch("pandas.read_csv", return_value=inegi_data),
            patch.object(dem_mod.directory_manager, "asegurar_ruta"),
        ):
            mapea2.renombra = MagicMock(
                side_effect=lambda: setattr(
                    mapea2, "inegi", pd.DataFrame({"Entidad": ["Jalisco"], "Total": [7_000_000]})
                )
            )

            def mock_combina():
                mapea2.df_merge = pd.DataFrame(
                    {"Entidad": ["Jalisco"], "Casos": [10], "Total": [7_000_000]}
                )

            mapea2.combina = mock_combina
            with patch.object(mapea2.df_merge.__class__, "to_csv"):
                with patch.object(pd.DataFrame, "to_csv"):
                    with patch.object(pd.DataFrame, "to_excel"):
                        mapea2.run()
