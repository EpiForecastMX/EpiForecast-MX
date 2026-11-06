"""Cronología de boletines: tres fechas separadas, sin decidir el veredicto."""

from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfWriter
import pytest

from epiforecast.publication import bulletin_provenance as bp

EMITIDO = "2026-11-06T03:44:45+00:00"


def _pdf(path: Path, created: str | None) -> Path:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if created:
        writer.add_metadata({"/CreationDate": created})
    with path.open("wb") as handle:
        writer.write(handle)
    return path


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "esperado"),
    [
        ("D:20261103120000-06'00'", "2026-11-03T18:00:00+00:00"),
        ("D:20261103120000+01'00'", "2026-11-03T11:00:00+00:00"),
        ("D:20261103120000Z", "2026-11-03T12:00:00+00:00"),
        ("D:20261103120000", None),
        ("D:20261399120000Z", None),
        ("fecha", None),
        (None, None),
    ],
)
def test_parse_pdf_date_no_adivina_la_zona(raw, esperado):
    assert bp.parse_pdf_date(raw) == esperado


@pytest.mark.unit
def test_separa_creacion_disponibilidad_y_captura(tmp_path):
    pdf = _pdf(tmp_path / "2026_sem43.pdf", "D:20261103120000-06'00'")
    entrada = bp.bulletin_entry(
        pdf,
        emitted_at=EMITIDO,
        first_available=bp.parse_first_available(
            "2026-11-07T10:00:00-06:00|captura de la página oficial"
        ),
        captured_at="2026-11-09T09:00:00-06:00",
    )
    assert entrada["pdf_metadata"]["created_utc"] == "2026-11-03T18:00:00+00:00"
    assert entrada["first_available_evidence"] == "captura de la página oficial"
    assert entrada["after_emission"] == {
        "created": False,
        "first_available": True,
        "captured": True,
    }


@pytest.mark.unit
def test_sin_evidencia_de_disponibilidad_queda_nula(tmp_path):
    entrada = bp.bulletin_entry(_pdf(tmp_path / "a.pdf", None), emitted_at=EMITIDO)
    assert entrada["first_available_utc"] is None
    assert entrada["after_emission"]["first_available"] is None
    assert entrada["after_emission"]["created"] is None


@pytest.mark.unit
def test_pdf_ilegible_conserva_hash_y_declara_el_error(tmp_path):
    pdf = tmp_path / "roto.pdf"
    pdf.write_bytes(b"no es un pdf")
    entrada = bp.bulletin_entry(pdf, emitted_at=EMITIDO)
    assert entrada["pdf_metadata"]["error"]
    assert len(entrada["sha256"]) == 64


@pytest.mark.unit
@pytest.mark.parametrize("texto", ["2026-11-07T10:00:00-06:00", "2026-11-07T10:00:00-06:00| "])
def test_disponibilidad_exige_evidencia(texto):
    with pytest.raises(bp.ProvenanceError, match="exige"):
        bp.parse_first_available(texto)


@pytest.mark.unit
def test_disponibilidad_exige_zona_horaria():
    with pytest.raises(bp.ProvenanceError, match="sin zona"):
        bp.parse_first_available("2026-11-07T10:00:00|evidencia")


def _escribe(root: Path, pdf: Path, **kw) -> dict:
    ruta = bp.write_provenance(
        root,
        disease_id="diabetes_t2",
        release_id="r1",
        forecast_emitted_at=EMITIDO,
        pdfs=[pdf],
        **kw,
    )
    return json.loads(ruta.read_text("utf-8"))


@pytest.mark.unit
def test_registro_es_idempotente_y_completa_la_disponibilidad(tmp_path):
    pdf = _pdf(tmp_path / "a.pdf", None)
    primero = _escribe(tmp_path, pdf)
    assert primero == _escribe(tmp_path, pdf)
    assert len(primero["bulletins"]) == 1
    disponible = bp.parse_first_available("2026-11-07T10:00:00-06:00|captura")
    final = _escribe(tmp_path, pdf, first_available=disponible)
    assert final["bulletins"][0]["after_emission"]["first_available"] is True
    assert final["bulletins"][0]["captured_utc"] == primero["bulletins"][0]["captured_utc"]


@pytest.mark.unit
def test_no_reescribe_una_disponibilidad_distinta(tmp_path):
    pdf = _pdf(tmp_path / "a.pdf", None)
    _escribe(tmp_path, pdf, first_available=bp.parse_first_available("2026-11-07T10:00:00Z|x"))
    with pytest.raises(bp.ProvenanceError, match="ya registrada"):
        _escribe(tmp_path, pdf, first_available=bp.parse_first_available("2026-11-08T10:00:00Z|y"))


@pytest.mark.unit
def test_rechaza_mezclar_releases(tmp_path):
    pdf = _pdf(tmp_path / "a.pdf", None)
    _escribe(tmp_path, pdf)
    with pytest.raises(bp.ProvenanceError, match="release_id"):
        bp.write_provenance(
            tmp_path,
            disease_id="diabetes_t2",
            release_id="otro",
            forecast_emitted_at=EMITIDO,
            pdfs=[pdf],
        )


@pytest.mark.unit
def test_disponibilidad_es_de_un_solo_boletin(tmp_path):
    a, b = _pdf(tmp_path / "a.pdf", None), _pdf(tmp_path / "b.pdf", None)
    with pytest.raises(bp.ProvenanceError, match="un solo"):
        bp.write_provenance(
            tmp_path,
            disease_id="d",
            release_id="r",
            forecast_emitted_at=EMITIDO,
            pdfs=[a, b],
            first_available=bp.parse_first_available("2026-11-07T10:00:00Z|x"),
        )
