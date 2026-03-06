from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scripts import build_tableau, entrena, predice

from epiforecast.utils.config import conf


@pytest.fixture
def mock_conf(tmp_path, monkeypatch):
    """Fixture to override configuration paths to point to a temporary directory."""
    from omegaconf import OmegaConf

    import epiforecast.utils.config as cfg_module

    # Re-build the real configuration because conftest.py mocked it.
    try:
        conf_base = OmegaConf.load("config/base.yaml")
        conf_data = OmegaConf.load("config/data/preprocessing.yaml")
        conf_features = OmegaConf.load("config/features/feature_engineering.yaml")
        conf_models = OmegaConf.load("config/models/prophet.yaml")
        conf_viz = OmegaConf.load("config/visualization/plots.yaml")

        _merged = OmegaConf.merge(conf_base, conf_data, conf_features, conf_models, conf_viz)
        real_conf = OmegaConf.to_container(_merged, resolve=True)

        # Update the module's conf dict in place so that references hold
        cfg_module.conf.clear()
        cfg_module.conf.update(real_conf)
    except Exception as e:
        pytest.skip(f"No se pudieron cargar los YAML reales: {e}")

    # Now we safely monkeypatch the required paths
    monkeypatch.setitem(conf["data"], "data_inegi", str(tmp_path / "data_inegi_General.csv"))
    forecasts_dir = tmp_path / "reports" / "forecasts" / "prophet"
    forecasts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setitem(conf["data"], "forecast", str(forecasts_dir / "all_forecast_prophet.csv"))
    monkeypatch.setitem(conf["data"], "tableau", str(tmp_path / "tableau.csv"))
    monkeypatch.setitem(conf["paths"], "models", str(tmp_path / "models"))
    monkeypatch.setitem(conf["paths"], "reports", str(tmp_path / "reports"))

    # Configure minimal run
    monkeypatch.setitem(conf["padecimiento"], "modelado_estados", True)
    monkeypatch.setitem(conf["padecimiento"], "modelado_hibrido", False)
    monkeypatch.setitem(conf["padecimiento"], "entrena_modelo", True)
    monkeypatch.setitem(conf, "n_jobs_train", 1)
    monkeypatch.setitem(conf["prediccion"], "periodo", 2)
    monkeypatch.setitem(conf, "umbral_minimo_semanal", 0)  # Forzar CV o run

    yield tmp_path

    # Cleanup implicitly handled by monkeypatch for dict items, but tmp_path is deleted automatically


@pytest.fixture
def synthetic_data(mock_conf):
    """Generates synthetic data for the pipeline test. (600 weeks to ensure Prophet CV works)."""
    dates = pd.date_range(start="2010-01-01", periods=600, freq="W-MON")
    n = len(dates)

    df = pd.DataFrame(
        {
            "Padecimiento": ["Alzheimer"] * n,
            "Semana": [(i % 52) + 1 for i in range(n)],
            "Fecha": dates.strftime("%Y-%m-%d"),
            "Entidad": ["Aguascalientes"] * n,
            "incrementos_hombres": np.random.default_rng(42).integers(0, 5, n),
            "incrementos_mujeres": np.random.default_rng(43).integers(0, 5, n),
            "Region": ["Occidente"] * n,
            "incrementos_total": np.random.default_rng(44).integers(0, 10, n),
            "Superficie_km2": [5615.7] * n,
            "Hombres": [696683] * n,
            "Mujeres": [728924] * n,
            "Total": [1425607] * n,
            "region_salud_mental": ["Urbana media"] * n,
            "ratio_h_m": [0.95] * n,
            "ratio_h_m_cat": ["Mayormente mujeres"] * n,
            "tamano_poblacional_predefinido": ["1-3M"] * n,
            "tamano_poblacional_grupo_percentil": ["Población baja"] * n,
            "densidad_poblacion": [253.8] * n,
            "extension_territorial_percentil": ["Territorio pequeño"] * n,
            "densidad_poblacional_percentil": ["Alta"] * n,
        }
    )

    data_path = Path(conf["data"]["data_inegi"])
    data_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(data_path, index=False)

    return df


@pytest.mark.integration
@pytest.mark.slow
def test_pipeline_end_to_end(mock_conf, synthetic_data, monkeypatch):
    """
    Smoke test para el pipeline de MLOps:
    1. Entrena modelos (Prophet)
    2. Genera predicciones
    3. Construye dataset final para Tableau
    """
    # 1. Train
    entrena.main()

    models_dir = Path(conf["paths"]["models"]) / "Alzheimer"
    assert models_dir.exists(), "El directorio de modelos no se creó"
    pkl_files = list(models_dir.glob("*.pkl"))
    assert len(pkl_files) > 0, "No se generaron modelos .pkl"

    # 2. Predict (evitamos generar gráficos reales)
    import epiforecast.visualization.forecast_plots as fp

    monkeypatch.setattr(fp, "generar_graficos_pronostico", lambda: None)

    predice.main()

    forecast_file = Path(conf["data"]["forecast"])
    assert forecast_file.exists(), "No se generó el archivo de predicciones"
    df_forecast = pd.read_csv(forecast_file)
    assert not df_forecast.empty, "El forecast está vacío"

    # 3. Build Tableau (genera tableau_model.xlsx con 5 hojas)
    build_tableau.main()

    tableau_file = Path(conf["data"]["tableau"]).parent / "tableau_model.xlsx"
    assert tableau_file.exists(), "No se generó el archivo de Tableau"

    df_forecast_sheet = pd.read_excel(tableau_file, sheet_name="forecast")
    assert not df_forecast_sheet.empty, "La hoja 'forecast' está vacía"

    expected_cols = ["ds", "entidad", "padecimiento", "meta_modo", "yhat"]
    for col in expected_cols:
        assert col in df_forecast_sheet.columns, f"Falta la columna esperada: {col}"

    # Validate all sheets exist
    sheets = pd.ExcelFile(tableau_file).sheet_names
    for sheet in ["scaffold", "real", "forecast", "metricas", "entidades"]:
        assert sheet in sheets, f"Falta la hoja esperada: {sheet}"


# ── Ensemble / Stacking standalone smoke tests ───────────────────────────────


def _make_synthetic_epi(n_weeks: int = 200) -> pd.DataFrame:
    """Synthetic epidemiological DataFrame for ensemble/stacking tests."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2019-01-07", periods=n_weeks, freq="W-MON")
    return pd.DataFrame(
        {
            "Fecha": dates,
            "Padecimiento": ["Alzheimer"] * n_weeks,
            "Entidad": ["Nacional"] * n_weeks,
            "incrementos_total": rng.integers(5, 30, n_weeks),
        }
    )


@pytest.mark.integration
@pytest.mark.slow
def test_ensemble_train_predict_e2e(tmp_path, monkeypatch):
    """Smoke test: EnsembleForecaster fit + predict + save/load roundtrip."""

    from epiforecast.models import create_model
    import epiforecast.models.ensemble.model as ens_mod

    mock_conf = {
        "padecimiento": {"modelado_estados": False, "entrena_modelo": True},
        "paths": {"models": str(tmp_path / "models")},
        "data": {"model_train": str(tmp_path / "train")},
        "peridos_atipicos": [
            {"holiday": "COVID", "ds": "2020-03-23", "lower_window": 0, "upper_window": 913}
        ],
        "FECHA_CORTE_ENTRENAMIENTO_ENSEMBLE": "2022-06-01",
        "HORIZON_ENSEMBLE": 12,
        "prophet_base": {
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 0.1,
            "seasonality_mode": "additive",
        },
        "xgboost": {"n_estimators": 30, "max_depth": 3, "learning_rate": 0.05},
        "parallel": {
            "alpha": 1.0,
            "oof_folds": 2,
            "oof_cutoff": "2022-06-01",
            "min_train_weeks": 52,
        },
    }

    df = _make_synthetic_epi(200)

    with monkeypatch.context() as m:
        m.setattr(ens_mod, "conf", mock_conf)
        forecaster = create_model(
            "ensemble", df=df, sexo="incrementos_total", padecimiento="Alzheimer"
        )
        result = forecaster.run()
        assert result is not None

        # save + load roundtrip
        pkl_path = tmp_path / "ensemble_test.pkl"
        forecaster.save(pkl_path)
        assert pkl_path.exists()

        loaded = create_model(
            "ensemble", df=df, sexo="incrementos_total", padecimiento="Alzheimer"
        )
        loaded.load(pkl_path)
        params = loaded.get_params()
        assert isinstance(params, dict)


@pytest.mark.integration
@pytest.mark.slow
def test_stacking_train_predict_e2e(tmp_path, monkeypatch):
    """Smoke test: StackingForecaster fit + predict + save/load roundtrip."""

    from epiforecast.models import create_model
    import epiforecast.models.stacking.model as stk_mod

    mock_conf = {
        "padecimiento": {"modelado_estados": False, "entrena_modelo": True},
        "paths": {"models": str(tmp_path / "models")},
        "data": {"model_train": str(tmp_path / "train")},
        "peridos_atipicos": [
            {"holiday": "COVID", "ds": "2020-03-23", "lower_window": 0, "upper_window": 913}
        ],
        "FECHA_CORTE_ENTRENAMIENTO_STACKING": "2022-06-01",
        "HORIZON_STACKING": 12,
        "stacking": {
            "oof_cutoff": "2022-06-01",
            "prophet": {
                "changepoint_prior_scale": 0.05,
                "seasonality_prior_scale": 0.1,
                "seasonality_mode": "additive",
                "yearly_custom": {"period": 365.25, "fourier_order": 6},
            },
            "ets": {"seasonal_periods": 52, "trend": "add", "seasonal": "add"},
            "lgbm": {"n_estimators": 30, "max_depth": 3, "learning_rate": 0.05},
            "meta_learner": {
                "type": "ridge",
                "alpha": 1.0,
                "add_temporal_features": False,
            },
        },
    }

    df = _make_synthetic_epi(200)

    with monkeypatch.context() as m:
        m.setattr(stk_mod, "conf", mock_conf)
        forecaster = create_model(
            "stacking", df=df, sexo="incrementos_total", padecimiento="Alzheimer"
        )
        result = forecaster.run()
        assert result is not None

        # save + load roundtrip
        pkl_path = tmp_path / "stacking_test.pkl"
        forecaster.save(pkl_path)
        assert pkl_path.exists()

        loaded = create_model(
            "stacking", df=df, sexo="incrementos_total", padecimiento="Alzheimer"
        )
        loaded.load(pkl_path)
        assert loaded._weights is not None
