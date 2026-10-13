"""Ronda W37: las métricas de la ventana de selección salen del knowledge público.

Quedan en la evidencia de revisión, rotuladas «diagnóstico de selección W28–W37; no evaluación
independiente». El glosario y los rankings de casos (no de error) se conservan.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts import build_web_knowledge as bwk

from epiforecast.publication.metricas_seleccion import (
    CLAVE_DECLARACION,
    ROTULO,
    claves_metrica,
    separa_metricas,
)

pytestmark = pytest.mark.unit


def _knowledge() -> dict:
    return {
        "_version": "1.0",
        "smape_global": 50.0,
        "stats": {
            "total_modelos": 333,
            "smape_prod_median": 41.2,
            "mase_prod_mean": 0.8,
            "top5_smape": [{"entidad": "Colima", "smape": 3.1}],
            "precision_historica_mean": 97.0,
            "por_pad": {
                "Depresion": {
                    "n": 111,
                    "smape_prod_mean": 30.0,
                    "por_sexo": {"general": {"mase_prod_median": 0.7, "n": 37}},
                }
            },
            "por_motor": {"DeepAR": {"n": 39, "rmse_mean": 4.0, "mae_median": 2.0}},
        },
        "prod_models": [
            {
                "padecimiento": "Depresion",
                "entidad": "Colima",
                "modelo_produccion": "Prophet",
                "smape_prod": 12.0,
                "mase_prod": 0.5,
            },
            {"padecimiento": "Parkinson", "entidad": "Jalisco", "modelo_produccion": "Ensemble"},
        ],
        "boletin": {"ranking_entidades": [{"entidad": "Jalisco", "casos": 10}]},
        "dengue": {
            "modelo_productivo": "DeepAR",
            "smape_nacional": 23.14,
            "motores_productivos": ["DeepAR", "Prophet"],
        },
        "rendimiento_2026": {
            "por_pad": {"Depresion": {"motores": {"Prophet": {"smape_med": 20.0}}}}
        },
        "definiciones": {"SMAPE": "Error porcentual absoluto simétrico", "MASE": "Error escalado"},
    }


def test_no_queda_ninguna_metrica_publica() -> None:
    k = _knowledge()
    assert claves_metrica(k)  # control: el knowledge de entrada sí las trae
    publico, evidencia = separa_metricas(k)
    assert claves_metrica(publico) == []
    assert "rendimiento_2026" not in publico
    assert "smape_nacional" not in publico["dengue"]
    assert publico["prod_models"][0] == {
        "padecimiento": "Depresion",
        "entidad": "Colima",
        "modelo_produccion": "Prophet",
    }
    assert publico["stats"]["por_pad"]["Depresion"] == {
        "n": 111,
        "por_sexo": {"general": {"n": 37}},
    }


def test_se_conserva_lo_que_no_es_metrica() -> None:
    publico, _ = separa_metricas(_knowledge())
    assert publico["definiciones"] == _knowledge()["definiciones"]
    assert publico["boletin"] == _knowledge()["boletin"]
    assert publico["dengue"]["motores_productivos"] == ["DeepAR", "Prophet"]
    assert publico["stats"]["total_modelos"] == 333


def test_declara_la_retirada_y_guarda_la_evidencia_rotulada() -> None:
    publico, evidencia = separa_metricas(_knowledge())
    dec = publico[CLAVE_DECLARACION]
    assert dec["publicadas"] is False and dec["rotulo"] == ROTULO
    assert ROTULO == "diagnóstico de selección W28–W37; no evaluación independiente"
    assert evidencia["rotulo"] == ROTULO
    r = evidencia["retirado"]
    assert r["dengue"] == {"smape_nacional": 23.14}
    assert r["smape_global"] == 50.0  # también en el primer nivel
    assert r["stats"]["smape_prod_median"] == 41.2
    assert r["rendimiento_2026"]["por_pad"]["Depresion"]["motores"]["Prophet"]["smape_med"] == 20.0
    assert (
        r["prod_models"][0] == {"smape_prod": 12.0, "mase_prod": 0.5}
        and r["prod_models"][1] is None
    )


def test_el_generador_escribe_evidencia_aparte(tmp_path: Path) -> None:
    _, evidencia = separa_metricas(_knowledge())
    destino = tmp_path / "rev" / "metricas.json"
    bwk.escribe_evidencia(evidencia, destino)
    assert json.loads(destino.read_text(encoding="utf-8"))["rotulo"] == ROTULO
