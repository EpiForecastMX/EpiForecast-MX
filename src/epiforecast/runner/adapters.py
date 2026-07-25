"""F2/C2 — registry de adapters de motor (por nombre). En C2 está VACÍO a propósito.

benchmark/refit/forecast resuelven el motor aquí; si no hay adapter, el job termina rc=2 y NUNCA
aparenta éxito. El primer adapter real se registra al cablear un motor (EPIC 5), no antes: no se
finge una interfaz de entrenamiento. La forma del ``EngineAdapter`` es PROVISIONAL (se cerrará con
el primer motor); C2 solo necesita la resolución por nombre y el fail-closed.

C7.2-A/R15.4 añade una capacidad OPCIONAL y tipada, ``FinalStateForecaster``, para pronosticar
desde un ``FinalState`` sin `run_dir` ni subprocess: es lo que necesita un consumidor de un release
bundle. No sustituye a ``run("forecast", run_dir)``, que sigue siendo el carril del runner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from epiforecast.runner.manifest import ArtifactRecord

if TYPE_CHECKING:  # sólo para tipar: evita importar el contrato de modelo final en runtime
    from epiforecast.runner.final_models import FinalState, ForecastRequest


class AdapterCapabilityError(ValueError):
    """El motor pedido no existe o no ofrece la capacidad exigida (nunca se sustituye por otro)."""


@runtime_checkable
class EngineAdapter(Protocol):
    """Interfaz de un motor. Se ejecuta dentro del subprocess limpio del worker."""

    name: str

    def supports(self, command: str) -> bool:
        """True si el motor implementa ``command`` (benchmark/refit/forecast)."""
        ...

    def run(self, command: str, run_dir: str) -> list[ArtifactRecord]:
        """Ejecuta ``command`` para este motor y devuelve los artefactos emitidos (validados)."""
        ...


@runtime_checkable
class FinalStateForecaster(Protocol):
    """Capacidad de pronosticar desde un modelo final ya cargado (sin `run_dir` ni subprocess)."""

    def forecast_state(
        self, state: FinalState, request: ForecastRequest
    ) -> dict[tuple[int, int], float]:
        """Pronostica los periodos de ``request`` desde ``state``; NO reajusta."""
        ...


_ADAPTERS: dict[str, EngineAdapter] = {}


def register_adapter(name: str, adapter: EngineAdapter) -> None:
    """Registra un adapter de motor (idempotente por nombre; rechaza colisión distinta)."""
    existing = _ADAPTERS.get(name)
    if existing is not None and existing is not adapter:
        raise ValueError(f"adapter ya registrado para el motor {name!r}")
    _ADAPTERS[name] = adapter


def get_adapter(name: str) -> EngineAdapter | None:
    """Adapter del motor ``name`` o ``None`` si no hay (→ el job termina rc=2)."""
    return _ADAPTERS.get(name)


def available_adapters() -> list[str]:
    return sorted(_ADAPTERS)


def final_forecaster(name: str) -> FinalStateForecaster:
    """Adapter de ``name`` con capacidad de forecast final, o ``AdapterCapabilityError``.

    Fail-closed a propósito: un motor presente en un release que no sabe pronosticar desde su estado
    invalida el release entero. Sustituirlo por otro motor cambiaría el portafolio en silencio.
    """
    adapter = _ADAPTERS.get(name)
    if adapter is None:
        raise AdapterCapabilityError(f"el motor {name!r} no está registrado (sin adapter)")
    if not callable(getattr(adapter, "forecast_state", None)):
        raise AdapterCapabilityError(
            f"el motor {name!r} no ofrece la capacidad de forecast final (forecast_state)"
        )
    return adapter  # type: ignore[return-value]
