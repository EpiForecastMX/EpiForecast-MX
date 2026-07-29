"""Actualiza el estado prospectivo declarado de un padecimiento, de forma reproducible.

Editar los JSON a mano contradice el objetivo del contrato: el estado es lo que la verdad observada
dice que es, no lo que alguien escriba (R76-P1). Este comando DERIVA la evaluación completa y su
resumen a partir de cuatro identidades separadas, y sólo entonces compara o escribe:

1. el **gate congelado** — umbrales, semanas programadas y digests;
2. el **bundle sellado** — de donde sale el candidato, que se verifica contra el gate;
3. el **dataset de ENTRENAMIENTO** congelado — reconstruye el control y da los denominadores MASE;
4. el **dataset de OBSERVACIÓN** — la verdad que llega con cada boletín y decide ``n/4``.

Usar el dataset de entrenamiento como verdad —que es lo que hacía antes— garantizaba
``INCOMPLETE 0/4`` para siempre: por definición termina en el origen del pronóstico (R78-P0-1).

    python -m scripts.prospective_status <padecimiento> --check
    python -m scripts.prospective_status <padecimiento> --write --observation-dataset-id <id>

Genérico: el padecimiento es un argumento y la identidad de los insumos se resuelve por el registry,
el bundle y los manifiestos —nunca por nombres inferidos ni rutas absolutas—.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
import math
from pathlib import Path
import sys
from typing import Any

from epiforecast import registry
from epiforecast.publication.observation_store import (
    resolve_observation_dir,
    resolve_training_dir,
)
from epiforecast.publication.prospective import (
    GATE_WEEKS,
    FrozenGate,
    Period,
    SeriesId,
    build_control,
    check_dataset_frame,
    evaluate,
    frame_digest,
    observation_cutoff,
    read_base_history,
)
from epiforecast.publication.status import (
    EVALUATION_FILE,
    STATUS_FILE,
    ProspectiveEvaluation,
    ProspectiveStatus,
    declared_paths,
    load_gate,
)
from epiforecast.runner.artifact_identity import ArtifactValidationError, equal, require
from epiforecast.runner.manifest import DatasetManifest, dataset_dir
from epiforecast.runner.release_contract import canonical_json, sha256_bytes
from epiforecast.runner.release_loader import verify_bundle
from epiforecast.runner.release_reproduce import read_bundled_frame
from epiforecast.runner.release_sources import DIR_FORECAST
from epiforecast.runner.release_store import default_releases_root, release_path

DATASET_CSV = "epi_dataset_v2.csv"
# Digests del manifiesto que dicen de qué fuentes salió un dataset. El de observación puede traer
# `raw` distinto —es un boletín nuevo—, pero config y exposición tienen que ser el mismo carril.
SOURCE_KEYS: tuple[str, ...] = ("raw", "config", "exposure")
IDENTITY_KEYS: tuple[str, ...] = ("config", "exposure")


def _manifest(
    dataset_id: str,
    runs_root: Path | None = None,
    *,
    explicit_dir: Path | None = None,
) -> tuple[DatasetManifest, Path]:
    """Manifiesto de un dataset, con su INTEGRIDAD comprobada: el CSV es el que dice ser."""
    directorio = explicit_dir or dataset_dir(dataset_id, runs_root)
    require(directorio.is_dir(), f"dataset {dataset_id}: no está en runs/")
    manifest = DatasetManifest.read(directorio)
    equal(f"dataset {dataset_id}: dataset_id del manifiesto", manifest.dataset_id, dataset_id)
    declarado = manifest.digests.get("dataset")
    require(bool(declarado), f"dataset {dataset_id}: manifiesto sin digest propio")
    csv = directorio / DATASET_CSV
    require(csv.is_file(), f"dataset {dataset_id}: falta {DATASET_CSV}")
    equal(f"dataset {dataset_id}: digest del CSV", sha256_bytes(csv.read_bytes()), declarado)
    return manifest, directorio


def _history(
    directorio: Path, *, expected_series: int | None = None
) -> dict[SeriesId, dict[Period, float]]:
    """Historia por serie, PREVIA validación del frame tabular: los duplicados no pueden perderse."""
    check_dataset_frame(directorio / DATASET_CSV, expected_series=expected_series)
    return read_base_history(directorio / DATASET_CSV)


def check_observation_dataset(
    manifest: DatasetManifest,
    training: DatasetManifest,
    observation_history: Mapping[SeriesId, dict[Period, float]],
    training_history: Mapping[SeriesId, dict[Period, float]],
    origin: Period,
) -> None:
    """El dataset de observación tiene que ser el MISMO carril, con más semanas. Nada más.

    Un snapshot de otro padecimiento, de otra configuración o con la historia previa reescrita no
    es «más verdad»: es otro experimento, y compararlo contra el candidato congelado no significa
    nada (R78-P0-1).
    """
    equal("dataset de observación: disease_id", manifest.disease_id, training.disease_id)
    for clave in IDENTITY_KEYS:
        equal(
            f"dataset de observación: digest de {clave}",
            manifest.digests.get(clave),
            training.digests.get(clave),
        )
    equal(
        "dataset de observación: SeriesKeys", sorted(observation_history), sorted(training_history)
    )
    require(
        int(manifest.counts.get("base", 0)) == len(training_history),
        f"dataset de observación: declara {manifest.counts.get('base')} series base, "
        f"se esperaban {len(training_history)}",
    )

    for serie, historia in observation_history.items():
        valores = list(historia.values())
        require(
            all(math.isfinite(v) for v in valores),
            f"dataset de observación {serie}: hay valores no finitos",
        )
        require(all(v >= 0 for v in valores), f"dataset de observación {serie}: valores negativos")
        # El PREFIJO hasta el origen no puede haberse movido: si la historia con la que se congeló
        # cambió, el candidato ya no es comparable con nada.
        previo_obs = {p: v for p, v in historia.items() if p <= origin}
        previo_tr = {p: v for p, v in training_history[serie].items() if p <= origin}
        equal(f"dataset de observación {serie}: historia hasta el origen", previo_obs, previo_tr)


def derive_evaluation(
    disease_id: str,
    *,
    observation_dataset_id: str | None = None,
    config_root_path: Path | None = None,
    runs_root: Path | None = None,
    observation_store_root: Path | None = None,
) -> tuple[ProspectiveEvaluation, ProspectiveStatus]:
    """Evaluación completa y su resumen, derivados de los cuatro insumos verificados."""
    rutas = declared_paths(disease_id, config_root_path=config_root_path)
    gate: FrozenGate = load_gate(rutas["gate"])
    equal(f"{disease_id}: disease_id del gate", gate.disease_id, disease_id)

    declarado = str(registry.require(disease_id).artifact_source.release_id)
    equal(f"{disease_id}: release del gate contra el registry", gate.release_id, declarado)

    # 1) Bundle: el candidato se VERIFICA contra el gate antes de evaluar nada.
    sede = release_path(default_releases_root(), disease_id, gate.release_id)
    verificado = verify_bundle(sede)
    base = read_bundled_frame(sede / DIR_FORECAST / "forecast_base.csv", "forecast_base")
    columnas = ["geography_id", "sex", "epi_year", "epi_week", "y_pred_cases"]
    candidato = (
        base[columnas]
        .sort_values(["geography_id", "sex", "epi_year", "epi_week"])
        .reset_index(drop=True)
    )
    equal("candidato del bundle contra el gate", frame_digest(candidato), gate.candidate_digest)

    # 2) Entrenamiento congelado: control y denominadores MASE.
    training_id = str(verificado.chain["dataset_id"])
    obs_id = observation_dataset_id or training_id
    effective_runs = runs_root or dataset_dir(training_id).parent
    training_dir = resolve_training_dir(
        disease_id,
        obs_id,
        training_id,
        runs_root=effective_runs,
        store_root=observation_store_root,
    )
    training_manifest, training_dir = _manifest(training_id, runs_root, explicit_dir=training_dir)
    equal(
        "dataset de entrenamiento contra el gate",
        training_manifest.digests.get("dataset"),
        gate.dataset_digest,
    )
    training_history = _history(training_dir)
    control = build_control(training_history, gate.origin, gate.horizon)
    equal("control reconstruido contra el gate", frame_digest(control), gate.control_digest)

    # 3) Observación: la verdad que decide n/4.
    if obs_id == training_id:
        obs_dir = training_dir
    else:
        obs_dir = resolve_observation_dir(
            disease_id,
            obs_id,
            runs_root=effective_runs,
            store_root=observation_store_root,
        )
    obs_manifest, obs_dir = _manifest(obs_id, runs_root, explicit_dir=obs_dir)
    observation_history = _history(obs_dir, expected_series=len(training_history))
    check_observation_dataset(
        obs_manifest, training_manifest, observation_history, training_history, gate.origin
    )

    corte = observation_cutoff(observation_history)
    resultado: dict[str, Any] = evaluate(
        gate, candidato, control, observation_history, training=training_history, cutoff=corte
    )
    seleccion = resultado["selection"]
    semanas = tuple((int(a), int(s)) for a, s in resultado["weeks"])

    evaluation = ProspectiveEvaluation(
        disease_id=gate.disease_id,
        release_id=gate.release_id,
        gate_digest=gate.digest(),
        candidate_digest=gate.candidate_digest,
        control_digest=gate.control_digest,
        training_dataset_id=training_id,
        training_dataset_digest=str(training_manifest.digests["dataset"]),
        observation_dataset_id=obs_id,
        observation_dataset_digest=str(obs_manifest.digests["dataset"]),
        observation_source_digests={
            k: str(obs_manifest.digests[k]) for k in SOURCE_KEYS if k in obs_manifest.digests
        },
        observation_cutoff=corte,
        scheduled_weeks=gate.target_weeks,
        completed_weeks=semanas,
        skipped_weeks=tuple(
            ((int(d["week"][0]), int(d["week"][1])), str(d["reason"]))
            for d in seleccion["skipped_weeks"]
        ),
        verdict=str(resultado["verdict"]),
        scopes=dict(resultado["scopes"]),
        metrics=dict(resultado["metrics"]),
        per_week=tuple(dict(d) for d in resultado["per_week"]),
    )
    status = ProspectiveStatus(
        disease_id=gate.disease_id,
        release_id=gate.release_id,
        gate_digest=gate.digest(),
        evaluation_digest=evaluation.digest(),
        observation_dataset_id=evaluation.observation_dataset_id,
        observation_dataset_digest=evaluation.observation_dataset_digest,
        verdict=evaluation.verdict,
        weeks_required=GATE_WEEKS,
        weeks_available=len(semanas),
        completed_weeks=semanas,
        target_weeks=gate.target_weeks,
    )
    return evaluation, status


def _write_atomic(destino: Path, datos: bytes) -> None:
    """Temporal + rename: o queda el archivo nuevo entero, o el anterior intacto."""
    tmp = destino.with_name(f"{destino.name}.tmp")
    try:
        tmp.write_bytes(datos)
        tmp.replace(destino)
    finally:
        tmp.unlink(missing_ok=True)


def _declared_observation_id(rutas: dict[str, Path]) -> str | None:
    """Verdad ya declarada, para que ``--check`` no vuelva en silencio al dataset congelado."""
    for clave in ("status", "evaluation"):
        try:
            datos = json.loads(rutas[clave].read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        valor = datos.get("observation_dataset_id")
        if isinstance(valor, str) and valor:
            return valor
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("disease_id")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--check", action="store_true", help="compara; no escribe nada")
    grupo.add_argument("--write", action="store_true", help="escribe evaluación y estado")
    parser.add_argument(
        "--observation-dataset-id",
        default=None,
        help="dataset EpiDatasetV2 con la verdad observada (obligatorio con --write)",
    )
    parser.add_argument("--config-root", type=Path, default=None)
    parser.add_argument("--runs-root", type=Path, default=None)
    parser.add_argument("--observation-store-root", type=Path, default=None)
    args = parser.parse_args(argv)

    rutas = declared_paths(args.disease_id, config_root_path=args.config_root)
    obs_id = args.observation_dataset_id
    if args.write and not obs_id:
        print(
            "✖ --write exige --observation-dataset-id: la verdad tiene que declararse, "
            "no inferirse del dataset congelado",
            file=sys.stderr,
        )
        return 2
    if args.check and not obs_id:
        obs_id = _declared_observation_id(rutas)

    try:
        evaluation, status = derive_evaluation(
            args.disease_id,
            observation_dataset_id=obs_id,
            config_root_path=args.config_root,
            runs_root=args.runs_root,
            observation_store_root=args.observation_store_root,
        )
    except (ArtifactValidationError, OSError, ValueError) as exc:
        print(f"✖ no se pudo derivar el estado: {exc}", file=sys.stderr)
        return 2

    esperado_eval = canonical_json(evaluation.payload())
    esperado_status = canonical_json(status.payload())
    etiqueta = status.progress_label()

    if args.check:
        actual_eval = rutas["evaluation"].read_bytes() if rutas["evaluation"].exists() else b""
        actual_status = rutas["status"].read_bytes() if rutas["status"].exists() else b""
        if (actual_eval, actual_status) == (esperado_eval, esperado_status):
            print(f"✔ {args.disease_id}: {etiqueta} — evaluación y estado declarados coinciden")
            print(f"  verdad observada: {evaluation.observation_dataset_id}")
            return 0
        print(f"✖ {args.disease_id}: lo declarado NO es lo que implica la verdad observada")
        print(f"  derivado: {etiqueta} · verdad {evaluation.observation_dataset_id}")
        print(f"  {EVALUATION_FILE}: {'ausente' if not actual_eval else 'difiere'}")
        print(f"  {STATUS_FILE}: {'ausente' if not actual_status else 'difiere'}")
        print(
            f"\n  Actualízalo con:  python -m scripts.prospective_status {args.disease_id} "
            f"--write --observation-dataset-id {evaluation.observation_dataset_id}"
        )
        return 1

    rutas["root"].mkdir(parents=True, exist_ok=True)
    # Primero la evidencia y después el resumen que la referencia: si algo falla en medio, el estado
    # viejo apunta a una evaluación que ya no está y el loader lo rechaza, en vez de aceptar una
    # mezcla silenciosa.
    _write_atomic(rutas["evaluation"], esperado_eval)
    _write_atomic(rutas["status"], esperado_status)
    print(f"✔ {args.disease_id}: {etiqueta}")
    print(f"  verdad observada: {evaluation.observation_dataset_id}")
    print(f"  evaluación: {rutas['evaluation']}")
    print(f"  estado:     {rutas['status']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
