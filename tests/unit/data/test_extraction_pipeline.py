"""Tests for extraction_pipeline.py — run_pipeline orchestration."""

from unittest.mock import MagicMock, patch

import pytest

import epiforecast.data.extraction.extraction_pipeline as ep_mod
from epiforecast.data.extraction.extraction_pipeline import run_pipeline


class TestInputValidation:
    def test_invalid_input_dir_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Input dir"):
            run_pipeline(
                input_dir=str(tmp_path / "nonexistent"),
                output_dir=str(tmp_path),
                keywords=["F32"],
            )

    def test_invalid_output_dir_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Output dir"):
            run_pipeline(
                input_dir=str(tmp_path),
                output_dir=str(tmp_path / "nonexistent"),
                keywords=["F32"],
            )

    def test_empty_keywords_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="KEYWORDS"):
            run_pipeline(
                input_dir=str(tmp_path),
                output_dir=str(out),
                keywords=[],
            )


class TestEmptyInputDir:
    def test_no_pdfs_no_csv_created(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        messages = []
        run_pipeline(
            input_dir=str(tmp_path),
            output_dir=str(out),
            keywords=["F32"],
            log_fn=messages.append,
        )
        assert not (out / "dataset_boletin_epidemiologico.csv").exists()

    def test_logs_pdf_count(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        messages = []
        run_pipeline(
            input_dir=str(tmp_path),
            output_dir=str(out),
            keywords=["F32"],
            log_fn=messages.append,
        )
        assert any("0" in m for m in messages)


class TestWithMockedPDF:
    def test_page_not_found_logged(self, tmp_path):
        # Create a fake PDF file
        pdf = tmp_path / "boletin_2024_01.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        out = tmp_path / "out"
        out.mkdir()

        messages = []

        with (
            patch.object(ep_mod, "find_page_and_week", return_value=(None, None, None)),
        ):
            run_pipeline(
                input_dir=str(tmp_path),
                output_dir=str(out),
                keywords=["F32"],
                log_fn=messages.append,
            )
        assert any("‼️" in m or "No se encontró" in m for m in messages)

    def test_on_file_callback_called(self, tmp_path):
        pdf = tmp_path / "boletin_2024_01.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        out = tmp_path / "out"
        out.mkdir()

        seen_files = []

        with (
            patch.object(ep_mod, "find_page_and_week", return_value=(None, None, None)),
        ):
            run_pipeline(
                input_dir=str(tmp_path),
                output_dir=str(out),
                keywords=["F32"],
                log_fn=lambda _: None,
                on_file=seen_files.append,
            )
        assert "boletin_2024_01.pdf" in seen_files

    def test_camelot_no_tables_skipped(self, tmp_path):
        pdf = tmp_path / "boletin_2024_01.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        out = tmp_path / "out"
        out.mkdir()

        mock_tables = MagicMock()
        mock_tables.n = 0

        messages = []

        with (
            patch.object(ep_mod, "find_page_and_week", return_value=(3, 2024, 1)),
            patch.object(ep_mod.camelot, "read_pdf", return_value=mock_tables),
        ):
            run_pipeline(
                input_dir=str(tmp_path),
                output_dir=str(out),
                keywords=["F32"],
                log_fn=messages.append,
            )
        assert not (out / "dataset_boletin_epidemiologico.csv").exists()

    def test_save_matched_pages_creates_dir(self, tmp_path):
        pdf = tmp_path / "boletin_2024_01.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        out = tmp_path / "out"
        out.mkdir()

        with (
            patch.object(ep_mod, "find_page_and_week", return_value=(None, None, None)),
        ):
            run_pipeline(
                input_dir=str(tmp_path),
                output_dir=str(out),
                keywords=["F32"],
                log_fn=lambda _: None,
                save_matched_pages=True,
            )
        assert (out / "pdf_matched_pages").is_dir()

    def test_save_individual_tables_creates_dir(self, tmp_path):
        pdf = tmp_path / "boletin_2024_01.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        out = tmp_path / "out"
        out.mkdir()

        with (
            patch.object(ep_mod, "find_page_and_week", return_value=(None, None, None)),
        ):
            run_pipeline(
                input_dir=str(tmp_path),
                output_dir=str(out),
                keywords=["F32"],
                log_fn=lambda _: None,
                save_individual_tables=True,
            )
        assert (out / "csv_tablas_individuales").is_dir()

    def test_exception_creates_failed_file(self, tmp_path):
        pdf = tmp_path / "boletin_error.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        out = tmp_path / "out"
        out.mkdir()

        with patch.object(ep_mod, "find_page_and_week", side_effect=RuntimeError("boom")):
            run_pipeline(
                input_dir=str(tmp_path),
                output_dir=str(out),
                keywords=["F32"],
                log_fn=lambda _: None,
            )
        assert (out / "failed_files.txt").exists()

    def test_successful_extraction_creates_csv(self, tmp_path):
        import pandas as pd

        pdf = tmp_path / "boletin_2024_01.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        out = tmp_path / "out"
        out.mkdir()

        # Build a mock clean df and long df
        mock_clean = pd.DataFrame(
            {
                0: ["Jalisco"] * 5,
                1: ["10"] * 5,
                2: ["5"] * 5,
                3: ["5"] * 5,
                4: ["9"] * 5,
            }
        )
        mock_long = pd.DataFrame(
            {
                "Anio": [2024] * 5,
                "Semana": ["01"] * 5,
                "Entidad": ["Jalisco"] * 5,
                "Padecimiento": ["F32"] * 5,
                "Casos_semana": [10] * 5,
                "Acumulado_hombres": [5] * 5,
                "Acumulado_mujeres": [5] * 5,
                "Acumulado_anio_anterior": [9] * 5,
            }
        )

        mock_table = MagicMock()
        mock_table.df = mock_clean
        mock_tables = MagicMock()
        mock_tables.n = 1
        mock_tables.__getitem__ = MagicMock(return_value=mock_table)

        with (
            patch.object(ep_mod, "find_page_and_week", return_value=(3, 2024, 1)),
            patch.object(ep_mod.camelot, "read_pdf", return_value=mock_tables),
            patch.object(ep_mod, "clean_df", return_value=mock_clean),
            patch.object(ep_mod, "pad_prev_year_cols", return_value=mock_clean),
            patch.object(ep_mod, "reshape", return_value=mock_long),
        ):
            run_pipeline(
                input_dir=str(tmp_path),
                output_dir=str(out),
                keywords=["F32"],
                log_fn=lambda _: None,
            )
        assert (out / "dataset_boletin_epidemiologico.csv").exists()
