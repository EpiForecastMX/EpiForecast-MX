"""Banco ampliado: ¿algún motor le gana al naive y a los simples? (sólo pliegues de desarrollo).

Tres lecturas, de la más honesta a la más optimista:
1. Motor fijo: cada motor en todos los padecimientos, sin elegir nada (fuera de muestra puro).
2. Selección por ventana creciente: se elige el motor con los pliegues previos y se mide en el
   siguiente, entre todos los motores o sólo entre los simples.
3. Mejor a posteriori por clase: el mejor complejo frente al mejor simple de cada padecimiento,
   ambos elegidos viendo el resultado (optimista para los dos lados; sólo como techo).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

SIMPLES = {"simple"}


def tabla(metricas: pd.DataFrame) -> pd.DataFrame:
    """Media por padecimiento y motor del sMAPE nacional (sólo pliegues completos en todos)."""
    m = metricas[metricas["completo"]]
    return m.pivot_table(
        index="disease_id", columns="engine", values="smape_nacional", aggfunc="mean"
    )


def motor_fijo(t: pd.DataFrame, control: str, clase_de: dict[str, str]) -> pd.DataFrame:
    filas = []
    mejor_simple = t[[c for c in t if clase_de.get(str(c)) in SIMPLES]].min(axis=1)
    for e in t.columns:
        ok = t[e].notna() & t[control].notna()
        if not ok.any():
            continue
        se, sc, ms = t.loc[ok, e], t.loc[ok, control], mejor_simple.loc[ok]
        ratio = se / sc.where(sc > 0)
        filas.append(
            {
                "engine": e,
                "clase": clase_de.get(str(e), "?"),
                "padecimientos": int(ok.sum()),
                "mediana_smape_nacional": round(float(se.median()), 2),
                "mediana_vs_naive_pct": round(float((ratio.median() - 1) * 100), 1),
                "gana_al_naive": int((se < sc - 1e-9).sum()),
                "gana_al_naive_5pct": int((se < sc * 0.95).sum()),
                "pierde_mas_10pct": int((se > sc * 1.10).sum()),
                "gana_al_mejor_simple": int((se < ms - 1e-9).sum()),
            }
        )
    return pd.DataFrame(filas).sort_values("mediana_smape_nacional").reset_index(drop=True)


def seleccion_creciente(
    metricas: pd.DataFrame, control: str, clase_de: dict[str, str]
) -> dict[str, Any]:
    """Elige con pliegues previos y mide en el siguiente (padecimientos con ≥ 2 pliegues)."""
    m = metricas[metricas["completo"]]
    res: dict[str, list[float]] = {"naive": [], "todos": [], "simples": [], "complejos": []}
    for _, g in m.groupby("disease_id"):
        p = g.pivot_table(index="fold", columns="engine", values="smape_nacional")
        p = p.dropna(axis=1)
        if len(p) < 2 or control not in p:
            continue
        acum: dict[str, list[float]] = {k: [] for k in res}
        for i in range(1, len(p)):
            previo, sig = p.iloc[:i].mean(), p.iloc[i]
            grupos: dict[str, list[str]] = {
                "naive": [control],
                "todos": [str(c) for c in p.columns],
                "simples": [str(c) for c in p if clase_de.get(str(c)) in SIMPLES],
                "complejos": [str(c) for c in p if clase_de.get(str(c)) not in SIMPLES],
            }
            for k, cols in grupos.items():
                elegido = str(previo.loc[cols].sort_values().index[0])
                acum[k].append(float(sig.loc[elegido]))
        for k in res:
            res[k].append(float(np.mean(acum[k])))
    df = pd.DataFrame(res)
    out: dict[str, Any] = {"padecimientos": len(df)}
    for k in ("todos", "simples", "complejos"):
        out[k] = {
            "mediana": round(float(df[k].median()), 2),
            "gana_al_naive": int((df[k] < df["naive"] - 1e-9).sum()),
            "pierde_mas_10pct": int((df[k] > df["naive"] * 1.10).sum()),
        }
    out["naive_mediana"] = round(float(df["naive"].median()), 2)
    out["complejos_ganan_a_simples"] = int((df["complejos"] < df["simples"] - 1e-9).sum())
    return out


def techo_por_clase(t: pd.DataFrame, clase_de: dict[str, str]) -> dict[str, Any]:
    simples = [c for c in t if clase_de.get(str(c)) in SIMPLES]
    complejos = [c for c in t if clase_de.get(str(c)) not in SIMPLES]
    s, c = t[simples].min(axis=1), t[complejos].min(axis=1)
    ok = s.notna() & c.notna()
    gana = t.loc[ok, complejos].idxmin(axis=1)[(c < s)[ok]]
    return {
        "padecimientos": int(ok.sum()),
        "mejor_complejo_gana": int((c[ok] < s[ok]).sum()),
        "mejora_mediana_pct_cuando_gana": round(
            float(((c - s) / s)[ok & (c < s)].median() * 100), 1
        ),
        "motor_que_gana": gana.value_counts().to_dict(),
    }
