"""Tests del motor NB-GLM (Negative-Binomial GLM + Fourier + ENSO) para Dengue."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from epiforecast.models import create_model, list_models
from epiforecast.models.nbglm.model import NBGLMForecaster


def _serie(n: int = 200, amp: float = 50.0, base: float = 20.0) -> pd.DataFrame:
    """Serie sintética semanal con estacionalidad anual + ruido."""
    ds = pd.date_range("2019-01-07", periods=n, freq="W-MON")
    wk = ds.isocalendar().week.to_numpy()
    y = base + amp * np.clip(np.sin(2 * np.pi * (wk - 27) / 52), 0, None)
    rng = np.random.default_rng(0)
    y = np.clip(y + rng.normal(0, 5, n), 0, None).round()
    return pd.DataFrame({"ds": ds, "y": y})


def _fit_model(serie: pd.DataFrame, padecimiento: str = "Dengue") -> NBGLMForecaster:
    m = NBGLMForecaster(padecimiento=padecimiento)
    m.serie = serie
    m.fit(serie)
    return m


def test_registrado_en_factory():
    assert "nbglm" in list_models()
    assert isinstance(create_model("nbglm", padecimiento="Dengue"), NBGLMForecaster)


def test_fit_predict_incluye_insample_y_futuro():
    serie = _serie()
    m = _fit_model(serie)
    out = m.predict(52)
    # in-sample (len serie) + 52 futuro
    assert len(out) == len(serie) + 52
    assert {"ds", "yhat", "yhat_lower", "yhat_upper"} <= set(out.columns)
    assert (out["yhat"] >= 0).all()
    assert (out["yhat_lower"] <= out["yhat"]).all()
    assert (out["yhat"] <= out["yhat_upper"]).all()


def test_serie_cero_fallback_constante():
    """Series sin transmisión (CDMX/Tlaxcala): no revienta, pronostica ~0."""
    ds = pd.date_range("2019-01-07", periods=120, freq="W-MON")
    serie = pd.DataFrame({"ds": ds, "y": np.zeros(len(ds))})
    m = _fit_model(serie)
    out = m.predict(52)
    assert m._res is None  # cayó al fallback
    assert float(out["yhat"].sum()) == 0.0


def test_enso_cohort_gated():
    """El regresor ENSO solo se activa para la cohorte de conteos (Dengue)."""
    assert NBGLMForecaster(padecimiento="Dengue").enso_regressor is True
    assert NBGLMForecaster(padecimiento="Depresion").enso_regressor is False


def test_save_load_roundtrip(tmp_path):
    serie = _serie()
    m = _fit_model(serie)
    pred1 = m.predict(52)
    p = tmp_path / "nbglm.pkl"
    m.save(p)
    m2 = NBGLMForecaster(padecimiento="Dengue")
    m2.load(p)
    pred2 = m2.predict(52)
    np.testing.assert_allclose(pred1["yhat"].to_numpy(), pred2["yhat"].to_numpy(), rtol=1e-9)


def test_date_fromisocalendar_grid():
    """El futuro arranca en el lunes ISO siguiente a la última semana real."""
    serie = _serie()
    m = _fit_model(serie)
    out = m.predict(4)
    fut = out.tail(4)
    assert (fut["ds"].dt.weekday == 0).all()  # lunes
    assert fut["ds"].iloc[0] > pd.Timestamp(serie["ds"].iloc[-1])


def test_default_preserva_comportamiento_productivo():
    """Los nuevos parámetros tienen defaults que NO alteran el path productivo."""
    serie = _serie()
    m = _fit_model(serie)
    base = m.predict(52)
    explicito = m.predict(52, freeze_trend=False, future_oni=None, trend_anchor_weeks=None)
    np.testing.assert_allclose(base["yhat"].to_numpy(), explicito["yhat"].to_numpy(), rtol=1e-12)


def test_freeze_trend_modifica_futuro_y_es_valido():
    """freeze_trend congela la tendencia: cambia el tramo futuro pero deja un pronóstico válido.

    No asumimos el signo del coeficiente de tendencia (en la serie sintética es arbitrario);
    solo que congelar la deriva produce un futuro DISTINTO, finito y no negativo.
    """
    serie = _serie(n=260, amp=80.0, base=30.0)
    m = _fit_model(serie)
    h = 156
    libre = m.predict(h).tail(h)["yhat"].to_numpy()
    congelado = m.predict(h, freeze_trend=True).tail(h)["yhat"].to_numpy()
    assert not np.allclose(libre, congelado)  # la tendencia sí mueve el horizonte lejano
    assert np.isfinite(congelado).all()
    assert (congelado >= 0).all()
    # el in-sample no cambia (freeze solo afecta el futuro)
    n0 = len(serie)
    in_libre = m.predict(h).head(n0)["yhat"].to_numpy()
    in_congelado = m.predict(h, freeze_trend=True).head(n0)["yhat"].to_numpy()
    np.testing.assert_allclose(in_libre, in_congelado, rtol=1e-12)


def test_trend_anchor_en_n0_equivale_a_freeze():
    """trend_anchor_weeks=n0 es idéntico a freeze_trend=True (anchor default == n0)."""
    serie = _serie(n=260, amp=80.0, base=30.0)
    m = _fit_model(serie)
    n0 = len(serie)
    h = 104
    congelado = m.predict(h, freeze_trend=True)["yhat"].to_numpy()
    anclado_n0 = m.predict(h, trend_anchor_weeks=float(n0))["yhat"].to_numpy()
    np.testing.assert_allclose(congelado, anclado_n0, rtol=1e-12)
    # anclar a otra semana sí cambia el futuro (y respeta freeze implícito)
    anclado_bajo = m.predict(h, trend_anchor_weeks=20.0).tail(h)["yhat"].to_numpy()
    assert not np.allclose(congelado[-h:], anclado_bajo)
    assert np.isfinite(anclado_bajo).all()
    assert (anclado_bajo >= 0).all()


def test_future_oni_inyecta_escenario():
    """future_oni reemplaza la persistencia ONI por el escenario provisto (cambia el futuro)."""
    serie = _serie()
    m = _fit_model(serie)
    h = 52
    base = m.predict(h).tail(h)["yhat"].to_numpy()
    nino_fuerte = m.predict(h, future_oni=np.full(h, 2.5)).tail(h)["yhat"].to_numpy()
    assert not np.allclose(base, nino_fuerte)
    assert np.isfinite(nino_fuerte).all()
    assert (nino_fuerte >= 0).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
