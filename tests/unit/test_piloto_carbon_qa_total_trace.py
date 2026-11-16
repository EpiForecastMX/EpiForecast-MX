"""Pruebas unitarias herméticas de trazabilidad del método de medición TOTAL por PDF (Fable R3).

Verifica sin abrir PDFs reales ni reejecutar QA masiva:
1. ``pdfplumber_geometry_12col`` cuando la página tiene geometría válida de 12 columnas, con
   ``total_measurement_fallback_reason=None`` y preservación estricta del ``TOTAL`` impreso
   (incluidas discrepancias impresas genuinas, sin usar sumas estatales como oráculo).
2. Respaldo Camelot estricto cuando ``has_12_col_geometry=False`` (con motivo explícito, tanto en
   flujo normal como con ``reintento_row_tol``).
3. Registro explícito ``pdfplumber_exception:<Tipo>: <mensaje>`` cuando ``pdfplumber`` lanza una
   excepción, manteniendo el respaldo estricto sin silencio diagnóstico.
4. Celda vacía o token puenteado en geometría de 12 columnas: mantiene ``printed_total_12=None``
   (``sin_total_12``), método ``pdfplumber_geometry_12col`` y ``fallback_reason=None`` sin caer a
   Camelot ni fabricar ceros.
5. Boletines de 11 columnas (``optional_prev_in_image``) y estados no ``ok`` (``total_measurement_method=None``).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from scripts.piloto_carbon_alta1 import qa_serie_extraida as qa

from epiforecast.data.epi_geo_exposure import load_geo_catalog

pytestmark = pytest.mark.unit

_SYNTH_STOPS_12: tuple[float, ...] = (
    198.0,
    228.0,
    258.0,
    288.0,
    318.0,
    348.0,
    378.0,
    410.0,
    440.0,
    470.0,
    500.0,
    532.0,
)


def _fmt_thousands(val: int) -> str:
    return "-" if val == 0 else f"{val:,}".replace(",", " ")


def _cell_words(text_val: str, x1_stop: float, top: float) -> list[dict[str, Any]]:
    parts = text_val.split(" ")
    boxes_rev: list[dict[str, Any]] = []
    cursor_x1 = x1_stop
    for part in reversed(parts):
        width = max(3.0, 4.5 * len(part))
        x0 = round(cursor_x1 - width, 2)
        boxes_rev.append({"text": part, "x0": x0, "x1": round(cursor_x1, 2), "top": top})
        cursor_x1 = x0 - 2.1
    return list(reversed(boxes_rev))


class _TracePage12Col:
    width = 580.0
    height = 760.0

    def __init__(
        self,
        body_rows_12: Sequence[Sequence[int]],
        total_cells_12: Sequence[str | None],
        *,
        bridging_word: dict[str, Any] | None = None,
    ) -> None:
        words: list[dict[str, Any]] = []
        for blk in range(3):
            s0, s1, s2, s3 = _SYNTH_STOPS_12[4 * blk : 4 * blk + 4]
            words.extend(
                [
                    {"text": "Sem.", "x0": s0 - 18.0, "x1": s0, "top": 220.0},
                    {"text": "Acum.", "x0": s1 - 8.0, "x1": s2 - 4.0, "top": 217.5},
                    {"text": "M", "x0": s1 - 8.0, "x1": s1, "top": 229.0},
                    {"text": "F", "x0": s2 - 6.0, "x1": s2, "top": 229.0},
                    {"text": "Acum.", "x0": s3 - 24.0, "x1": s3, "top": 220.0},
                ]
            )
        catalog = load_geo_catalog()
        entidades = [catalog.entity(cve).nombre_canonico for cve in sorted(catalog.cve_ents())]
        for r_idx, (ent, row_vals) in enumerate(zip(entidades, body_rows_12, strict=True)):
            y = 245.0 + r_idx * 12.5
            words.append({"text": ent.split()[0], "x0": 60.0, "x1": 135.0, "top": y})
            for c_idx, val in enumerate(row_vals):
                words.extend(_cell_words(_fmt_thousands(val), _SYNTH_STOPS_12[c_idx], y))
        y_tot = 670.0
        words.append({"text": "TOTAL", "x0": 95.0, "x1": 130.0, "top": y_tot})
        for c_idx, cell_txt in enumerate(total_cells_12):
            if cell_txt:
                words.extend(_cell_words(cell_txt, _SYNTH_STOPS_12[c_idx], y_tot))
        if bridging_word is not None:
            words.append(bridging_word)
        self._words = words
        self.images: list[dict[str, float]] = []

    def extract_words(self, **_kw: Any) -> list[dict[str, Any]]:
        return list(self._words)


class _FakePdfDoc:
    def __init__(self, page_obj: Any) -> None:
        self.pages = [page_obj]

    def __enter__(self) -> _FakePdfDoc:
        return self

    def __exit__(self, *_a: object) -> None:
        return None


def _make_reader(text: str) -> Any:
    class _Page:
        def extract_text(self) -> str:
            return text

    class _Reader:
        def __init__(self, _path: str) -> None:
            self.pages = [_Page()]

    return _Reader


def _group_spec_optin() -> dict[str, Any]:
    return {
        "n_states_expected": 32,
        "observation_lag_weeks": 1,
        "page_anchors": ["adquirida"],
        "state_markers": ["zacatecas"],
        "reintento_row_tol": 4,
        "inner_block_columns": {12: [8, 4]},
        "bloque_sin_prev_en_capa_texto": {11: [4, 3, 4]},
    }


def _fixture_32_states() -> tuple[
    list[list[int]], pd.DataFrame, dict[str, list[int | None]], list[int]
]:
    catalog = load_geo_catalog()
    cves = sorted(catalog.cve_ents())
    entidades = [catalog.entity(cve).nombre_canonico for cve in cves]
    body_rows: list[list[int]] = []
    camelot_rows: list[list[str]] = [["FEDERATIVA", *[""] * 12]]
    canon_a51: dict[str, list[int | None]] = {}
    sums_12 = [0] * 12
    for idx, (cve, ent) in enumerate(zip(cves, entidades, strict=True)):
        row = [
            1 + (idx % 3),
            10 + idx,
            8 + idx,
            15 + idx,
            3 + (idx % 4),
            100 + idx,
            60 + idx,
            130 + idx,
            2 + (idx % 2),
            20 + idx,
            18 + idx,
            25 + idx,
        ]
        body_rows.append(row)
        for j, v in enumerate(row):
            sums_12[j] += v
        canon_a51[cve] = [row[4], row[5], row[6], row[7]]
        camelot_rows.append([ent, *(_fmt_thousands(v) for v in row)])
    camelot_rows.append(["TOTAL", *(_fmt_thousands(s) for s in sums_12)])
    return body_rows, pd.DataFrame(camelot_rows), canon_a51, sums_12


def _wire_common_mocks(
    monkeypatch: pytest.MonkeyPatch, camelot_df: pd.DataFrame, header_text: str
) -> None:
    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,760,580,0")
    monkeypatch.setattr(qa, "PdfReader", _make_reader(header_text))
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": camelot_df.copy()})()],
    )
    monkeypatch.setattr(
        "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": camelot_df.copy()})()],
    )


def test_total_trace_geometry_12col_success_and_errata_without_sum_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Geometría 12col registra método pdfplumber_geometry_12col y preserva errata impresa real."""
    body_rows, camelot_df, canon_a51, sums_12 = _fixture_32_states()
    # Camelot tendría fusión espuria en TOTAL, pero geometría lee los tokens reales impresos:
    fused_df = camelot_df.copy()
    fused_df.iloc[-1, 5] = f"{sums_12[4]}{sums_12[5]}"
    fused_df.iloc[-1, 6] = ""

    _wire_common_mocks(monkeypatch, fused_df, "Casos hasta la semana epidemiológica 19 del 2024")
    page_ok = _TracePage12Col(body_rows, [_fmt_thousands(s) for s in sums_12])
    monkeypatch.setattr("pdfplumber.open", lambda _p: _FakePdfDoc(page_ok))

    pdf_ok = tmp_path / "2024_sem20.pdf"
    pdf_ok.write_bytes(b"%PDF-1.4\n")
    res_ok = qa.inspect_one_pdf(
        (str(pdf_ok), ["adquirida"], ["zacatecas"], 1, _group_spec_optin())
    )
    assert res_ok["status"] == "ok"
    assert res_ok["has_12_col_geometry"] is True
    assert res_ok["total_measurement_method"] == "pdfplumber_geometry_12col"
    assert res_ok["total_measurement_fallback_reason"] is None
    assert res_ok["printed_total_12"] == sums_12

    # Errata impresa genuina (H impreso = 1697 != suma estatal): NO usa suma estatal como oráculo
    errata_totals = list(sums_12)
    errata_totals[5] = 1697
    page_err = _TracePage12Col(body_rows, [_fmt_thousands(s) for s in errata_totals])
    monkeypatch.setattr("pdfplumber.open", lambda _p: _FakePdfDoc(page_err))
    pdf_err = tmp_path / "2015_sem40.pdf"
    pdf_err.write_bytes(b"%PDF-1.4\n")
    res_err = qa.inspect_one_pdf(
        (str(pdf_err), ["adquirida"], ["zacatecas"], 1, _group_spec_optin())
    )
    assert res_err["total_measurement_method"] == "pdfplumber_geometry_12col"
    assert res_err["total_measurement_fallback_reason"] is None
    assert res_err["printed_total_12"][5] == 1697

    c6 = qa.compare_canon_against_pdf_blocks(
        {(2024, 20): canon_a51, (2015, 40): canon_a51},
        [res_ok, res_err],
    )
    assert c6["files_by_status"]["total_coincide_12col"] == ["2024_sem20.pdf"]
    assert c6["files_by_status"]["total_difiere"] == ["2015_sem40.pdf"]
    assert c6["total_measurement_method_counts"] == {"pdfplumber_geometry_12col": 2}
    assert c6["total_measurement_fallback_files"] == []


def test_total_trace_geometry_false_and_pdfplumber_exception_record_fallback_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Geometría ausente o excepción en pdfplumber registran método de respaldo y motivo exacto."""
    _, camelot_df, canon_a51, sums_12 = _fixture_32_states()
    _wire_common_mocks(monkeypatch, camelot_df, "Casos hasta la semana epidemiológica 19 del 2024")

    # 1) Página sin geometría de 12 columnas (p. ej. palabras vacías) → motivo missing_state_or_total_anchor
    class _EmptyGeoPage:
        def extract_words(self, **_kw: Any) -> list[dict[str, Any]]:
            return []

    monkeypatch.setattr("pdfplumber.open", lambda _p: _FakePdfDoc(_EmptyGeoPage()))
    pdf_fb = tmp_path / "2024_sem20.pdf"
    pdf_fb.write_bytes(b"%PDF-1.4\n")
    res_fb = qa.inspect_one_pdf(
        (str(pdf_fb), ["adquirida"], ["zacatecas"], 1, _group_spec_optin())
    )
    assert res_fb["status"] == "ok"
    assert res_fb["has_12_col_geometry"] is False
    assert res_fb["total_measurement_method"] == "camelot_fallback_stream"
    assert res_fb["total_measurement_fallback_reason"] == "missing_state_or_total_anchor"
    assert res_fb["printed_total_12"] == sums_12

    # 2) Excepción en pdfplumber.open → motivo explícito pdfplumber_exception:<Tipo>: <mensaje>
    def _boom(_path: str) -> Any:
        raise RuntimeError("xref stream corrupt")

    monkeypatch.setattr("pdfplumber.open", _boom)
    pdf_exc = tmp_path / "2024_sem21.pdf"
    pdf_exc.write_bytes(b"%PDF-1.4\n")
    res_exc = qa.inspect_one_pdf(
        (str(pdf_exc), ["adquirida"], ["zacatecas"], 1, _group_spec_optin())
    )
    assert res_exc["status"] == "ok"
    assert res_exc["has_12_col_geometry"] is False
    assert res_exc["total_measurement_method"] == "camelot_fallback_stream"
    assert (
        res_exc["total_measurement_fallback_reason"]
        == "pdfplumber_exception:RuntimeError: xref stream corrupt"
    )
    assert res_exc["printed_total_12"] == sums_12

    c6 = qa.compare_canon_against_pdf_blocks(
        {(2024, 20): canon_a51, (2024, 21): canon_a51},
        [res_fb, res_exc],
    )
    assert c6["total_measurement_method_counts"] == {"camelot_fallback_stream": 2}
    assert c6["total_measurement_fallback_files"] == [
        {
            "file": "2024_sem20.pdf",
            "method": "camelot_fallback_stream",
            "fallback_reason": "missing_state_or_total_anchor",
        },
        {
            "file": "2024_sem21.pdf",
            "method": "camelot_fallback_stream",
            "fallback_reason": "pdfplumber_exception:RuntimeError: xref stream corrupt",
        },
    ]


def test_total_trace_unknown_tokens_and_none_field_in_11col_and_non_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Token desconocido/celda vacía en geometría deja printed_total_12=None sin caer a Camelot; no-ok tiene None."""
    body_rows, camelot_df, canon_a51, sums_12 = _fixture_32_states()
    _wire_common_mocks(monkeypatch, camelot_df, "Casos hasta la semana epidemiológica 19 del 2024")

    # 1) Token puenteando dos columnas en TOTAL con geometría válida → printed_total_12=None
    bridging = {"text": "999999", "x0": 310.0, "x1": 355.0, "top": 670.0}
    page_bridge = _TracePage12Col(
        body_rows, [_fmt_thousands(s) for s in sums_12], bridging_word=bridging
    )
    monkeypatch.setattr("pdfplumber.open", lambda _p: _FakePdfDoc(page_bridge))
    pdf_unk = tmp_path / "2024_sem22.pdf"
    pdf_unk.write_bytes(b"%PDF-1.4\n")
    res_unk = qa.inspect_one_pdf(
        (str(pdf_unk), ["adquirida"], ["zacatecas"], 1, _group_spec_optin())
    )
    assert res_unk["status"] == "ok"
    assert res_unk["has_12_col_geometry"] is True
    assert res_unk["total_measurement_method"] == "pdfplumber_geometry_12col"
    assert res_unk["total_measurement_fallback_reason"] is None
    assert res_unk["printed_total_12"] is None
    assert len(res_unk["printed_total_unknown_tokens"]) == 1

    c6_unk = qa.compare_canon_against_pdf_blocks({(2024, 22): canon_a51}, [res_unk])
    assert c6_unk["files_by_status"]["sin_total_12"] == ["2024_sem22.pdf"]
    assert c6_unk["total_measurement_fallback_files"] == []

    # 2) Estado no-ok (no_page / bad_filename) expone campos de método explícitamente en None
    res_bad = qa.inspect_one_pdf(("nombre_invalido.pdf", ["adquirida"], ["zacatecas"], 1))
    assert res_bad["status"] == "bad_filename"
    assert res_bad["total_measurement_method"] is None
    assert res_bad["total_measurement_fallback_reason"] is None

    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: None)
    res_nopage = qa.inspect_one_pdf((str(pdf_unk), ["adquirida"], ["zacatecas"], 1))
    assert res_nopage["status"] == "no_page"
    assert res_nopage["total_measurement_method"] is None
    assert res_nopage["total_measurement_fallback_reason"] is None
    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)

    # 3) Celda vacía en TOTAL con geometría 12col → printed_total_12=None, método geométrico
    cells_with_gap: list[str | None] = [_fmt_thousands(s) for s in sums_12]
    cells_with_gap[6] = None
    monkeypatch.setattr(
        "pdfplumber.open", lambda _p: _FakePdfDoc(_TracePage12Col(body_rows, cells_with_gap))
    )
    res_gap = qa.inspect_one_pdf(
        (str(pdf_unk), ["adquirida"], ["zacatecas"], 1, _group_spec_optin())
    )
    assert res_gap["has_12_col_geometry"] is True
    assert res_gap["total_measurement_method"] == "pdfplumber_geometry_12col"
    assert res_gap["total_measurement_fallback_reason"] is None
    assert res_gap["printed_total_12"] is None

    # 4) 11 columnas con bloque_sin_prev_en_capa_texto → método proyectado y campo 7 en None
    catalog = load_geo_catalog()
    cves = sorted(catalog.cve_ents())
    entidades = [catalog.entity(cve).nombre_canonico for cve in cves]
    rows_11 = [["FEDERATIVA", *[""] * 11]]
    sums_11 = [0] * 11
    for idx, ent in enumerate(entidades):
        vals_11 = [2, 10, 8, 12, 4 + idx, 50 + idx, 30 + idx, 3, 15, 20, 25]
        for j, v in enumerate(vals_11):
            sums_11[j] += v
        rows_11.append([ent, *(_fmt_thousands(v) for v in vals_11)])
    rows_11.append(["TOTAL", *(_fmt_thousands(s) for s in sums_11)])
    df_11 = pd.DataFrame(rows_11)

    class _Page11Col:
        width = 540.0
        height = 720.0

        def __init__(self) -> None:
            self._words = [
                {"text": "Sem.", "x0": 139.9, "x1": 156.3, "top": 183.5},
                {"text": "H", "x0": 175.2, "x1": 180.3, "top": 189.5},
                {"text": "M", "x0": 204.3, "x1": 210.6, "top": 189.5},
                {"text": "Acum.", "x0": 226.1, "x1": 247.7, "top": 183.5},
                {"text": "Sem.", "x0": 258.3, "x1": 274.7, "top": 183.5},
                {"text": "H", "x0": 293.1, "x1": 298.3, "top": 189.5},
                {"text": "M", "x0": 321.2, "x1": 327.6, "top": 189.5},
                {"text": "Sem.", "x0": 375.7, "x1": 392.2, "top": 183.5},
                {"text": "H", "x0": 412.1, "x1": 417.3, "top": 189.5},
                {"text": "M", "x0": 444.3, "x1": 450.7, "top": 189.5},
                {"text": "Acum.", "x0": 469.3, "x1": 490.9, "top": 183.5},
                {"text": "Aguascalientes", "x0": 45.3, "x1": 98.8, "top": 201.3},
                {"text": "TOTAL", "x0": 75.9, "x1": 101.1, "top": 637.0},
            ]
            self.images = [{"x0": 345.0, "x1": 368.0, "top": 201.0 + k * 13.0} for k in range(33)]

        def extract_words(self, **_kw: Any) -> list[dict[str, Any]]:
            return list(self._words)

    pdf_11 = tmp_path / "2026_sem42.pdf"
    pdf_11.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": df_11.copy()})()],
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": df_11.copy()})()],
    )
    monkeypatch.setattr("pdfplumber.open", lambda _p: _FakePdfDoc(_Page11Col()))
    res_11 = qa.inspect_one_pdf(
        (str(pdf_11), ["adquirida"], ["zacatecas"], 1, _group_spec_optin())
    )
    assert res_11["status"] == "ok"
    assert res_11["has_12_col_geometry"] is False
    assert res_11["total_measurement_method"] == "camelot_11col_sin_prev_projected"
    assert res_11["total_measurement_fallback_reason"] == "optional_prev_in_image_11col"
    assert res_11["printed_total_12"] == [*sums_11[:7], None, *sums_11[7:]]

    # 5) Contrato retrocompatible de 3 elementos en measure_printed_total_12_pdfplumber
    monkeypatch.setattr("pdfplumber.open", lambda _p: _FakePdfDoc(page_bridge))
    tot_3, unk_3, has_geo_3 = qa.measure_printed_total_12_pdfplumber(str(pdf_unk), 1)
    assert tot_3 is None
    assert len(unk_3) == 1
    assert has_geo_3 is True
