"""Reintentos del extractor de cuadros que sólo actúan cuando faltan entidades.

2024_sem09 (Cuadro 3.5): camelot delimita la tabla desde Baja California y deja fuera a
Aguascalientes; con el área de la página completa lee las 32. Una lectura válida no cambia.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from epiforecast.data.extraction import cuadro_extractor as ce

pytestmark = pytest.mark.unit


def _tabla(n: int) -> pd.DataFrame:
    from epiforecast.data.extraction.dengue_extractor import _STATE_LOOKUP

    estados = sorted(set(_STATE_LOOKUP.values()))
    assert len(estados) == 32
    filas = [[e, "1", "2", "3", "4", "5", "6", "7", "8"] for e in estados[:n]]
    return pd.DataFrame(filas, columns=list(range(9)))


@pytest.fixture
def falso_pdf(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    llamadas: list[dict[str, Any]] = []
    monkeypatch.setattr(ce, "find_cuadro_page", lambda *a, **k: 16)
    monkeypatch.setattr(ce, "_area_pagina", lambda *a, **k: "0,842,595,0")
    return llamadas


def test_reintento_con_pagina_completa_recupera_la_entidad(
    monkeypatch: pytest.MonkeyPatch, falso_pdf: list[dict[str, Any]]
) -> None:
    def tabla(pdf: str, page: int, **kw: Any) -> pd.DataFrame:
        falso_pdf.append(kw)
        return _tabla(32 if "table_areas" in kw else 31)

    monkeypatch.setattr(ce, "_tabla_estatal", tabla)
    r = ce.extract_cuadro_from_pdf("x/2024_sem09.pdf", "alta20_hepatitis_a_b15", "hepatitis_a_b15")
    assert r["valid"] and r["n_states"] == 32
    assert any("table_areas" in kw for kw in falso_pdf)


def test_una_lectura_completa_no_reintenta(
    monkeypatch: pytest.MonkeyPatch, falso_pdf: list[dict[str, Any]]
) -> None:
    def tabla(pdf: str, page: int, **kw: Any) -> pd.DataFrame:
        falso_pdf.append(kw)
        return _tabla(32)

    monkeypatch.setattr(ce, "_tabla_estatal", tabla)
    r = ce.extract_cuadro_from_pdf("x/2024_sem09.pdf", "alta20_hepatitis_a_b15", "hepatitis_a_b15")
    assert r["valid"]
    assert len(falso_pdf) == 1 and "table_areas" not in falso_pdf[0]


def test_la_reparacion_de_valor_en_nombre_solo_se_pide_en_grupos_que_la_declaran(
    monkeypatch: pytest.MonkeyPatch, falso_pdf: list[dict[str, Any]]
) -> None:
    def tabla(pdf: str, page: int, **kw: Any) -> pd.DataFrame:
        falso_pdf.append(kw)
        return _tabla(32)

    monkeypatch.setattr(ce, "_tabla_estatal", tabla)
    ce.extract_cuadro_from_pdf("x/2024_sem09.pdf", "alta20_hepatitis_a_b15", "hepatitis_a_b15")
    assert falso_pdf[-1].get("valor_en_nombre") is False
    assert ce.load_group("alta10b_helmintiasis_b65").get("valor_en_columna_nombre") is True
    assert ce.load_group("alta20_giardiasis_a071").get("valor_en_columna_nombre") is True
    assert not ce.load_group("alta20_ascariasis_b77").get("valor_en_columna_nombre")
