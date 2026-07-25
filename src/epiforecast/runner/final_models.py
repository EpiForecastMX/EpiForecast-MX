"""F2/C5.3 — contrato COMÚN de modelo final: refit gobernado por la selección aceptada.

Un modelo final es un par (envelope, estado). El envelope declara la identidad completa —SeriesKey
explícita, motor, transformación, configuración, procedencia (dataset/política/selección/aceptación),
ventana de train, ``final_refit``, formato y digest del estado, versiones efectivas— y NUNCA se
infiere nada del nombre del archivo. El estado es lo mínimo que el motor necesita para pronosticar.

Cada motor solo aporta dos funciones, sin condicionales por padecimiento:
- ``FinalFitFn(FinalWindow) -> FinalState``: ajusta con TODA la historia disponible.
- ``FinalForecastFn(FinalState, ForecastRequest) -> {periodo: casos}``: pronostica sin reajustar.

``model_index.json`` sella los envelopes y estados de un motor con sus digests; cargar un modelo
re-verifica ese sello, así que un estado alterado o movido no puede usarse en silencio.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from epiforecast.artifacts.transforms import TransformContract
from epiforecast.data.epi_dataset_spec import COL_GEO_ID, COL_SEX, SeriesKey
from epiforecast.runner import contracts as ct
from epiforecast.runner.manifest import ArtifactRecord

SCHEMA_FINAL_MODEL = "final_model.v1"
SCHEMA_MODEL_INDEX = "model_index.v1"
FINAL_FOLD_ID = "final_refit"

FMT_JSON = "json"
FMT_PROPHET_JSON = "prophet_json"
FMT_STATSMODELS_PICKLE = "statsmodels_pickle"
_TEXT_FORMATS = frozenset({FMT_JSON, FMT_PROPHET_JSON})
_EXTENSIONS = {FMT_JSON: ".json", FMT_PROPHET_JSON: ".json", FMT_STATSMODELS_PICKLE: ".pkl"}

Period = tuple[int, int]


class FinalModelError(ValueError):
    """El contrato de modelo final se violó (estado, envelope o cobertura inválidos)."""


@dataclass(frozen=True)
class FinalWindow:
    """Toda la historia disponible de UNA serie base (ordenada y contigua) para el refit final."""

    spec: ct.TrainingSpec
    train: dict[Period, float]
    train_exposure: dict[Period, float]


@dataclass(frozen=True)
class FinalState:
    """Estado entrenado y serializable, con su formato DECLARADO (nunca inferido del archivo)."""

    fmt: str
    text: str | None = None
    data: bytes | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.fmt not in _EXTENSIONS:
            raise FinalModelError(f"formato de estado no soportado: {self.fmt!r}")
        if (self.fmt in _TEXT_FORMATS) != (self.text is not None):
            raise FinalModelError(f"formato {self.fmt!r}: texto y formato no concuerdan")
        if (self.fmt not in _TEXT_FORMATS) != (self.data is not None):
            raise FinalModelError(f"formato {self.fmt!r}: bytes y formato no concuerdan")

    def to_bytes(self) -> bytes:
        return self.text.encode("utf-8") if self.text is not None else (self.data or b"")


@dataclass(frozen=True)
class ForecastRequest:
    """Lo que necesita un motor para pronosticar desde su estado: periodos y exposición futura."""

    transform: TransformContract
    periods: tuple[Period, ...]
    exposure: dict[Period, float] = field(default_factory=dict)

    def exposure_array(self) -> list[float] | None:
        if not self.transform.requires_exposure:
            return None
        faltan = [p for p in self.periods if p not in self.exposure]
        if faltan:
            raise FinalModelError(f"exposición futura ausente en {faltan[:3]}")
        return [float(self.exposure[p]) for p in self.periods]


FinalFitFn = Callable[[FinalWindow], FinalState]
FinalForecastFn = Callable[[FinalState, ForecastRequest], dict[Period, float]]


def model_stem(key: SeriesKey) -> str:
    """Nombre de archivo estable; la identidad vive en el envelope, no aquí."""
    return f"{key.geography_id}_{key.sex}"


def build_envelope(
    window: FinalWindow,
    state: FinalState,
    provenance: dict[str, Any],
    versions: dict[str, str],
    state_path: str,
    state_digest: str,
) -> dict[str, Any]:
    """Envelope del modelo final: identidad EXPLÍCITA + procedencia + estado declarado."""
    periods = sorted(window.train)
    key = window.spec.key
    return {
        "artifact_schema_version": SCHEMA_FINAL_MODEL,
        "disease_id": key.disease_id,
        "series_key": {
            "geography_level": key.geography_level,
            "geography_id": key.geography_id,
            "sex": key.sex,
            "frequency": key.frequency,
        },
        "engine": window.spec.engine,
        "transform": window.spec.transform.to_dict(),
        "transform_digest": window.spec.transform.digest(),
        "config": state.config,
        "config_digest": hashlib.sha256(
            json.dumps(state.config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "provenance": provenance,
        "train_start": list(periods[0]),
        "train_end": list(periods[-1]),
        "n_train": len(periods),
        "seed": window.spec.seed,
        "final_refit": True,
        "state_format": state.fmt,
        "state_path": state_path,
        "state_digest": state_digest,
        "library_versions": versions,
    }


def write_model(
    models_dir: Path,
    window: FinalWindow,
    state: FinalState,
    provenance: dict[str, Any],
    versions: dict[str, str],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Escribe estado + envelope de UNA serie. Devuelve (envelope, digests de ambos archivos)."""
    models_dir.mkdir(parents=True, exist_ok=True)
    stem = model_stem(window.spec.key)
    state_name = f"{stem}.state{_EXTENSIONS[state.fmt]}"
    payload = state.to_bytes()
    (models_dir / state_name).write_bytes(payload)
    state_digest = hashlib.sha256(payload).hexdigest()

    envelope = build_envelope(window, state, provenance, versions, state_name, state_digest)
    envelope_name = f"{stem}.envelope.json"
    envelope_bytes = json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8")
    (models_dir / envelope_name).write_bytes(envelope_bytes)
    return envelope, {
        "envelope_path": envelope_name,
        "envelope_digest": hashlib.sha256(envelope_bytes).hexdigest(),
        "state_path": state_name,
        "state_digest": state_digest,
    }


def write_artifact_record(run_dir: Path, path: Path, schema: str) -> ArtifactRecord:
    """``ArtifactRecord`` con digest de un archivo ya escrito (ruta relativa al run)."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRecord(str(path.relative_to(run_dir)), digest, schema, validated=True)


def write_index(
    run_dir: Path, engine: str, entries: list[dict[str, Any]], summary: dict[str, Any]
) -> ArtifactRecord:
    """``model_index.json``: sella cada envelope y estado del motor con su digest."""
    models_dir = run_dir / "models" / engine
    models_dir.mkdir(parents=True, exist_ok=True)
    index = {
        "schema": SCHEMA_MODEL_INDEX,
        "engine": engine,
        "n_models": len(entries),
        **summary,
        "models": sorted(entries, key=lambda e: (e[COL_GEO_ID], e[COL_SEX])),
    }
    path = models_dir / "model_index.json"
    path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ArtifactRecord(
        str(path.relative_to(run_dir)), digest, SCHEMA_MODEL_INDEX, validated=True
    )


def load_models(run_dir: Path, engine: str) -> list[tuple[dict[str, Any], FinalState]]:
    """Carga los modelos de un motor VERIFICANDO el sello del índice (envelope y estado)."""
    index_path = run_dir / "models" / engine / "model_index.json"
    if not index_path.exists():
        raise FinalModelError(f"no hay model_index.json para el motor {engine!r}")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schema") != SCHEMA_MODEL_INDEX:
        raise FinalModelError(f"schema de índice inesperado: {index.get('schema')!r}")
    models_dir = index_path.parent
    out: list[tuple[dict[str, Any], FinalState]] = []
    for entry in index["models"]:
        envelope_path = models_dir / entry["envelope_path"]
        envelope_bytes = envelope_path.read_bytes()
        if hashlib.sha256(envelope_bytes).hexdigest() != entry["envelope_digest"]:
            raise FinalModelError(f"envelope alterado: {entry['envelope_path']}")
        envelope = json.loads(envelope_bytes)
        state_bytes = (models_dir / envelope["state_path"]).read_bytes()
        if hashlib.sha256(state_bytes).hexdigest() != envelope["state_digest"]:
            raise FinalModelError(f"estado alterado: {envelope['state_path']}")
        if not envelope.get("final_refit"):
            raise FinalModelError(f"{envelope['state_path']}: no es un refit final")
        fmt = envelope["state_format"]
        state = FinalState(
            fmt=fmt,
            text=state_bytes.decode("utf-8") if fmt in _TEXT_FORMATS else None,
            data=None if fmt in _TEXT_FORMATS else state_bytes,
            config=envelope["config"],
        )
        out.append((envelope, state))
    return out


def final_windows(
    products: pd.DataFrame, assigned: set[tuple[str, str]], ctx: Any
) -> list[FinalWindow]:
    """Ventanas de refit: TODA la historia de cada serie asignada al motor (nunca derivadas)."""
    from epiforecast.data.epi_dataset_spec import (
        BASE_SEXES,
        COL_EPI_WEEK,
        COL_EPI_YEAR,
        COL_EXPOSURE,
        COL_GEO_LEVEL,
        COL_Y_CASES,
        GEO_LEVEL_ESTADO,
    )

    base = products[
        (products[COL_GEO_LEVEL] == GEO_LEVEL_ESTADO) & products[COL_SEX].isin(BASE_SEXES)
    ]
    windows: list[FinalWindow] = []
    for (cve, sexo), grp in base.groupby([COL_GEO_ID, COL_SEX], sort=True):
        if (str(cve), str(sexo)) not in assigned:
            continue
        train: dict[Period, float] = {}
        exposure: dict[Period, float] = {}
        for y, w, cases, exp in zip(
            grp[COL_EPI_YEAR], grp[COL_EPI_WEEK], grp[COL_Y_CASES], grp[COL_EXPOSURE], strict=True
        ):
            period = (int(y), int(w))
            train[period] = float(cases)
            exposure[period] = float(exp)
        windows.append(
            FinalWindow(
                ctx.spec_for(str(cve), str(sexo)),
                dict(sorted(train.items())),
                dict(sorted(exposure.items())),
            )
        )
    if len(windows) != len(assigned):
        raise FinalModelError(f"series asignadas no resueltas: {len(windows)} de {len(assigned)}")
    return windows
