"""Búsqueda anidada de hiperparámetros (v2, tras la mesa de expertos del 22-nov-2026).

Sólo años de DESARROLLO de la política de cada release (``flujo.anios``). La historia se trunca al
último año de desarrollo al cargarla: los años de prueba ni siquiera viven en memoria.

CV anidada con varios pliegues externos. Para cada año externo O (los dos últimos años de
desarrollo que tengan al menos un año interno antes), la búsqueda usa sólo los años de desarrollo
anteriores a O y se mide una vez en O. Además hay un estudio de transferencia: se ajusta con todos
los años de desarrollo de los padecimientos de historia larga y se mide en los de historia corta
(un solo año de desarrollo, 2025), que nunca entran en la búsqueda.

Objetivo: media recortada (10 %) entre padecimientos de la media de log(sMAPE_motor / sMAPE_naive)
en los años internos. Es relativo al control (quita el efecto de año) y robusto a colas, y es la
misma escala del reporte. Un pronóstico no finito vale sMAPE 200.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import stats

from epiforecast.banco import ajuste, flujo
from epiforecast.runner.evaluation import smape_percent

Arr = np.ndarray[Any, Any]
PENALIZACION = 200.0
RECORTE = 0.1
CONTROL = ("estacional_nivel", ajuste.ESPACIOS["estacional_nivel"][2])  # = naive lag 52
TRANSFERENCIA = "transferencia"


@dataclass
class Padecimiento:
    disease_id: str
    y: Arr
    anios: Arr
    semanas: Arr
    desarrollo: list[int]
    ets: dict[int, dict[str, Arr]] = field(default_factory=dict)
    naive_cache: dict[int, float] = field(default_factory=dict)

    def internos(self, externo: int | str) -> list[int]:
        if externo == TRANSFERENCIA:
            return list(self.desarrollo)
        return [a for a in self.desarrollo if a < int(externo)]

    @property
    def externos(self) -> list[int]:
        """Los dos últimos años de desarrollo con al menos un año interno antes."""
        return [a for i, a in enumerate(self.desarrollo) if i >= 1][-2:]

    @property
    def historia_corta(self) -> bool:
        return len(self.desarrollo) < 2

    def corte(self, anio: int) -> tuple[Arr, Arr, Arr, Arr]:
        if anio not in self.desarrollo:
            raise flujo.BancoError(f"{self.disease_id}: {anio} no es año de desarrollo")
        n = int(np.argmax(self.anios >= anio))
        if n == 0:
            raise flujo.BancoError(f"{self.disease_id}: sin historia antes de {anio}")
        ho = self.anios == anio
        return self.y[:, :n], self.semanas[:n], self.semanas[ho], self.y[:, ho]


def cargar(disease: str) -> Padecimiento:
    dev, prueba = flujo.anios(disease)
    periodos, series = flujo.historia(disease)
    anios = np.array([a for a, _ in periodos])
    dentro = anios <= max(dev)  # trunca: los años de prueba no se cargan
    if set(anios[dentro]) & prueba:
        raise flujo.BancoError(f"{disease}: un año de prueba quedó antes del último de desarrollo")
    y = np.vstack([series[k] for k in sorted(series)])[:, dentro]
    semanas = np.array([w for _, w in periodos])[dentro]
    return Padecimiento(disease, y, anios[dentro], semanas, dev)


def precalcular_ets(p: Padecimiento) -> Padecimiento:
    """ETS nacional de cada variante y año de desarrollo (discreto: se calcula una vez)."""
    for anio in p.desarrollo:
        ytr, _, sem_ho, _ = p.corte(anio)
        nac = ytr.sum(axis=0)
        p.ets[anio] = {v: ajuste.ets_nacional(nac, len(sem_ho), v) for v in ajuste.VARIANTES_ETS}
    return p


def smape_pliegue(p: Padecimiento, motor: str, params: dict[str, Any], anio: int) -> float:
    fn = ajuste.ESPACIOS[motor][0]
    ytr, sem_tr, sem_ho, yho = p.corte(anio)
    try:
        pred = fn(ytr, sem_tr, sem_ho, params, {"ets_nacional": p.ets.get(anio, {})})
    except (ValueError, KeyError, IndexError, np.linalg.LinAlgError):
        return PENALIZACION
    if pred.shape != yho.shape or not np.isfinite(pred).all():
        return PENALIZACION
    pred = np.maximum(pred, 0.0)
    return float(smape_percent(yho.sum(axis=0), pred.sum(axis=0)))


def naive(p: Padecimiento, anio: int) -> float:
    if anio not in p.naive_cache:
        p.naive_cache[anio] = smape_pliegue(p, CONTROL[0], CONTROL[1], anio)
    return p.naive_cache[anio]


def log_ratio(p: Padecimiento, motor: str, params: dict[str, Any], anios: list[int]) -> float:
    """Media sobre ``anios`` de log(sMAPE_motor / sMAPE_naive); acotado para sMAPE cero."""
    vals = []
    for a in anios:
        m, n = smape_pliegue(p, motor, params, a), naive(p, a)
        vals.append(np.log(max(m, 1e-6) / max(n, 1e-6)))
    return float(np.mean(vals))


def objetivo(ps: list[Padecimiento], motor: str, externo: int | str) -> Any:
    espacio = ajuste.ESPACIOS[motor][1]

    def fn(trial: ajuste.Trial) -> float:
        params = espacio(trial)
        r = [log_ratio(p, motor, params, p.internos(externo)) for p in ps]
        return float(stats.trim_mean(r, RECORTE)) if len(r) > 2 else float(np.mean(r))

    return fn


def participantes(ps: list[Padecimiento], externo: int | str) -> list[Padecimiento]:
    """Padecimientos de la búsqueda para un externo: los que lo tienen y tienen años internos."""
    if externo == TRANSFERENCIA:
        return [p for p in ps if not p.historia_corta]
    return [p for p in ps if int(externo) in p.externos and p.internos(externo)]


def params_de(motor: str, crudos: dict[str, Any]) -> dict[str, Any]:
    """Reconstruye los parámetros completos (con defaults condicionales) desde un trial fijo."""

    class _Fijo:
        def suggest_int(self, name: str, low: int, high: int) -> int:
            return int(crudos[name])

        def suggest_float(self, name: str, low: float, high: float, *, log: bool = False) -> float:
            return float(crudos[name])

        def suggest_categorical(self, name: str, choices: list[Any]) -> Any:
            return crudos[name]

    return ajuste.ESPACIOS[motor][1](_Fijo())
