"""Build reproducibility metadata for serialized model artifacts."""

from __future__ import annotations

import datetime
from importlib.metadata import PackageNotFoundError, version
import subprocess
import sys

from loguru import logger


def build_model_metadata() -> dict[str, str]:
    """Return dict with package version, git hash, timestamp and Python version."""
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.debug("No se pudo obtener git hash (entorno sin git)")
        git_hash = "unknown"

    try:
        pkg_version = version("epiforecast-mx")
    except PackageNotFoundError:
        logger.debug("Paquete epiforecast-mx no instalado (modo desarrollo)")
        pkg_version = "unknown"

    return {
        "pkg_version": pkg_version,
        "git_hash": git_hash,
        "saved_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
