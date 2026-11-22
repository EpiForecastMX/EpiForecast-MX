"""Sensibilidad de los motores a quitar 2020–2021 de la historia de entrenamiento (sin E/S).

Pregunta: ¿las conclusiones del banco dependen de que la historia incluya la pandemia? Se
recortan las semanas de los años excluidos de la historia de cada padecimiento y se vuelve a
pronosticar cada año de desarrollo 2022–2024 con las mismas configuraciones. La referencia de
todas las variantes es el naive lag 52 con la historia COMPLETA (denominador fijo): así la
diferencia entre variantes sólo refleja la historia que vio el motor. En 2023 y 2024 el naive no
cambia al recortar (copia 2022 y 2023); en 2022 sin 2020–2021 copiaría 2019, y se reporta aparte.

Al recortar dos años completos, los rezagos por índice (t − 52·j) quedan mejor alineados que con
la historia completa: 2020 tiene 53 semanas MMWR y desfasaba una semana los años anteriores.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from epiforecast.banco import ajuste, flujo
from epiforecast.banco import ajuste_flujo as af

VARIANTES: dict[str, tuple[int, ...]] = {
    "completa": (),
    "sin_2020": (2020,),
    "sin_2020_2021": (2020, 2021),
}
PLIEGUES: tuple[int, ...] = (2022, 2023, 2024)
ETS_DEFAULT = str(ajuste.ESPACIOS["topdown"][2]["variante_ets"])


def sin_anios(p: af.Padecimiento, excluir: tuple[int, ...]) -> af.Padecimiento:
    """Copia de ``p`` sin las semanas de ``excluir`` (ni como historia ni como pliegue)."""
    if not excluir:
        return p
    keep = ~np.isin(p.anios, excluir)
    return af.Padecimiento(
        p.disease_id,
        p.y[:, keep],
        p.anios[keep],
        p.semanas[keep],
        [a for a in p.desarrollo if a not in excluir],
    )


def con_ets(p: af.Padecimiento, anios: tuple[int, ...], variante: str = ETS_DEFAULT) -> None:
    """Calcula el ETS nacional que usa el top-down por defecto, sólo donde falte."""
    for anio in anios:
        if variante in p.ets.get(anio, {}):
            continue
        ytr, _, sem_ho, _ = p.corte(anio)
        p.ets.setdefault(anio, {})[variante] = ajuste.ets_nacional(
            ytr.sum(axis=0), len(sem_ho), variante
        )


def configuraciones(globales: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Nombre → (motor, params fijos o dict año → params)."""
    d: dict[str, Any] = {m: (m, esp[2]) for m, esp in ajuste.ESPACIOS.items()}
    base = ajuste.ESPACIOS["estacional_nivel"][2]
    d["media_3a"] = ("estacional_nivel", base | {"anios": 3})
    d["mediana_5a"] = ("estacional_nivel", base | {"anios": 5, "estadistico": "mediana"})
    d["topdown_nxp"] = (
        "topdown",
        {"motor_nacional": "nivel_x_perfil", "ventana_pesos": 104}
        | {f"nxp_{k}": v for k, v in ajuste.ESPACIOS["nivel_x_perfil"][2].items()},
    )
    if globales:
        d["nivel_x_perfil_optuna"] = ("nivel_x_perfil", globales)
    return d


def filas(p: af.Padecimiento, configs: dict[str, Any]) -> list[dict[str, Any]]:
    """sMAPE nacional y log-razón contra el naive completo, por variante, pliegue y config."""
    pliegues = [a for a in PLIEGUES if a in p.desarrollo]
    out: list[dict[str, Any]] = []
    for variante, excluir in VARIANTES.items():
        q = sin_anios(p, excluir)
        validos = []
        for a in pliegues:
            try:
                q.corte(a)
            except flujo.BancoError:
                continue
            validos.append(a)
        con_ets(q, tuple(validos))
        for a in validos:
            ref = af.naive(p, a)
            naive_var = af.naive(q, a)
            for nombre, (motor, params) in configs.items():
                if isinstance(params, dict) and a in params:
                    params = params[a]
                elif isinstance(params, dict) and any(isinstance(k, int) for k in params):
                    continue  # config optimizada sin estudio para este año
                s = af.smape_pliegue(q, motor, params, a)
                out.append(
                    {
                        "disease_id": p.disease_id,
                        "variante": variante,
                        "pliegue": a,
                        "config": nombre,
                        "smape": s,
                        "naive_completa": ref,
                        "naive_variante": naive_var,
                        "log_ratio": float(np.log(max(s, 1e-6) / max(ref, 1e-6))),
                    }
                )
    return out
