"""QA cuantitativo post-extracción (C6, C7 y C8; H6 corregido) — piloto Carbon alta1.

Mide sobre el CSV canónico sellado y el corpus PDF sellado (sin crear criterios nuevos ni consultar
métricas de pronóstico de 2025):
- Pines y entorno obligatorios (``H6(g)``): exige ``expected_commit`` (40 hex), ``inventory_json`` y
  ``expected_inventory_sha256`` (64 hex), ``expected_canon_sha256`` (64 hex), ``cwd == worktree``,
  árbol git limpio (incluyendo no rastreados en raíz), ``registry.__file__`` y
  ``orchestrator.__file__`` bajo ``worktree``, y concordancia con ``SHA256SUMS`` / ``CANON_RAW.json``.
- Inspección por PDF tolerante y persistida (``H6(b)``, ``H6(e)``): ``_inspect_one_pdf`` captura
  excepciones como ``status="exception"``, lista archivos por cada estado y persiste
  ``<out_json>_por_pdf.json`` (``0444``) ANTES de ``validate-data``.
- Comparación celda a celda del CSV canónico contra los 3 bloques (``C6`` / ``H6(c)``): compara las
  ``32 × 4 = 128`` celdas por boletín del CSV canónico contra el bloque central ``A51-A53`` y contra
  los vecinos ``A50`` (izq.) y ``A54.0-A54.2`` (der.), además de la fila ``TOTAL`` impresa.
- Trayectoria de acumulados y detector descriptivo de caídas/saltos (``H6(d)``): serie nacional por
  semana de fuente y listado por archivo de caídas, picos revertidos (tipo ``2016_sem20``) y deltas
  estatales negativos, sin umbrales nuevos ni autoexclusión.
- Medición real de ``-1`` crudo y ``NA`` en objetivos 2025 (``H6(a)``): cuenta tokens ``"-1"`` y no
  numéricos directamente en las celdas crudas de Camelot antes de ``normalize_number``, y celdas
  vacías/``NA`` en ``boletin.csv`` (leído con ``dtype=str, keep_default_na=False``) mapeadas por
  ``epi_calendar.target_period`` a ``epi_year == 2025``.
- Copia segura a ``data/raw`` (``H6(f)``): si ``data/raw/data_raw_<key>.csv`` ya existe con el mismo
  SHA-256 hace no-op verificado sin ``PermissionError``; si difiere, rehúsa sobrescribir.
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
import stat
import sys
from typing import Any

import camelot
import pandas as pd
from pypdf import PdfReader
from scripts.piloto_carbon_alta1 import valida_run_v2 as vr
import yaml

from epiforecast import registry
from epiforecast.data import epi_calendar as ec
from epiforecast.data.epi_dataset import build_epi_dataset_v2
from epiforecast.data.epi_dataset_spec import QualityFlag
from epiforecast.data.epi_geo_exposure import load_geo_catalog
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


def _set_readonly(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def _norm_int(v: Any) -> int | None:
    n = normalize_number(v)
    return None if pd.isna(n) else int(n)


def _parse_csv_cell_str(raw_val: str) -> int | None:
    s = raw_val.strip()
    if not s:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f.is_integer() and f >= 0 else None


def inspect_one_pdf(task: tuple[str, list[str], list[str], int]) -> dict[str, Any]:
    """Inspecciona un PDF con captura de excepciones por archivo (H6(a), H6(b), H6(c))."""
    pdf_path, anchors, markers, lag = task
    fname = Path(pdf_path).name
    yr, wk = _year_week_from_filename(pdf_path)
    if yr is None or wk is None:
        return {"file": fname, "year": yr, "week": wk, "status": "bad_filename"}

    try:
        catalog = load_geo_catalog()
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

        cells_a50: dict[str, list[int | None]] = {}
        cells_a51: dict[str, list[int | None]] = {}
        cells_a54: dict[str, list[int | None]] = {}
        raw_minus_one_a51: list[dict[str, Any]] = []
        raw_non_numeric_a51: list[dict[str, Any]] = []

        for r_idx in range(32):
            state_raw = str(df_clean.iloc[r_idx, 0])
            cve = catalog.resolve(state_raw)
            cells_a50[cve] = [_norm_int(df_clean.iloc[r_idx, c]) for c in range(1, 5)]
            row_51: list[int | None] = []
            for offset, c in enumerate(range(5, 9)):
                raw_tok = str(df_clean.iloc[r_idx, c]).strip()
                norm_v = _norm_int(raw_tok)
                row_51.append(norm_v)
                if raw_tok == "-1":
                    raw_minus_one_a51.append({"cve_ent": cve, "col_offset": offset})
                if raw_tok not in ("", "-") and norm_v is None:
                    raw_non_numeric_a51.append(
                        {"cve_ent": cve, "col_offset": offset, "raw_token": raw_tok}
                    )
            cells_a51[cve] = row_51
            cells_a54[cve] = [_norm_int(df_clean.iloc[r_idx, c]) for c in range(9, 13)]

        tot_12: list[int] | None = None
        if tot_vals is not None and len(tot_vals) == 12:
            tot_12 = [int(v) for v in tot_vals]

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
            "cells_a50": cells_a50,
            "cells_a51": cells_a51,
            "cells_a54": cells_a54,
            "printed_total_12": tot_12,
            "raw_minus_one_a51": raw_minus_one_a51,
            "raw_non_numeric_a51": raw_non_numeric_a51,
        }
    except Exception as exc:  # noqa: BLE001 - capturar y persistir por PDF sin abortar lote (H6(b))
        return {
            "file": fname,
            "year": yr,
            "week": wk,
            "status": "exception",
            "error": f"{type(exc).__name__}: {exc}",
        }


def stage_raw_for_validate_data(canon_csv: Path, raw_dest: Path, expected_sha256: str) -> str:
    """Copia canon_csv a data/raw o verifica no-op si ya existe idéntico; rehúsa si difiere (H6(f))."""
    if raw_dest.exists():
        curr_sha = vr.sha256_file(raw_dest)
        if curr_sha == expected_sha256:
            return "verified_existing_noop"
        raise RuntimeError(
            f"data/raw existente ({raw_dest}) tiene sha256 {curr_sha} != {expected_sha256}; "
            "se rehúsa sobrescribir."
        )
    raw_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(canon_csv, raw_dest)
    _set_readonly(raw_dest)
    if vr.sha256_file(raw_dest) != expected_sha256:
        raise RuntimeError("SHA-256 de data/raw copiado no coincide con expected_sha256")
    return "copied_and_sealed_readonly"


def verify_qa_preconditions(
    *,
    disease_id: str,
    canon_csv: Path,
    expected_canon_sha256: str,
    pdf_dir: Path,
    inventory_json: Path,
    expected_inventory_sha256: str,
    worktree: Path,
    expected_commit: str,
    check_cwd_and_imports: bool = True,
) -> dict[str, Any]:
    """Verifica todos los pines, limpieza git, cwd e imports antes de ejecutar QA (H6(g))."""
    wt = worktree.resolve()
    if not vr.HEX40_RE.fullmatch(expected_commit or ""):
        raise RuntimeError("expected_commit ausente o no es SHA de 40 hex")
    if not vr.HEX64_RE.fullmatch(expected_inventory_sha256 or ""):
        raise RuntimeError("expected_inventory_sha256 ausente o no es SHA-256 de 64 hex")
    if not vr.HEX64_RE.fullmatch(expected_canon_sha256 or ""):
        raise RuntimeError("expected_canon_sha256 ausente o no es SHA-256 de 64 hex")

    if check_cwd_and_imports:
        actual_cwd = Path.cwd().resolve()
        if actual_cwd != wt:
            raise RuntimeError(f"cwd actual ({actual_cwd}) != worktree ({wt})")
        reg_file = Path(registry.__file__).resolve()
        orch_file = Path(orch.__file__).resolve()
        expected_reg = (wt / "src" / "epiforecast" / "registry.py").resolve()
        expected_orch = (wt / "src" / "epiforecast" / "runner" / "orchestrator.py").resolve()
        if reg_file != expected_reg:
            raise RuntimeError(f"registry.__file__ ({reg_file}) != {expected_reg}")
        if orch_file != expected_orch:
            raise RuntimeError(f"orchestrator.__file__ ({orch_file}) != {expected_orch}")

    head40 = vr.git_head_40(wt)
    if head40 != expected_commit:
        raise RuntimeError(f"HEAD ({head40}) != expected_commit ({expected_commit})")
    dirty = vr.git_dirty_entries(wt)
    if dirty:
        raise RuntimeError(f"Worktree sucio antes de QA: {dirty}")

    inv_fallas, inv_meta = vr.verify_pdf_inventory(
        pdf_dir,
        inventory_json,
        expected_inventory_sha256=expected_inventory_sha256,
    )
    if inv_fallas:
        raise RuntimeError(f"Inventario PDF inválido en QA: {inv_fallas}")

    actual_canon_sha = vr.sha256_file(canon_csv)
    if actual_canon_sha != expected_canon_sha256:
        raise RuntimeError(
            f"canon_csv sha256 ({actual_canon_sha}) != expected_canon_sha256 "
            f"({expected_canon_sha256})"
        )

    canon_dir = canon_csv.resolve().parent
    sums_path = canon_dir / "SHA256SUMS"
    canon_raw_json = canon_dir / f"{disease_id}_CANON_RAW.json"
    canon_provenance: dict[str, Any] = {
        "sums_verified": False,
        "canon_raw_json_verified": False,
    }
    if sums_path.is_file():
        expected_line = f"{expected_canon_sha256}  {canon_csv.name}"
        if expected_line not in sums_path.read_text(encoding="utf-8").splitlines():
            raise RuntimeError(f"{sums_path} no contiene la línea esperada para {canon_csv.name}")
        canon_provenance["sums_verified"] = True
    if canon_raw_json.is_file():
        cr_doc = json.loads(canon_raw_json.read_text(encoding="utf-8"))
        if (
            cr_doc.get("valida") is not True
            or cr_doc.get("raw_sha256") != expected_canon_sha256
            or cr_doc.get("snapshot_sha") != expected_commit
        ):
            raise RuntimeError(f"{canon_raw_json} no concuerda con los pines de QA")
        canon_provenance["canon_raw_json_verified"] = True
        canon_provenance["canon_raw_json_sha256"] = vr.sha256_file(canon_raw_json)

    return {
        "worktree": str(wt),
        "commit_sha40": head40,
        "cwd": str(Path.cwd().resolve()),
        "registry_file": str(Path(registry.__file__).resolve()),
        "orchestrator_file": str(Path(orch.__file__).resolve()),
        "qa_script_file": str(Path(__file__).resolve()),
        "qa_script_sha256": vr.sha256_file(Path(__file__).resolve()),
        "inventory_json": inv_meta["inventory_json"],
        "inventory_sha256": inv_meta["inventory_sha256"],
        "pdf_count": inv_meta["count"],
        "canon_csv": str(canon_csv.resolve()),
        "canon_csv_sha256": actual_canon_sha,
        "canon_provenance": canon_provenance,
    }


def analyze_canon_csv_cells_and_trajectories(
    canon_csv: Path,
    *,
    lag: int,
    keep_period_files: set[str],
) -> tuple[dict[tuple[int, int], dict[str, list[int | None]]], dict[str, Any]]:
    """Lee canon_csv como texto crudo, mide NA/-1 en objetivos 2025 y trayectorias de acumulados."""
    catalog = load_geo_catalog()
    raw_str_df = pd.read_csv(canon_csv, dtype=str, keep_default_na=False)
    value_cols = (
        "Casos_semana",
        "Acumulado_hombres",
        "Acumulado_mujeres",
        "Acumulado_anio_anterior",
    )

    canon_lookup: dict[tuple[int, int], dict[str, list[int | None]]] = {}
    na_2025_by_col: Counter[str] = Counter()
    na_2025_details: list[dict[str, Any]] = []
    literal_minus_one_csv_2025: list[dict[str, Any]] = []
    target_weeks_2025_seen: set[int] = set()

    parsed_rows: list[dict[str, Any]] = []
    for row in raw_str_df.to_dict(orient="records"):
        yr = int(str(row["Anio"]).strip())
        wk = int(str(row["Semana"]).strip())
        fname = f"{yr}_sem{wk:02d}.pdf"
        cve = catalog.resolve(str(row["Entidad"]))
        tp = ec.target_period(yr, wk, lag)
        vals = [_parse_csv_cell_str(str(row[c])) for c in value_cols]

        if fname not in keep_period_files:
            canon_lookup.setdefault((yr, wk), {})[cve] = vals

        if tp.epi_year == 2025:
            target_weeks_2025_seen.add(tp.epi_week)
            for c_name, parsed_v in zip(value_cols, vals, strict=True):
                raw_cell = str(row[c_name]).strip()
                if raw_cell == "-1":
                    literal_minus_one_csv_2025.append(
                        {"source_file": fname, "cve_ent": cve, "col": c_name}
                    )
                if parsed_v is None:
                    na_2025_by_col[c_name] += 1
                    if len(na_2025_details) < 100:
                        na_2025_details.append(
                            {
                                "source_file": fname,
                                "target_period": [tp.epi_year, tp.epi_week],
                                "cve_ent": cve,
                                "entidad": row["Entidad"],
                                "col": c_name,
                                "raw_value": raw_cell,
                            }
                        )

        parsed_rows.append(
            {
                "file": fname,
                "Anio": yr,
                "Semana": wk,
                "cve_ent": cve,
                "Entidad": str(row["Entidad"]),
                "sem": vals[0],
                "acum_h": vals[1],
                "acum_m": vals[2],
                "acum_prev": vals[3],
                "is_keep_period": fname in keep_period_files,
            }
        )

    p_df = pd.DataFrame(parsed_rows)
    obs_df = p_df[~p_df["is_keep_period"]].copy()

    # Deltas estatales negativos dentro del mismo año de fuente (listados por archivo)
    obs_df = obs_df.sort_values(["cve_ent", "Anio", "Semana"]).reset_index(drop=True)
    state_neg_events: list[dict[str, Any]] = []
    state_neg_files: set[str] = set()
    neg_h_count = 0
    neg_m_count = 0
    total_state_transitions = 0
    for (_, _), grp in obs_df.groupby(["cve_ent", "Anio"], sort=False):
        recs = grp.to_dict(orient="records")
        for idx in range(1, len(recs)):
            prev_r, curr_r = recs[idx - 1], recs[idx]
            total_state_transitions += 1
            for key_col, label in (("acum_h", "hombres"), ("acum_m", "mujeres")):
                pv, cv = prev_r[key_col], curr_r[key_col]
                if pv is not None and cv is not None and cv < pv:
                    if label == "hombres":
                        neg_h_count += 1
                    else:
                        neg_m_count += 1
                    state_neg_files.add(str(curr_r["file"]))
                    if len(state_neg_events) < 100:
                        state_neg_events.append(
                            {
                                "file": curr_r["file"],
                                "prev_file": prev_r["file"],
                                "cve_ent": curr_r["cve_ent"],
                                "entidad": curr_r["Entidad"],
                                "sexo": label,
                                "prev_acum": int(pv),
                                "curr_acum": int(cv),
                                "delta": int(cv - pv),
                            }
                        )

    # Serie nacional por semana de fuente dentro de cada año: caídas y picos revertidos (H6(d))
    nat_rows: list[dict[str, Any]] = []
    for (yr_k, wk_k), grp_yw in obs_df.groupby(["Anio", "Semana"], sort=True):
        yr_i, wk_i = int(str(yr_k)), int(str(wk_k))
        s_sem = int(grp_yw["sem"].fillna(0).sum())
        s_h = int(grp_yw["acum_h"].fillna(0).sum())
        s_m = int(grp_yw["acum_m"].fillna(0).sum())
        s_prev = int(grp_yw["acum_prev"].fillna(0).sum())
        nat_rows.append(
            {
                "file": f"{yr_i}_sem{wk_i:02d}.pdf",
                "year": yr_i,
                "week": wk_i,
                "sem": s_sem,
                "acum_h": s_h,
                "acum_m": s_m,
                "acum_total": s_h + s_m,
                "acum_prev": s_prev,
            }
        )

    nat_drops: list[dict[str, Any]] = []
    nat_spikes_reverted: list[dict[str, Any]] = []
    weekly_increments: list[dict[str, Any]] = []
    sem_vs_delta_gaps: list[dict[str, Any]] = []

    by_year: dict[int, list[dict[str, Any]]] = {}
    for nr in nat_rows:
        by_year.setdefault(int(nr["year"]), []).append(nr)

    for _yr, seq in sorted(by_year.items()):
        for idx in range(1, len(seq)):
            p, c = seq[idx - 1], seq[idx]
            dh = c["acum_h"] - p["acum_h"]
            dm = c["acum_m"] - p["acum_m"]
            dt = c["acum_total"] - p["acum_total"]
            dp = c["acum_prev"] - p["acum_prev"]
            inc_entry = {
                "file": c["file"],
                "prev_file": p["file"],
                "sem_printed": c["sem"],
                "delta_acum_h": dh,
                "delta_acum_m": dm,
                "delta_acum_total": dt,
                "delta_acum_prev": dp,
                "sem_minus_delta_total": c["sem"] - dt,
                "prev_acum_total": p["acum_total"],
                "curr_acum_total": c["acum_total"],
            }
            weekly_increments.append(inc_entry)
            sem_vs_delta_gaps.append(inc_entry)
            if dh < 0 or dm < 0 or dt < 0 or dp < 0:
                nat_drops.append(inc_entry)
        for idx in range(1, len(seq) - 1):
            p, c, n = seq[idx - 1], seq[idx], seq[idx + 1]
            if (p["acum_total"] < c["acum_total"] and c["acum_total"] > n["acum_total"]) or (
                p["acum_total"] > c["acum_total"] and c["acum_total"] < n["acum_total"]
            ):
                nat_spikes_reverted.append(
                    {
                        "file": c["file"],
                        "prev_file": p["file"],
                        "next_file": n["file"],
                        "triplet_acum_total": [
                            p["acum_total"],
                            c["acum_total"],
                            n["acum_total"],
                        ],
                        "triplet_sem": [p["sem"], c["sem"], n["sem"]],
                    }
                )

    top_jumps = sorted(weekly_increments, key=lambda x: x["delta_acum_total"], reverse=True)[:10]
    top_gaps = sorted(
        sem_vs_delta_gaps, key=lambda x: abs(int(x["sem_minus_delta_total"])), reverse=True
    )[:10]

    diagnostics = {
        "target_2025_csv_na_and_minus_one": {
            "extractor_note": (
                "pdf_extractor.normalize_number convierte '-1' y tokens no numéricos ('s.n.', "
                "'n.e.') en pd.NA (cadena vacía en boletin.csv). Por ello se auditan tanto las "
                "celdas vacías/NA en boletin.csv que mapean a objetivos 2025 como los tokens "
                "crudos '-1'/no-numéricos directamente en Camelot antes de normalize_number."
            ),
            "target_weeks_2025_mapped_from_csv": len(target_weeks_2025_seen),
            "na_counts_by_column_in_2025_targets": {c: int(na_2025_by_col[c]) for c in value_cols},
            "na_total_cells_in_2025_targets": int(sum(na_2025_by_col.values())),
            "na_cells_sample_in_2025_targets": na_2025_details,
            "literal_minus_one_strings_in_csv_2025": literal_minus_one_csv_2025,
        },
        "cumulative_trajectories_and_anomalies": {
            "intra_year_state_transitions": total_state_transitions,
            "raw_negative_deltas_hombres": neg_h_count,
            "raw_negative_deltas_mujeres": neg_m_count,
            "state_negative_delta_files": sorted(state_neg_files),
            "state_negative_deltas_sample": state_neg_events,
            "national_cumulative_drops_by_file": nat_drops,
            "national_spike_or_drop_reverted_triplets": nat_spikes_reverted,
            "top_10_weekly_acum_total_jumps": top_jumps,
            "top_10_abs_sem_minus_delta_acum_total": top_gaps,
            "national_series_by_source_week": nat_rows,
        },
    }
    return canon_lookup, diagnostics


def compare_canon_against_pdf_blocks(
    canon_lookup: dict[tuple[int, int], dict[str, list[int | None]]],
    pdf_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compara el CSV canónico celda a celda contra los 3 bloques de cada boletín (H6(c), H6(e))."""
    files_by_status: dict[str, list[str]] = {
        "ok": [],
        "no_page": [],
        "no_table": [],
        "unexpected_shape": [],
        "exception": [],
        "bad_filename": [],
        "total_coincide": [],
        "total_difiere": [],
        "sin_total_12": [],
        "lag_mismatch": [],
        "header_cutoff_unparsed": [],
    }
    lag_mismatch_details: list[dict[str, Any]] = []
    exception_details: list[dict[str, Any]] = []

    denom_bulletins = 0
    denom_cells = 0
    canon_missing_cells = 0
    pdf_a51_missing_cells = 0
    diff_cells_vs_a51 = 0
    diff_cells_vs_a50 = 0
    diff_cells_vs_a54 = 0
    mismatch_a51_details: list[dict[str, Any]] = []
    canon_eq_a50_files: list[str] = []
    canon_eq_a54_files: list[str] = []
    total_eq_a50_files: list[str] = []
    total_eq_a54_files: list[str] = []

    raw_pdf_minus_one_all: list[dict[str, Any]] = []
    raw_pdf_minus_one_2025: list[dict[str, Any]] = []
    raw_pdf_non_num_2025: list[dict[str, Any]] = []
    cols_counter: Counter[int] = Counter()
    pages_by_year: dict[int, set[int]] = {}

    for r in pdf_rows:
        st = str(r.get("status", "unknown"))
        fname = str(r["file"])
        files_by_status.setdefault(st, []).append(fname)
        if st == "exception":
            exception_details.append({"file": fname, "error": r.get("error")})
        if st != "ok":
            continue

        yr, wk = int(r["year"]), int(r["week"])
        pages_by_year.setdefault(yr, set()).add(int(r["page"]))
        cols_counter[int(r["data_cols"])] += 1

        if r["lag_matches_mmwr"] is False:
            files_by_status["lag_mismatch"].append(fname)
            lag_mismatch_details.append(
                {
                    "file": fname,
                    "printed_target": r["printed_target"],
                    "mmwr_target": r["mmwr_target"],
                }
            )
        elif r["lag_matches_mmwr"] is None:
            files_by_status["header_cutoff_unparsed"].append(fname)

        for item in r["raw_minus_one_a51"]:
            entry = {"file": fname, "mmwr_target": r["mmwr_target"], **item}
            raw_pdf_minus_one_all.append(entry)
            if r["mmwr_target"][0] == 2025:
                raw_pdf_minus_one_2025.append(entry)
        if r["mmwr_target"][0] == 2025:
            for item in r["raw_non_numeric_a51"]:
                raw_pdf_non_num_2025.append(
                    {"file": fname, "mmwr_target": r["mmwr_target"], **item}
                )

        canon_states = canon_lookup.get((yr, wk))
        if canon_states is None or len(canon_states) != 32:
            mismatch_a51_details.append(
                {"file": fname, "reason": "boletín ausente o sin 32 entidades en canon_csv"}
            )
            diff_cells_vs_a51 += 128
            continue

        denom_bulletins += 1
        denom_cells += 128
        bul_diff_a51 = 0
        bul_diff_a50 = 0
        bul_diff_a54 = 0

        for cve in sorted(canon_states):
            c_row = canon_states[cve]
            p_51 = r["cells_a51"].get(cve, [None, None, None, None])
            p_50 = r["cells_a50"].get(cve, [None, None, None, None])
            p_54 = r["cells_a54"].get(cve, [None, None, None, None])
            for k in range(4):
                if c_row[k] is None:
                    canon_missing_cells += 1
                if p_51[k] is None:
                    pdf_a51_missing_cells += 1
                if c_row[k] != p_51[k]:
                    bul_diff_a51 += 1
                    if len(mismatch_a51_details) < 50:
                        mismatch_a51_details.append(
                            {
                                "file": fname,
                                "cve_ent": cve,
                                "col_offset": k,
                                "canon_val": c_row[k],
                                "pdf_a51_val": p_51[k],
                            }
                        )
                if c_row[k] != p_50[k]:
                    bul_diff_a50 += 1
                if c_row[k] != p_54[k]:
                    bul_diff_a54 += 1

        diff_cells_vs_a51 += bul_diff_a51
        diff_cells_vs_a50 += bul_diff_a50
        diff_cells_vs_a54 += bul_diff_a54
        if bul_diff_a50 == 0:
            canon_eq_a50_files.append(fname)
        if bul_diff_a54 == 0:
            canon_eq_a54_files.append(fname)

        canon_sum_4 = [sum(canon_states[cve][k] or 0 for cve in canon_states) for k in range(4)]
        tot_12 = r["printed_total_12"]
        if tot_12 is None:
            files_by_status["sin_total_12"].append(fname)
        else:
            if canon_sum_4 == tot_12[4:8]:
                files_by_status["total_coincide"].append(fname)
            else:
                files_by_status["total_difiere"].append(fname)
            if canon_sum_4 == tot_12[0:4]:
                total_eq_a50_files.append(fname)
            if canon_sum_4 == tot_12[8:12]:
                total_eq_a54_files.append(fname)

    return {
        "files_by_status": {k: sorted(v) for k, v in files_by_status.items()},
        "status_counts": {k: len(v) for k, v in files_by_status.items()},
        "exception_details": exception_details,
        "data_columns_distribution": {str(k): v for k, v in sorted(cols_counter.items())},
        "pages_range_by_year": {
            str(y): [min(ps), max(ps)] for y, ps in sorted(pages_by_year.items())
        },
        "lag_mismatch_details": lag_mismatch_details,
        "canon_cell_by_cell_contrast": {
            "denominator_bulletins": denom_bulletins,
            "denominator_cells_4col": denom_cells,
            "canon_missing_cells": canon_missing_cells,
            "pdf_a51_missing_cells": pdf_a51_missing_cells,
            "canon_vs_target_a51_diff_cells": diff_cells_vs_a51,
            "canon_vs_target_a51_mismatch_sample": mismatch_a51_details,
            "canon_vs_left_a50_diff_cells": diff_cells_vs_a50,
            "bulletins_where_canon_equals_left_a50": canon_eq_a50_files,
            "canon_vs_right_a54_diff_cells": diff_cells_vs_a54,
            "bulletins_where_canon_equals_right_a54": canon_eq_a54_files,
            "bulletins_where_canon_sum_equals_printed_total_a50": total_eq_a50_files,
            "bulletins_where_canon_sum_equals_printed_total_a54": total_eq_a54_files,
        },
        "raw_pdf_tokens_before_normalize_number": {
            "raw_minus_one_cells_all_years": raw_pdf_minus_one_all,
            "raw_minus_one_cells_target_2025": raw_pdf_minus_one_2025,
            "raw_non_numeric_cells_target_2025": raw_pdf_non_num_2025,
        },
    }


def run_qa_report(
    *,
    disease_id: str,
    canon_csv: Path,
    expected_canon_sha256: str,
    pdf_dir: Path,
    inventory_json: Path,
    expected_inventory_sha256: str,
    worktree: Path,
    expected_commit: str,
    out_json: Path,
    out_md: Path,
    jobs: int = 4,
    run_validate_data: bool = True,
    check_cwd_and_imports: bool = True,
) -> dict[str, Any]:
    """Ejecuta las mediciones C6, C7 y C8 con persistencia intermedia y pines obligatorios."""
    out_pdf_detail_json = out_json.with_name(f"{out_json.stem}_por_pdf.json")
    for out_p in (out_json, out_md, out_pdf_detail_json):
        if out_p.exists():
            raise RuntimeError(
                f"El archivo de salida QA ya existe ({out_p}); use una ruta nueva para no "
                "sobrescribir evidencia previa."
            )

    provenance = verify_qa_preconditions(
        disease_id=disease_id,
        canon_csv=canon_csv,
        expected_canon_sha256=expected_canon_sha256,
        pdf_dir=pdf_dir,
        inventory_json=inventory_json,
        expected_inventory_sha256=expected_inventory_sha256,
        worktree=worktree,
        expected_commit=expected_commit,
        check_cwd_and_imports=check_cwd_and_imports,
    )

    wt = worktree.resolve()
    spec_reg = registry.require(disease_id)
    grp = load_group(spec_reg.extraction_group)
    lag = int(grp["observation_lag_weeks"])
    excl_entries = [
        e for e in (grp.get("source_exclusions") or []) if disease_id in e.get("diseases", [])
    ]
    excl_files = {str(e["file"]) for e in excl_entries}
    keep_period_files = {str(e["file"]) for e in excl_entries if e.get("keep_period", False)}

    pdfs = [str(p) for p in sorted(pdf_dir.resolve().glob("*.pdf")) if p.name not in excl_files]
    tasks = [(p, list(grp["page_anchors"]), list(grp["state_markers"]), lag) for p in pdfs]

    if jobs <= 1:
        pdf_rows = list(map(inspect_one_pdf, tasks))
    else:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            pdf_rows = list(ex.map(inspect_one_pdf, tasks, chunksize=4))

    canon_lookup, csv_diag = analyze_canon_csv_cells_and_trajectories(
        canon_csv,
        lag=lag,
        keep_period_files=keep_period_files,
    )
    c6_block = compare_canon_against_pdf_blocks(canon_lookup, pdf_rows)

    # H6(b): persistir evidencia por PDF ANTES de la etapa de dataset / validate-data
    out_json.parent.mkdir(parents=True, exist_ok=True)
    compact_pdf_rows = [
        {k: v for k, v in r.items() if k not in {"cells_a50", "cells_a51", "cells_a54"}}
        for r in pdf_rows
    ]
    with out_pdf_detail_json.open("x", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "schema": "piloto_carbon_alta1.qa_por_pdf.v1",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "provenance": provenance,
                    "c6_summary": c6_block,
                    "pdf_rows": compact_pdf_rows,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
    _set_readonly(out_pdf_detail_json)

    raw_dest = wt / "data" / "raw" / f"data_raw_{spec_reg.artifact_key}.csv"
    dataset_manifest_info: dict[str, Any] = {"executed": False}
    if run_validate_data:
        raw_action = stage_raw_for_validate_data(canon_csv, raw_dest, expected_canon_sha256)
        dm = orch.validate_data(disease_id)
        dataset_manifest_info = {
            "executed": True,
            "raw_dest_action": raw_action,
            "raw_dest_path": str(raw_dest),
            "raw_dest_sha256": vr.sha256_file(raw_dest),
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
        "schema": "piloto_carbon_alta1.qa_serie_extraida.v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "disease_id": disease_id,
        "provenance_and_pins": provenance,
        "per_pdf_persisted_file": str(out_pdf_detail_json.resolve()),
        "c6_antibloque_y_total": {
            "non_excluded_pdfs_inspected": len(pdf_rows),
            "excluded_pdfs_declared": sorted(excl_files),
            "keep_period_pdfs_declared": sorted(keep_period_files),
            **c6_block,
        },
        "c7_calendario_lag_densidad_calidad": {
            "mmwr_weeks_in_year": mmwr_years,
            "historical_lag_verification": {
                "expected_lag_weeks": lag,
                "bulletins_ok": len(c6_block["files_by_status"]["ok"]),
                "lag_mismatch_files": c6_block["files_by_status"]["lag_mismatch"],
                "lag_mismatch_details": c6_block["lag_mismatch_details"],
                "header_cutoff_unparsed_files": c6_block["files_by_status"][
                    "header_cutoff_unparsed"
                ],
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
                "raw_pdf_minus_one_cells_target_2025": c6_block[
                    "raw_pdf_tokens_before_normalize_number"
                ]["raw_minus_one_cells_target_2025"],
                "raw_pdf_non_numeric_cells_target_2025": c6_block[
                    "raw_pdf_tokens_before_normalize_number"
                ]["raw_non_numeric_cells_target_2025"],
                **csv_diag["target_2025_csv_na_and_minus_one"],
            },
            "cumulative_trajectories_and_anomalies": csv_diag[
                "cumulative_trajectories_and_anomalies"
            ],
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

    with out_json.open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    _set_readonly(out_json)

    c6 = report["c6_antibloque_y_total"]
    c7 = report["c7_calendario_lag_densidad_calidad"]
    cc = c6["canon_cell_by_cell_contrast"]
    traj = c7["cumulative_trajectories_and_anomalies"]
    md_lines = [
        f"# Reporte QA de Serie Extraída (`C6`, `C7`, `C8`) — `{disease_id}`",
        "",
        f"- **Commit QA fijado (`40` hex)**: `{provenance['commit_sha40']}`",
        f"- **Inventario PDF sellado**: `{provenance['inventory_sha256']}` "
        f"(`{provenance['pdf_count']}` PDFs)",
        f"- **CSV canónico**: `{provenance['canon_csv']}` (`sha256: {provenance['canon_csv_sha256']}`)",
        f"- **Detalle por PDF persistido**: `{out_pdf_detail_json.resolve()}`",
        f"- **Dataset validado (`C8`)**: `{dataset_manifest_info.get('dataset_id')}` "
        f"(`action: {dataset_manifest_info.get('raw_dest_action')}`, "
        f"`raw_dest_sha256: {dataset_manifest_info.get('raw_dest_sha256')}`)",
        "",
        "## 1. Guardia anti-bloque celda a celda y fila `TOTAL` (`C6`)",
        f"- Conteos por estado PDF: `{c6['status_counts']}`",
        f"- Archivos no `ok`: `no_page={c6['files_by_status']['no_page']}`, "
        f"`no_table={c6['files_by_status']['no_table']}`, "
        f"`unexpected_shape={c6['files_by_status']['unexpected_shape']}`, "
        f"`exception={c6['files_by_status']['exception']}`",
        f"- Celdas del CSV canónico comparadas contra `A51-A53` (PDF): "
        f"`{cc['denominator_cells_4col']}` en `{cc['denominator_bulletins']}` boletines "
        f"(`difieren={cc['canon_vs_target_a51_diff_cells']}`, "
        f"`ausentes_canon={cc['canon_missing_cells']}`, "
        f"`ausentes_pdf={cc['pdf_a51_missing_cells']}`)",
        f"- Contraste celda a celda del CSV canónico contra vecino izquierdo `A50`: "
        f"`difieren={cc['canon_vs_left_a50_diff_cells']}` / `{cc['denominator_cells_4col']}`, "
        f"`boletines_identicos={cc['bulletins_where_canon_equals_left_a50']}`",
        f"- Contraste celda a celda del CSV canónico contra vecino derecho `A54.0-A54.2`: "
        f"`difieren={cc['canon_vs_right_a54_diff_cells']}` / `{cc['denominator_cells_4col']}`, "
        f"`boletines_identicos={cc['bulletins_where_canon_equals_right_a54']}`",
        f"- Fila `TOTAL` impresa: `coincide={len(c6['files_by_status']['total_coincide'])}`, "
        f"`difiere={c6['files_by_status']['total_difiere']}`, "
        f"`sin_total_12={c6['files_by_status']['sin_total_12']}`",
        "",
        "## 2. Calendario MMWR, objetivos 2025, trayectorias y densidad (`C7`)",
        f"- Rango objetivo: `{c7['series_span']['first_target_period']}` a "
        f"`{c7['series_span']['last_target_period']}` "
        f"(`{c7['series_span']['total_target_weeks']}` semanas, "
        f"`{c7['series_span']['total_base_rows']}` filas base)",
        f"- Discrepancias de rezago impreso vs `epi_calendar`: "
        f"`{c7['historical_lag_verification']['lag_mismatch_files']}`",
        f"- Semanas de entrenamiento previas por pliegue: `{c7['train_weeks_before_folds']}`",
        f"- Integridad objetivos 2025 (sin pronóstico): "
        f"`semanas={c7['target_2025_integrity_no_forecast']['target_weeks_present_2025']}`, "
        f"`total_imputed={c7['target_2025_integrity_no_forecast']['total_imputed_rows_2025']}`, "
        f"`NA_csv_por_col={c7['target_2025_integrity_no_forecast']['na_counts_by_column_in_2025_targets']}`, "
        f"`tokens_-1_crudos_camelot={len(c7['target_2025_integrity_no_forecast']['raw_pdf_minus_one_cells_target_2025'])}`",
        f"- Caídas nacionales intra-año de acumulados: "
        f"`{[x['file'] for x in traj['national_cumulative_drops_by_file']]}`",
        f"- Picos/caídas nacionales revertidos (tripleta): "
        f"`{[x['file'] for x in traj['national_spike_or_drop_reverted_triplets']]}`",
        f"- Deltas estatales negativos crudos: "
        f"`H={traj['raw_negative_deltas_hombres']}`, `M={traj['raw_negative_deltas_mujeres']}` "
        f"en `{len(traj['state_negative_delta_files'])}` archivos",
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
    with out_md.open("x", encoding="utf-8") as fh:
        fh.write("\n".join(md_lines) + "\n")
    _set_readonly(out_md)
    return report


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--disease", default="sifilis_adquirida_a51")
    ap.add_argument("--canon-csv", type=Path, required=True)
    ap.add_argument("--expected-canon-sha256", required=True)
    ap.add_argument("--pdf-dir", type=Path, required=True)
    ap.add_argument("--inventory-json", type=Path, required=True)
    ap.add_argument("--expected-inventory-sha256", required=True)
    ap.add_argument("--worktree", type=Path, required=True)
    ap.add_argument("--expected-commit", required=True)
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
        expected_canon_sha256=args.expected_canon_sha256,
        pdf_dir=args.pdf_dir,
        inventory_json=args.inventory_json,
        expected_inventory_sha256=args.expected_inventory_sha256,
        worktree=args.worktree,
        expected_commit=args.expected_commit,
        out_json=args.out_json,
        out_md=args.out_md,
        jobs=args.jobs,
        run_validate_data=not args.skip_validate_data,
    )
    span = rep["c7_calendario_lag_densidad_calidad"]["series_span"]
    print(
        f"QA_OK id={rep['disease_id']} weeks={span['total_target_weeks']} "
        f"dataset_id={rep['c8_validate_data'].get('dataset_id')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
