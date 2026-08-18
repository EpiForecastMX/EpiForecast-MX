"""Contratos de la sincronizacion aditiva del consolidado.

El consolidado es una superposicion: filas versionadas por el flujo automatizado y
filas que solo existen en local (el carril de obesidad). La sincronizacion debe sumar
las semanas nuevas sin retirar lo local, y debe negarse a continuar si el origen
cambio una fila que ya existia, porque eso es una correccion de la fuente y no una
semana nueva.
"""

from pathlib import Path

import pandas as pd
import pytest
from scripts.sincroniza_consolidado import (
    SincronizacionError,
    discrepancias_en_comun,
    filas_nuevas,
    sincroniza,
)

CLAVE = ["Anio", "Semana", "Entidad", "Padecimiento"]


def _fila(anio, semana, entidad, padecimiento, casos, ant=None):
    return {
        "Anio": anio,
        "Semana": semana,
        "Entidad": entidad,
        "Padecimiento": padecimiento,
        "Casos_semana": casos,
        "Acumulado_hombres": casos,
        "Acumulado_mujeres": casos,
        "Acumulado_anio_anterior": ant,
    }


@pytest.fixture
def local(tmp_path: Path) -> Path:
    """Consolidado local: dos semanas de un padecimiento publicado y uno solo local."""
    filas = [
        _fila(2026, 27, "Jalisco", "Depresión", 10),
        _fila(2026, 27, "Jalisco", "Obesidad", 99),
    ]
    ruta = tmp_path / "consolidado.csv"
    pd.DataFrame(filas).to_csv(ruta, index=False)
    return ruta


def test_agrega_las_semanas_nuevas(local: Path) -> None:
    versionado = pd.DataFrame(
        [
            _fila(2026, 27, "Jalisco", "Depresión", 10),
            _fila(2026, 28, "Jalisco", "Depresión", 12),
        ]
    )
    resumen = sincroniza(local, versionado, aplicar=True)

    assert resumen["filas_nuevas"] == 1
    assert resumen["aplicado"] is True
    despues = pd.read_csv(local)
    assert len(despues) == 3
    assert set(despues.query("Semana == 28")["Casos_semana"]) == {12}


def test_preserva_los_padecimientos_que_solo_existen_en_local(local: Path) -> None:
    """Es el caso que un pull forzado destruye: obesidad no esta en el origen."""
    versionado = pd.DataFrame(
        [
            _fila(2026, 27, "Jalisco", "Depresión", 10),
            _fila(2026, 28, "Jalisco", "Depresión", 12),
        ]
    )
    resumen = sincroniza(local, versionado, aplicar=True)

    assert resumen["padecimientos_solo_locales"] == ["Obesidad"]
    despues = pd.read_csv(local)
    assert (despues["Padecimiento"] == "Obesidad").sum() == 1


def test_se_niega_si_el_origen_corrigio_una_fila_existente(local: Path) -> None:
    """Un valor distinto en una fila ya conocida no es una semana nueva."""
    versionado = pd.DataFrame([_fila(2026, 27, "Jalisco", "Depresión", 777)])

    with pytest.raises(SincronizacionError, match="correccion de la fuente"):
        sincroniza(local, versionado, aplicar=True)

    assert pd.read_csv(local).query("Padecimiento == 'Depresión'")["Casos_semana"].iloc[0] == 10


def test_el_modo_en_seco_no_escribe(local: Path) -> None:
    antes = local.read_bytes()
    versionado = pd.DataFrame(
        [
            _fila(2026, 27, "Jalisco", "Depresión", 10),
            _fila(2026, 28, "Jalisco", "Depresión", 12),
        ]
    )
    resumen = sincroniza(local, versionado, aplicar=False)

    assert resumen["filas_nuevas"] == 1
    assert resumen["aplicado"] is False
    assert local.read_bytes() == antes


def test_sin_novedades_no_cambia_nada(local: Path) -> None:
    versionado = pd.DataFrame([_fila(2026, 27, "Jalisco", "Depresión", 10)])
    antes = local.read_bytes()

    resumen = sincroniza(local, versionado, aplicar=True)

    assert resumen["filas_nuevas"] == 0
    assert local.read_bytes() == antes


def test_dos_ausencias_no_son_discrepancia() -> None:
    """Comparar nulos directamente marcaria como distinta una fila identica."""
    a = pd.DataFrame([_fila(2026, 27, "Jalisco", "Depresión", 10, ant=None)])
    b = pd.DataFrame([_fila(2026, 27, "Jalisco", "Depresión", 10, ant=None)])

    assert discrepancias_en_comun(a, b).empty


def test_filas_nuevas_distingue_por_la_clave_completa() -> None:
    """Misma semana y entidad, otro padecimiento: es una fila nueva, no un conflicto."""
    local_df = pd.DataFrame([_fila(2026, 27, "Jalisco", "Depresión", 10)])
    versionado = pd.DataFrame(
        [
            _fila(2026, 27, "Jalisco", "Depresión", 10),
            _fila(2026, 27, "Jalisco", "Parkinson", 4),
        ]
    )

    nuevas = filas_nuevas(versionado, local_df)

    assert len(nuevas) == 1
    assert nuevas.iloc[0]["Padecimiento"] == "Parkinson"


def test_la_fusion_no_deja_claves_duplicadas(local: Path) -> None:
    versionado = pd.DataFrame(
        [
            _fila(2026, 28, "Jalisco", "Depresión", 12),
            _fila(2026, 29, "Jalisco", "Depresión", 13),
        ]
    )
    sincroniza(local, versionado, aplicar=True)

    despues = pd.read_csv(local)
    assert not despues.duplicated(subset=CLAVE).any()


def test_la_escritura_no_deja_temporal(local: Path) -> None:
    """La escritura es atomica: ni al terminar queda un .part que confunda al inventario."""
    versionado = pd.DataFrame(
        [
            _fila(2026, 27, "Jalisco", "Depresión", 10),
            _fila(2026, 28, "Jalisco", "Depresión", 12),
        ]
    )
    sincroniza(local, versionado, aplicar=True)

    assert list(local.parent.glob("*.part")) == []
