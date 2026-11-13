"""Valores y entidad en renglones separados: el caso de 2014-2015 que se leía como ceros."""

from __future__ import annotations

import pandas as pd
import pytest

from epiforecast.data.extraction.cuadro_extractor import alinea_renglones

pytestmark = pytest.mark.unit


def test_une_valores_con_la_entidad_del_renglon_siguiente():
    df = pd.DataFrame([["", "194", "766"], ["Aguascalientes", "", ""]])
    out = alinea_renglones(df)
    assert out.iloc[1].tolist() == ["Aguascalientes", "194", "766"]
    assert out.iloc[0].tolist() == ["", "", ""]


def test_una_tabla_alineada_no_cambia():
    df = pd.DataFrame([["ENTIDAD", "Sem.", "Acum."], ["Aguascalientes", "194", "766"]])
    assert alinea_renglones(df).equals(df)


def test_no_toma_valores_de_un_renglon_con_nombre():
    df = pd.DataFrame([["Encabezado", "1", "2"], ["Aguascalientes", "", ""]])
    assert alinea_renglones(df).equals(df)


# Variante de 2024_sem50 en adelante (página de giardiasis y otras helmintiasis): el primer valor del
# renglón de valores cae en la columna del nombre y la segunda columna queda vacía.
def test_valor_en_nombre_une_y_mueve_el_primer_valor():
    from epiforecast.data.extraction.cuadro_extractor import alinea_valor_en_nombre

    df = pd.DataFrame(
        [
            ["-", "", "-", "", "13", "15"],
            ["Aguascalientes", "", "", "", "", ""],
            ["1", "", "1", "", "22", "30"],
            ["Baja California", "", "", "", "", ""],
        ]
    )
    out = alinea_valor_en_nombre(df)
    assert out.iloc[1].tolist() == ["Aguascalientes", "-", "-", "", "13", "15"]
    assert out.iloc[3].tolist() == ["Baja California", "1", "1", "", "22", "30"]
    assert out.iloc[0].tolist() == [""] * 6
    # Con la reparación anterior sola esas filas seguían sin valores (se leían como ceros).
    assert alinea_renglones(df).iloc[1].tolist() == ["Aguascalientes", "", "", "", "", ""]


def test_valor_en_nombre_no_toca_una_tabla_alineada_ni_un_encabezado():
    from epiforecast.data.extraction.cuadro_extractor import alinea_valor_en_nombre

    alineada = pd.DataFrame([["ENTIDAD", "Sem.", "Acum."], ["Aguascalientes", "194", "766"]])
    assert alinea_valor_en_nombre(alineada).equals(alineada.astype(str))
    # Un renglón previo con texto (no un valor suelto) no se une.
    encabezado = pd.DataFrame([["Sem.", "", "H", "M"], ["Aguascalientes", "", "", ""]])
    assert alinea_valor_en_nombre(encabezado).equals(encabezado.astype(str))
    # Si la segunda columna del renglón de valores no está vacía, no es este patrón.
    otro = pd.DataFrame([["1", "2", "3", "4"], ["Aguascalientes", "", "", ""]])
    assert alinea_valor_en_nombre(otro).equals(otro.astype(str))


def test_valor_pegado_al_nombre_en_la_misma_celda():
    from epiforecast.data.extraction.cuadro_extractor import alinea_valor_en_nombre

    df = pd.DataFrame(
        [
            ["Chihuahua", "", "", "", "", ""],
            ["8\nCiudad de México", "", "29", "", "30", "80"],
            ["-\nNuevo León", "", "5", "", "3", "14"],
        ]
    )
    out = alinea_valor_en_nombre(df)
    assert out.iloc[1].tolist() == ["Ciudad de México", "8", "29", "", "30", "80"]
    assert out.iloc[2].tolist() == ["Nuevo León", "-", "5", "", "3", "14"]
    # Sin la reparación la celda no se reconoce como entidad y el boletín pierde la fila.
    assert alinea_renglones(df).iloc[1, 0] == "8\nCiudad de México"
