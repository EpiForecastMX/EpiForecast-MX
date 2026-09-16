"""Pruebas del calendario canónico: ``Semana_boletin = ISO(ds) + 1``.

Las anclas provienen de la especificación congelada H-SPEC-1.1 del Protocolo H y no se derivan
del código que se prueba.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from epiforecast.utils.semana_epi import (
    SemanaFueraDeRangoError,
    SemanaUnoLegacyError,
    ds_de_semana_boletin,
    semana_boletin_de_ds,
    semana_boletin_de_serie,
    semanas_del_anio_boletin,
    semanas_iso_del_anio,
)

pytestmark = pytest.mark.unit

# H-SPEC-1.1 §4.1: (semana del boletín 2026, ds legado). La semana 53 solo si la fuente la publica.
ANCLAS = [
    (2, "2025-12-29"),
    (5, "2026-01-19"),
    (6, "2026-01-26"),
    (15, "2026-03-30"),
    (16, "2026-04-06"),
    (31, "2026-07-20"),
    (53, "2026-12-21"),
]

# Enmienda W33: cortes productivos.
CORTES = [(23, "2026-05-25"), (24, "2026-06-01"), (33, "2026-08-03"), (34, "2026-08-10")]


@pytest.mark.parametrize(("semana", "ds"), ANCLAS + CORTES)
def test_anclas_ds_a_semana(semana: int, ds: str) -> None:
    assert semana_boletin_de_ds(ds) == (2026, semana)


@pytest.mark.parametrize(("semana", "ds"), ANCLAS + CORTES)
def test_anclas_semana_a_ds(semana: int, ds: str) -> None:
    assert ds_de_semana_boletin(2026, semana) == pd.Timestamp(ds)


@pytest.mark.parametrize(("semana", "ds"), ANCLAS + CORTES)
def test_identidad_iso_no_sirve(semana: int, ds: str) -> None:
    """Mutante obligatorio: tomar la semana ISO como semana del boletín debe fallar."""
    iso = pd.Timestamp(ds).isocalendar()[1]
    assert iso != semana


def test_ida_y_vuelta_todo_el_anio() -> None:
    for sem in range(2, semanas_del_anio_boletin(2026) + 1):
        assert semana_boletin_de_ds(ds_de_semana_boletin(2026, sem)) == (2026, sem)


def test_semana_uno_no_tiene_ds() -> None:
    with pytest.raises(SemanaUnoLegacyError):
        ds_de_semana_boletin(2026, 1)


def test_semana_fuera_de_rango() -> None:
    with pytest.raises(SemanaFueraDeRangoError):
        ds_de_semana_boletin(2026, semanas_del_anio_boletin(2026) + 1)


def test_w53_conserva_identidad() -> None:
    """La 53 no se trunca ni se funde en la 52: son semanas distintas con ds distintos."""
    assert ds_de_semana_boletin(2026, 52) == pd.Timestamp("2026-12-14")
    assert ds_de_semana_boletin(2026, 53) == pd.Timestamp("2026-12-21")
    assert semana_boletin_de_ds("2026-12-21").semana == 53


def test_frontera_ultima_semana_iso() -> None:
    """La última semana ISO del año ya es la semana 1 del año de boletín siguiente."""
    assert semanas_iso_del_anio(2026) == 53
    assert semana_boletin_de_ds("2026-12-28") == (2027, 1)
    assert semanas_iso_del_anio(2027) == 52
    assert semana_boletin_de_ds(date(2027, 12, 27)) == (2028, 1)


def test_version_vectorizada_coincide_con_la_escalar() -> None:
    fechas = pd.Series(pd.to_datetime([d for _, d in ANCLAS + CORTES] + ["2026-12-28"]))
    tabla = semana_boletin_de_serie(fechas)
    esperado = [semana_boletin_de_ds(f) for f in fechas]
    assert list(tabla["anio_boletin"]) == [e.anio for e in esperado]
    assert list(tabla["semana_boletin"]) == [e.semana for e in esperado]


def test_vectorizada_conserva_el_indice() -> None:
    fechas = pd.Series(pd.to_datetime(["2026-01-26", "2026-08-03"]), index=[7, 9])
    assert list(semana_boletin_de_serie(fechas).index) == [7, 9]


def test_fecha_de_presentacion_equivale_a_ds_mas_siete_dias() -> None:
    """Atajo que usa ``build_tableau``: la fecha de presentación es ``ds + 7 días``.

    Equivale al lunes de la semana ISO del boletín, es decir al ``ds`` de la semana siguiente.
    Se fija aquí para que el atajo no pueda derivar del calendario canónico.
    """
    for semana in range(2, semanas_del_anio_boletin(2026)):
        ds = ds_de_semana_boletin(2026, semana)
        assert ds + pd.Timedelta(weeks=1) == ds_de_semana_boletin(2026, semana + 1)
