"""Cronología de cada boletín usado en la validación prospectiva.

Una semana solo es prospectiva «respecto de la información» si el boletín no estaba disponible al
emitir el pronóstico. Este registro separa las tres fechas que suelen confundirse: creación
(metadatos del PDF), primera disponibilidad verificable (declarada con su evidencia) y captura
(cuando el archivo llegó a este equipo), y las compara con la emisión.

Vive junto al gate, pero no entra en sus digests ni en el veredicto: documenta, no decide. Los
metadatos acreditan que ESE archivo no existía antes de su fecha; no excluyen que circulara otra
versión. Sin evidencia de disponibilidad, el campo queda nulo y el reporte lo dice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PyPdfError

SCHEMA = "bulletin_provenance.v1"
PROVENANCE_FILE = "bulletin_provenance.json"
_PDF_DATE = re.compile(r"^D:(\d{14})(?:(Z)|([+-])(\d{2})'?(\d{2})'?)?")


class ProvenanceError(ValueError):
    """La evidencia cronológica es inconsistente o está mal declarada."""


@dataclass(frozen=True, slots=True)
class FirstAvailability:
    """Primera disponibilidad pública verificable, siempre con su evidencia."""

    at: str
    evidence: str


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def parse_instant(text: str) -> datetime:
    """ISO 8601 con zona horaria; una fecha sin zona no permite comparar con la emisión."""
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        raise ProvenanceError(f"fecha sin zona horaria: {text}")
    return value


def parse_first_available(text: str) -> FirstAvailability:
    """Lee ``<ISO 8601>|<evidencia>``, la forma de ``--first-available``."""
    at, separador, evidence = text.partition("|")
    if not separador or not evidence.strip():
        raise ProvenanceError("--first-available exige '<fecha ISO con zona>|<evidencia>'")
    return FirstAvailability(_iso_utc(parse_instant(at.strip())), evidence.strip())


def parse_pdf_date(raw: object) -> str | None:
    """Convierte ``D:AAAAMMDDhhmmss±hh'mm'`` a UTC; sin zona declarada no se adivina."""
    if not isinstance(raw, str):
        return None
    found = _PDF_DATE.match(raw)
    if found is None:
        return None
    stamp, zulu, sign, hours, minutes = found.groups()
    if not zulu and not sign:
        return None
    try:
        base = datetime.strptime(stamp, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    offset = timedelta(hours=int(hours or 0), minutes=int(minutes or 0))
    zone = timezone(-offset if sign == "-" else offset)
    return _iso_utc(base.replace(tzinfo=zone))


def pdf_metadata(path: Path) -> dict[str, str | None]:
    """Fechas tal como las declara el PDF, crudas y normalizadas."""
    try:
        info: dict[Any, Any] = dict(PdfReader(str(path)).metadata or {})
    except (OSError, PyPdfError, ValueError) as exc:
        return {
            "created_raw": None,
            "created_utc": None,
            "modified_raw": None,
            "modified_utc": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    created = info.get("/CreationDate")
    modified = info.get("/ModDate")
    return {
        "created_raw": str(created) if created is not None else None,
        "created_utc": parse_pdf_date(created),
        "modified_raw": str(modified) if modified is not None else None,
        "modified_utc": parse_pdf_date(modified),
        "error": None,
    }


def _posterior(instant: str | None, emitted_at: datetime) -> bool | None:
    return None if instant is None else parse_instant(instant) > emitted_at


def bulletin_entry(
    path: Path,
    *,
    emitted_at: str,
    first_available: FirstAvailability | None = None,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Evidencia de un boletín. La captura por defecto es la fecha del archivo en disco."""
    data = path.read_bytes()
    metadata = pdf_metadata(path)
    emitted = parse_instant(emitted_at)
    captured = captured_at or _iso_utc(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
    first = first_available.at if first_available else None
    return {
        "name": path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "pdf_metadata": metadata,
        "first_available_utc": first,
        "first_available_evidence": first_available.evidence if first_available else None,
        "captured_utc": _iso_utc(parse_instant(captured)),
        "after_emission": {
            "created": _posterior(metadata["created_utc"], emitted),
            "first_available": _posterior(first, emitted),
            "captured": _posterior(captured, emitted),
        },
    }


def merge_entries(
    current: dict[str, Any] | None,
    *,
    disease_id: str,
    release_id: str,
    forecast_emitted_at: str,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Une entradas nuevas por sha256: la evidencia registrada no se reescribe en silencio."""
    payload = current or {
        "schema": SCHEMA,
        "disease_id": disease_id,
        "release_id": release_id,
        "forecast_emitted_at": forecast_emitted_at,
        "bulletins": [],
    }
    for key, expected in (
        ("schema", SCHEMA),
        ("disease_id", disease_id),
        ("release_id", release_id),
        ("forecast_emitted_at", forecast_emitted_at),
    ):
        if payload.get(key) != expected:
            raise ProvenanceError(f"{PROVENANCE_FILE}: {key} no coincide con {expected}")
    known = {item["sha256"]: item for item in payload["bulletins"]}
    for entry in entries:
        previous = known.get(entry["sha256"])
        if previous is None:
            payload["bulletins"].append(entry)
            known[entry["sha256"]] = entry
        elif entry["first_available_utc"] is not None and (
            previous["first_available_utc"] is None
        ):
            previous["first_available_utc"] = entry["first_available_utc"]
            previous["first_available_evidence"] = entry["first_available_evidence"]
            previous["after_emission"]["first_available"] = entry["after_emission"][
                "first_available"
            ]
        elif (
            entry["first_available_utc"] is not None
            and entry["first_available_utc"] != previous["first_available_utc"]
        ):
            raise ProvenanceError(
                f"{entry['name']}: primera disponibilidad ya registrada distinta"
            )
    payload["bulletins"].sort(key=lambda item: item["name"])
    return payload


def write_provenance(
    root: Path,
    *,
    disease_id: str,
    release_id: str,
    forecast_emitted_at: str,
    pdfs: list[Path],
    first_available: FirstAvailability | None = None,
    captured_at: str | None = None,
) -> Path:
    """Actualiza ``<root>/bulletin_provenance.json`` de forma atómica."""
    if first_available is not None and len(pdfs) != 1:
        raise ProvenanceError("--first-available describe un solo boletín")
    destination = root / PROVENANCE_FILE
    current = json.loads(destination.read_text("utf-8")) if destination.is_file() else None
    entries = [
        bulletin_entry(
            path,
            emitted_at=forecast_emitted_at,
            first_available=first_available,
            captured_at=captured_at,
        )
        for path in pdfs
    ]
    payload = merge_entries(
        current,
        disease_id=disease_id,
        release_id=release_id,
        forecast_emitted_at=forecast_emitted_at,
        entries=entries,
    )
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8"
    )
    temporary.replace(destination)
    return destination
