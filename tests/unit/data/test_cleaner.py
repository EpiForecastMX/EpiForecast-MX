# tests/unit/data/test_cleaner.py
"""Unit tests for CleanDataset (src/epiforecast/data/preprocessing/cleaner.py).

CleanDataset reads cleaning rules from `conf` at construction time.  All tests
patch the module-level `conf` name so no real YAML files are required.
"""

from unittest.mock import patch

import pandas as pd
import pytest

# The module under test — imported here so the patch target is unambiguous.
import epiforecast.data.preprocessing.cleaner as cleaner_mod
from epiforecast.data.preprocessing.cleaner import CleanDataset

# ── Helper ─────────────────────────────────────────────────────────────────────

_EMPTY_CONF: dict = {
    "columnas_eliminar": [],
    "valores_sustituir": [],
    "registros_eliminar": [],
}


def _make_cleaner(df: pd.DataFrame, conf_override: dict | None = None) -> CleanDataset:
    """Create a CleanDataset with a patched `conf`, avoiding real YAML loading."""
    effective_conf = conf_override if conf_override is not None else _EMPTY_CONF
    with patch.object(cleaner_mod, "conf", effective_conf):
        return CleanDataset(df)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def simple_df() -> pd.DataFrame:
    """Minimal DataFrame for cleaner tests."""
    return pd.DataFrame(
        {
            "Entidad": ["Jalisco", "CIUDAD DE MEXICO", "Oaxaca", "ELIMINAR"],
            "col_a_eliminar": [1, 2, 3, 4],
            "Casos": [10, 20, 15, 5],
        }
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestColumnNormalisation:
    """Column names with leading/trailing spaces are stripped."""

    def test_strips_whitespace_from_column_names(self):
        """Column names with spaces are cleaned on initialisation."""
        df = pd.DataFrame({" Entidad ": ["Jalisco"], " Casos ": [10]})
        cleaner = _make_cleaner(df)
        cleaner.run()

        assert "Entidad" in cleaner.df.columns
        assert "Casos" in cleaner.df.columns

    def test_columns_without_spaces_unchanged(self, simple_df: pd.DataFrame):
        """Clean column names must not be altered."""
        cleaner = _make_cleaner(simple_df)
        cleaner.run()

        assert "Entidad" in cleaner.df.columns
        assert "Casos" in cleaner.df.columns


class TestColumnDeletion:
    """_elimina_columnas() removes columns listed in conf['columnas_eliminar']."""

    def test_listed_column_is_dropped(self, simple_df: pd.DataFrame):
        """Column present in columnas_eliminar must be removed."""
        conf = {**_EMPTY_CONF, "columnas_eliminar": ["col_a_eliminar"]}
        cleaner = _make_cleaner(simple_df, conf)
        result = cleaner.run()

        assert "col_a_eliminar" not in result.columns

    def test_unlisted_columns_are_kept(self, simple_df: pd.DataFrame):
        """Columns not in the list must remain in the DataFrame."""
        conf = {**_EMPTY_CONF, "columnas_eliminar": ["col_a_eliminar"]}
        cleaner = _make_cleaner(simple_df, conf)
        result = cleaner.run()

        assert "Entidad" in result.columns
        assert "Casos" in result.columns

    def test_missing_column_does_not_raise(self, simple_df: pd.DataFrame):
        """If the configured column does not exist, no exception is raised."""
        conf = {**_EMPTY_CONF, "columnas_eliminar": ["columna_inexistente"]}
        cleaner = _make_cleaner(simple_df, conf)
        result = cleaner.run()  # must not raise

        assert result is not None

    def test_resumen_counts_eliminated_columns(self, simple_df: pd.DataFrame):
        """resumen() must reflect the number of deleted columns."""
        conf = {**_EMPTY_CONF, "columnas_eliminar": ["col_a_eliminar"]}
        cleaner = _make_cleaner(simple_df, conf)
        cleaner.run()

        resumen = cleaner.resumen()
        assert "1" in resumen["Columnas eliminadas"]


class TestValueSubstitution:
    """_sustituir_valores() replaces old values with new ones."""

    def test_replaces_matching_value(self, simple_df: pd.DataFrame):
        """Old value must be replaced by the configured substitute."""
        conf = {
            **_EMPTY_CONF,
            "valores_sustituir": [
                {
                    "columna_objetivo": "Entidad",
                    "texto_a_reemplazar": "CIUDAD DE MEXICO",
                    "texto_sustituto": "Ciudad de México",
                }
            ],
        }
        cleaner = _make_cleaner(simple_df, conf)
        result = cleaner.run()

        assert "CIUDAD DE MEXICO" not in result["Entidad"].values
        assert "Ciudad de México" in result["Entidad"].values

    def test_non_matching_value_unchanged(self, simple_df: pd.DataFrame):
        """Rows that don't match the substitution rule are untouched."""
        conf = {
            **_EMPTY_CONF,
            "valores_sustituir": [
                {
                    "columna_objetivo": "Entidad",
                    "texto_a_reemplazar": "CIUDAD DE MEXICO",
                    "texto_sustituto": "Ciudad de México",
                }
            ],
        }
        cleaner = _make_cleaner(simple_df, conf)
        result = cleaner.run()

        assert "Jalisco" in result["Entidad"].values
        assert "Oaxaca" in result["Entidad"].values

    def test_missing_column_does_not_raise(self, simple_df: pd.DataFrame):
        """Rule targeting a non-existent column must be skipped silently."""
        conf = {
            **_EMPTY_CONF,
            "valores_sustituir": [
                {
                    "columna_objetivo": "ColumnaInexistente",
                    "texto_a_reemplazar": "X",
                    "texto_sustituto": "Y",
                }
            ],
        }
        cleaner = _make_cleaner(simple_df, conf)
        cleaner.run()  # must not raise

    def test_resumen_counts_substitutions(self, simple_df: pd.DataFrame):
        """resumen() must report the number of substitutions applied."""
        conf = {
            **_EMPTY_CONF,
            "valores_sustituir": [
                {
                    "columna_objetivo": "Entidad",
                    "texto_a_reemplazar": "CIUDAD DE MEXICO",
                    "texto_sustituto": "Ciudad de México",
                }
            ],
        }
        cleaner = _make_cleaner(simple_df, conf)
        cleaner.run()

        resumen = cleaner.resumen()
        assert resumen["Sustituciones aplicadas"] == "1"


class TestRecordDeletion:
    """_eliminar_registros() removes rows whose column matches a value."""

    def test_matching_row_is_removed(self, simple_df: pd.DataFrame):
        """Row with the configured value must be deleted."""
        conf = {
            **_EMPTY_CONF,
            "registros_eliminar": [{"columna_objetivo": "Entidad", "valor": "ELIMINAR"}],
        }
        cleaner = _make_cleaner(simple_df, conf)
        result = cleaner.run()

        assert "ELIMINAR" not in result["Entidad"].values

    def test_other_rows_remain(self, simple_df: pd.DataFrame):
        """Rows that do not match the deletion rule must be preserved."""
        conf = {
            **_EMPTY_CONF,
            "registros_eliminar": [{"columna_objetivo": "Entidad", "valor": "ELIMINAR"}],
        }
        cleaner = _make_cleaner(simple_df, conf)
        result = cleaner.run()

        assert len(result) == len(simple_df) - 1

    def test_index_reset_after_deletion(self, simple_df: pd.DataFrame):
        """DataFrame index must be contiguous after row deletion."""
        conf = {
            **_EMPTY_CONF,
            "registros_eliminar": [{"columna_objetivo": "Entidad", "valor": "ELIMINAR"}],
        }
        cleaner = _make_cleaner(simple_df, conf)
        result = cleaner.run()

        assert list(result.index) == list(range(len(result)))

    def test_missing_column_does_not_raise(self, simple_df: pd.DataFrame):
        """Deletion rule with non-existent column must be skipped silently."""
        conf = {
            **_EMPTY_CONF,
            "registros_eliminar": [{"columna_objetivo": "ColumnaFalsa", "valor": "X"}],
        }
        cleaner = _make_cleaner(simple_df, conf)
        cleaner.run()  # must not raise


class TestResumenMetrics:
    """resumen() returns a dict that accurately reflects what was done."""

    def test_resumen_before_initial_row_count(self, simple_df: pd.DataFrame):
        """'Filas antes' must equal the original DataFrame length."""
        cleaner = _make_cleaner(simple_df)
        cleaner.run()

        resumen = cleaner.resumen()
        assert resumen["Filas antes"] == f"{len(simple_df):,}"

    def test_no_changes_returns_equal_row_counts(self, simple_df: pd.DataFrame):
        """With empty rules, before and after row counts must be equal."""
        cleaner = _make_cleaner(simple_df)
        cleaner.run()

        resumen = cleaner.resumen()
        assert resumen["Filas antes"] == resumen["Filas después"]
