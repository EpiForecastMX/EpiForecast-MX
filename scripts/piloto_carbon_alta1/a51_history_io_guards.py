"""IO exclusivo, guardas de integridad/cobertura y reporte para ``BASE_86_W43``."""

from __future__ import annotations

from collections.abc import Callable
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
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
_VALID_REPORT_STATUSES = frozenset({"CREATED_VERIFIED", "NOOP_IDENTICAL"})
_TRANSIENT_REPORT_KEYS = frozenset({"status", "noop_identical"})


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


def _check_existing_identical(target: Path, expected: bytes, label: str) -> bool:
    if target.is_symlink():
        raise BaseHistoryBuildError(f"{label} existente es symlink: {target}")
    if not target.exists():
        return False
    if not target.is_file():
        raise BaseHistoryBuildError(f"{label} existente no es archivo regular: {target}")
    if target.read_bytes() != expected:
        raise BaseHistoryBuildError(f"{label} ya existe con contenido distinto: {target}")
    return True


def _stage_and_link_exclusive(
    target: Path,
    payload: bytes,
    label: str,
    before_link: Callable[[Path], None] | None = None,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    created_tmp: Path | None = None
    prefix = f".{target.name}.tmp.{os.getpid()}."
    try:
        fd, raw_tmp = tempfile.mkstemp(prefix=prefix, dir=target.parent)
        created_tmp = Path(raw_tmp)
        created_tmp.chmod(0o644)
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        if created_tmp is not None:
            created_tmp.unlink(missing_ok=True)
        raise BaseHistoryBuildError(f"fallo en temporal exclusivo para {label}: {exc}") from exc

    try:
        if before_link is not None:
            before_link(created_tmp)
        os.link(created_tmp, target)
    except FileExistsError as exc:
        msg = f"{label} apareció concurrentemente; no se sobrescribe: {target}"
        raise BaseHistoryBuildError(msg) from exc
    except OSError as exc:
        raise BaseHistoryBuildError(f"fallo al enlazar {label} ({target}): {exc}") from exc
    finally:
        created_tmp.unlink(missing_ok=True)


def _verify_consolidado_parity(
    csv_path: Path,
    contrato: ContratoCobertura,
    expected_count: int,
    cutoff: tuple[int, int],
) -> int:
    cob = revisa_consolidado(csv_path, contrato, contrato.padecimientos)
    if not cob.pasa:
        raise BaseHistoryBuildError(f"falló revisa_consolidado: {list(cob.problemas[:5])}")
    cortes = cob.cifras["cortes"]
    if len(cortes) != expected_count:
        raise BaseHistoryBuildError(f"cubrió {len(cortes)} publicados != {expected_count}")
    if set(cortes.values()) != {cutoff}:
        raise BaseHistoryBuildError(f"corte dispar ({cutoff}): {set(cortes.values())}")
    return int(cob.cifras["filas"])


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
    header_line = base_bytes[: base_bytes.find(b"\n")].decode("utf-8").rstrip("\r")
    if header_line != CONSOLIDADO_COLS:
        raise BaseHistoryBuildError(f"encabezado fuera de CONSOLIDADO_COLS: {header_line!r}")
    with base_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if slug(row["Padecimiento"]) == a51_slug:
                raise BaseHistoryBuildError("base_csv (85) ya contiene filas de Sífilis adquirida")
    filas = _verify_consolidado_parity(base_csv, contrato_85, EXPECTED_OLD_PUBLISHED, cutoff)
    return {
        "old_published_verified": EXPECTED_OLD_PUBLISHED,
        "old_rows_verified": filas,
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
        raise BaseHistoryBuildError(f"tamaño inesperado ({candidate_csv}): {len(cand_bytes)}")
    prefix = cand_bytes[: len(base_bytes)]
    if prefix != base_bytes or sha256_bytes(prefix) != expected_base_sha256:
        raise BaseHistoryBuildError("el candidato no conserva base_csv como prefijo byte a byte")
    antes_de_siguiente = semana_siguiente(cutoff[0], cutoff[1], 1)
    diffs = diferencias_base(candidate_csv, {DISEASE_ID: raw_a51_csv}, antes_de_siguiente)
    if diffs:
        raise BaseHistoryBuildError(f"diferencias_base (< {antes_de_siguiente}): {diffs}")
    filas = _verify_consolidado_parity(candidate_csv, contrato_86, EXPECTED_NEW_PUBLISHED, cutoff)
    return {
        "new_published_verified": EXPECTED_NEW_PUBLISHED,
        "new_rows_verified": filas,
        "new_cutoff": list(cutoff),
        "diferencias_base_antes_de": list(antes_de_siguiente),
        "diferencias_base_count": 0,
    }


def write_exclusive_or_noop(target: Path, payload: bytes, label: str) -> bool:
    if _check_existing_identical(target, payload, label):
        return True
    _stage_and_link_exclusive(target, payload, label)
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
    verified: dict[str, Any] = {}

    def _pre_link(path: Path) -> None:
        verified.update(
            verify_candidate_86(
                path,
                base_bytes=base_bytes,
                expected_base_sha256=exp_base_sha,
                expected_out_bytes_len=len(expected_out_bytes),
                raw_a51_csv=raw_a51_csv,
                contrato_86=contrato_86,
                cutoff=cutoff,
            )
        )
        if path != out_csv and sha256_bytes(base_csv.read_bytes()) != exp_base_sha:
            raise BaseHistoryBuildError("base_csv cambió durante la verificación; abortando")

    noop = _check_existing_identical(out_csv, expected_out_bytes, "out_csv")
    if noop:
        _pre_link(out_csv)
    else:
        _stage_and_link_exclusive(out_csv, expected_out_bytes, "out_csv", before_link=_pre_link)

    if sha256_bytes(base_csv.read_bytes()) != exp_base_sha:
        raise BaseHistoryBuildError("base_csv no conserva su SHA-256 original tras la ejecución")
    if sha256_bytes(out_csv.read_bytes()) != expected_out_sha:
        raise BaseHistoryBuildError("out_csv final no coincide con el SHA-256 verificado")
    return noop, verified


def _revalidate_existing_noop_report(
    report_json: Path,
    expected_report: dict[str, Any],
    expected_bytes: bytes,
) -> None:
    if report_json.is_symlink() or not report_json.is_file():
        raise BaseHistoryBuildError(f"report_json inválido o symlink: {report_json}")
    existing_bytes = report_json.read_bytes()
    if existing_bytes == expected_bytes:
        return

    def _no_dup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        acc: dict[str, Any] = {}
        for key, val in pairs:
            if key in acc:
                raise BaseHistoryBuildError(f"clave JSON duplicada en report_json: {key!r}")
            acc[key] = val
        return acc

    try:
        parsed = json.loads(existing_bytes.decode("utf-8"), object_pairs_hook=_no_dup_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaseHistoryBuildError(f"report_json malformado ({report_json}): {exc}") from exc
    if not isinstance(parsed, dict) or set(parsed.keys()) != set(expected_report.keys()):
        raise BaseHistoryBuildError(f"report_json con claves inválidas: {report_json}")
    bad_status = parsed.get("status") not in _VALID_REPORT_STATUSES
    if bad_status or not isinstance(parsed.get("noop_identical"), bool):
        raise BaseHistoryBuildError(f"status/noop_identical inválidos en {report_json}")
    cur = {k: v for k, v in parsed.items() if k not in _TRANSIENT_REPORT_KEYS}
    exp = {k: v for k, v in expected_report.items() if k not in _TRANSIENT_REPORT_KEYS}
    if json.dumps(cur, sort_keys=True) != json.dumps(exp, sort_keys=True):
        raise BaseHistoryBuildError(f"report_json difiere de la identidad NO-OP: {report_json}")


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
        report_txt = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        report_bytes = report_txt.encode("utf-8")
        if noop and (report_json.is_symlink() or report_json.exists()):
            _revalidate_existing_noop_report(report_json, report, report_bytes)
        else:
            write_exclusive_or_noop(report_json, report_bytes, "report_json")
    return report
