# tests/unit/test_constants.py
"""Unit tests for project-wide constants (src/epiforecast/constants.py).

Validates the static data that drives the whole pipeline — condition codes,
state list, region names, sex modes, and numeric defaults.
"""

import pytest

from epiforecast.constants import (
    CONDITIONS,
    CV_HORIZON_DAYS,
    CV_INITIAL_DAYS,
    CV_PERIOD_DAYS,
    INEGI_REGIONS,
    RATE_PER,
    SEX_MODES,
    STATES,
)


class TestConditions:
    """CONDITIONS maps ICD-10 codes → Spanish disease names."""

    def test_has_exactly_three_conditions(self):
        """Pipeline expects exactly F32, G20, G30."""
        assert len(CONDITIONS) == 3

    def test_required_icd10_keys_present(self):
        """All three ICD-10 codes must be present."""
        assert "F32" in CONDITIONS
        assert "G20" in CONDITIONS
        assert "G30" in CONDITIONS

    def test_no_unexpected_keys(self):
        """Only the three configured codes should exist."""
        assert set(CONDITIONS.keys()) == {"F32", "G20", "G30"}

    @pytest.mark.parametrize(
        "code, expected_name",
        [
            ("F32", "Depresión"),
            ("G20", "Parkinson"),
            ("G30", "Alzheimer"),
        ],
    )
    def test_condition_names(self, code: str, expected_name: str):
        """Each ICD-10 code maps to the correct Spanish disease name."""
        assert CONDITIONS[code] == expected_name

    def test_all_values_are_non_empty_strings(self):
        """No empty or None disease names."""
        for code, name in CONDITIONS.items():
            assert isinstance(name, str), f"Nombre para {code} no es str"
            assert name.strip(), f"Nombre vacío para {code}"


class TestStates:
    """STATES must contain all 32 Mexican entities."""

    def test_exactly_32_states(self):
        """Mexico has exactly 32 federative entities."""
        assert len(STATES) == 32

    def test_all_entries_are_non_empty_strings(self):
        """No blank or non-string entries allowed."""
        for state in STATES:
            assert isinstance(state, str), f"Entrada inválida: {state!r}"
            assert state.strip(), f"Nombre de estado vacío: {state!r}"

    def test_no_duplicates(self):
        """Each state appears exactly once."""
        assert len(STATES) == len(set(STATES))

    @pytest.mark.parametrize(
        "state",
        [
            "Ciudad de México",
            "Jalisco",
            "Oaxaca",
            "Yucatán",
            "Nuevo León",
        ],
    )
    def test_key_states_present(self, state: str):
        """Spot-check that key entities are in the list."""
        assert state in STATES


class TestInegiRegions:
    """INEGI_REGIONS must contain all four mental-health regions."""

    def test_exactly_four_regions(self):
        assert len(INEGI_REGIONS) == 4

    def test_known_region_names(self):
        expected = {
            "Urbana media",
            "Sur-Sureste vulnerable",
            "Metropolitana alta",
            "Rural / dispersa",
        }
        assert set(INEGI_REGIONS) == expected


class TestSexModes:
    """SEX_MODES drives model segmentation."""

    def test_three_sex_modes(self):
        assert len(SEX_MODES) == 3

    def test_required_modes_present(self):
        assert "general" in SEX_MODES
        assert "hombres" in SEX_MODES
        assert "mujeres" in SEX_MODES


class TestNumericConstants:
    """Numeric constants used in rate normalisation and CV config."""

    def test_rate_per_is_100k(self):
        """Rates are expressed per 100 000 inhabitants."""
        assert RATE_PER == 100_000

    def test_cv_initial_days_positive(self):
        assert CV_INITIAL_DAYS > 0

    def test_cv_period_days_positive(self):
        assert CV_PERIOD_DAYS > 0

    def test_cv_horizon_days_positive(self):
        assert CV_HORIZON_DAYS > 0

    def test_cv_initial_longer_than_period(self):
        """Initial window must be larger than a single CV step."""
        assert CV_INITIAL_DAYS > CV_PERIOD_DAYS
