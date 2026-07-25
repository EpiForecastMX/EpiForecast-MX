"""C7.1/Acción 3 (R5.5) — el dataset sellado como AUTORIDAD de la ventana de entrenamiento.

``n_train`` y ``train_end`` gobiernan los 64 envelopes, así que no basta con que cuadre el total de
filas: un hueco compensado por un duplicado conserva el conteo global y movería la ventana sin que
nada fallara. Aquí se exige, serie por serie, el mismo calendario epidemiológico contiguo sobre el
universo exacto del catálogo, y sólo después se deriva la ventana.

Ninguna identidad del padecimiento está escrita en este módulo: el universo se recibe, el
calendario lo resuelve ``epi_calendar`` y los conteos salen del propio manifiesto.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from epiforecast.data.epi_calendar import shift, weeks_in_year
from epiforecast.data.epi_dataset_spec import (
    BASE_SEXES,
    COL_CVE_ENT,
    COL_DISEASE_ID,
    COL_EPI_WEEK,
    COL_EPI_YEAR,
    COL_SEXO,
)
from epiforecast.runner.artifact_identity import (
    IO_ERRORS,
    ArtifactValidationError,
    equal,
    int_of,
    mapping_of,
    read_json,
    require,
    require_exact_records,
    sequence_of,
    sha256_file,
    verify_records,
)
from epiforecast.runner.contracts import SCHEMA_DATASET, SCHEMA_PRODUCTS
from epiforecast.runner.manifest import DATASET_MANIFEST_SCHEMA, DatasetManifest

DATASET_FILE = "epi_dataset_v2.csv"
SCHEMA_LINEAGE = "lineage.v1"
# Inventario exacto del dataset sellado (R9.1). El contenido tabular de `products.csv` es de la
# Acción 4; que esté declarado y sellado sin ambigüedad es de aquí.
_DATASET_ARTIFACTS = {
    DATASET_FILE: SCHEMA_DATASET,
    "products.csv": SCHEMA_PRODUCTS,
    "lineage.json": SCHEMA_LINEAGE,
}
_COUNT_KEYS = ("base", "derived", "products")
_IDENTIDAD = [COL_DISEASE_ID, COL_CVE_ENT, COL_SEXO, COL_EPI_YEAR, COL_EPI_WEEK]

Period = tuple[int, int]


def _read_identity(dataset_dir: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(
            dataset_dir / DATASET_FILE,
            usecols=_IDENTIDAD,
            dtype={COL_CVE_ENT: str},
            low_memory=False,  # la inferencia de tipos no puede depender del tamaño del chunk
        )
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{DATASET_FILE}: ilegible ({exc})") from exc


def _periods_of(grupo: pd.DataFrame, who: str) -> tuple[Period, ...]:
    """Secuencia epidemiológica de UNA serie: sin duplicados, válida y contigua."""
    periodos = [
        (int_of(y, f"{who}: epi_year"), int_of(w, f"{who}: epi_week"))
        for y, w in zip(grupo[COL_EPI_YEAR], grupo[COL_EPI_WEEK], strict=True)
    ]
    require(periodos, f"{who}: serie vacía")
    ordenados = sorted(periodos)
    require(len(set(ordenados)) == len(ordenados), f"{who}: periodos duplicados")
    for year, week in ordenados:
        try:
            limite = weeks_in_year(year)
        except IO_ERRORS as exc:
            raise ArtifactValidationError(f"{who}: año epidemiológico inválido {year}") from exc
        require(1 <= week <= limite, f"{who}: semana {week} fuera de {year} (1..{limite})")
    for previo, actual in zip(ordenados, ordenados[1:], strict=False):
        if shift(previo[0], previo[1], 1) != actual:
            raise ArtifactValidationError(f"{who}: hueco entre {previo} y {actual}")
    return tuple(ordenados)


def dataset_window(
    dataset_dir: Path, disease_id: str, dataset_digest: str, geography_ids: list[str]
) -> tuple[int, Period, dict[str, int]]:
    """Ventana y conteos del dataset SELLADO, verificados serie por serie."""
    who = "dataset"
    require(dataset_dir.is_dir(), f"{who}: no existe {dataset_dir.name}")
    man = read_json(dataset_dir / "dataset_manifest.json", who, DATASET_MANIFEST_SCHEMA)
    equal(f"{who}: dataset_id", man.get("dataset_id"), dataset_dir.name)
    equal(f"{who}: disease_id", man.get("disease_id"), disease_id)
    equal(
        f"{who}: digest", mapping_of(man.get("digests") or {}, who).get("dataset"), dataset_digest
    )
    for registro in sequence_of(
        man.get("artifacts") if man.get("artifacts") is not None else [], f"{who}: artifacts"
    ):
        mapping_of(registro, f"{who}: artifacts[]")
    try:
        declarados = DatasetManifest.from_dict(man).artifacts
    except IO_ERRORS as exc:
        raise ArtifactValidationError(f"{who}: manifiesto inválido ({exc})") from exc
    # El dataset es la autoridad distribuible: su inventario debe ser EXACTO (R9.1). `products.csv`
    # materializa los 111 productos y `lineage.json` describe su derivación; ninguno puede faltar,
    # sobrar ni declarar otro schema. La unicidad de rutas la garantiza `verify_records`.
    verify_records(dataset_dir, declarados, who)
    require_exact_records(declarados, _DATASET_ARTIFACTS, who)
    equal(
        f"{who}: digest de {DATASET_FILE}",
        sha256_file(dataset_dir / DATASET_FILE, DATASET_FILE),
        dataset_digest,
    )

    frame = _read_identity(dataset_dir)
    require(len(frame), f"{DATASET_FILE}: sin filas")
    equal(f"{DATASET_FILE}: disease_id", sorted(set(frame[COL_DISEASE_ID])), [disease_id])
    esperado = sorted((geo, sex) for geo in geography_ids for sex in BASE_SEXES)
    series = {clave: grupo for clave, grupo in frame.groupby([COL_CVE_ENT, COL_SEXO], sort=True)}
    equal(f"{DATASET_FILE}: universo de series", sorted(series), esperado)

    referencia: tuple[Period, ...] | None = None
    for clave, grupo in series.items():
        periodos = _periods_of(grupo, f"{DATASET_FILE}: {clave}")
        if referencia is None:
            referencia = periodos
        elif periodos != referencia:
            raise ArtifactValidationError(
                f"{DATASET_FILE}: {clave} no comparte el calendario de las demás series "
                f"({len(periodos)} periodos frente a {len(referencia)})"
            )
    assert referencia is not None  # el universo no está vacío: lo garantiza la igualdad anterior
    equal(f"{DATASET_FILE}: filas", len(frame), len(referencia) * len(esperado))

    return len(referencia), referencia[-1], _counts(man, who, len(esperado))


def _counts(man: dict[str, object], who: str, n_series: int) -> dict[str, int]:
    """Conteos del dataset: enteros estrictos, no negativos y coherentes entre sí (R7.2)."""
    crudos = mapping_of(man.get("counts") or {}, f"{who}: counts")
    conteos: dict[str, int] = {}
    for clave, valor in crudos.items():
        conteos[clave] = int_of(valor, f"{who}: counts[{clave!r}]")
        require(conteos[clave] >= 0, f"{who}: counts[{clave!r}] negativo: {conteos[clave]}")
    for clave in _COUNT_KEYS:
        require(clave in conteos, f"{who}: counts sin {clave!r}")
    equal(f"{who}: counts['base']", conteos["base"], n_series)
    # Los derivados se MATERIALIZAN desde las bases: el total no puede ser otro.
    equal(f"{who}: counts['products']", conteos["products"], conteos["base"] + conteos["derived"])
    return conteos
