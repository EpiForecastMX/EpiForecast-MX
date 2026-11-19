"""Pruebas unitarias herméticas de la reparación opt-in de layout para ``cuadro_6_sifilis_adquirida``.

Cubre las dos causas medidas en los 27 boletines inválidos de 2025-2026:
1. ``reintento_row_tol: 4`` cuando ``row_tol=2`` parte números y nombres de entidad dejando las 32
   entidades con celdas vacías (p. ej. ``2025_sem02.pdf``, ``2026_sem01.pdf``).
2. ``bloque_sin_prev_en_capa_texto: {11: [4, 3, 4]}`` cuando el PDF imprime ``Acum.`` del año
   anterior de ``A51-A53`` como imágenes de celda sin capa de texto (p. ej. ``2025_sem12.pdf``,
   ``2026_sem42.pdf``), emitiendo ``3col_noprev`` con ``Acumulado_anio_anterior = pd.NA`` explícito
   tras validar el ``TOTAL`` de 11 columnas y la geometría de imágenes de esa banda.
"""

from __future__ import annotations

from typing import Any

from omegaconf import OmegaConf
import pandas as pd
import pytest

from epiforecast.data.extraction import cuadro_capa_texto as cct
from epiforecast.data.extraction import cuadro_extractor as ce

pytestmark = pytest.mark.unit

GRUPO = "cuadro_6_sifilis_adquirida"
DISEASE = "sifilis_adquirida_a51"

ESTADOS_32 = [
    "Aguascalientes",
    "Baja California",
    "Baja California Sur",
    "Campeche",
    "Coahuila",
    "Colima",
    "Chiapas",
    "Chihuahua",
    "Ciudad de México",
    "Durango",
    "Guanajuato",
    "Guerrero",
    "Hidalgo",
    "Jalisco",
    "México",
    "Michoacán",
    "Morelos",
    "Nayarit",
    "Nuevo León",
    "Oaxaca",
    "Puebla",
    "Querétaro",
    "Quintana Roo",
    "San Luis Potosí",
    "Sinaloa",
    "Sonora",
    "Tabasco",
    "Tamaulipas",
    "Tlaxcala",
    "Veracruz",
    "Yucatán",
    "Zacatecas",
]


def _fixture_partido_causa1() -> tuple[pd.DataFrame, pd.DataFrame, list[list[int]]]:
    """Reproduce el patrón exacto de 2025_sem02.pdf: cruda partida (row_tol=2) vs unida (row_tol=4)."""
    filas_partidas: list[list[str]] = [
        ["", "Sem.", "", "", "Acum.", "Sem.", "", "", "Acum.", "Sem.", "", "", "Acum.", "", ""]
    ]
    filas_unidas: list[list[str]] = [["FEDERATIVA", *[""] * 12]]
    esperados_a51: list[list[int]] = []
    sumas_12 = [0] * 12

    for i, est in enumerate(ESTADOS_32):
        a50 = ["-", "-", "-", "-"]
        sem_51 = i + 1
        h_51 = 10 + i
        m_51 = 20 + i
        prev_51 = 100 + i
        a54 = ["1", "2", "3", "4"]
        esperados_a51.append([sem_51, h_51, m_51, prev_51])
        vals_12 = [0, 0, 0, 0, sem_51, h_51, m_51, prev_51, 1, 2, 3, 4]
        for j, v in enumerate(vals_12):
            sumas_12[j] += v

        # Con row_tol=2 el primer '-' cae en col 0 y deja 3 columnas vacías intermedias -> 11 col vacías en estado
        filas_partidas.append(
            [
                "-",
                "-",
                "-",
                "-",
                str(sem_51),
                "",
                str(h_51),
                str(m_51),
                str(prev_51),
                "1",
                "",
                "2",
                "",
                "3",
                "4",
            ]
        )
        filas_partidas.append([est, *[""] * 14])
        filas_unidas.append([est, *a50, str(sem_51), str(h_51), str(m_51), str(prev_51), *a54])

    tot_str = ["-" if s == 0 else f"{s:,}".replace(",", " ") for s in sumas_12]
    filas_unidas.append(["TOTAL", *tot_str])
    return pd.DataFrame(filas_partidas), pd.DataFrame(filas_unidas), esperados_a51


def _fixture_11col_causa2() -> tuple[pd.DataFrame, list[list[int]]]:
    """Reproduce el patrón exacto de 2026_sem42.pdf: 4 A50 + 3 A51 (Sem,H,M) + 4 A54 + TOTAL 11 col."""
    filas: list[list[str]] = [["FEDERATIVA", *[""] * 11]]
    esperados_a51_3col: list[list[int]] = []
    sumas_11 = [0] * 11

    for i, est in enumerate(ESTADOS_32):
        a50 = [500 + i, 600 + i, 700 + i, 800 + i]
        a51_3 = [2 + i, 150 + i, 90 + i]
        a54 = [900 + i, 1000 + i, 1100 + i, 1200 + i]
        esperados_a51_3col.append(a51_3)
        vals_11 = [*a50, *a51_3, *a54]
        for j, v in enumerate(vals_11):
            sumas_11[j] += v
        filas.append([est, *(f"{v:,}".replace(",", " ") for v in vals_11)])

    filas.append(["TOTAL", *(f"{s:,}".replace(",", " ") for s in sumas_11)])
    return pd.DataFrame(filas), esperados_a51_3col


class _FakePageGeometry:
    """Página sintética pdfplumber con encabezados reales de Cuadro 6 e imágenes en banda central."""

    width = 540.0
    height = 720.0

    def __init__(
        self,
        *,
        include_central_acum_text: bool = False,
        omit_left_acum_text: bool = False,
        n_central_images: int = 33,
        extra_outside_image: bool = False,
        stray_word_in_gap: bool = False,
    ) -> None:
        self._words: list[dict[str, Any]] = [
            # Encabezados de los 3 bloques (top entre 178 y 191; Aguascalientes en top=201.3)
            {"text": "Sem.", "x0": 139.9, "x1": 156.3, "top": 183.5},
            {"text": "H", "x0": 175.2, "x1": 180.3, "top": 189.5},
            {"text": "M", "x0": 204.3, "x1": 210.6, "top": 189.5},
            {"text": "Sem.", "x0": 258.3, "x1": 274.7, "top": 183.5},
            {"text": "H", "x0": 293.1, "x1": 298.3, "top": 189.5},
            {"text": "M", "x0": 321.2, "x1": 327.6, "top": 189.5},
            {"text": "Sem.", "x0": 375.7, "x1": 392.2, "top": 183.5},
            {"text": "H", "x0": 412.1, "x1": 417.3, "top": 189.5},
            {"text": "M", "x0": 444.3, "x1": 450.7, "top": 189.5},
            {"text": "Acum.", "x0": 469.3, "x1": 490.9, "top": 183.5},
            {"text": "Aguascalientes", "x0": 45.3, "x1": 98.8, "top": 201.3},
            {"text": "95", "x0": 326.9, "x1": 334.4, "top": 201.0},
            {"text": "-", "x0": 391.8, "x1": 394.0, "top": 201.0},
            {"text": "TOTAL", "x0": 75.9, "x1": 101.1, "top": 637.0},
            # Pie de página debajo de TOTAL: no debe confundirse con celda de la tabla
            {"text": "Epidemiológica,", "x0": 340.0, "x1": 372.0, "top": 651.0},
        ]
        if not omit_left_acum_text:
            self._words.append({"text": "Acum.", "x0": 226.1, "x1": 247.7, "top": 183.5})
        if include_central_acum_text:
            self._words.append({"text": "Acum.", "x0": 342.0, "x1": 364.0, "top": 183.5})
        if stray_word_in_gap:
            self._words.append({"text": "429", "x0": 348.0, "x1": 362.0, "top": 215.0})

        # Logo superior (top=35, fuera del cuerpo) + celdas imagen en banda central (x ~ 345..368)
        self.images: list[dict[str, float]] = [{"x0": 410.0, "x1": 510.0, "top": 35.0}]
        for k in range(n_central_images):
            self.images.append({"x0": 345.0, "x1": 368.0, "top": 201.0 + k * 13.0})
        if extra_outside_image:
            self.images.append({"x0": 230.0, "x1": 247.0, "top": 220.0})

    def extract_words(self, **_kw: Any) -> list[dict[str, Any]]:
        return list(self._words)


class _FakePdfPlumberDoc:
    def __init__(self, page_obj: _FakePageGeometry, n_pages: int = 24) -> None:
        self.pages = [page_obj] * n_pages

    def __enter__(self) -> _FakePdfPlumberDoc:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _patch_camelot_and_pdfplumber(
    monkeypatch: pytest.MonkeyPatch,
    read_pdf_fn: Any,
    page_obj: _FakePageGeometry | None = None,
) -> None:
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_extractor.camelot.read_pdf", read_pdf_fn
    )
    monkeypatch.setattr(
        "epiforecast.data.extraction.cuadro_capa_texto.camelot.read_pdf", read_pdf_fn
    )
    if page_obj is not None:
        monkeypatch.setattr(
            "epiforecast.data.extraction.cuadro_capa_texto.pdfplumber.open",
            lambda _p: _FakePdfPlumberDoc(page_obj),
        )


def test_solo_cuadro_6_sifilis_adquirida_declara_reparaciones_opt_in() -> None:
    raw = OmegaConf.to_container(OmegaConf.load(ce._cuadros_path()), resolve=True)
    assert isinstance(raw, dict)
    grupos = raw["cuadro_groups"]
    con_rt = sorted(g for g, s in grupos.items() if "reintento_row_tol" in s)
    con_sp = sorted(g for g, s in grupos.items() if "bloque_sin_prev_en_capa_texto" in s)
    # alta_b44: la gonocócica comparte la página del cuadro 6 y su renglón partido.
    assert con_rt == sorted(
        [
            GRUPO,
            "alta20_mordedura_perro_w54",
            "alta20_mordedura_mamiferos_w55",
            "b44_gonococica_a54",
            "b44_violencia_intrafamiliar_y07",
            "b44_sifilis_congenita_a50",
            "b44_herida_arma_fuego_w32",
        ]
    )
    assert con_sp == [GRUPO]

    spec = grupos[GRUPO]
    assert spec["reintento_row_tol"] == 4
    assert spec["inner_block_columns"] == {12: [8, 4]}
    assert spec["bloque_sin_prev_en_capa_texto"] == {11: [4, 3, 4]}
    excl = sorted(e["file"] for e in spec["source_exclusions"])
    assert excl == ["2014_sem01.pdf", "2016_sem20.pdf"]


def test_causa1_regresion_antes_y_recuperacion_con_row_tol_4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    cruda_partida, cruda_unida, esperados = _fixture_partido_causa1()
    pdf = tmp_path / "2025_sem02.pdf"
    pdf.write_bytes(b"%PDF")
    llamadas: list[dict[str, Any]] = []

    def fake_read_pdf(_path: str, **_kw: Any) -> list[Any]:
        llamadas.append(_kw)
        df = cruda_unida if _kw.get("row_tol") == 4 else cruda_partida
        return [type("T", (), {"df": df})()]

    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 24)
    monkeypatch.setattr(ce, "_area_pagina", lambda *_a: "0,842,595,0")
    _patch_camelot_and_pdfplumber(monkeypatch, fake_read_pdf)

    # 1) Regresión ANTES: sin reintento_row_tol falla con "columnas inesperadas: 11 (esperaba [12])"
    spec_antes = {
        k: v
        for k, v in ce.load_group(GRUPO).items()
        if k not in ("reintento_row_tol", "bloque_sin_prev_en_capa_texto")
    }
    monkeypatch.setattr(ce, "load_group", lambda _g: dict(spec_antes))
    antes = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert not antes["valid"]
    assert antes["reason"] == "columnas inesperadas: 11 (esperaba [12])"

    # 2) DESPUÉS: con la configuración opt-in real recupera las 32 entidades y 4 columnas exactas
    monkeypatch.undo()
    llamadas.clear()
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 24)
    monkeypatch.setattr(ce, "_area_pagina", lambda *_a: "0,842,595,0")
    _patch_camelot_and_pdfplumber(monkeypatch, fake_read_pdf)

    despues = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert despues["valid"], despues["reason"]
    assert despues["layout"] == "4col_prev"
    assert despues["reparacion"] == "row_tol=4"
    assert "cuadra con el TOTAL impreso" in despues["reason"]
    assert any(k.get("row_tol") == 4 for k in llamadas)

    df = despues["df"].set_index("Entidad")
    cols = ["Casos_semana", "Acumulado_hombres", "Acumulado_mujeres", "Acumulado_anio_anterior"]
    assert len(df) == 32
    assert int(df[cols].isna().sum().sum()) == 0
    for est, vals in zip(ESTADOS_32, esperados, strict=True):
        assert df.loc[est, cols].tolist() == vals


def test_causa1_lectura_valida_por_omision_no_reintenta_y_negativas_fallan_cerrado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    cruda_partida, cruda_unida, _ = _fixture_partido_causa1()
    pdf = tmp_path / "2024_sem10.pdf"
    pdf.write_bytes(b"%PDF")
    llamadas: list[dict[str, Any]] = []

    def fake_ok(_path: str, **kw: Any) -> list[Any]:
        llamadas.append(kw)
        return [type("T", (), {"df": cruda_unida})()]

    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 24)
    monkeypatch.setattr(ce, "_area_pagina", lambda *_a: "0,842,595,0")
    _patch_camelot_and_pdfplumber(monkeypatch, fake_ok)

    ok_normal = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert ok_normal["valid"]
    assert "reparacion" not in ok_normal
    assert ok_normal["reason"] == "ok"
    assert len(llamadas) == 1 and "row_tol" not in llamadas[0]

    # Negativa A: si aun con row_tol=4 siguen vacías las filas estatales, falla cerrado (jamás ceros)
    _patch_camelot_and_pdfplumber(
        monkeypatch, lambda *_a, **_k: [type("T", (), {"df": cruda_partida})()]
    )
    fallo_vacio = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert not fallo_vacio["valid"]
    assert "filas estatales sin valores" in fallo_vacio["reason"]

    # Negativa B: si row_tol=4 recupera 12 columnas pero el TOTAL impreso difiere, falla cerrado
    mala_total = cruda_unida.copy()
    mala_total.iloc[-1, 5] = "99999"
    _patch_camelot_and_pdfplumber(
        monkeypatch,
        lambda *_a, **kw: [
            type("T", (), {"df": mala_total if kw.get("row_tol") == 4 else cruda_partida})()
        ],
    )
    fallo_tot = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert not fallo_tot["valid"]
    assert "distinta del TOTAL impreso" in fallo_tot["reason"]


def test_causa2_regresion_antes_y_extraccion_3col_noprev_validada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    cruda_11, esperados_3 = _fixture_11col_causa2()
    pdf = tmp_path / "2026_sem42.pdf"
    pdf.write_bytes(b"%PDF")

    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 24)
    monkeypatch.setattr(ce, "_area_pagina", lambda *_a: "0,720,540,0")
    _patch_camelot_and_pdfplumber(
        monkeypatch,
        lambda *_a, **_k: [type("T", (), {"df": cruda_11})()],
        _FakePageGeometry(),
    )

    # 1) Regresión ANTES: sin bloque_sin_prev_en_capa_texto falla con columnas inesperadas: 11
    spec_antes = {
        k: v for k, v in ce.load_group(GRUPO).items() if k != "bloque_sin_prev_en_capa_texto"
    }
    monkeypatch.setattr(ce, "load_group", lambda _g: dict(spec_antes))
    antes = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert not antes["valid"]
    assert antes["reason"] == "columnas inesperadas: 11 (esperaba [12])"

    # 2) DESPUÉS: extrae Sem/H/M exactos de A51 (nunca vecinos A50>=500 ni A54>=900) y prev = pd.NA
    monkeypatch.undo()
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 24)
    monkeypatch.setattr(ce, "_area_pagina", lambda *_a: "0,720,540,0")
    _patch_camelot_and_pdfplumber(
        monkeypatch,
        lambda *_a, **_k: [type("T", (), {"df": cruda_11})()],
        _FakePageGeometry(),
    )

    despues = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert despues["valid"], despues["reason"]
    assert despues["layout"] == "3col_noprev"
    assert despues["reparacion"] == "sin_prev_en_capa_texto"
    assert despues["reason"] == cct.MOTIVO_SIN_PREV_TEXTO

    df = despues["df"].set_index("Entidad")
    assert len(df) == 32
    assert bool(df["Acumulado_anio_anterior"].isna().all())
    assert (
        int(df[["Casos_semana", "Acumulado_hombres", "Acumulado_mujeres"]].isna().sum().sum()) == 0
    )
    assert int(df["Casos_semana"].max()) < 500
    for est, vals3 in zip(ESTADOS_32, esperados_3, strict=True):
        assert (
            df.loc[est, ["Casos_semana", "Acumulado_hombres", "Acumulado_mujeres"]].tolist()
            == vals3
        )


@pytest.mark.parametrize(
    ("geo_kwargs", "esperado_en_motivo"),
    [
        ({"include_central_acum_text": True}, "patrón de encabezados Acum."),
        ({"omit_left_acum_text": True}, "patrón de encabezados Acum."),
        ({"n_central_images": 10}, "imágenes de celda en banda central"),
        ({"extra_outside_image": True}, "imágenes de celda en banda central"),
        ({"stray_word_in_gap": True}, "tokens de texto dentro de la banda"),
    ],
)
def test_causa2_negativas_geometria_impiden_mezclar_bloques(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    geo_kwargs: dict[str, Any],
    esperado_en_motivo: str,
) -> None:
    cruda_11, _ = _fixture_11col_causa2()
    pdf = tmp_path / "2026_sem42.pdf"
    pdf.write_bytes(b"%PDF")

    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 24)
    monkeypatch.setattr(ce, "_area_pagina", lambda *_a: "0,720,540,0")
    _patch_camelot_and_pdfplumber(
        monkeypatch,
        lambda *_a, **_k: [type("T", (), {"df": cruda_11})()],
        _FakePageGeometry(**geo_kwargs),
    )

    res = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert not res["valid"]
    assert res["df"] is None
    assert esperado_en_motivo in res["reason"]


def test_causa2_negativas_total_descuadrado_celda_vacia_y_ancho_ajeno(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    cruda_11, _ = _fixture_11col_causa2()
    pdf = tmp_path / "2026_sem42.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *_a: 24)
    monkeypatch.setattr(ce, "_area_pagina", lambda *_a: "0,720,540,0")

    # 1) TOTAL de 11 columnas no cuadra
    mala_tot = cruda_11.copy()
    mala_tot.iloc[-1, 6] = "1"
    _patch_camelot_and_pdfplumber(
        monkeypatch,
        lambda *_a, **_k: [type("T", (), {"df": mala_tot})()],
        _FakePageGeometry(),
    )
    r_tot = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert not r_tot["valid"]
    assert "distinta del TOTAL impreso" in r_tot["reason"]

    # 2) Celda vacía '' en tabla de 11 columnas
    con_hueco = cruda_11.copy()
    con_hueco.iloc[2, 6] = ""
    _patch_camelot_and_pdfplumber(
        monkeypatch,
        lambda *_a, **_k: [type("T", (), {"df": con_hueco})()],
        _FakePageGeometry(),
    )
    r_hueco = ce.extract_cuadro_from_pdf(str(pdf), GRUPO, DISEASE)
    assert not r_hueco["valid"]
    assert "celdas o filas vacías" in r_hueco["reason"]

    # 3) Otro grupo con inner_block_columns {12: [8, 4]} sin opt-in sigue rechazando 11 columnas
    _patch_camelot_and_pdfplumber(
        monkeypatch,
        lambda *_a, **_k: [type("T", (), {"df": cruda_11})()],
        _FakePageGeometry(),
    )
    r_otro = ce.extract_cuadro_from_pdf(str(pdf), "alta20c_cisticercosis_b69", "cisticercosis_b69")
    assert not r_otro["valid"]
    assert r_otro["reason"] == "columnas inesperadas: 11 (esperaba [12])"
