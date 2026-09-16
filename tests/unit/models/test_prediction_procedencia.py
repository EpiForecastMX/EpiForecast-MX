"""Contrato de procedencia de cada fila de pronóstico (`ForecastModelLoader`).

``predict`` devuelve el ajuste histórico y el futuro en un mismo marco. Sin un marcador
explícito, cualquier consumidor puede puntuar como pronóstico lo que era ajuste dentro de la
muestra. Estas pruebas fijan el sello que los distingue.
"""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.models.prediction import ForecastModelLoader

pytestmark = pytest.mark.unit

CORTE = pd.Timestamp("2026-01-26")  # semana 6 del boletín de 2026


class _MotorFalso:
    """Motor mínimo: solo necesita declarar hasta dónde llegó su ajuste."""

    def __init__(self, corte: pd.Timestamp | None = CORTE) -> None:
        self._corte = corte

    @property
    def ultimo_ds_ajustado(self) -> pd.Timestamp | None:
        return self._corte


def _loader(corte: pd.Timestamp | None = CORTE) -> ForecastModelLoader:
    """Instancia sin pasar por ``__init__``, que cargaría configuración y un modelo real."""
    loader = ForecastModelLoader.__new__(ForecastModelLoader)
    loader.forecaster = _MotorFalso(corte)  # type: ignore[attr-defined]
    return loader


def _marco() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ds": pd.to_datetime(["2026-01-19", "2026-01-26", "2026-02-02", "2026-02-09"]),
            "yhat": [1.0, 2.0, 3.0, 4.0],
        }
    )


def test_separa_ajuste_de_pronostico() -> None:
    out = _loader()._sella_procedencia(_marco())
    assert list(out["fase_modelo"]) == ["ajuste", "ajuste", "pronostico", "pronostico"]


def test_adelanto_es_cero_en_el_ajuste_y_crece_en_el_futuro() -> None:
    out = _loader()._sella_procedencia(_marco())
    assert list(out["adelanto_semanas"]) == [0, 0, 1, 2]


def test_reporta_el_corte_en_el_calendario_del_boletin() -> None:
    """El corte del 26 de enero es la semana 6 del boletín, no la 5 ni la semana ISO."""
    out = _loader()._sella_procedencia(_marco())
    assert set(out["anio_boletin_corte"]) == {2026}
    assert set(out["semana_boletin_corte"]) == {6}
    assert set(out["ultimo_ds_ajustado"]) == {CORTE}


def test_sin_corte_conocido_no_se_inventa_fase() -> None:
    """Si el motor no declara su ajuste, las columnas quedan ausentes, nunca en un valor por
    omisión que parezca cierto."""
    out = _loader(corte=None)._sella_procedencia(_marco())
    for col in ("fase_modelo", "adelanto_semanas", "semana_boletin_corte"):
        assert out[col].isna().all()


def test_no_altera_las_columnas_originales() -> None:
    marco = _marco()
    out = _loader()._sella_procedencia(marco)
    pd.testing.assert_frame_equal(out[["ds", "yhat"]], marco)


def test_corte_inutilizable_no_rompe_ni_inventa_fase() -> None:
    """Un motor que declara un corte que no es fecha deja la procedencia ausente, sin reventar."""

    class _MotorRaro:
        @property
        def ultimo_ds_ajustado(self) -> object:
            return object()

    loader = ForecastModelLoader.__new__(ForecastModelLoader)
    loader.forecaster = _MotorRaro()  # type: ignore[attr-defined]
    out = loader._sella_procedencia(_marco())
    assert len(out) == 4
    assert out["fase_modelo"].isna().all()


class _MotorConIntervalo:
    """Motor que sí produce intervalo propio, como Prophet o DeepAR."""

    ultimo_ds_ajustado = CORTE

    def __init__(self, nominal: float = 0.8) -> None:
        self._nominal = nominal

    @property
    def intervalo_nominal(self) -> float:
        return self._nominal

    @property
    def intervalo_metodo(self) -> str:
        return "motor de prueba: intervalo nativo"


def _marco_con_banda(lower: list[float], upper: list[float]) -> pd.DataFrame:
    marco = _marco()
    marco["yhat_lower"] = lower
    marco["yhat_upper"] = upper
    return marco


def _loader_de(motor: object) -> ForecastModelLoader:
    loader = ForecastModelLoader.__new__(ForecastModelLoader)
    loader.forecaster = motor  # type: ignore[attr-defined]
    return loader


def test_motor_con_intervalo_propio_lo_conserva_y_lo_declara() -> None:
    marco = _marco_con_banda([0.5, 1.5, 2.5, 3.5], [1.5, 2.5, 3.5, 4.5])
    out = _loader_de(_MotorConIntervalo(0.8))._sella_procedencia(marco)
    assert out["intervalo_disponible"].all()
    assert set(out["intervalo_nivel_nominal"]) == {0.8}
    assert list(out["yhat_lower"]) == [0.5, 1.5, 2.5, 3.5]


def test_banda_degenerada_se_vacia_y_se_declara_ausente() -> None:
    """``lower == upper == yhat`` no es un intervalo angosto: es la ausencia de intervalo."""
    marco = _marco_con_banda([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0])
    out = _loader_de(_MotorConIntervalo(0.9))._sella_procedencia(marco)
    assert not out["intervalo_disponible"].any()
    assert out["yhat_lower"].isna().all()
    assert out["yhat_upper"].isna().all()
    assert out["intervalo_nivel_nominal"].isna().all()


def test_motor_sin_intervalo_no_hereda_banda_de_nadie() -> None:
    out = _loader_de(_MotorFalso())._sella_procedencia(
        _marco_con_banda([1, 2, 3, 4], [9, 9, 9, 9])
    )
    assert not out["intervalo_disponible"].any()
    assert out["yhat_lower"].isna().all()
