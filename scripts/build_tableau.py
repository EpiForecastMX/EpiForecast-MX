# scripts/build_tableau.py
#
# Genera tableau_model.xlsx con 5 hojas normalizadas para el modelo relacional de Tableau.
#
# La hoja "scaffold" es la tabla ancla central: contiene la unión completa de
# (ds, entidad, padecimiento, meta_modo) del histórico Y del pronóstico, garantizando
# que las fechas futuras (2026-2027) aparezcan aunque no tengan datos reales.
#
# Modelo relacional recomendado en Tableau:
#
#   scaffold (ancla — 4 llaves)
#   ├── real        on ds + entidad + padecimiento   [3 llaves, sin meta_modo]
#   ├── forecast    on ds + entidad + padecimiento + meta_modo
#   ├── metricas    on entidad + padecimiento + meta_modo
#   └── entidades   on entidad
#
# Hoja "real": una fila por (ds, entidad, padecimiento) con los 3 incrementos.
#   - No se expande por meta_modo → 3x menos filas que el CSV plano anterior.
#   - y_real eliminado (redundante; usar Calc_Y_Selected en Tableau).
#
# Hoja "metricas": modelo_productivo y archivo_modelo_usado movidos aquí desde forecast
#   (son constantes por grupo, no varían por fecha).
#
# Filtros en Tableau deben venir de scaffold.entidad, scaffold.padecimiento,
# scaffold.meta_modo y scaffold.ds — nunca de real.* o forecast.* directamente.

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.cohorts import filter_neuro
from epiforecast.utils.config import conf, logger

_METRICS = ["rmse", "mae", "mape", "smape", "mase"]
_MODELS = ["prophet", "deepar", "ensemble", "stacking"]

# Contrato explícito de columnas por hoja — lo que llega a Tableau
REAL_COLS = [
    "ds",
    "entidad",
    "padecimiento",
    "incrementos_total",
    "incrementos_hombres",
    "incrementos_mujeres",
]

FORECAST_COLS = [
    "ds",
    "entidad",
    "padecimiento",
    "meta_modo",
    "yhat",
]

METRICAS_COLS = [
    "entidad",
    "padecimiento",
    "meta_modo",
    "modelo_productivo",
    "archivo_modelo_usado",
    "rmse",
    "mae",
    "mape",
    "smape",
    "mase",
]

ENTIDAD_COLS = [
    "entidad",
    "Region",
    "Region Socio-Urbana",
    "Superficie_km2",
    "densidad_poblacion",
    "densidad_poblacional_percentil",
    "extension_territorial_percentil",
    "tamano_poblacional_predefinido",
    "tamano_poblacional_grupo_percentil",
    "ratio_h_m_cat",
    "Poblacion Hombres",
    "Poblacion Mujeres",
]

# Llave compuesta que identifica unívocamente cada observación/pronóstico
SCAFFOLD_COLS = ["ds", "entidad", "padecimiento", "meta_modo"]


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------


def load_inputs(in_real: Path, forecast_base: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carga el histórico INEGI y une los archivos all_forecast_*.csv de los 4 modelos."""
    if not in_real.exists():
        raise FileNotFoundError(f"No se encontró histórico: {in_real}")

    logger.info("Leyendo histórico: {}", in_real)
    real = pd.read_csv(in_real)
    # Guard: Tableau es solo de la cohorte neuro de producción (Dengue tiene su pipeline).
    real = filter_neuro(real)

    forecast_files = sorted(forecast_base.rglob("all_forecast_*.csv"))
    if not forecast_files:
        raise FileNotFoundError(f"No se encontraron archivos forecast en: {forecast_base}")

    # Une pronósticos de cada modelo en un DataFrame ancho (yhat_prophet, yhat_deepar, …)
    join_cols = ["ds", "meta_padecimiento", "meta_entidad", "meta_modo"]
    all_fcst = pd.DataFrame()

    for fcst_path in forecast_files:
        model_name = fcst_path.stem.replace("all_forecast_", "")
        logger.info("Leyendo forecast ({}): {}", model_name, fcst_path)

        df = pd.read_csv(fcst_path)
        df = filter_neuro(df, col="meta_padecimiento")  # defensivo: excluye forecasts no-neuro

        # Elimina columnas yhat_ internas del modelo (bandas de incertidumbre, etc.)
        internal_yhat = [
            c
            for c in df.columns
            if c.startswith("yhat_") and c not in ("yhat_lower", "yhat_upper")
        ]
        if internal_yhat:
            df = df.drop(columns=internal_yhat)

        df = df.rename(columns={"yhat": f"yhat_{model_name}"})

        if all_fcst.empty:
            all_fcst = df
        else:
            cols = join_cols + [f"yhat_{model_name}"]
            all_fcst = all_fcst.merge(df[cols], on=join_cols, how="outer")

    return real, all_fcst


# ---------------------------------------------------------------------------
# Preparación
# ---------------------------------------------------------------------------


def prepare_inputs(real: pd.DataFrame, fcst: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normaliza nombres de columnas y resuelve duplicados de fecha por semana ISO."""
    real["Fecha"] = pd.to_datetime(real["Fecha"], errors="coerce")
    fcst["ds"] = pd.to_datetime(fcst["ds"], errors="coerce")

    n_bad_real = int(real["Fecha"].isna().sum())
    n_bad_fcst = int(fcst["ds"].isna().sum())
    if n_bad_real:
        logger.warning("Fechas inválidas en histórico (Fecha): {}. Se eliminan.", n_bad_real)
    if n_bad_fcst:
        logger.warning("Fechas inválidas en forecast (ds): {}. Se eliminan.", n_bad_fcst)

    real = real.dropna(subset=["Fecha"]).rename(
        columns={
            "Fecha": "ds",
            "Padecimiento": "padecimiento",
            "Entidad": "entidad",
            "region_salud_mental": "Region Socio-Urbana",
            "Total": "Poblacion Total",
            "Hombres": "Poblacion Hombres",
            "Mujeres": "Poblacion Mujeres",
        }
    )
    fcst = fcst.dropna(subset=["ds"]).copy()
    fcst["padecimiento"] = fcst["meta_padecimiento"]
    fcst["entidad"] = fcst["meta_entidad"]

    if "Region Socio-Urbana" in real.columns:
        real["Region Socio-Urbana"] = (
            "Region " + real["Region Socio-Urbana"].astype(str).str.strip()
        )

    # Desempate semana ISO: cuando Semana==1 gana sobre Semana==53 en el mismo lunes
    if "Semana" in real.columns:
        real["_wk_pref"] = (real["Semana"] == 1).astype(int)
        real = (
            real.sort_values(
                ["padecimiento", "entidad", "ds", "_wk_pref"],
                ascending=[True, True, True, False],
            )
            .drop_duplicates(["padecimiento", "entidad", "ds"], keep="first")
            .drop(columns="_wk_pref")
        )

    return real.reset_index(drop=True), fcst.reset_index(drop=True)


def agregar_agregados_geograficos(real: pd.DataFrame) -> pd.DataFrame:
    """Agrega filas de Nacional y por Región Socio-Urbana para visualizaciones de resumen."""
    sum_cols = [
        c
        for c in ["incrementos_total", "incrementos_hombres", "incrementos_mujeres"]
        if c in real.columns
    ]

    frames = [real]

    nacional = (
        real.groupby(["ds", "padecimiento"], as_index=False)[sum_cols]
        .sum()
        .assign(entidad="Nacional", **{"Region Socio-Urbana": "Nacional"})
    )
    frames.append(nacional.reindex(columns=real.columns, fill_value=pd.NA))

    if "Region Socio-Urbana" in real.columns:
        regional = (
            real.groupby(["ds", "padecimiento", "Region Socio-Urbana"], as_index=False)[sum_cols]
            .sum()
            .assign(entidad=lambda x: x["Region Socio-Urbana"])
        )
        frames.append(regional.reindex(columns=real.columns, fill_value=pd.NA))

    out = pd.concat(frames, ignore_index=True)
    logger.info("Agregados geográficos -> filas: {}", len(out))
    return out


def expand_real_by_modo(real: pd.DataFrame) -> pd.DataFrame:
    """Expande el histórico a tres filas por observación (general, hombres, mujeres).

    Cada fila activa una sola medida en y_real para que Tableau pueda filtrar
    por meta_modo sin necesidad de campos calculados adicionales.
    """
    g = real.assign(meta_modo="general", y_real=real["incrementos_total"]).copy()
    h = real.assign(meta_modo="hombres", y_real=real["incrementos_hombres"]).copy()
    m = real.assign(meta_modo="mujeres", y_real=real["incrementos_mujeres"]).copy()

    # Limpia columnas del modo inactivo para no confundir en Tableau
    g[["incrementos_hombres", "incrementos_mujeres"]] = pd.NA
    h[["incrementos_total", "incrementos_mujeres"]] = pd.NA
    m[["incrementos_total", "incrementos_hombres"]] = pd.NA

    out = pd.concat([g, h, m], ignore_index=True)
    return out.sort_values(["padecimiento", "entidad", "ds", "meta_modo"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Selección de modelo productivo y métricas
# ---------------------------------------------------------------------------


def _load_prod_assignments() -> pd.DataFrame | None:
    """Lee asignaciones de modelo del Excel de producción si existe."""
    prod_path = Path("reports/ProdDetails/tabla_333_modelos_produccion.xlsx")
    if not prod_path.exists():
        return None
    try:
        prod = pd.read_excel(prod_path, sheet_name="Produccion")
        # Normalizar nombre de entidad: region_ -> Region
        prod["entidad"] = prod["entidad"].str.replace(r"^region_", "Region ", regex=True)
        # Normalizar nombre de modelo a minúsculas (Tableau usa lowercase)
        prod["modelo_produccion"] = prod["modelo_produccion"].str.lower()
        return prod[["padecimiento", "entidad", "sexo", "modelo_produccion"]].rename(
            columns={"sexo": "meta_modo", "modelo_produccion": "_prod_modelo"}
        )
    except Exception as e:
        logger.warning("No se pudo leer Excel de producción: {}", e)
        return None


def _seleccionar_modelo_productivo(
    df: pd.DataFrame,
    grp: list[str],
    yhat_model_cols: list[str],
) -> pd.DataFrame:
    """Elige el modelo productivo por grupo.

    Si existe el Excel de producción (tabla_333_modelos_produccion.xlsx),
    usa sus asignaciones para garantizar consistencia. Si no, calcula
    por SMAPE menor (fallback).
    """
    if not yhat_model_cols:
        df["yhat"] = np.nan
        df["modelo_productivo"] = pd.NA
        return df

    # --- Intentar leer asignaciones del Excel de producción ---
    prod_assign = _load_prod_assignments()
    if prod_assign is not None:
        df = df.merge(prod_assign, on=grp, how="left")
        df["modelo_productivo"] = df["_prod_modelo"]
        df = df.drop(columns="_prod_modelo")

        # Asignar yhat según el modelo ganador
        df["yhat"] = np.nan
        for col in yhat_model_cols:
            modelo = col.replace("yhat_", "")
            mask = df["modelo_productivo"].eq(modelo)
            df.loc[mask, "yhat"] = df.loc[mask, col]

        # Fallback para series sin asignación en el Excel
        no_model = df["modelo_productivo"].isna()
        if no_model.any():
            fallback_col = next(
                (
                    c
                    for c in ["yhat_deepar", "yhat_ensemble", "yhat_prophet"]
                    if c in yhat_model_cols
                ),
                yhat_model_cols[0],
            )
            df.loc[no_model, "modelo_productivo"] = fallback_col.replace("yhat_", "")
            df.loc[no_model, "yhat"] = df.loc[no_model, fallback_col]
            logger.warning(
                "Series sin asignación en Excel de producción: {}. Fallback a {}.",
                int(no_model.sum() / max(1, len(df[df["y_real"].notna()]))),
                fallback_col,
            )

        # Rellenar yhat faltantes con cualquier modelo disponible
        still_na = df["yhat"].isna()
        for col in yhat_model_cols:
            df.loc[still_na, "yhat"] = df.loc[still_na, col]
            still_na = df["yhat"].isna()

        winners = (
            df[grp + ["modelo_productivo"]].drop_duplicates()["modelo_productivo"].value_counts()
        )
        logger.info("Modelo productivo (desde Excel producción) -> {}", dict(winners))
        return df

    # --- Fallback: selección por SMAPE calculado ---
    logger.warning("Excel de producción no encontrado; selección por SMAPE calculado.")

    fallback_order = ["yhat_ensemble", "yhat_stacking", "yhat_prophet", "yhat_deepar"]
    fallback_col = next((c for c in fallback_order if c in yhat_model_cols), yhat_model_cols[0])

    rows = df[df["y_real"].notna()].copy()
    if rows.empty:
        df["modelo_productivo"] = fallback_col.replace("yhat_", "")
        df["yhat"] = df[fallback_col]
        for c in yhat_model_cols:
            if c != fallback_col:
                df["yhat"] = df["yhat"].fillna(df[c])
        logger.warning("Sin datos reales para SMAPE; fallback a {}", fallback_col)
        return df

    smape_parts = []
    for col in yhat_model_cols:
        modelo = col.replace("yhat_", "")
        tmp = rows[grp + ["y_real", col]].copy()
        tmp["y_real"] = pd.to_numeric(tmp["y_real"], errors="coerce")
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
        tmp = tmp.dropna(subset=["y_real", col])
        if tmp.empty:
            continue

        denom = (tmp["y_real"].abs() + tmp[col].abs()).replace(0, np.nan)
        tmp["_smape"] = (2 * (tmp["y_real"] - tmp[col]).abs() / denom) * 100

        agg = tmp.groupby(grp, as_index=False)["_smape"].mean()
        agg["modelo_productivo"] = modelo
        agg["yhat_col"] = col
        smape_parts.append(agg)

    if not smape_parts:
        df["modelo_productivo"] = fallback_col.replace("yhat_", "")
        df["yhat"] = df[fallback_col]
        for c in yhat_model_cols:
            if c != fallback_col:
                df["yhat"] = df["yhat"].fillna(df[c])
        logger.warning("No se pudo calcular SMAPE; fallback a {}", fallback_col)
        return df

    smape_all = pd.concat(smape_parts, ignore_index=True)
    best = smape_all.loc[
        smape_all.groupby(grp)["_smape"].idxmin(),
        grp + ["modelo_productivo", "yhat_col"],
    ]

    df = df.merge(best, on=grp, how="left")

    df["yhat"] = np.nan
    for col in yhat_model_cols:
        mask = df["yhat_col"].eq(col)
        df.loc[mask, "yhat"] = df.loc[mask, col]

    no_model = df["modelo_productivo"].isna()
    if no_model.any():
        df.loc[no_model, "modelo_productivo"] = fallback_col.replace("yhat_", "")
        df.loc[no_model, "yhat"] = df.loc[no_model, fallback_col]
        for c in yhat_model_cols:
            if c != fallback_col:
                still_na = no_model & df["yhat"].isna()
                df.loc[still_na, "yhat"] = df.loc[still_na, c]

    df = df.drop(columns="yhat_col", errors="ignore")

    winners = df[grp + ["modelo_productivo"]].drop_duplicates()["modelo_productivo"].value_counts()
    logger.info("Modelo productivo por SMAPE -> {}", dict(winners))
    return df


def _calcular_metricas(
    df: pd.DataFrame, grp: list[str], yhat_model_cols: list[str]
) -> pd.DataFrame:
    """Calcula RMSE, MAE, MAPE, SMAPE y MASE por modelo y asigna las métricas del ganador."""
    if "y_real" not in df.columns or not yhat_model_cols:
        return df

    rows = df[df["y_real"].notna()].copy()
    rows["y_real"] = pd.to_numeric(rows["y_real"], errors="coerce")
    rows = rows.dropna(subset=["y_real"])
    if rows.empty:
        return df

    metric_parts = []

    for col in yhat_model_cols:
        modelo = col.replace("yhat_", "")
        tmp = rows[grp + ["ds", "y_real", col]].copy()
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
        tmp = tmp.dropna(subset=[col])
        if tmp.empty:
            continue

        tmp = tmp.sort_values(grp + ["ds"])
        y, yh = tmp["y_real"], tmp[col]
        err = (y - yh).abs()

        tmp["_rmse_sq"] = (y - yh) ** 2
        tmp["_mae"] = err
        tmp["_mape"] = (err / y.abs().replace(0, np.nan)) * 100
        tmp["_smape"] = (2 * err / (y.abs() + yh.abs()).replace(0, np.nan)) * 100
        # MASE usa diferenciación anual (52 semanas) como benchmark naive
        tmp["_naive_diff"] = tmp.groupby(grp)["y_real"].diff(52).abs()

        agg = tmp.groupby(grp, as_index=False).agg(
            _rmse_sq=("_rmse_sq", "mean"),
            _mae=("_mae", "mean"),
            _mape=("_mape", "mean"),
            _smape=("_smape", "mean"),
            _naive_mean=("_naive_diff", "mean"),
        )

        agg[f"rmse_{modelo}"] = agg["_rmse_sq"] ** 0.5
        agg[f"mae_{modelo}"] = agg["_mae"]
        agg[f"mape_{modelo}"] = agg["_mape"]
        agg[f"smape_{modelo}"] = agg["_smape"]
        agg[f"mase_{modelo}"] = agg["_mae"] / agg["_naive_mean"].replace(0, np.nan)

        metric_parts.append(agg[grp + [f"{m}_{modelo}" for m in _METRICS]])

    if not metric_parts:
        return df

    metrics = metric_parts[0]
    for other in metric_parts[1:]:
        metrics = metrics.merge(other, on=grp, how="outer")

    df = df.merge(metrics, on=grp, how="left")

    # Promueve las métricas del modelo ganador a las columnas canónicas (rmse, mae, etc.)
    for m in _METRICS:
        df[m] = np.nan
        for mod in _MODELS:
            col = f"{m}_{mod}"
            if col in df.columns:
                mask = df["modelo_productivo"].eq(mod)
                df.loc[mask, m] = df.loc[mask, col]

    # Overlay: si existe el Excel de producción, usar sus métricas CV como canónicas
    prod_path = Path("reports/ProdDetails/tabla_333_modelos_produccion.xlsx")
    if prod_path.exists():
        try:
            prod = pd.read_excel(prod_path, sheet_name="Produccion")
            prod["entidad"] = prod["entidad"].str.replace(r"^region_", "Region ", regex=True)
            prod_metrics = prod[
                [
                    "padecimiento",
                    "entidad",
                    "sexo",
                    "smape_prod",
                    "mase_prod",
                    "rmse_prod",
                    "mae_prod",
                ]
            ].rename(
                columns={
                    "sexo": "meta_modo",
                    "smape_prod": "_p_smape",
                    "mase_prod": "_p_mase",
                    "rmse_prod": "_p_rmse",
                    "mae_prod": "_p_mae",
                }
            )
            df = df.merge(prod_metrics, on=grp, how="left")
            for canon, src in [
                ("smape", "_p_smape"),
                ("mase", "_p_mase"),
                ("rmse", "_p_rmse"),
                ("mae", "_p_mae"),
            ]:
                mask = df[src].notna()
                df.loc[mask, canon] = df.loc[mask, src]
            df = df.drop(columns=["_p_smape", "_p_mase", "_p_rmse", "_p_mae"])
            logger.info("Métricas canónicas alineadas con Excel de producción.")
        except Exception as e:
            logger.warning("No se pudieron leer métricas de producción: {}", e)

    return df


# ---------------------------------------------------------------------------
# Construcción del modelo base
# ---------------------------------------------------------------------------


def build_base(real_long: pd.DataFrame, fcst: pd.DataFrame) -> pd.DataFrame:
    """Une histórico y pronósticos, selecciona el mejor modelo por SMAPE y calcula métricas."""
    join_cols = ["ds", "padecimiento", "entidad", "meta_modo"]

    if real_long.duplicated(join_cols).any():
        raise ValueError("Duplicados en real_long para llaves de join.")
    if fcst.duplicated(join_cols).any():
        raise ValueError("Duplicados en forecast para llaves de join.")

    base = real_long.merge(fcst, how="outer", on=join_cols, validate="m:1")

    bad_keys = base[join_cols].isna().sum()
    bad_keys = bad_keys[bad_keys > 0]
    if not bad_keys.empty:
        detail = ", ".join(f"{c}: {n}" for c, n in bad_keys.items())
        raise ValueError(f"NaN en llaves críticas del modelo base. Detalle -> {detail}")

    grp = ["padecimiento", "entidad", "meta_modo"]
    yhat_model_cols = [
        c for c in base.columns if c.startswith("yhat_") and c not in ("yhat_lower", "yhat_upper")
    ]

    base = _seleccionar_modelo_productivo(base, grp, yhat_model_cols)
    base = _calcular_metricas(base, grp, yhat_model_cols)
    base = base.sort_values(["padecimiento", "entidad", "ds", "meta_modo"]).reset_index(drop=True)

    logger.info("Modelo base construido -> filas: {} | cols: {}", len(base), base.shape[1])
    return base


# ---------------------------------------------------------------------------
# Construcción de hojas de salida
# ---------------------------------------------------------------------------


def _first_non_null(s: pd.Series):
    s = s.dropna()
    return s.iloc[0] if not s.empty else pd.NA


def make_fact_real(real: pd.DataFrame) -> pd.DataFrame:
    """Hoja 'real': una fila por (ds, entidad, padecimiento) con los tres incrementos."""
    fact = real[[c for c in REAL_COLS if c in real.columns]].copy()
    fact = fact.drop_duplicates(["ds", "padecimiento", "entidad"])

    if fact.duplicated(["ds", "padecimiento", "entidad"]).any():
        raise ValueError("fact_real tiene duplicados en la llave.")

    return fact.sort_values(["padecimiento", "entidad", "ds"]).reset_index(drop=True)


def make_fact_forecast(base: pd.DataFrame) -> pd.DataFrame:
    """Hoja 'forecast': pronósticos del modelo productivo, redondeados a enteros."""
    fact = base[[c for c in FORECAST_COLS if c in base.columns]].copy()
    fact = fact.drop_duplicates(["ds", "padecimiento", "entidad", "meta_modo"])

    if fact.duplicated(["ds", "padecimiento", "entidad", "meta_modo"]).any():
        raise ValueError("fact_forecast tiene duplicados en la llave.")

    fact["yhat"] = pd.to_numeric(fact["yhat"], errors="coerce").round(0).astype("Int64")
    return fact.sort_values(["padecimiento", "entidad", "ds", "meta_modo"]).reset_index(drop=True)


def make_fact_metricas(base: pd.DataFrame) -> pd.DataFrame:
    """Hoja 'metricas': una fila por serie con las métricas y modelo productivo."""
    fact = base[[c for c in METRICAS_COLS if c in base.columns]].copy()
    fact = fact.drop_duplicates(["padecimiento", "entidad", "meta_modo"])

    if fact.duplicated(["padecimiento", "entidad", "meta_modo"]).any():
        raise ValueError("fact_metricas tiene duplicados en la llave.")

    metric_cols = [c for c in _METRICS if c in fact.columns]
    fact[metric_cols] = fact[metric_cols].round(4)

    return fact.sort_values(["padecimiento", "entidad", "meta_modo"]).reset_index(drop=True)


def make_dim_entidad(real: pd.DataFrame) -> pd.DataFrame:
    """Hoja 'entidades': atributos geográficos y demográficos por entidad federativa."""
    cols = [c for c in ENTIDAD_COLS if c in real.columns]
    if "entidad" not in cols:
        raise ValueError("No existe la columna 'entidad' para dim_entidad.")

    dim = (
        real[cols]
        .groupby("entidad", as_index=False)
        .agg({c: _first_non_null for c in cols if c != "entidad"})
        .sort_values("entidad")
        .reset_index(drop=True)
    )

    if dim["entidad"].duplicated().any():
        raise ValueError("dim_entidad tiene duplicados.")

    return dim


def make_scaffold(real_long: pd.DataFrame, fact_forecast: pd.DataFrame) -> pd.DataFrame:
    """Hoja 'scaffold': tabla ancla central del modelo relacional de Tableau.

    Contiene todas las combinaciones únicas de (ds, entidad, padecimiento, meta_modo)
    que existen en el histórico o en los pronósticos. Al relacionar 'real' y 'forecast'
    con scaffold sobre estas 4 llaves, cualquier filtro sobre scaffold se propaga
    automáticamente a ambas hojas — sin necesidad de duplicar filtros.
    """
    r = real_long[SCAFFOLD_COLS].drop_duplicates()
    f = fact_forecast[SCAFFOLD_COLS].drop_duplicates()

    scaffold = (
        pd.concat([r, f], ignore_index=True)
        .drop_duplicates()
        .sort_values(SCAFFOLD_COLS)
        .reset_index(drop=True)
    )
    logger.info("Scaffold construido -> filas: {}", len(scaffold))
    return scaffold


# ---------------------------------------------------------------------------
# Salida
# ---------------------------------------------------------------------------


def save_outputs(
    fact_real: pd.DataFrame,
    fact_forecast: pd.DataFrame,
    fact_metricas: pd.DataFrame,
    dim_entidad: pd.DataFrame,
    scaffold: pd.DataFrame,
    out_dir: Path,
) -> None:
    """Escribe tableau_model.xlsx con las 5 hojas del modelo relacional."""
    directory_manager.asegurar_ruta(out_dir)
    out_file = out_dir / "tableau_model.xlsx"

    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        scaffold.to_excel(writer, sheet_name="scaffold", index=False)
        fact_real.to_excel(writer, sheet_name="real", index=False)
        fact_forecast.to_excel(writer, sheet_name="forecast", index=False)
        fact_metricas.to_excel(writer, sheet_name="metricas", index=False)
        dim_entidad.to_excel(writer, sheet_name="entidades", index=False)

    logger.success(
        "Excel Tableau generado: {} | sheets={{scaffold:{}, real:{}, forecast:{}, metricas:{}, entidades:{}}}",
        out_file,
        len(scaffold),
        len(fact_real),
        len(fact_forecast),
        len(fact_metricas),
        len(dim_entidad),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    in_real = Path(conf["data"]["data_inegi"])
    forecast_base = Path(conf["paths"]["reports"]) / "forecasts"
    out_dir = Path(conf["data"]["tableau"]).parent

    real, fcst = load_inputs(in_real, forecast_base)
    real, fcst = prepare_inputs(real, fcst)

    # Agrega filas de Nacional y regiones antes de construir la dimensión de entidades
    real = agregar_agregados_geograficos(real)
    dim_entidad = make_dim_entidad(real)

    # Expande a tres filas por modo (general/hombres/mujeres) y construye el modelo base
    real_long = expand_real_by_modo(real)
    base = build_base(real_long, fcst)

    fact_real = make_fact_real(real)
    fact_forecast = make_fact_forecast(base)
    fact_metricas = make_fact_metricas(base)
    scaffold = make_scaffold(real_long, fact_forecast)

    save_outputs(
        fact_real=fact_real,
        fact_forecast=fact_forecast,
        fact_metricas=fact_metricas,
        dim_entidad=dim_entidad,
        scaffold=scaffold,
        out_dir=out_dir,
    )


if __name__ == "__main__":
    main()
