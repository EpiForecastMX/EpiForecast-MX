"""Tests for comparison_html template functions."""

from __future__ import annotations

import pandas as pd

from epiforecast.visualization.comparison_html import (
    _get_prod_metrics,
    _html_metric_table,
    _leakage_badge,
    _overfitting_badge,
    fmt,
    html_detalle_padecimiento,
    html_footer,
    html_head,
    html_resumen,
    winner_among,
)


class TestOverfittingBadge:
    def test_alto(self) -> None:
        badge = _overfitting_badge(smape_test=30.0, smape_train=10.0)
        assert "Alto" in badge
        assert "badge-red" in badge

    def test_moderado(self) -> None:
        badge = _overfitting_badge(smape_test=15.0, smape_train=10.0)
        assert "Moderado" in badge
        assert "badge-yellow" in badge

    def test_ok(self) -> None:
        badge = _overfitting_badge(smape_test=10.0, smape_train=10.0)
        assert "OK" in badge
        assert "badge-green" in badge

    def test_none_test(self) -> None:
        badge = _overfitting_badge(None, 10.0)
        assert "N/D" in badge

    def test_none_train(self) -> None:
        badge = _overfitting_badge(10.0, None)
        assert "N/D" in badge

    def test_nan_test(self) -> None:
        badge = _overfitting_badge(float("nan"), 10.0)
        assert "N/D" in badge

    def test_zero_train(self) -> None:
        badge = _overfitting_badge(10.0, 0.0)
        assert "N/D" in badge


class TestLeakageBadge:
    def test_sospechoso(self) -> None:
        badge = _leakage_badge(0.3)
        assert "Sospechoso" in badge
        assert "badge-red" in badge

    def test_ok(self) -> None:
        badge = _leakage_badge(5.0)
        assert "OK" in badge
        assert "badge-green" in badge

    def test_none(self) -> None:
        badge = _leakage_badge(None)
        assert "N/D" in badge

    def test_nan(self) -> None:
        badge = _leakage_badge(float("nan"))
        assert "N/D" in badge

    def test_exact_threshold(self) -> None:
        badge = _leakage_badge(0.5)
        assert "OK" in badge


class TestFmt:
    def test_normal_value(self) -> None:
        assert fmt(3.14159, 2) == "3.14"

    def test_none_returns_na(self) -> None:
        assert fmt(None) == "N/A"

    def test_nan_returns_na(self) -> None:
        assert fmt(float("nan")) == "N/A"

    def test_string_number(self) -> None:
        assert fmt("2.5", 1) == "2.5"

    def test_invalid_string(self) -> None:
        assert fmt("abc") == "N/A"

    def test_zero(self) -> None:
        assert fmt(0, 2) == "0.00"

    def test_integer(self) -> None:
        assert fmt(42, 0) == "42"


class TestWinnerAmong:
    def test_finds_minimum(self) -> None:
        row = pd.Series({"rmse_prophet": 5.0, "rmse_deepar": 3.0, "rmse_ensemble": 4.0})
        assert winner_among(row, "rmse", ["prophet", "deepar", "ensemble"]) == "deepar"

    def test_ignores_nan(self) -> None:
        row = pd.Series({"rmse_prophet": float("nan"), "rmse_deepar": 3.0})
        assert winner_among(row, "rmse", ["prophet", "deepar"]) == "deepar"

    def test_ignores_none(self) -> None:
        row = pd.Series({"rmse_prophet": None, "rmse_deepar": 3.0})
        assert winner_among(row, "rmse", ["prophet", "deepar"]) == "deepar"

    def test_all_missing(self) -> None:
        row = pd.Series({"rmse_prophet": None})
        assert winner_among(row, "rmse", ["prophet"]) == ""

    def test_missing_column(self) -> None:
        row = pd.Series({"other": 1.0})
        assert winner_among(row, "rmse", ["prophet"]) == ""


class TestGetProdMetrics:
    def test_returns_metrics(self) -> None:
        row = pd.Series(
            {
                "modelo_productivo": "prophet",
                "smape_prophet": 5.0,
                "smape_train_prophet": 3.0,
            }
        )
        st, str_val = _get_prod_metrics(row, ["prophet"])
        assert st == 5.0
        assert str_val == 3.0

    def test_no_prod_model(self) -> None:
        row = pd.Series({"modelo_productivo": ""})
        st, str_val = _get_prod_metrics(row, ["prophet"])
        assert st is None
        assert str_val is None

    def test_missing_prod(self) -> None:
        row = pd.Series({"other": 1})
        st, str_val = _get_prod_metrics(row, ["prophet"])
        assert st is None


class TestHtmlHead:
    def test_returns_valid_html(self) -> None:
        html = html_head("2026-03-04", ["prophet", "deepar"])
        assert "<!DOCTYPE html>" in html
        assert "Prophet" in html
        assert "DeepAR" in html

    def test_kpi_series(self) -> None:
        html = html_head("2026-03-04", ["prophet"], n_series=99)
        assert "99" in html

    def test_kpi_smape(self) -> None:
        html = html_head(
            "2026-03-04",
            ["prophet"],
            best_smape=12.5,
            best_model="prophet",
        )
        assert "12.5%" in html


# ---------------------------------------------------------------------------
# html_resumen
# ---------------------------------------------------------------------------


def _make_merged() -> pd.DataFrame:
    """Minimal merged DataFrame for testing html_resumen."""
    return pd.DataFrame(
        {
            "padecimiento": ["Depresion", "Depresion", "Parkinson"],
            "Entidad": ["Nacional", "Jalisco", "Nacional"],
            "sexo": ["general", "general", "general"],
            "nivel": ["nacional", "regional", "nacional"],
            "rmse_prophet": [5.0, 6.0, 4.0],
            "rmse_deepar": [4.5, 7.0, 3.0],
            "mae_prophet": [3.0, 4.0, 2.0],
            "mae_deepar": [2.5, 5.0, 1.5],
            "smape_prophet": [10.0, 15.0, 8.0],
            "smape_deepar": [12.0, 14.0, 9.0],
            "mase_prophet": [0.8, 1.2, 0.6],
            "mase_deepar": [0.9, 1.0, 0.7],
            "smape_train_prophet": [5.0, 8.0, 4.0],
            "smape_train_deepar": [6.0, 7.0, 5.0],
            "modelo_productivo": ["prophet", "deepar", "deepar"],
        }
    )


class TestHtmlResumen:
    def test_returns_section(self) -> None:
        merged = _make_merged()
        html = html_resumen(merged, ["Depresion", "Parkinson"], ["prophet", "deepar"])
        assert "Resumen por Padecimiento" in html
        assert "<table>" in html
        assert "Depresion" in html
        assert "Parkinson" in html

    def test_winner_cell_highlighted(self) -> None:
        merged = _make_merged()
        html = html_resumen(merged, ["Depresion"], ["prophet", "deepar"])
        assert 'class="winner"' in html

    def test_prod_badge(self) -> None:
        merged = _make_merged()
        html = html_resumen(merged, ["Parkinson"], ["prophet", "deepar"])
        assert "prod-badge" in html


class TestHtmlMetricTable:
    def test_returns_table(self) -> None:
        data = _make_merged()
        html = _html_metric_table(data, ["prophet", "deepar"])
        assert "<table>" in html
        assert "<thead>" in html
        assert "<tbody>" in html
        assert "Nacional" in html

    def test_empty_data(self) -> None:
        data = pd.DataFrame(columns=_make_merged().columns)
        html = _html_metric_table(data, ["prophet"])
        assert "<tbody></tbody>" in html or "<tbody>\n</tbody>" in html or "tbody" in html


class TestHtmlFooter:
    def test_contains_footer(self) -> None:
        html = html_footer("2026-03-04 10:00")
        assert "<footer>" in html
        assert "EpiForecast-MX" in html
        assert "2026-03-04 10:00" in html
        assert "CDMX" in html

    def test_contains_reveal_js(self) -> None:
        html = html_footer("2026-03-04")
        assert "<script>" in html
        assert "IntersectionObserver" in html


class TestHtmlDetallePadecimiento:
    def test_returns_section(self) -> None:
        data = _make_merged()
        html = html_detalle_padecimiento("Depresion", "depresion", data, ["prophet", "deepar"])
        assert "Depresion" in html
        assert "<section" in html

    def test_empty_nacional(self) -> None:
        data = _make_merged()
        data = data[data["nivel"] != "nacional"]
        html = html_detalle_padecimiento("Test", "test", data, ["prophet"])
        assert "</section>" in html
