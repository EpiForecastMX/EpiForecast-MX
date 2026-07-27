"""C7.6-ADAPTERS-B0.4 — genera el workbook Tableau de STAGING de un shard.

    python -m scripts.tableau_workbook --shard <dir> --out runs/tableau_staging/x.twb

El id de la hoja sale de `C7_TABLEAU_STAGING_SPREADSHEET_ID` (o de `--spreadsheet-id`), nunca del
workbook productivo. El destino tiene que ser un temporal o una ruta gitignored: este artefacto no
entra al repositorio, y ``reports/dashboards/viz_epiforecastmx.twb`` no se abre ni se toca.

Genera y **verifica**: si el XML resultante contiene Tableau Public, el id productivo, una ruta
absoluta o una tabla legacy, el comando termina en rc no-cero y no deja el archivo.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import Any

from epiforecast.publication.recovery import plan_bytes
from epiforecast.publication.sheets_sink import staging_ids
from epiforecast.publication.tableau_adapter import TableauAdapterError, build_tables
from epiforecast.publication.tableau_workbook import build_workbook_xml, verify_workbook
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.release_contract import sha256_bytes

RC_OK = 0
RC_ERROR = 1
RC_REFUSED = 2

# Único destino trackeado que jamás puede ser la salida.
WORKBOOK_PRODUCTIVO = Path("reports/dashboards/viz_epiforecastmx.twb")
# Raíces admitidas: `runs/` está gitignored y los temporales del sistema, por definición, tampoco.
RAICES_PERMITIDAS = ("runs", "tmp", "var", "private")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.tableau_workbook",
        description="Genera y verifica el workbook Tableau de staging de un release",
    )
    parser.add_argument("--shard", required=True, type=Path, help="raíz del shard compilado")
    parser.add_argument("--out", required=True, type=Path, help="destino .twb (temporal o runs/)")
    parser.add_argument(
        "--spreadsheet-id", default=None, help="id de la hoja de staging; por defecto, del entorno"
    )
    return parser


def _check_destino(destino: Path, raiz_repo: Path) -> None:
    """El artefacto no entra al repositorio. Y el workbook productivo no es un destino."""
    resuelto = destino.resolve()
    require_no = resuelto == (raiz_repo / WORKBOOK_PRODUCTIVO).resolve()
    if require_no:
        raise ArtifactValidationError(
            f"--out apunta al workbook productivo {WORKBOOK_PRODUCTIVO}; no se toca"
        )
    if resuelto.suffix != ".twb":
        raise ArtifactValidationError(f"--out tiene que terminar en .twb, no {resuelto.suffix!r}")
    partes = resuelto.parts
    if not any(p in RAICES_PERMITIDAS for p in partes):
        raise ArtifactValidationError(
            f"--out {resuelto} no está bajo un temporal ni bajo runs/: "
            "este workbook no se versiona"
        )


def main(
    argv: Sequence[str] | None = None,
    *,
    entorno: dict[str, str] | None = None,
    raiz_repo: Path | None = None,
    salida: Any = None,
) -> int:
    destino_texto = sys.stdout if salida is None else salida
    args = build_parser().parse_args(argv)
    raiz = Path.cwd() if raiz_repo is None else raiz_repo

    try:
        staging, produccion = staging_ids(entorno)
        identificador = args.spreadsheet_id or staging
        if produccion and identificador == produccion:
            raise ArtifactValidationError(
                "--spreadsheet-id es el id productivo; el workbook de staging no lo lleva"
            )
        _check_destino(args.out, raiz)
    except ArtifactValidationError as exc:
        destino_texto.write(f"REFUSED: {exc}\n")
        return RC_REFUSED

    try:
        tablas = build_tables(args.shard)
        etiqueta = str(tablas.releases.iloc[0]["publication_label"])
        xml = build_workbook_xml(tablas, spreadsheet_id=identificador, label=etiqueta)
        resumen = verify_workbook(xml, forbidden_ids=[produccion or ""])
    except (ArtifactValidationError, TableauAdapterError) as exc:
        destino_texto.write(f"ERROR: {exc}\n")
        return RC_ERROR

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(xml)
    destino_texto.write(
        plan_bytes(
            {
                **resumen,
                "disease_id": tablas.disease_id,
                "release_id": tablas.release_id,
                "out": str(args.out),
                "bytes": len(xml),
                "digest": sha256_bytes(xml),
            }
        ).decode("utf-8")
    )
    destino_texto.write("\n")
    return RC_OK


if __name__ == "__main__":  # pragma: no cover - entrada de proceso
    raise SystemExit(main())


__all__ = ["RC_ERROR", "RC_OK", "RC_REFUSED", "WORKBOOK_PRODUCTIVO", "build_parser", "main"]
