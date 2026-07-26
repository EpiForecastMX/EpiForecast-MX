"""C7.4 — gate prospectivo congelado: el congelamiento y la regla de "no cuenta".

Lo que se protege:
 - congelar es reproducible y sensible: cambiar cualquier componente mueve el digest del gate;
 - el control es determinista y es de verdad lag-52, no un placeholder;
 - una semana ausente o PARCIAL no cuenta, y jamás se convierte en cero;
 - con menos de cuatro semanas válidas el veredicto es INCOMPLETE, nunca un PASS optimista.
"""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.data.epi_calendar import shift
from epiforecast.publication.prospective import (
    ACCEPTANCE_RULE,
    GATE_WEEKS,
    VERDICT_INCOMPLETE,
    VERDICT_PASS,
    FrozenGate,
    available_weeks,
    build_control,
    evaluate,
    frame_digest,
)
from epiforecast.runner.release_reproduce import horizon_periods

ORIGEN = (2026, 26)
SERIES = [("01", "hombres"), ("01", "mujeres")]


def _historia(hasta=ORIGEN, extra=()):
    """Historia sintética contigua desde 2024-W01 hasta `hasta`, más periodos extra."""
    periodos = []
    y, w = 2024, 1
    while (y, w) <= hasta:
        periodos.append((y, w))
        w += 1
        if w > 52:
            y, w = y + 1, 1
    return {s: {p: float(10 + p[1]) for p in [*periodos, *extra]} for s in SERIES}


def _gate(**cambios):
    base = {
        "disease_id": "x",
        "release_id": "x_release_abc123456789",
        "origin": ORIGEN,
        "horizon": 52,
        "target_weeks": tuple(horizon_periods(ORIGEN, GATE_WEEKS)),
        "candidate_digest": "a" * 64,
        "control_digest": "b" * 64,
        "dataset_digest": "c" * 64,
        "rule": dict(ACCEPTANCE_RULE),
    }
    base.update(cambios)
    return FrozenGate(**base)


# ── Congelar ──────────────────────────────────────────────────────────────────────────────────
def test_el_gate_congela_las_cuatro_semanas_siguientes_al_origen():
    assert _gate().target_weeks == ((2026, 27), (2026, 28), (2026, 29), (2026, 30))


def test_el_digest_del_gate_es_reproducible():
    assert _gate().digest() == _gate().digest()


@pytest.mark.parametrize(
    "cambio",
    [
        {"candidate_digest": "0" * 64},
        {"control_digest": "0" * 64},
        {"dataset_digest": "0" * 64},
        {"origin": (2026, 25)},
        {"rule": {**ACCEPTANCE_RULE, "smape_base": 99.0}},
    ],
)
def test_mover_cualquier_componente_mueve_el_digest_del_gate(cambio):
    """Aflojar el umbral después de ver resultados tendría que ser detectable. Lo es."""
    assert _gate(**cambio).digest() != _gate().digest()


def test_la_regla_de_aceptacion_viaja_dentro_del_congelado():
    payload = _gate().payload()
    assert payload["acceptance_rule_max_degradation_pct"] == {
        "smape_base": 5.0,
        "smape_national_general": 10.0,
        "smape_products": 5.0,
    }
    assert payload["control_engine"] == "seasonal_naive_lag52"


# ── El control ────────────────────────────────────────────────────────────────────────────────
def test_el_control_es_determinista():
    hist = _historia()
    assert frame_digest(build_control(hist, ORIGEN, 4)) == frame_digest(
        build_control(hist, ORIGEN, 4)
    )


def test_el_control_es_de_verdad_lag_52_y_no_un_relleno():
    hist = {SERIES[0]: {}}
    y, w = 2025, 1
    while (y, w) <= ORIGEN:
        hist[SERIES[0]][(y, w)] = float(w * 100)
        w += 1
        if w > 52:
            y, w = y + 1, 1
    control = build_control(hist, ORIGEN, 2)
    # El salto es de 52 SEMANAS, no "la misma semana del año pasado": 2025 es un año MMWR de 53
    # semanas, así que 2026-W27 se apoya en 2025-W28. Escribir aquí `(2025, 27)` daría un test
    # verde-por-accidente en años de 52 semanas y rojo en los de 53.
    origen_del_salto = shift(2026, 27, -52)
    assert origen_del_salto == (2025, 28), "el calendario MMWR de 2025 tiene 53 semanas"
    fila = control[(control.epi_year == 2026) & (control.epi_week == 27)]
    assert float(fila["y_pred_cases"].iloc[0]) == hist[SERIES[0]][origen_del_salto]


def test_el_control_falla_si_la_historia_no_cubre_el_lag():
    from epiforecast.runner.artifact_identity import ArtifactValidationError

    with pytest.raises(ArtifactValidationError, match="lag-52"):
        build_control({SERIES[0]: {(2026, 26): 1.0}}, ORIGEN, 1)


# ── "No cuenta" nunca es cero ─────────────────────────────────────────────────────────────────
def test_una_semana_ausente_no_cuenta_y_no_se_vuelve_cero():
    hist = _historia()
    assert available_weeks(hist, tuple(horizon_periods(ORIGEN, 4))) == []
    assert all((2026, 27) not in serie for serie in hist.values())


def test_una_semana_parcial_no_cuenta():
    """Presente en una serie y ausente en otra: la semana entera se descarta."""
    hist = _historia()
    hist[SERIES[0]][(2026, 27)] = 5.0  # sólo una de las dos series
    assert available_weeks(hist, tuple(horizon_periods(ORIGEN, 4))) == []


def test_una_semana_completa_si_cuenta():
    hist = _historia()
    for serie in hist.values():
        serie[(2026, 27)] = 5.0
    assert available_weeks(hist, tuple(horizon_periods(ORIGEN, 4))) == [(2026, 27)]


# ── Veredicto ─────────────────────────────────────────────────────────────────────────────────
def _forecast(valor: float, semanas):
    return pd.DataFrame(
        [
            {"geography_id": g, "sex": s, "epi_year": y, "epi_week": w, "y_pred_cases": valor}
            for (g, s) in SERIES
            for (y, w) in semanas
        ]
    )


@pytest.mark.parametrize("n_semanas", [0, 1, 2, 3])
def test_con_menos_de_cuatro_semanas_el_veredicto_es_incomplete(n_semanas):
    hist = _historia()
    semanas = horizon_periods(ORIGEN, 4)[:n_semanas]
    for serie in hist.values():
        for p in semanas:
            serie[p] = 5.0
    res = evaluate(_gate(), _forecast(5.0, semanas), _forecast(7.0, semanas), hist)
    assert res["verdict"] == VERDICT_INCOMPLETE
    assert res["weeks_available"] == n_semanas
    assert res["weeks_required"] == GATE_WEEKS


def test_con_las_cuatro_semanas_completas_se_evalua_y_se_reporta_por_semana():
    hist = _historia()
    semanas = horizon_periods(ORIGEN, 4)
    for serie in hist.values():
        for p in semanas:
            serie[p] = 5.0
    res = evaluate(_gate(), _forecast(5.0, semanas), _forecast(7.0, semanas), hist)
    assert res["verdict"] == VERDICT_PASS
    assert len(res["per_week"]) == GATE_WEEKS
    # El candidato clava la verdad y el control no: el detalle por semana lo refleja.
    assert all(w["smape_candidate"] == 0.0 for w in res["per_week"])
    assert all(w["smape_control"] > 0.0 for w in res["per_week"])


def test_el_veredicto_lleva_el_digest_del_gate_congelado():
    gate = _gate()
    res = evaluate(gate, _forecast(1.0, []), _forecast(1.0, []), _historia())
    assert res["gate_digest"] == gate.digest()
