"""Fábrica SINTÉTICA de boletines con rezago impreso constante (0 o 1), para las pruebas de rezago.

No lee datos reales, ``runs/`` ni artefactos sellados: sólo el catálogo geográfico trackeado en
``config/``. Los acumulados por sexo se generan coherentes con el calendario OBJETIVO del rezago
declarado (se reinician cuando la semana objetivo es la 1), de modo que un calendario mal aplicado
aguas abajo deja huellas medibles en la reconciliación (``sex_delta_total_mismatch``).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from epiforecast.data import epi_calendar as ec
from epiforecast.data import epi_dataset as ed
from epiforecast.data.epi_dataset_spec import ExposureSnapshot
from epiforecast.data.epi_geo_exposure import GeoCatalog
from epiforecast.data.epi_reconcile import reconcile_state
from epiforecast.publication.prospective import (
    ACCEPTANCE_RULE,
    GATE_WEEKS,
    FrozenGate,
    build_control,
    check_dataset_frame,
    frame_digest,
    read_base_history,
)
from epiforecast.runner.release_reproduce import horizon_periods

Period = tuple[int, int]

RAW_COLUMNS: tuple[str, ...] = (
    "Anio",
    "Semana",
    "Entidad",
    "Padecimiento",
    "Casos_semana",
    "Acumulado_hombres",
    "Acumulado_mujeres",
    "Acumulado_anio_anterior",
)


def source_periods(end: Period, n: int) -> list[Period]:
    """Las ``n`` semanas FUENTE consecutivas (MMWR) que terminan en ``end``, en orden creciente."""
    return [ec.shift(end[0], end[1], -k) for k in range(n - 1, -1, -1)]


def raw_boletines(
    periods: list[Period], lag: int, catalog: GeoCatalog, padecimiento: str
) -> pd.DataFrame:
    """Raw por sexo (esquema del extractor) con 32 entidades por semana fuente."""
    filas: list[dict[str, object]] = []
    acum: dict[str, tuple[int, int]] = {}
    for k, (anio, semana) in enumerate(periods):
        objetivo = ec.target_period(anio, semana, lag)
        for i, ent in enumerate(catalog.entities):
            h0, m0 = acum.get(ent.cve_ent, (0, 0))
            if objetivo.epi_week == 1:
                h0, m0 = 0, 0
            casos = 1 + (k + i) % 5
            h = casos // 2 + (k % 2 if casos > 1 else 0)
            m = casos - h
            acum[ent.cve_ent] = (h0 + h, m0 + m)
            filas.append(
                {
                    "Anio": anio,
                    "Semana": semana,
                    "Entidad": ent.nombre_canonico,
                    "Padecimiento": padecimiento,
                    "Casos_semana": casos,
                    "Acumulado_hombres": h0 + h,
                    "Acumulado_mujeres": m0 + m,
                    "Acumulado_anio_anterior": 7,
                }
            )
    return pd.DataFrame(filas, columns=list(RAW_COLUMNS))


def snapshot(catalog: GeoCatalog) -> ExposureSnapshot:
    return ExposureSnapshot(
        source_id="sintetico",
        reference="sintetico",
        cutoff=date(2020, 3, 15),
        columns_by_sex={"hombres": "Hombres", "mujeres": "Mujeres"},
        total_column="Total",
        digest="sintetico",
        by_cve_ent={
            c: {"Hombres": 1000, "Mujeres": 1100, "Total": 2100} for c in catalog.cve_ents()
        },
    )


def state_frame(raw: pd.DataFrame, catalog: GeoCatalog, lag: int) -> pd.DataFrame:
    """raw → prep (rezago) → frame estatal reconciliado, con las funciones reales del carril."""
    return reconcile_state(ed.build_prep(raw, catalog, lag), set(catalog.cve_ents()))


def dataset_csv(
    raw: pd.DataFrame, catalog: GeoCatalog, lag: int, out: Path, disease_id: str
) -> Path:
    """EpiDatasetV2 sintético (64 bases) escrito como CSV, como lo leen el gate y la observación."""
    state = state_frame(raw, catalog, lag)
    base = ed.explode_base(state, snapshot(catalog), catalog, disease_id)
    base = base.sort_values(["cve_ent", "sexo", "epi_year", "epi_week"]).reset_index(drop=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    base.to_csv(out, index=False)
    return out


def congela_gate(csv: Path, disease_id: str) -> FrozenGate:
    """La misma secuencia que ``crea_gate.construye`` del skill, sin release ni ``runs/``.

    ``crea_gate.py`` vive fuera del repositorio (no está en CI): aquí se encadenan las MISMAS
    funciones reales que usa (``check_dataset_frame`` → ``read_base_history`` → origen = máximo
    periodo → ``horizon_periods(origen, GATE_WEEKS)`` → ``build_control(historia, origen, 52)``).
    El candidato es el propio control (como en un release de control).
    """
    check_dataset_frame(csv, expected_series=64)
    historia = read_base_history(csv)
    origen = max(max(serie) for serie in historia.values())
    control = build_control(historia, origen, 52)
    return FrozenGate(
        disease_id=disease_id,
        release_id=f"{disease_id}_release_sintetico",
        origin=origen,
        horizon=52,
        target_weeks=tuple(horizon_periods(origen, GATE_WEEKS)),
        candidate_digest=frame_digest(control),
        control_digest=frame_digest(control),
        dataset_digest="sintetico",
        rule=dict(ACCEPTANCE_RULE),
    )
