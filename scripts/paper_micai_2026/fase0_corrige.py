#!/usr/bin/env python3
"""Fase 0, paso 3: aplicar semana_boletin = semana_ds + 1 y medir el efecto.

Corre SIEMPRE sobre el paquete sellado. Imprime lado a lado lo publicado y lo corregido
para cada cifra que el paper afirma en la seccion de validacion.

Uso:  ../../.venv/bin/python fase0_corrige.py
"""

from __future__ import annotations

import bundle
from fase0_reproduce import carga_observado_por_serie, carga_pronosticos, heldout, smape
import numpy as np
import pandas as pd


def tabla2(desfase: int):
    b = bundle.observado()
    b = b[(b.Padecimiento == "Depresión") & (b.Anio == 2026)]
    obs = b.groupby("Semana")["Casos_semana"].sum().sort_index()
    t = bundle.tableau()
    d = t[
        (t.padecimiento == "Depresión") & (t.meta_modo == "general") & (t.entidad == "Nacional")
    ].copy()
    d["ds"] = pd.to_datetime(d.ds)
    d = d[d.ds.dt.isocalendar().year == 2026]
    # el pronostico guardado en ds de semana N corresponde al boletin de la semana N+desfase
    d["w"] = d.ds.dt.isocalendar().week.astype(int) + desfase
    pred = d.set_index("w")["yhat_ensemble"].sort_index()
    semanas = [w for w in range(2, 19) if w in obs.index and w in pred.index]
    y, f = obs[semanas].values, pred[semanas].values
    dev = 100 * (f - y) / y
    return dict(
        semanas=semanas,
        y=y,
        f=f,
        smape=smape(y, f),
        acum=100 * (f.sum() - y.sum()) / y.sum(),
        mae=float(np.mean(np.abs(y - f))),
        obs=y.sum(),
        pred=f.sum(),
        dentro=int((np.abs(dev) <= 5).sum()),
        peor_sem=semanas[int(np.abs(dev).argmax())],
        peor=float(np.abs(dev).max()),
        dev=dev,
    )


def linea(nombre, a, b, fmt="{:.2f}"):
    print(f"  {nombre:<34} {fmt.format(a):>12} {fmt.format(b):>12}")


if __name__ == "__main__":
    print("=" * 74)
    print("FASE 0 · PASO 3 — efecto de semana_boletin = semana_ds + 1")
    print(bundle.sello())
    print("=" * 74)

    p, c = tabla2(0), tabla2(1)
    print("\n== Tabla 2 · nacional general, W02-W18 ==")
    print(f"  {'':<34} {'publicado':>12} {'corregido':>12}")
    linea("sMAPE (%)", p["smape"], c["smape"])
    linea("desviacion acumulada (%)", p["acum"], c["acum"])
    linea("MAE semanal (casos)", p["mae"], c["mae"])
    linea("observado acumulado", p["obs"], c["obs"], "{:.0f}")
    linea("predicho acumulado", p["pred"], c["pred"], "{:.0f}")
    linea("semanas dentro de +-5%", p["dentro"], c["dentro"], "{:.0f}")
    linea(
        f"mayor desviacion (semanas{p['peor_sem']}/semanas{c['peor_sem']})", p["peor"], c["peor"]
    )
    print("\n  comparador CV del mismo estrato: 8.75 %")
    print(
        f"  ¿el error OOS sigue por debajo del de CV?  publicado: "
        f"{'si' if p['smape'] < 8.75 else 'NO'}   corregido: {'si' if c['smape'] < 8.75 else 'NO'}"
    )
    print(
        f"  ¿la desviacion acumulada sigue dentro de +-5 %?  publicado: "
        f"{'si' if abs(p['acum']) <= 5 else 'NO'}   corregido: {'si' if abs(c['acum']) <= 5 else 'NO'}"
    )

    print("\n  semana a semana (desviacion %):")
    print(
        f"  {'sem':<5} {'obs':>7} {'pred pub':>10} {'dev pub':>9} {'pred corr':>11} {'dev corr':>10}"
    )
    for i, w in enumerate(p["semanas"]):
        print(
            f"  semanas{w:02d}   {p['y'][i]:>7.0f} {p['f'][i]:>10.0f} {p['dev'][i]:>8.1f}% "
            f"{c['f'][i]:>11.0f} {c['dev'][i]:>9.1f}%"
        )

    print("\n== Held-out: reseleccion en W02-W11, puntuacion en W12-W18 ==")
    obs = carga_observado_por_serie()
    d = bundle.metricas_cv()
    dep = d[d.padecimiento.astype(str).str.contains("epres", case=False, na=False)]
    cv = {
        (r["entidad"], r["sexo"]): str(r["modelo_produccion"]).strip().lower()
        for _, r in dep.iterrows()
    }
    print(f"  {'':<34} {'publicado':>12} {'corregido':>12}")
    res = {}
    for etiqueta, desf in (("publicado", 0), ("corregido", 1)):
        res[etiqueta] = heldout(obs, carga_pronosticos(desf), cv, 11)
    (n0, r0, g0, a0, b0), (n1, r1, g1, a1, b1) = res["publicado"], res["corregido"]
    linea("series evaluadas (n)", n0, n1, "{:.0f}")
    linea("reasignadas", r0, r1, "{:.0f}")
    linea("de esas, mejoran", g0, g1, "{:.0f}")
    linea("% que mejoran", 100 * g0 / r0, 100 * g1 / r1)
    linea("mediana held-out antes (%)", a0, a1)
    linea("mediana held-out despues (%)", b0, b1)
    print("\n" + "=" * 74)
