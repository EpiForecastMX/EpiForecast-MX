"""Validación semanal: rango de fechas del boletín (calendario v2) y corte declarado en el pie.

Ancla: portada del boletín W39 de 2026, «del 27 de septiembre al 3 de octubre del 2026».
"""

from __future__ import annotations

import pandas as pd
import pytest
from scripts.genera_validacion_semanal import _corte_declarado, _epiweek_date_range

pytestmark = pytest.mark.unit


def test_rango_es_la_semana_epidemiologica_publicada() -> None:
    assert _epiweek_date_range(2026, 39) == "27 septiembre - 3 octubre 2026"
    assert _epiweek_date_range(2025, 53) == "28 diciembre - 3 enero 2026"
    assert _epiweek_date_range(2026, 20) == "17-23 mayo 2026"


def test_corte_declarado_por_los_pronosticos() -> None:
    fc = pd.DataFrame(
        {"anio_boletin_corte": [2026.0, 2026.0], "semana_boletin_corte": [37.0, 37.0]}
    )
    assert _corte_declarado(fc) == (2026, 37)
    assert _corte_declarado(fc.drop(columns="semana_boletin_corte")) is None
    with pytest.raises(SystemExit):
        _corte_declarado(
            pd.DataFrame({"anio_boletin_corte": [2026, 2026], "semana_boletin_corte": [33, 37]})
        )
