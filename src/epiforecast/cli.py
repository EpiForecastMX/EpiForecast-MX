"""Thin wrapper to launch the ``epi`` interactive console.

Flit can only create console-scripts that point to importable modules inside
the installed package.  The real CLI lives in ``epi.py`` at the repo root and
is heavy (~1 400 lines), so instead of moving it we simply exec it here.
"""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


def main() -> None:
    """Run ``epi.py`` located at the repository root."""
    # Resolve repo root relative to this file: src/epiforecast/cli.py -> ../../..
    repo = Path(__file__).resolve().parents[2]
    epi_path = repo / "epi.py"

    if not epi_path.exists():
        print(f"Error: no se encontro {epi_path}", file=sys.stderr)
        raise SystemExit(1)

    # Make repo root importable (epi.py may import local modules)
    root_str = str(repo)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    sys.argv[0] = str(epi_path)
    runpy.run_path(str(epi_path), run_name="__main__")
