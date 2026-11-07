"""Prueba negativa hermética: sin release, el compilador rechaza al padecimiento."""

from __future__ import annotations

import dataclasses

import pytest

from epiforecast import registry
from epiforecast.publication.compiler import MODE_CANDIDATE, compile_release
from epiforecast.runner.artifact_identity import ArtifactValidationError


def test_un_padecimiento_sin_release_no_se_compila(tmp_path, monkeypatch):
    sin_release = dataclasses.replace(
        registry.require("covid_19"),
        lifecycle="configured",
        artifact_source=registry.ArtifactSource(backend=registry.BACKEND_LEGACY),
    )
    monkeypatch.setattr(registry, "require", lambda _: sin_release)
    with pytest.raises(ArtifactValidationError, match="exige backend 'runner_release'"):
        compile_release(disease_id="sintetico", mode=MODE_CANDIDATE, releases_root=tmp_path)
