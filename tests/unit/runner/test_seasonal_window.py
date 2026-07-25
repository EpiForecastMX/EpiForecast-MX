"""F2/C3b — ventanas estacionales: media/mediana 3/5 exactas, W53 parcial/fallback, invariancia."""

from __future__ import annotations

import pytest

from epiforecast.data.epi_calendar import shift
from epiforecast.data.epi_dataset_spec import SeriesKey
from epiforecast.runner import adapters
from epiforecast.runner import contracts as ct
from epiforecast.runner.engines import harness
from epiforecast.runner.engines.seasonal_window import (
    WindowConfigError,
    _as_predict_fn,
    load_window_config,
    make_predictor,
)

_NAMES = {"seasonal_mean_3y", "seasonal_median_3y", "seasonal_mean_5y", "seasonal_median_5y"}


def _spec_for(engine: str) -> ct.TrainingSpec:
    return ct.TrainingSpec(
        key=SeriesKey("synthetic_disease", "estado", "05", "hombres"),
        engine=engine,
        dataset_digest="d" * 64,
        policy_name="rolling_cv_v1",
        policy_digest="p" * 64,
        fold_id="development_2024",
        seed=1,
        horizon=1,
        transform=ct.identity_transform("synthetic_disease", engine),
    )


def test_config_y_registro():
    cfg = load_window_config()
    assert set(cfg) == _NAMES
    for name in _NAMES:
        ad = adapters.get_adapter(name)
        assert ad is not None
        assert ad.supports("benchmark") and ad.supports("refit") and ad.supports("forecast")


def test_mean_3y_exacto():
    tmap = {(2021, 1): 10.0, (2022, 1): 20.0, (2023, 1): 30.0}
    preds, nfb = make_predictor(3, "mean", 1)(tmap, [(2024, 1)])
    assert preds[(2024, 1)] == 20.0 and nfb == 0


def test_median_3y_exacto():
    tmap = {(2021, 1): 10.0, (2022, 1): 100.0, (2023, 1): 30.0}
    preds, _ = make_predictor(3, "median", 1)(tmap, [(2024, 1)])
    assert preds[(2024, 1)] == 30.0  # mediana de [10, 100, 30]


def test_mean_5y_exacto():
    tmap = {(2019 + i, 5): float(i) for i in range(5)}  # (2019,5)=0 … (2023,5)=4
    preds, _ = make_predictor(5, "mean", 1)(tmap, [(2024, 5)])
    assert preds[(2024, 5)] == 2.0


def test_solo_periodos_de_la_ventana_declarada():
    # (2020,1) queda FUERA de la ventana de 3 años para (2024,1); no se usa.
    tmap = {(2022, 1): 20.0, (2023, 1): 40.0, (2020, 1): 999.0}
    preds, nfb = make_predictor(3, "mean", 1)(tmap, [(2024, 1)])
    assert preds[(2024, 1)] == 30.0 and nfb == 0  # media de (20, 40); ignora 2020


def test_w53_historial_parcial():
    # Ventana 5y de (2025,53): solo 2020 tuvo W53 → 1 valor >= min_obs=1.
    tmap = {(2020, 53): 42.0}
    preds, nfb = make_predictor(5, "mean", 1)(tmap, [(2025, 53)])
    assert preds[(2025, 53)] == 42.0 and nfb == 0


def test_w53_sin_historial_usa_fallback():
    # Ventana vacía → fallback seasonal_naive_lag52 recursivo, registrado.
    src = shift(2025, 53, -52)
    preds, nfb = make_predictor(5, "mean", 1)({src: 9.0}, [(2025, 53)])
    assert preds[(2025, 53)] == 9.0 and nfb == 1


def test_min_obs_fuerza_fallback():
    src = shift(2024, 1, -52)
    tmap = {(2023, 1): 5.0, src: 99.0}  # 1 valor en ventana, pero min_obs=2 → fallback
    preds, nfb = make_predictor(3, "mean", 2)(tmap, [(2024, 1)])
    assert preds[(2024, 1)] == 99.0 and nfb == 1


def test_invariancia_post_origen():
    holdout = [(2024, w) for w in range(1, 53)]
    base = {(y, w): float(y * 100 + w) for y in range(2019, 2024) for w in range(1, 53)}
    altered = dict(base)
    for k in holdout:
        altered[k] = -999.0
    predict = make_predictor(5, "mean", 1)
    assert predict(base, holdout)[0] == predict(altered, holdout)[0]


def test_wrapper_del_harness_preserva_preds_y_fallback():
    # El adapter al contrato PredictFn no altera las predicciones ni el conteo de fallback.
    window = make_predictor(3, "mean", 1)
    train = {(2021, 1): 10.0, (2022, 1): 20.0, (2023, 1): 30.0}
    preds, nfb = window(train, [(2024, 1)])
    request = harness.SeriesRequest(
        spec=_spec_for("seasonal_mean_3y"), train=train, holdout=((2024, 1),), origin=(2023, 52)
    )
    out = _as_predict_fn(window)(request)
    assert out.predictions == preds and out.n_fallback == nfb and out.diagnostics == {}


def test_estadistico_invalido_levanta():
    with pytest.raises(WindowConfigError):
        make_predictor(3, "moda", 1)
