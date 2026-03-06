"""HTML report generation: comparative analysis across all forecast models.

HTML template functions extracted to comparison_html.py for SRP compliance.
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from epiforecast.utils import paths as directory_manager
from epiforecast.utils.config import conf, logger
from epiforecast.visualization.comparison_html import (
    _MODELS,
    html_detalle_padecimiento,
    html_footer,
    html_head,
    html_resumen,
)
from epiforecast.visualization.forecast_plots import _normalizar_nombre

_TZ_CDMX = ZoneInfo("America/Mexico_City")

_METRICS = ["rmse", "mae", "smape", "mase"]
_METRICS_MERGE = ["rmse", "mae", "smape", "mase", "smape_train"]

_MERGE_KEYS = ["padecimiento", "sexo", "nivel", "Entidad"]


def generar_reporte_html(config: dict[str, Any] | None = None) -> Path | None:
    """Genera un reporte HTML comparativo entre todos los modelos disponibles."""
    _conf = config if config is not None else conf
    models_dir = Path("models")
    output_dir = Path(_conf["paths"]["reports"]) / "forecasts" / "comparacion_modelos"
    output_html = output_dir / "comparacion_modelos.html"
    directory_manager.asegurar_ruta(output_dir)

    # Cargar CSVs completos de cada modelo
    available: dict[str, pd.DataFrame] = {}
    for model_key in _MODELS:
        frames: list[pd.DataFrame] = []
        for csv in sorted((models_dir / model_key).rglob("*_completo.csv")):
            frames.append(pd.read_csv(csv))
        if frames:
            df = pd.concat(frames, ignore_index=True)
            if "Entidad" not in df.columns:
                df["Entidad"] = ""
            df["Entidad"] = df["Entidad"].fillna("")
            available[model_key] = df
            logger.info("  Cargado {}: {} filas", model_key, len(df))

    if not available:
        logger.warning("No se encontraron CSVs completos para el reporte HTML.")
        return None

    logger.info("Modelos encontrados: {}", list(available.keys()))

    # Merge N-way
    merged = _merge_all_models(available)

    # Determinar modelo productivo por SMAPE
    merged = _assign_modelo_productivo(merged, list(available.keys()))

    ahora = datetime.now(_TZ_CDMX).strftime("%Y-%m-%d %H:%M")
    padecimientos = sorted(merged["padecimiento"].dropna().unique())
    model_keys = list(available.keys())

    # KPI stats para el hero
    smape_cols = [f"smape_{mk}" for mk in model_keys if f"smape_{mk}" in merged.columns]
    best_smape, best_model = 0.0, ""
    if smape_cols:
        means = {c.replace("smape_", ""): merged[c].mean(skipna=True) for c in smape_cols}
        best_model = min(means, key=lambda k: means[k])
        best_smape = means[best_model]

    html_parts: list[str] = [
        html_head(
            ahora,
            model_keys,
            n_series=len(merged),
            best_smape=best_smape,
            best_model=best_model,
            n_padecimientos=len(padecimientos),
        )
    ]
    html_parts.append(html_resumen(merged, padecimientos, model_keys))

    for pad in padecimientos:
        pad_data = merged[merged["padecimiento"] == pad].copy()
        pad_norm = _normalizar_nombre(pad)
        html_parts.append(html_detalle_padecimiento(pad, pad_norm, pad_data, model_keys))

    html_parts.append(html_footer(ahora))

    output_html.write_text("\n".join(html_parts), encoding="utf-8")
    logger.success("Reporte HTML generado: {}", output_html)
    return output_html


# -- Data helpers -------------------------------------------------------------


def _merge_all_models(available: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge N-way de metricas de todos los modelos."""
    base_cols = _MERGE_KEYS + [
        c
        for c in ("confianza", "promedio_semanal")
        if any(c in df.columns for df in available.values())
    ]

    merged: pd.DataFrame | None = None
    for model_key, df in available.items():
        keep = [c for c in base_cols if c in df.columns]
        metric_cols = [c for c in _METRICS_MERGE if c in df.columns]
        subset = df[keep + metric_cols].copy()
        subset = subset.rename(columns={m: f"{m}_{model_key}" for m in metric_cols})
        if merged is None:
            merged = subset
        else:
            on_cols = [c for c in _MERGE_KEYS if c in merged.columns and c in subset.columns]
            new_cols = on_cols + [c for c in subset.columns if c not in merged.columns]
            merged = merged.merge(subset[new_cols], on=on_cols, how="outer")

    return merged if merged is not None else pd.DataFrame()


def _assign_modelo_productivo(merged: pd.DataFrame, model_keys: list[str]) -> pd.DataFrame:
    """Agrega columna modelo_productivo basada en menor SMAPE."""
    smape_cols = [f"smape_{mk}" for mk in model_keys if f"smape_{mk}" in merged.columns]
    if not smape_cols:
        merged["modelo_productivo"] = ""
        return merged

    smape_matrix = merged[smape_cols].copy()
    col_to_model = {col: col.replace("smape_", "") for col in smape_cols}
    best_col = smape_matrix.idxmin(axis=1, skipna=True)
    merged["modelo_productivo"] = best_col.map(col_to_model).fillna("")
    return merged
