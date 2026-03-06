# scripts/build_tableau.py
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger

_METRICS = ["rmse", "mae", "mape", "smape", "mase"]
_MODELS = ["prophet", "deepar", "ensemble", "stacking"]

KEEP_COLS_TWB = [
    "ds",
    "entidad",
    "padecimiento",
    "meta_modo",
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
    "incrementos_total",
    "incrementos_hombres",
    "incrementos_mujeres",
    "yhat",
    "archivo_modelo_usado",
    "modelo_productivo",
    "y_real",
    "rmse",
    "mae",
    "mape",
    "smape",
    "mase",
]


def load_inputs(in_real: Path, forecast_base: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not in_real.exists():
        raise FileNotFoundError(f"No se encontró histórico: {in_real}")

    logger.info("Leyendo histórico: {}", in_real)
    real = pd.read_csv(in_real)

    # Buscar todos los archivos de forecast disponibles
    forecast_files = list(forecast_base.rglob("all_forecast_*.csv"))
    if not forecast_files:
        raise FileNotFoundError(f"No se encontraron archivos de forecast en: {forecast_base}")

    all_fcst_df: pd.DataFrame = pd.DataFrame()
    join_cols = ["ds", "meta_padecimiento", "meta_entidad", "meta_modo"]

    for fcst_path in sorted(forecast_files):
        # Extraer nombre del modelo del nombre del archivo: all_forecast_{modelo}.csv
        model_name = fcst_path.stem.replace("all_forecast_", "")
        logger.info("Leyendo forecast ({}): {}", model_name, fcst_path)
        df = pd.read_csv(fcst_path)

        # Eliminar columnas internas yhat_* del modelo (ej. yhat_prophet, yhat_tasa
        # dentro del CSV de ensemble/prophet) para evitar duplicados al renombrar.
        internal_yhat = [
            c
            for c in df.columns
            if c.startswith("yhat_") and c not in ("yhat_lower", "yhat_upper")
        ]
        if internal_yhat:
            df = df.drop(columns=internal_yhat)

        # Renombrar yhat para evitar colisiones
        df = df.rename(columns={"yhat": f"yhat_{model_name}"})

        if all_fcst_df.empty:
            all_fcst_df = df
        else:
            cols_to_keep = join_cols + [f"yhat_{model_name}"]
            df_to_merge = df[cols_to_keep]
            all_fcst_df = all_fcst_df.merge(df_to_merge, on=join_cols, how="outer")

    return real, all_fcst_df


def agregar_agregados_geograficos(real: pd.DataFrame) -> pd.DataFrame:
    """Agrega Nacional y Region Socio-Urbana sumando incrementos."""
    sum_cols = [
        c
        for c in ["incrementos_total", "incrementos_hombres", "incrementos_mujeres"]
        if c in real.columns
    ]
    nacional = (
        real.groupby(["ds", "padecimiento"], as_index=False)[sum_cols]
        .sum()
        .assign(entidad="Nacional", **{"Region Socio-Urbana": "Nacional"})
    )
    regional = (
        real.groupby(["ds", "padecimiento", "Region Socio-Urbana"], as_index=False)[sum_cols]
        .sum()
        .assign(entidad=lambda x: x["Region Socio-Urbana"])
        if "Region Socio-Urbana" in real.columns
        else pd.DataFrame()
    )
    return pd.concat(
        [
            real,
            nacional.reindex(columns=real.columns, fill_value=pd.NA),
            regional.reindex(columns=real.columns, fill_value=pd.NA),
        ],
        ignore_index=True,
    )


def prepare_inputs(real: pd.DataFrame, fcst: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Parse fechas + limpia inválidas
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
        }
    )
    if "Region Socio-Urbana" in real.columns:
        real["Region Socio-Urbana"] = (
            "Region " + real["Region Socio-Urbana"].astype(str).str.strip()
        )
    fcst = fcst.dropna(subset=["ds"]).copy()
    fcst["padecimiento"] = fcst["meta_padecimiento"]
    fcst["entidad"] = fcst["meta_entidad"]

    # Fix crítico general: Si hay fechas duplicadas en la serie de tiempo de una entidad/padecimiento
    # (ej. porque el calendario ISO choca semanas 1 y 53 de años contiguos en el mismo lunes),
    # resolvemos el empate prefiriendo la semana 1.
    if "Semana" in real.columns:
        real["_wk_pref"] = (real["Semana"] == 1).astype(int)
        real = (
            real.sort_values(
                ["padecimiento", "entidad", "ds", "_wk_pref"],
                ascending=[True, True, True, False],
            )
            .drop_duplicates(["padecimiento", "entidad", "ds"], keep="first")
            .drop(columns=["_wk_pref"])
        )

    return real.reset_index(drop=True), fcst.reset_index(drop=True)


def expand_real_by_modo(real: pd.DataFrame) -> pd.DataFrame:
    """
    Expande a 3 modos
    solo el incremento correspondiente queda poblado,
    los demás se dejan como NaN para evitar triple conteo.
    """
    r = real.copy()

    g = r.assign(meta_modo="general", y_real=r["incrementos_total"])
    h = r.assign(meta_modo="hombres", y_real=r["incrementos_hombres"])
    m = r.assign(meta_modo="mujeres", y_real=r["incrementos_mujeres"])

    g = g.assign(incrementos_hombres=pd.NA, incrementos_mujeres=pd.NA)
    h = h.assign(incrementos_total=pd.NA, incrementos_mujeres=pd.NA)
    m = m.assign(incrementos_total=pd.NA, incrementos_hombres=pd.NA)

    return pd.concat([g, h, m], ignore_index=True)


def keep_only_columns(df: pd.DataFrame, keep_cols: list[str]) -> pd.DataFrame:
    present = [c for c in keep_cols if c in df.columns]
    missing = [c for c in keep_cols if c not in df.columns]
    extra = [c for c in df.columns if c not in keep_cols]
    if missing:
        logger.warning("Columnas TWB ausentes (se omiten): {}", missing)
    if extra:
        logger.info("Se eliminarán columnas no usadas por TWB: {}", len(extra))
    return df.loc[:, present]


def _seleccionar_modelo_productivo(
    df: pd.DataFrame,
    grp: list[str],
    yhat_model_cols: list[str],
) -> pd.DataFrame:
    """Asigna yhat y modelo_productivo por mejor SMAPE por grupo.

    Para cada (padecimiento, entidad, meta_modo), calcula SMAPE de cada modelo
    donde hay dato real, y elige el modelo con menor SMAPE. Si no hay datos
    reales para comparar, usa fallback: ensemble > stacking > prophet > deepar.
    """
    if not yhat_model_cols:
        df["yhat"] = np.nan
        df["modelo_productivo"] = ""
        return df

    # Calcular SMAPE por grupo y modelo (solo filas con y_real)
    fallback_order = ["yhat_ensemble", "yhat_stacking", "yhat_prophet", "yhat_deepar"]
    fallback_col = next((c for c in fallback_order if c in yhat_model_cols), yhat_model_cols[0])

    mask_real = (
        df["y_real"].notna() if "y_real" in df.columns else pd.Series(False, index=df.index)
    )
    rows_with_real = df[mask_real]

    if rows_with_real.empty:
        # Sin datos reales: fallback fijo
        df["yhat"] = df[fallback_col]
        df["modelo_productivo"] = fallback_col.replace("yhat_", "")
        for col in yhat_model_cols:
            if col != fallback_col:
                df["yhat"] = df["yhat"].fillna(df[col])
        logger.warning("Sin datos reales para SMAPE; fallback a {}", fallback_col)
        return df

    # SMAPE por grupo y modelo
    smape_records = []
    for col in yhat_model_cols:
        modelo = col.replace("yhat_", "")
        tmp = rows_with_real[grp + ["y_real", col]].copy()
        tmp = tmp.dropna(subset=["y_real", col])
        tmp["y_real"] = pd.to_numeric(tmp["y_real"], errors="coerce")
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
        tmp = tmp.dropna(subset=["y_real", col])
        if tmp.empty:
            continue
        denom = (tmp["y_real"].abs() + tmp[col].abs()).replace(0, np.nan)
        tmp["_smape"] = (2 * (tmp["y_real"] - tmp[col]).abs() / denom) * 100
        grp_smape = tmp.groupby(grp, as_index=False)["_smape"].mean()
        grp_smape = grp_smape.rename(columns={"_smape": "smape"})
        grp_smape["modelo"] = modelo
        grp_smape["yhat_col"] = col
        smape_records.append(grp_smape)

    if not smape_records:
        df["yhat"] = df[fallback_col]
        df["modelo_productivo"] = fallback_col.replace("yhat_", "")
        logger.warning("No se pudo calcular SMAPE; fallback a {}", fallback_col)
        return df

    all_smape = pd.concat(smape_records, ignore_index=True)
    # Mejor modelo = menor SMAPE por grupo
    best = all_smape.loc[all_smape.groupby(grp)["smape"].idxmin()]
    best_map = best[grp + ["modelo", "yhat_col"]].copy()

    df = df.merge(best_map, on=grp, how="left")
    df = df.rename(columns={"modelo": "modelo_productivo"})

    # Asignar yhat fila a fila segun el modelo ganador
    df["yhat"] = np.nan
    for col in yhat_model_cols:
        modelo = col.replace("yhat_", "")
        mask = df["yhat_col"] == col
        df.loc[mask, "yhat"] = df.loc[mask, col]

    # Fallback para filas sin modelo asignado (ej. entidades sin datos reales)
    no_model = df["yhat"].isna() & df["modelo_productivo"].isna()
    if no_model.any():
        df.loc[no_model, "modelo_productivo"] = fallback_col.replace("yhat_", "")
        df.loc[no_model, "yhat"] = df.loc[no_model, fallback_col]
        for col in yhat_model_cols:
            if col != fallback_col:
                still_na = df["yhat"].isna() & no_model
                df.loc[still_na, "yhat"] = df.loc[still_na, col]

    df = df.drop(columns=["yhat_col"], errors="ignore")

    # Log resumen
    winners = best_map["modelo"].value_counts()
    logger.info("Modelo productivo por SMAPE -> {}", dict(winners))
    return df


def _calcular_metricas_por_modelo(
    df: pd.DataFrame,
    grp: list[str],
    yhat_model_cols: list[str],
) -> pd.DataFrame:
    """Calcula RMSE, MAE, MAPE, SMAPE, MASE por grupo para cada modelo.

    Agrega columnas {metrica}_{modelo} y {metrica} (del modelo productivo).
    """
    if "y_real" not in df.columns or not yhat_model_cols:
        return df

    mask_real = df["y_real"].notna()
    rows = df[mask_real].copy()
    rows["y_real"] = pd.to_numeric(rows["y_real"], errors="coerce")
    rows = rows.dropna(subset=["y_real"])

    if rows.empty:
        return df

    all_model_metrics: list[pd.DataFrame] = []

    for col in yhat_model_cols:
        modelo = col.replace("yhat_", "")
        tmp = rows[grp + ["y_real", col]].copy()
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
        tmp = tmp.dropna(subset=[col])
        if tmp.empty:
            continue

        y = tmp["y_real"]
        yh = tmp[col]
        err = (y - yh).abs()
        denom_smape = (y.abs() + yh.abs()).replace(0, np.nan)
        denom_mape = y.abs().replace(0, np.nan)

        tmp["_rmse_sq"] = (y - yh) ** 2
        tmp["_mae"] = err
        tmp["_mape"] = (err / denom_mape) * 100
        tmp["_smape"] = (2 * err / denom_smape) * 100
        # MASE: |error| / mean(|y - y_{t-52}|) — naive estacional (lag-52)
        tmp["_naive_diff"] = tmp.groupby(grp)["y_real"].diff(52).abs()

        grp_metrics = tmp.groupby(grp, as_index=False).agg(
            _rmse_sq=("_rmse_sq", "mean"),
            _mae=("_mae", "mean"),
            _mape=("_mape", "mean"),
            _smape=("_smape", "mean"),
            _naive_mean=("_naive_diff", "mean"),
            _mae_raw=("_mae", "mean"),
        )
        grp_metrics[f"rmse_{modelo}"] = grp_metrics["_rmse_sq"] ** 0.5
        grp_metrics[f"mae_{modelo}"] = grp_metrics["_mae"]
        grp_metrics[f"mape_{modelo}"] = grp_metrics["_mape"]
        grp_metrics[f"smape_{modelo}"] = grp_metrics["_smape"]
        naive = grp_metrics["_naive_mean"].replace(0, np.nan)
        grp_metrics[f"mase_{modelo}"] = grp_metrics["_mae_raw"] / naive

        keep = grp + [f"{m}_{modelo}" for m in _METRICS]
        all_model_metrics.append(grp_metrics[keep])

    if not all_model_metrics:
        return df

    # Merge todas las metricas por modelo
    merged = all_model_metrics[0]
    for other in all_model_metrics[1:]:
        merged = merged.merge(other, on=grp, how="outer")

    df = df.merge(merged, on=grp, how="left")

    # Columnas del modelo productivo (sin sufijo)
    for m in _METRICS:
        df[m] = np.nan
        for mod in _MODELS:
            col = f"{m}_{mod}"
            if col in df.columns:
                mask = df["modelo_productivo"] == mod
                df.loc[mask, m] = df.loc[mask, col]

    n_metric_cols = sum(1 for c in df.columns if any(c.startswith(f"{m}_") for m in _METRICS))
    logger.info("Metricas calculadas: {} columnas por modelo + 5 del productivo", n_metric_cols)
    return df


def build_and_save_tableau(real_long: pd.DataFrame, fcst: pd.DataFrame, out_file: Path) -> None:
    join_cols = ["ds", "padecimiento", "entidad", "meta_modo"]
    logger.info("Join por: {}", join_cols)

    if fcst.duplicated(join_cols).any():
        raise ValueError("Duplicados en forecast para llaves de join.")
    if real_long.duplicated(join_cols).any():
        raise ValueError("Duplicados en histórico expandido para llaves de join.")

    out = real_long.merge(fcst, how="outer", on=join_cols, validate="m:1")

    grp = ["padecimiento", "entidad", "meta_modo"]

    # Columna yhat + modelo_productivo: seleccion por mejor SMAPE por grupo
    yhat_model_cols = [
        c for c in out.columns if c.startswith("yhat_") and c not in ("yhat_lower", "yhat_upper")
    ]
    out = _seleccionar_modelo_productivo(out, grp, yhat_model_cols)

    # Metricas por modelo: calculadas desde y_real vs yhat_{modelo}
    out = _calcular_metricas_por_modelo(out, grp, yhat_model_cols)

    # Renombres mínimos
    rename_map = {
        "Total": "Poblacion Total",
        "Hombres": "Poblacion Hombres",
        "Mujeres": "Poblacion Mujeres",
        "region_salud_mental": "Region Socio-Urbana",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})

    # Validación llaves críticas sin NaN
    key_cols = ["ds", "padecimiento", "entidad", "meta_modo"]
    bad_keys = out[key_cols].isna().sum()
    bad_keys = bad_keys[bad_keys > 0]
    if not bad_keys.empty:
        detail = ", ".join(f"{c}: {n}" for c, n in bad_keys.items())
        raise ValueError(f"Dataset final con NaN en llaves críticas. Detalle -> {detail}")

    # Validar completitud: alertar si algun modelo tiene >50% filas sin prediccion
    for modelo in ("prophet", "deepar", "ensemble", "stacking"):
        col = f"yhat_{modelo}"
        if col in out.columns:
            n_missing = int(out[col].isna().sum())
            n_total = len(out)
            pct = 100 * n_missing / n_total if n_total > 0 else 0
            if pct > 50:
                logger.warning("Modelo {} tiene {:.0f}% filas sin prediccion", modelo, pct)

    out = out.sort_values(["padecimiento", "entidad", "ds", "meta_modo"]).reset_index(drop=True)

    rows_full, cols_full = out.shape
    cells_full = rows_full * cols_full
    logger.info(
        "Dataset completo -> filas: {} | columnas: {} | celdas totales: {}",
        rows_full,
        cols_full,
        cells_full,
    )
    out = keep_only_columns(out, KEEP_COLS_TWB)
    rows_opt, cols_opt = out.shape
    cells_opt = rows_opt * cols_opt
    logger.info(
        "Dataset optimizado -> filas: {} | columnas: {} | celdas totales: {}",
        rows_opt,
        cols_opt,
        cells_opt,
    )
    logger.info("Mejora vs dataset completo: {:.2f}%", 100 * (1 - (cells_opt / cells_full)))

    # Redondear predicciones a enteros (no existen fracciones de caso)
    yhat_cols = [c for c in out.columns if c.startswith("yhat")]
    for col in yhat_cols:
        out[col] = out[col].round(0).astype("Int64")

    out.to_csv(out_file, index=False)
    logger.success(
        "tableau.csv generado: {} | filas: {} | cols: {}", out_file, len(out), out.shape[1]
    )


def main() -> None:
    in_real = Path(conf["data"]["data_inegi"])
    forecast_base = Path(conf["paths"]["reports"]) / "forecasts"
    out_file = Path(conf["data"]["tableau"])

    directory_manager.asegurar_ruta(out_file.parent)
    real, fcst = load_inputs(in_real, forecast_base)
    real, fcst = prepare_inputs(real, fcst)
    real = agregar_agregados_geograficos(real)
    real_long = expand_real_by_modo(real)
    build_and_save_tableau(real_long, fcst, out_file)


if __name__ == "__main__":
    main()
