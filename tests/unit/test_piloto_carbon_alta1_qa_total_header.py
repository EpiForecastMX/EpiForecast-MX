"""Pruebas unitarias sintéticas de reparación de medición QA (TOTAL geométrico y corte de encabezado).

Cubre sin PDFs reales ni valores de producción hardcodeados:
1. Separación geométrica de celdas ``TOTAL`` fusionadas por Camelot usando posiciones impresas de las
   12 columnas (``pdfplumber``), sin usar sumas estatales como oráculo y rechazando celdas vacías.
2. Preservación de discrepancias impresas genuinas en ``TOTAL`` (``total_difiere``) y denominadores
   ausentes o corruptos (``sin_total_12``).
3. Normalización defensiva de espacios intrapalabra por kerning en ``epidemiológica`` y año de 4
   dígitos (``"e pidemioló gica"``, ``"20 21"``) en el subtítulo principal de corte.
4. Preservación de ``None`` (``header_cutoff_unparsed``) en encabezados rasterizados sin usar
   ``Semana N, YYYY`` ni inferir ``N - lag``.
5. Exclusión estricta del subtítulo secundario de rezago 0 del vecino ``A50`` tras ``";"`` y de las
   columnas vecinas ``A50``/``A54`` en ``TOTAL``.
6. No regresión en boletines normales de 12 columnas, 11 columnas ``sin_prev_en_capa_texto`` y otros
   grupos sin flags opt-in.
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

# 12 posiciones de alineación derecha (x1) sintéticas para los 3 bloques [A50(4), A51(4), A54(4)]
_SYNTH_COL_RIGHT_STOPS: tuple[float, ...] = (
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


def _format_thousand_spaces(val: int) -> str:
    return "-" if val == 0 else f"{val:,}".replace(",", " ")


def _words_for_right_aligned_cell(
    text_val: str, x1_stop: float, top: float
) -> list[dict[str, Any]]:
    """Construye subpalabras sintéticas alineadas a ``x1_stop`` con hueco de miles (~2.1 pt)."""
    parts = text_val.split(" ")
    boxes_rev: list[dict[str, Any]] = []
    cursor_x1 = x1_stop
    for part in reversed(parts):
        width = max(3.0, 4.5 * len(part))
        x0 = round(cursor_x1 - width, 2)
        boxes_rev.append({"text": part, "x0": x0, "x1": round(cursor_x1, 2), "top": top})
        cursor_x1 = x0 - 2.1
    return list(reversed(boxes_rev))


class _SyntheticPage12ColQA:
    """Página ``pdfplumber`` 100 % sintética con 12 columnas alineadas a la derecha."""

    width = 580.0
    height = 760.0

    def __init__(
        self,
        body_rows_12: Sequence[Sequence[int]],
        printed_total_cells_12: Sequence[str | None],
        *,
        extra_bridging_word: dict[str, Any] | None = None,
    ) -> None:
        words: list[dict[str, Any]] = []
        # Encabezados de 3 bloques: Sem. / M / F / Acum.
        for blk in range(3):
            s0, s1, s2, s3 = _SYNTH_COL_RIGHT_STOPS[4 * blk : 4 * blk + 4]
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
                words.extend(
                    _words_for_right_aligned_cell(
                        _format_thousand_spaces(val), _SYNTH_COL_RIGHT_STOPS[c_idx], y
                    )
                )

        y_tot = 670.0
        words.append({"text": "TOTAL", "x0": 95.0, "x1": 130.0, "top": y_tot})
        for c_idx, cell_txt in enumerate(printed_total_cells_12):
            if cell_txt is None or cell_txt == "":
                continue
            words.extend(
                _words_for_right_aligned_cell(cell_txt, _SYNTH_COL_RIGHT_STOPS[c_idx], y_tot)
            )
        if extra_bridging_word is not None:
            words.append(extra_bridging_word)

        self._words = words
        self.images: list[dict[str, float]] = []

    def extract_words(self, **_kw: Any) -> list[dict[str, Any]]:
        return list(self._words)


class _SyntheticPdfDocQA:
    def __init__(self, page_obj: Any, n_pages: int = 1) -> None:
        self.pages = [page_obj] * n_pages

    def __enter__(self) -> _SyntheticPdfDocQA:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _FakePyPdfPage:
    def __init__(self, txt: str) -> None:
        self._txt = txt

    def extract_text(self) -> str:
        return self._txt


def _make_pypdf_reader(txt: str) -> Any:
    class _R:
        def __init__(self, _path: str) -> None:
            self.pages = [_FakePyPdfPage(txt)]

    return _R


def _optin_spec() -> dict[str, Any]:
    return {
        "page_anchors": ["adquirida"],
        "state_markers": ["zacatecas"],
        "observation_lag_weeks": 1,
        "n_states_expected": 32,
        "reintento_row_tol": 4,
        "inner_block_columns": {12: [8, 4]},
        "bloque_sin_prev_en_capa_texto": {11: [4, 3, 4]},
    }


def _build_32_state_rows_and_df(
    *,
    a51_per_state: list[int] | None = None,
    camelot_total_12: list[str] | None = None,
) -> tuple[list[list[int]], pd.DataFrame, dict[str, list[int | None]], list[int]]:
    catalog = load_geo_catalog()
    cves = sorted(catalog.cve_ents())
    entidades = [catalog.entity(cve).nombre_canonico for cve in cves]

    body_rows_12: list[list[int]] = []
    table_rows: list[list[str]] = [["FEDERATIVA", *[""] * 12]]
    canon_states: dict[str, list[int | None]] = {}
    sums_12 = [0] * 12

    for idx, (cve, ent) in enumerate(zip(cves, entidades, strict=True)):
        if a51_per_state is not None:
            a51 = list(a51_per_state)
        else:
            # Suma en 32 estados: Sem=112, H=3376, M=6736, prev=10096
            a51 = [3 + (idx % 2), 90 + idx, 195 + idx, 300 + idx]
        row_12 = [1, 5, 4, 6, *a51, 2, 70 + idx, 140 + idx, 320 + idx]
        body_rows_12.append(row_12)
        canon_states[cve] = [int(v) for v in a51]
        for j, v in enumerate(row_12):
            sums_12[j] += v
        table_rows.append([ent, *(_format_thousand_spaces(v) for v in row_12)])

    tot_cells = (
        camelot_total_12
        if camelot_total_12 is not None
        else [_format_thousand_spaces(s) for s in sums_12]
    )
    table_rows.append(["TOTAL", *tot_cells])
    return body_rows_12, pd.DataFrame(table_rows), canon_states, sums_12


def test_merged_total_cells_split_by_printed_column_geometry_and_blank_cell_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Camelot fusiona Sem+H y M+prev en TOTAL dejando ''; geometría PDF separa las 12 columnas."""
    # _parse_printed_total_12 rechaza celdas vacías y fusiones múltiples en lugar de fabricar 0
    tot_blank, unk_blank = qa._parse_printed_total_12(
        [
            "4",
            "154",
            "133",
            "122",
            "104 3 334",
            "",
            "2 076",
            "4 423",
            "72",
            "2 256",
            "1 797",
            "4 512",
        ]
    )
    assert tot_blank is None
    assert {u["col_index"] for u in unk_blank} == {4, 5}

    body_12, camelot_df, canon_states, sums_12 = _build_32_state_rows_and_df(
        camelot_total_12=[
            "32",
            "160",
            "128",
            "192",
            "112 3 376",
            "",
            "6 736 10 096",
            "",
            "64",
            "2 736",
            "4 976",
            "10 736",
        ]
    )
    assert sums_12[4:8] == [112, 3376, 6736, 10096]
    printed_cells_12 = [_format_thousand_spaces(s) for s in sums_12]
    fake_page = _SyntheticPage12ColQA(body_12, printed_cells_12)

    pdf_file = tmp_path / "2018_sem49.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,760,580,0")
    monkeypatch.setattr(
        qa,
        "PdfReader",
        _make_pypdf_reader("Casos hasta la semana epidemiológica 48 del 2018"),
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": camelot_df.copy()})()],
    )
    monkeypatch.setattr(
        "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": camelot_df.copy()})()],
    )
    monkeypatch.setattr(
        "pdfplumber.open",
        lambda _p: _SyntheticPdfDocQA(fake_page),
    )

    res = qa.inspect_one_pdf((str(pdf_file), ["adquirida"], ["zacatecas"], 1, _optin_spec()))
    assert res["status"] == "ok"
    assert res["printed_total_12"] == sums_12
    assert res["printed_total_12"][4:8] == [112, 3376, 6736, 10096]
    assert res["printed_total_unknown_tokens"] == []

    c6 = qa.compare_canon_against_pdf_blocks({(2018, 49): canon_states}, [res])
    assert c6["files_by_status"]["total_coincide"] == ["2018_sem49.pdf"]
    assert c6["files_by_status"]["total_coincide_12col"] == ["2018_sem49.pdf"]
    assert c6["files_by_status"]["total_difiere"] == []


def test_true_printed_total_mismatch_and_missing_denominator_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Errata real impresa en TOTAL queda en total_difiere; celda TOTAL ausente queda sin_total_12."""
    # 1) Errata impresa genuina: estados suman H=3840 (32 * 120), pero el PDF imprime TOTAL H='1 690'
    body_err, df_err, canon_err, sums_err = _build_32_state_rows_and_df(
        a51_per_state=[2, 120, 35, 95],
    )
    printed_err_cells = [_format_thousand_spaces(s) for s in sums_err]
    printed_err_cells[5] = "1 690"  # distinto de sums_err[5] == 3840
    df_err.iloc[-1, 6] = "1 690"

    pdf_err = tmp_path / "2015_sem40.pdf"
    pdf_err.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,760,580,0")
    monkeypatch.setattr(
        qa,
        "PdfReader",
        _make_pypdf_reader("Casos hasta la semana epidemiológica 39 del 2015"),
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": df_err.copy()})()],
    )
    monkeypatch.setattr(
        "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": df_err.copy()})()],
    )
    monkeypatch.setattr(
        "pdfplumber.open",
        lambda _p: _SyntheticPdfDocQA(_SyntheticPage12ColQA(body_err, printed_err_cells)),
    )

    res_err = qa.inspect_one_pdf((str(pdf_err), ["adquirida"], ["zacatecas"], 1, _optin_spec()))
    assert res_err["status"] == "ok"
    assert res_err["printed_total_12"][4:8] == [64, 1690, 1120, 3040]

    c6_err = qa.compare_canon_against_pdf_blocks({(2015, 40): canon_err}, [res_err])
    assert c6_err["files_by_status"]["total_difiere"] == ["2015_sem40.pdf"]
    assert c6_err["files_by_status"]["total_coincide"] == []
    assert c6_err["canon_cell_by_cell_contrast"]["canon_vs_target_a51_diff_cells"] == 0

    # 2) Denominador TOTAL ausente en columna 5 (sin glifo impreso) -> None y sin_total_12, jamás 0
    printed_missing_col: list[str | None] = list(printed_err_cells)
    printed_missing_col[5] = None
    df_missing = df_err.copy()
    df_missing.iloc[-1, 6] = ""
    pdf_miss = tmp_path / "2020_sem10.pdf"
    pdf_miss.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        qa,
        "PdfReader",
        _make_pypdf_reader("Casos hasta la semana epidemiológica 9 del 2020"),
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": df_missing.copy()})()],
    )
    monkeypatch.setattr(
        "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": df_missing.copy()})()],
    )
    monkeypatch.setattr(
        "pdfplumber.open",
        lambda _p: _SyntheticPdfDocQA(_SyntheticPage12ColQA(body_err, printed_missing_col)),
    )

    res_miss = qa.inspect_one_pdf((str(pdf_miss), ["adquirida"], ["zacatecas"], 1, _optin_spec()))
    assert res_miss["status"] == "ok"
    assert res_miss["printed_total_12"] is None
    assert res_miss["printed_total_unknown_tokens"] == [{"col_index": 5, "raw_token": ""}]

    c6_miss = qa.compare_canon_against_pdf_blocks({(2020, 10): canon_err}, [res_miss])
    assert c6_miss["files_by_status"]["sin_total_12"] == ["2020_sem10.pdf"]
    assert c6_miss["files_by_status"]["total_coincide"] == []
    assert c6_miss["files_by_status"]["total_difiere"] == []
    assert c6_miss["canon_cell_by_cell_contrast"]["denominator_cells_4col"] == 128


def test_header_cutoff_parses_intraword_whitespace_and_year_split_defensively(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parsea splits tipográficos reales en epidemiológica y año, rechazando años/semanas inválidos."""
    body_12, camelot_df, canon_states, sums_12 = _build_32_state_rows_and_df()
    fake_page = _SyntheticPage12ColQA(body_12, [_format_thousand_spaces(s) for s in sums_12])

    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,760,580,0")
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": camelot_df.copy()})()],
    )
    monkeypatch.setattr("pdfplumber.open", lambda _p: _SyntheticPdfDocQA(fake_page))

    valid_cases = [
        (
            "2015_sem40.pdf",
            "CUADRO 6.\nhasta la semana e pidemioló gica 39 del 2015\nA50 A51-A53",
            [2015, 39],
        ),
        (
            "2019_sem32.pdf",
            "CUADRO 6.\nhasta la semana epidemioló gica 31 del 2019\nA50 A51-A53",
            [2019, 31],
        ),
        (
            "2019_sem13.pdf",
            "CUADRO 6.\nhasta la semana epidemiológi ca 12 del 2019\nA50 A51-A53",
            [2019, 12],
        ),
        (
            "2021_sem24.pdf",
            "CUADRO 6.\nhasta la semana epidemiológica 23 del 20 21; Sífilis Congénita hasta la semana 24",
            [2021, 23],
        ),
    ]

    rows_ok = []
    canon_lookup = {}
    for fname, header_txt, exp_target in valid_cases:
        p = tmp_path / fname
        p.write_bytes(b"%PDF-1.4\n")
        monkeypatch.setattr(qa, "PdfReader", _make_pypdf_reader(header_txt))
        r = qa.inspect_one_pdf((str(p), ["adquirida"], ["zacatecas"], 1, _optin_spec()))
        assert r["printed_target"] == exp_target
        assert r["lag_matches_mmwr"] is True
        rows_ok.append(r)
        canon_lookup[(int(r["year"]), int(r["week"]))] = canon_states

    c6 = qa.compare_canon_against_pdf_blocks(canon_lookup, rows_ok)
    assert len(c6["files_by_status"]["lag_verified_match"]) == 4
    assert c6["files_by_status"]["header_cutoff_unparsed"] == []
    assert c6["files_by_status"]["lag_mismatch"] == []

    # Casos negativos defensivos: año de 5 dígitos, semana 54 fuera de MMWR y frase sin 'epidemiológica'
    invalid_headers = [
        "hasta la semana epidemiológica 23 del 20 215",
        "hasta la semana epidemiológica 54 del 2021",
        "hasta la semana 23 del 2021",
    ]
    for idx, bad_txt in enumerate(invalid_headers, start=1):
        p_bad = tmp_path / f"2021_sem{idx:02d}.pdf"
        p_bad.write_bytes(b"%PDF-1.4\n")
        monkeypatch.setattr(qa, "PdfReader", _make_pypdf_reader(bad_txt))
        r_bad = qa.inspect_one_pdf((str(p_bad), ["adquirida"], ["zacatecas"], 1, _optin_spec()))
        assert r_bad["printed_target"] is None
        assert r_bad["lag_matches_mmwr"] is None


def test_raster_header_remains_none_never_uses_running_header_or_n_minus_lag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Encabezado rasterizado con cabezal de página 'Semana 12, 2025' permanece None (sin falso PASS)."""
    body_12, camelot_df, canon_states, sums_12 = _build_32_state_rows_and_df()
    fake_page = _SyntheticPage12ColQA(body_12, [_format_thousand_spaces(s) for s in sums_12])

    pdf_raster = tmp_path / "2025_sem12.pdf"
    pdf_raster.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,760,580,0")
    monkeypatch.setattr(
        qa,
        "PdfReader",
        _make_pypdf_reader(
            "Vigilancia Epidemiológica Semana 12, 2025\nENTIDAD FEDERATIVA A50 A51-A53"
        ),
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": camelot_df.copy()})()],
    )
    monkeypatch.setattr("pdfplumber.open", lambda _p: _SyntheticPdfDocQA(fake_page))

    res = qa.inspect_one_pdf((str(pdf_raster), ["adquirida"], ["zacatecas"], 1, _optin_spec()))
    assert res["status"] == "ok"
    assert res["printed_target"] is None
    assert res["lag_matches_mmwr"] is None

    c6 = qa.compare_canon_against_pdf_blocks({(2025, 12): canon_states}, [res])
    assert c6["files_by_status"]["header_cutoff_unparsed"] == ["2025_sem12.pdf"]
    assert c6["files_by_status"]["lag_verified_match"] == []
    assert c6["files_by_status"]["lag_mismatch"] == []


def test_neighbor_a50_lag0_subtitle_after_semicolon_and_a50_total_never_chosen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Jamás selecciona el corte lag-0 del vecino A50 tras ';' ni el TOTAL de A50."""
    body_12, camelot_df, canon_states, sums_12 = _build_32_state_rows_and_df()
    fake_page = _SyntheticPage12ColQA(body_12, [_format_thousand_spaces(s) for s in sums_12])

    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,760,580,0")
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": camelot_df.copy()})()],
    )
    monkeypatch.setattr("pdfplumber.open", lambda _p: _SyntheticPdfDocQA(fake_page))

    # 1) Corte principal con '20 21' seguido tras ';' por corte completo lag-0 de Sífilis Congénita (24)
    pdf_dual = tmp_path / "2021_sem24.pdf"
    pdf_dual.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        qa,
        "PdfReader",
        _make_pypdf_reader(
            "CUADRO 6.\nhasta la semana epidemiológica 23 del 20 21; "
            "Sífilis Congénita hasta la semana epidemiológica 24 del 2021"
        ),
    )
    res_dual = qa.inspect_one_pdf((str(pdf_dual), ["adquirida"], ["zacatecas"], 1, _optin_spec()))
    assert res_dual["printed_target"] == [2021, 23]
    assert res_dual["lag_matches_mmwr"] is True

    # 2) Si el corte principal antes de ';' es ilegible, devuelve None y NO cae al subtítulo A50 tras ';'
    for corrupt_txt in (
        "hasta la semana [ilegible]; Sífilis Congénita hasta la semana epidemiológica 24 del 2021",
        "hasta la semana [ilegible];\nSífilis Congénita hasta la semana epidemiológica 24 del 2021",
        "Sífilis Congénita hasta la semana epidemiológica 24 del 2021",
    ):
        monkeypatch.setattr(qa, "PdfReader", _make_pypdf_reader(corrupt_txt))
        r_corrupt = qa.inspect_one_pdf(
            (str(pdf_dual), ["adquirida"], ["zacatecas"], 1, _optin_spec())
        )
        assert r_corrupt["printed_target"] is None
        assert r_corrupt["lag_matches_mmwr"] is None

    # 3) Si canon_csv tuviera por error las celdas de A50 en lugar de A51, C6 lo detecta en celdas y TOTAL
    catalog = load_geo_catalog()
    a50_wrong_canon: dict[str, list[int | None]] = {
        cve: [1, 5, 4, 6] for cve in sorted(catalog.cve_ents())
    }
    c6_wrong = qa.compare_canon_against_pdf_blocks({(2021, 24): a50_wrong_canon}, [res_dual])
    assert c6_wrong["canon_cell_by_cell_contrast"]["canon_vs_target_a51_diff_cells"] == 128
    assert c6_wrong["canon_cell_by_cell_contrast"]["bulletins_where_canon_equals_left_a50"] == [
        "2021_sem24.pdf"
    ]
    assert c6_wrong["files_by_status"]["total_difiere"] == ["2021_sem24.pdf"]


def test_normal_12col_11col_sin_prev_and_other_groups_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """12 col normal, 11 col sin_prev_en_capa_texto y tareas de otros grupos conservan sus contratos."""
    _, camelot_df_12, canon_12, sums_12 = _build_32_state_rows_and_df()

    # 1) Tarea de 4 elementos (otros grupos sin group_spec) con PDF stub y 12 columnas limpias
    pdf_other_12 = tmp_path / "2024_sem20.pdf"
    pdf_other_12.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(qa, "find_cuadro_page", lambda *_a, **_k: 1)
    monkeypatch.setattr(qa, "_area_pagina", lambda *_a, **_k: "0,760,580,0")
    monkeypatch.setattr(
        qa,
        "PdfReader",
        _make_pypdf_reader("Casos hasta la semana epidemiológica 19 del 2024"),
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": camelot_df_12.copy()})()],
    )
    monkeypatch.setattr(
        "scripts.piloto_carbon_alta1.qa_serie_extraida.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": camelot_df_12.copy()})()],
    )

    res_4tuple = qa.inspect_one_pdf((str(pdf_other_12), ["adquirida"], ["zacatecas"], 1))
    assert res_4tuple["status"] == "ok"
    assert res_4tuple["printed_total_12"] == sums_12
    assert res_4tuple["printed_target"] == [2024, 19]
    assert res_4tuple["lag_matches_mmwr"] is True

    # 2) Otro grupo con 8 columnas (sin bloque_sin_prev_en_capa_texto) mantiene unexpected_shape
    df_8col = camelot_df_12.iloc[:, :9].copy()
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": df_8col.copy()})()],
    )
    res_8col = qa.inspect_one_pdf((str(pdf_other_12), ["adquirida"], ["zacatecas"], 1))
    assert res_8col["status"] == "unexpected_shape"
    assert res_8col["data_cols"] == 8

    # 3) 11 columnas con bloque_sin_prev_en_capa_texto mantiene proyección None en índice 7
    catalog = load_geo_catalog()
    cves = sorted(catalog.cve_ents())
    entidades = [catalog.entity(cve).nombre_canonico for cve in cves]
    rows_11 = [["FEDERATIVA", *[""] * 11]]
    sums_11 = [0] * 11
    canon_11: dict[str, list[int | None]] = {}
    for idx, (cve, ent) in enumerate(zip(cves, entidades, strict=True)):
        vals_11 = [2, 10, 8, 12, 4 + idx, 50 + idx, 30 + idx, 3, 15, 20, 25]
        for j, v in enumerate(vals_11):
            sums_11[j] += v
        canon_11[cve] = [4 + idx, 50 + idx, 30 + idx, None]
        rows_11.append([ent, *(_format_thousand_spaces(v) for v in vals_11)])
    rows_11.append(["TOTAL", *(_format_thousand_spaces(s) for s in sums_11)])
    df_11 = pd.DataFrame(rows_11)

    class _Fake11GeoPage:
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
    monkeypatch.setattr(qa, "PdfReader", _make_pypdf_reader("CUADRO 6 Sífilis adquirida"))
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": df_11.copy()})()],
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.camelot.read_pdf",
        lambda *_a, **_k: [type("T", (), {"df": df_11.copy()})()],
    )
    monkeypatch.setattr("pdfplumber.open", lambda _p: _SyntheticPdfDocQA(_Fake11GeoPage()))

    res_11 = qa.inspect_one_pdf((str(pdf_11), ["adquirida"], ["zacatecas"], 1, _optin_spec()))
    assert res_11["status"] == "ok"
    assert res_11["optional_prev_in_image"] is True
    assert res_11["printed_total_12"] == [*sums_11[:7], None, *sums_11[7:]]
    assert res_11["printed_target"] is None

    c6_11 = qa.compare_canon_against_pdf_blocks({(2026, 42): canon_11}, [res_11])
    assert c6_11["files_by_status"]["total_coincide_11col_sin_prev"] == ["2026_sem42.pdf"]
    assert c6_11["files_by_status"]["header_cutoff_unparsed_raster_prev"] == ["2026_sem42.pdf"]
    assert len(canon_12) == 32
