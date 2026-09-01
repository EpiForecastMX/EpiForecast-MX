"""Los agregados legacy públicos sólo se validan en el carril manual de integración.

No se omiten si faltan: ese carril declara que va a comprobar los artefactos y su ausencia
es un fallo. El job normal usa ``-m 'not integration'`` y los deselecciona, por lo que no
aparecen como cuatro skips verdes en un clon que nunca restauró los CSV.
"""

from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
DISEASE = "obesidad"


@pytest.mark.parametrize(
    "artefacto",
    [
        "reports/forecasts/prophet/all_forecast_prophet.csv",
        "reports/forecasts/deepar/all_forecast_deepar.csv",
        "reports/forecasts/ensemble/all_forecast_ensemble.csv",
        "reports/forecasts/stacking/all_forecast_stacking.csv",
    ],
)
def test_los_agregados_legacy_no_contienen_obesidad(artefacto: str) -> None:
    """Compilar Obesidad jamás añade filas a los agregados de los cuatro publicados."""
    ruta = REPO / artefacto
    assert ruta.is_file(), (
        f"{artefacto} no está restaurado; el carril de integración no puede validar "
        "un artefacto ausente"
    )
    padecimientos = set(
        pd.read_csv(ruta, usecols=["meta_padecimiento"])["meta_padecimiento"].astype(str)
    )
    assert padecimientos, f"{artefacto} está vacío"
    assert not {value for value in padecimientos if value.lower() == DISEASE}
