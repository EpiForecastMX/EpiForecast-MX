"""Prophet y NB-GLM pronostican desde disco sin ``self.serie``: su corte debe seguir conocido.

Sin él, ``ForecastModelLoader._sella_procedencia`` no sella fase, adelanto ni intervalo
(INCIDENTE_02 de la liberación W37: 234,099 filas de Prophet sin procedencia).
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from epiforecast.models.nbglm.model import NBGLMForecaster
from epiforecast.models.prediction import ForecastModelLoader
from epiforecast.models.prophet.model import ProphetForecaster

pytestmark = pytest.mark.unit

CORTE = pd.Timestamp("2026-06-22")


def _marco() -> pd.DataFrame:
    ds = pd.date_range("2026-06-15", periods=4, freq="7D")
    return pd.DataFrame(
        {
            "ds": ds,
            "yhat": [1.0, 2.0, 3.0, 4.0],
            "yhat_lower": [0.5, 1.5, 2.5, 3.5],
            "yhat_upper": [1.5, 2.5, 3.5, 4.5],
        }
    )


def _loader(motor: object) -> ForecastModelLoader:
    loader = ForecastModelLoader.__new__(ForecastModelLoader)
    loader.forecaster = motor  # type: ignore[attr-defined]
    return loader


def _prophet_cargado() -> ProphetForecaster:
    motor = ProphetForecaster.__new__(ProphetForecaster)
    motor.serie = pd.DataFrame()  # tras load(): sin serie
    motor._model = SimpleNamespace(
        history=pd.DataFrame({"ds": pd.date_range("2026-05-25", CORTE, freq="7D")}),
        interval_width=0.8,
    )
    return motor


def _nbglm_cargado(con_ajuste: bool = True) -> NBGLMForecaster:
    motor = NBGLMForecaster.__new__(NBGLMForecaster)
    motor.serie = pd.DataFrame()
    motor._last_ds = CORTE
    motor._res = object() if con_ajuste else None
    return motor


def test_prophet_tras_load_declara_su_corte_desde_history() -> None:
    assert _prophet_cargado().ultimo_ds_ajustado == CORTE


def test_prophet_tras_load_sella_fase_e_intervalo() -> None:
    out = _loader(_prophet_cargado())._sella_procedencia(_marco())
    assert list(out["fase_modelo"]) == ["ajuste", "ajuste", "pronostico", "pronostico"]
    assert out["intervalo_disponible"].all()
    assert set(out["intervalo_nivel_nominal"]) == {0.8}


def test_prophet_sin_modelo_no_inventa_corte() -> None:
    motor = ProphetForecaster.__new__(ProphetForecaster)
    motor.serie = pd.DataFrame()
    motor._model = None
    assert motor.ultimo_ds_ajustado is None


def test_nbglm_tras_load_declara_corte_e_intervalo() -> None:
    out = _loader(_nbglm_cargado())._sella_procedencia(_marco())
    assert _nbglm_cargado().ultimo_ds_ajustado == CORTE
    assert out["intervalo_disponible"].all()
    assert set(out["intervalo_nivel_nominal"]) == {0.95}


def test_nbglm_en_fallback_constante_no_declara_intervalo() -> None:
    out = _loader(_nbglm_cargado(con_ajuste=False))._sella_procedencia(_marco())
    assert not out["intervalo_disponible"].any()
    assert out["yhat_lower"].isna().all()
