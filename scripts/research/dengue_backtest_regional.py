#!/usr/bin/env python
"""dengue_backtest_regional.py — Backtest OOS por REGIÓN: nativo vs agregación.

Pregunta: para las 4 regiones de Dengue, ¿un modelo regional NATIVO (Prophet / NB-GLM /
DeepAR entrenado sobre la serie agregada de la región) pronostica mejor, fuera de muestra, que
la AGREGACIÓN bottom-up (sumar el pronóstico de cada estado de la región)?

Diseño leave-one-epidemic-out (honesto OOS): por cada corte se entrena SOLO con datos
anteriores al corte y se puntúa el año siguiente (52 sem). Reusa las funciones de
``dengue_backtest`` (config Dengue fiel: log1p, multiplicativo, cp=0.05; NB-GLM con ONI).
DeepAR usa el ``DeepARForecaster`` de producción (config short_series) sobre la serie truncada.

La agregación se reporta en dos brackets RÁPIDOS y deterministas: ``agg-Prophet`` (Σ Prophet por
estado) y ``agg-NBGLM`` (Σ NB-GLM por estado). Si el nativo no le gana ni al mejor bracket, la
conclusión (agregar gana) es robusta sin re-entrenar DeepAR en los 14 estados que lo usan.

Uso:
    python -m scripts.research.dengue_backtest_regional            # rápido (sin DeepAR nativo)
    python -m scripts.research.dengue_backtest_regional --deepar   # + DeepAR nativo regional
"""

from __future__ import annotations

import argparse
from datetime import date
import warnings

import pandas as pd

warnings.filterwarnings("ignore")
import logging  # noqa: E402

logging.getLogger("cmdstanpy").disabled = True

import scripts.build_dengue_gallery as G  # noqa: E402, N812
from scripts.research.dengue_backtest import evaluar, fit_nbglm, fit_prophet  # noqa: E402

from epiforecast.constants import ENTIDAD_DISPLAY  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402

CORTES = {"2019 (pico)": "2019-01-01", "2024 (pico mayor)": "2024-01-01"}
DENGUE_DATA = "data/processed/data_inegi_Dengue.csv"

_BOL: list[pd.DataFrame] = []


def _bol() -> pd.DataFrame:
    if not _BOL:
        b = cargar_boletin_dengue()
        b["Entidad"] = b["Entidad"].replace(ENTIDAD_DISPLAY)
        _BOL.append(b)
    return _BOL[0]


def _serie(sub: pd.DataFrame) -> pd.DataFrame:
    """(ds, y) semanal desde un subconjunto del boletín de Dengue."""
    g = sub.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    g = g.sort_values(["Anio", "Semana"])
    g["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(g["Anio"], g["Semana"], strict=False)
    ]
    return g.rename(columns={"Casos_semana": "y"})[["ds", "y"]].reset_index(drop=True)


def _region_members(rs: str) -> set[str]:
    return {ENTIDAD_DISPLAY.get(x, x) for x in G._region_members(rs)}


def serie_region(rs: str) -> pd.DataFrame:
    return _serie(_bol()[_bol()["Entidad"].isin(_region_members(rs))])


def serie_state(st: str) -> pd.DataFrame:
    return _serie(_bol()[_bol()["Entidad"] == st])


def fit_deepar_region(rs: str, cutoff: pd.Timestamp, periods: int) -> pd.DataFrame:
    """DeepAR nativo regional (config de producción) sobre la región truncada al corte."""
    from epiforecast.models import create_model

    dd = pd.read_csv(DENGUE_DATA)
    dd["Fecha"] = pd.to_datetime(dd["Fecha"])
    sub = dd[(dd["region_salud_mental"] == rs) & (dd["Fecha"] < cutoff)].copy()
    m = create_model("deepar", df=sub, sexo="incrementos_total", entidad=rs, padecimiento="Dengue")
    m.run()  # CV se omite (entidad != None -> skip_cv_estatal); fit final sobre la serie truncada
    fc = m.predict(periods)
    fc["ds"] = pd.to_datetime(fc["ds"])
    # DeepAR resamplea a W-MON (Lunes de FIN de periodo), desfasado del Lunes ISO de inicio que
    # usa la serie real -> el merge fallaría (n=0). Reanclar al mismo grid ISO (Lunes de inicio).
    iso = fc["ds"].dt.isocalendar()
    fc["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(y), min(int(w), 52), 1))
        for y, w in zip(iso["year"], iso["week"], strict=False)
    ]
    return fc.groupby("ds", as_index=False)["yhat"].mean()


def agg_bracket(rs: str, cutoff: pd.Timestamp, periods: int, motor: str) -> pd.DataFrame:
    """Agregación = suma del pronóstico por estado con un motor fijo (Prophet o NB-GLM).

    Estados degenerados (serie casi-cero al corte) donde el GLM no converge caen a Prophet; si
    Prophet tampoco, se omiten (aportan ~0 a la suma, coherente con 'si es 0, es 0')."""
    acc: dict[pd.Timestamp, float] = {}
    for st in sorted(_region_members(rs)):
        s = serie_state(st)
        train = s[s["ds"] < cutoff]
        if len(train) < 60:
            continue
        try:
            fc = fit_prophet(train, periods) if motor == "Prophet" else fit_nbglm(train, periods)
        except Exception:  # noqa: BLE001 — estado degenerado: fallback a Prophet
            try:
                fc = fit_prophet(train, periods)
            except Exception:  # noqa: BLE001
                continue
        for d, v in zip(fc["ds"], fc["yhat"], strict=False):
            acc[pd.Timestamp(d)] = acc.get(pd.Timestamp(d), 0.0) + float(v)
    if not acc:
        return pd.DataFrame(columns=["ds", "yhat"])
    return pd.DataFrame({"ds": list(acc), "yhat": list(acc.values())}).sort_values("ds")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deepar", action="store_true", help="incluir DeepAR nativo regional (lento)")
    args = ap.parse_args()

    filas = []
    for _folder, data_n, rs in G.DENGUE_REGIONES:
        reg = serie_region(rs)
        for nombre, corte in CORTES.items():
            c = pd.Timestamp(corte)
            train = reg[reg["ds"] < c]
            real = reg[(reg["ds"] >= c) & (reg["ds"] < c + pd.Timedelta(weeks=52))]
            if len(train) < 60 or real.empty:
                continue

            def _safe(fn: object, _t: pd.DataFrame = train, _rs: str = rs, _c: pd.Timestamp = c):
                try:
                    return fn(_t, _rs, _c)
                except Exception as e:  # noqa: BLE001
                    print(f"    ! {e}")
                    return pd.DataFrame(columns=["ds", "yhat"])

            metodos = [
                ("nativo Prophet", _safe(lambda t, *_: fit_prophet(t, 52))),
                ("nativo NB-GLM", _safe(lambda t, *_: fit_nbglm(t, 52))),
                ("agg-Prophet", _safe(lambda _t, r, cc: agg_bracket(r, cc, 52, "Prophet"))),
                ("agg-NBGLM", _safe(lambda _t, r, cc: agg_bracket(r, cc, 52, "NBGLM"))),
            ]
            if args.deepar:
                metodos.insert(
                    2, ("nativo DeepAR", _safe(lambda _t, r, cc: fit_deepar_region(r, cc, 52)))
                )
            for etiqueta, pred in metodos:
                r = evaluar(real, pred, etiqueta)
                r["region"] = data_n
                r["corte"] = nombre
                filas.append(r)
            print(f"  ✓ {data_n} · {nombre}")

    out = pd.DataFrame(filas)
    cols = [
        "region",
        "corte",
        "modelo",
        "n",
        "SMAPE",
        "MAE",
        "pico_real",
        "pico_pred",
        "ratio_pico",
    ]
    out = out[[c for c in cols if c in out.columns]]
    pd.set_option("display.width", 160, "display.max_columns", 20)
    print("\n" + out.to_string(index=False))
    print("\nSMAPE medio por método (menor es mejor):")
    print(out.groupby("modelo")["SMAPE"].mean().round(1).sort_values().to_string())
    print("\nMAE medio por método (menor es mejor):")
    print(out.groupby("modelo")["MAE"].mean().round(0).sort_values().to_string())
    out.to_csv("reports/ProdDetails/backtest_regional_dengue.csv", index=False)
    print("\n→ reports/ProdDetails/backtest_regional_dengue.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
