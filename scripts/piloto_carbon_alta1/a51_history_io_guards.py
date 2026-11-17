"""IO exclusivo, guardas de integridad/cobertura y reporte para ``BASE_86_W43``.

Verifica ``revisa_consolidado`` sobre el prefijo de 85 publicados y sobre el candidato de 86,
contrasta ``diferencias_base`` frente al raw de entrenamiento, garantiza prefijo byte-idéntico y
materializa salidas únicamente mediante creación exclusiva (``os.link``) o NO-OP byte-idéntico.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from scripts.paso_semanal import CONSOLIDADO_COLS
from scripts.piloto_carbon_alta1.a51_history_projection import (
    CONSOLIDADO_HEADER,
    DISEASE_ID,
    EXPECTED_NEW_PUBLISHED,
    EXPECTED_OLD_PUBLISHED,
    BaseHistoryBuildError,
)

from epiforecast.data.epi_calendar import shift as semana_siguiente
from epiforecast.publication.consolidado_base import diferencias_base
from epiforecast.publication.contratos_datos import ContratoCobertura, revisa_consolidado, slug

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_hex64(value: str, flag_name: str) -> str:
    norm = value.strip().lower()
    if not _HEX64_RE.fullmatch(norm):
        raise BaseHistoryBuildError(f"{flag_name} debe ser SHA-256 de 64 hex: {value!r}")
    return norm


def require_regular_input(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise BaseHistoryBuildError(f"{label} ausente o symlink no permitido: {path}")


def verify_base_85_prefix(
    base_csv: Path,
    base_bytes: bytes,
    *,
    a51_slug: str,
    contrato_85: ContratoCobertura,
    cutoff: tuple[int, int],
) -> dict[str, Any]:
    if not base_bytes.endswith(b"\n"):
        raise BaseHistoryBuildError(f"base_csv no termina en salto de línea LF: {base_csv}")
    first_nl = base_bytes.find(b"\n")
    header_line = base_bytes[:first_nl].decode("utf-8").rstrip("\r")
    if header_line != CONSOLIDADO_COLS:
        raise BaseHistoryBuildError(
            f"encabezado de base_csv fuera de CONSOLIDADO_COLS: {header_line!r}"
        )
    with base_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if slug(row["Padecimiento"]) == a51_slug:
                raise BaseHistoryBuildError(
                    "base_csv (85 publicados) ya contiene filas de Sífilis adquirida"
                )

    cob_85 = revisa_consolidado(base_csv, contrato_85, contrato_85.padecimientos)
    if not cob_85.pasa:
        raise BaseHistoryBuildError(
            f"base_csv no pasa revisa_consolidado (85): {list(cob_85.problemas[:5])}"
        )
    cortes_85 = cob_85.cifras["cortes"]
    if len(cortes_85) != EXPECTED_OLD_PUBLISHED:
        raise BaseHistoryBuildError(
            f"base_csv cubrió {len(cortes_85)} publicados (se esperan {EXPECTED_OLD_PUBLISHED})"
        )
    if set(cortes_85.values()) != {cutoff}:
        raise BaseHistoryBuildError(
            f"base_csv no está alineada en el corte fuente {cutoff}: {set(cortes_85.values())}"
        )
    return {
        "old_published_verified": len(cortes_85),
        "old_rows_verified": int(cob_85.cifras["filas"]),
        "old_cutoff": list(cutoff),
    }


def verify_candidate_86(
    candidate_csv: Path,
    *,
    base_bytes: bytes,
    expected_base_sha256: str,
    expected_out_bytes_len: int,
    raw_a51_csv: Path,
    contrato_86: ContratoCobertura,
    cutoff: tuple[int, int],
) -> dict[str, Any]:
    cand_bytes = candidate_csv.read_bytes()
    if len(cand_bytes) != expected_out_bytes_len:
        raise BaseHistoryBuildError(
            f"tamaño inesperado en {candidate_csv}: {len(cand_bytes)} != {expected_out_bytes_len}"
        )
    prefix = cand_bytes[: len(base_bytes)]
    if prefix != base_bytes or sha256_bytes(prefix) != expected_base_sha256:
        raise BaseHistoryBuildError("el candidato no conserva base_csv como prefijo byte a byte")

    antes_de_siguiente = semana_siguiente(cutoff[0], cutoff[1], 1)
    diffs = diferencias_base(candidate_csv, {DISEASE_ID: raw_a51_csv}, antes_de_siguiente)
    if diffs:
        raise BaseHistoryBuildError(
            f"diferencias_base detectó discrepancias frente al raw A51 (< {antes_de_siguiente}): "
            f"{diffs}"
        )

    cob_86 = revisa_consolidado(candidate_csv, contrato_86, contrato_86.padecimientos)
    if not cob_86.pasa:
        raise BaseHistoryBuildError(
            f"candidato 86 no pasa revisa_consolidado: {list(cob_86.problemas[:5])}"
        )
    cortes_86 = cob_86.cifras["cortes"]
    if len(cortes_86) != EXPECTED_NEW_PUBLISHED:
        raise BaseHistoryBuildError(
            f"candidato cubrió {len(cortes_86)} publicados (se esperan {EXPECTED_NEW_PUBLISHED})"
        )
    if set(cortes_86.values()) != {cutoff}:
        raise BaseHistoryBuildError(
            f"corte dispar en candidato 86 (esperado {cutoff}): {set(cortes_86.values())}"
        )
    return {
        "new_published_verified": len(cortes_86),
        "new_rows_verified": int(cob_86.cifras["filas"]),
        "new_cutoff": list(cutoff),
        "diferencias_base_antes_de": list(antes_de_siguiente),
        "diferencias_base_count": 0,
    }


def write_exclusive_or_noop(target: Path, payload: bytes, label: str) -> bool:
    """Devuelve ``True`` si fue NO-OP byte-idéntico; ``False`` si creó ``target`` en exclusiva."""
    if target.is_symlink():
        raise BaseHistoryBuildError(f"{label} existente es symlink: {target}")
    if target.exists():
        if not target.is_file():
            raise BaseHistoryBuildError(f"{label} existente no es archivo regular: {target}")
        if target.read_bytes() != payload:
            raise BaseHistoryBuildError(
                f"{label} ya existe con contenido distinto (no se sobrescribe archivo único): "
                f"{target}"
            )
        return True

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    try:
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.link(tmp_path, target)
    except FileExistsError as exc:
        raise BaseHistoryBuildError(
            f"{label} apareció concurrentemente; no se sobrescribe: {target}"
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    return False


def materialize_or_verify_out_csv(
    *,
    out_csv: Path,
    expected_out_bytes: bytes,
    expected_out_sha: str,
    base_csv: Path,
    base_bytes: bytes,
    exp_base_sha: str,
    raw_a51_csv: Path,
    contrato_86: ContratoCobertura,
    cutoff: tuple[int, int],
) -> tuple[bool, dict[str, Any]]:
    if out_csv.is_symlink():
        raise BaseHistoryBuildError(f"out_csv existente es symlink: {out_csv}")

    if out_csv.exists():
        if not out_csv.is_file():
            raise BaseHistoryBuildError(f"out_csv existente no es archivo regular: {out_csv}")
        if out_csv.read_bytes() != expected_out_bytes:
            raise BaseHistoryBuildError(
                f"out_csv ya existe con contenido distinto; no se sobrescribe archivo único: "
                f"{out_csv}"
            )
        new86_info = verify_candidate_86(
            out_csv,
            base_bytes=base_bytes,
            expected_base_sha256=exp_base_sha,
            expected_out_bytes_len=len(expected_out_bytes),
            raw_a51_csv=raw_a51_csv,
            contrato_86=contrato_86,
            cutoff=cutoff,
        )
        noop = True
    else:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        tmp_out = out_csv.with_name(f".{out_csv.name}.tmp.{os.getpid()}")
        try:
            fd = os.open(tmp_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(fd, "wb") as fh:
                fh.write(expected_out_bytes)
            new86_info = verify_candidate_86(
                tmp_out,
                base_bytes=base_bytes,
                expected_base_sha256=exp_base_sha,
                expected_out_bytes_len=len(expected_out_bytes),
                raw_a51_csv=raw_a51_csv,
                contrato_86=contrato_86,
                cutoff=cutoff,
            )
            if sha256_bytes(base_csv.read_bytes()) != exp_base_sha:
                raise BaseHistoryBuildError("base_csv cambió durante la verificación; abortando")
            os.link(tmp_out, out_csv)
        except FileExistsError as exc:
            raise BaseHistoryBuildError(
                f"out_csv apareció concurrentemente; no se sobrescribe: {out_csv}"
            ) from exc
        finally:
            tmp_out.unlink(missing_ok=True)
        noop = False

    if sha256_bytes(base_csv.read_bytes()) != exp_base_sha:
        raise BaseHistoryBuildError("base_csv no conserva su SHA-256 original tras la ejecución")
    if sha256_bytes(out_csv.read_bytes()) != expected_out_sha:
        raise BaseHistoryBuildError("out_csv final no coincide con el SHA-256 verificado")
    return noop, new86_info


def emit_history_report(
    *,
    noop: bool,
    data_name: str,
    base_csv: Path,
    exp_base_sha: str,
    base_bytes_len: int,
    raw_a51_csv: Path,
    exp_raw_sha: str,
    out_csv: Path,
    expected_out_sha: str,
    out_bytes_len: int,
    old85_info: dict[str, Any],
    new86_info: dict[str, Any],
    exclusions_info: dict[str, Any],
    a51_summary: dict[str, Any],
    report_json: Path | None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": "piloto_carbon_alta1.base_86_w43.v1",
        "status": "NOOP_IDENTICAL" if noop else "CREATED_VERIFIED",
        "noop_identical": noop,
        "disease_id": DISEASE_ID,
        "data_name": data_name,
        "consolidado_columns": CONSOLIDADO_HEADER,
        "base_csv": str(base_csv),
        "base_sha256": exp_base_sha,
        "base_bytes": base_bytes_len,
        "raw_a51_csv": str(raw_a51_csv),
        "raw_a51_sha256": exp_raw_sha,
        "out_csv": str(out_csv),
        "out_sha256": expected_out_sha,
        "out_bytes": out_bytes_len,
        "prefix_byte_identical": True,
        "old85_guard": old85_info,
        "new86_guard": new86_info,
        "inherited_exclusions_and_lag": exclusions_info,
        "a51_history": a51_summary,
    }
    if report_json is not None:
        report_bytes = (
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        write_exclusive_or_noop(report_json, report_bytes, "report_json")
    return report
