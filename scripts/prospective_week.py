"""Incorpora boletines nuevos al gate prospectivo sin tocar el pipeline semanal legacy.

Este comando es deliberadamente estrecho:

1. extrae el padecimiento declarado de uno o más PDF explícitos;
2. crea un raw de observación temporal preservando byte-a-byte el prefijo lógico histórico;
3. construye EpiDatasetV2 + productos con el runner genérico, sin entrenar;
4. deriva la evaluación contra el candidato y el control congelados;
5. emite un reporte canónico. En ``--dry-run`` NO modifica el estado declarado.

No descarga datos, no ejecuta DVC, no escribe superficies públicas y no decide lifecycle.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import hashlib
from pathlib import Path
import sys
import tempfile
from typing import Any

import pandas as pd
from scripts.prospective_status import derive_evaluation

from epiforecast import registry
from epiforecast.data import epi_calendar as ec
from epiforecast.data.epi_dataset import load_config, raw_path_for
from epiforecast.data.epi_geo_exposure import GeoCatalog, load_geo_catalog
from epiforecast.data.extraction.cuadro_extractor import extract_cuadro_from_pdf
from epiforecast.runner import orchestrator
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.manifest import default_runs_root
from epiforecast.runner.release_contract import canonical_json, sha256_bytes

REPORT_SCHEMA = "prospective_week_dry_run.v1"
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
RAW_KEY: tuple[str, ...] = ("Anio", "Semana", "Entidad", "Padecimiento")


class ProspectiveWeekError(ValueError):
    """El boletín no puede incorporarse al carril prospectivo."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _period(year: object, week: object, label: str) -> tuple[int, int]:
    def exact_int(value: object) -> int:
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped.isascii() or not stripped.isdigit():
                raise ValueError
            return int(stripped)
        if isinstance(value, (int, float)) and float(value).is_integer():
            return int(value)
        raise ValueError

    try:
        result = (exact_int(year), exact_int(week))
    except ValueError as exc:
        raise ProspectiveWeekError(f"{label}: año/semana no enteros: {year!r}/{week!r}") from exc
    try:
        ec.week_start(*result)
    except ValueError as exc:
        raise ProspectiveWeekError(f"{label}: periodo MMWR inválido {result}") from exc
    return result


def _require_raw_shape(frame: pd.DataFrame, *, disease_name: str, label: str) -> pd.DataFrame:
    missing = sorted(set(RAW_COLUMNS) - set(frame.columns))
    extra = sorted(set(frame.columns) - set(RAW_COLUMNS))
    if missing or extra:
        raise ProspectiveWeekError(
            f"{label}: columnas inválidas; faltan={missing}, sobran={extra}"
        )
    out = frame.loc[:, RAW_COLUMNS].copy()
    if out.empty:
        raise ProspectiveWeekError(f"{label}: sin filas")
    diseases = sorted(str(v) for v in out["Padecimiento"].dropna().unique())
    if diseases != [disease_name]:
        raise ProspectiveWeekError(
            f"{label}: Padecimiento debe ser sólo {disease_name!r}, llegó {diseases}"
        )
    if out.duplicated(list(RAW_KEY)).any():
        raise ProspectiveWeekError(f"{label}: claves {RAW_KEY} duplicadas")
    for row in out[["Anio", "Semana"]].drop_duplicates().itertuples(index=False):
        _period(row.Anio, row.Semana, label)
    return out


def _resolved_entities(frame: pd.DataFrame, catalog: GeoCatalog, label: str) -> list[str]:
    try:
        return [catalog.resolve(str(value)) for value in frame["Entidad"]]
    except ValueError as exc:
        raise ProspectiveWeekError(f"{label}: {exc}") from exc


def extract_new_rows(
    disease: str, pdfs: Iterable[Path], *, catalog: GeoCatalog | None = None
) -> pd.DataFrame:
    """Extrae y valida cada PDF: periodo declarado, padecimiento y cobertura geográfica exacta."""
    declared = registry.require(disease)
    config = load_config(disease)
    geo = catalog or load_geo_catalog()
    expected = set(geo.cve_ents())
    frames: list[pd.DataFrame] = []
    periods: set[tuple[int, int]] = set()
    paths = [Path(p).resolve() for p in pdfs]
    if not paths:
        raise ProspectiveWeekError("se requiere al menos un PDF")

    for pdf in paths:
        if not pdf.is_file():
            raise ProspectiveWeekError(f"PDF inexistente o no regular: {pdf}")
        result = extract_cuadro_from_pdf(str(pdf), declared.extraction_group, declared.id)
        if not result.get("valid") or not isinstance(result.get("df"), pd.DataFrame):
            raise ProspectiveWeekError(
                f"{pdf.name}: extracción inválida ({result.get('reason', 'sin motivo')})"
            )
        frame = _require_raw_shape(result["df"], disease_name=declared.data_name, label=pdf.name)
        period = _period(result.get("year"), result.get("week"), pdf.name)
        row_periods = {
            _period(row.Anio, row.Semana, pdf.name)
            for row in frame[["Anio", "Semana"]].drop_duplicates().itertuples(index=False)
        }
        if row_periods != {period}:
            raise ProspectiveWeekError(
                f"{pdf.name}: periodo del filename {period} != filas {sorted(row_periods)}"
            )
        if period in periods:
            raise ProspectiveWeekError(f"periodo repetido entre PDFs: {period}")
        periods.add(period)
        cves = _resolved_entities(frame, geo, pdf.name)
        if len(cves) != config.expected_n_states or set(cves) != expected:
            raise ProspectiveWeekError(
                f"{pdf.name}: cobertura geográfica inválida "
                f"({len(cves)} filas, {len(set(cves))} entidades)"
            )
        if len(cves) != len(set(cves)):
            raise ProspectiveWeekError(f"{pdf.name}: entidad duplicada tras resolver aliases")
        frames.append(frame)

    merged = pd.concat(frames, ignore_index=True)
    return merged.sort_values(["Anio", "Semana", "Entidad"]).reset_index(drop=True)


def merge_observation_raw(
    baseline: pd.DataFrame,
    new_rows: pd.DataFrame,
    *,
    disease_name: str,
    catalog: GeoCatalog | None = None,
) -> pd.DataFrame:
    """Añade periodos fuente posteriores; el prefijo histórico no se reemplaza ni se corrige."""
    geo = catalog or load_geo_catalog()
    old = _require_raw_shape(baseline, disease_name=disease_name, label="raw baseline")
    new = _require_raw_shape(new_rows, disease_name=disease_name, label="boletines nuevos")
    old_periods = {
        _period(row.Anio, row.Semana, "raw baseline")
        for row in old[["Anio", "Semana"]].drop_duplicates().itertuples(index=False)
    }
    new_periods = {
        _period(row.Anio, row.Semana, "boletines nuevos")
        for row in new[["Anio", "Semana"]].drop_duplicates().itertuples(index=False)
    }
    latest = max(old_periods, key=lambda p: ec.week_start(*p))
    stale = sorted(p for p in new_periods if ec.week_start(*p) <= ec.week_start(*latest))
    if stale:
        raise ProspectiveWeekError(
            f"los boletines deben ser posteriores al baseline {latest}; llegaron {stale}"
        )

    old_cves = _resolved_entities(old, geo, "raw baseline")
    new_cves = _resolved_entities(new, geo, "boletines nuevos")
    old_key = pd.DataFrame(
        {
            "Anio": old["Anio"].astype(int),
            "Semana": old["Semana"].astype(int),
            "cve_ent": old_cves,
            "Padecimiento": old["Padecimiento"].astype(str),
        }
    )
    new_key = pd.DataFrame(
        {
            "Anio": new["Anio"].astype(int),
            "Semana": new["Semana"].astype(int),
            "cve_ent": new_cves,
            "Padecimiento": new["Padecimiento"].astype(str),
        }
    )
    if old_key.duplicated().any() or new_key.duplicated().any():
        raise ProspectiveWeekError("clave (Anio,Semana,Entidad,Padecimiento) duplicada")
    overlap = old_key.merge(new_key, how="inner")
    if not overlap.empty:
        raise ProspectiveWeekError("los boletines nuevos sobrescriben claves históricas")

    combined = pd.concat([old, new], ignore_index=True)
    # Orden estable sin reinterpretar valores. El prefijo lógico es exactamente `old`.
    return combined.sort_values(["Anio", "Semana", "Entidad"]).reset_index(drop=True)


def _report_payload(
    *,
    disease_id: str,
    source_periods: list[tuple[int, int]],
    baseline_raw_digest: str,
    observation_raw_digest: str,
    dataset_manifest: Any,
    evaluation: Any,
    status: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "disease_id": disease_id,
        "source_periods": [list(p) for p in source_periods],
        "baseline_raw_digest": baseline_raw_digest,
        "observation_raw_digest": observation_raw_digest,
        "observation_dataset_id": dataset_manifest.dataset_id,
        "observation_dataset_digest": dataset_manifest.digests["dataset"],
        "observation_cutoff": list(evaluation.observation_cutoff),
        "release_id": evaluation.release_id,
        "gate_digest": evaluation.gate_digest,
        "candidate_digest": evaluation.candidate_digest,
        "control_digest": evaluation.control_digest,
        "weeks_required": status.weeks_required,
        "weeks_available": status.weeks_available,
        "completed_weeks": [list(p) for p in status.completed_weeks],
        "skipped_weeks": [
            {"week": list(period), "reason": reason} for period, reason in evaluation.skipped_weeks
        ],
        "verdict": status.verdict,
    }
    payload["report_digest"] = sha256_bytes(canonical_json(payload))
    return payload


def run_week(
    disease: str,
    pdfs: Iterable[Path],
    *,
    baseline_raw: Path | None = None,
    runs_root: Path | None = None,
) -> dict[str, Any]:
    """Ejecuta el carril aislado y devuelve evidencia canónica; no escribe estado público."""
    declared = registry.require(disease)
    source = (baseline_raw or raw_path_for(disease)).resolve()
    if not source.is_file():
        raise ProspectiveWeekError(f"raw baseline inexistente: {source}")
    baseline = pd.read_csv(source, low_memory=False)
    new_rows = extract_new_rows(declared.id, pdfs)
    merged = merge_observation_raw(baseline, new_rows, disease_name=declared.data_name)
    source_periods = sorted(
        {
            _period(row.Anio, row.Semana, "boletines nuevos")
            for row in new_rows[["Anio", "Semana"]].drop_duplicates().itertuples(index=False)
        },
        key=lambda p: ec.week_start(*p),
    )
    effective_runs = (runs_root or default_runs_root()).resolve()
    effective_runs.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="prospective_week_") as tmp:
        observation_raw = Path(tmp) / source.name
        merged.to_csv(observation_raw, index=False)
        manifest = orchestrator.validate_data(
            declared.id, runs_root=effective_runs, raw_path=observation_raw
        )
        evaluation, status = derive_evaluation(
            declared.id,
            observation_dataset_id=manifest.dataset_id,
            runs_root=effective_runs,
        )
        return _report_payload(
            disease_id=declared.id,
            source_periods=source_periods,
            baseline_raw_digest=_sha256(source),
            observation_raw_digest=_sha256(observation_raw),
            dataset_manifest=manifest,
            evaluation=evaluation,
            status=status,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disease", required=True)
    parser.add_argument("--pdf", type=Path, action="append", required=True)
    parser.add_argument("--baseline-raw", type=Path, default=None)
    parser.add_argument("--runs-root", type=Path, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        required=True,
        help="obligatorio: no modifica el estado prospectivo declarado",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run_week(
            args.disease,
            args.pdf,
            baseline_raw=args.baseline_raw,
            runs_root=args.runs_root,
        )
    except (
        ArtifactValidationError,
        OSError,
        ProspectiveWeekError,
        ValueError,
    ) as exc:
        print(f"✖ prospective-week: {exc}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(canonical_json(payload))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
