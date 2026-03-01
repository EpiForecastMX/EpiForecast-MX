"""Tests para chart_constants: constantes de layout y estilo."""

from epiforecast.visualization.chart_constants import (
    ALPHA_BAND,
    ALPHA_COVID,
    ALPHA_FORECAST_ZONE,
    ALPHA_GRID,
    ALPHA_OBS,
    FIGSIZE,
    MARGINS,
)


class TestChartConstants:
    def test_figsize_is_tuple(self):
        assert isinstance(FIGSIZE, tuple)
        assert len(FIGSIZE) == 2
        assert all(isinstance(x, int | float) for x in FIGSIZE)

    def test_margins_is_dict(self):
        assert isinstance(MARGINS, dict)
        expected_keys = {"bottom", "top", "left", "right"}
        assert set(MARGINS.keys()) == expected_keys

    def test_alphas_in_valid_range(self):
        alphas = [ALPHA_BAND, ALPHA_OBS, ALPHA_FORECAST_ZONE, ALPHA_COVID, ALPHA_GRID]
        for alpha in alphas:
            assert 0 <= alpha <= 1, f"Alpha {alpha} fuera de rango [0, 1]"
