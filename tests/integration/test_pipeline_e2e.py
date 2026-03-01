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
    monkeypatch.setitem(conf["data"], "forecast", str(tmp_path / "forecast.csv"))
    monkeypatch.setitem(conf["data"], "tableau", str(tmp_path / "tableau.csv"))
    monkeypatch.setitem(conf["paths"], "models", str(tmp_path / "models"))

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

    # 3. Build Tableau
    build_tableau.main()

    tableau_file = Path(conf["data"]["tableau"])
    assert tableau_file.exists(), "No se generó el archivo de Tableau"

    df_tableau = pd.read_csv(tableau_file)
    assert not df_tableau.empty, "El dataset de Tableau está vacío"

    expected_cols = ["ds", "entidad", "padecimiento", "yhat_prophet", "incrementos_total"]
    for col in expected_cols:
        assert col in df_tableau.columns, f"Falta la columna esperada: {col}"

    # Validate successful run
    assert len(df_tableau) > 0, "Deberían haber filas en el resultado"
