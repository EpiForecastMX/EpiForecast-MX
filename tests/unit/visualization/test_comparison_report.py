# tests/unit/visualization/test_comparison_report.py
"""Unit tests for comparison_report.py and comparison_html.py."""

import pandas as pd

from epiforecast.visualization.comparison_html import (
    _html_metric_table,
    fmt,
    html_footer,
    html_head,
    html_resumen,
    winner_among,
)
from epiforecast.visualization.comparison_report import (
    _assign_modelo_productivo,
    _merge_all_models,
)

# -- fmt ----------------------------------------------------------------------


class TestFmt:
    def test_float_value(self) -> None:
        assert fmt(3.14159, 2) == "3.14"

    def test_integer_value(self) -> None:
        assert fmt(42, 0) == "42"

    def test_none_returns_na(self) -> None:
        assert fmt(None) == "N/A"

    def test_nan_returns_na(self) -> None:
        assert fmt(float("nan")) == "N/A"

    def test_string_number(self) -> None:
        assert fmt("2.5", 1) == "2.5"

    def test_non_numeric_string(self) -> None:
        assert fmt("abc") == "N/A"

    def test_default_decimals(self) -> None:
        assert fmt(1.23456789) == "1.2346"


# -- winner_among -------------------------------------------------------------


class TestWinnerAmong:
    def test_prophet_wins(self) -> None:
        row = pd.Series({"rmse_prophet": 1.0, "rmse_deepar": 2.0})
        assert winner_among(row, "rmse", ["prophet", "deepar"]) == "prophet"

    def test_deepar_wins(self) -> None:
        row = pd.Series({"rmse_prophet": 5.0, "rmse_deepar": 3.0})
        assert winner_among(row, "rmse", ["prophet", "deepar"]) == "deepar"

    def test_four_models(self) -> None:
        row = pd.Series(
            {
                "smape_prophet": 10.0,
                "smape_deepar": 8.0,
                "smape_ensemble": 6.0,
                "smape_stacking": 7.0,
            }
        )
        assert (
            winner_among(row, "smape", ["prophet", "deepar", "ensemble", "stacking"]) == "ensemble"
        )

    def test_tie_returns_first(self) -> None:
        row = pd.Series({"rmse_prophet": 1.0, "rmse_deepar": 1.0})
        result = winner_among(row, "rmse", ["prophet", "deepar"])
        assert result == "prophet"

    def test_nan_values(self) -> None:
        row = pd.Series({"rmse_prophet": float("nan"), "rmse_deepar": 1.0})
        assert winner_among(row, "rmse", ["prophet", "deepar"]) == "deepar"

    def test_missing_col(self) -> None:
        row = pd.Series({"rmse_prophet": 1.0})
        assert winner_among(row, "rmse", ["prophet", "deepar"]) == "prophet"


# -- html_head ----------------------------------------------------------------


class TestHtmlHead:
    def test_returns_html_string(self) -> None:
        result = html_head("2026-01-01 12:00", ["prophet", "deepar"])
        assert "<!DOCTYPE html>" in result
        assert "2026-01-01 12:00" in result

    def test_contains_all_model_names(self) -> None:
        result = html_head("now", ["prophet", "deepar", "ensemble", "stacking"])
        assert "Prophet" in result
        assert "DeepAR" in result
        assert "Ensemble" in result
        assert "Stacking" in result
        assert "4 modelos" in result

    def test_contains_style(self) -> None:
        result = html_head("now", ["prophet"])
        assert "<style>" in result
        assert ".winner" in result
        assert ".prod-badge" in result


# -- html_footer --------------------------------------------------------------


class TestHtmlFooter:
    def test_returns_closing_tags(self) -> None:
        result = html_footer("2026-01-01 12:00")
        assert "</html>" in result
        assert "2026-01-01 12:00" in result


# -- html_resumen -------------------------------------------------------------


class TestHtmlResumen:
    def test_renders_table_4_models(self) -> None:
        merged = pd.DataFrame(
            {
                "padecimiento": ["Alzheimer", "Alzheimer"],
                "rmse_prophet": [1.0, 2.0],
                "rmse_deepar": [1.5, 2.5],
                "rmse_ensemble": [0.9, 1.8],
                "rmse_stacking": [1.1, 2.1],
                "mae_prophet": [0.8, 1.2],
                "mae_deepar": [0.9, 1.3],
                "mae_ensemble": [0.7, 1.0],
                "mae_stacking": [0.85, 1.1],
                "smape_prophet": [10.0, 12.0],
                "smape_deepar": [11.0, 13.0],
                "smape_ensemble": [9.0, 11.0],
                "smape_stacking": [10.5, 12.5],
                "mase_prophet": [0.5, 0.6],
                "mase_deepar": [0.7, 0.8],
                "mase_ensemble": [0.4, 0.5],
                "mase_stacking": [0.55, 0.65],
                "modelo_productivo": ["ensemble", "ensemble"],
            }
        )
        result = html_resumen(merged, ["Alzheimer"], ["prophet", "deepar", "ensemble", "stacking"])
        assert "<table>" in result
        assert "Alzheimer" in result
        assert "Ensemble" in result
        assert "prod-ensemble" in result

    def test_empty_padecimientos(self) -> None:
        merged = pd.DataFrame(columns=["padecimiento", "modelo_productivo"])
        result = html_resumen(merged, [], ["prophet"])
        assert "<table>" in result


# -- _html_metric_table -------------------------------------------------------


class TestHtmlMetricTable:
    def test_renders_rows(self) -> None:
        data = pd.DataFrame(
            {
                "Entidad": ["Nacional"],
                "sexo": ["incrementos_total"],
                "rmse_prophet": [1.0],
                "rmse_deepar": [1.5],
                "smape_prophet": [10.0],
                "smape_deepar": [12.0],
                "mae_prophet": [0.8],
                "mae_deepar": [0.9],
                "mase_prophet": [0.5],
                "mase_deepar": [0.6],
                "modelo_productivo": ["prophet"],
            }
        )
        result = _html_metric_table(data, ["prophet", "deepar"])
        assert "<table>" in result
        assert "Nacional" in result
        assert "prod-prophet" in result

    def test_renders_4_models(self) -> None:
        data = pd.DataFrame(
            {
                "Entidad": ["Sonora"],
                "sexo": ["incrementos_total"],
                "rmse_prophet": [1.0],
                "rmse_deepar": [1.5],
                "rmse_ensemble": [0.9],
                "rmse_stacking": [1.1],
                "mae_prophet": [0.8],
                "mae_deepar": [0.9],
                "mae_ensemble": [0.7],
                "mae_stacking": [0.85],
                "smape_prophet": [10.0],
                "smape_deepar": [11.0],
                "smape_ensemble": [9.0],
                "smape_stacking": [10.5],
                "mase_prophet": [0.5],
                "mase_deepar": [0.7],
                "mase_ensemble": [0.4],
                "mase_stacking": [0.55],
                "modelo_productivo": ["ensemble"],
            }
        )
        result = _html_metric_table(data, ["prophet", "deepar", "ensemble", "stacking"])
        assert "Sonora" in result
        assert "winner" in result
        assert "prod-ensemble" in result


# -- _merge_all_models -------------------------------------------------------


class TestMergeAllModels:
    def test_two_models(self) -> None:
        df_p = pd.DataFrame(
            {
                "padecimiento": ["Alz"],
                "sexo": ["total"],
                "nivel": ["nacional"],
                "Entidad": [""],
                "rmse": [1.0],
                "smape": [10.0],
            }
        )
        df_d = pd.DataFrame(
            {
                "padecimiento": ["Alz"],
                "sexo": ["total"],
                "nivel": ["nacional"],
                "Entidad": [""],
                "rmse": [2.0],
                "smape": [15.0],
            }
        )
        merged = _merge_all_models({"prophet": df_p, "deepar": df_d})
        assert "rmse_prophet" in merged.columns
        assert "rmse_deepar" in merged.columns
        assert len(merged) == 1
        assert merged["rmse_prophet"].iloc[0] == 1.0
        assert merged["smape_deepar"].iloc[0] == 15.0

    def test_empty_dict(self) -> None:
        merged = _merge_all_models({})
        assert merged.empty

    def test_single_model(self) -> None:
        df = pd.DataFrame(
            {
                "padecimiento": ["Alz"],
                "sexo": ["total"],
                "nivel": ["nacional"],
                "Entidad": [""],
                "rmse": [3.0],
                "mae": [2.0],
            }
        )
        merged = _merge_all_models({"ensemble": df})
        assert "rmse_ensemble" in merged.columns
        assert "mae_ensemble" in merged.columns


# -- _assign_modelo_productivo -----------------------------------------------


class TestAssignModeloProductivo:
    def test_assigns_by_smape(self) -> None:
        df = pd.DataFrame(
            {
                "smape_prophet": [10.0, 20.0],
                "smape_deepar": [15.0, 5.0],
            }
        )
        result = _assign_modelo_productivo(df, ["prophet", "deepar"])
        assert result["modelo_productivo"].iloc[0] == "prophet"
        assert result["modelo_productivo"].iloc[1] == "deepar"

    def test_no_smape_cols(self) -> None:
        df = pd.DataFrame({"rmse_prophet": [1.0]})
        result = _assign_modelo_productivo(df, ["prophet"])
        assert result["modelo_productivo"].iloc[0] == ""

    def test_four_models(self) -> None:
        df = pd.DataFrame(
            {
                "smape_prophet": [10.0],
                "smape_deepar": [12.0],
                "smape_ensemble": [8.0],
                "smape_stacking": [9.0],
            }
        )
        result = _assign_modelo_productivo(df, ["prophet", "deepar", "ensemble", "stacking"])
        assert result["modelo_productivo"].iloc[0] == "ensemble"
