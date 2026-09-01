"""Rutas puras y contrato mínimo del doctor de ``runner_release``."""

import dataclasses

import pytest

from epiforecast import registry, registry_doctor
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_store import default_releases_root, release_path


@pytest.mark.unit
def test_la_sede_se_deriva_de_disease_id_y_release_id(tmp_path):
    sede = tmp_path / "releases"
    destino = release_path(sede, "obesidad", "obesidad_release_abc123456789")
    assert destino == sede / "obesidad" / "obesidad_release_abc123456789"


@pytest.mark.unit
@pytest.mark.parametrize("segmento", ["../fuera", "con/barra", "..", ".", "", "  "])
def test_la_sede_rechaza_segmentos_que_no_son_un_directorio(tmp_path, segmento):
    sede = tmp_path / "releases"
    with pytest.raises(ArtifactValidationError):
        release_path(sede, "obesidad", segmento)
    with pytest.raises(ArtifactValidationError):
        release_path(sede, segmento, "obesidad_release_abc123456789")


@pytest.mark.contract
def test_la_sede_por_defecto_es_artifacts_releases_del_repo():
    ruta = default_releases_root()
    assert ruta.parts[-2:] == ("artifacts", "releases")
    assert (ruta.parents[1] / "pyproject.toml").is_file()


@pytest.mark.contract
def test_el_doctor_falla_con_la_sede_vacía(tmp_path):
    real = registry.require("obesidad")
    disease = dataclasses.replace(
        real,
        artifact_source=registry.ArtifactSource(
            backend=registry.BACKEND_RUNNER_RELEASE,
            release_id="obesidad_release_000000000000",
        ),
        training_engines=(),
        eligible_engines=(),
    )
    problemas = registry_doctor._diagnose_runner_release(disease, tmp_path / "releases")
    assert len(problemas) == 1 and problemas[0].severity == "error"
