"""C7.2-B/R19.5 — sede final, promoción atómica y doctor de ``runner_release``.

Todo ocurre en `tmp_path`: la sede se INYECTA, así que la prueba usa una suya y jamás escribe en
`artifacts/releases/` del repo. Eso es también la prueba de que el doctor no resuelve rutas por
convención ni por cwd — si lo hiciera, estos tests no podrían existir sin tocar el repo.

Lo que se fija: un release sólo llega a su sede entero (rename atómico), promoverlo dos veces es
idempotente, promover contenido distinto bajo el mismo ID se rechaza, y el doctor no da verde por
que el directorio exista, sino porque el bundle verifica Y reproduce.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from epiforecast import registry, registry_doctor
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_contract import MANIFEST_FILE
from epiforecast.runner.release_loader import verify_bundle
from epiforecast.runner.release_store import (
    diff_trees,
    promote_release,
)
from tests.unit.runner import artifact_fixtures as af
from tests.unit.runner import release_fixtures as rf

pytestmark = pytest.mark.skipif(
    not af.hay_runs(), reason="los runs sellados de C5 no están en este entorno (runs/ gitignored)"
)


@pytest.fixture(scope="module")
def bundle(tmp_path_factory) -> Path:
    return rf.construir(tmp_path_factory.mktemp("release")).path


@pytest.fixture
def sede(tmp_path) -> Path:
    return tmp_path / "releases"


def _promover(bundle: Path, sede: Path):
    return promote_release(bundle, releases_root=sede, disease_id=af.DISEASE)


def _disease_release(release_id: str) -> registry.Disease:
    """Obesidad, pero declarando el backend de release. No toca el registry real."""
    real = registry.require(af.DISEASE)
    return dataclasses.replace(
        real,
        artifact_source=registry.ArtifactSource(
            backend=registry.BACKEND_RUNNER_RELEASE, release_id=release_id
        ),
        training_engines=(),
        eligible_engines=(),
    )


def _diagnosticar(disease: registry.Disease, sede: Path) -> list[registry_doctor.Problem]:
    return registry_doctor._diagnose_runner_release(disease, sede)


# ── Promoción ─────────────────────────────────────────────────────────────────────────────────
def test_promover_deja_el_release_entero_en_su_sede(bundle, sede):
    promovido = _promover(bundle, sede)
    assert promovido.reused is False
    assert promovido.path == sede / af.DISEASE / bundle.name
    assert not diff_trees(bundle, promovido.path)
    assert verify_bundle(promovido.path).release_id == bundle.name


def test_promover_dos_veces_el_mismo_contenido_es_idempotente(bundle, sede):
    primero = _promover(bundle, sede)
    segundo = _promover(bundle, sede)
    assert (primero.reused, segundo.reused) == (False, True)
    assert primero.path == segundo.path
    assert [p.name for p in (sede / af.DISEASE).iterdir()] == [bundle.name]


def test_promover_no_repara_una_sede_manipulada(bundle, sede):
    """La sede es inmutable: si su contenido cambió, promover NO la sobrescribe en silencio.

    Un bundle VÁLIDO con otro contenido tendría otro `release_id` —lo garantiza la identidad—, así
    que el caso real de "mismo ID, contenido distinto" es que alguien tocara el destino. Promover
    otra vez debe delatarlo, nunca arreglarlo por debajo.
    """
    promovido = _promover(bundle, sede)
    (promovido.path / "forecast" / "forecast.csv").write_text("manipulado\n", encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="contenido distinto"):
        _promover(bundle, sede)


def test_no_se_promueve_un_bundle_que_no_verifica(bundle, sede, tmp_path):
    roto = rf.copia(bundle, tmp_path / "roto")
    (roto / MANIFEST_FILE).unlink()
    with pytest.raises(ArtifactValidationError):
        _promover(roto, sede)
    assert not sede.exists() or not any(sede.rglob(MANIFEST_FILE))


def test_no_se_promueve_un_release_de_otro_padecimiento(bundle, sede):
    with pytest.raises(ArtifactValidationError, match="disease_id"):
        promote_release(bundle, releases_root=sede, disease_id="otro_padecimiento")


def test_la_promoción_no_deja_staging(bundle, sede):
    promovido = _promover(bundle, sede)
    assert [p.name for p in promovido.path.parent.iterdir()] == [promovido.release_id]


# ── Doctor de runner_release ──────────────────────────────────────────────────────────────────
def test_el_doctor_acepta_el_release_declarado_en_su_sede(bundle, sede):
    promovido = _promover(bundle, sede)
    assert _diagnosticar(_disease_release(promovido.release_id), sede) == []


def test_el_doctor_falla_si_el_release_declarado_no_está_en_la_sede(bundle, sede):
    _promover(bundle, sede)
    problemas = _diagnosticar(_disease_release("obesidad_release_000000000000"), sede)
    assert len(problemas) == 1 and "no está en la sede" in problemas[0].message


def test_el_doctor_avisa_si_el_padecimiento_declara_motores_legacy(bundle, sede):
    promovido = _promover(bundle, sede)
    disease = dataclasses.replace(
        _disease_release(promovido.release_id), training_engines=("prophet",)
    )
    problemas = _diagnosticar(disease, sede)
    assert [p.severity for p in problemas] == ["warning"]


def _mutar(sede: Path, release_id: str, mutacion) -> None:
    mutacion(sede / af.DISEASE / release_id)


@pytest.mark.parametrize(
    ("nombre", "mutacion", "patron"),
    [
        (
            "schema",
            lambda root: rf.degradar_a_v1(root),
            "release_manifest.v1",
        ),
        (
            "digest",
            lambda root: (root / "forecast" / "forecast.csv").write_bytes(b"alterado\n"),
            "digest",
        ),
        (
            "inventario",
            lambda root: (root / "forecast" / "colado.csv").write_text("x\n", encoding="utf-8"),
            "no declarados",
        ),
        (
            "modelo_faltante",
            lambda root: rf.un_estado(root).unlink(),
            "faltan",
        ),
    ],
)
def test_el_doctor_rechaza_un_release_mutado_en_la_sede(bundle, sede, nombre, mutacion, patron):
    promovido = _promover(bundle, sede)
    _mutar(sede, promovido.release_id, mutacion)
    problemas = _diagnosticar(_disease_release(promovido.release_id), sede)
    assert len(problemas) == 1
    assert patron in problemas[0].message, f"{nombre}: {problemas[0].message}"


def test_el_doctor_rechaza_un_release_colocado_bajo_otro_id(bundle, sede):
    """El nombre del directorio no es identidad: dentro debe estar EL release que se declara."""
    promovido = _promover(bundle, sede)
    ajeno = promovido.path.parent / "obesidad_release_deadbeef1234"
    promovido.path.rename(ajeno)
    # El bundle sigue siendo válido en sí mismo: lo que falla es que no es el declarado.
    assert verify_bundle(ajeno).release_id == promovido.release_id
    problemas = _diagnosticar(_disease_release("obesidad_release_deadbeef1234"), sede)
    assert len(problemas) == 1 and "donde el registry declara" in problemas[0].message


def test_el_doctor_rechaza_un_release_de_otro_padecimiento(bundle, sede):
    """Cambiar el padecimiento y re-sellar no cuela: los runs sellados que viajan dentro lo dicen."""
    promovido = _promover(bundle, sede)
    manifest = json.loads((promovido.path / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest["disease_id"] = "otro_padecimiento"
    (promovido.path / MANIFEST_FILE).write_text(json.dumps(manifest), encoding="utf-8")
    rf.resellar(promovido.path)
    problemas = _diagnosticar(_disease_release(promovido.release_id), sede)
    assert len(problemas) == 1
    assert "otro_padecimiento" in problemas[0].message


def _falsear_forecast_coherentemente(root: Path) -> Path:
    """Altera una predicción y deja TODO lo demás cuadrando: sellos internos, digests e identidad.

    No basta con tocar el CSV: el `run_manifest.json` del forecast que viaja dentro también sella su
    digest, así que hay que actualizarlo. Sin ese paso la mutación muere en el sello y la prueba
    daría verde sin haber ejercitado jamás la reproducción — el falso verde clásico.
    """
    csv = root / "forecast" / "forecast_base.csv"
    lineas = csv.read_text(encoding="utf-8").splitlines(keepends=True)
    campos = lineas[1].rstrip("\n").split(",")
    campos[13] = str(float(campos[13]) + 1.0)
    lineas[1] = ",".join(campos) + "\n"
    csv.write_text("".join(lineas), encoding="utf-8")

    manifiesto = root / "forecast" / "run_manifest.json"
    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    for registro in datos["artifacts"]:
        if registro["path"] == "forecast_base.csv":
            registro["digest"] = rf.sha256_bytes(csv.read_bytes())
    manifiesto.write_text(json.dumps(datos, indent=2, sort_keys=True), encoding="utf-8")
    rf.resellar(root)
    # Un release falseado "bien hecho" también se guardaría bajo el ID que dice tener.
    falseado = rf.leer_manifest(root)["release_id"]
    destino = root.parent / falseado
    root.rename(destino)
    return destino


def test_el_release_falseado_coherentemente_pasa_la_verificación_estructural(bundle, sede):
    """Guardia de la prueba siguiente: si esto fallara, la reproducción no se estaría probando."""
    promovido = _promover(bundle, sede)
    falseado = _falsear_forecast_coherentemente(promovido.path)
    # Schema, checksums, inventario, sellos internos e identidad vuelven a cuadrar entre sí; lo
    # único que cambia es el `release_id`, porque la identidad cubre cada byte de cada payload.
    assert verify_bundle(falseado).release_id == falseado.name != promovido.release_id


def test_el_doctor_exige_que_el_release_reproduzca_no_solo_que_verifique(bundle, sede):
    """El corazón del backend: los modelos cargan y vuelven a dar el forecast que transporta.

    La predicción falseada sobrevive a schema, checksums, inventario, sellos internos e identidad.
    Sólo cargar los 64 modelos y volver a pronosticar la descubre.
    """
    promovido = _promover(bundle, sede)
    falseado = _falsear_forecast_coherentemente(promovido.path)
    # Se declara el ID que el bundle falseado dice tener: así el doctor llega hasta el final y la
    # reproducción es lo ÚNICO que queda entre el artefacto y un verde.
    problemas = _diagnosticar(_disease_release(falseado.name), sede)
    assert len(problemas) == 1
    assert "forecast_base.csv" in problemas[0].message
