"""QA cuantitativo post-extracción (C6, C7 y C8) — piloto Carbon alta1.

Mide sobre el CSV canónico sellado y el corpus PDF sellado (sin crear criterios nuevos ni consultar
métricas de pronóstico de 2025):
- C6 (anti-bloque y fila TOTAL): cuadre de la suma nacional de las 32 entidades contra el bloque
  central del renglón TOTAL impreso, y contraste cuantitativo celda a celda y de fila TOTAL contra
  los dos bloques vecinos de Cuadro 6 (Sífilis congénita A50 e Infección gonocócica A54.0-A54.2),
  declarando denominadores, ausentes, página y conteo de columnas por boletín/época.
- C7 (calendario, rezago histórico, densidad semanal y calidad): verificación del rezago impreso 1
  contra ``epi_calendar.target_period`` en los encabezados de los PDFs, ``weeks_in_year`` canónico
  (2014, 2020, 2021..2024, 2025), cobertura de objetivos 2025 sin ``-1``, deltas negativos crudos
  de acumulados por sexo, distribución de ``y_cases`` y proporción de ceros por serie base (64),
  ``min_train_weeks`` real antes de cada pliegue frente a 260, conteo de ``total_imputed`` (global
  y en 2025) y nivel anual nacional 2014-2025.
- C8 (``validate-data``): copia verificada por SHA-256 a ``data/raw/data_raw_<artifact_key>.csv`` y
  ejecución de ``epiforecast.runner.orchestrator.validate_data``.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any

import camelot
import pandas as pd
from pypdf import PdfReader
from scripts.piloto_carbon_alta1.valida_run_v2 import sha256_file
import yaml

from epiforecast import registry
from epiforecast.data import epi_calendar as ec
from epiforecast.data.epi_dataset import build_epi_dataset_v2
from epiforecast.data.epi_dataset_spec import QualityFlag
from epiforecast.data.extraction.cuadro_extractor import (
    _area_pagina,
    _tabla_estatal,
    find_cuadro_page,
    load_group,
)
from epiforecast.data.extraction.cuadro_reparaciones import fila_total
from epiforecast.data.extraction.dengue_extractor import _year_week_from_filename
from epiforecast.data.extraction.pdf_extractor import normalize_number
from epiforecast.runner import orchestrator as orch

CUTOFF_RE = re.compile(
    r"hasta\s+la\s+semana\s+epidemiol[oó]gica\s+(\d{1,2})\s+del?\s+(\d{4})",
    re.IGNORECASE,
)


def _norm_int(v: Any) -> int | None:
    n = normalize_number(v)
    return None if pd.isna(n) else int(n)


def _inspect_one_pdf(task: tuple[str, list[str], list[str], int]) -> dict[str, Any]:
    """Inspecciona un PDF: página, corte impreso, columnas, TOTAL y contraste con vecinos."""
    pdf_path, anchors, markers, lag = task
    fname = Path(pdf_path).name
    yr, wk = _year_week_from_filename(pdf_path)
    if yr is None or wk is None:
        return {"file": fname, "status": "bad_filename"}

    page = find_cuadro_page(pdf_path, anchors, markers)
    if page is None:
        return {"file": fname, "year": yr, "week": wk, "status": "no_page"}

    reader = PdfReader(pdf_path)
    text = reader.pages[page - 1].extract_text() or ""
    m = CUTOFF_RE.search(text)
    printed_target = [int(m.group(2)), int(m.group(1))] if m else None
    tp = ec.target_period(yr, wk, lag)
    mmwr_target = [tp.epi_year, tp.epi_week]
    lag_matches_mmwr = printed_target == mmwr_target if printed_target is not None else None

    tables = camelot.read_pdf(pdf_path, pages=str(page), flavor="stream")
    raw_tbl = max((t.df for t in tables), key=len) if tables else None
    tot_vals = fila_total(raw_tbl) if raw_tbl is not None else None

    df_clean = _tabla_estatal(pdf_path, page)
    if df_clean is not None and len(df_clean) < 32:
        amp = _tabla_estatal(pdf_path, page, edge_tol=500)
        if amp is not None and len(amp) == 32:
            df_clean = amp
    if df_clean is not None and len(df_clean) < 32:
        area = _area_pagina(pdf_path, page)
        comp = _tabla_estatal(pdf_path, page, table_areas=[area]) if area else None
        if comp is not None and len(comp) == 32:
            df_clean = comp

    if df_clean is None:
        return {
            "file": fname,
            "year": yr,
            "week": wk,
            "page": page,
            "status": "no_table",
            "printed_target": printed_target,
            "mmwr_target": mmwr_target,
            "lag_matches_mmwr": lag_matches_mmwr,
        }

    data_cols = int(df_clean.shape[1] - 1)
    n_states = int(len(df_clean))
    if data_cols != 12 or n_states != 32:
        return {
            "file": fname,
            "year": yr,
            "week": wk,
            "page": page,
            "status": "unexpected_shape",
            "data_cols": data_cols,
            "n_states": n_states,
            "printed_target": printed_target,
            "mmwr_target": mmwr_target,
            "lag_matches_mmwr": lag_matches_mmwr,
        }

    def block_matrix(start_col: int) -> list[list[int | None]]:
        return [
            [_norm_int(df_clean.iloc[r_idx, c_idx]) for c_idx in range(start_col, start_col + 4)]
            for r_idx in range(32)
        ]

    mat_a50 = block_matrix(1)
    mat_a51 = block_matrix(5)
    mat_a54 = block_matrix(9)

    sum_a50 = [sum(row[k] or 0 for row in mat_a50) for k in range(4)]
    sum_a51 = [sum(row[k] or 0 for row in mat_a51) for k in range(4)]
    sum_a54 = [sum(row[k] or 0 for row in mat_a54) for k in range(4)]

    missing_cells_a51 = sum(1 for row in mat_a51 for v in row if v is None)
    diff_cells_vs_a50 = sum(
        1 for r_i in range(32) for k in range(4) if mat_a51[r_i][k] != mat_a50[r_i][k]
    )
    diff_cells_vs_a54 = sum(
        1 for r_i in range(32) for k in range(4) if mat_a51[r_i][k] != mat_a54[r_i][k]
    )

    total_row_status = "sin_total_12"
    printed_mid: list[int] | None = None
    if tot_vals is not None and len(tot_vals) == 12:
        printed_mid = [int(v) for v in tot_vals[4:8]]
        total_row_status = "coincide" if printed_mid == sum_a51 else "difiere"

    return {
        "file": fname,
        "year": yr,
        "week": wk,
        "page": page,
        "status": "ok",
        "data_cols": data_cols,
        "n_states": n_states,
        "printed_target": printed_target,
        "mmwr_target": mmwr_target,
        "lag_matches_mmwr": lag_matches_mmwr,
        "sum_a50": sum_a50,
        "sum_a51": sum_a51,
        "sum_a54": sum_a54,
        "printed_total_a51": printed_mid,
        "total_row_status": total_row_status,
        "missing_cells_a51": missing_cells_a51,
        "diff_cells_vs_a50": diff_cells_vs_a50,
        "diff_cells_vs_a54": diff_cells_vs_a54,
        "identical_to_a50": mat_a51 == mat_a50,
        "identical_to_a54": mat_a51 == mat_a54,
    }


def _compute_raw_negative_deltas(raw_df: pd.DataFrame) -> dict[str, Any]:
    """Cuenta deltas negativos crudos en Acumulado_hombres y Acumulado_mujeres dentro del mismo año."""
    df = raw_df.copy()
    df["Anio"] = pd.to_numeric(df["Anio"], errors="coerce")
    df["Semana_num"] = pd.to_numeric(df["Semana"], errors="coerce")
    df["Acumulado_hombres"] = pd.to_numeric(df["Acumulado_hombres"], errors="coerce")
    df["Acumulado_mujeres"] = pd.to_numeric(df["Acumulado_mujeres"], errors="coerce")
    df = df.sort_values(["Entidad", "Anio", "Semana_num"]).reset_index(drop=True)

    neg_h = 0
    neg_m = 0
    total_transitions = 0
    for (_, _), grp in df.groupby(["Entidad", "Anio"], sort=False):
        dh = grp["Acumulado_hombres"].diff().dropna()
        dm = grp["Acumulado_mujeres"].diff().dropna()
        total_transitions += int(len(dh))
        neg_h += int((dh < 0).sum())
        neg_m += int((dm < 0).sum())

    raw_minus_one_2025 = int(
        ((df["Anio"] == 2025) & (df["Casos_semana"].astype(str).str.strip() == "-1")).sum()
    )
    return {
        "intra_year_state_transitions": total_transitions,
        "raw_negative_deltas_hombres": neg_h,
        "raw_negative_deltas_mujeres": neg_m,
        "raw_casos_semana_minus_one_in_source_2025": raw_minus_one_2025,
    }


def run_qa_report(
    *,
    disease_id: str,
    canon_csv: Path,
    pdf_dir: Path,
    worktree: Path,
    out_json: Path,
    out_md: Path,
    jobs: int = 4,
    run_validate_data: bool = True,
) -> dict[str, Any]:
    """Ejecuta las mediciones C6, C7 y C8 y escribe reporte JSON y Markdown."""
    wt = worktree.resolve()
    spec_reg = registry.require(disease_id)
    grp = load_group(spec_reg.extraction_group)
    excl_files = {
        str(e["file"])
        for e in (grp.get("source_exclusions") or [])
        if disease_id in e.get("diseases", [])
    }
    pdfs = [str(p) for p in sorted(pdf_dir.resolve().glob("*.pdf")) if p.name not in excl_files]
    tasks = [
        (
            p,
            list(grp["page_anchors"]),
            list(grp["state_markers"]),
            int(grp["observation_lag_weeks"]),
        )
        for p in pdfs
    ]

    if jobs <= 1:
        pdf_rows = list(map(_inspect_one_pdf, tasks))
    else:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            pdf_rows = list(ex.map(_inspect_one_pdf, tasks, chunksize=4))

    raw_df = pd.read_csv(canon_csv, dtype={"Semana": str}, low_memory=False)
    raw_sha = sha256_file(canon_csv)

    raw_by_yw: dict[tuple[int, int], list[int]] = {}
    for (y_key, w_key), grp_yw in raw_df.dropna(subset=["Casos_semana"]).groupby(
        ["Anio", "Semana"]
    ):
        raw_by_yw[(int(str(y_key)), int(str(w_key)))] = [
            int(pd.to_numeric(grp_yw["Casos_semana"], errors="coerce").fillna(0).sum()),
            int(pd.to_numeric(grp_yw["Acumulado_hombres"], errors="coerce").fillna(0).sum()),
            int(pd.to_numeric(grp_yw["Acumulado_mujeres"], errors="coerce").fillna(0).sum()),
            int(pd.to_numeric(grp_yw["Acumulado_anio_anterior"], errors="coerce").fillna(0).sum()),
        ]

    total_status_counts: Counter[str] = Counter()
    raw_vs_camelot_mismatch: list[str] = []
    lag_mismatch_files: list[dict[str, Any]] = []
    lag_unparsed_files: list[str] = []
    identical_a50_files: list[str] = []
    identical_a54_files: list[str] = []
    total_diff_cells_a50 = 0
    total_diff_cells_a54 = 0
    total_cells_compared = 0
    total_missing_cells = 0
    pages_by_year: dict[int, set[int]] = {}
    cols_counter: Counter[int] = Counter()

    for r in pdf_rows:
        if r.get("status") != "ok":
            total_status_counts[str(r.get("status"))] += 1
            continue
        yr, wk = int(r["year"]), int(r["week"])
        pages_by_year.setdefault(yr, set()).add(int(r["page"]))
        cols_counter[int(r["data_cols"])] += 1
        total_status_counts[str(r["total_row_status"])] += 1
        if raw_by_yw.get((yr, wk)) != r["sum_a51"]:
            raw_vs_camelot_mismatch.append(r["file"])
        if r["lag_matches_mmwr"] is False:
            lag_mismatch_files.append(
                {
                    "file": r["file"],
                    "printed_target": r["printed_target"],
                    "mmwr_target": r["mmwr_target"],
                }
            )
        elif r["lag_matches_mmwr"] is None:
            lag_unparsed_files.append(r["file"])
        if r["identical_to_a50"]:
            identical_a50_files.append(r["file"])
        if r["identical_to_a54"]:
            identical_a54_files.append(r["file"])
        total_diff_cells_a50 += int(r["diff_cells_vs_a50"])
        total_diff_cells_a54 += int(r["diff_cells_vs_a54"])
        total_cells_compared += 32 * 4
        total_missing_cells += int(r["missing_cells_a51"])

    raw_deltas_info = _compute_raw_negative_deltas(raw_df)

    raw_dest = wt / "data" / "raw" / f"data_raw_{spec_reg.artifact_key}.csv"
    dataset_manifest_info: dict[str, Any] = {"executed": False}
    if run_validate_data:
        raw_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(canon_csv, raw_dest)
        if sha256_file(raw_dest) != raw_sha:
            raise RuntimeError("SHA-256 de data/raw no coincide con canon_csv")
        dm = orch.validate_data(disease_id)
        dataset_manifest_info = {
            "executed": True,
            "raw_dest_path": str(raw_dest),
            "raw_dest_sha256": sha256_file(raw_dest),
            "dataset_id": dm.dataset_id,
            "code_commit": dm.code_commit,
            "digests": dm.digests,
            "counts": dm.counts,
        }
        ds_df = pd.read_csv(wt / "runs" / dm.dataset_id / "epi_dataset_v2.csv", low_memory=False)
    else:
        res_ds = build_epi_dataset_v2(
            disease_id,
            runs_root=out_json.parent / "_tmp_qa_runs",
            raw_path=canon_csv,
        )
        ds_df = res_ds.dataset

    policy_cfg = yaml.safe_load(
        (wt / "config" / "evaluation" / "rolling_cv_v1.yaml").read_text(encoding="utf-8")
    )
    min_train_req = int(policy_cfg["min_train_weeks"])

    periods = (
        ds_df[["epi_year", "epi_week"]]
        .drop_duplicates()
        .sort_values(["epi_year", "epi_week"])
        .reset_index(drop=True)
    )
    first_period = [int(periods.iloc[0]["epi_year"]), int(periods.iloc[0]["epi_week"])]
    last_period = [int(periods.iloc[-1]["epi_year"]), int(periods.iloc[-1]["epi_week"])]

    fold_years = [int(f["epi_year"]) for f in policy_cfg["folds"]["development"]] + [
        int(f["epi_year"]) for f in policy_cfg["folds"]["test"]
    ]
    train_weeks_before_fold: dict[str, dict[str, Any]] = {}
    for fy in fold_years:
        n_before = int((periods["epi_year"] < fy).sum())
        train_weeks_before_fold[str(fy)] = {
            "train_weeks": n_before,
            "min_train_weeks_policy": min_train_req,
            "meets_min_train_weeks": n_before >= min_train_req,
        }

    series_stats: list[dict[str, Any]] = []
    for (cve, sexo), grp_s in ds_df.groupby(["cve_ent", "sexo"], sort=True):
        y_vals = pd.to_numeric(grp_s["y_cases"], errors="coerce").fillna(0)
        n_obs = int(len(y_vals))
        n_zero = int((y_vals == 0).sum())
        series_stats.append(
            {
                "cve_ent": str(cve),
                "entidad": str(grp_s["entidad_canonica"].iloc[0]),
                "sexo": str(sexo),
                "n_weeks": n_obs,
                "zero_weeks": n_zero,
                "zero_fraction": round(n_zero / n_obs, 6) if n_obs else 0.0,
                "median_weekly": float(y_vals.median()),
                "mean_weekly": round(float(y_vals.mean()), 4),
                "p90_weekly": float(y_vals.quantile(0.9)),
                "max_weekly": int(y_vals.max()),
            }
        )
    zero_fracs = sorted(s["zero_fraction"] for s in series_stats)
    medians = sorted(s["median_weekly"] for s in series_stats)

    qflags = ds_df["quality_flags"].fillna("").astype(str)

    def has_flag(flg: str) -> pd.Series[bool]:
        return qflags.apply(lambda s: flg in s.split("|") if s else False)

    imputed_mask = has_flag(QualityFlag.TOTAL_IMPUTED)
    ds_2025 = ds_df[ds_df["epi_year"] == 2025]
    qflags_2025 = ds_2025["quality_flags"].fillna("").astype(str)
    imputed_2025 = int(
        qflags_2025.apply(
            lambda s: QualityFlag.TOTAL_IMPUTED in s.split("|") if s else False
        ).sum()
    )
    weeks_2025_present = int(ds_2025[["epi_year", "epi_week"]].drop_duplicates().shape[0])
    rows_2025_present = int(len(ds_2025))

    annual_totals: list[dict[str, Any]] = []
    for yr_key, grp_y in ds_df.groupby("epi_year", sort=True):
        yr_int = int(str(yr_key))
        h_sum = int(grp_y.loc[grp_y["sexo"] == "hombres", "y_cases"].sum())
        m_sum = int(grp_y.loc[grp_y["sexo"] == "mujeres", "y_cases"].sum())
        n_w = int(grp_y["epi_week"].nunique())
        annual_totals.append(
            {
                "epi_year": yr_int,
                "weeks_observed": n_w,
                "canonical_weeks_in_year": ec.weeks_in_year(yr_int),
                "y_hombres": h_sum,
                "y_mujeres": m_sum,
                "y_total": h_sum + m_sum,
            }
        )

    mmwr_years = {
        str(y): ec.weeks_in_year(y)
        for y in (2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026)
    }

    report: dict[str, Any] = {
        "schema": "piloto_carbon_alta1.qa_serie_extraida.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "disease_id": disease_id,
        "canon_csv_path": str(canon_csv.resolve()),
        "canon_csv_sha256": raw_sha,
        "c6_antibloque_y_total": {
            "non_excluded_pdfs_inspected": len(pdf_rows),
            "excluded_pdfs_declared": sorted(excl_files),
            "data_columns_distribution": {str(k): v for k, v in sorted(cols_counter.items())},
            "pages_range_by_year": {
                str(y): [min(ps), max(ps)] for y, ps in sorted(pages_by_year.items())
            },
            "total_row_comparison_counts": dict(total_status_counts),
            "raw_vs_camelot_sum_mismatches": raw_vs_camelot_mismatch,
            "neighbor_contrast": {
                "denominator_bulletins": int(sum(cols_counter.values())),
                "denominator_state_cells_4col": total_cells_compared,
                "missing_cells_in_target_block": total_missing_cells,
                "bulletins_identical_to_left_A50": identical_a50_files,
                "bulletins_identical_to_right_A54": identical_a54_files,
                "differing_cells_vs_left_A50": total_diff_cells_a50,
                "differing_cells_vs_right_A54": total_diff_cells_a54,
            },
        },
        "c7_calendario_lag_densidad_calidad": {
            "mmwr_weeks_in_year": mmwr_years,
            "historical_lag_verification": {
                "expected_lag_weeks": int(grp["observation_lag_weeks"]),
                "bulletins_checked": int(sum(cols_counter.values())),
                "lag_mismatches_vs_epi_calendar": lag_mismatch_files,
                "header_cutoff_unparsed_files": lag_unparsed_files,
            },
            "series_span": {
                "first_target_period": first_period,
                "last_target_period": last_period,
                "total_target_weeks": int(len(periods)),
                "base_series_count": len(series_stats),
                "total_base_rows": int(len(ds_df)),
            },
            "train_weeks_before_folds": train_weeks_before_fold,
            "target_2025_integrity_no_forecast": {
                "canonical_weeks_2025": ec.weeks_in_year(2025),
                "target_weeks_present_2025": weeks_2025_present,
                "base_rows_present_2025": rows_2025_present,
                "total_imputed_rows_2025": imputed_2025,
                "raw_minus_one_count_source_2025": raw_deltas_info[
                    "raw_casos_semana_minus_one_in_source_2025"
                ],
            },
            "raw_cumulative_deltas": raw_deltas_info,
            "reconciled_quality_flags_rows": {
                "total_imputed": int(imputed_mask.sum()),
                "source_missing": int(has_flag(QualityFlag.SOURCE_MISSING).sum()),
                "negative_source": int(has_flag(QualityFlag.NEGATIVE_SOURCE).sum()),
                "sex_delta_total_mismatch": int(
                    has_flag(QualityFlag.SEX_DELTA_TOTAL_MISMATCH).sum()
                ),
                "sex_fallback_state_13w": int(has_flag(QualityFlag.SEX_FALLBACK_STATE_13W).sum()),
                "sex_fallback_national": int(has_flag(QualityFlag.SEX_FALLBACK_NATIONAL).sum()),
                "sex_fallback_half": int(has_flag(QualityFlag.SEX_FALLBACK_HALF).sum()),
            },
            "weekly_density_summary_64_bases": {
                "min_zero_fraction": zero_fracs[0] if zero_fracs else None,
                "median_zero_fraction": zero_fracs[len(zero_fracs) // 2] if zero_fracs else None,
                "max_zero_fraction": zero_fracs[-1] if zero_fracs else None,
                "min_weekly_median": medians[0] if medians else None,
                "median_weekly_median": medians[len(medians) // 2] if medians else None,
                "max_weekly_median": medians[-1] if medians else None,
                "highest_zero_fraction_series": sorted(
                    series_stats, key=lambda x: x["zero_fraction"], reverse=True
                )[:8],
            },
            "annual_national_reconciled_totals": annual_totals,
            "per_base_series_stats": series_stats,
        },
        "c8_validate_data": dataset_manifest_info,
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    c6 = report["c6_antibloque_y_total"]
    c7 = report["c7_calendario_lag_densidad_calidad"]
    md_lines = [
        f"# Reporte QA de Serie Extraída (`C6`, `C7`, `C8`) — `{disease_id}`",
        "",
        f"- **CSV canónico**: `{canon_csv.resolve()}` (`sha256: {raw_sha}`)",
        f"- **Dataset validado (`C8`)**: `{dataset_manifest_info.get('dataset_id')}` "
        f"(`raw_dest_sha256: {dataset_manifest_info.get('raw_dest_sha256')}`)",
        "",
        "## 1. Guardia anti-bloque y fila `TOTAL` (`C6`)",
        f"- Boletines no excluidos inspeccionados: `{c6['non_excluded_pdfs_inspected']}` "
        f"(excluidos declarados: `{c6['excluded_pdfs_declared']}`)",
        f"- Distribución de ancho de columnas de datos: `{c6['data_columns_distribution']}`",
        f"- Cuadre con renglón `TOTAL` impreso: `{c6['total_row_comparison_counts']}`",
        f"- Boletines idénticos a vecino izquierdo `A50`: "
        f"`{len(c6['neighbor_contrast']['bulletins_identical_to_left_A50'])}` "
        f"(celdas distintas: `{c6['neighbor_contrast']['differing_cells_vs_left_A50']}` / "
        f"`{c6['neighbor_contrast']['denominator_state_cells_4col']}`)",
        f"- Boletines idénticos a vecino derecho `A54.0-A54.2`: "
        f"`{len(c6['neighbor_contrast']['bulletins_identical_to_right_A54'])}` "
        f"(celdas distintas: `{c6['neighbor_contrast']['differing_cells_vs_right_A54']}` / "
        f"`{c6['neighbor_contrast']['denominator_state_cells_4col']}`)",
        "",
        "## 2. Calendario MMWR, rezago histórico, densidad semanal y calidad (`C7`)",
        f"- Rango objetivo: `{c7['series_span']['first_target_period']}` a "
        f"`{c7['series_span']['last_target_period']}` "
        f"(`{c7['series_span']['total_target_weeks']}` semanas, "
        f"`{c7['series_span']['total_base_rows']}` filas base)",
        f"- Discrepancias de rezago impreso vs `epi_calendar`: "
        f"`{len(c7['historical_lag_verification']['lag_mismatches_vs_epi_calendar'])}`",
        f"- Semanas de entrenamiento previas por pliegue: `{c7['train_weeks_before_folds']}`",
        f"- Integridad 2025 (sin pronóstico): `{c7['target_2025_integrity_no_forecast']}`",
        f"- Deltas negativos crudos en acumulados: `{c7['raw_cumulative_deltas']}`",
        f"- Banderas de reconciliación (filas base): `{c7['reconciled_quality_flags_rows']}`",
        f"- Fracción de ceros en las 64 series base (mín / med / máx): "
        f"`{c7['weekly_density_summary_64_bases']['min_zero_fraction']}` / "
        f"`{c7['weekly_density_summary_64_bases']['median_zero_fraction']}` / "
        f"`{c7['weekly_density_summary_64_bases']['max_zero_fraction']}`",
        "",
        "## 3. Nivel anual nacional reconciliado (`2014–2026`)",
        "",
        "| Año | Semanas obs. / MMWR | Hombres | Mujeres | Total |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in annual_totals:
        md_lines.append(
            f"| `{row['epi_year']}` | `{row['weeks_observed']} / {row['canonical_weeks_in_year']}` "
            f"| `{row['y_hombres']:,}` | `{row['y_mujeres']:,}` | `{row['y_total']:,}` |"
        )
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return report


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--disease", default="sifilis_adquirida_a51")
    ap.add_argument("--canon-csv", type=Path, required=True)
    ap.add_argument("--pdf-dir", type=Path, required=True)
    ap.add_argument("--worktree", type=Path, required=True)
    ap.add_argument("--out-json", type=Path, required=True)
    ap.add_argument("--out-md", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--skip-validate-data", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    rep = run_qa_report(
        disease_id=args.disease,
        canon_csv=args.canon_csv,
        pdf_dir=args.pdf_dir,
        worktree=args.worktree,
        out_json=args.out_json,
        out_md=args.out_md,
        jobs=args.jobs,
        run_validate_data=not args.skip_validate_data,
    )
    print(
        f"QA_OK id={rep['disease_id']} weeks={rep['c7_calendario_lag_densidad_calidad']['series_span']['total_target_weeks']} "
        f"dataset_id={rep['c8_validate_data'].get('dataset_id')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
