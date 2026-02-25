"""Tests for inegi_tables.py — Rich console EDA output."""

from unittest.mock import patch

import pandas as pd

import epiforecast.visualization.inegi_tables as it_mod
from epiforecast.visualization.inegi_tables import _fmt, _print_df, _print_series, eda_inegi


class TestFmt:
    def test_nan_returns_empty_string(self):
        assert _fmt(float("nan")) == ""

    def test_integer_formatted_with_commas(self):
        result = _fmt(1000000)
        assert result == "1,000,000"

    def test_float_with_decimal_places(self):
        result = _fmt(3.14159, nd=2)
        assert "3.14" in result

    def test_float_integer_value_no_decimals(self):
        result = _fmt(5.0)
        assert result == "5"

    def test_string_returned_as_is(self):
        result = _fmt("texto")
        assert result == "texto"

    def test_pd_na(self):
        result = _fmt(pd.NA)
        assert result == ""

    def test_zero(self):
        result = _fmt(0)
        assert result == "0"


class TestPrintDf:
    def _make_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Entidad federativa": ["Jalisco", "Oaxaca"],
                "Total": [7_000_000, 4_000_000],
                "ratio_h_m": [0.98, 1.02],
            }
        )

    def test_runs_without_error(self, capsys):
        df = self._make_df()
        # Should not raise
        _print_df(df, "Test Table")

    def test_max_rows_respected(self, capsys):
        df = pd.DataFrame({"A": list(range(20))})
        _print_df(df, "Largo", max_rows=5)  # should not raise

    def test_empty_dataframe(self, capsys):
        df = pd.DataFrame()
        _print_df(df, "Vacío")  # should not raise


class TestPrintSeries:
    def test_runs_without_error(self, capsys):
        s = pd.Series([10, 5, 3], index=["A", "B", "C"])
        _print_series(s, "Conteos")  # should not raise

    def test_empty_series(self, capsys):
        s = pd.Series([], dtype=int)
        _print_series(s, "Vacío")  # should not raise


class TestEdaInegi:
    def _make_inegi_df(self, include_region: bool = True) -> pd.DataFrame:
        n = 5
        df = pd.DataFrame(
            {
                "Entidad federativa": [f"Estado {i}" for i in range(n)],
                "Total": [1_000_000 * (i + 1) for i in range(n)],
                "Hombres": [500_000 * (i + 1) for i in range(n)],
                "Mujeres": [500_000 * (i + 1) for i in range(n)],
                "Superficie_km2": [10_000 * (i + 1) for i in range(n)],
                "densidad_poblacion": [100.0 * (i + 1) for i in range(n)],
                "ratio_h_m": [0.98 + i * 0.01 for i in range(n)],
                "ratio_h_m_cat": pd.Categorical(
                    ["Balanceado"] * n,
                    categories=["Mayormente mujeres", "Balanceado", "Mayormente hombres"],
                ),
                "tamano_poblacional_predefinido": pd.Categorical(
                    ["0-1M"] * n, categories=["0-1M", "1-3M", "3-6M", "6M+"]
                ),
                "tamano_poblacional_grupo_percentil": pd.Categorical(
                    ["Población baja"] * n,
                    categories=["Población baja", "Media-baja", "Media-alta", "Alta"],
                ),
                "extension_territorial_percentil": pd.Categorical(
                    ["Territorio pequeño"] * n,
                    categories=[
                        "Territorio pequeño",
                        "Medio-pequeño",
                        "Medio-grande",
                        "Grande",
                    ],
                ),
                "densidad_poblacional_percentil": pd.Categorical(
                    ["Baja"] * n,
                    categories=["Baja", "Media-baja", "Media-alta", "Alta"],
                ),
            }
        )
        if include_region:
            df["region_salud_mental"] = ["Metropolitana alta"] * n
        return df

    def test_runs_without_error(self):
        df = self._make_inegi_df()
        with (
            patch.object(it_mod, "barras_inegi", return_value=None),
            patch.object(it_mod, "boxplots_inegi", return_value=None),
        ):
            eda_inegi(df)  # should not raise

    def test_runs_without_region(self):
        df = self._make_inegi_df(include_region=False)
        with (
            patch.object(it_mod, "barras_inegi", return_value=None),
            patch.object(it_mod, "boxplots_inegi", return_value=None),
        ):
            eda_inegi(df)

    def test_with_nan_values(self):
        df = self._make_inegi_df()
        df.loc[0, "Total"] = float("nan")
        with (
            patch.object(it_mod, "barras_inegi", return_value=None),
            patch.object(it_mod, "boxplots_inegi", return_value=None),
        ):
            eda_inegi(df)

    def test_barras_called(self):
        df = self._make_inegi_df()
        with (
            patch.object(it_mod, "barras_inegi") as mock_barras,
            patch.object(it_mod, "boxplots_inegi", return_value=None),
        ):
            eda_inegi(df)
        mock_barras.assert_called_once()

    def test_boxplots_called(self):
        df = self._make_inegi_df()
        with (
            patch.object(it_mod, "barras_inegi", return_value=None),
            patch.object(it_mod, "boxplots_inegi") as mock_box,
        ):
            eda_inegi(df)
        mock_box.assert_called_once()

    def test_with_missing_region_entries(self):
        df = self._make_inegi_df(include_region=True)
        df.loc[0, "region_salud_mental"] = None
        with (
            patch.object(it_mod, "barras_inegi", return_value=None),
            patch.object(it_mod, "boxplots_inegi", return_value=None),
        ):
            eda_inegi(df)
