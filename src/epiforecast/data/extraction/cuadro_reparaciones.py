"""Reparaciones de tabla y variantes por periodo del extractor de cuadros.

Separado de ``cuadro_extractor`` por el límite de 300 líneas por módulo. Las reparaciones
actúan sobre la tabla que entrega camelot; ``spec_del_periodo`` resuelve la configuración del
grupo para el boletín, cuando el bloque cambia de página o de posición según el año.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


def spec_del_periodo(spec: dict[str, Any], year: int, week: int) -> dict[str, Any]:
    """Configuración del grupo vigente para el boletín ``year``/``week``.

    ``periodos`` es una lista de ``{desde: "AAAA_semNN", <claves>}``: desde ese boletín, cada
    clave sustituye a la del grupo y una clave en ``null`` la retira. Se aplican en orden, así
    que un periodo posterior prevalece. Sin ``periodos`` el grupo queda igual.
    """
    actual = {k: v for k, v in spec.items() if k != "periodos"}
    for periodo in spec.get("periodos") or []:
        anio, sem = str(periodo["desde"]).split("_sem")
        if (year, week) < (int(anio), int(sem)):
            continue
        for clave, valor in periodo.items():
            if clave == "desde":
                continue
            if valor is None:
                actual.pop(clave, None)
            else:
                actual[clave] = valor
    return actual


def alinea_renglones(df: pd.DataFrame) -> pd.DataFrame:
    """Une el renglón de valores con el nombre de la entidad cuando camelot los separa.

    En 68 boletines de 2014-2015 cada entidad sale en dos renglones: los valores sin nombre y,
    debajo, el nombre sin valores. Sin esto, ``reshape`` los lee como ceros con estado ``ok``.
    Sólo actúa sobre ese patrón exacto; cualquier otra tabla pasa igual.
    """
    filas = df.astype(str).to_numpy(copy=True)
    vacio = filas[:, 1:] == ""
    for i in range(1, len(filas)):
        con_nombre = filas[i, 0].strip() != "" and bool(vacio[i].all())
        previa_sin_nombre = filas[i - 1, 0].strip() == "" and not bool(vacio[i - 1].all())
        if con_nombre and previa_sin_nombre:
            filas[i, 1:] = filas[i - 1, 1:]
            filas[i - 1, 1:] = ""
            vacio[i - 1] = True
            vacio[i] = False
    return pd.DataFrame(filas, index=df.index, columns=df.columns)


def sin_llamadas(df: pd.DataFrame) -> pd.DataFrame:
    """Quita las llamadas de nota (``*``, ``§``) al final del nombre de la entidad.

    En 2014_sem28-31 el Cuadro 5.1 imprime «Michoacán *» por una fe de erratas: sin esto la
    entidad no se reconoce y el boletín queda con 31 estados aunque el PDF trae las 32 filas.
    """
    df = df.copy()
    df[df.columns[0]] = df[df.columns[0]].astype(str).str.replace(r"[\s*§]+$", "", regex=True)
    return df


_NUMERO_SUELTO = re.compile(r"^(?:\d[\d ]*|-)$")


def despega_primera_columna(df: pd.DataFrame) -> pd.DataFrame:
    """Separa el primer valor cuando camelot lo pega al nombre de la entidad.

    En 2023_sem45 (Cuadro 13.3) un renglón alterado («Chiapas San Luis Potosí») hace que camelot
    funda la primera columna de valores con el nombre en toda la tabla («53\nAguascalientes» o
    «Yucatán\n28»): ninguna entidad se reconoce y sobra una columna. El valor es la línea numérica
    de la celda y el nombre, la última línea que no lo es. Donde no hay valor legible queda vacío,
    así que quien llama sólo usa esta reparación para bloques que no empiezan en la primera
    columna; un nombre mal elegido deja una entidad repetida y la extracción falla cerrada.
    """
    nombres, valores = [], []
    for celda in df.iloc[:, 0].astype(str):
        lineas = [x.strip() for x in celda.split("\n") if x.strip()]
        numeros = [x for x in lineas if _NUMERO_SUELTO.match(x)]
        textos = [x for x in lineas if not _NUMERO_SUELTO.match(x)]
        nombres.append(textos[-1] if textos else "")
        valores.append(numeros[0] if len(numeros) == 1 and textos else "")
    out = df.copy()
    out.columns = pd.RangeIndex(start=0, stop=2 * out.shape[1], step=2)
    out[0] = nombres
    out[1] = valores
    out = out[sorted(out.columns)]
    out.columns = pd.RangeIndex(out.shape[1])
    return out
