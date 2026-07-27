"""C7.6-ADAPTERS-B0.4 — genera el workbook Tableau de STAGING de un shard.

    python -m scripts.tableau_workbook --shard <dir> --out runs/tableau_staging/x.twb

El id de la hoja sale de `C7_TABLEAU_STAGING_SPREADSHEET_ID`, y `--spreadsheet-id` sólo sirve para
**confirmarlo**: tiene que coincidir exactamente. Un workbook apuntando a otra hoja se separaría del
sink que se pretende validar, y entonces validar el uno no dice nada del otro (R102-P1). Se exige
además la variable productiva, para poder demostrar que no colisionan.

El destino tiene que ser descendiente de `<repo>/runs/` —comprobadamente gitignored— o de la raíz
temporal real del sistema. Se comprueba **antes** de crear directorios o escribir bytes, y sobre la
ruta ya resuelta, de modo que un symlink no pueda colar el artefacto dentro del repositorio
(R102-P0-3). ``reports/dashboards/viz_epiforecastmx.twb`` no se abre ni se toca.

Genera y **verifica**: si el XML resultante contiene Tableau Public, el id productivo, una ruta
absoluta o una tabla legacy, el comando termina en rc no-cero y no deja el archivo.

Lo que este comando NO demuestra: que Tableau Desktop pueda abrir, consultar y refrescar el
workbook. Eso es un gate de B1-PREFLIGHT, y por eso la salida declara
``tableau_desktop_validated: false`` en vez de llamarlo «validado».
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import subprocess
import sys
import tempfile
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
# Directorio del repositorio donde SÍ puede caer un artefacto local. Se comprueba que esté ignorado.
DIRECTORIO_RUNS = "runs"


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


def _esta_ignorado(ruta: Path, raiz_repo: Path) -> bool:
    """¿git ignora esta ruta? Se pregunta a git, no se deduce leyendo `.gitignore` a ojo."""
    try:
        resultado = subprocess.run(  # noqa: S603 — argumentos fijos, sin shell
            ["git", "check-ignore", "-q", str(ruta)],  # noqa: S607
            cwd=str(raiz_repo),
            capture_output=True,
            check=False,
        )
    except OSError:
        return False  # sin git no se puede demostrar; no demostrado es no
    return resultado.returncode == 0


def _check_destino(destino: Path, raiz_repo: Path) -> None:
    """El artefacto no entra al repositorio. Y el workbook productivo no es un destino.

    Buscar `tmp`, `var` o `runs` entre los componentes de la ruta aceptaba
    ``<repo>/reports/tmp/x.twb`` y ``<repo>/reports/runs/x.twb``, que son rutas trackeables dentro
    del repositorio (R102-P0-3). Aquí se compara contra dos **raíces resueltas**, y la resolución es
    lo que impide que un symlink apunte a otro sitio del que se declara.
    """
    resuelto = destino.expanduser().resolve()
    if resuelto == (raiz_repo / WORKBOOK_PRODUCTIVO).resolve():
        raise ArtifactValidationError(
            f"--out apunta al workbook productivo {WORKBOOK_PRODUCTIVO}; no se toca"
        )
    if resuelto.suffix != ".twb":
        raise ArtifactValidationError(f"--out tiene que terminar en .twb, no {resuelto.suffix!r}")

    runs = (raiz_repo / DIRECTORIO_RUNS).resolve()
    temporal = Path(tempfile.gettempdir()).resolve()
    if resuelto.is_relative_to(runs):
        if not _esta_ignorado(runs, raiz_repo):
            raise ArtifactValidationError(
                f"{DIRECTORIO_RUNS}/ no está ignorado por git en este árbol; "
                "escribir ahí metería el workbook al repositorio"
            )
        return
    if resuelto.is_relative_to(temporal):
        return
    raise ArtifactValidationError(
        f"--out {resuelto} no desciende de {runs} ni de {temporal}: este workbook no se versiona"
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
        # Se exigen las dos: sin la productiva no se puede demostrar que no colisionan.
        staging, produccion = staging_ids(entorno, require_production=True)
        identificador = args.spreadsheet_id or staging
        if identificador != staging:
            raise ArtifactValidationError(
                "--spreadsheet-id no coincide con la hoja de staging declarada; un workbook que "
                "apunta a otra hoja no valida el sink que se quiere validar"
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
                # Se generó y se verificó el XML. Abrirlo en Tableau Desktop es un gate de B1.
                "tableau_desktop_validated": False,
            }
        ).decode("utf-8")
    )
    destino_texto.write("\n")
    return RC_OK


if __name__ == "__main__":  # pragma: no cover - entrada de proceso
    raise SystemExit(main())


__all__ = ["RC_ERROR", "RC_OK", "RC_REFUSED", "WORKBOOK_PRODUCTIVO", "build_parser", "main"]
