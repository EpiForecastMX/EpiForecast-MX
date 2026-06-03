"""Tests del extractor de Dengue de producción (A97.x, layout 12 columnas).

Cubre las funciones puras del orquestador (``reshape_dengue_aggregated``) y las
validaciones anti-corrupción (``duplicated_adjacent_column``, ``total_discrepancy``),
que protegen la extracción 2020+ y antes no tenían pruebas.
"""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.data.extraction.dengue_extractor import reshape_dengue_aggregated
from epiforecast.data.extraction.dengue_validation import (
    duplicated_adjacent_column,
    total_discrepancy,
)


def _fila(entidad: str, sev0: list, sev1: list, sev2: list) -> list:
    """Fila de 12 columnas de datos: 3 severidades x [Sem, H, M, año_anterior]."""
    return [entidad, *sev0, *sev1, *sev2]


def _tabla_prod() -> pd.DataFrame:
    rows = [
        # Aguascalientes: H=4+1+0=5, M=8+0+0=8, Sem=4+1+0=5, prev=2+0+0=2
        _fila("Aguascalientes", [4, 4, 8, 2], [1, 1, 0, 0], [0, 0, 0, 0]),
        # Zacatecas: H=10+2+1=13, M=12+3+0=15, Sem=5+2+1=8, prev=7+0+0=7
        _fila("Zacatecas", [5, 10, 12, 7], [2, 2, 3, 0], [1, 1, 0, 0]),
    ]
    return pd.DataFrame(rows)


def test_reshape_suma_tres_severidades() -> None:
    df = reshape_dengue_aggregated(_tabla_prod(), year=2024, week=45)
    assert list(df["Padecimiento"].unique()) == ["Dengue"]
    ags = df[df["Entidad"] == "Aguascalientes"].iloc[0]
    assert ags["Acumulado_hombres"] == 5
    assert ags["Acumulado_mujeres"] == 8
    assert ags["Casos_semana"] == 5
    assert ags["Acumulado_anio_anterior"] == 2
    assert ags["Semana"] == "45"
    zac = df[df["Entidad"] == "Zacatecas"].iloc[0]
    assert zac["Acumulado_hombres"] == 13
    assert zac["Acumulado_mujeres"] == 15


def test_reshape_rechaza_si_no_son_12_columnas() -> None:
    # 10 columnas de datos (layout histórico) -> debe fallar en el reshape de producción.
    bad = pd.DataFrame([["Aguascalientes", *([1] * 10)]])
    with pytest.raises(ValueError, match="12 columnas|se hallaron"):
        reshape_dengue_aggregated(bad, year=2024, week=10)


def test_total_discrepancy_cero_cuando_cuadra() -> None:
    tabla = _tabla_prod()
    # Suma por columna de datos (1..12):
    # Sem0=9,H0=14,M0=20,prev0=9, Sem1=3,H1=3,M1=3,prev1=0, Sem2=1,H2=1,M2=0,prev2=0
    total = "TOTAL 9 14 20 9 3 3 3 0 1 1 0 0"
    assert total_discrepancy(tabla, total) == 0


def test_total_discrepancy_detecta_desfase() -> None:
    tabla = _tabla_prod()
    total = "TOTAL 9 14 20 9 3 3 3 0 1 1 0 99"  # último col difiere en 99
    assert total_discrepancy(tabla, total) == 99


def test_duplicated_adjacent_column_detecta_artefacto_camelot() -> None:
    # >=16 entidades con dos columnas de datos contiguas idénticas y no triviales.
    rows = []
    for i in range(20):
        r = [f"Estado{i}", 5, 7, 7, 1, 2, 3, 4, 1, 0, 0, 0, 0]  # col2==col3 (=7)
        rows.append(r)
    df = pd.DataFrame(rows)
    assert duplicated_adjacent_column(df) == 2


def test_duplicated_adjacent_column_ok_cuando_no_hay_artefacto() -> None:
    rows = [[f"Estado{i}", 5, 7, 8, 1, 2, 3, 4, 1, 0, 1, 2, 3] for i in range(20)]
    df = pd.DataFrame(rows)
    assert duplicated_adjacent_column(df) is None
