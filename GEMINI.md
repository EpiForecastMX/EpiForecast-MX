# GEMINI.md: Contexto de EpiForecast-MX

Este archivo actua como guia y contexto permanente para el agente Gemini CLI.

## 1. Proposito y Alcance

**EpiForecast-MX** es una plataforma de inteligencia epidemiologica multi-modelo para el **IMSS**. Pronostica la incidencia semanal de Depresion (F32), Parkinson (G20) y Alzheimer (G30) en las 32 entidades federativas de Mexico con un horizonte de 52 semanas. Utiliza 5 motores de pronostico: **Prophet**, **DeepAR**, **Ensemble** (Prophet + XGBoost), **Stacking** (Prophet + ETS + LightGBM + Ridge) y **NBGLM** (Negative-Binomial GLM + Fourier + regresor El Nino/ONI, usado para Dengue). Cada motor neuro genera 333 artefactos .pkl.

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
- **NBGLMForecaster** (`src/epiforecast/models/nbglm/model.py`): Negative-Binomial GLM con estacionalidad de Fourier, lags y regresor El Nino/ONI (`src/epiforecast/data/enso.py`). Count-correcto, deterministico, extrapola sin divergencia. Es el motor productivo de Dengue (junto con DeepAR y Prophet) y el mejor en backtest leave-one-epidemic-out. No se usa en la cohorte neuro.
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
6. **Prediccion completa**: `make predict-all` (4 modelos secuencialmente: Prophet, DeepAR, Ensemble, Stacking).
7. **Tableau**: `make tableau` (seleccion SMAPE del modelo productivo + metricas por modelo).
8. **Comparacion**: `make compare` (graficos Real vs 4 modelos), `make compare-metrics` (Excel + HTML con badges Overfitting/Leakage).
9. **Tabla de produccion**: `make tabla-produccion` (333 modelos, validacion semanal, graficos embebidos).
10. **Reporte Avance 5**: `make reporte-avance5` (Markdown + 18 graficos + CSV de 333 modelos de produccion).
11. **Patch metricas train**: `python -m scripts.patch_train_metrics` (parchea CSVs existentes con rmse_train/smape_train sin re-entrenar).
12. **Pipeline compuesto**: `make model-pipeline` (train -> models-push -> predict -> report -> forecast-push).

### Aislamiento de outputs
Los artefactos se guardan en subcarpetas dinamicas basadas en el `modelo_activo`:
- Modelos: `models/prophet/`, `models/deepar/`, `models/ensemble/`, `models/stacking/`
- Forecasts: `reports/forecasts/prophet/`, `reports/forecasts/deepar/`, `reports/forecasts/ensemble/`, `reports/forecasts/stacking/`
- Comparacion: `reports/forecasts/comparacion_modelos/`
- Produccion: `reports/ProdDetails/`

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
| `config/features/feature_engineering.yaml` | Parametros de feature engineering |
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

## 6. Consola Interactiva EPI

La consola EPI (`python epi.py`) es un CLI interactivo con Rich TUI y tema IMSS 2026:

### Arquitectura
- **Entry point**: `epi.py` — REPL loop principal.
- **Flujo**: entrada → `normalize_typos()` → `classify_intent()` → router a handler o `engine.translate()`.
- **Intent classifier** (`epi_modules/intent.py`): 17+ intents (saludo, salir, chat, datos, modelos, pronostico, scripts, ayuda, targets, stats, logs, pipeline, salud, historial, dashboard, banner, limpiar).
- **Typo correction**: 50+ mapeos de errores comunes en espanol.
- **Fuzzy matching**: Sugiere el comando mas cercano por distancia Levenshtein.

### Modulos de funcionalidad (`epi_modules/features/`)
| Modulo | Funcion |
|--------|---------|
| `ai_chat.py` | Chat con KnowledgeBase local + Gemini fallback con historial conversacional |
| `dashboard.py` | Dashboard multi-panel (datos, modelos, forecasts, sesion, salud) |
| `data_cache.py` | Cache lazy-loading del boletin, tableau, produccion, configs |
| `data_explorer.py` | Navegador del boletin con filtros y barras Unicode |
| `forecast_viewer.py` | Sparklines de pronosticos a 52 semanas por modelo |
| `knowledge_base.py` | Base de conocimiento local: metricas, boletin, modelos, equipo, semanas epi |
| `model_browser.py` | Tabla paginada de 333 modelos con SMAPE color-coded y badges |

### Modulos de presentacion (`epi_modules/views/`)
| Modulo | Funcion |
|--------|---------|
| `approval.py` | Gate de confirmacion con clasificacion de riesgo (safe/modify/destructive) |
| `banner.py` | Banner ASCII de bienvenida con logo EpiForecast |
| `common.py` | Logs, pipeline status, session stats, scripts listing, historial |
| `health.py` | Dashboard de salud del sistema (Python, venv, deps, configs, datos) |
| `help_menu.py` | Menu de ayuda multi-seccion |
| `targets.py` | Navegador de targets Makefile con categorias de riesgo |

### Componentes core (`epi_modules/`)
| Modulo | Funcion |
|--------|---------|
| `engine.py` | EpiEngine: parseo Makefile, traduccion Gemini, ejecucion subprocesos, SessionStats |
| `intent.py` | Clasificador de intents, TYPO_MAP, GREETINGS, EXIT_WORDS, fuzzy_suggest |
| `theme.py` | IMSS_THEME (PANTONE verde #006847, dorado #BC955C, guinda #9F2241), RISK_LEVELS |

## 7. Estructura del Proyecto

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
│   ├── features/                 #   Feature engineering
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
├── epi_modules/                  # Consola interactiva EPI (v3.0)
│   ├── engine.py                 #   EpiEngine + SessionStats
│   ├── intent.py                 #   Clasificador de intents + typos + fuzzy
│   ├── theme.py                  #   Tema Rich IMSS 2026
│   ├── features/                 #   7 modulos de funcionalidad
│   └── views/                    #   6 modulos de presentacion
├── scripts/                      # Entry points CLI (~24 scripts)
│   ├── entrena.py                #   Entrenamiento principal
│   ├── entrena_sagemaker.py      #   Entry point SageMaker
│   ├── predice.py                #   Generacion de pronosticos
│   ├── compara_modelos.py        #   Comparacion visual
│   ├── compara_metricas.py       #   Comparacion metricas (Excel + HTML)
│   ├── genera_validacion_semanal.py # Validacion semanal Real vs Forecast
│   ├── genera_tabla_produccion.py#   Tabla 333 modelos de produccion (SMAPE)
│   ├── genera_reporte_avance5.py #   Reporte Avance 5 (Markdown + 18 graficos)
│   ├── compliance_check.py       #   Auditoria de calidad (Cookiecutter + SOLID + MLOps)
│   ├── patch_train_metrics.py    #   Parche metricas train sin re-entrenar
│   ├── scrape_boletines.py       #   Scraper SINAVE (Selenium)
│   ├── ci_process_boletines.py   #   Procesamiento CI/CD de boletines
│   ├── publish_gsheets.py        #   Publicacion a Google Sheets
│   └── ...                       #   Preprocesamiento, reportes, paneles, etc.
├── tests/                        # unit/ + integration/ (~62 archivos, 945 tests, coverage ~79%, gate fail_under=68)
├── data/                         # raw/ -> interim/ -> processed/ (DVC)
├── models/                       # Artefactos .pkl por modelo/padecimiento (DVC, 4x333 modelos)
├── reports/                      # Graficos, reportes HTML/Markdown, forecasts CSV, ProdDetails/
├── .github/workflows/            # CI (quality + tests), scraping, procesamiento, gsheets
├── epi.py                        # Entry point de la consola EPI
├── Makefile                      # Orquestacion MLOps (~55 targets)
└── pyproject.toml                # Dependencias, Ruff, Mypy, Pytest
```

## 8. Estandares de Calidad

- **Lint**: Ruff (line-length=99, Python 3.12, isort, bugbear, simplify, pathlib).
- **SRP**: Maximo 300 lineas por modulo (excepto deepar/model.py por complejidad inherente).
- **Tipado**: mypy estricto. Retornos de funciones deben estar tipados. Usar `.to_numpy()` en vez de `.values` para compatibilidad mypy.
- **Tests**: Pytest con marcadores `slow` e `integration`. Gate de cobertura EJECUTABLE (`fail_under = 68`); cobertura ~79% (suite completa). Actualmente 945 tests en ~62 archivos.
- **Logging**: loguru exclusivamente (`from epiforecast.utils.config import logger`).
- **Imports**: stdlib → terceros → locales (enforced por Ruff isort).
- **Pre-commit**: Ruff check + format, mypy, trailing whitespace, YAML/TOML check.
- **Visualizacion**: Paleta IMSS 2026. Zona horaria CDMX (UTC-6). Alto contraste para diferenciar modelos.
- **Versionado**: Codigo en Git, artefactos pesados (.pkl, .csv) en DVC (S3).
- **CI**: GitHub Actions — lint, format check, typecheck, tests (sin DVC). Scraping y procesamiento diario de boletines.

## 9. Instrucciones Criticas para el Agente

- **Configuracion**: Siempre leer de `config/*.yaml` usando `epiforecast.utils.config`.
- **Polimorfismo**: No importar clases de modelos directamente en scripts; usar `create_model` de la fabrica.
- **Consistencia**: Al anadir modelos, asegurar que implementen la interfaz `ForecastModel` y retornen tanto el historial como el pronostico en `.predict()`.
- **Validacion**: Antes de finalizar tareas, ejecutar `make quality` y verificar la generacion de imagenes en `reports/forecasts/`.
- **Dependencias**: `pip install -e ".[dev]"` para desarrollo. DVC opcional: `pip install -e ".[dvc]"`.
- **SageMaker**: Solo se usa para DeepAR. Prophet y Ensemble corren rapido en CPU local.
- **Ensemble**: Opera sobre conteos absolutos (no tasas). Pipeline: `make train-ensemble` o `make avance5`.
- **Stacking**: Opera sobre conteos absolutos. Pipeline: `make train-stacking`. Config: `config/models/stacking.yaml`.
- **Prediccion**: `make predict-all` genera pronosticos de los 4 modelos secuencialmente. La ficha tecnica al pie de cada grafico detecta automaticamente el modelo real (Prophet, DeepAR, Ensemble, Stacking).
- **Tableau**: `make tableau` genera `data/processed/tableau.csv` con `modelo_productivo` (SMAPE) y metricas por modelo.
- **Reporte Avance 5**: `make reporte-avance5` genera Markdown + 18 graficos + Excel de 333 modelos de produccion (`tabla_333_modelos_produccion.xlsx`).
- **Seleccion del motor productivo (canonico desde 2026-04-30)**: `scripts/reselect_motor_2026.py` re-selecciona motor por SMAPE 2026 real del Boletin SINAVE (>=10 sem, >=10 casos), con MASE como desempate. Series ruidosas (<10 casos) se fuerzan a Ensemble. Series sin realidad reciente (4 regiones) respetan CV anterior. Distribucion productiva actual: Prophet 126, Ensemble 95, DeepAR 78, Stacking 34. Genera `auditoria_motores_2026.xlsx` con motor anterior, motor nuevo, SMAPE de los 4 motores en 2026 y criterio. Pipeline canonico tras boletin nuevo: `make tabla-produccion -> python3 scripts/reselect_motor_2026.py -> python3 scripts/build_tableau.py -> python3 scripts/build_web_knowledge.py -> python3 scripts/genera_validacion_semanal.py -> make compare`.
- **Excel de produccion**: 2 hojas. Hoja 1 (Produccion): ~50 columnas con metricas, diagnosticos (overfitting, leakage), `precision_historica`, `pron_sem_previa`/`realidad_sem_previa` para validar con boletin nuevo, ademas de 9 columnas de auditoria 2026 (`smape_2026_*`, `motor_anterior`, `criterio_seleccion`, etc.). Hoja 2 (Detalle Semanal): 52 semanas de realidad, pronostico y % acierto por semana (163 columnas). Formato IMSS 2026. Graficos embebidos (6 PNGs).
- **Validacion semanal**: `scripts/genera_validacion_semanal.py` genera HTML comparando Real vs Forecast para la semana mas reciente.
- **Predicciones enteras**: Todas las columnas `yhat*` en Tableau y proyecciones en produccion se redondean a enteros (no existen fracciones de caso epidemiologico).
- **Diagnosticos**: Cada `run()` de los 4 modelos computa `rmse_train` y `smape_train` (metricas in-sample). El reporte HTML muestra badges de Overfitting (ratio smape_test/smape_train > 2 = Alto, > 1.3 = Moderado) y Leakage (smape_train < 0.5% = Sospechoso).
- **MLflow**: Integracion opcional (`pip install -e ".[mlflow]"`). Registra automaticamente cada run de entrenamiento en `mlruns/` con metricas (rmse, mae, smape, mase, elapsed_seconds) y parametros. No-op si no esta instalado. Visualizar: `mlflow server --backend-store-uri ./mlruns`.
- **Consola EPI**: `python epi.py` lanza la consola interactiva. No modificar el flujo del REPL sin entender el router de intents en `epi_modules/intent.py`.

## 10. Modulos SRP (archivos extraidos)

Para cumplir con el limite de 300 lineas por modulo (SRP), se extrajeron funciones auxiliares:

| Modulo original | Modulo extraido | Contenido |
|----------------|-----------------|-----------|
| `prophet/model.py` | `prophet/data_prep.py` | `agrupa()`, `crea_train_test()`, `promedio_semanal()`, `eval_rapida()`, `build_holidays()`, `build_seasonality_params()`, `apply_regional_params()` |
| `ensemble/model.py` | `ensemble/helpers.py` | `construir_features_xgb()`, `construir_holidays()`, `preparar_datos_ensemble()`, `generar_predicciones_insample()`, `calcular_metricas_ensemble()`, `calcular_metricas_prophet_base()` |
| `stacking/model.py` | `stacking/experts.py` | `ProphetExpert`, `ETSExpert`, `LGBMExpert` — expertos individuales del stacking |
| `stacking/model.py` | `stacking/meta_learner.py` | `StackingMetaLearner` — Ridge meta-learner con pesos no negativos |
| `visualization/comparison_plots.py` | `visualization/comparison_report.py` | `generar_reporte_html()` + funciones HTML auxiliares |
| `visualization/comparison_report.py` | `visualization/comparison_html.py` | Templates HTML (tablas, badges Overfitting/Leakage, hero, footer) |
| `visualization/comparison_report.py` | `visualization/comparison_css.py` | Estilos CSS (paleta IMSS 2026, badges diagnosticos) |
| `visualization/forecast_chart.py` | `visualization/chart_constants.py` | Constantes de estilo (FIGSIZE, MARGINS, font sizes, alphas) |
| `visualization/forecast_chart.py` | `visualization/chart_renderer.py` | `plot_series()` — renderizado de capas, bandas, COVID, outliers |
| `visualization/forecast_chart.py` | `visualization/chart_annotations.py` | `_anotar_divisores()`, `_anotar_zona_cv()`, `_render_ficha_tecnica()` (deteccion automatica de modelo) |
| — | `visualization/avance5_tables.py` | Carga metricas, merge N-way 4 modelos, generacion Markdown Avance 5 |
| — | `visualization/avance5_charts.py` | 6 builders puros: tendencia, residuales, importancia, barras, boxplots, heatmap |
| — | `utils/mlflow_logger.py` | Wrapper opcional MLflow: `log_training_run()` (no-op sin mlflow) |
