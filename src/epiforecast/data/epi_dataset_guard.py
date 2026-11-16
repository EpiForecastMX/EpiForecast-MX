"""Verificación pre-vuelo de sólo lectura para el contexto y manifiestos de EpiDatasetV2.

Valida las especificaciones de artefactos y audita ``run_dir`` ANTES de cualquier escritura,
creación de directorios, ``chmod`` o borrado:
- Rechaza enlaces simbólicos y entradas no permitidas en ``run_dir`` e ``inputs/``.
- Verifica coherencia de ``manifest.json`` y ``dataset_manifest.json`` existentes (permitiendo que
  ``code_commit`` y ``created_at`` difieran legítimamente entre commits de código cuando los datos
  y digests permanecen idénticos).
- Verifica byte a byte y por SHA-256 los artefactos existentes y rechaza contextos sellados con
  piezas faltantes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

_ALLOWED_ROOT_ENTRIES: frozenset[str] = frozenset(
    {
        "inputs",
        "epi_dataset_v2.csv",
        "manifest.json",
        "products.csv",
        "lineage.json",
        "dataset_manifest.json",
    }
)
_SEALED_MARKERS: tuple[str, ...] = (
    "manifest.json",
    "dataset_manifest.json",
    "products.csv",
    "lineage.json",
)
_REMEDY_HINT = (
    "prefiere un worktree limpio nuevo o un runs_root aislado vía API Python; "
    "sólo mueve a runs/_quarantine/ a mano sin procesos activos y tras inventariar y "
    "respaldar por SHA-256 el contexto previo (no borrar trabajo único: las corridas y "
    "selecciones dependientes del dataset anterior pierden su contexto y quedan invalidadas)"
)


@dataclass(frozen=True)
class StagedArtifact:
    """Artefacto esperado bajo ``run_dir`` con bytes y SHA-256 precalculados."""

    rel_path: str
    content: bytes
    digest: str
    stat_source: Path | None = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _unexpected_entry_message(scope: str, name: str) -> str:
    if name in {"run_manifest.json", "jobs"}:
        return (
            f"{scope}: el directorio del dataset contiene artefactos de ejecución ({name}); "
            "mueve esos residuos a runs/_quarantine/ a mano antes de continuar"
        )
    if name == ".DS_Store" or (name.startswith(".") and name.endswith(".tmp")):
        return (
            f"{scope}: residuo temporal o del sistema ({name}, p.ej. .DS_Store o .tmp de proceso "
            "interrumpido/concurrente); verifica que no haya otro proceso activo y retíralo a mano"
        )
    return f"{scope}: contexto existente contiene entrada ajena ({name}); {_REMEDY_HINT}"


def _load_json_dict(path: Path, label: str, error_cls: type[ValueError]) -> dict[str, Any]:
    def _reject_dups(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise error_cls(f"{label}: clave JSON duplicada {key!r} en {path.name}")
            out[key] = value
        return out

    try:
        raw_text = path.read_text(encoding="utf-8")
        loaded = json.loads(raw_text, object_pairs_hook=_reject_dups)
    except ValueError as exc:
        if isinstance(exc, error_cls):
            raise
        raise error_cls(f"{label}: JSON inválido en {path.name}: {exc}") from exc
    except OSError as exc:
        raise error_cls(f"{label}: no se pudo leer {path.name}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise error_cls(f"{label}: raíz JSON en {path.name} debe ser objeto")
    return loaded


def validate_artifact_specs(
    artifacts: Sequence[StagedArtifact], error_cls: type[ValueError]
) -> None:
    if not artifacts:
        raise error_cls("staging de dataset requiere al menos un artefacto")
    seen: set[str] = set()
    for art in artifacts:
        rel = Path(art.rel_path)
        parts = rel.parts
        if (
            not art.rel_path
            or rel.is_absolute()
            or ".." in parts
            or not (
                art.rel_path in {"epi_dataset_v2.csv", "manifest.json"}
                or (len(parts) == 2 and parts[0] == "inputs" and bool(parts[1]))
            )
        ):
            raise error_cls(f"ruta relativa de artefacto inválida: {art.rel_path!r}")
        if art.rel_path in seen:
            raise error_cls(f"ruta relativa de artefacto duplicada: {art.rel_path!r}")
        seen.add(art.rel_path)
        computed = sha256_bytes(art.content)
        if computed != art.digest:
            raise error_cls(
                f"digest interno inconsistente para {art.rel_path}: {computed} != {art.digest}"
            )


def _verify_manifests_if_present(
    run_dir: Path,
    run_id: str,
    disease_id: str,
    digests: Mapping[str, str],
    error_cls: type[ValueError],
) -> None:
    expected_digests = dict(digests)
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        man = _load_json_dict(manifest_path, run_dir.name, error_cls)
        if man.get("run_id") != run_id or man.get("disease_id") != disease_id:
            raise error_cls(
                f"{run_dir.name}: manifest.json declara contexto distinto "
                f"(run_id={man.get('run_id')!r}, disease_id={man.get('disease_id')!r}) "
                f"vs esperado ({run_id!r}, {disease_id!r}); {_REMEDY_HINT}"
            )
        if man.get("digests") != expected_digests:
            raise error_cls(
                f"{run_dir.name}: manifest.json declara digests distintos; "
                f"se rehúsa reescribir ({_REMEDY_HINT})"
            )

    dataset_manifest_path = run_dir / "dataset_manifest.json"
    if dataset_manifest_path.exists():
        dm = _load_json_dict(dataset_manifest_path, run_dir.name, error_cls)
        if dm.get("dataset_id") != run_id or dm.get("disease_id") != disease_id:
            raise error_cls(
                f"{run_dir.name}: dataset_manifest.json declara contexto distinto "
                f"(dataset_id={dm.get('dataset_id')!r}, disease_id={dm.get('disease_id')!r}) "
                f"vs esperado ({run_id!r}, {disease_id!r}); {_REMEDY_HINT}"
            )
        if dm.get("digests") != expected_digests:
            raise error_cls(
                f"{run_dir.name}: dataset_manifest.json declara digests distintos; "
                f"se rehúsa reescribir ({_REMEDY_HINT})"
            )
        dm_arts = dm.get("artifacts")
        if dm_arts is not None:
            if not isinstance(dm_arts, list):
                raise error_cls(f"{run_dir.name}: artifacts inválido en dataset_manifest.json")
            for rec in dm_arts:
                if not isinstance(rec, dict):
                    raise error_cls(f"{run_dir.name}: registro de artefacto inválido")
                rec_path = rec.get("path")
                rec_digest = rec.get("digest")
                if rec_path == "epi_dataset_v2.csv" and rec_digest != expected_digests.get(
                    "dataset"
                ):
                    raise error_cls(
                        f"{run_dir.name}: digest de epi_dataset_v2.csv en dataset_manifest.json "
                        "no coincide con el dataset esperado"
                    )
                if isinstance(rec_path, str) and rec_path in {"products.csv", "lineage.json"}:
                    deriv_path = run_dir / rec_path
                    if (
                        deriv_path.is_symlink()
                        or not deriv_path.is_file()
                        or sha256_file(deriv_path) != rec_digest
                    ):
                        raise error_cls(
                            f"{run_dir.name}: artefacto derivado '{rec_path}' ausente o "
                            "modificado respecto a dataset_manifest.json"
                        )


def preflight_dataset_context(
    *,
    run_dir: Path,
    run_id: str,
    disease_id: str,
    digests: Mapping[str, str],
    artifacts: Sequence[StagedArtifact],
    error_cls: type[ValueError] = ValueError,
) -> tuple[int, list[StagedArtifact]]:
    """Audita ``run_dir`` en sólo lectura; devuelve ``(verificados, faltantes)``."""
    validate_artifact_specs(artifacts, error_cls)

    if run_dir.is_symlink():
        raise error_cls(f"el directorio del dataset no puede ser enlace simbólico: {run_dir}")

    inputs_dir = run_dir / "inputs"
    expected_input_names = {
        Path(art.rel_path).name for art in artifacts if Path(art.rel_path).parts[0] == "inputs"
    }

    if run_dir.exists():
        if not run_dir.is_dir():
            raise error_cls(f"la ruta del dataset existe y no es directorio: {run_dir}")
        for entry in run_dir.iterdir():
            if entry.is_symlink():
                raise error_cls(
                    f"{run_dir.name}: no se permiten enlaces simbólicos ({entry.name})"
                )
            if entry.name not in _ALLOWED_ROOT_ENTRIES:
                raise error_cls(_unexpected_entry_message(run_dir.name, entry.name))
            if entry.name == "inputs":
                if not entry.is_dir():
                    raise error_cls(f"{run_dir.name}: 'inputs' existente no es un directorio")
            elif not entry.is_file():
                raise error_cls(f"{run_dir.name}: '{entry.name}' existente no es archivo regular")

        if inputs_dir.exists():
            for inp in inputs_dir.iterdir():
                if inp.is_symlink() or not inp.is_file():
                    raise error_cls(
                        f"{run_dir.name}/inputs: entrada inválida o enlace simbólico ({inp.name})"
                    )
                if inp.name not in expected_input_names:
                    raise error_cls(_unexpected_entry_message(f"{run_dir.name}/inputs", inp.name))

        _verify_manifests_if_present(run_dir, run_id, disease_id, digests, error_cls)

    verified_count = 0
    missing: list[StagedArtifact] = []
    for art in artifacts:
        dst = run_dir / art.rel_path
        if dst.is_symlink():
            raise error_cls(f"{run_dir.name}: no se permite enlace simbólico en {art.rel_path}")
        if dst.exists():
            if not dst.is_file():
                raise error_cls(f"{run_dir.name}: {art.rel_path} existente no es archivo regular")
            actual_bytes = dst.read_bytes()
            actual_digest = sha256_bytes(actual_bytes)
            if actual_digest != art.digest or actual_bytes != art.content:
                raise error_cls(
                    f"{run_dir.name}: {art.rel_path} existente difiere del esperado "
                    f"({actual_digest} != {art.digest}); se rehúsa sobrescribir ({_REMEDY_HINT})"
                )
            verified_count += 1
        else:
            missing.append(art)

    if run_dir.exists() and missing:
        present_markers = [m for m in _SEALED_MARKERS if (run_dir / m).exists()]
        if present_markers:
            missing_rels = [art.rel_path for art in missing]
            raise error_cls(
                f"{run_dir.name}: contexto existente sellado ({present_markers}) incompleto; "
                f"faltan {missing_rels} ({_REMEDY_HINT})"
            )

    return verified_count, missing
