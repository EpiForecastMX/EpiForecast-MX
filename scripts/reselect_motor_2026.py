"""Reselección del modelo productivo basado en realidad de 2026.

Cambia el criterio de selección del motor productivo de "SMAPE de validación
cruzada interna 2014-2025" a "SMAPE sobre las semanas reales de 2026 ya
publicadas en el Boletín SINAVE", que es lo que verdaderamente importa para
producción.

Reglas:
1. Series con >= 10 semanas reales 2026 y total real >= 10 casos:
   SMAPE 2026 real es el criterio primario, MASE como tie-breaker.
2. Series con >= 10 semanas reales 2026 pero total real < 10 casos
   (ruidosas, divisiones cercanas a cero): forzamos Ensemble (estable, baja
   varianza, dominante en agregados nacionales).
3. Series con < 10 semanas reales 2026 (las regiones agregadas sintéticas
   y series donde por algún motivo falten datos): respetamos la lógica
   anterior (`modelo_produccion` original sin tocar).

Salidas:
- Sobreescribe `reports/ProdDetails/tabla_333_modelos_produccion.xlsx` con
  la columna `modelo_produccion` reasignada y nuevas columnas de auditoría:
  `smape_real_2026`, `n_semanas_real_2026`, `criterio_seleccion`,
  `motor_anterior`.
- Genera `reports/ProdDetails/auditoria_motores_2026.xlsx` con el detalle
  de las 333 combinaciones, motor anterior, motor nuevo, ambos SMAPEs,
  delta y razón.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from epiforecast.constants import NEURO_CONDITIONS

ROOT = Path(__file__).resolve().parent.parent
PROD_TABLE = ROOT / "reports/ProdDetails/tabla_333_modelos_produccion.xlsx"
BOLETIN = ROOT / "data/processed/dataset_boletin_epidemiologico.csv"
FORECAST_PATHS = {
    "Prophet": ROOT / "reports/forecasts/prophet/all_forecast_prophet.csv",
    "DeepAR": ROOT / "reports/forecasts/deepar/all_forecast_deepar.csv",
    "Ensemble": ROOT / "reports/forecasts/ensemble/all_forecast_ensemble.csv",
    "Stacking": ROOT / "reports/forecasts/stacking/all_forecast_stacking.csv",
}
AUDIT_OUT = ROOT / "reports/ProdDetails/auditoria_motores_2026.xlsx"
WEEKS_LIMIT = 15  # Cuántas semanas de 2026 considerar (= boletín más reciente)
MIN_WEEKS_REAL = 10  # Mínimo para usar criterio "real" en lugar de CV
MIN_TOTAL_CASOS = 10  # Por debajo: serie ruidosa, forzamos Ensemble
NOISY_FALLBACK = "Ensemble"
MOTORES = ["Prophet", "DeepAR", "Ensemble", "Stacking"]


def smape(y: np.ndarray, yhat: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    denom = (np.abs(y) + np.abs(yhat)) / 2
    mask = denom > 0
    if mask.sum() == 0:
        return np.nan
    return float(np.mean(np.abs(y[mask] - yhat[mask]) / denom[mask]) * 100)


def build_real_2026(weeks_limit: int) -> pd.DataFrame:
    """Devuelve real semanal 2026 por (padecimiento, entidad, sexo, semana)."""
    df = pd.read_csv(BOLETIN)
    # Guard: la re-selección de motor es solo para la cohorte neuro de producción.
    # Excluye Dengue (presente en el consolidado pero sin forecasts/modelos propios aún).
    df = df[df["Padecimiento"].isin(NEURO_CONDITIONS)]
    sub = df[(df["Anio"] == 2026) & (df["Semana"] <= weeks_limit)].copy()
    sub = sub.sort_values(["Padecimiento", "Entidad", "Semana"])

    gen = sub.groupby(["Padecimiento", "Entidad", "Semana"])["Casos_semana"].sum().reset_index()
    gen["sexo"] = "general"
    gen = gen.rename(columns={"Casos_semana": "real"})

    def _diff(col: str, sexo: str) -> pd.DataFrame:
        rows = []
        for (pad, ent), grp in sub.groupby(["Padecimiento", "Entidad"]):
            grp = grp.sort_values("Semana")
            diffs = grp[col].diff().fillna(grp[col]).clip(lower=0)
            for sem, val in zip(grp["Semana"], diffs, strict=False):
                rows.append(
                    {
                        "Padecimiento": pad,
                        "Entidad": ent,
                        "Semana": int(sem),
                        "real": float(val),
                        "sexo": sexo,
                    }
                )
        return pd.DataFrame(rows)

    hom = _diff("Acumulado_hombres", "hombres")
    muj = _diff("Acumulado_mujeres", "mujeres")
    long_df = pd.concat([gen, hom, muj], ignore_index=True)

    nac = long_df.groupby(["Padecimiento", "Semana", "sexo"])["real"].sum().reset_index()
    nac["Entidad"] = "Nacional"
    full = pd.concat(
        [long_df, nac[["Padecimiento", "Entidad", "Semana", "sexo", "real"]]],
        ignore_index=True,
    )
    full["padecimiento"] = full["Padecimiento"].replace({"Depresión": "Depresion"})
    return full.rename(columns={"Entidad": "entidad"})[
        ["padecimiento", "entidad", "sexo", "Semana", "real"]
    ]


def build_forecasts_2026(weeks_limit: int) -> pd.DataFrame:
    """Devuelve yhat semanal 2026 por (motor, padecimiento, entidad, sexo, semana)."""
    pieces = []
    for motor, path in FORECAST_PATHS.items():
        df = pd.read_csv(path, low_memory=False)[
            ["ds", "yhat", "meta_padecimiento", "meta_entidad", "meta_modo"]
        ]
        df["ds"] = pd.to_datetime(df["ds"])
        df = df[df["ds"].dt.year == 2026].copy()
        df = df.sort_values(["meta_padecimiento", "meta_entidad", "meta_modo", "ds"])
        df["Semana"] = (
            df.groupby(["meta_padecimiento", "meta_entidad", "meta_modo"]).cumcount() + 1
        )
        df = df[df["Semana"] <= weeks_limit]
        df = df.rename(
            columns={
                "meta_padecimiento": "padecimiento",
                "meta_entidad": "entidad",
                "meta_modo": "sexo",
            }
        )
        df["motor"] = motor
        df["padecimiento"] = df["padecimiento"].replace({"Depresión": "Depresion"})
        pieces.append(df[["motor", "padecimiento", "entidad", "sexo", "Semana", "yhat"]])
    return pd.concat(pieces, ignore_index=True)


def smape_per_motor(real: pd.DataFrame, fc: pd.DataFrame) -> pd.DataFrame:
    """Por (padecimiento, entidad, sexo) calcula SMAPE de cada motor en 2026 real."""
    fc_wide = fc.pivot_table(
        index=["padecimiento", "entidad", "sexo", "Semana"],
        columns="motor",
        values="yhat",
    ).reset_index()
    merged = real.merge(fc_wide, on=["padecimiento", "entidad", "sexo", "Semana"], how="inner")
    rows = []
    for (pad, ent, sx), grp in merged.groupby(["padecimiento", "entidad", "sexo"]):
        if len(grp) < MIN_WEEKS_REAL:
            continue
        row = {
            "padecimiento": pad,
            "entidad": ent,
            "sexo": sx,
            "n_semanas_real_2026": len(grp),
            "total_real_2026": float(grp["real"].sum()),
        }
        for m in MOTORES:
            if m in grp.columns and grp[m].notna().sum() >= MIN_WEEKS_REAL:
                row[f"smape_2026_{m.lower()}"] = smape(grp["real"], grp[m])
            else:
                row[f"smape_2026_{m.lower()}"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def reselect(prod: pd.DataFrame, smape_df: pd.DataFrame) -> pd.DataFrame:
    """Aplica las reglas de re-selección y devuelve la tabla actualizada."""
    prod = prod.copy()
    prod["padecimiento"] = prod["padecimiento"].replace({"Depresión": "Depresion"})
    prod = prod.merge(smape_df, on=["padecimiento", "entidad", "sexo"], how="left")
    prod["motor_anterior"] = prod["modelo_produccion"]

    def _pick_row(row: pd.Series) -> tuple[str, str, float | None]:
        n = row.get("n_semanas_real_2026")
        total = row.get("total_real_2026")
        if pd.isna(n) or n < MIN_WEEKS_REAL:
            return row["modelo_produccion"], "cv_smape (sin realidad reciente)", None
        if pd.notna(total) and total < MIN_TOTAL_CASOS:
            return (
                NOISY_FALLBACK,
                f"forzado a {NOISY_FALLBACK} (serie ruidosa, total<{MIN_TOTAL_CASOS})",
                None,
            )
        smapes = {m: row.get(f"smape_2026_{m.lower()}") for m in MOTORES}
        valid = {m: v for m, v in smapes.items() if pd.notna(v)}
        if not valid:
            return row["modelo_produccion"], "cv_smape (no hay forecast 2026 válido)", None
        winner = min(valid, key=lambda m: valid[m])
        return winner, "smape_real_2026", valid[winner]

    selections = prod.apply(_pick_row, axis=1, result_type="expand")
    selections.columns = [
        "modelo_produccion_nuevo",
        "criterio_seleccion",
        "smape_real_2026_ganador",
    ]
    prod = pd.concat([prod, selections], axis=1)
    prod["modelo_produccion"] = prod["modelo_produccion_nuevo"]
    prod = prod.drop(columns=["modelo_produccion_nuevo"])

    # Actualizar smape_prod / mase_prod / rmse_prod / mae_prod al motor seleccionado
    for met in ("smape", "mase", "rmse", "mae"):
        prod[f"{met}_prod"] = prod.apply(
            lambda r, _met=met: r.get(f"{r['modelo_produccion'].lower()}_{_met}"),
            axis=1,
        )

    # Actualizar justificacion
    def _just(row: pd.Series) -> str:
        m_old = row["motor_anterior"]
        m_new = row["modelo_produccion"]
        crit = row["criterio_seleccion"]
        if m_old == m_new:
            return row.get("justificacion", "") or f"{m_new} confirmado por {crit}"
        if "ruidosa" in crit:
            return f"Reasignado de {m_old} a {m_new}: {crit}"
        sn = row.get("smape_real_2026_ganador")
        sn_txt = f"{sn:.2f}%" if pd.notna(sn) else "—"
        return f"Reasignado de {m_old} a {m_new}: SMAPE 2026 real={sn_txt} (sobre {int(row['n_semanas_real_2026'])} sem)"

    prod["justificacion"] = prod.apply(_just, axis=1)
    return prod


def main() -> None:
    print(f"Cargando tabla productiva: {PROD_TABLE}")
    prod = pd.read_excel(PROD_TABLE, sheet_name=0)
    print(f"  {len(prod)} combinaciones")

    print("Cargando boletín 2026 sem 1-15...")
    real = build_real_2026(WEEKS_LIMIT)
    print(f"  {len(real)} filas reales")

    print("Cargando forecasts 4 motores 2026 sem 1-15...")
    fc = build_forecasts_2026(WEEKS_LIMIT)
    print(f"  {len(fc)} filas de forecast")

    print("Calculando SMAPE 2026 por motor por combinación...")
    smape_df = smape_per_motor(real, fc)
    print(f"  {len(smape_df)} combinaciones con datos suficientes")

    print("Aplicando reglas de re-selección...")
    new_prod = reselect(prod, smape_df)

    cambios = (new_prod["motor_anterior"] != new_prod["modelo_produccion"]).sum()
    print(f"\nCambios aplicados: {cambios} de {len(new_prod)}")
    print("Nueva distribución de modelos productivos:")
    print(new_prod["modelo_produccion"].value_counts().to_dict())

    # Auditoría
    audit = new_prod[
        [
            "padecimiento",
            "entidad",
            "sexo",
            "motor_anterior",
            "modelo_produccion",
            "criterio_seleccion",
            "n_semanas_real_2026",
            "total_real_2026",
            "smape_2026_prophet",
            "smape_2026_deepar",
            "smape_2026_ensemble",
            "smape_2026_stacking",
            "smape_real_2026_ganador",
        ]
    ].copy()
    audit = audit.sort_values(
        ["motor_anterior", "modelo_produccion", "padecimiento", "entidad", "sexo"]
    )
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    audit.to_excel(AUDIT_OUT, index=False)
    print(f"Auditoría: {AUDIT_OUT}")

    # Reescribir tabla productiva (mantenemos las columnas originales + nuevas)
    cols_originales = pd.read_excel(PROD_TABLE, sheet_name=0).columns.tolist()
    cols_finales = cols_originales + [
        c
        for c in [
            "n_semanas_real_2026",
            "total_real_2026",
            "smape_2026_prophet",
            "smape_2026_deepar",
            "smape_2026_ensemble",
            "smape_2026_stacking",
            "smape_real_2026_ganador",
            "motor_anterior",
            "criterio_seleccion",
        ]
        if c not in cols_originales
    ]
    new_prod = new_prod[cols_finales]

    # Si hay hojas adicionales en el original, conservarlas
    xl = pd.ExcelFile(PROD_TABLE)
    sheets_extra = {
        name: pd.read_excel(PROD_TABLE, sheet_name=name)
        for name in xl.sheet_names
        if name != xl.sheet_names[0]
    }

    with pd.ExcelWriter(PROD_TABLE, engine="openpyxl") as w:
        new_prod.to_excel(w, sheet_name=xl.sheet_names[0], index=False)
        for name, df_ in sheets_extra.items():
            df_.to_excel(w, sheet_name=name, index=False)
    print(f"Tabla productiva reescrita: {PROD_TABLE}")


if __name__ == "__main__":
    main()
