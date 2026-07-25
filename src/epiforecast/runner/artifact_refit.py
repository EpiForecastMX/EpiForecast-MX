"""C7.1/Acción 3 — el resumen del refit y el lineage del forecast como contrato.

``refit_summary.json`` declara el portafolio refiteado y la procedencia de la cadena;
``lineage.json`` declara de qué refit sale el forecast y qué productos cubre. Ambos deben repetir
exactamente lo que ya está verificado río arriba: la ventana la fija el dataset, el reparto lo fija
la selección congelada y los conteos los fija el manifiesto del dataset.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from epiforecast.data.epi_dataset_spec import GEO_LEVEL_ESTADO
from epiforecast.runner.artifact_identity import (
    equal,
    input_digest,
    provenance_of,
    read_json,
    require,
    text_of,
)
from epiforecast.runner.manifest import RunManifest

SCHEMA_REFIT_SUMMARY = "refit_summary.v1"
SCHEMA_LINEAGE = "lineage.v1"
SUMMARY_FILE = "refit_summary.json"
# Digests de la cadena que el resumen debe repetir desde el manifiesto del refit.
CHAIN_DIGESTS = ("acceptance_digest", "final_selection_digest", "selection_digest")


@dataclass(frozen=True, slots=True)
class Summary:
    """Lo que ``refit_summary.json`` declara y el resto de la cadena debe repetir."""

    acceptance_run_id: str
    selection_run_id: str
    train_end: tuple[int, int]
    n_train_values: tuple[int, ...]


def read_summary(refit_dir: Path, man: RunManifest, reparto: Mapping[str, int]) -> Summary:
    """``refit_summary.json``: modelos finales, reparto por motor y procedencia de la cadena."""
    who = "refit: refit_summary"
    resumen = read_json(refit_dir / SUMMARY_FILE, who, SCHEMA_REFIT_SUMMARY)
    equal(f"{who}: run_id", resumen.get("run_id"), man.run_id)
    equal(f"{who}: disease_id", resumen.get("disease_id"), man.disease_id)
    equal(f"{who}: code_commit", resumen.get("code_commit"), man.code_commit)
    require(resumen.get("final_refit") is True, f"{who}: no declara final_refit")
    total = sum(reparto.values())
    for campo in ("n_models", "n_series_selected"):
        equal(f"{who}: {campo}", resumen.get(campo), total)
    for campo in ("distribution", "engines"):
        equal(f"{who}: {campo}", resumen.get(campo), dict(reparto))
    equal(
        f"{who}: geography_levels",
        list(resumen.get("geography_levels") or []),
        [GEO_LEVEL_ESTADO],
    )
    procedencia = resumen.get("provenance")
    provenance_of(procedencia, {c: input_digest(man, c, who) for c in CHAIN_DIGESTS}, who)
    origen = dict(procedencia or {})  # type: ignore[arg-type]
    return Summary(
        acceptance_run_id=text_of(origen.get("acceptance_run_id"), f"{who}: acceptance_run_id"),
        selection_run_id=text_of(origen.get("selection_run_id"), f"{who}: selection_run_id"),
        train_end=tuple(resumen.get("train_end") or ()),  # type: ignore[arg-type]
        n_train_values=tuple(resumen.get("n_train_values") or ()),
    )


def check_lineage(
    forecast_dir: Path,
    refit_run_id: str,
    refit_digest: str,
    reparto: Mapping[str, int],
    conteos: Mapping[str, int],
    train_end: tuple[int, int],
) -> None:
    """``lineage.json``: el forecast proviene del refit sellado y cubre los mismos productos."""
    who = "forecast: lineage"
    lineage = read_json(forecast_dir / "lineage.json", who, SCHEMA_LINEAGE)
    equal(f"{who}: refit_run_id", lineage.get("refit_run_id"), refit_run_id)
    equal(f"{who}: refit_digest", lineage.get("refit_digest"), refit_digest)
    equal(f"{who}: engines", lineage.get("engines"), dict(reparto))
    equal(f"{who}: base_series", lineage.get("base_series"), conteos.get("base"))
    equal(f"{who}: derived_products", lineage.get("derived_products"), conteos.get("derived"))
    equal(f"{who}: products", lineage.get("products"), conteos.get("products"))
    equal(f"{who}: origin", tuple(lineage.get("origin") or ()), train_end)
