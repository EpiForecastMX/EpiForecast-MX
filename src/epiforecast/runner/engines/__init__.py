"""F2/C3.4 — bootstrap de adapters de motor: importar este paquete registra los motores.

El worker de subprocess importa ``epiforecast.runner.engines`` para poblar el registry de adapters
(``runner.adapters``). Cada módulo de motor se auto-registra al importarse.
"""

from __future__ import annotations

from epiforecast.runner.engines import seasonal_naive as seasonal_naive
from epiforecast.runner.engines import seasonal_window as seasonal_window

__all__ = ["seasonal_naive", "seasonal_window"]
