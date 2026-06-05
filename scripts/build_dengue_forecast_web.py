"""Construye el JSON de pronóstico de Dengue para la página pública.

Emite ``dengue_forecast.json`` con tres capas para el gráfico nacional:

1. ``historico``  — incidencia semanal real nacional (conteos), desde el boletín.
2. ``pronostico`` — pronóstico PRODUCTIVO a 1 año (52 sem) del motor ganador para la
   serie nacional general (DeepAR o Prophet, según el selector). Es el horizonte que
   los datos soportan con precisión.
3. ``proyeccion`` — proyección estacional multi-año del motor NB-GLM (conteos + Fourier +
   El Niño), con la tendencia congelada (``freeze_trend``). Extiende el horizonte MUCHO más
   allá de las 52 semanas que soporta DeepAR, mostrando el patrón estacional esperado a un
   nivel estable. NO predice la magnitud de la próxima gran epidemia (con solo 2 ciclos en
   los datos, el ciclo de ~4 años no es aprendible), pero al venir del mejor modelo del
   estudio es más principista que la antigua banda plana de Prophet.

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
MOTORES = ["Prophet", "DeepAR", "Ensemble", "Stacking", "NBGLM"]
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


def serie_contexto_a9091() -> pd.DataFrame:
    """Serie nacional semanal 2014-2018W26 del esquema viejo A90/A91 (CONTEXTO, no modelado).

    Otra clasificación y definición de caso; se muestra solo como contexto histórico en el
    gráfico (segmento atenuado) para que la vista de pronóstico arranque desde 2014. Cuentas
    semanales = diff del acumulado nacional dentro de cada año.
    """
    path = Path(conf["paths"]["interim"]) / "dengue_a90a91_nacional.csv"
    if not path.exists():
        return pd.DataFrame(columns=["ds", "y"])
    old = pd.read_csv(path).sort_values(["Anio", "Semana"])
    old["y"] = (
        old.groupby("Anio")["confirmado_acum_nacional"]
        .diff()
        .fillna(old["confirmado_acum_nacional"])
        .clip(lower=0)
    )
    old["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(a), min(int(s), 52), 1))
        for a, s in zip(old["Anio"], old["Semana"], strict=False)
    ]
    return old[["ds", "y"]].reset_index(drop=True)


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


def proyeccion_nbglm(serie: pd.DataFrame, anios: int, after: pd.Timestamp) -> pd.DataFrame:
    """Proyección estacional multi-año con NB-GLM (mejor modelo del estudio), tendencia congelada.

    Se ajusta sobre toda la serie real y se predice ``anios * 52`` semanas, devolviendo solo el
    tramo posterior a ``after`` (el fin del pronóstico productivo de 1 año) para que las dos capas
    del gráfico —pronóstico preciso y proyección— sean secuenciales y no se encimen el 1er año.

    ``freeze_trend=True`` mantiene la tendencia en su último nivel observado: extrapolar la
    pendiente (inflada por la epidemia de 2024) sobreestimaría los años no epidémicos. El ONI
    futuro se proyecta con persistencia amortiguada hacia neutral (sin filtrar clima del futuro).
    """
    from epiforecast.models.nbglm.model import NBGLMForecaster

    # NB-GLM exige ds únicos; el mapeo W53->W52 del histórico genera duplicados -> agregamos.
    t = serie[["ds", "y"]].groupby("ds", as_index=False)["y"].sum().sort_values("ds")
    np.random.seed(RANDOM_SEED)
    model = NBGLMForecaster(padecimiento="Dengue")
    model.fit(t)
    fc = model.predict(horizon=anios * 52, freeze_trend=True)
    fc["ds"] = pd.to_datetime(fc["ds"])
    horizonte = t["ds"].max() + pd.Timedelta(weeks=anios * 52)
    cols = [c for c in ["ds", "yhat", "yhat_lower", "yhat_upper"] if c in fc.columns]
    return fc[(fc["ds"] > after) & (fc["ds"] <= horizonte)][cols].sort_values("ds")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Directorio de salida (Reports/dengue)")
    ap.add_argument("--generado", required=True, help="Fecha de generación YYYY-MM-DD")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    serie = serie_nacional()
    contexto = serie_contexto_a9091()
    last_real = serie["ds"].max()
    motor, dist = motor_nacional()
    pron = pronostico_productivo(motor, last_real)
    # La proyección arranca donde TERMINA el pronóstico productivo de 1 año (sin solaparse).
    horizonte_productivo = pron["ds"].max() if len(pron) else last_real
    proy = proyeccion_nbglm(serie, ANIOS_PROYECCION, horizonte_productivo)

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
            "motor_proyeccion": "NBGLM",
            "distribucion": dist,
            "anios_proyeccion": ANIOS_PROYECCION,
            # Eje del gráfico: desde 2014 (historia completa con los ciclos epidémicos reales).
            # El chart usa escala logarítmica para que el pico de 2024 (~10 mil/sem) y los años
            # bajos + el pronóstico (~cientos-miles/sem) sean todos visibles y proporcionados.
            "chart_from_year": 2014,
            "escala": "log",
        },
        "historico_contexto": _pts(contexto, "y"),
        "historico": _pts(serie, "y"),
        "pronostico": _pts(pron, "yhat", "yhat_lower", "yhat_upper"),
        "proyeccion": _pts(proy, "yhat", "yhat_lower", "yhat_upper"),
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
