#!/usr/bin/env python3
"""Fase 4: materializar TODAS las cifras de la seccion de validacion, publicadas y
corregidas, desde el paquete sellado.

Regla de la fase: nada se edita en el paper hasta que este script emita el juego
completo y demuestre que, con la alineacion publicada, reproduce lo impreso.

Ventana: W02-W18. Alineacion corregida: semana_boletin = semana_ds + 1.
Motores bloqueados a nivel nacional: general -> Ensemble, mujeres -> Ensemble,
hombres -> Prophet.

Uso:  .venv/bin/python scripts/paper_micai_2026/fase4_cifras.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bundle  # noqa: E402

SALIDA = Path(__file__).resolve().parents[1].parent / "reports/paper_micai_2026"
MOTORES = ["prophet", "deepar", "ensemble", "stacking"]
BLOQUEADO = {"general": "ensemble", "mujeres": "ensemble", "hombres": "prophet"}
RMSE_CV = {"general": 372.23, "mujeres": 239.42, "hombres": 101.44}
VENTANA = list(range(2, 19))


def smape(y, f) -> float:
    y, f = np.asarray(y, float), np.asarray(f, float)
    return float(100 * np.mean(np.abs(y - f) / ((np.abs(y) + np.abs(f)) / 2)))


def desviacion_poisson(y, f) -> float:
    """Devianza media de Poisson: metrica apropiada para conteos."""
    y, f = np.asarray(y, float), np.asarray(f, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(y > 0, y * np.log(y / f), 0.0)
    return float(np.mean(2 * (t - (y - f))))


def dm_hln(y, f1, f2, h: int = 1) -> tuple[float, float, int]:
    """Diebold-Mariano con la correccion de muestra pequena de Harvey-Leybourne-Newbold."""
    y, f1, f2 = np.asarray(y, float), np.asarray(f1, float), np.asarray(f2, float)
    d = (y - f1) ** 2 - (y - f2) ** 2
    n = len(d)
    dbar = d.mean()
    gamma0 = np.sum((d - dbar) ** 2) / n
    var = gamma0
    for k in range(1, h):
        gk = np.sum((d[k:] - dbar) * (d[:-k] - dbar)) / n
        var += 2 * (1 - k / h) * gk
    dm = dbar / np.sqrt(var / n)
    corr = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    est = dm * corr
    p = 2 * (1 - stats.t.cdf(abs(est), df=n - 1))
    return float(est), float(p), int(n)


# ------------------------------------------------------------------ series nacionales
def observado_nacional() -> dict[str, pd.Series]:
    d = bundle.observado()
    d = d[(d.Padecimiento == "Depresión") & (d.Anio == 2026)].copy()
    d["Entidad"] = d["Entidad"].replace({"Distrito Federal": "Ciudad de México"})
    out = {"general": d.groupby("Semana")["Casos_semana"].sum().sort_index()}
    for modo, col in [("hombres", "Acumulado_hombres"), ("mujeres", "Acumulado_mujeres")]:
        filas = []
        for _e, g in d.sort_values("Semana").groupby("Entidad"):
            wk = np.diff(np.concatenate([[0], g[col].values]))
            filas += [(int(s), max(v, 0)) for s, v in zip(g["Semana"].values, wk, strict=True)]
        out[modo] = pd.DataFrame(filas, columns=["Semana", "y"]).groupby("Semana")["y"].sum()
    return out


def pronostico_nacional(desfase: int) -> dict[str, dict[str, pd.Series]]:
    """{modo: {motor: serie}} en semanas de boletin si desfase=1."""
    t = bundle.tableau()
    d = t[(t.padecimiento == "Depresión") & (t.entidad == "Nacional")].copy()
    d["ds"] = pd.to_datetime(d.ds)
    d = d[d.ds.dt.isocalendar().year == 2026]
    d["w"] = d.ds.dt.isocalendar().week.astype(int) + desfase
    out = {}
    for modo in ("general", "mujeres", "hombres"):
        sub = d[d.meta_modo == modo]
        out[modo] = {m: sub.set_index("w")[f"yhat_{m}"].sort_index() for m in MOTORES}
    return out


def reconciliado(pron: dict, semanas: list[int]) -> pd.Series:
    """MinT WLS diagonal sobre los tres estratos nacionales bloqueados."""
    base = np.vstack(
        [
            pron[modo][BLOQUEADO[modo]].reindex(semanas).to_numpy(float)
            for modo in ("general", "mujeres", "hombres")
        ]
    )
    # w_mat/s_mat/g_mat son W, S y G en la notacion de MinT (Wickramasuriya et al.)
    w_mat = np.diag([RMSE_CV[m] ** 2 for m in ("general", "mujeres", "hombres")])
    w_inv = np.linalg.inv(w_mat)
    s_mat = np.array([[1, 1], [1, 0], [0, 1]], float)
    g_mat = np.linalg.inv(s_mat.T @ w_inv @ s_mat) @ s_mat.T @ w_inv
    rec = s_mat @ (g_mat @ base)
    return pd.Series(rec[0], index=semanas)


def cobertura(obs_g: pd.Series, pron_g: pd.Series, semanas: list[int], desfase: int) -> dict:
    """Intervalo empirico al 80 %: percentiles 10/90 de los residuales post-2021.

    La fila `Nacional` de tableau no trae observado, asi que el historico sale del
    boletin y se cruza con el pronostico nacional bajo LA MISMA alineacion que el
    resto del juego -- si no, el intervalo se calibraria con un desfase distinto al
    que se esta evaluando.
    """
    b = bundle.observado()
    b = b[b.Padecimiento == "Depresión"].copy()
    b = b[(b.Anio >= 2021) & (b.Anio <= 2025)]
    hist_obs = b.groupby(["Anio", "Semana"])["Casos_semana"].sum()

    t = bundle.tableau()
    d = t[
        (t.padecimiento == "Depresión") & (t.entidad == "Nacional") & (t.meta_modo == "general")
    ].copy()
    d["ds"] = pd.to_datetime(d.ds)
    iso = d.ds.dt.isocalendar()
    d["anio"] = iso.year.astype(int)
    d["w"] = iso.week.astype(int) + desfase
    d = d[(d.anio >= 2021) & (d.anio <= 2025)]
    hist_pred = d.set_index(["anio", "w"])["yhat_ensemble"]

    comun = hist_obs.index.intersection(hist_pred.index)
    res = (hist_obs.loc[comun] - hist_pred.loc[comun]).dropna().to_numpy(float)
    if res.size == 0:
        raise SystemExit("sin residuales historicos: revisar el cruce")
    lo, hi = np.percentile(res, [10, 90])
    y = obs_g.reindex(semanas).to_numpy(float)
    f = pron_g.reindex(semanas).to_numpy(float)
    dentro = int(np.sum((y >= f + lo) & (y <= f + hi)))
    return {
        "dentro": dentro,
        "de": len(semanas),
        "pct": round(100 * dentro / len(semanas), 1),
        "n_residuales": int(res.size),
    }


def juego(desfase: int) -> dict:
    obs = observado_nacional()
    pron = pronostico_nacional(desfase)
    g_obs = obs["general"]
    g_pred = pron["general"][BLOQUEADO["general"]]
    sem = [w for w in VENTANA if w in g_obs.index and w in g_pred.index]
    y = g_obs.reindex(sem).to_numpy(float)
    f = g_pred.reindex(sem).to_numpy(float)
    rec = reconciliado(pron, sem).to_numpy(float)
    dev = 100 * (f - y) / y

    dm = {}
    for m in ("deepar", "prophet", "stacking"):
        est, p, n = dm_hln(y, f, pron["general"][m].reindex(sem).to_numpy(float))
        dm[f"ensemble_vs_{m}"] = {"DM_HLN": round(est, 3), "p": round(p, 3), "n": n}

    filas = []
    for w in [1, *sem]:
        yy = float(g_obs.get(w, np.nan))
        ff = float(g_pred.get(w, np.nan))
        rr = float(rec[sem.index(w)]) if w in sem else None
        filas.append(
            {
                "semana": w,
                "obs": yy,
                "pred": ff,
                "recon": rr,
                "dev_pct": round(100 * (ff - yy) / yy, 1) if yy else None,
            }
        )

    return {
        "alineacion": "publicada (ds=w)" if desfase == 0 else "corregida (ds=w+1)",
        "ventana": f"W{sem[0]:02d}-W{sem[-1]:02d}",
        "n_semanas": len(sem),
        "tabla2": filas,
        "smape_pct": round(smape(y, f), 2),
        "mae": round(float(np.mean(np.abs(y - f))), 1),
        "desviacion_acumulada_pct": round(float(100 * (f.sum() - y.sum()) / y.sum()), 2),
        "obs_acumulado": int(y.sum()),
        "pred_acumulado": int(round(f.sum())),
        "recon_acumulado": int(round(rec.sum())),
        "desviacion_acumulada_recon_pct": round(float(100 * (rec.sum() - y.sum()) / y.sum()), 1),
        "mediana_abs_dev_semanal_pct": round(float(np.median(np.abs(dev))), 1),
        "peor_semana": int(sem[int(np.argmax(np.abs(dev)))]),
        "peor_dev_pct": round(float(dev[int(np.argmax(np.abs(dev)))]), 1),
        "smape_ultimas4_pct": round(smape(y[-4:], f[-4:]), 1),
        "poisson_deviance": {
            m: round(desviacion_poisson(y, pron["general"][m].reindex(sem).to_numpy(float)), 1)
            for m in MOTORES
        },
        "diebold_mariano": dm,
        "cobertura_80": cobertura(g_obs, g_pred, sem, desfase),
    }


if __name__ == "__main__":
    print("=" * 78)
    print("FASE 4 · CIFRAS COMPLETAS —", bundle.sello())
    print("=" * 78)
    res = {"publicada": juego(0), "corregida": juego(1)}

    # Cifras por serie y de reseleccion: salen de Fase 1, sobre el mismo paquete y la
    # misma alineacion. Se copian aqui para que el paper tenga UNA sola fuente.
    f1 = SALIDA / "resultados"
    est = pd.read_csv(f1 / "ablacion_estatica.csv")
    din = pd.read_csv(f1 / "ablacion_dinamica.csv")
    oos = pd.read_csv(f1 / "oos_por_serie.csv")
    reg = oos.entidad.astype(str).str.startswith("Region ")
    res["por_serie"] = {
        "ventana": "W02-W18",
        "alineacion": "corregida (ds=w+1)",
        "mediana_oos_n99": {
            m: round(float(oos.loc[~reg, f"oos_{m}"].median()), 2) for m in MOTORES
        },
        "mediana_oos_n111": {m: round(float(oos[f"oos_{m}"].median()), 2) for m in MOTORES},
        "n99": int((~reg).sum()),
        "n111": int(len(oos)),
    }
    pool = "prophet+deepar+ensemble+stacking"
    res["reseleccion"] = {
        d["universo"]: {
            k: d[k]
            for k in ("n", "reasignadas", "pct_mejoran", "med_global_antes", "med_global_despues")
        }
        for d in din[din.pool == pool].round(2).to_dict("records")
    }
    res["ablacion_estatica_n99"] = (
        est[est.universo == "n99"][["pool", "mediana", "media", "p_vs_pool_completo"]]
        .round(3)
        .to_dict("records")
    )

    pub = res["publicada"]
    controles = [
        ("sMAPE", pub["smape_pct"], 6.63),
        ("desv. acum.", pub["desviacion_acumulada_pct"], 4.40),
        ("obs acum.", pub["obs_acumulado"], 48300),
        ("pred acum.", pub["pred_acumulado"], 50424),
        ("MAE", pub["mae"], 184.1),
        ("DM vs deepar", pub["diebold_mariano"]["ensemble_vs_deepar"]["DM_HLN"], -1.515),
        ("p vs deepar", pub["diebold_mariano"]["ensemble_vs_deepar"]["p"], 0.149),
        ("p vs prophet", pub["diebold_mariano"]["ensemble_vs_prophet"]["p"], 0.101),
        ("p vs stacking", pub["diebold_mariano"]["ensemble_vs_stacking"]["p"], 0.026),
    ]
    print("\n== Control: ¿la alineacion publicada reproduce lo impreso? ==")
    ok = True
    for nom, got, esp in controles:
        bien = abs(float(got) - float(esp)) <= (0.51 if abs(esp) > 100 else 0.011)
        ok &= bien
        print(f"  [{'OK ' if bien else 'NO '}] {nom:<16} impreso {esp:>10}   obtenido {got:>10}")

    print("\n== Publicado vs corregido ==")
    p, c = res["publicada"], res["corregida"]
    for k in (
        "smape_pct",
        "desviacion_acumulada_pct",
        "mae",
        "pred_acumulado",
        "recon_acumulado",
        "desviacion_acumulada_recon_pct",
        "mediana_abs_dev_semanal_pct",
        "peor_semana",
        "peor_dev_pct",
        "smape_ultimas4_pct",
    ):
        print(f"  {k:<34} {p[k]:>12} {c[k]:>12}")
    print(f"  {'poisson_deviance':<34} {json.dumps(p['poisson_deviance'])}")
    print(f"  {'':<34} {json.dumps(c['poisson_deviance'])}")
    print(
        f"  {'cobertura_80':<34} {json.dumps(p['cobertura_80'])}  {json.dumps(c['cobertura_80'])}"
    )
    for k in p["diebold_mariano"]:
        print(
            f"  {k:<34} {json.dumps(p['diebold_mariano'][k])}  ->  {json.dumps(c['diebold_mariano'][k])}"
        )

    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "fase4_cifras.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    print(f"\n  juego completo -> {SALIDA / 'fase4_cifras.json'}")
    raise SystemExit(0 if ok else 1)
