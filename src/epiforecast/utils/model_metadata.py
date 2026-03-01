"""Build reproducibility metadata for serialized model artifacts."""

from __future__ import annotations

import datetime
from importlib.metadata import version
import subprocess
import sys


def build_model_metadata() -> dict[str, str]:
    """Return dict with package version, git hash, timestamp and Python version."""
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        git_hash = "unknown"

    try:
        pkg_version = version("epiforecast-mx")
    except Exception:
        pkg_version = "unknown"

    return {
        "pkg_version": pkg_version,
        "git_hash": git_hash,
        "saved_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
