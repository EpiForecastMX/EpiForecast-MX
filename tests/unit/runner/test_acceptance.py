"""F2/C5.2 — gate de aceptación 2025: veredicto global, fallback y candados del stage test."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from epiforecast.runner import acceptance
from epiforecast.runner import orchestrator as orch
from epiforecast.runner.policy import load_policy

_RULE = acceptance.AcceptanceRule.from_policy(load_policy("rolling_cv_v1"))
_CONTROL = {"smape_bases": 100.0, "smape_all": 100.0, "smape_nacional_general": 100.0}


def _sel(engine: str = "ets_add_damped_log1p") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"geography_id": f"{i:02d}", "sex": sexo, "selected_engine": engine}
            for i in range(1, 33)
            for sexo in ("hombres", "mujeres")
        ]
    )


def test_regla_declarada_en_la_politica():
    assert _RULE.control_engine == "seasonal_naive_lag52"
    assert _RULE.fallback_engine == "seasonal_naive_lag52"
    assert _RULE.max_worse_pct == {
        "smape_bases": 5.0,
        "smape_all": 5.0,
        "smape_nacional_general": 10.0,
    }


def test_portafolio_mejor_que_el_control_pasa():
    portfolio = {"smape_bases": 80.0, "smape_all": 80.0, "smape_nacional_general": 80.0}
    verdict = acceptance.evaluate_gate(portfolio, _CONTROL, _RULE)
    assert verdict["accepted"]
    assert all(c["worse_pct"] == pytest.approx(-20.0) for c in verdict["checks"])


def test_umbral_exacto_por_ambito():
    # bases/all admiten hasta +5%; nacional General hasta +10%.
    justo = {"smape_bases": 105.0, "smape_all": 105.0, "smape_nacional_general": 110.0}
    assert acceptance.evaluate_gate(justo, _CONTROL, _RULE)["accepted"]
    pasado = {"smape_bases": 105.01, "smape_all": 105.0, "smape_nacional_general": 110.0}
    verdict = acceptance.evaluate_gate(pasado, _CONTROL, _RULE)
    assert not verdict["accepted"]
    assert [c["passed"] for c in verdict["checks"]] == [False, True, True]


def test_un_solo_ambito_reprobado_rechaza_todo():
    # El veredicto es GLOBAL: no se salva parte del portafolio.
    parcial = {"smape_bases": 50.0, "smape_all": 50.0, "smape_nacional_general": 111.0}
    assert not acceptance.evaluate_gate(parcial, _CONTROL, _RULE)["accepted"]


def test_seleccion_final_conserva_el_mapa_si_pasa():
    verdict = {"accepted": True, "checks": []}
    final = acceptance.final_selection(_sel(), verdict, _RULE)
    assert set(final["selected_engine"]) == {"ets_add_damped_log1p"}
    assert set(final["source"]) == {"development_selection"} and len(final) == 64


def test_seleccion_final_cae_al_fallback_si_falla():
    verdict = {"accepted": False, "checks": []}
    final = acceptance.final_selection(_sel(), verdict, _RULE)
    assert set(final["selected_engine"]) == {_RULE.fallback_engine}  # las 64, sin excepciones
    assert set(final["source"]) == {"acceptance_fallback"}


def test_evidencia_sellada_y_verificable(tmp_path):
    verdict = {"accepted": True, "checks": []}
    final = acceptance.final_selection(_sel(), verdict, _RULE)
    arts = acceptance.write_acceptance(
        tmp_path, pd.DataFrame([{"engine": "portfolio"}]), final, "# reporte\n", verdict
    )
    assert len(arts) == 4
    cargada, payload = acceptance.load_accepted(tmp_path)
    assert len(cargada) == 64 and payload["accepted"] is True

    (tmp_path / "final_selection.csv").write_text("geography_id,sex\n", encoding="utf-8")
    with pytest.raises(acceptance.AcceptanceError, match="alterado"):
        acceptance.load_accepted(tmp_path)


def test_evidencia_exige_acceptance_json(tmp_path):
    with pytest.raises(acceptance.AcceptanceError, match="no hay acceptance.json"):
        acceptance.load_accepted(tmp_path)
    (tmp_path / "acceptance.json").write_text(json.dumps({"schema": "otro"}), encoding="utf-8")
    with pytest.raises(acceptance.AcceptanceError, match="schema"):
        acceptance.load_accepted(tmp_path)


def test_stage_test_exige_seleccion_congelada():
    # Falla ANTES de materializar el dataset: un intento inválido no llega ni a tocar datos.
    with pytest.raises(orch.RunnerError, match="requiere --selection"):
        orch.run_command("Obesidad", "benchmark", stage="test")


def test_tune_con_stage_test_esta_prohibido():
    with pytest.raises(orch.RunnerError, match="solo existe para benchmark"):
        orch.run_command("Obesidad", "tune", stage="test", selection_run_id="cualquiera")
