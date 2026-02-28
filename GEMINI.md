# GEMINI.md: Contexto de EpiForecast-MX

Este archivo actua como guia y contexto permanente para el agente Gemini CLI.

## 1. Proposito y Alcance

**EpiForecast-MX** es una plataforma de inteligencia epidemiologica multi-modelo para el **IMSS**. Pronostica la incidencia semanal de Depresion (F32), Parkinson (G20) y Alzheimer (G30) en las 32 entidades federativas de Mexico con un horizonte de 52 semanas.

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
- **ModelFactory** (`src/epiforecast/models/factory.py`): Punto unico de instanciacion via `create_model(name, **kwargs)`. Registra modelos con `@register_model("nombre")`.

**Regla critica**: No importar clases de modelos directamente en scripts; siempre usar `create_model` de la fabrica.

## 3. Flujo de Datos y MLOps

### Pipeline de datos
1. **Extraccion e Ingesta**: Scraper de PDFs del SINAVE (`scripts/scrape_boletines.py`) y API del INEGI (`scripts/descarga_inegi.py`).
2. **Preprocesamiento**: Filtrado por padecimiento, limpieza (nulos, duplicados), feature engineering (outliers, regiones, agrupacion), mapeo INEGI.
3. **Comando**: `make preprocess` (ejecuta todo secuencialmente).

### Pipeline de modelado
1. **Entrenamiento local**: `make train-prophet` (CPU, joblib paralelo), `make train-deepar` (CPU/MPS local).
2. **Entrenamiento GPU**: `make train-sagemaker` (DeepAR en AWS SageMaker, `ml.g4dn.xlarge` con NVIDIA T4 + CUDA 12.4).
3. **Prediccion**: `make predict ARGS="modelo_activo='deepar'"` (52 semanas, desnormalizadas).
4. **Comparacion**: `make compare` (graficos Real vs Prophet vs DeepAR).

### Aislamiento de outputs
Los artefactos se guardan en subcarpetas dinamicas basadas en el `modelo_activo`:
- Modelos: `models/prophet/`, `models/deepar/`
- Forecasts: `reports/forecasts/prophet/`, `reports/forecasts/deepar/`
- Comparacion: `reports/forecasts/comparacion_modelos/`

## 4. Configuracion

Toda la configuracion se lee de YAMLs via OmegaConf. Acceso: `from epiforecast.utils.config import conf, logger`.

| Archivo | Contenido |
|---------|-----------|
| `config/base.yaml` | `modelo_activo`, padecimiento, rutas con interpolacion |
| `config/models/prophet.yaml` | Grid de HP, estacionalidad, periodos atipicos, CV weights |
| `config/models/deepar.yaml` | Epochs, capas, dropout, learning rate, context/prediction length |
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
│   ├── models/                   #   Factory + Prophet + DeepAR + base
│   │   ├── base.py               #     Interfaz abstracta ForecastModel
│   │   ├── factory.py            #     create_model() + @register_model
│   │   ├── prophet/              #     ProphetForecaster + CV + tuner
│   │   ├── deepar/               #     DeepARForecaster + CV
│   │   └── ensemble/             #     (futuro)
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
├── tests/                        # unit/ + integration/ (~43 archivos, coverage 80%+)
├── data/                         # raw/ -> interim/ -> processed/ (DVC)
├── models/                       # Artefactos .pkl por modelo/padecimiento (DVC)
├── reports/                      # Graficos, reportes HTML, forecasts CSV
├── .github/workflows/            # CI (quality + tests), scraping, gsheets
├── Makefile                      # Orquestacion MLOps
└── pyproject.toml                # Dependencias, Ruff, Mypy, Pytest
```

## 7. Estandares de Calidad

- **Lint**: Ruff (line-length=99, Python 3.12, isort, bugbear, simplify, pathlib).
- **Tipado**: mypy estricto. Retornos de funciones deben estar tipados.
- **Tests**: Pytest con marcadores `slow` e `integration`. Coverage minimo 80%.
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
- **SageMaker**: Solo se usa para DeepAR. Prophet corre rapido en CPU local.
