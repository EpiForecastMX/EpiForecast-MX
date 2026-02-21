<p align="center">
  <img src="https://images.seeklogo.com/logo-png/7/1/imss-logo-png_seeklogo-70988.png" alt="IMSS Logo" width="120"/>
</p>

<h1 align="center">EpiForecast-MX</h1>

<p align="center">
  <strong>Sistema de Pronóstico Epidemiológico para Enfermedades Neurológicas y de Salud Mental en México</strong>
</p>

<p align="center">
  <em>Proyecto Capstone · Maestría en Inteligencia Artificial Aplicada · Tecnológico de Monterrey</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-006341?style=flat&logo=python&logoColor=white" alt="Python 3.12"/>
  <img src="https://img.shields.io/badge/Prophet-Meta-006341?style=flat&logo=meta&logoColor=white" alt="Prophet"/>
  <img src="https://img.shields.io/badge/DVC-S3-006341?style=flat&logo=dvc&logoColor=white" alt="DVC"/>
  <img src="https://img.shields.io/badge/CI%2FCD-GitHub_Actions-006341?style=flat&logo=githubactions&logoColor=white" alt="GitHub Actions"/>
  <img src="https://img.shields.io/badge/Licencia-MIT-006341?style=flat" alt="MIT License"/>
</p>

<p align="center">
  <a href="#descripción">Descripción</a> •
  <a href="#arquitectura">Arquitectura</a> •
  <a href="#instalación">Instalación</a> •
  <a href="#comandos">Comandos</a> •
  <a href="#cicd">CI/CD</a> •
  <a href="#pipeline-de-preprocesamiento">Pipeline</a> •
  <a href="#stack-tecnológico">Stack</a> •
  <a href="#equipo">Equipo</a>
</p>

---

## Descripción

**EpiForecast-MX** es una plataforma de inteligencia epidemiológica desarrollada en colaboración con el **Instituto Mexicano del Seguro Social (IMSS)** para el pronóstico de casos de enfermedades neurológicas y de salud mental en México.

### Objetivo

Predecir la incidencia de **Depresión (F32)**, **Parkinson (G20)** y **Alzheimer (G30)** mediante modelos de series de tiempo, utilizando datos históricos (2014-2026) del Sistema Nacional de Vigilancia Epidemiológica (SINAVE) e indicadores demográficos del INEGI.

El sistema genera **proyecciones a nivel nacional y estatal** (32 entidades federativas) con intervalos de predicción confiables, proporcionando herramientas para la **planificación estratégica en salud pública**.

### Características Principales

- **Extracción automatizada** de datos desde boletines epidemiológicos oficiales (PDF)
- **Pipeline CI/CD completo** que detecta, descarga y procesa nuevos boletines diariamente
- **Modelado predictivo** con Facebook Prophet segmentado por región y sexo, normalizado a **tasa por 100,000 habitantes**
- **Versionado de datos** con DVC sobre Amazon S3 para reproducibilidad total
- **Notificaciones automáticas** vía Amazon SNS al equipo cuando se actualizan datos

---

## Arquitectura

### Flujo de Datos

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PIPELINE AUTOMATIZADO                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   SINAVE (Boletines PDF)                                                        │
│           │                                                                      │
│           ▼                                                                      │
│   ┌───────────────────┐      ┌───────────────────┐      ┌──────────────────┐   │
│   │  Scraper Diario   │─────▶│  Extracción PDF   │─────▶│  Dataset CSV     │   │
│   │  (Selenium)       │      │  (Camelot)        │      │  (2014-2026)     │   │
│   └───────────────────┘      └───────────────────┘      └──────────────────┘   │
│           │                          │                          │               │
│           ▼                          ▼                          ▼               │
│   ┌───────────────────────────────────────────────────────────────────────┐    │
│   │                         Amazon S3 (DVC)                                │    │
│   │                    s3://epiforecast-mx-data                            │    │
│   └───────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PIPELINE DE MODELADO                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Dataset CSV ──▶ Limpieza ──▶ Feature Engineering ──▶ INEGI Mapping            │
│                                                              │                   │
│                                                              ▼                   │
│                                    ┌─────────────────────────────────────┐      │
│                                    │         Prophet Model               │      │
│                                    │   (por región × sexo × enfermedad)  │      │
│                                    └─────────────────────────────────────┘      │
│                                                              │                   │
│                                                              ▼                   │
│                                                  models/*.pkl (DVC → S3)        │
│                                                              │                   │
│                                                              ▼                   │
│                                                     Pronósticos CSV              │
│                                                       (DVC → S3)                │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Componentes Principales

| Módulo | Descripción |
|--------|-------------|
| `src/extraccion/` | Extracción de tablas desde PDFs con Camelot y búsqueda por keywords |
| `src/datos/` | Limpieza, filtrado por padecimiento y feature engineering |
| `src/modelado/` | Implementación de Prophet con validación cruzada temporal |
| `src/configuraciones/` | Carga de configuración YAML y logging con Loguru |
| `scripts/` | Orquestadores para Makefile y CI/CD |

---

## Estructura del Proyecto

```
EpiForecast-MX/
│
├── .github/workflows/          # Pipelines CI/CD
│   ├── scrape_boletines.yml    #   └─ Scraper diario SINAVE (2 PM CDMX)
│   └── process_boletines.yml   #   └─ Extracción y merge automático
│
├── config/                     # Configuración YAML
│   ├── params.yaml             #   └─ Parámetros generales y rutas
│   ├── modelado.yaml           #   └─ Hiperparámetros Prophet y periodos atípicos
│   ├── limpieza.yaml           #   └─ Reglas de limpieza de datos
│   ├── FE.yaml                 #   └─ Feature engineering, regiones, outliers
│   ├── reportes.yaml           #   └─ Paleta IMSS, matplotlib rcParams, templates EDA
│   └── logging.yaml            #   └─ Loguru dual-sink (consola + archivo)
│
├── data/
│   ├── raw_PDFs/               # ~633 boletines epidemiológicos 2014-2026 (~1GB, DVC)
│   ├── raw/                    # CSVs crudos (data_raw.csv, data_raw_{padecimiento}.csv)
│   ├── processed/              # Dataset consolidado, data_prepare, data_inegi, .xlsx (DVC)
│   ├── interim/                # Datos intermedios (data_clean.csv)
│   ├── utils/                  # Datos auxiliares (inegi.csv)
│   └── registry.json           # Registro de boletines descargados
│
├── src/
│   ├── configuraciones/        # Gestión de configuración (OmegaConf + Loguru)
│   ├── datos/                  # Limpieza, filtrado, FE, EDA, descarga INEGI
│   ├── extraccion/             # Pipeline de extracción PDF (Camelot)
│   ├── modelado/               # Prophet (train/predict), mapeo INEGI
│   └── utils/                  # Gráficos, reportes PDF, directory manager
│
├── scripts/                    # Entry points para Makefile y CI/CD
├── models/                     # Modelos entrenados Prophet (.pkl) (DVC)
├── notebooks/                  # Libretas de análisis (Avance 1-3, Data Extract)
├── outputs/                    # Visualizaciones generadas
│   ├── eda/                    #   └─ Gráficos EDA (21+ figuras)
│   └── feature_engineering/    #   └─ Heatmaps, bump charts, series temporales
├── logs/                       # Logs rotativos (Loguru)
├── reports/                    # Reportes y figuras
│   ├── docs/                   #   └─ PDFs de EDA generados
│   └── figures/                #   └─ Figuras de reportes
│
├── Makefile                    # Automatización de tareas
├── requirements.txt            # Dependencias Python
├── pyproject.toml              # Metadatos del proyecto y config Ruff
└── CLAUDE.md                   # Guía de contexto para Claude Code
```

---

## Instalación

### Requisitos Previos

- **Python 3.12**
- **Git**
- **AWS CLI** (configurado con credenciales del equipo)
- **Ghostscript** (para procesamiento de PDFs)

### macOS

```bash
# 1. Clonar repositorio
git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
cd EpiForecast-MX

# 2. Configurar AWS (solicitar credenciales al equipo)
aws configure

# 3. Setup completo (instala Ghostscript, dependencias y descarga datos)
make setup
```

### Linux / WSL

```bash
# 1. Clonar repositorio
git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
cd EpiForecast-MX

# 2. Configurar AWS
aws configure

# 3. Setup completo
make setup-linux
```

### Instalación Manual

```bash
# Crear entorno virtual
make create_environment        # Con venv
make create_environment_conda  # Con Conda

# Activar entorno
source integrador/bin/activate  # venv
conda activate integrador       # Conda

# Instalar dependencias
make requirements

# Descargar datos desde S3
make data-pull
```

---

## Comandos

Todos los comandos están definidos en el `Makefile` de la raíz del proyecto. Ejecuta `make help` para ver los disponibles.

### Setup y Entorno

| Comando | Descripción |
|---------|-------------|
| `make setup` | Setup completo para macOS (Ghostscript + dependencias + datos) |
| `make setup-linux` | Setup completo para Linux/WSL |
| `make setup_mac` | Instala solo dependencias del sistema (macOS) |
| `make setup_linux` | Instala solo dependencias del sistema (Linux) |
| `make create_environment` | Crea entorno virtual con venv e instala dependencias |
| `make create_environment_conda` | Crea entorno con Conda e instala dependencias |
| `make requirements` | Instala/actualiza dependencias de Python |
| `source scripts/imss.sh` | **Sincronización rápida:** desactiva conda/venv + activa integrador + git pull + dvc pull |

### Pipeline de Datos

| Comando | Descripción |
|---------|-------------|
| `make preprocess` | Pipeline completo: get_dataset → filter → clean → transform → get_inegi → mapper |
| `make get_dataset` | Copia dataset base desde `data/processed/` a `data/raw/` |
| `make filter` | Filtra dataset por padecimiento configurado en `params.yaml` |
| `make clean` | Limpia datos: elimina nulos, duplicados, formatea columnas |
| `make transform` | Aplica feature engineering y transformaciones |
| `make get_inegi` | Descarga datos demográficos del INEGI |
| `make mapper` | Mapea entidades con regiones INEGI |

### Modelado

| Comando | Descripción |
|---------|-------------|
| `make train` | Entrena modelo Prophet con CV temporal (tasa por 100K, por estado o region) |
| `make predict` | Genera predicciones (120 semanas) usando los modelos entrenados |
| `make models-push` | Versiona modelos con DVC y sube a S3 |
| `make forecast-push` | Versiona forecast con DVC y sube a S3 |

### Gestión de Datos (DVC)

| Comando | Descripción |
|---------|-------------|
| `make data-pull` | Descarga datos desde S3 |
| `make data-push` | Sube datos a S3 |
| `make data-status` | Muestra estado de sincronización DVC |
| `make data-add PDF=ruta/archivo.pdf` | Agrega nuevo boletín PDF al tracking |
| `make data-commit` | Commitea cambios de datos y push a Git + S3 |
| `make data-weekly PDF=ruta/archivo.pdf` | Flujo semanal completo (add + commit) |
| `make s3-sync` | Sube CSVs directamente a S3 (acceso directo, sin DVC) |

### Calidad de Código

| Comando | Descripción |
|---------|-------------|
| `make lint` | Verifica código con Ruff (formato + linting) |
| `make format` | Auto-formatea código con Ruff |
| `make clean_py` | Elimina archivos `.pyc` y carpetas `__pycache__` |

### Utilidades

| Comando | Descripción |
|---------|-------------|
| `make help` | Muestra todos los comandos disponibles con descripción |
| `make reset_logs` | Elimina y recrea carpeta `logs/` |
| `make reset_interim` | Elimina y recrea carpeta `data/interim/` |

---

## CI/CD

El proyecto cuenta con un pipeline completamente automatizado mediante **GitHub Actions**.

### Pipeline de Scraping

**Workflow:** `scrape_boletines.yml`
**Schedule:** Diario a las 14:00 hrs (CDMX)

```
┌──────────────────────────────────────────────────────────────┐
│  1. Selenium navega página SINAVE                            │
│  2. Compara con registry.json                                │
│  3. Descarga PDFs nuevos a data/raw_PDFs/                    │
│  4. DVC add + push a S3                                      │
│  5. Git commit (registry.json + raw_PDFs.dvc)                │
│  6. Notificación SNS al equipo                               │
└──────────────────────────────────────────────────────────────┘
```

### Pipeline de Procesamiento

**Workflow:** `process_boletines.yml`
**Trigger:** Automático al completar scraping (o manual)

```
┌──────────────────────────────────────────────────────────────┐
│  1. DVC pull (PDFs + dataset actual)                         │
│  2. Detecta PDFs no procesados                               │
│  3. Extrae tablas con Camelot (keywords: F32, G20, G30)      │
│  4. Merge incremental al dataset principal                   │
│  5. DVC add + push dataset actualizado                       │
│  6. Git commit (.dvc pointer)                                │
│  7. Notificación SNS al equipo                               │
└──────────────────────────────────────────────────────────────┘
```

### GitHub Secrets Requeridos

| Secret | Descripción |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | Credencial de acceso AWS |
| `AWS_SECRET_ACCESS_KEY` | Credencial secreta AWS |
| `AWS_REGION` | Región AWS (`us-east-1`) |
| `SNS_TOPIC_ARN` | ARN del topic SNS (opcional) |

### Sincronización Local

Cuando el pipeline actualice el dataset, sincroniza tu entorno local:

```bash
git pull && dvc pull
```

---

## Pipeline de Preprocesamiento

El comando `make preprocess` ejecuta el pipeline completo de preparación de datos. **Antes de ejecutarlo, es obligatorio descargar los datos versionados con DVC.**

### Ejecución

```bash
# 1. Descargar datos desde S3 (obligatorio antes de preprocess)
make data-pull

# 2. Ejecutar pipeline completo de preprocesamiento
make preprocess
```

### Pasos del Pipeline

`make preprocess` ejecuta los siguientes targets en orden secuencial:

| # | Target | Lee | Produce |
|---|--------|-----|---------|
| 1 | `reset_logs` | — | `logs/` (directorio limpio) |
| 2 | `reset_interim` | — | `data/interim/` (directorio limpio) |
| 3 | `get_dataset` | `data/processed/dataset_boletin_epidemiologico.csv` | `data/raw/data_raw.csv` |
| 4 | `filter` | `data/raw/data_raw.csv` | `data/raw/data_raw_{padecimiento}.csv` |
| 5 | `clean` | `data/raw/data_raw_{padecimiento}.csv` | `data/interim/data_clean.csv` |
| 6 | `transform` | `data/interim/data_clean.csv` | `data/processed/data_prepare_{padecimiento}.csv` |
| 7 | `get_inegi` | API INEGI (PxWeb + Superficie) | `data/utils/inegi.csv` |
| 8 | `mapper` | `data/processed/data_prepare_{padecimiento}.csv` + `data/utils/inegi.csv` | `data/processed/data_inegi_{padecimiento}.csv` + `data/processed/EpiForecast-MX.xlsx` |

> `{padecimiento}` se resuelve según `padecimiento.tipo` en `config/params.yaml` (por defecto: `General`).

### Flujo de Archivos

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PREREQUISITO: make data-pull  (descarga datos versionados desde S3)       │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PASO 1: reset_logs                                                        │
│  Limpia ──▶ logs/                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  PASO 2: reset_interim                                                     │
│  Limpia ──▶ data/interim/                                                  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PASO 3: get_dataset                                                       │
│  Lee:    data/processed/dataset_boletin_epidemiologico.csv  (vía DVC)      │
│  Produce: data/raw/data_raw.csv                                            │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PASO 4: filter                                                            │
│  Lee:    data/raw/data_raw.csv                                             │
│  Produce: data/raw/data_raw_General.csv                                    │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PASO 5: clean                                                             │
│  Lee:    data/raw/data_raw_General.csv                                     │
│  Produce: data/interim/data_clean.csv                                      │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PASO 6: transform                                                         │
│  Lee:    data/interim/data_clean.csv                                       │
│  Produce: data/processed/data_prepare_General.csv                          │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PASO 7: get_inegi                                                         │
│  Lee:    API INEGI (PxWeb población + superficie)                          │
│  Produce: data/utils/inegi.csv                                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PASO 8: mapper                                                            │
│  Lee:    data/processed/data_prepare_General.csv                           │
│          data/utils/inegi.csv                                              │
│  Produce: data/processed/data_inegi_General.csv                            │
│           data/processed/EpiForecast-MX.xlsx                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

> **Importante:** No ejecutes `make -j preprocess` (modo paralelo). Los pasos son secuenciales y dependen de la salida del paso anterior. Los nombres de archivo con `General` corresponden al valor por defecto de `padecimiento.tipo` en `config/params.yaml`.

---

## Flujo de Modelado (Entrenamiento y Prediccion)

Una vez completado el preprocesamiento, el flujo de modelado genera modelos Prophet por estado/region y sexo, y produce un forecast consolidado.

### Transformaciones del Target

Prophet no modela conteos absolutos directamente. Se aplican dos transformaciones al target para mejorar la calidad del ajuste:

**1. Normalizacion a tasa por 100K habitantes**
- Iguala la escala entre estados con diferente poblacion (CDMX ~9M vs Colima ~730K)
- Produce RMSE comparable entre estados grandes y pequenos

**2. Log-transform: `y = log(1 + tasa)`**
- Estabiliza la varianza en series volatiles (especialmente Depresion)
- Comprime picos extremos, permitiendo a Prophet ajustar mejor la estacionalidad
- Redujo el RMSE medio de Depresion en **-64%** y elimino todos los modelos con RMSE > 1.0

**3. Modo de estacionalidad adaptativo**
- El grid de cross-validation incluye `additive` y `multiplicative`
- CV elige automaticamente: `additive` gana en ~49% de modelos de Depresion
- Alzheimer y Parkinson prefieren `multiplicative` (~74%)

**4. Grids diferenciados por padecimiento**
- Cada padecimiento tiene su propio grid de hiperparametros, optimizado tras analisis de 297 modelos
- Alzheimer: solo multiplicative, 6 combinaciones
- Depresion: ambos modos, 18 combinaciones
- Parkinson: ambos modos, 12 combinaciones

**5. Parametros regionales para modelos por estado**
- `fourier_order_regional: 3` (vs 5 nacional) para reducir overfitting en series cortas
- `n_changepoints_regional: 12` (vs 25 default) para entidades de baja poblacion

**6. Filtro de series insuficientes**
- Series con promedio < 1 caso/semana se descartan antes de CV (~84 modelos filtrados)
- Genera fila con `confianza: "insuficiente"` sin modelo .pkl

**7. Cambios de regimen por entidad**
- Se configuran como holidays en Prophet, filtrados por entidad/padecimiento
- Tabasco Depresion (2023): -6.2% RMSE

Las predicciones se **desnormalizan automaticamente** a conteos absolutos en `all_forecast.csv` (primero `exp(y) - 1`, luego `× poblacion / 100K`). El CSV incluye tanto `yhat` (conteos) como `yhat_tasa` (por 100K).

Configuracion en `config/modelado.yaml`:

```yaml
normalizar_tasa: true          # modelar tasa por 100K
columna_poblacion: "Total"     # columna de poblacion
tasa_por: 100000               # factor de normalizacion
log_transform: true            # log(1+y) para estabilizar varianza
umbral_minimo_semanal: 1.0     # promedio minimo de casos/semana para entrenar

param_grid_prophet:
  alzheimer:
    seasonality_mode: [multiplicative]
    changepoint_prior_scale: [0.005, 0.01, 0.03]
    seasonality_prior_scale: [0.1, 0.5]
  depresion:
    seasonality_mode: [additive, multiplicative]
    changepoint_prior_scale: [0.01, 0.03, 0.05]
    seasonality_prior_scale: [0.05, 0.1, 0.5]
  parkinson:
    seasonality_mode: [multiplicative, additive]
    changepoint_prior_scale: [0.01, 0.05, 0.07]
    seasonality_prior_scale: [0.1, 0.5]
```

### Flujo completo

```bash
# 1. Entrenar modelos (genera .pkl y .csv en models/)
make train

# 2. Versionar modelos y subir a S3
make models-push

# 3. Generar predicciones consolidadas (forecast/all_forecast.csv)
make predict

# 4. Versionar forecast y subir a S3
make forecast-push

# 5. Commit de archivos DVC y push a GitHub
git add models.dvc forecast/all_forecast.csv.dvc
git commit -m "feat: nuevos modelos y forecast"
git push
```

### Diagrama

```
make train
    │
    ▼
models/
├── Alzheimer/    ─┐
├── Depresion/     ├── Prophet_{Padecimiento}_{Estado}_{Sexo}_{Fecha}.pkl
└── Parkinson/    ─┘
    │
    ▼
make models-push ──▶ DVC add + push ──▶ S3 (s3://epiforecast-mx-data)
    │
    ▼
make predict
    │
    ▼
forecast/all_forecast.csv  (todas las predicciones consolidadas, 120 semanas)
    │
    ▼
make forecast-push ──▶ DVC add + push ──▶ S3
    │
    ▼
git add *.dvc && git commit && git push
```

### Archivos DVC generados

| Archivo | Contenido | Almacenamiento |
|---------|-----------|----------------|
| `models.dvc` | Hash de toda la carpeta `models/` (~900 archivos, ~109 MB) | S3 |
| `forecast/all_forecast.csv.dvc` | Hash del forecast consolidado (~180 MB) | S3 |

> Ambos archivos `.dvc` se commitean a Git. Los datos reales viven en S3 y se descargan con `dvc pull`.

### Sincronizacion para el equipo

Cuando un miembro del equipo entrena nuevos modelos y hace push, los demas solo necesitan:

```bash
# Opcion 1: Sincronizacion rapida (activa entorno + git pull + dvc pull)
source scripts/imss.sh

# Opcion 2: Manual
git pull origin main
dvc pull
```

Esto descarga automaticamente los modelos y forecasts mas recientes desde S3.

### Acceso directo a CSVs en S3

Ademas del versionado con DVC, los CSVs clave se publican directamente en S3 para acceso sin necesidad de DVC (dashboards, APIs, consumo externo):

| Archivo | Ruta S3 |
|---------|---------|
| Datos con INEGI | `s3://epiforecast-mx-data/latest/data_inegi_General.csv` |
| Forecast consolidado | `s3://epiforecast-mx-data/latest/all_forecast.csv` |

Para actualizar estos archivos despues de un reentrenamiento:

```bash
make s3-sync
```

---

## Stack Tecnológico

### Lenguaje y Entorno

| Tecnología | Versión | Uso |
|------------|---------|-----|
| Python | 3.12 | Lenguaje principal |
| Conda / venv | - | Gestión de entornos |

### Procesamiento de Datos

| Librería | Versión | Uso |
|----------|---------|-----|
| pandas | 2.3.0 | Manipulación de datos |
| NumPy | 2.0.0 | Computación numérica |
| SciPy | 1.14.1 | Funciones estadísticas |
| Camelot | 0.11.0 | Extracción de tablas PDF |
| pypdf | 4.3.1 | Manipulación de PDFs |
| ghostscript | 0.7 | Wrapper de Ghostscript para Python |

### Machine Learning

| Librería | Versión | Uso |
|----------|---------|-----|
| Prophet | 1.3.0 | Pronóstico de series de tiempo |
| cmdstanpy | >=1.2.0 | Backend de Stan para Prophet |
| scikit-learn | 1.5.0 | Validación cruzada y métricas |
| xgboost | >=2.0.0 | Gradient boosting (notebooks) |
| statsmodels | 0.14.4 | Análisis estadístico |

### Visualización

| Librería | Versión | Uso |
|----------|---------|-----|
| Matplotlib | 3.10.0 | Gráficos estáticos |
| Seaborn | 0.13.2 | Visualización estadística |
| Plotly | 5.24.0 | Gráficos interactivos |
| kaleido | 0.2.1 | Exportar Plotly a imágenes estáticas |

### Reportes

| Librería | Versión | Uso |
|----------|---------|-----|
| reportlab | 4.4.7 | Generación de reportes PDF |
| rich | >=13.0 | Tablas formateadas en consola |

### Infraestructura

| Tecnología | Uso |
|------------|-----|
| DVC | Versionado de datos |
| Amazon S3 | Almacenamiento de datos |
| Amazon SNS | Notificaciones |
| GitHub Actions | CI/CD |
| Selenium | Web scraping |

### Calidad de Código

| Herramienta | Versión | Uso |
|-------------|---------|-----|
| Ruff | 0.14.10 | Linter y formateador |
| Loguru | 0.7.3 | Logging estructurado |
| OmegaConf | 2.3.0 | Gestión de configuración |

---

## Fuentes de Datos

| Fuente | Descripción | URL |
|--------|-------------|-----|
| SINAVE | Boletín Epidemiológico Semanal | [gob.mx/salud](https://www.gob.mx/salud/acciones-y-programas/direccion-general-de-epidemiologia-boletin-epidemiologico) |
| SINAVE Histórico | Archivo de boletines previos | [gob.mx/salud/historico](https://www.gob.mx/salud/acciones-y-programas/historico-boletin-epidemiologico) |
| INEGI | Datos demográficos regionales | [inegi.org.mx](https://www.inegi.org.mx/) |

---

## Infraestructura AWS

| Recurso | Valor |
|---------|-------|
| Bucket S3 | `s3://epiforecast-mx-data` |
| Región | `us-east-1` |
| SNS Topic | Configurado vía GitHub Secrets |

---

## Equipo

### Desarrolladores

| Nombre | Afiliación Profesional |
|--------|------------------------|
| **Juan Carlos Pérez Nava** | IT Professional, IMSS |
| **Luis Gerardo Sánchez Salazar** | Sr. Controls Engineer, Tesla |
| **Javier Augusto Rebull Saucedo** | Sr. Associate Development Application, Santander Bank US |

### Asesoría Académica

| Nombre | Institución |
|--------|-------------|
| **Dra. Grettel Barceló Alonso** | Tecnológico de Monterrey |

### Stakeholders IMSS

| Nombre | Rol |
|--------|-----|
| **Dra. Ruth Pérez** | Project Leader |
| **Dra. Lina Díaz Castro** | Investigadora en Psiquiatría |

---

## Licencia

Este proyecto está licenciado bajo la [MIT License](https://opensource.org/licenses/MIT).

---

<p align="center">
  <sub>Desarrollado con el apoyo del Instituto Mexicano del Seguro Social y el Tecnológico de Monterrey</sub>
</p>
