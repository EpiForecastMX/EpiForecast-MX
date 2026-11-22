"""Motores paramétricos vectorizados y sus espacios de búsqueda para Optuna (sin E/S).

Cada motor recibe la matriz de historia ``Y`` (series × semanas, orden MMWR, estrictamente previa
al pliegue), las semanas MMWR del train y del holdout, y un diccionario de hiperparámetros; devuelve
la matriz de pronósticos (series × holdout). Los espacios declaran qué puede tocar Optuna; los
valores por defecto reproducen la configuración del banco ampliado v1.

Diferencia declarada con el banco: la ventana estacional por rezago usa índices (t - 52·j) en vez
del calendario MMWR, así que en un pliegue de 53 semanas la semana 53 toma la semana 1 del año.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

Arr = np.ndarray[Any, Any]
Motor = Callable[[Arr, Arr, Arr, dict[str, Any], dict[str, Any]], Arr]


class Trial(Protocol):
    def suggest_int(self, name: str, low: int, high: int) -> int: ...
    def suggest_float(self, name: str, low: float, high: float, *, log: bool = False) -> float: ...
    def suggest_categorical(self, name: str, choices: list[Any]) -> Any: ...


def _estacional(y: Arr, h: int, anios: int, est: str) -> Arr:
    n = y.shape[1]
    out = np.empty((y.shape[0], h))
    for i in range(h):
        j0 = i // 52 + 1
        idx = [n + i - 52 * j for j in range(j0, j0 + anios) if n + i - 52 * j >= 0]
        col = y[:, idx]
        out[:, i] = col.mean(axis=1) if est == "media" else np.median(col, axis=1)
    return out


def media_movil(y: Arr, sem_tr: Arr, sem_ho: Arr, p: dict[str, Any], ctx: dict[str, Any]) -> Arr:
    return np.repeat(y[:, -int(p["ventana"]) :].mean(axis=1, keepdims=True), len(sem_ho), axis=1)


def nivel_x_perfil(
    y: Arr, sem_tr: Arr, sem_ho: Arr, p: dict[str, Any], ctx: dict[str, Any]
) -> Arr:
    """Nivel reciente × índice estacional por semana MMWR de varios años, encogido hacia 1."""
    w, anios, k = int(p["nivel_ventana"]), int(p["anios_perfil"]), float(p["encogimiento"])
    nivel = y[:, -w:].mean(axis=1)
    ventana, semanas = y[:, -52 * anios :], sem_tr[-52 * anios :]
    global_ = ventana.mean(axis=1)
    agg = np.mean if p["estadistico_perfil"] == "media" else np.median
    perfil = {}
    for s in np.unique(semanas):
        perfil[int(s)] = agg(ventana[:, semanas == s], axis=1)
    out = np.empty((y.shape[0], len(sem_ho)))
    with np.errstate(divide="ignore", invalid="ignore"):
        for i, s in enumerate(sem_ho):
            v = perfil.get(int(s), perfil.get(52, global_))
            indice = np.where(global_ > 0, v / global_, 1.0)
            out[:, i] = nivel * (1 + k * (indice - 1))
    return out


def tsb(y: Arr, sem_tr: Arr, sem_ho: Arr, p: dict[str, Any], ctx: dict[str, Any]) -> Arr:
    a, b = float(p["alfa"]), float(p["beta"])
    positivo = y > 0
    prob = positivo.mean(axis=1)
    conteo = positivo.sum(axis=1)
    z = np.where(conteo > 0, np.where(positivo, y, 0).sum(axis=1) / np.maximum(conteo, 1), 0)
    for t in range(y.shape[1]):
        pt = positivo[:, t]
        prob = prob + b * (pt.astype(float) - prob)
        z = np.where(pt, z + a * (y[:, t] - z), z)
    return np.repeat((prob * z)[:, None], len(sem_ho), axis=1)


def estacional_nivel(
    y: Arr, sem_tr: Arr, sem_ho: Arr, p: dict[str, Any], ctx: dict[str, Any]
) -> Arr:
    """Media o mediana de la misma semana en ``anios`` años × factor de nivel acotado."""
    base = _estacional(y, len(sem_ho), int(p["anios"]), str(p["estadistico"]))
    w = int(p["nivel_ventana"])
    if not p["con_nivel"] or y.shape[1] < 52 + w:
        return base
    factor = (y[:, -w:].sum(axis=1) + 1) / (y[:, -52 - w : -52].sum(axis=1) + 1)
    factor = np.clip(factor, float(p["nivel_min"]), float(p["nivel_max"]))
    return np.asarray(base * factor[:, None], dtype=float)


def topdown(y: Arr, sem_tr: Arr, sem_ho: Arr, p: dict[str, Any], ctx: dict[str, Any]) -> Arr:
    """Nacional por ETS (variante precalculada en ``ctx``) o nivel × perfil, repartido."""
    if p["motor_nacional"] == "ets":
        total = np.asarray(ctx["ets_nacional"][str(p["variante_ets"])], dtype=float)
    else:
        q = {k[4:]: v for k, v in p.items() if k.startswith("nxp_")}
        total = nivel_x_perfil(y.sum(axis=0, keepdims=True), sem_tr, sem_ho, q, ctx)[0]
    total = np.maximum(total, 0.0)
    pesos = y[:, -int(p["ventana_pesos"]) :].sum(axis=1)
    suma = pesos.sum()
    if suma == 0:
        return np.zeros((y.shape[0], len(sem_ho)))
    return np.asarray((pesos / suma)[:, None] * total[None, :], dtype=float)


VARIANTES_ETS: tuple[str, ...] = tuple(
    f"{t}_{x}" for x in ("log1p", "bruta") for t in ("amortiguada", "aditiva", "sin_tendencia")
)


def ets_nacional(z_bruto: Arr, h: int, variante: str) -> Arr:
    """ETS estacional (52) sobre el nacional; la variante fija tendencia y transformación."""
    import warnings

    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    tendencia, transf = variante.rsplit("_", 1)
    z = np.log1p(z_bruto) if transf == "log1p" else np.asarray(z_bruto, dtype=float)
    if len(z) < 104 or np.ptp(z) == 0:
        return np.full(h, float(z_bruto[-1]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(
            z,
            trend=None if tendencia == "sin_tendencia" else "add",
            damped_trend=tendencia == "amortiguada",
            seasonal="add",
            seasonal_periods=52,
            initialization_method="estimated",
        ).fit()
    f = np.asarray(fit.forecast(h), dtype=float)
    return np.expm1(f) if transf == "log1p" else f


def _nxp(t: Trial, prefijo: str = "") -> dict[str, Any]:
    return {
        f"{prefijo}nivel_ventana": t.suggest_int(f"{prefijo}nivel_ventana", 8, 104),
        f"{prefijo}anios_perfil": t.suggest_int(f"{prefijo}anios_perfil", 2, 5),
        f"{prefijo}encogimiento": t.suggest_float(f"{prefijo}encogimiento", 0.0, 1.0),
        f"{prefijo}estadistico_perfil": t.suggest_categorical(
            f"{prefijo}estadistico_perfil", ["media", "mediana"]
        ),
    }


def _espacio_estacional(t: Trial) -> dict[str, Any]:
    p: dict[str, Any] = {
        "anios": t.suggest_int("anios", 1, 5),
        "estadistico": t.suggest_categorical("estadistico", ["media", "mediana"]),
        "con_nivel": t.suggest_categorical("con_nivel", [False, True]),
    }
    if p["con_nivel"]:
        p["nivel_ventana"] = t.suggest_int("nivel_ventana", 4, 26)
        p["nivel_min"] = t.suggest_float("nivel_min", 0.2, 1.0)
        p["nivel_max"] = t.suggest_float("nivel_max", 1.0, 5.0)
    else:
        p |= {"nivel_ventana": 13, "nivel_min": 0.5, "nivel_max": 2.0}
    return p


def _espacio_topdown(t: Trial) -> dict[str, Any]:
    p: dict[str, Any] = {
        "motor_nacional": t.suggest_categorical("motor_nacional", ["ets", "nivel_x_perfil"]),
        "ventana_pesos": t.suggest_int("ventana_pesos", 13, 260),
    }
    if p["motor_nacional"] == "ets":
        p["variante_ets"] = t.suggest_categorical("variante_ets", list(VARIANTES_ETS))
    else:
        p |= _nxp(t, "nxp_")
    return p


ESPACIOS: dict[str, tuple[Motor, Callable[[Trial], dict[str, Any]], dict[str, Any]]] = {
    "media_movil": (
        media_movil,
        lambda t: {"ventana": t.suggest_int("ventana", 4, 156)},
        {"ventana": 52},
    ),
    "nivel_x_perfil": (
        nivel_x_perfil,
        _nxp,
        {
            "nivel_ventana": 52,
            "anios_perfil": 5,
            "encogimiento": 0.5,
            "estadistico_perfil": "media",
        },
    ),
    "tsb": (
        tsb,
        lambda t: {
            "alfa": t.suggest_float("alfa", 0.005, 0.6, log=True),
            "beta": t.suggest_float("beta", 0.005, 0.6, log=True),
        },
        {"alfa": 0.1, "beta": 0.1},
    ),
    "estacional_nivel": (
        estacional_nivel,
        _espacio_estacional,
        {
            "anios": 1,
            "estadistico": "media",
            "con_nivel": False,
            "nivel_ventana": 13,
            "nivel_min": 0.5,
            "nivel_max": 2.0,
        },
    ),
    "topdown": (
        topdown,
        _espacio_topdown,
        {"motor_nacional": "ets", "variante_ets": "amortiguada_log1p", "ventana_pesos": 104},
    ),
}
