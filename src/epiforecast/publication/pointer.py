"""C7.5-PREP — ``public_release_pointer.v1``: qué release estaría publicado, y en qué canales.

Es la pieza que C7.2-A.1 sacó del bundle. Un release describe QUÉ modelos hay y de dónde salen; el
puntero dice DÓNDE se publican. Están separados a propósito:

- apagar un canal edita el puntero y **no** mueve el ``release_id`` ni obliga a reconstruir nada;
- volver al release anterior es reemplazar un puntero, no reconstruir un bundle.

Por eso el rollback es barato y auditable: cambiar de release publicado es cambiar 12 caracteres.

Un puntero **inactivo** (``active=false``) es la forma normal de prepararlo antes de tiempo: existe,
se valida, se versiona… y no publica nada. Activarlo exige ``lifecycle=published``, que es un gate
aparte y posterior.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from epiforecast import registry
from epiforecast.runner.artifact_identity import (
    ArtifactValidationError,
    equal,
    read_json,
    require,
    text_of,
)
from epiforecast.runner.release_contract import canonical_json, sha256_bytes

POINTER_SCHEMA = "public_release_pointer.v1"
POINTER_FILE = "public_release_pointer.json"
LIFECYCLE_PUBLISHED = "published"

# Canales que un release del runner puede alimentar. `weekly_validation` y `prospective_validation`
# pertenecen al carril legacy (tabla_333 y congelado): un release no los produce, así que no puede
# declararlos.
SUPPORTED_CHANNELS: frozenset[str] = frozenset({"web", "epibot", "reports", "tableau"})


@dataclass(frozen=True, slots=True)
class PublicPointer:
    """A qué release apunta la superficie pública, en qué canales, y si está activo."""

    disease_id: str
    release_id: str
    channels: tuple[str, ...]
    gallery_enabled: bool
    active: bool
    lifecycle_required: str = LIFECYCLE_PUBLISHED

    def payload(self) -> dict[str, Any]:
        return {
            "schema": POINTER_SCHEMA,
            "disease_id": self.disease_id,
            "release_id": self.release_id,
            "channels": sorted(self.channels),
            "gallery_enabled": bool(self.gallery_enabled),
            "active": bool(self.active),
            "lifecycle_required": self.lifecycle_required,
        }

    def digest(self) -> str:
        return sha256_bytes(canonical_json(self.payload()))


def _check_channels(channels: tuple[str, ...], disease_id: str) -> tuple[str, ...]:
    require(channels, f"{disease_id}: el puntero no declara ningún canal")
    sobran = sorted(set(channels) - SUPPORTED_CHANNELS)
    require(
        not sobran,
        f"{disease_id}: canales no soportados por un release del runner: {sobran} "
        f"(soportados {sorted(SUPPORTED_CHANNELS)})",
    )
    equal(f"{disease_id}: canales duplicados", len(set(channels)), len(channels))
    return tuple(sorted(channels))


def pointer_for(disease: registry.Disease, *, active: bool = False) -> PublicPointer:
    """Puntero DERIVADO del registry. Inactivo por defecto: preparar no es publicar."""
    require(
        disease.artifact_backend == registry.BACKEND_RUNNER_RELEASE,
        f"{disease.id}: el puntero público exige backend {registry.BACKEND_RUNNER_RELEASE!r}, "
        f"no {disease.artifact_backend!r}",
    )
    return PublicPointer(
        disease_id=disease.id,
        release_id=text_of(disease.artifact_source.release_id, f"{disease.id}: release_id"),
        channels=_check_channels(tuple(disease.channels), disease.id),
        gallery_enabled=bool(disease.gallery_enabled),
        active=active,
    )


def check_activation(pointer: PublicPointer, disease: registry.Disease) -> None:
    """Un puntero ACTIVO exige `lifecycle=published`. Preparado e inactivo, no exige nada."""
    if not pointer.active:
        return
    equal(
        f"{disease.id}: lifecycle para activar el puntero", disease.lifecycle, LIFECYCLE_PUBLISHED
    )
    equal(
        f"{disease.id}: el puntero apunta a otro release",
        pointer.release_id,
        str(disease.artifact_source.release_id),
    )


def write_pointer(
    pointer: PublicPointer, output_root: Path, repo_root_path: Path | None = None
) -> Path:
    """Escribe el puntero en STAGING. Un puntero inactivo jamás toca una ruta pública."""
    from .compiler import check_staging_root

    require(
        not pointer.active,
        f"{pointer.disease_id}: escribir un puntero ACTIVO es publicar; eso es la activación de "
        "C7.5, no su preparación",
    )
    check_staging_root(output_root, repo_root_path)
    destino = output_root / pointer.disease_id / POINTER_FILE
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(canonical_json(pointer.payload()))
    return destino


def read_pointer(path: Path) -> PublicPointer:
    """Lee y valida un puntero; el schema se comprueba primero, como en el resto del contrato."""
    datos = read_json(path, POINTER_FILE, POINTER_SCHEMA)
    activo = datos.get("active")
    galeria = datos.get("gallery_enabled")
    for nombre, valor in (("active", activo), ("gallery_enabled", galeria)):
        if not isinstance(valor, bool):
            raise ArtifactValidationError(f"{POINTER_FILE}: {nombre} debe ser booleano")
    canales = datos.get("channels")
    if not isinstance(canales, list):
        raise ArtifactValidationError(f"{POINTER_FILE}: channels debe ser una lista")
    disease_id = text_of(datos.get("disease_id"), f"{POINTER_FILE}: disease_id")
    return PublicPointer(
        disease_id=disease_id,
        release_id=text_of(datos.get("release_id"), f"{POINTER_FILE}: release_id"),
        channels=_check_channels(tuple(str(c) for c in canales), disease_id),
        gallery_enabled=bool(galeria),
        active=bool(activo),
        lifecycle_required=text_of(
            datos.get("lifecycle_required"), f"{POINTER_FILE}: lifecycle_required"
        ),
    )


def rollback_to(pointer: PublicPointer, release_id: str) -> PublicPointer:
    """Rollback = reemplazar el release al que apunta. No reconstruye ni toca ningún bundle."""
    require(release_id != pointer.release_id, "rollback: el puntero ya apunta a ese release")
    return PublicPointer(
        disease_id=pointer.disease_id,
        release_id=text_of(release_id, "rollback: release_id"),
        channels=pointer.channels,
        gallery_enabled=pointer.gallery_enabled,
        active=pointer.active,
        lifecycle_required=pointer.lifecycle_required,
    )


def pointer_digests(pointers: Mapping[str, PublicPointer]) -> dict[str, str]:
    return {clave: p.digest() for clave, p in sorted(pointers.items())}
