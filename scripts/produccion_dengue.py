"""Selección del motor productivo para Dengue (cohorte propia, no neuro).

Análogo a ``reselect_motor_2026.py`` pero autónomo para Dengue: el padecimiento
no está en la tabla de 333 modelos neuro ni en su pipeline de re-selección
(esos scripts filtran a ``NEURO_CONDITIONS``). Aquí elegimos, por cada serie
(entidad × sexo), cuál de los 4 motores (Prophet, DeepAR, Ensemble, Stacking)
es el productivo, usando el SMAPE sobre la realidad del año de evaluación (el
último año con datos en el boletín, derivado, no hardcodeado).

Reglas (adaptadas a la naturaleza del Dengue, NO se reusan las de baja
incidencia de neuro):
1. Serie con >= MIN_WEEKS_REAL semanas reales y total >= MIN_TOTAL_CASOS:
   criterio primario = SMAPE real (MAE como desempate). criterio="smape_real".
2. Serie casi-cero (>= MIN_WEEKS_REAL semanas pero total < MIN_TOTAL_CASOS):
   se honra "si es 0, es 0" -> se elige el motor con MENOR MAE real (el que
   pronostica más cerca de cero), NO se fuerza Ensemble. criterio="mae_real_casi_cero".
3. Serie sin realidad reciente suficiente (< MIN_WEEKS_REAL semanas):
   se cae al SMAPE de validación cruzada del propio modelo (``smape_usado``
   embebido en el forecast). criterio="cv_smape".

Salidas (``reports/ProdDetails/``):
- ``produccion_dengue.csv``  — 1 fila por serie (entidad × sexo) con ``anio_eval``,
  SMAPE/MAE reales y CV de los 4 motores, motor ganador, criterio y justificación.
- ``produccion_dengue.xlsx`` — misma tabla, legible.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from epiforecast.evaluation.real_eval import build_forecasts, build_real, eval_year, smape
from epiforecast.utils.config import conf, logger

PADECIMIENTO = "Dengue"
MOTORES = ["Prophet", "DeepAR", "Ensemble", "Stacking", "NBGLM"]


# Rutas derivadas de config (no hardcodeadas) en acceso lazy: evita leer conf en import-time
# (frágil bajo pytest) y mantiene el módulo importable para tests de las funciones puras.
def _boletin() -> Path:
    return Path(conf["data"]["boletin"])


def _forecast_paths() -> dict[str, Path]:
    base = Path(conf["paths"]["reports"]) / "forecasts"
    return {m: base / m.lower() / f"all_forecast_{m.lower()}.csv" for m in MOTORES}


def _out_paths() -> tuple[Path, Path]:
    prod = Path(conf["paths"]["reports"]) / "ProdDetails"
    return prod / "produccion_dengue.csv", prod / "produccion_dengue.xlsx"


# Productivos: DeepAR, Prophet y NBGLM. Ensemble (Prophet+XGBoost) y Stacking
# (Prophet+ETS+LightGBM) divergen ~33x/99x: los árboles no extrapolan la dinámica epidémica
# a 52 sem. NBGLM (Negative-Binomial GLM + Fourier + ENSO) sí extrapola (estacionalidad
# paramétrica) y es count-correcto; validado en backtest leave-one-epidemic-out (SMAPE 52 vs
# Prophet+ENSO 76). Se reportan las métricas de los árboles para auditoría pero NO se eligen.
MOTORES_ELEGIBLES = ["Prophet", "DeepAR", "NBGLM"]
MIN_WEEKS_REAL = 10  # mínimo de semanas reales del año de eval. para usar criterio real
MIN_TOTAL_CASOS = 10  # por debajo: serie casi-cero ("si es 0, es 0")
SMAPE_TIE_BAND = 0.05  # motores dentro del 5% del mejor SMAPE se consideran empatados
#                        y se desempatan por MAE (evita flips por ruido en año bajo).


def mae(y: np.ndarray, yhat: np.ndarray) -> float:
    """MAE; NaN ante arreglo vacío (criterio de las series casi-cero, no usado en neuro)."""
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    if y.size == 0:
        return np.nan
    return float(np.mean(np.abs(y - yhat)))


def metrics_per_motor(real: pd.DataFrame, fc: pd.DataFrame, cv: pd.DataFrame) -> pd.DataFrame:
    """Por (entidad, sexo) calcula SMAPE/MAE reales y CV-SMAPE de cada motor."""
    fc_wide = fc.pivot_table(
        index=["entidad", "sexo", "Semana"], columns="motor", values="yhat"
    ).reset_index()
    merged = real.merge(fc_wide, on=["entidad", "sexo", "Semana"], how="inner")
    cv_wide = cv.pivot_table(index=["entidad", "sexo"], columns="motor", values="cv_smape")

    rows = []
    for (ent, sx), grp in merged.groupby(["entidad", "sexo"]):
        row = {
            "padecimiento": PADECIMIENTO,
            "entidad": ent,
            "sexo": sx,
            "n_semanas_real": int(len(grp)),
            "total_real": float(grp["real"].sum()),
        }
        for m in MOTORES:
            if m in grp.columns and grp[m].notna().sum() >= 1:
                row[f"smape_real_{m.lower()}"] = smape(grp["real"], grp[m])
                row[f"mae_real_{m.lower()}"] = mae(grp["real"], grp[m])
            else:
                row[f"smape_real_{m.lower()}"] = np.nan
                row[f"mae_real_{m.lower()}"] = np.nan
            cvv = (
                cv_wide.loc[(ent, sx), m]
                if (ent, sx) in cv_wide.index and m in cv_wide.columns
                else np.nan
            )
            row[f"cv_smape_{m.lower()}"] = float(cvv) if pd.notna(cvv) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _pick(row: pd.Series) -> tuple[str, str, float | None]:
    n = row["n_semanas_real"]
    total = row["total_real"]
    # Selección solo entre motores elegibles (DeepAR/Prophet); Ensemble/Stacking divergen.
    smapes = {m: row[f"smape_real_{m.lower()}"] for m in MOTORES_ELEGIBLES}
    smapes = {m: v for m, v in smapes.items() if pd.notna(v)}
    maes = {m: row[f"mae_real_{m.lower()}"] for m in MOTORES_ELEGIBLES}
    maes = {m: v for m, v in maes.items() if pd.notna(v)}
    cvs = {m: row[f"cv_smape_{m.lower()}"] for m in MOTORES_ELEGIBLES}
    cvs = {m: v for m, v in cvs.items() if pd.notna(v)}

    # Regla 1: realidad suficiente + casos suficientes -> SMAPE real con BANDA de empate.
    # Los motores dentro del 5% del mejor SMAPE se consideran empatados y se desempata por
    # MAE. Sin la banda, un margen de ruido (p.ej. Nacional: Prophet 19.50 vs DeepAR 19.63)
    # flipea a Prophet, que sobre-ajusta feo el pico epidémico; el MAE favorece a DeepAR,
    # que sigue mejor la magnitud. Consistente con la banda 5% del reselect neuro.
    if n >= MIN_WEEKS_REAL and total >= MIN_TOTAL_CASOS and smapes:
        best = min(smapes.values())
        band = {m: v for m, v in smapes.items() if v <= best * (1 + SMAPE_TIE_BAND)}
        winner = min(band, key=lambda m: maes.get(m, np.inf))
        return winner, "smape_real", smapes[winner]
    # Regla 2: serie casi-cero -> menor MAE (más cercano a cero), "si es 0, es 0"
    if n >= MIN_WEEKS_REAL and total < MIN_TOTAL_CASOS and maes:
        winner = min(maes, key=lambda m: maes[m])
        return winner, "mae_real_casi_cero", None
    # Regla 3: sin realidad reciente -> CV SMAPE
    if cvs:
        winner = min(cvs, key=lambda m: cvs[m])
        return winner, "cv_smape", cvs[winner]
    # Default seguro: Prophet es motor ELEGIBLE (DeepAR/Prophet). Rama casi inalcanzable
    # (requiere sin SMAPE, sin MAE y sin CV simultáneamente).
    return "Prophet", "default", None


def select(metrics: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    picks = out.apply(_pick, axis=1, result_type="expand")
    picks.columns = ["motor_productivo", "criterio_seleccion", "smape_ganador"]
    out = pd.concat([out, picks], axis=1)

    def _just(r: pd.Series) -> str:
        m = r["motor_productivo"]
        crit = r["criterio_seleccion"]
        if crit == "smape_real":
            return f"{m}: menor SMAPE real={r['smape_ganador']:.2f}% sobre {int(r['n_semanas_real'])} sem"
        if crit == "mae_real_casi_cero":
            return f"{m}: serie casi-cero (total {int(r['total_real'])} casos), menor MAE real"
        if crit == "cv_smape":
            return f"{m}: sin realidad reciente suficiente, menor SMAPE de validación cruzada"
        return f"{m}: default"

    out["justificacion"] = out.apply(_just, axis=1)
    return out


def main() -> None:
    pads = [PADECIMIENTO]
    anio = eval_year(_boletin(), pads)
    bol = pd.read_csv(_boletin(), usecols=["Padecimiento", "Anio", "Semana"])
    weeks_limit = int(bol.query("Padecimiento == @PADECIMIENTO and Anio == @anio")["Semana"].max())
    logger.info("Dengue {}: usando semanas 1..{}", anio, weeks_limit)

    # Cohorte de un solo padecimiento: se descarta la columna padecimiento del módulo común.
    real = build_real(_boletin(), pads, anio, weeks_limit).drop(columns=["padecimiento"])
    fc, cv = build_forecasts(_forecast_paths(), pads, anio, weeks_limit)
    fc = fc.drop(columns=["padecimiento"])
    cv = cv.drop(columns=["padecimiento"])
    metrics = metrics_per_motor(real, fc, cv)
    result = select(metrics)
    result.insert(3, "anio_eval", anio)

    out_csv, out_xlsx = _out_paths()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_csv, index=False)
    result.to_excel(out_xlsx, index=False)

    dist = result["motor_productivo"].value_counts().to_dict()
    crit = result["criterio_seleccion"].value_counts().to_dict()
    nac = result[(result["entidad"] == "Nacional") & (result["sexo"] == "general")]
    motor_nac = nac["motor_productivo"].iloc[0] if len(nac) else "—"
    logger.success(
        "Producción Dengue: {} series | distribución {} | criterios {} | motor Nacional general = {}",
        len(result),
        dist,
        crit,
        motor_nac,
    )
    logger.info("→ {}", out_csv)
    logger.info("→ {}", out_xlsx)


if __name__ == "__main__":
    main()
