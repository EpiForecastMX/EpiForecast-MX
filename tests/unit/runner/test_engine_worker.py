"""F2/C2 — engine_worker: resolución de adapter y result.json (rc 0/1/2), sin subprocess."""

from __future__ import annotations

import json

import pytest

from epiforecast.runner import adapters
from epiforecast.runner import engine_worker as w
from epiforecast.runner.manifest import ArtifactRecord


@pytest.fixture(autouse=True)
def _clean_adapters():
    saved = dict(adapters._ADAPTERS)
    adapters._ADAPTERS.clear()
    yield
    adapters._ADAPTERS.clear()
    adapters._ADAPTERS.update(saved)


def _result(run_dir, engine):
    return json.loads((run_dir / "jobs" / f"{engine}.result.json").read_text())


def test_sin_adapter_rc2(tmp_path):
    rc = w.main(
        [
            "--run-dir",
            str(tmp_path),
            "--engine",
            "prophet",
            "--command",
            "benchmark",
            "--attempt",
            "att1",
        ]
    )
    assert rc == w.RC_NO_ADAPTER
    r = _result(tmp_path, "prophet")
    assert r["status"] == "failed" and r["exit_code"] == 2 and r["error_type"] == "NoAdapter"
    assert r["artifacts"] == [] and r["attempt"] == "att1"


def test_adapter_ok_rc0(tmp_path):
    class _Fake:
        name = "prophet"

        def supports(self, command):
            return True

        def run(self, command, run_dir):
            return [ArtifactRecord("forecast_prophet.csv", "d", "forecast.v1", validated=True)]

    adapters.register_adapter("prophet", _Fake())
    rc = w.main(
        [
            "--run-dir",
            str(tmp_path),
            "--engine",
            "prophet",
            "--command",
            "forecast",
            "--attempt",
            "att2",
        ]
    )
    assert rc == w.RC_OK
    r = _result(tmp_path, "prophet")
    assert r["status"] == "succeeded" and r["exit_code"] == 0 and r["attempt"] == "att2"
    assert r["artifacts"][0]["schema"] == "forecast.v1" and r["artifacts"][0]["validated"] is True


def test_adapter_lanza_rc1(tmp_path):
    class _Boom:
        name = "deepar"

        def supports(self, command):
            return True

        def run(self, command, run_dir):
            raise RuntimeError("motor reventó")

    adapters.register_adapter("deepar", _Boom())
    rc = w.main(
        [
            "--run-dir",
            str(tmp_path),
            "--engine",
            "deepar",
            "--command",
            "benchmark",
            "--attempt",
            "att3",
        ]
    )
    assert rc == w.RC_ERROR
    r = _result(tmp_path, "deepar")
    assert r["status"] == "failed" and r["exit_code"] == 1 and r["error_type"] == "RuntimeError"


def test_comando_no_soportado_rc3(tmp_path):
    class _OnlyBench:
        name = "prophet"

        def supports(self, command):
            return command == "benchmark"

        def run(self, command, run_dir):  # no debería llamarse
            raise AssertionError("run no debe ejecutarse si el comando no está soportado")

    adapters.register_adapter("prophet", _OnlyBench())
    rc = w.main(
        ["--run-dir", str(tmp_path), "--engine", "prophet", "--command", "refit", "--attempt", "a"]
    )
    assert rc == w.RC_UNSUPPORTED
    r = _result(tmp_path, "prophet")
    assert (
        r["status"] == "failed" and r["exit_code"] == 3 and r["error_type"] == "UnsupportedCommand"
    )
