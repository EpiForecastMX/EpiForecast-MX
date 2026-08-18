"""Incorpora las semanas nuevas al consolidado sin destruir lo que solo existe en local.

El consolidado del boletin es una superposicion: lo que viene versionado por el flujo
automatizado (los padecimientos publicados) y filas que hoy solo viven en este disco
(el carril de obesidad, que no esta autorizado a versionarse). Por eso `dvc pull` se
niega a bajarlo: veria un archivo modificado y tendria que retirarlo.

Forzar la descarga resolveria el sintoma y borraria el trabajo local. Este modulo hace
lo contrario: trae la version versionada a un temporal, comprueba que las filas
compartidas coinciden **exactamente** y agrega unicamente las que faltan.

Falla cerrado. Si una fila que ya existia cambio de valor, no es una semana nueva: es
una correccion de la fuente, y decidir que hacer con ella no le toca a un script que
corre solo cada semana.

Uso:
    python -m scripts.sincroniza_consolidado [--dry-run]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CONSOLIDADO = Path("data/processed/dataset_boletin_epidemiologico.csv")
CLAVE = ["Anio", "Semana", "Entidad", "Padecimiento"]
VALORES = [
    "Casos_semana",
    "Acumulado_hombres",
    "Acumulado_mujeres",
    "Acumulado_anio_anterior",
]


class SincronizacionError(RuntimeError):
    """La sincronizacion no puede completarse sin una decision humana."""


def _descarga_versionado(destino: Path) -> None:
    """Trae a `destino` la version del consolidado que declara el puntero DVC."""
    resultado = subprocess.run(
        ["dvc", "get", ".", str(CONSOLIDADO), "-o", str(destino), "--force"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0 or not destino.is_file():
        raise SincronizacionError(
            f"no se pudo obtener la version versionada del consolidado: {resultado.stderr.strip()}"
        )


def discrepancias_en_comun(versionado: pd.DataFrame, local: pd.DataFrame) -> pd.DataFrame:
    """Devuelve las filas presentes en ambos cuyos valores difieren.

    Dos ausencias representan el mismo hecho y no cuentan como discrepancia, asi que
    se comparan por igualdad o por ser ambas nulas, sin rellenar con un centinela.
    """
    juntos = versionado.merge(local, on=CLAVE, suffixes=("_ver", "_loc"), how="inner")
    if juntos.empty:
        return juntos
    difiere = pd.Series(False, index=juntos.index)
    for columna in VALORES:
        izq, der = f"{columna}_ver", f"{columna}_loc"
        if izq in juntos and der in juntos:
            a, b = juntos[izq], juntos[der]
            difiere |= ~((a == b) | (a.isna() & b.isna()))
    return juntos[difiere]


def filas_nuevas(versionado: pd.DataFrame, local: pd.DataFrame) -> pd.DataFrame:
    """Filas del versionado cuya clave no existe en el local."""
    conocidas = set(map(tuple, local[CLAVE].to_numpy()))
    mascara = [tuple(fila) not in conocidas for fila in versionado[CLAVE].to_numpy()]
    return versionado[mascara]


def sincroniza(ruta: Path, versionado: pd.DataFrame, *, aplicar: bool) -> dict[str, Any]:
    """Fusiona de forma aditiva y devuelve el resumen de lo ocurrido."""
    local = pd.read_csv(ruta)

    conflictos = discrepancias_en_comun(versionado, local)
    if not conflictos.empty:
        raise SincronizacionError(
            f"{len(conflictos)} fila(s) ya existentes cambiaron de valor en el origen. "
            "Eso no es una semana nueva sino una correccion de la fuente; revisala a mano."
        )

    nuevas = filas_nuevas(versionado, local)
    solo_local = sorted(set(local["Padecimiento"]) - set(versionado["Padecimiento"]))

    resumen: dict[str, Any] = {
        "filas_antes": len(local),
        "filas_nuevas": len(nuevas),
        "filas_despues": len(local) + len(nuevas),
        "padecimientos_solo_locales": solo_local,
        "aplicado": False,
    }

    if aplicar and len(nuevas):
        fusionado = (
            pd.concat([local, nuevas], ignore_index=True).sort_values(CLAVE).reset_index(drop=True)
        )
        if fusionado.duplicated(subset=CLAVE).any():
            raise SincronizacionError("la fusion produjo claves duplicadas; no se escribio nada")
        # Escritura atomica: `to_csv` directo sobre el destino deja el consolidado truncado
        # si el proceso muere a media escritura, y ese archivo es la entrada de todo el
        # pipeline semanal. Se escribe al lado y se renombra, que en el mismo sistema de
        # archivos es atomico.
        temporal = ruta.with_name(ruta.name + ".part")
        try:
            fusionado.to_csv(temporal, index=False)
            temporal.replace(ruta)
        finally:
            temporal.unlink(missing_ok=True)
        resumen["aplicado"] = True

    return resumen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="informa que se agregaria sin escribir el consolidado",
    )
    args = parser.parse_args()

    ruta = REPO_ROOT / CONSOLIDADO
    if not ruta.is_file():
        print(f"ABORTA: no existe {ruta}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / "versionado.csv"
        try:
            _descarga_versionado(destino)
            versionado = pd.read_csv(destino)
            resumen = sincroniza(ruta, versionado, aplicar=not args.dry_run)
        except SincronizacionError as exc:
            print(f"ABORTA: {exc}", file=sys.stderr)
            return 1

    print(f"    filas locales           {resumen['filas_antes']:,}")
    print(f"    filas nuevas del origen {resumen['filas_nuevas']:,}")
    if resumen["padecimientos_solo_locales"]:
        print(f"    preservado solo local   {', '.join(resumen['padecimientos_solo_locales'])}")
    if resumen["aplicado"]:
        print(f"    consolidado actualizado {resumen['filas_despues']:,} filas")
    elif resumen["filas_nuevas"]:
        print("    (en seco: no se escribio)")
    else:
        print("    sin semanas nuevas que incorporar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
