"""Naive coherente: el control con la forma nacional corregida (rescate de controles, 22-nov-2026).

Motor GLOBAL del banco (``fn(series, train, hold, p) -> {serie: pronóstico}``). Parte del control
(naive lag 52 por serie, calendario MMWR) y sólo corrige la forma del nacional:

1. Miembros nacionales, todos con la historia estrictamente previa al origen: el naive nacional,
   nivel × perfil estacional (configuración por defecto del banco), nivel × perfil con encogimiento
   empírico-bayesiano del índice, ETS amortiguado sobre log1p y la media de la misma semana en
   3 años.
2. Combinación de formas: cada miembro se reescala al mismo nivel (media de las últimas 52 semanas
   por el número de semanas del horizonte) y se toma la mediana semana a semana. Combinar formas y
   no niveles evita que los miembros con años viejos arrastren el nivel en series en recuperación.
3. Reparto multiplicativo: cada semana, las bases del naive se multiplican por un mismo factor
   (acotado) para que sumen el nacional combinado. Un cero del naive sigue en cero, que es lo que
   protege la mediana del sMAPE de las bases ralas.
4. Redondeo controlado: bases enteras que suman el redondeo del nacional de cada semana (mayor
   residuo). Las 111 sumas siguen siendo coherentes.

Por qué así (mesa de expertos y banco de rescate, ``docs/RESCATE_CONTROLES.md``): la compuerta mide
a la vez el nacional, la mediana de las bases y los 111 productos; suavizar las bases las empeora,
y no tocarlas deja el nacional con el ruido del año anterior.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from epiforecast.banco import ajuste, motores

Arr = np.ndarray[Any, Any]
Period = tuple[int, int]
NXP = {"nivel_ventana": 52, "anios_perfil": 5, "encogimiento": 0.5, "estadistico_perfil": "media"}
# Variantes evaluadas en el banco de rescate. Cada una nombra los miembros de su mediana y si
# combina formas (nivel común) o valores crudos.
VARIANTES: dict[str, tuple[tuple[str, ...], bool]] = {
    "comb": (("nxp", "ets", "media3"), False),
    "comb4": (("naive", "nxp", "ets", "media3"), False),
    "f3": (("naive", "eb", "ets"), True),
    "f4": (("naive", "nxp", "ets", "media3"), True),
    "f5": (("naive", "nxp", "eb", "ets", "media3"), True),
}
LIMITES = (0.5, 2.0)


def perfil_eb(z: Arr, sem_tr: Arr, sem_ho: Arr, anios: int = 5) -> Arr:
    """Media de 52 semanas × índice estacional encogido por James-Stein entre años.

    El índice de cada semana es la media, entre años, del cociente semana / media del año. El
    encogimiento B = señal / (señal + ruido) sale de la varianza entre semanas frente a la varianza
    entre años de cada semana; con un solo año usa 0.5.
    """
    a = min(anios, len(z) // 52)
    nivel = float(z[-52:].mean())
    if a < 1:
        return np.full(len(sem_ho), nivel)
    m = z[len(z) - 52 * a :].reshape(a, 52)
    mu = m.mean(axis=1, keepdims=True)
    r = np.where(mu > 0, m / np.where(mu > 0, mu, 1.0), 1.0)
    indice = r.mean(axis=0)
    if a >= 2:
        ruido = float(r.var(axis=0, ddof=1).mean() / a)
        senal = max(float(indice.var(ddof=1)) - ruido, 0.0)
        b = senal / (senal + ruido) if senal + ruido > 0 else 0.0
    else:
        b = 0.5
    mapa = {int(s): 1.0 + b * (indice[i] - 1.0) for i, s in enumerate(sem_tr[-52:])}
    return np.array([nivel * mapa.get(int(s), mapa.get(52, 1.0)) for s in sem_ho])


def miembros(
    z: Arr, naive_nac: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]
) -> dict[str, Arr]:
    """Pronósticos nacionales de cada miembro, no negativos, desde la historia previa."""
    sem_tr = np.array([w for _, w in train])
    sem_ho = np.array([w for _, w in hold])
    nxp = ajuste.nivel_x_perfil(z[None, :], sem_tr, sem_ho, NXP, {})[0]
    if len(z) >= 104 and np.ptp(z) > 0:
        ets = ajuste.ets_nacional(z, len(hold), "amortiguada_log1p")
    else:
        ets = nxp
    media3 = motores.MOTORES["media_3y"](z, train, hold, p)
    out = {
        "naive": naive_nac,
        "nxp": nxp,
        "eb": perfil_eb(z, sem_tr, sem_ho),
        "ets": np.asarray(ets, dtype=float),
        "media3": np.asarray(media3, dtype=float),
    }
    return {k: np.maximum(np.nan_to_num(v, nan=0.0, posinf=0.0), 0.0) for k, v in out.items()}


def nacional(variante: str, m: dict[str, Arr], nivel: float) -> Arr:
    """Mediana semana a semana de los miembros (crudos o reescalados a un nivel común)."""
    nombres, formas = VARIANTES[variante]
    h = len(m["naive"])
    filas = []
    for n in nombres:
        v = m[n]
        if formas:
            v = v / v.sum() * nivel if v.sum() > 0 else np.full(h, nivel / h)
        filas.append(v)
    return np.asarray(np.median(np.vstack(filas), axis=0), dtype=float)


def escala_semanal(bases: Arr, total: Arr, limites: tuple[float, float] = LIMITES) -> Arr:
    """Multiplica las bases de cada semana por un factor común acotado; los ceros siguen en cero."""
    s = bases.sum(axis=0)
    k = np.where(s > 0, np.clip(total / np.where(s > 0, s, 1.0), *limites), 1.0)
    return np.asarray(bases * k[None, :], dtype=float)


def redondeo_controlado(pred: Arr) -> Arr:
    """Enteros por base que suman el redondeo del total de cada semana (método del mayor residuo)."""
    piso = np.floor(pred)
    residuo = pred - piso
    falta = np.rint(pred.sum(axis=0)).astype(int) - piso.sum(axis=0).astype(int)
    for h in range(pred.shape[1]):
        if falta[h] > 0:
            piso[np.argsort(-residuo[:, h], kind="stable")[: falta[h]], h] += 1
    return piso


def componentes(
    y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any]
) -> tuple[Arr, dict[str, Arr], float]:
    """Control por serie, miembros nacionales y nivel común; se calculan una sola vez."""
    control = np.vstack([motores.naive_lag52(s, train, hold, p) for s in y])
    control = np.maximum(control, 0.0)
    z = y.sum(axis=0)
    m = miembros(z, control.sum(axis=0), train, hold, p)
    return control, m, float(z[-52:].mean()) * len(hold)


def combinar(control: Arr, m: dict[str, Arr], nivel: float, variante: str, entero: bool) -> Arr:
    pred = escala_semanal(control, nacional(variante, m, nivel))
    return redondeo_controlado(pred) if entero else pred


def pronostico(
    y: Arr, train: list[Period], hold: list[Period], p: dict[str, Any], variante: str, entero: bool
) -> tuple[Arr, Arr]:
    """(bases, control) para la matriz ``y`` (series × semanas) de historia previa al origen."""
    control, m, nivel = componentes(y, train, hold, p)
    return combinar(control, m, nivel, variante, entero), control


def motor_global(variante: str = "f4", entero: bool = True) -> Any:
    """Adaptador al contrato GLOBAL del banco y de la sombra."""

    def fn(
        series: dict[tuple[str, str], Arr],
        train: list[Period],
        hold: list[Period],
        p: dict[str, Any],
    ) -> dict[tuple[str, str], Arr]:
        claves = sorted(series)
        pred, _ = pronostico(
            np.vstack([series[k] for k in claves]), train, hold, p, variante, entero
        )
        return {k: pred[i] for i, k in enumerate(claves)}

    return fn
