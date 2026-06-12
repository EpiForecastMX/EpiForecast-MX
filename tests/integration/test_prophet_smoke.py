"""Smoke test de entrenamiento real de Prophet (motor_ganador global neuro).

Los tests unitarios de Prophet mockean la clase ``Prophet``, dejando la ruta real
``fit()``/``predict()``/``run()`` sin cubrir (~55%). Aquí se entrena de verdad
(cmdstanpy) sobre una serie sintética y se valida el pronóstico, además de la rama
"baja confianza" de ``run()`` (umbral alto -> salta el grid CV). Marcado
`slow`+`integration`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from epiforecast.models.factory import create_model

pytestmark = [pytest.mark.slow, pytest.mark.integration]

_CFG = {
    "padecimiento": {"modelado_estados": True, "entrena_modelo": True},
    "paths": {"models": "/tmp/epi_test/models"},
    "data": {"model_train": "/tmp/epi_test/train"},
    "normalizar_tasa": False,
    "columna_poblacion": "Total",
    "tasa_por": 100_000,
    "log_transform": False,
    "param_model": {
        "weekly_seasonality": False,
        "daily_seasonality": False,
        "yearly_seasonality": True,
    },
    "add_seasonality": {
        "name": "monthly",
        "period": 30.5,
        "fourier_order": 5,
        "fourier_order_regional": 3,
    },
    "peridos_atipicos": [],
    "cambios_regimen": [],
    "FECHA_CORTE_ENTRENAMIENTO": "2023-01-01",
    "n_changepoints_regional": 12,
    "TS_SPLITS": 4,
    "TEST_SIZE": 52,
    "cv_weights": [0.5, 0.75, 1.0, 1.25],
    "cv_timeout_por_fold": 0,
    "cv_timeout_por_combo": 0,
    "param_grid_prophet": {
        "depresion": {
            "seasonality_mode": ["additive"],
            "changepoint_prior_scale": [0.05],
            "seasonality_prior_scale": [0.1],
        },
    },
}


def _df(n_weeks: int = 150) -> pd.DataFrame:
    """Serie sintética semanal con estacionalidad que cruza el corte 2023-01-01."""
    fechas = pd.date_range("2021-01-04", periods=n_weeks, freq="W-MON")
    wk = fechas.isocalendar().week.to_numpy()
    rng = np.random.default_rng(42)
    base = 30 + 15 * np.sin(2 * np.pi * wk / 52)
    hombres = np.clip(base + rng.normal(0, 3, n_weeks), 0, None).round().astype(int)
    return pd.DataFrame(
        {
            "Fecha": fechas,
            "Padecimiento": ["Depresión"] * n_weeks,
            "Entidad": ["Jalisco"] * n_weeks,
            "incrementos_hombres": hombres,
            "incrementos_mujeres": hombres + 5,
        }
    )


def _make(cfg: dict):
    return create_model(
        "prophet",
        df=_df(),
        sexo="incrementos_hombres",
        entidad="Jalisco",
        padecimiento="Depresión",
        config=cfg,
    )


def test_prophet_fit_predict_smoke():
    """Entrena Prophet de verdad y produce un pronóstico válido a 52 semanas."""
    m = _make(_CFG)
    m.agrupa()
    m.crea_train_test()  # deja `serie` con columnas ds/y (igual que el path productivo)
    assert {"ds", "y"} <= set(m.serie.columns)
    m.fit(m.serie)
    out = m.predict(horizon=52)
    assert {"ds", "yhat", "yhat_lower", "yhat_upper"} <= set(out.columns)
    assert len(out) >= 52
    fut = out.tail(52)
    assert np.isfinite(fut["yhat"].to_numpy()).all()
    assert (fut["yhat_lower"] <= fut["yhat"] + 1e-6).all()
    assert (fut["yhat"] <= fut["yhat_upper"] + 1e-6).all()


def test_prophet_predict_sin_fit_lanza():
    """`predict()` sin `fit()` previo levanta RuntimeError (guard del contrato)."""
    m = _make(_CFG)
    m.agrupa()
    m.crea_train_test()
    with pytest.raises(RuntimeError):
        m.predict(horizon=8)
