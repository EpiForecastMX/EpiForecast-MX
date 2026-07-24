"""F1/C1 — reconciliación pura: mayor residuo + escenarios del contrato (con ajustes C1-2c)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from epiforecast.data import epi_reconcile as rc

EXP1 = {"01"}
EXP2 = {"01", "02"}


# ── largest_remainder_split ──
@pytest.mark.parametrize(
    "total,prop", [(10, 0.6), (11, 0.5), (7, 0.375), (100, 0.333), (1, 0.9), (5, 0.0), (5, 1.0)]
)
def test_split_preserva_suma(total, prop):
    h, m = rc.largest_remainder_split(total, prop)
    assert h + m == total and h >= 0 and m >= 0


def test_split_cero_y_empate():
    assert rc.largest_remainder_split(0, 0.7) == (0, 0)
    assert rc.largest_remainder_split(11, 0.5) == (6, 5)  # empate → hombres


def test_split_extremos():
    assert rc.largest_remainder_split(5, 0.0) == (0, 5)
    assert rc.largest_remainder_split(5, 1.0) == (5, 0)


def test_round_half_up():
    assert rc._round_half_up(24.5) == 25
    assert rc._round_half_up(25.0) == 25
    assert rc._round_half_up(25.4) == 25


# ── helper para construir prep sintético ──
def _row(cve, ey, ew, casos, ah, am, sy=None, swk=None):
    return {
        "cve_ent": cve,
        "source_year": sy if sy is not None else ey,
        "source_week": swk if swk is not None else ew,
        "epi_year": ey,
        "epi_week": ew,
        "period_start": date(ey, 1, 1),
        "ds": date(ey, 1, 2),
        "casos_source": casos,
        "acum_h": ah,
        "acum_m": am,
    }


def _run(rows, expected):
    return rc.reconcile_state(pd.DataFrame(rows), expected)


def _get(state, cve, ey, ew):
    d = state[(state.cve_ent == cve) & (state.epi_year == ey) & (state.epi_week == ew)]
    assert len(d) == 1
    return d.iloc[0]


# ── split por delta + mismatch ──
def test_delta_split_basico():
    st = _run([_row("01", 2020, 1, 10, 6, 4), _row("01", 2020, 2, 10, 12, 8)], EXP1)
    r1 = _get(st, "01", 2020, 1)
    assert (r1.y_hombres, r1.y_mujeres) == (6, 4)
    assert r1.observed and abs(r1.sex_prop_applied - 0.6) < 1e-9 and r1.quality_flags == ""


def test_sex_delta_total_mismatch():
    r = _get(_run([_row("01", 2020, 1, 8, 6, 4)], EXP1), "01", 2020, 1)
    assert "sex_delta_total_mismatch" in r.quality_flags
    assert r.sex_delta_total == 10 and r.sex_delta_residual == 2
    assert (r.y_hombres, r.y_mujeres) == (5, 3) and r.y_hombres + r.y_mujeres == 8


# ── source_missing: política de 4 condiciones vs cero aislado ──
def test_source_missing_vs_cero_aislado():
    rows = [
        _row("01", 2020, 1, 10, 6, 4),
        _row("02", 2020, 1, 10, 5, 5),
        _row("01", 2020, 2, 0, 6, 4),  # cero AISLADO (02 no cero) → nacional>0 → real
        _row("02", 2020, 2, 8, 9, 9),
        _row("01", 2020, 3, 0, 0, 0),  # ambos cero + colapso acumulado → source_missing
        _row("02", 2020, 3, 0, 0, 0),
    ]
    st = _run(rows, EXP2)
    r_iso = _get(st, "01", 2020, 2)
    assert r_iso.observed and r_iso.total_reconciled == 0
    assert "source_missing" not in r_iso.quality_flags
    for cve in ("01", "02"):
        r_sm = _get(st, cve, 2020, 3)
        assert not r_sm.observed and "source_missing" in r_sm.quality_flags


def test_cero_nacional_sin_colapso_no_es_source_missing():
    # Baja incidencia (tipo F50): total nacional 0 SIN colapso de acumulados → NO source_missing.
    rows = [
        _row("01", 2020, 1, 3, 3, 0),
        _row("02", 2020, 1, 3, 0, 3),
        _row("01", 2020, 2, 0, 3, 0),  # cero pero acumulado NO colapsa (sigue en 3,0)
        _row("02", 2020, 2, 0, 0, 3),
    ]
    st = _run(rows, EXP2)
    for cve in ("01", "02"):
        r = _get(st, cve, 2020, 2)
        assert r.observed and "source_missing" not in r.quality_flags  # cero real


# ── predecessor_snapshot_invalid tras colapso ──
def test_predecessor_invalid_tras_colapso():
    rows = [
        _row("01", 2020, 1, 10, 6, 4),
        _row("01", 2020, 2, 12, 12, 10),
        _row("01", 2020, 3, 0, 0, 0),  # colapso → source_missing
        _row("01", 2020, 4, 15, 20, 16),  # observado, baseline previo inválido
        _row("01", 2020, 5, 8, 24, 20),  # reanuda
    ]
    st = _run(rows, EXP1)
    assert "source_missing" in _get(st, "01", 2020, 3).quality_flags
    r4 = _get(st, "01", 2020, 4)
    assert "predecessor_snapshot_invalid" in r4.quality_flags and r4.observed
    assert "sex_fallback" in r4.quality_flags
    r5 = _get(st, "01", 2020, 5)
    assert "predecessor_snapshot_invalid" not in r5.quality_flags and pd.notna(r5.sex_prop_source)


# ── imputación causal por misma semana en años previos ──
def test_imputa_total_por_misma_semana_anios_previos():
    rows = [
        _row("01", 2018, 10, 20, 12, 8),
        _row("02", 2018, 10, 100, 60, 40),
        _row("01", 2019, 10, 30, 18, 12),
        _row("02", 2019, 10, 100, 120, 80),
        _row("01", 2020, 10, 0, 0, 0),  # colapso → source_missing → imputar
        _row("02", 2020, 10, 0, 0, 0),
    ]
    r = _get(_run(rows, EXP2), "01", 2020, 10)
    assert not r.observed and r.total_reconciled == 25  # mediana([20,30]) half-up
    assert "total_imputed" in r.quality_flags


# ── C1-2c: total entero finito no negativo ──
def test_casos_fraccionario_falla_gate():
    with pytest.raises(rc.ReconcileError):
        _run([_row("01", 2020, 1, 5.5, 6, 4)], EXP1)


def test_casos_negativo_imputado_nunca_negativo():
    rows = [
        _row("01", 2018, 5, 40, 24, 16),
        _row("01", 2019, 5, 50, 30, 20),
        _row("01", 2020, 5, -3, 6, 4),  # revisión negativa → imputar por misma semana
    ]
    r = _get(_run(rows, EXP1), "01", 2020, 5)
    assert not r.observed and "negative_source" in r.quality_flags
    assert r.total_source == -3 and r.total_reconciled == 45  # mediana([40,50])
    assert r.y_hombres >= 0 and r.y_mujeres >= 0 and r.y_hombres + r.y_mujeres == 45


# ── C1-2c: ventana literalmente de 13 periodos calendario ──
def test_fallback_sexual_ventana_13_periodos_calendario():
    # W01 aporta prop válida 0.9; W02.. tienen delta inválido (acum congelado) → fallback.
    rows = [_row("01", 2020, 1, 10, 9, 1)]  # prop 0.9 en el periodo 0
    for w in range(2, 17):  # W02..W16: acum congelado (9,1) → delta 0 → inválido
        rows.append(_row("01", 2020, w, 10, 9, 1))
    st = _run(rows, EXP1)
    r14 = _get(st, "01", 2020, 14)  # i=13: ventana [0,13) incluye el periodo 0 → usa 0.9
    assert abs(r14.sex_prop_applied - 0.9) < 1e-9
    assert "sex_fallback_state_13w" in r14.quality_flags
    r15 = _get(st, "01", 2020, 15)  # i=14: ventana [1,14) excluye el periodo 0 → ya no usa 0.9
    assert "sex_fallback_state_13w" not in r15.quality_flags
    assert r15.sex_prop_applied == 0.5 and "sex_fallback_half" in r15.quality_flags


# ── C1-2c: fallback nacional = periodo inmediatamente anterior (no acumulado) ──
def test_fallback_nacional_periodo_inmediatamente_anterior():
    rows = [
        # 02 aporta deltas válidos que CAMBIAN: W01 prop 0.8, W02/W03 prop 0.6.
        _row("02", 2020, 1, 10, 8, 2),
        _row("02", 2020, 2, 10, 14, 6),
        _row("02", 2020, 3, 10, 20, 10),
        # 01 nunca tiene delta válido (acum congelado en 0) → siempre fallback.
        _row("01", 2020, 1, 5, 0, 0),
        _row("01", 2020, 2, 5, 0, 0),
        _row("01", 2020, 3, 5, 0, 0),
    ]
    st = _run(rows, EXP2)
    r3 = _get(st, "01", 2020, 3)  # i=2: nacional previo = periodo 1 (delta 02 W02 = 6/10 = 0.6)
    assert "sex_fallback_national" in r3.quality_flags
    assert abs(r3.sex_prop_applied - 0.6) < 1e-9  # NO 0.7 (acumulado (8+6)/(10+10))


# ── order-invariance ──
def test_order_invariante():
    rows = [
        _row("01", 2020, 1, 10, 6, 4),
        _row("02", 2020, 1, 20, 11, 9),
        _row("01", 2020, 2, 12, 12, 8),
        _row("02", 2020, 2, 18, 20, 18),
    ]
    key = ["epi_year", "epi_week", "cve_ent"]
    a = _run(rows, EXP2).sort_values(key).reset_index(drop=True)
    b = _run(list(reversed(rows)), EXP2).sort_values(key).reset_index(drop=True)
    assert a.equals(b)


def test_columnas_faltantes_levanta():
    with pytest.raises(rc.ReconcileError):
        rc.reconcile_state(pd.DataFrame({"cve_ent": ["01"]}), EXP1)
