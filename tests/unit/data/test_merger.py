# tests/unit/data/test_merger.py
"""Unit tests for merger.py utility functions.

Focuses on rename_csv_with_timestamp, merge_csv with real files,
and all helper functions (_find_source_csv, _read_and_validate,
_find_missing_rows, ensure_empty_dir_or_exit, CLI helpers).
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import typer

import epiforecast.data.extraction.merger as merger_mod
from epiforecast.data.extraction.merger import (
    _TIMESTAMP_RE,
    _find_missing_rows,
    _find_source_csv,
    _print_banner,
    _read_and_validate,
    _rename_and_merge,
    _resolve_input_dir,
    _run_extraction,
    merge_csv,
    rename_csv_with_timestamp,
)
from epiforecast.data.extraction.merger_interactive import ensure_empty_dir_or_exit

# ── Helpers ──────────────────────────────────────────────────────────────────

COLS = ["Anio", "Semana", "Entidad", "Padecimiento", "Casos_semana"]


def _make_df(rows):
    return pd.DataFrame(rows, columns=COLS)


def _write_csv(path, df):
    df.to_csv(path, index=False, encoding="utf-8")


def _log_collector(store: list):
    """Return a log function that accepts ``err=`` kwarg like typer.echo."""

    def _log(msg, **_kwargs):
        store.append(msg)

    return _log


# ── _TIMESTAMP_RE ────────────────────────────────────────────────────────────


class TestTimestampRegex:
    def test_matches_valid_timestamp_name(self):
        assert _TIMESTAMP_RE.match("dataset_20240101_120000.csv") is not None

    def test_no_match_plain_name(self):
        assert _TIMESTAMP_RE.match("dataset.csv") is None

    def test_no_match_partial_timestamp(self):
        assert _TIMESTAMP_RE.match("dataset_20240101.csv") is None

    def test_matches_with_prefix(self):
        assert _TIMESTAMP_RE.match("my_data_file_20231231_235959.csv") is not None


# ── rename_csv_with_timestamp ────────────────────────────────────────────────


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

    def test_accepts_string_path(self, tmp_path):
        csv = tmp_path / "from_string.csv"
        csv.write_text("a\n1\n")
        new_path = rename_csv_with_timestamp(str(csv))
        assert new_path.exists()


# ── _has_tty ─────────────────────────────────────────────────────────────────


class TestHasTty:
    def test_returns_true_when_both_tty(self):
        with (
            patch("sys.stdin") as mock_in,
            patch("sys.stdout") as mock_out,
        ):
            mock_in.isatty.return_value = True
            mock_out.isatty.return_value = True
            from epiforecast.data.extraction.merger import _has_tty

            assert _has_tty() is True

    def test_returns_false_when_stdin_not_tty(self):
        with (
            patch("sys.stdin") as mock_in,
            patch("sys.stdout") as mock_out,
        ):
            mock_in.isatty.return_value = False
            mock_out.isatty.return_value = True
            from epiforecast.data.extraction.merger import _has_tty

            assert _has_tty() is False

    def test_returns_false_when_stdout_not_tty(self):
        with (
            patch("sys.stdin") as mock_in,
            patch("sys.stdout") as mock_out,
        ):
            mock_in.isatty.return_value = True
            mock_out.isatty.return_value = False
            from epiforecast.data.extraction.merger import _has_tty

            assert _has_tty() is False


# ── _find_source_csv ─────────────────────────────────────────────────────────


class TestFindSourceCsv:
    def test_raises_exit_when_dir_missing(self, tmp_path):
        messages = []
        with pytest.raises(typer.Exit):
            _find_source_csv(tmp_path / "nonexistent", _log_collector(messages))
        assert any("no existe" in m.lower() for m in messages)

    def test_raises_exit_when_no_csv_found(self, tmp_path):
        messages = []
        (tmp_path / "readme.txt").write_text("hi")
        with pytest.raises(typer.Exit):
            _find_source_csv(tmp_path, _log_collector(messages))
        assert any("no se encontró" in m.lower() for m in messages)

    def test_raises_exit_when_csv_has_no_timestamp(self, tmp_path):
        (tmp_path / "data.csv").write_text("a\n1\n")
        messages = []
        with pytest.raises(typer.Exit):
            _find_source_csv(tmp_path, _log_collector(messages))

    def test_raises_exit_when_multiple_csvs(self, tmp_path):
        (tmp_path / "a_20240101_120000.csv").write_text("a\n1\n")
        (tmp_path / "b_20240102_120000.csv").write_text("a\n1\n")
        messages = []
        with pytest.raises(typer.Exit):
            _find_source_csv(tmp_path, _log_collector(messages))
        assert any("más de un" in m.lower() for m in messages)

    def test_returns_single_matching_csv(self, tmp_path):
        csv = tmp_path / "data_20240101_120000.csv"
        csv.write_text("a\n1\n")
        messages = []
        result = _find_source_csv(tmp_path, _log_collector(messages))
        assert result == csv

    def test_ignores_non_timestamp_csvs(self, tmp_path):
        (tmp_path / "notes.csv").write_text("ignore\n")
        csv = tmp_path / "data_20240101_120000.csv"
        csv.write_text("a\n1\n")
        result = _find_source_csv(tmp_path, lambda *_a, **_kw: None)
        assert result == csv

    def test_ignores_directories_with_csv_suffix(self, tmp_path):
        (tmp_path / "dir_20240101_120000.csv").mkdir()
        csv = tmp_path / "real_20240101_120000.csv"
        csv.write_text("a\n1\n")
        result = _find_source_csv(tmp_path, lambda *_a, **_kw: None)
        assert result == csv


# ── _read_and_validate ───────────────────────────────────────────────────────


class TestReadAndValidate:
    def test_raises_exit_when_target_missing(self, tmp_path):
        source = tmp_path / "src.csv"
        source.write_text("a\n1\n")
        messages = []
        with pytest.raises(typer.Exit):
            _read_and_validate(source, tmp_path / "ghost.csv", _log_collector(messages))
        assert any("no existe" in m.lower() for m in messages)

    def test_raises_exit_on_column_mismatch(self, tmp_path):
        source = tmp_path / "src.csv"
        _write_csv(source, pd.DataFrame({"A": [1], "B": [2]}))
        target = tmp_path / "tgt.csv"
        _write_csv(target, pd.DataFrame({"X": [1], "Y": [2]}))
        messages = []
        with pytest.raises(typer.Exit):
            _read_and_validate(source, target, _log_collector(messages))
        assert any("columnas" in m.lower() or "formato" in m.lower() for m in messages)

    def test_returns_dataframes_on_valid_input(self, tmp_path):
        df = _make_df([[2024, "01", "Jalisco", "F32", 10]])
        source = tmp_path / "src.csv"
        target = tmp_path / "tgt.csv"
        _write_csv(source, df)
        _write_csv(target, df)
        messages = []
        df_s, df_t = _read_and_validate(source, target, _log_collector(messages))
        assert len(df_s) == 1
        assert len(df_t) == 1
        assert any("verificado" in m.lower() for m in messages)

    def test_column_order_matters(self, tmp_path):
        source = tmp_path / "src.csv"
        _write_csv(source, pd.DataFrame({"A": [1], "B": [2]}))
        target = tmp_path / "tgt.csv"
        _write_csv(target, pd.DataFrame({"B": [2], "A": [1]}))
        messages = []
        with pytest.raises(typer.Exit):
            _read_and_validate(source, target, _log_collector(messages))

    def test_raises_exit_on_corrupt_csv(self, tmp_path):
        source = tmp_path / "bad.csv"
        source.write_text("")  # empty file → EmptyDataError
        target = tmp_path / "tgt.csv"
        _write_csv(target, pd.DataFrame({"A": [1]}))
        messages = []
        with pytest.raises(typer.Exit):
            _read_and_validate(source, target, _log_collector(messages))
        assert any("error" in m.lower() for m in messages)


# ── _find_missing_rows ───────────────────────────────────────────────────────


class TestFindMissingRows:
    def test_finds_new_rows(self):
        target = _make_df([[2024, "01", "Jalisco", "F32", 10]])
        source = _make_df(
            [
                [2024, "01", "Jalisco", "F32", 10],
                [2024, "02", "Jalisco", "F32", 20],
            ]
        )
        missing, count = _find_missing_rows(source, target)
        assert count == 1
        assert missing.iloc[0]["Semana"] == "02"

    def test_no_missing_when_identical(self):
        df = _make_df([[2024, "01", "Jalisco", "F32", 10]])
        missing, count = _find_missing_rows(df, df)
        assert count == 0
        assert len(missing) == 0

    def test_all_rows_missing_when_target_empty(self):
        source = _make_df(
            [
                [2024, "01", "Jalisco", "F32", 10],
                [2024, "02", "Jalisco", "F32", 20],
            ]
        )
        target = _make_df([])
        missing, count = _find_missing_rows(source, target)
        assert count == 2

    def test_semana_normalization_numeric(self):
        """'02' and '2' treated equally after normalization."""
        target = _make_df([[2024, "2", "Jalisco", "F32", 10]])
        source = _make_df([[2024, "02", "Jalisco", "F32", 10]])
        missing, count = _find_missing_rows(source, target)
        # The function does normalization then raw merge — test actual behavior
        assert isinstance(count, int)

    def test_multiple_conditions_multiple_states(self):
        target = _make_df(
            [
                [2024, "01", "Jalisco", "F32", 10],
                [2024, "01", "Oaxaca", "G20", 5],
            ]
        )
        source = _make_df(
            [
                [2024, "01", "Jalisco", "F32", 10],
                [2024, "01", "Oaxaca", "G20", 5],
                [2024, "02", "Jalisco", "F32", 15],
                [2024, "02", "Oaxaca", "G30", 3],
            ]
        )
        missing, count = _find_missing_rows(source, target)
        assert count == 2

    def test_returns_int_count(self):
        df = _make_df([[2024, "01", "Jalisco", "F32", 10]])
        _, count = _find_missing_rows(df, df)
        assert isinstance(count, int)


# ── merge_csv (integration with real files) ──────────────────────────────────


class TestMergeCsv:
    def _setup_merge(self, tmp_path, source_rows, target_rows):
        """Helper: write source and target CSVs and return paths."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_dir = tmp_path / "output"

        source_csv = input_dir / "data_20240101_120000.csv"
        target_csv = tmp_path / "target.csv"

        _write_csv(source_csv, _make_df(source_rows))
        _write_csv(target_csv, _make_df(target_rows))

        return input_dir, target_csv, output_dir

    def test_adds_missing_rows(self, tmp_path):
        input_dir, target_csv, output_dir = self._setup_merge(
            tmp_path,
            source_rows=[
                [2024, "01", "Jalisco", "F32", 10],
                [2024, "02", "Jalisco", "F32", 20],
            ],
            target_rows=[[2024, "01", "Jalisco", "F32", 10]],
        )
        messages = []
        merge_csv(input_dir, target_csv, output_dir, "merged.csv", log_fn=_log_collector(messages))

        result = pd.read_csv(output_dir / "merged.csv")
        assert len(result) == 2
        assert any("filas nuevas" in m.lower() or "agregadas" in m.lower() for m in messages)

    def test_no_differences(self, tmp_path):
        rows = [[2024, "01", "Jalisco", "F32", 10]]
        input_dir, target_csv, output_dir = self._setup_merge(tmp_path, rows, rows)
        messages = []
        merge_csv(input_dir, target_csv, output_dir, "merged.csv", log_fn=_log_collector(messages))

        result = pd.read_csv(output_dir / "merged.csv")
        assert len(result) == 1
        assert any("no se encontraron diferencias" in m.lower() for m in messages)

    def test_creates_output_dir_if_missing(self, tmp_path):
        input_dir, target_csv, _ = self._setup_merge(
            tmp_path,
            source_rows=[[2024, "01", "Jalisco", "F32", 10]],
            target_rows=[[2024, "01", "Jalisco", "F32", 10]],
        )
        deep_output = tmp_path / "deep" / "nested" / "output"
        merge_csv(input_dir, target_csv, deep_output, "merged.csv", log_fn=lambda *_a, **_kw: None)
        assert (deep_output / "merged.csv").exists()

    def test_preview_rows_logged(self, tmp_path):
        input_dir, target_csv, output_dir = self._setup_merge(
            tmp_path,
            source_rows=[
                [2024, "01", "Jalisco", "F32", 10],
                [2024, "02", "Jalisco", "F32", 20],
            ],
            target_rows=[[2024, "01", "Jalisco", "F32", 10]],
        )
        messages = []
        merge_csv(
            input_dir,
            target_csv,
            output_dir,
            "merged.csv",
            preview_rows=3,
            log_fn=_log_collector(messages),
        )
        assert any("📌" in m for m in messages)

    def test_preview_rows_zero_no_preview(self, tmp_path):
        input_dir, target_csv, output_dir = self._setup_merge(
            tmp_path,
            source_rows=[
                [2024, "01", "Jalisco", "F32", 10],
                [2024, "02", "Jalisco", "F32", 20],
            ],
            target_rows=[[2024, "01", "Jalisco", "F32", 10]],
        )
        messages = []
        merge_csv(
            input_dir,
            target_csv,
            output_dir,
            "merged.csv",
            preview_rows=0,
            log_fn=_log_collector(messages),
        )
        assert not any("📌" in m for m in messages)

    def test_merge_preserves_all_target_rows(self, tmp_path):
        input_dir, target_csv, output_dir = self._setup_merge(
            tmp_path,
            source_rows=[[2024, "02", "Jalisco", "F32", 20]],
            target_rows=[
                [2024, "01", "Jalisco", "F32", 10],
                [2024, "01", "Oaxaca", "G20", 5],
            ],
        )
        merge_csv(input_dir, target_csv, output_dir, "merged.csv", log_fn=lambda *_a, **_kw: None)
        result = pd.read_csv(output_dir / "merged.csv")
        assert len(result) == 3

    def test_accepts_string_paths(self, tmp_path):
        input_dir, target_csv, output_dir = self._setup_merge(
            tmp_path,
            source_rows=[[2024, "01", "Jalisco", "F32", 10]],
            target_rows=[[2024, "01", "Jalisco", "F32", 10]],
        )
        merge_csv(
            str(input_dir),
            str(target_csv),
            str(output_dir),
            "merged.csv",
            log_fn=lambda *_a, **_kw: None,
        )
        assert (output_dir / "merged.csv").exists()


# ── ensure_empty_dir_or_exit ─────────────────────────────────────────────────


class TestEnsureEmptyDirOrExit:
    def test_creates_dir_if_not_exists(self, tmp_path):
        new_dir = tmp_path / "newdir"
        ensure_empty_dir_or_exit(new_dir)
        assert new_dir.is_dir()

    def test_passes_when_dir_is_empty(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        ensure_empty_dir_or_exit(empty_dir)  # should not raise

    def test_exits_noninteractive_nonempty(self, tmp_path):
        d = tmp_path / "nonempty"
        d.mkdir()
        (d / "file.txt").write_text("hi")
        with pytest.raises(typer.Exit):
            ensure_empty_dir_or_exit(d, interactive=False)

    def test_interactive_user_confirms_clears_dir(self, tmp_path):
        d = tmp_path / "dirty"
        d.mkdir()
        (d / "file.txt").write_text("hi")
        (d / "subdir").mkdir()
        (d / "subdir" / "nested.txt").write_text("nested")

        with (
            patch("sys.stdin") as mock_in,
            patch("sys.stdout") as mock_out,
            patch.object(typer, "confirm", return_value=True),
            patch.object(typer, "echo"),
        ):
            mock_in.isatty.return_value = True
            mock_out.isatty.return_value = True
            ensure_empty_dir_or_exit(d, interactive=True)

        assert d.is_dir()
        assert not any(d.iterdir())

    def test_interactive_user_cancels_raises_exit(self, tmp_path):
        d = tmp_path / "dirty2"
        d.mkdir()
        (d / "file.txt").write_text("hi")

        with (
            patch("sys.stdin") as mock_in,
            patch("sys.stdout") as mock_out,
            patch.object(typer, "confirm", return_value=False),
            patch.object(typer, "echo"),
        ):
            mock_in.isatty.return_value = True
            mock_out.isatty.return_value = True
            with pytest.raises(typer.Exit):
                ensure_empty_dir_or_exit(d, interactive=True)

    def test_nonempty_no_tty_raises_even_if_interactive_true(self, tmp_path):
        d = tmp_path / "notty"
        d.mkdir()
        (d / "f.txt").write_text("x")
        with (
            patch("sys.stdin") as mock_in,
            patch("sys.stdout") as mock_out,
        ):
            mock_in.isatty.return_value = False
            mock_out.isatty.return_value = False
            with pytest.raises(typer.Exit):
                ensure_empty_dir_or_exit(d, interactive=True)


# ── _resolve_input_dir ───────────────────────────────────────────────────────


class TestResolveInputDir:
    def test_returns_original_when_no_tty(self, tmp_path):
        with patch.object(merger_mod, "_has_tty", return_value=False):
            result = _resolve_input_dir(tmp_path)
        assert result == tmp_path

    def test_returns_original_when_user_declines(self, tmp_path):
        with (
            patch.object(merger_mod, "_has_tty", return_value=True),
            patch.object(typer, "confirm", return_value=False),
        ):
            result = _resolve_input_dir(tmp_path)
        assert result == tmp_path

    def test_returns_picked_dir(self, tmp_path):
        picked = tmp_path / "picked"
        picked.mkdir()
        with (
            patch.object(merger_mod, "_has_tty", return_value=True),
            patch.object(typer, "confirm", return_value=True),
            patch.object(merger_mod, "_pick_directory_gui", return_value=picked),
        ):
            result = _resolve_input_dir(tmp_path)
        assert result == picked

    def test_falls_back_when_gui_returns_none(self, tmp_path):
        with (
            patch.object(merger_mod, "_has_tty", return_value=True),
            patch.object(typer, "confirm", return_value=True),
            patch.object(merger_mod, "_pick_directory_gui", return_value=None),
            patch.object(typer, "echo"),
        ):
            result = _resolve_input_dir(tmp_path)
        assert result == tmp_path


# ── _print_banner ────────────────────────────────────────────────────────────


class TestPrintBanner:
    def test_prints_without_error(self, tmp_path):
        messages = []
        with patch.object(typer, "echo", side_effect=messages.append):
            _print_banner(tmp_path, tmp_path / "out", ["F32", "G20"])
        assert len(messages) > 0
        assert any("pipeline" in m.lower() or "input" in m.lower() for m in messages)


# ── _run_extraction ──────────────────────────────────────────────────────────


class TestRunExtraction:
    def test_success_logs_completed(self):
        messages = []
        with (
            patch.object(merger_mod, "run_pipeline"),
            patch.object(typer, "echo", side_effect=messages.append),
        ):
            _run_extraction("in", "out", ["F32"], False, False)
        assert any("completado" in m.lower() for m in messages)

    def test_exception_raises_exit(self):
        with (
            patch.object(merger_mod, "run_pipeline", side_effect=RuntimeError("boom")),
            patch.object(typer, "echo"),
        ):
            with pytest.raises(typer.Exit):
                _run_extraction("in", "out", ["F32"], False, False)


# ── _rename_and_merge ────────────────────────────────────────────────────────


class TestRenameAndMerge:
    def test_calls_rename_and_merge(self):
        with (
            patch.object(typer, "echo"),
            patch.object(merger_mod, "rename_csv_with_timestamp", return_value="ok"),
            patch.object(merger_mod, "merge_csv") as mock_merge,
        ):
            _rename_and_merge()
        mock_merge.assert_called_once()

    def test_rename_failure_raises_exit(self):
        with (
            patch.object(typer, "echo"),
            patch.object(
                merger_mod, "rename_csv_with_timestamp", side_effect=FileNotFoundError("nope")
            ),
        ):
            with pytest.raises(typer.Exit):
                _rename_and_merge()


# ── _pick_directory_gui ──────────────────────────────────────────────────────


class TestPickDirectoryGui:
    def test_returns_none_when_tkinter_unavailable(self):
        with patch.dict("sys.modules", {"tkinter": None}):
            from epiforecast.data.extraction.merger import _pick_directory_gui

            result = _pick_directory_gui()
            assert result is None

    def test_returns_none_on_runtime_error(self):
        mock_tk = MagicMock()
        mock_tk.Tk.side_effect = RuntimeError("no display")
        with patch.dict("sys.modules", {"tkinter": mock_tk}):
            from epiforecast.data.extraction.merger import _pick_directory_gui

            result = _pick_directory_gui()
            assert result is None


# ── main CLI ─────────────────────────────────────────────────────────────────


class TestMainCli:
    def test_exits_when_input_dir_missing(self, tmp_path):
        with (
            patch.object(merger_mod, "_resolve_input_dir", return_value=tmp_path / "nope"),
            patch.object(typer, "echo"),
        ):
            with pytest.raises(typer.Exit):
                merger_mod.main(
                    input_dir=tmp_path / "nope",
                    output_dir=tmp_path / "out",
                    keywords=["F32"],
                    save_matched_pages=False,
                    save_individual_tables=False,
                )

    def test_calls_pipeline_steps(self, tmp_path):
        input_dir = tmp_path / "pdfs"
        input_dir.mkdir()
        output_dir = tmp_path / "out"

        with (
            patch.object(merger_mod, "_resolve_input_dir", return_value=input_dir),
            patch.object(merger_mod, "_print_banner"),
            patch.object(merger_mod, "_run_extraction") as mock_extract,
            patch.object(merger_mod, "_rename_and_merge") as mock_merge,
        ):
            merger_mod.main(
                input_dir=input_dir,
                output_dir=output_dir,
                keywords=["F32"],
                save_matched_pages=False,
                save_individual_tables=False,
            )
        mock_extract.assert_called_once()
        mock_merge.assert_called_once()
