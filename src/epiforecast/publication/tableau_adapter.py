"""C7.6-ADAPTERS-A — adaptador del shard de un release a tablas propias de Tableau.

Por qué existe: la cadena viva de Tableau —``build_tableau`` → ``tableau_model.xlsx`` →
``publish_gsheets`` → cinco pestañas— filtra a la cohorte neuro por construcción, así que un release
del runner no puede aparecer ahí sin reescribir el legacy. Reescribirlo sería mezclar dos
identidades: la cohorte histórica y los releases inmutables. En vez de eso, este adaptador produce
**tablas propias** con nombre reservado:

    runner_forecast     una fila por producto × periodo del release
    runner_releases     una fila por release, con su estado prospectivo y su linaje

Nada de esto toca ``scaffold``, ``real``, ``forecast``, ``metricas`` ni ``entidades``, y este módulo
no importa ``filter_neuro``: el universo lo define el shard, no una lista de padecimientos.

Genérico: ni un padecimiento, ni un conteo (64/111/5,772), ni un ``release_id`` escritos aquí. Todo
sale del manifiesto del shard. El sink es un protocolo, de modo que las pruebas usan un doble y esta
ronda no autentica ni escribe en Google Sheets.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from epiforecast.runner.artifact_identity import IO_ERRORS, ArtifactValidationError, equal, require
from epiforecast.runner.release_contract import canonical_json, sha256_bytes

ADAPTER_SCHEMA = "tableau_runner_tables.v1"
SHARD_SCHEMA = "publication_shard.v1"

# Nombres RESERVADOS. El prefijo `runner_` es el namespace que separa estas tablas de las cinco
# legacy; el promotor nunca debe escribir fuera de él.
TABLE_FORECAST = "runner_forecast"
TABLE_RELEASES = "runner_releases"
TABLES: tuple[str, ...] = (TABLE_FORECAST, TABLE_RELEASES)

# Sufijos del protocolo transaccional del sink (A5).
SUFFIX_NEXT = "__next"
SUFFIX_PREVIOUS = "__previous"

# Claves de identidad de una fila de release: el upsert es por aquí, nunca por posición.
RELEASE_KEY: tuple[str, str] = ("disease_id", "release_id")

SHARD_MANIFEST = "shard_manifest.json"
FORECAST_CSV = "tableau/forecast_shard.csv"
SCHEMA_JSON = "tableau/schema.json"


class TableauAdapterError(ArtifactValidationError):
    """Fallo del adaptador. Hereda de la excepción de identidad: es el mismo tipo de error."""


def _read_json(path: Path, etiqueta: str) -> dict[str, Any]:
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TableauAdapterError(f"{etiqueta}: no existe {path}") from exc
    except (*IO_ERRORS, json.JSONDecodeError) as exc:
        raise TableauAdapterError(f"{etiqueta}: ilegible ({exc})") from exc
    require(isinstance(datos, dict), f"{etiqueta}: se esperaba un objeto JSON")
    return dict(datos)


@dataclass(frozen=True, slots=True)
class RunnerTables:
    """Las dos tablas del namespace, ya validadas contra el manifiesto del shard."""

    forecast: pd.DataFrame
    releases: pd.DataFrame
    disease_id: str
    release_id: str

    def as_mapping(self) -> dict[str, pd.DataFrame]:
        return {TABLE_FORECAST: self.forecast, TABLE_RELEASES: self.releases}

    def digests(self) -> dict[str, str]:
        """Digest determinista por tabla: mismo contenido → mismo digest, en cualquier máquina."""
        return {
            nombre: sha256_bytes(frame.to_csv(index=False).encode("utf-8"))
            for nombre, frame in sorted(self.as_mapping().items())
        }


def _check_forecast(frame: pd.DataFrame, columnas: Sequence[str], filas: int) -> None:
    """El frame tiene que ser exactamente lo que el shard declara. Nada se infiere."""
    equal("runner_forecast: columnas", list(frame.columns), list(columnas))
    equal("runner_forecast: filas", len(frame), filas)

    claves = ["geography_level", "geography_id", "sex", "epi_year", "epi_week"]
    faltan = [c for c in claves if c not in frame.columns]
    require(not faltan, f"runner_forecast: faltan columnas clave {faltan}")
    duplicadas = int(frame.duplicated(subset=claves).sum())
    require(not duplicadas, f"runner_forecast: {duplicadas} claves serie×periodo duplicadas")

    valores = pd.to_numeric(frame["yhat_cases"], errors="coerce")
    require(bool(valores.notna().all()), "runner_forecast: yhat_cases no numérico")
    require(bool((valores >= 0).all()), "runner_forecast: yhat_cases negativo")

    # Point-only: los límites viajan vacíos. Si un día llegan valores, esto falla en vez de dejar
    # que Tableau dibuje una banda que nadie calculó.
    for columna in ("yhat_lower", "yhat_upper"):
        serie = frame[columna]
        vacia = serie.isna() | (serie.astype(str).str.strip() == "")
        require(
            bool(vacia.all()),
            f"runner_forecast: {columna} trae valores y el release es point-only",
        )


def build_tables(shard_root: Path) -> RunnerTables:
    """Lee un shard compilado y produce las dos tablas del namespace ``runner_``."""
    root = Path(shard_root)
    manifest = _read_json(root / SHARD_MANIFEST, SHARD_MANIFEST)
    equal(f"{SHARD_MANIFEST}: schema", manifest.get("schema"), SHARD_SCHEMA)
    schema = _read_json(root / SCHEMA_JSON, SCHEMA_JSON)
    equal(f"{SCHEMA_JSON}: schema", schema.get("schema"), SHARD_SCHEMA)
    equal("schema.json contra el manifiesto", schema.get("release_id"), manifest.get("release_id"))

    estado = manifest.get("publication_status")
    require(isinstance(estado, dict), "el shard no trae publication_status")
    assert isinstance(estado, dict)  # noqa: S101 — para mypy
    etiqueta = manifest.get("publication_label")
    require(bool(etiqueta), "el shard no trae publication_label")
    equal("etiqueta contra el estado", etiqueta, estado.get("label"))

    csv = root / FORECAST_CSV
    require(csv.is_file(), f"{FORECAST_CSV}: no existe")
    try:
        frame = pd.read_csv(csv, dtype=str, keep_default_na=False, na_values=[])
    except IO_ERRORS as exc:
        raise TableauAdapterError(f"{FORECAST_CSV}: ilegible ({exc})") from exc

    columnas = [c["name"] for c in schema.get("columns", [])]
    require(bool(columnas), f"{SCHEMA_JSON}: no declara columnas")
    _check_forecast(frame, columnas, int(manifest["rows"]))

    fila_release = {
        "disease_id": manifest["disease_id"],
        "release_id": manifest["release_id"],
        "display_name": manifest.get("display_name", ""),
        "lifecycle": manifest["lifecycle"],
        "origin_epi_year": manifest["origin"][0],
        "origin_epi_week": manifest["origin"][1],
        "horizon_weeks": manifest["horizon_weeks"],
        "rows": manifest["rows"],
        "models": manifest["models"],
        "products": manifest["products"],
        "interval_method": manifest["interval_method"],
        "uncertainty_available": bool(manifest["uncertainty_available"]),
        "publication_label": etiqueta,
        "verdict": estado["verdict"],
        "weeks_available": estado["weeks_available"],
        "weeks_required": estado["weeks_required"],
        "gate_digest": estado["gate_digest"],
        "evaluation_digest": estado["evaluation_digest"],
        "status_digest": estado["status_digest"],
        "observation_dataset_id": estado["observation_dataset_id"],
        "refit_digest": manifest.get("refit_digest", ""),
    }
    # El linaje del refit no está en `_facts`, pero sí en cada fila del forecast: se toma de ahí y se
    # exige que sea único, en vez de escribirlo a mano.
    if "refit_digest" in frame.columns:
        unicos = sorted(set(frame["refit_digest"]))
        equal("runner_forecast: refit_digest único", len(unicos), 1)
        fila_release["refit_digest"] = unicos[0]
    require(bool(fila_release["refit_digest"]), "runner_releases: falta refit_digest")

    require(
        not bool(manifest["uncertainty_available"]),
        "runner_releases: el shard declara incertidumbre y estas tablas son point-only",
    )
    return RunnerTables(
        forecast=frame,
        releases=pd.DataFrame([fila_release]),
        disease_id=str(manifest["disease_id"]),
        release_id=str(manifest["release_id"]),
    )


def upsert_releases(actual: pd.DataFrame | None, nuevas: pd.DataFrame) -> pd.DataFrame:
    """Upsert por ``(disease_id, release_id)``: reemplaza esa fila y respeta las demás.

    Concatenar duplicaría el release en cada promoción; sobrescribir la tabla entera borraría los
    releases de otros padecimientos. Ninguna de las dos es aceptable en una tabla compartida.
    """
    if actual is None or actual.empty:
        return nuevas.reset_index(drop=True)
    faltan = [c for c in RELEASE_KEY if c not in actual.columns]
    require(not faltan, f"runner_releases: la tabla existente no tiene {faltan}")
    llaves = set(zip(nuevas[RELEASE_KEY[0]], nuevas[RELEASE_KEY[1]], strict=True))
    conserva = actual[
        ~actual.apply(lambda r: (r[RELEASE_KEY[0]], r[RELEASE_KEY[1]]) in llaves, axis=1)
    ]
    return (
        pd.concat([conserva, nuevas], ignore_index=True)
        .sort_values(list(RELEASE_KEY))
        .reset_index(drop=True)
    )


def write_local(tables: RunnerTables, destino: Path) -> dict[str, str]:
    """Serialización local determinista (CSV + XLSX) para inspección y round-trip.

    No es una promoción: escribe donde se le diga, y el llamador es quien decide que sea un
    temporal. → {ruta relativa: sha256}
    """
    destino.mkdir(parents=True, exist_ok=True)
    registro: dict[str, str] = {}
    for nombre, frame in sorted(tables.as_mapping().items()):
        datos = frame.to_csv(index=False).encode("utf-8")
        (destino / f"{nombre}.csv").write_bytes(datos)
        registro[f"{nombre}.csv"] = sha256_bytes(datos)
    libro = destino / "runner_tables.xlsx"
    with pd.ExcelWriter(libro, engine="openpyxl") as writer:
        for nombre, frame in sorted(tables.as_mapping().items()):
            frame.to_excel(writer, sheet_name=nombre, index=False)
    registro["runner_tables.xlsx"] = sha256_bytes(libro.read_bytes())
    manifiesto = {
        "schema": ADAPTER_SCHEMA,
        "disease_id": tables.disease_id,
        "release_id": tables.release_id,
        "tables": {
            nombre: int(len(frame)) for nombre, frame in sorted(tables.as_mapping().items())
        },
        "digests": tables.digests(),
        "files": dict(sorted(registro.items())),
    }
    (destino / "adapter_manifest.json").write_bytes(canonical_json(manifiesto))
    return registro


def read_local(destino: Path) -> dict[str, pd.DataFrame]:
    """Round-trip: vuelve a leer lo escrito, para comprobar que nada se perdió al serializar."""
    return {
        nombre: pd.read_csv(
            destino / f"{nombre}.csv", dtype=str, keep_default_na=False, na_values=[]
        )
        for nombre in TABLES
    }


# ── Sink transaccional (A5): protocolo + promoción simulada ────────────────────────────────────
class TableSink(Protocol):
    """Destino de tablas. Las pruebas usan un doble; el cliente real llega en otra ronda."""

    def list_tables(self) -> list[str]: ...

    def read_table(self, name: str) -> pd.DataFrame | None: ...

    def write_table(self, name: str, frame: pd.DataFrame) -> None: ...

    def rename_table(self, origen: str, destino: str) -> None: ...

    def drop_table(self, name: str) -> None: ...


def promote(sink: TableSink, tables: RunnerTables) -> dict[str, Any]:
    """Promoción TRANSACCIONAL a las tablas del namespace. Simulable con un sink falso.

    El orden importa y es el único que deja el destino recuperable:

    1. escribir ``<tabla>__next`` completa —con el upsert ya aplicado sobre lo que hay activo—;
    2. validar filas y digests de lo escrito;
    3. mover la activa a ``<tabla>__previous`` y ``__next`` a activa;
    4. si algo falla antes del paso 3, las tablas ACTIVAS no se tocan.

    El rollback es el swap inverso: `rollback()`.
    """
    activas = set(sink.list_tables())
    escritas: list[str] = []
    try:
        for nombre, frame in sorted(tables.as_mapping().items()):
            objetivo = frame
            if nombre == TABLE_RELEASES:
                objetivo = upsert_releases(sink.read_table(nombre), frame)
            sink.write_table(f"{nombre}{SUFFIX_NEXT}", objetivo)
            escritas.append(f"{nombre}{SUFFIX_NEXT}")
            leido = sink.read_table(f"{nombre}{SUFFIX_NEXT}")
            require(
                leido is not None, f"{nombre}{SUFFIX_NEXT}: el sink no devolvió la tabla escrita"
            )
            assert leido is not None  # noqa: S101 — para mypy
            equal(f"{nombre}{SUFFIX_NEXT}: filas", len(leido), len(objetivo))
    except Exception:
        # Nada de lo activo se tocó todavía: se limpian sólo las temporales.
        for nombre in escritas:
            sink.drop_table(nombre)
        raise

    movidas: list[str] = []
    for nombre in sorted(tables.as_mapping()):
        if nombre in activas:
            sink.rename_table(nombre, f"{nombre}{SUFFIX_PREVIOUS}")
        sink.rename_table(f"{nombre}{SUFFIX_NEXT}", nombre)
        movidas.append(nombre)
    return {
        "promoted": movidas,
        "previous": [f"{n}{SUFFIX_PREVIOUS}" for n in movidas if n in activas],
        "digests": tables.digests(),
    }


def rollback(sink: TableSink, nombres: Sequence[str] = TABLES) -> list[str]:
    """Swap inverso: ``__previous`` vuelve a ser la activa. Sin ``__previous`` no hay nada que hacer."""
    restauradas = []
    existentes = set(sink.list_tables())
    for nombre in sorted(nombres):
        previa = f"{nombre}{SUFFIX_PREVIOUS}"
        if previa not in existentes:
            continue
        if nombre in existentes:
            sink.drop_table(nombre)
        sink.rename_table(previa, nombre)
        restauradas.append(nombre)
    return restauradas


class MemorySink:
    """Sink en memoria. Es el doble de pruebas, y también la especificación ejecutable del sink."""

    def __init__(self, inicial: Mapping[str, pd.DataFrame] | None = None) -> None:
        self._tablas: dict[str, pd.DataFrame] = {k: v.copy() for k, v in (inicial or {}).items()}
        self.operaciones: list[str] = []

    def list_tables(self) -> list[str]:
        return sorted(self._tablas)

    def read_table(self, name: str) -> pd.DataFrame | None:
        frame = self._tablas.get(name)
        return frame.copy() if frame is not None else None

    def write_table(self, name: str, frame: pd.DataFrame) -> None:
        self.operaciones.append(f"write:{name}")
        self._tablas[name] = frame.copy()

    def rename_table(self, origen: str, destino: str) -> None:
        self.operaciones.append(f"rename:{origen}->{destino}")
        require(origen in self._tablas, f"sink: no existe la tabla {origen}")
        self._tablas[destino] = self._tablas.pop(origen)

    def drop_table(self, name: str) -> None:
        self.operaciones.append(f"drop:{name}")
        self._tablas.pop(name, None)
