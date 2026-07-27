"""C7.6-STATUS-A.1 — la regla 5/5/10 se aplica de verdad, y las semanas se reemplazan.

Hasta A.1 `evaluate()` devolvía PASS con sólo tener cuatro semanas, sin comparar contra el control
(R76-P0-1): el FAIL documentado no podía ocurrir nunca. Y `available_weeks()` sólo miraba las cuatro
semanas programadas, así que un boletín incompleto dejaba el gate atascado para siempre (R76-P0-3).

Todo es sintético y usa el catálogo geográfico TRACKEADO: no hace falta `runs/` ni el release.
"""

# ruff: noqa: N802 — los nombres llevan FAIL/PASS/INCOMPLETE en mayúscula a propósito: son los
# veredictos del contrato, y leerlos en el nombre del test es más útil que la convención.

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.publication.prospective import (
    ACCEPTANCE_RULE,
    GATE_WEEKS,
    SCOPE_BASE,
    SCOPE_NATIONAL,
    SCOPE_PRODUCTS,
    VERDICT_FAIL,
    VERDICT_INCOMPLETE,
    VERDICT_PASS,
    WEEK_MISSING,
    WEEK_PARTIAL,
    FrozenGate,
    evaluate,
    select_weeks,
    week_state,
)
from epiforecast.runner.release_reproduce import horizon_periods

ORIGEN = (2026, 26)
CATALOGO = load_geo_catalog()
SERIES = [(e.cve_ent, s) for e in CATALOGO.entities for s in ("hombres", "mujeres")]
VENTANA = tuple(horizon_periods(ORIGEN, 52))
OBJETIVO = tuple(horizon_periods(ORIGEN, GATE_WEEKS))


def _gate(**cambios) -> FrozenGate:
    base = {
        "disease_id": "x",
        "release_id": "x_release_abc123456789",
        "origin": ORIGEN,
        "horizon": 52,
        "target_weeks": OBJETIVO,
        "candidate_digest": "a" * 64,
        "control_digest": "b" * 64,
        "dataset_digest": "c" * 64,
        "rule": dict(ACCEPTANCE_RULE),
    }
    base.update(cambios)
    return FrozenGate(**base)


def _historia(semanas=OBJETIVO, valor=100.0, faltantes=(), parciales=()):
    hist = {}
    for i, serie in enumerate(SERIES):
        hist[serie] = {}
        for p in semanas:
            if p in faltantes:
                continue
            if p in parciales and i == 0:  # a UNA serie le falta esa semana → parcial
                continue
            hist[serie][p] = valor
    return hist


def _pred(semanas, funcion):
    """Frame de predicción base: `funcion(indice_serie, periodo)` da el valor."""
    return pd.DataFrame(
        [
            {
                "geography_id": geo,
                "sex": sexo,
                "epi_year": p[0],
                "epi_week": p[1],
                "y_pred_cases": funcion(i, p),
            }
            for i, (geo, sexo) in enumerate(SERIES)
            for p in semanas
        ]
    )


def _evaluar(hist, cand, ctrl, gate=None):
    return evaluate(gate or _gate(), cand, ctrl, hist, catalog=CATALOGO)


# ── La regla, de verdad ───────────────────────────────────────────────────────────────────────
def test_candidato_catastrofico_con_control_perfecto_es_FAIL():
    hist = _historia()
    r = _evaluar(hist, _pred(VENTANA, lambda i, p: 100_000.0), _pred(VENTANA, lambda i, p: 100.0))
    assert r["verdict"] == VERDICT_FAIL
    assert r["weeks_available"] == GATE_WEEKS
    for scope in (SCOPE_BASE, SCOPE_PRODUCTS, SCOPE_NATIONAL):
        assert r["scopes"][scope]["passes"] is False
        assert r["scopes"][scope]["smape_candidate"] > r["scopes"][scope]["smape_control"]


def test_candidato_igual_al_control_es_PASS():
    hist = _historia()
    r = _evaluar(hist, _pred(VENTANA, lambda i, p: 100.0), _pred(VENTANA, lambda i, p: 100.0))
    assert r["verdict"] == VERDICT_PASS
    assert all(r["scopes"][s]["passes"] for s in (SCOPE_BASE, SCOPE_PRODUCTS, SCOPE_NATIONAL))


def test_los_tres_ambitos_se_evaluan_por_separado():
    """Errores que se cancelan al agregar: las bases fallan y el nacional no se entera.

    Es la razón de tener tres ámbitos: un sesgo alterno por sexo desaparece en el total nacional.
    """
    hist = _historia()
    cand = _pred(VENTANA, lambda i, p: 100.0 * (3.0 if i % 2 else 1 / 3.0))
    ctrl = _pred(VENTANA, lambda i, p: 100.0)
    r = _evaluar(hist, cand, ctrl)
    assert r["scopes"][SCOPE_BASE]["smape_candidate"] > 0.0
    assert (
        r["scopes"][SCOPE_NATIONAL]["smape_candidate"] < r["scopes"][SCOPE_BASE]["smape_candidate"]
    )
    assert r["scopes"][SCOPE_BASE]["passes"] is False
    assert r["verdict"] == VERDICT_FAIL  # basta con que falle UN ámbito


def test_el_umbral_del_gate_es_el_que_manda():
    """Con el mismo error, aflojar el umbral cambiaría el veredicto: por eso está congelado."""
    hist = _historia()
    cand = _pred(VENTANA, lambda i, p: 104.0)
    ctrl = _pred(VENTANA, lambda i, p: 103.0)
    estricto = _evaluar(hist, cand, ctrl)
    laxo = _evaluar(hist, cand, ctrl, gate=_gate(rule={k: 500.0 for k in ACCEPTANCE_RULE}))
    assert estricto["scopes"][SCOPE_BASE]["max_degradation_pct"] == ACCEPTANCE_RULE[SCOPE_BASE]
    assert laxo["verdict"] == VERDICT_PASS
    assert laxo["scopes"][SCOPE_BASE]["degradation_pct"] == pytest.approx(
        estricto["scopes"][SCOPE_BASE]["degradation_pct"]
    )


def test_control_perfecto_y_candidato_imperfecto_no_produce_inf_silencioso():
    hist = _historia()
    r = _evaluar(hist, _pred(VENTANA, lambda i, p: 101.0), _pred(VENTANA, lambda i, p: 100.0))
    deg = r["scopes"][SCOPE_BASE]["degradation_pct"]
    assert deg == float("inf")  # control=0 y candidato>0 → el ámbito falla, sin dividir
    assert r["verdict"] == VERDICT_FAIL


def test_las_metricas_extra_se_reportan_pero_no_deciden():
    hist = _historia()
    r = _evaluar(hist, _pred(VENTANA, lambda i, p: 100.0), _pred(VENTANA, lambda i, p: 100.0))
    for scope in (SCOPE_BASE, SCOPE_PRODUCTS, SCOPE_NATIONAL):
        assert set(r["metrics"][scope]) >= {"smape", "mae", "rmse", "wape", "bias", "mase"}
    assert r["verdict"] == VERDICT_PASS  # decidido por sMAPE contra el control, no por MAE


# ── Semanas: reemplazo, parciales y ausentes ──────────────────────────────────────────────────
def test_una_semana_ausente_se_reemplaza_por_la_siguiente_completa():
    faltante = OBJETIVO[1]
    hist = _historia(semanas=VENTANA[:8], faltantes=(faltante,))
    seleccion = select_weeks(hist, _gate())
    assert faltante not in seleccion.completed
    assert len(seleccion.completed) == GATE_WEEKS
    assert seleccion.completed[-1] == VENTANA[4]  # entra la siguiente válida
    assert (faltante, WEEK_MISSING) in seleccion.skipped
    assert seleccion.scheduled == OBJETIVO  # lo programado no se reescribe


def test_una_semana_parcial_no_cuenta_ni_se_vuelve_cero():
    parcial = OBJETIVO[2]
    hist = _historia(semanas=VENTANA[:8], parciales=(parcial,))
    assert week_state(hist, parcial) == WEEK_PARTIAL
    seleccion = select_weeks(hist, _gate())
    assert parcial not in seleccion.completed
    assert (parcial, WEEK_PARTIAL) in seleccion.skipped
    # Y la verdad de esa semana NO se completó con ceros para la serie que faltaba.
    assert all(parcial not in serie or serie[parcial] == 100.0 for serie in hist.values())


def test_sin_cuatro_semanas_completas_el_veredicto_es_INCOMPLETE():
    hist = _historia(semanas=OBJETIVO[:2])
    r = _evaluar(hist, _pred(VENTANA, lambda i, p: 100.0), _pred(VENTANA, lambda i, p: 100.0))
    assert r["verdict"] == VERDICT_INCOMPLETE
    assert r["weeks_available"] == 2
    assert r["scopes"], "aun incompleto se reporta lo medido hasta ahora"


def test_sin_ninguna_semana_el_veredicto_es_INCOMPLETE_y_no_hay_ambitos():
    hist = _historia(semanas=())
    r = _evaluar(hist, _pred(VENTANA, lambda i, p: 100.0), _pred(VENTANA, lambda i, p: 100.0))
    assert (r["verdict"], r["weeks_available"], r["scopes"]) == (VERDICT_INCOMPLETE, 0, {})
    assert r["selection"]["completed_weeks"] == []


def test_la_seleccion_no_pasa_del_horizonte_congelado():
    """Sólo se miran semanas DENTRO del horizonte del release: fuera de él no hay pronóstico."""
    hist = _historia(semanas=(*VENTANA, (2027, 30)))
    seleccion = select_weeks(hist, _gate(horizon=2))
    assert all(p in VENTANA[:2] for p in seleccion.completed)
