"""Selección del motor productivo para Dengue (cohorte propia, no neuro).

Análogo a ``reselect_motor_2026.py`` pero autónomo para Dengue: el padecimiento
no está en la tabla de 333 modelos neuro ni en su pipeline de re-selección
(esos scripts filtran a ``NEURO_CONDITIONS``). Aquí elegimos, por cada serie
(entidad × sexo), cuál de los 4 motores (Prophet, DeepAR, Ensemble, Stacking)
es el productivo, usando el SMAPE sobre la realidad 2026 ya publicada en el
boletín.

Reglas (adaptadas a la naturaleza del Dengue, NO se reusan las de baja
incidencia de neuro):
1. Serie con >= MIN_WEEKS_REAL semanas reales 2026 y total >= MIN_TOTAL_CASOS:
   criterio primario = SMAPE 2026 real (MAE como desempate). criterio="smape_real_2026".
2. Serie casi-cero (>= MIN_WEEKS_REAL semanas pero total < MIN_TOTAL_CASOS):
   se honra "si es 0, es 0" -> se elige el motor con MENOR MAE 2026 (el que
   pronostica más cerca de cero), NO se fuerza Ensemble. criterio="mae_real_2026_casi_cero".
3. Serie sin realidad reciente suficiente (< MIN_WEEKS_REAL semanas):
   se cae al SMAPE de validación cruzada del propio modelo (``smape_usado``
   embebido en el forecast). criterio="cv_smape".

Salidas (``reports/ProdDetails/``):
- ``produccion_dengue.csv``  — 1 fila por serie (entidad × sexo) con SMAPE/MAE
  2026 y CV de los 4 motores, motor ganador, criterio y justificación.
- ``produccion_dengue.xlsx`` — misma tabla, legible.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from epiforecast.utils.config import logger

ROOT = Path(__file__).resolve().parent.parent
BOLETIN = ROOT / "data/processed/dataset_boletin_epidemiologico.csv"
FORECAST_PATHS = {
    "Prophet": ROOT / "reports/forecasts/prophet/all_forecast_prophet.csv",
    "DeepAR": ROOT / "reports/forecasts/deepar/all_forecast_deepar.csv",
    "Ensemble": ROOT / "reports/forecasts/ensemble/all_forecast_ensemble.csv",
    "Stacking": ROOT / "reports/forecasts/stacking/all_forecast_stacking.csv",
}
OUT_CSV = ROOT / "reports/ProdDetails/produccion_dengue.csv"
OUT_XLSX = ROOT / "reports/ProdDetails/produccion_dengue.xlsx"

PADECIMIENTO = "Dengue"
MOTORES = ["Prophet", "DeepAR", "Ensemble", "Stacking"]
# Solo DeepAR y Prophet son productivos para Dengue. Ensemble (Prophet+XGBoost) y Stacking
# (Prophet+ETS+LightGBM) divergen ~33x/99x: los modelos de árboles no extrapolan la dinámica
# epidémica del dengue a 52 semanas (y el log1p amplifica el overshoot exponencialmente).
# Se reportan sus métricas para auditoría pero NO se eligen como motor productivo.
MOTORES_ELEGIBLES = ["Prophet", "DeepAR"]
MIN_WEEKS_REAL = 10  # mínimo de semanas reales 2026 para usar criterio real
MIN_TOTAL_CASOS = 10  # por debajo: serie casi-cero ("si es 0, es 0")


def smape(y: np.ndarray, yhat: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    denom = (np.abs(y) + np.abs(yhat)) / 2
    mask = denom > 0
    if mask.sum() == 0:
        return np.nan
    return float(np.mean(np.abs(y[mask] - yhat[mask]) / denom[mask]) * 100)


def mae(y: np.ndarray, yhat: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    return float(np.mean(np.abs(y - yhat)))


def build_real_2026(weeks_limit: int) -> pd.DataFrame:
    """Real semanal 2026 de Dengue por (entidad, sexo, semana)."""
    df = pd.read_csv(BOLETIN)
    df = df[df["Padecimiento"] == PADECIMIENTO].copy()
    sub = df[(df["Anio"] == 2026) & (df["Semana"] <= weeks_limit)].copy()
    sub = sub.sort_values(["Entidad", "Semana"])

    gen = sub.groupby(["Entidad", "Semana"])["Casos_semana"].sum().reset_index()
    gen["sexo"] = "general"
    gen = gen.rename(columns={"Casos_semana": "real"})

    def _diff(col: str, sexo: str) -> pd.DataFrame:
        rows = []
        for ent, grp in sub.groupby("Entidad"):
            grp = grp.sort_values("Semana")
            diffs = grp[col].diff().fillna(grp[col]).clip(lower=0)
            for sem, val in zip(grp["Semana"], diffs, strict=False):
                rows.append({"Entidad": ent, "Semana": int(sem), "real": float(val), "sexo": sexo})
        return pd.DataFrame(rows)

    hom = _diff("Acumulado_hombres", "hombres")
    muj = _diff("Acumulado_mujeres", "mujeres")
    long_df = pd.concat(
        [
            gen.rename(columns={"Entidad": "Entidad"})[["Entidad", "Semana", "sexo", "real"]],
            hom,
            muj,
        ],
        ignore_index=True,
    )

    nac = long_df.groupby(["Semana", "sexo"])["real"].sum().reset_index()
    nac["Entidad"] = "Nacional"
    full = pd.concat([long_df, nac[["Entidad", "Semana", "sexo", "real"]]], ignore_index=True)
    return full.rename(columns={"Entidad": "entidad"})[["entidad", "sexo", "Semana", "real"]]


def build_forecasts_2026(weeks_limit: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (yhat semanal 2026, cv_smape por serie/motor) para Dengue."""
    pieces = []
    cv_rows = []
    for motor, path in FORECAST_PATHS.items():
        raw = pd.read_csv(path, low_memory=False)
        raw = raw[raw["meta_padecimiento"] == PADECIMIENTO].copy()
        # CV SMAPE por serie (constante por entidad/sexo en el forecast)
        cv = raw.groupby(["meta_entidad", "meta_modo"])["smape_usado"].first().reset_index()
        cv = cv.rename(
            columns={"meta_entidad": "entidad", "meta_modo": "sexo", "smape_usado": "cv_smape"}
        )
        cv["motor"] = motor
        cv_rows.append(cv)

        df = raw[["ds", "yhat", "meta_entidad", "meta_modo"]].copy()
        df["ds"] = pd.to_datetime(df["ds"])
        df = df[df["ds"].dt.year == 2026]
        df = df.sort_values(["meta_entidad", "meta_modo", "ds"])
        df["Semana"] = df.groupby(["meta_entidad", "meta_modo"]).cumcount() + 1
        df = df[df["Semana"] <= weeks_limit]
        df = df.rename(columns={"meta_entidad": "entidad", "meta_modo": "sexo"})
        df["motor"] = motor
        pieces.append(df[["motor", "entidad", "sexo", "Semana", "yhat"]])
    return pd.concat(pieces, ignore_index=True), pd.concat(cv_rows, ignore_index=True)


def metrics_per_motor(real: pd.DataFrame, fc: pd.DataFrame, cv: pd.DataFrame) -> pd.DataFrame:
    """Por (entidad, sexo) calcula SMAPE/MAE 2026 y CV-SMAPE de cada motor."""
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
            "n_semanas_real_2026": int(len(grp)),
            "total_real_2026": float(grp["real"].sum()),
        }
        for m in MOTORES:
            if m in grp.columns and grp[m].notna().sum() >= 1:
                row[f"smape_2026_{m.lower()}"] = smape(grp["real"], grp[m])
                row[f"mae_2026_{m.lower()}"] = mae(grp["real"], grp[m])
            else:
                row[f"smape_2026_{m.lower()}"] = np.nan
                row[f"mae_2026_{m.lower()}"] = np.nan
            cvv = (
                cv_wide.loc[(ent, sx), m]
                if (ent, sx) in cv_wide.index and m in cv_wide.columns
                else np.nan
            )
            row[f"cv_smape_{m.lower()}"] = float(cvv) if pd.notna(cvv) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _pick(row: pd.Series) -> tuple[str, str, float | None]:
    n = row["n_semanas_real_2026"]
    total = row["total_real_2026"]
    # Selección solo entre motores elegibles (DeepAR/Prophet); Ensemble/Stacking divergen.
    smapes = {m: row[f"smape_2026_{m.lower()}"] for m in MOTORES_ELEGIBLES}
    smapes = {m: v for m, v in smapes.items() if pd.notna(v)}
    maes = {m: row[f"mae_2026_{m.lower()}"] for m in MOTORES_ELEGIBLES}
    maes = {m: v for m, v in maes.items() if pd.notna(v)}
    cvs = {m: row[f"cv_smape_{m.lower()}"] for m in MOTORES_ELEGIBLES}
    cvs = {m: v for m, v in cvs.items() if pd.notna(v)}

    # Regla 1: realidad suficiente + casos suficientes -> SMAPE real (MAE desempate)
    if n >= MIN_WEEKS_REAL and total >= MIN_TOTAL_CASOS and smapes:
        winner = min(smapes, key=lambda m: (round(smapes[m], 4), maes.get(m, np.inf)))
        return winner, "smape_real_2026", smapes[winner]
    # Regla 2: serie casi-cero -> menor MAE (más cercano a cero), "si es 0, es 0"
    if n >= MIN_WEEKS_REAL and total < MIN_TOTAL_CASOS and maes:
        winner = min(maes, key=lambda m: maes[m])
        return winner, "mae_real_2026_casi_cero", None
    # Regla 3: sin realidad reciente -> CV SMAPE
    if cvs:
        winner = min(cvs, key=lambda m: cvs[m])
        return winner, "cv_smape", cvs[winner]
    return "Ensemble", "default", None


def select(metrics: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    picks = out.apply(_pick, axis=1, result_type="expand")
    picks.columns = ["motor_productivo", "criterio_seleccion", "smape_ganador"]
    out = pd.concat([out, picks], axis=1)

    def _just(r: pd.Series) -> str:
        m = r["motor_productivo"]
        crit = r["criterio_seleccion"]
        if crit == "smape_real_2026":
            return f"{m}: menor SMAPE 2026 real={r['smape_ganador']:.2f}% sobre {int(r['n_semanas_real_2026'])} sem"
        if crit == "mae_real_2026_casi_cero":
            return (
                f"{m}: serie casi-cero (total {int(r['total_real_2026'])} casos), menor MAE 2026"
            )
        if crit == "cv_smape":
            return f"{m}: sin realidad 2026 suficiente, menor SMAPE de validación cruzada"
        return f"{m}: default"

    out["justificacion"] = out.apply(_just, axis=1)
    return out


def main() -> None:
    weeks_limit = int(
        pd.read_csv(BOLETIN, usecols=["Padecimiento", "Anio", "Semana"])
        .query("Padecimiento == @PADECIMIENTO and Anio == 2026")["Semana"]
        .max()
    )
    logger.info("Dengue 2026: usando semanas 1..{}", weeks_limit)

    real = build_real_2026(weeks_limit)
    fc, cv = build_forecasts_2026(weeks_limit)
    metrics = metrics_per_motor(real, fc, cv)
    result = select(metrics)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_CSV, index=False)
    result.to_excel(OUT_XLSX, index=False)

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
    logger.info("→ {}", OUT_CSV)
    logger.info("→ {}", OUT_XLSX)


if __name__ == "__main__":
    main()
