"""Genera CSV con la tabla completa de modelos y seleccion de produccion.

Compara los 4 algoritmos (Prophet, DeepAR, Ensemble, Stacking) para cada
combinacion (padecimiento x entidad x sexo) y selecciona el modelo de
produccion con justificacion automatica.

Uso:
    python -m scripts.genera_tabla_produccion
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from epiforecast.utils.config import logger
from epiforecast.visualization.avance5_tables import (
    _MODEL_LABELS,
    cargar_completos,
    merge_all_models,
)

_MODELS = ["prophet", "deepar", "ensemble", "stacking"]
_METRICS = ["rmse", "mae", "smape", "mase"]
_EMPATE_PCT = 0.05  # 5% para considerar empate en SMAPE
_HORIZON = 52  # semanas de pronostico
_LOW_VOLUME_THRESHOLD = 5  # casos/52sem para considerar baja confianza

_SEXO_DISPLAY = {
    "incrementos_total": "general",
    "incrementos_hombres": "hombres",
    "incrementos_mujeres": "mujeres",
}

_MODO_TO_INCREMENTO = {
    "general": "incrementos_total",
    "hombres": "incrementos_hombres",
    "mujeres": "incrementos_mujeres",
}

# Umbrales diagnosticos (mismos que comparison_html.py)
_OVERFIT_ALTO = 2.0
_OVERFIT_MODERADO = 1.3
_LEAKAGE_THRESHOLD = 0.5

_OUTPUT = Path("reports") / "reports" / "tabla_333_modelos_produccion.csv"


def _best_model_for_metric(
    row: pd.Series,  # type: ignore[type-arg]
    metric: str,
    model_keys: list[str],
) -> str:
    """Retorna el nombre del modelo con menor valor en la metrica dada."""
    vals: dict[str, float] = {}
    for mk in model_keys:
        col = f"{metric}_{mk}"
        v = row.get(col)
        if pd.notna(v):
            vals[mk] = float(v)
    if not vals:
        return ""
    best_key = min(vals, key=lambda k: vals[k])
    return _MODEL_LABELS.get(best_key, best_key)


def _count_wins(row: pd.Series, model_keys: list[str]) -> dict[str, int]:  # type: ignore[type-arg]
    """Cuenta en cuantas metricas gana cada modelo."""
    wins: dict[str, int] = {mk: 0 for mk in model_keys}
    for metric in _METRICS:
        vals: dict[str, float] = {}
        for mk in model_keys:
            col = f"{metric}_{mk}"
            v = row.get(col)
            if pd.notna(v):
                vals[mk] = float(v)
        if vals:
            best = min(vals, key=lambda k: vals[k])
            wins[best] += 1
    return wins


def _get_metric_vals(
    row: pd.Series,  # type: ignore[type-arg]
    metric: str,
    available: list[str],
) -> dict[str, float]:
    """Extrae valores de una metrica para los modelos disponibles."""
    vals: dict[str, float] = {}
    for mk in available:
        v = row.get(f"{metric}_{mk}")
        if pd.notna(v):
            vals[mk] = float(v)
    return vals


def _select_production(
    row: pd.Series,  # type: ignore[type-arg]
    model_keys: list[str],
) -> tuple[str, int, str]:
    """Selecciona modelo de produccion con justificacion.

    Criterio: SMAPE primario → desempate por MASE → desempate por RMSE.

    Returns:
        (modelo_key, n_victorias, justificacion)
    """
    available = [mk for mk in model_keys if pd.notna(row.get(f"smape_{mk}"))]
    if not available:
        return ("", 0, "Sin datos disponibles.")

    smape_vals = _get_metric_vals(row, "smape", available)
    mase_vals = _get_metric_vals(row, "mase", available)
    rmse_vals = _get_metric_vals(row, "rmse", available)

    # 1. Ganador por SMAPE (menor es mejor)
    smape_winner = min(smape_vals, key=lambda k: smape_vals[k])
    smape_best = smape_vals[smape_winner]

    # 2. Desempate si diferencia < 5%
    ganador = smape_winner
    for mk in available:
        if mk == smape_winner:
            continue
        if smape_vals[mk] > 0 and abs(smape_vals[mk] - smape_best) / smape_vals[mk] < _EMPATE_PCT:
            # Desempate por MASE
            mase_w = mase_vals.get(smape_winner)
            mase_c = mase_vals.get(mk)
            if mase_w is not None and mase_c is not None and mase_c < mase_w:
                ganador = mk
                break
            # Desempate por RMSE
            rmse_w = rmse_vals.get(smape_winner)
            rmse_c = rmse_vals.get(mk)
            if rmse_w is not None and rmse_c is not None and rmse_c < rmse_w:
                ganador = mk
                break

    # Contar victorias del ganador
    wins = _count_wins(row, available)
    n_wins = wins.get(ganador, 0)
    total_metrics = sum(
        1 for m in _METRICS if any(pd.notna(row.get(f"{m}_{mk}")) for mk in available)
    )

    # --- Construir justificacion centrada en SMAPE / MASE ---
    ganador_label = _MODEL_LABELS.get(ganador, ganador)
    smape_ganador = smape_vals[ganador]
    mase_ganador = mase_vals.get(ganador)
    parts: list[str] = []

    # Comparacion SMAPE con segundo lugar
    otros = sorted(
        [(mk, v) for mk, v in smape_vals.items() if mk != ganador],
        key=lambda x: x[1],
    )
    if otros:
        segundo_key, smape_segundo = otros[0]
        segundo_label = _MODEL_LABELS.get(segundo_key, segundo_key)
        if smape_ganador <= smape_segundo and smape_segundo > 0:
            pct_diff = (smape_segundo - smape_ganador) / smape_segundo * 100
            if pct_diff < 5:
                parts.append(
                    f"{ganador_label} gana por margen mínimo "
                    f"(SMAPE {smape_ganador:.1f}% vs {segundo_label} {smape_segundo:.1f}%, "
                    f"-{pct_diff:.1f}%)."
                )
            else:
                parts.append(
                    f"{ganador_label} domina con SMAPE {smape_ganador:.1f}% "
                    f"(vs {segundo_label} {smape_segundo:.1f}%)."
                )
        else:
            parts.append(
                f"{ganador_label} elegido por desempate MASE/RMSE "
                f"(SMAPE {smape_ganador:.1f}% vs {segundo_label} {smape_segundo:.1f}%)."
            )
    else:
        parts.append(f"{ganador_label} único modelo disponible (SMAPE {smape_ganador:.1f}%).")

    # MASE: interpretacion relativa al naive seasonal
    if mase_ganador is not None:
        if mase_ganador < 0.5:
            parts.append(f"MASE={mase_ganador:.2f}, muy superior al naive seasonal.")
        elif mase_ganador < 1.0:
            parts.append(f"MASE={mase_ganador:.2f}, supera naive seasonal.")
        else:
            parts.append(f"MASE={mase_ganador:.2f}, no supera naive seasonal.")

    # Victorias
    if n_wins > 1:
        parts.append(f"Gana en {n_wins}/{total_metrics} métricas.")

    # SMAPE > 150% = serie de bajo volumen
    if smape_ganador > 150:
        parts.append("Serie de bajo volumen.")

    # RMSE como dato complementario
    rmse_ganador = rmse_vals.get(ganador)
    if rmse_ganador is not None:
        parts.append(f"RMSE={rmse_ganador:.2f}.")

    return (ganador, n_wins, " ".join(parts))


def _display_entidad(row: pd.Series) -> str:  # type: ignore[type-arg]
    """Nombre de entidad legible."""
    ent = row.get("Entidad", "")
    if not ent or ent == "":
        nivel = row.get("nivel", "")
        if nivel == "nacional":
            return "Nacional"
        return "Nacional"
    return str(ent)


def _build_region_map() -> dict[str, str]:
    """Construye mapa entidad -> region desde data_inegi_General.csv."""
    real_path = Path("data") / "processed" / "data_inegi_General.csv"
    if not real_path.exists():
        return {}
    real = pd.read_csv(real_path)
    if "region_salud_mental" not in real.columns:
        return {}
    return dict(real.groupby("Entidad")["region_salud_mental"].first().items())


_MODEL_KEY_MAP: dict[str, str] = {
    "Prophet": "prophet",
    "DeepAR": "deepar",
    "Ensemble": "ensemble",
    "Stacking": "stacking",
}

_SEXO_TO_MODO: dict[str, str] = {
    "general": "general",
    "hombres": "hombres",
    "mujeres": "mujeres",
}


def _load_forecasts() -> dict[str, pd.DataFrame]:
    """Carga los CSVs de forecast de cada modelo (ultimas _HORIZON filas por serie)."""
    forecasts: dict[str, pd.DataFrame] = {}
    base = Path("reports") / "forecasts"
    for mk in _MODELS:
        csv_path = base / mk / f"all_forecast_{mk}.csv"
        if not csv_path.exists():
            logger.warning("Forecast no encontrado: {}", csv_path)
            continue
        df = pd.read_csv(csv_path)
        df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
        forecasts[mk] = df
        logger.info("  Forecast cargado {}: {} filas", mk, len(df))
    return forecasts


def _sum_forecast_52(
    forecasts: dict[str, pd.DataFrame],
    modelo_key: str,
    padecimiento: str,
    entidad: str,
    sexo: str,
) -> float:
    """Suma las ultimas 52 semanas de yhat para una combinacion dada."""
    if modelo_key not in forecasts:
        return np.nan
    df = forecasts[modelo_key]
    modo = _SEXO_TO_MODO.get(sexo, sexo)
    # Normalizar: production usa "region_X", forecast usa "Region X"
    meta_ent = entidad
    if meta_ent.startswith("region_"):
        meta_ent = "Region " + meta_ent[len("region_") :]

    mask = (
        (df["meta_padecimiento"] == padecimiento)
        & (df["meta_entidad"] == meta_ent)
        & (df["meta_modo"] == modo)
    )
    serie = df.loc[mask].sort_values("ds")
    if serie.empty:
        return np.nan
    last_52 = serie.tail(_HORIZON)
    total = last_52["yhat"].sum()
    return int(round(max(total, 0.0)))


def _overfitting_label(smape_test: float | None, smape_train: float | None) -> str:
    """Devuelve etiqueta de overfitting (texto plano, sin HTML)."""
    if (
        smape_test is None
        or smape_train is None
        or (isinstance(smape_test, float) and np.isnan(smape_test))
        or (isinstance(smape_train, float) and np.isnan(smape_train))
        or smape_train == 0
    ):
        return "N/D"
    ratio = smape_test / smape_train
    if ratio > _OVERFIT_ALTO:
        return f"Alto ({ratio:.1f}x)"
    if ratio > _OVERFIT_MODERADO:
        return f"Moderado ({ratio:.1f}x)"
    return f"OK ({ratio:.1f}x)"


def _leakage_label(smape_train: float | None) -> str:
    """Devuelve etiqueta de leakage (texto plano, sin HTML)."""
    if smape_train is None or (isinstance(smape_train, float) and np.isnan(smape_train)):
        return "N/D"
    if smape_train < _LEAKAGE_THRESHOLD:
        return f"Sospechoso ({smape_train:.2f}%)"
    return f"OK ({smape_train:.1f}%)"


def _load_real_data() -> pd.DataFrame:
    """Carga datos reales de data_inegi_General.csv para calcular casos historicos."""
    path = Path("data") / "processed" / "data_inegi_General.csv"
    if not path.exists():
        logger.warning("No se encontró datos reales: {}", path)
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    return df


def _prev_52_real(
    real_df: pd.DataFrame,
    padecimiento: str,
    entidad: str,
    sexo: str,
) -> float:
    """Suma las ultimas 52 semanas de incidencia real para la combinacion dada."""
    if real_df.empty:
        return np.nan
    col_inc = _MODO_TO_INCREMENTO.get(sexo, "incrementos_total")
    if col_inc not in real_df.columns:
        return np.nan

    # Normalizar nombre de entidad para match con real data
    meta_ent = entidad
    if meta_ent.startswith("region_"):
        meta_ent = "Region " + meta_ent[len("region_") :]

    # Agregados: Nacional o Region -> sumar estados constituyentes
    if entidad == "Nacional":
        mask_n = real_df["Padecimiento"] == padecimiento
        agg = real_df.loc[mask_n].groupby("Fecha")[col_inc].sum().reset_index()
        agg = agg.sort_values("Fecha")
        if len(agg) < _HORIZON:
            return np.nan
        total = agg.tail(_HORIZON)[col_inc].sum()
        return int(round(max(total, 0.0)))

    if entidad.startswith("region_"):
        region_name = entidad[len("region_") :]
        if "region_salud_mental" in real_df.columns:
            mask_r = (real_df["Padecimiento"] == padecimiento) & (
                real_df["region_salud_mental"] == region_name
            )
            agg = real_df.loc[mask_r].groupby("Fecha")[col_inc].sum().reset_index()
            agg = agg.sort_values("Fecha")
            if len(agg) >= _HORIZON:
                total = agg.tail(_HORIZON)[col_inc].sum()
                return int(round(max(total, 0.0)))
        return np.nan

    mask = (real_df["Padecimiento"] == padecimiento) & (real_df["Entidad"] == meta_ent)
    serie = real_df.loc[mask].sort_values("Fecha")
    if serie.empty or len(serie) < _HORIZON:
        return np.nan
    total = serie.tail(_HORIZON)[col_inc].sum()
    return int(round(max(total, 0.0)))


def _prev_52_pronos(
    forecasts: dict[str, pd.DataFrame],
    modelo_key: str,
    padecimiento: str,
    entidad: str,
    sexo: str,
    real_df: pd.DataFrame,
) -> float:
    """Suma el yhat del modelo para las mismas 52 semanas que cubren los datos reales."""
    if modelo_key not in forecasts:
        return np.nan
    df = forecasts[modelo_key]
    modo = _SEXO_TO_MODO.get(sexo, sexo)
    meta_ent = entidad
    if meta_ent.startswith("region_"):
        meta_ent = "Region " + meta_ent[len("region_") :]

    mask_fc = (
        (df["meta_padecimiento"] == padecimiento)
        & (df["meta_entidad"] == meta_ent)
        & (df["meta_modo"] == modo)
    )
    serie_fc = df.loc[mask_fc].sort_values("ds")
    if serie_fc.empty:
        return np.nan

    # Determinar rango de las ultimas 52 semanas reales
    col_inc = _MODO_TO_INCREMENTO.get(sexo, "incrementos_total")
    if not real_df.empty and col_inc in real_df.columns:
        if entidad == "Nacional":
            mask_r = real_df["Padecimiento"] == padecimiento
            fechas = real_df.loc[mask_r, "Fecha"].sort_values().unique()
        else:
            mask_r = (real_df["Padecimiento"] == padecimiento) & (real_df["Entidad"] == meta_ent)
            fechas = real_df.loc[mask_r, "Fecha"].sort_values()
        if len(fechas) >= _HORIZON:
            last_52_dates = pd.to_datetime(pd.Series(fechas)).sort_values().tail(_HORIZON)
            date_min = last_52_dates.iloc[0]
            date_max = last_52_dates.iloc[-1]
            in_range = serie_fc[(serie_fc["ds"] >= date_min) & (serie_fc["ds"] <= date_max)]
            if len(in_range) >= _HORIZON - 2:  # tolerancia de +-2 semanas
                total = in_range["yhat"].sum()
                return int(round(max(total, 0.0)))

    # Fallback: tomar las 52 semanas anteriores a las ultimas 52 (horizonte futuro)
    n = len(serie_fc)
    if n < _HORIZON * 2:
        return np.nan
    prev_block = serie_fc.iloc[-(2 * _HORIZON) : -_HORIZON]
    total = prev_block["yhat"].sum()
    return int(round(max(total, 0.0)))


_ZERO_THRESHOLD = 1e-6


def _is_zero_row(row: pd.Series, model_keys: list[str]) -> bool:  # type: ignore[type-arg]
    """True si todas las metricas RMSE son ~0 o NaN (serie sin incidencia)."""
    for mk in model_keys:
        v = row.get(f"rmse_{mk}")
        if pd.notna(v) and float(v) > _ZERO_THRESHOLD:
            return False
    return True


def main() -> None:
    """Genera la tabla de 333 modelos de produccion."""
    logger.info("=== Tabla de modelos de produccion ===")

    # 1. Cargar y merge
    data = cargar_completos()
    if not data:
        logger.error("No se encontraron CSVs. Ejecute 'make train-all' primero.")
        return

    model_keys = [mk for mk in _MODELS if mk in data]
    merged = merge_all_models(data)
    logger.info("Merge: {} filas, modelos: {}", len(merged), model_keys)

    # Mapa entidad -> region para asignar modelo regional
    region_map = _build_region_map()

    # Cargar forecasts para sumar las 52 semanas proyectadas
    forecasts = _load_forecasts()

    # Cargar datos reales para calcular casos historicos
    real_df = _load_real_data()

    # 2. Construir tabla de salida
    rows_out: list[dict[str, object]] = []

    for idx, (_, row) in enumerate(
        merged.sort_values(["padecimiento", "Entidad", "sexo"]).iterrows(),
        start=1,
    ):
        ganador_key, n_wins, justificacion = _select_production(row, model_keys)
        total_metrics = sum(
            1 for m in _METRICS if any(pd.notna(row.get(f"{m}_{mk}")) for mk in model_keys)
        )

        out: dict[str, object] = {
            "numero": idx,
            "padecimiento": row.get("padecimiento", ""),
            "entidad": _display_entidad(row),
            "sexo": _SEXO_DISPLAY.get(str(row.get("sexo", "")), str(row.get("sexo", ""))),
        }

        # Metricas por modelo
        for mk in _MODELS:
            for metric in _METRICS:
                col = f"{metric}_{mk}"
                val = row.get(col)
                out[f"{mk}_{metric}"] = round(float(val), 4) if pd.notna(val) else np.nan

        # Mejor por metrica
        for metric in _METRICS:
            out[f"mejor_{metric}"] = _best_model_for_metric(row, metric, model_keys)

        # Produccion
        out["victorias"] = f"{n_wins}/{total_metrics}" if total_metrics > 0 else "0/0"
        out["modelo_produccion"] = _MODEL_LABELS.get(ganador_key, ganador_key)

        # Tipo de modelo: propio vs regional (antes de justificacion)
        entidad = str(out["entidad"])
        if _is_zero_row(row, model_keys) and entidad in region_map:
            region = region_map[entidad]
            out["tipo_modelo"] = "regional"
            out["region_asignada"] = f"region_{region}"
        else:
            out["tipo_modelo"] = "propio"
            out["region_asignada"] = ""

        # Casos proyectados 52 semanas del modelo de produccion
        modelo_fc_key = _MODEL_KEY_MAP.get(str(out["modelo_produccion"]), ganador_key)
        out["casos_52_semanas_futuro"] = _sum_forecast_52(
            forecasts,
            modelo_fc_key,
            str(out["padecimiento"]),
            str(out["entidad"]),
            str(out["sexo"]),
        )

        # Metricas del modelo de produccion
        smape_prod = row.get(f"smape_{ganador_key}") if ganador_key else None
        mase_prod = row.get(f"mase_{ganador_key}") if ganador_key else None
        rmse_prod = row.get(f"rmse_{ganador_key}") if ganador_key else None
        mae_prod = row.get(f"mae_{ganador_key}") if ganador_key else None
        smape_train_prod = row.get(f"smape_train_{ganador_key}") if ganador_key else None

        out["smape_prod"] = round(float(smape_prod), 4) if pd.notna(smape_prod) else np.nan
        out["mase_prod"] = round(float(mase_prod), 4) if pd.notna(mase_prod) else np.nan
        out["rmse_prod"] = round(float(rmse_prod), 4) if pd.notna(rmse_prod) else np.nan
        out["mae_prod"] = round(float(mae_prod), 4) if pd.notna(mae_prod) else np.nan

        # Diagnosticos: overfitting y leakage
        _smape_test = float(smape_prod) if pd.notna(smape_prod) else None
        _smape_tr = float(smape_train_prod) if pd.notna(smape_train_prod) else None
        out["overfitting"] = _overfitting_label(_smape_test, _smape_tr)
        out["leakage"] = _leakage_label(_smape_tr)

        # Casos historicos: ultimas 52 semanas reales y pronosticadas por el modelo
        out["casos_prev_52_semanas_real"] = _prev_52_real(
            real_df, str(out["padecimiento"]), str(out["entidad"]), str(out["sexo"])
        )
        out["casos_prev_52_semanas_pronos"] = _prev_52_pronos(
            forecasts,
            modelo_fc_key,
            str(out["padecimiento"]),
            str(out["entidad"]),
            str(out["sexo"]),
            real_df,
        )

        out["justificacion"] = justificacion

        rows_out.append(out)

    df_out = pd.DataFrame(rows_out)

    # Asignar modelo regional a filas con metricas en cero:
    # buscar la fila de la region correspondiente (mismo padecimiento y sexo)
    zero_mask = df_out["tipo_modelo"] == "regional"
    if zero_mask.any():
        for idx_z in df_out[zero_mask].index:
            pad = df_out.at[idx_z, "padecimiento"]
            sexo = df_out.at[idx_z, "sexo"]
            region = df_out.at[idx_z, "region_asignada"]
            # Buscar la fila regional
            region_row = df_out[
                (df_out["entidad"] == region)
                & (df_out["padecimiento"] == pad)
                & (df_out["sexo"] == sexo)
            ]
            if not region_row.empty:
                modelo_regional = region_row.iloc[0]["modelo_produccion"]
                casos_regional = region_row.iloc[0]["casos_52_semanas_futuro"]
                df_out.at[idx_z, "modelo_produccion"] = modelo_regional
                df_out.at[idx_z, "casos_52_semanas_futuro"] = casos_regional
                df_out.at[idx_z, "justificacion"] = (
                    f"Sin incidencia local. Se asigna modelo de la región "
                    f"({region}): {modelo_regional}."
                )
                logger.info(
                    "  {} {} {}: sin incidencia -> {} ({})",
                    pad,
                    df_out.at[idx_z, "entidad"],
                    sexo,
                    modelo_regional,
                    region,
                )

    # Reasignar modelo regional a filas con baja confianza (<5 casos en 52 semanas)
    # Solo aplica a entidades estatales (no Nacional, no regiones)
    _entidades_no_reasignables = {"Nacional"} | {
        e for e in df_out["entidad"].unique() if str(e).startswith("region_")
    }
    low_mask = (
        (df_out["casos_52_semanas_futuro"] < _LOW_VOLUME_THRESHOLD)
        & (df_out["tipo_modelo"] == "propio")
        & (~df_out["entidad"].isin(_entidades_no_reasignables))
    )
    if low_mask.any():
        logger.info(
            "--- Reasignacion por baja confianza (<{} casos/52sem) ---", _LOW_VOLUME_THRESHOLD
        )
        for idx_l in df_out[low_mask].index:
            ent = df_out.at[idx_l, "entidad"]
            if ent not in region_map:
                continue
            pad = df_out.at[idx_l, "padecimiento"]
            sexo = df_out.at[idx_l, "sexo"]
            casos_orig = df_out.at[idx_l, "casos_52_semanas_futuro"]
            modelo_orig = df_out.at[idx_l, "modelo_produccion"]
            region = region_map[ent]
            region_key = f"region_{region}"
            region_row = df_out[
                (df_out["entidad"] == region_key)
                & (df_out["padecimiento"] == pad)
                & (df_out["sexo"] == sexo)
            ]
            if not region_row.empty:
                modelo_regional = region_row.iloc[0]["modelo_produccion"]
                casos_regional = region_row.iloc[0]["casos_52_semanas_futuro"]
                df_out.at[idx_l, "modelo_produccion"] = modelo_regional
                df_out.at[idx_l, "casos_52_semanas_futuro"] = casos_regional
                df_out.at[idx_l, "tipo_modelo"] = "regional"
                df_out.at[idx_l, "region_asignada"] = region_key
                df_out.at[idx_l, "justificacion"] = (
                    f"Baja confianza: {casos_orig} casos proyectados en 52 semanas "
                    f"(modelo local: {modelo_orig}). "
                    f"Se asigna modelo de la región ({region_key}): {modelo_regional}."
                )
                logger.info(
                    "  {} {} {}: {} casos -> {} ({})",
                    pad,
                    ent,
                    sexo,
                    casos_orig,
                    modelo_regional,
                    region_key,
                )

    # 3. Guardar CSV
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(_OUTPUT, index=False, encoding="utf-8-sig")
    logger.success("CSV generado: {} ({} filas)", _OUTPUT, len(df_out))

    # 4. Resumen
    logger.info("--- Distribucion de modelos de produccion ---")
    counts = df_out["modelo_produccion"].value_counts()
    total = len(df_out)
    for modelo, n in counts.items():
        logger.info("  {}: {}/{} ({:.1f}%)", modelo, n, total, n / total * 100)

    # Resumen por padecimiento
    for pad in sorted(df_out["padecimiento"].unique()):
        sub = df_out[df_out["padecimiento"] == pad]
        pad_counts = sub["modelo_produccion"].value_counts()
        parts = [f"{m}: {c}" for m, c in pad_counts.items()]
        logger.info("  {} -> {}", pad, ", ".join(parts))


if __name__ == "__main__":
    main()
