"""Base del consolidado frente al raw vigente: duplicados y series sin desglose (tercera auditoría)."""

from __future__ import annotations

from pathlib import Path

import pytest

from epiforecast.publication.consolidado_base import diferencias_base

pytestmark = pytest.mark.unit

_CAB_SEXO = (
    "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_hombres,Acumulado_mujeres,"
    "Acumulado_anio_anterior\n"
)
_CAB_TOTAL = (
    "Anio,Semana,Entidad,Padecimiento,Casos_semana,Acumulado_total,Acumulado_anio_anterior\n"
)


def _escribe(tmp_path: Path, nombre: str, texto: str) -> Path:
    p = tmp_path / nombre
    p.write_text(texto, encoding="utf-8")
    return p


def _con_sexo(tmp_path: Path, base_filas: str, raw_filas: str) -> dict[str, list[tuple[int, int]]]:
    raw = _escribe(tmp_path, "raw.csv", _CAB_SEXO + raw_filas)
    base = _escribe(tmp_path, "base.csv", _CAB_SEXO + base_filas)
    return diferencias_base(base, {"o": raw}, (2026, 43))


_FILA = "2014,2,Aguascalientes,Obesidad,10,6,4,\n"


def test_la_base_identica_no_tiene_diferencias(tmp_path: Path):
    assert _con_sexo(tmp_path, _FILA, _FILA) == {}


def test_un_duplicado_falso_antes_de_la_fila_correcta_se_rechaza(tmp_path: Path):
    """A1: al indexar por clave, la fila correcta ocultaba a la falsa que la precedía."""
    falsa = "2014,2,Aguascalientes,Obesidad,999999,0,0,\n"
    assert _con_sexo(tmp_path, falsa + _FILA, _FILA) == {"o": [(2014, 2)]}


def test_un_duplicado_identico_tambien_se_rechaza(tmp_path: Path):
    assert _con_sexo(tmp_path, _FILA + _FILA, _FILA) == {"o": [(2014, 2)]}


def test_un_duplicado_en_el_raw_se_rechaza(tmp_path: Path):
    falsa = "2014,2,Aguascalientes,Obesidad,999999,0,0,\n"
    assert _con_sexo(tmp_path, _FILA, falsa + _FILA) == {"o": [(2014, 2)]}


def test_un_duplicado_posterior_al_corte_tambien_se_rechaza(tmp_path: Path):
    """La unicidad se exige en toda la historia, no sólo antes de la semana nueva."""
    w43 = "2026,43,Aguascalientes,Obesidad,1,1,0,\n"
    assert _con_sexo(tmp_path, _FILA, _FILA + w43 + w43) == {"o": [(2026, 43)]}


def _sin_sexo(tmp_path: Path, base_fila: str) -> dict[str, list[tuple[int, int]]]:
    raw = _escribe(
        tmp_path,
        "raw.csv",
        _CAB_TOTAL + "2026,42,Aguascalientes,Tumor maligno del cuello del útero,2,120,57.0\n",
    )
    base = _escribe(tmp_path, "base.csv", _CAB_SEXO + base_fila)
    return diferencias_base(base, {"c53": raw}, (2026, 43))


def test_la_serie_sin_desglose_acepta_hombres_y_mujeres_vacios(tmp_path: Path):
    fila = "2026,42,Aguascalientes,Tumor maligno del cuello del útero,2,,,57.0\n"
    assert _sin_sexo(tmp_path, fila) == {}


@pytest.mark.parametrize("h,m", [("12345", "67890"), ("0", ""), ("", "0")])
def test_la_serie_sin_desglose_rechaza_acumulados_por_sexo_inventados(
    tmp_path: Path, h: str, m: str
):
    """A2: la base de una serie sin desglose debe traer H/M vacíos, como se proyecta."""
    fila = f"2026,42,Aguascalientes,Tumor maligno del cuello del útero,2,{h},{m},57.0\n"
    assert _sin_sexo(tmp_path, fila) == {"c53": [(2026, 42)]}
