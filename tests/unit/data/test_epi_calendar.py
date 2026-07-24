"""F1/C1 — calendario epidemiológico (MMWR): ejemplos del plan + fronteras + round-trips."""

from __future__ import annotations

from datetime import date

import pytest

from epiforecast.data import epi_calendar as ec

# ── Ejemplos obligatorios del plan (fuente → objetivo con observation_lag_weeks=1) ──


@pytest.mark.parametrize(
    "src_year,src_week,exp_year,exp_week,exp_period_start,exp_ds",
    [
        (2025, 53, 2025, 52, date(2025, 12, 21), date(2025, 12, 22)),
        (2026, 1, 2025, 53, date(2025, 12, 28), date(2025, 12, 29)),
        (2026, 2, 2026, 1, date(2026, 1, 4), date(2026, 1, 5)),
    ],
)
def test_target_period_ejemplos_del_plan(
    src_year, src_week, exp_year, exp_week, exp_period_start, exp_ds
):
    p = ec.target_period(src_year, src_week, observation_lag_weeks=1)
    assert (p.epi_year, p.epi_week) == (exp_year, exp_week)
    assert p.period_start == exp_period_start
    assert p.ds == exp_ds


def test_lag_cero_es_identidad():
    # Sin lag, la (año, semana) de fuente ES el objetivo.
    p = ec.target_period(2026, 2, observation_lag_weeks=0)
    assert (p.epi_year, p.epi_week) == (2026, 2)
    p0 = ec.target_period(2025, 10, observation_lag_weeks=0)
    assert (p0.epi_year, p0.epi_week) == (2025, 10)


def test_lag_negativo_rechazado():
    with pytest.raises(ValueError):
        ec.target_period(2025, 10, observation_lag_weeks=-1)


# ── Cuenta de semanas por año (regla Jan-4) ──


@pytest.mark.parametrize(
    "year,expected",
    [(2014, 53), (2015, 52), (2020, 53), (2021, 52), (2024, 52), (2025, 53), (2026, 52)],
)
def test_weeks_in_year(year, expected):
    assert ec.weeks_in_year(year) in (52, 53)
    assert ec.weeks_in_year(year) == expected


# ── period_start siempre domingo; ds siempre lunes ──


@pytest.mark.parametrize("year", [2014, 2020, 2025, 2026])
def test_period_start_domingo_y_ds_lunes(year):
    for w in range(1, ec.weeks_in_year(year) + 1):
        ps = ec.week_start(year, w)
        ds = ec.ds_for(year, w)
        assert ps.weekday() == 6, (year, w, ps)  # domingo
        assert ds.weekday() == 0, (year, w, ds)  # lunes
        assert (ds - ps).days == 1


def test_week1_contiene_4_de_enero():
    for year in (2014, 2015, 2020, 2024, 2025, 2026):
        ps = ec.week_start(year, 1)
        assert 0 <= (date(year, 1, 4) - ps).days < 7  # el 4-ene cae dentro de la semana 1


# ── Round-trips: (year,week) ↔ fecha ──


@pytest.mark.parametrize("year", [2014, 2019, 2020, 2024, 2025, 2026])
def test_roundtrip_week_start_epi_from_date(year):
    for w in range(1, ec.weeks_in_year(year) + 1):
        ps = ec.week_start(year, w)
        assert ec.epi_from_date(ps) == (year, w)
        # cualquier día de la semana mapea a la misma (year, week)
        for offset in range(7):
            assert ec.epi_from_date(date.fromordinal(ps.toordinal() + offset)) == (year, w)
        # el ds (lunes) sigue en la misma semana
        assert ec.epi_from_date(ec.ds_for(year, w)) == (year, w)


# ── Fronteras de año: 52/53 → 1 sin colisión ni hueco ──


@pytest.mark.parametrize("year", [2014, 2020, 2024, 2025])
def test_frontera_ultima_semana_a_w1_del_siguiente(year):
    n = ec.weeks_in_year(year)
    last = ec.week_start(year, n)
    nxt_w1 = ec.week_start(year + 1, 1)
    assert (nxt_w1 - last).days == 7  # exactamente una semana, sin hueco ni solape
    assert ec.shift(year, n, 1) == (year + 1, 1)
    assert ec.shift(year + 1, 1, -1) == (year, n)


def test_no_colision_entre_w52_w53_w1():
    # 2025 tiene W53; 2025-W52, 2025-W53 y 2026-W01 deben ser tres domingos consecutivos distintos.
    s52 = ec.week_start(2025, 52)
    s53 = ec.week_start(2025, 53)
    s01 = ec.week_start(2026, 1)
    assert s52 < s53 < s01
    assert (s53 - s52).days == 7 and (s01 - s53).days == 7
    assert len({s52, s53, s01}) == 3


def test_shift_ida_y_vuelta_es_identidad():
    for year in (2014, 2020, 2025, 2026):
        for w in range(1, ec.weeks_in_year(year) + 1):
            for delta in (-53, -1, 1, 52, 53):
                y2, w2 = ec.shift(year, w, delta)
                assert ec.shift(y2, w2, -delta) == (year, w)


# ── Anomalías: semana fuera de rango se clasifica (fail-loud) ──


@pytest.mark.parametrize("year,bad_week", [(2026, 53), (2026, 0), (2025, 54), (2015, 53)])
def test_week_start_semana_invalida_levanta(year, bad_week):
    with pytest.raises(ValueError):
        ec.week_start(year, bad_week)
