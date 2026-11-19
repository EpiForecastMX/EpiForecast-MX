"""El rezago inicial del plan por periodos entra en la configuración efectiva (re-auditoría).

Caso de la re-auditoría: dos planes aceptados con rezago inicial 1 y 2, ambos a 0 desde 2021_sem01,
sobre boletines anteriores al cambio. Dan objetivos distintos y, con el código anterior, el mismo
``config_effective`` y el mismo ``config_digest``. Los datasets ya sellados (inicial 1) conservan su
serialización byte a byte: se fija aquí el ``calendar`` exacto que llevaban.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from epiforecast.data import epi_dataset as ed
from epiforecast.data import epi_lag_calendar as lc
from epiforecast.data import epi_lag_schedule as ls
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from tests.unit.data import rezago_sintetico as syn

pytestmark = pytest.mark.unit

_HUECO = {"periodo": "2020-W53", "motivo": "ningún boletín imprime la semana 53 de 2020"}


def _grupo(inicial: int, **cambio: Any) -> dict[str, Any]:
    return {
        "observation_lag_weeks": inicial,
        "n_states_expected": 32,
        "periodos": [{"desde": "2021_sem01", "observation_lag_weeks": 0, **cambio}],
    }


def _construye(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, inicial: int
) -> ed.EpiDatasetV2Result:
    catalog = load_geo_catalog()
    raw = syn.raw_boletines(syn.source_periods((2019, 30), 20), 1, catalog, "Obesidad")
    raw_path = tmp_path / f"raw_{inicial}.csv"
    raw.to_csv(raw_path, index=False)
    monkeypatch.setattr(ed, "_cuadros_group", lambda _gid: _grupo(inicial))
    monkeypatch.setattr(ed, "load_exposure_snapshot", lambda _sid, cat: syn.snapshot(cat))
    return ed.build_epi_dataset_v2(
        "Obesidad", runs_root=tmp_path / f"runs_{inicial}", raw_path=raw_path
    )


def test_rezago_inicial_1_y_2_dan_configuraciones_distintas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    uno = _construye(monkeypatch, tmp_path, 1)
    dos = _construye(monkeypatch, tmp_path, 2)
    objetivo = {r.run_id: tuple(r.dataset[["epi_year", "epi_week"]].min()) for r in (uno, dos)}
    assert len(set(objetivo.values())) == 2  # los objetivos difieren
    assert uno.digests["config"] != dos.digests["config"]
    cal = {
        r.config.lag_schedule.initial if r.config.lag_schedule else -1: json.loads(
            (r.run_dir / "inputs" / "config_effective.json").read_text()
        )["calendar"]
        for r in (uno, dos)
    }
    assert lc.schedule_from_calendar(cal[1]) == ls.schedule_from_group(_grupo(1))
    assert lc.schedule_from_calendar(cal[2]) == ls.schedule_from_group(_grupo(2))
    assert lc.INITIAL_KEY not in cal[1] and cal[2][lc.INITIAL_KEY] == 2


def test_calendar_de_los_sellados_no_cambia() -> None:
    """Forma exacta del ``calendar`` de los nueve sellados (inicial 1, cambio en 2021 o 2015)."""
    plan = ls.schedule_from_group(_grupo(1, huecos_objetivo=[_HUECO]))
    assert lc.calendar_payload(plan) == {
        "observation_lag_weeks": 0,
        "lag_schedule": [
            {"desde": "2021_sem01", "observation_lag_weeks": 0, "huecos_objetivo": ["2020-W53"]}
        ],
    }
    assert lc.calendar_payload(ls.LagSchedule(1)) == {"observation_lag_weeks": 1}
    assert lc.calendar_payload(ls.LagSchedule(0)) == {"observation_lag_weeks": 0}


@pytest.mark.parametrize("inicial", [0, 1, 2, 3])
@pytest.mark.parametrize("huecos", [None, [_HUECO]])
def test_ida_y_vuelta_del_calendar(inicial: int, huecos: list[dict[str, str]] | None) -> None:
    extra = {"huecos_objetivo": huecos} if huecos else {}
    plan = ls.schedule_from_group(_grupo(inicial, **extra))
    assert lc.schedule_from_calendar(lc.calendar_payload(plan)) == plan


def test_serializacion_inyectiva() -> None:
    planes = {ls.LagSchedule(i) for i in range(4)} | {
        ls.schedule_from_group(_grupo(i)) for i in range(4)
    }
    textos = {json.dumps(lc.calendar_payload(p), sort_keys=True) for p in planes}
    assert len(textos) == len(planes)


@pytest.mark.parametrize(
    "calendar",
    [
        {"observation_lag_weeks": 1, "lag_schedule_initial": 2},  # inicial sin cambios
        {  # vigente que no es el del último cambio
            "observation_lag_weeks": 1,
            "lag_schedule": [{"desde": "2021_sem01", "observation_lag_weeks": 0,
                              "huecos_objetivo": []}],
        },
    ],
)  # fmt: skip
def test_calendar_incoherente_falla_cerrado(calendar: dict[str, Any]) -> None:
    with pytest.raises(ls.LagScheduleError):
        lc.schedule_from_calendar(calendar)
