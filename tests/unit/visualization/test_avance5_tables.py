"""Tests de las funciones puras de ``avance5_tables`` (merge, win-rate, markdown).

El módulo (603 líneas) mezcla carga de archivos (``cargar_completos``, I/O, no se
testea aquí) con transformación de datos y generación de tablas/markdown. Estos
tests fijan la lógica pura (merge N-way, win-rate, tablas y el reporte markdown)
como red de seguridad para el refactor de partición.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from epiforecast.visualization.avance5_tables import (
    _determinar_ganador,
    _tabla_agregada,
    generar_markdown,
    merge_all_models,
    win_rate_by_state,
)

_KEYS = ["prophet", "deepar", "ensemble", "stacking"]
_PADS = ["Depresión", "Parkinson", "Alzheimer"]


def _model_df(scale: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "padecimiento": ["Depresión", "Parkinson"],
            "sexo": ["incrementos_total", "incrementos_total"],
            "nivel": ["estatal", "estatal"],
            "Entidad": ["Jalisco", "Oaxaca"],
            "rmse": [5.0 * scale, 6.0 * scale],
            "mae": [4.0, 5.0],
            "smape": [12.0, 15.0],
            "mase": [0.8, 0.9],
        }
    )


def _merged(n_per_pad: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    rows = []
    for pad in _PADS:
        for i in range(n_per_pad):
            row: dict[str, object] = {
                "padecimiento": pad,
                "sexo": "incrementos_total",
                "nivel": "estatal",
                "Entidad": f"Estado{i}",
            }
            rmses = {}
            for mk in _KEYS:
                row[f"rmse_{mk}"] = float(rng.uniform(3, 9))
                row[f"mae_{mk}"] = float(rng.uniform(2, 7))
                row[f"smape_{mk}"] = float(rng.uniform(10, 30))
                row[f"mase_{mk}"] = float(rng.uniform(0.5, 1.5))
                rmses[mk] = row[f"rmse_{mk}"]
            row["ganador_rmse"] = min(rmses, key=lambda k: rmses[k])
            rows.append(row)
    return pd.DataFrame(rows)


def test_merge_all_models_renombra_y_calcula_ganador():
    data = {"prophet": _model_df(1.0), "deepar": _model_df(0.5)}
    merged = merge_all_models(data)
    assert {"rmse_prophet", "rmse_deepar"} <= set(merged.columns)
    assert "ganador_rmse" in merged.columns
    # DeepAR tiene menor RMSE (scale 0.5) -> gana ambas filas
    assert (merged["ganador_rmse"] == "deepar").all()


def test_win_rate_by_state_porcentajes():
    win = win_rate_by_state(_merged(), _KEYS)
    assert set(win).issubset(set(_PADS)) and win  # un DataFrame por padecimiento con datos
    any_df = next(iter(win.values()))
    assert "Entidad" in any_df.columns
    label_cols = [c for c in any_df.columns if c != "Entidad"]
    # cada fila suma 100% (un único ganador por estado/padecimiento en el fixture)
    assert np.allclose(any_df[label_cols].sum(axis=1).to_numpy(), 100.0)


def test_tabla_agregada_resalta_mejor():
    md = _tabla_agregada(_merged(), _KEYS)
    assert md.startswith("| Métrica |")
    assert "RMSE" in md and "**" in md  # negrita en el mejor de cada métrica


def test_determinar_ganador_devuelve_key_valido():
    g = _determinar_ganador(_merged(), _KEYS)
    assert g in _KEYS


def test_generar_markdown_reporte_completo():
    md = generar_markdown(_merged(), _KEYS)
    assert isinstance(md, str) and len(md) > 200
    # menciona métricas y al menos un modelo
    assert "SMAPE" in md.upper()
    assert any(lbl in md for lbl in ("Prophet", "DeepAR", "Ensemble", "Stacking"))
