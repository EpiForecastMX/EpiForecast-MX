"""Pruebas del calendario canónico (versión 2): semana del boletín, ``ds`` legado y fecha del boletín.

Las anclas del año 2026 provienen de la especificación congelada H-SPEC-1.1 del Protocolo H; la
del 2026-W53 queda sustituida por la enmienda de calendario W53 (13-oct-2026): 2026 tiene 52
semanas del boletín y 2026-12-21 es la semana 1 de 2027. Las fronteras de año se anclan en los
máximos publicados del consolidado (53 semanas en 2014, 2020 y 2025) y en la portada del boletín
W39 de 2026, no en el código que se prueba. La equivalencia con el legado se comprueba ejecutando
el propio ``DataTransformation``.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from epiforecast.data.preprocessing.transformer import DataTransformation
from epiforecast.utils.semana_epi import (
    CALENDARIO_VERSION,
    DsSinSemanaBoletinError,
    SemanaFueraDeRangoError,
    SemanaUnoLegacyError,
    colision_legado_semana_uno,
    ds_de_semana_boletin,
    ds_legado_semana_uno,
    fin_semana_boletin,
    inicio_semana_boletin,
    semana_boletin_de_ds,
    semana_boletin_de_serie,
    semanas_del_anio_boletin,
    semanas_iso_del_anio,
)

pytestmark = pytest.mark.unit

# H-SPEC-1.1 §4.1: (semana del boletín 2026, ds legado).
ANCLAS = [
    (2, "2025-12-29"),
    (5, "2026-01-19"),
    (6, "2026-01-26"),
    (15, "2026-03-30"),
    (16, "2026-04-06"),
    (31, "2026-07-20"),
]

# Enmienda W33 y ronda W37: cortes productivos, el corte de calificación y la ventana de selección.
CORTES = [
    (23, "2026-05-25"),
    (24, "2026-06-01"),
    (27, "2026-06-22"),
    (28, "2026-06-29"),
    (33, "2026-08-03"),
    (34, "2026-08-10"),
    (37, "2026-08-31"),
    (39, "2026-09-14"),
]

# Máximos publicados por año en el consolidado (todas las cohortes completas coinciden).
SEMANAS_PUBLICADAS = {
    2014: 53,
    2015: 52,
    2016: 52,
    2017: 52,
    2018: 52,
    2019: 52,
    2020: 53,
    2021: 52,
    2022: 52,
    2023: 52,
    2024: 52,
    2025: 53,
}

# Fronteras de año: (ds legado, semana del boletín) según el legado.
FRONTERAS = [
    # 2014 tiene 53 semanas del boletín y 52 ISO: la 53 existe y la 1 de 2015 colisiona con la 2.
    ("2014-12-15", (2014, 52)),
    ("2014-12-22", (2014, 53)),
    ("2014-12-29", (2015, 2)),
    # 2015 tiene 52 semanas del boletín y 53 ISO: la 1 de 2016 va en 2015-12-21 y 2015-12-28 sobra.
    ("2015-12-14", (2015, 52)),
    ("2015-12-21", (2016, 1)),
    ("2016-01-04", (2016, 2)),
    # 2020 tiene 53 en ambos calendarios: sin colisión ni salto.
    ("2020-12-21", (2020, 53)),
    ("2020-12-28", (2021, 1)),
    ("2021-01-04", (2021, 2)),
    # 2025 como 2014.
    ("2025-12-15", (2025, 52)),
    ("2025-12-22", (2025, 53)),
    ("2025-12-29", (2026, 2)),
    # Horizonte 2026/27, como 2015/16.
    ("2026-12-14", (2026, 52)),
    ("2026-12-21", (2027, 1)),
    ("2027-01-04", (2027, 2)),
    # 2027 normal (52 y 52).
    ("2027-12-20", (2027, 52)),
    ("2027-12-27", (2028, 1)),
]

SIN_SEMANA = ["2015-12-28", "2026-12-28"]


def test_version() -> None:
    assert CALENDARIO_VERSION == "2"


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


@pytest.mark.parametrize(("anio", "n"), SEMANAS_PUBLICADAS.items())
def test_semanas_del_anio_siguen_al_boletin(anio: int, n: int) -> None:
    assert semanas_del_anio_boletin(anio) == n


def test_conteo_iso_no_sirve() -> None:
    """Mutante de la versión 1: el conteo ISO difiere del publicado en 2014, 2015 y 2025."""
    distintos = {a for a, n in SEMANAS_PUBLICADAS.items() if semanas_iso_del_anio(a) != n}
    assert distintos == {2014, 2015, 2025}
    assert semanas_del_anio_boletin(2026) == 52 and semanas_iso_del_anio(2026) == 53


def test_fecha_del_boletin_de_la_portada() -> None:
    """Portada del boletín W39 de 2026: «del 27 de septiembre al 3 de octubre del 2026»."""
    assert inicio_semana_boletin(2026, 39) == date(2026, 9, 27)
    assert fin_semana_boletin(2026, 39) == date(2026, 10, 3)
    assert inicio_semana_boletin(2025, 53) == date(2025, 12, 28)
    assert inicio_semana_boletin(2026, 1) == date(2026, 1, 4)
    with pytest.raises(SemanaFueraDeRangoError):
        inicio_semana_boletin(2026, 53)


@pytest.mark.parametrize(("ds", "semana"), FRONTERAS)
def test_fronteras_de_anio(ds: str, semana: tuple[int, int]) -> None:
    assert semana_boletin_de_ds(ds) == semana
    if semana[1] >= 2:
        assert ds_de_semana_boletin(*semana) == pd.Timestamp(ds)


@pytest.mark.parametrize("ds", SIN_SEMANA)
def test_ds_sin_semana_del_boletin(ds: str) -> None:
    with pytest.raises(DsSinSemanaBoletinError):
        semana_boletin_de_ds(ds)
    tabla = semana_boletin_de_serie(pd.Series(pd.to_datetime([ds])))
    assert tabla.isna().all(axis=None)


def test_w53_conserva_identidad() -> None:
    """La 53 no se trunca, no se descarta ni se funde en la 52: semanas distintas, ds distintos."""
    for anio in (2014, 2020, 2025):
        ds52, ds53 = ds_de_semana_boletin(anio, 52), ds_de_semana_boletin(anio, 53)
        assert ds53 - ds52 == pd.Timedelta(weeks=1)
        assert semana_boletin_de_ds(ds53) == (anio, 53)
    with pytest.raises(SemanaFueraDeRangoError):
        ds_de_semana_boletin(2026, 53)


def test_colisiones_del_legado_en_semana_uno() -> None:
    """Tras una semana 53 que el ISO no tiene, el legado fecha la semana 1 y la 2 el mismo lunes."""
    colisiones = {a for a in range(2015, 2029) if colision_legado_semana_uno(a)}
    assert colisiones == {2015, 2026}
    assert ds_legado_semana_uno(2026) == pd.Timestamp("2025-12-29")
    assert ds_legado_semana_uno(2016) == pd.Timestamp("2015-12-21")
    assert ds_legado_semana_uno(2027) == pd.Timestamp("2026-12-21")


def test_semana_uno_no_es_evaluable() -> None:
    with pytest.raises(SemanaUnoLegacyError):
        ds_de_semana_boletin(2026, 1)


def test_semana_fuera_de_rango() -> None:
    with pytest.raises(SemanaFueraDeRangoError):
        ds_de_semana_boletin(2026, semanas_del_anio_boletin(2026) + 1)
    with pytest.raises(SemanaFueraDeRangoError):
        ds_de_semana_boletin(2025, 54)


def test_ida_y_vuelta_todos_los_anios() -> None:
    for anio in range(2014, 2029):
        for sem in range(2, semanas_del_anio_boletin(anio) + 1):
            assert semana_boletin_de_ds(ds_de_semana_boletin(anio, sem)) == (anio, sem)


def _lunes(desde: str, hasta: str) -> pd.Series:
    return pd.Series(pd.date_range(desde, hasta, freq="W-MON"))


def test_version_vectorizada_coincide_con_la_escalar() -> None:
    fechas = _lunes("2013-12-30", "2028-12-25")
    tabla = semana_boletin_de_serie(fechas)
    for f, a, s in zip(fechas, tabla["anio_boletin"], tabla["semana_boletin"], strict=True):
        try:
            esperado = semana_boletin_de_ds(f)
        except DsSinSemanaBoletinError:
            assert pd.isna(a) and pd.isna(s), f
            continue
        assert (a, s) == esperado, f
    assert int(tabla["semana_boletin"].isna().sum()) == 2  # 2015-12-28 y 2026-12-28
    assert str(tabla["semana_boletin"].dtype) == "Int64"


def test_vectorizada_conserva_el_indice() -> None:
    fechas = pd.Series(pd.to_datetime(["2026-01-26", "2026-08-03"]), index=[7, 9])
    assert list(semana_boletin_de_serie(fechas).index) == [7, 9]


def test_fecha_de_presentacion_equivale_a_ds_mas_siete_dias() -> None:
    """Atajo que usa ``build_tableau``: dentro del año, la fecha de presentación es ``ds + 7 días``.

    Equivale al ``ds`` de la semana siguiente. Se fija aquí para que el atajo no pueda derivar del
    calendario canónico.
    """
    for semana in range(2, semanas_del_anio_boletin(2026)):
        ds = ds_de_semana_boletin(2026, semana)
        assert ds + pd.Timedelta(weeks=1) == ds_de_semana_boletin(2026, semana + 1)


# --- equivalencia con el legado ---------------------------------------------------------------


def _boletin_completo(desde: int, hasta: int) -> pd.DataFrame:
    filas = [
        (a, s) for a in range(desde, hasta + 1) for s in range(1, semanas_del_anio_boletin(a) + 1)
    ]
    df = pd.DataFrame(filas, columns=["Anio", "Semana"])
    df["Entidad"] = "Colima"
    df["Padecimiento"] = "Depresión"
    df["Acumulado_hombres"] = df.groupby("Anio").cumcount() + 1
    df["Acumulado_mujeres"] = df["Acumulado_hombres"]
    df["anio_original"] = df["Anio"]
    df["semana_original"] = df["Semana"]
    return df


def test_coincide_con_el_transformer_legado() -> None:
    """El ``ds`` que fecha ``DataTransformation`` para cada semana publicada es el del módulo."""
    t = DataTransformation(_boletin_completo(2013, 2028), config={})
    t._ajusta_semanas()
    t._prepara_series_tiempo()
    df = t.df
    assert len(df) == sum(semanas_del_anio_boletin(a) for a in range(2013, 2029))
    for a, s, fecha in zip(df["anio_original"], df["semana_original"], df["Fecha"], strict=True):
        if a == 2013 and s == 1:
            continue  # sin año previo en los datos: el legado usa el máximo global
        if s == 1:
            assert fecha == ds_legado_semana_uno(a), (a, s)
            esperado = (a, 2) if colision_legado_semana_uno(a) else (a, 1)
            assert semana_boletin_de_ds(fecha) == esperado, (a, s)
        else:
            assert fecha == ds_de_semana_boletin(a, s), (a, s)
            assert semana_boletin_de_ds(fecha) == (a, s), (a, s)
    # Los lunes del legado sin semana del boletín son exactamente los que el módulo rotula así.
    todos = set(_lunes("2014-01-06", "2028-12-18"))
    sin_fila = todos - set(df["Fecha"])
    assert sin_fila == {pd.Timestamp(d) for d in SIN_SEMANA}
