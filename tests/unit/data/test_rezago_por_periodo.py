"""Rezago impreso por periodo (opt-in): un cambio de régimen único declarado en ``periodos``.

Sintéticas y herméticas (sólo el catálogo geográfico trackeado). Los periodos objetivo esperados se
escriben a mano: si el plan aplicara mal el rezago por periodo, el año de 53 semanas o el hueco de
la frontera, estas pruebas fallan. Con el código anterior (rezago único por grupo) no existe
``epi_lag_schedule`` y ``load_config`` ignora el rezago de ``periodos``.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from epiforecast.data import epi_dataset as ed
from epiforecast.data import epi_lag_schedule as ls
from epiforecast.data.epi_dataset_spec import QualityFlag
from epiforecast.data.epi_geo_exposure import GeoCatalog, load_geo_catalog
from epiforecast.data.epi_reconcile import reconcile_state
from tests.unit.data import rezago_sintetico as syn

pytestmark = pytest.mark.unit

_HUECO_2020 = {"periodo": "2020-W53", "motivo": "ningún boletín imprime la semana 53 de 2020"}


@pytest.fixture(scope="module")
def catalog() -> GeoCatalog:
    return load_geo_catalog()


def _grupo(**extra: Any) -> dict[str, Any]:
    return {"observation_lag_weeks": 1, "n_states_expected": 32, **extra}


def _cambio_2021(**extra: Any) -> dict[str, Any]:
    return {"desde": "2021_sem01", "observation_lag_weeks": 0, **extra}


def _raw(fuentes: list[tuple[int, int]], catalog: GeoCatalog) -> pd.DataFrame:
    return syn.raw_boletines(fuentes, 0, catalog, "Sintético")


# ── 1. Lectura del plan ──


def test_sin_cambios_es_rezago_constante() -> None:
    plan = ls.schedule_from_group(_grupo(periodos=[{"desde": "2017_sem02", "x": 1}]))
    assert plan == ls.LagSchedule(1)
    assert plan.vigente == 1 and plan.payload() == []


def test_rezago_vigente_es_el_del_ultimo_cambio() -> None:
    plan = ls.schedule_from_group(
        _grupo(
            periodos=[{"desde": "2017_sem02", "x": 1}, _cambio_2021(huecos_objetivo=[_HUECO_2020])]
        )
    )
    assert plan.vigente == 0
    assert plan.lag_for((2020, 53)) == 1 and plan.lag_for((2021, 1)) == 0
    assert plan.lag_for((2026, 44)) == 0
    assert plan.payload() == [
        {"desde": "2021_sem01", "observation_lag_weeks": 0, "huecos_objetivo": ["2020-W53"]}
    ]


@pytest.mark.parametrize(
    "grupo",
    [
        _grupo(periodos=[_cambio_2021(observation_lag_weeks=None)]),
        _grupo(periodos=[_cambio_2021(observation_lag_weeks=True)]),
        _grupo(periodos=[_cambio_2021(observation_lag_weeks=-1)]),
        _grupo(periodos=[_cambio_2021(desde="2021-W01")]),
        _grupo(periodos=[_cambio_2021(desde="2021_sem53")]),  # 2021 tiene 52 semanas
        _grupo(periodos=[_cambio_2021(), {"desde": "2018_sem01", "observation_lag_weeks": 1}]),
        _grupo(periodos=[{"desde": "2017_sem02", "huecos_objetivo": [_HUECO_2020]}]),
        _grupo(huecos_objetivo=[_HUECO_2020]),
        _grupo(periodos=[_cambio_2021(huecos_objetivo=[{"periodo": "2020-W53", "motivo": " "}])]),
        _grupo(
            periodos=[_cambio_2021(huecos_objetivo=[{"periodo": "2020_sem53", "motivo": "m"}])]
        ),
        _grupo(periodos=[_cambio_2021(huecos_objetivo=[])]),
        _grupo(observation_lag_weeks=None),
    ],
)
def test_plan_mal_declarado_falla_cerrado(grupo: dict[str, Any]) -> None:
    with pytest.raises(ls.LagScheduleError):
        ls.schedule_from_group(grupo)


# ── 2. Fuente → objetivo en la frontera ──


def test_frontera_2021_deja_el_hueco_2020_w53() -> None:
    plan = ls.schedule_from_group(_grupo(periodos=[_cambio_2021(huecos_objetivo=[_HUECO_2020])]))
    fuentes = [(2020, 52), (2020, 53), (2021, 1), (2021, 2)]
    tp = ls.plan_targets(fuentes, plan)
    objetivos = [(tp.targets[f].epi_year, tp.targets[f].epi_week) for f in fuentes]
    assert objetivos == [(2020, 51), (2020, 52), (2021, 1), (2021, 2)]
    assert [((p.epi_year, p.epi_week), s) for p, s in tp.gaps] == [((2020, 53), (2021, 1))]


def test_hueco_no_declarado_falla_cerrado() -> None:
    plan = ls.schedule_from_group(_grupo(periodos=[_cambio_2021()]))
    with pytest.raises(ls.LagScheduleError, match="no declarado"):
        ls.plan_targets([(2020, 53), (2021, 1)], plan)


def test_hueco_declarado_que_no_ocurre_falla() -> None:
    hueco = {"periodo": "2015-W48", "motivo": "m"}
    plan = ls.schedule_from_group(
        _grupo(
            periodos=[
                {"desde": "2015_sem49", "observation_lag_weeks": 0, "huecos_objetivo": [hueco]}
            ]
        )
    )
    with pytest.raises(ls.LagScheduleError, match="no ocurre"):
        ls.plan_targets([(2015, 49), (2015, 50)], plan)  # sin frontera en las fuentes


def test_cambio_2015_sem49_deja_el_hueco_2015_w48() -> None:
    hueco = {"periodo": "2015-W48", "motivo": "m"}
    plan = ls.schedule_from_group(
        _grupo(
            periodos=[
                {"desde": "2015_sem49", "observation_lag_weeks": 0, "huecos_objetivo": [hueco]}
            ]
        )
    )
    tp = ls.plan_targets([(2015, 47), (2015, 48), (2015, 49), (2015, 50)], plan)
    assert [(tp.targets[f].epi_week) for f in sorted(tp.targets)] == [46, 47, 49, 50]
    assert [((p.epi_year, p.epi_week), s) for p, s in tp.gaps] == [((2015, 48), (2015, 49))]


def test_solapamiento_falla_cerrado() -> None:
    # De rezago 0 a 1: el boletín 2021_sem02 vuelve a la semana 2021-W01 de 2021_sem01.
    plan = ls.schedule_from_group(
        {
            "observation_lag_weeks": 0,
            "periodos": [{"desde": "2021_sem02", "observation_lag_weeks": 1}],
        }
    )
    with pytest.raises(ls.LagScheduleError, match="solapamiento"):
        ls.plan_targets([(2021, 1), (2021, 2)], plan)


def test_frontera_con_boletin_faltante_falla_cerrado() -> None:
    plan = ls.schedule_from_group(_grupo(periodos=[_cambio_2021(huecos_objetivo=[_HUECO_2020])]))
    with pytest.raises(ls.LagScheduleError, match="no consecutivos"):
        ls.plan_targets([(2020, 52), (2021, 1)], plan)


def test_boletin_faltante_sin_cambio_de_rezago_conserva_el_comportamiento() -> None:
    tp = ls.plan_targets([(2019, 10), (2019, 12)], ls.LagSchedule(1))
    assert tp.gaps == () and [p.epi_week for p in tp.targets.values()] == [9, 11]


# ── 3. Prep y reconciliación ──


def test_entero_y_plan_constante_dan_el_mismo_prep(catalog: GeoCatalog) -> None:
    raw = _raw(syn.source_periods((2021, 3), 6), catalog)
    a = ed.build_prep(raw, catalog, 1)
    b = ed.build_prep(raw, catalog, ls.LagSchedule(1))
    pd.testing.assert_frame_equal(a, b)
    assert sorted(set(zip(a["epi_year"], a["epi_week"], strict=True))) == [
        (2020, 50),
        (2020, 51),
        (2020, 52),
        (2020, 53),
        (2021, 1),
        (2021, 2),
    ]


def test_hueco_declarado_se_imputa_y_se_marca(catalog: GeoCatalog) -> None:
    plan = ls.schedule_from_group(_grupo(periodos=[_cambio_2021(huecos_objetivo=[_HUECO_2020])]))
    fuentes = syn.source_periods((2021, 4), 20)
    prep = ed.build_prep(_raw(fuentes, catalog), catalog, plan)
    assert not prep.duplicated(["cve_ent", "epi_year", "epi_week"]).any()
    hueco = prep[(prep["epi_year"] == 2020) & (prep["epi_week"] == 53)]
    assert len(hueco) == 32 and hueco["casos_source"].isna().all()
    assert set(zip(hueco["source_year"], hueco["source_week"], strict=True)) == {(2021, 1)}
    state = ls.mark_gap_rows(reconcile_state(prep, set(catalog.cve_ents())), plan)
    periodos = sorted(set(zip(state["epi_year"], state["epi_week"], strict=True)))
    assert len(periodos) == 21 and (2020, 53) in periodos  # 20 fuentes + 1 hueco, contiguos
    marcadas = state[state["quality_flags"].str.contains(QualityFlag.LAG_REGIME_GAP)]
    assert set(zip(marcadas["epi_year"], marcadas["epi_week"], strict=True)) == {(2020, 53)}
    assert len(marcadas) == 32 and not marcadas["observed"].any()
    assert marcadas["quality_flags"].str.contains(QualityFlag.TOTAL_IMPUTED).all()


def test_load_config_lee_el_rezago_vigente(monkeypatch: pytest.MonkeyPatch) -> None:
    grupo = _grupo(periodos=[_cambio_2021(huecos_objetivo=[_HUECO_2020])])
    monkeypatch.setattr(ed, "_cuadros_group", lambda _gid: grupo)
    cfg = ed.load_config("obesidad")
    assert cfg.observation_lag_weeks == 0
    assert cfg.lag_schedule is not None and cfg.lag_schedule.vigente == 0
    monkeypatch.setattr(ed, "_cuadros_group", lambda _gid: _grupo())
    constante = ed.load_config("obesidad")
    assert constante.observation_lag_weeks == 1 and constante.lag_schedule is None
    monkeypatch.setattr(ed, "_cuadros_group", lambda _gid: _grupo(periodos=[_cambio_2021()]))
    cfg_sin_hueco = ed.load_config("obesidad")  # el hueco se detecta al ver las fuentes
    assert cfg_sin_hueco.observation_lag_weeks == 0
    monkeypatch.setattr(ed, "_cuadros_group", lambda _gid: _grupo(huecos_objetivo=[_HUECO_2020]))
    with pytest.raises(ed.EpiDatasetError):
        ed.load_config("obesidad")
