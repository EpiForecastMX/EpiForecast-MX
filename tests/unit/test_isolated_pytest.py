from __future__ import annotations

from pathlib import Path
import signal
import subprocess

import pytest
from scripts import run_isolated_pytest


def test_parse_collected_files_deduplica_y_conserva_orden():
    output = "\n".join(
        [
            "tests/integration/test_a.py::test_uno",
            "tests/integration/test_a.py::test_dos[param]",
            "tests/integration/test_b.py::test_tres",
            "3 tests collected",
        ]
    )

    assert run_isolated_pytest.parse_collected_files(output) == (
        Path("tests/integration/test_a.py"),
        Path("tests/integration/test_b.py"),
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(0, 0), (3, 3), (-signal.SIGSEGV, 139), (-signal.SIGTERM, 143)],
)
def test_normalized_returncode(raw, expected):
    assert run_isolated_pytest.normalized_returncode(raw) == expected


def test_run_files_lanza_un_proceso_por_archivo(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(run_isolated_pytest.subprocess, "run", fake_run)

    rc = run_isolated_pytest.run_files(
        (Path("tests/a.py"), Path("tests/b.py")),
        "slow or integration",
        coverage=False,
    )

    assert rc == 0
    assert len(calls) == 2
    assert any(arg == "tests/a.py" for arg in calls[0])
    assert any(arg == "tests/b.py" for arg in calls[1])
    assert all("tests/b.py" not in call for call in calls[:1])


def test_run_files_reporta_sigsegv_y_detiene(monkeypatch, capsys):
    calls = 0

    def fake_run(command, **kwargs):
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(command, -signal.SIGSEGV)

    monkeypatch.setattr(run_isolated_pytest.subprocess, "run", fake_run)

    rc = run_isolated_pytest.run_files(
        (Path("tests/a.py"), Path("tests/no_debe_correr.py")),
        "integration",
        coverage=False,
    )

    assert rc == 139
    assert calls == 1
    assert "SIGSEGV detectado" in capsys.readouterr().err
