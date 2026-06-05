#!/usr/bin/env python
"""dengue_backtest.py — Banco de pruebas para mejorar el pronóstico de Dengue.

Backtest leave-one-epidemic-out sobre la serie NACIONAL semanal de Dengue:
entrena hasta antes de un año epidémico y pronostica ese año a 52 semanas, comparando
modelos. Objetivo: medir si (a) un GLM Negative-Binomial con estacionalidad de Fourier
y (b) agregar el índice El Niño (ONI) como regresor a Prophet mejoran sobre el Prophet
actual, sobre todo en la MAGNITUD del pico (lo que los modelos autorregresivos no captan).

Uso:
    python -m scripts.research.dengue_backtest
"""

from __future__ import annotations

from datetime import date
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import logging  # noqa: E402

logging.getLogger("cmdstanpy").disabled = True

from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402

ONI_PATH = "data/external/oni.ascii.txt"
_SEAS_TO_MONTH = {  # centro del trimestre móvil ONI -> mes
    "DJF": 1,
    "JFM": 2,
    "FMA": 3,
    "MAM": 4,
    "AMJ": 5,
    "MJJ": 6,
    "JJA": 7,
    "JAS": 8,
    "ASO": 9,
    "SON": 10,
    "OND": 11,
    "NDJ": 12,
}


def serie_nacional() -> pd.DataFrame:
    """Serie nacional semanal (ds=lunes ISO, y=conteos)."""
    df = cargar_boletin_dengue()
    g = df.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    g = g.sort_values(["Anio", "Semana"])
    g["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(g["Anio"], g["Semana"], strict=False)
    ]
    return g.rename(columns={"Casos_semana": "y"})[["ds", "y"]].reset_index(drop=True)


ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"


def _ensure_oni() -> None:
    """Descarga el ONI de NOAA si falta (data/external está gitignored)."""
    from pathlib import Path
    import urllib.request

    p = Path(ONI_PATH)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(ONI_URL, ONI_PATH)  # noqa: S310


def oni_weekly() -> pd.DataFrame:
    """ONI mensual -> semanal (interpolado), índice por fecha."""
    _ensure_oni()
    rows = []
    with open(ONI_PATH) as f:
        next(f)
        for line in f:
            p = line.split()
            if len(p) == 4 and p[0] in _SEAS_TO_MONTH:
                rows.append((int(p[1]), _SEAS_TO_MONTH[p[0]], float(p[3])))
    o = pd.DataFrame(rows, columns=["yr", "mo", "oni"])
    o["ds"] = pd.to_datetime({"year": o.yr, "month": o.mo, "day": 1})
    return o.set_index("ds").resample("W-MON")["oni"].mean().interpolate().reset_index()


def add_oni(df: pd.DataFrame, lag_weeks: int) -> pd.DataFrame:
    """Agrega oni rezagado lag_weeks (clima precede al dengue)."""
    o = oni_weekly()
    o["ds_target"] = o["ds"] + pd.Timedelta(weeks=lag_weeks)
    m = df.merge(o[["ds_target", "oni"]], left_on="ds", right_on="ds_target", how="left")
    m["oni"] = m["oni"].ffill().bfill()
    return m.drop(columns=["ds_target"])


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #
def fit_prophet(
    train: pd.DataFrame, periods: int, regressor: str | None = None, oni_scenario: str = "perfect"
):
    """Prophet con la config de Dengue (log1p, multiplicativa, cp=0.05).

    oni_scenario: "perfect" = ONI futuro observado (¿tiene valor la covariable?);
    "realista" = solo ONI conocido al momento del pronóstico (observado donde el rezago
    de 16 sem ya lo entrega) + persistencia del último ONI conocido para la cola.
    """
    from prophet import Prophet

    t = train.copy()
    cutoff = t["ds"].max()
    t["y"] = np.log1p(t["y"].clip(lower=0))
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
    if regressor:
        m.add_regressor(regressor)
    np.random.seed(42)
    m.fit(t[["ds", "y"] + ([regressor] if regressor else [])])
    fut = m.make_future_dataframe(periods=periods, freq="W-MON")
    if regressor:
        o = oni_weekly()
        if oni_scenario == "realista":
            # Solo se conoce ONI hasta el cutoff; el target en t usa ONI(t-16sem).
            o = o[o["ds"] <= cutoff]
            last = o["oni"].iloc[-1]
        o["ds_target"] = o["ds"] + pd.Timedelta(weeks=LAG_ONI)
        merged = fut[["ds"]].merge(
            o[["ds_target", "oni"]], left_on="ds", right_on="ds_target", how="left"
        )
        vals = merged["oni"].ffill()
        if oni_scenario == "realista":
            vals = vals.fillna(last)  # cola futura = persistencia del último ONI conocido
        fut[regressor] = vals.bfill().to_numpy()
    fc = m.predict(fut)
    fc["yhat"] = np.expm1(fc["yhat"]).clip(lower=0)
    return fc[["ds", "yhat"]].tail(periods).reset_index(drop=True)


def fit_prophet_enso_deploy(train: pd.DataFrame, periods: int):
    """Prophet + ONI usando el módulo de producción enso.py (estrategia DESPLEGABLE:
    ONI observado hasta el cutoff + persistencia amortiguada para la cola futura)."""
    from prophet import Prophet

    from epiforecast.data import enso

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
    np.random.seed(42)
    m.fit(t[["ds", "y", "oni"]])
    fut = m.make_future_dataframe(periods=periods, freq="W-MON")
    fut["oni"] = enso.oni_for_dates(fut["ds"], as_of=cutoff)
    fc = m.predict(fut)
    fc["yhat"] = np.expm1(fc["yhat"]).clip(lower=0)
    return fc[["ds", "yhat"]].tail(periods).reset_index(drop=True)


def _fourier(ds: pd.Series, k: int) -> np.ndarray:
    """Términos de Fourier para el ciclo anual (semana ISO)."""
    wk = ds.dt.isocalendar().week.astype(float).to_numpy()
    feats = []
    for i in range(1, k + 1):
        feats.append(np.sin(2 * np.pi * i * wk / 52.0))
        feats.append(np.cos(2 * np.pi * i * wk / 52.0))
    return np.column_stack(feats)


def fit_nbglm(train: pd.DataFrame, periods: int, k: int = 4, use_oni: bool = False):
    """GLM Negative-Binomial con Fourier(annual) + lag1 + lag52 + tendencia [+ ONI].

    Pronóstico iterativo: realimenta sus propias predicciones para los lags. Con use_oni,
    agrega el índice El Niño rezagado (estrategia desplegable de enso.py) como covariable.
    """
    import statsmodels.api as sm

    from epiforecast.data import enso

    t = train.reset_index(drop=True).copy()
    cutoff = t["ds"].max()
    y = t["y"].clip(lower=0).to_numpy(dtype=float)
    n = len(y)
    four = _fourier(t["ds"], k)
    trend = (np.arange(n) / 52.0).reshape(-1, 1)
    lag1 = np.log1p(np.concatenate([[y[0]], y[:-1]]))
    lag52 = np.log1p(np.concatenate([np.full(min(52, n), y[0]), y[:-52]])[:n])
    feats = [np.ones(n), four, trend, lag1, lag52]
    fut_ds = pd.date_range(t["ds"].iloc[-1] + pd.Timedelta(weeks=1), periods=periods, freq="W-MON")
    if use_oni:
        oni_hist = enso.oni_for_dates(t["ds"], as_of=cutoff)
        oni_fut = enso.oni_for_dates(pd.Series(fut_ds), as_of=cutoff)
        feats.append(oni_hist.reshape(-1, 1))
    xmat = np.column_stack(feats)
    res = sm.GLM(y, xmat, family=sm.families.NegativeBinomial(alpha=1.0)).fit()

    hist = list(y)
    four_f = _fourier(pd.Series(fut_ds), k)
    preds = []
    for i in range(periods):
        tr = (n + i) / 52.0
        l1 = np.log1p(hist[-1])
        l52 = np.log1p(hist[-52]) if len(hist) >= 52 else np.log1p(hist[0])
        row = [1.0, *four_f[i], tr, l1, l52]
        if use_oni:
            row.append(float(oni_fut[i]))
        yhat = float(res.predict(np.array(row).reshape(1, -1))[0])
        yhat = max(0.0, min(yhat, 50000.0))  # acota explosiones del lag
        preds.append(yhat)
        hist.append(yhat)
    return pd.DataFrame({"ds": fut_ds, "yhat": preds})


# --------------------------------------------------------------------------- #
# Métricas y backtest
# --------------------------------------------------------------------------- #
def smape(real: np.ndarray, pred: np.ndarray) -> float:
    d = (np.abs(real) + np.abs(pred)) / 2
    e = np.where(d == 0, 0.0, np.abs(real - pred) / d)
    return float(np.mean(e) * 100)


def evaluar(real: pd.DataFrame, pred: pd.DataFrame, etiqueta: str) -> dict:
    m = real.merge(pred, on="ds", how="inner")
    if m.empty:
        return {"modelo": etiqueta, "n": 0}
    r, p = m["y"].to_numpy(float), m["yhat"].to_numpy(float)
    return {
        "modelo": etiqueta,
        "n": len(m),
        "SMAPE": round(smape(r, p), 1),
        "MAE": round(float(np.mean(np.abs(r - p))), 1),
        "pico_real": int(r.max()),
        "pico_pred": int(p.max()),
        "ratio_pico": round(p.max() / r.max(), 2) if r.max() > 0 else None,
    }


LAG_ONI = 16


def main() -> int:
    serie = serie_nacional()
    print(f"Serie nacional: {len(serie)} sem, {serie.ds.min().date()} a {serie.ds.max().date()}\n")
    serie_oni = add_oni(serie, LAG_ONI)

    # Leave-one-epidemic-out: entrenar hasta antes del año, pronosticar 52 sem
    cortes = {"2019 (pico)": "2019-01-01", "2023": "2023-01-01", "2024 (pico mayor)": "2024-01-01"}
    filas = []
    for nombre, corte in cortes.items():
        c = pd.Timestamp(corte)
        train = serie[serie.ds < c]
        train_oni = serie_oni[serie_oni.ds < c]
        real = serie[(serie.ds >= c) & (serie.ds < c + pd.Timedelta(weeks=52))]
        if len(train) < 60 or real.empty:
            continue
        for etiqueta, pred in [
            ("Prophet (actual)", fit_prophet(train, 52)),
            ("Prophet+ONI perfect", fit_prophet(train_oni, 52, "oni", "perfect")),
            ("Prophet+ONI realista", fit_prophet(train_oni, 52, "oni", "realista")),
            ("Prophet+ENSO deploy", fit_prophet_enso_deploy(train, 52)),
            ("NB-GLM Fourier", fit_nbglm(train, 52)),
            ("NB-GLM + ONI", fit_nbglm(train, 52, use_oni=True)),
        ]:
            res = evaluar(real, pred, etiqueta)
            res["corte"] = nombre
            filas.append(res)

    out = pd.DataFrame(filas)[
        ["corte", "modelo", "n", "SMAPE", "MAE", "pico_real", "pico_pred", "ratio_pico"]
    ]
    pd.set_option("display.width", 140, "display.max_columns", 20)
    print(out.to_string(index=False))
    print("\nResumen SMAPE medio por modelo (menor es mejor):")
    print(out.groupby("modelo")["SMAPE"].mean().round(1).sort_values().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
