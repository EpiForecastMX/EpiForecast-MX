"""Pruebas de la galería (`scripts.build_dengue_gallery`), que no tenía ninguna.

Cubren las dos piezas que el sitio usaba mal: el calendario con el que se fecha lo real y la
construcción de las series por sexo.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

import pandas as pd
import pytest

from epiforecast.utils.semana_epi import ds_de_semana_boletin

pytestmark = pytest.mark.unit


@pytest.fixture
def galeria(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Importa la galería con una configuración utilizable en pruebas.

    El módulo resuelve ``conf["paths"]["reports"]`` al importarse y ``tests/conftest.py`` inyecta
    un ``conf`` mínimo que no trae esa clave. Todo va por ``monkeypatch`` para no contaminar a
    otras pruebas, que fue lo que rompió la suite la primera vez.
    """
    cfg = sys.modules["epiforecast.utils.config"]
    monkeypatch.setitem(cfg.conf["paths"], "reports", str(tmp_path / "reports"))
    monkeypatch.delitem(sys.modules, "scripts.build_dengue_gallery", raising=False)
    return importlib.import_module("scripts.build_dengue_gallery")


def test_fecha_usa_el_calendario_canonico(galeria) -> None:
    """La semana N del boletín se fecha con su ds legado, no con el lunes de la semana ISO N."""
    g = pd.DataFrame({"Anio": [2026, 2026], "Semana": [6, 31], "c": [1, 2]})
    out = galeria._fecha_boletin(g)
    assert list(out["ds"]) == [ds_de_semana_boletin(2026, 6), ds_de_semana_boletin(2026, 31)]
    assert list(out["ds"].dt.date.astype(str)) == ["2026-01-26", "2026-07-20"]


def test_semana_1_se_descarta_y_la_53_conserva_identidad(galeria) -> None:
    g = pd.DataFrame({"Anio": [2026] * 4, "Semana": [1, 6, 52, 53], "c": [9, 1, 2, 3]})
    out = galeria._fecha_boletin(g)
    assert 1 not in set(out["Semana"])  # sin ds distinguible en el calendario legado
    ds52 = out.loc[out["Semana"] == 52, "ds"].iloc[0]
    ds53 = out.loc[out["Semana"] == 53, "ds"].iloc[0]
    assert ds52 != ds53
    assert str(ds53.date()) == "2026-12-21"


def test_sexo_usa_incrementos_reales_no_una_proporcion(galeria) -> None:
    """Hombres y mujeres salen del acumulado publicado, no de repartir la serie general."""
    g = pd.DataFrame({"Anio": [2026] * 4, "Semana": [2, 3, 4, 5], "ah": [10, 25, 45, 70]})
    assert galeria._incrementos_observados(g, "ah").tolist() == [10.0, 15.0, 20.0, 25.0]


def test_acumulado_que_baja_se_repone_sin_mirar_el_futuro(galeria) -> None:
    """Un ajuste retrospectivo de la fuente se repara con los incrementos previos."""
    g = pd.DataFrame({"Anio": [2026] * 5, "Semana": [2, 3, 4, 5, 6], "ah": [10, 25, 20, 40, 55]})
    inc = galeria._incrementos_observados(g, "ah").tolist()
    assert inc[:2] == [10.0, 15.0]
    assert inc[2] == 12.0  # media de los dos previos (10 y 15), redondeada
    assert inc[3:] == [20.0, 15.0]


def test_sin_antecedente_utilizable_queda_ausente(galeria) -> None:
    """Sin incrementos previos válidos no se inventa un valor."""
    g = pd.DataFrame({"Anio": [2026] * 2, "Semana": [2, 3], "ah": [-5, 1]})
    assert pd.isna(galeria._incrementos_observados(g, "ah").iloc[0])


def _zoom_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    fechas = pd.to_datetime(["2026-06-01", "2026-06-08", "2026-06-15", "2026-06-22"])
    real = pd.DataFrame({"ds": fechas, "y": [10.0, 11.0, 12.0, 13.0]})
    fc = pd.DataFrame({"ds": fechas, "yhat": [10.0, 11.0, 12.0, 13.0]})
    return real, fc


def test_zoom_declara_el_intervalo_del_motor(galeria) -> None:
    """Con banda propia, el payload la declara disponible para que la gráfica la dibuje."""
    real, fc = _zoom_frames()
    fc["yhat_lower"] = fc["yhat"] - 2
    fc["yhat_upper"] = fc["yhat"] + 2
    payload = galeria.zoom_payload(real, fc, "Prophet")
    assert payload["intervalo_disponible"] is True


def test_zoom_declara_ausencia_cuando_la_banda_es_degenerada(galeria) -> None:
    """Ensemble y Stacking emiten ``lower == upper == yhat``: el sitio no debe dibujar banda."""
    real, fc = _zoom_frames()
    fc["yhat_lower"] = fc["yhat"]
    fc["yhat_upper"] = fc["yhat"]
    payload = galeria.zoom_payload(real, fc, "Stacking")
    assert payload["intervalo_disponible"] is False


def test_zoom_declara_ausencia_sin_columnas_de_banda(galeria) -> None:
    real, fc = _zoom_frames()
    payload = galeria.zoom_payload(real, fc, "Ensemble")
    assert payload["intervalo_disponible"] is False
