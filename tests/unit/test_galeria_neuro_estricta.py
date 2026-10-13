"""Galería neuro: observaciones semanales estrictas por sexo y semana 53 con identidad propia.

Antes, ``boletin_real`` volcaba el primer acumulado de un año que empieza a mitad (neuro 2014 arranca
en la W2) como si fuera el incremento de una semana, y atribuía a una sola semana la diferencia a
través de un hueco del boletín. Además, la semana 53 publicada (2014, 2025) hacía fallar la galería.
"""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import pytest

from epiforecast.utils.semana_epi import ds_de_semana_boletin

pytestmark = pytest.mark.unit


@pytest.fixture
def galeria(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    cfg = sys.modules["epiforecast.utils.config"]
    monkeypatch.setitem(cfg.conf["paths"], "reports", str(tmp_path / "reports"))
    monkeypatch.delitem(sys.modules, "scripts.build_dengue_gallery", raising=False)
    return importlib.import_module("scripts.build_dengue_gallery")


def _boletin(filas: list[tuple[int, int, int, int, int]]) -> pd.DataFrame:
    """(Anio, Semana, Casos_semana, Acumulado_hombres, Acumulado_mujeres) de Colima, Depresión."""
    df = pd.DataFrame(
        filas, columns=["Anio", "Semana", "Casos_semana", "Acumulado_hombres", "Acumulado_mujeres"]
    )
    df["Entidad"] = "Colima"
    df["Padecimiento"] = "Depresión"
    return df


def _real(
    galeria: Any, monkeypatch: pytest.MonkeyPatch, bol: pd.DataFrame, sexo: str
) -> pd.DataFrame:
    monkeypatch.setattr(galeria, "_boletin_neuro", lambda: bol)
    return galeria.boletin_real("Depresión", "Colima", sexo)


def test_primer_acumulado_de_un_anio_a_mitad_no_se_desagrega(galeria, monkeypatch) -> None:
    bol = _boletin([(2014, 2, 40, 300, 500), (2014, 3, 30, 310, 520), (2014, 4, 30, 322, 538)])
    h = _real(galeria, monkeypatch, bol, "hombres")
    assert h["y"].tolist() == [10.0, 12.0]  # la W2 (acumulado de dos semanas) queda ausente
    assert h["ds"].tolist() == [ds_de_semana_boletin(2014, 3), ds_de_semana_boletin(2014, 4)]
    # control: con la regla anterior la W2 entraba como un pico de 300
    g = bol.rename(columns={"Acumulado_hombres": "ah"})
    assert galeria._incrementos_observados(g, "ah").iloc[0] == 300.0


def test_diferencia_a_traves_de_un_hueco_queda_ausente(galeria, monkeypatch) -> None:
    bol = _boletin(
        [
            (2017, 8, 9, 100, 200),
            (2017, 9, 9, 110, 210),
            (2017, 12, 9, 150, 260),
            (2017, 13, 9, 161, 270),
        ]
    )
    m = _real(galeria, monkeypatch, bol, "mujeres")
    assert m["y"].tolist() == [10.0, 10.0]  # 9→12 son tres semanas: no se atribuyen a la 12
    assert ds_de_semana_boletin(2017, 12) not in set(m["ds"])
    assert 0.0 not in set(m["y"])  # lo ausente no se convierte en cero al agregar


def test_la_serie_general_es_el_conteo_semanal_publicado(galeria, monkeypatch) -> None:
    bol = _boletin([(2014, 2, 40, 300, 500), (2014, 3, 30, 310, 520)])
    gen = _real(galeria, monkeypatch, bol, "general")
    assert gen["y"].tolist() == [40.0, 30.0]


def test_semana_53_publicada_se_fecha_y_conserva_su_valor(galeria, monkeypatch) -> None:
    bol = _boletin(
        [
            (2025, 51, 20, 1000, 2000),
            (2025, 52, 21, 1011, 2012),
            (2025, 53, 22, 1023, 2025),
            (2026, 1, 5, 2, 3),
            (2026, 2, 6, 5, 6),
        ]
    )
    gen = _real(galeria, monkeypatch, bol, "general")
    assert dict(zip(gen["ds"].dt.strftime("%Y-%m-%d"), gen["y"], strict=True)) == {
        "2025-12-08": 20.0,
        "2025-12-15": 21.0,
        "2025-12-22": 22.0,  # 2025-W53 con ds propio, sin fundirse en la 52
        "2025-12-29": 6.0,  # 2026-W2; la W1 no es evaluable (colisión del legado)
    }
    h = _real(galeria, monkeypatch, bol, "hombres")
    assert h.loc[h["ds"] == pd.Timestamp("2025-12-22"), "y"].tolist() == [12.0]
