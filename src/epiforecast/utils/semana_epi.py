"""Conversión canónica entre la semana del boletín (SINAVE), el ``ds`` legado y la fecha del boletín.

**Única fuente de verdad del calendario.** Todo el proyecto debe convertir ``ds`` a semana
del boletín, y viceversa, a través de este módulo: observado, pronóstico, métricas, selección
de motor y gráficas. Queda prohibido comparar ``Semana`` contra ``isocalendar(ds).week``.

Versión 2 (enmienda de calendario W53, 13-oct-2026). La versión 1 (``4081010f…``, código
archivado ``1bd24a8e``) limitaba cada año al número de semanas ISO. El boletín sigue el
calendario epidemiológico MMWR (semanas de domingo a sábado), que no siempre tiene las mismas
semanas que el ISO: 2014, 2020 y 2025 tienen 53; 2015 y 2026, 52 (ISO 53). En los años en que
ambos conteos difieren, la versión 1 rechazaba la semana 53 publicada (2014 y 2025) y rotulaba
mal la frontera de año (2014/15, 2015/16, 2025/26 y el horizonte 2026/27).

Tres identidades distintas
--------------------------
- **Semana original del boletín**: ``(Anio, Semana)`` tal como se publica, de 1 a 52 o 53.
- **``ds`` legado**: la fecha que ``DataTransformation`` asigna a esa semana y con la que se
  entrenaron y pronostican los modelos. ``_ajusta_semanas`` resta 1 a toda semana que no sea la
  1 y mueve la semana 1 al año anterior, con semana ``máximo del año anterior + 1``; después
  ``_prepara_series_tiempo`` fecha ``lunes ISO-W1(Anio) + (Semana - 1)`` semanas. Por eso::

      ds(Y, s) = lunes ISO-W1(Y) + (s - 2) semanas                 para s >= 2
      ds(Y, 1) = lunes ISO-W1(Y - 1) + (n(Y - 1) - 1) semanas      (n = semanas del boletín)

  Fuera de la frontera de año equivale a ``Semana_boletin = ISO(ds) + 1``.
- **Fecha del boletín**: el domingo en que empieza la semana epidemiológica publicada (y el
  sábado en que termina). Es la fecha que imprime la portada del boletín.

`transformer.py` es el sitio que **define** el ``ds`` legado y no se corrige aquí: cambiarlo
movería cada ``ds`` de la historia e invalidaría los modelos entrenados. Este módulo lo invierte.

Fronteras
---------
- **Semana 1 del boletín**: no evaluable. Su ``ds`` legado existe, pero su incremento se calcula
  contra la semana 52/53 del año anterior y, en los años con semana 53 (2014, 2025), su ``ds``
  coincide con el de la semana 2 (colisión del legado: 2014-12-29 y 2025-12-29). Se rechaza en
  :func:`ds_de_semana_boletin`, nunca se imputa ni se empareja con la semana 2;
  :func:`ds_legado_semana_uno` la expone sólo para documentar y auditar.
- **Semana 53**: tiene identidad y ``ds`` propios (2025-W53 = 2025-12-22). Queda prohibido
  truncarla con ``min(semana, 52)``, descartarla o sumarla dentro de la semana 52.
- **``ds`` sin semana del boletín**: en los años con 52 semanas del boletín y 53 ISO (2015, 2026)
  el legado salta un lunes (2015-12-28, 2026-12-28): ningún boletín le corresponde. En la historia
  no hay filas; en el horizonte del pronóstico sí hay un paso con ese ``ds``. Se rotula como sin
  semana (``<NA>`` en la versión vectorizada) y no se empareja con ningún observado.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple

import pandas as pd

from epiforecast.data import epi_calendar

CALENDARIO_VERSION = "2"


class SemanaBoletin(NamedTuple):
    """Identidad temporal del boletín: año y semana epidemiológica publicada."""

    anio: int
    semana: int


class SemanaUnoLegacyError(ValueError):
    """La semana 1 del boletín no es evaluable en el calendario legado."""


class SemanaFueraDeRangoError(ValueError):
    """La semana pedida no existe en el año de boletín indicado."""


class DsSinSemanaBoletinError(ValueError):
    """El ``ds`` es un paso del calendario legado al que no corresponde ninguna semana publicada."""


def semanas_iso_del_anio(anio: int) -> int:
    """Número de semanas ISO del año: 52 o 53.

    El 28 de diciembre siempre cae en la última semana ISO del año, por definición del estándar.
    """
    return date(anio, 12, 28).isocalendar().week


def semanas_del_anio_boletin(anio: int) -> int:
    """Semanas que publica el boletín en ese año (calendario MMWR de ``epi_calendar``): 52 o 53."""
    return epi_calendar.weeks_in_year(anio)


def _valida(anio: int, semana: int) -> None:
    maximo = semanas_del_anio_boletin(anio)
    if not 1 <= semana <= maximo:
        raise SemanaFueraDeRangoError(
            f"El año de boletín {anio} admite semanas de 1 a {maximo}; se pidió {semana}."
        )


def inicio_semana_boletin(anio: int, semana: int) -> date:
    """Fecha del boletín: domingo en que empieza la semana epidemiológica publicada."""
    _valida(anio, semana)
    return epi_calendar.week_start(anio, semana)


def fin_semana_boletin(anio: int, semana: int) -> date:
    """Sábado en que termina la semana epidemiológica publicada."""
    return inicio_semana_boletin(anio, semana) + timedelta(days=6)


def _lunes_iso_uno(anio: int) -> date:
    return date.fromisocalendar(anio, 1, 1)


def ds_de_semana_boletin(anio: int, semana: int) -> pd.Timestamp:
    """Convierte una semana del boletín (2 a 52 o 53) al ``ds`` legado que le corresponde.

    Es la inversa exacta de :func:`semana_boletin_de_ds` para ``semana >= 2``.
    """
    if semana == 1:
        raise SemanaUnoLegacyError(
            f"La semana 1 de {anio} no es evaluable en el calendario legado y no debe "
            "emparejarse con la semana 2."
        )
    _valida(anio, semana)
    return pd.Timestamp(_lunes_iso_uno(anio) + timedelta(weeks=semana - 2))


def ds_legado_semana_uno(anio: int) -> pd.Timestamp:
    """``ds`` que el transformer asigna a la semana 1 de ``anio`` (sólo para documentar/auditar)."""
    previo = anio - 1
    return pd.Timestamp(
        _lunes_iso_uno(previo) + timedelta(weeks=semanas_del_anio_boletin(previo) - 1)
    )


def colision_legado_semana_uno(anio: int) -> bool:
    """True si la semana 1 y la 2 de ``anio`` comparten ``ds`` legado (años tras una semana 53)."""
    return ds_legado_semana_uno(anio) == ds_de_semana_boletin(anio, 2)


def semana_boletin_de_ds(ds: date | pd.Timestamp | str) -> SemanaBoletin:
    """Convierte un ``ds`` legado a la semana del boletín que representa.

    Fuera de la frontera de año aplica ``Semana = ISO(ds) + 1``. La posición del legado que sigue a
    la última semana del año es la semana 1 del año siguiente; si esa posición ya es la semana ISO 1
    del año siguiente (colisión), el ``ds`` se lee como la semana 2. Un ``ds`` posterior, sin
    semana publicada, levanta :class:`DsSinSemanaBoletinError`.
    """
    iso = pd.Timestamp(ds).isocalendar()
    anio, k = int(iso[0]), int(iso[1]) - 1  # k: semanas desde el lunes ISO-W1 del año
    n = semanas_del_anio_boletin(anio)
    if k <= n - 2:
        return SemanaBoletin(anio, k + 2)
    if k == n - 1:
        return SemanaBoletin(anio + 1, 1)
    raise DsSinSemanaBoletinError(
        f"{pd.Timestamp(ds).date()} no corresponde a ninguna semana del boletín: el calendario "
        f"legado salta ese lunes porque {anio} tiene {n} semanas del boletín y "
        f"{semanas_iso_del_anio(anio)} ISO."
    )


def semana_boletin_de_serie(ds: pd.Series) -> pd.DataFrame:
    """Versión vectorizada: devuelve un ``DataFrame`` con ``anio_boletin`` y ``semana_boletin``.

    Ambas columnas son ``Int64``: un ``ds`` sin semana del boletín queda en ``<NA>`` en las dos.
    Conserva el índice de la serie de entrada para poder asignarse directamente a un ``DataFrame``.
    """
    fechas = pd.to_datetime(ds)
    iso = fechas.dt.isocalendar()
    anio = iso["year"].astype("int64")
    k = iso["week"].astype("int64") - 1
    n = anio.map(semanas_del_anio_boletin)
    normal = k <= n - 2
    semana_uno = k == n - 1
    anio_b = anio.where(normal, anio + 1).where(normal | semana_uno)
    semana_b = (k + 2).where(normal, 1).where(normal | semana_uno)
    return pd.DataFrame(
        {"anio_boletin": anio_b.astype("Int64"), "semana_boletin": semana_b.astype("Int64")},
        index=fechas.index,
    )
