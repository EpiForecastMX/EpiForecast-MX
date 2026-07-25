"""C7.2-A/R15.3 — la metadata canónica del release: cadena, calendario y ``release_manifest.v1``.

Todo lo que el manifest declara se DERIVA de artefactos sellados: la cadena y sus ``code_commit``
salen de los manifiestos de los runs (nunca del git vivo), el calendario del refit y del lineage, los
conteos del dataset y del forecast, y el reparto por motor de la selección congelada. Aquí no hay ni
un padecimiento, ni un motor, ni un 64/47/111 escritos a mano.

El ``release_id`` se calcula ANTES del manifest, desde el payload de identidad, y por eso el manifest
puede llevarlo dentro sin crear un ciclo.

C7.2-A.1: el manifest describe QUÉ modelos hay y de dónde salen, nunca DÓNDE se publican. Canales,
galería, lifecycle y activación son política pública —revocable, y ajena a los modelos— y vivirán en
el ``public_release_pointer.v1`` de C7.5, que apuntará a este ``release_id`` por referencia.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from epiforecast.data.epi_calendar import shift
from epiforecast.runner.artifact_identity import int_of, read_json, require, text_of
from epiforecast.runner.release_contract import (
    BUILDER_VERSION,
    IDENTITY_SCHEMA,
    INTERVAL_METHOD_NONE,
    RELEASE_SCHEMA,
    RUNTIME_CONFIG_SCHEMA,
    identity_payload,
    release_id_for,
)
from epiforecast.runner.release_runtime import RUNTIME_CONFIG_FILE, RUNTIME_DIR
from epiforecast.runner.release_sources import PayloadEntry, ReleaseSources

if TYPE_CHECKING:  # sólo para tipar; en runtime lo pasa el llamador
    from epiforecast.runner.artifact_validation import VerifiedRunnerRuns

RUN_MANIFEST = "run_manifest.json"
DATASET_MANIFEST = "dataset_manifest.json"
RUNTIME_CONFIG_PATH = f"{RUNTIME_DIR}/{RUNTIME_CONFIG_FILE}"


def dataset_digests(sources: ReleaseSources, clave: str) -> str:
    """Un digest declarado por el manifiesto del dataset (``dataset`` o ``config``)."""
    man = read_json(sources.dataset_dir / DATASET_MANIFEST, "dataset: manifiesto")
    digests = man.get("digests")
    require(isinstance(digests, dict), "dataset: manifiesto sin digests")
    return text_of(dict(digests or {}).get(clave), f"dataset: digests[{clave!r}]")


def chain_of(verified: VerifiedRunnerRuns, sources: ReleaseSources) -> dict[str, str]:
    """Los eslabones SELLADOS de la cadena; el ``code_commit`` sale de los runs, no del git vivo."""
    refit = read_json(sources.refit_dir / RUN_MANIFEST, "refit: manifiesto")
    forecast = read_json(sources.forecast_dir / RUN_MANIFEST, "forecast: manifiesto")
    dataset = read_json(sources.dataset_dir / DATASET_MANIFEST, "dataset: manifiesto")
    return {
        "dataset_id": verified.dataset_id,
        "dataset_digest": dataset_digests(sources, "dataset"),
        "policy_digest": verified.policy_digest,
        "policy_name": sources.policy_path.stem,
        "selection_digest": verified.selection_digest,
        "final_selection_digest": verified.final_selection_digest,
        "acceptance_run_id": verified.acceptance_run_id,
        "acceptance_digest": verified.acceptance_digest,
        "refit_run_id": verified.refit_run_id,
        "refit_digest": verified.refit_digest,
        "forecast_run_id": verified.forecast_run_id,
        "dataset_code_commit": text_of(dataset.get("code_commit"), "dataset: code_commit"),
        "refit_code_commit": text_of(refit.get("code_commit"), "refit: code_commit"),
        "forecast_code_commit": text_of(forecast.get("code_commit"), "forecast: code_commit"),
    }


def _calendar(verified: VerifiedRunnerRuns, horizon: int) -> dict[str, Any]:
    """Origen y horizonte MMWR completos, derivados del refit sellado."""
    periodos = []
    actual = verified.train_end
    for _ in range(horizon):
        actual = shift(actual[0], actual[1], 1)
        periodos.append(list(actual))
    return {
        "origin": list(verified.train_end),
        "horizon": horizon,
        "first_period": periodos[0],
        "last_period": periodos[-1],
        "n_train": verified.n_train,
    }


def build_manifest(
    verified: VerifiedRunnerRuns,
    sources: ReleaseSources,
    entries: Sequence[PayloadEntry],
    digests: Mapping[str, str],
    destino: Path,
) -> dict[str, Any]:
    """``release_manifest.v1``: identidad, cadena, calendario, conteos e inventario de payloads.

    Describe QUÉ modelos hay y de dónde salen. No describe dónde se publican: canales, galería y
    lifecycle son política revocable de C7.5 y no viajan en el bundle (C7.2-A.1).
    """
    lineage = read_json(sources.forecast_dir / "lineage.json", "forecast: lineage")
    forecast_man = read_json(sources.forecast_dir / RUN_MANIFEST, "forecast: manifiesto")
    horizon = int_of(lineage.get("horizon"), "forecast: lineage: horizon")

    cadena = chain_of(verified, sources)
    release_id, identity_digest = release_id_for(
        identity_payload(disease_id=verified.disease_id, chain=cadena, payloads=digests)
    )
    esquemas = {e.bundle_path: e.schema for e in entries}
    esquemas[RUNTIME_CONFIG_PATH] = RUNTIME_CONFIG_SCHEMA
    conteos = {
        **dict(verified.counts),
        "models": verified.n_models,
        "horizon": horizon,
        **{
            clave: int_of(valor, f"forecast: counts[{clave!r}]")
            for clave, valor in dict(forecast_man.get("counts") or {}).items()
        },
    }
    return {
        "schema": RELEASE_SCHEMA,
        "release_id": release_id,
        "identity_schema": IDENTITY_SCHEMA,
        "identity_digest": identity_digest,
        "builder_version": BUILDER_VERSION,
        "disease_id": verified.disease_id,
        "chain": cadena,
        "calendar": _calendar(verified, horizon),
        "counts": dict(sorted(conteos.items())),
        "engines": dict(sorted(verified.distribution)),
        "intervals": {
            "interval_method": INTERVAL_METHOD_NONE,
            "uncertainty_available": False,
        },
        "runtime_inputs": sorted(p for p in digests if p.startswith(f"{RUNTIME_DIR}/")),
        "payloads": [
            {
                "path": ruta,
                "bytes": (destino / ruta).stat().st_size,
                "sha256": digests[ruta],
                "schema": esquemas[ruta],
            }
            for ruta in sorted(digests)
        ],
    }
