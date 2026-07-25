"""C7.2-A/R15.5 — comprobaciones ESTRUCTURALES de un release bundle (inventario, sumas, identidad).

Es la capa que no sabe nada de modelos ni de forecast: sólo exige que el directorio sea exactamente
lo que su manifest declara, que ``SHA256SUMS.txt`` lo cubra sin cubrirse a sí mismo y que el
``release_id`` VUELVA A SALIR del payload de identidad. Si algo de esto falla, abrir los modelos
sería mirar un artefacto que ya no es el que se firmó.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    int_of,
    mapping_of,
    read_json,
    require,
    sequence_of,
    sha256_file,
    text_of,
)
from epiforecast.runner.release_contract import (
    CHECKSUMS_FILE,
    MANIFEST_FILE,
    MANIFEST_KEYS,
    check_bundle_path,
    check_digest,
    check_no_activation,
    identity_payload,
    parse_checksums,
    release_id_for,
)

SCHEMA_RUN_MANIFEST = "run_manifest.v1"
STATUS_SUCCEEDED = "succeeded"

# ruta -> (sha256, bytes, schema)
Inventory = dict[str, tuple[str, int, str]]


def payload_inventory(manifest: Mapping[str, Any]) -> Inventory:
    """``ruta -> (sha256, bytes, schema)`` declarado por el manifest, sin autorreferencias."""
    who = f"{MANIFEST_FILE}: payloads"
    inventario: Inventory = {}
    for crudo in sequence_of(manifest.get("payloads"), who):
        registro = mapping_of(crudo, f"{who}[]")
        ruta = check_bundle_path(registro.get("path"), who)
        require(ruta not in inventario, f"{who}: ruta declarada dos veces: {ruta}")
        inventario[ruta] = (
            check_digest(registro.get("sha256"), f"{who}: {ruta}"),
            int_of(registro.get("bytes"), f"{who}: bytes de {ruta}"),
            text_of(registro.get("schema"), f"{who}: schema de {ruta}"),
        )
    require(inventario, f"{who}: el release no declara payloads")
    return inventario


def check_inventory(root: Path, inventario: Mapping[str, tuple[str, int, str]]) -> None:
    """El bundle contiene EXACTAMENTE lo declarado más manifest y checksums: ni un archivo más."""
    presentes = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    esperados = {*inventario, MANIFEST_FILE, CHECKSUMS_FILE}
    sobran, faltan = sorted(presentes - esperados), sorted(esperados - presentes)
    require(not faltan, f"release: faltan {len(faltan)} archivos declarados, p.ej. {faltan[:3]}")
    require(not sobran, f"release: {len(sobran)} archivos no declarados, p.ej. {sobran[:3]}")
    for ruta, (digest, tamano, _) in inventario.items():
        path = root / ruta
        equal(f"release: digest de {ruta}", sha256_file(path, ruta), digest)
        equal(f"release: tamaño de {ruta}", path.stat().st_size, tamano)


def check_checksums(root: Path, inventario: Mapping[str, tuple[str, int, str]]) -> None:
    """``SHA256SUMS.txt`` cubre payloads + manifest y NUNCA se cubre a sí mismo."""
    path = root / CHECKSUMS_FILE
    require(path.is_file(), f"release: falta {CHECKSUMS_FILE}")
    try:
        texto = path.read_text(encoding="utf-8")
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"release: {CHECKSUMS_FILE} ilegible ({exc})") from exc
    declarados = parse_checksums(texto, "release")
    esperado = {ruta: digest for ruta, (digest, _, _) in inventario.items()}
    esperado[MANIFEST_FILE] = sha256_file(root / MANIFEST_FILE, MANIFEST_FILE)
    equal(f"release: cobertura de {CHECKSUMS_FILE}", sorted(declarados), sorted(esperado))
    for ruta, digest in esperado.items():
        equal(f"release: {CHECKSUMS_FILE}: digest de {ruta}", declarados[ruta], digest)


def check_manifest_shape(manifest: Mapping[str, Any]) -> None:
    """El manifest declara EXACTAMENTE sus claves: nada puede crecerle sin mover el ``release_id``.

    Sin este cierre, un manifest podía ganar campos que la identidad no cubre —empezando por los de
    activación pública— y seguir verificando. Con él, cualquier añadido es un error de contrato.
    """
    equal(f"{MANIFEST_FILE}: claves", sorted(manifest), sorted(MANIFEST_KEYS))
    check_no_activation(manifest, MANIFEST_FILE)


def check_identity(manifest: Mapping[str, Any], digests: Mapping[str, str]) -> tuple[str, str]:
    """El ``release_id`` se RECALCULA desde el payload de identidad: no se cree el declarado."""
    cadena = {
        text_of(k, f"{MANIFEST_FILE}: chain"): text_of(v, f"{MANIFEST_FILE}: chain[{k!r}]")
        for k, v in mapping_of(manifest.get("chain"), f"{MANIFEST_FILE}: chain").items()
    }
    check_no_activation(cadena, f"{MANIFEST_FILE}: chain")
    identidad = identity_payload(
        disease_id=text_of(manifest.get("disease_id"), f"{MANIFEST_FILE}: disease_id"),
        chain=cadena,
        payloads=digests,
    )
    release_id, identity_digest = release_id_for(identidad)
    equal(f"{MANIFEST_FILE}: release_id", manifest.get("release_id"), release_id)
    equal(f"{MANIFEST_FILE}: identity_digest", manifest.get("identity_digest"), identity_digest)
    return release_id, identity_digest


def check_run_manifest(
    root: Path,
    prefix: str,
    manifest_name: str,
    *,
    run_id: str,
    disease_id: str,
    command: str,
    required: set[str],
    digests: Mapping[str, str],
) -> None:
    """El manifiesto sellado del run de origen sigue describiendo lo que el bundle contiene."""
    who = f"release/{prefix}: {manifest_name}"
    man = read_json(root / prefix / manifest_name, who, SCHEMA_RUN_MANIFEST)
    equal(f"{who}: run_id", man.get("run_id"), run_id)
    equal(f"{who}: disease_id", man.get("disease_id"), disease_id)
    equal(f"{who}: command", man.get("command"), command)
    equal(f"{who}: status", man.get("status"), STATUS_SUCCEEDED)
    grupos = [sequence_of(man.get("artifacts") or [], f"{who}: artifacts")]
    for engine, job in mapping_of(man.get("jobs") or {}, f"{who}: jobs").items():
        datos = mapping_of(job, f"{who}/{engine}")
        equal(f"{who}/{engine}: status", datos.get("status"), STATUS_SUCCEEDED)
        grupos.append(sequence_of(datos.get("artifacts") or [], f"{who}/{engine}: artifacts"))
    vistos: set[str] = set()
    for registros in grupos:
        for crudo in registros:
            registro = mapping_of(crudo, f"{who}: artifacts[]")
            relativo = text_of(registro.get("path"), f"{who}: path")
            ruta = f"{prefix}/{relativo}"
            if ruta not in digests:
                continue  # el bundle no lleva los parciales por job: sólo lo publicable
            vistos.add(relativo)
            equal(
                f"{who}: digest de {relativo}",
                digests[ruta],
                text_of(registro.get("digest"), f"{who}: digest de {relativo}"),
            )
    faltan = sorted(required - vistos)
    require(not faltan, f"{who}: el manifiesto no sella {faltan}")
