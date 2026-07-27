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
import io
import json
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from epiforecast.runner.artifact_identity import IO_ERRORS, ArtifactValidationError, equal, require
from epiforecast.runner.release_contract import canonical_json, sha256_bytes

ADAPTER_SCHEMA = "tableau_runner_tables.v1"
# Vista de conveniencia, NO autoritativa: su contenedor ZIP lleva metadata temporal.
XLSX_VIEW = "runner_tables.xlsx"
SHARD_SCHEMA = "publication_shard.v1"

# Nombres RESERVADOS. El prefijo `runner_` es el namespace que separa estas tablas de las cinco
# legacy; el promotor nunca debe escribir fuera de él.
TABLE_FORECAST = "runner_forecast"
TABLE_RELEASES = "runner_releases"
TABLES: tuple[str, ...] = (TABLE_FORECAST, TABLE_RELEASES)

# Sufijos del protocolo transaccional del sink (A5).
SUFFIX_NEXT = "__next"
SUFFIX_PREVIOUS = "__previous"
SUFFIX_BACKUP = "__backup"

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


def _check_sealed(root: Path, manifest: Mapping[str, Any], relativo: str) -> bytes:
    """Bytes de un archivo del shard, VERIFICADOS contra el inventario que el propio shard sella.

    Parsear primero y confiar después es el orden equivocado: un CSV alterado se convierte en un
    DataFrame perfectamente válido, y el conteo de filas no lo delata (R96-P0-3).
    """
    files = manifest.get("files")
    require(isinstance(files, dict), f"{SHARD_MANIFEST}: no trae el inventario `files`")
    assert isinstance(files, dict)  # noqa: S101 — para mypy
    declarado = files.get(relativo)
    require(bool(declarado), f"{SHARD_MANIFEST}: no declara {relativo}")
    path = root / relativo
    require(path.is_file(), f"{relativo}: no existe en el shard")
    datos = path.read_bytes()
    equal(f"{relativo}: digest contra el inventario del shard", sha256_bytes(datos), declarado)
    return datos


def build_tables(shard_root: Path) -> RunnerTables:
    """Lee un shard compilado y produce las dos tablas del namespace ``runner_``."""
    root = Path(shard_root)
    manifest = _read_json(root / SHARD_MANIFEST, SHARD_MANIFEST)
    equal(f"{SHARD_MANIFEST}: schema", manifest.get("schema"), SHARD_SCHEMA)
    schema = json.loads(_check_sealed(root, manifest, SCHEMA_JSON).decode("utf-8"))
    equal(f"{SCHEMA_JSON}: schema", schema.get("schema"), SHARD_SCHEMA)
    # Identidad cruzada completa, no sólo el release.
    for clave in ("release_id", "disease_id", "lifecycle", "rows", "interval_method"):
        equal(
            f"{SCHEMA_JSON}: {clave} contra el manifiesto", schema.get(clave), manifest.get(clave)
        )
    equal(
        f"{SCHEMA_JSON}: estado contra el manifiesto",
        schema.get("publication_status"),
        manifest.get("publication_status"),
    )

    estado = manifest.get("publication_status")
    require(isinstance(estado, dict), "el shard no trae publication_status")
    assert isinstance(estado, dict)  # noqa: S101 — para mypy
    etiqueta = manifest.get("publication_label")
    require(bool(etiqueta), "el shard no trae publication_label")
    equal("etiqueta contra el estado", etiqueta, estado.get("label"))

    datos = _check_sealed(root, manifest, FORECAST_CSV)
    try:
        frame = pd.read_csv(io.BytesIO(datos), dtype=str, keep_default_na=False, na_values=[])
    except (*IO_ERRORS, ValueError) as exc:
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


def write_local(tables: RunnerTables, destino: Path, *, xlsx: bool = True) -> dict[str, str]:
    """Serialización local: **CSV autoritativo** + un XLSX de conveniencia.

    El XLSX NO entra en los digests. Un `.xlsx` es un ZIP con metadata temporal del contenedor, así
    que dos escrituras del mismo contenido dan SHA distintos: llamarlo determinista sería falso
    (R96-P1-1). Se conserva como vista para abrir a mano, declarado como no autoritativo.

    No es una promoción: escribe donde se le diga, y el llamador decide que sea un temporal.
    → {ruta relativa: sha256} sólo de lo autoritativo
    """
    destino.mkdir(parents=True, exist_ok=True)
    registro: dict[str, str] = {}
    for nombre, frame in sorted(tables.as_mapping().items()):
        datos = frame.to_csv(index=False).encode("utf-8")
        (destino / f"{nombre}.csv").write_bytes(datos)
        registro[f"{nombre}.csv"] = sha256_bytes(datos)
    vistas: list[str] = []
    if xlsx:
        libro = destino / XLSX_VIEW
        with pd.ExcelWriter(libro, engine="openpyxl") as writer:
            for nombre, frame in sorted(tables.as_mapping().items()):
                frame.to_excel(writer, sheet_name=nombre, index=False)
        vistas.append(XLSX_VIEW)
    manifiesto = {
        "schema": ADAPTER_SCHEMA,
        "disease_id": tables.disease_id,
        "release_id": tables.release_id,
        "tables": {
            nombre: int(len(frame)) for nombre, frame in sorted(tables.as_mapping().items())
        },
        "digests": tables.digests(),
        "files": dict(sorted(registro.items())),
        # Se declara para que nadie lo confunda con evidencia: existe, y no cuenta.
        "non_authoritative_views": vistas,
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


def _canonical_frame(frame: pd.DataFrame) -> str:
    """Serialización canónica de una tabla: mismo contenido → mismo texto, para comparar de verdad."""
    return str(frame.astype(str).to_csv(index=False))


def _verify_readback(sink: TableSink, nombre: str, esperado: pd.DataFrame) -> None:
    """Relee lo escrito y compara TODO el contenido, no el número de filas.

    Comparar sólo `len` dejaba pasar un sink que alteraba un valor y conservaba el conteo: la
    promoción activaba el dato alterado y reportaba el digest del frame original (R96-P0-3).
    """
    leido = sink.read_table(nombre)
    require(leido is not None, f"{nombre}: el sink no devolvió la tabla escrita")
    assert leido is not None  # noqa: S101 — para mypy
    equal(f"{nombre}: columnas tras releer", list(leido.columns), list(esperado.columns))
    equal(f"{nombre}: filas tras releer", len(leido), len(esperado))
    equal(
        f"{nombre}: contenido tras releer",
        sha256_bytes(_canonical_frame(leido).encode("utf-8")),
        sha256_bytes(_canonical_frame(esperado).encode("utf-8")),
    )


class PromotionRecoveryError(TableauAdapterError):
    """La operación falló Y la restauración no pudo devolver el sink a su estado previo.

    No se disfraza de error normal: quien lo reciba tiene que recuperar a mano, y para eso lleva el
    inventario de lo que quedó en el sink.
    """

    def __init__(self, mensaje: str, inventario: Mapping[str, Any]) -> None:
        super().__init__(f"RECOVERY_REQUIRED: {mensaje}")
        self.status = "RECOVERY_REQUIRED"
        self.inventario = dict(inventario)


# Namespace ADMINISTRADO: los únicos nombres que este protocolo puede leer, escribir o borrar.
_SUFIJOS_GESTIONADOS = ("", SUFFIX_PREVIOUS, SUFFIX_NEXT, SUFFIX_BACKUP)


def managed_tables(nombres: Sequence[str] = TABLES) -> list[str]:
    """Activa, previa, temporal y respaldo de cada tabla. Todo lo demás en el sink es ajeno."""
    return [f"{n}{sufijo}" for n in sorted(nombres) for sufijo in _SUFIJOS_GESTIONADOS]


def _inventario(
    sink: TableSink,
    nombres: Sequence[str],
    antes: Mapping[str, pd.DataFrame],
    residuos: Sequence[str] = (),
) -> dict[str, Any]:
    """Lo que hace falta para recuperar a mano: qué hay, qué debería haber y qué es nuestro."""
    return {
        "tables": sorted(sink.list_tables()),
        "expected_before": sorted(antes),
        "namespace": sorted(nombres),
        "managed": managed_tables(nombres),
        "residues": sorted(residuos),
    }


def _snapshot(sink: TableSink, gestionadas: Sequence[str]) -> dict[str, pd.DataFrame]:
    """Fotografía del namespace administrado ENTERO: activas, previas, temporales y respaldos."""
    existentes = set(sink.list_tables())
    fotos: dict[str, pd.DataFrame] = {}
    for nombre in gestionadas:
        if nombre not in existentes:
            continue
        frame = sink.read_table(nombre)
        require(frame is not None, f"{nombre}: el sink lo lista y no lo devuelve")
        assert frame is not None  # noqa: S101 — para mypy
        fotos[nombre] = frame
    return fotos


def _check_preflight(sink: TableSink, nombres: Sequence[str], gestionadas: Sequence[str]) -> None:
    """Sin residuos no se empieza.

    Un ``__next`` o un ``__backup`` vivo es la evidencia de una recuperación inconclusa. Empezar
    encima la sobrescribiría, que es justamente lo que impediría recuperar (R98-P1-1). Aquí no se
    toca el sink: se mira y se sale.
    """
    existentes = set(sink.list_tables())
    residuos = [
        n for n in gestionadas if n.endswith((SUFFIX_NEXT, SUFFIX_BACKUP)) and n in existentes
    ]
    if residuos:
        raise PromotionRecoveryError(
            f"el sink conserva residuos de una operación anterior: {residuos}",
            _inventario(sink, nombres, {}, residuos),
        )


def _restaurar(
    sink: TableSink, antes: Mapping[str, pd.DataFrame], gestionadas: Sequence[str]
) -> None:
    """Devuelve el namespace administrado EXACTAMENTE a la fotografía del preflight.

    Se restaura por contenido y no por el nombre en que quedó cada cosa: así la compensación es la
    misma haya fallado el respaldo, la activación o la consolidación, en vez de una cadena de casos
    particulares que se olvida justo del que ocurrió (R98-P0-1).
    """
    for nombre in gestionadas:
        if nombre not in antes and nombre in set(sink.list_tables()):
            sink.drop_table(nombre)
    for nombre, frame in antes.items():
        actual = sink.read_table(nombre) if nombre in set(sink.list_tables()) else None
        if actual is None or _canonical_frame(actual) != _canonical_frame(frame):
            sink.write_table(nombre, frame)


def _verificar_restauracion(
    sink: TableSink, antes: Mapping[str, pd.DataFrame], gestionadas: Sequence[str]
) -> None:
    """Restaurar sin verificar es afirmar. Se comparan los nombres y el contenido de cada uno."""
    presentes = sorted(n for n in gestionadas if n in set(sink.list_tables()))
    equal("restauración: tablas del namespace", presentes, sorted(antes))
    for nombre, frame in antes.items():
        _verify_readback(sink, nombre, frame)


def _compensar(
    sink: TableSink,
    nombres: Sequence[str],
    antes: Mapping[str, pd.DataFrame],
    gestionadas: Sequence[str],
    error: Exception,
) -> None:
    """Restaura y verifica; si eso tampoco sale, el fallo se reporta como RECOVERY_REQUIRED."""
    try:
        _restaurar(sink, antes, gestionadas)
        _verificar_restauracion(sink, antes, gestionadas)
    except Exception as fallo:
        raise PromotionRecoveryError(
            f"{error} · restauración: {fallo}", _inventario(sink, nombres, antes)
        ) from error


def promote(sink: TableSink, tables: RunnerTables) -> dict[str, Any]:
    """Promoción RECUPERABLE de las dos tablas del namespace.

    Un sink de hojas de cálculo no ofrece transacciones multi-tabla, así que no se promete
    atomicidad: se promete **recuperabilidad**. El protocolo es:

    1. *preflight*: se rechaza cualquier residuo y se fotografía el namespace administrado entero;
    2. se escribe cada ``<tabla>__next`` y se **relee entera** para compararla;
    3. se respalda cada activa en ``<tabla>__backup`` —sin tocar un ``__previous`` válido, que es
       el punto de retorno del rollback anterior—;
    4. se activan las dos;
    5. se verifican las dos ya activas;
    6. se consolida ``__backup``→``__previous``;
    7. ante fallo en cualquier frontera —write, read, rename o drop— **incluida la consolidación**,
       se restaura la fotografía completa y se verifica. Si eso falla, `PromotionRecoveryError`.

    Antes, un fallo en el rename de la segunda tabla dejaba una activa nueva y la otra AUSENTE
    (R96-P0-2), y la consolidación caía fuera de la recuperación (R98-P0-1). Ahora, o queda todo el
    namespace como estaba, o queda la promoción entera.
    """
    nombres = sorted(tables.as_mapping())
    gestionadas = managed_tables(nombres)
    _check_preflight(sink, nombres, gestionadas)
    antes = _snapshot(sink, gestionadas)

    objetivos: dict[str, pd.DataFrame] = {}
    try:
        # ── 2. temporales verificadas ──
        for nombre in nombres:
            frame = tables.as_mapping()[nombre]
            objetivo = (
                upsert_releases(sink.read_table(nombre), frame)
                if nombre == TABLE_RELEASES
                else frame
            )
            objetivos[nombre] = objetivo
            sink.write_table(f"{nombre}{SUFFIX_NEXT}", objetivo)
            _verify_readback(sink, f"{nombre}{SUFFIX_NEXT}", objetivo)

        # ── 3-4. respaldo y activación ──
        for nombre in nombres:
            if nombre in antes:
                sink.rename_table(nombre, f"{nombre}{SUFFIX_BACKUP}")
            sink.rename_table(f"{nombre}{SUFFIX_NEXT}", nombre)

        # ── 5. verificación de las dos activas ──
        for nombre in nombres:
            _verify_readback(sink, nombre, objetivos[nombre])

        # ── 6. consolidación del punto de retorno, dentro del protocolo compensable ──
        for nombre in nombres:
            respaldo = f"{nombre}{SUFFIX_BACKUP}"
            existentes = set(sink.list_tables())
            if respaldo not in existentes:
                continue
            previa = f"{nombre}{SUFFIX_PREVIOUS}"
            if previa in existentes:
                sink.drop_table(previa)
            sink.rename_table(respaldo, previa)
    except Exception as error:
        _compensar(sink, nombres, antes, gestionadas, error)
        raise

    return {
        "status": "PROMOTED",
        "promoted": list(nombres),
        "previous": [f"{n}{SUFFIX_PREVIOUS}" for n in nombres if n in antes],
        "digests": {
            nombre: sha256_bytes(_canonical_frame(objetivos[nombre]).encode("utf-8"))
            for nombre in nombres
        },
    }


def rollback(sink: TableSink, nombres: Sequence[str] = TABLES) -> list[str]:
    """Swap inverso RECUPERABLE, sobre el **par** y no tabla por tabla.

    Antes se hacía `drop(activa)` y luego `rename(previa → activa)`: si ese rename fallaba, se
    perdían las dos (R96-P0-2). Después, cada tabla se protegía por separado: si la primera
    restauraba y la segunda fallaba, el par quedaba mezclado —una activa de la promoción anterior y
    otra de la nueva—, que es el estado que ningún consumidor puede interpretar (R98-P0-2).

    Ahora se fotografía el namespace entero, se restauran todas, se verifican todas y sólo entonces
    se retiran los respaldos; cualquier fallo devuelve la fotografía completa.

    Sólo vuelven las tablas que tienen ``__previous``: una que se creó en la promoción no tiene a
    qué volver, y borrarla sería inventar una semántica que nadie pidió.
    """
    nombres = sorted(nombres)
    gestionadas = managed_tables(nombres)
    _check_preflight(sink, nombres, gestionadas)
    existentes = set(sink.list_tables())
    restaurables = [n for n in nombres if f"{n}{SUFFIX_PREVIOUS}" in existentes]
    if not restaurables:
        return []
    antes = _snapshot(sink, gestionadas)

    try:
        for nombre in restaurables:
            if nombre in set(sink.list_tables()):
                sink.rename_table(nombre, f"{nombre}{SUFFIX_BACKUP}")
            sink.rename_table(f"{nombre}{SUFFIX_PREVIOUS}", nombre)
        for nombre in restaurables:
            _verify_readback(sink, nombre, antes[f"{nombre}{SUFFIX_PREVIOUS}"])
        for nombre in restaurables:
            respaldo = f"{nombre}{SUFFIX_BACKUP}"
            if respaldo in set(sink.list_tables()):
                sink.drop_table(respaldo)
    except Exception as error:
        _compensar(sink, nombres, antes, gestionadas, error)
        raise

    return list(restaurables)


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
