"""Plugin pytest: presupuesto explícito de skips para un carril de CI.

No cambia la semántica de ningún test. Sólo cuando el llamador pasa ``--max-skips`` cuenta
los resultados realmente omitidos y transforma el run en fallo si exceden el presupuesto.
"""

from __future__ import annotations

from typing import Any

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("epiforecast-ci")
    group.addoption(
        "--max-skips",
        type=int,
        default=None,
        help="falla si el run produce más skips que este presupuesto",
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # noqa: ARG001
    budget = session.config.getoption("--max-skips")
    if budget is None:
        return
    reporter: Any = session.config.pluginmanager.get_plugin("terminalreporter")
    skipped = len(reporter.stats.get("skipped", [])) if reporter is not None else 0
    if skipped <= budget:
        return
    if reporter is not None:
        reporter.write_sep(
            "=",
            f"SKIP BUDGET EXCEEDED: {skipped} skips > {budget} permitidos",
            red=True,
            bold=True,
        )
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
