"""F1/C1 — reconciliación pura: mayor residuo + escenarios sintéticos de las reglas del contrato."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from epiforecast.data import epi_reconcile as rc


# ── largest_remainder_split ──
@pytest.mark.parametrize(
    "total,prop", [(10, 0.6), (11, 0.5), (7, 0.375), (100, 0.333), (1, 0.9), (5, 0.0), (5, 1.0)]
)
def test_split_preserva_suma(total, prop):
    h, m = rc.largest_remainder_split(total, prop)
    assert h + m == total
    assert h >= 0 and m >= 0


def test_split_cero():
    assert rc.largest_remainder_split(0, 0.7) == (0, 0)


def test_split_negativo_preserva_suma():
    h, m = rc.largest_remainder_split(-8, 0.6)
    assert h + m == -8  # revisión conservada


def test_split_empate_va_a_hombres():
    assert rc.largest_remainder_split(11, 0.5) == (6, 5)


def test_split_extremos():
    assert rc.largest_remainder_split(5, 0.0) == (0, 5)
    assert rc.largest_remainder_split(5, 1.0) == (5, 0)


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


def _prep(rows):
    return pd.DataFrame(rows)


def _get(state, cve, ey, ew):
    d = state[(state.cve_ent == cve) & (state.epi_year == ey) & (state.epi_week == ew)]
    assert len(d) == 1
    return d.iloc[0]


# ── split por delta + mismatch ──
def test_delta_split_basico():
    st = rc.reconcile_state(
        _prep(
            [
                _row("01", 2020, 1, 10, 6, 4),  # W01 baseline 0 → dh=6 dm=4, prop 0.6
                _row("01", 2020, 2, 10, 12, 8),  # dh=6 dm=4
            ]
        )
    )
    r1 = _get(st, "01", 2020, 1)
    assert (r1.y_hombres, r1.y_mujeres) == (6, 4)
    assert r1.observed and abs(r1.sex_prop_applied - 0.6) < 1e-9
    assert r1.quality_flags == ""  # sin flags: dh+dm==casos


def test_sex_delta_total_mismatch():
    # dh+dm = 10 pero Casos_semana = 8: se usa la proporción 0.6 igualmente y se anota el mismatch.
    st = rc.reconcile_state(_prep([_row("01", 2020, 1, 8, 6, 4)]))
    r = _get(st, "01", 2020, 1)
    assert "sex_delta_total_mismatch" in r.quality_flags
    assert r.sex_delta_total == 10 and r.sex_delta_residual == 2  # 10 - 8
    assert (r.y_hombres, r.y_mujeres) == (5, 3)  # split de 8 con prop 0.6
    assert r.y_hombres + r.y_mujeres == 8


# ── source_missing vs cero aislado real ──
def test_source_missing_vs_cero_aislado():
    rows = [
        _row("01", 2020, 1, 10, 6, 4),
        _row("02", 2020, 1, 10, 5, 5),
        _row("01", 2020, 2, 0, 6, 4),  # solo 01 en cero → nacional>0 → cero real
        _row("02", 2020, 2, 8, 9, 9),
        _row("01", 2020, 3, 0, 6, 4),  # ambos en cero → nacional 0 → source_missing
        _row("02", 2020, 3, 0, 9, 9),
    ]
    st = rc.reconcile_state(_prep(rows))
    r_iso = _get(st, "01", 2020, 2)
    assert r_iso.observed and r_iso.total_reconciled == 0  # cero real conservado
    assert "source_missing" not in r_iso.quality_flags
    for cve in ("01", "02"):
        r_sm = _get(st, cve, 2020, 3)
        assert not r_sm.observed
        assert "source_missing" in r_sm.quality_flags
        assert "total_imputed" in r_sm.quality_flags


# ── predecessor_snapshot_invalid tras colapso ──
def test_predecessor_invalid_tras_colapso():
    rows = [
        _row("01", 2020, 1, 10, 6, 4),
        _row("01", 2020, 2, 12, 12, 10),
        _row("01", 2020, 3, 0, 0, 0),  # colapso (nacional=1 entidad → 0) → source_missing
        _row("01", 2020, 4, 15, 20, 16),  # observado, pero baseline previo inválido
        _row("01", 2020, 5, 8, 24, 20),  # reanuda (baseline W04 válido)
    ]
    st = rc.reconcile_state(_prep(rows))
    assert "source_missing" in _get(st, "01", 2020, 3).quality_flags
    r4 = _get(st, "01", 2020, 4)
    assert "predecessor_snapshot_invalid" in r4.quality_flags
    assert r4.observed  # el total sí se observa
    assert "sex_fallback" in r4.quality_flags  # sin delta válido → fallback
    r5 = _get(st, "01", 2020, 5)
    assert "predecessor_snapshot_invalid" not in r5.quality_flags
    assert pd.notna(r5.sex_prop_source)  # delta válido de nuevo


# ── imputación causal por misma semana en años previos ──
def test_imputa_total_por_misma_semana_anios_previos():
    rows = [
        _row("01", 2018, 10, 20, 12, 8, sy=2018, swk=11),
        _row("02", 2018, 10, 100, 60, 40, sy=2018, swk=11),
        _row("01", 2019, 10, 30, 18, 12, sy=2019, swk=11),
        _row("02", 2019, 10, 100, 60, 40, sy=2019, swk=11),
        # 2020-W10: ambos en cero → source_missing → imputar por mediana de misma semana
        _row("01", 2020, 10, 0, 0, 0, sy=2020, swk=11),
        _row("02", 2020, 10, 0, 0, 0, sy=2020, swk=11),
    ]
    st = rc.reconcile_state(_prep(rows))
    r = _get(st, "01", 2020, 10)
    assert not r.observed
    assert r.total_reconciled == 25  # mediana([20, 30])
    assert "total_imputed" in r.quality_flags


# ── order-invariance ──
def test_order_invariante():
    rows = [
        _row("01", 2020, 1, 10, 6, 4),
        _row("02", 2020, 1, 20, 11, 9),
        _row("01", 2020, 2, 12, 12, 8),
        _row("02", 2020, 2, 18, 20, 18),
    ]
    a = rc.reconcile_state(_prep(rows)).sort_values(["epi_year", "epi_week", "cve_ent"])
    b = rc.reconcile_state(_prep(list(reversed(rows)))).sort_values(
        ["epi_year", "epi_week", "cve_ent"]
    )
    assert a.reset_index(drop=True).equals(b.reset_index(drop=True))


def test_columnas_faltantes_levanta():
    with pytest.raises(rc.ReconcileError):
        rc.reconcile_state(pd.DataFrame({"cve_ent": ["01"]}))
