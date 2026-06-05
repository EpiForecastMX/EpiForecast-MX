#!/usr/bin/env python
"""dengue_bridge2014.py — ¿Ayuda extender la serie de Dengue a 2014?

Compara, con MÉTRICA CONSISTENTE (leave-one-epidemic-out), el Prophet+ENSO actual
(entrenado solo en 2018-2026) contra uno entrenado en la serie PUENTEADA 2014-2026
(A90/A91 confirmado 2014-2018 + A97.x 2018-2026) con un indicador de régimen que
absorbe el cambio de definición/nivel (~2x). La historia 2014+ además habilita un
backtest del pico 2019 (que con la serie corta se salta por falta de historia previa).

Uso:
    python -m scripts.research.dengue_bridge2014
"""

from __future__ import annotations

from datetime import date
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import logging  # noqa: E402

logging.getLogger("cmdstanpy").disabled = True

from epiforecast.data import enso  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402

A9091 = "data/interim/dengue_a90a91_nacional.csv"
SEAM = pd.Timestamp(date.fromisocalendar(2018, 27, 1))  # 2018-W27: inicio A97.x


def serie_a97() -> pd.DataFrame:
    """Serie nacional A97.x 2018-2026 (ds lunes ISO, y conteos)."""
    df = cargar_boletin_dengue()
    g = df.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    g["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(g["Anio"], g["Semana"], strict=False)
    ]
    return g.rename(columns={"Casos_semana": "y"})[["ds", "y"]].sort_values("ds")


def serie_a9091_weekly() -> pd.DataFrame:
    """A90/A91 confirmado 2014-2018: acumulado dentro del año -> semanal (diff)."""
    a = pd.read_csv(A9091)
    a = a.sort_values(["Anio", "Semana"])
    a["y"] = a.groupby("Anio")["confirmado_acum_nacional"].diff()
    a["y"] = a["y"].fillna(a["confirmado_acum_nacional"]).clip(lower=0)  # W1 = primer acumulado
    a["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(yr), min(int(s), 52), 1))
        for yr, s in zip(a["Anio"], a["Semana"], strict=False)
    ]
    return a[["ds", "y"]].sort_values("ds")


def serie_puenteada() -> pd.DataFrame:
    """Serie 2014-2026 = A90/A91 (hasta < seam) + A97.x (>= seam), con regime 0/1."""
    old = serie_a9091_weekly()
    old = old[old["ds"] < SEAM]
    new = serie_a97()
    new = new[new["ds"] >= SEAM]
    s = pd.concat([old, new], ignore_index=True).drop_duplicates("ds").sort_values("ds")
    s["regime"] = (s["ds"] >= SEAM).astype(float)
    return s.reset_index(drop=True)


def _fit(train: pd.DataFrame, periods: int, use_regime: bool):
    """Prophet (log1p, multiplicativa, cp=0.05) + ONI (deploy) [+ regime si bridged]."""
    from prophet import Prophet

    cutoff = train["ds"].max()
    t = train.copy()
    t["y"] = np.log1p(t["y"].clip(lower=0))
    t["oni"] = enso.oni_for_dates(t["ds"], as_of=cutoff)
    m = Prophet(
        growth="linear",
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10.0,
    )
    m.add_seasonality(name="yearly", period=365.25, fourier_order=10)
    m.add_regressor("oni")
    cols = ["ds", "y", "oni"]
    if use_regime:
        m.add_regressor("regime", mode="additive")  # absorbe el salto de nivel/definición
        cols.append("regime")
    np.random.seed(42)
    m.fit(t[cols])
    fut = m.make_future_dataframe(periods=periods, freq="W-MON")
    fut["oni"] = enso.oni_for_dates(fut["ds"], as_of=cutoff)
    if use_regime:
        fut["regime"] = 1.0  # el futuro está en el régimen A97.x
    fc = m.predict(fut)
    fc["yhat"] = np.expm1(fc["yhat"]).clip(lower=0)
    return fc[["ds", "yhat"]].tail(periods).reset_index(drop=True)


def smape(r: np.ndarray, p: np.ndarray) -> float:
    d = (np.abs(r) + np.abs(p)) / 2
    e = np.where(d == 0, 0.0, np.abs(r - p) / d)
    return float(np.mean(e) * 100)


def evaluar(real: pd.DataFrame, pred: pd.DataFrame, etq: str, corte: str) -> dict:
    m = real.merge(pred, on="ds", how="inner")
    if m.empty:
        return {"corte": corte, "modelo": etq, "n": 0}
    r, p = m["y"].to_numpy(float), m["yhat"].to_numpy(float)
    return {
        "corte": corte,
        "modelo": etq,
        "n": len(m),
        "SMAPE": round(smape(r, p), 1),
        "MAE": round(float(np.mean(np.abs(r - p))), 1),
        "pico_real": int(r.max()),
        "pico_pred": int(p.max()),
        "ratio_pico": round(p.max() / r.max(), 2) if r.max() > 0 else None,
    }


def main() -> int:
    a97 = serie_a97().reset_index(drop=True)
    bridged = serie_puenteada()
    print(f"A97.x: {len(a97)} sem ({a97.ds.min().date()}..{a97.ds.max().date()})")
    print(
        f"Puenteada: {len(bridged)} sem ({bridged.ds.min().date()}..{bridged.ds.max().date()})\n"
    )

    cortes = {"2019 (pico)": "2019-01-01", "2023": "2023-01-01", "2024 (pico)": "2024-01-01"}
    filas = []
    for nombre, c in cortes.items():
        cc = pd.Timestamp(c)
        real = a97[(a97.ds >= cc) & (a97.ds < cc + pd.Timedelta(weeks=52))]
        if real.empty:
            continue
        # Modelo A: solo 2018-2026 (actual). Modelo B: puenteado 2014-2026 + regime.
        tr_a97 = a97[a97.ds < cc]
        tr_bridge = bridged[bridged.ds < cc]
        if len(tr_a97) >= 60:
            filas.append(
                evaluar(real, _fit(tr_a97, 52, use_regime=False), "Prophet+ENSO (2018+)", nombre)
            )
        if len(tr_bridge) >= 60:
            filas.append(
                evaluar(
                    real, _fit(tr_bridge, 52, use_regime=True), "Prophet+ENSO+2014(bridge)", nombre
                )
            )

    out = pd.DataFrame(filas)
    pd.set_option("display.width", 150, "display.max_columns", 20)
    print(out.to_string(index=False))
    print("\nSMAPE medio por modelo (menor es mejor):")
    print(out.groupby("modelo")["SMAPE"].mean().round(1).sort_values().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
