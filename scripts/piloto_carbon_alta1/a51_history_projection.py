"""Proyección y validación de datos fuente de ``sifilis_adquirida_a51`` para ``BASE_86_W43``.

Escanea el CSV crudo de entrenamiento, valida columnas, entidades canónicas, unicidad por
``(Anio, Semana, Entidad)``, contigüidad MMWR reciente y proyecta cada semana fuente
``<= cutoff`` a ``CONSOLIDADO_COLS`` sin aplicar ``observation_lag_weeks``, registrando
explícitamente celdas ``NA`` y exclusiones fuente heredadas.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from scripts.paso_semanal import CONSOLIDADO_COLS, filas_de_semana

from epiforecast.data.epi_calendar import shift as semana_siguiente
from epiforecast.data.extraction import cuadro_extractor
from epiforecast.publication.consolidado_base import entero
from epiforecast.publication.contratos_datos import ContratoCobertura

DISEASE_ID = "sifilis_adquirida_a51"
EXPECTED_OLD_PUBLISHED = 85
EXPECTED_NEW_PUBLISHED = 86
EXPECTED_STATES = 32
CONSOLIDADO_HEADER: list[str] = CONSOLIDADO_COLS.split(",")
VALUE_COLS: tuple[str, ...] = (
    "Casos_semana",
    "Acumulado_hombres",
    "Acumulado_mujeres",
    "Acumulado_anio_anterior",
)


class BaseHistoryBuildError(RuntimeError):
    """Fallo cerrado al construir o verificar ``BASE_86_W43``."""


def declared_source_exclusions(extraction_group: str) -> dict[str, Any]:
    grupo = cuadro_extractor.load_group(extraction_group)
    exclusions: list[dict[str, Any]] = []
    for raw_exc in grupo.get("source_exclusions") or []:
        diseases = [str(d) for d in (raw_exc.get("diseases") or [])]
        if diseases and DISEASE_ID not in diseases:
            continue
        exclusions.append(
            {
                "file": str(raw_exc.get("file", "")),
                "keep_period": bool(raw_exc.get("keep_period", False)),
                "reason": str(raw_exc.get("reason", "")).strip(),
            }
        )
    return {
        "extraction_group": extraction_group,
        "observation_lag_weeks_in_group": int(grupo.get("observation_lag_weeks", 0)),
        "lag_applied_in_consolidado": False,
        "source_exclusions": exclusions,
    }


def _scan_raw_periods(
    raw_csv: Path,
    *,
    expected_data_name: str,
    canonical_entities: frozenset[str],
    contrato: ContratoCobertura,
) -> set[tuple[int, int]]:
    with raw_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        required_raw = {
            "Anio",
            "Semana",
            "Entidad",
            "Padecimiento",
            "Casos_semana",
            "Acumulado_anio_anterior",
        }
        missing_cols = sorted(required_raw - set(fieldnames))
        if missing_cols:
            raise BaseHistoryBuildError(f"raw A51 sin columnas requeridas: {missing_cols}")
        if "Acumulado_total" not in fieldnames and not {
            "Acumulado_hombres",
            "Acumulado_mujeres",
        }.issubset(fieldnames):
            raise BaseHistoryBuildError(
                f"raw A51 sin columnas de acumulado por sexo ni total: {fieldnames}"
            )
        seen_keys: set[tuple[int, int, str]] = set()
        raw_periods: set[tuple[int, int]] = set()
        for row in reader:
            if row["Padecimiento"] != expected_data_name:
                raise BaseHistoryBuildError(
                    f"Padecimiento inesperado en raw A51: {row['Padecimiento']!r} "
                    f"(esperado {expected_data_name!r})"
                )
            anio = entero(row["Anio"], "Anio")
            semana = entero(row["Semana"], "Semana")
            canon_ent = contrato.entidad_canonica(row["Entidad"])
            if canon_ent is None or canon_ent not in canonical_entities:
                raise BaseHistoryBuildError(
                    f"Entidad fuera de catálogo en raw A51 ({anio}-W{semana:02d}): "
                    f"{row['Entidad']!r}"
                )
            key = (anio, semana, canon_ent)
            if key in seen_keys:
                raise BaseHistoryBuildError(f"Clave duplicada en raw A51: {key}")
            seen_keys.add(key)
            raw_periods.add((anio, semana))
    return raw_periods


def _project_single_period(
    raw_csv: Path,
    *,
    anio: int,
    semana: int,
    expected_data_name: str,
    canonical_entities: frozenset[str],
    contrato: ContratoCobertura,
    na_counts_by_col: dict[str, int],
    full_row_na_periods: list[list[int]],
    prev_only_na_periods: list[list[int]],
    partial_na_cells: list[dict[str, Any]],
) -> list[str]:
    lines = filas_de_semana(raw_csv, anio, semana)
    if len(lines) != EXPECTED_STATES:
        raise BaseHistoryBuildError(
            f"A51 {anio}-W{semana:02d}: {len(lines)} filas proyectadas "
            f"(se esperan {EXPECTED_STATES})"
        )
    parsed_rows = list(csv.reader(lines))
    period_entities: set[str] = set()
    empty_all_four = 0
    empty_prev_only = 0
    period_partials: list[dict[str, Any]] = []

    for cols in parsed_rows:
        if len(cols) != len(CONSOLIDADO_HEADER):
            raise BaseHistoryBuildError(
                f"fila proyectada fuera de CONSOLIDADO_COLS ({len(cols)} cols): {cols!r}"
            )
        if (entero(cols[0], "Anio"), entero(cols[1], "Semana")) != (anio, semana):
            raise BaseHistoryBuildError(
                f"semana MMWR fuente alterada al proyectar {anio}-W{semana:02d}: {cols[:2]!r}"
            )
        if cols[3] != expected_data_name:
            raise BaseHistoryBuildError(f"Padecimiento alterado al proyectar: {cols[3]!r}")
        canon_ent = contrato.entidad_canonica(cols[2])
        if canon_ent is None or canon_ent in period_entities:
            raise BaseHistoryBuildError(
                f"entidad inválida o duplicada en {anio}-W{semana:02d}: {cols[2]!r}"
            )
        period_entities.add(canon_ent)

        vals = cols[4:8]
        for col_name, cell in zip(VALUE_COLS, vals, strict=True):
            if cell.strip() == "":
                na_counts_by_col[col_name] += 1

        if all(v.strip() == "" for v in vals):
            empty_all_four += 1
        elif vals[3].strip() == "" and all(v.strip() != "" for v in vals[:3]):
            empty_prev_only += 1
        elif any(v.strip() == "" for v in vals):
            missing_names = [
                name for name, cell in zip(VALUE_COLS, vals, strict=True) if cell.strip() == ""
            ]
            period_partials.append(
                {
                    "year": anio,
                    "week": semana,
                    "entity": cols[2],
                    "missing_columns": missing_names,
                }
            )

    if period_entities != canonical_entities:
        missing_ents = sorted(canonical_entities - period_entities)
        raise BaseHistoryBuildError(
            f"A51 {anio}-W{semana:02d}: faltan entidades canónicas {missing_ents[:5]}"
        )

    if empty_all_four == EXPECTED_STATES:
        full_row_na_periods.append([anio, semana])
    elif empty_prev_only == EXPECTED_STATES:
        prev_only_na_periods.append([anio, semana])
    else:
        if empty_all_four:
            raise BaseHistoryBuildError(
                f"A51 {anio}-W{semana:02d}: {empty_all_four} filas totalmente vacías "
                f"(parcial inesperado)"
            )
        if empty_prev_only:
            for cols in parsed_rows:
                vals = cols[4:8]
                if vals[3].strip() == "" and all(v.strip() != "" for v in vals[:3]):
                    period_partials.append(
                        {
                            "year": anio,
                            "week": semana,
                            "entity": cols[2],
                            "missing_columns": ["Acumulado_anio_anterior"],
                        }
                    )
        partial_na_cells.extend(period_partials)
    return lines


def scan_and_project_a51_history(
    raw_csv: Path,
    *,
    expected_data_name: str,
    cutoff: tuple[int, int],
    canonical_entities: frozenset[str],
    contrato: ContratoCobertura,
) -> tuple[bytes, dict[str, Any]]:
    raw_periods = _scan_raw_periods(
        raw_csv,
        expected_data_name=expected_data_name,
        canonical_entities=canonical_entities,
        contrato=contrato,
    )
    included_periods = sorted(p for p in raw_periods if p <= cutoff)
    excluded_after_cutoff = sorted(p for p in raw_periods if p > cutoff)
    if not included_periods:
        raise BaseHistoryBuildError(f"raw A51 no contiene periodos <= {cutoff}")
    if included_periods[-1] != cutoff:
        raise BaseHistoryBuildError(
            f"último periodo incluido {included_periods[-1]} != corte requerido {cutoff}"
        )

    mmwr_gaps = [
        [list(a), list(b)]
        for a, b in zip(included_periods, included_periods[1:], strict=False)
        if semana_siguiente(a[0], a[1], 1) != b
    ]
    min_depth = contrato.profundidad_minima
    if len(included_periods) < min_depth:
        raise BaseHistoryBuildError(
            f"historia A51 insuficiente: {len(included_periods)} < {min_depth} semanas"
        )
    recent_periods = included_periods[-min_depth:]
    recent_gaps = [
        (a, b)
        for a, b in zip(recent_periods, recent_periods[1:], strict=False)
        if semana_siguiente(a[0], a[1], 1) != b
    ]
    if recent_gaps:
        raise BaseHistoryBuildError(
            f"huecos MMWR en las últimas {min_depth} semanas de A51: {recent_gaps[:3]}"
        )

    projected_lines: list[str] = []
    full_row_na_periods: list[list[int]] = []
    prev_only_na_periods: list[list[int]] = []
    partial_na_cells: list[dict[str, Any]] = []
    na_counts_by_col: dict[str, int] = dict.fromkeys(VALUE_COLS, 0)

    for anio, semana in included_periods:
        projected_lines.extend(
            _project_single_period(
                raw_csv,
                anio=anio,
                semana=semana,
                expected_data_name=expected_data_name,
                canonical_entities=canonical_entities,
                contrato=contrato,
                na_counts_by_col=na_counts_by_col,
                full_row_na_periods=full_row_na_periods,
                prev_only_na_periods=prev_only_na_periods,
                partial_na_cells=partial_na_cells,
            )
        )

    payload = "".join(line + "\n" for line in projected_lines).encode("utf-8")
    summary: dict[str, Any] = {
        "rows_added": len(projected_lines),
        "periods_included_count": len(included_periods),
        "first_period_source_mmwr": list(included_periods[0]),
        "last_period_source_mmwr": list(included_periods[-1]),
        "periods_excluded_after_cutoff": [list(p) for p in excluded_after_cutoff],
        "historical_mmwr_gaps": mmwr_gaps,
        "na_declaration": {
            "na_counts_by_column": na_counts_by_col,
            "full_row_na_periods": full_row_na_periods,
            "prev_year_only_na_periods": prev_only_na_periods,
            "partial_na_cells": partial_na_cells,
        },
    }
    return payload, summary
