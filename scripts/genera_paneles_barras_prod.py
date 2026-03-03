"""Genera paneles individuales del modelo ganador (PROD) por semana.

Cada PNG muestra un solo panel alargado (26x5.5) con las 104 barras
(52 hist + 52 futuro) del modelo de produccion seleccionado por SMAPE.
Salida: reports/forecasts/comparacion_modelos/PROD_MODELS/{Pad}/individual_barras_semana/
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from epiforecast.constants import VIZ_DPI_SCREEN
from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger
from epiforecast.visualization.comparison_bars import build_single_prod_bars
from epiforecast.visualization.forecast_plots import _normalizar_nombre


def main() -> None:
    forecast_base = Path(conf["paths"]["reports"]) / "forecasts"
    output_dir = forecast_base / "comparacion_modelos" / "PROD_MODELS"

    # Cargar los 4 modelos
    model_keys = ["prophet", "deepar", "ensemble", "stacking"]
    model_dfs: dict[str, pd.DataFrame] = {}
    for mk in model_keys:
        csv_path = forecast_base / mk / f"all_forecast_{mk}.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, low_memory=False)
            df["ds"] = pd.to_datetime(df["ds"])
            model_dfs[mk] = df
            logger.info("Cargado {}: {:,} filas", mk, len(df))

    if not model_dfs:
        logger.error("No hay CSVs de forecast.")
        return

    ref_df = model_dfs[next(iter(model_dfs))]
    grupos = ref_df.groupby(["meta_padecimiento", "meta_entidad", "meta_modo"])

    count = 0
    skipped = 0
    for (pad_, ent_, modo_), _ in grupos:
        pad = str(pad_)
        ent = "" if ent_ is None or (isinstance(ent_, float) and np.isnan(ent_)) else str(ent_)
        modo = str(modo_)

        # Filtrar grupo por modelo
        groups: dict[str, pd.DataFrame] = {}
        for mk, mdf in model_dfs.items():
            mask = (
                (mdf["meta_padecimiento"] == pad)
                & (mdf["meta_entidad"].fillna("") == ent)
                & (mdf["meta_modo"] == modo)
            )
            grp = mdf[mask]
            if not grp.empty:
                groups[mk] = grp

        if not groups:
            continue

        # Serie real
        serie_real = _load_serie_real(pad, ent, modo)
        if serie_real is None:
            skipped += 1
            continue

        # Generar panel individual del modelo ganador
        fig = build_single_prod_bars(serie_real, groups, pad, ent, modo)
        if fig is None:
            skipped += 1
            plt.close("all")
            continue

        # Guardar
        safe_ent = _normalizar_nombre(ent if ent else "Nacional")
        pad_norm = _normalizar_nombre(pad)
        base_name = f"{pad}_{safe_ent}_{modo}.png"
        bar_dir = output_dir / pad_norm / "individual_barras_semana"
        directory_manager.asegurar_ruta(bar_dir)
        fig.savefig(bar_dir / base_name, dpi=VIZ_DPI_SCREEN, bbox_inches="tight")
        plt.close(fig)
        count += 1

        if count % 50 == 0:
            logger.info("Generados {} paneles PROD...", count)

    logger.success(
        "Total: {} paneles PROD generados ({} omitidos) en {}",
        count,
        skipped,
        output_dir,
    )


def _load_serie_real(pad: str, ent: str, modo: str) -> pd.DataFrame | None:
    pad_norm = _normalizar_nombre(pad)
    ent_norm = _normalizar_nombre(ent if ent and ent.lower() != "nacional" else "")

    for model_key, prefix in [
        ("prophet", "Prophet"),
        ("ensemble", "Ensemble"),
        ("stacking", "Stacking"),
        ("deepar", "Deepar"),
    ]:
        csv_name = f"{prefix}_{pad_norm}_{ent_norm + '_' if ent_norm else ''}{modo}.csv"
        csv_path = Path(conf["paths"]["models"]).parent / model_key / pad_norm / csv_name
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            df["ds"] = pd.to_datetime(df["ds"])
            return df
    return None


if __name__ == "__main__":
    main()
