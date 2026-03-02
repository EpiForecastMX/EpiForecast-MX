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

_SEXO_DISPLAY = {
    "incrementos_total": "general",
    "incrementos_hombres": "hombres",
    "incrementos_mujeres": "mujeres",
}

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
                    f"{ganador_label} gana por margen minimo "
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
        parts.append(f"{ganador_label} unico modelo disponible (SMAPE {smape_ganador:.1f}%).")

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
        parts.append(f"Gana en {n_wins}/{total_metrics} metricas.")

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
        out["justificacion"] = justificacion

        # Tipo de modelo: propio vs regional
        entidad = str(out["entidad"])
        if _is_zero_row(row, model_keys) and entidad in region_map:
            region = region_map[entidad]
            out["tipo_modelo"] = "regional"
            out["region_asignada"] = f"region_{region}"
        else:
            out["tipo_modelo"] = "propio"
            out["region_asignada"] = ""

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
                df_out.at[idx_z, "modelo_produccion"] = modelo_regional
                df_out.at[idx_z, "justificacion"] = (
                    f"Sin incidencia local. Se asigna modelo regional "
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
