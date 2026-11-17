"""Construye ``BASE_86_W43`` sumando la historia ``<= fuente W43`` de ``A51`` sobre ``BASE_85``.

Reglas fail-closed:
- Todos los caminos, SHA-256 esperados y el corte fuente MMWR son obligatorios (sin defaults).
- ``base_csv`` (85 publicados) jamás se modifica; ``out_csv`` conserva ``base_csv`` como prefijo
  byte a byte y sólo añade las filas normalizadas (``CONSOLIDADO_COLS``) de
  ``sifilis_adquirida_a51`` con periodo fuente ``(Anio, Semana) <= (cutoff_year, cutoff_week)``,
  sin aplicar ``observation_lag_weeks`` (semana MMWR fuente del boletín).
- Destino exclusivo o NO-OP idéntico: si ``out_csv`` ya existe con bytes distintos, aborta sin
  sobrescribirlo; si coincide byte a byte, revalida todas las guardas y termina en NO-OP.
- Guardas reales (``nofakePASS``): ``revisa_consolidado`` sobre el prefijo de 85 publicados,
  32 entidades canónicas por cada periodo real de ``A51``, ``diferencias_base`` vacía frente al raw
  de entrenamiento hasta el corte inclusive, y ``revisa_consolidado`` con paridad de 86 publicados
  en ``(cutoff_year, cutoff_week)``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
from pathlib import Path
import sys
from typing import Any

from scripts.piloto_carbon_alta1.a51_history_io_guards import (
    emit_history_report,
    materialize_or_verify_out_csv,
    require_hex64,
    require_regular_input,
    sha256_bytes,
    verify_base_85_prefix,
)
from scripts.piloto_carbon_alta1.a51_history_projection import (
    DISEASE_ID,
    EXPECTED_NEW_PUBLISHED,
    EXPECTED_OLD_PUBLISHED,
    EXPECTED_STATES,
    BaseHistoryBuildError,
    declared_source_exclusions,
    scan_and_project_a51_history,
)

from epiforecast import registry
from epiforecast.data.epi_calendar import shift as semana_siguiente
from epiforecast.publication.contratos_datos import ContratoCobertura, slug

__all__ = [
    "DISEASE_ID",
    "EXPECTED_NEW_PUBLISHED",
    "EXPECTED_OLD_PUBLISHED",
    "EXPECTED_STATES",
    "BaseHistoryBuildError",
    "build_base_86_w43",
    "main",
]


def _resolve_published_contracts() -> tuple[
    registry.Disease, str, ContratoCobertura, ContratoCobertura
]:
    spec = registry.require(DISEASE_ID)
    if spec.lifecycle != "published":
        raise BaseHistoryBuildError(
            f"{DISEASE_ID} debe tener lifecycle='published' en el registry activo "
            f"(actual: {spec.lifecycle!r})"
        )

    contrato_86 = ContratoCobertura.canonico()
    a51_slug = slug(spec.data_name)
    if a51_slug not in contrato_86.release:
        raise BaseHistoryBuildError(
            f"{DISEASE_ID} ({a51_slug!r}) no figura en ContratoCobertura.canonico().release"
        )
    if len(contrato_86.padecimientos) != EXPECTED_NEW_PUBLISHED:
        raise BaseHistoryBuildError(
            f"ContratoCobertura.canonico() declara {len(contrato_86.padecimientos)} publicados "
            f"(se esperan {EXPECTED_NEW_PUBLISHED})"
        )
    if len(contrato_86.entidades) != EXPECTED_STATES:
        raise BaseHistoryBuildError(
            f"catálogo geográfico con {len(contrato_86.entidades)} entidades "
            f"(se esperan {EXPECTED_STATES})"
        )

    contrato_85 = dataclasses.replace(
        contrato_86,
        release=tuple(p for p in contrato_86.release if p != a51_slug),
        releases={k: v for k, v in contrato_86.releases.items() if k != a51_slug},
    )
    if len(contrato_85.padecimientos) != EXPECTED_OLD_PUBLISHED:
        raise BaseHistoryBuildError(
            f"contrato previo quedó con {len(contrato_85.padecimientos)} publicados "
            f"(se esperan {EXPECTED_OLD_PUBLISHED})"
        )
    return spec, a51_slug, contrato_85, contrato_86


def build_base_86_w43(
    *,
    base_csv: Path,
    expected_base_sha256: str,
    raw_a51_csv: Path,
    expected_raw_sha256: str,
    cutoff_year: int,
    cutoff_week: int,
    out_csv: Path,
    report_json: Path | None = None,
) -> dict[str, Any]:
    exp_base_sha = require_hex64(expected_base_sha256, "--expected-base-sha256")
    exp_raw_sha = require_hex64(expected_raw_sha256, "--expected-raw-sha256")
    require_regular_input(base_csv, "base_csv")
    require_regular_input(raw_a51_csv, "raw_a51_csv")

    resolved_inputs = {base_csv.resolve(), raw_a51_csv.resolve()}
    if out_csv.resolve() in resolved_inputs:
        raise BaseHistoryBuildError("out_csv no puede apuntar a base_csv ni a raw_a51_csv")
    forbidden_report = resolved_inputs | {out_csv.resolve()}
    if report_json is not None and report_json.resolve() in forbidden_report:
        raise BaseHistoryBuildError(
            "report_json debe ser una ruta independiente de entradas y salida"
        )

    cutoff = (int(cutoff_year), int(cutoff_week))
    try:
        semana_siguiente(cutoff[0], cutoff[1], 1)
    except ValueError as exc:
        raise BaseHistoryBuildError(f"corte MMWR inválido {cutoff}: {exc}") from exc

    base_bytes = base_csv.read_bytes()
    actual_base_sha = sha256_bytes(base_bytes)
    if actual_base_sha != exp_base_sha:
        raise BaseHistoryBuildError(
            f"SHA-256 de base_csv no coincide: {actual_base_sha} != {exp_base_sha}"
        )

    raw_bytes = raw_a51_csv.read_bytes()
    actual_raw_sha = sha256_bytes(raw_bytes)
    if actual_raw_sha != exp_raw_sha:
        raise BaseHistoryBuildError(
            f"SHA-256 de raw_a51_csv no coincide: {actual_raw_sha} != {exp_raw_sha}"
        )

    spec, a51_slug, contrato_85, contrato_86 = _resolve_published_contracts()

    old85_info = verify_base_85_prefix(
        base_csv,
        base_bytes,
        a51_slug=a51_slug,
        contrato_85=contrato_85,
        cutoff=cutoff,
    )
    exclusions_info = declared_source_exclusions(spec.extraction_group)
    a51_payload, a51_summary = scan_and_project_a51_history(
        raw_a51_csv,
        expected_data_name=spec.data_name,
        cutoff=cutoff,
        canonical_entities=frozenset(contrato_86.entidades),
        contrato=contrato_86,
    )

    expected_out_bytes = base_bytes + a51_payload
    expected_out_sha = sha256_bytes(expected_out_bytes)

    noop, new86_info = materialize_or_verify_out_csv(
        out_csv=out_csv,
        expected_out_bytes=expected_out_bytes,
        expected_out_sha=expected_out_sha,
        base_csv=base_csv,
        base_bytes=base_bytes,
        exp_base_sha=exp_base_sha,
        raw_a51_csv=raw_a51_csv,
        contrato_86=contrato_86,
        cutoff=cutoff,
    )

    return emit_history_report(
        noop=noop,
        data_name=spec.data_name,
        base_csv=base_csv,
        exp_base_sha=exp_base_sha,
        base_bytes_len=len(base_bytes),
        raw_a51_csv=raw_a51_csv,
        exp_raw_sha=exp_raw_sha,
        out_csv=out_csv,
        expected_out_sha=expected_out_sha,
        out_bytes_len=len(expected_out_bytes),
        old85_info=old85_info,
        new86_info=new86_info,
        exclusions_info=exclusions_info,
        a51_summary=a51_summary,
        report_json=report_json,
    )


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-csv", type=Path, required=True)
    ap.add_argument("--expected-base-sha256", type=str, required=True)
    ap.add_argument("--raw-a51-csv", type=Path, required=True)
    ap.add_argument("--expected-raw-sha256", type=str, required=True)
    ap.add_argument("--cutoff-year", type=int, required=True)
    ap.add_argument("--cutoff-week", type=int, required=True)
    ap.add_argument("--out-csv", type=Path, required=True)
    ap.add_argument("--report-json", type=Path, default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = build_base_86_w43(
            base_csv=args.base_csv,
            expected_base_sha256=args.expected_base_sha256,
            raw_a51_csv=args.raw_a51_csv,
            expected_raw_sha256=args.expected_raw_sha256,
            cutoff_year=args.cutoff_year,
            cutoff_week=args.cutoff_week,
            out_csv=args.out_csv,
            report_json=args.report_json,
        )
    except BaseHistoryBuildError as exc:
        print(f"✖ {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
