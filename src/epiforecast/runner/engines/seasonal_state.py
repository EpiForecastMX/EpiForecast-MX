"""F2/C5.3 — estado final de los motores estacionales: historia mínima + configuración, en JSON.

Los motores estacionales no estiman parámetros: su "modelo" es la cola de historia que necesitan
para reconstruir el pronóstico (lag-52 o ventana de N años) más su configuración declarada. Una
sola implementación para el baseline y para la familia de ventanas.
"""

from __future__ import annotations

import json
from typing import Any

from epiforecast.runner import final_models as fm

Period = tuple[int, int]


def seasonal_state(
    train: dict[Period, float], history_weeks: int, config: dict[str, Any]
) -> fm.FinalState:
    """Cola de ``history_weeks`` periodos (la MÍNIMA que el motor necesita) + configuración."""
    periods = sorted(train)[-history_weeks:]
    payload = {"history": [[y, w, float(train[(y, w)])] for y, w in periods]}
    return fm.FinalState(
        fmt=fm.FMT_JSON,
        text=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        config={**config, "history_weeks": history_weeks, "n_history": len(periods)},
    )


def seasonal_history(state: fm.FinalState) -> dict[Period, float]:
    """Reconstruye el mapa periodo→casos desde el estado serializado."""
    payload = json.loads(state.text or "{}")
    return {(int(y), int(w)): float(v) for y, w, v in payload["history"]}
