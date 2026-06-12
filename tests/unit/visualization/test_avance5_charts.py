"""Tests smoke + estructurales de los 6 builders de gráficos del Avance 5.

``avance5_charts.py`` (537 líneas) construye las figuras del reporte Avance 5 y
estaba excluido de la cobertura (omit). Estos tests fijan el comportamiento
(la figura se construye y tiene la estructura esperada) como red de seguridad
para el refactor de partición. Backend Agg (headless), sin pixel-compare.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from epiforecast.visualization import avance5_charts as ac
from epiforecast.visualization.comparison_config import MODEL_STYLES

_KEYS = list(MODEL_STYLES)  # prophet, deepar, ensemble, stacking
_LABELS = [MODEL_STYLES[k].label for k in _KEYS]


@pytest.fixture(autouse=True)
def _close_figs():
    yield
    plt.close("all")


def _serie_fc():
    ds = pd.date_range("2022-01-03", periods=60, freq="W-MON")
    wk = ds.isocalendar().week.to_numpy()
    y = 50 + 20 * np.sin(2 * np.pi * wk / 52)
    serie_real = pd.DataFrame({"ds": ds, "y": y})
    ds_fut = pd.date_range("2022-01-03", periods=68, freq="W-MON")
    yhat = 50 + 18 * np.sin(2 * np.pi * ds_fut.isocalendar().week.to_numpy() / 52)
    winner = pd.DataFrame(
        {"ds": ds_fut, "yhat": yhat, "yhat_lower": yhat - 6, "yhat_upper": yhat + 6}
    )
    prophet = pd.DataFrame({"ds": ds_fut, "yhat": yhat + 2})
    return serie_real, winner, prophet, ds[-1]


def _merged():
    rng = np.random.default_rng(3)
    rows = []
    for ent in ("Jalisco", "Oaxaca", "Sonora"):
        row = {"padecimiento": "Depresion", "Entidad": ent}
        for mk in _KEYS:
            row[f"rmse_{mk}"] = float(rng.uniform(3, 9))
            row[f"mae_{mk}"] = float(rng.uniform(2, 7))
            row[f"smape_{mk}"] = float(rng.uniform(10, 30))
            row[f"mase_{mk}"] = float(rng.uniform(0.5, 1.5))
        rows.append(row)
    return pd.DataFrame(rows)


def test_build_trend_prediction():
    serie_real, winner, prophet, cutoff = _serie_fc()
    fig = ac.build_trend_prediction(serie_real, winner, prophet, "Depresion", "stacking", cutoff)
    assert fig is not None
    assert len(fig.axes[0].lines) >= 3  # real + ganador + prophet


def test_build_residual_analysis_2x2():
    rng = np.random.default_rng(1)
    residuals = rng.normal(0, 5, 80)
    dates = pd.Series(pd.date_range("2022-01-03", periods=80, freq="W-MON"))
    fig = ac.build_residual_analysis(residuals, dates, "Stacking", "#1A237E", "Depresion")
    assert len(fig.axes) == 4


def test_build_feature_importance_2_paneles():
    fig = ac.build_feature_importance(
        np.array([0.4, 0.3, 0.2, 0.1]),
        ["lag1", "lag2", "roll4", "mes"],
        np.array([0.5, 0.3, 0.2]),
        ["Prophet", "ETS", "LGBM"],
    )
    assert len(fig.axes) == 2


def test_build_metric_bars_grid_y_tabla():
    fig = ac.build_metric_bars(_merged(), _KEYS, padecimiento="Depresion")
    assert fig is not None
    assert len(fig.axes) >= 4  # grilla 2x2 (+ tabla)


def test_build_error_boxplots():
    fig = ac.build_error_boxplots(_merged(), _KEYS)
    assert fig is not None
    assert len(fig.axes) >= 1


def test_build_win_rate_heatmap():
    rng = np.random.default_rng(2)
    win_df = pd.DataFrame({"Entidad": ["Jalisco", "Oaxaca", "Sonora"]})
    for lab in _LABELS:
        win_df[lab] = rng.uniform(0, 100, 3)
    fig = ac.build_win_rate_heatmap(win_df, "Depresion", _KEYS)
    assert fig is not None


def test_build_win_rate_heatmap_sin_datos():
    """Sin columnas de modelos válidas, devuelve una figura con 'Sin datos'."""
    fig = ac.build_win_rate_heatmap(pd.DataFrame({"Entidad": ["Jalisco"]}), "Depresion", _KEYS)
    assert fig is not None
    assert len(fig.axes) == 1
