"""Regla canónica de selección de motor productivo por serie (EPIC 3).

Núcleo compartido por las tres políticas del selector unificado
(``legacy_neuro_2026``, ``legacy_dengue_2026``, ``rolling_cv_v1``). Implementa el
criterio del proyecto (ver ``perseriesmodel2026/src/selection.py``):

  Tier 1  menor sMAPE; candidatos dentro de ``REL_MARGIN`` (5%) del mejor pasan a
  Tier 2  menor MASE; empate exacto pasa a
  Tier 3  menor RMSE; si persiste, orden estable por nombre de motor.

Más el fallback de baja incidencia: series con < ``LOW_INCIDENCE_CASES`` casos en las
52 semanas previas al origen se asignan al motor regional (no a su motor propio).

Toda comparación es sobre **casos absolutos** (tras invertir tasa/log). Este módulo es
puro y determinista (sin I/O), para poder testearlo aisladamente.
"""

from __future__ import annotations

from dataclasses import dataclass

REL_MARGIN: float = 0.05
LOW_INCIDENCE_CASES: int = 5


@dataclass(frozen=True)
class Candidate:
    """Métricas de un motor candidato para una serie (menor = mejor)."""

    engine: str
    smape: float | None = None
    mase: float | None = None
    rmse: float | None = None


def select_engine(candidates: list[Candidate], rel_margin: float = REL_MARGIN) -> str | None:
    """Devuelve el motor ganador aplicando el criterio de 3 tiers, o ``None`` si no hay
    candidato con sMAPE."""
    valid = [c for c in candidates if c.smape is not None]
    if not valid:
        return None

    # Tier 1: banda de sMAPE (dentro de rel_margin del mejor).
    smapes = [s for s in (c.smape for c in valid) if s is not None]
    threshold = min(smapes) * (1 + rel_margin)
    band = [c for c in valid if c.smape is not None and c.smape <= threshold]
    if len(band) == 1:
        return band[0].engine

    # Tier 2: menor MASE (empate exacto continúa).
    with_mase = [c for c in band if c.mase is not None]
    if with_mase:
        best_mase = min(m for m in (c.mase for c in with_mase) if m is not None)
        tied = [c for c in with_mase if c.mase == best_mase]
        if len(tied) == 1:
            return tied[0].engine
        band = tied

    # Tier 3: menor RMSE.
    with_rmse = [c for c in band if c.rmse is not None]
    if with_rmse:
        best_rmse = min(r for r in (c.rmse for c in with_rmse) if r is not None)
        band = [c for c in with_rmse if c.rmse == best_rmse]

    # Desempate final estable: orden alfabético de motor (determinista).
    return sorted(band, key=lambda c: c.engine)[0].engine


def is_low_incidence(trailing_52wk_total: float, threshold: int = LOW_INCIDENCE_CASES) -> bool:
    """``True`` si la serie tiene menos de ``threshold`` casos en las 52 semanas previas al
    origen (se asigna al motor regional en vez de a su motor propio)."""
    return trailing_52wk_total < threshold
