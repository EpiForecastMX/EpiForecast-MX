"""C7.6-ADAPTERS-B0.4 — el workbook Tableau de staging: generado, genérico y verificado.

Lo que protege: que el artefacto de staging **no** sea una copia del productivo —ni su servidor, ni
su `cloudFileId`, ni sus cinco tablas—, que lleve la etiqueta de validación y la advertencia
point-only, que sus filtros salgan de los datos y que no pueda escribirse dentro del repositorio.

`reports/dashboards/viz_epiforecastmx.twb` no se abre en ninguna prueba: sólo se comprueba que sigue
byte-idéntico.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd
import pytest
from scripts.tableau_workbook import RC_OK, RC_REFUSED, WORKBOOK_PRODUCTIVO
from scripts.tableau_workbook import main as generar

from epiforecast.publication.compiler import POINT_ONLY_SUFFIX
from epiforecast.publication.sheets_sink import LEGACY_TABS, PRODUCTION_ID_ENV, STAGING_ID_ENV
from epiforecast.publication.tableau_adapter import (
    TABLE_FORECAST,
    TABLE_RELEASES,
    ArtifactValidationError,
    build_tables,
)
from epiforecast.publication.tableau_workbook import (
    MAX_FILTER_CARDINALITY,
    WORKBOOK_SCHEMA,
    build_workbook_xml,
    filter_dimensions,
    verify_workbook,
)
from tests.unit.publication.test_tableau_adapter import ETIQUETA, _shard

ID_STAGING = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF"
ID_PRODUCCION = "1ZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZzZ"
ENTORNO = {STAGING_ID_ENV: ID_STAGING, PRODUCTION_ID_ENV: ID_PRODUCCION}


def _xml(tmp_path, **kwargs) -> bytes:
    tablas = build_tables(_shard(tmp_path, filas=3))
    return build_workbook_xml(
        tablas,
        spreadsheet_id=kwargs.pop("spreadsheet_id", ID_STAGING),
        label=kwargs.pop("label", ETIQUETA),
    )


# ── El artefacto generado ──────────────────────────────────────────────────────────────────────
def test_el_workbook_declara_las_dos_tablas_del_namespace_y_ninguna_legacy(tmp_path):
    resumen = verify_workbook(_xml(tmp_path), forbidden_ids=[ID_PRODUCCION])
    assert resumen["tables"] == [TABLE_FORECAST, TABLE_RELEASES]
    assert resumen["schema"] == WORKBOOK_SCHEMA
    texto = _xml(tmp_path).decode("utf-8")
    for legacy in LEGACY_TABS:
        assert f'table="{legacy}"' not in texto


def test_la_etiqueta_y_el_point_only_viajan_con_las_cifras(tmp_path):
    xml = _xml(tmp_path)
    resumen = verify_workbook(xml)
    assert resumen["labels"] == [ETIQUETA]
    raiz = ET.fromstring(xml.decode("utf-8"))
    pies = [c.text for c in raiz.iter("caption-formatted-text")]
    assert pies and all(POINT_ONLY_SUFFIX in (p or "") for p in pies)
    assert len(resumen["worksheets"]) == 2


def test_el_id_llega_por_parametro_y_no_hay_rastro_del_productivo(tmp_path):
    texto = _xml(tmp_path).decode("utf-8")
    assert ID_STAGING in texto, "el id de staging es el que conecta"
    assert ID_PRODUCCION not in texto
    assert "public.tableau.com" not in texto and 'cloudFileId=""' not in texto


def test_es_determinista(tmp_path):
    uno, otro = _xml(tmp_path), _xml(tmp_path)
    assert hashlib.sha256(uno).hexdigest() == hashlib.sha256(otro).hexdigest()


def test_sin_etiqueta_no_se_genera(tmp_path):
    with pytest.raises(ArtifactValidationError, match="etiqueta de validación"):
        _xml(tmp_path, label="   ")
    with pytest.raises(ArtifactValidationError, match="id de la hoja"):
        _xml(tmp_path, spreadsheet_id="")


# ── Filtros derivados ──────────────────────────────────────────────────────────────────────────
def test_los_filtros_salen_de_los_datos_no_de_una_lista(tmp_path):
    tablas = build_tables(_shard(tmp_path, filas=3))
    filtros = filter_dimensions(tablas.forecast)
    assert "geography_level" in filtros and filtros["geography_level"] == ["estado"]
    assert "sex" in filtros
    for prohibido in ("yhat_cases", "yhat_lower", "yhat_upper", "ds"):
        assert prohibido not in filtros, "la medida y las columnas vacías no son filtros"
    # Por encima del umbral una columna deja de ser filtro: sería una lista, no un filtro.
    muchos = tablas.forecast.assign(geography_id=[f"{i:03d}" for i in range(len(tablas.forecast))])
    for _ in range(4):  # 3 filas × 4 = 12 < umbral; se replica
        muchos = pd.concat([muchos, muchos], ignore_index=True)
    muchos["geography_id"] = [f"{i:03d}" for i in range(len(muchos))]
    assert len(set(muchos["geography_id"])) > MAX_FILTER_CARDINALITY
    assert "geography_id" not in filter_dimensions(muchos)


def test_el_generador_no_conoce_ningun_padecimiento_por_su_nombre():
    fuente = Path("src/epiforecast/publication/tableau_workbook.py").read_text(encoding="utf-8")
    for prohibido in ("Obesidad", "obesidad", "E66", "Depresion", "Dengue"):
        assert prohibido not in fuente, f"{prohibido} escrito en el generador"
    # Las cinco legacy no se escriben aquí: llegan importadas de una sola definición.
    assert "from .sheets_sink import LEGACY_TABS" in fuente
    assert "LEGACY_TABS = " not in fuente, "no se redefine la lista"
    for legacy in ("scaffold", "entidades", "metricas"):
        assert legacy not in fuente, f"{legacy} escrito a mano en el generador"


# ── El verificador ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("sustituir", "por", "patron"),
    [
        ("sheets.googleapis.com", "public.tableau.com", "public.tableau.com"),
        (ID_STAGING, ID_PRODUCCION, "id de hoja prohibido"),
        ('filename="runner_forecast"', 'filename="/Users/alguien/extract.hyper"', "ruta absoluta"),
        (f'table="{TABLE_FORECAST}"', f'table="{LEGACY_TABS[0]}"', "legacy|inesperadas"),
        (WORKBOOK_SCHEMA, "otra-cosa", "source-build"),
        (POINT_ONLY_SUFFIX, "sin advertencia", "point-only"),
    ],
)
def test_el_verificador_rechaza_lo_que_no_puede_estar(tmp_path, sustituir, por, patron):
    texto = _xml(tmp_path).decode("utf-8")
    assert sustituir in texto, "la prueba tiene que alterar algo que de verdad está"
    alterado = texto.replace(sustituir, por).encode("utf-8")
    with pytest.raises(ArtifactValidationError, match=patron):
        verify_workbook(alterado, forbidden_ids=[ID_PRODUCCION])


def test_el_verificador_rechaza_un_xml_base_de_tableau_public(tmp_path):
    texto = (
        _xml(tmp_path)
        .decode("utf-8")
        .replace("<workbook ", '<workbook xml:base="https://otro.example" ', 1)
    )
    with pytest.raises(ArtifactValidationError, match="xml:base"):
        verify_workbook(texto.encode("utf-8"))


# ── El CLI ─────────────────────────────────────────────────────────────────────────────────────
def _generar(tmp_path, destino, **kwargs):
    salida = io.StringIO()
    rc = generar(
        [
            "--shard",
            str(_shard(tmp_path, filas=3)),
            "--out",
            str(destino),
            *kwargs.pop("extra", []),
        ],
        entorno=kwargs.pop("entorno", ENTORNO),
        raiz_repo=kwargs.pop("raiz_repo", Path.cwd()),
        salida=salida,
    )
    return rc, salida.getvalue()


def test_escribe_bajo_un_temporal_y_verifica(tmp_path):
    destino = tmp_path / "runs" / "staging.twb"
    rc, salida = _generar(tmp_path, destino)
    assert rc == RC_OK, salida
    assert destino.is_file()
    assert verify_workbook(destino, forbidden_ids=[ID_PRODUCCION])["tables"] == [
        TABLE_FORECAST,
        TABLE_RELEASES,
    ]


def test_no_escribe_dentro_del_repositorio(tmp_path):
    rc, salida = _generar(tmp_path, Path("reports/dashboards/staging.twb"))
    assert rc == RC_REFUSED
    assert "no se versiona" in salida


def test_no_puede_apuntar_al_workbook_productivo(tmp_path):
    rc, salida = _generar(tmp_path, WORKBOOK_PRODUCTIVO)
    assert rc == RC_REFUSED
    assert "productivo" in salida


def test_exige_extension_twb(tmp_path):
    rc, salida = _generar(tmp_path, tmp_path / "runs" / "staging.xml")
    assert rc == RC_REFUSED
    assert ".twb" in salida


def test_sin_hoja_de_staging_declarada_no_genera(tmp_path):
    rc, salida = _generar(tmp_path, tmp_path / "runs" / "x.twb", entorno={})
    assert rc == RC_REFUSED
    assert STAGING_ID_ENV in salida


def test_el_id_productivo_como_parametro_se_rechaza(tmp_path):
    rc, salida = _generar(
        tmp_path, tmp_path / "runs" / "x.twb", extra=["--spreadsheet-id", ID_PRODUCCION]
    )
    assert rc == RC_REFUSED
    assert "productivo" in salida


def test_el_workbook_productivo_sigue_byte_identico():
    """No se abre, no se lee para copiar nada: sólo se comprueba que nadie lo tocó."""
    import subprocess

    ruta = WORKBOOK_PRODUCTIVO
    if not ruta.is_file():
        pytest.skip("el workbook productivo no está en este árbol")
    estado = subprocess.run(
        ["git", "status", "--porcelain", "--", str(ruta)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert estado.stdout.strip() == "", f"{ruta} aparece modificado: {estado.stdout!r}"
