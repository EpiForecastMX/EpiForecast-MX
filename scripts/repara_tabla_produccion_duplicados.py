"""Repara claves duplicadas de la tabla de producción con la autoridad de Dengue.

`reports/ProdDetails/tabla_333_modelos_produccion.xlsx` (rastreada) llevaba 435 filas: las
tres series nacionales de Dengue aparecían dos veces, con motores y sMAPE contradictorios
(filas Prophet y filas DeepAR). La causa raíz —el merge N-way no unificaba el agregado
nacional que cada motor codifica distinto— ya está corregida en
`avance5_data.merge_all_models`; regenerar la tabla exige re-correr el backtest CV de los
432 modelos (~19 min y los `.pkl`), que no es una reparación sino otra corrida.

Esta reparación es mínima y determinista: para cada clave (padecimiento, entidad, sexo)
repetida se conserva la fila cuyo `modelo_produccion` coincide con la autoridad
(`reports/ProdDetails/produccion_dengue.csv`, el selector productivo de Dengue que
`catalog.py` documenta como fuente del Dengue publicado) y se retiran las demás, en TODAS
las hojas que llevan la clave; `numero` se renumera 1..N para conservar la invariante
«numero == posición» que el generador garantiza. Si una clave repetida no tiene
exactamente una fila que case con la autoridad, o la autoridad no la conoce, se aborta sin
escribir. La salida es byte-reproducible: mismas propiedades del documento y marcas de
tiempo fijas en el ZIP, así que dos corridas dan el mismo SHA256.

Uso:
    python scripts/repara_tabla_produccion_duplicados.py \\
        --tabla reports/ProdDetails/tabla_333_modelos_produccion.xlsx \\
        --autoridad reports/ProdDetails/produccion_dengue.csv \\
        --out <destino.xlsx>
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import io
from pathlib import Path
import re
import sys
import unicodedata
import zipfile

from openpyxl import load_workbook
import pandas as pd

CLAVE = ("padecimiento", "entidad", "sexo")
FECHA_FIJA = (1980, 1, 1, 0, 0, 0)
MARCA_DOCUMENTO = datetime(2026, 9, 2, 0, 0, 0)


class ReparacionError(ValueError):
    pass


def _slug(texto: object) -> str:
    plano = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in plano if not unicodedata.combining(c)).lower().strip()


def _clave(fila: pd.Series) -> tuple[str, str, str]:
    return tuple(_slug(fila[c]) for c in CLAVE)  # type: ignore[return-value]


def autoridad_de(ruta: Path) -> dict[tuple[str, str, str], str]:
    """(padecimiento, entidad, sexo) -> motor productivo, desde produccion_dengue.csv."""
    df = pd.read_csv(ruta)
    faltan = [c for c in (*CLAVE, "motor_productivo") if c not in df.columns]
    if faltan:
        raise ReparacionError(f"la autoridad {ruta.name} no trae las columnas {faltan}")
    autoridad: dict[tuple[str, str, str], str] = {}
    for _, fila in df.iterrows():
        clave = _clave(fila)
        if clave in autoridad:
            raise ReparacionError(f"la autoridad repite la clave {clave}")
        autoridad[clave] = _slug(fila["motor_productivo"])
    return autoridad


def filas_a_retirar(
    hoja: pd.DataFrame, autoridad: dict[tuple[str, str, str], str]
) -> tuple[list[int], list[str]]:
    """Índices (posicionales) de las filas repetidas que contradicen la autoridad."""
    if any(c not in hoja.columns for c in (*CLAVE, "modelo_produccion")):
        raise ReparacionError("la hoja no trae padecimiento/entidad/sexo/modelo_produccion")
    claves = [_clave(f) for _, f in hoja.iterrows()]
    repetidas = {k for k in claves if claves.count(k) > 1}
    retirar: list[int] = []
    decisiones: list[str] = []
    for clave in sorted(repetidas):
        if clave not in autoridad:
            raise ReparacionError(f"la clave repetida {clave} no está en la autoridad")
        posiciones = [i for i, k in enumerate(claves) if k == clave]
        casan = [
            i for i in posiciones if _slug(hoja.iloc[i]["modelo_produccion"]) == autoridad[clave]
        ]
        if len(casan) != 1:
            raise ReparacionError(
                f"la clave repetida {clave} tiene {len(casan)} fila(s) que casan con la "
                f"autoridad ({autoridad[clave]}); se exige exactamente una"
            )
        sobran = [i for i in posiciones if i != casan[0]]
        retirar.extend(sobran)
        decisiones.append(
            f"{clave}: conserva fila {int(hoja.iloc[casan[0]]['numero'])} "
            f"({hoja.iloc[casan[0]]['modelo_produccion']}), retira "
            f"{[int(hoja.iloc[i]['numero']) for i in sobran]} "
            f"({[hoja.iloc[i]['modelo_produccion'] for i in sobran]})"
        )
    return sorted(retirar), decisiones


def repara(tabla: Path, autoridad_ruta: Path) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Todas las hojas, con las filas contradictorias retiradas y `numero` renumerado."""
    autoridad = autoridad_de(autoridad_ruta)
    hojas = pd.read_excel(tabla, sheet_name=None)
    decisiones: list[str] = []
    reparadas: dict[str, pd.DataFrame] = {}
    numeros_retirados: set[int] | None = None
    for nombre, hoja in hojas.items():
        if not all(c in hoja.columns for c in CLAVE):
            reparadas[nombre] = hoja
            continue
        retirar, nuevas = filas_a_retirar(hoja, autoridad)
        retirados = {int(hoja.iloc[i]["numero"]) for i in retirar}
        if numeros_retirados is None:
            numeros_retirados = retirados
        elif retirados != numeros_retirados:
            raise ReparacionError(
                f"la hoja {nombre!r} retiraría {sorted(retirados)} y la primera "
                f"{sorted(numeros_retirados)}; las hojas no cuentan la misma historia"
            )
        decisiones.extend(f"[{nombre}] {d}" for d in nuevas)
        limpia = hoja.drop(index=hoja.index[retirar]).reset_index(drop=True)
        if "numero" in limpia.columns:
            limpia["numero"] = range(1, len(limpia) + 1)
        reparadas[nombre] = limpia
    if not numeros_retirados:
        raise ReparacionError("la tabla no tiene claves repetidas; nada que reparar")
    return reparadas, decisiones


def escribe_reproducible(hojas: dict[str, pd.DataFrame], destino: Path) -> str:
    """Escribe el libro como lo hace el pipeline (pandas/openpyxl) y fija lo no determinista."""
    crudo = io.BytesIO()
    with pd.ExcelWriter(crudo, engine="openpyxl") as escritor:
        for nombre, hoja in hojas.items():
            hoja.to_excel(escritor, sheet_name=nombre, index=False)
    crudo.seek(0)
    libro = load_workbook(crudo)
    libro.properties.creator = "openpyxl"
    libro.properties.lastModifiedBy = None
    libro.properties.created = MARCA_DOCUMENTO
    libro.properties.modified = MARCA_DOCUMENTO
    con_props = io.BytesIO()
    libro.save(con_props)
    con_props.seek(0)
    # openpyxl estampa la hora local en cada entrada del ZIP y la hora de guardado en
    # `docProps/core.xml` (pisa `properties.modified` al guardar): se reempaqueta con fecha
    # fija en las entradas y con las marcas del documento fijadas en el XML.
    salida = io.BytesIO()
    marca = MARCA_DOCUMENTO.strftime("%Y-%m-%dT%H:%M:%SZ")
    with (
        zipfile.ZipFile(con_props) as origen,
        zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z,
    ):
        for info in origen.infolist():
            contenido = origen.read(info.filename)
            if info.filename == "docProps/core.xml":
                texto = contenido.decode("utf-8")
                texto = re.sub(
                    r"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
                    rf"\g<1>{marca}\g<2>",
                    texto,
                )
                contenido = texto.encode("utf-8")
            nuevo = zipfile.ZipInfo(info.filename, date_time=FECHA_FIJA)
            nuevo.compress_type = zipfile.ZIP_DEFLATED
            nuevo.external_attr = info.external_attr
            z.writestr(nuevo, contenido)
    contenido = salida.getvalue()
    destino.write_bytes(contenido)
    return hashlib.sha256(contenido).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tabla", required=True, type=Path)
    parser.add_argument("--autoridad", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        hojas, decisiones = repara(args.tabla, args.autoridad)
        digest = escribe_reproducible(hojas, args.out)
    except ReparacionError as exc:
        print(f"ABORTA: {exc}", file=sys.stderr)
        return 1
    for d in decisiones:
        print(f"    {d}")
    for nombre, hoja in hojas.items():
        print(f"    hoja {nombre!r}: {len(hoja)} filas")
    print(f"    escrito {args.out} sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
