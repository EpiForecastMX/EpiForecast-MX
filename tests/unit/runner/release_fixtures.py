"""Construcción AISLADA de un release bundle + utilidades de mutación (C7.2-A).

Ninguna prueba escribe bajo ``runs/`` ni bajo ``artifacts/releases/``: los runs sellados se copian a
``tmp_path`` (``artifact_fixtures.copiar_runs_sellados``) y el bundle se construye en un temporal.

``resellar`` rehace TODO lo que el propio release firma —digests y tamaños del inventario,
``release_id``, ``identity_digest`` y ``SHA256SUMS.txt``— para que una mutación se mida contra la
IDENTIDAD del artefacto y no muera en el sello. ``resellar_checksums`` sólo rehace el archivo de
sumas, para las mutaciones que deben chocar contra la identidad recalculada.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from epiforecast import registry
from epiforecast.runner.artifact_validation import validate_runner_runs
from epiforecast.runner.release_builder import BuiltRelease, build_release
from epiforecast.runner.release_contract import (
    CHECKSUMS_FILE,
    MANIFEST_FILE,
    build_checksums,
    canonical_json,
    identity_payload,
    release_id_for,
    sha256_bytes,
)
from epiforecast.runner.release_sources import resolve_sources
from tests.unit.runner import artifact_fixtures as af

POLICY = Path("config/evaluation/rolling_cv_v1.yaml")


@dataclass(frozen=True)
class Preparado:
    """Cadena verificada + rutas fuente sobre una copia aislada de los runs sellados."""

    verified: Any
    sources: Any
    runs_root: Path


def chain_source() -> registry.ArtifactSource:
    """``ArtifactSource`` de tipo ``runner_runs`` derivada de la cadena SELLADA del release.

    El registry ya declara ``runner_release`` (C7.2-B), pero promover se hace SIEMPRE desde los runs
    sellados; sus identidades viven en el ``chain`` del bundle, no escritas a mano aquí.
    """
    cadena = af.sealed_chain()
    return registry.ArtifactSource(
        backend=registry.BACKEND_RUNNER_RUNS,
        refit_run_id=cadena["refit_run_id"],
        forecast_run_id=cadena["forecast_run_id"],
        policy_digest=cadena["policy_digest"],
        final_selection_digest=cadena["final_selection_digest"],
    )


def preparar(tmp_path: Path) -> Preparado:
    """Copia los runs sellados a ``tmp_path/runs`` y valida la cadena sobre ESA copia."""
    runs = af.copiar_runs_sellados(tmp_path / "runs")
    src = chain_source()
    verificado = validate_runner_runs(
        disease_id=af.DISEASE,
        refit_run_id=str(src.refit_run_id),
        forecast_run_id=str(src.forecast_run_id),
        policy_digest=str(src.policy_digest),
        final_selection_digest=str(src.final_selection_digest),
        runs_root=runs,
        policy_path=POLICY,
    )
    return Preparado(
        verified=verificado,
        sources=resolve_sources(verificado, runs_root=runs, policy_path=POLICY),
        runs_root=runs,
    )


def construir_en(prep: Preparado, output_root: Path) -> BuiltRelease:
    return build_release(
        verified=prep.verified,
        sources=prep.sources,
        output_root=output_root,
    )


def construir(tmp_path: Path, *, salida: str = "out") -> BuiltRelease:
    """Prepara y construye en un solo paso (el caso común de las pruebas)."""
    return construir_en(preparar(tmp_path), tmp_path / salida)


def construir_por_entry(prep: Preparado, output_root: Path) -> BuiltRelease:
    """Construye por el ENTRY POINT real (registry incluido), sobre la copia aislada de los runs."""
    from epiforecast.runner.release_entry import build_release_for_disease

    return build_release_for_disease(
        af.DISEASE, runs_root=prep.runs_root, policy_path=POLICY, output_root=output_root
    )


def disease_desde_runs(**politica: object) -> registry.Disease:
    """Obesidad declarando ``runner_runs`` (como antes del flip) y la política pública que se pida.

    Promover exige el backend de runs; el flip a ``runner_release`` es el estado POSTERIOR. Esta
    sustitución permite seguir ejercitando el entry point real sin escribir identidades a mano.
    """
    import dataclasses

    return dataclasses.replace(
        registry.require(af.DISEASE), artifact_source=chain_source(), **politica
    )


def copia(bundle: Path, destino: Path) -> Path:
    """Copia del bundle ya construido: las mutaciones nunca tocan el original de la sesión."""
    shutil.copytree(bundle, destino)
    return destino


def leer_manifest(root: Path) -> dict[str, Any]:
    return json.loads((root / MANIFEST_FILE).read_text(encoding="utf-8"))


def escribir_manifest(root: Path, manifest: dict[str, Any]) -> None:
    (root / MANIFEST_FILE).write_bytes(canonical_json(manifest))


def payload_digests(root: Path, manifest: dict[str, Any]) -> dict[str, str]:
    return {p["path"]: p["sha256"] for p in manifest["payloads"]}


def resellar_checksums(root: Path) -> None:
    """Rehace sólo ``SHA256SUMS.txt`` a partir de lo que el manifest declara."""
    manifest = leer_manifest(root)
    entradas = payload_digests(root, manifest)
    entradas[MANIFEST_FILE] = sha256_bytes((root / MANIFEST_FILE).read_bytes())
    (root / CHECKSUMS_FILE).write_bytes(build_checksums(entradas))


def resellar(root: Path) -> None:
    """Rehace inventario, identidad y sumas: la prueba mide identidad, no el sello."""
    manifest = leer_manifest(root)
    payloads = []
    for registro in manifest["payloads"]:
        path = root / registro["path"]
        if not path.exists():
            continue
        datos = path.read_bytes()
        payloads.append({**registro, "sha256": sha256_bytes(datos), "bytes": len(datos)})
    manifest["payloads"] = sorted(payloads, key=lambda r: r["path"])
    # El re-sellado usa el builder que DECLARA el manifest, no el instalado: así un fixture de
    # otro productor se puede re-sellar de forma coherente (C7.2-A.2.1).
    identidad = identity_payload(
        disease_id=manifest["disease_id"],
        chain=manifest["chain"],
        payloads={r["path"]: r["sha256"] for r in manifest["payloads"]},
        builder_version=manifest["builder_version"],
    )
    manifest["release_id"], manifest["identity_digest"] = release_id_for(identidad)
    escribir_manifest(root, manifest)
    resellar_checksums(root)


# Versiones ANTERIORES del contrato, sólo para probar que se rechazan. Nunca se persistió un
# bundle v1: estos fixtures lo fabrican degradando uno v2 (C7.2-A.2/R19.1.6).
SCHEMAS_V1 = {"schema": "release_manifest.v1", "identity_schema": "identity_payload.v1"}


def degradar_a_v1(root: Path, *, claves: tuple[str, ...] = ("schema", "identity_schema")) -> None:
    """Reescribe el manifest como si lo hubiera emitido el builder anterior, y re-sella las sumas."""
    manifest = leer_manifest(root)
    for clave in claves:
        manifest[clave] = SCHEMAS_V1[clave]
    escribir_manifest(root, manifest)
    resellar_checksums(root)


def reconstruir_con_builder(root: Path, builder_version: str) -> str:
    """Fixture de OTRO productor bajo el mismo schema v2: re-sella identidad y sumas. → release_id."""
    manifest = leer_manifest(root)
    manifest["builder_version"] = builder_version
    escribir_manifest(root, manifest)
    resellar(root)
    return str(leer_manifest(root)["release_id"])


def un_estado(root: Path) -> Path:
    """Ruta de un estado de modelo dentro del bundle (orden estable)."""
    return sorted((root / "refit" / "models").rglob("*.state.*"))[0]


def un_envelope(root: Path) -> Path:
    return sorted((root / "refit" / "models").rglob("*.envelope.json"))[0]
