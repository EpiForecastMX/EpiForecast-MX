"""Tests for model metadata builder."""

from __future__ import annotations

from unittest.mock import patch

from epiforecast.utils.model_metadata import build_model_metadata


class TestBuildModelMetadata:
    def test_returns_expected_keys(self) -> None:
        meta = build_model_metadata()
        assert "pkg_version" in meta
        assert "git_hash" in meta
        assert "saved_at" in meta
        assert "python_version" in meta

    def test_python_version_format(self) -> None:
        meta = build_model_metadata()
        parts = meta["python_version"].split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_saved_at_is_iso(self) -> None:
        meta = build_model_metadata()
        # ISO format contains T separator
        assert "T" in meta["saved_at"]

    def test_git_hash_not_empty(self) -> None:
        meta = build_model_metadata()
        assert len(meta["git_hash"]) > 0

    def test_git_unavailable_returns_unknown(self) -> None:
        with patch(
            "epiforecast.utils.model_metadata.subprocess.check_output",
            side_effect=FileNotFoundError,
        ):
            meta = build_model_metadata()
            assert meta["git_hash"] == "unknown"

    def test_pkg_not_installed_returns_unknown(self) -> None:
        from importlib.metadata import PackageNotFoundError

        with patch(
            "epiforecast.utils.model_metadata.version",
            side_effect=PackageNotFoundError,
        ):
            meta = build_model_metadata()
            assert meta["pkg_version"] == "unknown"
