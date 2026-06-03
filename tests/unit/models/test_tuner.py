"""Tests for tuner.py — ProphetTuner HP optimizer."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import epiforecast.models.prophet.tuner as tuner_mod
from epiforecast.models.prophet.tuner import _GRID_KEY_MAP, ProphetTuner

_MOCK_CONF = {
    "param_grid_prophet": {
        "alzheimer": {
            "seasonality_mode": ["multiplicative"],
            "changepoint_prior_scale": [0.03, 0.01],
            "seasonality_prior_scale": [0.05, 0.1],
        },
        "depresion": {
            "seasonality_mode": ["additive", "multiplicative"],
            "changepoint_prior_scale": [0.05, 0.01],
            "seasonality_prior_scale": [0.1],
        },
        "parkinson": {
            "seasonality_mode": ["multiplicative"],
            "changepoint_prior_scale": [0.05],
            "seasonality_prior_scale": [0.1],
        },
    },
    "cv_timeout_por_combo": 0,
}


def _make_tuner(padecimiento: str = "Alzheimer") -> ProphetTuner:
    forecaster = MagicMock()
    forecaster.df = pd.DataFrame({"Padecimiento": [padecimiento] * 5})
    with patch.object(tuner_mod, "conf", _MOCK_CONF):
        tuner = ProphetTuner(forecaster)
    return tuner


class TestGridKeyMap:
    def test_alzheimer_key(self):
        assert _GRID_KEY_MAP["Alzheimer"] == "alzheimer"

    def test_depresion_key(self):
        assert _GRID_KEY_MAP["Depresión"] == "depresion"

    def test_parkinson_key(self):
        assert _GRID_KEY_MAP["Parkinson"] == "parkinson"

    def test_all_diseases_mapped(self):
        # 3 neurológicos + Dengue
        assert len(_GRID_KEY_MAP) == 4
        assert _GRID_KEY_MAP["Dengue"] == "dengue"


class TestLoadGrid:
    def test_alzheimer_loads_grid(self):
        tuner = _make_tuner("Alzheimer")
        assert "changepoint_prior_scale" in tuner.param_grid

    def test_depresion_loads_grid(self):
        tuner = _make_tuner("Depresión")
        assert "seasonality_mode" in tuner.param_grid

    def test_unknown_padecimiento_raises(self):
        forecaster = MagicMock()
        forecaster.df = pd.DataFrame({"Padecimiento": ["Gripe"] * 3})
        with patch.object(tuner_mod, "conf", _MOCK_CONF):
            with pytest.raises(ValueError, match="param_grid_prophet"):
                ProphetTuner(forecaster)

    def test_grid_has_expected_keys(self):
        tuner = _make_tuner("Alzheimer")
        assert "seasonality_mode" in tuner.param_grid
        assert "changepoint_prior_scale" in tuner.param_grid
        assert "seasonality_prior_scale" in tuner.param_grid


class TestBuildSortedCombos:
    def test_returns_list_of_dicts(self):
        tuner = _make_tuner("Alzheimer")
        combos = tuner._build_sorted_combos()
        assert isinstance(combos, list)
        assert all(isinstance(c, dict) for c in combos)

    def test_sorted_by_cp_descending(self):
        tuner = _make_tuner("Alzheimer")
        combos = tuner._build_sorted_combos()
        cps = [c["changepoint_prior_scale"] for c in combos]
        assert cps == sorted(cps, reverse=True)

    def test_correct_number_of_combos_alzheimer(self):
        tuner = _make_tuner("Alzheimer")
        combos = tuner._build_sorted_combos()
        # alzheimer: 1 mode × 2 cp × 2 sp = 4
        assert len(combos) == 4

    def test_correct_number_of_combos_depresion(self):
        tuner = _make_tuner("Depresión")
        combos = tuner._build_sorted_combos()
        # depresion: 2 mode × 2 cp × 1 sp = 4
        assert len(combos) == 4

    def test_each_combo_has_all_keys(self):
        tuner = _make_tuner("Alzheimer")
        combos = tuner._build_sorted_combos()
        required = {"seasonality_mode", "changepoint_prior_scale", "seasonality_prior_scale"}
        for combo in combos:
            assert required.issubset(combo.keys())


class TestFallbackParams:
    def test_returns_dict(self):
        tuner = _make_tuner("Alzheimer")
        params = tuner._fallback_params()
        assert isinstance(params, dict)

    def test_selects_highest_cp(self):
        tuner = _make_tuner("Alzheimer")
        params = tuner._fallback_params()
        assert params["changepoint_prior_scale"] == max(
            _MOCK_CONF["param_grid_prophet"]["alzheimer"]["changepoint_prior_scale"]
        )

    def test_uses_first_value_for_other_keys(self):
        tuner = _make_tuner("Alzheimer")
        params = tuner._fallback_params()
        assert params["seasonality_mode"] == "multiplicative"
        assert params["seasonality_prior_scale"] == 0.05


class TestRun:
    def test_returns_params_and_metrics(self):
        tuner = _make_tuner("Alzheimer")
        mock_metrics = {"rmse": 0.1, "mae": 0.05, "mape": 10.0, "smape": 9.0, "mase": 0.8}
        with patch.object(tuner_mod, "ProphetCrossValidator") as MockCV:
            mock_cv = MagicMock()
            mock_cv.evaluate_combo.return_value = (mock_metrics, False, None)
            MockCV.return_value = mock_cv
            params, metrics = tuner.run()
        assert isinstance(params, dict)
        assert isinstance(metrics, dict)

    def test_best_rmse_selected(self):
        tuner = _make_tuner("Alzheimer")
        call_count = 0
        responses = [
            ({"rmse": 0.5, "mae": 0.3, "mape": 30.0, "smape": 25.0, "mase": 1.2}, False, None),
            ({"rmse": 0.1, "mae": 0.05, "mape": 5.0, "smape": 4.5, "mase": 0.8}, False, None),
            ({"rmse": 0.3, "mae": 0.2, "mape": 20.0, "smape": 17.0, "mase": 1.0}, False, None),
            ({"rmse": 0.2, "mae": 0.1, "mape": 10.0, "smape": 9.0, "mase": 0.9}, False, None),
        ]

        def side_effect(params):
            nonlocal call_count
            r = responses[call_count % len(responses)]
            call_count += 1
            return r

        with patch.object(tuner_mod, "ProphetCrossValidator") as MockCV:
            mock_cv = MagicMock()
            mock_cv.evaluate_combo.side_effect = side_effect
            MockCV.return_value = mock_cv
            params, metrics = tuner.run()
        assert metrics["rmse"] == 0.1

    def test_all_timeouts_uses_fallback(self):
        tuner = _make_tuner("Alzheimer")
        tuner.cv_timeout = 0  # disable combo-level timeout backstop
        with patch.object(tuner_mod, "ProphetCrossValidator") as MockCV:
            mock_cv = MagicMock()
            mock_cv.evaluate_combo.return_value = (
                {
                    "rmse": float("inf"),
                    "mae": float("inf"),
                    "mape": float("inf"),
                    "smape": float("inf"),
                    "mase": None,
                },
                True,
                0.03,
            )
            MockCV.return_value = mock_cv
            params, metrics = tuner.run()
        assert params is not None
        assert "changepoint_prior_scale" in params

    def test_newton_threshold_skips_low_cp(self):
        tuner = _make_tuner("Alzheimer")
        tuner.cv_timeout = 0
        evaluated_cps = []

        def side_effect(params):
            cp = params.get("changepoint_prior_scale", 0)
            evaluated_cps.append(cp)
            # Only the first (highest cp) times out
            if cp == 0.03:
                return (
                    {
                        "rmse": float("inf"),
                        "mae": float("inf"),
                        "mape": float("inf"),
                        "smape": float("inf"),
                        "mase": None,
                    },
                    True,
                    0.03,
                )
            return (
                {"rmse": 0.1, "mae": 0.05, "mape": 5.0, "smape": 4.5, "mase": 0.8},
                False,
                None,
            )

        with patch.object(tuner_mod, "ProphetCrossValidator") as MockCV:
            mock_cv = MagicMock()
            mock_cv.evaluate_combo.side_effect = side_effect
            MockCV.return_value = mock_cv
            params, metrics = tuner.run()
        # All combos with cp=0.01 should have been skipped
        assert 0.01 not in evaluated_cps
