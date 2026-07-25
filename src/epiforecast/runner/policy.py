"""F2/C3 — política de evaluación declarativa (``config/evaluation/<name>.yaml``).

Todo el diseño del backtest OOS (folds por año, train previo, horizonte, métricas, seed) vive en
config; NADA en condicionales Python. El loader materializa las ventanas desde el calendario MMWR y
valida las invariantes (dev: disjuntos, 52 sem, ≥260 semanas previas). El train de un fold es toda
la historia ESTRICTAMENTE anterior al inicio del holdout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any, cast

from omegaconf import OmegaConf

from epiforecast.data.epi_calendar import shift, week_start, weeks_in_year

_ROOT = Path(__file__).resolve().parents[3]

GROUP_DEVELOPMENT = "development"  # elegibles para selección/tuning
GROUP_TEST = "test"  # bloqueado: no participa en tuning
GROUP_STRESS = "stress"  # solo reporte
GROUP_PROSPECTIVE = "prospective"  # solo reporte (parcial)


class PolicyError(ValueError):
    """Política de evaluación ausente o inválida."""


def policy_path(name: str) -> Path:
    path = _ROOT / "config" / "evaluation" / f"{name}.yaml"
    if not path.exists():
        raise PolicyError(f"política de evaluación desconocida: {name!r} ({path})")
    return path


def policy_digest(name: str) -> str:
    """sha256 del archivo de política (entra en el ``run_id`` → cambios de política = nuevo run)."""
    return hashlib.sha256(policy_path(name).read_bytes()).hexdigest()


def _load_raw(name: str) -> dict[str, Any]:
    return cast(
        "dict[str, Any]", OmegaConf.to_container(OmegaConf.load(policy_path(name)), resolve=True)
    )


def candidate_engines(name: str) -> list[str]:
    """Motores candidatos declarados en la política (default del benchmark)."""
    raw = _load_raw(name)
    engines = [str(e) for e in raw.get("candidate_engines", [])]
    if not engines:
        raise PolicyError(f"política {name!r} sin candidate_engines")
    return engines


def policy_seed(name: str) -> int:
    return int(_load_raw(name)["seed"])


# ── Loader completo: folds materializados + validación ──
def _count_periods(start: tuple[int, int], end: tuple[int, int]) -> int:
    """Nº de periodos MMWR en [start, end) (diferencia de fechas de inicio de semana / 7)."""
    days = (week_start(end[0], end[1]) - week_start(start[0], start[1])).days
    return days // 7


@dataclass(frozen=True)
class Fold:
    """Un fold OOS: holdout (periodos futuros) + origen (última semana de train)."""

    fold_id: str  # p.ej. "development_2021"
    group: str  # development | test | stress | prospective
    epi_year: int
    holdout: tuple[tuple[int, int], ...]  # periodos (epi_year, epi_week) del holdout
    train_end: tuple[int, int]  # última semana de train (origen del pronóstico)
    train_weeks_before: int  # nº de periodos de train disponibles desde series_start

    @property
    def n_weeks(self) -> int:
        return len(self.holdout)

    @property
    def origin(self) -> tuple[int, int]:
        return self.train_end


@dataclass(frozen=True)
class EvaluationPolicy:
    """Política de backtest OOS materializada y validada."""

    name: str
    digest: str
    seed: int
    seasonal_horizon: int
    min_train_weeks: int
    mase_seasonal_lag: int
    series_start: tuple[int, int]
    primary_metric: str
    reported_metrics: tuple[str, ...]
    candidate_engines: tuple[str, ...]
    folds: tuple[Fold, ...]
    stages: dict[str, Any]
    selection: dict[str, Any] = field(default_factory=dict)
    acceptance: dict[str, Any] = field(default_factory=dict)

    def development_folds(self) -> tuple[Fold, ...]:
        return tuple(f for f in self.folds if f.group == GROUP_DEVELOPMENT)

    def folds_for_stage(self, stage: str) -> tuple[Fold, ...]:
        spec = self.stages.get(stage)
        if spec is None:
            raise PolicyError(f"stage desconocido en la política {self.name!r}: {stage!r}")
        groups = set(spec.get("fold_groups", [GROUP_DEVELOPMENT]))
        chosen = tuple(f for f in self.folds if f.group in groups)
        last_n = spec.get("last_n_folds")
        if last_n:
            chosen = chosen[-int(last_n) :]
        return chosen


def _build_fold(group: str, entry: dict[str, Any], series_start: tuple[int, int]) -> Fold:
    year = int(entry["epi_year"])
    calendar_weeks = weeks_in_year(year)
    n_weeks = int(entry.get("n_weeks", calendar_weeks))
    if "n_weeks" in entry and n_weeks != calendar_weeks:
        raise PolicyError(
            f"fold {group}_{year}: n_weeks={n_weeks} no coincide con el calendario "
            f"({calendar_weeks} semanas MMWR)"
        )
    holdout = tuple((year, w) for w in range(1, n_weeks + 1))
    train_end = shift(year, 1, -1)  # semana inmediatamente anterior al holdout
    before = _count_periods(series_start, (year, 1))
    return Fold(f"{group}_{year}", group, year, holdout, train_end, before)


def load_policy(name: str) -> EvaluationPolicy:
    """Carga y VALIDA la política: folds materializados desde el calendario + invariantes dev."""
    raw = _load_raw(name)
    ss = raw["series_start"]
    series_start = (int(ss["epi_year"]), int(ss["epi_week"]))
    folds = tuple(
        _build_fold(group, entry, series_start)
        for group, entries in raw["folds"].items()
        for entry in entries
    )
    metrics = raw["metrics"]
    pol = EvaluationPolicy(
        name=str(raw["name"]),
        digest=policy_digest(name),
        seed=int(raw["seed"]),
        seasonal_horizon=int(raw["seasonal_horizon"]),
        min_train_weeks=int(raw["min_train_weeks"]),
        mase_seasonal_lag=int(raw["mase_seasonal_lag"]),
        series_start=series_start,
        primary_metric=str(metrics["primary"]),
        reported_metrics=tuple(str(m) for m in metrics["reported"]),
        candidate_engines=tuple(candidate_engines(name)),
        folds=folds,
        stages=dict(raw["stages"]),
        selection=dict(raw.get("selection", {})),
        acceptance=dict(raw.get("acceptance", {})),
    )
    _validate(pol)
    return pol


def _validate(pol: EvaluationPolicy) -> None:
    if pol.seasonal_horizon <= 0 or pol.mase_seasonal_lag <= 0:
        raise PolicyError("seasonal_horizon y mase_seasonal_lag deben ser positivos")
    dev = pol.development_folds()
    if len(dev) < 1:
        raise PolicyError("la política no declara folds de development")
    # Dev: cada fold con 52 semanas y ≥ min_train_weeks previas.
    for f in dev:
        if f.n_weeks != 52:
            raise PolicyError(f"fold dev {f.fold_id}: {f.n_weeks} semanas (se esperan 52)")
        if f.train_weeks_before < pol.min_train_weeks:
            raise PolicyError(
                f"fold dev {f.fold_id}: {f.train_weeks_before} semanas previas "
                f"(< {pol.min_train_weeks})"
            )
    # Todos los folds disjuntos (ningún periodo compartido entre folds).
    seen: set[tuple[int, int]] = set()
    for f in pol.folds:
        overlap = seen & set(f.holdout)
        if overlap:
            raise PolicyError(f"folds solapados en {sorted(overlap)[:3]}")
        seen.update(f.holdout)
