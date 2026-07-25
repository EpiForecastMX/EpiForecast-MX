"""C7.1/Acción 3 — el portafolio de modelos finales, descrito por los artefactos y no por constantes.

Qué series DEBEN existir se deriva del catálogo geográfico trackeado × ``BASE_SEXES``; qué motor le
toca a cada una se deriva de ``final_selection.csv`` sellado; la ventana viene de
``artifact_dataset``. Ningún padecimiento, motor, clave INEGI, total de modelos ni ventana de
entrenamiento está escrito aquí: si el portafolio cambia, cambia el artefacto, no este módulo.

Selección, manifiesto, ``model_index.json``, envelopes y estados deben describir EXACTAMENTE el
mismo portafolio; un modelo faltante, duplicado, extra, no indexado o asignado a otro motor es un
error.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from epiforecast.artifacts.transforms import TransformContract
from epiforecast.data.epi_dataset_spec import (
    BASE_SEXES,
    COL_GEO_ID,
    COL_SEX,
    FREQ_EPI_WEEK,
    GEO_LEVEL_ESTADO,
)
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    mapping_of,
    provenance_of,
    read_json,
    require,
    sequence_of,
    sha256_file,
    text_of,
)
from epiforecast.runner.final_models import (
    SCHEMA_FINAL_MODEL,
    SCHEMA_MODEL_INDEX,
    load_models,
)

SELECTION_FILE = "final_selection.csv"
COL_SELECTED_ENGINE = "selected_engine"

SeriesId = tuple[str, str]


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Identidad SELLADA de un modelo final, ya contrastada entre índice, envelope y estado.

    Se propaga para que el inventario del forecast compare contra esto y no vuelva a abrir modelos
    ni infiera nada. Dos series pueden compartir `state_digest` si eso es lo que declaran sus
    estados sellados: la identidad es la igualdad por `SeriesKey`, no "todos distintos".
    """

    series: SeriesId
    engine: str
    n_train: int
    train_end: tuple[int, int]
    state_format: str
    state_digest: str


@dataclass(frozen=True, slots=True)
class ModelExpectations:
    """Identidad que TODO modelo final del portafolio debe repetir sin excepción."""

    disease_id: str
    n_train: int
    train_end: tuple[int, int]
    provenance: Mapping[str, str]


def read_selection(refit_dir: Path, expected_digest: str) -> dict[SeriesId, str]:
    """``(geography_id, sex) -> motor`` desde la selección congelada, re-verificando su digest."""
    path = refit_dir / SELECTION_FILE
    require(path.exists(), f"refit: falta {SELECTION_FILE}")
    equal(f"refit: digest de {SELECTION_FILE}", sha256_file(path, SELECTION_FILE), expected_digest)
    try:
        frame = pd.read_csv(path, dtype=str)
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{SELECTION_FILE}: ilegible ({exc})") from exc
    faltan = {COL_GEO_ID, COL_SEX, COL_SELECTED_ENGINE} - set(frame.columns)
    require(not faltan, f"{SELECTION_FILE}: faltan columnas {sorted(faltan)}")
    seleccion: dict[SeriesId, str] = {}
    for geo, sex, engine in zip(
        frame[COL_GEO_ID], frame[COL_SEX], frame[COL_SELECTED_ENGINE], strict=True
    ):
        clave = (
            text_of(geo, f"{SELECTION_FILE}: geography_id"),
            text_of(sex, f"{SELECTION_FILE}: sex"),
        )
        require(clave not in seleccion, f"{SELECTION_FILE}: serie duplicada {clave}")
        seleccion[clave] = text_of(engine, f"{SELECTION_FILE}: motor de {clave}")
    return seleccion


def check_universe(selection: Mapping[SeriesId, str], geography_ids: list[str]) -> None:
    """El universo entrenable es catálogo × sexos base: ni una serie de menos ni una ajena."""
    esperado = {(geo, sex) for geo in geography_ids for sex in BASE_SEXES}
    faltan = sorted(esperado - set(selection))
    sobran = sorted(set(selection) - esperado)
    require(not faltan, f"selección: faltan {len(faltan)} series del catálogo, p.ej. {faltan[:3]}")
    require(not sobran, f"selección: {len(sobran)} series ajenas al catálogo, p.ej. {sobran[:3]}")


def distribution(selection: Mapping[SeriesId, str]) -> dict[str, int]:
    """Reparto motor → nº de series, derivado de la selección (no de un diccionario escrito)."""
    reparto: dict[str, int] = {}
    for engine in selection.values():
        reparto[engine] = reparto.get(engine, 0) + 1
    return dict(sorted(reparto.items()))


def _transform_digest(raw: object, label: str) -> str:
    """Digest recalculado del contrato de transformación declarado (no se cree el escrito)."""
    if not isinstance(raw, dict):
        raise ArtifactValidationError(f"{label}: transform ausente o mal formado")
    try:
        return TransformContract.from_dict(raw).digest()
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{label}: transform inválido ({exc})") from exc


def _check_index(
    refit_dir: Path, engine: str, esperados: int, exp: ModelExpectations
) -> tuple[list[dict[str, Any]], str]:
    """``model_index.json`` de un motor: identidad, conteos, ventana y procedencia.

    Devuelve sus entradas y el digest de transformación para contrastarlos, una a una, contra los
    envelopes cargados: el índice no puede decir algo distinto del modelo que sella (R5.2).
    """
    who = f"refit/{engine}: model_index"
    index = read_json(refit_dir / "models" / engine / "model_index.json", who, SCHEMA_MODEL_INDEX)
    equal(f"{who}: disease_id", index.get("disease_id"), exp.disease_id)
    equal(f"{who}: engine", index.get("engine"), engine)
    require(index.get("final_refit") is True, f"{who}: no declara final_refit")
    for campo in ("n_models", "n_assigned"):
        equal(f"{who}: {campo}", index.get(campo), esperados)
    entradas = [
        mapping_of(entrada, f"{who}: entrada")
        for entrada in sequence_of(index.get("models") or [], f"{who}: models")
    ]
    equal(f"{who}: entradas", len(entradas), esperados)
    equal(f"{who}: train_end", tuple(index.get("train_end") or ()), exp.train_end)
    equal(f"{who}: n_train_values", list(index.get("n_train_values") or []), [exp.n_train])
    provenance_of(index.get("provenance"), dict(exp.provenance), who)
    digest = _transform_digest(index.get("transform"), who)
    equal(f"{who}: transform_digest", index.get("transform_digest"), digest)
    return entradas, digest


def _check_entry(entry: Mapping[str, Any], envelope: Mapping[str, Any], who: str) -> None:
    """La entrada del índice y el envelope que sella describen el MISMO modelo.

    ``load_models`` resuelve el estado por lo que dice el envelope; sin este contraste, una entrada
    podía declarar otra serie, otro estado y otro digest y el portafolio seguía validando (R5.2).
    """
    key = mapping_of(envelope.get("series_key") or {}, f"{who}: series_key")
    equal(f"{who}: geography_id del índice", entry.get(COL_GEO_ID), key.get("geography_id"))
    equal(f"{who}: sex del índice", entry.get(COL_SEX), key.get("sex"))
    for campo in ("n_train", "state_path", "state_digest", "state_format"):
        equal(f"{who}: {campo} del índice", entry.get(campo), envelope.get(campo))
    for campo in ("train_start", "train_end"):
        equal(
            f"{who}: {campo} del índice",
            tuple(entry.get(campo) or ()),
            tuple(envelope.get(campo) or ()),
        )


def _check_engine_dir(models_dir: Path, entradas: list[dict[str, Any]], who: str) -> None:
    """En el directorio del motor no puede haber ningún archivo de modelo fuera del índice."""
    declarados = {"model_index.json"}
    for entry in entradas:
        declarados.add(text_of(entry.get("envelope_path"), f"{who}: envelope_path"))
        declarados.add(text_of(entry.get("state_path"), f"{who}: state_path"))
    presentes = {p.name for p in models_dir.iterdir() if p.is_file()}
    sobran = sorted(presentes - declarados)
    require(not sobran, f"{who}: archivos de modelo no indexados: {sobran[:3]}")
    equal(f"{who}: archivos del motor", len(presentes), len(declarados))


def _check_envelope(
    envelope: dict[str, Any], engine: str, exp: ModelExpectations, transform_digest: str
) -> SeriesId:
    """Un modelo final: identidad explícita, serie base, ventana y procedencia. → su SeriesKey."""
    who = f"refit/{engine}: envelope"
    equal(f"{who}: schema", envelope.get("artifact_schema_version"), SCHEMA_FINAL_MODEL)
    equal(f"{who}: disease_id", envelope.get("disease_id"), exp.disease_id)
    equal(f"{who}: engine", envelope.get("engine"), engine)
    require(envelope.get("final_refit") is True, f"{who}: no declara final_refit")
    key = envelope.get("series_key")
    require(isinstance(key, dict), f"{who}: series_key ausente o mal formada")
    key = dict(key or {})
    equal(f"{who}: geography_level", key.get("geography_level"), GEO_LEVEL_ESTADO)
    equal(f"{who}: frequency", key.get("frequency"), FREQ_EPI_WEEK)
    sexo = text_of(key.get("sex"), f"{who}: sex")
    require(sexo in BASE_SEXES, f"{who}: {sexo!r} no es un sexo de serie base")
    equal(f"{who}: n_train", envelope.get("n_train"), exp.n_train)
    equal(f"{who}: train_end", tuple(envelope.get("train_end") or ()), exp.train_end)
    provenance_of(envelope.get("provenance"), dict(exp.provenance), who)
    recalculado = _transform_digest(envelope.get("transform"), who)
    equal(f"{who}: transform_digest declarado", envelope.get("transform_digest"), recalculado)
    equal(f"{who}: transform_digest del motor", recalculado, transform_digest)
    return (text_of(key.get("geography_id"), f"{who}: geography_id"), sexo)


def validate_models(
    refit_dir: Path,
    selection: Mapping[SeriesId, str],
    reparto: Mapping[str, int],
    exp: ModelExpectations,
) -> dict[SeriesId, ModelIdentity]:
    """Los modelos en disco describen EXACTAMENTE el portafolio que declara la selección.

    Devuelve la identidad ya contrastada entre índice, envelope y estado cargable, para que ningún
    consumidor —el inventario del forecast, por ejemplo— vuelva a abrir ni a inferir modelos.
    """
    identidades: dict[SeriesId, ModelIdentity] = {}
    for engine, esperados in reparto.items():
        who = f"refit/{engine}"
        entradas, transform_digest = _check_index(refit_dir, engine, esperados, exp)
        _check_engine_dir(refit_dir / "models" / engine, entradas, who)
        try:
            modelos = load_models(refit_dir, engine)  # re-verifica envelope y estado sellados
        except IO_ERRORS as exc:
            raise ArtifactValidationError(f"{who}: modelos no cargables ({exc})") from exc
        equal(f"{who}: modelos cargados", len(modelos), esperados)
        for entry, (envelope, _estado) in zip(entradas, modelos, strict=True):
            clave = _check_envelope(envelope, engine, exp, transform_digest)
            _check_entry(entry, envelope, who)
            require(clave not in identidades, f"refit: {clave} tiene más de un modelo final")
            require(clave in selection, f"{who}: {clave} no está en la selección")
            equal(f"refit: motor de {clave}", engine, selection[clave])
            identidades[clave] = ModelIdentity(
                series=clave,
                engine=engine,
                n_train=exp.n_train,
                train_end=exp.train_end,
                state_format=text_of(envelope.get("state_format"), f"{who}: state_format"),
                state_digest=text_of(envelope.get("state_digest"), f"{who}: state_digest"),
            )
    equal("refit: modelos finales", len(identidades), len(selection))
    return identidades
