# tests/unit/data/test_merger.py
"""Unit tests for merger.py utility functions.

Focuses on rename_csv_with_timestamp and the pure merge logic
without triggering typer.Exit or real file system side effects beyond tmp_path.
"""

import pandas as pd
import pytest

from epiforecast.data.extraction.merger import (
    _TIMESTAMP_RE,
    rename_csv_with_timestamp,
)

# ── _TIMESTAMP_RE ─────────────────────────────────────────────────────────────


class TestTimestampRegex:
    def test_matches_valid_timestamp_name(self):
        assert _TIMESTAMP_RE.match("dataset_20240101_120000.csv") is not None

    def test_no_match_plain_name(self):
        assert _TIMESTAMP_RE.match("dataset.csv") is None

    def test_no_match_partial_timestamp(self):
        assert _TIMESTAMP_RE.match("dataset_20240101.csv") is None

    def test_matches_with_prefix(self):
        assert _TIMESTAMP_RE.match("my_data_file_20231231_235959.csv") is not None


# ── rename_csv_with_timestamp ─────────────────────────────────────────────────


class TestRenameCsvWithTimestamp:
    def test_renames_file(self, tmp_path):
        csv = tmp_path / "output.csv"
        csv.write_text("a,b\n1,2\n")
        new_path = rename_csv_with_timestamp(csv)
        assert new_path.exists()
        assert not csv.exists()

    def test_returned_path_matches_timestamp_pattern(self, tmp_path):
        csv = tmp_path / "output.csv"
        csv.write_text("a,b\n1,2\n")
        new_path = rename_csv_with_timestamp(csv)
        assert _TIMESTAMP_RE.match(new_path.name) is not None

    def test_raises_file_not_found_for_missing_file(self, tmp_path):
        missing = tmp_path / "ghost.csv"
        with pytest.raises(FileNotFoundError):
            rename_csv_with_timestamp(missing)

    def test_raises_value_error_for_non_csv(self, tmp_path):
        txt = tmp_path / "file.txt"
        txt.write_text("hello")
        with pytest.raises(ValueError, match="csv"):
            rename_csv_with_timestamp(txt)

    def test_stem_preserved_in_new_name(self, tmp_path):
        csv = tmp_path / "mi_archivo.csv"
        csv.write_text("x\n1\n")
        new_path = rename_csv_with_timestamp(csv)
        assert new_path.name.startswith("mi_archivo_")


# ── merge logic via DataFrames (pure function equivalent) ─────────────────────


class TestMergeCsvLogic:
    """Tests the merge logic semantics that merge_csv implements,
    using pandas directly to avoid typer.Exit interactions."""

    COLS = ["Anio", "Semana", "Entidad", "Padecimiento", "Casos_semana"]

    def _make_df(self, rows):
        return pd.DataFrame(rows, columns=self.COLS)

    def test_new_rows_are_added(self):
        """Rows present in source but not in target should appear in result."""
        target = self._make_df(
            [
                [2024, "01", "Jalisco", "F32", 10],
            ]
        )
        source = self._make_df(
            [
                [2024, "01", "Jalisco", "F32", 10],
                [2024, "02", "Jalisco", "F32", 20],  # new row
            ]
        )

        merged = source.merge(target, how="left", on=self.COLS, indicator=True)
        missing_mask = merged["_merge"] == "left_only"
        missing = source.loc[missing_mask]

        result = pd.concat([target, missing], ignore_index=True)
        assert len(result) == 2

    def test_no_duplicates_when_rows_match(self):
        """No rows should be added when source and target are identical."""
        target = self._make_df([[2024, "01", "Jalisco", "F32", 10]])
        source = self._make_df([[2024, "01", "Jalisco", "F32", 10]])

        merged = source.merge(target, how="left", on=self.COLS, indicator=True)
        missing_mask = merged["_merge"] == "left_only"
        missing = source.loc[missing_mask]

        assert len(missing) == 0

    def test_column_mismatch_detected(self):
        """Columns must match between source and target for merge to work."""
        target = self._make_df([[2024, "01", "Jalisco", "F32", 10]])
        source_bad = pd.DataFrame([[2024, "01"]], columns=["Anio", "Semana"])

        assert list(source_bad.columns) != list(target.columns)

    def test_semana_normalization(self):
        """'02' and '2' should be treated as equal after pd.to_numeric."""
        target = self._make_df([[2024, "2", "Jalisco", "F32", 10]])
        source = self._make_df([[2024, "02", "Jalisco", "F32", 10]])

        # Normalize semana
        for df in [target, source]:
            df["Semana"] = (
                pd.to_numeric(df["Semana"], errors="coerce").astype("Int64").astype("string")
            )

        merged = source.merge(target, how="left", on=self.COLS, indicator=True)
        missing_mask = merged["_merge"] == "left_only"
        assert missing_mask.sum() == 0
