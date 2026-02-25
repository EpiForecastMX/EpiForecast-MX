"""Tests for forecast_plots.py — _normalizar_nombre and _extract_metricas."""

import pandas as pd

from epiforecast.visualization.forecast_plots import _extract_metricas, _normalizar_nombre


class TestNormalizarNombre:
    def test_removes_accents(self):
        result = _normalizar_nombre("Depresión")
        assert result == "Depresion"

    def test_replaces_spaces_with_underscore(self):
        result = _normalizar_nombre("Ciudad de México")
        assert result == "Ciudad_de_Mexico"

    def test_replaces_slash_with_dash(self):
        result = _normalizar_nombre("Sur/Sureste")
        assert result == "Sur-Sureste"

    def test_no_change_for_ascii(self):
        result = _normalizar_nombre("Jalisco")
        assert result == "Jalisco"

    def test_handles_mixed_case(self):
        result = _normalizar_nombre("Baja California")
        assert result == "Baja_California"

    def test_multiple_spaces_collapsed(self):
        result = _normalizar_nombre("Norte  Occidente")
        assert result == "Norte_Occidente"

    def test_none_cast_to_string(self):
        # function calls str(s) so None becomes "None"
        result = _normalizar_nombre(None)  # type: ignore[arg-type]
        assert result == "None"

    def test_alzheimer_with_accent(self):
        result = _normalizar_nombre("Álzheimer")
        assert result == "Alzheimer"


class TestExtractMetricas:
    def _make_forecast_df(
        self,
        mase: float | None = 0.75,
        rmse: float | None = 0.12,
        confianza: str = "normal",
        archivo_orig: str = "model_orig.pkl",
        archivo_usado: str = "model_orig.pkl",
    ) -> pd.DataFrame:
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
        mask = pd.Series([True])
        result = _extract_metricas(df, mask, pd.DataFrame())
        assert abs(result["mase"] - 0.75) < 1e-9

    def test_rmse_extracted(self):
        df = self._make_forecast_df(rmse=0.12)
        mask = pd.Series([True])
        result = _extract_metricas(df, mask, pd.DataFrame())
        assert abs(result["rmse"] - 0.12) < 1e-9

    def test_not_fallback_when_same_model(self):
        df = self._make_forecast_df(archivo_orig="model.pkl", archivo_usado="model.pkl")
        mask = pd.Series([True])
        result = _extract_metricas(df, mask, pd.DataFrame())
        assert result["es_fallback"] is False

    def test_is_fallback_when_different_model(self):
        df = self._make_forecast_df(
            archivo_orig="model_orig.pkl", archivo_usado="model_regional.pkl"
        )
        mask = pd.Series([True])
        result = _extract_metricas(df, mask, pd.DataFrame())
        assert result["es_fallback"] is True

    def test_nan_mase_returns_none(self):
        df = self._make_forecast_df(mase=None)
        mask = pd.Series([True])
        result = _extract_metricas(df, mask, pd.DataFrame())
        assert result["mase"] is None

    def test_nan_rmse_returns_none(self):
        df = self._make_forecast_df(rmse=None)
        mask = pd.Series([True])
        result = _extract_metricas(df, mask, pd.DataFrame())
        assert result["rmse"] is None

    def test_hp_from_df_hp_all(self):
        df = self._make_forecast_df(archivo_usado="model.pkl")
        mask = pd.Series([True])
        df_hp = pd.DataFrame(
            {
                "archivo_modelo": ["model.pkl"],
                "seasonality_mode": ["multiplicative"],
                "changepoint_prior_scale": [0.03],
                "seasonality_prior_scale": [0.1],
            }
        ).set_index("archivo_modelo")
        result = _extract_metricas(df, mask, df_hp)
        assert result.get("seasonality_mode") == "multiplicative"
        assert abs(result.get("changepoint_prior_scale", 0) - 0.03) < 1e-9

    def test_confianza_default_normal(self):
        df = self._make_forecast_df(confianza="normal")
        mask = pd.Series([True])
        result = _extract_metricas(df, mask, pd.DataFrame())
        assert result["confianza"] == "normal"

    def test_required_keys_present(self):
        df = self._make_forecast_df()
        mask = pd.Series([True])
        result = _extract_metricas(df, mask, pd.DataFrame())
        for key in ("mase", "rmse", "confianza", "es_fallback", "modelo_usado"):
            assert key in result
