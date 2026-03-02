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
_EMPATE_PCT = 0.05  # 5% para considerar empate en RMSE

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


def _select_production(
    row: pd.Series,  # type: ignore[type-arg]
    model_keys: list[str],
) -> tuple[str, int, str]:
    """Selecciona modelo de produccion con justificacion.

    Returns:
        (modelo_key, n_victorias, justificacion)
    """
    available = [mk for mk in model_keys if pd.notna(row.get(f"rmse_{mk}"))]
    if not available:
        return ("", 0, "Sin datos disponibles.")

    # 1. Ganador por RMSE
    rmse_vals = {mk: float(row[f"rmse_{mk}"]) for mk in available}
    rmse_winner = min(rmse_vals, key=lambda k: rmse_vals[k])
    rmse_best = rmse_vals[rmse_winner]

    # 2. Desempate si diferencia < 5%
    ganador = rmse_winner
    for mk in available:
        if mk == rmse_winner:
            continue
        if rmse_vals[mk] > 0 and abs(rmse_vals[mk] - rmse_best) / rmse_vals[mk] < _EMPATE_PCT:
            # Desempate por MASE
            mase_w = row.get(f"mase_{rmse_winner}")
            mase_c = row.get(f"mase_{mk}")
            if pd.notna(mase_w) and pd.notna(mase_c) and float(mase_c) < float(mase_w):
                ganador = mk
                break
            # Desempate por MAE
            mae_w = row.get(f"mae_{rmse_winner}")
            mae_c = row.get(f"mae_{mk}")
            if pd.notna(mae_w) and pd.notna(mae_c) and float(mae_c) < float(mae_w):
                ganador = mk
                break

    # Contar victorias del ganador
    wins = _count_wins(row, available)
    n_wins = wins.get(ganador, 0)
    total_metrics = sum(
        1 for m in _METRICS if any(pd.notna(row.get(f"{m}_{mk}")) for mk in available)
    )

    # Construir justificacion
    ganador_label = _MODEL_LABELS.get(ganador, ganador)
    rmse_ganador = rmse_vals[ganador]
    parts: list[str] = []

    # Comparacion con segundo lugar (excluir al ganador, tomar el mejor de los demas)
    otros = sorted(
        [(mk, v) for mk, v in rmse_vals.items() if mk != ganador],
        key=lambda x: x[1],
    )
    if otros:
        segundo_key, rmse_segundo = otros[0]
        segundo_label = _MODEL_LABELS.get(segundo_key, segundo_key)
        # Si ganador fue elegido por desempate, puede tener RMSE >= segundo
        if rmse_ganador <= rmse_segundo and rmse_segundo > 0:
            pct_diff = (rmse_segundo - rmse_ganador) / rmse_segundo * 100
            if pct_diff < 5:
                parts.append(
                    f"{ganador_label} gana por margen minimo "
                    f"(RMSE {rmse_ganador:.2f} vs {segundo_label} {rmse_segundo:.2f}, "
                    f"-{pct_diff:.1f}%)."
                )
            else:
                parts.append(
                    f"{ganador_label} domina con RMSE {rmse_ganador:.2f} "
                    f"(vs {segundo_label} {rmse_segundo:.2f})."
                )
        else:
            # Ganador elegido por desempate (MASE/MAE), no por RMSE
            parts.append(
                f"{ganador_label} elegido por desempate MASE/MAE "
                f"(RMSE {rmse_ganador:.2f} vs {segundo_label} {rmse_segundo:.2f})."
            )
    else:
        parts.append(f"{ganador_label} unico modelo disponible (RMSE {rmse_ganador:.2f}).")

    # Victorias
    if n_wins > 1:
        parts.append(f"Gana en {n_wins}/{total_metrics} metricas.")

    # MASE < 1
    mase_val = row.get(f"mase_{ganador}")
    if pd.notna(mase_val) and float(mase_val) < 1.0:
        parts.append(f"MASE={float(mase_val):.2f} supera naive seasonal.")

    # SMAPE > 150% = serie de bajo volumen
    smape_val = row.get(f"smape_{ganador}")
    if pd.notna(smape_val) and float(smape_val) > 150:
        parts.append("Serie de bajo volumen.")

    justificacion = " ".join(parts)
    return (ganador, n_wins, justificacion)


def _display_entidad(row: pd.Series) -> str:  # type: ignore[type-arg]
    """Nombre de entidad legible."""
    ent = row.get("Entidad", "")
    if not ent or ent == "":
        nivel = row.get("nivel", "")
        if nivel == "nacional":
            return "Nacional"
        return "Nacional"
    return str(ent)


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

        rows_out.append(out)

    df_out = pd.DataFrame(rows_out)

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
