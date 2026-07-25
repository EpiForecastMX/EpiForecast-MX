"""C7.2-A/R15-C2 — resolución de las RUTAS FUENTE de un release desde los runs sellados.

``VerifiedRunnerRuns`` es identidad, no un contenedor de archivos: no lleva ``runs_root``, ni las
rutas de envelopes y estados, ni los bytes de política, selección, aceptación o insumos. Esta capa
—impura a propósito— recibe roots explícitos, abre los inventarios ya verificados y devuelve rutas
tipadas, con el digest que cada manifiesto DECLARA para volver a comprobarlo al copiar.

Nada se infiere del nombre de un archivo: los envelopes y estados salen de ``model_index.json``, el
catálogo y la exposición de ``config_effective.json``, y la política del path que se inyecta.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from epiforecast.data.epi_dataset_spec import BASE_SEXES, COL_CVE_ENT, COL_EXPOSURE, COL_SEXO
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    mapping_of,
    read_json,
    require,
    sequence_of,
    text_of,
)
from epiforecast.runner.release_contract import sha256_bytes
from epiforecast.runner.release_runtime import RUNTIME_DIR

if TYPE_CHECKING:  # sólo para tipar; en runtime lo pasa el llamador
    from epiforecast.runner.artifact_validation import VerifiedRunnerRuns

DATASET_CSV = "epi_dataset_v2.csv"
DATASET_CONFIG = "config_effective.json"
INPUTS_DIR = "inputs"
SELECTION_FILE = "final_selection.csv"
ACCEPTANCE_FILE = "acceptance.json"
SUMMARY_FILE = "refit_summary.json"
RUN_MANIFEST = "run_manifest.json"
MODEL_INDEX = "model_index.json"

# Subdirectorios del bundle (genéricos: ningún padecimiento ni motor aparece aquí).
DIR_POLICY = "policy"
DIR_SELECTION = "selection"
DIR_REFIT = "refit"
DIR_FORECAST = "forecast"
ACCEPTANCE_MANIFEST = "acceptance_run_manifest.json"
# Salidas del forecast que el release DEBE llevar (el consolidado, no los parciales por job).
FORECAST_PAYLOADS: tuple[str, ...] = (
    "forecast.csv",
    "forecast_base.csv",
    "model_inventory.csv",
    "lineage.json",
)

# Schemas de los archivos que el release introduce por su cuenta; el resto los declara el
# manifiesto del run de origen y se propagan tal cual.
SCHEMA_POLICY = "selection_policy.v1"
SCHEMA_RUN_MANIFEST = "run_manifest.v1"
SCHEMA_ENVELOPE = "final_model.v1"
SCHEMA_STATE = "final_model_state.v1"
SCHEMA_GEO_CATALOG = "geo_catalog.v1"
SCHEMA_EXPOSURE = "exposure_projection.v1"

SeriesId = tuple[str, str]


@dataclass(frozen=True, slots=True)
class ReleaseSources:
    """Rutas fuente EXPLÍCITAS de un release; inyectables enteras para probar sin `runs/`."""

    runs_root: Path
    dataset_dir: Path
    acceptance_dir: Path
    refit_dir: Path
    forecast_dir: Path
    policy_path: Path
    catalog_path: Path
    exposure_path: Path
    dataset_config_path: Path
    dataset_csv_path: Path


@dataclass(frozen=True, slots=True)
class PayloadEntry:
    """Un archivo del bundle: destino relativo, origen, schema y el digest que se declara."""

    bundle_path: str
    source_path: Path
    schema: str
    declared_digest: str | None = None


def _existing(path: Path, label: str) -> Path:
    require(path.is_file(), f"{label}: no existe {path.name}")
    return path


def resolve_sources(
    verified: VerifiedRunnerRuns, *, runs_root: Path, policy_path: Path
) -> ReleaseSources:
    """Rutas fuente de la cadena ya verificada. Los roots se inyectan; nada se busca solo."""
    dataset_dir = runs_root / verified.dataset_id
    inputs = dataset_dir / INPUTS_DIR
    config_path = _existing(inputs / DATASET_CONFIG, "dataset: config efectiva")
    config = read_json(config_path, "dataset: config efectiva")
    catalogo = mapping_of(config.get("geo_catalog"), "dataset: geo_catalog")
    exposicion = mapping_of(config.get("exposure"), "dataset: exposure")
    catalog_name = Path(text_of(catalogo.get("path"), "dataset: geo_catalog.path")).name
    source_id = text_of(exposicion.get("source_id"), "dataset: exposure.source_id")
    return ReleaseSources(
        runs_root=runs_root,
        dataset_dir=dataset_dir,
        acceptance_dir=runs_root / verified.acceptance_run_id,
        refit_dir=runs_root / verified.refit_run_id,
        forecast_dir=runs_root / verified.forecast_run_id,
        policy_path=_existing(policy_path, "política"),
        catalog_path=_existing(inputs / catalog_name, "dataset: catálogo geográfico"),
        exposure_path=_existing(inputs / f"exposure_{source_id}.csv", "dataset: exposición"),
        dataset_config_path=config_path,
        dataset_csv_path=_existing(dataset_dir / DATASET_CSV, "dataset: csv"),
    )


def read_dataset_config(sources: ReleaseSources, expected_digest: str) -> dict[str, Any]:
    """Config efectiva del dataset, re-verificada contra el ``config`` digest de su manifiesto.

    El archivo no viaja al bundle (lleva una ruta relativa al workspace), pero su identidad sí: se
    recalcula el digest con la MISMA serialización que lo produjo y se propaga como
    ``dataset_config_digest`` dentro de ``runtime_config.json``.
    """
    who = "dataset: config efectiva"
    config = read_json(sources.dataset_config_path, who)
    try:
        canonico = json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:  # pragma: no cover — read_json garantiza un dict JSON
        raise ArtifactValidationError(f"{who}: no reserializable ({exc})") from exc
    equal(f"{who}: digest", sha256_bytes(canonico), expected_digest)
    return {**config, "__digest__": expected_digest}


def dataset_exposure(sources: ReleaseSources, geography_ids: list[str]) -> dict[SeriesId, int]:
    """Exposición SELLADA por serie base según el dataset: constante por ``(cve_ent, sexo)``."""
    who = f"dataset: {DATASET_CSV}"
    try:
        frame = pd.read_csv(
            sources.dataset_csv_path,
            usecols=[COL_CVE_ENT, COL_SEXO, COL_EXPOSURE],
            dtype={COL_CVE_ENT: str},
            low_memory=False,
        )
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{who}: ilegible ({exc})") from exc
    salida: dict[SeriesId, int] = {}
    for clave, grupo in frame.groupby([COL_CVE_ENT, COL_SEXO], sort=True):
        valores = set(grupo[COL_EXPOSURE].tolist())
        equal(f"{who}: exposición constante de {clave}", len(valores), 1)
        valor = float(valores.pop())
        require(valor.is_integer() and valor > 0, f"{who}: exposición inválida en {clave}")
        salida[(str(clave[0]), str(clave[1]))] = int(valor)
    esperado = sorted((geo, sexo) for geo in geography_ids for sexo in BASE_SEXES)
    equal(f"{who}: universo de exposición", sorted(salida), esperado)
    return salida


def _declared(man: Mapping[str, Any], label: str) -> dict[str, tuple[str, str]]:
    """``ruta -> (digest, schema)`` declarados por un manifiesto de run (globales y de cada job)."""
    grupos = [sequence_of(man.get("artifacts") or [], f"{label}: artifacts")]
    for engine, job in mapping_of(man.get("jobs") or {}, f"{label}: jobs").items():
        datos = mapping_of(job, f"{label}/{engine}")
        grupos.append(sequence_of(datos.get("artifacts") or [], f"{label}/{engine}: artifacts"))
    salida: dict[str, tuple[str, str]] = {}
    for registros in grupos:
        for crudo in registros:
            registro = mapping_of(crudo, f"{label}: artifacts[]")
            ruta = text_of(registro.get("path"), f"{label}: path")
            salida[ruta] = (
                text_of(registro.get("digest"), f"{label}: digest de {ruta}"),
                text_of(registro.get("schema"), f"{label}: schema de {ruta}"),
            )
    return salida


def _from_manifest(
    declarados: Mapping[str, tuple[str, str]], ruta: str, label: str
) -> tuple[str, str]:
    """Digest y schema que el manifiesto del run declara para ``ruta`` (sin declarar = error)."""
    registro = declarados.get(ruta)
    require(registro is not None, f"{label}: el manifiesto no declara {ruta}")
    return registro  # type: ignore[return-value]


def _model_payloads(
    sources: ReleaseSources, engines: tuple[str, ...], declarados: Mapping[str, tuple[str, str]]
) -> list[PayloadEntry]:
    """Índice + envelope + estado de cada motor, enumerados por lo que DECLARA el índice."""
    entradas: list[PayloadEntry] = []
    for engine in engines:
        relativo = f"models/{engine}/{MODEL_INDEX}"
        index_path = _existing(sources.refit_dir / relativo, f"refit/{engine}: índice")
        digest, schema = _from_manifest(declarados, relativo, f"refit/{engine}")
        entradas.append(PayloadEntry(f"{DIR_REFIT}/{relativo}", index_path, schema, digest))
        index = read_json(index_path, f"refit/{engine}: {MODEL_INDEX}")
        for crudo in sequence_of(index.get("models") or [], f"refit/{engine}: models"):
            entrada = mapping_of(crudo, f"refit/{engine}: models[]")
            for campo, clave_digest, esquema in (
                ("envelope_path", "envelope_digest", SCHEMA_ENVELOPE),
                ("state_path", "state_digest", SCHEMA_STATE),
            ):
                nombre = text_of(entrada.get(campo), f"refit/{engine}: {campo}")
                require(
                    "/" not in nombre, f"refit/{engine}: {campo} debe ser un nombre de archivo"
                )
                entradas.append(
                    PayloadEntry(
                        f"{DIR_REFIT}/models/{engine}/{nombre}",
                        _existing(index_path.parent / nombre, f"refit/{engine}: {nombre}"),
                        esquema,
                        text_of(entrada.get(clave_digest), f"refit/{engine}: {clave_digest}"),
                    )
                )
    return entradas


def payload_plan(verified: VerifiedRunnerRuns, sources: ReleaseSources) -> list[PayloadEntry]:
    """Inventario COMPLETO de payloads del bundle (sin manifest ni checksums), ordenado por ruta."""
    refit_man = read_json(sources.refit_dir / RUN_MANIFEST, "refit: manifiesto")
    forecast_man = read_json(sources.forecast_dir / RUN_MANIFEST, "forecast: manifiesto")
    declarados_forecast = _declared(forecast_man, "forecast")
    declarados_acta = _declared(
        read_json(sources.acceptance_dir / RUN_MANIFEST, "aceptación: manifiesto"), "aceptación"
    )

    entradas: list[PayloadEntry] = [
        PayloadEntry(
            f"{DIR_POLICY}/{sources.policy_path.name}",
            sources.policy_path,
            SCHEMA_POLICY,
            verified.policy_digest,
        ),
        PayloadEntry(
            f"{DIR_SELECTION}/{SELECTION_FILE}",
            _existing(sources.acceptance_dir / SELECTION_FILE, "aceptación: selección"),
            _from_manifest(declarados_acta, SELECTION_FILE, "aceptación")[1],
            verified.final_selection_digest,
        ),
        PayloadEntry(
            f"{DIR_SELECTION}/{ACCEPTANCE_FILE}",
            _existing(sources.acceptance_dir / ACCEPTANCE_FILE, "aceptación: veredicto"),
            _from_manifest(declarados_acta, ACCEPTANCE_FILE, "aceptación")[1],
            verified.acceptance_digest,
        ),
        PayloadEntry(
            f"{DIR_SELECTION}/{ACCEPTANCE_MANIFEST}",
            _existing(sources.acceptance_dir / RUN_MANIFEST, "aceptación: manifiesto"),
            SCHEMA_RUN_MANIFEST,
        ),
        PayloadEntry(
            f"{DIR_REFIT}/{RUN_MANIFEST}",
            _existing(sources.refit_dir / RUN_MANIFEST, "refit"),
            SCHEMA_RUN_MANIFEST,
        ),
        PayloadEntry(
            f"{DIR_REFIT}/{SUMMARY_FILE}",
            _existing(sources.refit_dir / SUMMARY_FILE, "refit: resumen"),
            _from_manifest(_declared(refit_man, "refit"), SUMMARY_FILE, "refit")[1],
            verified.refit_digest,
        ),
        PayloadEntry(
            f"{DIR_FORECAST}/{RUN_MANIFEST}",
            _existing(sources.forecast_dir / RUN_MANIFEST, "forecast"),
            SCHEMA_RUN_MANIFEST,
        ),
        *(
            PayloadEntry(
                f"{DIR_FORECAST}/{nombre}",
                _existing(sources.forecast_dir / nombre, f"forecast: {nombre}"),
                _from_manifest(declarados_forecast, nombre, "forecast")[1],
                _from_manifest(declarados_forecast, nombre, "forecast")[0],
            )
            for nombre in FORECAST_PAYLOADS
        ),
        *_model_payloads(sources, verified.engines, _declared(refit_man, "refit")),
        PayloadEntry(
            f"{RUNTIME_DIR}/{sources.catalog_path.name}", sources.catalog_path, SCHEMA_GEO_CATALOG
        ),
        PayloadEntry(
            f"{RUNTIME_DIR}/{sources.exposure_path.name}", sources.exposure_path, SCHEMA_EXPOSURE
        ),
    ]
    rutas = [e.bundle_path for e in entradas]
    equal("plan de payloads: rutas únicas", len(set(rutas)), len(rutas))
    return sorted(entradas, key=lambda e: e.bundle_path)
