"""F2/C3.4 — seasonal_naive_lag52: recuperación lag-52 exacta, recursión h>52, invariancia origen."""

from __future__ import annotations

from epiforecast.data.epi_calendar import shift, weeks_in_year
from epiforecast.runner import adapters
from epiforecast.runner.engines.seasonal_naive import ENGINE, predict_series


def _truth_map(years):
    return {(y, w): y * 1000 + w for y in years for w in range(1, weeks_in_year(y) + 1)}


def test_adapter_registrado():
    assert ENGINE in adapters.available_adapters()
    assert adapters.get_adapter(ENGINE) is not None


def test_recupera_lag52_exacto():
    # Fold dev 2021 (52 sem): cada predicción == valor real 52 semanas atrás (en train).
    tmap = _truth_map([2019, 2020, 2021])
    holdout = [(2021, w) for w in range(1, 53)]
    preds = predict_series(tmap, holdout)
    for y, w in holdout:
        src = shift(y, w, -52)
        assert src[0] < 2021  # el origen del salto está en el train
        assert preds[(y, w)] == tmap[src]  # recuperación exacta


def test_recursion_para_semana_53():
    # 2020 tiene 53 semanas: la semana 53 salta a (2020,1), que está en el holdout → recursivo.
    tmap = _truth_map([2018, 2019, 2020])
    holdout = [(2020, w) for w in range(1, 54)]
    preds = predict_series(tmap, holdout)
    assert shift(2020, 53, -52) == (2020, 1)  # el origen cae dentro del holdout
    assert preds[(2020, 53)] == preds[(2020, 1)]  # recursivo, no consulta el real posterior
    assert preds[(2020, 1)] == tmap[shift(2020, 1, -52)]  # (2020,1) sí viene del train


def test_invariancia_post_origen():
    # Alterar la verdad DENTRO del holdout no cambia ninguna predicción.
    holdout = [(2021, w) for w in range(1, 53)]
    base = _truth_map([2019, 2020, 2021])
    altered = dict(base)
    for y, w in holdout:
        altered[(y, w)] = -999  # basura en el holdout
    assert predict_series(base, holdout) == predict_series(altered, holdout)
