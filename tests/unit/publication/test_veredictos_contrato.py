"""Contrato de veredictos con el frontend, que vive en otro repositorio.

`epibot/scripts/lib/candidate.mjs` rechaza cualquier veredicto que no conozca, y su prueba fija la
misma lista. Sin este par, `CONTROL_ONLY` nació en el backend sin que el instalador del sitio lo
aceptara, y el fallo sólo habría aparecido al completar 4/4. Si cambias esta lista, cambia también
`VERDICTS` en ese archivo y publícalo antes.
"""

import pytest

from epiforecast.publication.status import VERDICTS, VERDICTS_PUBLICABLES

pytestmark = pytest.mark.unit


def test_lista_de_veredictos_igual_a_la_del_frontend() -> None:
    assert VERDICTS == ("INCOMPLETE", "PASS", "FAIL", "CONTROL_ONLY")


def test_fail_es_el_unico_veredicto_no_publicable() -> None:
    assert set(VERDICTS) - set(VERDICTS_PUBLICABLES) == {"FAIL"}
