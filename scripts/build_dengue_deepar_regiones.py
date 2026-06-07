#!/usr/bin/env python
"""build_dengue_deepar_regiones.py — Entrena DeepAR nativo por REGIÓN de Dengue y cachea su
pronóstico para la galería.

El backtest leave-one-epidemic-out (`scripts/research/dengue_backtest_regional.py`) mostró que el
regional NATIVO gana en epidemias y que **DeepAR es el mejor** (MAE 460 vs 3.7k-10k de la
agregación; ratio de pico 0.43 vs 34-41). La agregación bottom-up COMPONE los sobre-tiros
estatales y explota. Así que las 4 regiones de Dengue pasan a usar DeepAR nativo.

DeepAR local se entrena **una región a la vez** (n_jobs=1, ~15-20 min c/u; el deadlock previo era
por concurrencia). Este script entrena cada región sobre su serie agregada completa, predice
(ajuste in-sample reciente + futuro, con banda nativa de cuantiles) y escribe el pronóstico a
``reports/ProdDetails/dengue_deepar_regiones.csv``. La galería (`build_dengue_gallery`) lee ese
cache: entrenar (lento) queda desacoplado de generar la galería (rápido).

Las fechas de DeepAR (resamplea a W-MON de FIN de periodo) se reanclan al grid ISO (Lunes de
INICIO de semana) que usa la serie real, para que casen en la galería.

Uso:
    python -m scripts.build_dengue_deepar_regiones      # entrena las 4 regiones (~80 min)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import warnings

import pandas as pd

warnings.filterwarnings("ignore")
import logging  # noqa: E402

logging.getLogger("cmdstanpy").disabled = True

import scripts.build_dengue_gallery as G  # noqa: E402, N812

from epiforecast.models import create_model  # noqa: E402
from epiforecast.utils.config import conf, logger  # noqa: E402

DENGUE_DATA = Path("data/processed/data_inegi_Dengue.csv")
OUT = Path(conf["paths"]["reports"]) / "ProdDetails" / "dengue_deepar_regiones.csv"
HORIZON = 52


def _snap_iso(fc: pd.DataFrame) -> pd.DataFrame:
    """Reancla las fechas al Lunes ISO de inicio de semana (DeepAR resamplea a W-MON de fin)."""
    iso = pd.to_datetime(fc["ds"]).dt.isocalendar()
    fc = fc.copy()
    fc["ds"] = [
        pd.Timestamp(date.fromisocalendar(int(y), min(int(w), 52), 1))
        for y, w in zip(iso["year"], iso["week"], strict=False)
    ]
    cols = [c for c in ["yhat", "yhat_lower", "yhat_upper"] if c in fc.columns]
    return fc.groupby("ds", as_index=False)[cols].mean()


def main() -> int:
    dd = pd.read_csv(DENGUE_DATA)
    dd["Fecha"] = pd.to_datetime(dd["Fecha"])
    rows = []
    for _folder, data_n, region_short in G.DENGUE_REGIONES:
        sub = dd[dd["region_salud_mental"] == region_short].copy()
        if sub.empty:
            logger.warning("Sin datos para región {}", data_n)
            continue
        logger.info("Entrenando DeepAR nativo — {} ({} filas)...", data_n, len(sub))
        m = create_model(
            "deepar", df=sub, sexo="incrementos_total", entidad=region_short, padecimiento="Dengue"
        )
        m.run()  # CV omitida (entidad != None); fit final sobre la serie completa
        fc = m.predict(HORIZON)  # ajuste in-sample reciente + futuro, con banda nativa
        fc["ds"] = pd.to_datetime(fc["ds"])
        fc = _snap_iso(fc)
        fc.insert(0, "region", data_n)
        rows.append(fc)
        logger.success(
            "{}: {} sem pronosticadas ({} → {})",
            data_n,
            len(fc),
            fc["ds"].min().date(),
            fc["ds"].max().date(),
        )

    if not rows:
        logger.error("No se generó ningún pronóstico regional.")
        return 1
    out = pd.concat(rows, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    logger.success("DeepAR regional Dengue: {} filas → {}", len(out), OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
