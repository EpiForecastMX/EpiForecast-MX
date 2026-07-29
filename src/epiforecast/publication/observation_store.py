"""Sede portable de datasets de observación prospectiva.

``runs/`` es un workspace local y gitignored. Un estado trackeado no puede apuntar únicamente ahí:
un clon debe poder restaurar el dataset observado desde DVC y recomputar el veredicto. Esta sede
guarda el directorio completo de ``validate-data`` más el reporte semanal y los PDF que lo
originaron; no es una superficie pública ni altera el dataset de entrenamiento congelado.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from epiforecast.runner.artifact_identity import ArtifactValidationError, require
from epiforecast.runner.release_contract import canonical_json

_ROOT = Path(__file__).resolve().parents[3]
OBSERVATIONS_DIR = _ROOT / "artifacts" / "observations"
REPORT_FILE = "prospective_week_report.json"
SOURCE_DIR = "source_bulletins"
TRAINING_DIR = "_training"
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _segment(value: str, label: str) -> str:
    require(bool(_ID.fullmatch(value)), f"{label} inválido: {value!r}")
    return value


def observation_path(disease_id: str, dataset_id: str, *, store_root: Path | None = None) -> Path:
    """Ruta determinista ``<store>/<disease>/<dataset>`` con segmentos fail-closed."""
    return (
        (store_root or OBSERVATIONS_DIR)
        / _segment(disease_id, "disease_id")
        / _segment(dataset_id, "dataset_id")
    )


def tree_digest(root: Path) -> str:
    """Digest estable de rutas relativas + bytes, independiente de mtime y root absoluto."""
    require(root.is_dir(), f"árbol de observación inexistente: {root}")
    digest = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink())
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\0")
    return digest.hexdigest()


def _equivalent_digest(root: Path) -> str:
    """Equivalencia de contenido; ignora sólo telemetría volátil del DatasetManifest."""
    digest = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink())
    for path in files:
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if path.name == "dataset_manifest.json":
            payload = json.loads(data)
            payload.pop("created_at", None)
            payload.pop("code_commit", None)
            data = canonical_json(payload)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
        digest.update(b"\0")
    return digest.hexdigest()


def materialize_observation(
    source_dataset_dir: Path,
    *,
    training_dataset_dir: Path,
    disease_id: str,
    dataset_id: str,
    source_pdfs: Sequence[Path],
    report: Mapping[str, Any],
    store_root: Path | None = None,
) -> Path:
    """Copia la evidencia completa con rename final; repetir exige bytes idénticos."""
    require(source_dataset_dir.is_dir(), f"dataset observado inexistente: {source_dataset_dir}")
    require(
        training_dataset_dir.is_dir(),
        f"dataset de entrenamiento inexistente: {training_dataset_dir}",
    )
    destination = observation_path(disease_id, dataset_id, store_root=store_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{dataset_id}.tmp.", dir=str(destination.parent)))
    try:
        shutil.copytree(source_dataset_dir, temp, dirs_exist_ok=True)
        shutil.copytree(
            training_dataset_dir,
            temp / TRAINING_DIR / training_dataset_dir.name,
        )
        bulletins = temp / SOURCE_DIR
        bulletins.mkdir()
        seen: set[str] = set()
        for source in sorted((Path(p).resolve() for p in source_pdfs), key=lambda p: p.name):
            require(source.is_file(), f"PDF fuente inexistente: {source}")
            require(source.name not in seen, f"PDF fuente repetido por nombre: {source.name}")
            seen.add(source.name)
            shutil.copy2(source, bulletins / source.name)
        (temp / REPORT_FILE).write_bytes(canonical_json(report))

        if destination.exists():
            require(
                _equivalent_digest(destination) == _equivalent_digest(temp),
                f"la observación {dataset_id} ya existe con bytes distintos",
            )
            return destination
        temp.replace(destination)
        return destination
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def effective_raw_path(dataset_dir: Path, raw_digest: str) -> Path:
    """Raw efectivo dentro de ``inputs/``, resuelto por digest y no por un nombre inferido."""
    inputs = dataset_dir / "inputs"
    require(inputs.is_dir(), f"{dataset_dir.name}: falta inputs/")
    matches = [
        path
        for path in inputs.iterdir()
        if path.is_file()
        and not path.is_symlink()
        and hashlib.sha256(path.read_bytes()).hexdigest() == raw_digest
    ]
    require(
        len(matches) == 1,
        f"{dataset_dir.name}: se esperaba un raw efectivo por digest, encontrados {len(matches)}",
    )
    return matches[0]


def resolve_observation_dir(
    disease_id: str,
    dataset_id: str,
    *,
    runs_root: Path,
    store_root: Path | None = None,
) -> Path:
    """Prefiere el run local; si no está, usa la copia portable restaurada por DVC."""
    local = runs_root / _segment(dataset_id, "dataset_id")
    if local.is_dir():
        return local
    portable = observation_path(disease_id, dataset_id, store_root=store_root)
    if portable.is_dir():
        return portable
    raise ArtifactValidationError(
        f"dataset de observación {dataset_id} no está en runs/ ni en {portable}; "
        "restaura su target DVC dirigido"
    )


def resolve_training_dir(
    disease_id: str,
    observation_dataset_id: str,
    training_dataset_id: str,
    *,
    runs_root: Path,
    store_root: Path | None = None,
) -> Path:
    """Dataset congelado local o copia sellada dentro de la observación portable."""
    local = runs_root / _segment(training_dataset_id, "training_dataset_id")
    if local.is_dir():
        return local
    portable = (
        observation_path(disease_id, observation_dataset_id, store_root=store_root)
        / TRAINING_DIR
        / _segment(training_dataset_id, "training_dataset_id")
    )
    if portable.is_dir():
        return portable
    raise ArtifactValidationError(
        f"dataset de entrenamiento {training_dataset_id} no está en runs/ ni en la "
        f"observación portable {observation_dataset_id}"
    )
