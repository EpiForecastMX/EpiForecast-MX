# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**EpiForecast-MX** es una plataforma de inteligencia epidemiológica desarrollada en colaboración con el **Instituto Mexicano del Seguro Social (IMSS)** como proyecto Capstone de la Maestría en Inteligencia Artificial Aplicada del Tecnológico de Monterrey.

Predice la incidencia semanal de tres padecimientos neurológicos/salud mental:
- **Depresión (CIE-10: F32)**
- **Parkinson (CIE-10: G20)**
- **Alzheimer (CIE-10: G30)**

Utiliza Facebook Prophet para series de tiempo, con datos históricos (2014-2026) del SINAVE e indicadores demográficos del INEGI. Genera proyecciones a nivel **estatal** (32 entidades) o por **región INEGI de salud mental**, segmentadas por sexo.

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
make train          # Entrena Prophet con CV temporal (por estado o region segun config)
make models-push    # Versiona modelos con DVC y sube a S3
make predict        # Genera predicciones (120 semanas) con modelos entrenados
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
              train (Prophet por estado o region x sexo)
                      │
                      ▼
              models/*.pkl (DVC → S3)  +  predict → forecast/all_forecast.csv (DVC → S3)
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

### Periodos Atípicos Configurados (modelado.yaml)
- **Pandemia COVID-19**: 2020-03-23, ventana de 913 días (~2.5 años)
- **Atípico 2016**: 2016-05-16, ventana de 182 días

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

## Estado Actual del Pipeline

### Funcional
- Pipeline de preprocesamiento completo (`make preprocess`)
- Scraping + procesamiento automatizado (CI/CD)
- Entrenamiento Prophet con CV temporal por estado o región (`make train`)
- Predicción básica (`make predict`)
- Generación de reportes EDA en PDF
- Detección de outliers parametrizada (IQR / Z-score)

### TODOs / Inconsistencias Conocidas
- **`pyproject.toml`**: `requires-python = "~=3.14.0"` deberia ser `~=3.12.0`; `name = "alzheimer"` y `[tool.ruff] src = ["alzheimer"]` deberian reflejar el nombre actual del proyecto
- **`metadata` en `params.yaml`**: referencia al proyecto antiguo ("Alzheimer", URL de repo anterior)



# EpiForecast-MX — Contexto Core

Eres un asistente experto en series de tiempo epidemiológicas trabajando en **EpiForecast-MX**, un sistema de pronóstico desarrollado con el **IMSS** como Capstone de Maestría en IA Aplicada (Tec de Monterrey).

## Qué predecimos

Incidencia semanal de 3 padecimientos neurológicos/salud mental en México:
- **Depresión (F32)** — el más difícil, 100% de los peores modelos
- **Parkinson (G20)** — baja incidencia, buen desempeño
- **Alzheimer (G30)** — series más estables, mejor desempeño

## Datos

- **Fuente:** Boletines SINAVE (2014–2026), extraídos de PDF con Camelot
- **Granularidad:** Semanal × 32 estados × sexo (hombres/mujeres/todos)
- **Target:** Tasa por 100K habitantes (no conteos absolutos)
- **Demografía:** Poblaciones INEGI para normalización/desnormalización

## Arquitectura

- **Algoritmo:** Prophet 1.3 — un modelo por (padecimiento × estado × sexo) = **297 modelos**
- **CV:** Ventana inicial 730 días, periodo 56 días, horizonte 168 días, 4 folds temporales
- **Predicción:** 120 semanas (~2.3 años)
- **Periodos atípicos:** COVID-19 (2020-03-23, 913 días) y anomalía 2016 (182 días)

## Pipeline de transformación del target

```
Entrada: conteo semanal de incidencia
  → Tasa: y_tasa = (incidencia / población) × 100,000
  → Log:  y_final = log(1 + y_tasa)
  → Prophet modela y_final

Predicción (inversión):
  → exp(yhat) - 1 = yhat_tasa
  → yhat_tasa × población / 100,000 = yhat_conteo
```

## Config actual

```yaml
# config/modelado.yaml
normalizar_tasa: true
columna_poblacion: "Total"
tasa_por: 100000
log_transform: true

param_grid_prophet:  # 24 combinaciones = 2×3×4
  seasonality_mode: [multiplicative, additive]
  changepoint_prior_scale: [0.01, 0.03, 0.05]
  seasonality_prior_scale: [0.1, 0.5, 1.0, 2.0]

periodos_atipicos:
  - nombre: "COVID-19"
    inicio: "2020-03-23"
    ventana_dias: 913
  - nombre: "Atipico 2016"
    inicio: "2016-05-16"
    ventana_dias: 182
```

## Stack

Python 3.12, Prophet 1.3, pandas, NumPy, Camelot, DVC + AWS S3, GitHub Actions, Matplotlib/Plotly, OmegaConf, Loguru

## Estructura de modelos

```
models/{Padecimiento}/Prophet_{Padecimiento}_{Estado}_{Sexo}_{Fecha}.pkl
```
Cada `.pkl` tiene un `.csv` sidecar con datos de entrenamiento (incluye `Total` para desnormalización).

## Infra

- GitHub Actions: scraping diario 2PM CDMX → PDF → merge incremental
- DVC + S3: `s3://epiforecast-mx-data/`
- Dashboard: Tableau Public en proyectointegrador.org/epidashboard

## Reglas

- `y` de Prophet = `log(1 + tasa por 100K)`, NO conteos
- Commits y docs en **español**
- Paleta IMSS para visualizaciones
- Frecuencia semanal (`W` en pandas)

# EpiForecast-MX — Métricas y Hallazgos de Entrenamiento

## Métricas actuales (RMSE en tasa por 100K, sin log-transform)

| Padecimiento | RMSE medio | RMSE mediana | RMSE máx | Notas |
|---|---|---|---|---|
| Alzheimer | 0.033 | 0.026 | 0.182 | Excelente |
| Parkinson | 0.074 | 0.060 | 0.347 | Bueno |
| Depresión | 0.586 | 0.488 | 2.448 | 100% de los peores modelos |

Top 10 peores: TODOS Depresión (Nayarit, Colima, Durango, BCS, Tabasco, Chihuahua, CDMX).

## Hallazgos del grid (297 modelos, tasa 100K, sin log)

- `cp=0.01` dominó con 57.9% — tasa suaviza series, favorece rigidez
- `sp=0.1` ganador con 37.4%
- `multiplicative` dominó ~94%

## Hallazgos CON log-transform (en curso, ~26% completado)

- **Additive gana ~67% para Alzheimer** (vs 6% sin log) — cambio drástico
- cp=0.01 sigue dominando, pero cp=0.03 gana en algunos estados Alzheimer
- RMSE en log-space: 0.02-0.06 para Alzheimer

## Cross-validation: impacto COVID por fold

4 folds temporales expansivos. Fold 1 (2020-12 → 2021-12, COVID) siempre peor:

**Depresión (Nayarit, log-transform, promedio 24 combos):**

| Fold | Validación | RMSE | Nota |
|---|---|---|---|
| 1 | 2020-12 → 2021-12 | 0.94 | COVID, peor siempre |
| 2 | 2021-12 → 2022-12 | ~0.85 | Recuperación |
| 3 | 2022-12 → 2023-12 | ~0.70 | Mejora |
| 4 | 2024-01 → 2024-12 | 0.60 | Mejor fold |

**Alzheimer (Sonora hombres, log-transform):**

| Fold | Validación | RMSE | Nota |
|---|---|---|---|
| 1 | 2020-12 → 2021-12 | 0.0355 | Solo ~28% peor |
| 2 | 2021-12 → 2022-12 | 0.0318 | |
| 3 | 2022-12 → 2023-12 | 0.0302 | |
| 4 | 2024-01 → 2024-12 | 0.0277 | |

**Penalización COVID:** Depresión ~56%, Alzheimer ~28%, algunos estados apenas ~6%.

**Implicación:** El fold COVID sesga selección hacia rigidez (cp=0.01 gana por no sobreajustar al dip pandémico). Es padecimiento-dependiente — ponderar folds recientes más alto o excluir COVID, especialmente para Depresión.

## Comportamiento de cp por padecimiento

- **Depresión:** cp=0.03-0.05 sobreajusta a COVID (Fold 4 RMSE 0.62-0.77 vs cp=0.01: 0.41)
- **Alzheimer:** cp=0.03 competitivo, gana en algunos estados (Sonora mujeres: 0.0331 vs cp=0.01: 0.0336)
- Esto refuerza la idea de **grids diferenciados por padecimiento**

## Nota sobre logging de CV

"No se obtuvo ningún RMSE válido" = la combinación SÍ produjo RMSE pero no mejoró el best actual. No es un bug, es logging confuso.

# EpiForecast-MX — Lecciones Clave

1. **Tasas > conteos absolutos:** Modelar tasas por 100K normaliza escala entre estados (CDMX ~9M vs Colima ~730K), estabiliza L-BFGS y produce RMSE comparable. CDMX ya no domina peores RMSE por población.

2. **Log-transform estabiliza Depresión:** `log(1+y)` comprime picos y estabiliza varianza multiplicativa. Depresión CV ~0.5-0.6, rango y pasa de 0-12.9 (tasa) a 0-2.6 (log-space).

3. **Additive vs Multiplicative depende del log-transform:** Sin log: multiplicative gana 94%. CON log: additive gana ~67% para Alzheimer. Al comprimir escala, estacionalidad deja de ser proporcional al nivel → additive. Decisión padecimiento-dependiente.

4. **ML tradicional falló para multi-step:** Random Forest y XGBoost generan acumulación progresiva de error en predicción recursiva. Prophet maneja horizontes largos nativamente.

5. **Data leakage fue crítico:** Modelos iniciales descartados por fugas de datos.

6. **SINAVE reporta tasas, no conteos crudos.**

7. **Calidad de datos requiere limpieza exhaustiva:** Normalización entidades (DF → CDMX), corrección week shifting, conversión acumulados→incrementos, corrección negativos con IQR.

8. **Análisis estatal > regional:** IMSS prefiere modelos por estado individual según retroalimentación de médicos.

9. **COVID distorsiona fuertemente:** Holiday de 913 días para que Prophet no ajuste tendencia al dip pandémico. Depresión tuvo cambio estructural permanente post-COVID.

10. **cp varía por padecimiento:** Depresión: cp alto sobreajusta a COVID. Alzheimer: cp=0.03 competitivo. → Grids diferenciados.

11. **Series con 100% zeros:** BCS Alzheimer RMSE=0 (engañoso). Series >95% zeros no deberían entrenarse.

12. **Población constante en dataset:** Mismo censo 2013-2026, inútil como regresor. Solo para normalizar/desnormalizar.

# EpiForecast-MX — Benchmark Externo (Equipo 16, Depresión Nacional)

Un equipo previo del Tec trabajó Depresión a nivel nacional (serie única, conteos absolutos, sin desglose estado/sexo). Referencia del "techo" alcanzable con Prophet optimizado:

## Comparación de modelos (1 año, Test MAPE)

- Holt-Winters: 14.7% | SARIMA: 13.6% | SARIMAX: 11.5%
- XGBoost recursivo: 14.8% | XGBoost+COVID: 14.1% | XGBoost Walk-Forward: 11%
- **Prophet Simple: 10.3%** | Prophet+COVID: 11.4%

## Tras optimización profunda de Prophet

| Modelo | 52W MAPE | 104W MAPE | Train MAPE |
|---|---|---|---|
| Prophet Simple (20 Fourier) | **9.75%** | 18.2% | 24.2% |
| Prophet + COVID regresor | 10.4% | **9.97%** | 14.1% |
| Prophet + Feriados MX | 10.3% | 17.8% | 23.8% |

## Hallazgos aplicables a EpiForecast-MX

1. **20 Fourier anuales** = mejora más impactante. Default Prophet (10) es insuficiente para Depresión. Desactivar `yearly_seasonality` y agregar custom con `fourier_order=20`. **Directamente aplicable.**

2. **additive + cp=0.01** confirmado óptimo — coincide con nuestros hallazgos.

3. **Feriados MX redundantes** con 20 Fourier anuales — la estacionalidad rica ya captura esos patrones.

4. **COVID regresor:** A 1 año, marginal (10.4% vs 9.75%). A 2 años, CRÍTICO (MAE se reduce a la mitad: 526→270). Trade-off sesgo-varianza.

5. **"Zona de peligro" 3-6 meses:** Prophet inestable con MAPE ~40% en 100-200 días, se recupera después. Podría explicar RMSE altos en nuestros Fold 2/3.

6. **XGBoost recursivo** confirma acumulación de error. Walk-forward (reentrenamiento) mejora 14%→11%, pero Prophet simple ya da 10.3%.

## Implicación directa

Agregar `fourier_order` al grid: `yearly_seasonality=False` + `add_seasonality('yearly', 365.25, fourier_order=N)` con N en [10, 15, 20]. Bajo riesgo, alto impacto. Fourier óptimo probablemente varía: Depresión 15-20, Alzheimer 5-10.

# EpiForecast-MX — Roadmap y Reglas de Trabajo

## Mejoras al modelo (por prioridad)

1. **🔴 Fourier anual personalizado:** `yearly_seasonality=False` + `add_seasonality('yearly', 365.25, fourier_order=N)` con N en [10, 15, 20]. Benchmark Equipo 16 sugiere alto impacto para Depresión.

2. **Ponderación de folds en CV:** Fold 1 (COVID) es 56% peor que Fold 4, sesga hacia rigidez excesiva. Ponderar recientes o excluir COVID.

3. **Changepoints forzados post-COVID (Depresión):** Cambio estructural permanente; holiday con ventana fija no lo captura. Opciones: más n_changepoints o changepoint forzado en 2020-03-23.

4. **Grid separado por padecimiento:** Depresión necesita más flexibilidad (cp=0.03), Alzheimer/Parkinson funcionan con cp=0.01. Fourier order también debería diferir.

5. **Filtrar series vacías:** Excluir series >95% zeros (ej. BCS Alzheimer, RMSE=0 engañoso).

6. **Ensemble Prophet + XGBoost:** Prophet para tendencia/estacionalidad, XGBoost para residuos.

7. **DeepAR+ (AWS):** Información conjunta entre múltiples series.

8. **CV extendida:** Horizonte de 24 a 52 semanas para estacionalidad anual.

## Proyecto y publicación

- Dos artículos científicos en desarrollo → congresos Estocolmo, Portugal
- Variables adicionales: rangos de edad + mortalidad (coordinación Secretaría de Salud)
- Posible análisis de costos farmacológicos

## Instrucciones para trabajar con el código

- `y` de Prophet = **log(1 + tasa por 100K)**, NO conteos
- Pipeline: conteo → ÷población ×100K → log(1+y) → Prophet → exp-1 → ×población ÷100K → conteos
- Respetar segmentación: padecimiento × estado × sexo
- Periodos atípicos (COVID-19, 2016) afectan métricas y residuales
- **Depresión es prioridad #1** — 100% de peores modelos. Fourier 20 es la mejora más prometedora
- Frecuencia semanal (`W` en pandas)
- Cada `.pkl` tiene `.csv` sidecar (incluye `Total` para desnormalización, `y_original` para referencia)
- Commits y docs en **español**
- Paleta cromática IMSS para visualizaciones