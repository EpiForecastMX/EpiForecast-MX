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
from epiforecast.evaluation.real_eval import build_forecasts, build_real, eval_year, smape

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


def _real_neuro(anio: int, weeks_limit: int) -> pd.DataFrame:
    """Real neuro (módulo común) con el nombre de Depresión normalizado para el merge."""
    real = build_real(BOLETIN, NEURO_CONDITIONS, anio, weeks_limit)
    real["padecimiento"] = real["padecimiento"].replace({"Depresión": "Depresion"})
    return real


def _forecasts_neuro(anio: int, weeks_limit: int) -> pd.DataFrame:
    """Forecast neuro (módulo común, alineado por semana ISO) con Depresión normalizada."""
    fc, _cv = build_forecasts(FORECAST_PATHS, NEURO_CONDITIONS, anio, weeks_limit)
    fc["padecimiento"] = fc["padecimiento"].replace({"Depresión": "Depresion"})
    return fc


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
    # Idempotencia: si la tabla ya trae columnas de auditoría 2026 (de una reselección
    # previa, p.ej. en el refresh semanal sin tabla-produccion), se eliminan para que el
    # merge no las duplique con sufijos _x/_y ni el concat genere columnas repetidas.
    _audit_prev = [
        "n_semanas_real_2026",
        "total_real_2026",
        *[f"smape_2026_{m.lower()}" for m in MOTORES],
        "criterio_seleccion",
        "smape_real_2026_ganador",
        "motor_anterior",
    ]
    prod = prod.drop(columns=[c for c in _audit_prev if c in prod.columns])
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

    anio = eval_year(BOLETIN, NEURO_CONDITIONS)  # último año con datos neuro (derivado)
    print(f"Cargando boletín {anio} sem 1-{WEEKS_LIMIT}...")
    real = _real_neuro(anio, WEEKS_LIMIT)
    print(f"  {len(real)} filas reales")

    print(f"Cargando forecasts 4 motores {anio} sem 1-{WEEKS_LIMIT}...")
    fc = _forecasts_neuro(anio, WEEKS_LIMIT)
    print(f"  {len(fc)} filas de forecast")
    if fc.empty or real.empty:
        raise SystemExit(
            "Sin forecasts/real neuro en los all_forecast_*.csv (¿están en Dengue-only?). "
            "Corre 'make predict-all' para la cohorte neuro antes de re-seleccionar."
        )

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
