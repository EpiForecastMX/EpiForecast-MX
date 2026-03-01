# scripts/build_tableau.py
from __future__ import annotations

from pathlib import Path

import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger

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
    "yhat_prophet",
    "yhat_deepar",
    "yhat_ensemble",
    "yhat_stacking",
    "yhat_lower",
    "yhat_upper",
    "trend",
    "yearly_custom",
    "mase_usado",
    "mae_usado",
    "mape_usado",
    "rmse_usado",
    "archivo_modelo_original",
    "archivo_modelo_usado",
    "confianza_original",
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
        columns={"Fecha": "ds", "Padecimiento": "padecimiento", "Entidad": "entidad"}
    )
    fcst = fcst.dropna(subset=["ds"]).copy()
    fcst["padecimiento"] = fcst["meta_padecimiento"]
    fcst["entidad"] = fcst["meta_entidad"]

    # Fix crítico general: Si hay fechas duplicadas en la serie de tiempo de una entidad/padecimiento
    # (ej. porque el calendario ISO choca semanas 1 y 53 de años contiguos en el mismo lunes),
    # resolvemos el empate prefiriendo la semana 53, que suele contener el acumulado final del año.
    if "Semana" in real.columns:
        real["_wk_pref"] = (real["Semana"] == 53).astype(int)
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


def build_and_save_tableau(real_long: pd.DataFrame, fcst: pd.DataFrame, out_file: Path) -> None:
    join_cols = ["ds", "padecimiento", "entidad", "meta_modo"]
    logger.info("Join por: {}", join_cols)

    if fcst.duplicated(join_cols).any():
        raise ValueError("Duplicados en forecast para llaves de join.")
    if real_long.duplicated(join_cols).any():
        raise ValueError("Duplicados en histórico expandido para llaves de join.")

    out = real_long.merge(fcst, how="outer", on=join_cols, validate="m:1")

    # RMSE por modelo (solo donde hay dato real y forecast)
    grp = ["padecimiento", "entidad", "meta_modo"]
    yhat_cols = [
        c
        for c in out.columns
        if c.startswith("yhat_") and c not in ("yhat_lower", "yhat_upper", "yhat_ensemble")
    ]
    yhat_col = yhat_cols[0] if yhat_cols else None

    if yhat_col and "y_real" in out.columns:
        tmp = out[grp + ["y_real", yhat_col]].copy()
        tmp = tmp[tmp["y_real"].notna() & tmp[yhat_col].notna()]
        tmp["y_real"] = pd.to_numeric(tmp["y_real"], errors="coerce")
        tmp[yhat_col] = pd.to_numeric(tmp[yhat_col], errors="coerce")
        tmp = tmp.dropna(subset=["y_real", yhat_col])

        rmse_df = (
            tmp.assign(se=(tmp["y_real"] - tmp[yhat_col]) ** 2)
            .groupby(grp, as_index=False)["se"]
            .mean()
            .assign(rmse_modelo=lambda d: d["se"] ** 0.5)
            .drop(columns=["se"])
        )
        out = out.merge(rmse_df, how="left", on=grp)

    # Columna yhat unificada: prioridad ensemble > stacking > prophet > deepar
    yhat_priority = ["yhat_ensemble", "yhat_stacking", "yhat_prophet", "yhat_deepar"]
    available = [c for c in yhat_priority if c in out.columns]
    if available:
        out["yhat"] = out[available[0]]
        for col in available[1:]:
            out["yhat"] = out["yhat"].fillna(out[col])
        logger.info("Columna yhat unificada creada (prioridad: {})", " > ".join(available))

    # Renombres mínimos
    rename_map = {
        "Total": "Poblacion Total",
        "Hombres": "Poblacion Hombres",
        "Mujeres": "Poblacion Mujeres",
        "region_salud_mental": "Region Socio-Urbana",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})

    # solo numéricas generales, NO incrementos
    block_fill = {"incrementos_total", "incrementos_hombres", "incrementos_mujeres"}
    num_cols = [c for c in out.select_dtypes(include=["number"]).columns if c not in block_fill]
    if num_cols:
        out[num_cols] = out[num_cols].fillna(0)

    # Validación llaves críticas sin NaN
    key_cols = ["ds", "padecimiento", "entidad", "meta_modo"]
    bad_keys = out[key_cols].isna().sum()
    bad_keys = bad_keys[bad_keys > 0]
    if not bad_keys.empty:
        detail = ", ".join(f"{c}: {n}" for c, n in bad_keys.items())
        raise ValueError(f"Dataset final con NaN en llaves críticas. Detalle -> {detail}")

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
    real_long = expand_real_by_modo(real)
    build_and_save_tableau(real_long, fcst, out_file)


if __name__ == "__main__":
    main()
