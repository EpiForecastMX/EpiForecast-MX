"""Tests del guard de envolvente estacional (forecast_guards)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from epiforecast.models.forecast_guards import clamp_seasonal_envelope


def _history() -> pd.DataFrame:
    # Dos años de fechas semanales con un máximo histórico conocido por semana del año.
    ds = pd.date_range("2023-01-02", periods=104, freq="W-MON")
    # y = patrón estacional: bajo al inicio del año, alto a mitad.
    woy = ds.isocalendar().week.to_numpy()
    y = np.where(woy >= 27, 500.0, 20.0)
    return pd.DataFrame({"ds": ds, "y": y})


def test_clamp_recorta_overshoot_por_semana():
    """Un yhat muy por encima del máximo histórico de esa semana se acota a max*1.5."""
    hist = _history()
    # Pronóstico en una semana de temporada baja (woy 3): histórico max 20 → techo 30.
    fut = pd.DataFrame({"ds": pd.to_datetime(["2026-01-19"]), "yhat": [2000.0]})
    out = clamp_seasonal_envelope(fut, hist, factor=1.5)
    assert out["yhat"].iloc[0] == 30.0  # 20 * 1.5


def test_clamp_no_toca_valores_plausibles():
    """Un yhat por debajo del techo estacional no se modifica."""
    hist = _history()
    fut = pd.DataFrame({"ds": pd.to_datetime(["2026-08-03"]), "yhat": [400.0]})  # woy ~32
    out = clamp_seasonal_envelope(fut, hist, factor=1.5)
    assert out["yhat"].iloc[0] == 400.0  # techo 750; 400 < 750 → sin cambio


def test_clamp_preserva_nan():
    hist = _history()
    fut = pd.DataFrame({"ds": pd.to_datetime(["2026-01-19"]), "yhat": [np.nan]})
    out = clamp_seasonal_envelope(fut, hist, factor=1.5)
    assert np.isnan(out["yhat"].iloc[0])


def test_clamp_noop_con_history_vacia():
    fut = pd.DataFrame({"ds": pd.to_datetime(["2026-01-19"]), "yhat": [2000.0]})
    out = clamp_seasonal_envelope(fut, pd.DataFrame(columns=["ds", "y"]))
    assert out["yhat"].iloc[0] == 2000.0


def test_clamp_noop_sin_columna_y():
    hist = pd.DataFrame({"ds": pd.date_range("2023-01-02", periods=10, freq="W-MON")})
    fut = pd.DataFrame({"ds": pd.to_datetime(["2026-01-19"]), "yhat": [2000.0]})
    out = clamp_seasonal_envelope(fut, hist)
    assert out["yhat"].iloc[0] == 2000.0


def test_clamp_fallback_semana_ausente_usa_global():
    """Una semana del año sin histórico cae al máximo global * factor."""
    # Histórico solo de semanas 1-5; pronóstico en semana 40 → fallback global (max 20 → 30).
    ds = pd.date_range("2023-01-02", periods=5, freq="W-MON")
    hist = pd.DataFrame({"ds": ds, "y": [10.0, 20.0, 15.0, 12.0, 8.0]})
    fut = pd.DataFrame({"ds": pd.to_datetime(["2026-10-05"]), "yhat": [999.0]})
    out = clamp_seasonal_envelope(fut, hist, factor=1.5)
    assert out["yhat"].iloc[0] == 30.0  # global max 20 * 1.5


def test_clamp_no_muta_el_original():
    hist = _history()
    fut = pd.DataFrame({"ds": pd.to_datetime(["2026-01-19"]), "yhat": [2000.0]})
    clamp_seasonal_envelope(fut, hist)
    assert fut["yhat"].iloc[0] == 2000.0  # el input no cambia
