"""Calendario epidemiológico (estilo MMWR/CDC) para el carril E66 / EpiDatasetV2 (F1).

Contrato (plan §3 F1):

- La semana epidemiológica va de **domingo a sábado**.
- La **semana 1** de un ``epi_year`` es la que contiene el **4 de enero** (equivalente: la primera
  semana con ≥4 días en enero); su ``period_start`` es el **domingo en o antes del 4 de enero**.
- ``period_start`` = domingo epidemiológico de ``(epi_year, epi_week)``.
- ``ds`` = **lunes siguiente** a ``period_start`` (solo timestamp de modelado).
- La identidad canónica es ``(epi_year, epi_week)`` — **NO** la fecha ISO ni el máximo observado.
- Un boletín declara ``observation_lag_weeks`` (E66 = 1): la ``(año, semana)`` de la **fuente** se
  desplaza ``lag`` semanas hacia atrás en el calendario epidemiológico para obtener el **objetivo**.

Este módulo es **puro** y **no** reemplaza a ``data/preprocessing/transformer.py`` (que sirve el
legacy neuro/Dengue byte-idéntico con calendario ISO). Es exclusivamente para el carril nuevo.

Ejemplos (verificados en pruebas): fuente ``2025-W53`` → ``2025-W52`` (``ds=2025-12-22``);
``2026-W01`` → ``2025-W53`` (``ds=2025-12-29``); ``2026-W02`` → ``2026-W01`` (``ds=2026-01-05``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


def _sunday_on_or_before(d: date) -> date:
    """El domingo en o antes de ``d`` (``date.weekday()``: lun=0 … dom=6)."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def first_week_start(epi_year: int) -> date:
    """Domingo que inicia la **semana 1** de ``epi_year`` (domingo en o antes del 4 de enero)."""
    return _sunday_on_or_before(date(epi_year, 1, 4))


def weeks_in_year(epi_year: int) -> int:
    """Número de semanas epidemiológicas (52 o 53) en ``epi_year``."""
    return (first_week_start(epi_year + 1) - first_week_start(epi_year)).days // 7


def week_start(epi_year: int, epi_week: int) -> date:
    """``period_start`` (domingo) de ``(epi_year, epi_week)``.

    Levanta ``ValueError`` si ``epi_week`` cae fuera de ``1..weeks_in_year(epi_year)`` — las
    anomalías se **clasifican** (fail-loud), no se corrigen silenciosamente.
    """
    n = weeks_in_year(epi_year)
    if not 1 <= epi_week <= n:
        raise ValueError(f"epi_week {epi_week} fuera de rango 1..{n} para el año {epi_year}")
    return first_week_start(epi_year) + timedelta(weeks=epi_week - 1)


def epi_from_date(d: date) -> tuple[int, int]:
    """``(epi_year, epi_week)`` al que pertenece la fecha ``d`` (cualquier día de su semana)."""
    s = _sunday_on_or_before(d)
    year = s.year + 1
    while first_week_start(year) > s:
        year -= 1
    return year, (s - first_week_start(year)).days // 7 + 1


def shift(epi_year: int, epi_week: int, delta_weeks: int) -> tuple[int, int]:
    """Desplaza ``(epi_year, epi_week)`` en ``delta_weeks`` cruzando fronteras 52/53/1 sin colisión."""
    return epi_from_date(week_start(epi_year, epi_week) + timedelta(weeks=delta_weeks))


def ds_for(epi_year: int, epi_week: int) -> date:
    """``ds`` de modelado: el **lunes** siguiente al ``period_start`` de ``(epi_year, epi_week)``."""
    return week_start(epi_year, epi_week) + timedelta(days=1)


@dataclass(frozen=True)
class EpiPeriod:
    """Periodo epidemiológico objetivo con su identidad canónica y timestamps derivados."""

    epi_year: int
    epi_week: int
    period_start: date  # domingo epidemiológico
    ds: date  # lunes de modelado (period_start + 1 día)


def target_period(source_year: int, source_week: int, observation_lag_weeks: int) -> EpiPeriod:
    """De la ``(año, semana)`` de **fuente** del boletín a la :class:`EpiPeriod` **objetivo**.

    Aplica el ``observation_lag_weeks`` desplazando hacia atrás en el calendario epidemiológico.
    """
    if observation_lag_weeks < 0:
        raise ValueError(f"observation_lag_weeks negativo: {observation_lag_weeks}")
    epi_year, epi_week = shift(source_year, source_week, -observation_lag_weeks)
    ps = first_week_start(epi_year) + timedelta(weeks=epi_week - 1)
    return EpiPeriod(epi_year, epi_week, ps, ps + timedelta(days=1))
