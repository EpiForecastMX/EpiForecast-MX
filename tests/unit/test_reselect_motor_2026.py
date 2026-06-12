"""Tests de la re-selección de motor productivo neuro (`scripts.reselect_motor_2026`).

Cubre las tres reglas de decisión y el cálculo de SMAPE 2026 por motor, que antes
no tenían test propio (a diferencia de la selección de Dengue en
``test_produccion_dengue.py``). Son funciones puras sobre ``pandas`` — no tocan
archivos, red ni los CSV de producción.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scripts.reselect_motor_2026 import (
    MIN_TOTAL_CASOS,
    MIN_WEEKS_REAL,
    NOISY_FALLBACK,
    reselect,
    smape_per_motor,
)


def _prod_row(entidad: str, modelo: str) -> dict:
    """Fila mínima de producción con las columnas que `reselect` espera/actualiza."""
    row = {
        "padecimiento": "Depresion",
        "entidad": entidad,
        "sexo": "Total",
        "modelo_produccion": modelo,
        "justificacion": "",
    }
    # columnas de métricas por motor que el paso de actualización lee ({motor}_{met})
    for m in ("prophet", "deepar", "ensemble", "stacking"):
        for met in ("smape", "mase", "rmse", "mae"):
            row[f"{m}_{met}"] = 1.0
    return row


def _smape_row(entidad: str, n: float, total: float, smapes: dict[str, float]) -> dict:
    row = {
        "padecimiento": "Depresion",
        "entidad": entidad,
        "sexo": "Total",
        "n_semanas_real_2026": n,
        "total_real_2026": total,
    }
    for m in ("prophet", "deepar", "ensemble", "stacking"):
        row[f"smape_2026_{m}"] = smapes.get(m, np.nan)
    return row


def _run(prod_rows: list[dict], smape_rows: list[dict]) -> pd.DataFrame:
    out = reselect(pd.DataFrame(prod_rows), pd.DataFrame(smape_rows))
    return out.set_index("entidad")


def test_regla1_realidad_fuerte_elige_menor_smape():
    """>=10 semanas y >=10 casos: gana el motor con menor SMAPE 2026 real."""
    prod = [_prod_row("Jalisco", "Stacking")]
    smape = [
        _smape_row(
            "Jalisco",
            n=12,
            total=500.0,
            smapes={"prophet": 20.0, "deepar": 8.0, "ensemble": 30.0, "stacking": 40.0},
        )
    ]
    out = _run(prod, smape)
    assert out.loc["Jalisco", "modelo_produccion"] == "DeepAR"
    assert out.loc["Jalisco", "criterio_seleccion"] == "smape_real_2026"
    assert out.loc["Jalisco", "smape_real_2026_ganador"] == 8.0


def test_regla2_serie_ruidosa_fuerza_ensemble():
    """>=10 semanas pero <10 casos: se fuerza el fallback seguro (Ensemble)."""
    prod = [_prod_row("Colima", "DeepAR")]
    smape = [
        _smape_row(
            "Colima",
            n=12,
            total=float(MIN_TOTAL_CASOS - 2),
            smapes={"prophet": 5.0, "deepar": 6.0, "ensemble": 90.0, "stacking": 7.0},
        )
    ]
    out = _run(prod, smape)
    assert out.loc["Colima", "modelo_produccion"] == NOISY_FALLBACK == "Ensemble"
    assert "ruidosa" in out.loc["Colima", "criterio_seleccion"]


def test_regla3_pocas_semanas_respeta_cv():
    """<10 semanas reales: se respeta la asignación previa por CV (no se cambia)."""
    prod = [_prod_row("Aguascalientes", "Stacking")]
    smape = [
        _smape_row(
            "Aguascalientes",
            n=float(MIN_WEEKS_REAL - 5),
            total=300.0,
            smapes={"prophet": 1.0, "deepar": 1.0, "ensemble": 1.0, "stacking": 99.0},
        )
    ]
    out = _run(prod, smape)
    # aunque Stacking tiene el peor SMAPE, se conserva por falta de realidad reciente
    assert out.loc["Aguascalientes", "modelo_produccion"] == "Stacking"
    assert "cv_smape" in out.loc["Aguascalientes", "criterio_seleccion"]


def test_sin_forecast_2026_valido_respeta_cv():
    """Con realidad suficiente pero sin ningún SMAPE de motor válido, conserva CV."""
    prod = [_prod_row("Sonora", "Prophet")]
    smape = [_smape_row("Sonora", n=12, total=400.0, smapes={})]  # todos NaN
    out = _run(prod, smape)
    assert out.loc["Sonora", "modelo_produccion"] == "Prophet"
    assert out.loc["Sonora", "criterio_seleccion"].startswith("cv_smape")


def test_motor_anterior_se_preserva():
    """`motor_anterior` guarda la asignación original para la auditoría."""
    prod = [_prod_row("Yucatan", "Stacking")]
    smape = [
        _smape_row(
            "Yucatan",
            n=12,
            total=500.0,
            smapes={"prophet": 50.0, "deepar": 5.0, "ensemble": 60.0, "stacking": 70.0},
        )
    ]
    out = _run(prod, smape)
    assert out.loc["Yucatan", "motor_anterior"] == "Stacking"
    assert out.loc["Yucatan", "modelo_produccion"] == "DeepAR"  # reasignado


def test_smape_per_motor_calcula_y_descarta_grupos_cortos():
    """`smape_per_motor` calcula por grupo y descarta los de <10 semanas."""
    weeks_ok = list(range(1, 13))  # 12 semanas -> se conserva
    weeks_short = list(range(1, 6))  # 5 semanas  -> se descarta
    real_rows, fc_rows = [], []
    for ent, weeks in (("Jalisco", weeks_ok), ("Nayarit", weeks_short)):
        for w in weeks:
            real_rows.append(
                {
                    "padecimiento": "Depresion",
                    "entidad": ent,
                    "sexo": "Total",
                    "Semana": w,
                    "real": 100.0 + w,
                }
            )
            # un solo motor con cobertura completa (Prophet); el resto quedará NaN
            fc_rows.append(
                {
                    "padecimiento": "Depresion",
                    "entidad": ent,
                    "sexo": "Total",
                    "Semana": w,
                    "motor": "Prophet",
                    "yhat": 100.0 + w,
                }
            )
    out = smape_per_motor(pd.DataFrame(real_rows), pd.DataFrame(fc_rows)).set_index("entidad")
    assert "Jalisco" in out.index and "Nayarit" not in out.index  # grupo corto descartado
    assert out.loc["Jalisco", "n_semanas_real_2026"] == 12
    assert out.loc["Jalisco", "smape_2026_prophet"] == 0.0  # forecast == real
    assert np.isnan(out.loc["Jalisco", "smape_2026_deepar"])  # motor ausente -> NaN
