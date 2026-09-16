"""Pruebas del congelado prospectivo (`scripts.pronostico_congelado`).

El script no tenía pruebas propias. Estas fijan el calendario que usa para cortar y para
etiquetar, que es donde vivía un desfase de una semana contra el boletín.

El módulo se importa dentro de cada prueba, no al colectar: ``tests/conftest.py`` inyecta un
``epiforecast.utils.config`` mínimo cuyo ``paths`` no trae ``reports``, y el script lo resuelve
al importarse.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

import pandas as pd
import pytest

from epiforecast.utils.semana_epi import ds_de_semana_boletin, semana_boletin_de_serie

pytestmark = pytest.mark.unit


def _modulo(boletin: str, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Importa el script con una configuración utilizable en pruebas.

    Todo cambio va por ``monkeypatch``: el ``conf`` que inyecta ``tests/conftest.py`` es un dict
    global del proceso, y mutarlo sin restaurar rompía a otras pruebas que resuelven ``reports``.
    """
    cfg = sys.modules["epiforecast.utils.config"]
    monkeypatch.setitem(cfg.conf["paths"], "reports", str(tmp_path / "reports"))
    monkeypatch.setitem(cfg.conf["data"], "boletin", boletin)
    monkeypatch.delitem(sys.modules, "scripts.pronostico_congelado", raising=False)
    return importlib.import_module("scripts.pronostico_congelado")


def _boletin(path: Any, ultima_semana: int) -> str:
    filas = [
        {"Padecimiento": "Depresión", "Anio": 2026, "Semana": s, "Casos_semana": 10}
        for s in range(2, ultima_semana + 1)
    ]
    pd.DataFrame(filas).to_csv(path, index=False)
    return str(path)


def test_corte_es_el_ds_de_la_ultima_semana_observada(tmp_path, monkeypatch) -> None:
    """El corte cae en el ds de la última semana del boletín, no una semana después.

    Con el cálculo anterior el corte quedaba en el lunes de la semana ISO igual al número de
    semana, siete días tarde, y el congelado descartaba la primera semana no vista.
    """
    m = _modulo(_boletin(tmp_path / "boletin.csv", 31), tmp_path, monkeypatch)
    anio, wk, corte = m._cutoffs()[m._norm("Depresión")]
    assert (anio, wk) == (2026, 31)
    assert corte == ds_de_semana_boletin(2026, 31) == pd.Timestamp("2026-07-20")


def test_corte_no_trunca_la_semana_53(tmp_path, monkeypatch) -> None:
    m = _modulo(_boletin(tmp_path / "boletin.csv", 53), tmp_path, monkeypatch)
    _, wk, corte = m._cutoffs()[m._norm("Depresión")]
    assert wk == 53
    assert corte == pd.Timestamp("2026-12-21")  # ds propio de la 53, no el de la 52


def test_la_etiqueta_iso_guardada_no_sirve_para_unir() -> None:
    """Los congelados antiguos guardaron la semana ISO cruda; ``ds`` es el dato autoritativo.

    Por eso ``validar`` re-deriva la semana desde ``ds`` en lugar de confiar en la columna.
    """
    snap = pd.DataFrame({"ds": pd.to_datetime(["2026-05-18", "2026-07-20"])})
    iso = snap["ds"].dt.isocalendar().week.astype(int)
    canonico = semana_boletin_de_serie(snap["ds"])["semana_boletin"]
    assert list(iso) == [21, 30]
    assert list(canonico) == [22, 31]
