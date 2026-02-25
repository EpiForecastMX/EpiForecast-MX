# tests/unit/data/test_pdf_extractor.py
"""Unit tests for pure data-transformation functions in pdf_extractor.py.

Does NOT test PDF parsing (find_page_and_week, extract_matched_page, run_pipeline)
because those require real PDF files and Camelot/Ghostscript.
"""

import pandas as pd

from epiforecast.data.extraction.pdf_extractor import (
    build_column_map,
    clean_df,
    eliminar_columnas_vacias,
    normalize_number,
    pad_prev_year_cols,
    print_run_summary,
    reshape,
    reshape_wide,
)

# ── build_column_map ──────────────────────────────────────────────────────────


class TestBuildColumnMap:
    def test_single_keyword_default_params(self):
        result = build_column_map(["F32"])
        assert "F32" in result
        assert result["F32"]["total"] == 1
        assert result["F32"]["hombres"] == 2
        assert result["F32"]["mujeres"] == 3
        assert result["F32"]["total_prev"] == 4

    def test_three_keywords_sequential(self):
        kws = ["F32", "G20", "G30"]
        result = build_column_map(kws)
        assert result["F32"]["total"] == 1
        assert result["G20"]["total"] == 5
        assert result["G30"]["total"] == 9

    def test_custom_start_col(self):
        result = build_column_map(["A"], start_col=10)
        assert result["A"]["total"] == 10

    def test_custom_step(self):
        result = build_column_map(["A", "B"], step=3)
        assert result["A"]["total"] == 1
        assert result["B"]["total"] == 4


# ── normalize_number ──────────────────────────────────────────────────────────


class TestNormalizeNumber:
    def test_integer_string(self):
        assert normalize_number("42") == 42

    def test_integer_with_comma(self):
        assert normalize_number("1,450") == 1450

    def test_integer_with_space(self):
        assert normalize_number("1 450") == 1450

    def test_dash_returns_zero(self):
        assert normalize_number("-") == 0

    def test_empty_string_returns_zero(self):
        assert normalize_number("") == 0

    def test_nan_returns_na(self):
        import pandas as pd

        assert pd.isna(normalize_number(pd.NA))

    def test_text_returns_na(self):
        import pandas as pd

        result = normalize_number("n.e.")
        assert pd.isna(result)

    def test_zero_string(self):
        assert normalize_number("0") == 0

    def test_large_number(self):
        assert normalize_number("1,000,000") == 1000000


# ── eliminar_columnas_vacias ──────────────────────────────────────────────────


class TestEliminarColumnasVacias:
    def _make_df(self):
        """DataFrame with Aguascalientes..Zacatecas range and an empty middle column."""
        data = {
            0: ["Aguascalientes", "Jalisco", "Zacatecas"],
            1: ["10", "20", "30"],
            2: ["", "", ""],  # fully blank column
            3: ["100", "200", "300"],
        }
        return pd.DataFrame(data)

    def test_removes_blank_columns(self):
        df = self._make_df()
        result = eliminar_columnas_vacias(df)
        # Column index 2 was blank; should be dropped
        assert result.shape[1] == 3

    def test_handles_missing_state_names(self):
        """If start/end state not found, return df unchanged."""
        df = pd.DataFrame({0: ["Estado1", "Estado2"], 1: ["10", "20"]})
        result = eliminar_columnas_vacias(df)
        assert result.shape == df.shape

    def test_no_blank_columns_unchanged(self):
        data = {
            0: ["Aguascalientes", "Jalisco", "Zacatecas"],
            1: ["10", "20", "30"],
            2: ["100", "200", "300"],
        }
        df = pd.DataFrame(data)
        result = eliminar_columnas_vacias(df)
        assert result.shape[1] == 3


# ── pad_prev_year_cols ────────────────────────────────────────────────────────


class TestPadPrevYearCols:
    def test_adds_na_column_when_no_prev(self):
        keywords = ["F32"]
        # 1 + 3*1 = 4 columns (no prev-year)
        df = pd.DataFrame([[str(i) for i in range(4)]])
        result = pad_prev_year_cols(df, keywords)
        # After padding: 1 + 4*1 = 5 columns
        assert result.shape[1] == 5

    def test_noop_when_correct_width(self):
        keywords = ["F32"]
        # 1 + 4*1 = 5 columns (already has prev-year)
        df = pd.DataFrame([[str(i) for i in range(5)]])
        result = pad_prev_year_cols(df, keywords)
        assert result.shape[1] == 5  # unchanged

    def test_na_in_prev_column(self):
        keywords = ["F32"]
        df = pd.DataFrame([[str(i) for i in range(4)]])
        result = pad_prev_year_cols(df, keywords)
        # Column index 4 (new_base + 3) should be NA
        assert pd.isna(result.iloc[0, 4])

    def test_two_keywords(self):
        keywords = ["F32", "G20"]
        # 1 + 3*2 = 7 columns
        df = pd.DataFrame([[str(i) for i in range(7)]])
        result = pad_prev_year_cols(df, keywords)
        # 1 + 4*2 = 9 columns
        assert result.shape[1] == 9


# ── clean_df ──────────────────────────────────────────────────────────────────


class TestCleanDf:
    def _sample_df(self):
        """Simulates raw camelot output with header junk and state data."""
        data = {
            0: [
                "ENTIDAD FEDERATIVA",
                "Aguascalientes",
                "",
                "Jalisco",
                "TOTAL NACIONAL",
                "Zacatecas",
            ],
            1: ["Total", "10", "", "20", "30", "15"],
            2: ["Hombres", "5", "", "10", "15", "8"],
        }
        return pd.DataFrame(data)

    def test_removes_header_rows(self):
        df = self._sample_df()
        result = clean_df(df)
        assert not any(result[0].str.match(r"^ENTIDAD", case=False))

    def test_removes_empty_first_col(self):
        df = self._sample_df()
        result = clean_df(df)
        assert "" not in result[0].values

    def test_removes_total_rows(self):
        df = self._sample_df()
        result = clean_df(df)
        assert not any(result[0].str.upper().str.startswith("TOTAL"))

    def test_keeps_valid_state_rows(self):
        df = self._sample_df()
        result = clean_df(df)
        assert "Aguascalientes" in result[0].values


# ── reshape ───────────────────────────────────────────────────────────────────


class TestReshape:
    def _make_clean_df(self):
        """Minimal 2-row df with 1 keyword, 4 data columns."""
        data = {
            0: ["Aguascalientes", "Jalisco"],
            1: ["10", "20"],  # total
            2: ["6", "12"],  # hombres
            3: ["4", "8"],  # mujeres
            4: ["9", "18"],  # prev year
        }
        return pd.DataFrame(data)

    def test_output_has_expected_columns(self):
        df = self._make_clean_df()
        col_map = build_column_map(["F32"])
        result = reshape(df, 2024, 5, col_map)
        expected_cols = {
            "Anio",
            "Semana",
            "Entidad",
            "Padecimiento",
            "Casos_semana",
            "Acumulado_hombres",
            "Acumulado_mujeres",
            "Acumulado_anio_anterior",
        }
        assert expected_cols == set(result.columns)

    def test_one_row_per_keyword_per_state(self):
        df = self._make_clean_df()
        col_map = build_column_map(["F32", "G20"], start_col=1, step=4)
        # 2-col df won't have G20 data, but col_map tries to access those columns
        # Use single keyword for this test
        col_map = build_column_map(["F32"])
        result = reshape(df, 2024, 5, col_map)
        assert len(result) == 2  # 2 states × 1 keyword

    def test_semana_zero_padded(self):
        df = self._make_clean_df()
        col_map = build_column_map(["F32"])
        result = reshape(df, 2024, 5, col_map)
        assert result["Semana"].iloc[0] == "05"

    def test_year_assigned(self):
        df = self._make_clean_df()
        col_map = build_column_map(["F32"])
        result = reshape(df, 2024, 1, col_map)
        assert (result["Anio"] == 2024).all()


# ── reshape_wide ──────────────────────────────────────────────────────────────


class TestReshapeWide:
    def _make_clean_df(self):
        data = {
            0: ["Aguascalientes", "Jalisco"],
            1: ["10", "20"],
            2: ["6", "12"],
            3: ["4", "8"],
            4: ["9", "18"],
        }
        return pd.DataFrame(data)

    def test_output_one_row_per_state(self):
        df = self._make_clean_df()
        col_map = build_column_map(["F32"])
        result = reshape_wide(df, 2024, 3, col_map)
        assert len(result) == 2

    def test_output_has_wide_columns(self):
        df = self._make_clean_df()
        col_map = build_column_map(["F32"])
        result = reshape_wide(df, 2024, 3, col_map)
        assert "Casos_semana_F32" in result.columns
        assert "Acumulado_hombres_F32" in result.columns


# ── print_run_summary ─────────────────────────────────────────────────────────


class TestPrintRunSummary:
    def test_runs_without_error(self):
        log_lines = []
        run_log = [
            {"file": "boletin1.pdf", "year": 2024, "week": 5, "page": 3, "rows": 32},
            {"file": "boletin2.pdf", "year": None, "week": None, "page": None, "rows": None},
        ]
        print_run_summary(run_log, log_fn=log_lines.append)
        assert len(log_lines) > 0

    def test_reports_success_percentage(self):
        log_lines = []
        run_log = [
            {"file": "a.pdf", "year": 2024, "week": 1, "page": 2, "rows": 32},
            {"file": "b.pdf", "year": 2024, "week": 2, "page": 3, "rows": 30},
        ]
        print_run_summary(run_log, log_fn=log_lines.append)
        summary = "\n".join(log_lines)
        # 1 of 2 files has exactly 32 rows → 50%
        assert "50.0%" in summary

    def test_empty_run_log(self):
        log_lines = []
        print_run_summary([], log_fn=log_lines.append)
        assert any("0/0" in line or "0.0%" in line for line in log_lines)
