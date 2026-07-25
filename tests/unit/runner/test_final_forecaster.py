"""C7.2-A/R15.4 — capacidad TIPADA para pronosticar desde un ``FinalState``.

Un consumidor del release necesita pronosticar sin `run_dir`, sin `job_context.json` y sin
subprocess. La alternativa —un `if engine == "..."` en el loader— reintroduciría el acoplamiento por
padecimiento que C5/C7.1 quitaron, así que la capacidad se declara en el registry de adapters y un
motor que no la ofrece hace fallar el bundle con error tipado: JAMÁS se sustituye por otro.

El carril legacy ``adapter.run("forecast", run_dir)`` no se toca: sigue siendo el que ejecuta el
subprocess del runner.
"""

from __future__ import annotations

import pytest

from epiforecast.runner import adapters
from epiforecast.runner.adapters import (
    AdapterCapabilityError,
    FinalStateForecaster,
    available_adapters,
    final_forecaster,
    get_adapter,
)

# Importar el paquete de motores registra los adapters reales.
import epiforecast.runner.engines  # noqa: F401  isort:skip


def _con_forecast() -> list[str]:
    """Los motores que declaran soportar el comando ``forecast`` del runner."""
    return [n for n in available_adapters() if get_adapter(n).supports("forecast")]  # type: ignore[union-attr]


def test_hay_motores_registrados_que_soportan_forecast():
    assert _con_forecast(), "sin motores no se prueba nada"


@pytest.mark.parametrize("engine", _con_forecast())
def test_todo_motor_que_pronostica_ofrece_la_capacidad_final(engine):
    adapter = final_forecaster(engine)
    assert isinstance(adapter, FinalStateForecaster)
    assert adapter.name == engine


@pytest.mark.parametrize("engine", _con_forecast())
def test_la_capacidad_delega_en_la_función_de_forecast_del_motor(engine):
    """Reutiliza la implementación existente: no hay un segundo camino de pronóstico."""
    adapter = get_adapter(engine)
    metodo = adapter.forecast_state.__func__  # type: ignore[union-attr]
    assert metodo.__doc__ and "forecast_final" in metodo.__doc__


def test_un_motor_desconocido_falla_con_error_tipado():
    with pytest.raises(AdapterCapabilityError, match="sin adapter"):
        final_forecaster("motor_que_no_existe")


def test_un_adapter_sin_la_capacidad_falla_con_error_tipado(monkeypatch):
    class SinCapacidad:
        name = "motor_mudo"

        def supports(self, command: str) -> bool:
            return command == "forecast"

        def run(self, command: str, run_dir: str) -> list:
            return []

    monkeypatch.setitem(adapters._ADAPTERS, "motor_mudo", SinCapacidad())
    with pytest.raises(AdapterCapabilityError, match="no ofrece"):
        final_forecaster("motor_mudo")


def test_la_capacidad_no_puede_ser_un_atributo_no_invocable(monkeypatch):
    class Falso:
        name = "motor_falso"
        forecast_state = "no soy una función"

        def supports(self, command: str) -> bool:
            return command == "forecast"

        def run(self, command: str, run_dir: str) -> list:
            return []

    monkeypatch.setitem(adapters._ADAPTERS, "motor_falso", Falso())
    with pytest.raises(AdapterCapabilityError, match="no ofrece"):
        final_forecaster("motor_falso")
