"""Escritura exclusiva sin reemplazo (no-replace), staging idempotente y empaquetado de artefactos.

Delega la pre-auditoría de sólo lectura en ``epi_dataset_guard`` y materializa archivos nuevos
mediante temporal exclusivo (``O_CREAT | O_EXCL``) + ``fsync`` + verificación SHA-256 +
``hardlink_to`` (enlace atómico sin reemplazo), preservando archivos existentes idénticos ``0444``
y escribiendo siempre ``manifest.json`` al final como marcador de completitud.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import json
import os
from pathlib import Path
import shutil
from typing import Any, Literal
import uuid

import pandas as pd

from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data.epi_dataset_guard import (
    StagedArtifact,
    preflight_dataset_context,
    sha256_bytes,
    sha256_file,
)
from epiforecast.data.epi_dataset_spec import EpiDatasetConfig, ExposureSnapshot

StagingAction = Literal["verified_noop", "created", "completed_partial"]

__all__ = [
    "StagedArtifact",
    "StagingAction",
    "assemble_dataset_artifacts",
    "stage_dataset_run",
    "stage_file_idempotent",
    "write_exclusive_no_replace",
]


def write_exclusive_no_replace(
    dst: Path,
    content: bytes,
    expected_digest: str,
    *,
    stat_source: Path | None = None,
    error_cls: type[ValueError] = ValueError,
    _before_link_hook: Callable[[Path, Path], None] | None = None,
) -> None:
    """Crea ``dst`` de forma atómica y exclusiva (no-replace) sin tocar archivos previos."""
    if sha256_bytes(content) != expected_digest:
        raise error_cls(f"digest no coincide con contenido a escribir en {dst.name}")
    if dst.is_symlink() or dst.exists():
        raise error_cls(f"el destino ya existe (no-replace): {dst}")
    if dst.parent.is_symlink() or not dst.parent.is_dir():
        raise error_cls(f"directorio padre inválido o enlace simbólico: {dst.parent}")

    tmp_path = dst.parent / f".{dst.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(tmp_path, flags, 0o644)
    except OSError as exc:
        raise error_cls(f"no se pudo crear temporal exclusivo en {dst.parent}: {exc}") from exc

    try:
        view = memoryview(content)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise error_cls(f"escritura incompleta en temporal para {dst}")
            view = view[written:]
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        tmp_path.unlink(missing_ok=True)
        raise
    else:
        os.close(fd)

    try:
        if sha256_file(tmp_path) != expected_digest:
            raise error_cls(f"verificación SHA-256 falló en temporal para {dst}")
        if stat_source is not None:
            shutil.copystat(stat_source, tmp_path, follow_symlinks=True)
        if _before_link_hook is not None:
            _before_link_hook(tmp_path, dst)
        try:
            dst.hardlink_to(tmp_path)
        except FileExistsError as exc:
            raise error_cls(
                f"colisión concurrente al crear {dst}: el destino apareció durante el staging"
            ) from exc
        except OSError as exc:
            raise error_cls(f"no se pudo publicar sin reemplazo {dst}: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)


def stage_file_idempotent(
    dst: Path,
    content: bytes,
    expected_digest: str | None = None,
    *,
    stat_source: Path | None = None,
    error_cls: type[ValueError] = ValueError,
    _before_link_hook: Callable[[Path, Path], None] | None = None,
) -> Literal["verified_noop", "created"]:
    """Verifica NO-OP si ``dst`` existe idéntico (incluso ``0444``); falla si difiere; crea exclusivo."""
    digest = expected_digest if expected_digest is not None else sha256_bytes(content)
    if sha256_bytes(content) != digest:
        raise error_cls(f"digest esperado inconsistente para {dst.name}")
    if dst.is_symlink():
        raise error_cls(f"no se permite enlace simbólico en destino: {dst}")
    if dst.exists():
        if not dst.is_file():
            raise error_cls(f"el destino existente no es archivo regular: {dst}")
        actual_bytes = dst.read_bytes()
        actual_digest = sha256_bytes(actual_bytes)
        if actual_digest != digest or actual_bytes != content:
            raise error_cls(
                f"el archivo existente {dst} difiere del esperado "
                f"({actual_digest} != {digest}); se rehúsa sobrescribir"
            )
        return "verified_noop"

    write_exclusive_no_replace(
        dst,
        content,
        digest,
        stat_source=stat_source,
        error_cls=error_cls,
        _before_link_hook=_before_link_hook,
    )
    return "created"


def stage_dataset_run(
    *,
    run_dir: Path,
    run_id: str,
    disease_id: str,
    digests: Mapping[str, str],
    artifacts: Sequence[StagedArtifact],
    error_cls: type[ValueError] = ValueError,
) -> StagingAction:
    """Materializa o verifica de forma idempotente ``run_dir`` sin sobrescribir archivos previos."""
    verified_count, missing = preflight_dataset_context(
        run_dir=run_dir,
        run_id=run_id,
        disease_id=disease_id,
        digests=digests,
        artifacts=artifacts,
        error_cls=error_cls,
    )
    if not missing:
        return "verified_noop"

    inputs_dir = run_dir / "inputs"
    if run_dir.is_symlink():
        raise error_cls(f"el directorio del dataset no puede ser enlace simbólico: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    if inputs_dir.is_symlink():
        raise error_cls(f"{run_dir.name}: 'inputs' no puede ser enlace simbólico")
    if any(Path(art.rel_path).parts[0] == "inputs" for art in missing):
        inputs_dir.mkdir(parents=True, exist_ok=True)

    # G4: manifest.json es marcador de sellado; se escribe SIEMPRE al final aunque cambie el orden.
    ordered_missing = sorted(missing, key=lambda art: art.rel_path == "manifest.json")
    for art in ordered_missing:
        write_exclusive_no_replace(
            run_dir / art.rel_path,
            art.content,
            art.digest,
            stat_source=art.stat_source,
            error_cls=error_cls,
        )

    return "completed_partial" if verified_count > 0 else "created"


def assemble_dataset_artifacts(
    *,
    run_id: str,
    cfg: EpiDatasetConfig,
    effective_raw_path: Path,
    raw_bytes: bytes,
    raw_digest: str,
    catalog_path: Path,
    catalog_bytes: bytes,
    catalog_digest: str,
    snapshot: ExposureSnapshot,
    config_payload: Mapping[str, Any],
    digests: Mapping[str, str],
    base: pd.DataFrame,
    state: pd.DataFrame,
    dataset_bytes: bytes,
    dataset_digest: str,
) -> tuple[StagedArtifact, ...]:
    """Serializa los 6 artefactos canónicos de ``runs/<run_id>/`` (4 insumos + dataset + manifest)."""
    exp_proj = pd.DataFrame(
        [{"cve_ent": c, **snapshot.by_cve_ent[c]} for c in sorted(snapshot.by_cve_ent)]
    )
    exposure_csv: str = exp_proj.to_csv(index=False)
    exposure_bytes = exposure_csv.encode("utf-8")
    config_bytes = json.dumps(dict(config_payload), indent=2, ensure_ascii=False).encode("utf-8")
    manifest = {
        "run_id": run_id,
        "disease_id": cfg.disease_id,
        "digests": dict(digests),
        "exposure": {
            "source_id": snapshot.source_id,
            "reference": snapshot.reference,
            "cutoff": str(snapshot.cutoff),
        },
        "counts": {
            "base_rows": int(len(base)),
            "state_rows": int(len(state)),
            "series": int(base.groupby([spec.COL_CVE_ENT, spec.COL_SEXO]).ngroups),
            "periods": int(state.groupby([spec.COL_EPI_YEAR, spec.COL_EPI_WEEK]).ngroups),
            "imputed_totals": int((~state["observed"]).sum()),
        },
    }
    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
    return (
        StagedArtifact(
            f"inputs/{effective_raw_path.name}",
            raw_bytes,
            raw_digest,
            stat_source=effective_raw_path,
        ),
        StagedArtifact(
            f"inputs/{catalog_path.name}",
            catalog_bytes,
            catalog_digest,
            stat_source=catalog_path,
        ),
        StagedArtifact(
            f"inputs/exposure_{cfg.exposure_source_id}.csv",
            exposure_bytes,
            sha256_bytes(exposure_bytes),
        ),
        StagedArtifact(
            "inputs/config_effective.json",
            config_bytes,
            sha256_bytes(config_bytes),
        ),
        StagedArtifact("epi_dataset_v2.csv", dataset_bytes, dataset_digest),
        StagedArtifact("manifest.json", manifest_bytes, sha256_bytes(manifest_bytes)),
    )
