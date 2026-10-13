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


def _tablas(m: Any, con_dengue: bool) -> None:
    m.TABLA_333.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "padecimiento": ["Depresión", "Dengue", "Dengue"],
            "entidad": ["Nacional", "Nacional", "Colima"],
            "sexo": ["general"] * 3,
            "modelo_produccion": ["Ensemble", "Stacking", "Prophet"],
        }
    ).to_excel(m.TABLA_333, index=False)
    if con_dengue:
        pd.DataFrame(
            {
                "padecimiento": ["Dengue", "Dengue"],
                "entidad": ["Nacional", "Colima"],
                "sexo": ["general"] * 2,
                "motor_productivo": ["DeepAR", "Prophet"],
            }
        ).to_csv(m.PROD_DENGUE, index=False)


def test_dengue_sale_solo_de_la_asignacion_congelada(tmp_path, monkeypatch) -> None:
    """Las filas Dengue de tabla_333 (copiadas de la previa) no deben sumarse a la asignación.

    Antes cada serie Dengue quedaba dos veces en el mapa y ``freeze`` la congelaba con ambos
    motores, incluido Stacking, que no es elegible para Dengue.
    """
    m = _modulo(_boletin(tmp_path / "boletin.csv", 31), tmp_path, monkeypatch)
    _tablas(m, con_dengue=True)
    prod = m._load_prod_map()
    den = prod[prod["pad_norm"] == "dengue"].set_index("entidad")["motor_key"]
    assert den.to_dict() == {"Nacional": "deepar", "Colima": "prophet"}
    assert not prod.duplicated(["pad_norm", "entidad", "sexo"]).any()
    assert prod.loc[prod["pad_norm"] == "depresion", "motor_key"].tolist() == ["ensemble"]


def test_sin_asignacion_dengue_se_conserva_la_tabla(tmp_path, monkeypatch) -> None:
    """Control: sin ``produccion_dengue.csv`` la tabla es la única fuente y no se descarta."""
    m = _modulo(_boletin(tmp_path / "boletin.csv", 31), tmp_path, monkeypatch)
    _tablas(m, con_dengue=False)
    prod = m._load_prod_map()
    assert (prod["pad_norm"] == "dengue").sum() == 2
