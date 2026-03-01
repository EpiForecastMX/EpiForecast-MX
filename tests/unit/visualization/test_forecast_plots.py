# tests/unit/visualization/test_forecast_plots.py
"""Tests for forecast_plots.py — all pure helpers + orchestrator with mocks."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import epiforecast.visualization.forecast_plots as fp_mod
from epiforecast.visualization.forecast_plots import (
    _build_csv_path,
    _extract_metricas,
    _load_hp_data,
    _load_training_series,
    _nivel_directory,
    _normalizar_nombre,
    generar_graficos_pronostico,
)

# ── _normalizar_nombre ───────────────────────────────────────────────────────


class TestNormalizarNombre:
    def test_removes_accents(self):
        assert _normalizar_nombre("Depresión") == "Depresion"

    def test_replaces_spaces_with_underscore(self):
        assert _normalizar_nombre("Ciudad de México") == "Ciudad_de_Mexico"

    def test_replaces_slash_with_dash(self):
        assert _normalizar_nombre("Sur/Sureste") == "Sur-Sureste"

    def test_no_change_for_ascii(self):
        assert _normalizar_nombre("Jalisco") == "Jalisco"

    def test_handles_mixed_case(self):
        assert _normalizar_nombre("Baja California") == "Baja_California"

    def test_multiple_spaces_collapsed(self):
        assert _normalizar_nombre("Norte  Occidente") == "Norte_Occidente"

    def test_none_cast_to_string(self):
        assert _normalizar_nombre(None) == "None"  # type: ignore[arg-type]

    def test_alzheimer_with_accent(self):
        assert _normalizar_nombre("Álzheimer") == "Alzheimer"


# ── _nivel_directory ─────────────────────────────────────────────────────────


class TestNivelDirectory:
    def test_empty_string_returns_nacional(self):
        assert _nivel_directory("") == "Nacional"

    def test_nacional_returns_nacional(self):
        assert _nivel_directory("Nacional") == "Nacional"

    def test_nacional_case_insensitive(self):
        assert _nivel_directory("nacional") == "Nacional"

    def test_state_name_returned(self):
        assert _nivel_directory("Jalisco") == "Jalisco"

    def test_spaces_replaced_with_underscore(self):
        assert _nivel_directory("Baja California") == "Baja_California"

    def test_slash_replaced_with_dash(self):
        assert _nivel_directory("Sur/Sureste") == "Sur-Sureste"


# ── _build_csv_path ──────────────────────────────────────────────────────────


class TestBuildCsvPath:
    @pytest.fixture(autouse=True)
    def _set_modelo_activo(self):
        with patch.object(fp_mod, "conf", {"modelo_activo": "prophet"}):
            yield

    def test_nacional_path(self, tmp_path):
        result = _build_csv_path("Depresión", "", "hombres", tmp_path)
        assert result == tmp_path / "Depresion" / "Prophet_Depresion_hombres.csv"

    def test_nacional_explicit(self, tmp_path):
        result = _build_csv_path("Depresión", "Nacional", "mujeres", tmp_path)
        assert result == tmp_path / "Depresion" / "Prophet_Depresion_mujeres.csv"

    def test_state_path(self, tmp_path):
        result = _build_csv_path("Parkinson", "Jalisco", "hombres", tmp_path)
        assert result == tmp_path / "Parkinson" / "Prophet_Parkinson_Jalisco_hombres.csv"

    def test_state_with_spaces(self, tmp_path):
        result = _build_csv_path("Alzheimer", "Baja California", "mujeres", tmp_path)
        assert result == tmp_path / "Alzheimer" / "Prophet_Alzheimer_Baja_California_mujeres.csv"

    def test_region_path(self, tmp_path):
        result = _build_csv_path("Depresión", "Region Norte", "hombres", tmp_path)
        assert result == tmp_path / "Depresion" / "Prophet_Depresion_region_Norte_hombres.csv"

    def test_region_with_accent(self, tmp_path):
        result = _build_csv_path("Depresión", "Region Sur/Sureste", "mujeres", tmp_path)
        assert (
            result == tmp_path / "Depresion" / "Prophet_Depresion_region_Sur-Sureste_mujeres.csv"
        )


# ── _load_training_series ────────────────────────────────────────────────────


class TestLoadTrainingSeries:
    @pytest.fixture(autouse=True)
    def _set_modelo_activo(self):
        with patch.object(fp_mod, "conf", {"modelo_activo": "prophet"}):
            yield

    def test_returns_none_when_csv_missing(self, tmp_path):
        with patch.object(fp_mod, "logger"):
            result = _load_training_series("Depresión", "Jalisco", "hombres", tmp_path)
        assert result is None

    def test_loads_y_column(self, tmp_path):
        pad_dir = tmp_path / "Depresion"
        pad_dir.mkdir()
        csv = pad_dir / "Prophet_Depresion_Jalisco_hombres.csv"
        df = pd.DataFrame({"ds": ["2024-01-01", "2024-01-08"], "y": [1.0, 2.0]})
        df.to_csv(csv, index=False)

        with patch.object(fp_mod, "logger"):
            result = _load_training_series("Depresión", "Jalisco", "hombres", tmp_path)

        assert result is not None
        assert list(result.columns) == ["ds", "y"]
        assert len(result) == 2

    def test_renames_y_original_to_y(self, tmp_path):
        pad_dir = tmp_path / "Depresion"
        pad_dir.mkdir()
        csv = pad_dir / "Prophet_Depresion_Jalisco_hombres.csv"
        df = pd.DataFrame(
            {
                "ds": ["2024-01-01", "2024-01-08"],
                "y": [0.5, 0.7],
                "y_original": [10.0, 20.0],
            }
        )
        df.to_csv(csv, index=False)

        with patch.object(fp_mod, "logger"):
            result = _load_training_series("Depresión", "Jalisco", "hombres", tmp_path)

        assert result is not None
        assert list(result.columns) == ["ds", "y"]
        assert result["y"].iloc[0] == 10.0  # uses y_original, not y

    def test_drops_invalid_dates(self, tmp_path):
        pad_dir = tmp_path / "Depresion"
        pad_dir.mkdir()
        csv = pad_dir / "Prophet_Depresion_Jalisco_hombres.csv"
        df = pd.DataFrame({"ds": ["2024-01-01", "not_a_date"], "y": [1.0, 2.0]})
        df.to_csv(csv, index=False)

        with patch.object(fp_mod, "logger"):
            result = _load_training_series("Depresión", "Jalisco", "hombres", tmp_path)

        assert result is not None
        assert len(result) == 1

    def test_nacional_path(self, tmp_path):
        pad_dir = tmp_path / "Depresion"
        pad_dir.mkdir()
        csv = pad_dir / "Prophet_Depresion_hombres.csv"
        df = pd.DataFrame({"ds": ["2024-01-01"], "y": [1.0]})
        df.to_csv(csv, index=False)

        with patch.object(fp_mod, "logger"):
            result = _load_training_series("Depresión", "", "hombres", tmp_path)

        assert result is not None


# ── _load_hp_data ────────────────────────────────────────────────────────────


class TestLoadHpData:
    def test_empty_dir_returns_empty_df(self, tmp_path):
        result = _load_hp_data(tmp_path)
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_loads_completo_csv(self, tmp_path):
        csv = tmp_path / "Depresion_completo.csv"
        df = pd.DataFrame(
            {
                "archivo_modelo": ["model_a.pkl", "model_b.pkl"],
                "seasonality_mode": ["additive", "multiplicative"],
                "changepoint_prior_scale": [0.05, 0.1],
                "seasonality_prior_scale": [0.1, 0.2],
            }
        )
        df.to_csv(csv, index=False)

        result = _load_hp_data(tmp_path)
        assert len(result) == 2
        assert result.index.name == "archivo_modelo"

    def test_deduplicates_by_archivo_modelo(self, tmp_path):
        csv = tmp_path / "dup_completo.csv"
        df = pd.DataFrame(
            {
                "archivo_modelo": ["model.pkl", "model.pkl"],
                "seasonality_mode": ["additive", "multiplicative"],
                "changepoint_prior_scale": [0.05, 0.1],
                "seasonality_prior_scale": [0.1, 0.2],
            }
        )
        df.to_csv(csv, index=False)

        result = _load_hp_data(tmp_path)
        assert len(result) == 1

    def test_skips_csv_with_missing_columns(self, tmp_path):
        csv = tmp_path / "bad_completo.csv"
        pd.DataFrame({"wrong_col": [1]}).to_csv(csv, index=False)

        result = _load_hp_data(tmp_path)
        assert result.empty

    def test_loads_from_nested_dirs(self, tmp_path):
        subdir = tmp_path / "Depresion"
        subdir.mkdir()
        csv = subdir / "Depresion_completo.csv"
        df = pd.DataFrame(
            {
                "archivo_modelo": ["nested.pkl"],
                "seasonality_mode": ["additive"],
                "changepoint_prior_scale": [0.05],
                "seasonality_prior_scale": [0.1],
            }
        )
        df.to_csv(csv, index=False)

        result = _load_hp_data(tmp_path)
        assert len(result) == 1

    def test_merges_multiple_completo_csvs(self, tmp_path):
        for name, modelo in [("a_completo.csv", "m1.pkl"), ("b_completo.csv", "m2.pkl")]:
            df = pd.DataFrame(
                {
                    "archivo_modelo": [modelo],
                    "seasonality_mode": ["additive"],
                    "changepoint_prior_scale": [0.05],
                    "seasonality_prior_scale": [0.1],
                }
            )
            df.to_csv(tmp_path / name, index=False)

        result = _load_hp_data(tmp_path)
        assert len(result) == 2


# ── _extract_metricas ────────────────────────────────────────────────────────


class TestExtractMetricas:
    def _make_forecast_df(
        self,
        mase=0.75,
        rmse=0.12,
        confianza="normal",
        archivo_orig="model_orig.pkl",
        archivo_usado="model_orig.pkl",
    ):
        return pd.DataFrame(
            {
                "meta_padecimiento": ["Depresión"],
                "meta_entidad": ["Jalisco"],
                "meta_modo": ["hombres"],
                "mase_usado": [mase],
                "rmse_usado": [rmse],
                "confianza_original": [confianza],
                "archivo_modelo_original": [archivo_orig],
                "archivo_modelo_usado": [archivo_usado],
            }
        )

    def test_returns_dict(self):
        df = self._make_forecast_df()
        mask = pd.Series([True])
        result = _extract_metricas(df, mask, pd.DataFrame())
        assert isinstance(result, dict)

    def test_mase_extracted(self):
        df = self._make_forecast_df(mase=0.75)
        result = _extract_metricas(df, pd.Series([True]), pd.DataFrame())
        assert abs(result["mase"] - 0.75) < 1e-9

    def test_rmse_extracted(self):
        df = self._make_forecast_df(rmse=0.12)
        result = _extract_metricas(df, pd.Series([True]), pd.DataFrame())
        assert abs(result["rmse"] - 0.12) < 1e-9

    def test_not_fallback_when_same_model(self):
        df = self._make_forecast_df(archivo_orig="m.pkl", archivo_usado="m.pkl")
        result = _extract_metricas(df, pd.Series([True]), pd.DataFrame())
        assert result["es_fallback"] is False

    def test_is_fallback_when_different_model(self):
        df = self._make_forecast_df(archivo_orig="orig.pkl", archivo_usado="regional.pkl")
        result = _extract_metricas(df, pd.Series([True]), pd.DataFrame())
        assert result["es_fallback"] is True

    def test_nan_mase_returns_none(self):
        df = self._make_forecast_df(mase=None)
        result = _extract_metricas(df, pd.Series([True]), pd.DataFrame())
        assert result["mase"] is None

    def test_nan_rmse_returns_none(self):
        df = self._make_forecast_df(rmse=None)
        result = _extract_metricas(df, pd.Series([True]), pd.DataFrame())
        assert result["rmse"] is None

    def test_hp_from_df_hp_all(self):
        df = self._make_forecast_df(archivo_usado="model.pkl")
        df_hp = pd.DataFrame(
            {
                "archivo_modelo": ["model.pkl"],
                "seasonality_mode": ["multiplicative"],
                "changepoint_prior_scale": [0.03],
                "seasonality_prior_scale": [0.1],
            }
        ).set_index("archivo_modelo")
        result = _extract_metricas(df, pd.Series([True]), df_hp)
        assert result["seasonality_mode"] == "multiplicative"
        assert abs(result["changepoint_prior_scale"] - 0.03) < 1e-9

    def test_confianza_default_normal(self):
        df = self._make_forecast_df(confianza="normal")
        result = _extract_metricas(df, pd.Series([True]), pd.DataFrame())
        assert result["confianza"] == "normal"

    def test_required_keys_present(self):
        df = self._make_forecast_df()
        result = _extract_metricas(df, pd.Series([True]), pd.DataFrame())
        for key in ("mase", "rmse", "confianza", "es_fallback", "modelo_usado"):
            assert key in result

    def test_nan_confianza_defaults_to_normal(self):
        df = self._make_forecast_df(confianza=None)
        result = _extract_metricas(df, pd.Series([True]), pd.DataFrame())
        assert result["confianza"] == "normal"

    def test_hp_not_added_when_model_not_in_hp(self):
        df = self._make_forecast_df(archivo_usado="missing.pkl")
        df_hp = pd.DataFrame(
            {
                "archivo_modelo": ["other.pkl"],
                "seasonality_mode": ["additive"],
                "changepoint_prior_scale": [0.05],
                "seasonality_prior_scale": [0.1],
            }
        ).set_index("archivo_modelo")
        result = _extract_metricas(df, pd.Series([True]), df_hp)
        assert "seasonality_mode" not in result


# ── generar_graficos_pronostico ──────────────────────────────────────────────


class TestGenerarGraficosPronostico:
    """Smoke tests for the orchestrator with mocked I/O."""

    def _make_forecast_csv(self, tmp_path):
        """Create a minimal all_forecast.csv."""
        return pd.DataFrame(
            {
                "ds": ["2024-01-01", "2024-01-08"],
                "yhat": [1.0, 1.5],
                "yhat_lower": [0.8, 1.2],
                "yhat_upper": [1.2, 1.8],
                "meta_padecimiento": ["Depresion"] * 2,
                "meta_entidad": ["Jalisco"] * 2,
                "meta_modo": ["hombres"] * 2,
                "mase_usado": [0.75] * 2,
                "rmse_usado": [0.12] * 2,
                "confianza_original": ["normal"] * 2,
                "archivo_modelo_original": ["m.pkl"] * 2,
                "archivo_modelo_usado": ["m.pkl"] * 2,
            }
        )

    def _make_training_csv(self, path):
        """Write a training CSV at the given path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "ds": ["2023-01-01", "2023-06-01", "2023-12-01"],
                "y": [5.0, 6.0, 7.0],
            }
        ).to_csv(path, index=False)

    def test_generates_chart_for_single_model(self, tmp_path):
        forecast_file = tmp_path / "forecast.csv"
        models_root = tmp_path / "models"
        forecast_root = tmp_path / "output"

        self._make_forecast_csv(tmp_path).to_csv(forecast_file, index=False)
        self._make_training_csv(
            models_root / "Depresion" / "Prophet_Depresion_Jalisco_hombres.csv"
        )

        mock_conf = {
            "data": {"forecast": str(forecast_file)},
            "paths": {"models": str(models_root), "forecast": str(forecast_root)},
        }
        mock_graficos = MagicMock()
        mock_graficos.graficar_pronostico.return_value = str(forecast_root / "chart.png")

        with (
            patch.object(fp_mod, "conf", mock_conf),
            patch.object(fp_mod, "logger"),
            patch.object(fp_mod, "GraficosHelper", return_value=mock_graficos),
            patch.object(fp_mod, "directory_manager"),
        ):
            generar_graficos_pronostico()

        mock_graficos.graficar_pronostico.assert_called_once()
        call_kwargs = mock_graficos.graficar_pronostico.call_args
        assert "Depresion" in call_kwargs.kwargs.get("titulo", call_kwargs[1].get("titulo", ""))

    def test_skips_model_when_training_csv_missing(self, tmp_path):
        forecast_file = tmp_path / "forecast.csv"
        models_root = tmp_path / "models"
        models_root.mkdir()
        forecast_root = tmp_path / "output"

        self._make_forecast_csv(tmp_path).to_csv(forecast_file, index=False)

        mock_conf = {
            "data": {"forecast": str(forecast_file)},
            "paths": {"models": str(models_root), "forecast": str(forecast_root)},
        }
        mock_graficos = MagicMock()

        with (
            patch.object(fp_mod, "conf", mock_conf),
            patch.object(fp_mod, "logger"),
            patch.object(fp_mod, "GraficosHelper", return_value=mock_graficos),
            patch.object(fp_mod, "directory_manager"),
        ):
            generar_graficos_pronostico()

        mock_graficos.graficar_pronostico.assert_not_called()

    def test_drops_invalid_dates_from_forecast(self, tmp_path):
        forecast_file = tmp_path / "forecast.csv"
        models_root = tmp_path / "models"
        forecast_root = tmp_path / "output"

        df = self._make_forecast_csv(tmp_path)
        # Add a row with invalid date
        bad_row = df.iloc[[0]].copy()
        bad_row["ds"] = "not_a_date"
        df = pd.concat([df, bad_row], ignore_index=True)
        df.to_csv(forecast_file, index=False)
        self._make_training_csv(
            models_root / "Depresion" / "Prophet_Depresion_Jalisco_hombres.csv"
        )

        mock_conf = {
            "data": {"forecast": str(forecast_file)},
            "paths": {"models": str(models_root), "forecast": str(forecast_root)},
        }
        mock_graficos = MagicMock()
        mock_graficos.graficar_pronostico.return_value = "chart.png"

        with (
            patch.object(fp_mod, "conf", mock_conf),
            patch.object(fp_mod, "logger"),
            patch.object(fp_mod, "GraficosHelper", return_value=mock_graficos),
            patch.object(fp_mod, "directory_manager"),
        ):
            generar_graficos_pronostico()

        # Should still generate chart (bad date dropped)
        mock_graficos.graficar_pronostico.assert_called_once()

    def test_handles_nacional_entidad(self, tmp_path):
        forecast_file = tmp_path / "forecast.csv"
        models_root = tmp_path / "models"
        forecast_root = tmp_path / "output"

        df = self._make_forecast_csv(tmp_path)
        df["meta_entidad"] = pd.NA  # Nacional
        df.to_csv(forecast_file, index=False)
        self._make_training_csv(models_root / "Depresion" / "Prophet_Depresion_hombres.csv")

        mock_conf = {
            "data": {"forecast": str(forecast_file)},
            "paths": {"models": str(models_root), "forecast": str(forecast_root)},
        }
        mock_graficos = MagicMock()
        mock_graficos.graficar_pronostico.return_value = "chart.png"

        with (
            patch.object(fp_mod, "conf", mock_conf),
            patch.object(fp_mod, "logger"),
            patch.object(fp_mod, "GraficosHelper", return_value=mock_graficos),
            patch.object(fp_mod, "directory_manager"),
        ):
            generar_graficos_pronostico()

        call_kwargs = mock_graficos.graficar_pronostico.call_args
        titulo = call_kwargs.kwargs.get("titulo", call_kwargs[1].get("titulo", ""))
        assert "Nacional" in titulo
