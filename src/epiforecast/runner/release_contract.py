"""C7.2-A — identidad ACÍCLICA y serialización canónica de un release bundle del runner.

El ``release_id`` sale de un ``identity_payload.v2`` que NO contiene el manifest ni los checksums:
calcularlo sobre el manifest que lo lleva dentro, o sobre ``SHA256SUMS.txt``, crearía una
dependencia circular. El orden obligatorio es identity → ``release_id`` → manifest → checksums.

Todo el orden se fija con ``sorted()`` de Python sobre rutas POSIX relativas (comparación por punto
de código): la sección 20 del plan documenta cómo ``sort`` de shell cambia de resultado con
``LC_COLLATE`` y movía un digest agregado sin que cambiara un solo byte.

Genérico: ningún padecimiento, motor, conteo ni ruta del workspace aparece aquí. Toda entrada
inválida se convierte en ``ArtifactValidationError`` (la misma frontera tipada de C7.1).
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import PurePosixPath
import re
from typing import Any

from epiforecast.runner.artifact_identity import (
    ArtifactValidationError,
    equal,
    require,
    text_of,
)

RELEASE_SCHEMA = "release_manifest.v2"
IDENTITY_SCHEMA = "identity_payload.v2"
RUNTIME_CONFIG_SCHEMA = "runtime_config.v1"
# C7.2-A.1: v2 saca la metadata de activación de la identidad. Va DENTRO del payload de identidad,
# así que un bundle construido con v1 y otro con v2 nunca comparten `release_id`.
BUILDER_VERSION = "runner_release_builder.v2"

MANIFEST_FILE = "release_manifest.json"
CHECKSUMS_FILE = "SHA256SUMS.txt"
# El portafolio C5 es point-only: los motores no producen intervalos homogéneos y no se inventan.
INTERVAL_METHOD_NONE = "none"
# Los dos archivos que se describen a sí mismos: nunca entran al inventario de payloads.
SELF_DESCRIBING: tuple[str, str] = (MANIFEST_FILE, CHECKSUMS_FILE)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SEPARATOR = "  "  # coreutils: digest + dos espacios + ruta

# Claves EXACTAS del payload de identidad. Cerrado a propósito: nada del entorno puede colarse, y
# tampoco nada de POLÍTICA PÚBLICA (canales, galería, lifecycle, activado). Ver ACTIVATION_KEYS.
IDENTITY_KEYS: frozenset[str] = frozenset(
    {
        "schema",
        "release_schema",
        "builder_version",
        "disease_id",
        "chain",
        "payloads",
    }
)

# Claves EXACTAS del manifest. Es un conjunto cerrado por la misma razón: sin él, el manifest podría
# crecer campos no verificados —empezando por los de activación— sin mover el `release_id`.
MANIFEST_KEYS: frozenset[str] = frozenset(
    {
        "schema",
        "release_id",
        "identity_schema",
        "identity_digest",
        "builder_version",
        "disease_id",
        "chain",
        "calendar",
        "counts",
        "engines",
        "intervals",
        "runtime_inputs",
        "payloads",
    }
)

# Metadata de ACTIVACIÓN PÚBLICA: canales, galería, lifecycle y estado de activación. NO pertenece
# al bundle (C7.2-A.1). Un release describe QUÉ modelos hay y de dónde salen; dónde se publican es
# una decisión posterior y revocable que vivirá en el `public_release_pointer.v1` de C7.5,
# apuntando al `release_id` por referencia. Acoplarlas obligaría a reconstruir —y a renombrar— un
# bundle cuyos modelos no cambiaron sólo por encender o apagar un canal.
ACTIVATION_KEYS: frozenset[str] = frozenset(
    {"activation", "channels", "channels_candidate", "gallery", "gallery_enabled", "lifecycle"}
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(payload: Mapping[str, Any]) -> bytes:
    """JSON canónico: UTF-8, claves ordenadas, separadores estables y salto de línea final."""
    try:
        texto = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ArtifactValidationError(
            f"payload no serializable como JSON canónico ({exc})"
        ) from exc
    return (texto + "\n").encode("utf-8")


def check_bundle_path(raw: object, label: str) -> str:
    """Ruta POSIX RELATIVA dentro del bundle: sin absolutos, traversal, ``.``, vacíos ni ``\\``."""
    ruta = text_of(raw, f"{label}: ruta")
    require("\\" not in ruta, f"{label}: {ruta!r} usa separador de Windows")
    require(not ruta.startswith("/"), f"{label}: {ruta!r} es absoluta")
    require(ruta == ruta.strip(), f"{label}: {ruta!r} tiene espacios al borde")
    partes = ruta.split("/")
    require(all(partes), f"{label}: {ruta!r} tiene un segmento vacío")
    require(
        not any(p in (".", "..") for p in partes), f"{label}: {ruta!r} sale del bundle (traversal)"
    )
    equal(f"{label}: ruta normalizada", str(PurePosixPath(ruta)), ruta)
    return ruta


def check_digest(raw: object, label: str) -> str:
    digest = text_of(raw, f"{label}: digest")
    require(
        _SHA256.match(digest), f"{label}: {digest!r} no es un sha256 hexadecimal en minúsculas"
    )
    return digest


def _payload_inventory(raw: object, label: str) -> dict[str, str]:
    """Inventario ``ruta -> sha256`` validado y ordenado; el manifest y los checksums NO caben."""
    if not isinstance(raw, Mapping):
        raise ArtifactValidationError(f"{label}: se esperaba un mapeo ruta → digest")
    require(raw, f"{label}: sin payloads")
    inventario: dict[str, str] = {}
    for ruta_cruda, digest_crudo in raw.items():
        ruta = check_bundle_path(ruta_cruda, label)
        require(
            ruta not in SELF_DESCRIBING,
            f"{label}: {ruta} se describe a sí mismo y no puede ser un payload",
        )
        require(ruta not in inventario, f"{label}: ruta declarada dos veces: {ruta}")
        inventario[ruta] = check_digest(digest_crudo, f"{label}: {ruta}")
    return dict(sorted(inventario.items()))


def identity_payload(
    *, disease_id: str, chain: Mapping[str, str], payloads: Mapping[str, str]
) -> dict[str, Any]:
    """``identity_payload.v2``: lo ÚNICO de lo que puede depender el ``release_id``.

    Lleva la cadena sellada (dataset/política/selección/aceptación/refit/forecast) y el digest de
    CADA payload. Un byte distinto en cualquier archivo del bundle mueve el ID; el manifest y los
    checksums, que contienen el ID, quedan fuera para no crear un ciclo.

    Lo que tampoco entra —y ésa es la corrección de C7.2-A.1— es la POLÍTICA DE PUBLICACIÓN. Los
    modelos de un release no cambian porque se encienda un canal, así que encender un canal no puede
    cambiar su identidad ni obligar a reconstruirlo.
    """
    who = "identity_payload"
    return {
        "schema": IDENTITY_SCHEMA,
        "release_schema": RELEASE_SCHEMA,
        "builder_version": BUILDER_VERSION,
        "disease_id": text_of(disease_id, f"{who}: disease_id"),
        "chain": {
            text_of(k, f"{who}: chain"): text_of(v, f"{who}: chain[{k!r}]")
            for k, v in sorted(chain.items())
        },
        "payloads": _payload_inventory(payloads, f"{who}: payloads"),
    }


def check_no_activation(data: Mapping[str, Any], label: str) -> None:
    """Ninguna clave de activación pública puede aparecer en el bundle (C7.2-A.1)."""
    intrusas = sorted(ACTIVATION_KEYS & set(data))
    require(
        not intrusas,
        f"{label}: {intrusas} es metadata de activación pública y no pertenece al release "
        f"(vivirá en el public_release_pointer.v1 de C7.5, por referencia al release_id)",
    )


def release_id_for(identity: Mapping[str, Any]) -> tuple[str, str]:
    """``(release_id, identity_digest)`` desde el payload canónico. Sin ciclos ni fechas."""
    equal("identity_payload: claves", sorted(identity), sorted(IDENTITY_KEYS))
    equal("identity_payload: schema", identity.get("schema"), IDENTITY_SCHEMA)
    disease_id = text_of(identity.get("disease_id"), "identity_payload: disease_id")
    digest = sha256_bytes(canonical_json(identity))
    return f"{disease_id}_release_{digest[:12]}", digest


def build_checksums(entries: Mapping[str, str]) -> bytes:
    """``SHA256SUMS.txt`` sobre payloads + manifest, ordenado por ``sorted()`` y sin autorreferencia."""
    who = CHECKSUMS_FILE
    lineas: list[str] = []
    vistos: set[str] = set()
    for ruta_cruda, digest_crudo in sorted(entries.items()):
        ruta = check_bundle_path(ruta_cruda, who)
        require(ruta != CHECKSUMS_FILE, f"{who}: no puede incluirse a sí mismo")
        require(ruta not in vistos, f"{who}: ruta declarada dos veces: {ruta}")
        vistos.add(ruta)
        lineas.append(f"{check_digest(digest_crudo, f'{who}: {ruta}')}{_SEPARATOR}{ruta}\n")
    require(lineas, f"{who}: sin entradas")
    return "".join(lineas).encode("utf-8")


def parse_checksums(text: str, label: str) -> dict[str, str]:
    """Lee ``SHA256SUMS.txt`` fail-closed: formato exacto, sin duplicados ni autorreferencia."""
    who = f"{label}: {CHECKSUMS_FILE}"
    require(text.strip(), f"{who}: archivo vacío")
    entradas: dict[str, str] = {}
    for numero, linea in enumerate(text.splitlines(), start=1):
        donde = f"{who}: línea {numero}"
        require(linea, f"{donde}: vacía")
        partes = linea.split(_SEPARATOR, 1)
        require(len(partes) == 2, f"{donde}: se esperaba 'digest{_SEPARATOR}ruta'")
        digest = check_digest(partes[0], donde)
        ruta = check_bundle_path(partes[1], donde)
        require(ruta != CHECKSUMS_FILE, f"{donde}: {CHECKSUMS_FILE} no puede incluirse a sí mismo")
        require(ruta not in entradas, f"{who}: ruta declarada dos veces: {ruta}")
        entradas[ruta] = digest
    require(entradas, f"{who}: sin entradas")
    return entradas
