"""Base del consolidado semanal frente a las observaciones vigentes de cada publicado.

El consolidado de la semana N se arma conservando byte a byte la base de W(N-1). Si esa base es un
consolidado ya sustituido (por ejemplo, anterior a una corrección de la extracción), la semana nueva
heredaría cifras históricas corregidas. Esta comprobación compara, para cada padecimiento publicado,
su historia en la base con el raw de su observación vigente en todos los periodos anteriores a N:
cualquier fila distinta, ausente o sobrante rechaza la base (auditoría 9-nov-2026, R1).

La comparación es numérica (``3`` y ``3.0`` son iguales). Un raw sin desglose por sexo se compara con
hombres y mujeres vacíos, igual que se proyecta al consolidado; en la base esos campos se leen tal
cual, de modo que un acumulado por sexo en una serie sin desglose es una diferencia (A2).

Antes de comparar se exige que cada clave (año, semana, entidad) aparezca una sola vez, en toda la
historia, tanto en la base como en el raw: un duplicado se marcaría como diferencia aunque una de
sus copias coincidiera, porque al indexar por clave la última fila ocultaría a la primera
(tercera auditoría, 9-nov-2026, A1).
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

Clave = tuple[int, int, str]
Valores = tuple[float | None, float | None, float | None, float | None]


def _num(v: str | None) -> float | None:
    v = (v or "").strip()
    return None if v == "" else float(v)


def entero(v: str | None, campo: str) -> int:
    """Año o semana como entero: acepta ``2`` y ``2.0``; rechaza fracciones, vacíos y no finitos.

    ``int(float("2.5"))`` daba 2 y una semana fraccionaria pasaba por la de su parte entera
    (cuarta auditoría, 9-nov-2026, B2).
    """
    try:
        x = float((v or "").strip())
    except ValueError:
        raise ValueError(f"{campo} no numérico: {v!r}") from None
    if not math.isfinite(x) or not x.is_integer():
        raise ValueError(f"{campo} no entero: {v!r}")
    return int(x)


def _clave(r: dict[str, str]) -> Clave:
    return (entero(r["Anio"], "Anio"), entero(r["Semana"], "Semana"), r["Entidad"])


def _valores(r: dict[str, str], proyecta_sin_sexo: bool) -> Valores:
    """Valores comparables; ``proyecta_sin_sexo`` vacía H/M (sólo para el raw sin desglose)."""
    return (
        _num(r["Casos_semana"]),
        None if proyecta_sin_sexo else _num(r.get("Acumulado_hombres")),
        None if proyecta_sin_sexo else _num(r.get("Acumulado_mujeres")),
        _num(r["Acumulado_anio_anterior"]),
    )


def _indexa(
    filas: list[dict[str, str]], proyecta_sin_sexo: bool
) -> tuple[dict[Clave, Valores], set[Clave]]:
    """Índice por clave y claves repetidas, sin que una copia sobrescriba a otra en silencio."""
    indice: dict[Clave, Valores] = {}
    repetidas: set[Clave] = set()
    for r in filas:
        k = _clave(r)
        if k in indice:
            repetidas.add(k)
        indice[k] = _valores(r, proyecta_sin_sexo)
    return indice, repetidas


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

    ``raws`` asocia cada padecimiento publicado con el raw de su observación vigente. Incluye además
    los periodos, de cualquier fecha, con una clave repetida en la base o en el raw. Devuelve sólo
    los padecimientos con diferencias; vacío significa que la base es la vigente.
    """
    leidos = {d: _lee_raw(p) for d, p in raws.items()}
    nombres = {nombre for nombre, _, _ in leidos.values()}
    por_nombre: dict[str, list[dict[str, str]]] = {n: [] for n in nombres}
    with base.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            destino = por_nombre.get(r["Padecimiento"])
            if destino is not None:
                destino.append(r)
    out: dict[str, list[tuple[int, int]]] = {}
    for d, (nombre, sin_sexo, filas) in leidos.items():
        obs, rep_obs = _indexa(filas, proyecta_sin_sexo=sin_sexo)
        en_base, rep_base = _indexa(por_nombre[nombre], proyecta_sin_sexo=False)
        periodos = {k[:2] for k in rep_obs | rep_base}
        periodos |= {
            k[:2]
            for k in obs.keys() | en_base.keys()
            if k[:2] < antes_de and obs.get(k) != en_base.get(k)
        }
        if periodos:
            out[d] = sorted(periodos)
    return out
