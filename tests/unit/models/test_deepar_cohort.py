"""Tests para los overrides cohort-aware de DeepAR (historia corta, p.ej. Dengue)."""

from __future__ import annotations

import pandas as pd

from epiforecast.models.factory import create_model

_SHORT_CFG = {
    "deepar": {
        "context_length": 104,
        "prediction_length": 52,
        "freq": "W-MON",
        "short_series": {
            "enabled": True,
            "context_length": 52,
            "max_lag": 53,
            "cv_n_splits": 2,
            "cv_test_size": 26,
            "gap_fill": "interpolate",
        },
    }
}


def test_neuro_no_aplica_short_series() -> None:
    """Un padecimiento neuro conserva la config larga y gap-fill en cero."""
    m = create_model(
        "deepar",
        df=pd.DataFrame(),
        sexo=None,
        entidad=None,
        padecimiento="Depresión",
        config=_SHORT_CFG,
    )
    assert m.short_max_lag is None
    assert m.context_length == 104
    assert m.gap_fill == "zero"
    assert m.cv_n_splits_override is None
    assert m.cv_test_size_override is None


def test_dengue_aplica_short_series() -> None:
    """Dengue (no neuro) acorta memoria, capa lags, aligera CV e interpola huecos."""
    m = create_model(
        "deepar",
        df=pd.DataFrame(),
        sexo=None,
        entidad=None,
        padecimiento="Dengue",
        config=_SHORT_CFG,
    )
    assert m.short_max_lag == 53
    assert m.context_length == 52
    assert m.gap_fill == "interpolate"
    assert m.cv_n_splits_override == 2
    assert m.cv_test_size_override == 26


def test_interpolate_rellena_huecos_sin_inventar_ceros() -> None:
    """Un hueco de boletin se interpola; una semana real con 0 se conserva en 0."""
    m = create_model(
        "deepar",
        df=pd.DataFrame(),
        sexo=None,
        entidad=None,
        padecimiento="Dengue",
        config=_SHORT_CFG,
    )
    # Semana 2 ausente (hueco), semana 4 presente con valor 0
    idx = pd.to_datetime(["2024-01-01", "2024-01-15", "2024-01-22"])
    ts = pd.Series([10.0, 30.0, 0.0], index=idx)
    out = m._resample_fill(ts)
    # 2024-01-08 fue interpolado (≈20), no quedo en 0
    assert out.loc["2024-01-08"] > 0
    # 2024-01-22 era un 0 real y se conserva
    assert out.loc["2024-01-22"] == 0


def test_gap_fill_zero_neuro_rellena_huecos_con_cero() -> None:
    """Cohorte neuro (gap_fill='zero'): los huecos se rellenan con 0, sin interpolar."""
    m = create_model(
        "deepar",
        df=pd.DataFrame(),
        sexo=None,
        entidad=None,
        padecimiento="Depresión",
        config=_SHORT_CFG,
    )
    assert m.gap_fill == "zero"
    idx = pd.to_datetime(["2024-01-01", "2024-01-15", "2024-01-22"])
    ts = pd.Series([10.0, 30.0, 5.0], index=idx)
    out = m._resample_fill(ts)
    # 2024-01-08 (hueco) se rellena con 0 (comportamiento neuro historico), no interpola
    assert out.loc["2024-01-08"] == 0
