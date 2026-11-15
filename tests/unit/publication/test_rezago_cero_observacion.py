"""Observación prospectiva con rezago 0: el boletín N (= origen) aporta 0/4 y el N+1 exactamente 1/4.

Pruebas SINTÉTICAS y herméticas. ``run_week`` exige PDF, registry, release sellado y ``runs/``; aquí
se encadenan sus piezas puras reales: ``merge_observation_raw`` (idempotencia del último boletín) →
``build_prep``/``reconcile_state``/``explode_base`` con el rezago del grupo → ``read_base_history``
→ ``evaluate`` (que usa ``select_weeks`` con el corte observado), igual que ``derive_evaluation``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from scripts import prospective_week as pw

from epiforecast.data.epi_geo_exposure import GeoCatalog, load_geo_catalog
from epiforecast.publication.prospective import (
    VERDICT_INCOMPLETE,
    build_control,
    evaluate,
    observation_cutoff,
    read_base_history,
)
from tests.unit.data import rezago_sintetico as syn

pytestmark = pytest.mark.unit

_PAD = "Sintético"
_ID = "sintetico_x00"


@pytest.fixture(scope="module")
def catalog() -> GeoCatalog:
    return load_geo_catalog()


def _semana(raw: pd.DataFrame, periodo: tuple[int, int]) -> pd.DataFrame:
    sel = (raw["Anio"] == periodo[0]) & (raw["Semana"] == periodo[1])
    return raw.loc[sel].reset_index(drop=True)


def _hasta(raw: pd.DataFrame, periodo: tuple[int, int]) -> pd.DataFrame:
    clave = raw["Anio"] * 100 + raw["Semana"]
    return raw.loc[clave <= periodo[0] * 100 + periodo[1]].reset_index(drop=True)


def _observa(
    tmp: Path, raw: pd.DataFrame, lag: int, catalog: GeoCatalog, gate: Any, training: Any
) -> dict[str, Any]:
    csv = syn.dataset_csv(raw, catalog, lag, tmp / "obs" / "epi_dataset_v2.csv", _ID)
    historia = read_base_history(csv)
    # El prefijo hasta el origen no se mueve (lo que exige check_observation_dataset).
    for serie, valores in historia.items():
        assert {p: v for p, v in valores.items() if p <= gate.origin} == {
            p: v for p, v in training[serie].items() if p <= gate.origin
        }
    control = build_control(training, gate.origin, gate.horizon)
    return evaluate(
        gate,
        control,
        control,
        historia,
        catalog=catalog,
        training=training,
        cutoff=observation_cutoff(historia),
    )


# (rezago, boletín N del entrenamiento = última semana fuente, origen, boletín N+1, semana nueva)
_CASOS = [
    (0, (2026, 43), (2026, 43), (2026, 44), (2026, 44)),
    (0, (2025, 53), (2025, 53), (2026, 1), (2026, 1)),
    (0, (2025, 52), (2025, 52), (2025, 53), (2025, 53)),
    (1, (2026, 43), (2026, 42), (2026, 44), (2026, 43)),
    (1, (2026, 1), (2025, 53), (2026, 2), (2026, 1)),
]


@pytest.mark.parametrize(("lag", "n", "origen", "n1", "nueva"), _CASOS)
def test_boletin_n_da_0_de_4_y_n_mas_1_da_1_de_4_idempotente(
    tmp_path: Path,
    catalog: GeoCatalog,
    lag: int,
    n: tuple[int, int],
    origen: tuple[int, int],
    n1: tuple[int, int],
    nueva: tuple[int, int],
) -> None:
    todo = syn.raw_boletines(syn.source_periods(n1, 57), lag, catalog, _PAD)
    entrenamiento = _hasta(todo, n)
    csv = syn.dataset_csv(entrenamiento, catalog, lag, tmp_path / "train" / "ds.csv", _ID)
    gate = syn.congela_gate(csv, _ID)
    training = read_base_history(csv)
    assert gate.origin == origen

    # Boletín N otra vez (= origen con rezago 0): la fusión es idempotente y no hay semana nueva.
    repetido = pw.merge_observation_raw(entrenamiento, _semana(todo, n), disease_name=_PAD)
    pd.testing.assert_frame_equal(
        repetido.reset_index(drop=True),
        entrenamiento.sort_values(["Anio", "Semana", "Entidad"]).reset_index(drop=True),
        check_dtype=False,
    )
    r0 = _observa(tmp_path / "n", repetido, lag, catalog, gate, training)
    assert r0["observation_cutoff"] == list(origen)
    assert (r0["weeks_available"], r0["weeks_required"]) == (0, 4)
    assert r0["verdict"] == VERDICT_INCOMPLETE
    assert r0["selection"]["skipped_weeks"] == []  # el futuro no es «ausente»

    # Boletín N+1: exactamente una semana objetivo nueva, la primera de la ventana.
    con_n1 = pw.merge_observation_raw(entrenamiento, _semana(todo, n1), disease_name=_PAD)
    assert len(con_n1) == len(entrenamiento) + 32
    r1 = _observa(tmp_path / "n1", con_n1, lag, catalog, gate, training)
    assert gate.target_weeks[0] == nueva
    assert r1["observation_cutoff"] == list(nueva)
    assert (r1["weeks_available"], r1["weeks"]) == (1, [list(nueva)])
    assert r1["selection"]["skipped_weeks"] == []
    assert r1["verdict"] == VERDICT_INCOMPLETE

    # Repetir el boletín N+1 es idempotente: mismo raw y misma evaluación.
    otra_vez = pw.merge_observation_raw(con_n1, _semana(todo, n1), disease_name=_PAD)
    pd.testing.assert_frame_equal(otra_vez, con_n1)
    r1b = _observa(tmp_path / "n1b", otra_vez, lag, catalog, gate, training)
    assert r1b == r1


def test_revision_del_boletin_repetido_se_rechaza(catalog: GeoCatalog) -> None:
    todo = syn.raw_boletines(syn.source_periods((2026, 1), 4), 0, catalog, _PAD)
    revisado = _semana(todo, (2026, 1)).copy()
    revisado["Casos_semana"] = revisado["Casos_semana"] + (revisado.index == 0)
    with pytest.raises(pw.ProspectiveWeekError, match="valores distintos"):
        pw.merge_observation_raw(todo, revisado, disease_name=_PAD)
