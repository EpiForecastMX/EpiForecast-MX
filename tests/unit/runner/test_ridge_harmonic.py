"""F2/C3d — Ridge armónico: recuperación exacta, split interno causal, desempate y fail-closed."""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np
import pytest

from epiforecast.data.epi_calendar import ds_for, shift
from epiforecast.data.epi_dataset_spec import SeriesKey
from epiforecast.runner import adapters
from epiforecast.runner import contracts as ct
from epiforecast.runner.engines import harness, ridge_harmonic
from epiforecast.runner.engines.ridge_harmonic import (
    ENGINE,
    RidgeFitError,
    load_ridge_config,
    make_predictor,
)

_DISEASE = "synthetic_disease"
_CFG = load_ridge_config()
_N_TRAIN = 366  # 2014-W01..2020-W53, igual que el primer fold dev
_HORIZON = 52


def _periods(n: int, start: tuple[int, int] = (2014, 1)) -> list[tuple[int, int]]:
    out = [start]
    for _ in range(n - 1):
        out.append(shift(out[-1][0], out[-1][1], 1))
    return out


def _request(values, horizon: int = _HORIZON, transform=ct.log1p_transform, skip: int = 0):
    todos = _periods(len(values) + skip + horizon)
    train_p = todos[skip : skip + len(values)]
    holdout = todos[skip + len(values) : skip + len(values) + horizon]
    spec = ct.TrainingSpec(
        key=SeriesKey(_DISEASE, "estado", "05", "hombres"),
        engine=ENGINE,
        dataset_digest="d" * 64,
        policy_name="rolling_cv_v1",
        policy_digest="p" * 64,
        fold_id="development_2021",
        seed=20260724,
        horizon=horizon,
        transform=transform(_DISEASE, ENGINE),
    )
    train = {p: float(v) for p, v in zip(train_p, values, strict=True)}
    return harness.SeriesRequest(spec, train, tuple(holdout), train_p[-1])


def _predict(request: harness.SeriesRequest) -> harness.SeriesForecast:
    return make_predictor(_CFG)(request)


def _sinusoide(n: int, amplitud: float = 0.30, nivel: float = 100.0, skip: int = 0):
    """Serie exactamente representable en log1p por un armónico anual de orden 1."""
    days = np.array([ds_for(*p).toordinal() for p in _periods(n + skip)[skip:]], dtype=float)
    return np.expm1(np.log1p(nivel) + amplitud * np.sin(2 * np.pi * days / 365.25))


def test_adapter_registrado_con_ciclo_completo():
    ad = adapters.get_adapter(ENGINE)
    assert ad is not None
    assert ad.supports("benchmark") and ad.supports("refit") and ad.supports("forecast")
    assert ad.supports("tune") is False  # la selección de Ridge es interna, no por rejilla externa


def test_config_declarativa():
    assert _CFG["engine"] == ENGINE and _CFG["solver"] == "svd"
    assert _CFG["target_transform"] == "log1p" and _CFG["fit_intercept"] is True
    assert _CFG["fourier_orders"] == [2, 4, 6] and _CFG["alphas"] == [0.1, 1.0, 10.0]
    assert _CFG["inner_validation_weeks"] == 52 and _CFG["selection_metric"] == "smape"
    assert _CFG["tie_break"] == ["min_fourier_order", "max_alpha"]
    assert _CFG["seasonal_period_days"] == 365.25 and _CFG["resource_limits"] == {"max_threads": 1}


def test_recupera_una_sinusoide_sintetica():
    valores = _sinusoide(_N_TRAIN + _HORIZON)
    out = _predict(_request(valores[:_N_TRAIN]))
    pred = np.array(list(out.predictions.values()))
    rel = np.abs(pred - valores[_N_TRAIN:]) / valores[_N_TRAIN:]
    assert rel.max() < 0.005  # < 0.5% de error relativo en las 52 semanas OOS
    assert out.diagnostics["fourier_order"] == 2  # el orden mínimo ya contiene el armónico anual
    assert out.diagnostics["n_candidates_valid"] == 9


def test_serie_constante_cero_y_desempate_declarado():
    # Todos los candidatos empatan en sMAPE 0 → desempate: menor orden, luego mayor alpha.
    out = _predict(_request([0.0] * _N_TRAIN))
    preds = np.array(list(out.predictions.values()))
    assert np.isfinite(preds).all() and (preds >= 0).all()
    assert np.allclose(preds, 0.0, rtol=0, atol=1e-12)
    assert out.diagnostics["inner_smape"] == 0.0
    assert out.diagnostics["fourier_order"] == 2 and out.diagnostics["alpha"] == 10.0


def test_features_usan_fechas_mmwr_no_iso():
    # ds_for(2015,1) = 2015-01-05, que en ISO es la semana 2: el diseño no puede venir de ISO.
    assert ds_for(2015, 1) == dt.date(2015, 1, 5)
    assert ds_for(2015, 1).isocalendar()[:2] == (2015, 2)
    assert dt.date.fromisocalendar(2015, 1, 1) == dt.date(2014, 12, 29)
    days = ridge_harmonic._days([(2015, 1), (2020, 53)])
    assert list(days) == [ds_for(2015, 1).toordinal(), ds_for(2020, 53).toordinal()]


def test_split_interno_son_las_ultimas_52_del_train():
    out = _predict(_request(_sinusoide(_N_TRAIN)))
    assert out.diagnostics["n_inner_validation"] == 52
    assert out.diagnostics["n_inner_train"] == _N_TRAIN - 52
    assert out.diagnostics["n_candidates"] == 9


def test_el_holdout_no_altera_la_seleccion():
    # Mismo train, holdout de otra longitud: hiperparámetros y ajuste exterior idénticos.
    valores = _sinusoide(_N_TRAIN)
    a = _predict(_request(valores, horizon=52)).diagnostics
    b = _predict(_request(valores, horizon=13)).diagnostics
    claves = ("fourier_order", "alpha", "inner_smape", "coef_norm", "intercept")
    assert {k: a[k] for k in claves} == {k: b[k] for k in claves}


def test_cambiar_el_inner_validation_puede_cambiar_los_hiperparametros():
    # La selección SÍ depende de las últimas 52 semanas del train (y de nada posterior al origen).
    base = list(_sinusoide(_N_TRAIN))
    perturbado = list(base)
    for i in range(_N_TRAIN - 52, _N_TRAIN):
        perturbado[i] = base[i] * 3.0
    a = _predict(_request(base)).diagnostics
    b = _predict(_request(perturbado)).diagnostics
    assert a["inner_smape"] != b["inner_smape"]


def test_predictor_determinista():
    valores = _sinusoide(_N_TRAIN)
    a = _predict(_request(valores))
    b = _predict(_request(valores))
    assert a.predictions == b.predictions and a.diagnostics == b.diagnostics


def test_sin_candidatos_validos_falla_cerrado(monkeypatch):
    # expm1 de un pronóstico enorme desborda → ningún candidato utilizable → rc≠0, sin recortar.
    monkeypatch.setattr(
        ridge_harmonic,
        "_fit_predict",
        lambda df, yf, dt_, cand, cfg: (np.full(len(dt_), 1e6), 0.0, 0.0),
    )
    with pytest.raises(RidgeFitError, match="ningún candidato"):
        _predict(_request(_sinusoide(_N_TRAIN)))


def test_refit_inutilizable_falla_cerrado(monkeypatch):
    real = ridge_harmonic._to_counts
    estado = {"n": 0}

    def contado(transform, values):
        estado["n"] += 1
        return None if estado["n"] > 9 else real(transform, values)  # falla solo el refit

    monkeypatch.setattr(ridge_harmonic, "_to_counts", contado)
    with pytest.raises(RidgeFitError, match="refit"):
        _predict(_request(_sinusoide(_N_TRAIN)))


def test_candidatos_invalidos_se_descartan_sin_recortar(monkeypatch):
    real = ridge_harmonic._fit_predict

    def sesgado(days_fit, y_fit, days_target, cand, cfg):
        if cand.fourier_order == 2:  # invalida los 3 candidatos de orden 2
            return np.full(len(days_target), 1e6), 0.0, 0.0
        return real(days_fit, y_fit, days_target, cand, cfg)

    monkeypatch.setattr(ridge_harmonic, "_fit_predict", sesgado)
    out = _predict(_request(_sinusoide(_N_TRAIN)))
    assert out.diagnostics["n_candidates_valid"] == 6
    assert out.diagnostics["fourier_order"] in (4, 6)


def test_inner_train_corto_falla_cerrado():
    with pytest.raises(RidgeFitError, match="inner-train"):
        _predict(_request(_sinusoide(150)))  # 150-52 = 98 < min_inner_train_weeks


def test_hueco_en_el_train_falla_cerrado():
    request = _request(_sinusoide(_N_TRAIN))
    train = dict(request.train)
    train.pop((2016, 10))
    with pytest.raises(harness.HarnessError, match="hueco en el train"):
        _predict(harness.SeriesRequest(request.spec, train, request.holdout, request.origin))


def test_transform_gobernada_por_metadata():
    # Con contrato identidad el ajuste ocurre en conteos: el intercepto vive en esa escala.
    log_out = _predict(_request([7.0] * _N_TRAIN))
    id_out = _predict(_request([7.0] * _N_TRAIN, transform=ct.identity_transform))
    assert log_out.diagnostics["intercept"] == pytest.approx(np.log1p(7.0), abs=1e-6)
    assert id_out.diagnostics["intercept"] == pytest.approx(7.0, abs=1e-6)
    assert list(log_out.predictions.values())[0] == pytest.approx(7.0, abs=1e-6)
    assert list(id_out.predictions.values())[0] == pytest.approx(7.0, abs=1e-6)


def test_params_del_adapter_declarados():
    ad: Any = adapters.get_adapter(ENGINE)
    assert ad._cfg["fourier_orders"] == _CFG["fourier_orders"]
    assert ad._cfg["resource_limits"]["max_threads"] == 1
