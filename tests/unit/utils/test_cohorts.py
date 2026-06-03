"""Tests para el helper de cohorte (is_neuro / filter_neuro)."""

import pandas as pd

from epiforecast.constants import NEURO_CONDITIONS
from epiforecast.utils.cohorts import filter_neuro, is_neuro


class TestIsNeuro:
    def test_neuro_conditions_true(self):
        for p in NEURO_CONDITIONS:
            assert is_neuro(p)

    def test_dengue_false(self):
        assert not is_neuro("Dengue")

    def test_none_false(self):
        assert not is_neuro(None)

    def test_unknown_false(self):
        assert not is_neuro("Zika")


class TestFilterNeuro:
    def _df(self):
        return pd.DataFrame(
            {"Padecimiento": ["Depresión", "Parkinson", "Alzheimer", "Dengue"], "x": [1, 2, 3, 4]}
        )

    def test_excludes_dengue(self):
        out = filter_neuro(self._df())
        assert "Dengue" not in out["Padecimiento"].tolist()
        assert len(out) == 3

    def test_missing_column_noop(self):
        df = pd.DataFrame({"otra": [1, 2]})
        out = filter_neuro(df)
        assert len(out) == 2  # no-op si falta la columna

    def test_custom_column(self):
        df = pd.DataFrame({"pad": ["Dengue", "Parkinson"], "x": [1, 2]})
        out = filter_neuro(df, col="pad")
        assert out["pad"].tolist() == ["Parkinson"]
