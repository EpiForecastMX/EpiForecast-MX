# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**EpiForecast-MX** es una plataforma de inteligencia epidemiológica desarrollada en colaboración con el **Instituto Mexicano del Seguro Social (IMSS)** como proyecto Capstone de la Maestría en Inteligencia Artificial Aplicada del Tecnológico de Monterrey.

Predice la incidencia semanal de tres padecimientos neurológicos/salud mental:
- **Depresión (CIE-10: F32)**
- **Parkinson (CIE-10: G20)**
- **Alzheimer (CIE-10: G30)**

Utiliza Facebook Prophet para series de tiempo, con datos históricos (2014-2026) del SINAVE e indicadores demográficos del INEGI. Los modelos trabajan con **tasas por 100,000 habitantes** (no conteos absolutos) para normalizar la escala entre estados. Genera proyecciones a nivel **estatal** (32 entidades) o por **región INEGI de salud mental**, segmentadas por sexo.

## Convenciones del Proyecto

- **Idioma de commits:** español (ej. `Feat: implementando imputación por zscore`)
- **Branding IMSS:** paleta cromática institucional definida en `config/reportes.yaml` (`IMSS_COLORS`, `PALETTE_MAIN`, `PALETTE_PADECIMIENTO`, `PALETTE_SEXO`)
- **Tasas:** los indicadores per cápita se expresan por **100,000 habitantes**
- **Entorno virtual:** se llama `integrador/` (no `.venv`); activar con `source integrador/bin/activate`
- **Configuración:** todos los parámetros en YAML (`config/`), cargados via OmegaConf en `src/configuraciones/config_params.py`
- **Logging:** Loguru con dual-sink (consola + archivo rotativo) configurado en `config/logging.yaml`
- **Versionado de datos:** archivos grandes (PDFs, datasets, modelos, forecast) trackeados por DVC en S3 (`s3://epiforecast-mx-data/`)
- **Linter/formatter:** Ruff (line-length 99)

## Estructura de Directorios

```
EpiForecast-MX/
├── .github/workflows/              # Pipelines CI/CD
│   ├── scrape_boletines.yml        #   Scraper diario SINAVE (2 PM CDMX)
│   └── process_boletines.yml       #   Extracción y merge automático
│
├── config/                         # Configuración YAML
│   ├── params.yaml                 #   Parámetros generales y rutas
│   ├── modelado.yaml               #   Hiperparámetros Prophet, CV, periodos atípicos
│   ├── limpieza.yaml               #   Reglas de limpieza (columnas a eliminar, sustituciones)
│   ├── FE.yaml                     #   Feature engineering, regiones, outliers (IQR/Z-score)
│   ├── reportes.yaml               #   Paleta IMSS, matplotlib rcParams, templates EDA
│   └── logging.yaml                #   Loguru dual-sink (consola + archivo)
│
├── data/
│   ├── raw_PDFs/                   # ~633 boletines epidemiológicos 2014-2026 (DVC)
│   ├── raw/                        # CSVs crudos (data_raw.csv, data_raw_{padecimiento}.csv)
│   ├── interim/                    # Datos intermedios (data_clean.csv)
│   ├── processed/                  # Dataset final, data_prepare, data_inegi, .xlsx
│   ├── utils/                      # Datos auxiliares (inegi.csv)
│   └── registry.json               # Registro de boletines descargados (anti-duplicados)
│
├── src/
│   ├── configuraciones/            # Carga de config YAML + logger (config_params.py)
│   ├── datos/                      # Limpieza, filtrado, FE, EDA, descarga, INEGI
│   │   ├── clean_dataset.py        #   Limpieza de datos
│   │   ├── filtrar_padecimiento.py #   Filtrado por padecimiento
│   │   ├── preparacion.py          #   Feature engineering (outliers, agrupación, regiones)
│   │   ├── get_inegi.py            #   Descarga datos INEGI (PxWeb + superficie)
│   │   ├── descarga_dataset.py     #   Copia dataset base
│   │   └── EDA.py                  #   Análisis exploratorio (ReportData)
│   ├── extraccion/                 # Pipeline de extracción PDF
│   │   ├── pipeline.py             #   Extracción con Camelot (keywords F32, G20, G30)
│   │   ├── merge_datasets.py       #   Merge incremental al dataset principal
│   │   ├── cli.py / gui.py         #   Interfaces CLI y GUI
│   │   └── inegi.py / inegi_eda.py #   Utilidades INEGI
│   ├── modelado/                   # Modelos Prophet
│   │   ├── prophet.py              #   SerieTiempoProphet (CV, train, eval por estado/región)
│   │   ├── forecast.py             #   ForecastModelLoader (carga .pkl y predice)
│   │   └── mapea_inegi.py          #   MapeaInegi (merge datos + INEGI + export xlsx)
│   └── utils/                      # Utilidades compartidas
│       ├── graficos.py             #   GraficosHelper (histogramas, violins, series, etc.)
│       ├── reporte_PDF.py          #   PDFReportGenerator (reportes EDA con reportlab)
│       ├── directory_manager.py    #   Gestión de carpetas y archivos
│       └── datos.py                #   OperacionesDatos (helpers pandas)
│
├── scripts/                        # Entry points para Makefile y CI/CD
│   ├── entrena.py                  #   make train
│   ├── predice.py                  #   make predict
│   ├── padecimiento.py             #   make filter
│   ├── limpieza_dataset.py         #   make clean
│   ├── realiza_prep.py             #   make transform
│   ├── descarga_inegi.py           #   make get_inegi
│   ├── mapea.py                    #   make mapper
│   ├── get_dataset.py              #   make get_dataset
│   ├── scrape_boletines.py         #   CI: scraper SINAVE
│   ├── ci_process_boletines.py     #   CI: extracción + merge
│   └── imss.sh                     #   Sincronización rápida (source scripts/imss.sh)
│
├── notebooks/                      # Libretas de análisis
│   ├── Avance1.Equipo01.ipynb
│   ├── Avance2_Equipo01.ipynb
│   ├── Avance3.Equipo01.ipynb
│   └── Data_Extract_ProyectoIntegrador_Equipo1.ipynb
│
├── outputs/                        # Visualizaciones generadas
│   ├── eda/                        #   Gráficos EDA (21+ figuras)
│   └── feature_engineering/        #   Gráficos FE (heatmaps, bump charts, series)
│
├── models/                         # Modelos entrenados Prophet (.pkl) (DVC)
├── logs/                           # Logs rotativos (Loguru)
├── reports/                        # Reportes PDF y figuras
│   ├── docs/                       #   PDFs de EDA generados
│   └── figures/                    #   Figuras de reportes
│
├── Makefile                        # Automatización de tareas
├── requirements.txt                # Dependencias Python
├── pyproject.toml                  # Metadatos del proyecto y config Ruff
└── CLAUDE.md                       # Este archivo
```

## Stack Técnico

| Categoría | Tecnologías |
|-----------|-------------|
| Lenguaje | Python 3.12 |
| Forecasting | Prophet 1.3, cmdstanpy |
| ML / Stats | scikit-learn, xgboost, statsmodels, SciPy |
| Datos | pandas, NumPy |
| PDF Extraction | camelot-py (+ Ghostscript), pypdf |
| Visualización | matplotlib, seaborn, plotly, kaleido |
| Reportes | reportlab (PDF), rich (consola) |
| Config / Logging | OmegaConf, Loguru |
| Data Versioning | DVC + Amazon S3 |
| CI/CD | GitHub Actions, Selenium (scraping) |
| Cloud | AWS S3, AWS SNS |
| Code Quality | Ruff |

## Comandos Útiles

### Setup
```bash
make setup              # macOS: Ghostscript + deps + DVC pull
make setup-linux        # Linux/WSL equivalente
make requirements       # Solo instalar dependencias Python
make data-pull          # Descargar datos desde S3 via DVC
source scripts/imss.sh  # Sync rápido: activa venv + git pull + dvc pull
```

### Pipeline de Preprocesamiento
```bash
make preprocess   # Pipeline completo (secuencial, NO usar -j):
                  #   reset_logs → reset_interim → get_dataset → filter
                  #   → clean → transform → get_inegi → mapper
make filter       # Filtrar por padecimiento (config/params.yaml → padecimiento.tipo)
make clean        # Limpiar dataset (nulos, duplicados, formato)
make transform    # Feature engineering (outliers IQR/Z-score, regiones, agrupación)
make get_inegi    # Descargar datos demográficos INEGI
make mapper       # Mapear entidades con regiones INEGI → genera .csv y .xlsx
```

### Modelado
```bash
make train          # Entrena Prophet con CV temporal (tasa por 100K, por estado o region)
make models-push    # Versiona modelos con DVC y sube a S3
make predict        # Genera predicciones (120 semanas), desnormaliza a conteos
make forecast-push  # Versiona forecast con DVC y sube a S3
```

### Flujo completo de modelado
```bash
make train          # 1. Entrenar
make models-push    # 2. Subir modelos a S3
make predict        # 3. Predecir
make forecast-push  # 4. Subir forecast a S3
git add models.dvc forecast/all_forecast.csv.dvc
git commit -m "feat: nuevos modelos y forecast"
git push
```

### DVC
```bash
make data-pull    # Descargar datos, modelos y forecast desde S3
make data-push    # Subir datos a S3
make data-status  # Estado de sincronizacion
make data-add PDF=ruta/archivo.pdf   # Trackear nuevo PDF
make data-commit  # Commitear datos + push a Git y S3
```

### Code Quality
```bash
make lint         # Ruff check + format check
make format       # Auto-format con Ruff
```

## Arquitectura

### Flujo de Datos
```
SINAVE PDFs ──▶ Extracción (Camelot) ──▶ Merge ──▶ dataset_boletin_epidemiologico.csv
                                                           │
                      ┌────────────────────────────────────┘
                      ▼
              filter (por padecimiento)
                      │
                      ▼
              clean (nulos, duplicados, formato)
                      │
                      ▼
              transform (FE: outliers IQR/Z-score, agrupación por sexo, regiones)
                      │
                      ▼
              mapper (merge con INEGI: población, superficie, región salud mental)
                      │
                      ▼
              train (Prophet por estado o region x sexo, tasa por 100K)
                      │
                      ▼
              models/*.pkl (DVC → S3)  +  predict (desnormaliza a conteos)
                      │                     → forecast/all_forecast.csv (DVC → S3)
```

### Configuración Clave (`config/params.yaml`)

```yaml
padecimiento:
  tipo: "General"           # General | Depresión | Parkinson | Alzheimer
  modelado_estados: true    # true = modelos por estado, false = por región INEGI
  modelado_region: "Metropolitana alta"  # región específica (si modelado_estados=false)
  modelado_sexo: "todos"    # hombres | mujeres | todos
  entrena_modelo: true      # entrenar modelo final con todo el dataset
```

### Regiones INEGI de Salud Mental
- Urbana media
- Sur-Sureste vulnerable
- Metropolitana alta
- Rural / dispersa

### Transformaciones del Target (modelado.yaml)

Prophet modela el target con tres transformaciones secuenciales:

1. **Normalización a tasa por 100K:** `y_tasa = (incidencia / población) × 100,000`
2. **Log-transform:** `y = log(1 + y_tasa)` — estabiliza varianza en series volátiles (especialmente Depresión)
3. **Prophet entrena sobre `y`** (espacio log-tasa)

Al predecir, `forecast.py` revierte ambas transformaciones: `exp(ŷ) - 1` → desnormaliza a conteos. El CSV de entrenamiento (sidecar del .pkl) guarda la columna `Total` para la desnormalización.

```yaml
normalizar_tasa: true          # activar normalización
columna_poblacion: "Total"     # columna de población en data_inegi
tasa_por: 100000               # factor (per 100K hab.)
log_transform: true            # log(1+y) para estabilizar varianza
```

### Grid de hiperparámetros (modelado.yaml)
Grids diferenciados por padecimiento (optimizados tras análisis de 297 modelos). CV elige automáticamente el mejor conjunto.

```yaml
param_grid_prophet:
  alzheimer:
    seasonality_mode: [multiplicative]              # additive eliminado (+51% RMSE)
    changepoint_prior_scale: [0.01, 0.03]           # 0.005 eliminado (L-BFGS failures)
    seasonality_prior_scale: [0.1, 0.5]             # 4 combinaciones
  depresion:
    seasonality_mode: [additive, multiplicative]    # additive mejor promedio
    changepoint_prior_scale: [0.01, 0.03, 0.05]
    seasonality_prior_scale: [0.05, 0.1, 0.5, 1.0] # 1.0 re-agregado (ganador 29.3%)
    # 24 combinaciones
  parkinson:
    seasonality_mode: [multiplicative, additive]
    changepoint_prior_scale: [0.01, 0.03, 0.05, 0.07] # 0.03 agregado
    seasonality_prior_scale: [0.1, 0.5, 1.0]           # 1.0 re-agregado
    # 24 combinaciones
```

La selección del grid se hace automáticamente en `SerieTiempoProphet.__init__` leyendo la columna `Padecimiento` del DataFrame.

### Parámetros regionales para modelos por estado
Para series estatales (más cortas que las nacionales), se aplican automáticamente:
- **`fourier_order_regional: 3`** — reduce overfitting vs fourier_order=5 nacional (especialmente Depresión)
- **`n_changepoints_regional: 12`** — reduce overfitting en entidades < 1M hab. (vs 25 default de Prophet)

Ambos se aplican solo cuando `modelado_estados: true` en `params.yaml`.

### Cross-validation con pesos progresivos
Los 4 folds de CV se ponderan con `cv_weights: [0.5, 0.75, 1.0, 1.25]`, dando más peso a los folds recientes (2023-2024) y menos al periodo post-COVID (2020-2021). Se usa `np.average()` en vez de `np.mean()`.

### Métricas de CV
`prophet_cross_val()` retorna RMSE, MAE y MAPE. El CSV de resultados incluye las tres métricas más `tiempo_cv_seg`, `tiempo_train_seg` y `tiempo_total_seg` por modelo.

### Clasificación de confianza
Series con promedio < `umbral_minimo_semanal` (default: 1.0 caso/semana) se marcan con `confianza: "insuficiente"` en el CSV de resultados. **Se entrenan y generan `.pkl` de todos modos** para que el dashboard Tableau muestre todas las entidades con su etiqueta de confianza. ~84 modelos son insuficientes (principalmente Alzheimer y Parkinson en estados de baja población).

### Periodos Atípicos Configurados (modelado.yaml)
- **Pandemia COVID-19**: 2020-03-23, ventana de 913 días (~2.5 años)
- **Atípico 2016**: 2016-05-16, ventana de 182 días

### Cambios de régimen por entidad (modelado.yaml)
Se agregan como holidays a Prophet, filtrados por `entidad` y `padecimiento` en `SerieTiempoProphet.__init__`:
- **Tabasco Depresión**: 2023-01-09, ventana 365 días (-6.2% RMSE)

Nota: Solo se incluyen cambios temporales. Los step functions permanentes (Nayarit, Colima, Durango, BCS) empeoran el RMSE con holidays porque Prophet los trata como eventos temporales.

## CI/CD (GitHub Actions)

1. **`scrape_boletines.yml`** — Diario 2 PM CDMX: Selenium descarga nuevos boletines SINAVE → DVC push → git commit → SNS
2. **`process_boletines.yml`** — Trigger post-scraping: extrae tablas (Camelot, keywords F32/G20/G30) → merge incremental → DVC push → SNS

## Data Files (DVC-versioned en S3)

- **`data/raw_PDFs/`** — ~633 boletines epidemiologicos 2014-2026 (~1GB)
- **`data/processed/dataset_boletin_epidemiologico.csv`** — Dataset consolidado
- **`models/`** — ~900 modelos Prophet .pkl + .csv de entrenamiento (~109 MB)
- **`forecast/all_forecast.csv`** — Predicciones consolidadas (~180 MB)
- **`data/registry.json`** — Registro de boletines procesados (anti-duplicados, Git)
- **`data/utils/inegi.csv`** — Datos demograficos INEGI (poblacion, superficie, Git)

## Resultados del Modelado (v4 — 2025-02-21)

297 modelos Prophet entrenados (3 padecimientos × 33 entidades × 3 sexos) en ~57 minutos con `n_jobs=-2` (joblib).

| Padecimiento | Modelos | Insuficientes | RMSE medio | RMSE rango | Mejor estado | Peor estado |
|-------------|---------|---------------|------------|------------|-------------|-------------|
| Depresión | 99 | 0 | 0.114 | 0.04–0.41 | Querétaro (0.04) | Nayarit (0.41) |
| Parkinson | 99 | 20 | 0.065 | 0.02–0.18 | Sinaloa (0.02) | BCS (0.18) |
| Alzheimer | 99 | 64 | 0.054 | 0.01–0.22 | Tabasco (0.01) | Chihuahua (0.22) |

- **213 modelos con confianza "normal"**, 84 marcados "insuficiente" (promedio < 1 caso/semana)
- **Depresión** tiene 100% cobertura (todos los estados tienen suficiente volumen)
- **Alzheimer** tiene solo 35 modelos normales (65% insuficientes) — estados de baja población
- Modelo más lento: Chihuahua-Depresión (39 min por fallback Newton en L-BFGS)
- Forecast: 120 semanas a futuro, desnormalizado a conteos en `all_forecast.csv`
- Hallazgos detallados en `REPORTE_HALLAZGOS_MODELADO_v2.md`

## Estado Actual del Pipeline

### Funcional
- Pipeline de preprocesamiento completo (`make preprocess`)
- Scraping + procesamiento automatizado (CI/CD)
- Entrenamiento Prophet con CV temporal por estado o región, normalizado a tasa por 100K + log-transform (`make train`)
- Predicción con inversión de log-transform y desnormalización automática a conteos (`make predict`)
- Generación de reportes EDA en PDF
- Detección de outliers parametrizada (IQR / Z-score)
- Entrenamiento paralelo con joblib (`n_jobs=-2`, backend loky)
- Progreso % visible en modo paralelo y secuencial

### TODOs / Inconsistencias Conocidas
- **`pyproject.toml`**: `requires-python = "~=3.14.0"` deberia ser `~=3.12.0`; `name = "alzheimer"` y `[tool.ruff] src = ["alzheimer"]` deberian reflejar el nombre actual del proyecto
- **`metadata` en `params.yaml`**: referencia al proyecto antiguo ("Alzheimer", URL de repo anterior)
- **Nayarit-Depresión**: RMSE=0.41 (peor modelo), cambio de régimen 2018 no absorbido completamente
- **Chihuahua-Depresión**: Newton fallback causa 39 min de entrenamiento (vs ~30s promedio)
