"""Construye el JSON de pronóstico de Dengue para la página pública.

Emite ``dengue_forecast.json`` con tres capas para el gráfico nacional:

1. ``historico``  — incidencia semanal real nacional (conteos), desde el boletín.
2. ``pronostico`` — pronóstico PRODUCTIVO a 1 año (52 sem) del motor ganador para la
   serie nacional general (DeepAR o Prophet, según el selector). Es el horizonte que
   los datos soportan con precisión.
3. ``proyeccion`` — proyección estacional ILUSTRATIVA a 5 años (Prophet con tendencia
   plana sobre log1p). NO predice la magnitud de la próxima epidemia: solo extiende el
   patrón estacional esperado (con solo 2 ciclos epidémicos en los datos, el ciclo de
   ~4 años no es aprendible).

Más metadatos de producción: motor nacional y distribución de motores (DeepAR/Prophet).

Uso:
    python -m scripts.build_dengue_forecast_web --out <dir> --generado 2026-06-04
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import logging
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from epiforecast.constants import RANDOM_SEED
from epiforecast.data.boletin import cargar_boletin_dengue
from epiforecast.utils.config import conf

warnings.filterwarnings("ignore")
logging.getLogger("cmdstanpy").disabled = True

# Rutas derivadas de config (no hardcodeadas).
_REPORTS = Path(conf["paths"]["reports"])
PROD = _REPORTS / "ProdDetails" / "produccion_dengue.csv"
# Forecast de los 4 motores: el motor productivo nacional puede ser cualquiera; sin las 4
# rutas, un motor no listado caería silenciosamente a Prophet y meta.motor_nacional mentiría.
MOTORES = ["Prophet", "DeepAR", "Ensemble", "Stacking"]
FORECAST = {
    m: _REPORTS / "forecasts" / m.lower() / f"all_forecast_{m.lower()}.csv" for m in MOTORES
}
ANIOS_PROYECCION = 5


def serie_nacional() -> pd.DataFrame:
    """Serie nacional general semanal (conteos) con ds = lunes de la semana ISO.

    Usa el lunes de la semana ISO (``date.fromisocalendar``) para que el histórico quede
    en la MISMA rejilla de fechas (W-MON) que el pronóstico de los modelos y empalme sin
    corrimiento. Fuente única: el consolidado de producción (``cargar_boletin_dengue``).
    """
    df = cargar_boletin_dengue()
    g = df.groupby(["Anio", "Semana"])["Casos_semana"].sum().reset_index()
    g = g.sort_values(["Anio", "Semana"])
    g["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(g["Anio"], g["Semana"], strict=False)
    ]
    return g.rename(columns={"Casos_semana": "y"})[["ds", "y"]].reset_index(drop=True)


def motor_nacional() -> tuple[str, dict[str, int]]:
    """Motor productivo de la serie nacional general + distribución global."""
    prod = pd.read_csv(PROD)
    dist = {k: int(v) for k, v in prod["motor_productivo"].value_counts().items()}
    nac = prod[(prod["entidad"] == "Nacional") & (prod["sexo"] == "general")]
    motor = str(nac["motor_productivo"].iloc[0]) if len(nac) else "Prophet"
    return motor, dist


def pronostico_productivo(motor: str, last_real: pd.Timestamp) -> pd.DataFrame:
    """Pronóstico futuro (1 año) del motor ganador para nacional general."""
    path = FORECAST.get(motor, FORECAST["Prophet"])
    df = pd.read_csv(path, low_memory=False)
    d = df[
        (df["meta_padecimiento"] == "Dengue")
        & (df["meta_entidad"] == "Nacional")
        & (df["meta_modo"] == "general")
    ].copy()
    d["ds"] = pd.to_datetime(d["ds"])
    cols = [c for c in ["ds", "yhat", "yhat_lower", "yhat_upper"] if c in d.columns]
    d = d[d["ds"] > last_real][cols].sort_values("ds")
    return d


def proyeccion_estacional(serie: pd.DataFrame, anios: int) -> pd.DataFrame:
    """Banda estacional ilustrativa a N años: Prophet log1p + tendencia plana."""
    from prophet import Prophet

    t = serie.copy()
    t["y"] = np.log1p(t["y"].clip(lower=0))
    m = Prophet(
        growth="flat",
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
        seasonality_mode="multiplicative",
        seasonality_prior_scale=10.0,
    )
    m.add_seasonality(name="yearly_custom", period=365.25, fourier_order=10)
    np.random.seed(RANDOM_SEED)
    m.fit(t)
    fut = m.make_future_dataframe(periods=anios * 52, freq="W-MON")
    fc = m.predict(fut)
    fc["yhat"] = np.expm1(fc["yhat"]).clip(lower=0)
    last_real = serie["ds"].max()
    return fc[fc["ds"] > last_real][["ds", "yhat"]].sort_values("ds")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Directorio de salida (Reports/dengue)")
    ap.add_argument("--generado", required=True, help="Fecha de generación YYYY-MM-DD")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    serie = serie_nacional()
    last_real = serie["ds"].max()
    motor, dist = motor_nacional()
    pron = pronostico_productivo(motor, last_real)
    proy = proyeccion_estacional(serie, ANIOS_PROYECCION)

    def _pts(df: pd.DataFrame, *cols: str) -> list[dict[str, object]]:
        rows = []
        for _, r in df.iterrows():
            d = {"ds": pd.Timestamp(r["ds"]).strftime("%Y-%m-%d")}
            for c in cols:
                if c in df.columns:
                    d[c] = round(float(r[c]), 1)
            rows.append(d)
        return rows

    data = {
        "meta": {
            "generado": args.generado,
            "ultima_real": last_real.strftime("%Y-%m-%d"),
            "motor_nacional": motor,
            "distribucion": dist,
            "anios_proyeccion": ANIOS_PROYECCION,
            # Inicio del eje del gráfico: ~4 años de detalle reciente antes del horizonte.
            "chart_from_year": int(last_real.year) - 4,
        },
        "historico": _pts(serie, "y"),
        "pronostico": _pts(pron, "yhat", "yhat_lower", "yhat_upper"),
        "proyeccion": _pts(proy, "yhat"),
    }
    (out / "dengue_forecast.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"dengue_forecast.json: motor nacional={motor} | "
        f"hist={len(data['historico'])} pron={len(data['pronostico'])} "
        f"proy={len(data['proyeccion'])} | dist={dist}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
