"""Tests for ensemble helper functions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from epiforecast.models.ensemble.helpers import (
    calcular_metricas_ensemble,
    calcular_metricas_prophet_base,
    preparar_datos_ensemble,
)

# ---------------------------------------------------------------------------
# preparar_datos_ensemble
# ---------------------------------------------------------------------------


def _make_df(n: int = 200) -> pd.DataFrame:
    dates = pd.date_range("2020-01-06", periods=n, freq="W-MON")
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "ds": dates,
            "y": rng.uniform(10, 100, n),
            "Padecimiento": "Depresion",
        }
    )


class TestPrepararDatos:
    def test_basic_split(self) -> None:
        df = _make_df()
        serie, train, test = preparar_datos_ensemble(
            df,
            padecimiento="Depresion",
            sexo="y",
            cutoff="2023-06-01",
        )
        assert not serie.empty
        assert not train.empty
        assert "ds" in train.columns
        assert "y" in train.columns

    def test_empty_df_raises(self) -> None:
        with pytest.raises(ValueError, match="vacio"):
            preparar_datos_ensemble(pd.DataFrame(), "Depresion", "y", "2023-01-01")

    def test_cutoff_splits_correctly(self) -> None:
        df = _make_df()
        cutoff = "2023-01-01"
        _, train, test = preparar_datos_ensemble(df, "Depresion", "y", cutoff)
        assert (train["ds"] < pd.Timestamp(cutoff)).all()
        if not test.empty:
            assert (test["ds"] >= pd.Timestamp(cutoff)).all()

    def test_y_original_column_present(self) -> None:
        df = _make_df()
        serie, _, _ = preparar_datos_ensemble(df, "Depresion", "y", "2023-06-01")
        assert "y_original" in serie.columns

    def test_with_fecha_column(self) -> None:
        df = _make_df()
        df = df.rename(columns={"ds": "Fecha"})
        df["Casos"] = df["y"]
        serie, train, _ = preparar_datos_ensemble(df, "Depresion", "Casos", "2023-06-01")
        assert not serie.empty

    def test_no_matching_column_raises(self) -> None:
        df = pd.DataFrame(
            {
                "ds": pd.date_range("2020-01-01", periods=5, freq="W"),
                "Padecimiento": "X",
                "other_col": range(5),
            }
        )
        with pytest.raises(ValueError, match="No se encontro columna"):
            preparar_datos_ensemble(df, "X", "nonexistent", "2023-01-01")

    def test_padecimiento_accent_matching(self) -> None:
        df = _make_df()
        df["Padecimiento"] = "Depresi\u00f3n"  # con acento
        serie, _, _ = preparar_datos_ensemble(df, "Depresion", "y", "2023-06-01")
        assert not serie.empty


# ---------------------------------------------------------------------------
# calcular_metricas_ensemble
# ---------------------------------------------------------------------------


class TestCalcularMetricasEnsemble:
    def test_basic_metrics(self) -> None:
        dates = pd.date_range("2024-01-01", periods=10, freq="W-MON")
        train = pd.DataFrame({"ds": dates[:7], "y": np.arange(7, dtype=float) + 10})
        test = pd.DataFrame({"ds": dates[7:], "y": [15.0, 18.0, 22.0]})
        pred = pd.DataFrame({"ds": dates[7:], "yhat_ensemble": [14.0, 19.0, 21.0]})
        result = calcular_metricas_ensemble(test, pred, train, "test_model", 1.5)
        assert result["modelo"] == "test_model"
        assert result["rmse"] > 0
        assert result["tiempo"] == 1.5

    def test_empty_test_returns_zeros(self) -> None:
        result = calcular_metricas_ensemble(
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame({"y": [1, 2, 3]}),
            "empty",
            0.0,
        )
        assert result["rmse"] == 0.0
        assert result["mase"] is None


# ---------------------------------------------------------------------------
# calcular_metricas_prophet_base
# ---------------------------------------------------------------------------


class TestCalcularMetricasProphetBase:
    def test_basic_metrics(self) -> None:
        dates = pd.date_range("2024-01-01", periods=10, freq="W-MON")
        train = pd.DataFrame({"ds": dates[:7], "y": np.arange(7, dtype=float) + 10})
        test = pd.DataFrame({"ds": dates[7:], "y": [15.0, 18.0, 22.0]})
        pred = pd.DataFrame({"ds": dates[7:], "yhat_prophet": [16.0, 17.0, 23.0]})
        result = calcular_metricas_prophet_base(test, pred, train, 2.0)
        assert result["modelo"] == "Prophet Base"
        assert result["rmse"] > 0
        assert result["tiempo"] == 2.0

    def test_empty_returns_zeros(self) -> None:
        result = calcular_metricas_prophet_base(
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame({"y": [1]}),
            0.0,
        )
        assert result["rmse"] == 0.0
