"""Base del consolidado semanal frente a las observaciones vigentes de cada publicado.

El consolidado de la semana N se arma conservando byte a byte la base de W(N-1). Si esa base es un
consolidado ya sustituido (por ejemplo, anterior a una corrección de la extracción), la semana nueva
heredaría cifras históricas corregidas. Esta comprobación compara, para cada padecimiento publicado,
su historia en la base con el raw de su observación vigente en todos los periodos anteriores a N:
cualquier fila distinta, ausente o sobrante rechaza la base (auditoría 9-nov-2026, R1).

La comparación es numérica (``3`` y ``3.0`` son iguales). Un raw sin desglose por sexo se compara con
hombres y mujeres vacíos, igual que se proyecta al consolidado.
"""

from __future__ import annotations

import csv
from pathlib import Path

Clave = tuple[int, int, str]
Valores = tuple[float | None, float | None, float | None, float | None]


def _num(v: str | None) -> float | None:
    v = (v or "").strip()
    return None if v == "" else float(v)


def _clave(r: dict[str, str]) -> Clave:
    return (int(float(r["Anio"])), int(float(r["Semana"])), r["Entidad"])


def _valores(r: dict[str, str], sin_sexo: bool) -> Valores:
    return (
        _num(r["Casos_semana"]),
        None if sin_sexo else _num(r.get("Acumulado_hombres")),
        None if sin_sexo else _num(r.get("Acumulado_mujeres")),
        _num(r["Acumulado_anio_anterior"]),
    )


def _lee_raw(raw: Path) -> tuple[str, bool, list[dict[str, str]]]:
    with raw.open(encoding="utf-8", newline="") as fh:
        lector = csv.DictReader(fh)
        sin_sexo = "Acumulado_total" in (lector.fieldnames or [])
        filas = list(lector)
    if not filas:
        raise ValueError(f"{raw}: raw de observación vacío")
    nombres = {r["Padecimiento"] for r in filas}
    if len(nombres) != 1:
        raise ValueError(f"{raw}: más de un padecimiento ({sorted(nombres)})")
    return nombres.pop(), sin_sexo, filas


def diferencias_base(
    base: Path, raws: dict[str, Path], antes_de: tuple[int, int]
) -> dict[str, list[tuple[int, int]]]:
    """Periodos (año, semana) anteriores a ``antes_de`` en que la base difiere del raw vigente.

    ``raws`` asocia cada padecimiento publicado con el raw de su observación vigente. Devuelve sólo
    los padecimientos con diferencias; vacío significa que la base es la vigente.
    """
    leidos = {d: _lee_raw(p) for d, p in raws.items()}
    nombres = {nombre for nombre, _, _ in leidos.values()}
    por_nombre: dict[str, dict[Clave, dict[str, str]]] = {n: {} for n in nombres}
    with base.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            destino = por_nombre.get(r["Padecimiento"])
            if destino is not None:
                destino[_clave(r)] = r
    out: dict[str, list[tuple[int, int]]] = {}
    for d, (nombre, sin_sexo, filas) in leidos.items():
        obs = {_clave(r): _valores(r, sin_sexo) for r in filas if _clave(r)[:2] < antes_de}
        en_base = {
            k: _valores(r, sin_sexo) for k, r in por_nombre[nombre].items() if k[:2] < antes_de
        }
        periodos = {k[:2] for k in obs.keys() | en_base.keys() if obs.get(k) != en_base.get(k)}
        if periodos:
            out[d] = sorted(periodos)
    return out
