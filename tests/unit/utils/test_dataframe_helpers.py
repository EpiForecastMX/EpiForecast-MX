# tests/unit/utils/test_dataframe_helpers.py
"""Unit tests for OperacionesDatos (src/epiforecast/utils/dataframe_helpers.py).

Tests cover:
- IQR statistics calculation with known values
- Outlier detection via IQR
- Behaviour on empty / all-NaN series
- Input validation (missing column, non-numeric column)
- Z-score outlier correction
"""

import numpy as np
import pandas as pd
import pytest

from epiforecast.utils.dataframe_helpers import OperacionesDatos

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def normal_df() -> pd.DataFrame:
    """DataFrame with one numeric column containing no outliers."""
    return pd.DataFrame({"valores": [10.0, 12.0, 11.0, 13.0, 9.0, 10.0, 12.0, 11.0]})


@pytest.fixture
def df_with_outlier() -> pd.DataFrame:
    """DataFrame whose 'valores' column has one clear high outlier (1000)."""
    return pd.DataFrame({"valores": [10.0, 12.0, 11.0, 13.0, 9.0, 10.0, 12.0, 1000.0]})


@pytest.fixture
def df_with_nan() -> pd.DataFrame:
    """DataFrame whose numeric column contains NaN values."""
    return pd.DataFrame({"valores": [10.0, np.nan, 12.0, np.nan, 11.0]})


# ── IQR statistics ─────────────────────────────────────────────────────────────


class TestIQRStatistics:
    """OperacionesDatos.iqr() returns correct quartile boundaries."""

    def test_returns_all_expected_keys(self, normal_df: pd.DataFrame):
        """Result dict must contain q1, q3, iqr, lim_inf, lim_sup."""
        result = OperacionesDatos.iqr(normal_df, "valores")
        assert set(result.keys()) == {"q1", "q3", "iqr", "lim_inf", "lim_sup"}

    def test_q1_less_than_q3(self, normal_df: pd.DataFrame):
        """Q1 must always be ≤ Q3 for non-trivial data."""
        result = OperacionesDatos.iqr(normal_df, "valores")
        assert result["q1"] <= result["q3"]

    def test_iqr_equals_q3_minus_q1(self, normal_df: pd.DataFrame):
        """IQR must equal Q3 - Q1."""
        result = OperacionesDatos.iqr(normal_df, "valores")
        assert result["iqr"] == pytest.approx(result["q3"] - result["q1"])

    def test_lim_inf_equals_q1_minus_factor_times_iqr(self, normal_df: pd.DataFrame):
        """Lower fence: Q1 - factor × IQR (default factor = 1.5)."""
        result = OperacionesDatos.iqr(normal_df, "valores", factor=1.5)
        expected = result["q1"] - 1.5 * result["iqr"]
        assert result["lim_inf"] == pytest.approx(expected)

    def test_lim_sup_equals_q3_plus_factor_times_iqr(self, normal_df: pd.DataFrame):
        """Upper fence: Q3 + factor × IQR."""
        result = OperacionesDatos.iqr(normal_df, "valores", factor=1.5)
        expected = result["q3"] + 1.5 * result["iqr"]
        assert result["lim_sup"] == pytest.approx(expected)

    def test_custom_factor_applied(self, normal_df: pd.DataFrame):
        """Changing factor must change lim_inf / lim_sup accordingly."""
        r1 = OperacionesDatos.iqr(normal_df, "valores", factor=1.5)
        r3 = OperacionesDatos.iqr(normal_df, "valores", factor=3.0)
        assert r3["lim_sup"] > r1["lim_sup"]
        assert r3["lim_inf"] < r1["lim_inf"]

    def test_all_nan_returns_nan_dict(self):
        """All-NaN column must return a dict of NaN values (not raise)."""
        df = pd.DataFrame({"valores": [np.nan, np.nan, np.nan]})
        result = OperacionesDatos.iqr(df, "valores")
        assert all(np.isnan(v) for v in result.values())

    def test_nan_values_ignored_in_calculation(self, df_with_nan: pd.DataFrame):
        """NaN entries must be dropped before computing quartiles."""
        result = OperacionesDatos.iqr(df_with_nan, "valores")
        # Valid values: 10, 12, 11 → no NaN in result
        assert not np.isnan(result["q1"])
        assert not np.isnan(result["q3"])


class TestIQRValidation:
    """OperacionesDatos.iqr() raises on invalid input."""

    def test_missing_column_raises_key_error(self, normal_df: pd.DataFrame):
        """Non-existent column name must raise KeyError."""
        with pytest.raises(KeyError):
            OperacionesDatos.iqr(normal_df, "columna_falsa")

    def test_non_numeric_column_raises_type_error(self):
        """String column must raise TypeError."""
        df = pd.DataFrame({"texto": ["a", "b", "c"]})
        with pytest.raises(TypeError):
            OperacionesDatos.iqr(df, "texto")


# ── Outlier detection ──────────────────────────────────────────────────────────


class TestOutliersIQR:
    """OperacionesDatos.outliers_iqr() detects rows outside IQR fences."""

    def test_detects_known_outlier(self, df_with_outlier: pd.DataFrame):
        """Row with value 1000 must be flagged as outlier."""
        df_out, _ = OperacionesDatos.outliers_iqr(df_with_outlier, "valores")
        assert len(df_out) == 1
        assert df_out.iloc[0]["valores"] == 1000.0

    def test_no_outliers_returns_empty(self, normal_df: pd.DataFrame):
        """Tight, evenly-distributed data should produce no outliers."""
        df_out, _ = OperacionesDatos.outliers_iqr(normal_df, "valores")
        assert df_out.empty

    def test_metadata_has_six_elements(self, df_with_outlier: pd.DataFrame):
        """Metadata list must always have 6 elements: lim_inf, lim_sup, q1, q3, iqr, col."""
        _, meta = OperacionesDatos.outliers_iqr(df_with_outlier, "valores")
        assert len(meta) == 6

    def test_metadata_last_element_is_column_name(self, df_with_outlier: pd.DataFrame):
        """Last metadata element must be the column name."""
        _, meta = OperacionesDatos.outliers_iqr(df_with_outlier, "valores")
        assert meta[-1] == "valores"

    def test_result_is_copy_not_view(self, df_with_outlier: pd.DataFrame):
        """Returned outlier DataFrame must be a copy — mutations do not propagate."""
        df_out, _ = OperacionesDatos.outliers_iqr(df_with_outlier, "valores")
        original_val = df_with_outlier.iloc[-1]["valores"]
        df_out.iloc[0, df_out.columns.get_loc("valores")] = -1
        assert df_with_outlier.iloc[-1]["valores"] == original_val

    def test_nan_not_flagged_as_outlier(self, df_with_nan: pd.DataFrame):
        """NaN values must not be treated as outliers."""
        df_out, _ = OperacionesDatos.outliers_iqr(df_with_nan, "valores")
        assert df_out.empty


# ── Z-score outlier correction ─────────────────────────────────────────────────


class TestZScore:
    """OperacionesDatos.zscore() replaces outliers based on Z-score."""

    @pytest.fixture
    def grouped_df(self) -> pd.DataFrame:
        """DataFrame with two groups; one outlier per group."""
        rng = np.random.default_rng(0)
        base = rng.integers(50, 150, size=20).tolist()
        base[5] = 9999  # outlier in group A
        base[15] = 9999  # outlier in group B
        groups = ["A"] * 10 + ["B"] * 10
        return pd.DataFrame({"Grupo": groups, "Valor": base})

    def test_outlier_replaced_with_mean(self, grouped_df: pd.DataFrame):
        """With reemplazo='media', extreme values must be replaced by group mean."""
        result = OperacionesDatos.zscore(
            grouped_df, "Valor", agrupacion=["Grupo"], umbral=2, reemplazo="media"
        )
        assert result["Valor"].max() < 9999

    def test_original_df_not_mutated(self, grouped_df: pd.DataFrame):
        """Input DataFrame must not be modified (zscore works on a copy)."""
        original_max = grouped_df["Valor"].max()
        OperacionesDatos.zscore(
            grouped_df, "Valor", agrupacion=["Grupo"], umbral=2, reemplazo="media"
        )
        assert grouped_df["Valor"].max() == original_max

    def test_zscore_columns_added(self, grouped_df: pd.DataFrame):
        """Result must include Zscore_ and Outlier_ helper columns."""
        result = OperacionesDatos.zscore(
            grouped_df, "Valor", agrupacion=["Grupo"], umbral=2, reemplazo="media"
        )
        assert "Zscore_Valor" in result.columns
        assert "Outlier_Valor" in result.columns

    def test_invalid_reemplazo_raises_value_error(self, grouped_df: pd.DataFrame):
        """Unsupported replacement strategy must raise ValueError."""
        with pytest.raises(ValueError):
            OperacionesDatos.zscore(
                grouped_df,
                "Valor",
                agrupacion=["Grupo"],
                reemplazo="invalido",
            )

    def test_mediana_replacement(self, grouped_df: pd.DataFrame):
        """With reemplazo='mediana', extreme values must be replaced by group median."""
        result = OperacionesDatos.zscore(
            grouped_df, "Valor", agrupacion=["Grupo"], umbral=2, reemplazo="mediana"
        )
        assert result["Valor"].max() < 9999

    def test_cercano_replacement(self, grouped_df: pd.DataFrame):
        """With reemplazo='cercano', values are clamped to the nearest IQR fence."""
        result = OperacionesDatos.zscore(
            grouped_df, "Valor", agrupacion=["Grupo"], umbral=2, reemplazo="cercano"
        )
        assert result["Valor"].max() < 9999
