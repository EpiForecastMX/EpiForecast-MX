#!/usr/bin/env python3
"""Fase 0, paso 2: reproducir las cifras PUBLICADAS, sin corregir nada.

Antes de tocar la alineacion de semanas hay que demostrar que el paquete sellado devuelve
exactamente lo que el paper imprimio. Si algo no cuadra aqui, el problema es el paquete y
no la alineacion, y no se sigue adelante.

Uso:  ../../.venv/bin/python fase0_reproduce.py
"""

from __future__ import annotations

import bundle
import numpy as np
import pandas as pd

MOTORES = ["deepar", "prophet", "ensemble", "stacking"]


def smape(y, f) -> float:
    y, f = np.asarray(y, float), np.asarray(f, float)
    dn = (np.abs(y) + np.abs(f)) / 2
    m = dn > 0
    return float(100 * np.mean(np.abs(y - f)[m] / dn[m]))


def veredicto(nombre: str, obtenido: float, publicado: float, tol: float) -> bool:
    ok = abs(obtenido - publicado) <= tol
    marca = "OK " if ok else "NO "
    print(f"  [{marca}] {nombre:<46} publicado {publicado:>8.2f}   obtenido {obtenido:>8.2f}")
    return ok


# --------------------------------------------------------------- Tabla 2 (validacion 2026)
def tabla2() -> list[bool]:
    print("\n== Tabla 2 · validacion prospectiva nacional, W02-W18 (Ensemble bloqueado) ==")
    b = bundle.observado()
    b = b[(b.Padecimiento == "Depresión") & (b.Anio == 2026)]
    obs = b.groupby("Semana")["Casos_semana"].sum().sort_index()

    t = bundle.tableau()
    d = t[
        (t.padecimiento == "Depresión") & (t.meta_modo == "general") & (t.entidad == "Nacional")
    ].copy()
    d["ds"] = pd.to_datetime(d.ds)
    d = d[d.ds.dt.isocalendar().year == 2026]
    d["w"] = d.ds.dt.isocalendar().week.astype(int)
    pred = d.set_index("w")["yhat_ensemble"].sort_index()

    semanas = [w for w in range(2, 19) if w in obs.index and w in pred.index]
    y, f = obs[semanas].values, pred[semanas].values
    return [
        veredicto("sMAPE (%)", smape(y, f), 6.63, 0.005),
        veredicto("desviacion acumulada (%)", 100 * (f.sum() - y.sum()) / y.sum(), 4.40, 0.005),
        veredicto("observado acumulado", y.sum(), 48300, 0.5),
        veredicto("predicho acumulado", f.sum(), 50424, 0.5),
        veredicto("MAE semanal", np.mean(np.abs(y - f)), 184, 0.5),
        veredicto("semanas evaluadas", len(semanas), 17, 0),
    ]


# --------------------------------------------------------------- conteo de seleccion
def elige(fila, pool) -> str | None:
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


def seleccion() -> list[bool]:
    print("\n== Conteo de seleccion sobre las 111 series de Depresion ==")
    d = bundle.metricas_cv()
    dep = d[d.padecimiento.astype(str).str.contains("epresi", na=False)].copy()
    print(f"  series en el paquete: {len(dep)}")

    regla = dep.apply(lambda f: elige(f, MOTORES), axis=1).value_counts().to_dict()
    print(f"  regla primaria (sMAPE 5% -> MASE -> RMSE): {regla}")

    # El XLSX historico no tiene `motor_anterior` (columna posterior al paper): el
    # despliegue de la epoca vive en `modelo_produccion`.
    desplegado = (
        dep["modelo_produccion"].astype(str).str.strip().str.lower().value_counts().to_dict()
    )
    print(f"  desplegado historico (motor_anterior):     {desplegado}")

    r = [
        veredicto("DeepAR por la regla primaria", regla.get("deepar", 0), 107, 0),
        veredicto("DeepAR desplegado (tras fallback)", desplegado.get("deepar", 0), 108, 0),
    ]
    regla_serie = dep.apply(lambda f: elige(f, MOTORES), axis=1)
    desp_serie = dep["modelo_produccion"].astype(str).str.strip().str.lower()
    dif = dep.loc[regla_serie.values != desp_serie.values]
    print(f"\n  series donde la regla y el despliegue difieren: {len(dif)}")
    for _, f in dif.iterrows():
        print(
            f"    {f['entidad']} · {f['sexo']}: regla={elige(f, MOTORES)} "
            f"desplegado={str(f['modelo_produccion']).lower()}"
        )
        print(
            f"      sMAPE stacking={f['stacking_smape']:.3f} deepar={f['deepar_smape']:.3f} "
            f"(empate, umbral {1.05 * f['stacking_smape']:.3f})"
        )
        print(
            f"      MASE  stacking={f['stacking_mase']:.3f} deepar={f['deepar_mase']:.3f}"
            f"   <- la regla del paper desempata aqui y elige Stacking"
        )
        print(
            f"      RMSE  stacking={f['stacking_rmse']:.2f} deepar={f['deepar_rmse']:.2f}"
            f"   <- produccion desempato aqui y eligio DeepAR"
        )
    return r


# --------------------------------------------------------------- held-out reseleccion
def carga_observado_por_serie() -> pd.DataFrame:
    d = bundle.observado()
    d = d[d["Padecimiento"] == "Depresión"].copy()
    d["Entidad"] = d["Entidad"].replace({"Distrito Federal": "Ciudad de México"})
    d = d[d["Anio"] == 2026].sort_values(["Entidad", "Semana"])
    rec = []
    for e, g in d.groupby("Entidad"):
        g = g.sort_values("Semana")
        for _, r in g.iterrows():
            rec.append((e, "general", int(r["Semana"]), r["Casos_semana"]))
        for modo, col in [("hombres", "Acumulado_hombres"), ("mujeres", "Acumulado_mujeres")]:
            wk = np.diff(np.concatenate([[0], g[col].values]))
            for w, v in zip(g["Semana"].values, wk, strict=True):
                rec.append((e, modo, int(w), max(v, 0)))
    obs = pd.DataFrame(rec, columns=["Entidad", "modo", "Semana", "y"])
    nat = obs.groupby(["modo", "Semana"])["y"].sum().reset_index()
    nat["Entidad"] = "Nacional"
    return pd.concat([obs, nat[["Entidad", "modo", "Semana", "y"]]], ignore_index=True)


def carga_pronosticos(desfase: int) -> dict[str, pd.DataFrame]:
    """desfase=0 reproduce el paper; desfase=1 lleva el pronostico a semanas de boletin."""
    fcs = {}
    for m in MOTORES:
        fc = bundle.forecast(m)
        fc = fc[
            fc["meta_padecimiento"].astype(str).str.contains("epres", case=False, na=False)
        ].copy()
        fc["ds"] = pd.to_datetime(fc["ds"])
        fc = fc[fc["ds"].dt.year == 2026]
        fc["Semana"] = fc["ds"].dt.isocalendar().week.astype(int) + desfase
        fcs[m] = (
            fc.rename(columns={"meta_entidad": "Entidad", "meta_modo": "modo"})
            .groupby(["Entidad", "modo", "Semana"])["yhat"]
            .mean()
            .reset_index()
        )
    return fcs


def heldout(obs, fcs, cv, corte: int) -> tuple[int, int, int, float, float]:
    filas = []
    for (e, modo), go in obs.groupby(["Entidad", "modo"]):
        yo = go.set_index("Semana")["y"]
        per, ok = {}, True
        for m in MOTORES:
            sub = fcs[m]
            sub = sub[(sub.Entidad == e) & (sub.modo == modo)].set_index("Semana")["yhat"]
            comun = [w for w in range(2, 19) if w in yo.index and w in sub.index]
            tempranas = [w for w in comun if w <= corte]
            tardias = [w for w in comun if w > corte]
            if len(tempranas) < 4 or len(tardias) < 4:
                ok = False
                break
            per[m] = (smape(yo[tempranas], sub[tempranas]), smape(yo[tardias], sub[tardias]))
        if not ok:
            continue
        mcv = cv.get((e, modo))
        if mcv not in per:
            continue
        mre = min(MOTORES, key=lambda m: per[m][0])
        filas.append(dict(reasignada=mre != mcv, H_cv=per[mcv][1], H_re=per[mre][1]))
    r = pd.DataFrame(filas)
    rea = r[r.reasignada]
    gana = int((rea.H_re < rea.H_cv).sum())
    return len(r), len(rea), gana, rea.H_cv.median(), rea.H_re.median()


def reseleccion() -> list[bool]:
    print("\n== Held-out: reseleccionar en W02-W11, puntuar en W12-W18 ==")
    obs = carga_observado_por_serie()
    d = bundle.metricas_cv()
    dep = d[d.padecimiento.astype(str).str.contains("epres", case=False, na=False)]
    cv = {
        (r["entidad"], r["sexo"]): str(r["modelo_produccion"]).strip().lower()
        for _, r in dep.iterrows()
    }
    n, nre, gana, mcv, mre = heldout(obs, carga_pronosticos(0), cv, 11)
    pct = 100 * gana / nre
    print(f"  n={n}  reasignadas={nre}  mejoran={gana}")
    return [
        veredicto("% de reasignadas que mejoran", pct, 69, 0.5),
        veredicto("mediana held-out antes (%)", mcv, 32.0, 0.05),
        veredicto("mediana held-out despues (%)", mre, 26.4, 0.05),
    ]


if __name__ == "__main__":
    print("=" * 78)
    print("FASE 0 · PASO 2 — reproducir lo publicado, SIN corregir")
    print(bundle.sello())
    print("=" * 78)
    r = tabla2() + seleccion() + reseleccion()
    print("\n" + "=" * 78)
    print(f"VEREDICTO: {sum(r)}/{len(r)} comprobaciones reproducen lo publicado")
    print("=" * 78)
    raise SystemExit(0 if all(r) else 1)
