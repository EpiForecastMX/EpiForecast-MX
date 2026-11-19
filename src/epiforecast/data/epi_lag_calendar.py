"""Rezago de la configuración efectiva de EpiDatasetV2: serialización inyectiva del plan.

``calendar`` de ``config_effective.json`` (y por tanto ``config_digest``) debe bastar para
reconstruir el plan de rezago aplicado. Antes sólo guardaba el rezago vigente y los cambios: dos
planes con distinto rezago inicial (p. ej. 1 y 2, ambos a 0 desde 2021_sem01) daban objetivos
distintos con la misma configuración y el mismo digest.

El rezago inicial se escribe en ``lag_schedule_initial`` sólo si hay cambios y difiere de
:data:`IMPLICIT_INITIAL` (1), el inicial de los nueve datasets con cambios ya construidos y
sellados. Así su serialización, su ``config_digest`` y su ``dataset_id`` no cambian (la prueba
única de 2025 de esos releases no puede repetirse), y la lectura es inequívoca: sin la clave, el
inicial es 1. ``build_epi_dataset_v2`` comprueba la ida y vuelta y falla cerrado si no coincide.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from epiforecast.data.epi_lag_schedule import (
    GAPS_KEY,
    LAG_KEY,
    LagSchedule,
    LagScheduleError,
    _lag,
    schedule_from_group,
)

SCHEDULE_KEY = "lag_schedule"
INITIAL_KEY = "lag_schedule_initial"
# Rezago inicial implícito cuando ``calendar`` trae cambios y no trae ``INITIAL_KEY``. Es el rezago
# inicial de todos los datasets con cambios construidos antes de serializarlo; omitirlo en ese caso
# conserva byte a byte su configuración efectiva y su ``config_digest`` (releases sellados).
IMPLICIT_INITIAL = 1


def calendar_payload(schedule: LagSchedule) -> dict[str, Any]:
    """Claves de rezago de ``calendar`` en la configuración efectiva (entra en ``config_digest``).

    Inyectiva: :func:`schedule_from_calendar` recupera el plan completo. El rezago inicial sólo se
    escribe si hay cambios y difiere de :data:`IMPLICIT_INITIAL`; sin cambios coincide con el
    vigente. Así la serialización de los datasets ya construidos no cambia.
    """
    out: dict[str, Any] = {LAG_KEY: schedule.vigente}
    if schedule.changes:
        out[SCHEDULE_KEY] = schedule.payload()
        if schedule.initial != IMPLICIT_INITIAL:
            out[INITIAL_KEY] = schedule.initial
    return out


def schedule_from_calendar(calendar: Mapping[str, Any]) -> LagSchedule:
    """Plan de rezago que describe ``calendar`` (inversa de :func:`calendar_payload`)."""
    cambios = calendar.get(SCHEDULE_KEY) or []
    if not cambios:
        if INITIAL_KEY in calendar:
            raise LagScheduleError(f"{INITIAL_KEY} sin {SCHEDULE_KEY}")
        return LagSchedule(_lag(calendar.get(LAG_KEY), LAG_KEY))
    grupo = {
        LAG_KEY: calendar.get(INITIAL_KEY, IMPLICIT_INITIAL),
        "periodos": [
            {**c, GAPS_KEY: [{"periodo": g, "motivo": "-"} for g in c[GAPS_KEY]] or None}
            for c in cambios
        ],
    }
    plan = schedule_from_group(grupo)
    if plan.vigente != calendar.get(LAG_KEY):
        raise LagScheduleError(f"{LAG_KEY} {calendar.get(LAG_KEY)!r} distinto del vigente")
    return plan
