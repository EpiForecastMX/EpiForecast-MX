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


# ── Loader completo: folds materializados + validación ──
def test_load_policy_estructura():
    pol = policy.load_policy("rolling_cv_v1")
    assert pol.name == "rolling_cv_v1" and pol.seed == 20260724
    assert pol.seasonal_horizon == 52 and pol.mase_seasonal_lag == 52
    assert pol.primary_metric == "smape"
    assert pol.reported_metrics == ("smape", "mase", "mae", "rmse", "wape", "bias")
    assert pol.series_start == (2014, 1)
    # 4 dev + 1 test + 1 stress + 1 prospective = 7 folds.
    assert len(pol.folds) == 7 and len(pol.development_folds()) == 4


def test_dev_folds_disjuntos_52_sem_260_previas():
    dev = policy.load_policy("rolling_cv_v1").development_folds()
    assert [f.epi_year for f in dev] == [2021, 2022, 2023, 2024]
    assert all(f.n_weeks == 52 for f in dev)
    assert all(f.train_weeks_before >= 260 for f in dev)
    # Disjuntos: años distintos → holdouts sin intersección.
    todos = [p for f in dev for p in f.holdout]
    assert len(todos) == len(set(todos)) == 4 * 52


def test_fold_origen_y_holdout():
    dev = {f.epi_year: f for f in policy.load_policy("rolling_cv_v1").development_folds()}
    f21 = dev[2021]
    assert f21.holdout[0] == (2021, 1) and f21.holdout[-1] == (2021, 52)
    assert f21.origin == (2020, 53)  # última semana de train (2020 tiene 53 sem MMWR)
    assert f21.train_weeks_before == 366  # 2014-W01..2020-W53


def test_report_folds():
    folds = {f.fold_id: f for f in policy.load_policy("rolling_cv_v1").folds}
    assert folds["test_2025"].n_weeks == 53  # bloqueado, 53 sem
    assert folds["stress_2020"].n_weeks == 53  # stress, 53 sem
    assert "prospective_2026" in folds


def test_stages():
    pol = policy.load_policy("rolling_cv_v1")
    smoke = pol.folds_for_stage("smoke")
    full = pol.folds_for_stage("full")
    assert [f.epi_year for f in smoke] == [2024]  # último fold dev
    assert [f.epi_year for f in full] == [2021, 2022, 2023, 2024]
    with pytest.raises(policy.PolicyError):
        pol.folds_for_stage("no_existe")


def test_validate_rechaza_pocas_semanas_previas():
    bad = policy.Fold(
        "development_2015",
        "development",
        2015,
        tuple((2015, w) for w in range(1, 53)),
        (2014, 53),
        52,
    )  # solo 52 semanas previas (< 260)
    pol = policy.EvaluationPolicy(
        name="x",
        digest="d",
        seed=1,
        seasonal_horizon=52,
        min_train_weeks=260,
        mase_seasonal_lag=52,
        series_start=(2014, 1),
        primary_metric="smape",
        reported_metrics=("smape",),
        candidate_engines=("seasonal_naive_lag52",),
        folds=(bad,),
        stages={},
    )
    with pytest.raises(policy.PolicyError):
        policy._validate(pol)
