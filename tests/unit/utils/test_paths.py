# tests/unit/utils/test_paths.py
"""Unit tests for src/epiforecast/utils/paths.py.

Covers directory creation, file-existence checks, and folder-cleanup
functions using pytest's tmp_path fixture so no real project paths are touched.
"""

from pathlib import Path

import pytest

from epiforecast.utils.paths import asegurar_ruta, existe_archivo, limpia_carpeta


class TestAsegurarRuta:
    """asegurar_ruta() creates missing directories and returns the Path."""

    def test_creates_missing_directory(self, tmp_path: Path):
        """Directory that does not exist must be created."""
        new_dir = tmp_path / "subdir" / "deep"
        assert not new_dir.exists()

        result = asegurar_ruta(new_dir)

        assert result.exists()
        assert result.is_dir()

    def test_returns_path_object(self, tmp_path: Path):
        """Return value must always be a Path instance."""
        result = asegurar_ruta(tmp_path)
        assert isinstance(result, Path)

    def test_existing_directory_not_raised(self, tmp_path: Path):
        """Calling on an existing directory must not raise."""
        result = asegurar_ruta(tmp_path)
        assert result == tmp_path

    def test_accepts_string_input(self, tmp_path: Path):
        """Function must handle a plain string path, not only Path objects."""
        target = tmp_path / "from_string"
        result = asegurar_ruta(str(target))
        assert result.is_dir()

    def test_returns_same_path_that_was_passed(self, tmp_path: Path):
        """Returned Path must match the directory that was requested."""
        target = tmp_path / "expected"
        result = asegurar_ruta(target)
        assert result == target


class TestExisteArchivo:
    """existe_archivo() returns True/False based on file presence."""

    def test_existing_file_returns_true(self, tmp_path: Path):
        """A file that exists on disk must return True."""
        f = tmp_path / "archivo.txt"
        f.write_text("contenido")
        assert existe_archivo(f) is True

    def test_missing_file_returns_false(self, tmp_path: Path):
        """A non-existent path must return False."""
        missing = tmp_path / "no_existe.csv"
        assert existe_archivo(missing) is False

    def test_directory_returns_false(self, tmp_path: Path):
        """Directories are not files; should return False."""
        assert existe_archivo(tmp_path) is False

    def test_accepts_string_path(self, tmp_path: Path):
        """Must work with a string argument, not only Path."""
        f = tmp_path / "str_test.txt"
        f.write_text("x")
        assert existe_archivo(str(f)) is True


class TestLimpiaCarpeta:
    """limpia_carpeta() deletes all files inside a directory."""

    def test_removes_all_files(self, tmp_path: Path):
        """All files inside the directory must be deleted."""
        for i in range(3):
            (tmp_path / f"file_{i}.txt").write_text("data")

        limpia_carpeta(tmp_path)

        remaining = list(tmp_path.iterdir())
        assert remaining == [], f"Se esperaba carpeta vacía, quedan: {remaining}"

    def test_subdirectories_preserved(self, tmp_path: Path):
        """Subdirectories should NOT be removed (only files)."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        limpia_carpeta(tmp_path)

        assert subdir.exists(), "Subdirectorio fue eliminado (no debería)"

    def test_empty_directory_ok(self, tmp_path: Path):
        """Cleaning an already-empty folder must not raise."""
        limpia_carpeta(tmp_path)  # should be a no-op

    def test_raises_on_non_directory(self, tmp_path: Path):
        """Passing a file path (not a directory) must raise ValueError."""
        f = tmp_path / "not_a_dir.txt"
        f.write_text("x")
        with pytest.raises(ValueError):
            limpia_carpeta(f)
