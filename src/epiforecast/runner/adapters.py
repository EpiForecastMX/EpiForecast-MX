"""F2/C2 — registry de adapters de motor (por nombre). En C2 está VACÍO a propósito.

benchmark/refit/forecast resuelven el motor aquí; si no hay adapter, el job termina rc=2 y NUNCA
aparenta éxito. El primer adapter real se registra al cablear un motor (EPIC 5), no antes: no se
finge una interfaz de entrenamiento. La forma del ``EngineAdapter`` es PROVISIONAL (se cerrará con
el primer motor); C2 solo necesita la resolución por nombre y el fail-closed.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from epiforecast.runner.manifest import ArtifactRecord


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
