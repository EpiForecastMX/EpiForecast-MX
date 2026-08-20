"""Acceso unico al paquete historico sellado. No hay otra puerta.

Cualquier script que produzca una cifra para el paper importa de aqui. `ruta()` verifica
el SHA-256 contra el MANIFEST antes de devolver nada, y `prohibe_rutas_vivas()` aborta si
el proceso tiene abierto cualquier archivo del arbol de trabajo que el paquete reemplaza.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
# Los datos del paquete pesan ~500 MB y NO se versionan: viven fuera del arbol rastreado.
# Lo que si se versiona es este codigo, el MANIFEST y los resultados.
BASE = Path(os.environ.get("EPIFORECAST_BUNDLE", RAIZ / "Congresos/MICAI/bundle_historico"))
_MAN = json.loads((BASE / "MANIFEST.json").read_text())
_POR_NOMBRE = {p["nombre"]: p for p in _MAN["piezas"]}

# Rutas del arbol vivo que el paquete sustituye. Tocarlas es el error que este modulo existe
# para impedir: hoy dan cifras distintas a las publicadas.
VIVAS_PROHIBIDAS = {
    (RAIZ / "data/processed/tableau.csv").resolve(),
    (RAIZ / "data/processed/dataset_boletin_epidemiologico.csv").resolve(),
    (RAIZ / "reports/ProdDetails/tabla_333_modelos_produccion.xlsx").resolve(),
    *(
        (RAIZ / f"reports/forecasts/{m}/all_forecast_{m}.csv").resolve()
        for m in ("deepar", "prophet", "ensemble", "stacking")
    ),
}


class FueraDelPaqueteError(RuntimeError):
    """Se intento leer un artefacto vivo en lugar del sellado."""


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def ruta(nombre: str) -> Path:
    """Devuelve la ruta sellada de `nombre` tras verificar su SHA-256."""
    if nombre not in _POR_NOMBRE:
        raise FueraDelPaqueteError(
            f"{nombre!r} no esta en el MANIFEST. Piezas: {sorted(_POR_NOMBRE)}"
        )
    p = BASE / nombre
    real = _sha256(p)
    esperado = _POR_NOMBRE[nombre]["sha256"]
    if real != esperado:
        raise FueraDelPaqueteError(f"{nombre}: sha256 {real[:16]} != manifest {esperado[:16]}")
    return p


def prohibe_rutas_vivas(*candidatas: str | Path) -> None:
    """Aborta si alguna ruta apunta al arbol vivo que el paquete reemplaza."""
    for c in candidatas:
        r = Path(c).resolve()
        if r in VIVAS_PROHIBIDAS:
            raise FueraDelPaqueteError(
                f"ruta viva prohibida: {r}\n"
                "  Las cifras del paper salen del paquete sellado. Usa bundle.ruta(...)."
            )


def verifica_todo() -> list[tuple[str, bool]]:
    """Verifica las siete piezas. Devuelve [(nombre, ok)]."""
    out = []
    for nombre in _POR_NOMBRE:
        try:
            ruta(nombre)
            out.append((nombre, True))
        except FueraDelPaqueteError:
            out.append((nombre, False))
    return out


def observado() -> pd.DataFrame:
    return pd.read_csv(ruta("dataset_boletin_epidemiologico.csv"))


def tableau() -> pd.DataFrame:
    return pd.read_csv(ruta("tableau.csv"), low_memory=False)


def metricas_cv() -> pd.DataFrame:
    return pd.read_excel(ruta("tabla_333_modelos_produccion.xlsx"), sheet_name=0)


def forecast(motor: str) -> pd.DataFrame:
    return pd.read_csv(ruta(f"forecasts/{motor}/all_forecast_{motor}.csv"), low_memory=False)


def sello() -> str:
    return (
        f"paquete sellado {_MAN['sellado_utc']} · modelos {_MAN['commit_modelos']} · "
        f"observaciones {_MAN['commit_observaciones']}"
    )
