"""C7.2-A/R15.2+R15.6 — matriz de RECHAZO del release bundle.

Un bundle sólo es evidencia si romperlo se nota. Aquí se muta una copia del bundle prístino y se
exige un ``ArtifactValidationError`` con el mensaje correcto: ningún traceback, ningún verde por
descuido y —sobre todo— ningún fallo que se resuelva en el sello cuando lo que se quiere probar es
la IDENTIDAD o el CONTENIDO.

Por eso hay tres grupos con re-sellado distinto:

| grupo | re-sellado | qué debe atrapar la mutación |
| --- | --- | --- |
| sello | ninguno | inventario, digests, tamaños y ``SHA256SUMS.txt`` |
| identidad | sólo checksums | el ``release_id`` recalculado deja de cuadrar |
| contenido | inventario + identidad + checksums | los sellos INTERNOS de los runs de origen |
"""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path

import pytest

from epiforecast.runner import adapters
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_contract import CHECKSUMS_FILE, MANIFEST_FILE
from epiforecast.runner.release_loader import verify_bundle
from epiforecast.runner.release_runtime import RUNTIME_CONFIG_FILE, RUNTIME_DIR
from tests.unit.runner import artifact_fixtures as af
from tests.unit.runner import release_fixtures as rf

pytestmark = pytest.mark.skipif(
    not af.hay_runs(), reason="los runs sellados de C5 no están en este entorno (runs/ gitignored)"
)

Mutacion = Callable[[Path], None]


@pytest.fixture(scope="module")
def prístino(tmp_path_factory) -> Path:
    return rf.construir(tmp_path_factory.mktemp("release")).path


def _copia(prístino: Path, tmp_path: Path) -> Path:
    return rf.copia(prístino, tmp_path / "bundle")


def _añadir(path: Path) -> None:
    path.write_bytes(path.read_bytes() + b"\n")


def _payload(root: Path, sufijo: str) -> Path:
    return sorted(p for p in root.rglob(f"*{sufijo}") if p.is_file())[0]


# ── Grupo 1: el sello del release ─────────────────────────────────────────────────────────────
def _borrar_payload(root: Path) -> None:
    (root / "forecast" / "lineage.json").unlink()


def _archivo_intruso(root: Path) -> None:
    (root / "forecast" / "colado.csv").write_text("intruso\n", encoding="utf-8")


def _alterar_payload(root: Path) -> None:
    _añadir(root / "forecast" / "forecast.csv")


def _alterar_checksums(root: Path) -> None:
    texto = (root / CHECKSUMS_FILE).read_text(encoding="utf-8")
    (root / CHECKSUMS_FILE).write_text(texto.replace("a", "b", 1), encoding="utf-8")


def _borrar_checksums(root: Path) -> None:
    (root / CHECKSUMS_FILE).unlink()


def _checksums_autorreferentes(root: Path) -> None:
    with (root / CHECKSUMS_FILE).open("a", encoding="utf-8") as fh:
        fh.write(f"{'0' * 64}  {CHECKSUMS_FILE}\n")


def _checksums_incompletos(root: Path) -> None:
    lineas = (root / CHECKSUMS_FILE).read_text(encoding="utf-8").splitlines(keepends=True)
    (root / CHECKSUMS_FILE).write_text("".join(lineas[1:]), encoding="utf-8")


def _borrar_manifest(root: Path) -> None:
    (root / MANIFEST_FILE).unlink()


def _digest_falso(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["payloads"][0]["sha256"] = "0" * 64
    rf.escribir_manifest(root, manifest)


def _tamaño_falso(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["payloads"][0]["bytes"] = 1
    rf.escribir_manifest(root, manifest)


def _schema_desconocido(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["schema"] = "release_manifest.v99"
    rf.escribir_manifest(root, manifest)


def _ruta_absoluta(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["payloads"][0]["path"] = "/etc/passwd"
    rf.escribir_manifest(root, manifest)


def _traversal(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["payloads"][0]["path"] = "../fuera.csv"
    rf.escribir_manifest(root, manifest)


def _payload_duplicado(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["payloads"].append(dict(manifest["payloads"][0]))
    rf.escribir_manifest(root, manifest)


def _sin_payloads(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["payloads"] = []
    rf.escribir_manifest(root, manifest)


SELLO: list[tuple[Mutacion, str]] = [
    (_borrar_payload, "faltan"),
    (_archivo_intruso, "no declarados"),
    (_alterar_payload, "digest de"),
    (_alterar_checksums, "SHA256SUMS"),
    (_borrar_checksums, r"faltan 1 archivos declarados.*SHA256SUMS\.txt"),
    (_checksums_autorreferentes, "no puede incluirse a sí mismo"),
    (_checksums_incompletos, "cobertura de SHA256SUMS.txt"),
    (_borrar_manifest, "falta release_manifest.json"),
    (_digest_falso, "digest de"),
    (_tamaño_falso, "tamaño de"),
    (_schema_desconocido, "schema"),
    (_ruta_absoluta, "es absoluta"),
    (_traversal, "traversal"),
    (_payload_duplicado, "declarada dos veces"),
    (_sin_payloads, "no declara payloads"),
]


@pytest.mark.parametrize(("mutacion", "patron"), SELLO, ids=[m.__name__ for m, _ in SELLO])
def test_el_sello_del_release_atrapa_la_mutación(prístino, tmp_path, mutacion, patron):
    root = _copia(prístino, tmp_path)
    mutacion(root)
    with pytest.raises(ArtifactValidationError, match=patron):
        verify_bundle(root)


# ── Grupo 2: identidad recalculada (se rehacen los checksums a propósito) ─────────────────────
def _chain_alterada(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["chain"]["dataset_digest"] = "f" * 64
    rf.escribir_manifest(root, manifest)


def _activación_alterada(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["activation"]["channels_candidate"] = ["web"]
    rf.escribir_manifest(root, manifest)


def _activada_a_mano(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["activation"]["activated"] = True
    rf.escribir_manifest(root, manifest)


def _disease_alterado(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["disease_id"] = "otro_padecimiento"
    rf.escribir_manifest(root, manifest)


def _release_id_falso(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["release_id"] = f"{af.DISEASE}_release_{'0' * 12}"
    rf.escribir_manifest(root, manifest)


def _identity_digest_falso(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["identity_digest"] = "0" * 64
    rf.escribir_manifest(root, manifest)


IDENTIDAD: list[tuple[Mutacion, str]] = [
    (_chain_alterada, "release_id"),
    (_activación_alterada, "release_id"),
    (_activada_a_mano, "release_id"),
    (_disease_alterado, "release_id"),
    (_release_id_falso, "release_id"),
    (_identity_digest_falso, "identity_digest"),
]


@pytest.mark.parametrize(("mutacion", "patron"), IDENTIDAD, ids=[m.__name__ for m, _ in IDENTIDAD])
def test_la_identidad_recalculada_atrapa_la_mutación(prístino, tmp_path, mutacion, patron):
    """Aunque se rehagan las sumas, el ``release_id`` vuelve a calcularse y deja de cuadrar."""
    root = _copia(prístino, tmp_path)
    mutacion(root)
    rf.resellar_checksums(root)
    with pytest.raises(ArtifactValidationError, match=patron):
        verify_bundle(root)


# ── Grupo 3: contenido, con el release RE-SELLADO entero ─────────────────────────────────────
def _estado_alterado(root: Path) -> None:
    _añadir(rf.un_estado(root))


def _envelope_alterado(root: Path) -> None:
    path = rf.un_envelope(root)
    datos = json.loads(path.read_text(encoding="utf-8"))
    datos["n_train"] = 1
    path.write_text(json.dumps(datos, indent=2, sort_keys=True), encoding="utf-8")


def _selección_alterada(root: Path) -> None:
    _añadir(root / "selection" / "final_selection.csv")


def _veredicto_alterado(root: Path) -> None:
    _añadir(root / "selection" / "acceptance.json")


def _resumen_alterado(root: Path) -> None:
    _añadir(root / "refit" / "refit_summary.json")


def _forecast_alterado(root: Path) -> None:
    _añadir(root / "forecast" / "forecast.csv")


def _catálogo_alterado(root: Path) -> None:
    _añadir(_payload(root / RUNTIME_DIR, "entidades_mx.csv"))


def _exposición_alterada(root: Path) -> None:
    _añadir(_payload(root / RUNTIME_DIR, "static.csv"))


def _motor_de_menos(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["engines"].pop(sorted(manifest["engines"])[0])
    rf.escribir_manifest(root, manifest)


def _runtime_inputs_incompleto(root: Path) -> None:
    manifest = rf.leer_manifest(root)
    manifest["runtime_inputs"] = manifest["runtime_inputs"][:1]
    rf.escribir_manifest(root, manifest)


def _runtime_config_sin_contraste(root: Path) -> None:
    path = root / RUNTIME_DIR / RUNTIME_CONFIG_FILE
    datos = json.loads(path.read_text(encoding="utf-8"))
    datos["exposure"]["dataset_check"]["verified"] = False
    path.write_text(json.dumps(datos, sort_keys=True), encoding="utf-8")


def _runtime_config_de_otro_dataset(root: Path) -> None:
    path = root / RUNTIME_DIR / RUNTIME_CONFIG_FILE
    datos = json.loads(path.read_text(encoding="utf-8"))
    datos["exposure"]["dataset_check"]["dataset_digest"] = "e" * 64
    path.write_text(json.dumps(datos, sort_keys=True), encoding="utf-8")


CONTENIDO: list[tuple[Mutacion, str]] = [
    (_estado_alterado, "no cargables"),
    (_envelope_alterado, "no cargables"),
    (_selección_alterada, "digest de final_selection.csv"),
    (_veredicto_alterado, "digest de acceptance.json"),
    (_resumen_alterado, "digest de refit_summary.json"),
    (_forecast_alterado, "digest de forecast.csv"),
    (_catálogo_alterado, "catálogo: digest"),
    (_exposición_alterada, "exposición: digest"),
    (_motor_de_menos, "reparto por motor"),
    (_runtime_inputs_incompleto, "runtime_inputs"),
    (_runtime_config_sin_contraste, "no se contrastó"),
    (_runtime_config_de_otro_dataset, "dataset_digest"),
]


@pytest.mark.parametrize(("mutacion", "patron"), CONTENIDO, ids=[m.__name__ for m, _ in CONTENIDO])
def test_los_sellos_internos_atrapan_la_mutación(prístino, tmp_path, mutacion, patron):
    """Con el release entero re-sellado, sólo puede salvarlo la identidad SELLADA de los runs."""
    root = _copia(prístino, tmp_path)
    mutacion(root)
    rf.resellar(root)
    with pytest.raises(ArtifactValidationError, match=patron):
        verify_bundle(root)


# ── Grupo 4: la capacidad de forecast del motor ──────────────────────────────────────────────
def test_un_motor_sin_capacidad_de_forecast_final_invalida_el_release(
    prístino, tmp_path, monkeypatch
):
    """R15.4: nunca se sustituye por otro motor; el release deja de ser cargable."""
    root = _copia(prístino, tmp_path)
    from epiforecast.runner.release_loader import bootstrap_engines

    bootstrap_engines()
    engine = sorted(rf.leer_manifest(root)["engines"])[0]
    monkeypatch.delitem(adapters._ADAPTERS, engine)
    with pytest.raises(ArtifactValidationError, match="no está registrado"):
        verify_bundle(root)


def test_el_bundle_prístino_sigue_verificando_después_de_todas_las_mutaciones(prístino):
    """Guardia: si el prístino se hubiera contaminado, toda la matriz de arriba sería ruido."""
    assert verify_bundle(prístino).release_id == prístino.name
