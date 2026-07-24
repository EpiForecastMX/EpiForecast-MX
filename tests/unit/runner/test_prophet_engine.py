"""F2/C4.3 — perfiles Prophet: rejilla determinista, transform por metadata y fail-closed."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd
import pytest

from epiforecast.data.epi_calendar import ds_for, shift
from epiforecast.data.epi_dataset_spec import SeriesKey
from epiforecast.runner import adapters
from epiforecast.runner import contracts as ct
from epiforecast.runner.engines import harness, prophet_engine
from epiforecast.runner.engines.prophet_engine import (
    ProphetEngineError,
    build_grid,
    load_prophet_config,
)

_DISEASE = "obesidad"  # perfil del registry: rate_scale=100000
_COUNT = "prophet_count_log1p"
_RATE = "prophet_rate_log1p"
_CFG = load_prophet_config()
_N_TRAIN = 366
_HORIZON = 8  # horizonte corto: los tests unitarios no necesitan 52 semanas
_EXPOSICION = 500_000.0


def _periods(n: int, start: tuple[int, int] = (2014, 1)) -> list[tuple[int, int]]:
    out = [start]
    for _ in range(n - 1):
        out.append(shift(out[-1][0], out[-1][1], 1))
    return out


def _request(valores, engine: str = _COUNT, horizon: int = _HORIZON) -> harness.SeriesRequest:
    todos = _periods(len(valores) + horizon)
    train_p, holdout = todos[: len(valores)], tuple(todos[len(valores) :])
    transform = prophet_engine._TRANSFORMS[str(_CFG["engines"][engine]["transform"])]
    spec = ct.TrainingSpec(
        key=SeriesKey(_DISEASE, "estado", "05", "hombres"),
        engine=engine,
        dataset_digest="d" * 64,
        policy_name="rolling_cv_v1",
        policy_digest="p" * 64,
        fold_id="development_2021",
        seed=20260724,
        horizon=horizon,
        transform=transform(_DISEASE, engine),
    )
    return harness.SeriesRequest(
        spec,
        {p: float(v) for p, v in zip(train_p, valores, strict=True)},
        holdout,
        train_p[-1],
        {p: _EXPOSICION for p in train_p},
        {p: _EXPOSICION for p in holdout},
    )


def _config(**over: Any) -> dict[str, Any]:
    base = {
        "seasonality_mode": "additive",
        "changepoint_prior_scale": 0.01,
        "seasonality_prior_scale": 0.5,
        "fourier_order": 5,
    }
    base.update(over)
    return base


def _serie(n: int, nivel: float = 100.0, amplitud: float = 0.3):
    days = np.array([ds_for(*p).toordinal() for p in _periods(n)], dtype=float)
    return np.expm1(np.log1p(nivel) + amplitud * np.sin(2 * np.pi * days / 365.25))


def test_adapters_registrados_con_tune_y_benchmark():
    for name in (_COUNT, _RATE):
        ad = adapters.get_adapter(name)
        assert ad is not None
        assert ad.supports("benchmark") and ad.supports("tune")
        assert not ad.supports("refit") and not ad.supports("forecast")


def test_config_declarativa_sin_extras_legacy():
    common = _CFG["common"]
    assert common["growth"] == "linear"
    assert common["yearly_seasonality"] is False  # nativas desactivadas
    assert common["weekly_seasonality"] is False and common["daily_seasonality"] is False
    assert common["uncertainty_samples"] == 0 and common["mcmc_samples"] == 0
    assert common["seasonality_period_days"] == 365.25
    assert set(_CFG["engines"]) == {_COUNT, _RATE}
    assert _CFG["grid"]["fourier_order"] == [5, 10]
    assert [r["param"] for r in _CFG["selection"]["tie_break"]] == [
        "fourier_order",
        "changepoint_prior_scale",
        "seasonality_prior_scale",
        "seasonality_mode",
    ]


def test_rejilla_completa_y_determinista():
    grid = build_grid(_CFG)
    assert len(grid) == 36 == 2 * 3 * 3 * 2
    assert grid == build_grid(_CFG) and len({tuple(sorted(c.items())) for c in grid}) == 36
    assert grid[0] == {
        "seasonality_mode": "additive",
        "changepoint_prior_scale": 0.01,
        "seasonality_prior_scale": 0.05,
        "fourier_order": 5,
    }


def test_transform_por_perfil_desde_el_registry():
    count = ct.log1p_transform(_DISEASE, _COUNT)
    rate = ct.rate_log1p_transform(_DISEASE, _RATE)
    assert count.forward_steps == ("log1p",) and count.rate_scale is None
    assert rate.forward_steps == ("rate_per_exposure", "log1p")
    assert rate.inverse_steps == ("expm1", "rate_to_count")
    assert rate.rate_scale == 100_000.0 and rate.requires_exposure


def test_benchmark_sin_configuracion_congelada_falla_cerrado(tmp_path):
    cfg = copy.deepcopy(_CFG)
    cfg["engines"][_COUNT]["frozen"] = None
    sin_congelar = prophet_engine.ProphetProfileAdapter(_COUNT, cfg)
    with pytest.raises(ProphetEngineError, match="sin configuración congelada"):
        sin_congelar.run("benchmark", str(tmp_path))


def test_configuracion_congelada_es_una_combinacion_de_la_rejilla():
    # El benchmark usa lo que congeló el tuning; nunca reabre la rejilla.
    grid = build_grid(_CFG)
    for name in (_COUNT, _RATE):
        frozen = _CFG["engines"][name]["frozen"]
        assert frozen is not None and dict(frozen) in grid


def test_predictor_conteo_recupera_el_nivel():
    out = prophet_engine.make_predictor(_CFG["common"], _config())(_request(_serie(_N_TRAIN)))
    preds = np.array(list(out.predictions.values()))
    assert np.isfinite(preds).all() and (preds >= 0).all()
    assert 60.0 < preds.mean() < 160.0  # alrededor del nivel 100 de la serie sintética
    assert (
        out.diagnostics["fourier_order"] == 5 and out.diagnostics["seasonality_mode"] == "additive"
    )


def test_predictor_tasa_vuelve_a_casos_con_la_exposicion_del_periodo():
    valores = _serie(_N_TRAIN)
    conteo = prophet_engine.make_predictor(_CFG["common"], _config())(_request(valores, _COUNT))
    tasa = prophet_engine.make_predictor(_CFG["common"], _config())(_request(valores, _RATE))
    a = np.array(list(conteo.predictions.values()))
    b = np.array(list(tasa.predictions.values()))
    # Con exposición constante, tasa y conteo describen la misma serie salvo la escala del contrato.
    assert np.isfinite(b).all() and (b >= 0).all()
    assert np.allclose(a, b, rtol=0.05)


def test_el_motor_usa_ds_mmwr(monkeypatch):
    visto: dict[str, pd.DataFrame] = {}

    def fake(frame, future, config, common):
        visto["frame"], visto["future"] = frame, future
        return np.full(len(future), np.log1p(50.0))

    monkeypatch.setattr(prophet_engine, "_fit_forecast", fake)
    request = _request(_serie(_N_TRAIN))
    prophet_engine.make_predictor(_CFG["common"], _config())(request)
    esperado = [pd.Timestamp(ds_for(*p)) for p in sorted(request.train)]
    assert list(visto["frame"]["ds"]) == esperado
    assert list(visto["future"]["ds"]) == [pd.Timestamp(ds_for(*p)) for p in request.holdout]
    assert visto["frame"]["y"].iloc[0] == pytest.approx(
        np.log1p(sorted(request.train.items())[0][1])
    )


@pytest.mark.parametrize("valor", [-3.0, np.inf, np.nan])
def test_pronostico_inutilizable_falla_cerrado(monkeypatch, valor):
    monkeypatch.setattr(
        prophet_engine, "_fit_forecast", lambda f, fut, c, com: np.full(len(fut), valor)
    )
    with pytest.raises(ProphetEngineError):
        prophet_engine.make_predictor(_CFG["common"], _config())(_request(_serie(_N_TRAIN)))


def test_fallo_del_ajuste_se_propaga_sin_fallback(monkeypatch):
    def explota(frame, future, config, common):
        raise RuntimeError("stan no convergió")

    monkeypatch.setattr(prophet_engine, "_fit_forecast", explota)
    with pytest.raises(ProphetEngineError, match="ajuste Prophet fallido"):
        prophet_engine.make_predictor(_CFG["common"], _config())(_request(_serie(_N_TRAIN)))


def test_versiones_efectivas_en_los_params():
    ad: Any = adapters.get_adapter(_RATE)
    params = ad._params({})
    assert params["prophet_version"] and params["cmdstanpy_version"]
    assert params["transform"] == "rate_log1p" and params["growth"] == "linear"
