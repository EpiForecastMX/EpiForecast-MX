"""Vista de rechazados: sólo sale de un rechazo autorizado y cuenta el año de prueba tal cual."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from scripts.rejected_view import comprobaciones, exige_rechazo, prueba_serie

from epiforecast import registry
from epiforecast.runner.artifact_identity import ArtifactValidationError

_RUN = "run_rechazado"
_CADENA = {"acceptance_outcome": "fallback_control", "acceptance_run_id": _RUN}


def _disease(**cambios):
    base = {"id": "x", "lifecycle": "trained", "channels": (), "acceptance_fallback_run": _RUN}
    return SimpleNamespace(**{**base, **cambios})


def test_un_rechazo_autorizado_sin_publicar_pasa():
    exige_rechazo(_disease(), _CADENA)


@pytest.mark.parametrize(
    "cambios",
    [
        {"lifecycle": "published"},
        {"channels": ("web",)},
        {"acceptance_fallback_run": "otro"},
    ],
)
def test_no_sale_de_un_padecimiento_publicado_o_sin_autorizar(cambios):
    with pytest.raises(ArtifactValidationError):
        exige_rechazo(_disease(**cambios), _CADENA)


def test_no_sale_de_un_release_aceptado():
    with pytest.raises(ArtifactValidationError, match="no cayó al control"):
        exige_rechazo(_disease(), {"acceptance_run_id": _RUN})


def test_comprobaciones_conservan_el_veredicto():
    acta = {
        "checks": [
            {
                "scope": "smape_nacional_general",
                "portfolio": 104.745,
                "control": 87.678,
                "worse_pct": 19.465,
                "max_worse_pct": 10.0,
                "passed": False,
            }
        ]
    }
    fila = comprobaciones(acta)[0]
    assert (fila["portafolio"], fila["control"], fila["peor_pct"]) == (104.7, 87.7, 19.5)
    assert fila["pasa"] is False


def _semanas(pred: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "epi_year": 2025,
            "epi_week": range(1, len(pred) + 1),
            "ds": [f"2025-01-0{i}" for i in range(1, len(pred) + 1)],
            "y_true_cases": [10.0] * len(pred),
            "y_pred_cases": pred,
        }
    )


def test_la_prueba_separa_portafolio_y_control():
    r = prueba_serie(_semanas([30.0, 30.0]), _semanas([10.0, 10.0]))
    assert r["observado"] == [10, 10]
    assert r["smape_control"] == 0.0
    assert r["smape_portafolio"] > 0.0


def test_covid_es_el_rechazado_autorizado_sin_canales():
    spec = registry.require("covid_19")
    assert spec.lifecycle == "trained" and not spec.channels
    assert spec.acceptance_fallback_run == "covid_19_benchmark_test_effc1d95aa18_cc0cc27ec02b"
    assert "covid-19" not in [n.lower() for n in registry.names(published_only=True)]
