"""Control positivo y negativo del presupuesto de skips del job Tests."""

from pathlib import Path
import subprocess
import sys


def _run(example: Path, budget: int) -> subprocess.CompletedProcess[str]:
    example.write_text(
        "import pytest\n\n@pytest.mark.skip(reason='skip fabricado')\ndef test_demo(): pass\n",
        encoding="utf-8",
    )
    return subprocess.run(  # noqa: S603 — argv cerrado, sin shell
        [
            sys.executable,
            "-m",
            "pytest",
            str(example),
            "-q",
            "-p",
            "tests.skip_budget",
            f"--max-skips={budget}",
            "-o",
            "addopts=",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_un_skip_dentro_del_presupuesto_pasa(tmp_path: Path) -> None:
    result = _run(tmp_path / "test_budget_ok.py", 1)
    assert result.returncode == 0, result.stdout + result.stderr


def test_un_skip_inesperado_pone_el_run_en_rojo(tmp_path: Path) -> None:
    result = _run(tmp_path / "test_budget_fail.py", 0)
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "SKIP BUDGET EXCEEDED: 1 skips > 0 permitidos" in output
