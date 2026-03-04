"""Tests for CLI thin wrapper."""

from __future__ import annotations

from pathlib import Path

from epiforecast import cli


class TestCLIPathResolution:
    def test_epi_path_exists(self) -> None:
        """Verify the path resolution logic points to repo root with epi.py."""
        cli_path = Path(cli.__file__).resolve()
        repo = cli_path.parents[2]
        epi = repo / "epi.py"
        assert epi.exists(), f"epi.py not found at {epi}"

    def test_repo_root_has_pyproject(self) -> None:
        """Verify repo root detection is correct."""
        cli_path = Path(cli.__file__).resolve()
        repo = cli_path.parents[2]
        assert (repo / "pyproject.toml").exists()

    def test_main_is_callable(self) -> None:
        assert callable(cli.main)
