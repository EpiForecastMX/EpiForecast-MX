"""Rezago impreso 0 frente a 1 en los cruces MMWR: calendario, dataset y gate prospectivo.

Pruebas SINTÉTICAS y herméticas (sin datos reales, sin ``runs/`` ni release sellado). Las semanas
esperadas van escritas a mano, no recalculadas con el mismo calendario que se prueba: si
``target_period``, ``build_prep`` o ``horizon_periods`` aplicaran mal el rezago o el año de 53
semanas, estas pruebas fallan.

Contrato: la paridad semanal compara la semana FUENTE N; la semana objetivo de cada padecimiento es
N - rezago. Con rezago 0 el objetivo ES la fuente.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from epiforecast.data import epi_calendar as ec
from epiforecast.data import epi_dataset as ed
from epiforecast.data.epi_dataset_spec import QualityFlag
from epiforecast.data.epi_geo_exposure import GeoCatalog, load_geo_catalog
from epiforecast.publication.prospective import GATE_WEEKS, build_control, read_base_history
from tests.unit.data import rezago_sintetico as syn

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def catalog() -> GeoCatalog:
    return load_geo_catalog()  # config trackeado → CI-safe


# ── 1. Calendario: fuente → objetivo en los tres cruces 53 → 01 del carril ──

# (fuentes consecutivas alrededor del cruce, objetivos con rezago 0, objetivos con rezago 1)
_CRUCES = {
    "2014W53_2015W01": (
        [(2014, 52), (2014, 53), (2015, 1), (2015, 2)],
        [(2014, 52), (2014, 53), (2015, 1), (2015, 2)],
        [(2014, 51), (2014, 52), (2014, 53), (2015, 1)],
    ),
    "2020W53_2021W01": (
        [(2020, 52), (2020, 53), (2021, 1), (2021, 2)],
        [(2020, 52), (2020, 53), (2021, 1), (2021, 2)],
        [(2020, 51), (2020, 52), (2020, 53), (2021, 1)],
    ),
    "2025W53_2026W01": (
        [(2025, 52), (2025, 53), (2026, 1), (2026, 2)],
        [(2025, 52), (2025, 53), (2026, 1), (2026, 2)],
        [(2025, 51), (2025, 52), (2025, 53), (2026, 1)],
    ),
}
# Domingo de inicio de la semana 1 (regla del 4 de enero), escrito a mano.
_W01_START = {2015: date(2015, 1, 4), 2021: date(2021, 1, 3), 2026: date(2026, 1, 4)}


@pytest.mark.parametrize("cruce", sorted(_CRUCES))
@pytest.mark.parametrize("lag", [0, 1])
def test_target_period_en_el_cruce_53_01(cruce: str, lag: int) -> None:
    fuentes, objetivo0, objetivo1 = _CRUCES[cruce]
    esperado = objetivo0 if lag == 0 else objetivo1
    obtenido = [ec.target_period(a, s, lag) for a, s in fuentes]
    assert [(p.epi_year, p.epi_week) for p in obtenido] == esperado
    # Contiguas a 7 días exactos: ni se duplica ni se pierde una semana objetivo.
    inicios = [p.period_start for p in obtenido]
    assert [b - a for a, b in zip(inicios, inicios[1:], strict=False)] == [timedelta(7)] * 3
    assert all(p.ds == p.period_start + timedelta(days=1) for p in obtenido)
    assert all(p.period_start.weekday() == 6 for p in obtenido)  # domingo
    # La semana 1 del objetivo arranca el domingo de la regla del 4 de enero.
    semana1 = next(p for p in obtenido if p.epi_week == 1)
    assert semana1.period_start == _W01_START[semana1.epi_year]


@pytest.mark.parametrize("anio", [2021, 2026])  # años de 52 semanas
@pytest.mark.parametrize("lag", [0, 1])
def test_fuente_sem53_en_anio_de_52_falla_ruidosamente(anio: int, lag: int) -> None:
    with pytest.raises(ValueError, match="fuera de rango"):
        ec.target_period(anio, 53, lag)


@pytest.mark.parametrize("cruce", sorted(_CRUCES))
@pytest.mark.parametrize("lag", [0, 1])
def test_build_prep_por_entidad_sin_duplicar_ni_perder(
    catalog: GeoCatalog, cruce: str, lag: int
) -> None:
    fuentes, objetivo0, objetivo1 = _CRUCES[cruce]
    esperado = objetivo0 if lag == 0 else objetivo1
    raw = syn.raw_boletines(fuentes, lag, catalog, "Sintético")
    prep = ed.build_prep(raw, catalog, lag)
    assert len(prep) == 32 * len(fuentes)
    assert not prep.duplicated(["cve_ent", "epi_year", "epi_week"]).any()
    for _, grupo in prep.groupby("cve_ent"):
        grupo = grupo.sort_values("period_start")
        assert list(zip(grupo["source_year"], grupo["source_week"], strict=True)) == fuentes
        assert list(zip(grupo["epi_year"], grupo["epi_week"], strict=True)) == esperado
    if lag == 0:  # identidad: la fuente ES el objetivo
        assert (prep["source_year"] == prep["epi_year"]).all()
        assert (prep["source_week"] == prep["epi_week"]).all()


@pytest.mark.parametrize("fin", [(2015, 6), (2021, 6), (2026, 6)])
@pytest.mark.parametrize("lag", [0, 1])
def test_reconciliacion_reinicia_el_acumulado_en_la_semana_objetivo_1(
    catalog: GeoCatalog, fin: tuple[int, int], lag: int
) -> None:
    # Diez semanas fuente que cruzan 53 → 01. Los acumulados del boletín se reinician en la semana
    # OBJETIVO 1 del rezago declarado; con el calendario bien aplicado los deltas por sexo casan
    # con Casos_semana en todos los periodos (salvo el primero, sin predecesor).
    fuentes = syn.source_periods(fin, 10)
    raw = syn.raw_boletines(fuentes, lag, catalog, "Sintético")
    state = syn.state_frame(raw, catalog, lag)
    assert len(state) == 32 * 10
    assert (state["total_reconciled"] == state["total_source"]).all()
    assert state["observed"].all()
    resto = state[state["period_start"] != state["period_start"].min()]
    assert len(resto) == 32 * 9
    assert not resto["quality_flags"].str.contains(QualityFlag.SEX_DELTA_TOTAL_MISMATCH).any()
    assert (resto["quality_flags"] == "").all()
    periodos = sorted(set(zip(state["epi_year"], state["epi_week"], strict=True)))
    esperado_fin = fin if lag == 0 else (fin[0], fin[1] - 1)
    assert periodos[-1] == esperado_fin
    assert len(periodos) == 10


# ── 2. Gate prospectivo: origen = último periodo OBJETIVO del dataset; ventana MMWR ──

# (lag, semana fuente final del raw, origen esperado, ventana de 4 esperada) — a mano.
_GATES = [
    (0, (2026, 43), (2026, 43), [(2026, 44), (2026, 45), (2026, 46), (2026, 47)]),
    (1, (2026, 43), (2026, 42), [(2026, 43), (2026, 44), (2026, 45), (2026, 46)]),
    (0, (2025, 52), (2025, 52), [(2025, 53), (2026, 1), (2026, 2), (2026, 3)]),
    (1, (2026, 1), (2025, 53), [(2026, 1), (2026, 2), (2026, 3), (2026, 4)]),
    (0, (2020, 53), (2020, 53), [(2021, 1), (2021, 2), (2021, 3), (2021, 4)]),
    (0, (2026, 52), (2026, 52), [(2027, 1), (2027, 2), (2027, 3), (2027, 4)]),
    (1, (2015, 1), (2014, 53), [(2015, 1), (2015, 2), (2015, 3), (2015, 4)]),
]


@pytest.mark.parametrize(("lag", "fin", "origen", "ventana"), _GATES)
def test_gate_origen_y_ventana_mmwr(
    tmp_path: Path,
    catalog: GeoCatalog,
    lag: int,
    fin: tuple[int, int],
    origen: tuple[int, int],
    ventana: list[tuple[int, int]],
) -> None:
    raw = syn.raw_boletines(syn.source_periods(fin, 56), lag, catalog, "Sintético")
    csv = syn.dataset_csv(raw, catalog, lag, tmp_path / "epi_dataset_v2.csv", "sintetico_x00")
    gate = syn.congela_gate(csv, "sintetico_x00")
    assert gate.origin == origen
    assert list(gate.target_weeks) == ventana
    assert gate.payload()["target_weeks"] == [list(p) for p in ventana]
    # El primer horizonte es N+1 y el origen nunca entra en la ventana.
    assert gate.origin not in gate.target_weeks
    # El control (y por tanto el candidato) cubre exactamente el horizonte que arranca en N+1.
    control = build_control(read_base_history(csv), gate.origin, 52)
    periodos = sorted(
        set(zip(control["epi_year"], control["epi_week"], strict=True)),
        key=lambda p: ec.week_start(*p),
    )
    assert periodos[:GATE_WEEKS] == ventana
    assert len(periodos) == 52
