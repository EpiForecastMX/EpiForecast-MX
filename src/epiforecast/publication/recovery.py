"""C7.6-ADAPTERS-B0 — inventario, diagnóstico y recuperación EXPLÍCITA del namespace ``runner_``.

El preflight de `promote` es fail-closed: si queda un ``__next`` o un ``__backup`` de una operación
que no terminó, no deja empezar otra. Eso es correcto —escribir encima borraría la evidencia— pero
deja el carril parado, y la salida no puede ser «limpia lo que sobre».

Aquí la recuperación se **propone** antes de aplicarse:

1. se inventaría el namespace administrado y se le calcula un digest;
2. se clasifica el estado de cada tabla;
3. se emite un plan de acciones concretas, ligado a ese digest;
4. aplicar exige que el inventario siga siendo el mismo —si la hoja cambió entre el plan y el
   `--apply`, el plan ya no describe la realidad—;
5. al terminar se verifican las dos activas.

Un plan es un artefacto: mismo estado → mismos bytes. Por eso no lleva marcas de tiempo.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from epiforecast.runner.artifact_identity import equal, require
from epiforecast.runner.release_contract import canonical_json, sha256_bytes

from .tableau_adapter import (
    SUFFIX_BACKUP,
    SUFFIX_NEXT,
    SUFFIX_PREVIOUS,
    TABLES,
    TableauAdapterError,
    TableSink,
    canonical_frame,
    managed_tables,
    verify_readback,
)

INVENTORY_SCHEMA = "tableau_runner_inventory.v1"
PLAN_SCHEMA = "tableau_runner_recovery.v1"

# Estados por tabla activa. Son excluyentes y se derivan del inventario, no se declaran.
STATE_CLEAN = "CLEAN"  # activa presente, sin residuos
STATE_MISSING = "MISSING"  # ni activa ni respaldo: no hay nada que recuperar
STATE_NEXT_RESIDUE = "NEXT_RESIDUE"  # sobra un __next de una promoción abortada
STATE_BACKUP_ORPHAN = "BACKUP_ORPHAN"  # la activa está y su respaldo también: consolidar
STATE_RECOVERY_REQUIRED = "RECOVERY_REQUIRED"  # la activa falta pero vive en respaldo o previa

# Acciones que el plan puede proponer. No existe ninguna que borre fuera del namespace.
ACTION_DROP_NEXT = "drop_next"
ACTION_RESTORE_BACKUP = "restore_backup"
ACTION_RESTORE_PREVIOUS = "restore_previous"
ACTION_CONSOLIDATE_BACKUP = "consolidate_backup"

# De dónde saldrá la activa al terminar. Se decide ANTES de mutar, no se descubre a mitad.
SOURCE_ACTIVE = "active"
SOURCE_BACKUP = SUFFIX_BACKUP.lstrip("_")
SOURCE_PREVIOUS = SUFFIX_PREVIOUS.lstrip("_")
SOURCE_NONE = "none"


def table_inventory(sink: TableSink, nombres: Sequence[str] = TABLES) -> dict[str, Any]:
    """Inventario del namespace administrado: qué existe, con cuántas filas y con qué digest."""
    gestionadas = managed_tables(nombres)
    presentes = set(sink.list_tables())
    tablas: dict[str, Any] = {}
    for nombre in gestionadas:
        if nombre not in presentes:
            continue
        frame = sink.read_table(nombre)
        require(frame is not None, f"{nombre}: el sink lo lista y no lo devuelve")
        assert frame is not None  # noqa: S101 — para mypy
        tablas[nombre] = {
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "digest": sha256_bytes(canonical_frame(frame).encode("utf-8")),
        }
    cuerpo = {
        "schema": INVENTORY_SCHEMA,
        "namespace": sorted(nombres),
        "managed": gestionadas,
        "tables": tablas,
        "foreign": sorted(t for t in presentes if t not in gestionadas),
    }
    return {**cuerpo, "inventory_digest": sha256_bytes(canonical_json(cuerpo))}


def classify(inventario: Mapping[str, Any], nombres: Sequence[str] = TABLES) -> dict[str, str]:
    """Estado de cada tabla activa, derivado del inventario. Uno solo por tabla."""
    tablas = inventario["tables"]
    estados: dict[str, str] = {}
    for nombre in sorted(nombres):
        activa = nombre in tablas
        respaldo = f"{nombre}{SUFFIX_BACKUP}" in tablas
        previa = f"{nombre}{SUFFIX_PREVIOUS}" in tablas
        temporal = f"{nombre}{SUFFIX_NEXT}" in tablas
        if not activa and (respaldo or previa):
            # Falta la activa, pero existe de dónde traerla: es recuperable, no perdida.
            estados[nombre] = STATE_RECOVERY_REQUIRED
        elif not activa:
            estados[nombre] = STATE_MISSING
        elif respaldo:
            estados[nombre] = STATE_BACKUP_ORPHAN
        elif temporal:
            estados[nombre] = STATE_NEXT_RESIDUE
        else:
            estados[nombre] = STATE_CLEAN
    return estados


def projected_sources(
    inventario: Mapping[str, Any], nombres: Sequence[str] = TABLES
) -> dict[str, str]:
    """De dónde saldrá cada activa al terminar. Se decide ANTES de mutar.

    El orden es deliberado: la propia activa, su respaldo, y sólo entonces la previa. Si ninguna de
    las tres existe, la tabla es irrecuperable y ese hecho tiene que conocerse **antes** de la
    primera mutación, no descubrirse al validar la postcondición (R102-P0-2).
    """
    tablas = inventario["tables"]
    fuentes: dict[str, str] = {}
    for nombre in sorted(nombres):
        if nombre in tablas:
            fuentes[nombre] = SOURCE_ACTIVE
        elif f"{nombre}{SUFFIX_BACKUP}" in tablas:
            fuentes[nombre] = SOURCE_BACKUP
        elif f"{nombre}{SUFFIX_PREVIOUS}" in tablas:
            fuentes[nombre] = SOURCE_PREVIOUS
        else:
            fuentes[nombre] = SOURCE_NONE
    return fuentes


def recovery_plan(sink: TableSink, nombres: Sequence[str] = TABLES) -> dict[str, Any]:
    """Plan de recuperación DETERMINISTA, ligado al digest del inventario que lo justifica.

    Si alguna tabla es irrecuperable, el plan sale **sin una sola acción**. Antes proponía borrar los
    ``__next`` y descubría al final que faltaban las activas: con sólo dos ``__next`` y nada más,
    eso borraba la única copia que quedaba y luego informaba error, con el namespace vacío
    (R102-P0-2). Y la validación es global: no se ejecuta media recuperación porque la otra tabla sí
    tuviera arreglo.
    """
    inventario = table_inventory(sink, nombres)
    estados = classify(inventario, nombres)
    fuentes = projected_sources(inventario, nombres)
    bloqueadas = sorted(n for n, origen in fuentes.items() if origen == SOURCE_NONE)

    base: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "inventory_digest": inventario["inventory_digest"],
        "namespace": sorted(nombres),
        "states": estados,
        "sources": fuentes,
        "blocked": bloqueadas,
    }
    if bloqueadas:
        # Un `__next` aislado no se activa ni se borra: es evidencia, y se conserva hasta que alguien
        # decida explícitamente qué hacer con ella.
        return {
            **base,
            "actions": [],
            "status": "RECOVERY_REQUIRED",
            "reason": (
                f"sin activa, respaldo ni previa para {bloqueadas}: no hay recuperación posible "
                "sin decidir a mano qué es la verdad"
            ),
        }

    acciones: list[dict[str, str]] = []
    for nombre in sorted(nombres):
        estado, origen = estados[nombre], fuentes[nombre]
        if origen == SOURCE_BACKUP:
            # La activa no está: el respaldo es la única copia y vuelve a su sitio.
            acciones.append({"action": ACTION_RESTORE_BACKUP, "table": nombre, "state": estado})
        elif origen == SOURCE_PREVIOUS:
            # Sin respaldo, la previa es lo único que puede volver a ser activa. Se declara.
            acciones.append({"action": ACTION_RESTORE_PREVIOUS, "table": nombre, "state": estado})
        elif estado == STATE_BACKUP_ORPHAN:
            # La activa está: el respaldo pasa a ser el punto de retorno, no se descarta.
            acciones.append(
                {"action": ACTION_CONSOLIDATE_BACKUP, "table": nombre, "state": estado}
            )
        if f"{nombre}{SUFFIX_NEXT}" in inventario["tables"]:
            # Sólo con la activa asegurada: un temporal nunca activado no es la última copia de nada.
            acciones.append({"action": ACTION_DROP_NEXT, "table": nombre, "state": estado})
    return {
        **base,
        "actions": acciones,
        "status": "RECOVERY_REQUIRED" if acciones else "CLEAN",
    }


def plan_bytes(plan: Mapping[str, Any]) -> bytes:
    """Serialización canónica del plan: mismo estado del sink → mismos bytes, siempre."""
    return canonical_json(dict(plan))


def apply_recovery(
    sink: TableSink, plan: Mapping[str, Any], nombres: Sequence[str] = TABLES
) -> dict[str, Any]:
    """Aplica un plan YA emitido, revalidando que la hoja no se movió entre medias.

    Aplicar un plan sobre un inventario distinto del que lo justificó es actuar sobre una foto
    vieja: podría restaurar un respaldo que otra operación ya consolidó.
    """
    equal("recovery: schema del plan", plan.get("schema"), PLAN_SCHEMA)
    equal("recovery: namespace del plan", list(plan.get("namespace", [])), sorted(nombres))
    actual = table_inventory(sink, nombres)
    equal(
        "recovery: el inventario cambió desde que se emitió el plan",
        actual["inventory_digest"],
        plan.get("inventory_digest"),
    )
    bloqueadas = list(plan.get("blocked", []))
    require(
        not bloqueadas,
        f"recovery: {bloqueadas} no tiene activa, respaldo ni previa; aplicar cualquier acción "
        "empeoraría el estado. No se toca nada.",
    )
    fotos = {n: sink.read_table(n) for n in actual["tables"]}

    aplicadas: list[dict[str, str]] = []
    for accion in plan.get("actions", []):
        nombre = accion["table"]
        require(
            nombre in sorted(nombres), f"recovery: acción sobre {nombre!r}, fuera del namespace"
        )
        _aplicar_una(sink, accion["action"], nombre, fotos)
        aplicadas.append(dict(accion))

    _verificar_activas(sink, nombres, fotos)
    posterior = table_inventory(sink, nombres)
    return {
        "schema": PLAN_SCHEMA,
        "status": "RECOVERED" if aplicadas else "CLEAN",
        "applied": aplicadas,
        "inventory_digest_before": plan.get("inventory_digest"),
        "inventory_digest_after": posterior["inventory_digest"],
        "states_after": classify(posterior, nombres),
    }


def _aplicar_una(
    sink: TableSink, accion: str, nombre: str, fotos: Mapping[str, pd.DataFrame | None]
) -> None:
    existentes = set(sink.list_tables())
    respaldo, temporal, previa = (
        f"{nombre}{SUFFIX_BACKUP}",
        f"{nombre}{SUFFIX_NEXT}",
        f"{nombre}{SUFFIX_PREVIOUS}",
    )
    if accion == ACTION_DROP_NEXT:
        if temporal in existentes:
            sink.drop_table(temporal)
        return
    if accion == ACTION_RESTORE_BACKUP:
        require(respaldo in existentes, f"recovery: {respaldo} ya no está; el plan quedó obsoleto")
        if nombre in existentes:
            sink.drop_table(nombre)
        sink.rename_table(respaldo, nombre)
        return
    if accion == ACTION_RESTORE_PREVIOUS:
        require(previa in existentes, f"recovery: {previa} ya no está; el plan quedó obsoleto")
        require(nombre not in existentes, f"recovery: {nombre} ya está activa; no se pisa")
        sink.rename_table(previa, nombre)
        return
    if accion == ACTION_CONSOLIDATE_BACKUP:
        require(respaldo in existentes, f"recovery: {respaldo} ya no está; el plan quedó obsoleto")
        if previa in existentes:
            sink.drop_table(previa)
        sink.rename_table(respaldo, previa)
        return
    raise TableauAdapterError(f"recovery: acción desconocida {accion!r}")


def _verificar_activas(
    sink: TableSink, nombres: Sequence[str], fotos: Mapping[str, pd.DataFrame | None]
) -> None:
    """Las dos activas tienen que existir y coincidir con la copia que las justifica."""
    faltan = [n for n in sorted(nombres) if sink.read_table(n) is None]
    require(not faltan, f"recovery: al terminar faltan las activas {faltan}")
    for nombre in sorted(nombres):
        esperado = fotos.get(nombre)
        for alternativa in (SUFFIX_BACKUP, SUFFIX_PREVIOUS):
            if esperado is None:
                esperado = fotos.get(f"{nombre}{alternativa}")
        if esperado is not None:
            verify_readback(sink, nombre, esperado)
