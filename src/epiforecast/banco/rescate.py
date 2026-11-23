"""Banco de rescate de controles: la compuerta completa del runner en pliegues de desarrollo.

Pregunta (22-nov-2026): ¿qué técnica habría pasado la compuerta de aceptación en los padecimientos
publicados sólo con el control? La compuerta compara contra el naive lag 52 tres ámbitos a la vez:
sMAPE del nacional General (hasta 10 % peor), mediana del sMAPE de las bases (hasta 5 %) y mediana
del sMAPE de todos los productos (111, o 37 sin desglose por sexo; hasta 5 %). Los límites salen de
la política de cada release, no de este código.

Sólo años de DESARROLLO: la historia se trunca al último año de desarrollo al cargarla, como en la
búsqueda anidada; los años de prueba ni siquiera viven en memoria. No publica ni selecciona para
producción.

- Un pliegue es *positivo* si pasa los tres ámbitos y además mejora el nacional.
- Selección anidada entre variantes: para el año externo O se elige la variante con más pliegues
  positivos en los años de desarrollo anteriores a O (sólo padecimientos de historia larga) y se
  mide una vez en O; la historia corta se mide con la variante elegida en toda la historia larga.
- Un padecimiento queda *rescatado en desarrollo* si pasa la compuerta en todos sus años externos y
  la media de su mejora nacional es negativa. No es aceptación: la prueba de 2025 ya se consumió y
  sólo la validación prospectiva cuenta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import yaml

from epiforecast.banco import coherente, flujo
from epiforecast.data.epi_geo_exposure import GeoCatalog
from epiforecast.runner.evaluation import smape_percent

Arr = np.ndarray[Any, Any]
AMBITOS = ("smape_nacional_general", "smape_bases", "smape_all")
TRANSFERENCIA = "transferencia"


@dataclass
class Caso:
    disease_id: str
    claves: list[tuple[str, str]]
    y: Arr
    periodos: list[tuple[int, int]]
    desarrollo: list[int]
    limites: dict[str, float]


def limites(disease: str) -> dict[str, float]:
    """``acceptance.max_worse_pct`` de la política del release público."""
    rel = flujo._json(flujo._ROOT / "config/publication" / disease / "public_release_pointer.json")
    (pol,) = sorted(
        (flujo._ROOT / "artifacts/releases" / disease / rel["release_id"] / "policy").glob(
            "*.yaml"
        )
    )
    raw = yaml.safe_load(pol.read_text(encoding="utf-8"))["acceptance"]["max_worse_pct"]
    return {k: float(raw[k]) for k in AMBITOS}


def cargar(disease: str) -> Caso:
    dev, prueba = flujo.anios(disease)
    periodos, series = flujo.historia(disease)
    dentro = [i for i, q in enumerate(periodos) if q[0] <= max(dev)]
    if {periodos[i][0] for i in dentro} & prueba:
        raise flujo.BancoError(f"{disease}: un año de prueba quedó antes del último de desarrollo")
    claves = sorted(series)
    y = np.vstack([series[k][dentro] for k in claves])
    return Caso(disease, claves, y, [periodos[i] for i in dentro], dev, limites(disease))


def matriz_s(claves: list[tuple[str, str]], cat: GeoCatalog) -> tuple[Arr, int]:
    """Matriz de agregación: bases, estado General (con sexo), región por sexo y nacional."""
    nb = len(claves)
    i = np.eye(nb)
    sexos = sorted({s for _, s in claves})
    filas = list(i)
    if sexos != ["general"]:
        for geo in sorted({g for g, _ in claves}):
            filas.append(sum(i[j] for j, (g, _) in enumerate(claves) if g == geo))
    grupos = [[s] for s in sexos] + ([sexos] if len(sexos) > 1 else [])
    for reg in sorted(cat.macroregion_ids()):
        estados = set(cat.states_in_macroregion(reg))
        for ss in grupos:
            filas.append(sum(i[j] for j, (g, s) in enumerate(claves) if g in estados and s in ss))
    for ss in grupos:
        filas.append(sum(i[j] for j, (_, s) in enumerate(claves) if s in ss))
    return np.vstack(filas), nb


def metricas(s: Arr, nb: int, verdad: Arr, pred: Arr) -> dict[str, float]:
    t, p = s @ verdad, s @ np.maximum(pred, 0.0)
    sm = np.array([smape_percent(t[k], p[k]) for k in range(len(s))])
    return {
        "smape_nacional_general": float(sm[-1]),
        "smape_bases": float(np.median(sm[:nb])),
        "smape_all": float(np.median(sm)),
    }


def candidatos() -> list[str]:
    return [f"{v}|{'ent' if e else 'cont'}" for v in coherente.VARIANTES for e in (True, False)]


def filas(caso: Caso, cat: GeoCatalog, p: dict[str, Any]) -> list[dict[str, Any]]:
    """Métricas del control y de cada variante en cada año de desarrollo con un año previo."""
    s, nb = matriz_s(caso.claves, cat)
    out = []
    anios = np.array([a for a, _ in caso.periodos])
    for anio in caso.desarrollo:
        n = int(np.argmax(anios >= anio))
        ho = anios == anio
        if n < 52:
            continue
        train, hold = caso.periodos[:n], [q for q, h in zip(caso.periodos, ho, strict=True) if h]
        ytr, verdad = caso.y[:, :n], caso.y[:, ho]
        control, m, nivel = coherente.componentes(ytr, train, hold, p)
        preds = {
            c: coherente.combinar(control, m, nivel, c.split("|")[0], c.endswith("|ent"))
            for c in candidatos()
        }
        for motor, pr in {"control": control, **preds}.items():
            out.append(
                {"disease_id": caso.disease_id, "anio": anio, "motor": motor}
                | metricas(s, nb, verdad, pr)
                | {f"lim_{k}": caso.limites[k] for k in AMBITOS}
            )
    return out


def compuerta(df: pd.DataFrame) -> pd.DataFrame:
    """Une cada variante con su control y aplica los tres límites (``worse_pct`` del runner)."""
    ctrl = df[df["motor"] == "control"].set_index(["disease_id", "anio"])[list(AMBITOS)]
    m = df[df["motor"] != "control"].join(ctrl, on=["disease_id", "anio"], rsuffix="_control")
    ok = pd.Series(True, index=m.index)
    for k in AMBITOS:
        c, v = m[f"{k}_control"], m[k]
        # Igual que ``acceptance.evaluate_gate``: con el control en 0 la comprobación reprueba.
        peor = np.where(c > 0, (v - c) / c.where(c > 0, 1.0) * 100, np.inf)
        m[f"peor_{k}"] = peor
        ok &= m[f"peor_{k}"] <= m[f"lim_{k}"]
    m["pasa"] = ok
    m["positivo"] = ok & (m["peor_smape_nacional_general"] < 0)
    return m


def anidado(g: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Variante elegida por año externo con los años internos y su resultado en el externo."""
    primero = g.groupby("disease_id")["anio"].transform("min")
    largo = primero < max(g["anio"])  # historia corta = un solo año de desarrollo, el último
    largo &= g.groupby("disease_id")["anio"].transform("nunique") > 1
    elegidas, partes = {}, []
    externos = sorted({a for a in g.loc[largo, "anio"].unique()})[-2:]
    for ext in [*externos, TRANSFERENCIA]:
        if ext == TRANSFERENCIA:
            interno, externo = g[largo], g[~largo]
        else:
            interno, externo = g[largo & (g["anio"] < ext)], g[g["anio"] == ext]
        tasa = interno.groupby("motor")["positivo"].mean()
        elegida = str(tasa.sort_values(ascending=False, kind="stable").index[0])
        elegidas[str(ext)] = elegida
        partes.append(externo[externo["motor"] == elegida].assign(externo=str(ext)))
    return pd.concat(partes, ignore_index=True), elegidas


def veredictos(ext: pd.DataFrame) -> pd.DataFrame:
    v = ext.groupby("disease_id").agg(
        pasa=("pasa", "all"),
        mejora_nacional_pct=("peor_smape_nacional_general", "mean"),
        anios=("anio", lambda s: ",".join(str(a) for a in sorted(s))),
    )
    v["rescatado"] = v["pasa"] & (v["mejora_nacional_pct"] < 0)
    return v.reset_index()
