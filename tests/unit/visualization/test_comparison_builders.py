"""Tests smoke + estructurales de los builders de comparación de modelos.

``comparison_builders.py`` (728 líneas) construye las figuras de comparación
multi-modelo y estaba al 0% de cobertura. Estos tests fijan el comportamiento
(la figura se construye y tiene la estructura esperada: nº de ejes, líneas,
barras) SIN comparar pixeles, para servir de red de seguridad ante el refactor
de partición del módulo. Backend Agg (headless, en memoria).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from epiforecast.visualization import comparison_builders as cb
from epiforecast.visualization.comparison_config import MODEL_STYLES

_MODELS = list(MODEL_STYLES)  # prophet, deepar, ensemble, stacking


def _inputs(*, with_metrics: bool = True, modelos: list[str] | None = None):
    """Construye (serie_real, target_y, predictions, pad, ent, modo) sintéticos."""
    modelos = modelos if modelos is not None else _MODELS
    n_hist = 60
    ds_hist = pd.date_range("2022-01-03", periods=n_hist, freq="W-MON")
    wk = ds_hist.isocalendar().week.to_numpy()
    rng = np.random.default_rng(7)
    y = 50 + 20 * np.sin(2 * np.pi * wk / 52) + rng.normal(0, 4, n_hist)
    serie_real = pd.DataFrame({"ds": ds_hist, "Total": 1_000_000.0}).reset_index(drop=True)
    target_y = pd.Series(np.clip(y, 0, None).round(), name="y")

    ds_full = pd.date_range("2022-01-03", periods=n_hist + 8, freq="W-MON")  # +8 futuro
    predictions: dict[str, pd.DataFrame] = {}
    for i, key in enumerate(modelos):
        wk2 = ds_full.isocalendar().week.to_numpy()
        yhat = 50 + 20 * np.sin(2 * np.pi * wk2 / 52) + (i + 1) * 2.0  # residual != 0
        df = pd.DataFrame({"ds": ds_full, "yhat": yhat})
        if with_metrics:
            df["smape_usado"] = 12.0 + i
            df["mase_usado"] = 0.8 + 0.05 * i
            df["rmse_usado"] = 5.0 + i
            df["mae_usado"] = 4.0 + i
            df["mape_usado"] = 11.0 + i
        predictions[key] = df
    return serie_real, target_y, predictions, "Depresion", "Jalisco", "General"


@pytest.fixture(autouse=True)
def _close_figs():
    yield
    plt.close("all")


def test_build_small_multiples_grid_2x2():
    fig = cb.build_small_multiples(*_inputs())
    assert fig is not None
    assert len(fig.axes) == 4  # grilla 2x2, un panel por motor


def test_build_overlay_traza_real_y_modelos():
    serie_real, target_y, predictions, pad, ent, modo = _inputs()
    fig = cb.build_overlay(serie_real, target_y, predictions, pad, ent, modo)
    assert fig is not None
    ax = fig.axes[0]
    # 1 línea de historial real + 1 por cada motor presente
    assert len(ax.lines) >= 1 + len(_MODELS)


def test_build_metrics_bars_barras_y_tabla():
    fig = cb.build_metrics_bars(*_inputs(with_metrics=True))
    assert fig is not None
    assert len(fig.axes) >= 2  # eje de barras + eje de tabla
    ax_bar = fig.axes[0]
    # 4 motores x 3 métricas (RMSE/MAE/SMAPE) = 12 barras
    assert len(ax_bar.patches) == len(_MODELS) * 3


def test_build_metrics_bars_sin_metricas_devuelve_none():
    """Sin columnas *_usado no hay métricas CV -> el builder devuelve None."""
    fig = cb.build_metrics_bars(*_inputs(with_metrics=False))
    assert fig is None


def test_build_residuals_grid_2x2():
    fig = cb.build_residuals(*_inputs())
    assert fig is not None
    assert len(fig.axes) == 4


def test_builders_con_modelo_faltante():
    """Faltando motores (solo 2 de 4), las figuras siguen construyéndose."""
    args = _inputs(modelos=["prophet", "deepar"])
    assert len(cb.build_small_multiples(*args).axes) == 4  # grilla fija
    assert cb.build_overlay(*args) is not None
    assert cb.build_residuals(*args) is not None
