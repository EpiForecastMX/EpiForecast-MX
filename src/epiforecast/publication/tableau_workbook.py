"""C7.6-ADAPTERS-B0.4 — generador de un workbook Tableau de STAGING para el namespace ``runner_``.

Existe un workbook trackeado, ``reports/dashboards/viz_epiforecastmx.twb``, y **no es** una plantilla
de staging: declara ``xml:base=https://public.tableau.com``, referencia el workbook público, lleva un
``cloudFileId`` concreto de Drive y consume las cinco tablas legacy. Copiarlo para «adaptarlo» sería
la vía más corta a publicar un candidate en Tableau Public, así que aquí no se abre ni se lee: se
**genera** uno nuevo desde el shard y desde el id de la hoja de staging, que llega por parámetro.

Lo que el artefacto tiene que mostrar no es negociable: la etiqueta de validación viaja con las
cifras y el release es point-only, sin banda. Un pronóstico sin su condición es exactamente la
captura que después circula sin ella.

Los filtros salen de los datos —de las columnas de baja cardinalidad que traiga el shard—, no de una
lista de padecimientos: si mañana entra otro release, este generador lo cubre sin tocar una línea.

`verify_workbook` es la contraparte: rechaza Tableau Public, ids productivos, rutas absolutas y
cualquier mención de las cinco tabs legacy. Generar y verificar son dos pasos, no uno.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import re
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

from epiforecast.runner.artifact_identity import ArtifactValidationError, require

from .compiler import POINT_ONLY_SUFFIX
from .sheets_sink import LEGACY_TABS
from .tableau_adapter import TABLE_FORECAST, TABLE_RELEASES, RunnerTables

WORKBOOK_SCHEMA = "tableau_runner_workbook.v1"
TABLEAU_VERSION = "2024.1"

# Todo lo que un workbook de staging no puede contener.
FORBIDDEN_SUBSTRINGS = ("public.tableau.com", "tableau.com/views", "tableauusercontent.com")
ABSOLUTE_PATH = re.compile(r"(?:^|['\"\s=])(?:/(?:Users|home|Volumes|var)/|[A-Za-z]:\\\\)")

# Máxima cardinalidad para que una columna sirva de filtro. Por encima no es un filtro, es una lista.
MAX_FILTER_CARDINALITY = 12
# Columnas que nunca son dimensión de filtro: son la medida y las que el release deja vacías.
NEVER_FILTER = ("yhat_cases", "yhat_lower", "yhat_upper", "ds")


def _datatype(serie: pd.Series) -> str:
    """Tipo declarado a partir de los valores, no de un mapa de nombres escrito a mano."""
    valores = [v for v in serie.astype(str) if v != ""]
    if not valores:
        return "string"
    if all(re.fullmatch(r"-?\d+", v) for v in valores):
        return "integer"
    if all(re.fullmatch(r"-?\d+(?:\.\d+)?", v) for v in valores):
        return "real"
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in valores):
        return "date"
    return "string"


def filter_dimensions(frame: pd.DataFrame) -> dict[str, list[str]]:
    """Filtros DERIVADOS: columnas de baja cardinalidad con sus valores, ordenados."""
    salida: dict[str, list[str]] = {}
    for columna in frame.columns:
        if columna in NEVER_FILTER:
            continue
        valores = sorted({v for v in frame[columna].astype(str) if v != ""})
        if 1 <= len(valores) <= MAX_FILTER_CARDINALITY:
            salida[str(columna)] = valores
    return salida


def _columnas(padre: ET.Element, frame: pd.DataFrame) -> None:
    for columna in frame.columns:
        tipo = _datatype(frame[columna])
        ET.SubElement(
            padre,
            "column",
            {
                "caption": str(columna),
                "datatype": tipo,
                "name": f"[{columna}]",
                "role": "measure" if tipo in {"integer", "real"} else "dimension",
                "type": "quantitative" if tipo in {"integer", "real"} else "nominal",
            },
        )


def _datasource(nombre: str, spreadsheet_id: str, frame: pd.DataFrame) -> ET.Element:
    ds = ET.Element(
        "datasource",
        {
            "caption": nombre,
            "inline": "true",
            "name": f"runner.{nombre}",
            "version": TABLEAU_VERSION,
        },
    )
    conexion = ET.SubElement(ds, "connection", {"class": "federated"})
    nombradas = ET.SubElement(conexion, "named-connections")
    nombrada = ET.SubElement(
        nombradas, "named-connection", {"caption": nombre, "name": f"google-sheets.{nombre}"}
    )
    # El id llega por parámetro. Nunca se copia el `cloudFileId` del workbook productivo.
    ET.SubElement(
        nombrada,
        "connection",
        {
            "class": "google-sheets",
            "cloudFileId": spreadsheet_id,
            "filename": nombre,
            "sheet": nombre,
            "server": "sheets.googleapis.com",
        },
    )
    relacion = ET.SubElement(
        conexion,
        "relation",
        {
            "connection": f"google-sheets.{nombre}",
            "name": nombre,
            "table": nombre,
            "type": "table",
        },
    )
    columnas = ET.SubElement(relacion, "columns", {"header": "yes"})
    for columna in frame.columns:
        ET.SubElement(
            columnas,
            "column",
            {
                "datatype": _datatype(frame[columna]),
                "name": str(columna),
                "ordinal": str(list(frame.columns).index(columna)),
            },
        )
    _columnas(ds, frame)
    return ds


def _worksheet(
    nombre: str, fuente: str, etiqueta: str, filtros: Mapping[str, Sequence[str]]
) -> ET.Element:
    hoja = ET.Element("worksheet", {"name": nombre})
    vista = ET.SubElement(hoja, "table")
    # La condición viaja con la cifra: título y subtítulo, no una nota al pie que se recorta.
    ET.SubElement(vista, "title-formatted-text").text = etiqueta
    ET.SubElement(vista, "caption-formatted-text").text = POINT_ONLY_SUFFIX
    dependencias = ET.SubElement(
        ET.SubElement(vista, "view"), "datasource-dependencies", {"datasource": fuente}
    )
    for columna, valores in sorted(filtros.items()):
        filtro = ET.SubElement(
            dependencias, "filter", {"class": "categorical", "column": f"[{columna}]"}
        )
        grupo = ET.SubElement(filtro, "groupfilter", {"function": "union"})
        for valor in valores:
            ET.SubElement(grupo, "groupfilter", {"function": "member", "member": valor})
    return hoja


def build_workbook_xml(tables: RunnerTables, *, spreadsheet_id: str, label: str) -> bytes:
    """XML del workbook de staging. Determinista: mismas tablas e id → mismos bytes."""
    require(bool(spreadsheet_id.strip()), "workbook: falta el id de la hoja de staging")
    require(bool(label.strip()), "workbook: el release no trae etiqueta de validación")

    raiz = ET.Element(
        "workbook",
        {
            "source-build": WORKBOOK_SCHEMA,
            "source-platform": "generated",
            "version": TABLEAU_VERSION,
        },
    )
    fuentes = ET.SubElement(raiz, "datasources")
    hojas = ET.SubElement(raiz, "worksheets")
    for nombre, frame in sorted(tables.as_mapping().items()):
        fuentes.append(_datasource(nombre, spreadsheet_id, frame))
        filtros = filter_dimensions(frame) if nombre == TABLE_FORECAST else {}
        hojas.append(_worksheet(nombre, f"runner.{nombre}", label, filtros))

    ET.indent(raiz, space="  ")
    cuerpo = bytes(ET.tostring(raiz, encoding="utf-8", xml_declaration=True))
    return cuerpo if cuerpo.endswith(b"\n") else cuerpo + b"\n"


def verify_workbook(xml: bytes | Path, *, forbidden_ids: Sequence[str] = ()) -> dict[str, Any]:
    """Rechaza lo que un workbook de staging no puede contener. Verificar no es confiar."""
    datos: bytes = xml.read_bytes() if isinstance(xml, Path) else bytes(xml)
    texto = datos.decode("utf-8")

    for prohibido in FORBIDDEN_SUBSTRINGS:
        if prohibido in texto:
            raise ArtifactValidationError(f"workbook: contiene {prohibido!r}; esto no es staging")
    for identificador in forbidden_ids:
        if identificador and identificador in texto:
            raise ArtifactValidationError(
                "workbook: contiene un id de hoja prohibido (productivo)"
            )
    if ABSOLUTE_PATH.search(texto):
        raise ArtifactValidationError(
            "workbook: contiene una ruta absoluta; un extract local no es un artefacto compartible"
        )

    raiz = ET.fromstring(texto)  # noqa: S314 — entrada propia, generada en este módulo
    require(raiz.tag == "workbook", "workbook: la raíz no es <workbook>")
    require(
        raiz.get("source-build") == WORKBOOK_SCHEMA,
        f"workbook: source-build {raiz.get('source-build')!r} no es {WORKBOOK_SCHEMA}",
    )
    for atributo in ("xml:base", "{http://www.w3.org/XML/1998/namespace}base"):
        # ElementTree normaliza el prefijo; el mensaje conserva el nombre con el que se escribe.
        require(
            raiz.get(atributo) is None, "workbook: declara xml:base y un staging no apunta fuera"
        )

    tablas = sorted(t for r in raiz.iter("relation") if (t := r.get("table")))
    legacy = sorted(set(tablas) & set(LEGACY_TABS))
    require(not legacy, f"workbook: consume tablas legacy {legacy}")
    require(
        tablas == [TABLE_FORECAST, TABLE_RELEASES],
        f"workbook: tablas inesperadas {tablas}",
    )
    etiquetas = [x for t in raiz.iter("title-formatted-text") if (x := t.text)]
    require(bool(etiquetas), "workbook: ninguna hoja muestra la etiqueta de validación")
    pies = [x for c in raiz.iter("caption-formatted-text") if (x := c.text)]
    require(
        all(POINT_ONLY_SUFFIX in (p or "") for p in pies) and len(pies) == len(tablas),
        "workbook: falta la advertencia point-only en alguna hoja",
    )
    return {
        "schema": WORKBOOK_SCHEMA,
        "tables": tablas,
        "labels": sorted(set(etiquetas)),
        "worksheets": sorted((w.get("name") or "") for w in raiz.iter("worksheet")),
    }
