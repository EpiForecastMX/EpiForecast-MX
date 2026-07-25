"""C7.1/Acción 3 — primitivas de identidad de los artefactos sellados del runner.

Toda lectura, parseo y comparación de un artefacto ajeno pasa por aquí y se convierte en
``ArtifactValidationError``: un JSON truncado, un schema desconocido o un tipo incorrecto NUNCA
escapan como traceback (P0.4). El llamador decide cómo presentarlo (``Problem`` en el doctor).

Ajeno al CLI, al registry y a cualquier padecimiento concreto: recibe rutas e identidades
esperadas y no lee configuración global.
"""

from __future__ import annotations

from collections.abc import Iterable
import hashlib
import json
import numbers
from pathlib import Path
from typing import Any

from epiforecast.runner.manifest import STATUS_SUCCEEDED, ArtifactRecord, RunManifest

# Fallos esperables al leer/parsear/deserializar un artefacto que no controlamos: archivo ausente
# o ilegible, JSON inválido, schema inesperado (ManifestError es ValueError), clave o tipo que no
# encaja con la dataclass destino.
IO_ERRORS = (OSError, ValueError, TypeError, KeyError, UnicodeDecodeError)


class ArtifactValidationError(ValueError):
    """La identidad declarada por los artefactos sellados no cierra."""


def require(condition: object, message: str) -> None:
    if not condition:
        raise ArtifactValidationError(message)


def equal(label: str, got: object, expected: object) -> None:
    if got != expected:
        raise ArtifactValidationError(f"{label}: {got!r} != {expected!r}")


def sha256_file(path: Path, label: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ArtifactValidationError(f"{label}: ilegible ({exc})") from exc


def read_json(path: Path, label: str, schema: str | None = None) -> dict[str, Any]:
    """JSON de un artefacto como diccionario, con su schema declarado si se exige."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{label}: JSON ilegible ({exc})") from exc
    if not isinstance(data, dict):
        raise ArtifactValidationError(f"{label}: se esperaba un objeto JSON")
    if schema is not None:
        equal(f"{label}: schema", data.get("schema"), schema)
    return data


def text_of(raw: object, label: str) -> str:
    """Campo de identidad: string no vacío. Un ``int``, ``None`` o lista es un error de contrato."""
    if not isinstance(raw, str) or not raw.strip():
        raise ArtifactValidationError(f"{label}: se esperaba un string no vacío, no {raw!r}")
    return raw


def int_of(raw: object, label: str) -> int:
    """Entero de identidad ESTRICTO, sin coerción (R7.2).

    ``int(valor)`` "arreglaba" metadata inválida y dejaba escapar un ``ValueError`` crudo. Aquí un
    string, un ``float`` (incluidos NaN e infinito), un ``bool`` o ``None`` son errores de
    contrato; los enteros de NumPy sí valen, porque son ``numbers.Integral``.
    """
    if isinstance(raw, bool) or not isinstance(raw, numbers.Integral):
        raise ArtifactValidationError(f"{label}: se esperaba un entero, no {raw!r}")
    return int(raw)


def mapping_of(raw: object, label: str) -> dict[str, Any]:
    """Frontera de tipos: un objeto JSON. Evita que un tipo ajeno escape como ``AttributeError``."""
    if not isinstance(raw, dict):
        raise ArtifactValidationError(f"{label}: se esperaba un objeto, no {type(raw).__name__}")
    return raw


def sequence_of(raw: object, label: str) -> list[Any]:
    """Frontera de tipos: una lista JSON (un string tampoco vale, aunque sea iterable)."""
    if not isinstance(raw, list):
        raise ArtifactValidationError(f"{label}: se esperaba una lista, no {type(raw).__name__}")
    return raw


def verify_records(run_dir: Path, records: Iterable[ArtifactRecord], label: str) -> None:
    """Cada artefacto declarado existe, dice ``validated=true``, conserva su SHA256 y es único.

    La unicidad va ANTES de cualquier diccionario por ``path`` (R9.2): dos records con la misma
    ruta se colapsarían en «gana el último» y el inventario dejaría de ser una identidad.
    """
    vistos: set[str] = set()
    for rec in records:
        who = f"{label}: artefacto {rec.path}"
        require(rec.path not in vistos, f"{label}: ruta declarada dos veces: {rec.path}")
        vistos.add(rec.path)
        require(rec.validated, f"{who} sin validated=true")
        path = run_dir / rec.path
        require(path.exists(), f"{who} ausente")
        equal(f"{who}: digest", sha256_file(path, who), rec.digest)


def require_exact_records(
    records: Iterable[ArtifactRecord], required: dict[str, str], label: str
) -> None:
    """Inventario EXACTO: ni un artefacto de menos, ni uno de más, cada uno con su schema."""
    declarados = {rec.path: rec.schema for rec in records}
    equal(f"{label}: inventario", sorted(declarados), sorted(required))
    for path, schema in required.items():
        equal(f"{label}: schema de {path}", declarados[path], schema)


def _check_shape(data: dict[str, Any], label: str) -> None:
    """Normaliza los tipos ANTES de construir la dataclass (R5.4).

    ``RunManifest.from_dict`` asume que ``jobs`` es un mapeo y que ``artifacts`` es una lista; con
    un tipo ajeno reventaría con ``AttributeError`` fuera de la frontera de error. Se valida aquí,
    en la lectura, y no envolviendo la lógica entera en un ``except Exception``.
    """
    # Ojo: `data.get(k) or {}` colapsaría un `[]` o un `""` en un mapeo válido y dejaría pasar el
    # tipo ajeno. Sólo la AUSENCIA (None) se sustituye por el default.
    for clave in ("jobs", "input_digests", "counts"):
        if data.get(clave) is not None:
            mapping_of(data[clave], f"{label}: {clave}")
    if data.get("artifacts") is not None:
        for registro in sequence_of(data["artifacts"], f"{label}: artifacts"):
            mapping_of(registro, f"{label}: artifacts[]")
    for engine, job in (data.get("jobs") or {}).items():
        who = f"{label}/{engine}"
        if mapping_of(job, who).get("artifacts") is not None:
            for registro in sequence_of(job["artifacts"], f"{who}: artifacts"):
                mapping_of(registro, f"{who}: artifacts[]")


def read_manifest(run_dir: Path, run_id: str, disease_id: str, command: str) -> RunManifest:
    """Manifiesto de un run sellado: identidad completa + artefactos re-verificados en disco.

    El nombre del directorio es parte de la identidad: un run copiado a otro nombre deja de ser
    el que declara el registry. Cada job debe declarar su motor, haber terminado con éxito y salir
    con ``exit_code=0``: un job a medias no sella nada.
    """
    require((run_dir / "run_manifest.json").exists(), f"{command}: no existe {run_dir.name}")
    data = read_json(run_dir / "run_manifest.json", command)
    _check_shape(data, command)
    try:
        man = RunManifest.from_dict(data)
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{command}: manifiesto ilegible ({exc})") from exc
    equal(f"{command}: run_id", man.run_id, run_id)
    equal(f"{command}: directorio", run_dir.name, run_id)
    equal(f"{command}: disease_id", man.disease_id, disease_id)
    equal(f"{command}: command", man.command, command)
    equal(f"{command}: status", man.status, STATUS_SUCCEEDED)
    verify_records(run_dir, man.artifacts, command)
    for engine, job in man.jobs.items():
        who = f"{command}/{engine}"
        equal(f"{who}: engine del job", job.engine, engine)
        equal(f"{who}: status", job.status, STATUS_SUCCEEDED)
        equal(f"{who}: exit_code", job.exit_code, 0)
        verify_records(run_dir, job.artifacts, who)
    return man


def require_artifacts(
    man: RunManifest, required: dict[str, str], label: str, *, exact: bool = False
) -> None:
    """Los artefactos que el contrato EXIGE deben estar declarados, con su schema.

    Verificar «todos los records que haya» no basta: un manifiesto sin declarar su salida
    obligatoria dejaría de sellar el run (R5.3). Con ``exact``, además, no puede declarar otros.
    """
    declarados = {rec.path: rec.schema for rec in man.artifacts}
    for path, schema in required.items():
        require(path in declarados, f"{label}: el manifiesto no declara {path}")
        equal(f"{label}: schema de {path}", declarados[path], schema)
    if exact:
        equal(f"{label}: artefactos declarados", sorted(declarados), sorted(required))


def require_job_artifacts(man: RunManifest, required: dict[str, str], label: str) -> None:
    """Cada job declara EXACTAMENTE el artefacto que su contrato exige (p.ej. su model_index)."""
    for engine, job in man.jobs.items():
        declarados = {rec.path: rec.schema for rec in job.artifacts}
        esperado = {path.format(engine=engine): schema for path, schema in required.items()}
        equal(f"{label}/{engine}: artefactos del job", sorted(declarados), sorted(esperado))
        for path, schema in esperado.items():
            equal(f"{label}/{engine}: schema de {path}", declarados[path], schema)


def input_digest(man: RunManifest, key: str, label: str) -> str:
    """Digest de entrada declarado por el manifiesto (ausente o no-string = contrato roto)."""
    return text_of(man.input_digests.get(key), f"{label}: input_digests[{key!r}]")


def provenance_of(raw: object, expected: dict[str, str], label: str) -> None:
    """Procedencia declarada == procedencia esperada, clave por clave (sin tolerar ausencias)."""
    if not isinstance(raw, dict):
        raise ArtifactValidationError(f"{label}: procedencia ausente o mal formada")
    got: dict[str, Any] = raw
    for clave, valor in expected.items():
        equal(f"{label}: {clave}", got.get(clave), valor)
