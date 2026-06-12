# src/epiforecast/visualization/avance5_data.py
"""Carga de artefactos, N-way merge y win-rate para el reporte Avance 5."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from epiforecast.constants import RATE_PER
from epiforecast.utils.config import logger

_MODEL_KEYS = ["prophet", "deepar", "ensemble", "stacking"]
_MODEL_LABELS = {
    "prophet": "Prophet",
    "deepar": "DeepAR",
    "ensemble": "Ensemble",
    "stacking": "Stacking",
}

_MERGE_KEYS = ["padecimiento", "sexo", "nivel", "Entidad"]
_METRICS = ["rmse", "mae", "smape", "mase"]
_METRICS_MERGE = ["rmse", "mae", "smape", "mase", "smape_train", "rmse_train", "tiempo_total_seg"]

_PADECIMIENTOS = ["Depresión", "Parkinson", "Alzheimer"]

# Nombres de archivo sin acentos
_NOMBRE_ARCHIVO: dict[str, str] = {
    "Depresión": "depresion",
    "Parkinson": "parkinson",
    "Alzheimer": "alzheimer",
}


def _pad_filename(pad: str) -> str:
    """Nombre de archivo sin acentos para un padecimiento."""
    return _NOMBRE_ARCHIVO.get(pad, pad.lower())


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def cargar_completos(models_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Lee ``models/{model}/**/*_completo.csv`` de cada modelo disponible.

    Si DeepAR reporta metricas en escala de tasa (por 100k habitantes), las
    rescala automaticamente a casos absolutos usando la poblacion de
    ``data/processed/data_inegi_General.csv``.
    """
    base = models_dir or Path("models")
    result: dict[str, pd.DataFrame] = {}
    for key in _MODEL_KEYS:
        frames: list[pd.DataFrame] = []
        model_dir = base / key
        if not model_dir.exists():
            continue
        for csv in sorted(model_dir.rglob("*_completo.csv")):
            frames.append(pd.read_csv(csv))
        if frames:
            df = pd.concat(frames, ignore_index=True)
            if "Entidad" not in df.columns:
                df["Entidad"] = ""
            df["Entidad"] = df["Entidad"].fillna("")
            result[key] = df
            logger.info("  Cargado {}: {} filas", key, len(df))

    # Rescalar DeepAR si sus metricas estan en escala de tasa
    if "deepar" in result and len(result) >= 2:
        result["deepar"] = _rescalar_deepar(result)

    return result


_METRICS_SCALE = ["rmse", "mae", "rmse_train"]


def _rescalar_deepar(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Rescala RMSE/MAE de DeepAR de tasa-por-100k a casos absolutos.

    DeepAR (GluonTS con ``scaling=True``) computa metricas de CV en la escala
    normalizada internamente (tasa por 100k habitantes).  Los demas modelos
    las computan en casos absolutos.  Multiplicamos por ``Poblacion / RATE_PER``
    para cada serie, usando la poblacion de ``data_inegi_General.csv``.
    """
    deepar_df = data["deepar"].copy()

    # Detectar si realmente necesita rescale: comparar mediana con otro modelo
    ref_key = next((k for k in ("prophet", "ensemble", "stacking") if k in data), None)
    if ref_key is None:
        return deepar_df
    ref_median = data[ref_key]["rmse"].median(skipna=True)
    deepar_median = deepar_df["rmse"].median(skipna=True)
    if deepar_median == 0 or ref_median / deepar_median < 5:
        logger.info("  DeepAR metricas ya estan en escala comparable, sin rescale.")
        return deepar_df

    # Cargar poblacion por (padecimiento, Entidad)
    real_path = Path("data") / "processed" / "data_inegi_General.csv"
    if not real_path.exists():
        logger.warning("No se encontro {} para rescalar DeepAR.", real_path)
        return deepar_df

    real = pd.read_csv(real_path)
    pop_map = real.groupby(["Padecimiento", "Entidad"])["Total"].last().reset_index()
    pop_map = pop_map.rename(columns={"Padecimiento": "padecimiento"})

    # Normalizar nombres de entidad (quitar acentos) para el join
    deepar_df["_ent_norm"] = deepar_df["Entidad"].map(_normalizar_entidad)
    pop_map["_ent_norm"] = pop_map["Entidad"].map(_normalizar_entidad)

    # Poblacion nacional por padecimiento (suma de 32 estados)
    nacional_pop = pop_map.groupby("padecimiento")["Total"].sum().to_dict()

    # Poblacion regional (suma de estados en la region) — extraer region del nombre
    region_pop = _build_region_pop(real)

    # Construir lookup de poblacion
    pop_lookup: dict[tuple[str, str], float] = {}
    for _, row in pop_map.iterrows():
        pop_lookup[(row["padecimiento"], row["_ent_norm"])] = float(row["Total"])

    # Asignar poblacion a cada fila de DeepAR
    totals: list[float] = []
    for _, row in deepar_df.iterrows():
        pad = row["padecimiento"]
        ent_norm = row["_ent_norm"]
        # 1. Match exacto por estado
        pop = pop_lookup.get((pad, ent_norm))
        if pop is not None:
            totals.append(pop)
            continue
        # 2. Nacional (general, hombres, mujeres)
        if ent_norm in ("general", "hombres", "mujeres"):
            totals.append(float(nacional_pop.get(pad, 0)))
            continue
        # 3. Regional
        if ent_norm.startswith("region "):
            region_name = ent_norm.replace("region ", "")
            totals.append(float(region_pop.get((pad, region_name), 0)))
            continue
        # 4. Sin match
        totals.append(0.0)

    deepar_df["_pop"] = totals

    n_matched = sum(1 for t in totals if t > 0)
    logger.info(
        "  DeepAR: {} / {} series con poblacion asignada.",
        n_matched,
        len(deepar_df),
    )

    # Aplicar factor: metrica_abs = metrica_tasa * (Total / RATE_PER)
    scale = deepar_df["_pop"] / RATE_PER
    scale = scale.replace(0, np.nan)
    for metric in _METRICS_SCALE:
        if metric in deepar_df.columns:
            deepar_df[metric] = deepar_df[metric] * scale

    deepar_df = deepar_df.drop(columns=["_ent_norm", "_pop"], errors="ignore")
    logger.info("  DeepAR metricas rescaladas a casos absolutos (x Poblacion/100k).")
    return deepar_df


def _normalizar_entidad(nombre: str) -> str:
    """Quita acentos, unifica separadores y pasa a minusculas para matching robusto."""
    import unicodedata

    if not isinstance(nombre, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", nombre)
    result = "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
    # Unificar region_X → region X (Prophet usa guion bajo, DeepAR usa espacio)
    return result.replace("region_", "region ")


def _build_region_pop(real: pd.DataFrame) -> dict[tuple[str, str], float]:
    """Suma de poblacion por (padecimiento, region) para series regionales."""
    if "Region" not in real.columns or "region_salud_mental" not in real.columns:
        return {}
    result: dict[tuple[str, str], float] = {}
    # Usar region_salud_mental como agrupador
    for (pad, region), grp in real.groupby(["Padecimiento", "region_salud_mental"]):
        # Ultima poblacion por entidad, luego sumar
        pop = grp.groupby("Entidad")["Total"].last().sum()
        region_norm = _normalizar_entidad(str(region))
        result[(str(pad), region_norm)] = float(pop)
    return result


# ---------------------------------------------------------------------------
# N-way merge
# ---------------------------------------------------------------------------


def merge_all_models(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge N-way por claves comunes.  Renombra metricas a ``{metric}_{model}``.

    Normaliza nombres de entidad (quita acentos) antes del merge para evitar
    que DeepAR ("Mexico") y Prophet ("México") generen filas duplicadas.
    """
    base_cols = _MERGE_KEYS + [
        c
        for c in ("confianza", "promedio_semanal")
        if any(c in df.columns for df in data.values())
    ]

    # Construir lookup normalizado -> nombre con acentos (preferir la version
    # acentuada que viene de Prophet/Ensemble/Stacking).
    ent_display: dict[str, str] = {}
    for df in data.values():
        if "Entidad" in df.columns:
            for name in df["Entidad"].dropna().unique():
                norm = _normalizar_entidad(str(name))
                # Preferir la version mas larga (con acentos)
                if norm not in ent_display or len(str(name)) > len(ent_display[norm]):
                    ent_display[norm] = str(name)

    merged: pd.DataFrame | None = None
    for model_key, df in data.items():
        keep = [c for c in base_cols if c in df.columns]
        metric_cols = [c for c in _METRICS_MERGE if c in df.columns]
        subset = df[keep + metric_cols].copy()
        # DeepAR almacena nacionales como Entidad='general'/'hombres'/'mujeres'
        # con nivel='regional' y sexo='incrementos_total'.  En realidad el
        # Entidad codifica el sexo.  Normalizar: mover Entidad→sexo, vaciar
        # Entidad, cambiar nivel a 'nacional' para que haga match con
        # Prophet/Ensemble/Stacking.
        if "Entidad" in subset.columns and "nivel" in subset.columns and "sexo" in subset.columns:
            _sexo_map = {
                "general": "incrementos_total",
                "hombres": "incrementos_hombres",
                "mujeres": "incrementos_mujeres",
            }
            mask_nacional = subset["Entidad"].isin(_sexo_map)
            if mask_nacional.any():
                subset.loc[mask_nacional, "sexo"] = subset.loc[mask_nacional, "Entidad"].map(
                    _sexo_map
                )
                subset.loc[mask_nacional, "nivel"] = "nacional"
                subset.loc[mask_nacional, "Entidad"] = ""
        # Normalizar entidad para merge robusto
        if "Entidad" in subset.columns:
            subset["Entidad"] = subset["Entidad"].map(
                lambda x: _normalizar_entidad(str(x)) if pd.notna(x) else ""
            )
        subset = subset.rename(columns={m: f"{m}_{model_key}" for m in metric_cols})
        if merged is None:
            merged = subset
        else:
            on_cols = [c for c in _MERGE_KEYS if c in merged.columns and c in subset.columns]
            new_cols = on_cols + [c for c in subset.columns if c not in merged.columns]
            merged = merged.merge(subset[new_cols], on=on_cols, how="outer")

    if merged is None:
        return pd.DataFrame()

    # Restaurar nombres de entidad con acentos para display
    if "Entidad" in merged.columns:
        merged["Entidad"] = merged["Entidad"].map(lambda x: ent_display.get(x, x) if x else "")

    # Columna ganador por RMSE
    model_keys = list(data.keys())
    rmse_cols = [f"rmse_{mk}" for mk in model_keys if f"rmse_{mk}" in merged.columns]
    if rmse_cols:
        col_to_model = {col: col.replace("rmse_", "") for col in rmse_cols}
        best = merged[rmse_cols].idxmin(axis=1, skipna=True)
        merged["ganador_rmse"] = best.map(col_to_model).fillna("")

    return merged


def win_rate_by_state(merged: pd.DataFrame, model_keys: list[str]) -> dict[str, pd.DataFrame]:
    """Conteo de victorias RMSE por estado para cada padecimiento."""
    result: dict[str, pd.DataFrame] = {}
    for pad in _PADECIMIENTOS:
        sub = merged[merged["padecimiento"] == pad].copy()
        if sub.empty or "ganador_rmse" not in sub.columns:
            continue
        rows: list[dict[str, object]] = []
        for ent in sorted(sub["Entidad"].unique()):
            ent_data = sub[sub["Entidad"] == ent]
            total = len(ent_data)
            row: dict[str, object] = {"Entidad": ent}
            for mk in model_keys:
                wins = (ent_data["ganador_rmse"] == mk).sum()
                row[_MODEL_LABELS.get(mk, mk)] = wins / total * 100 if total else 0.0
            rows.append(row)
        if rows:
            result[pad] = pd.DataFrame(rows)
    return result
