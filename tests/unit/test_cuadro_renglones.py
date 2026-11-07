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
