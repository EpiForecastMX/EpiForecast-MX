"""La portada (``hero_series.json``) sale de esta ronda: modelo nacional, corte y sin métricas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.build_hero_series import PADECIMIENTOS, construye

pytestmark = pytest.mark.unit


def _zoom(motor: str) -> dict:
    d = ["2026-08-24", "2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21"]
    return {
        "motor": motor,
        "intervalo_disponible": True,
        "corte_modelo": {"anio": 2026, "semana": 37},
        "last_real": "2026-09-14",
        "d": d,
        "r": [1, 2, 3, 4, None],
        "y": [9, 9, 5, 6, 7],
        "lo": [8, 8, 4, 5, 6],
        "hi": [10, 10, 6, 7, 8],
    }


MOTOR = {
    "Depresion": "Ensemble",
    "Parkinson": "Prophet",
    "Alzheimer": "Prophet",
    "Dengue": "DeepAR",
}
CASOS = {"Depresion": 160999, "Parkinson": 7391, "Alzheimer": 1915, "Dengue": 8811}


def _entradas(tmp_path: Path) -> tuple[Path, dict]:
    neuro = {c: _zoom(MOTOR[p]) for p, *_r, c in PADECIMIENTOS if p != "Dengue"}
    dengue = {PADECIMIENTOS[-1][-1]: _zoom("DeepAR")}
    (tmp_path / "zoom_data_neuro.json").write_text(json.dumps(neuro), "utf-8")
    (tmp_path / "zoom_data_dengue.json").write_text(json.dumps(dengue), "utf-8")
    kb = {
        "seguimiento_post_corte": {
            "corte": {"etiqueta": "2026-W37"},
            "ultima_semana_observada": {"etiqueta": "2026-W39"},
        },
        "weekly_comparison": {p: {"pronostico_52_pasos": v} for p, v in CASOS.items()},
        "prod_models": [
            {
                "padecimiento": p,
                "entidad": "Nacional",
                "sexo": "general",
                "modelo_produccion": MOTOR[p],
            }
            for p in ("Depresion", "Parkinson", "Alzheimer")
        ],
        "stats": {
            "por_pad": {
                p: {"por_sexo": {"general": {"casos_nacional": CASOS[p]}}}
                for p in ("Depresion", "Parkinson", "Alzheimer")
            }
        },
        "dengue": {"motor_nacional": "DeepAR", "casos_futuro_nacional_52sem": 8811},
    }
    return tmp_path, kb


def test_el_hero_es_el_modelo_nacional_desde_el_corte_y_sin_metricas(tmp_path: Path) -> None:
    rep, kb = _entradas(tmp_path)
    hero = construye(rep, kb, "2026-10-14")
    assert (hero["corte"], hero["ultima_observada"]) == ("2026-W37", "2026-W39")
    dep = hero["series"][0]
    assert (dep["label"], dep["motor"], dep["casos"]) == ("Depresión", "Ensemble", 160999)
    # 2026-08-31 es el ds del corte W37: hasta ahí no hay línea del modelo (sería ajuste).
    assert dep["y"] == [None, None, 5, 6, 7] and dep["hi"][:2] == [None, None]
    assert "smape" not in json.dumps(hero) and len(hero["series"]) == 4


def test_falla_si_el_total_no_es_el_de_la_tabla_semanal_o_cambia_el_motor(tmp_path: Path) -> None:
    rep, kb = _entradas(tmp_path)
    kb["dengue"]["casos_futuro_nacional_52sem"] = 8350  # los 50 pasos posteriores a W39
    with pytest.raises(SystemExit, match="52 pasos"):
        construye(rep, kb, "x")
    rep, kb = _entradas(tmp_path)
    kb["prod_models"][0]["modelo_produccion"] = "DeepAR"
    with pytest.raises(SystemExit, match="motor"):
        construye(rep, kb, "x")
