"""Test del loader de fuente única del boletín de Dengue."""

from __future__ import annotations

import pandas as pd

from epiforecast.data.boletin import cargar_boletin_dengue


def test_filtra_a_dengue(tmp_path):
    csv = tmp_path / "consolidado.csv"
    pd.DataFrame(
        {
            "Padecimiento": ["Dengue", "Parkinson", "Dengue"],
            "Entidad": ["Veracruz", "Jalisco", "Jalisco"],
            "Anio": [2026, 2026, 2026],
            "Semana": [1, 1, 1],
            "Casos_semana": [10, 5, 7],
        }
    ).to_csv(csv, index=False)
    out = cargar_boletin_dengue(csv)
    assert set(out["Padecimiento"].unique()) == {"Dengue"}
    assert len(out) == 2
    assert out["Casos_semana"].sum() == 17


def test_sin_columna_padecimiento_devuelve_todo(tmp_path):
    csv = tmp_path / "interim.csv"
    pd.DataFrame({"Entidad": ["Veracruz"], "Casos_semana": [3]}).to_csv(csv, index=False)
    out = cargar_boletin_dengue(csv)
    assert len(out) == 1
