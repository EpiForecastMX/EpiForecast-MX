"""F2/C2 — ``run_manifest.v1``: manifiesto de ejecución por ``run_id`` (estado, jobs, artefactos).

Documento vivo de un run: comando y estado, commit de código y digests de inputs/config,
timestamps, jobs por motor (pending/running/succeeded/failed) con su error/exit-code, artefactos
con ruta/digest/schema/validación y los conteos 64/47/111. La reanudación SOLO se autoriza si el
job está ``succeeded`` con todos sus artefactos validados (``JobRecord.is_complete``).

Serializable a JSON sin dependencias nuevas (dataclasses + json). Claves y metadata (ArtifactRecord)
son inmutables; el manifiesto y los jobs mutan al avanzar el run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "run_manifest.v1"

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


class ManifestError(ValueError):
    """Manifiesto o transición de estado inválidos."""


def utc_now() -> str:
    """Timestamp ISO-8601 en UTC (inyectable en pruebas vía monkeypatch)."""
    return datetime.now(UTC).isoformat()


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
    artifacts: list[ArtifactRecord] = field(default_factory=list)

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


@dataclass
class RunManifest:
    """``run_manifest.v1`` — estado completo de un run bajo ``runs/<run_id>/``."""

    run_id: str
    disease_id: str
    command: str
    status: str = STATUS_PENDING
    schema: str = MANIFEST_SCHEMA
    code_commit: str | None = None
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
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunManifest:
        schema = data.get("schema")
        if schema != MANIFEST_SCHEMA:
            raise ManifestError(f"schema de manifiesto inesperado: {schema!r}")
        d = dict(data)
        d.pop("schema", None)
        jobs_raw: dict[str, Any] = d.pop("jobs", {}) or {}
        arts_raw: list[Any] = d.pop("artifacts", []) or []
        jobs = {
            eng: JobRecord(
                **{**jr, "artifacts": [ArtifactRecord(**a) for a in jr.get("artifacts", [])]}
            )
            for eng, jr in jobs_raw.items()
        }
        artifacts = [ArtifactRecord(**a) for a in arts_raw]
        return cls(jobs=jobs, artifacts=artifacts, **d)

    @classmethod
    def read(cls, run_dir: Path) -> RunManifest:
        path = run_dir / "run_manifest.json"
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
