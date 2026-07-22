"""E1-S3: completeness fail-fast (reemplaza el ``raise`` en runtime de tuner.py).

Todo padecimiento del registry debe estar completo (grids, web, cie, elegibles⊆entrenables)
antes de entrenar. Falla en CI, no a media hora de CV.
"""

from __future__ import annotations

from epiforecast import registry
from epiforecast.registry_doctor import diagnose


def test_registry_completo_sin_errores():
    problems = [p for p in diagnose() if p.severity == "error"]
    assert problems == [], [f"[{p.disease}] {p.message}" for p in problems]


def test_todo_padecimiento_con_prophet_tiene_grid():
    for d in registry.get_registry().diseases:
        if "prophet" in d.training_engines:
            assert d.prophet_grid_key, f"{d.id}: sin prophet_grid_key"


def test_obesidad_config_only_verde():
    # El onboarding de Obesidad debe dejar su config completa aunque siga 'configured'.
    problems = [p for p in diagnose("Obesidad") if p.severity == "error"]
    assert problems == [], [p.message for p in problems]
