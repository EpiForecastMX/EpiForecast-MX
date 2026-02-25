# scripts/build_tableau.py
from __future__ import annotations

from pathlib import Path

import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger


def load_inputs(in_real: Path, in_fcst: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not in_real.exists():
        raise FileNotFoundError(f"No se encontró histórico: {in_real}")
    if not in_fcst.exists():
        raise FileNotFoundError(f"No se encontró forecast: {in_fcst}")

    logger.info("Leyendo histórico: {}", in_real)
    real = pd.read_csv(in_real)

    logger.info("Leyendo forecast: {}", in_fcst)
    fcst = pd.read_csv(in_fcst)

    return real, fcst


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

    # Fix crítico: 2014-12-29 y 2025-12-29 (Semana 53 vs 1)
    if "Semana" in real.columns:
        special_ds = pd.to_datetime(["2014-12-29", "2025-12-29"])
        is_special = real["ds"].isin(special_ds)

        if is_special.any():
            a = real.loc[~is_special].copy()
            b = real.loc[is_special].copy()

            b["_wk_pref"] = (b["Semana"] == 53).astype(int)
            b = (
                b.sort_values(
                    ["padecimiento", "entidad", "ds", "_wk_pref"],
                    ascending=[True, True, True, False],
                )
                .drop_duplicates(["padecimiento", "entidad", "ds"], keep="first")
                .drop(columns=["_wk_pref"])
            )
            real = pd.concat([a, b], ignore_index=True)

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
    tmp = out[grp + ["y_real", "yhat"]].copy()
    tmp = tmp[tmp["y_real"].notna() & tmp["yhat"].notna()]
    tmp["y_real"] = pd.to_numeric(tmp["y_real"], errors="coerce")
    tmp["yhat"] = pd.to_numeric(tmp["yhat"], errors="coerce")
    tmp = tmp.dropna(subset=["y_real", "yhat"])

    rmse_df = (
        tmp.assign(se=(tmp["y_real"] - tmp["yhat"]) ** 2)
        .groupby(grp, as_index=False)["se"]
        .mean()
        .assign(rmse_modelo=lambda d: d["se"] ** 0.5)
        .drop(columns=["se"])
    )
    out = out.merge(rmse_df, how="left", on=grp)

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
    out.to_csv(out_file, index=False)
    logger.success(
        "tableau.csv generado: {} | filas: {} | cols: {}", out_file, len(out), out.shape[1]
    )


def main() -> None:
    in_real = Path(conf["data"]["data_inegi"])
    in_fcst = Path(conf["data"]["forecast"])
    out_file = Path(conf["data"]["tableau"])

    directory_manager.asegurar_ruta(out_file.parent)
    real, fcst = load_inputs(in_real, in_fcst)
    real, fcst = prepare_inputs(real, fcst)
    real_long = expand_real_by_modo(real)
    build_and_save_tableau(real_long, fcst, out_file)


if __name__ == "__main__":
    main()
