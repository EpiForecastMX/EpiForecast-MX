"""F2/C2 — run_engines: subprocess limpio por motor, fail-closed rc=2, reanudación honesta.

Spawnea el worker real (intérprete fresco, sin adapters registrados) → siempre rc=2 en C2.
No requiere datos gitignored (no construye dataset). El gate de validate-data va en integration.
"""

from __future__ import annotations

import pytest

from epiforecast.runner import orchestrator as orch
from epiforecast.runner.manifest import (
    CMD_BENCHMARK,
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    ArtifactRecord,
    RunManifest,
)


def test_engines_vacio_levanta(tmp_path):
    with pytest.raises(orch.RunnerError):
        orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, [])


def test_sin_adapter_todos_fallan_rc2(tmp_path):
    man = orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, ["prophet", "deepar"])
    assert man.status == STATUS_FAILED and man.exit_code == 2
    assert set(man.jobs) == {"prophet", "deepar"}
    for j in man.jobs.values():
        assert j.status == STATUS_FAILED and j.exit_code == 2 and j.error_type == "NoAdapter"
    # Manifiesto y result.json quedan bajo el run_dir.
    assert (tmp_path / "run_manifest.json").exists()
    assert (tmp_path / "jobs" / "prophet.result.json").exists()
    # Ningún job es reanudable (no succeeded + validado).
    assert not any(j.is_complete() for j in man.jobs.values())


def test_reanudacion_salta_job_completo(tmp_path):
    # Semilla: prophet succeeded + artefacto validado (mismo comando).
    seed = RunManifest(run_id=tmp_path.name, disease_id="obesidad", command=CMD_BENCHMARK)
    seed.job("prophet").succeed([ArtifactRecord("p.csv", "d", "forecast.v1", validated=True)])
    seed.write(tmp_path)

    man = orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, ["prophet", "deepar"], resume=True)
    assert man.jobs["prophet"].status == STATUS_SUCCEEDED  # NO se re-ejecutó
    assert man.jobs["prophet"].is_complete()
    assert man.jobs["deepar"].status == STATUS_FAILED and man.jobs["deepar"].exit_code == 2
    # deepar NO corrió su worker durante el resume de prophet: solo deepar.result.json existe.
    assert (tmp_path / "jobs" / "deepar.result.json").exists()
    assert not (tmp_path / "jobs" / "prophet.result.json").exists()


def test_pkl_existente_no_cuenta_como_terminado(tmp_path):
    # Un .pkl suelto NO autoriza saltar el job: sin manifiesto succeeded+validado, se re-ejecuta.
    (tmp_path / "prophet.pkl").write_bytes(b"fake-pickle")
    man = orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, ["prophet"], resume=True)
    assert man.jobs["prophet"].status == STATUS_FAILED and man.jobs["prophet"].exit_code == 2


def test_no_resume_reejecuta_completo(tmp_path):
    seed = RunManifest(run_id=tmp_path.name, disease_id="obesidad", command=CMD_BENCHMARK)
    seed.job("prophet").succeed([ArtifactRecord("p.csv", "d", "forecast.v1", validated=True)])
    seed.write(tmp_path)
    man = orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, ["prophet"], resume=False)
    assert man.jobs["prophet"].status == STATUS_FAILED  # sin resume → re-ejecuta → rc2
