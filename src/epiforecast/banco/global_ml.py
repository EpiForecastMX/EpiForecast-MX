"""Banco ampliado: LightGBM global y directo por padecimiento (sin recursión ni fuga).

Un modelo por pliegue entrenado con todas las bases del padecimiento. Cada fila es (serie, origen,
horizonte) y sus rasgos usan sólo valores en o antes del origen: la misma semana 52/104/156 semanas
antes del objetivo (con salto a 104 si el objetivo cae en la semana 53), medias recientes, razón de
nivel de 13 semanas, semana MMWR del objetivo y horizonte. Los orígenes de entrenamiento terminan
52 semanas antes del fin del train para que ningún objetivo toque el pliegue.
"""

from __future__ import annotations

from typing import Any

import numpy as np

Period = tuple[int, int]
Arr = np.ndarray[Any, Any]
RASGOS = ["s_a", "s_b", "s_c", "m4", "m13", "m52", "r13", "semana", "h", "nivel"]


def _rasgos(y: Arr, o: int, h: int, semana: int) -> list[float]:
    t = o + h
    lag = 52 if h <= 52 else 104
    idx = [t - lag, t - lag - 52, t - lag - 104]
    if max(idx) > o:
        raise AssertionError("rasgo posterior al origen")
    sa, sb, sc = (float(np.log1p(y[i])) if i >= 0 else np.nan for i in idx)
    reciente, previo = y[o - 12 : o + 1].sum(), y[o - 64 : o - 51].sum()
    return [
        sa,
        sb,
        sc,
        float(np.log1p(y[o - 3 : o + 1].mean())),
        float(np.log1p(y[o - 12 : o + 1].mean())),
        float(np.log1p(y[o - 51 : o + 1].mean())),
        float(np.log((reciente + 1.0) / (previo + 1.0))),
        float(semana),
        float(h),
        float(np.log1p(y[max(0, o - 103) : o + 1].mean())),
    ]


def lgbm_global_directo(
    series: dict[tuple[str, str], Arr], train: list[Period], hold: list[Period], p: dict[str, Any]
) -> dict[tuple[str, str], Arr]:
    import lightgbm as lgb

    cfg = p["lgbm"]
    n, horizonte = len(train), len(hold)
    o_final = n - 1
    semanas_train = [w for _, w in train]
    origenes = range(
        max(104, o_final - 52 * int(cfg["anios_origenes"])),
        o_final - 52 + 1,
        int(cfg["origenes_cada"]),
    )
    filas_x, filas_y = [], []
    for y in series.values():
        for o in origenes:
            for h in range(1, 53):
                filas_x.append(_rasgos(y, o, h, semanas_train[o + h]))
                filas_y.append(float(np.log1p(y[o + h])))
    if not filas_x:
        raise ValueError("historia insuficiente para orígenes de entrenamiento")
    modelo = lgb.LGBMRegressor(
        n_estimators=int(cfg["n_estimators"]),
        learning_rate=float(cfg["learning_rate"]),
        num_leaves=int(cfg["num_leaves"]),
        min_child_samples=int(cfg["min_child_samples"]),
        random_state=int(cfg["seed"]),
        n_jobs=1,
        verbose=-1,
        deterministic=True,
    )
    modelo.fit(np.array(filas_x), np.array(filas_y))
    out = {}
    for key, y in series.items():
        rasgos = [_rasgos(y, o_final, h, hold[h - 1][1]) for h in range(1, horizonte + 1)]
        out[key] = np.expm1(modelo.predict(np.array(rasgos)))
    return out
