"""F2/C2 — run_engines: subprocess limpio por motor, fail-closed rc=2, reanudación honesta.

Spawnea el worker real (intérprete fresco, sin adapters registrados) → siempre rc=2 en C2.
No requiere datos gitignored (no construye dataset). El gate de validate-data va en integration.
"""

from __future__ import annotations

import hashlib

import pytest

from epiforecast.runner import orchestrator as orch
from epiforecast.runner.manifest import (
    CMD_BENCHMARK,
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    ArtifactRecord,
    JobRecord,
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
    # Manifiesto, result.json y logs stdout/stderr quedan bajo el run_dir.
    assert (tmp_path / "run_manifest.json").exists()
    assert (tmp_path / "jobs" / "prophet.result.json").exists()
    assert (tmp_path / "jobs" / "prophet.stdout.txt").exists()
    assert (tmp_path / "jobs" / "prophet.stderr.txt").exists()
    assert man.jobs["prophet"].stdout == "jobs/prophet.stdout.txt"
    # Ningún job es reanudable (no succeeded + validado).
    assert not any(j.is_complete() for j in man.jobs.values())


# ── Aceptación de un job: rc0 + intento correcto + digest de artefactos (funciones puras) ──
def test_verify_artifacts(tmp_path):
    (tmp_path / "f.csv").write_text("hola")
    digest = hashlib.sha256(b"hola").hexdigest()
    assert orch.verify_artifacts(tmp_path, [{"path": "f.csv", "digest": digest}]) == []
    # ausente y digest incorrecto → problemas
    assert orch.verify_artifacts(tmp_path, [{"path": "no.csv", "digest": digest}])
    assert orch.verify_artifacts(tmp_path, [{"path": "f.csv", "digest": "malo"}])


def test_apply_result_rechaza_stale(tmp_path):
    job = JobRecord(engine="prophet")
    stale = {"status": "succeeded", "attempt": "viejo", "artifacts": []}
    orch._apply_result(tmp_path, job, "prophet", 0, stale, attempt="nuevo")
    assert job.status == STATUS_FAILED and job.error_type == "StaleResult"


def test_apply_result_rechaza_digest_no_coincidente(tmp_path):
    (tmp_path / "f.csv").write_text("x")
    job = JobRecord(engine="prophet")
    result = {
        "status": "succeeded",
        "attempt": "a",
        "artifacts": [{"path": "f.csv", "digest": "malo", "schema": "forecast.v1"}],
    }
    orch._apply_result(tmp_path, job, "prophet", 0, result, attempt="a")
    assert job.status == STATUS_FAILED and job.error_type == "ArtifactMismatch"


def test_apply_result_acepta_con_digest_correcto(tmp_path):
    (tmp_path / "f.csv").write_text("x")
    digest = hashlib.sha256(b"x").hexdigest()
    job = JobRecord(engine="prophet")
    result = {
        "status": "succeeded",
        "attempt": "a",
        "artifacts": [{"path": "f.csv", "digest": digest, "schema": "forecast.v1"}],
    }
    orch._apply_result(tmp_path, job, "prophet", 0, result, attempt="a")
    assert job.status == STATUS_SUCCEEDED and job.is_complete()


def _seed_complete(tmp_path, engine="prophet"):
    """Semilla: manifiesto con un job succeeded + artefacto REAL en disco (digest coincidente)."""
    content = b"forecast-data"
    (tmp_path / "p.csv").write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    seed = RunManifest(run_id=tmp_path.name, disease_id="obesidad", command=CMD_BENCHMARK)
    seed.job(engine).succeed([ArtifactRecord("p.csv", digest, "forecast.v1", validated=True)])
    seed.write(tmp_path)
    return digest


def test_reanudacion_salta_job_completo(tmp_path):
    _seed_complete(tmp_path)
    man = orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, ["prophet", "deepar"], resume=True)
    assert (
        man.jobs["prophet"].status == STATUS_SUCCEEDED
    )  # NO se re-ejecutó (artefacto verificado)
    assert man.jobs["prophet"].is_complete()
    assert man.jobs["deepar"].status == STATUS_FAILED and man.jobs["deepar"].exit_code == 2
    assert (tmp_path / "jobs" / "deepar.result.json").exists()
    assert not (tmp_path / "jobs" / "prophet.result.json").exists()


def test_resume_reejecuta_si_artefacto_corrupto(tmp_path):
    # El manifiesto dice succeeded+validated, pero el artefacto en disco NO coincide → se re-ejecuta.
    _seed_complete(tmp_path)
    (tmp_path / "p.csv").write_bytes(b"corrompido")  # digest ya no coincide
    man = orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, ["prophet"], resume=True)
    assert man.jobs["prophet"].status == STATUS_FAILED and man.jobs["prophet"].exit_code == 2


def test_resume_reejecuta_si_artefacto_ausente(tmp_path):
    _seed_complete(tmp_path)
    (tmp_path / "p.csv").unlink()  # artefacto borrado
    man = orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, ["prophet"], resume=True)
    assert man.jobs["prophet"].status == STATUS_FAILED


def test_pkl_existente_no_cuenta_como_terminado(tmp_path):
    # Un .pkl suelto NO autoriza saltar el job: sin manifiesto succeeded+validado, se re-ejecuta.
    (tmp_path / "prophet.pkl").write_bytes(b"fake-pickle")
    man = orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, ["prophet"], resume=True)
    assert man.jobs["prophet"].status == STATUS_FAILED and man.jobs["prophet"].exit_code == 2


def test_no_resume_reejecuta_completo(tmp_path):
    _seed_complete(tmp_path)
    man = orch.run_engines(tmp_path, "obesidad", CMD_BENCHMARK, ["prophet"], resume=False)
    assert man.jobs["prophet"].status == STATUS_FAILED  # sin resume → re-ejecuta → rc2


def test_copia_digests_y_counts_al_manifest(tmp_path):
    man = orch.run_engines(
        tmp_path,
        "obesidad",
        CMD_BENCHMARK,
        ["prophet"],
        input_digests={"raw": "aa", "dataset": "bb"},
        counts={"base": 64, "products": 111},
    )
    assert man.input_digests == {"raw": "aa", "dataset": "bb"}
    assert man.counts == {"base": 64, "products": 111}


def test_require_clean_rechaza_arbol_sucio(monkeypatch):
    # Guard de run oficial: cambios trackeados sin commit → RunnerError ANTES de construir datos.
    monkeypatch.setattr(orch, "_tracked_dirty", lambda: ["src/epiforecast/x.py"])
    with pytest.raises(orch.RunnerError):
        orch.run_command("Obesidad", "benchmark", require_clean=True)


def test_guard_rechaza_residuos_de_ejecucion_en_un_dataset(tmp_path):
    # C7.0: dataset_id y run_id son identidades DISTINTAS. Un run_manifest.json o un jobs/ dentro
    # del dir de un dataset es ambigüedad pre-C3 y debe fallar cerrado, no colarse.
    d = tmp_path / "obesidad_deadbeef"
    d.mkdir()
    orch.reject_run_residues(d)  # dir limpio: no levanta

    (d / "dataset_manifest.json").write_text("{}")
    (d / "manifest.json").write_text("{}")
    (d / "inputs").mkdir()
    orch.reject_run_residues(d)  # procedencia legítima del constructor: tampoco levanta

    (d / "run_manifest.json").write_text("{}")
    with pytest.raises(orch.RunnerError, match="artefactos de ejecución"):
        orch.reject_run_residues(d)

    (d / "run_manifest.json").unlink()
    (d / "jobs").mkdir()
    with pytest.raises(orch.RunnerError, match="artefactos de ejecución"):
        orch.reject_run_residues(d)
