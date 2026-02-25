# tests/unit/data/test_filter.py
"""Unit tests for FiltraPadecimiento (src/epiforecast/data/preprocessing/filter.py).

FiltraPadecimiento takes a DataFrame and a config dict with 'columna' and 'tipo'
and returns only rows whose 'columna' value contains 'tipo' (case-insensitive).
No YAML config is required — all configuration is passed in explicitly.
"""

import pandas as pd
import pytest

from epiforecast.data.preprocessing.filter import FiltraPadecimiento

# ── Shared fixture ────────────────────────────────────────────────────────────


@pytest.fixture
def mixed_df() -> pd.DataFrame:
    """DataFrame with three different padecimientos for filter testing."""
    return pd.DataFrame(
        {
            "Padecimiento": [
                "Depresión",
                "Depresión",
                "Parkinson",
                "Alzheimer",
                "Depresión",
            ],
            "Entidad": ["Jalisco", "Oaxaca", "Jalisco", "Oaxaca", "Puebla"],
            "Casos": [10, 15, 5, 3, 8],
        }
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestFiltraPadecimientoBasic:
    """Basic filtering behaviour."""

    def test_filters_to_matching_rows_only(self, mixed_df: pd.DataFrame):
        """Only rows whose Padecimiento contains 'Depresión' are returned."""
        filtro = FiltraPadecimiento(mixed_df, {"columna": "Padecimiento", "tipo": "Depresión"})
        result = filtro.run()

        assert result is not None
        assert len(result) == 3
        assert result["Padecimiento"].unique().tolist() == ["Depresión"]

    def test_filter_is_case_insensitive(self, mixed_df: pd.DataFrame):
        """Matching must work regardless of case in the filter value."""
        filtro = FiltraPadecimiento(mixed_df, {"columna": "Padecimiento", "tipo": "depresión"})
        result = filtro.run()

        assert result is not None
        assert len(result) == 3

    def test_general_returns_all_rows(self, mixed_df: pd.DataFrame):
        """'General' is a special value that bypasses filtering."""
        filtro = FiltraPadecimiento(mixed_df, {"columna": "Padecimiento", "tipo": "General"})
        result = filtro.run()

        assert result is not None
        assert len(result) == len(mixed_df)

    def test_filter_parkinson(self, mixed_df: pd.DataFrame):
        """Filter for Parkinson returns only its single row."""
        filtro = FiltraPadecimiento(mixed_df, {"columna": "Padecimiento", "tipo": "Parkinson"})
        result = filtro.run()

        assert result is not None
        assert len(result) == 1
        assert result.iloc[0]["Padecimiento"] == "Parkinson"


class TestFiltraPadecimientoEdgeCases:
    """Edge cases: missing code, empty df, missing column."""

    def test_nonexistent_code_returns_none(self, mixed_df: pd.DataFrame):
        """Code not present in the data must return None (0 matches)."""
        filtro = FiltraPadecimiento(mixed_df, {"columna": "Padecimiento", "tipo": "Esquizofrenia"})
        result = filtro.run()

        assert result is None

    def test_empty_dataframe_returns_none(self):
        """Empty input DataFrame must return None."""
        filtro = FiltraPadecimiento(
            pd.DataFrame({"Padecimiento": [], "Casos": []}),
            {"columna": "Padecimiento", "tipo": "Depresión"},
        )
        result = filtro.run()

        assert result is None

    def test_missing_column_returns_none(self, mixed_df: pd.DataFrame):
        """Non-existent column name must return None."""
        filtro = FiltraPadecimiento(
            mixed_df, {"columna": "ColumnaInexistente", "tipo": "Depresión"}
        )
        result = filtro.run()

        assert result is None

    def test_none_tipo_returns_none(self, mixed_df: pd.DataFrame):
        """Undefined (None) 'tipo' must return None."""
        filtro = FiltraPadecimiento(mixed_df, {"columna": "Padecimiento", "tipo": None})
        result = filtro.run()

        assert result is None


class TestFiltraPadecimientoNoSideEffects:
    """The original DataFrame must never be mutated."""

    def test_original_df_unchanged_after_filter(self, mixed_df: pd.DataFrame):
        """Input DataFrame must be identical before and after run()."""
        original_shape = mixed_df.shape
        original_values = mixed_df.copy()

        FiltraPadecimiento(mixed_df, {"columna": "Padecimiento", "tipo": "Depresión"}).run()

        assert mixed_df.shape == original_shape
        pd.testing.assert_frame_equal(mixed_df, original_values)

    def test_result_is_independent_copy(self, mixed_df: pd.DataFrame):
        """Mutating the result must not affect the original DataFrame."""
        filtro = FiltraPadecimiento(mixed_df, {"columna": "Padecimiento", "tipo": "Depresión"})
        result = filtro.run()

        assert result is not None
        result["Casos"] = 0  # mutate result

        # original must be unchanged
        assert (mixed_df["Casos"] != 0).any()
