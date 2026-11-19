"""Rezago impreso por periodo (opt-in) para EpiDatasetV2: fuente del boletín → periodo objetivo.

Un grupo de ``config/data/cuadros.yaml`` declara ``observation_lag_weeks`` (rezago inicial). Cuando
el título impreso cambia de régimen una sola vez (p. ej. «hasta la semana N-1» hasta 2020_sem53 y
«hasta la semana N» desde 2021_sem01), una entrada de ``periodos`` lo declara::

    periodos:
      - desde: "2021_sem01"
        observation_lag_weeks: 0
        huecos_objetivo:
          - {periodo: "2020-W53", motivo: "..."}

El rezago **vigente** (el del último cambio) es el que aplica a todo boletín posterior, incluido el
paso semanal. Sin cambios declarados el plan es idéntico al rezago constante de siempre.

Contrato (falla cerrado):

- Dos boletines consecutivos del raw nunca comparten ni invierten su periodo objetivo
  (solapamiento: dos fuentes al mismo objetivo).
- En la frontera de un cambio de rezago los boletines deben ser consecutivos; los periodos objetivo
  que ninguna fuente cubre (hueco) deben declararse en ``huecos_objetivo`` de ese cambio, y un hueco
  declarado que no ocurre también falla. Un hueco declarado se emite como periodo sin fuente (casos y
  acumulados vacíos): la reconciliación lo imputa causalmente y lleva ``lag_regime_gap``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import pairwise
import re
from typing import Any, SupportsFloat, SupportsInt, cast

import pandas as pd

from epiforecast.data import epi_calendar as ec
from epiforecast.data.epi_dataset_spec import QualityFlag
from epiforecast.data.epi_geo_exposure import GeoCatalog

Period = tuple[int, int]
_DESDE = re.compile(r"^(\d{4})_sem(\d{2})$")
_PERIODO = re.compile(r"^(\d{4})-W(\d{2})$")
LAG_KEY = "observation_lag_weeks"
GAPS_KEY = "huecos_objetivo"


class LagScheduleError(ValueError):
    """Rezago por periodo mal declarado, solapamiento o hueco objetivo no declarado."""


@dataclass(frozen=True)
class LagChange:
    """Desde el boletín ``desde`` (incluido) el rezago impreso es ``lag``."""

    desde: Period
    lag: int
    gaps: tuple[Period, ...] = ()  # periodos objetivo sin fuente, declarados con motivo


@dataclass(frozen=True)
class LagSchedule:
    initial: int
    changes: tuple[LagChange, ...] = ()

    def regime_of(self, source: Period) -> int:
        """Índice del último cambio vigente en ``source`` (-1 = rezago inicial)."""
        idx = -1
        for i, ch in enumerate(self.changes):
            if source >= ch.desde:
                idx = i
        return idx

    def lag_for(self, source: Period) -> int:
        i = self.regime_of(source)
        return self.initial if i < 0 else self.changes[i].lag

    @property
    def vigente(self) -> int:
        """Rezago del último régimen: el que usa todo lo semanal."""
        return self.changes[-1].lag if self.changes else self.initial

    def payload(self) -> list[dict[str, Any]]:
        """Forma canónica para el digest de configuración (vacía si el rezago es constante)."""
        return [
            {
                "desde": f"{c.desde[0]}_sem{c.desde[1]:02d}",
                LAG_KEY: c.lag,
                GAPS_KEY: [f"{y}-W{w:02d}" for y, w in c.gaps],
            }
            for c in self.changes
        ]


def _lag(value: object, who: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LagScheduleError(f"{who} inválido (entero >=0, no bool): {value!r}")
    return value


def _period(text: object, pattern: re.Pattern[str], who: str) -> Period:
    m = pattern.match(str(text)) if isinstance(text, str) else None
    if m is None:
        raise LagScheduleError(f"{who}: formato inválido {text!r}")
    year, week = int(m.group(1)), int(m.group(2))
    try:
        ec.week_start(year, week)
    except ValueError as exc:
        raise LagScheduleError(f"{who}: {exc}") from exc
    return year, week


def _gaps(value: object, who: str) -> tuple[Period, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not value:
        raise LagScheduleError(f"{who}: se esperaba una lista no vacía")
    out: list[Period] = []
    for j, item in enumerate(value):
        if not isinstance(item, Mapping) or set(item) != {"periodo", "motivo"}:
            raise LagScheduleError(f"{who}[{j}]: se esperaba {{periodo, motivo}}")
        if not str(item["motivo"] or "").strip():
            raise LagScheduleError(f"{who}[{j}]: motivo vacío")
        out.append(_period(item["periodo"], _PERIODO, f"{who}[{j}].periodo"))
    if len(set(out)) != len(out):
        raise LagScheduleError(f"{who}: periodos repetidos")
    return tuple(sorted(out))


def schedule_from_group(group: Mapping[str, Any]) -> LagSchedule:
    """Plan de rezago de un grupo de cuadro: inicial + cambios declarados en ``periodos``."""
    if GAPS_KEY in group:
        raise LagScheduleError(f"{GAPS_KEY} sólo se declara dentro del cambio de rezago")
    initial = _lag(group.get(LAG_KEY), LAG_KEY)
    changes: list[LagChange] = []
    for i, per in enumerate(group.get("periodos") or []):
        who = f"periodos[{i}]"
        if LAG_KEY not in per:
            if GAPS_KEY in per:
                raise LagScheduleError(f"{who}: {GAPS_KEY} sin cambio de {LAG_KEY}")
            continue
        desde = _period(per.get("desde"), _DESDE, f"{who}.desde")
        if changes and desde <= changes[-1].desde:
            raise LagScheduleError(f"{who}: los cambios de rezago deben ir en orden creciente")
        lag = _lag(per[LAG_KEY], f"{who}.{LAG_KEY}")
        changes.append(LagChange(desde, lag, _gaps(per.get(GAPS_KEY), f"{who}.{GAPS_KEY}")))
    return LagSchedule(initial, tuple(changes))


@dataclass(frozen=True)
class TargetPlan:
    targets: dict[Period, ec.EpiPeriod]  # fuente → objetivo
    gaps: tuple[tuple[ec.EpiPeriod, Period], ...]  # (objetivo sin fuente, boletín que lo cierra)


def plan_targets(sources: Iterable[Period], schedule: LagSchedule) -> TargetPlan:
    """Objetivo de cada boletín fuente; falla ante solapamiento o hueco no declarado."""
    ordered = sorted(set(sources))
    targets = {s: ec.target_period(s[0], s[1], schedule.lag_for(s)) for s in ordered}
    gaps: list[tuple[ec.EpiPeriod, Period]] = []
    found: dict[int, set[Period]] = {}
    for prev, nxt in pairwise(ordered):
        tp, tn = targets[prev], targets[nxt]
        if tn.period_start <= tp.period_start:
            raise LagScheduleError(
                f"solapamiento: {prev} → {tp.epi_year}-W{tp.epi_week:02d} y {nxt} → "
                f"{tn.epi_year}-W{tn.epi_week:02d} (dos fuentes al mismo objetivo)"
            )
        if schedule.lag_for(prev) == schedule.lag_for(nxt):
            continue  # mismo rezago: un objetivo faltante sólo refleja un boletín faltante
        if ec.shift(prev[0], prev[1], 1) != nxt:
            raise LagScheduleError(
                f"cambio de rezago entre boletines no consecutivos {prev} y {nxt}: "
                "declarar el boletín intermedio (keep_period) antes de la frontera"
            )
        actual = ec.shift(tp.epi_year, tp.epi_week, 1)
        while actual != (tn.epi_year, tn.epi_week):
            gaps.append((ec.target_period(actual[0], actual[1], 0), nxt))
            found.setdefault(schedule.regime_of(nxt), set()).add(actual)
            actual = ec.shift(actual[0], actual[1], 1)
    for i, ch in enumerate(schedule.changes):
        hallados, declarados = found.get(i, set()), set(ch.gaps)
        if hallados - declarados:
            raise LagScheduleError(
                f"hueco objetivo no declarado al cambiar el rezago en {ch.desde}: "
                f"{sorted(hallados - declarados)} (declararlo en {GAPS_KEY} con motivo)"
            )
        if declarados - hallados:
            raise LagScheduleError(
                f"hueco declarado que no ocurre en {ch.desde}: {sorted(declarados - hallados)}"
            )
    return TargetPlan(targets, tuple(gaps))


def _i(v: object) -> int:
    return int(cast("SupportsInt", v))


def _f(v: object) -> float:
    return float(cast("SupportsFloat", v))


def build_prep(raw: pd.DataFrame, catalog: GeoCatalog, lag: int | LagSchedule) -> pd.DataFrame:
    """raw → prep (calendario objetivo + cve_ent), listo para ``reconcile_state``.

    ``lag`` entero equivale a un rezago constante. Los huecos declarados se emiten como periodos
    sin fuente para cada entidad del catálogo (la reconciliación los imputa).
    """
    schedule = lag if isinstance(lag, LagSchedule) else LagSchedule(_lag(lag, LAG_KEY))
    sources = {(_i(y), _i(w)) for y, w in zip(raw["Anio"], raw["Semana"], strict=True)}
    plan = plan_targets(sources, schedule)
    recs: list[dict[str, object]] = []
    sin_sexo = "Acumulado_total" in raw.columns
    for r in raw.itertuples(index=False):
        tp = plan.targets[(_i(r.Anio), _i(r.Semana))]
        recs.append(
            {
                "cve_ent": catalog.resolve(str(r.Entidad)),
                "source_year": _i(r.Anio),
                "source_week": _i(r.Semana),
                "epi_year": tp.epi_year,
                "epi_week": tp.epi_week,
                "period_start": tp.period_start,
                "ds": tp.ds,
                "casos_source": (float("nan") if pd.isna(r.Casos_semana) else _f(r.Casos_semana)),
                # Sin desglose por sexo, el acumulado total ocupa el lugar de «hombres» y
                # «mujeres» queda en cero: la reconciliación del total no cambia.
                "acum_h": _f(r.Acumulado_total if sin_sexo else r.Acumulado_hombres),
                "acum_m": 0.0 if sin_sexo else _f(r.Acumulado_mujeres),
            }
        )
    for tp, (sy, sw) in plan.gaps:
        for cve in catalog.cve_ents():
            recs.append(
                {
                    "cve_ent": cve,
                    "source_year": sy,
                    "source_week": sw,
                    "epi_year": tp.epi_year,
                    "epi_week": tp.epi_week,
                    "period_start": tp.period_start,
                    "ds": tp.ds,
                    "casos_source": float("nan"),
                    "acum_h": float("nan"),
                    "acum_m": float("nan"),
                }
            )
    return pd.DataFrame(recs)


def mark_gap_rows(state: pd.DataFrame, schedule: LagSchedule) -> pd.DataFrame:
    """Añade ``lag_regime_gap`` a las filas estatales de los huecos declarados."""
    huecos = {p for ch in schedule.changes for p in ch.gaps}
    if not huecos:
        return state
    out = state.copy()
    en_hueco = [
        (int(y), int(w)) in huecos for y, w in zip(out["epi_year"], out["epi_week"], strict=True)
    ]
    out.loc[en_hueco, "quality_flags"] = [
        "|".join(f for f in (str(flags), QualityFlag.LAG_REGIME_GAP) if f)
        for flags in out.loc[en_hueco, "quality_flags"]
    ]
    return out
