# tests/unit/visualization/test_comparison_report.py
"""Unit tests for comparison_report.py (HTML report generation)."""

import pandas as pd

from epiforecast.visualization.comparison_report import (
    _fmt,
    _ganador_class,
    _html_footer,
    _html_head,
    _html_metric_table,
    _html_resumen,
)

# ── _fmt ─────────────────────────────────────────────────────────────────────


class TestFmt:
    def test_float_value(self):
        assert _fmt(3.14159, 2) == "3.14"

    def test_integer_value(self):
        assert _fmt(42, 0) == "42"

    def test_none_returns_na(self):
        assert _fmt(None) == "N/A"

    def test_nan_returns_na(self):
        assert _fmt(float("nan")) == "N/A"

    def test_string_number(self):
        assert _fmt("2.5", 1) == "2.5"

    def test_non_numeric_string(self):
        assert _fmt("abc") == "N/A"

    def test_default_decimals(self):
        assert _fmt(1.23456789) == "1.2346"


# ── _ganador_class ───────────────────────────────────────────────────────────


class TestGanadorClass:
    def test_prophet_wins(self):
        p_cls, d_cls = _ganador_class(1.0, 2.0)
        assert p_cls == "winner"
        assert d_cls == ""

    def test_deepar_wins(self):
        p_cls, d_cls = _ganador_class(5.0, 3.0)
        assert p_cls == ""
        assert d_cls == "winner"

    def test_tie(self):
        p_cls, d_cls = _ganador_class(1.0, 1.0)
        assert p_cls == ""
        assert d_cls == ""

    def test_none_values(self):
        p_cls, d_cls = _ganador_class(None, 1.0)
        assert p_cls == ""
        assert d_cls == ""

    def test_nan_values(self):
        p_cls, d_cls = _ganador_class(float("nan"), 1.0)
        assert p_cls == ""
        assert d_cls == ""

    def test_string_values(self):
        p_cls, d_cls = _ganador_class("abc", 1.0)
        assert p_cls == ""
        assert d_cls == ""


# ── _html_head ───────────────────────────────────────────────────────────────


class TestHtmlHead:
    def test_returns_html_string(self):
        result = _html_head("2026-01-01 12:00")
        assert "<!DOCTYPE html>" in result
        assert "2026-01-01 12:00" in result

    def test_contains_title(self):
        result = _html_head("now")
        assert "EpiForecast-MX" in result

    def test_contains_style(self):
        result = _html_head("now")
        assert "<style>" in result
        assert ".winner" in result


# ── _html_footer ─────────────────────────────────────────────────────────────


class TestHtmlFooter:
    def test_returns_closing_tags(self):
        result = _html_footer("2026-01-01 12:00")
        assert "</html>" in result
        assert "2026-01-01 12:00" in result


# ── _html_resumen ────────────────────────────────────────────────────────────


class TestHtmlResumen:
    def test_renders_table(self):
        merged = pd.DataFrame(
            {
                "padecimiento": ["Alzheimer", "Alzheimer"],
                "rmse_p": [1.0, 2.0],
                "rmse_d": [1.5, 2.5],
                "mae_p": [0.8, 1.2],
                "mae_d": [0.9, 1.3],
                "smape_p": [10.0, 12.0],
                "smape_d": [11.0, 13.0],
                "mase_p": [0.5, 0.6],
                "mase_d": [0.7, 0.8],
            }
        )
        result = _html_resumen(merged, ["Alzheimer"], ["rmse", "mae", "smape", "mase"])
        assert "<table>" in result
        assert "Alzheimer" in result

    def test_empty_padecimientos(self):
        merged = pd.DataFrame(columns=["padecimiento"])
        result = _html_resumen(merged, [], ["rmse"])
        assert "<table>" in result


# ── _html_metric_table ───────────────────────────────────────────────────────


class TestHtmlMetricTable:
    def test_renders_rows(self):
        data = pd.DataFrame(
            {
                "Entidad": ["Nacional"],
                "sexo": ["incrementos_total"],
                "rmse_p": [1.0],
                "rmse_d": [1.5],
                "confianza_p": ["normal"],
            }
        )
        result = _html_metric_table(data, ["rmse"])
        assert "<table>" in result
        assert "Nacional" in result

    def test_insuficiente_class(self):
        data = pd.DataFrame(
            {
                "Entidad": ["Sonora"],
                "sexo": ["incrementos_total"],
                "rmse_p": [1.0],
                "rmse_d": [1.5],
                "confianza_p": ["insuficiente"],
            }
        )
        result = _html_metric_table(data, ["rmse"])
        assert "insuf" in result
