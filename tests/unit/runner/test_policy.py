"""F2/C3.0 — política de evaluación: ruta, digest, candidatos y seed (config trackeado, CI-safe)."""

from __future__ import annotations

import pytest

from epiforecast.runner import policy


def test_candidate_engines_desde_politica():
    # Los candidatos vienen de la política, NO de los training_engines legacy del registry.
    assert policy.candidate_engines("rolling_cv_v1") == ["seasonal_naive_lag52"]


def test_policy_digest_estable_y_no_vacio():
    d1 = policy.policy_digest("rolling_cv_v1")
    d2 = policy.policy_digest("rolling_cv_v1")
    assert d1 == d2 and len(d1) == 64


def test_policy_seed():
    assert policy.policy_seed("rolling_cv_v1") == 20260724


def test_politica_desconocida_levanta():
    with pytest.raises(policy.PolicyError):
        policy.policy_digest("no_existe")
