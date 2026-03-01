# GEMINI.md: Contexto de EpiForecast-MX

Este archivo actua como guia y contexto permanente para el agente Gemini CLI.

## 1. Proposito y Alcance

**EpiForecast-MX** es una plataforma de inteligencia epidemiologica multi-modelo para el **IMSS**. Pronostica la incidencia semanal de Depresion (F32), Parkinson (G20) y Alzheimer (G30) en las 32 entidades federativas de Mexico con un horizonte de 52 semanas. Utiliza 4 motores de pronostico: **Prophet**, **DeepAR**, **Ensemble** (Prophet + XGBoost) y **Stacking** (Prophet + ETS + LightGBM + Ridge). Cada modelo genera 333 artefactos .pkl.

| Padecimiento | CIE-10 | Reto |
|--------------|--------|------|
| Depresion | F32 | Alta linea base, estacionalidad, disrupcion COVID |
| Parkinson | G20 | Baja incidencia, series volatiles por estado |
| Alzheimer | G30 | Tendencias de envejecimiento, subregistro |

## 2. Arquitectura Polimorfica (SOLID)

El proyecto utiliza un patron **Factory** para gestionar multiples motores de pronostico:

- **ForecastModel** (`src/epiforecast/models/base.py`): Clase base abstracta. Interfaz: `fit()`, `predict()`, `cross_validate()`, `save()`, `load()`, `get_params()`, `run()`.
- **ProphetForecaster** (`src/epiforecast/models/prophet/model.py`): Meta Prophet con CV ponderado, grid search por padecimiento, periodos atipicos (COVID) y estacionalidad personalizada.
- **DeepARForecaster** (`src/epiforecast/models/deepar/model.py`): GluonTS + PyTorch. Multi-series (32 estados simultaneos), distribucion Student-t, early stopping.
- **EnsembleForecaster** (`src/epiforecast/models/ensemble/model.py`): Prophet base + XGBoost residual. Opera sobre conteos absolutos. Features: lags, rolling means, calendario.
- **StackingForecaster** (`src/epiforecast/models/stacking/model.py`): 3 expertos (Prophet, ETS, LightGBM) + Ridge meta-learner. Pesos optimizados via OOF predictions. Opera sobre conteos absolutos.
  - `stacking/experts.py`: ProphetExpert, ETSExpert (statsmodels), LGBMExpert (lightgbm).
  - `stacking/meta_learner.py`: StackingMetaLearner con Ridge regularizado y pesos no negativos.
- **ModelFactory** (`src/epiforecast/models/factory.py`): Punto unico de instanciacion via `create_model(name, **kwargs)`. Registra modelos con `@register_model("nombre")`.

**Regla critica**: No importar clases de modelos directamente en scripts; siempre usar `create_model` de la fabrica.

## 3. Flujo de Datos y MLOps

### Pipeline de datos
1. **Extraccion e Ingesta**: Scraper de PDFs del SINAVE (`scripts/scrape_boletines.py`) y API del INEGI (`scripts/descarga_inegi.py`).
2. **Preprocesamiento**: Filtrado por padecimiento, limpieza (nulos, duplicados), feature engineering (outliers, regiones, agrupacion), mapeo INEGI.
3. **Comando**: `make preprocess` (ejecuta todo secuencialmente).

### Pipeline de modelado
1. **Entrenamiento local**: `make train-prophet` (CPU, joblib paralelo), `make train-deepar` (CPU/MPS local), `make train-ensemble`, `make train-stacking`.
2. **Entrenamiento GPU**: `make train-sagemaker` (DeepAR en AWS SageMaker, `ml.g4dn.xlarge` con NVIDIA T4 + CUDA 12.4).
3. **Entrenamiento completo**: `make train-all` (4 modelos secuencialmente).
4. **Entrenamiento Ensemble con visualizaciones**: `make avance5` (Prophet + XGBoost, conteos absolutos).
5. **Prediccion**: `make predict ARGS="modelo_activo='deepar'"` (52 semanas, desnormalizadas).
6. **Tableau**: `make tableau` (seleccion SMAPE del modelo productivo + metricas por modelo).
7. **Comparacion**: `make compare` (graficos Real vs 4 modelos), `make compare-metrics` (Excel 4 modelos).

### Aislamiento de outputs
Los artefactos se guardan en subcarpetas dinamicas basadas en el `modelo_activo`:
- Modelos: `models/prophet/`, `models/deepar/`, `models/ensemble/`, `models/stacking/`
- Forecasts: `reports/forecasts/prophet/`, `reports/forecasts/deepar/`, `reports/forecasts/ensemble/`, `reports/forecasts/stacking/`
- Comparacion: `reports/forecasts/comparacion_modelos/`

## 4. Configuracion

Toda la configuracion se lee de YAMLs via OmegaConf. Acceso: `from epiforecast.utils.config import conf, logger`.

| Archivo | Contenido |
|---------|-----------|
| `config/base.yaml` | `modelo_activo`, padecimiento, rutas con interpolacion |
| `config/models/prophet.yaml` | Grid de HP, estacionalidad, periodos atipicos, CV weights |
| `config/models/deepar.yaml` | Epochs, capas, dropout, learning rate, context/prediction length |
| `config/models/ensemble.yaml` | Hiperparametros Ensemble (Prophet + XGBoost) |
| `config/models/stacking.yaml` | Experts (Prophet, ETS, LightGBM), meta-learner Ridge, OOF cutoff |
| `config/data/preprocessing.yaml` | Parametros de limpieza y transformacion |
| `config/visualization/plots.yaml` | Estilos de graficos IMSS |
| `config/infrastructure/logging.yaml` | Sinks de loguru (stderr + file) |

Overrides CLI: `python -m scripts.entrena modelo_activo='deepar' padecimiento.tipo='Alzheimer'`.

## 5. Infraestructura SageMaker

Para entrenamiento DeepAR con GPU en AWS:

- **Imagen Docker**: `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime` con GluonTS, Prophet, sagemaker-training.
- **Entry point**: `scripts/entrena_sagemaker.py` — detecta entorno SageMaker, copia datos, fuerza `modelo_activo=deepar`, invoca pipeline existente, copia modelos a `/opt/ml/model/`.
- **Launcher**: `aws/sagemaker_launcher.py` — build/push a ECR, lanzar Training Job, test local con Docker.
- **Instancia**: `ml.g4dn.xlarge` (NVIDIA T4, CUDA 12.x).
- **Cuenta**: `564141855321`, bucket `s3://epiforecast-mx-data`, region `us-east-1`.

```bash
make train-sagemaker          # Build + lanzar en GPU
make train-sagemaker-build    # Solo build imagen
make train-sagemaker-local    # Test local con Docker
```

## 6. Estructura del Proyecto

```
EpiForecast-MX/
├── aws/                          # Infraestructura SageMaker
│   ├── Dockerfile                #   Imagen Docker (PyTorch + CUDA + GluonTS)
│   ├── requirements_sagemaker.txt#   Deps del container
│   └── sagemaker_launcher.py     #   Orquestador ECR + Training Job
├── config/                       # Configuracion YAML unificada
│   ├── base.yaml                 #   Modelo activo, rutas, padecimiento
│   ├── models/                   #   Hiperparametros por algoritmo
│   ├── data/                     #   Preprocesamiento
│   ├── visualization/            #   Estilos de graficos
│   └── infrastructure/           #   Logging
├── src/epiforecast/              # Paquete Python principal
│   ├── models/                   #   Factory + Prophet + DeepAR + Ensemble + Stacking + base
│   │   ├── base.py               #     Interfaz abstracta ForecastModel
│   │   ├── factory.py            #     create_model() + @register_model
│   │   ├── prophet/              #     ProphetForecaster + CV + tuner + data_prep
│   │   ├── deepar/               #     DeepARForecaster + CV
│   │   ├── ensemble/             #     EnsembleForecaster + helpers
│   │   └── stacking/             #     StackingForecaster + experts + meta_learner
│   ├── data/                     #   Extraccion PDF, ingestion INEGI, preprocesamiento
│   ├── evaluation/               #   Metricas (RMSE, MAE, MAPE, SMAPE, MASE)
│   ├── visualization/            #   Graficos estilo IMSS 2026
│   ├── features/                 #   Feature engineering demografico
│   ├── utils/                    #   Config, paths, helpers
│   └── pipelines/                #   Pipeline base
├── scripts/                      # Entry points CLI (~15 scripts)
│   ├── entrena.py                #   Entrenamiento principal
│   ├── entrena_sagemaker.py      #   Entry point SageMaker
│   ├── predice.py                #   Generacion de pronosticos
│   ├── compara_modelos.py        #   Comparacion visual
│   └── ...                       #   Preprocesamiento, reportes, etc.
├── tests/                        # unit/ + integration/ (~34 archivos, 693 tests, coverage 70%+)
├── data/                         # raw/ -> interim/ -> processed/ (DVC)
├── models/                       # Artefactos .pkl por modelo/padecimiento (DVC, 4x333 modelos)
├── reports/                      # Graficos, reportes HTML, forecasts CSV
├── .github/workflows/            # CI (quality + tests), scraping, gsheets
├── Makefile                      # Orquestacion MLOps
└── pyproject.toml                # Dependencias, Ruff, Mypy, Pytest
```

## 7. Estandares de Calidad

- **Lint**: Ruff (line-length=99, Python 3.12, isort, bugbear, simplify, pathlib).
- **SRP**: Maximo 300 lineas por modulo (excepto deepar/model.py por complejidad inherente).
- **Tipado**: mypy estricto. Retornos de funciones deben estar tipados. Usar `.to_numpy()` en vez de `.values` para compatibilidad mypy.
- **Tests**: Pytest con marcadores `slow` e `integration`. Coverage minimo 70%. Actualmente 693 tests.
- **Logging**: loguru exclusivamente (`from epiforecast.utils.config import logger`).
- **Imports**: stdlib → terceros → locales (enforced por Ruff isort).
- **Pre-commit**: Ruff check + format, mypy, trailing whitespace, YAML/TOML check.
- **Visualizacion**: Paleta IMSS 2026. Zona horaria CDMX (UTC-6). Alto contraste para diferenciar modelos.
- **Versionado**: Codigo en Git, artefactos pesados (.pkl, .csv) en DVC (S3).
- **CI**: GitHub Actions — lint, format check, typecheck, tests (sin DVC).

## 8. Instrucciones Criticas para el Agente

- **Configuracion**: Siempre leer de `config/*.yaml` usando `epiforecast.utils.config`.
- **Polimorfismo**: No importar clases de modelos directamente en scripts; usar `create_model` de la fabrica.
- **Consistencia**: Al anadir modelos, asegurar que implementen la interfaz `ForecastModel` y retornen tanto el historial como el pronostico en `.predict()`.
- **Validacion**: Antes de finalizar tareas, ejecutar `make quality` y verificar la generacion de imagenes en `reports/forecasts/`.
- **Dependencias**: `pip install -e ".[dev]"` para desarrollo. DVC opcional: `pip install -e ".[dvc]"`.
- **SageMaker**: Solo se usa para DeepAR. Prophet y Ensemble corren rapido en CPU local.
- **Ensemble**: Opera sobre conteos absolutos (no tasas). Pipeline: `make train-ensemble` o `make avance5`.
- **Stacking**: Opera sobre conteos absolutos. Pipeline: `make train-stacking`. Config: `config/models/stacking.yaml`.
- **Tableau**: `make tableau` genera `data/processed/tableau.csv` con `modelo_productivo` (SMAPE) y metricas por modelo.

## 9. Modulos SRP (archivos extraidos)

Para cumplir con el limite de 300 lineas por modulo (SRP), se extrajeron funciones auxiliares:

| Modulo original | Modulo extraido | Contenido |
|----------------|-----------------|-----------|
| `prophet/model.py` | `prophet/data_prep.py` | `agrupa()`, `crea_train_test()`, `promedio_semanal()`, `eval_rapida()`, `build_holidays()`, `build_seasonality_params()`, `apply_regional_params()` |
| `ensemble/model.py` | `ensemble/helpers.py` | `construir_features_xgb()`, `construir_holidays()`, `preparar_datos_ensemble()`, `generar_predicciones_insample()`, `calcular_metricas_ensemble()`, `calcular_metricas_prophet_base()` |
| `stacking/model.py` | `stacking/experts.py` | `ProphetExpert`, `ETSExpert`, `LGBMExpert` — expertos individuales del stacking |
| `stacking/model.py` | `stacking/meta_learner.py` | `StackingMetaLearner` — Ridge meta-learner con pesos no negativos |
| `visualization/comparison_plots.py` | `visualization/comparison_report.py` | `generar_reporte_html()` + funciones HTML auxiliares |
| `visualization/forecast_chart.py` | `visualization/chart_constants.py` | Constantes de estilo (FIGSIZE, MARGINS, font sizes, alphas) |
| `visualization/forecast_chart.py` | `visualization/chart_renderer.py` | `plot_series()` — renderizado de capas, bandas, COVID, outliers |
| `visualization/forecast_chart.py` | `visualization/chart_annotations.py` | `_anotar_divisores()`, `_anotar_zona_cv()`, `_render_ficha_tecnica()` |
