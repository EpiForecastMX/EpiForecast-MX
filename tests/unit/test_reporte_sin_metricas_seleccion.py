"""Reporte de resultados (ronda W37): sin ranking ni métricas de la ventana de selección W28–W37.

Las métricas por serie de esta ronda son el error con el que se eligió cada motor: no llegan a la
página, ni visibles ni dentro del JSON incrustado. El backtest sellado de Dengue se conserva.
"""

from __future__ import annotations

import json
import re

import pytest
from scripts import genera_reporte as gr

from epiforecast.publication.metricas_seleccion import ROTULO, claves_metrica

pytestmark = pytest.mark.unit


def _stats() -> dict:
    pad = {
        "padecimiento": "Depresión",
        "total": 111,
        "estatales": 96,
        "nacionales": 3,
        "regionales": 12,
        "mase": 0.81,
        "smape": 40.0,
        "insuficientes": 0,
        "fallback": 0,
    }
    return {
        "total_modelos": 333,
        "fecha": "13/10/2026",
        "mase_global": 0.8,
        "smape_global": 41.0,
        "modelos_excelentes": 120,
        "dist_neuro": {"Ensemble": 109, "Stacking": 107, "Prophet": 78, "DeepAR": 39},
        "por_padecimiento": [pad],
        "ranking": [{"entidad": "Colima", "mase": 0.5, "smape": 20.0}],
        "top10": [{"label": "x", "mase": 0.1}],
        "mase_histo": [{"padecimiento": "Depresión", "bins": [1, 2]}],
        "por_sexo": [{"padecimiento": "Depresión", "mase": 0.7}],
    }


def _dengue() -> dict:
    return {
        "n_series": 99,
        "dist_all": {"DeepAR": 53, "Prophet": 46},
        "dist_general": {"DeepAR": 18, "Prophet": 15},
        "nacional_motor": "DeepAR",
        "nacional_smape": 23.1,
        "smape_ganador_median": 60.0,
        "backtest": gr.DENGUE_BACKTEST,
        "motor_table": [],
        "ranking": [
            {"entidad": "Nacional", "motor": "DeepAR", "smape": 23.1, "mae": 40.0, "casos": 9}
        ],
    }


def test_datos_publicables_sin_metricas_de_seleccion() -> None:
    d = gr.datos_publicables(_stats(), _dengue())
    assert claves_metrica(_stats())  # control: la entrada sí las trae
    assert claves_metrica(d) == []
    for k in ("ranking", "top10", "mase_histo", "por_sexo", "modelos_excelentes"):
        assert k not in d
    assert d["dengue"]["ranking"] == [{"entidad": "Nacional", "motor": "DeepAR", "casos": 9}]
    assert d["dengue"]["backtest"] == {"prophet": 102, "prophet_enso": 76, "nbglm": 52}
    assert d["metricas_seleccion"]["rotulo"] == ROTULO


def test_la_pagina_no_incrusta_ni_muestra_metricas_de_seleccion() -> None:
    html = gr.build_html(_stats(), _dengue())
    datos = json.loads(re.search(r"const D = (\{.*?\});\n", html, re.S).group(1))
    assert claves_metrica(datos) == []
    assert "__" not in re.sub(r"__[a-z]", "", html)  # sin marcadores de plantilla sin sustituir
    assert ROTULO in html
    for fuera in (
        'id="ranking"',
        'id="topbottom"',
        'id="calidad"',
        "maseCompareChart",
        "MASE Medio",
    ):
        assert fuera not in html
    assert 'id="metricas"' in html and 'id="cobertura"' in html
