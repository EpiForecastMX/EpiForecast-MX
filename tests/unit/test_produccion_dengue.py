"""Tests de las reglas de selección de motor productivo de Dengue."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scripts.produccion_dengue import _pick, mae, smape


def _row(**kw) -> pd.Series:
    base = {
        "n_semanas_real_2026": 20,
        "total_real_2026": 1000.0,
        "smape_2026_prophet": np.nan,
        "smape_2026_deepar": np.nan,
        "mae_2026_prophet": np.nan,
        "mae_2026_deepar": np.nan,
        "cv_smape_prophet": np.nan,
        "cv_smape_deepar": np.nan,
    }
    base.update(kw)
    return pd.Series(base)


def test_smape_cero_seguro():
    assert np.isnan(smape(np.array([0.0]), np.array([0.0])))  # denom 0 → nan
    assert smape(np.array([100.0]), np.array([100.0])) == 0.0  # predicción perfecta


def test_mae_arreglo_vacio_no_revienta():
    assert np.isnan(mae(np.array([]), np.array([])))


def test_regla1_elige_menor_smape_real():
    row = _row(smape_2026_prophet=40.0, smape_2026_deepar=20.0)
    motor, criterio, _ = _pick(row)
    assert motor == "DeepAR"
    assert criterio == "smape_real_2026"


def test_regla1_desempate_por_mae():
    # SMAPE empatado (mismo valor) → desempata por MAE menor.
    row = _row(
        smape_2026_prophet=30.0, smape_2026_deepar=30.0, mae_2026_prophet=5.0, mae_2026_deepar=2.0
    )
    motor, _, _ = _pick(row)
    assert motor == "DeepAR"


def test_regla2_casi_cero_elige_menor_mae():
    # Serie casi-cero (total < 10): no usa SMAPE, elige menor MAE (más cerca de 0).
    row = _row(
        total_real_2026=3.0,
        smape_2026_prophet=10.0,
        smape_2026_deepar=200.0,
        mae_2026_prophet=4.0,
        mae_2026_deepar=1.0,
    )
    motor, criterio, _ = _pick(row)
    assert motor == "DeepAR"
    assert criterio == "mae_real_2026_casi_cero"


def test_regla3_sin_realidad_usa_cv():
    row = _row(n_semanas_real_2026=3, cv_smape_prophet=15.0, cv_smape_deepar=80.0)
    motor, criterio, _ = _pick(row)
    assert motor == "Prophet"
    assert criterio == "cv_smape"


def test_default_es_motor_elegible():
    # Sin SMAPE, sin MAE, sin CV → default debe ser un motor ELEGIBLE (no Ensemble).
    row = _row(n_semanas_real_2026=3)  # <10 y todo NaN
    motor, criterio, _ = _pick(row)
    assert criterio == "default"
    assert motor in ("Prophet", "DeepAR")
