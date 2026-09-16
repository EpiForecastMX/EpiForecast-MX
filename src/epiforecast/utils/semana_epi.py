"""Conversión canónica entre el ``ds`` legado y la semana del boletín (SINAVE).

**Única fuente de verdad del calendario.** Todo el proyecto debe convertir ``ds`` a semana
del boletín, y viceversa, a través de este módulo: observado, pronóstico, métricas, selección
de motor y gráficas. Queda prohibido comparar ``Semana`` contra ``isocalendar(ds).week``.

Por qué existe
--------------
``TransformadorDatos.run`` ejecuta ``_ajusta_semanas`` (que resta 1 a ``Semana`` en toda fila
que no sea semana 1) y **después** ``_prepara_series_tiempo``, que construye la fecha como el
lunes de la semana ISO igual a esa ``Semana`` ya restada. Por eso el ``ds`` legado cumple::

    ISO(ds) = Semana_boletin - 1     <=>     Semana_boletin = ISO(ds) + 1

Ese desfase de una semana es la causa de errores ya documentados: el tablero de Tableau rotuló
durante meses la semana N del boletín como N-1, y la galería del sitio emparejaba lo real con el
pronóstico de la semana siguiente.

`transformer.py` es el sitio que **define** el calendario y no se corrige aquí: cambiarlo movería
cada ``ds`` de la historia e invalidaría los modelos entrenados. Este módulo lo invierte.

Fronteras
---------
- **Semana 1 del boletín** no tiene ``ds`` distinguible en el legado, porque ``_ajusta_semanas``
  la desplaza al año anterior y puede colisionar con la fila que representa la semana 2. Se trata
  como no evaluable: nunca se imputa ni se empareja con la semana 2.
- **La última semana ISO de un año** (52 o 53, según el año) representa ya la frontera siguiente:
  se clasifica como semana 1 del año de boletín siguiente y queda fuera del análisis del año en
  curso.
- **La semana 53 del boletín**, cuando la fuente la publica, se empareja con la semana ISO 52.
  Conserva identidad propia: queda prohibido truncarla con ``min(semana, 52)`` o sumarla dentro
  de la semana 52.
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

import pandas as pd


class SemanaBoletin(NamedTuple):
    """Identidad temporal del boletín: año y semana epidemiológica publicada."""

    anio: int
    semana: int


class SemanaUnoLegacyError(ValueError):
    """La semana 1 del boletín no tiene un ``ds`` distinguible en el calendario legado."""


class SemanaFueraDeRangoError(ValueError):
    """La semana pedida no existe en el año de boletín indicado."""


def semanas_iso_del_anio(anio: int) -> int:
    """Número de semanas ISO del año: 52 o 53.

    El 28 de diciembre siempre cae en la última semana ISO del año, por definición del estándar.
    """
    return date(anio, 12, 28).isocalendar().week


def semanas_del_anio_boletin(anio: int) -> int:
    """Última semana que el boletín puede publicar en ese año, incluida la 53 cuando existe.

    Coincide con el número de semanas ISO del año: la última semana ISO ya representa la frontera
    y pertenece a la semana 1 del año siguiente, así que la mayor semana representable de ``anio``
    proviene de la penúltima semana ISO más uno.
    """
    return semanas_iso_del_anio(anio)


def semana_boletin_de_ds(ds: date | pd.Timestamp | str) -> SemanaBoletin:
    """Convierte un ``ds`` legado a la semana del boletín que representa.

    Aplica ``Semana = ISO(ds) + 1``. Si ``ds`` cae en la última semana ISO de su año, pertenece
    ya a la semana 1 del año de boletín siguiente.
    """
    ts = pd.Timestamp(ds)
    iso = ts.isocalendar()
    anio_iso, semana_iso = int(iso[0]), int(iso[1])
    if semana_iso == semanas_iso_del_anio(anio_iso):
        return SemanaBoletin(anio_iso + 1, 1)
    return SemanaBoletin(anio_iso, semana_iso + 1)


def ds_de_semana_boletin(anio: int, semana: int) -> pd.Timestamp:
    """Convierte una semana del boletín al ``ds`` legado que le corresponde.

    Es la inversa exacta de :func:`semana_boletin_de_ds` para ``semana >= 2``.
    """
    if semana == 1:
        raise SemanaUnoLegacyError(
            f"La semana 1 de {anio} no tiene ds distinguible en el calendario legado; "
            "es no evaluable y no debe emparejarse con la semana 2."
        )
    maximo = semanas_del_anio_boletin(anio)
    if not 2 <= semana <= maximo:
        raise SemanaFueraDeRangoError(
            f"El año de boletín {anio} admite semanas de 2 a {maximo}; se pidió {semana}."
        )
    return pd.Timestamp(date.fromisocalendar(anio, semana - 1, 1))


def semana_boletin_de_serie(ds: pd.Series) -> pd.DataFrame:
    """Versión vectorizada: devuelve un ``DataFrame`` con ``anio_boletin`` y ``semana_boletin``.

    Conserva el índice de la serie de entrada para poder asignarse directamente a un ``DataFrame``.
    """
    fechas = pd.to_datetime(ds)
    iso = fechas.dt.isocalendar()
    anio_iso = iso["year"].astype(int)
    semana_iso = iso["week"].astype(int)
    ultima = anio_iso.map(semanas_iso_del_anio)
    frontera = semana_iso == ultima
    return pd.DataFrame(
        {
            "anio_boletin": anio_iso.where(~frontera, anio_iso + 1).astype(int),
            "semana_boletin": (semana_iso + 1).where(~frontera, 1).astype(int),
        },
        index=fechas.index,
    )
