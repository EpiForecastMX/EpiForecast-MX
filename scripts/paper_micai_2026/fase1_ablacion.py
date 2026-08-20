#!/usr/bin/env python3
"""Fase 1: ablacion del pool de candidatos, sobre el paquete sellado.

Contrato (predeclarado ANTES de ver resultados):
  - mapa regional: solo de `Region Socio-Urbana` del tableau sellado; se exige 32 estados,
    una region por estado y tamanos 4/7/6/15.
  - observaciones regionales: general = suma de Casos_semana de los estados miembros;
    hombres/mujeres = incremento semanal POR ESTADO y despues suma por region.
  - pronosticos regionales: las series `Region *` explicitas. Nunca suma de estados.
  - alineacion: semana_boletin = semana_ds + 1, siempre.
  - seleccion estatica: regla publicada, banda 5% -> MASE -> RMSE, siempre sobre n=111.
  - evaluacion OOS: principal n=99 (estados + nacional), sensibilidad n=111 (con regiones).
    Se reportan las dos. No se elige denominador despues de ver el resultado.
  - dinamica: reseleccion por minimo sMAPE en W02-W11 (definicion ya auditada), puntuada
    en W12-W18. La variante con desempates completos va como sensibilidad aparte.

Uso:  ../../.venv/bin/python fase1_ablacion.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bundle
import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI.parents[1] / "reports/paper_micai_2026/resultados"
MOTORES = ["prophet", "deepar", "ensemble", "stacking"]
TAMANOS_ESPERADOS = {
    "Metropolitana alta": 4,
    "Rural / dispersa": 7,
    "Sur-Sureste vulnerable": 6,
    "Urbana media": 15,
}
CORTE = 11
VENTANA = range(2, 19)


def smape(y, f) -> float:
    y, f = np.asarray(y, float), np.asarray(f, float)
    dn = (np.abs(y) + np.abs(f)) / 2
    m = dn > 0
    return float(100 * np.mean(np.abs(y - f)[m] / dn[m])) if m.any() else np.nan


# ------------------------------------------------------------------ mapa regional
def mapa_regional() -> pd.DataFrame:
    t = bundle.tableau()
    d = t[t.padecimiento == "Depresión"].copy()
    est = d[~d.entidad.astype(str).str.startswith("Region ") & (d.entidad != "Nacional")]
    m = (
        est[["entidad", "Region Socio-Urbana"]]
        .dropna()
        .drop_duplicates()
        .rename(columns={"Region Socio-Urbana": "region"})
    )
    # --- guardas del contrato ---
    if len(m) != 32:
        raise SystemExit(f"esperaba 32 estados, hay {len(m)}")
    if m.entidad.duplicated().any():
        raise SystemExit("hay estados con mas de una region")
    tam = m.region.value_counts().to_dict()
    if tam != TAMANOS_ESPERADOS:
        raise SystemExit(f"particion inesperada: {tam} != {TAMANOS_ESPERADOS}")
    print(f"  mapa regional OK: 32 estados, {tam}")
    return m.sort_values(["region", "entidad"]).reset_index(drop=True)


# ------------------------------------------------------------------ observaciones
def observaciones(mapa: pd.DataFrame) -> pd.DataFrame:
    d = bundle.observado()
    d = d[d["Padecimiento"] == "Depresión"].copy()
    d["Entidad"] = d["Entidad"].replace({"Distrito Federal": "Ciudad de México"})
    d = d[d["Anio"] == 2026].sort_values(["Entidad", "Semana"])
    rec = []
    for e, g in d.groupby("Entidad"):
        g = g.sort_values("Semana")
        for _, r in g.iterrows():
            rec.append((e, "general", int(r["Semana"]), float(r["Casos_semana"])))
        for modo, col in [("hombres", "Acumulado_hombres"), ("mujeres", "Acumulado_mujeres")]:
            wk = np.diff(np.concatenate([[0], g[col].values]))
            for w, v in zip(g["Semana"].values, wk, strict=True):
                rec.append((e, modo, int(w), float(max(v, 0))))
    obs = pd.DataFrame(rec, columns=["entidad", "modo", "Semana", "y"])

    # nacional = suma de estados (misma politica que Fase 0)
    nat = obs.groupby(["modo", "Semana"], as_index=False)["y"].sum()
    nat["entidad"] = "Nacional"

    # regiones = suma de estados miembros, DESPUES del incremento por estado
    reg = obs.merge(mapa, on="entidad", how="inner")
    reg = reg.groupby(["region", "modo", "Semana"], as_index=False)["y"].sum()
    reg["entidad"] = "Region " + reg["region"]

    return pd.concat(
        [obs, nat[["entidad", "modo", "Semana", "y"]], reg[["entidad", "modo", "Semana", "y"]]],
        ignore_index=True,
    )


# ------------------------------------------------------------------ pronosticos
def pronosticos() -> dict[str, pd.DataFrame]:
    fcs = {}
    for m in MOTORES:
        fc = bundle.forecast(m)
        fc = fc[
            fc["meta_padecimiento"].astype(str).str.contains("epres", case=False, na=False)
        ].copy()
        fc["ds"] = pd.to_datetime(fc["ds"])
        fc = fc[fc["ds"].dt.year == 2026]
        fc["Semana"] = fc["ds"].dt.isocalendar().week.astype(int) + 1  # -> semana de boletin
        fcs[m] = (
            fc.rename(columns={"meta_entidad": "entidad", "meta_modo": "modo"})
            .groupby(["entidad", "modo", "Semana"], as_index=False)["yhat"]
            .mean()
        )
    return fcs


# ------------------------------------------------------------------ regla publicada
def elige(fila: dict, pool: tuple[str, ...]) -> str | None:
    s = {m: fila[f"{m}_smape"] for m in pool if pd.notna(fila.get(f"{m}_smape"))}
    if not s:
        return None
    orden = sorted(s, key=lambda m: s[m])
    s1 = s[orden[0]]
    if len(orden) == 1 or s[orden[1]] > 1.05 * s1:
        return orden[0]
    banda = sorted(
        [m for m in s if s[m] <= 1.05 * s1], key=lambda m: (fila[f"{m}_mase"], fila[f"{m}_rmse"])
    )
    return banda[0]


def clave_xlsx_a_forecast(entidad: str) -> str:
    return entidad.replace("region_", "Region ") if str(entidad).startswith("region_") else entidad


# ------------------------------------------------------------------ OOS por serie y modelo
def oos_por_serie(obs: pd.DataFrame, fcs: dict) -> pd.DataFrame:
    o = obs.set_index(["entidad", "modo", "Semana"])["y"]
    idx = {m: fcs[m].set_index(["entidad", "modo", "Semana"])["yhat"] for m in MOTORES}
    llaves = sorted({(e, md) for e, md, _ in o.index})
    filas = []
    for e, md in llaves:
        fila = {"entidad": e, "modo": md}
        for m in MOTORES:
            try:
                sub = idx[m].loc[(e, md)]
            except KeyError:
                fila[f"oos_{m}"] = np.nan
                continue
            semanas = [w for w in VENTANA if (e, md, w) in o.index and w in sub.index]
            fila["n_sem"] = len(semanas)
            fila[f"oos_{m}"] = (
                smape([o.loc[(e, md, w)] for w in semanas], [sub.loc[w] for w in semanas])
                if len(semanas) >= 4
                else np.nan
            )
        filas.append(fila)
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ ablacion estatica
def estatica_por_serie(cv: pd.DataFrame, oos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por serie, una columna por pool: el sMAPE OOS del modelo que ese pool elige."""
    cv = cv.copy()
    cv["clave"] = cv.entidad.map(clave_xlsx_a_forecast)
    llave = oos.set_index(["entidad", "modo"])
    pools = (
        [tuple(MOTORES)]
        + [tuple(m for m in MOTORES if m != x) for x in MOTORES]
        + [(m,) for m in MOTORES]
    )
    filas = []
    for _, f in cv.iterrows():
        k = (f["clave"], f["sexo"])
        if k not in llave.index:
            continue
        fila = {
            "entidad": f["clave"],
            "modo": f["sexo"],
            "regional": str(f["clave"]).startswith("Region "),
        }
        completo = True
        for pool in pools:
            m = elige(f, pool)
            v = llave.loc[k, f"oos_{m}"] if m else np.nan
            fila[f"OOS::{'+'.join(pool)}"] = v
            fila[f"sel::{'+'.join(pool)}"] = m
            completo &= pd.notna(v)
        if completo:
            filas.append(fila)
    return pd.DataFrame(filas)


def resume_estatica(pxs: pd.DataFrame, universo: str) -> pd.DataFrame:
    d = pxs if universo == "n111" else pxs[~pxs.regional]
    pools = [c[5:] for c in d.columns if c.startswith("OOS::")]
    ref = "prophet+deepar+ensemble+stacking"
    filas = []
    for pool in pools:
        v = d[f"OOS::{pool}"]
        p = (
            np.nan
            if pool == ref
            else float(stats.wilcoxon(v, d[f"OOS::{ref}"], zero_method="zsplit").pvalue)
        )
        filas.append(
            dict(
                pool=pool,
                k=len(pool.split("+")),
                universo=universo,
                n=len(d),
                reparto=json.dumps(
                    {k2: int(n2) for k2, n2 in d[f"sel::{pool}"].value_counts().items()},
                    ensure_ascii=False,
                ),
                mediana=float(v.median()),
                media=float(v.mean()),
                p_vs_pool_completo=p,
            )
        )
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ ablacion dinamica
def dinamica_por_serie(obs, fcs, base: dict) -> pd.DataFrame:
    """Devuelve, por serie y por pool, el sMAPE held-out de la politica de ese pool.

    Una fila por serie; una columna por pool. Asi las comparaciones entre pools son
    PAREADAS sobre las mismas series: comparar medianas del subconjunto reasignado de
    cada pool compara conjuntos distintos y no es valido.
    """
    o = obs.set_index(["entidad", "modo", "Semana"])["y"]
    idx = {m: fcs[m].set_index(["entidad", "modo", "Semana"])["yhat"] for m in MOTORES}
    pools = (
        [tuple(MOTORES)]
        + [tuple(m for m in MOTORES if m != x) for x in MOTORES]
        + [(m,) for m in MOTORES]
    )
    filas = []
    for (e, md), m_base in base.items():
        per, ok = {}, True
        for m in MOTORES:
            try:
                sub = idx[m].loc[(e, md)]
            except KeyError:
                ok = False
                break
            semanas = [w for w in VENTANA if (e, md, w) in o.index and w in sub.index]
            tempranas = [w for w in semanas if w <= CORTE]
            tardias = [w for w in semanas if w > CORTE]
            if len(tempranas) < 4 or len(tardias) < 4:
                ok = False
                break
            per[m] = (
                smape([o.loc[(e, md, w)] for w in tempranas], [sub.loc[w] for w in tempranas]),
                smape([o.loc[(e, md, w)] for w in tardias], [sub.loc[w] for w in tardias]),
            )
        if not ok or m_base not in per:
            continue
        fila = {
            "entidad": e,
            "modo": md,
            "base": m_base,
            "H_base": per[m_base][1],
            "regional": str(e).startswith("Region "),
        }
        for pool in pools:
            m_re = min(pool, key=lambda m: per[m][0])
            fila[f"H::{'+'.join(pool)}"] = per[m_re][1]
            fila[f"sel::{'+'.join(pool)}"] = m_re
        filas.append(fila)
    return pd.DataFrame(filas)


def resume_dinamica(pxs: pd.DataFrame, universo: str) -> pd.DataFrame:
    d = pxs if universo == "n111" else pxs[~pxs.regional]
    pools = [c[3:] for c in d.columns if c.startswith("H::")]
    ref = "prophet+deepar+ensemble+stacking"
    filas = []
    for pool in pools:
        h, sel = d[f"H::{pool}"], d[f"sel::{pool}"]
        rea = sel != d["base"]
        # comparacion pareada contra el pool completo, sobre las MISMAS series
        p = (
            np.nan
            if pool == ref
            else float(stats.wilcoxon(h, d[f"H::{ref}"], zero_method="zsplit").pvalue)
        )
        filas.append(
            dict(
                pool=pool,
                k=len(pool.split("+")),
                universo=universo,
                n=len(d),
                reasignadas=int(rea.sum()),
                pct_mejoran=100 * float((h[rea] < d["H_base"][rea]).mean())
                if rea.any()
                else np.nan,
                med_global_antes=float(d["H_base"].median()),
                med_global_despues=float(h.median()),
                media_global_despues=float(h.mean()),
                p_vs_pool_completo=p,
            )
        )
    return pd.DataFrame(filas)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


if __name__ == "__main__":
    SALIDA.mkdir(exist_ok=True)
    print("=" * 92)
    print("FASE 1 · ABLACION DEL POOL —", bundle.sello())
    print("=" * 92)

    mapa = mapa_regional()
    mapa.to_csv(SALIDA / "region_membership.csv", index=False)

    obs = observaciones(mapa)
    fcs = pronosticos()
    cv_all = bundle.metricas_cv()
    cv = cv_all[cv_all.padecimiento.astype(str).str.contains("epresi", na=False)].copy()
    print(f"  series con metricas CV: {len(cv)}")

    oos = oos_por_serie(obs, fcs)
    oos.to_csv(SALIDA / "oos_por_serie.csv", index=False)
    reg_ok = oos[oos.entidad.astype(str).str.startswith("Region ")]["oos_deepar"].notna().sum()
    print(
        f"  series con OOS calculable: {int(oos['oos_deepar'].notna().sum())} "
        f"(de ellas regionales: {reg_ok}/12)"
    )

    print("\n" + "=" * 92)
    print("A · ABLACION ESTATICA — seleccion por CV (n=111 siempre), evaluada fuera de muestra")
    print("=" * 92)
    pxs_e = estatica_por_serie(cv, oos)
    pxs_e.to_csv(SALIDA / "estatica_por_serie.csv", index=False)
    ests = []
    for universo in ("n99", "n111"):
        e = resume_estatica(pxs_e, universo)
        ests.append(e)
        print(f"\n  universo {universo}")
        print(f"  {'pool':<34} {'n':>4} {'mediana':>9} {'media':>8} {'p vs 4':>8}")
        for _, r in e.iterrows():
            pv = "  —" if pd.isna(r["p_vs_pool_completo"]) else f"{r['p_vs_pool_completo']:.3f}"
            print(f"  {r['pool']:<34} {r['n']:>4} {r['mediana']:>9.2f} {r['media']:>8.2f} {pv:>8}")
    est = pd.concat(ests)
    est.to_csv(SALIDA / "ablacion_estatica.csv", index=False)
    print("\n  reparto de la seleccion por pool:")
    for _, r in ests[0].iterrows():
        print(f"    {r['pool']:<34} {r['reparto']}")

    print("\n" + "=" * 92)
    print("banda · ABLACION DINAMICA — reseleccion en W02-W11, puntuada en W12-W18")
    print("   metricas GLOBALES sobre las mismas series; el % entre reasignadas es diagnostico")
    print("=" * 92)
    base = {
        (clave_xlsx_a_forecast(r["entidad"]), r["sexo"]): str(r["modelo_produccion"])
        .strip()
        .lower()
        for _, r in cv.iterrows()
    }
    pxs = dinamica_por_serie(obs, fcs, base)
    pxs.to_csv(SALIDA / "dinamica_por_serie.csv", index=False)
    dinamicas = []
    for universo in ("n99", "n111"):
        din = resume_dinamica(pxs, universo)
        dinamicas.append(din)
        print(
            f"\n  universo {universo}  (despliegue historico: mediana "
            f"{din.med_global_antes.iloc[0]:.2f})"
        )
        print(
            f"  {'politica':<34} {'n':>4} {'reasig':>7} {'%mej':>6} "
            f"{'med global':>11} {'media':>8} {'p vs 4':>8}"
        )
        for _, r in din.iterrows():
            pv = "  —" if pd.isna(r["p_vs_pool_completo"]) else f"{r['p_vs_pool_completo']:.3f}"
            pm = "   —" if pd.isna(r["pct_mejoran"]) else f"{r['pct_mejoran']:.1f}"
            print(
                f"  {r['pool']:<34} {r['n']:>4} {r['reasignadas']:>7} {pm:>6} "
                f"{r['med_global_despues']:>11.2f} {r['media_global_despues']:>8.2f} {pv:>8}"
            )
    pd.concat(dinamicas).to_csv(SALIDA / "ablacion_dinamica.csv", index=False)

    hashes = {p.name: sha(p) for p in sorted(SALIDA.glob("*.csv"))}
    (SALIDA / "HASHES.json").write_text(
        json.dumps(dict(sello=bundle.sello(), archivos=hashes), indent=2, ensure_ascii=False)
        + "\n"
    )
    print(f"\n  resultados y hashes -> {SALIDA}")
