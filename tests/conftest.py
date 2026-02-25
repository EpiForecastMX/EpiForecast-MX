# tests/conftest.py
"""Shared fixtures for the EpiForecast-MX test suite.

Fixtures here are available to all test files without explicit imports.
"""

import sys
import types

import pandas as pd
import pytest


def pytest_configure(config):  # noqa: ARG001
    """Pre-inject a mock config module to avoid sys.exit(1) on YAML load failures.

    src/epiforecast/utils/config.py calls sys.exit(1) when config/rutas.yaml is
    not found (it was moved to config/_legacy/ during the refactor).  By inserting
    a lightweight mock into sys.modules *before* any test file is collected, we
    prevent the SystemExit from crashing pytest.

    setdefault is used so that if the YAML files ARE present (e.g. after a DVC
    pull in CI) the real module takes precedence.
    """
    from loguru import logger as _logger

    _mock = types.ModuleType("epiforecast.utils.config")
    _mock.conf = {  # type: ignore[attr-defined]
        "paths": {
            "utils": "/tmp/epi_test/utils",
            "figures": "/tmp/epi_test/figures",
            "models": "/tmp/epi_test/models",
        },
        "data": {
            "inegi": "/tmp/epi_test/utils/inegi.csv",
            "model_train": "/tmp/epi_test/train",
        },
    }
    _mock.logger = _logger  # type: ignore[attr-defined]
    sys.modules.setdefault("epiforecast.utils.config", _mock)


@pytest.fixture
def sample_epi_df() -> pd.DataFrame:
    """Minimal epidemiological DataFrame matching the project's data schema.

    Contains rows for three ICD-10 conditions, two states, two sexes and
    two weeks — enough to exercise filtering, grouping and aggregation logic.
    """
    data = {
        "Anio": [2023] * 12,
        "Semana": [1, 1, 1, 1, 2, 2, 2, 2, 1, 1, 2, 2],
        "Entidad": (["Jalisco"] * 4 + ["Jalisco"] * 4 + ["Oaxaca"] * 4),
        "Padecimiento": [
            "Depresión",
            "Depresión",
            "Parkinson",
            "Alzheimer",
            "Depresión",
            "Depresión",
            "Parkinson",
            "Alzheimer",
            "Depresión",
            "Depresión",
            "Parkinson",
            "Alzheimer",
        ],
        "Sexo": [
            "Hombres",
            "Mujeres",
            "Hombres",
            "Mujeres",
            "Hombres",
            "Mujeres",
            "Hombres",
            "Mujeres",
            "Hombres",
            "Mujeres",
            "Hombres",
            "Mujeres",
        ],
        "Casos": [10, 15, 5, 3, 12, 18, 6, 4, 8, 11, 2, 1],
        "CIE10": [
            "F32",
            "F32",
            "G20",
            "G30",
            "F32",
            "F32",
            "G20",
            "G30",
            "F32",
            "F32",
            "G20",
            "G30",
        ],
    }
    return pd.DataFrame(data)


@pytest.fixture
def mock_conf() -> dict:
    """Minimal mock of the project config dict (normally loaded from YAML).

    Only includes keys actually used by the modules under test.  Add new
    keys here as coverage expands.
    """
    return {
        "columnas_eliminar": ["col_a_eliminar"],
        "valores_sustituir": [
            {
                "columna_objetivo": "Entidad",
                "texto_a_reemplazar": "CIUDAD DE MEXICO",
                "texto_sustituto": "Ciudad de México",
            }
        ],
        "registros_eliminar": [{"columna_objetivo": "Entidad", "valor": "ELIMINAR"}],
        "padecimiento": {
            "tipo": "Depresión",
            "columna": "Padecimiento",
        },
    }
