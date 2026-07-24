"""F2/C3 — manifiestos del runner: ``dataset_manifest.v1`` (validate-data) y ``run_manifest.v1``.

Dos identidades separadas (hallazgo C3):
- ``dataset_id`` = digest reproducible del dataset validado. validate-data materializa el dataset
  bajo ``runs/<dataset_id>/`` y escribe su ``DatasetManifest``; NUNCA se sobrescribe por una
  ejecución de motores.
- ``run_id`` = digest de (dataset_id, comando, stage, política, motores, seed, commit). Cada
  benchmark/refit/forecast crea su PROPIO ``runs/<run_id>/`` y referencia el ``dataset_id``.

Documento vivo: comando/stage/estado, digests dataset+policy, timestamps, jobs por motor
(pending/running/succeeded/failed) con error/exit-code y stdout/stderr, artefactos con
ruta/digest/schema/validación y conteos. Reanudación SOLO si el job está ``succeeded`` con TODOS
sus artefactos validados (``JobRecord.is_complete``). Escritura ATÓMICA (temp + os.replace).

Serializable a JSON sin dependencias nuevas (dataclasses + json). Claves y metadata son inmutables;
manifiestos y jobs mutan al avanzar el run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "run_manifest.v1"
DATASET_MANIFEST_SCHEMA = "dataset_manifest.v1"

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUSES: frozenset[str] = frozenset(
    {STATUS_PENDING, STATUS_RUNNING, STATUS_SUCCEEDED, STATUS_FAILED}
)

# Comandos del runner genérico.
CMD_VALIDATE_DATA = "validate-data"
CMD_BENCHMARK = "benchmark"
CMD_REFIT = "refit"
CMD_FORECAST = "forecast"
COMMANDS: frozenset[str] = frozenset({CMD_VALIDATE_DATA, CMD_BENCHMARK, CMD_REFIT, CMD_FORECAST})

# Stages de ejecución (distinto stage → distinto run_id).
STAGE_SMOKE = "smoke"
STAGE_FULL = "full"
STAGES: frozenset[str] = frozenset({STAGE_SMOKE, STAGE_FULL})


class ManifestError(ValueError):
    """Manifiesto o transición de estado inválidos."""


def utc_now() -> str:
    """Timestamp ISO-8601 en UTC (inyectable en pruebas vía monkeypatch)."""
    return datetime.now(UTC).isoformat()


def _atomic_write_text(path: Path, text: str) -> None:
    """Escritura atómica: archivo temporal en el mismo dir + ``Path.replace`` (rename atómico)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def compute_run_id(
    disease_id: str,
    dataset_id: str,
    command: str,
    stage: str,
    policy_digest: str,
    engines: list[str],
    seed: int | None,
    code_commit: str | None,
) -> str:
    """run_id reproducible: digest de dataset+comando+stage+política+motores+seed+commit.

    Motores ordenados (el orden no cambia identidad). Distinto comando/stage → distinto run_id.
    """
    payload = {
        "dataset_id": dataset_id,
        "command": command,
        "stage": stage,
        "policy_digest": policy_digest,
        "engines": sorted(engines),
        "seed": seed,
        "code_commit": code_commit,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return f"{disease_id}_{command}_{stage}_{digest[:12]}"


@dataclass(frozen=True)
class ArtifactRecord:
    """Metadata inmutable de un artefacto emitido por el run (ruta relativa al run_dir)."""

    path: str
    digest: str  # sha256 del archivo
    schema: str  # p.ej. "epi_dataset_v2", "products.v1", "forecast.v1"
    validated: bool


@dataclass
class JobRecord:
    """Estado de un motor dentro de un comando (pending → running → succeeded|failed)."""

    engine: str
    status: str = STATUS_PENDING
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    stdout: str | None = None  # ruta relativa al log de stdout del subprocess
    stderr: str | None = None  # ruta relativa al log de stderr del subprocess
    artifacts: list[ArtifactRecord] = field(default_factory=list)

    def reset(self) -> None:
        """Limpia el estado (un intento previo fallido/incompleto no se hereda)."""
        self.status = STATUS_PENDING
        self.started_at = self.finished_at = None
        self.exit_code = self.error_type = self.error_message = None
        self.stdout = self.stderr = None
        self.artifacts.clear()

    def start(self) -> None:
        self.status = STATUS_RUNNING
        self.started_at = utc_now()

    def succeed(self, artifacts: list[ArtifactRecord] | None = None) -> None:
        self.status = STATUS_SUCCEEDED
        self.exit_code = 0
        self.finished_at = utc_now()
        if artifacts:
            self.artifacts.extend(artifacts)

    def fail(self, exit_code: int, error_type: str, error_message: str) -> None:
        if exit_code == 0:
            raise ManifestError("un job fallido no puede tener exit_code 0")
        self.status = STATUS_FAILED
        self.exit_code = exit_code
        self.error_type = error_type
        self.error_message = error_message
        self.finished_at = utc_now()

    def is_complete(self) -> bool:
        """Reanudable SOLO si terminó con éxito y TODOS sus artefactos están validados."""
        return (
            self.status == STATUS_SUCCEEDED
            and bool(self.artifacts)
            and all(a.validated for a in self.artifacts)
        )


def _jobs_from(raw: dict[str, Any]) -> dict[str, JobRecord]:
    return {
        eng: JobRecord(
            **{**jr, "artifacts": [ArtifactRecord(**a) for a in jr.get("artifacts", [])]}
        )
        for eng, jr in (raw or {}).items()
    }


def _artifacts_from(raw: list[Any]) -> list[ArtifactRecord]:
    return [ArtifactRecord(**a) for a in (raw or [])]


@dataclass
class DatasetManifest:
    """``dataset_manifest.v1`` — identidad del dataset validado bajo ``runs/<dataset_id>/``."""

    dataset_id: str
    disease_id: str
    schema: str = DATASET_MANIFEST_SCHEMA
    code_commit: str | None = None
    digests: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    artifacts: list[ArtifactRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, dataset_dir: Path) -> Path:
        path = dataset_dir / "dataset_manifest.json"
        _atomic_write_text(path, json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetManifest:
        if data.get("schema") != DATASET_MANIFEST_SCHEMA:
            raise ManifestError(f"schema de dataset inesperado: {data.get('schema')!r}")
        d = dict(data)
        d.pop("schema", None)
        arts = _artifacts_from(d.pop("artifacts", []))
        return cls(artifacts=arts, **d)

    @classmethod
    def read(cls, dataset_dir: Path) -> DatasetManifest:
        return cls.from_dict(
            json.loads((dataset_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
        )


@dataclass
class RunManifest:
    """``run_manifest.v1`` — ejecución de motores bajo ``runs/<run_id>/`` (referencia dataset_id)."""

    run_id: str
    disease_id: str
    command: str
    dataset_id: str = ""
    stage: str | None = None
    status: str = STATUS_PENDING
    schema: str = MANIFEST_SCHEMA
    code_commit: str | None = None
    policy_digest: str | None = None
    seed: int | None = None
    engines: list[str] = field(default_factory=list)
    input_digests: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    jobs: dict[str, JobRecord] = field(default_factory=dict)
    artifacts: list[ArtifactRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.command not in COMMANDS:
            raise ManifestError(f"comando desconocido: {self.command!r}")
        if self.status not in STATUSES:
            raise ManifestError(f"estado desconocido: {self.status!r}")
        if self.stage is not None and self.stage not in STAGES:
            raise ManifestError(f"stage desconocido: {self.stage!r}")

    # ── Transiciones del run ──
    def start(self) -> None:
        self.status = STATUS_RUNNING
        self.started_at = utc_now()

    def succeed(self) -> None:
        self.status = STATUS_SUCCEEDED
        self.exit_code = 0
        self.finished_at = utc_now()

    def fail(self, exit_code: int, error_type: str, error_message: str) -> None:
        if exit_code == 0:
            raise ManifestError("un run fallido no puede tener exit_code 0")
        self.status = STATUS_FAILED
        self.exit_code = exit_code
        self.error_type = error_type
        self.error_message = error_message
        self.finished_at = utc_now()

    # ── Jobs y artefactos ──
    def job(self, engine: str) -> JobRecord:
        return self.jobs.setdefault(engine, JobRecord(engine=engine))

    def add_artifact(self, artifact: ArtifactRecord) -> None:
        self.artifacts.append(artifact)

    # ── (De)serialización sin dependencias nuevas ──
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, sort_keys=False)

    def write(self, run_dir: Path) -> Path:
        path = run_dir / "run_manifest.json"
        _atomic_write_text(path, self.to_json())
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunManifest:
        if data.get("schema") != MANIFEST_SCHEMA:
            raise ManifestError(f"schema de manifiesto inesperado: {data.get('schema')!r}")
        d = dict(data)
        d.pop("schema", None)
        jobs = _jobs_from(d.pop("jobs", {}))
        artifacts = _artifacts_from(d.pop("artifacts", []))
        return cls(jobs=jobs, artifacts=artifacts, **d)

    @classmethod
    def read(cls, run_dir: Path) -> RunManifest:
        return cls.from_dict(
            json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        )
