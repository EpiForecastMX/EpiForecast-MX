# CLAUDE.md: Guia de Desarrollo EpiForecast-MX

## Resumen del Proyecto

**EpiForecast-MX** es una plataforma de inteligencia epidemiologica multi-modelo para el **IMSS**. Pronostica la incidencia semanal de Depresion (F32), Parkinson (G20) y Alzheimer (G30) en las 32 entidades federativas de Mexico con un horizonte de 52 semanas. Utiliza **Prophet** y **DeepAR** (GluonTS + PyTorch) como motores de pronostico.

## Comandos de Ejecucion (Makefile)

### Pipeline de Datos
- `make preprocess`: Ejecuta todo el flujo de limpieza y mapeo INEGI (secuencial).
- `make get-dataset`: Descarga el dataset RAW (SINAVE).
- `make filter ARGS="padecimiento.tipo='Depresion'"`: Filtra por padecimiento.
- `make clean`: Limpieza de nulos, duplicados y formato.
- `make transform`: Feature engineering (outliers, regiones, agrupacion).
- `make get-inegi`: Descarga datos demograficos INEGI.
- `make mapper`: Mapea entidades con INEGI.

### Entrenamiento y Modelado (Multi-Modelo)
- `make train`: Entrena segun el `modelo_activo` en `config/base.yaml`.
- `make train-prophet`: Fuerza entrenamiento con Prophet (CPU, paralelo con joblib).
- `make train-deepar`: Fuerza entrenamiento con DeepAR (local, CPU/MPS).
- `make train-all`: Entrena ambos modelos secuencialmente.
- `make train-sagemaker`: Build imagen Docker + lanzar entrenamiento DeepAR en AWS SageMaker (GPU).
- `make train-sagemaker-build`: Solo build + push imagen Docker a ECR.
- `make train-sagemaker-local`: Build imagen + test local con Docker.

### Prediccion y Comparacion
- `make predict ARGS="modelo_activo='deepar'"`: Genera pronosticos para un modelo especifico.
- `make compare`: Genera graficos de alta calidad comparando Real vs Prophet vs DeepAR.
- `make compare-metrics`: Genera comparativa de metricas (Excel).
- `make report`: Genera reporte HTML de resultados.
- `make bitacora`: Genera bitacora HTML del modelado Prophet v1-v6.

### Calidad y Pruebas
- `make quality`: Ejecuta lint (Ruff), typecheck (Mypy) y tests (Pytest).
- `make format`: Formatea el codigo automaticamente con Ruff.
- `make test-fast`: Ejecuta solo pruebas unitarias rapidas (sin slow/integration).
- `make lint`: Verifica formato y calidad sin modificar.
- `make typecheck`: Type check con mypy.

### DVC y Datos
- `make data-pull`: Descarga datos desde S3 via DVC.
- `make data-push`: Sube datos a S3 via DVC.
- `make models-push`: Versiona modelos y sube a S3.
- `make s3-sync`: Sync CSVs directo a S3 (sin DVC, acceso rapido).

## Arquitectura y Estandares

### Patron Factory (SOLID)
- Los modelos heredan de `epiforecast.models.base.ForecastModel`.
- Interfaz: `fit()`, `predict()`, `cross_validate()`, `save()`, `load()`, `get_params()`, `run()`.
- Se registran mediante el decorador `@register_model("nombre")`.
- Se instancian via `epiforecast.models.factory.create_model(name, **kwargs)`.
- Implementaciones: `ProphetForecaster` (Prophet), `DeepARForecaster` (GluonTS + PyTorch).
- No importar clases de modelos directamente en scripts; siempre usar `create_model`.

### Configuracion Dinamica
- `config/base.yaml`: Controla `modelo_activo`, padecimiento, rutas y opciones globales.
- `config/models/prophet.yaml`: Hiperparametros Prophet, grid de CV, estacionalidad, cambios de regimen.
- `config/models/deepar.yaml`: Hiperparametros DeepAR (epochs, capas, dropout, etc.).
- `config/data/preprocessing.yaml`: Parametros de preprocesamiento.
- `config/visualization/plots.yaml`: Estilos de graficos.
- `config/infrastructure/logging.yaml`: Configuracion de loguru.
- Las rutas en `config/base.yaml` usan interpolacion OmegaConf: `./models/${modelo_activo}`.
- Overrides CLI: `python -m scripts.entrena modelo_activo='deepar' padecimiento.tipo='Alzheimer'`.
- La config se carga via `from epiforecast.utils.config import conf, logger`.

### Entrenamiento SageMaker (DeepAR con GPU)
- Imagen Docker: `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime` (NVIDIA T4 en `ml.g4dn.xlarge`).
- Entry point: `scripts/entrena_sagemaker.py` — detecta entorno, copia datos, fuerza `modelo_activo=deepar`.
- Launcher: `aws/sagemaker_launcher.py` — build ECR, lanzar job, test local.
- Cuenta AWS: `564141855321`, bucket `s3://epiforecast-mx-data`, region `us-east-1`.
- Dependencias del container: `aws/requirements_sagemaker.txt` (sin DVC, sin dev tools).
- Flujo: `make train-sagemaker` → build + push ECR + lanzar job → descargar modelos con `aws s3 sync`.

### Estructura del Proyecto
```
EpiForecast-MX/
├── aws/                          # Infraestructura SageMaker (Dockerfile, launcher)
├── config/                       # Configuracion YAML unificada
│   ├── base.yaml                 #   Modelo activo, rutas, padecimiento
│   ├── models/                   #   Hiperparametros por algoritmo
│   ├── data/                     #   Preprocesamiento
│   ├── visualization/            #   Estilos de graficos
│   └── infrastructure/           #   Logging
├── src/epiforecast/              # Paquete Python principal
│   ├── models/                   #   Factory + Prophet + DeepAR + base
│   ├── data/                     #   Extraccion PDF, ingestion INEGI, preprocesamiento
│   ├── evaluation/               #   Metricas (RMSE, MAE, MAPE, SMAPE, MASE)
│   ├── visualization/            #   Graficos estilo IMSS
│   ├── features/                 #   Feature engineering demografico
│   ├── utils/                    #   Config, paths, helpers
│   └── pipelines/                #   Pipeline base
├── scripts/                      # Entry points CLI
├── tests/                        #   unit/ + integration/ (~43 archivos)
├── data/                         # raw/ → interim/ → processed/ (DVC)
├── models/                       # Artefactos .pkl (DVC)
├── reports/                      # Graficos, reportes HTML, forecasts
└── Makefile                      # Orquestacion MLOps
```

### Visualizacion
- Los graficos comparativos se guardan en `reports/forecasts/comparacion_modelos/`.
- Usan la zona horaria `America/Mexico_City` (UTC-6) para las marcas de tiempo.
- Estilo: Historial Real (Gris grueso), Prophet (Teal #004d40 dash-dot), DeepAR (Vino #880e4f dashed).
- Todos los reportes siguen la paleta IMSS 2026.

### Convenciones de Codigo
- **Imports**: Agrupar stdlib, luego terceros, luego locales (isort via Ruff).
- **Tipado**: Uso estricto de `mypy`. Retornos de funciones deben estar tipados.
- **Logging**: Usar `loguru.logger` para trazas de depuracion y errores.
- **Lint**: Ruff con line-length=99, target Python 3.12.
- **Tests**: Pytest con marcadores `slow` e `integration`. Coverage minimo 80%.
- **Pre-commit**: Ruff check + format, mypy, trailing whitespace, YAML/TOML check.

### Dependencias Clave
- **Core**: pandas, numpy, omegaconf, loguru, scikit-learn, rich, pydantic.
- **Prophet**: prophet, cmdstanpy.
- **DeepAR**: gluonts[torch], torch (PyTorch).
- **Visualizacion**: matplotlib, seaborn, plotly, kaleido.
- **Datos**: camelot-py, pypdf, reportlab, openpyxl.
- **Infraestructura**: boto3, sagemaker (opcional), dvc[s3] (opcional).
- **Dev**: pytest, ruff, mypy, pre-commit.
- Instalar: `pip install -e ".[dev]"`. DVC opcional: `pip install -e ".[dvc]"`.
