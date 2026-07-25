"""C7.1/Acción 3 (R5.1) — el run de ACEPTACIÓN, verificado y no sólo enlazado por digest.

Que el `acceptance_digest` sea consistente en toda la cadena demuestra que todos hablan del mismo
string, no que exista un veredicto positivo. Aquí se abre el run que la procedencia del refit
declara y se exige que sea un benchmark de test exitoso, del mismo padecimiento, dataset y
política, con `accepted=true`, todos sus checks en `passed=true` y la MISMA selección congelada que
usó el refit.

El ID del run, el fold, el año y el número de series NO se escriben aquí: viajan sellados en
``refit_summary.json`` y en el propio ``acceptance.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from epiforecast.runner.artifact_identity import (
    ArtifactValidationError,
    equal,
    mapping_of,
    read_json,
    read_manifest,
    require,
    require_artifacts,
    sequence_of,
    sha256_file,
    text_of,
    verify_records,
)
from epiforecast.runner.manifest import ArtifactRecord, RunManifest

SCHEMA_ACCEPTANCE = "acceptance.v1"
ACCEPTANCE_FILE = "acceptance.json"
SELECTION_FILE = "final_selection.csv"
SCHEMA_SELECTION = "final_selection.v1"
CMD_BENCHMARK = "benchmark"
STAGE_TEST = "test"


@dataclass(frozen=True, slots=True)
class VerifiedAcceptance:
    """Veredicto de aceptación ya verificado (no sólo referenciado)."""

    run_id: str
    digest: str
    selection_digest: str
    scopes: tuple[str, ...]


def _records(raw: object, label: str) -> list[ArtifactRecord]:
    """``ArtifactRecord`` declarados por ``acceptance.json`` (frontera de tipos incluida)."""
    salida: list[ArtifactRecord] = []
    for crudo in sequence_of(raw or [], label):
        datos = mapping_of(crudo, f"{label}[]")
        try:
            salida.append(ArtifactRecord(**datos))
        except TypeError as exc:
            raise ArtifactValidationError(f"{label}: registro inválido ({exc})") from exc
    return salida


def validate_acceptance(
    acceptance_dir: Path,
    *,
    run_id: str,
    disease_id: str,
    dataset_id: str,
    policy_digest: str,
    acceptance_digest: str,
    selection_digest: str,
    selection_run_id: str,
    final_selection_digest: str,
) -> VerifiedAcceptance:
    """Abre el run de aceptación declarado por el refit y exige un veredicto POSITIVO."""
    who = "aceptacion"
    man: RunManifest = read_manifest(acceptance_dir, run_id, disease_id, CMD_BENCHMARK)
    equal(f"{who}: stage", man.stage, STAGE_TEST)
    equal(f"{who}: dataset_id", man.dataset_id, dataset_id)
    equal(f"{who}: policy_digest", man.policy_digest, policy_digest)
    # Un benchmark puede perder TODOS sus jobs y conservar un veredicto de aspecto válido (R7.1):
    # los motores declarados y los jobs ejecutados tienen que ser el mismo conjunto.
    require(man.engines, f"{who}: el manifiesto no declara motores")
    equal(f"{who}: jobs", sorted(man.jobs), sorted(man.engines))
    for engine, job in man.jobs.items():
        require(job.artifacts, f"{who}/{engine}: job sin artefactos")

    equal(
        f"{who}: digest de {ACCEPTANCE_FILE}",
        sha256_file(acceptance_dir / ACCEPTANCE_FILE, ACCEPTANCE_FILE),
        acceptance_digest,
    )
    acta = read_json(acceptance_dir / ACCEPTANCE_FILE, who, SCHEMA_ACCEPTANCE)
    require(acta.get("accepted") is True, f"{who}: el veredicto no es accepted=true")
    checks = sequence_of(acta.get("checks") or [], f"{who}: checks")
    require(checks, f"{who}: veredicto sin comprobaciones")
    scopes: list[str] = []
    for crudo in checks:
        check = mapping_of(crudo, f"{who}: check")
        scope = text_of(check.get("scope"), f"{who}: scope de una comprobación")
        require(check.get("passed") is True, f"{who}: la comprobación {scope!r} no pasó")
        scopes.append(scope)

    # Los outputs que el propio veredicto declara son parte del contrato del run.
    declarados = _records(acta.get("artifacts"), f"{who}: artifacts")
    require(declarados, f"{who}: el veredicto no declara ningún artefacto")
    verify_records(acceptance_dir, declarados, who)
    por_ruta = {rec.path: rec for rec in declarados}
    require(SELECTION_FILE in por_ruta, f"{who}: el veredicto no declara {SELECTION_FILE}")
    equal(f"{who}: schema de {SELECTION_FILE}", por_ruta[SELECTION_FILE].schema, SCHEMA_SELECTION)
    requeridos = {rec.path: rec.schema for rec in declarados}
    require_artifacts(man, {**requeridos, ACCEPTANCE_FILE: SCHEMA_ACCEPTANCE}, who, exact=True)

    procedencia = mapping_of(acta.get("provenance") or {}, f"{who}: provenance")
    equal(f"{who}: run_id del veredicto", procedencia.get("run_id"), run_id)
    equal(f"{who}: selection_digest", procedencia.get("selection_digest"), selection_digest)
    # El digest de la selección no sustituye al ID del run que la produjo (R7.3).
    equal(f"{who}: selection_run_id", procedencia.get("selection_run_id"), selection_run_id)
    # La selección aceptada debe ser BYTE a byte la que refiteó el portafolio.
    equal(
        f"{who}: digest de {SELECTION_FILE}",
        sha256_file(acceptance_dir / SELECTION_FILE, SELECTION_FILE),
        final_selection_digest,
    )
    return VerifiedAcceptance(
        run_id=run_id,
        digest=acceptance_digest,
        selection_digest=selection_digest,
        scopes=tuple(scopes),
    )
