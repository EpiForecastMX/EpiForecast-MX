"""Tests del parser histórico A97.x (2018 sem 27+ y 2019, layout de 10 columnas)."""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.data.extraction.dengue_historico import (
    N_DATA_COLS_HIST,
    reshape_dengue_hist,
    total_discrepancy_hist,
)


def _fila(entidad: str, sev0: list, sev1: list, sev2: list) -> list:
    """Construye una fila del layout histórico: entidad + sev0(4) + sev1(3) + sev2(3)."""
    return [entidad, *sev0, *sev1, *sev2]


def _tabla_historica() -> pd.DataFrame:
    """Tabla mínima de 2 entidades en el layout histórico de 10 columnas de datos.

    sev0 = [Sem, H, M, prev]; sev1 = [Sem, H, M]; sev2 = [Sem, H, M].
    """
    rows = [
        # Aguascalientes: H = 4+1+0 = 5, M = 8+0+0 = 8, Sem = 4+1+0 = 5
        _fila("Aguascalientes", [4, 4, 8, 2], [1, 1, 0], [0, 0, 0]),
        # Zacatecas: H = 10+2+1 = 13, M = 12+3+0 = 15, Sem = 5+2+1 = 8
        _fila("Zacatecas", [5, 10, 12, 7], [2, 2, 3], [1, 1, 0]),
    ]
    return pd.DataFrame(rows)


def test_reshape_suma_severidades_por_sexo() -> None:
    df = reshape_dengue_hist(_tabla_historica(), year=2019, week=45)
    assert list(df["Padecimiento"].unique()) == ["Dengue"]
    ags = df[df["Entidad"] == "Aguascalientes"].iloc[0]
    assert ags["Acumulado_hombres"] == 5  # 4 + 1 + 0
    assert ags["Acumulado_mujeres"] == 8  # 8 + 0 + 0
    assert ags["Casos_semana"] == 5  # 4 + 1 + 0
    assert ags["Acumulado_anio_anterior"] == 2  # solo severidad 0
    assert ags["Anio"] == 2019
    assert ags["Semana"] == "45"
    zac = df[df["Entidad"] == "Zacatecas"].iloc[0]
    assert zac["Acumulado_hombres"] == 13  # 10 + 2 + 1
    assert zac["Acumulado_mujeres"] == 15  # 12 + 3 + 0


def test_reshape_rechaza_conteo_de_columnas_incorrecto() -> None:
    bad = pd.DataFrame([["Aguascalientes", 1, 2, 3]])  # 3 cols de datos, no 10
    with pytest.raises(ValueError, match="10 columnas"):
        reshape_dengue_hist(bad, year=2019, week=10)


def test_total_discrepancy_cero_cuando_cuadra() -> None:
    tabla = _tabla_historica()
    # Suma por columna de datos (1..10): Sem0,H0,M0,prev0,Sem1,H1,M1,Sem2,H2,M2
    # AGS:  4,4,8,2, 1,1,0, 0,0,0   ZAC: 5,10,12,7, 2,2,3, 1,1,0
    total = "TOTAL 9 14 20 9 3 3 3 1 1 0"
    assert total_discrepancy_hist(tabla, total) == 0


def test_total_discrepancy_none_sin_renglon_total() -> None:
    assert total_discrepancy_hist(_tabla_historica(), "no hay total aqui") is None


def test_n_data_cols_hist_es_10() -> None:
    assert N_DATA_COLS_HIST == 10
