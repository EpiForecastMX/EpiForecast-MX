"""Reparaciones de tabla y variantes por periodo del extractor de cuadros.

Separado de ``cuadro_extractor`` por el límite de 300 líneas por módulo. Las reparaciones
actúan sobre la tabla que entrega camelot; ``spec_del_periodo`` resuelve la configuración del
grupo para el boletín, cuando el bloque cambia de página o de posición según el año.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

import numpy as np
import pandas as pd

from epiforecast.data.extraction.dengue_extractor import _STATE_LOOKUP, _norm_entity
from epiforecast.data.extraction.pdf_extractor import eliminar_columnas_vacias, normalize_number


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


class OpcionesTabla(TypedDict):
    valor_en_nombre: bool
    parciales: bool


def opciones_tabla(spec: dict[str, Any]) -> OpcionesTabla:
    """Reparaciones opt-in de la lectura de camelot que declara el grupo (``_tabla_estatal``)."""
    return OpcionesTabla(
        valor_en_nombre=bool(spec.get("valor_en_columna_nombre")),
        parciales=bool(spec.get("une_renglones_parciales")),
    )


def alinea_renglones(df: pd.DataFrame, parciales: bool = False) -> pd.DataFrame:
    """Une el renglón de valores con el nombre de la entidad cuando camelot los separa.

    En 68 boletines de 2014-2015 cada entidad sale en dos renglones: los valores sin nombre y,
    debajo, el nombre sin valores. Sin esto, ``reshape`` los lee como ceros con estado ``ok``.
    Sólo actúa sobre ese patrón exacto; cualquier otra tabla pasa igual. Con ``parciales`` (opt-in
    del grupo) aplica además ``une_renglones_parciales``.
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
    alineada = pd.DataFrame(filas, index=df.index, columns=df.columns)
    return une_renglones_parciales(alineada) if parciales else alineada


def _es_entidad(nombre: str) -> bool:
    """Si el nombre (sin llamadas de nota) es una entidad federativa canónica o un alias."""
    return _norm_entity(re.sub(r"[\s*§]+$", "", nombre)) in _STATE_LOOKUP


AMBIGUO = "<renglon_ambiguo>"


def une_renglones_parciales(df: pd.DataFrame) -> pd.DataFrame:
    """Une una entidad con valores parciales y el renglón siguiente sin nombre que los completa.

    En el Cuadro 18.1 de 2019_sem48 a 2024_sem01 camelot parte el renglón de algunas entidades
    (Ciudad de México, México, Nuevo León...): arriba el nombre con los valores de un bloque y abajo,
    sin nombre, los de los otros, en uno o varios renglones seguidos. Sin esto ``reshape`` lee los
    bloques vacíos como ceros con estado ``ok``. Los complementarios se unen en orden mientras no se
    solapen con lo ya reunido; cualquier otra tabla pasa igual.

    Si el renglón con nombre es una entidad federativa y un complementario se solapa con lo ya
    reunido, no hay unión legítima de ése ni de los siguientes: no se unen y se marcan con
    :data:`AMBIGUO` las celdas vacías que usan las entidades y toda columna en que alguno de esos
    complementarios trae un valor, que se perdería aunque ninguna entidad con nombre la use (todas
    partidas). En 2020_sem52 (pág. 62) el renglón del bloque de la derecha de la entidad siguiente
    cae tras el complementario: sólo sus columnas quedan marcadas. Tras recortar el bloque del
    padecimiento, :func:`motivo_ambiguo` invalida la tabla sólo si la marca cae en ese bloque; una
    ambigüedad en el bloque de otro padecimiento no lo afecta. Encabezados y TOTAL no son
    entidades: sólo se unen con el renglón siguiente, sin marcas, como antes. Sólo en los grupos que
    lo declaran (``une_renglones_parciales: true``).
    """
    filas = df.astype(str).to_numpy(copy=True)
    vacio = filas[:, 1:] == ""
    entidades = np.array([_es_entidad(n) for n in filas[:, 0]], dtype=bool)
    usadas = ~vacio[entidades].all(axis=0) if entidades.any() else np.zeros(vacio.shape[1], bool)
    for i in range(len(filas) - 1):
        if filas[i, 0].strip() == "" or bool(vacio[i].all()):
            continue
        # Renglones complementarios seguidos (sin nombre y con valores). Sólo una entidad absorbe
        # la secuencia; TOTAL y encabezados conservan la regla de un único renglón siguiente.
        comp: list[int] = []
        for j in range(i + 1, len(filas) if entidades[i] else i + 2):
            if filas[j, 0].strip() != "" or bool(vacio[j].all()):
                break
            comp.append(j)
        for k, j in enumerate(comp):
            if bool((~vacio[i] & ~vacio[j]).any()):
                if entidades[i]:
                    # Desde el primer solape, cada columna con valor en un complementario restante
                    # lo pierde al no unirse (aunque ninguna entidad con nombre la use): se marca.
                    perdidas = (~vacio[comp[k:]]).any(axis=0)
                    filas[i, 1:][(vacio[i] & usadas) | perdidas] = AMBIGUO
                break
            filas[i, 1:][~vacio[j]] = filas[j, 1:][~vacio[j]]
            filas[j, 1:] = ""
            vacio[j] = True
            vacio[i] = filas[i, 1:] == ""
    return pd.DataFrame(filas, index=df.index, columns=df.columns)


def motivo_ambiguo(df: pd.DataFrame) -> str | None:
    """Motivo de invalidez si el bloque ya recortado conserva una celda :data:`AMBIGUO`."""
    marcadas = (df.iloc[:, 1:].astype(str) == AMBIGUO).any(axis=1)
    if not bool(marcadas.any()):
        return None
    nombres = ", ".join(sorted(df.loc[marcadas, df.columns[0]].astype(str)))
    return (
        f"renglones partidos ambiguos en el bloque del padecimiento ({nombres}): el renglón "
        "siguiente sin nombre trae valores solapados; no se une ni se lee"
    )


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


def alinea_valor_en_nombre(df: pd.DataFrame) -> pd.DataFrame:
    """Une valores y entidad cuando el primer valor cae en la columna del nombre.

    Desde 2024_sem50 la página de giardiasis y otras helmintiasis sale de camelot con cada entidad en
    dos renglones: arriba los valores, con el primero («-» o un número) en la columna del nombre y la
    segunda columna vacía, y abajo el nombre sin valores. ``alinea_renglones`` no lo une porque el
    renglón de valores no tiene la columna del nombre vacía, y ``reshape`` lo leía como ceros con
    estado ``ok``. Aquí el primer valor pasa a la segunda columna y el renglón se une con el nombre.
    Sólo actúa sobre ese patrón exacto y sólo en los grupos que lo declaran
    (``valor_en_columna_nombre: true``).
    """
    filas = df.astype(str).to_numpy(copy=True)
    if filas.shape[1] < 3:
        return pd.DataFrame(filas, index=df.index, columns=df.columns)
    for i in range(len(filas)):
        # Misma página, otra variante: el valor pegado al nombre en la celda («8\nCiudad de México»).
        partes = filas[i, 0].split("\n")
        if (
            len(partes) == 2
            and _NUMERO_SUELTO.match(partes[0].strip())
            and not _NUMERO_SUELTO.match(partes[1].strip())
            and filas[i, 1].strip() == ""
            and bool((filas[i, 2:] != "").any())
        ):
            filas[i, 0], filas[i, 1] = partes[1].strip(), partes[0].strip()
    for i in range(1, len(filas)):
        nombre = filas[i, 0].strip()
        con_nombre = nombre != "" and not _NUMERO_SUELTO.match(nombre)
        sin_valores = bool((filas[i, 1:] == "").all())
        previa = filas[i - 1]
        valor_en_nombre = bool(_NUMERO_SUELTO.match(previa[0].strip())) and previa[1].strip() == ""
        con_mas_valores = bool((previa[2:] != "").any())
        if con_nombre and sin_valores and valor_en_nombre and con_mas_valores:
            filas[i, 1] = previa[0].strip()
            filas[i, 2:] = previa[2:]
            filas[i - 1, :] = ""
    return pd.DataFrame(filas, index=df.index, columns=df.columns)


_TOKEN = re.compile(r"^(?:\d+|-)$")
_MILES = re.compile(r"\d \d{3}(?!\d)")


def _tokens_en_orden(celdas: list[str], ancho: int) -> list[str] | None:
    """Los ``ancho`` valores de las celdas en orden de lectura, o None si no son exactamente esos.

    Un número con separador de miles («1 070») se partiría en dos valores: ante ese patrón no se
    reparte (None), igual que ante un texto que no sea entero ni guion.
    """
    if any(_MILES.search(c) for c in celdas):
        return None
    tokens = " ".join(celdas).split()
    if len(tokens) != ancho or not all(_TOKEN.match(t) for t in tokens):
        return None
    return tokens


def fila_total(df_raw: pd.DataFrame) -> list[str] | None:
    """Celdas del renglón TOTAL impreso con las mismas columnas que deja ``clean_df``."""
    df = eliminar_columnas_vacias(alinea_renglones(df_raw))
    fila = df[df[0].astype(str).str.strip().str.upper().eq("TOTAL")]
    return None if len(fila) != 1 else [str(v) for v in fila.iloc[0, 1:]]


def primer_bloque_por_orden(
    df: pd.DataFrame, total: list[str] | None, columnas: int, ancho: int
) -> tuple[pd.DataFrame | None, str]:
    """Reparte en orden de lectura los valores del primer bloque cuando camelot los desacomoda.

    En 2014_sem02 y 2014_sem03 (Cuadro 12, meningitis) el PDF imprime cada guion de una columna
    corrido unos 40 pt a la izquierda, junto al valor de la columna anterior: camelot pega
    «- -» o «1 -» en una celda y el bloque de 4 valores ocupa 5 columnas. Cada renglón conserva
    sus 4 valores en orden, así que se toman en orden de lectura. Falla cerrado (None y motivo) si
    algún renglón o el TOTAL no trae exactamente ``ancho`` valores, o si la suma de las entidades
    no es el TOTAL impreso en cada columna. Sólo para grupos que lo declaran
    (``primer_bloque_por_orden``).
    """
    if df.empty:
        return None, "reparto por orden: tabla sin entidades"
    valores = []
    for _, fila in df.iterrows():
        tokens = _tokens_en_orden([str(v) for v in fila.iloc[1 : 1 + columnas]], ancho)
        if tokens is None:
            return None, f"reparto por orden: {fila.iloc[0]} no trae {ancho} valores legibles"
        valores.append(tokens)
    impreso = _tokens_en_orden(total[:columnas], ancho) if total is not None else None
    if impreso is None:
        return None, f"reparto por orden: TOTAL impreso sin {ancho} valores legibles"
    sumas = [sum(int(normalize_number(f[j])) for f in valores) for j in range(ancho)]
    if sumas != [int(normalize_number(t)) for t in impreso]:
        return None, f"reparto por orden: suma {sumas} distinta del TOTAL impreso {impreso}"
    resto = df.iloc[:, 1 + columnas :].to_numpy().tolist()
    filas = [[n, *v, *r] for n, v, r in zip(df.iloc[:, 0], valores, resto, strict=True)]
    return pd.DataFrame(filas, columns=range(1 + ancho + len(resto[0]))), "ok"
