# CLAUDE.md: Guia de Desarrollo EpiForecast-MX

## Resumen del Proyecto

**EpiForecast-MX** es una plataforma de inteligencia epidemiologica multi-modelo para el **IMSS**. Pronostica la incidencia semanal de Depresion (F32), Parkinson (G20) y Alzheimer (G30) en las 32 entidades federativas de Mexico con un horizonte de 52 semanas. Utiliza **Prophet**, **DeepAR** (GluonTS + PyTorch), **Ensemble** (Prophet + XGBoost) y **Stacking** (Prophet + ETS + LightGBM + Ridge) como motores de pronostico. Cada modelo genera 333 artefactos .pkl (3 padecimientos x ~111 combinaciones estado/region/sexo).

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
- `make train-ensemble`: Fuerza entrenamiento con Ensemble (Prophet + XGBoost).
- `make train-stacking`: Fuerza entrenamiento con Stacking (Prophet + ETS + LightGBM + Ridge).
- `make train-all`: Entrena los 4 modelos secuencialmente.
- `make avance5`: Entrena el Ensemble con visualizaciones comparativas para los 3 padecimientos.
- `make avance5 ARGS="padecimiento.tipo='Alzheimer'"`: Ensemble para un solo padecimiento.
- `make train-sagemaker`: Build imagen Docker + lanzar entrenamiento DeepAR en AWS SageMaker (GPU).
- `make train-sagemaker-build`: Solo build + push imagen Docker a ECR.
- `make train-sagemaker-local`: Build imagen + test local con Docker.
- `make train-sagemaker-parallel`: 3 jobs paralelos (1 por padecimiento).
- `make train-sagemaker-fast`: Build + 3 jobs paralelos.

### Prediccion y Comparacion
- `make predict ARGS="modelo_activo='deepar'"`: Genera pronosticos para un modelo especifico.
- `make predict-all`: Genera pronosticos de los 4 modelos secuencialmente (Prophet, DeepAR, Ensemble, Stacking).
- `make tableau`: Construye dataset Tableau con seleccion automatica de modelo productivo (SMAPE).
- `make compare`: Genera graficos de alta calidad comparando Real vs los 4 modelos.
- `make compare-metrics`: Genera comparativa de metricas (Excel + HTML con badges Overfitting/Leakage).
- `make tabla-produccion`: Genera tabla de 333 modelos de produccion (SMAPE, validacion semanal).
- `make report`: Genera reporte HTML de resultados.
- `make bitacora`: Genera bitacora HTML del modelado Prophet v1-v6.
- `make reporte-avance5`: Genera reporte Avance 5 (Markdown + 18 graficos + CSV de 333 modelos de produccion).

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
- `make s3-sync`: Sync CSVs + forecasts directo a S3 (sin DVC, acceso rapido para Tableau/dashboard).
- `make data-weekly`: Agrega y versiona nuevos datos semanales del boletin.

### Pipeline Compuesto
- `make model-pipeline`: Pipeline completo (train -> models-push -> predict -> report -> forecast-push).

## Arquitectura y Estandares

### Patron Factory (SOLID)
- Los modelos heredan de `epiforecast.models.base.ForecastModel`.
- Interfaz: `fit()`, `predict()`, `cross_validate()`, `save()`, `load()`, `get_params()`, `run()`.
- Se registran mediante el decorador `@register_model("nombre")`.
- Se instancian via `epiforecast.models.factory.create_model(name, **kwargs)`.
- Implementaciones: `ProphetForecaster` (Prophet), `DeepARForecaster` (GluonTS + PyTorch), `EnsembleForecaster` (Prophet + XGBoost), `StackingForecaster` (Prophet + ETS + LightGBM + Ridge).
- No importar clases de modelos directamente en scripts; siempre usar `create_model`.

### Configuracion Dinamica
- `config/base.yaml`: Controla `modelo_activo`, padecimiento, rutas y opciones globales.
- `config/models/prophet.yaml`: Hiperparametros Prophet, grid de CV, estacionalidad, cambios de regimen.
- `config/models/deepar.yaml`: Hiperparametros DeepAR (epochs, capas, dropout, etc.).
- `config/models/ensemble.yaml`: Hiperparametros Ensemble (Prophet + XGBoost).
- `config/models/stacking.yaml`: Hiperparametros Stacking (Prophet, ETS, LightGBM, Ridge meta-learner).
- `config/data/preprocessing.yaml`: Parametros de preprocesamiento.
- `config/features/feature_engineering.yaml`: Parametros de feature engineering.
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
│   ├── features/                 #   Feature engineering
│   ├── visualization/            #   Estilos de graficos
│   └── infrastructure/           #   Logging
├── src/epiforecast/              # Paquete Python principal
│   ├── models/                   #   Factory + Prophet + DeepAR + Ensemble + Stacking + base
│   ├── data/                     #   Extraccion PDF, ingestion INEGI, preprocesamiento
│   ├── evaluation/               #   Metricas (RMSE, MAE, MAPE, SMAPE, MASE)
│   ├── visualization/            #   Graficos estilo IMSS
│   ├── features/                 #   Feature engineering demografico
│   ├── utils/                    #   Config, paths, helpers
│   └── pipelines/                #   Pipeline base
├── epi_modules/                  # Consola interactiva EPI
│   ├── engine.py                 #   EpiEngine (Makefile, traduccion Gemini, ejecucion)
│   ├── intent.py                 #   Clasificador de intents, typos, fuzzy matching
│   ├── theme.py                  #   Tema Rich IMSS (PANTONE verde, dorado, guinda)
│   ├── features/                 #   Modulos de funcionalidad
│   │   ├── ai_chat.py            #     Chat con KnowledgeBase local + Gemini fallback
│   │   ├── dashboard.py          #     Dashboard multi-panel Rich Layout
│   │   ├── data_cache.py         #     Cache lazy-loading de datos del proyecto
│   │   ├── data_explorer.py      #     Explorador interactivo del boletin
│   │   ├── forecast_viewer.py    #     Visor de pronosticos con sparklines
│   │   ├── knowledge_base.py     #     Base de conocimiento local (sin IA externa)
│   │   └── model_browser.py      #     Navegador paginado de 333 modelos
│   └── views/                    #   Modulos de presentacion
│       ├── approval.py           #     Gate de aprobacion por nivel de riesgo
│       ├── banner.py             #     Banner ASCII de bienvenida
│       ├── common.py             #     Logs, pipeline, stats, scripts, historial
│       ├── health.py             #     Dashboard de salud del sistema
│       ├── help_menu.py          #     Menu de ayuda multi-seccion
│       └── targets.py            #     Navegador de targets Makefile
├── scripts/                      # Entry points CLI (~24 scripts)
├── tests/                        #   unit/ + integration/ (~46 archivos, 849 tests)
├── data/                         # raw/ → interim/ → processed/ (DVC)
├── models/                       # Artefactos .pkl (DVC, 4x333 = 1332 modelos)
├── reports/                      # Graficos, reportes HTML, forecasts, ProdDetails/
├── epi.py                        # Entry point de la consola interactiva EPI
└── Makefile                      # Orquestacion MLOps (~55 targets)
```

### Consola Interactiva EPI
- Entry point: `python epi.py`. REPL con Rich TUI y tema IMSS 2026.
- Flujo: entrada → `normalize_typos()` → `classify_intent()` → router a handler o `engine.translate()`.
- **Intent classifier** (`epi_modules/intent.py`): 17+ intents (saludo, salir, limpiar, banner, dashboard, chat, datos, modelos, pronostico, scripts, ayuda, targets, stats, logs, pipeline, salud, historial).
- **KnowledgeBase** (`epi_modules/features/knowledge_base.py`): Responde con datos reales del proyecto (metricas, boletin, modelos, equipo, semanas epidemiologicas). 18+ handlers en cadena de prioridad.
- **Chat IA** (`epi_modules/features/ai_chat.py`): KnowledgeBase local primero, Gemini como fallback con contexto enriquecido e historial conversacional.
- **Dashboard** (`epi_modules/features/dashboard.py`): Panel multi-seccion con datos del boletin, inventario de modelos, metricas forecast, stats de sesion.
- **Data explorer** (`epi_modules/features/data_explorer.py`): Navegador del boletin con filtros y barras Unicode.
- **Model browser** (`epi_modules/features/model_browser.py`): Tabla paginada de 333 modelos con SMAPE color-coded y badges diagnosticos.
- **Forecast viewer** (`epi_modules/features/forecast_viewer.py`): Sparklines de pronosticos a 52 semanas.
- **Aprobacion** (`epi_modules/views/approval.py`): Gate de confirmacion con clasificacion de riesgo (safe/modify/destructive).
- **Historial persistente**: Ultimos 100 comandos en `.epi_history.json`.
- **Logging**: `logs/epi.log` con timestamps ISO.

### Visualizacion
- Los graficos comparativos se guardan en `reports/forecasts/comparacion_modelos/`.
- Los graficos del Avance 5 (18 PNGs) se guardan en `reports/figures/ModeloFinal/`.
- Paneles individuales (barras, zoom, produccion) en subcarpetas de `comparacion_modelos/`.
- Usan la zona horaria `America/Mexico_City` (UTC-6) para las marcas de tiempo.
- Estilo: Historial Real (Gris grueso), Prophet (Teal #004d40 dash-dot), DeepAR (Vino #880e4f dashed), Ensemble (Naranja #FF6F00), Stacking (Indigo #1A237E).
- La ficha tecnica al pie de cada grafico forecast muestra el nombre real del modelo (detectado desde `meta_modelo` del CSV).
- Todos los reportes siguen la paleta IMSS 2026.

### Seleccion de Modelo de Produccion
- `scripts/genera_tabla_produccion.py` genera la base inicial de `reports/ProdDetails/tabla_333_modelos_produccion.xlsx` por SMAPE de validacion cruzada.
- **`scripts/reselect_motor_2026.py` (canónico desde 2026-04-30)**: re-selecciona el motor productivo usando SMAPE sobre realidad reciente del Boletin SINAVE 2026.
  - Regla 1: serie con >=10 sem reales 2026 y total >=10 casos -> SMAPE 2026 real es criterio primario; MASE como desempate.
  - Regla 2: serie con >=10 sem pero <10 casos (ruidosa, divisiones cercanas a cero infladas) -> forzar Ensemble como default seguro.
  - Regla 3: serie con <10 sem reales (4 regiones agregadas y huecos puntuales) -> respetar asignacion CV anterior.
  - Genera `reports/ProdDetails/auditoria_motores_2026.xlsx` con auditoria de los 333 combos: motor anterior, motor nuevo, SMAPE de los 4 motores en 2026 real, criterio de seleccion.
  - Distribucion productiva actual (post 2026-04-30, 227 cambios sobre los 333): Prophet 126, Ensemble 95, DeepAR 78, Stacking 34. `motor_ganador` global = Prophet.
- **Hoja 1 (Produccion)**: 333 filas x ~50 columnas. Metricas por modelo, diagnosticos, comparativa historica + 9 columnas de auditoria 2026.
  - `casos_52_semanas_futuro`: suma de yhat del horizonte futuro (entero).
  - `smape_prod/mase_prod/rmse_prod/mae_prod`: metricas CV del modelo seleccionado (recalculadas tras la re-asignacion).
  - `overfitting`: ratio smape_test/smape_train — Alto (>2x), Moderado (>1.3x), OK.
  - `leakage`: smape_train < 0.5% = Sospechoso, else OK.
  - `casos_prev_52_semanas_real / _pronos`: comparativa historica (enteros).
  - `precision_historica`: ratio pronos/real como porcentaje.
  - `pron_sem_previa / realidad_sem_previa`: ultima semana para validar con boletin nuevo.
  - `modelo_produccion`, `tipo_modelo`, `region_asignada` (n/a si propio), `justificacion`.
  - `n_semanas_real_2026`, `total_real_2026`, `smape_2026_{prophet,deepar,ensemble,stacking}`, `smape_real_2026_ganador`, `motor_anterior`, `criterio_seleccion`.
- Series con incidencia cero o baja confianza (<5 casos/52sem) se reasignan al modelo regional.
- Predicciones redondeadas a enteros. Formato Excel con paleta IMSS 2026, filtros y paneles congelados.
- Graficos embebidos: `scripts/excel_produccion_charts.py` genera 6 PNGs con paleta IMSS.
- Formateo: `scripts/excel_produccion_fmt.py` aplica estilos institucionales.
- **Pipeline canonico tras nuevo boletin**: `make tabla-produccion` -> `python3 scripts/reselect_motor_2026.py` -> `python3 scripts/build_tableau.py` -> `python3 scripts/build_web_knowledge.py` -> `python3 scripts/genera_validacion_semanal.py` -> `make compare` (PNGs).

### Validacion Semanal
- `scripts/genera_validacion_semanal.py` genera `reports/ProdDetails/validacion_semanal.html`.
- Compara pronosticos de los 4 modelos vs datos reales del boletin SINAVE mas reciente.
- Desglose por sexo (Nacional y Regional) para cada padecimiento.
- Actualiza columna `realidad_sem_previa` en el Excel de produccion.

### Tableau y Modelo Productivo
- `scripts/build_tableau.py` genera `data/processed/tableau.csv` con datos de los 4 modelos.
- Seleccion automatica de `modelo_productivo` basada en SMAPE por grupo (padecimiento, entidad, modo).
- Columnas: `yhat` (mejor prediccion, entero), `modelo_productivo`, `yhat_{modelo}` (enteros), `{metrica}_{modelo}`, metricas standalone.
- Todas las columnas `yhat*` se redondean a enteros antes de guardar (no existen fracciones de caso).
- Metricas calculadas in-situ desde `y_real` vs `yhat_{modelo}` (no depende de `*_completo.csv`).

### MLflow (Experiment Tracking)
- Integracion opcional: `pip install -e ".[mlflow]"`. No-op si no esta instalado.
- `epiforecast/utils/mlflow_logger.py`: wrapper que registra cada run de entrenamiento (metricas, parametros, tiempo).
- Se invoca automaticamente en `scripts/entrena.py` despues de cada modelo entrenado.
- Runs almacenados en `mlruns/` (local, no requiere servidor). Visualizar con `mlflow server --backend-store-uri ./mlruns`.
- Naming: `{modelo}_{padecimiento}_{entidad}` (ej: `stacking_Depresion_Baja California`).
- Metricas registradas: rmse, mae, mape, smape, mase, elapsed_seconds.

### CI/CD (GitHub Actions)
- `ci.yml`: Quality gate (lint + typecheck + tests). Push a main, PRs, weekly Monday 06:00 UTC.
- `scrape_boletines.yml`: Scraping diario automatizado de boletines SINAVE (Selenium + Chrome).
- `process_boletines.yml`: Procesamiento de PDFs con Camelot, merge al dataset consolidado.
- `gsheets.yml`: Publicacion de datos Tableau a Google Sheets (service account).

### Dengue (4.o padecimiento, en preparacion)
- **Cohorte:** `epiforecast.constants.NEURO_CONDITIONS` = [Depresion, Parkinson, Alzheimer] es la cohorte neurologica de produccion (333 modelos). Dengue se incorpora con pipeline propio. Usar `epiforecast.utils.cohorts.is_neuro(pad)` / `filter_neuro(df)` para distinguir (NO repetir `df.isin(NEURO_CONDITIONS)`). Los flujos neuro (filter modo "General", entrena, reselect_motor_2026, genera_validacion_semanal, build_web_knowledge, build_tableau) filtran a la cohorte neuro; Dengue se entrena solo con `padecimiento.tipo='Dengue'` explicito.
- **Extraccion:** Dengue vive en una tabla aparte del boletin (Cuadro 7.2, 3 severidades A97.0/A97.1/A97.2) que `dengue_extractor.py` agrega en un solo "Dengue". Soporte esquema OMS 2009 (A97.x) con dos layouts segun el año: **producción 2020+** (12 col, "acum. año anterior" por severidad) e **histórico 2018-W27..2019** (10 col, "acum. año anterior" solo en la 1ª severidad, etiquetas M/F; ver `dengue_historico.py`); el branch por año en `extract_dengue_from_pdf` conmuta reshape/validación. Serie resultante: **2018-W27..2026 (~391 sem nacionales)**. El esquema viejo OMS 1997 (A90/A91, 2014→2018-W26) usa otra tabla (por estatus de caso Confirmados/En Estudio, layouts de 2 bloques en 2014-2015 y 3 en 2016-2018H1) y NO se mergea al pipeline de producción (cambia taxonomía y definición). `_SOURCE_CORRECTIONS` corrige erratas de fuente conocidas (Zacatecas 2024-W41).
- **Serie histórica A90/A91 SEPARADA (contexto/EDA, NO entrena):** `dengue_historico_a9091.py` extrae Dengue **confirmado por sexo** del esquema viejo por **posición** (pdfplumber: camelot/extract_table fallan porque el espacio es separador de miles). Agrupa palabras en renglones por hueco vertical y en columnas por banda de x; suma SOLO las columnas con encabezado M/F (confirmados del año en curso, excluye año anterior y "En Estudio"); valida vs el renglón TOTAL impreso. `make dengue-historico-a9091` -> `scripts/extrae_dengue_a9091.py` -> `data/interim/dengue_a90a91_{historico,nacional,manifest}.csv` (gitignored, regenerables; `Padecimiento="Dengue_A90A91"`). Cobertura validada ~226/235 sem 2014-2018H1.
- **Pipeline Dengue (Makefile):** `make dengue-extract` -> `make dengue-merge` (+ dvc add/push del consolidado + commit .dvc) -> `make dengue-prep` (lee del CONSOLIDADO via override `data.raw_data_file`, NO del data_raw.csv neuro) -> `make dengue-train-estatal MODELO=<prophet|deepar|ensemble|stacking>` (los 4) -> `make predict-all ARGS="padecimiento.tipo='Dengue' padecimiento.modelado_hibrido=False"` -> `make dengue-produccion` (selector DeepAR/Prophet) -> `make dengue-web`. O `make dengue-pipeline` (extract+merge+prep). El `Makefile` ya usa `.venv/bin/python` por default (`PYTHON ?=`); ya NO hace falta pasar `PYTHON=.venv/bin/python` (override con `make ... PYTHON=python3` si tu venv ya está activo).
- **Helper de cohorte:** `epiforecast.utils.cohorts.is_count_log_cohort(pad)` (hoy = Dengue) centraliza el literal: la cohorte de conteos-log activa log_transform, desactiva normalizar_tasa, acota con el clamp estacional e invierte el log en predict. Usar este helper, NO `== "Dengue"` repetido.
- **Modelado Dengue (per-cohorte, neuro intacto):** grid `dengue` en `prophet.yaml` (multiplicativo, `changepoint_prior_scale=0.05` FIJO) + `_GRID_KEY_MAP`. SIN holiday COVID, cv_weights uniformes, SIN fallback regional ("si es 0, es 0"). **Prophet Dengue va CON log_transform y SIN normalizar_tasa** (cohort-aware en `prophet/model.py`: `is_neuro(pad) or pad=="Dengue"`): sin log la tendencia multiplicativa colapsa a ~0 al extrapolar, y la tasa/100k comprime la señal en log → ratio yhat/real nacional 0.00 → 1.01 con el fix. La inversión expm1 en predict requiere que `ForecastModelLoader` reciba `padecimiento` (predice.py lo pasa SOLO para Dengue; neuro conserva su path histórico padecimiento=None, byte-idéntico).
- **Producción Dengue = DeepAR + Prophet únicamente** (selector `scripts/produccion_dengue.py`, por serie vía SMAPE 2026 real alineado por semana ISO; distribución DeepAR 53 / Prophet 46, Nacional=Prophet). **Ensemble y Stacking quedan FUERA**: los árboles (XGBoost/LightGBM) no extrapolan la dinámica epidémica a 52 sem (divergen ~33x/99x) y el log1p amplifica el overshoot. Guard `forecast_guards.clamp_seasonal_envelope` (cohort-aware Dengue) los acota a la envolvente estacional histórica (33x/99x→~10x) pero NO se eligen como productivos.
- **Horizonte Dengue: 1 año productivo + proyección 5 años ilustrativa.** El pronóstico preciso es 52 sem (DeepAR no puede más: `past_length=context+lags+pred_length > 390 sem de datos`). La banda de 5 años (`build_dengue_forecast_web.py`, Prophet tendencia plana) es ILUSTRATIVA: con solo 2 ciclos epidémicos (2019, 2024) el ciclo de ~4 años no es aprendible; muestra el patrón estacional esperado, no la magnitud de la próxima epidemia. Web: `dengue_forecast.json` → sección de pronóstico en `dengue.html`.
- **DeepAR Dengue:** bloque `short_series` en `deepar.yaml` (cohort-aware via `is_neuro`): cohortes de menor historia que la neuro usan context_length=104, lags acotados (`max_lag=53`, conserva el lag anual), CV ligera (2x26) y `gap_fill=interpolate` (semanas sin boletin se interpolan; semana real con 0 se conserva en 0). DeepAR usa CUDA (SageMaker) > CPU; MPS (Apple Silicon) queda DESHABILITADO por defecto (ops de muestreo StudentT no implementados en MPS + riesgo de deadlock con procesos concurrentes); forzar con `deepar.allow_mps: true`. NO correr dos entrenamientos DeepAR locales concurrentes.

### Convenciones de Codigo
- **Imports**: Agrupar stdlib, luego terceros, luego locales (isort via Ruff).
- **Tipado**: Uso estricto de `mypy`. Retornos de funciones deben estar tipados.
- **Logging**: Usar `loguru.logger` para trazas de depuracion y errores.
- **Lint**: Ruff con line-length=99, target Python 3.12.
- **SRP**: Maximo 300 lineas por modulo (excepcion: deepar/model.py por complejidad inherente).
- **Tests**: Pytest con marcadores `slow` e `integration`. Coverage minimo 70%. Actualmente 849 tests en ~46 archivos.
- **Pre-commit**: Ruff check + format, mypy, trailing whitespace, YAML/TOML check.

### Dependencias Clave
- **Core**: pandas, numpy, omegaconf, loguru, scikit-learn, rich, pydantic.
- **Prophet**: prophet, cmdstanpy.
- **DeepAR**: gluonts[torch], torch (PyTorch).
- **Visualizacion**: matplotlib, seaborn, plotly, kaleido.
- **Datos**: camelot-py, pypdf, reportlab, openpyxl.
- **Infraestructura**: boto3, sagemaker (opcional), dvc[s3] (opcional), mlflow (opcional).
- **Ensemble**: xgboost.
- **Stacking**: lightgbm, statsmodels.
- **EPI Console**: rich, google-generativeai.
- **Dev**: pytest, ruff, mypy, pre-commit.
- Instalar: `pip install -e ".[dev]"`. DVC opcional: `pip install -e ".[dvc]"`. MLflow opcional: `pip install -e ".[mlflow]"`.

### Scripts Adicionales
- `scripts/compliance_check.py`: Auditoria de calidad (Cookiecutter DS + SOLID + MLOps).
- `scripts/excel_produccion_charts.py`: Graficos embebidos para Excel de produccion (6 PNGs).
- `scripts/excel_produccion_fmt.py`: Formateo IMSS 2026 para workbook de produccion.
- `scripts/genera_paneles_barras_prod.py`: Barras individuales del modelo productivo ganador.
- `scripts/genera_paneles_barras_semana.py`: Paneles de barras semanales (2x2 grids).
- `scripts/genera_paneles_zoom.py`: Paneles con zoom desde 2020.
- `scripts/genera_validacion_semanal.py`: Validacion semanal Real vs Forecast (HTML).
- `scripts/patch_train_metrics.py`: Parche metricas train en CSVs sin re-entrenar.
- `scripts/scrape_boletines.py`: Scraper SINAVE (Selenium).
- `scripts/ci_process_boletines.py`: Procesamiento CI/CD de boletines (Camelot).
- `scripts/publish_gsheets.py`: Publicacion a Google Sheets.

### Modulos SRP (archivos extraidos para cumplir limite de 300 lineas)
- `prophet/data_prep.py`: Funciones de preparacion de datos extraidas de `prophet/model.py`.
- `ensemble/helpers.py`: Feature engineering, preparacion de datos y metricas extraidas de `ensemble/model.py`.
- `stacking/experts.py`: Expertos individuales (ProphetExpert, ETSExpert, LGBMExpert) extraidos de `stacking/model.py`.
- `stacking/meta_learner.py`: Meta-learner Ridge/ElasticNet con pesos no negativos extraido de `stacking/model.py`.
- `visualization/comparison_report.py`: Generacion de reporte HTML extraida de `comparison_plots.py`.
- `visualization/comparison_html.py`: Templates HTML del reporte comparativo (tablas, badges, hero, footer).
- `visualization/comparison_css.py`: Estilos CSS del reporte comparativo (paleta IMSS 2026, badges diagnosticos).
- `visualization/chart_constants.py`: Constantes de estilo (tamaños, margenes, alphas) extraidas de `forecast_chart.py`.
- `visualization/chart_renderer.py`: Renderizado de series (capas, bandas, COVID, outliers) extraido de `forecast_chart.py`.
- `visualization/chart_annotations.py`: Anotaciones (divisores, zona CV, ficha tecnica con deteccion automatica de modelo) extraidas de `forecast_chart.py`.
- `visualization/avance5_tables.py`: Carga de metricas, merge N-way de 4 modelos, generacion de tablas y reporte Markdown del Avance 5.
- `visualization/avance5_charts.py`: 6 builders puros de graficos para el Avance 5 (tendencia, residuales, importancia, barras, boxplots, heatmap).
- `features/demographic.py`: Feature builder demografico extraido para SRP.
- `utils/mlflow_logger.py`: Wrapper opcional de MLflow para tracking de experimentos (no-op sin mlflow).
