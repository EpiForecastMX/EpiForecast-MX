"""Preparación de comparaciones del banco: emparejamiento por pliegue, familias y estratos.

Correcciones de la mesa de expertos (22-nov-2026):
- Cada par (motor, referencia) se compara sólo en los pliegues completos en ambos; un padecimiento
  donde el motor es idéntico a la referencia en todos sus pliegues es «no aplica», no un empate.
- Los titulares se dan sobre la intersección común de padecimientos y pliegues.
- Familias de Holm separadas: confirmatoria (ronda 1, diseñada antes de ver resultados) y
  exploratoria (ronda 2 y combinaciones, construidas después de ver la ronda 1).
- MAE relativo al naive con media geométrica (comparable entre padecimientos de distinta escala).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from epiforecast.banco import estadistica, motores

RONDA_1 = set(motores.MOTORES) | {"lgbm_global_directo"}
CLONES = {"topdown_media52_nacional": "media_52s"}  # mismo nacional exacto: fuera de rankings


def ronda(engine: str) -> int:
    return 1 if engine in RONDA_1 else 2


def completos(met: pd.DataFrame) -> pd.DataFrame:
    m = met[met["completo"] & np.isfinite(met["smape_nacional"])]
    out: pd.DataFrame = m.set_index(["disease_id", "fold", "engine"]).sort_index()
    return out


def pares(m: pd.DataFrame, a: str, b: str, col: str = "smape_nacional") -> pd.DataFrame:
    """Por padecimiento: media de ``col`` en los pliegues completos de ``a`` y ``b`` a la vez."""
    wide = m[col].unstack("engine")
    if a not in wide or b not in wide:
        return pd.DataFrame(columns=["a", "b", "pliegues", "identico"])
    w = wide[[a, b]].dropna()
    w = w.rename(columns={a: "a", b: "b"})
    w["igual"] = np.isclose(w["a"], w["b"], rtol=0, atol=1e-9)
    g = w.groupby(level="disease_id")
    out = g[["a", "b"]].mean()
    out["pliegues"] = g.size()
    out["identico"] = g["igual"].all()
    return out


def mae_relativo(m: pd.DataFrame, a: str, b: str) -> dict[str, float]:
    """Media geométrica de MAE_a / MAE_b por padecimiento × pliegue emparejado."""
    w = m["mae_nacional"].unstack("engine")
    if a not in w or b not in w:
        return {"mae_rel_geo": np.nan, "pliegues": 0}
    r = (w[a] / w[b]).replace([np.inf, -np.inf], np.nan).dropna()
    r = r[r > 0]
    return {"mae_rel_geo": float(np.exp(np.log(r).mean())), "pliegues": int(len(r))}


def contra(m: pd.DataFrame, ref: str, motores_: list[str], col: str) -> pd.DataFrame:
    filas = []
    for e in motores_:
        if e == ref:
            continue
        p = pares(m, e, ref, col)
        no_aplica = int(p["identico"].sum())
        p = p[~p["identico"]]
        a, b = p["a"].to_numpy(), p["b"].to_numpy()
        fila: dict[str, Any] = {"engine": e, "ronda": ronda(e), "no_aplica": no_aplica}
        fila |= {f"wilcoxon_{k}": v for k, v in estadistica.wilcoxon_pareado(a, b).items()}
        fila |= {f"signo_{k}": v for k, v in estadistica.prueba_signo(a, b).items()}
        fila |= estadistica.bootstrap_mejora(a, b)
        fila["peor_mas_10pct"] = int((a > b * 1.10).sum())
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = (a / b - 1) * 100 if len(a) else np.array([np.nan])
        fila |= {f"q{q}_pct": float(np.percentile(rel, q)) for q in (10, 50, 90)}
        fila |= mae_relativo(m, e, ref)
        filas.append(fila)
    df = pd.DataFrame(filas)
    df["familia"] = np.where(df["ronda"] == 1, "confirmatoria", "exploratoria")
    df["p_holm"] = np.nan
    for _, idx in df[df["wilcoxon_p"].notna()].groupby("familia").groups.items():
        df.loc[idx, "p_holm"] = estadistica.holm(df.loc[idx, "wilcoxon_p"].tolist())
    sig = df["p_holm"] < 0.05
    df["veredicto"] = np.select(
        [sig & (df["wilcoxon_r_rb"] < 0), sig & (df["wilcoxon_r_rb"] > 0)],
        ["mejor", "peor"],
        default="sin diferencia",
    )
    return df.sort_values(["familia", "mediana_pct"]).reset_index(drop=True)


def interseccion(m: pd.DataFrame, motores_: list[str]) -> pd.DataFrame:
    """Padecimiento × pliegue completos en todos los motores; media por padecimiento."""
    wide = m["smape_nacional"].unstack("engine")[motores_].dropna()
    return wide.groupby(level="disease_id").mean()


def por_pliegue(m: pd.DataFrame, ref: str, motores_: list[str]) -> pd.DataFrame:
    """Mediana de la mejora y victorias por año de desarrollo (consistencia entre años)."""
    wide = m["smape_nacional"].unstack("engine")
    filas = []
    for e in motores_:
        if e not in wide or e == ref:
            continue
        w = wide[[e, ref]].dropna()
        for fold, g in w.groupby(level="fold"):
            a, b = g[e].to_numpy(), g[ref].to_numpy()
            r = estadistica.wilcoxon_pareado(a, b)
            filas.append(
                {
                    "engine": e,
                    "fold": int(str(fold)),
                    "padecimientos": len(g),
                    "mediana_pct": float(np.median((a / b - 1) * 100)),
                    "gana": int((a < b).sum()),
                    "wilcoxon_p": r["p"],
                    "r_rb": r["r_rb"],
                }
            )
    return pd.DataFrame(filas)


def por_estrato(
    m: pd.DataFrame, ref: str, motores_: list[str], estrato: pd.Series
) -> pd.DataFrame:
    filas = []
    for e in motores_:
        p = pares(m, e, ref)
        p = p[~p["identico"]].join(estrato.rename("estrato"), how="inner")
        for s, g in p.groupby("estrato"):
            r = (g["a"] / g["b"] - 1) * 100
            filas.append(
                {
                    "engine": e,
                    "estrato": s,
                    "padecimientos": len(g),
                    "mediana_pct": float(r.median()),
                    "gana": int((g["a"] < g["b"]).sum()),
                    "peor_mas_10pct": int((r > 10).sum()),
                    "wilcoxon_p": estadistica.wilcoxon_pareado(
                        g["a"].to_numpy(), g["b"].to_numpy()
                    )["p"],
                }
            )
    return pd.DataFrame(filas)


def victorias_descriptivas(m: pd.DataFrame, ref: str, motores_: list[str]) -> pd.DataFrame:
    """Sustituye a Diebold-Mariano: proporción de pliegues con menor MAE nacional (descriptivo)."""
    w = m["mae_nacional"].unstack("engine")
    filas = []
    for e in motores_:
        if e not in w or e == ref:
            continue
        x = w[[e, ref]].dropna()
        filas.append(
            {
                "engine": e,
                "pliegues": len(x),
                "menor_mae": int((x[e] < x[ref]).sum()),
                "proporcion": float((x[e] < x[ref]).mean()),
            }
        )
    return pd.DataFrame(filas)


def wape_bases(banco_tareas: Any, motores_: list[str]) -> pd.DataFrame:
    """WAPE de las 64 series base por padecimiento × pliegue: Σ|y - ŷ| / Σy (en %).

    Complementa al sMAPE de bases, que castiga con 200 cada semana con cero observado y
    pronóstico positivo: el WAPE pesa por volumen y no explota en series con muchos ceros.
    """
    import json as _json
    from pathlib import Path as _Path

    filas = []
    for motor in motores_:
        for f in sorted(_Path(banco_tareas).glob(f"*__{motor}.parquet")):
            info = _json.loads(f.with_suffix(".json").read_text())
            fallidos = {x["fold"] for x in info["fallos"]}
            df = pd.read_parquet(f)
            df = df[~df["fold"].isin(fallidos)]
            df["abs"] = (df["y_pred"] - df["y_true"]).abs()
            g = df.groupby("fold")[["abs", "y_true"]].sum()
            for fold, r in g.iterrows():
                filas.append(
                    {
                        "disease_id": info["disease_id"],
                        "fold": int(str(fold)),
                        "engine": motor,
                        "completo": True,
                        "smape_nacional": 100 * r["abs"] / max(r["y_true"], 1e-9),
                        "mae_nacional": r["abs"],
                        "smape_bases": np.nan,
                    }
                )
    return pd.DataFrame(filas)
