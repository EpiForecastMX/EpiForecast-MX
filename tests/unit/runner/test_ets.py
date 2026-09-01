"""F2/C3c — motor ETS: predictor exacto, transform por metadata, retry declarado y fail-closed."""

from __future__ import annotations

import pickle
from typing import Any

import numpy as np
import pytest
from scipy.optimize._lbfgsb_py import LbfgsInvHessProduct
from scipy.sparse.linalg import LinearOperator

from epiforecast.data.epi_calendar import shift
from epiforecast.data.epi_dataset_spec import SeriesKey
from epiforecast.runner import adapters
from epiforecast.runner import contracts as ct
from epiforecast.runner.engines import ets, harness
from epiforecast.runner.engines.ets import ENGINE, EtsFitError, load_ets_config, make_predictor

_DISEASE = "synthetic_disease"
_CFG = load_ets_config()
_N_TRAIN = 366  # 2014-W01..2020-W53, igual que el primer fold dev


def _periods(n: int, start: tuple[int, int] = (2014, 1)) -> list[tuple[int, int]]:
    out = [start]
    for _ in range(n - 1):
        out.append(shift(out[-1][0], out[-1][1], 1))
    return out


def _request(values, horizon: int = 52, transform=ct.log1p_transform) -> harness.SeriesRequest:
    periods = _periods(len(values))
    origin = periods[-1]
    holdout, cur = [], origin
    for _ in range(horizon):
        cur = shift(cur[0], cur[1], 1)
        holdout.append(cur)
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
    train = {p: float(v) for p, v in zip(periods, values, strict=True)}
    return harness.SeriesRequest(spec, train, tuple(holdout), origin)


def _predict(request: harness.SeriesRequest) -> harness.SeriesForecast:
    return make_predictor(_CFG)(request)


def test_adapter_registrado_con_ciclo_completo():
    ad = adapters.get_adapter(ENGINE)
    assert ad is not None
    assert ad.supports("benchmark") and ad.supports("refit") and ad.supports("forecast")
    assert ad.supports("tune") is False  # ETS no tunea: su variante se decide por convergencia


def test_config_declarativa():
    assert _CFG["engine"] == ENGINE and _CFG["target_transform"] == "log1p"
    assert _CFG["remove_bias"] is False and _CFG["optimized"] is True
    primary, retry = _CFG["variants"]
    assert (primary["trend"], primary["damped_trend"], primary["strict"]) == ("add", True, True)
    assert primary["seasonal"] == "add" and primary["seasonal_periods"] == 52
    assert (retry["trend"], retry["damped_trend"], retry["strict"]) == (None, False, False)
    assert _CFG["resource_limits"] == {"max_threads": 1}


def test_serie_constante_recupera_el_nivel_exacto():
    # log1p/expm1 exactos: una serie constante en 7 pronostica 7 en todo el horizonte.
    out = _predict(_request([7.0] * _N_TRAIN))
    preds = np.array(list(out.predictions.values()))
    assert np.allclose(preds, 7.0, rtol=0, atol=1e-6)
    assert out.diagnostics["variant"] == "primary" and out.n_fallback == 0


def test_serie_constante_cero_es_finita_no_negativa_y_estable():
    # Gate del contrato: cero constante NO puede tumbar el job ni producir negativos.
    out = _predict(_request([0.0] * _N_TRAIN))
    preds = np.array(list(out.predictions.values()))
    assert np.isfinite(preds).all() and (preds >= 0).all()
    assert np.allclose(preds, 0.0, rtol=0, atol=1e-9)


def test_convergence_warning_activa_el_retry_y_queda_registrado(monkeypatch):
    llamadas: list[str] = []

    def fake(y, horizon, variant, cfg):
        llamadas.append(variant.name)
        warns = ["ConvergenceWarning"] if variant.strict else []
        return np.full(horizon, np.log1p(3.0)), True, warns, -100.0

    monkeypatch.setattr(ets, "_fit_forecast", fake)
    out = _predict(_request([5.0] * _N_TRAIN))
    assert llamadas == ["primary", "retry"]  # el warning de la primaria fuerza el reintento
    assert out.diagnostics["variant"] == "retry" and out.diagnostics["n_attempts"] == 2
    assert out.diagnostics["primary_rejected"] == "ConvergenceWarning"
    assert np.allclose(list(out.predictions.values()), 3.0, rtol=0, atol=1e-9)


def test_no_convergencia_de_la_primaria_activa_el_retry(monkeypatch):
    def fake(y, horizon, variant, cfg):
        return np.full(horizon, np.log1p(2.0)), not variant.strict, [], -1.0

    monkeypatch.setattr(ets, "_fit_forecast", fake)
    out = _predict(_request([5.0] * _N_TRAIN))
    assert out.diagnostics["variant"] == "retry"
    assert out.diagnostics["primary_rejected"] == "no convergió"


def test_negativos_tras_la_inversa_invalidan_ambas_variantes(monkeypatch):
    # expm1 de un pronóstico negativo en espacio log → conteos negativos: rc≠0, nunca ceros.
    monkeypatch.setattr(
        ets, "_fit_forecast", lambda y, h, v, c: (np.full(h, -5.0), True, [], -1.0)
    )
    with pytest.raises(EtsFitError, match="ninguna variante"):
        _predict(_request([5.0] * _N_TRAIN))


def test_no_finitos_invalidan_el_ajuste(monkeypatch):
    monkeypatch.setattr(
        ets, "_fit_forecast", lambda y, h, v, c: (np.full(h, np.inf), True, [], -1.0)
    )
    with pytest.raises(EtsFitError, match="ninguna variante"):
        _predict(_request([5.0] * _N_TRAIN))


def test_transform_gobernada_por_metadata(monkeypatch):
    # El motor NO hardcodea log1p: con TransformContract identidad ajusta en espacio de conteos.
    espacios: list[float] = []

    def fake(y, horizon, variant, cfg):
        espacios.append(float(y[0]))
        return np.full(horizon, float(y[0])), True, [], -1.0

    monkeypatch.setattr(ets, "_fit_forecast", fake)
    log_out = _predict(_request([7.0] * _N_TRAIN))
    id_out = _predict(_request([7.0] * _N_TRAIN, transform=ct.identity_transform))
    assert espacios[0] == pytest.approx(np.log1p(7.0))  # log1p aplicado por el contrato
    assert espacios[-1] == 7.0  # identidad: sin transformar
    assert list(log_out.predictions.values())[0] == pytest.approx(7.0)  # expm1 invierte
    assert list(id_out.predictions.values())[0] == pytest.approx(7.0)


def test_hueco_en_el_train_falla_cerrado():
    request = _request([5.0] * _N_TRAIN)
    train = dict(request.train)
    train.pop((2016, 10))  # invariante compartido del harness: NUNCA se rellenan huecos
    with pytest.raises(harness.HarnessError, match="hueco en el train"):
        _predict(harness.SeriesRequest(request.spec, train, request.holdout, request.origin))


def test_train_corto_falla_cerrado():
    with pytest.raises(EtsFitError, match="estaciones"):
        _predict(_request([5.0] * 100))


def test_predictor_determinista():
    values = [10.0 + 3.0 * np.sin(2 * np.pi * i / 52) + 0.01 * i for i in range(_N_TRAIN)]
    a = _predict(_request(values)).predictions
    b = _predict(_request(values)).predictions
    assert a == b  # mismo train → mismas predicciones, bit a bit


def test_solo_usa_el_train_recibido():
    # Invariancia post-origen: el predictor no tiene acceso a nada posterior al origen.
    values = [10.0 + 3.0 * np.sin(2 * np.pi * i / 52) for i in range(_N_TRAIN)]
    request = _request(values)
    assert max(request.train) == request.origin
    out = _predict(request)
    assert set(out.predictions) == set(request.holdout)
    assert all(np.isfinite(v) and v >= 0 for v in out.predictions.values())


def test_params_del_adapter_incluyen_variantes_y_limites():
    ad: Any = adapters.get_adapter(ENGINE)
    assert ad._cfg["variants"] == _CFG["variants"]
    assert ad._cfg["resource_limits"]["max_threads"] == 1


def test_loader_compat_repara_solo_el_xp_ausente_de_scipy_legacy(monkeypatch):
    operator = LbfgsInvHessProduct(np.eye(2), np.eye(2))
    monkeypatch.setattr(
        LinearOperator,
        "__getstate__",
        lambda instance: {key: value for key, value in instance.__dict__.items() if key != "_xp"},
    )
    payload = pickle.dumps(operator, protocol=pickle.HIGHEST_PROTOCOL)

    with pytest.raises(KeyError, match="_xp"):
        pickle.loads(payload)  # noqa: S301 — control negativo del pickle fabricado

    restored = ets._load_statsmodels_state(payload)
    assert np.array_equal(restored @ np.array([1.0, 2.0]), np.array([1.0, 2.0]))


def test_loader_compat_no_oculta_otro_keyerror(monkeypatch):
    def falla(_data):
        raise KeyError("otra_clave")

    monkeypatch.setattr(pickle, "loads", falla)
    with pytest.raises(KeyError, match="otra_clave"):
        ets._load_statsmodels_state(b"estado")
