"""F2/C3c — contrato del harness: train cortado en el origen, TrainingSpec real, gates de validez."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from epiforecast.data import epi_dataset_spec as spec
from epiforecast.data.epi_calendar import weeks_in_year
from epiforecast.runner import contracts as ct
from epiforecast.runner.engines import harness
from epiforecast.runner.policy import load_policy

_ENGINE = "spy_engine"
_DISEASE = "synthetic_disease"
_RATE_DISEASE = "obesidad"  # la escala de tasa sale del perfil del registry, no del test
_SERIES = (("05", "hombres"), ("09", "mujeres"))


def _rate_transform(engine: str):
    return ct.rate_log1p_transform(_RATE_DISEASE, engine)


def _fold():
    return load_policy("rolling_cv_v1").development_folds()[0]  # 2021 (origen 2020-W53)


def _base_truth(years=(2019, 2020, 2021)) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                spec.COL_GEO_ID: cve,
                spec.COL_SEX: sexo,
                spec.COL_EPI_YEAR: y,
                spec.COL_EPI_WEEK: w,
                spec.COL_Y_CASES: float(y * 100 + w),
                spec.COL_EXPOSURE: 1_000_000.0,
            }
            for cve, sexo in _SERIES
            for y in years
            for w in range(1, weeks_in_year(y) + 1)
        ]
    )


def _ctx(**over: Any) -> harness.EngineContext:
    kwargs: dict[str, Any] = {
        "engine": _ENGINE,
        "disease_id": _DISEASE,
        "dataset_digest": "d" * 64,
        "policy_name": "rolling_cv_v1",
        "policy_digest": "p" * 64,
        "seed": 20260724,
        "transform": ct.identity_transform(_DISEASE, _ENGINE),
    }
    kwargs.update(over)
    return harness.EngineContext(**kwargs)


def _flat(request: harness.SeriesRequest, value: float = 1.0) -> harness.SeriesForecast:
    return harness.SeriesForecast({p: value for p in request.holdout})


def test_train_cortado_en_el_origen():
    # El predictor NUNCA recibe la verdad del holdout: la invariancia post-origen es estructural.
    fold = _fold()
    seen: list[harness.SeriesRequest] = []

    def predict(request):
        seen.append(request)
        return _flat(request)

    harness._predict_fold(_base_truth(), fold, "run1", _ctx(), predict)
    assert len(seen) == len(_SERIES)
    for request in seen:
        assert max(request.train) == fold.train_end == (2020, 53)
        assert not set(request.train) & set(fold.holdout)
        assert len(request.train) == 53 + weeks_in_year(2019)  # 2019 + 2020 completos
        assert list(request.train) == sorted(request.train)  # orden ascendente garantizado


def test_training_spec_materializado():
    fold = _fold()
    specs: list[ct.TrainingSpec] = []

    def predict(request):
        specs.append(request.spec)
        return _flat(request)

    harness._predict_fold(_base_truth(), fold, "run1", _ctx(params={"k": 3}), predict)
    ts = specs[0]
    assert ts.engine == _ENGINE and ts.fold_id == fold.fold_id and ts.seed == 20260724
    assert ts.horizon == len(fold.holdout) == 52
    assert ts.dataset_digest == "d" * 64 and ts.policy_digest == "p" * 64
    assert ts.engine_params == {"k": 3} and ts.transform.engine_id == _ENGINE
    assert ts.key.disease_id == _DISEASE and ts.key.geography_level == "estado"
    assert {(s.key.geography_id, s.key.sex) for s in specs} == set(_SERIES)


def test_holdout_incompleto_levanta():
    def predict(request):
        preds = {p: 1.0 for p in request.holdout}
        preds.pop(request.holdout[-1])
        return harness.SeriesForecast(preds)

    with pytest.raises(harness.HarnessError, match="no cubren el holdout"):
        harness._predict_fold(_base_truth(), _fold(), "run1", _ctx(), predict)


@pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
def test_prediccion_invalida_levanta(bad):
    def predict(request):
        preds = {p: 1.0 for p in request.holdout}
        preds[request.holdout[0]] = bad
        return harness.SeriesForecast(preds)

    with pytest.raises(harness.HarnessError, match="predicción inválida"):
        harness._predict_fold(_base_truth(), _fold(), "run1", _ctx(), predict)


def test_diagnosticos_llevan_identidad_y_digests():
    ctx = _ctx()
    out = harness._predict_fold(
        _base_truth(),
        _fold(),
        "run1",
        ctx,
        lambda r: harness.SeriesForecast(
            {p: 1.0 for p in r.holdout}, diagnostics={"variant": "primary"}
        ),
    )
    assert len(out.diagnostics) == len(_SERIES) and len(out.timing) == len(_SERIES)
    row = out.diagnostics[0]
    assert row["fold"] == "development_2021" and row["disease_id"] == _DISEASE
    assert row["n_train"] == 53 + weeks_in_year(2019) and row["variant"] == "primary"
    assert row["transform_digest"] == ctx.transform.digest()
    assert row["config_digest"] == ctx.config_digest()
    assert "fit_seconds" in out.timing[0]  # telemetría wall-clock, fuera del artefacto


def test_sin_diagnosticos_no_emite_filas():
    out = harness._predict_fold(_base_truth(), _fold(), "run1", _ctx(), _flat)
    assert out.diagnostics == [] and len(out.forecast) == len(_SERIES) * 52


def test_exposicion_cubre_train_y_holdout_sin_filtrar_casos():
    # La exposición del holdout es el denominador del periodo objetivo, no una observación futura.
    fold = _fold()
    seen: list[harness.SeriesRequest] = []
    ctx = _ctx(
        engine="prophet_rate",
        disease_id=_RATE_DISEASE,
        transform=_rate_transform("prophet_rate"),
    )

    def predict(request):
        seen.append(request)
        return _flat(request)

    harness._predict_fold(_base_truth(), fold, "run1", ctx, predict)
    for request in seen:
        assert set(request.train_exposure) == set(request.train)
        assert set(request.holdout_exposure) == set(request.holdout)
        assert all(v == 1_000_000.0 for v in request.holdout_exposure.values())
        assert not set(request.holdout) & set(request.train)  # los casos del holdout no viajan


def test_exposicion_incompleta_o_no_positiva_levanta():
    ctx = _ctx(
        engine="prophet_rate",
        disease_id=_RATE_DISEASE,
        transform=_rate_transform("prophet_rate"),
    )
    base = _base_truth()
    faltante = base[~((base[spec.COL_EPI_YEAR] == 2021) & (base[spec.COL_EPI_WEEK] == 5))]
    with pytest.raises(harness.HarnessError, match="no cubre exactamente"):
        harness._predict_fold(faltante, _fold(), "run1", ctx, _flat)

    cero = base.copy()
    cero.loc[cero[spec.COL_EPI_YEAR] == 2021, spec.COL_EXPOSURE] = 0.0
    with pytest.raises(harness.HarnessError, match="exposición inválida"):
        harness._predict_fold(cero, _fold(), "run1", ctx, _flat)


def test_round_trip_de_tasa_vuelve_a_casos():
    transform = _rate_transform("prophet_rate")
    casos = np.array([0.0, 7.0, 153.0, 4210.0])
    exposicion = np.array([1_000_000.0, 250_000.0, 3_500_000.0, 900_000.0])
    ida = transform.apply_forward(casos, exposure=exposicion)
    vuelta = transform.apply_inverse(ida, exposure=exposicion)
    assert np.allclose(vuelta, casos, rtol=0, atol=1e-9)
    assert transform.rate_scale == 100_000.0  # del perfil del registry, no hardcodeado


def test_config_digest_depende_de_params_y_transform():
    base = _ctx().config_digest()
    assert base == _ctx().config_digest()
    assert base != _ctx(params={"k": 3}).config_digest()
    assert base != _ctx(resource_limits={"max_threads": 1}).config_digest()
    assert base != _ctx(transform=ct.log1p_transform(_DISEASE, _ENGINE)).config_digest()
