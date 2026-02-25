"""Tests for inegi_plots.py — barras_inegi and boxplots_inegi."""

from unittest.mock import patch

import pandas as pd

from epiforecast.visualization.inegi_plots import barras_inegi, boxplots_inegi


def _make_inegi_df(include_region: bool = True) -> pd.DataFrame:
    """Minimal INEGI DataFrame with all required columns."""
    n = 8
    df = pd.DataFrame(
        {
            "Entidad federativa": [f"Estado {i + 1}" for i in range(n)],
            "Total": [1_000_000 * (i + 1) for i in range(n)],
            "Hombres": [490_000 * (i + 1) for i in range(n)],
            "Mujeres": [510_000 * (i + 1) for i in range(n)],
            "Superficie_km2": [10_000 * (i + 1) for i in range(n)],
            "densidad_poblacion": [50.0 * (i + 1) for i in range(n)],
            "ratio_h_m": [0.96 + i * 0.01 for i in range(n)],
            "ratio_h_m_cat": pd.Categorical(
                (["Mayormente mujeres"] * 3 + ["Balanceado"] * 3 + ["Mayormente hombres"] * 2),
                categories=["Mayormente mujeres", "Balanceado", "Mayormente hombres"],
            ),
            "tamano_poblacional_grupo_percentil": pd.Categorical(
                (["Población baja"] * 2 + ["Media-baja"] * 2 + ["Media-alta"] * 2 + ["Alta"] * 2),
                categories=["Población baja", "Media-baja", "Media-alta", "Alta"],
            ),
            "extension_territorial_percentil": pd.Categorical(
                (
                    ["Territorio pequeño"] * 2
                    + ["Medio-pequeño"] * 2
                    + ["Medio-grande"] * 2
                    + ["Grande"] * 2
                ),
                categories=[
                    "Territorio pequeño",
                    "Medio-pequeño",
                    "Medio-grande",
                    "Grande",
                ],
            ),
            "densidad_poblacional_percentil": pd.Categorical(
                ["Baja"] * 2 + ["Media-baja"] * 2 + ["Media-alta"] * 2 + ["Alta"] * 2,
                categories=["Baja", "Media-baja", "Media-alta", "Alta"],
            ),
        }
    )
    if include_region:
        df["region_salud_mental"] = pd.Categorical(
            (
                ["Metropolitana alta"] * 2
                + ["Urbana media"] * 2
                + ["Rural / dispersa"] * 2
                + ["Sur-Sureste vulnerable"] * 2
            ),
            categories=[
                "Metropolitana alta",
                "Urbana media",
                "Rural / dispersa",
                "Sur-Sureste vulnerable",
            ],
        )
    return df


class TestBarrasInegi:
    def test_runs_with_region(self):
        df = _make_inegi_df(include_region=True)
        with patch("matplotlib.pyplot.show"):
            barras_inegi(df)  # should not raise

    def test_runs_without_region(self):
        df = _make_inegi_df(include_region=False)
        with patch("matplotlib.pyplot.show"):
            barras_inegi(df)

    def test_handles_different_n_states(self):
        n = 4
        df = pd.DataFrame(
            {
                "Entidad federativa": [f"E{i}" for i in range(n)],
                "Total": [100 * (i + 1) for i in range(n)],
                "Hombres": [50 * (i + 1) for i in range(n)],
                "Mujeres": [50 * (i + 1) for i in range(n)],
                "Superficie_km2": [1000 * (i + 1) for i in range(n)],
                "densidad_poblacion": [10.0 * (i + 1) for i in range(n)],
                "ratio_h_m": [1.0] * n,
                "ratio_h_m_cat": pd.Categorical(
                    ["Balanceado"] * n,
                    categories=["Mayormente mujeres", "Balanceado", "Mayormente hombres"],
                ),
                "tamano_poblacional_grupo_percentil": pd.Categorical(
                    ["Población baja"] * n,
                    categories=["Población baja", "Media-baja", "Media-alta", "Alta"],
                ),
                "extension_territorial_percentil": pd.Categorical(
                    ["Territorio pequeño"] * n,
                    categories=["Territorio pequeño", "Medio-pequeño", "Medio-grande", "Grande"],
                ),
                "densidad_poblacional_percentil": pd.Categorical(
                    ["Baja"] * n, categories=["Baja", "Media-baja", "Media-alta", "Alta"]
                ),
            }
        )
        with patch("matplotlib.pyplot.show"):
            barras_inegi(df)


class TestBoxplotsInegi:
    def test_runs_with_region(self):
        df = _make_inegi_df(include_region=True)
        with patch("matplotlib.pyplot.show"):
            boxplots_inegi(df)

    def test_runs_without_region(self):
        df = _make_inegi_df(include_region=False)
        with patch("matplotlib.pyplot.show"):
            boxplots_inegi(df)

    def test_with_zero_density(self):
        df = _make_inegi_df(include_region=False)
        df.loc[0, "densidad_poblacion"] = 0  # will be set to NA
        with patch("matplotlib.pyplot.show"):
            boxplots_inegi(df)

    def test_computes_ratio_if_missing(self):
        df = _make_inegi_df(include_region=False)
        df = df.drop(columns=["ratio_h_m"])  # force ratio recompute
        with patch("matplotlib.pyplot.show"):
            boxplots_inegi(df)

    def test_with_all_zero_population(self):
        df = _make_inegi_df(include_region=False)
        df["Total"] = 0  # all zeros → will be set to NA
        with patch("matplotlib.pyplot.show"):
            boxplots_inegi(df)
