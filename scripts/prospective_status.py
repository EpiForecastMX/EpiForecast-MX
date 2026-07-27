"""Actualiza el estado prospectivo declarado de un padecimiento, de forma reproducible.

Editar ``prospective_status.json`` a mano contradice el objetivo del contrato: el estado es lo que
la verdad observada dice que es, no lo que alguien escriba (R76-P1). Este comando lo DERIVA del
gate congelado, del release sellado y del dataset, y sólo entonces lo compara o lo escribe.

    python -m scripts.prospective_status <padecimiento> --check    # no muta nada; rc≠0 si difiere
    python -m scripts.prospective_status <padecimiento> --write    # escritura atómica

Genérico: el padecimiento es un argumento; la identidad de los insumos se resuelve por el registry
y por el propio bundle —nunca por nombres inferidos ni rutas absolutas—.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from epiforecast import registry
from epiforecast.publication.prospective import (
    GATE_WEEKS,
    FrozenGate,
    build_control,
    evaluate,
    read_base_history,
)
from epiforecast.publication.status import (
    GATE_FILE,
    STATUS_FILE,
    ProspectiveStatus,
    config_root,
    load_gate,
)
from epiforecast.runner.artifact_identity import ArtifactValidationError, equal
from epiforecast.runner.release_contract import canonical_json
from epiforecast.runner.release_loader import verify_bundle
from epiforecast.runner.release_reproduce import read_bundled_frame
from epiforecast.runner.release_sources import DIR_FORECAST
from epiforecast.runner.release_store import default_releases_root, release_path


def _dataset_csv(dataset_id: str) -> Path:
    from epiforecast.registry_doctor import _runs_root

    return _runs_root() / dataset_id / "epi_dataset_v2.csv"


def derive_status(disease_id: str, *, config_root_path: Path | None = None) -> ProspectiveStatus:
    """Estado que la verdad observada IMPLICA hoy, para el gate declarado de ese padecimiento."""
    raiz = (config_root_path if config_root_path is not None else config_root()) / disease_id
    gate: FrozenGate = load_gate(raiz / GATE_FILE)
    equal(f"{disease_id}: disease_id del gate", gate.disease_id, disease_id)

    declarado = str(registry.require(disease_id).artifact_source.release_id)
    equal(f"{disease_id}: release del gate contra el registry", gate.release_id, declarado)

    sede = release_path(default_releases_root(), disease_id, gate.release_id)
    verificado = verify_bundle(sede)
    base = read_bundled_frame(sede / DIR_FORECAST / "forecast_base.csv", "forecast_base")
    columnas = ["geography_id", "sex", "epi_year", "epi_week", "y_pred_cases"]
    candidato = (
        base[columnas]
        .sort_values(["geography_id", "sex", "epi_year", "epi_week"])
        .reset_index(drop=True)
    )
    historia = read_base_history(_dataset_csv(str(verificado.chain["dataset_id"])))

    control = build_control(historia, gate.origin, gate.horizon)
    resultado = evaluate(gate, candidato, control, historia)
    semanas = tuple((int(a), int(s)) for a, s in resultado["weeks"])
    return ProspectiveStatus(
        disease_id=gate.disease_id,
        release_id=gate.release_id,
        gate_digest=gate.digest(),
        verdict=str(resultado["verdict"]),
        weeks_required=GATE_WEEKS,
        weeks_available=len(semanas),
        completed_weeks=semanas,
        target_weeks=gate.target_weeks,
    )


def _write_atomic(destino: Path, datos: bytes) -> None:
    """Temporal + rename: o queda el estado nuevo entero, o el anterior intacto."""
    tmp = destino.with_suffix(f".tmp-{destino.suffix.lstrip('.')}")
    try:
        tmp.write_bytes(datos)
        tmp.replace(destino)
    finally:
        tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("disease_id")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--check", action="store_true", help="compara; no escribe nada")
    grupo.add_argument("--write", action="store_true", help="escribe el estado derivado")
    parser.add_argument("--config-root", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        derivado = derive_status(args.disease_id, config_root_path=args.config_root)
    except (ArtifactValidationError, OSError, ValueError) as exc:
        print(f"✖ no se pudo derivar el estado: {exc}", file=sys.stderr)
        return 2

    raiz = (args.config_root if args.config_root is not None else config_root()) / args.disease_id
    destino = raiz / STATUS_FILE
    esperado = canonical_json(derivado.payload())
    etiqueta = derivado.progress_label()

    if args.check:
        actual = destino.read_bytes() if destino.exists() else b""
        if actual == esperado:
            print(f"✔ {args.disease_id}: {etiqueta} — el archivo declarado coincide")
            return 0
        print(f"✖ {args.disease_id}: el estado declarado NO es el que implica la verdad observada")
        print(f"  derivado: {etiqueta}")
        print(f"  archivo : {'ausente' if not actual else 'difiere'}")
        print(
            f"\n  Actualízalo con:  python -m scripts.prospective_status {args.disease_id} --write"
        )
        return 1

    raiz.mkdir(parents=True, exist_ok=True)
    _write_atomic(destino, esperado)
    print(f"✔ {args.disease_id}: {etiqueta} — escrito en {destino}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
