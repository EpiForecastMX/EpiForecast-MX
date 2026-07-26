"""Ejecuta archivos pytest en procesos aislados.

Algunas dependencias numéricas cargan runtimes OpenMP incompatibles cuando se
ejercitan en el mismo intérprete (por ejemplo, PyTorch y LightGBM en macOS).
El aislamiento se hace por archivo para conservar fixtures compartidos dentro
de cada módulo sin mezclar runtimes nativos entre módulos.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import os
from pathlib import Path
import signal
import subprocess
import sys

_THREAD_ENV = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def parse_collected_files(output: str) -> tuple[Path, ...]:
    """Extrae archivos de node IDs de pytest, sin duplicados y en orden."""
    files: list[Path] = []
    seen: set[Path] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if "::" not in line:
            continue
        path = Path(line.split("::", maxsplit=1)[0])
        if path in seen:
            continue
        seen.add(path)
        files.append(path)
    return tuple(files)


def normalized_returncode(returncode: int) -> int:
    """Convierte una señal POSIX al código de salida convencional 128+señal."""
    return 128 + abs(returncode) if returncode < 0 else returncode


def _isolated_environment() -> dict[str, str]:
    env = os.environ.copy()
    for name in _THREAD_ENV:
        env[name] = "1"
    return env


def _pytest_base() -> list[str]:
    return [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "addopts=",
        "--strict-markers",
        "--tb=short",
        "-q",
    ]


def collect_files(paths: Sequence[Path], marker: str) -> tuple[Path, ...]:
    """Recolecta los archivos que contienen pruebas seleccionadas por marker."""
    command = [
        *_pytest_base(),
        "--collect-only",
        *(str(path) for path in paths),
        "-m",
        marker,
    ]
    result = subprocess.run(  # noqa: S603 - argumentos cerrados, sin shell
        command,
        check=False,
        capture_output=True,
        text=True,
        env=_isolated_environment(),
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"pytest collection failed with rc={result.returncode}")
    files = parse_collected_files(result.stdout)
    if not files:
        raise RuntimeError(f"no tests collected for marker: {marker}")
    return files


def run_files(files: Sequence[Path], marker: str, *, coverage: bool) -> int:
    """Ejecuta cada archivo en un intérprete nuevo y detiene ante el primer fallo."""
    coverage_args = (
        [
            "--cov=src/epiforecast",
            "--cov-append",
            "--cov-report=",
            "--cov-fail-under=0",
        ]
        if coverage
        else []
    )
    env = _isolated_environment()
    for path in files:
        print(f">>> Archivo aislado: {path}", flush=True)
        command = [*_pytest_base(), str(path), "-m", marker, *coverage_args]
        result = subprocess.run(command, check=False, env=env)  # noqa: S603
        if result.returncode == 0:
            continue
        rc = normalized_returncode(result.returncode)
        if result.returncode == -signal.SIGSEGV:
            print(f"SIGSEGV detectado en {path} (rc={rc})", file=sys.stderr)
        else:
            print(f"Fallo en {path} (rc={rc})", file=sys.stderr)
        return rc
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=[Path("tests")])
    parser.add_argument("--marker", default="slow or integration")
    parser.add_argument("--coverage", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        files = collect_files(args.paths, args.marker)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 2
    return run_files(files, args.marker, coverage=args.coverage)


if __name__ == "__main__":
    raise SystemExit(main())
