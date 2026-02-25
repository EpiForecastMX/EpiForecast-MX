"""Tests for imputation.py — IQR and Z-score outlier adjustment."""

import pandas as pd

from epiforecast.data.preprocessing.imputation import ajusta_outliers, ajusta_outliers_zscore


def _make_df(n_normal: int = 9, outlier: int = 10000) -> pd.DataFrame:
    """Minimal DataFrame with Padecimiento + Casos for outlier tests."""
    return pd.DataFrame(
        {
            "Padecimiento": ["Depresión"] * (n_normal + 1),
            "Casos": [5] * n_normal + [outlier],
        }
    )


class TestAjustaOutliersIQR:
    def test_returns_dataframe(self):
        df = _make_df()
        result = ajusta_outliers(df, ["Casos"], ["Padecimiento"])
        assert isinstance(result, pd.DataFrame)

    def test_outlier_clipped(self):
        df = _make_df(n_normal=9, outlier=10000)
        result = ajusta_outliers(df, ["Casos"], ["Padecimiento"])
        assert int(result["Casos"].max()) < 10000

    def test_no_extra_cols_in_result(self):
        df = _make_df()
        result = ajusta_outliers(df, ["Casos"], ["Padecimiento"])
        assert "iqr" not in result.columns
        assert "q1" not in result.columns
        assert "lim_inf" not in result.columns
        assert "lim_sup" not in result.columns

    def test_multiple_groups_processed(self):
        df = pd.DataFrame(
            {
                "Padecimiento": ["Depresión"] * 5 + ["Parkinson"] * 5,
                "Casos": [5, 5, 5, 5, 200] + [3, 3, 3, 3, 150],
            }
        )
        result = ajusta_outliers(df, ["Casos"], ["Padecimiento"])
        assert len(result) == 10

    def test_result_same_shape(self):
        df = _make_df()
        result = ajusta_outliers(df, ["Casos"], ["Padecimiento"])
        assert result.shape[0] == df.shape[0]

    def test_no_outlier_values_unchanged(self):
        df = pd.DataFrame(
            {
                "Padecimiento": ["Depresión"] * 5,
                "Casos": [5, 5, 5, 5, 5],
            }
        )
        result = ajusta_outliers(df, ["Casos"], ["Padecimiento"])
        assert result["Casos"].tolist() == [5, 5, 5, 5, 5]

    def test_multiple_columns(self):
        df = pd.DataFrame(
            {
                "Padecimiento": ["Depresión"] * 10,
                "ColA": [5] * 9 + [9999],
                "ColB": [3] * 9 + [8888],
            }
        )
        result = ajusta_outliers(df, ["ColA", "ColB"], ["Padecimiento"])
        assert int(result["ColA"].max()) < 9999
        assert int(result["ColB"].max()) < 8888


class TestAjustaOutliersZscore:
    def test_returns_dataframe(self):
        df = _make_df()
        result = ajusta_outliers_zscore(df, ["Casos"], ["Padecimiento"], 2, "media")
        assert isinstance(result, pd.DataFrame)

    def test_outlier_replaced(self):
        df = _make_df(n_normal=9, outlier=100000)
        result = ajusta_outliers_zscore(df, ["Casos"], ["Padecimiento"], 2, "media")
        assert float(result["Casos"].max()) < 100000

    def test_same_shape_returned(self):
        df = _make_df()
        result = ajusta_outliers_zscore(df, ["Casos"], ["Padecimiento"], 3, "media")
        assert result.shape[0] == df.shape[0]

    def test_multiple_columns_processed(self):
        df = pd.DataFrame(
            {
                "Padecimiento": ["Depresión"] * 10,
                "Col1": [5] * 9 + [100000],
                "Col2": [3] * 9 + [80000],
            }
        )
        result = ajusta_outliers_zscore(df, ["Col1", "Col2"], ["Padecimiento"], 2, "media")
        assert float(result["Col1"].max()) < 100000
        assert float(result["Col2"].max()) < 80000

    def test_no_outliers_unchanged(self):
        df = pd.DataFrame(
            {
                "Padecimiento": ["Depresión"] * 5,
                "Casos": [5, 5, 5, 5, 5],
            }
        )
        result = ajusta_outliers_zscore(df, ["Casos"], ["Padecimiento"], 3, "media")
        assert result["Casos"].tolist() == [5, 5, 5, 5, 5]
