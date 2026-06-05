#!/usr/bin/env python
"""dengue_climate_test.py — ¿Mejora el NB-GLM con clima local (NASA POWER)?

Prueba RIGUROSA (backtest leave-one-epidemic-out, misma métrica) de si agregar
temperatura y precipitación (NASA POWER, proxy nacional ponderado a estados de alta
carga de dengue), rezagadas según la literatura, mejora el motor NB-GLM+ONI ya
productivo. Clima futuro = climatología semanal (known-future). Despliega solo si gana.

Uso:
    python -m scripts.research.dengue_climate_test
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import logging  # noqa: E402

logging.getLogger("cmdstanpy").disabled = True

from scripts.research.dengue_backtest import _fourier, serie_nacional, smape  # noqa: E402

from epiforecast.data import enso  # noqa: E402

CACHE = Path("data/external/nasa_power_dengue.csv")
# Centroides aproximados de estados de alta carga de dengue (proxy nacional).
PUNTOS = {
    "Veracruz": (19.2, -96.1),
    "Jalisco": (20.0, -104.0),
    "Chiapas": (16.75, -93.1),
    "Guerrero": (16.86, -99.9),
}
TEMP_LAG, PRECIP_LAG = 3, 12  # semanas (lit.: temp ~2-3 sem, lluvia ~8-12 sem)


def _fetch_power(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    url = (
        f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,PRECTOTCORR"
        f"&community=AG&longitude={lon}&latitude={lat}&start={start}&end={end}&format=JSON"
    )
    out = subprocess.run(  # noqa: S603 — curl evita el problema de certs SSL del venv
        ["curl", "-s", url],
        capture_output=True,
        text=True,
        timeout=90,
        check=True,  # noqa: S607
    )
    p = json.loads(out.stdout)["properties"]["parameter"]
    df = pd.DataFrame({"t2m": p["T2M"], "precip": p["PRECTOTCORR"]})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df


def clima_semanal() -> pd.DataFrame:
    """Temp/precip semanal (W-MON), promedio de los puntos de alta carga. Cacheado."""
    if CACHE.exists():
        return pd.read_csv(CACHE, parse_dates=["ds"])
    serie = serie_nacional()
    start = serie["ds"].min().strftime("%Y%m%d")
    end = serie["ds"].max().strftime("%Y%m%d")
    frames = []
    for nombre, (lat, lon) in PUNTOS.items():
        d = _fetch_power(lat, lon, start, end)
        frames.append(d.rename(columns={c: f"{c}_{nombre}" for c in d.columns}))
    allp = pd.concat(frames, axis=1)
    daily = pd.DataFrame(
        {
            "t2m": allp[[c for c in allp if c.startswith("t2m")]].mean(axis=1),
            "precip": allp[[c for c in allp if c.startswith("precip")]].clip(lower=0).mean(axis=1),
        }
    )
    weekly = daily.resample("W-MON").agg({"t2m": "mean", "precip": "sum"}).reset_index()
    weekly = weekly.rename(columns={"index": "ds"})
    weekly.columns = ["ds", "t2m", "precip"]
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    weekly.to_csv(CACHE, index=False)
    return weekly


def _clima_features(ds: pd.Series, as_of: pd.Timestamp) -> np.ndarray:
    """temp(lag) y precip(lag) para las fechas objetivo. Futuro tras as_of = climatología."""
    cw = clima_semanal().set_index("ds").sort_index()
    cw = cw[cw.index <= as_of]  # solo clima conocido al momento del pronóstico
    # Climatología por semana ISO (para extrapolar el futuro como known-future).
    clim = cw.copy()
    clim["wk"] = clim.index.isocalendar().week.astype(int)
    clim_t = clim.groupby("wk")["t2m"].mean()
    clim_p = clim.groupby("wk")["precip"].mean()

    def lookup(target_dates: pd.Series, col: str, clim_s: pd.Series, lag: int) -> np.ndarray:
        src = pd.to_datetime(target_dates) - pd.Timedelta(weeks=lag)
        vals = cw[col].reindex(cw.index.union(pd.DatetimeIndex(src))).interpolate().reindex(src)
        wk = pd.DatetimeIndex(src).isocalendar().week.astype(int)
        fallback = wk.map(clim_s).to_numpy(dtype=float)  # climatología donde no hay observado
        out = vals.to_numpy(dtype=float)
        return np.where(np.isnan(out), fallback, out)

    t = lookup(ds, "t2m", clim_t, TEMP_LAG)
    p = lookup(ds, "precip", clim_p, PRECIP_LAG)
    # estandariza (mejora condicionamiento del GLM)
    t = (t - np.nanmean(t)) / (np.nanstd(t) + 1e-9)
    p = (p - np.nanmean(p)) / (np.nanstd(p) + 1e-9)
    return np.column_stack([t, p])


def fit_nbglm(train: pd.DataFrame, periods: int, k: int, use_clima: bool):
    import statsmodels.api as sm

    cutoff = train["ds"].max()
    y = train["y"].clip(lower=0).to_numpy(float)
    n = len(y)
    four = _fourier(train["ds"], k)
    trend = (np.arange(n) / 52.0).reshape(-1, 1)
    lag1 = np.log1p(np.concatenate([[y[0]], y[:-1]]))
    lag52 = np.log1p(np.concatenate([np.full(min(52, n), y[0]), y[:-52]])[:n])
    oni = enso.oni_for_dates(train["ds"], as_of=cutoff).reshape(-1, 1)
    feats = [np.ones(n), four, trend, lag1, lag52, oni]
    if use_clima:
        feats.append(_clima_features(train["ds"], cutoff))
    res = sm.GLM(y, np.column_stack(feats), family=sm.families.NegativeBinomial(alpha=1.0)).fit()

    fut_ds = pd.date_range(cutoff + pd.Timedelta(weeks=1), periods=periods, freq="W-MON")
    four_f = _fourier(pd.Series(fut_ds), k)
    oni_f = enso.oni_for_dates(pd.Series(fut_ds), as_of=cutoff)
    clima_f = _clima_features(pd.Series(fut_ds), cutoff) if use_clima else None
    hist = list(y)
    preds = []
    for i in range(periods):
        row = [
            1.0,
            *four_f[i],
            (n + i) / 52.0,
            np.log1p(hist[-1]),
            np.log1p(hist[-52]) if len(hist) >= 52 else np.log1p(hist[0]),
            float(oni_f[i]),
        ]
        if clima_f is not None:
            row.extend(clima_f[i].tolist())
        mu = float(np.clip(res.predict(np.array(row).reshape(1, -1))[0], 0, 50000))
        preds.append(mu)
        hist.append(mu)
    return pd.DataFrame({"ds": fut_ds, "yhat": preds})


def main() -> int:
    serie = serie_nacional()
    cw = clima_semanal()
    print(f"Clima NASA POWER: {len(cw)} sem ({cw.ds.min().date()}..{cw.ds.max().date()})\n")
    cortes = {"2023": "2023-01-01", "2024 (pico)": "2024-01-01"}
    filas = []
    for nombre, c in cortes.items():
        cc = pd.Timestamp(c)
        train = serie[serie.ds < cc]
        real = serie[(serie.ds >= cc) & (serie.ds < cc + pd.Timedelta(weeks=52))]
        if len(train) < 60 or real.empty:
            continue
        for etq, use in [("NB-GLM+ONI", False), ("NB-GLM+ONI+Clima", True)]:
            pred = fit_nbglm(train, 52, 4, use)
            m = real.merge(pred, on="ds")
            filas.append(
                {
                    "corte": nombre,
                    "modelo": etq,
                    "SMAPE": round(smape(m.y.to_numpy(float), m.yhat.to_numpy(float)), 1),
                    "ratio_pico": round(m.yhat.max() / m.y.max(), 2) if m.y.max() else None,
                }
            )
    out = pd.DataFrame(filas)
    print(out.to_string(index=False))
    print("\nSMAPE medio:")
    print(out.groupby("modelo")["SMAPE"].mean().round(1).sort_values().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
