"""C7.6-ADAPTERS-B0 — CLI operativo del namespace ``runner_`` en la hoja de STAGING.

    python -m scripts.tableau_staging inspect
    python -m scripts.tableau_staging stage --shard <dir_del_shard>
    python -m scripts.tableau_staging recover

Los tres son **dry-run por defecto**. `stage --apply` y `recover --apply` existen porque B1 los va a
necesitar, y por eso mismo están cerrados con llave: sin las cuatro condiciones de abajo el comando
termina con rc no-cero **antes de autenticar y antes de mutar**.

    1. `C7_TABLEAU_STAGING_SPREADSHEET_ID` declarado;
    2. distinto de `GSHEETS_SPREADSHEET_ID` —son la misma clase de identificador y confundirlos
       escribiría en la hoja que alimenta el Tableau público—;
    3. `--expect-inventory <digest>`: el estado sobre el que se emitió el plan;
    4. `--confirm-spreadsheet-id <id>`: el id de staging escrito a mano, no leído del entorno.

El namespace es fijo: ``runner_forecast``, ``runner_releases`` y sus sufijos administrados. No hay
bandera para ampliarlo, no hay `prune`, y ninguna operación toca las cinco tabs legacy.

La salida es JSON canónico: mismo estado → mismos bytes, para poder diffear dos ejecuciones.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import Any

from epiforecast.publication.recovery import (
    apply_recovery,
    classify,
    plan_bytes,
    recovery_plan,
    table_inventory,
)
from epiforecast.publication.sheets_sink import (
    PRODUCTION_ID_ENV,
    STAGING_ID_ENV,
    GoogleSheetsTableSink,
    open_spreadsheet,
    staging_ids,
)
from epiforecast.publication.tableau_adapter import (
    TABLES,
    TableauAdapterError,
    TableSink,
    build_tables,
    managed_tables,
    promote,
    promotion_plan,
)
from epiforecast.runner.artifact_identity import ArtifactValidationError

CMD_INSPECT = "inspect"
CMD_STAGE = "stage"
CMD_RECOVER = "recover"

RC_OK = 0
RC_ERROR = 1
RC_REFUSED = 2  # faltó una condición de seguridad: no se autenticó ni se mutó nada


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.tableau_staging",
        description="Inspección, staging y recuperación del namespace runner_ en la hoja de staging",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser(CMD_INSPECT, help="read-only: tabs, filas, digests, residuos y estado")

    stage = sub.add_parser(CMD_STAGE, help="plan de promoción (dry-run por defecto)")
    stage.add_argument("--shard", required=True, type=Path, help="raíz del shard compilado")
    _guardas(stage)

    recover = sub.add_parser(CMD_RECOVER, help="plan de recuperación (dry-run por defecto)")
    _guardas(recover)
    return parser


def _guardas(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--apply",
        action="store_true",
        help="ejecuta de verdad; exige --expect-inventory y --confirm-spreadsheet-id",
    )
    sub.add_argument("--expect-inventory", default=None, help="digest del inventario del plan")
    sub.add_argument("--confirm-spreadsheet-id", default=None, help="id de staging escrito a mano")


def _check_apply(args: argparse.Namespace, entorno: dict[str, str] | None = None) -> str:
    """Las cuatro condiciones. Se comprueban ANTES de abrir nada."""
    staging, _ = staging_ids(entorno)
    if not args.expect_inventory:
        raise ArtifactValidationError(
            "--apply exige --expect-inventory: aplicar sin fijar el estado de partida es actuar "
            "sobre una foto vieja"
        )
    if args.confirm_spreadsheet_id != staging:
        raise ArtifactValidationError(
            f"--confirm-spreadsheet-id no coincide con {STAGING_ID_ENV}; "
            "confirmar el destino a mano es la última barrera antes de escribir"
        )
    return staging


def _sink(inyectado: TableSink | None, entorno: dict[str, str] | None = None) -> TableSink:
    """Sink real o inyectado. Abrir la hoja es el único punto que autentica, y sólo aquí."""
    if inyectado is not None:
        return inyectado
    staging, _ = staging_ids(entorno)
    return GoogleSheetsTableSink(open_spreadsheet(staging), spreadsheet_id=staging)


def _emitir(salida: Any, destino: Any) -> None:
    destino.write(plan_bytes(salida).decode("utf-8"))


def _inspect(sink: TableSink) -> dict[str, Any]:
    inventario = table_inventory(sink, TABLES)
    return {
        "schema": inventario["schema"],
        "command": CMD_INSPECT,
        "mutating": False,
        "namespace": inventario["namespace"],
        "managed": inventario["managed"],
        "tables": inventario["tables"],
        "foreign": inventario["foreign"],
        "states": classify(inventario, TABLES),
        "inventory_digest": inventario["inventory_digest"],
    }


def _stage(sink: TableSink, shard: Path, *, aplicar: bool, esperado: str | None) -> dict[str, Any]:
    tablas = build_tables(shard)
    inventario = table_inventory(sink, TABLES)
    plan = promotion_plan(sink, tablas)
    salida: dict[str, Any] = {
        **plan,
        "command": CMD_STAGE,
        "disease_id": tablas.disease_id,
        "release_id": tablas.release_id,
        "inventory_digest": inventario["inventory_digest"],
        "states": classify(inventario, TABLES),
        "applied": False,
    }
    if not aplicar:
        return salida
    if esperado != inventario["inventory_digest"]:
        raise ArtifactValidationError(
            f"--expect-inventory {esperado} no es el inventario actual "
            f"{inventario['inventory_digest']}: la hoja se movió desde que se emitió el plan"
        )
    resultado = promote(sink, tablas)
    return {**salida, "applied": True, "result": resultado}


def _recover(sink: TableSink, *, aplicar: bool, esperado: str | None) -> dict[str, Any]:
    plan = recovery_plan(sink, TABLES)
    if not aplicar:
        return {**plan, "command": CMD_RECOVER, "applied": False}
    if esperado != plan["inventory_digest"]:
        raise ArtifactValidationError(
            f"--expect-inventory {esperado} no es el inventario actual {plan['inventory_digest']}"
        )
    resultado = apply_recovery(sink, plan, TABLES)
    return {**plan, "command": CMD_RECOVER, "applied": True, "result": resultado}


def main(
    argv: Sequence[str] | None = None,
    *,
    sink: TableSink | None = None,
    entorno: dict[str, str] | None = None,
    salida: Any = None,
) -> int:
    """`sink` y `entorno` se inyectan en pruebas; en operación real salen del entorno y de la API."""
    destino = sys.stdout if salida is None else salida
    args = build_parser().parse_args(argv)
    aplicar = bool(getattr(args, "apply", False))

    try:
        # Ni en dry-run: este CLI opera sobre UNA hoja de staging concreta, y no declararla es no
        # saber sobre qué se está mirando. La comprobación es de entorno; no abre nada.
        staging_ids(entorno)
        if aplicar:
            _check_apply(args, entorno)
    except ArtifactValidationError as exc:
        destino.write(f"REFUSED: {exc}\n")
        return RC_REFUSED

    try:
        conectado = _sink(sink, entorno)
        if args.comando == CMD_INSPECT:
            resultado = _inspect(conectado)
        elif args.comando == CMD_STAGE:
            resultado = _stage(
                conectado, args.shard, aplicar=aplicar, esperado=args.expect_inventory
            )
        else:
            resultado = _recover(conectado, aplicar=aplicar, esperado=args.expect_inventory)
    except (ArtifactValidationError, TableauAdapterError) as exc:
        destino.write(f"ERROR: {exc}\n")
        return RC_ERROR

    _emitir(resultado, destino)
    destino.write("\n")
    return RC_OK


def namespace_declarado() -> list[str]:
    """El namespace no se amplía por bandera. Esto es todo lo que el CLI puede tocar."""
    return managed_tables(TABLES)


if __name__ == "__main__":  # pragma: no cover - entrada de proceso
    raise SystemExit(main())


__all__ = [
    "PRODUCTION_ID_ENV",
    "RC_ERROR",
    "RC_OK",
    "RC_REFUSED",
    "STAGING_ID_ENV",
    "build_parser",
    "main",
    "namespace_declarado",
]
