"""Barra de fechas de la galería: semana del boletín (calendario v2), fechas del boletín y corte.

Antes se rotulaba con ``isocalendar`` sobre el ``ds`` legado, así que la semana N del boletín salía
como N-1. Fechas esperadas: portada del boletín W39 de 2026 («del 27 de septiembre al 3 de octubre»)
y el calendario epidemiológico (2027-W36 = 5–11 sep 2027).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from scripts import actualiza_barra_fechas as barra

pytestmark = pytest.mark.unit

_HTML = (
    "<span>Página actualizada: <strong>2 sep 2026</strong></span>"
    "<span>Datos reales hasta: <strong>semana 33 de 2026</strong> (10 ago 2026)</span>"
    "<span>Período pronosticado: <strong>sem 34 2026 → sem 4 2027</strong>"
    " (17 ago 2026 – 25 ene 2027)</span>"
)


def _zoom(tmp_path: Path, corte: dict[str, int] | None, ultimo: str = "2027-08-30") -> Path:
    serie = {"last_real": "2026-09-14", "d": ["2026-06-29", "2026-09-14", ultimo]}
    if corte is not None:
        serie["corte_modelo"] = corte  # type: ignore[assignment]
    p = tmp_path / "zoom.json"
    p.write_text(json.dumps({"a": serie, "b": dict(serie)}), encoding="utf-8")
    return p


def _corre(tmp_path: Path, zoom: Path) -> str:
    index = tmp_path / "index.html"
    index.write_text(_HTML, encoding="utf-8")
    assert barra.actualiza_barra(index, zoom, hoy=dt.date(2026, 10, 13))
    return index.read_text(encoding="utf-8")


def test_semana_real_y_periodo_desde_el_corte(tmp_path: Path) -> None:
    html = _corre(tmp_path, _zoom(tmp_path, {"anio": 2026, "semana": 37}))
    assert "Página actualizada: <strong>13 oct 2026</strong>" in html
    assert "<strong>semana 39 de 2026</strong> (27 sep – 3 oct 2026)" in html
    assert (
        "<strong>sem 38 2026 → sem 36 2027</strong> "
        "(modelos con corte en la semana 37 de 2026; 20 sep 2026 – 11 sep 2027)"
    ) in html


def test_control_la_semana_iso_del_ds_legado_es_la_anterior() -> None:
    assert dt.date(2026, 9, 14).isocalendar()[1] == 38  # lo que rotulaba la versión anterior
    assert barra._semana(dt.date(2026, 9, 14)) == (2026, 39)


def test_sin_corte_declarado_el_periodo_empieza_tras_lo_real(tmp_path: Path) -> None:
    html = _corre(tmp_path, _zoom(tmp_path, None))
    assert "<strong>sem 40 2026 → sem 36 2027</strong> (4 oct 2026 – 11 sep 2027)" in html


def test_ultimo_punto_sin_semana_del_boletin(tmp_path: Path) -> None:
    """2026-12-28 es el lunes que el legado salta: se rotula con la semana previa (2027-W1)."""
    html = _corre(tmp_path, _zoom(tmp_path, {"anio": 2026, "semana": 37}, ultimo="2026-12-28"))
    assert "<strong>sem 38 2026 → sem 1 2027</strong>" in html


def test_cortes_distintos_fallan(tmp_path: Path) -> None:
    p = tmp_path / "zoom.json"
    p.write_text(
        json.dumps(
            {
                "a": {
                    "last_real": "2026-09-14",
                    "d": ["2026-09-14"],
                    "corte_modelo": {"anio": 2026, "semana": 37},
                },
                "b": {
                    "last_real": "2026-09-14",
                    "d": ["2026-09-14"],
                    "corte_modelo": {"anio": 2026, "semana": 33},
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="cortes de modelo distintos"):
        barra.fechas_desde_zoom(p)
