"""F2/C2 — run_manifest.v1: transiciones de estado, is_complete y round-trip JSON."""

from __future__ import annotations

import pytest

from epiforecast.runner import manifest as m


def _manifest() -> m.RunManifest:
    return m.RunManifest(run_id="obesidad_abc123", disease_id="obesidad", command=m.CMD_BENCHMARK)


def test_comando_y_estado_invalidos_levantan():
    with pytest.raises(m.ManifestError):
        m.RunManifest(run_id="r", disease_id="obesidad", command="publicar")
    with pytest.raises(m.ManifestError):
        m.RunManifest(run_id="r", disease_id="obesidad", command=m.CMD_FORECAST, status="raro")


def test_job_transiciones():
    j = m.JobRecord(engine="prophet")
    assert j.status == m.STATUS_PENDING and not j.is_complete()
    j.start()
    assert j.status == m.STATUS_RUNNING and j.started_at
    j.succeed([m.ArtifactRecord("f.csv", "d", "forecast.v1", validated=True)])
    assert j.status == m.STATUS_SUCCEEDED and j.exit_code == 0 and j.is_complete()


def test_job_fallo():
    j = m.JobRecord(engine="deepar")
    j.start()
    j.fail(2, "NoAdapter", "sin adapter registrado")
    assert j.status == m.STATUS_FAILED and j.exit_code == 2 and not j.is_complete()
    with pytest.raises(m.ManifestError):
        m.JobRecord(engine="x").fail(0, "T", "m")  # fallo con exit 0 es inválido


def test_is_complete_exige_artefactos_validados():
    j = m.JobRecord(engine="prophet")
    j.succeed()  # sin artefactos
    assert not j.is_complete()
    j2 = m.JobRecord(engine="prophet")
    j2.succeed([m.ArtifactRecord("f.csv", "d", "forecast.v1", validated=False)])
    assert not j2.is_complete()  # artefacto no validado → no reanudable


def test_run_transiciones_y_jobs():
    man = _manifest()
    assert man.status == m.STATUS_PENDING and man.schema == m.MANIFEST_SCHEMA
    man.start()
    assert man.status == m.STATUS_RUNNING and man.started_at
    man.job("prophet").start()
    man.job("prophet").succeed([m.ArtifactRecord("p.csv", "d1", "forecast.v1", True)])
    man.job("deepar").fail(2, "NoAdapter", "sin adapter")
    man.add_artifact(m.ArtifactRecord("products.csv", "d2", "products.v1", True))
    man.succeed()
    assert man.status == m.STATUS_SUCCEEDED and man.exit_code == 0
    assert set(man.jobs) == {"prophet", "deepar"}
    assert man.job("prophet").is_complete() and not man.job("deepar").is_complete()


def test_run_fallo_exit0_levanta():
    man = _manifest()
    with pytest.raises(m.ManifestError):
        man.fail(0, "T", "m")


def test_round_trip_json(tmp_path):
    man = _manifest()
    man.code_commit = "728d9f3d"
    man.input_digests = {"raw": "aa", "dataset": "bb"}
    man.counts = {"base": 64, "derived": 47, "products": 111}
    man.start()
    man.job("prophet").succeed([m.ArtifactRecord("p.csv", "d", "forecast.v1", True)])
    man.add_artifact(m.ArtifactRecord("products.csv", "d2", "products.v1", True))
    man.succeed()

    path = man.write(tmp_path)
    assert path.name == "run_manifest.json"
    back = m.RunManifest.read(tmp_path)
    assert back.to_dict() == man.to_dict()
    assert back.counts == {"base": 64, "derived": 47, "products": 111}
    assert back.job("prophet").artifacts[0].schema == "forecast.v1"
    assert back.job("prophet").is_complete()


def test_from_dict_schema_desconocido_levanta():
    with pytest.raises(m.ManifestError):
        m.RunManifest.from_dict({"schema": "run_manifest.v2", "run_id": "r"})
