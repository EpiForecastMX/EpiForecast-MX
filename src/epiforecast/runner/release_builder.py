"""C7.2-A/R15.3 — builder de un release bundle inmutable, determinista y sin nada del workspace.

Recibe identidad ya verificada (``VerifiedRunnerRuns``), rutas fuente tipadas (``ReleaseSources``) y
un root de salida; copia los bytes DECLARADOS re-comprobando sus digests, genera únicamente metadata
canónica (``release_manifest``) y sella el bundle. No conoce ningún padecimiento, motor ni conteo.

Orden obligatorio, sin ciclos: payloads → ``identity_payload.v2`` → ``release_id`` →
``release_manifest.json`` → ``SHA256SUMS.txt``. La hora de construcción no participa en nada.

Se construye SIEMPRE en un staging temporal dentro del root de salida y sólo se promueve —con un
rename atómico— después de que el bundle se verifique entero: nunca queda un release a medias.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import filecmp
from pathlib import Path
import shutil
import tempfile
from typing import TYPE_CHECKING, Any

from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    require,
    sha256_file,
)
from epiforecast.runner.release_contract import (
    CHECKSUMS_FILE,
    MANIFEST_FILE,
    build_checksums,
    canonical_json,
    check_bundle_path,
    sha256_bytes,
)
from epiforecast.runner.release_manifest import (
    RUNTIME_CONFIG_PATH,
    build_manifest,
    dataset_digests,
)
from epiforecast.runner.release_runtime import (
    RUNTIME_DIR,
    build_runtime_config,
    read_projected_exposure,
)
from epiforecast.runner.release_sources import (
    PayloadEntry,
    ReleaseSources,
    dataset_exposure,
    payload_plan,
    read_dataset_config,
)

if TYPE_CHECKING:  # sólo para tipar; en runtime lo pasa el llamador
    from epiforecast.runner.artifact_validation import VerifiedRunnerRuns

__all__ = ["BuiltRelease", "build_release"]


@dataclass(frozen=True, slots=True)
class BuiltRelease:
    """Resultado del build: dónde quedó, con qué identidad y cuántos payloads lleva."""

    release_id: str
    identity_digest: str
    path: Path
    payloads: int
    reused: bool


def _copy_payloads(entries: Sequence[PayloadEntry], destino: Path) -> dict[str, str]:
    """Copia bytes y devuelve ``ruta -> sha256``, re-verificando cada digest DECLARADO (R15-C2)."""
    digests: dict[str, str] = {}
    for entrada in entries:
        ruta = check_bundle_path(entrada.bundle_path, "payload")
        salida = destino / ruta
        salida.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(entrada.source_path, salida)  # sin modo ni mtime: sólo contenido
        except OSError as exc:
            raise ArtifactValidationError(f"payload {ruta}: no se pudo copiar ({exc})") from exc
        digest = sha256_file(salida, f"payload {ruta}")
        if entrada.declared_digest is not None:
            equal(f"payload {ruta}: digest declarado", digest, entrada.declared_digest)
        digests[ruta] = digest
    return digests


def _runtime_config(
    verified: VerifiedRunnerRuns,
    sources: ReleaseSources,
    destino: Path,
    digests: Mapping[str, str],
) -> dict[str, Any]:
    """``runtime_config.v1`` + contraste OBLIGATORIO de la exposición contra el dataset sellado."""
    dataset_config = read_dataset_config(sources, dataset_digests(sources, "config"))
    catalog_rel = f"{RUNTIME_DIR}/{sources.catalog_path.name}"
    exposure_rel = f"{RUNTIME_DIR}/{sources.exposure_path.name}"
    config = build_runtime_config(
        disease_id=verified.disease_id,
        dataset_config=dataset_config,
        catalog_path=catalog_rel,
        catalog_digest=digests[catalog_rel],
        exposure_path=exposure_rel,
        exposure_digest=digests[exposure_rel],
        dataset_id=verified.dataset_id,
        dataset_digest=dataset_digests(sources, "dataset"),
        n_series=verified.n_models,
    )
    geografias = sorted({geo for geo, _ in verified.series})
    proyectada = read_projected_exposure(
        destino / exposure_rel,
        config["exposure"]["columns_by_sex"],
        config["exposure"]["total_column"],
        geografias,
        "release: exposición proyectada",
    )
    sellada = dataset_exposure(sources, geografias)
    discrepan = sorted(k for k in sellada if proyectada.get(k) != sellada[k])
    require(
        not discrepan and sorted(proyectada) == sorted(sellada),
        f"release: la exposición proyectada no coincide con la sellada en el dataset "
        f"({len(discrepan)} series, p.ej. {discrepan[:3]})",
    )
    return config


def _diff_trees(izq: Path, der: Path) -> list[str]:
    """Rutas que sobran, faltan o difieren BYTE a byte entre dos árboles."""
    izquierda = {p.relative_to(izq).as_posix() for p in izq.rglob("*") if p.is_file()}
    derecha = {p.relative_to(der).as_posix() for p in der.rglob("*") if p.is_file()}
    distintos = [
        ruta
        for ruta in sorted(izquierda & derecha)
        if not filecmp.cmp(izq / ruta, der / ruta, shallow=False)
    ]
    return sorted(izquierda ^ derecha) + distintos


def _finalize(staging: Path, output_root: Path, release_id: str) -> tuple[Path, bool]:
    """Idempotente: si el destino ya existe IDÉNTICO se reutiliza; si difiere, se rechaza."""
    destino = output_root / release_id
    if not destino.exists():
        output_root.mkdir(parents=True, exist_ok=True)
        staging.replace(destino)  # atómico dentro del mismo root: nunca hay un bundle a medias
        return destino, False
    diferencias = _diff_trees(staging, destino)
    require(
        not diferencias,
        f"release {release_id}: el destino ya existe con contenido distinto ({diferencias[:3]})",
    )
    shutil.rmtree(staging, ignore_errors=True)
    return destino, True


def build_release(
    *,
    verified: VerifiedRunnerRuns,
    sources: ReleaseSources,
    output_root: Path,
) -> BuiltRelease:
    """Construye el bundle bajo ``output_root/<release_id>/`` y lo valida antes de devolverlo."""
    from epiforecast.runner.release_loader import verify_bundle

    output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=output_root, prefix=".staging-"))
    try:
        entradas = payload_plan(verified, sources)
        digests = _copy_payloads(entradas, staging)
        crudo = canonical_json(_runtime_config(verified, sources, staging, digests))
        (staging / RUNTIME_CONFIG_PATH).write_bytes(crudo)
        digests[RUNTIME_CONFIG_PATH] = sha256_bytes(crudo)

        manifiesto = build_manifest(verified, sources, entradas, digests, staging)
        bytes_manifest = canonical_json(manifiesto)
        (staging / MANIFEST_FILE).write_bytes(bytes_manifest)
        (staging / CHECKSUMS_FILE).write_bytes(
            build_checksums({**digests, MANIFEST_FILE: sha256_bytes(bytes_manifest)})
        )
        # Validar ANTES de declarar éxito: un bundle que no carga no es un release.
        verify_bundle(staging)
        destino, reutilizado = _finalize(staging, output_root, manifiesto["release_id"])
    except IO_ERRORS:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return BuiltRelease(
        release_id=manifiesto["release_id"],
        identity_digest=manifiesto["identity_digest"],
        path=destino,
        payloads=len(digests),
        reused=reutilizado,
    )
