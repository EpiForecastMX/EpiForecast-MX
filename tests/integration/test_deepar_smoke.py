"""Smoke test de entrenamiento real de DeepAR (motor productivo).

Antes de esto, ninguna prueba ejercitaba la ruta `fit()`/`predict()` de DeepAR
(cobertura ~21%): los tests existentes solo cubren la config cohort-aware y el CV.
Aquí se entrena de verdad (1 época, serie sintética corta, CPU) y se valida la
forma del pronóstico, la no-negatividad y el roundtrip save/load. Marcado
`slow`+`integration` para no frenar la suite rápida.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from epiforecast.models.factory import create_model

pytestmark = [pytest.mark.slow, pytest.mark.integration]

_CFG = {
    "normalizar_tasa": False,  # evita necesitar población
    "deepar": {
        "epochs": 1,
        "context_length": 16,
        "prediction_length": 8,
        "num_batches_per_epoch": 1,
        "num_layers": 1,
        "num_cells": 8,
        "batch_size": 8,
        "num_samples": 20,
        "freq": "W-MON",
        "early_stopping_patience": 1,
        "multi_series": False,
    },
}


def _serie_df(n: int = 180) -> pd.DataFrame:
    """Serie sintética semanal de conteos (columna `general`) con estacionalidad."""
    fechas = pd.date_range("2019-01-07", periods=n, freq="W-MON")
    wk = fechas.isocalendar().week.to_numpy()
    base = 40 + 25 * np.clip(np.sin(2 * np.pi * (wk - 26) / 52), 0, None)
    rng = np.random.default_rng(0)
    general = np.clip(base + rng.normal(0, 4, n), 0, None).round()
    return pd.DataFrame({"Fecha": fechas, "general": general})


def _build_and_fit():
    m = create_model(
        "deepar",
        df=_serie_df(),
        sexo="general",
        entidad="Jalisco",  # entidad != None -> single-series
        padecimiento="Depresión",
        config=_CFG,
    )
    assert m._is_multi_series is False
    m.agrupa()
    assert not m.serie.empty
    m.fit(m.serie)
    return m


def test_deepar_fit_predict_smoke():
    """Entrena 1 época y produce un pronóstico válido a 8 semanas."""
    m = _build_and_fit()
    out = m.predict(horizon=8)
    assert isinstance(out, pd.DataFrame)
    assert "yhat" in out.columns
    assert len(out) >= 8
    fut = out.tail(8)
    assert np.isfinite(fut["yhat"].to_numpy()).all()
    assert (fut["yhat"] >= 0).all()  # nonnegative_pred_samples=True
    if {"yhat_lower", "yhat_upper"} <= set(out.columns):
        assert (fut["yhat_lower"] <= fut["yhat"] + 1e-6).all()
        assert (fut["yhat"] <= fut["yhat_upper"] + 1e-6).all()


def test_deepar_save_load_roundtrip(tmp_path):
    """El predictor entrenado se serializa y recarga produciendo salida válida."""
    m = _build_and_fit()
    p = tmp_path / "deepar.pkl"
    m.save(p)
    assert p.exists()

    m2 = create_model(
        "deepar",
        df=_serie_df(),
        sexo="general",
        entidad="Jalisco",
        padecimiento="Depresión",
        config=_CFG,
    )
    m2.agrupa()
    m2.load(p)
    out = m2.predict(horizon=8)
    assert len(out) >= 8
    fut = out.tail(8)
    assert np.isfinite(fut["yhat"].to_numpy()).all()
    assert (fut["yhat"] >= 0).all()
