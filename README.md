<p align="center">
  <img src="https://images.seeklogo.com/logo-png/7/1/imss-logo-png_seeklogo-70988.png" alt="IMSS Logo" width="110"/>
</p>

<h1 align="center">EpiForecast-MX</h1>

> WCP 2026 e-poster (#3134) presented in September 2026; its working file lives outside the repository.

<p align="center">
  <strong>Epidemiological Intelligence Platform for Disease Forecasting in Mexico</strong>
</p>

<p align="center">
  <em>Capstone Project - Master's in Applied Artificial Intelligence - Tecnologico de Monterrey</em><br>
  <em>In collaboration with the Instituto Mexicano del Seguro Social (IMSS)</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat&logo=python&logoColor=white" alt="Python 3.12"/>
  <img src="https://img.shields.io/badge/Models-Prophet_%2B_DeepAR_%2B_Ensemble_%2B_Stacking-orange?style=flat" alt="Multi-Model"/>
  <img src="https://img.shields.io/badge/GPU-SageMaker_T4-76b900?style=flat&logo=nvidia&logoColor=white" alt="GPU SageMaker"/>
  <img src="https://img.shields.io/badge/Tests-3249-brightgreen?style=flat" alt="3249 Tests"/>
  <img src="https://img.shields.io/badge/DVC-S3-945DD6?style=flat&logo=dvc&logoColor=white" alt="DVC + S3"/>
</p>

---

## Project Description

**EpiForecast-MX** is a production-grade epidemiological intelligence platform developed in partnership with the **Instituto Mexicano del Seguro Social (IMSS)** to forecast the weekly incidence of thirty-three reportable conditions across Mexico's 32 states with a 52-week horizon.

The platform uses a **polymorphic Factory pattern** to support multiple forecasting engines (**Prophet**, **DeepAR**, **Ensemble**, and **Stacking**), ensuring scalability and ease of integration for future algorithms. DeepAR training runs on AWS SageMaker with NVIDIA T4 GPUs for fast iteration. The Ensemble model combines Prophet with XGBoost residual correction, while the Stacking model uses Prophet + ETS + LightGBM experts with a Ridge meta-learner for optimal weight combination.

| Condition | ICD-10 | Challenge |
|-----------|--------|-----------|
| Depression | F32 | High baseline, seasonal patterns, COVID disruption |
| Parkinson's disease | G20 | Low incidence, volatile per-state series |
| Alzheimer's disease | G30 | Aging-population trends, underreporting |
| Dengue *(extra deliverable)* | A97 | Vector-borne, ~4-5 year epidemic cycle, near-zero off-season series |
| Generic runner releases (29) | various | Obesity, eating disorders, diabetes, cardiovascular, bulletin radar group and seventeen cancers; see the registry |

Four conditions (Depression, Parkinson's, Alzheimer's and Dengue) run on the legacy multi-model pipeline (333 neuro models plus 99 Dengue series); see [Dengue (Fourth Condition)](#dengue-fourth-condition-extra-deliverable). Twenty-nine more are published from sealed releases of the generic runner (`src/epiforecast/runner/`). The registry (`config/padecimientos.yaml`) decides which ones are public. Releases that failed the 2025 acceptance gate are published with the seasonal control by express order of the author, never as validated. Publication history: `docs/C7_7_PUBLICACION_OBESIDAD.md` through `docs/C7_12_CANCER.md`.

---

## Key Features

- **Multi-Model Orchestration** -- Seamlessly switch between Prophet, DeepAR, Ensemble, and Stacking via central configuration (`config/base.yaml`) or CLI arguments.
- **GPU Training on SageMaker** -- DeepAR trains on `ml.g4dn.xlarge` (NVIDIA T4, CUDA 12.4) via a single `make train-sagemaker` command. Local CPU/MPS training also supported.
- **EPI Interactive Console** -- AI-powered CLI (`python epi.py`) with natural-language command translation (Gemini), local KnowledgeBase for data queries, Rich TUI with IMSS institutional branding, risk-based command approval, session statistics, and persistent command history.
- **End-to-End ML Pipeline** -- Automated from PDF scraping (SINAVE bulletins) through INEGI demographic mapping to forecast charts and HTML reports.
- **Model Comparison Engine** -- High-contrast professional charts comparing Real vs. Prophet vs. DeepAR vs. Ensemble vs. Stacking performance across all states and conditions.
- **Weekly Validation** -- `scripts/genera_validacion_semanal.py` pairs each forecast with the bulletin value of the same week after the release cut; since round W37 it reports the pairs without scoring them.
- **Out-of-Sample Model Selection** -- Production engines for the 333 neuro series are selected out of sample on the W28-W37 window (round W37, criterion `H3 W28–W37`). Selection metrics are a selection diagnostic, not a published evaluation. Current distribution: Ensemble 109, Stacking 107, Prophet 78, DeepAR 39. `scripts/reselect_motor_2026.py` is the earlier in-sample selector (2026-04-30) and must not be rerun over the release table. The Tableau dataset exposes `modelo_productivo`.
- **Production Model Table** -- Excel with 3 sheets (Produccion, Detalle Semanal, Análisis Visual); 432 rows: 333 neuro production models plus 99 Dengue series.
- **Overfitting and Data Leakage Detection** -- Train metrics (RMSE, SMAPE) computed in-sample for all 4 models. HTML report shows diagnostic badges: Overfitting (test/train SMAPE ratio) and Leakage (suspiciously low train SMAPE).
- **Hybrid Fallback** -- Zero-incidence and low-confidence (<5 cases/52 weeks) state models automatically defer to regional aggregates to ensure 100% forecast coverage. Integer-rounded predictions (no fractional cases).
- **MLflow Experiment Tracking** -- Optional integration logs all training runs (metrics, hyperparameters, elapsed time) to MLflow. Non-intrusive: no-op when not installed. Install with `pip install -e ".[mlflow]"`, browse with `mlflow server --backend-store-uri ./mlruns`.
- **Automated Bulletin Pipeline** -- GitHub Actions scrapes new SINAVE bulletins Tuesday to Thursday at 20:00 UTC (plus manual dispatch), processes PDFs with Camelot, and merges into the consolidated dataset.
- **Cross-Validation** -- Prophet uses weighted time-series CV (4 folds, progressive weights). DeepAR uses multi-series CV with early stopping.
- **IMSS Institutional Branding** -- All visualizations and reports follow official IMSS 2026 chromatic and styling guidelines.

---

## EPI Interactive Console

The project includes a full-featured interactive CLI (`python epi.py`) built with Rich for terminal UI and Gemini for natural language understanding:

```
$ python epi.py
```

**Capabilities:**
- **Natural language commands** -- Type "entrena los modelos" or "dame las metricas de depresion" instead of remembering Makefile targets.
- **Local KnowledgeBase** -- Answers questions about the project data (cases, states, weeks, models, team members) using real cached data, without calling any external API.
- **Gemini fallback** -- When the local KB can't answer, queries the Gemini API with enriched project context.
- **Dashboard** -- Real-time overview panel with data stats, model inventory, forecast metrics, and session health.
- **Data explorer** -- Browse boletin data filtered by padecimiento, entidad, or sexo with inline Unicode bar charts.
- **Model browser** -- Paginated view of all 333 production models with SMAPE color coding and diagnostic badges.
- **Forecast viewer** -- Sparkline visualizations of 52-week forecast horizons per model.
- **Risk-based approval** -- Commands are color-coded by risk level (safe/modify/destructive) and require confirmation before execution.
- **Typo correction and fuzzy matching** -- Handles common Spanish misspellings and suggests the closest valid command.
- **Session statistics** -- Tracks commands run, success/failure rate, total duration, and uptime.
- **Persistent history** -- Last 100 commands saved in `.epi_history.json`.

---

## Project Structure

```
EpiForecast-MX/
|
|-- aws/                          # AWS SageMaker infrastructure
|   |-- Dockerfile                #   Docker image (PyTorch + CUDA + GluonTS)
|   |-- requirements_sagemaker.txt#   Container dependencies
|   +-- sagemaker_launcher.py     #   ECR build + Training Job launcher
|
|-- config/                       # Unified YAML configuration
|   |-- base.yaml                 #   Active model, paths, disease settings
|   |-- padecimientos.yaml        #   Disease registry: profiles, lifecycle, channels, releases
|   |-- engines/, evaluation/     #   Runner engines and selection policies
|   |-- publication/              #   Per-disease prospective gates and release pointers
|   |-- models/                   #   Per-algorithm hyperparameters
|   |   |-- prophet.yaml          #     Prophet HP grids, seasonality, regime changes
|   |   |-- deepar.yaml           #     DeepAR epochs, layers, dropout, context length
|   |   |-- ensemble.yaml         #     Ensemble (Prophet + XGBoost) hyperparameters
|   |   +-- stacking.yaml         #     Stacking experts + meta-learner hyperparameters
|   |-- data/                     #   Preprocessing parameters
|   |-- features/                 #   Feature engineering parameters
|   |-- visualization/            #   Plot styling (IMSS palette)
|   +-- infrastructure/           #   Logging configuration
|
|-- src/epiforecast/              # Core Python package
|   |-- models/                   #   Factory pattern + model implementations
|   |   |-- base.py               #     Abstract ForecastModel interface
|   |   |-- factory.py            #     create_model() + @register_model decorator
|   |   |-- prophet/              #     ProphetForecaster + cross-validator + tuner + data_prep
|   |   |-- deepar/               #     DeepARForecaster + cross-validator
|   |   |-- ensemble/             #     EnsembleForecaster (Prophet + XGBoost) + helpers
|   |   |-- stacking/             #     StackingForecaster (Prophet + ETS + LightGBM + Ridge)
|   |   +-- nbglm/                #     NB-GLM (suspended for Dengue since round W37)
|   |-- data/                     #   PDF extraction, INEGI ingestion, preprocessing
|   |-- evaluation/               #   Metrics (RMSE, MAE, MAPE, SMAPE, MASE)
|   |-- visualization/            #   IMSS publication-quality charts and reports
|   |-- features/                 #   Demographic feature engineering
|   |-- utils/                    #   Configuration loader, path management, helpers
|   |-- pipelines/                #   Pipeline base
|   |-- runner/                   #   Generic runner: datasets, rolling-origin CV, engines, sealed releases
|   |-- publication/              #   Publication: views, prospective gates, consolidated-file checks
|   +-- registry.py               #   Disease registry (lifecycle, channels, backends)
|
|-- epi_modules/                  # EPI interactive console modules
|   |-- engine.py                 #   EpiEngine (Makefile parsing, Gemini translation, execution)
|   |-- intent.py                 #   Intent classifier, typo correction, fuzzy matching
|   |-- theme.py                  #   IMSS Rich theme (PANTONE verde, dorado, guinda)
|   |-- features/                 #   Console feature modules
|   |   |-- ai_chat.py            #     KnowledgeBase local + Gemini fallback chat
|   |   |-- dashboard.py          #     Multi-panel Rich Layout dashboard
|   |   |-- data_cache.py         #     Lazy-loading project data cache
|   |   |-- data_explorer.py      #     Interactive boletin data browser
|   |   |-- forecast_viewer.py    #     Forecast sparkline viewer
|   |   |-- knowledge_base.py     #     Local fact database (no external AI)
|   |   +-- model_browser.py      #     333-model paginated browser
|   +-- views/                    #   Console view modules
|       |-- approval.py           #     Risk-based command approval gate
|       |-- banner.py             #     ASCII art welcome banner
|       |-- common.py             #     Logs, pipeline status, session stats, scripts listing
|       |-- health.py             #     System health dashboard
|       |-- help_menu.py          #     Multi-section help menu
|       +-- targets.py            #     Makefile target browser with risk categorization
|
|-- scripts/                      # CLI entry points
|   |-- entrena.py                #   Main training orchestrator
|   |-- entrena_sagemaker.py      #   SageMaker entry point (adapts /opt/ml/ environment)
|   |-- predice.py                #   Forecast generation (52 weeks, denormalized)
|   |-- compara_modelos.py        #   Visual model comparison
|   |-- compara_metricas.py       #   Metrics comparison (Excel + HTML with diagnostics)
|   |-- avance5_modelo_final.py   #   Ensemble training + visualization
|   |-- genera_reporte.py         #   HTML results report
|   |-- genera_bitacora.py        #   Modeling log (Prophet v1-v6)
|   |-- genera_reporte_avance5.py #   Avance 5 report (Markdown + 18 charts)
|   |-- genera_tabla_produccion.py#   Production model table (333 models, SMAPE selection)
|   |-- genera_validacion_semanal.py#  Weekly validation: Real vs Forecast (HTML report)
|   |-- compliance_check.py       #   Code quality audit (Cookiecutter DS + SOLID + MLOps)
|   |-- build_tableau.py          #   Tableau dataset builder
|   |-- patch_train_metrics.py    #   Patch CSVs with train metrics (no retraining)
|   |-- excel_produccion_charts.py#   Embedded charts for production Excel
|   |-- excel_produccion_fmt.py   #   IMSS 2026 Excel formatting
|   |-- genera_paneles_barras_prod.py   # Individual bar charts for production model
|   |-- genera_paneles_barras_semana.py # Weekly bar pair charts (2x2 grids)
|   |-- genera_paneles_zoom.py    #   Zoomed panel charts from 2020
|   |-- get_dataset.py            #   RAW data download (SINAVE)
|   |-- filtra_padecimiento.py    #   Disease filter
|   |-- limpieza_dataset.py       #   Data cleaning
|   |-- realiza_prep.py           #   Feature engineering
|   |-- descarga_inegi.py         #   INEGI demographic download
|   |-- mapea.py                  #   State-INEGI mapping
|   |-- scrape_boletines.py       #   SINAVE bulletin scraper (Selenium)
|   |-- ci_process_boletines.py   #   CI/CD bulletin processing (Camelot)
|   +-- publish_gsheets.py        #   Google Sheets publisher
|
|-- tests/                        # Test suite (176 test files, 3,249 tests; last CI 79.0%, gate at 70%)
|   |-- unit/                     #   Unit tests for all modules
|   +-- integration/              #   End-to-end pipeline tests
|
|-- data/                         # Data stages (managed by DVC)
|   |-- raw/                      #   Original SINAVE data
|   |-- interim/                  #   Cleaned intermediate data
|   +-- processed/                #   Final datasets (data_inegi_*.csv)
|
|-- models/                       # Trained model artifacts (.pkl, managed by DVC)
|   |-- prophet/                  #   Prophet models per disease/state/sex (333 models)
|   |-- deepar/                   #   DeepAR models per disease/state/sex (333 models)
|   |-- ensemble/                 #   Ensemble (Prophet+XGBoost) models (333 models)
|   +-- stacking/                 #   Stacking (Prophet+ETS+LightGBM+Ridge) models (333 models)
|
|-- reports/                      # Generated outputs
|   |-- forecasts/                #   Forecast CSVs, comparison charts, ensemble PNGs
|   |-- figures/                  #   EDA and analysis plots (ModeloFinal/ for Avance 5)
|   |-- ProdDetails/              #   Production Excel, weekly validation HTML
|   +-- docs/                     #   PDF reports
|
|-- .github/workflows/            # CI/CD
|   |-- ci.yml                    #   Quality gate (lint + typecheck + tests); integration is manual-only
|   |-- scrape_boletines.yml      #   Bulletin scraping (Tue-Thu)
|   |-- process_boletines.yml     #   Bulletin PDF processing (Camelot)
|   +-- gsheets.yml               #   Google Sheets publishing
|
|-- epi.py                        # EPI interactive console entry point
|-- Makefile                      # MLOps orchestration (~80 targets)
+-- pyproject.toml                # Dependencies, Ruff, Mypy, Pytest config
```

---

## Setup

### Prerequisites

- Python 3.12
- Ghostscript (for PDF extraction): `brew install ghostscript` (macOS) or `sudo apt-get install ghostscript` (Linux)
- AWS CLI configured (for SageMaker and DVC/S3)
- Docker (for SageMaker training)

### Installation

```bash
# Clone the repository
git clone https://github.com/EpiForecastMX/EpiForecast-MX.git
cd EpiForecast-MX

# Create virtual environment and install dependencies
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Optional: install DVC for data versioning
pip install -e ".[dvc]"

# Optional: install MLflow for experiment tracking
pip install -e ".[mlflow]"

# Pull data from S3 (requires AWS credentials)
make data-pull
```

Or use the automated setup:
```bash
make setup        # macOS (installs Ghostscript + deps + data pull)
make setup-linux  # Linux/WSL
```

---

## Usage

### 1. EPI Interactive Console

```bash
python epi.py
```

The EPI console accepts natural language in Spanish or English and translates it to Makefile targets. Examples:

```
epi > entrena todos los modelos     # -> make train-all
epi > dame las metricas de depresion # -> answers from local KnowledgeBase
epi > que semana epidemiologica es?  # -> current epi week from real data
epi > quien es Jarcos?               # -> team member info
epi > dashboard                      # -> real-time project overview
epi > datos alzheimer                # -> boletin data filtered by condition
epi > modelos                        # -> browse 333 production models
epi > ayuda                          # -> full help menu
```

### 2. Data Preprocessing

```bash
# Full preprocessing pipeline (download, filter, clean, transform, INEGI mapping)
make preprocess

# Individual steps
make get-dataset                                    # Download RAW data
make filter ARGS="padecimiento.tipo='Alzheimer'"    # Filter by condition
make clean                                          # Clean dataset
make transform                                      # Feature engineering
make get-inegi                                       # Download INEGI demographics
make mapper                                          # Map states to INEGI
```

### 3. Training

```bash
# Train using active model from config/base.yaml
make train

# Train specific models
make train-prophet    # Prophet (CPU, parallel with joblib)
make train-deepar     # DeepAR (local CPU/MPS)
make train-ensemble   # Ensemble (Prophet + XGBoost)
make train-stacking   # Stacking (Prophet + ETS + LightGBM + Ridge)
make train-all        # All 4 models sequentially

# Train Ensemble with comparison visualizations
make avance5                                              # All conditions
make avance5 ARGS="padecimiento.tipo='Alzheimer'"         # Single condition

# Train DeepAR on AWS SageMaker with GPU (recommended for speed)
make train-sagemaker          # Build Docker image + launch on ml.g4dn.xlarge
make train-sagemaker-build    # Only build + push image to ECR
make train-sagemaker-local    # Test locally with Docker
make train-sagemaker-parallel # 3 parallel jobs (1 per condition)
make train-sagemaker-fast     # Build + 3 parallel jobs
```

After SageMaker training completes, download the trained models:
```bash
aws s3 sync s3://epiforecast-mx-data/training/<JOB_NAME>/output/ ./models/deepar/
```

### 4. Prediction and Tableau

```bash
# Generate 52-week forecasts for all 4 models
make predict-all

# Or generate forecasts for a single model
make predict ARGS="modelo_activo='prophet'"
make predict ARGS="modelo_activo='deepar'"
make predict ARGS="modelo_activo='ensemble'"
make predict ARGS="modelo_activo='stacking'"

# Build Tableau dataset (SMAPE-based model selection + per-model metrics)
make tableau
```

The Tableau dataset (`data/processed/tableau.csv`) includes:
- `yhat`: Best prediction (integer-rounded, selected by lowest SMAPE per group)
- `modelo_productivo`: Name of the winning model per (condition, state, mode)
- Per-model predictions: `yhat_prophet`, `yhat_deepar`, `yhat_ensemble`, `yhat_stacking` (integer-rounded)
- Per-model metrics: `rmse_{model}`, `mae_{model}`, `mape_{model}`, `smape_{model}`, `mase_{model}`
- Productive model metrics: `rmse`, `mae`, `mape`, `smape`, `mase`

The production Excel (`reports/ProdDetails/tabla_333_modelos_produccion.xlsx`) has 3 sheets (the third, Análisis Visual, holds embedded charts):

**Sheet 1 - Produccion** (432 rows x 55 columns: 333 neuro plus 99 Dengue):
- Per-model metrics (RMSE, MAE, SMAPE, MASE) for all 4 algorithms
- `casos_52_semanas_futuro`: Total projected cases for 52-week horizon (integer)
- `smape_prod`, `mase_prod`, `rmse_prod`, `mae_prod`: Metrics of the selected model (recomputed after re-selection)
- `overfitting`: Diagnostic (Alto >2x, Moderado >1.3x, OK) based on smape_test/smape_train
- `leakage`: Diagnostic (Sospechoso if smape_train < 0.5%, else OK)
- `casos_prev_52_semanas_real / _pronos`: Historical 52-week comparison (integer)
- `precision_historica`: Forecast/real ratio as percentage
- `pron_sem_previa / realidad_sem_previa`: Last week values for live validation
- `modelo_produccion`, `tipo_modelo`, `region_asignada`, `justificacion`
- **2026 reality audit columns** (added by `reselect_motor_2026.py`): `n_semanas_real_2026`, `total_real_2026`, `smape_2026_{prophet,deepar,ensemble,stacking}`, `smape_real_2026_ganador`, `motor_anterior`, `criterio_seleccion`, `semana_validacion`

**Sheet 2 - Detalle Semanal** (432 rows x 163 columns):
- 52 columns `real_sem_N`: Actual weekly incidence
- 52 columns `pron_sem_N`: Model backtest prediction per week
- 52 columns `acierto_sem_N`: Forecast accuracy percentage per week

### 5. Comparison, Reports, and Validation

```bash
# Generate high-contrast comparison charts (Real vs all 4 models)
make compare

# Generate metrics comparison (Excel + HTML report with Overfitting/Leakage badges)
make compare-metrics

# Generate production model table (333 models, CV-based first-pass selection)
make tabla-produccion

# Legacy in-sample re-selector (superseded by the W37 out-of-sample selection; do not rerun on the release table)
# python3 scripts/reselect_motor_2026.py

# Generate HTML results report
make report

# Generate modeling log (Prophet iterations v1-v6)
make bitacora

# Generate Avance 5 report (Markdown + 18 charts + production CSV with 333 models)
make reporte-avance5

# Code quality audit (Cookiecutter DS structure + SOLID + MLOps compliance)
python scripts/compliance_check.py
```

Comparison charts are saved in `reports/forecasts/comparacion_modelos/` using CDMX timezone (UTC-6) for audit logs. The Avance 5 report generates `reports/ProdDetails/avance5_modelo_final.md`, `reports/ProdDetails/tabla_333_modelos_produccion.xlsx` (Excel with 3 sheets), and 18 analysis charts in `reports/figures/ModeloFinal/`.

#### Prospective Out-of-Sample Validation (frozen forecast)

> **Read this before trusting `smape_real_2026`.** The engine-selection metric is
> **in-sample**: production models are refit on the full series (2026 H1 included)
> and scored on their own in-sample fit. To measure honest out-of-sample skill we
> freeze today's forecast and compare it against bulletins that arrive **later**.
> Full audit: `docs/research/hallazgos/DENGUE_AUDITORIA_LEAKAGE.md`.

```bash
# Freeze the current productive forecast (future tail only, ds > cutoff = unseen).
# Covers the 4 legacy conditions; runner releases use their own frozen prospective gates (prospective_week.py).
make congela-pronostico

# Validate the frozen forecast against the current bulletin (honest OOS SMAPE/MAE).
# Only scores weeks AFTER the freeze cutoff (genuinely unseen when frozen).
make valida-prospectivo
```

`freeze` writes `reports/ProdDetails/congelado/forecast_congelado_<YYYYMMDD>.csv`
plus the `forecast_congelado_latest.txt` pointer; `validar` writes
`reports/ProdDetails/validacion_prospectiva.html` (+ `.csv`).

**Golden rule (do not forget):** after each new bulletin, run `make valida-prospectivo`
**before** retraining. Retraining first makes the newly arrived week becomes in-sample again and the test is lost. **Do not
re-freeze every week** (that resets the experiment); re-freeze only to set a new
baseline. Decision rule: if OOS SMAPE stays close to in-sample, the selection is sound;
if OOS exceeds ~2x in-sample, switch selection to `smape_prod` (rolling CV) or to a
locked forecast trained through end-2025.

### 6. Code Quality

```bash
# Full quality gate (lint + typecheck + tests)
make quality

# Individual checks
make lint          # Ruff check (format + lint rules)
make format        # Auto-format code
make typecheck     # mypy strict type checking
make test-fast     # Fast unit tests only
```

### 7. Data Versioning (DVC)

```bash
make data-pull       # Download data from S3
make data-push       # Upload data to S3
make models-push     # Version and upload trained models
make s3-sync         # Quick sync CSVs + forecasts to S3 (no DVC)
make data-weekly     # Add + commit new weekly bulletin data
make update-week     # disabled: aborts in preflight (see section 8)
```

### 8. Weekly Step

`make update-week` is permanently guarded and aborts in preflight (`scripts/actualiza_semanal.sh`).
The weekly step has three lanes, and none of them publishes a partial week:

1. **Legacy conditions** (Depression, Parkinson, Alzheimer, Dengue) through the v5 producer kept
   outside the repository.
2. **The 29 runner releases** through `make semana-revisa`, `make semana-observa PDF=… SALIDA=… [WRITE=1]`,
   `python -m scripts.paso_semanal consolida` and `make semana-vistas N=… FE=…`, failing closed for all
   if any one fails. `consolida` keeps the base byte for byte, rejects a superseded or altered base and
   runs `revisa_consolidado` (parity of every published condition).
3. **The bulletin radar** (`boletin.html`) through `scripts/boletin_semana.py` in the dashboard repo.

The full procedure lives in the `padecimiento-epiforecast` skill (`references/paso_semanal.md`).
Historical note: the 11-step `update-week` refresh and the P1/P1b W33 publication (2-Sep-2026) are
documented in `CLAUDE.md` and the git history.

> **Before retraining on a new bulletin, run `make valida-prospectivo`** to score the frozen forecast
> against the just-arrived weeks while they are still genuinely out-of-sample.

### Current Data Snapshot

- **Published cut:** W42/2026 for the four legacy conditions and the bulletin radar; the 29 runner
  releases observe through 2026-W41 (their 52-week horizon runs 2026-W42 to 2027-W41). A fail-closed
  parity rule forbids mixed public cuts.
- **Knowledge base:** about 260 KB (333 neuro production models, a `dengue` section, 26 stats keys,
  6 bulletin sections); each runner condition ships its own `knowledge.json` under
  `publication/<id>/<release>/` in the dashboard repo.
- **Forecast horizon:** 52 weeks ahead for every published condition.

---

## Architecture

### Factory Pattern (SOLID)

All models implement the `ForecastModel` abstract interface:

```python
class ForecastModel(ABC):
    def fit(self, train_data: pd.DataFrame) -> None: ...
    def predict(self, horizon: int) -> pd.DataFrame: ...
    def cross_validate(self, data: pd.DataFrame) -> dict[str, float]: ...
    def save(self, path: Path) -> None: ...
    def load(self, path: Path) -> None: ...
    def get_params(self) -> dict[str, Any]: ...
    def run(self) -> tuple[Any, dict, dict]: ...
```

Models register themselves with `@register_model("name")` and are instantiated via `create_model(name, **kwargs)`. This allows transparent switching between algorithms without modifying pipeline code. Currently registered models: `prophet`, `deepar`, `ensemble`, `stacking`, `nbglm` (the Negative-Binomial GLM + Fourier + El Niño/ONI engine, suspended for Dengue since round W37; see the Dengue section below). The generic runner registers its own engines (`src/epiforecast/runner/engines/`).

### Prophet

- Time-series cross-validation with 4 folds and progressive weights (recent folds weighted higher).
- Per-condition hyperparameter grids optimized over 297+ model runs.
- Custom yearly seasonality (Fourier order 10), COVID pandemic holiday, regime-change holidays.
- Hybrid fallback: low-incidence states defer to regional aggregates.
- Runs on CPU with joblib parallelism.

### DeepAR

- GluonTS implementation with PyTorch backend.
- Multi-series training: 32 state series trained simultaneously for national-level models.
- Student-t distribution output (robust to outliers), early stopping (patience 15).
- Context length: 104 weeks (2 years), prediction length: 52 weeks.
- Population-normalized rates (per 100K inhabitants).
- Trains on AWS SageMaker `ml.g4dn.xlarge` (NVIDIA T4, CUDA 12.4) or locally on CPU/MPS.

### Ensemble (Prophet + XGBoost)

- Hybrid approach: Prophet captures trend and seasonality, XGBoost corrects residuals.
- XGBoost features: lag (1, 2, 4 weeks), rolling means (4, 8, 12 weeks), month, week of year.
- XGBoost hyperparameters tuned via temporal cross-validation on Prophet residuals.
- Operates on absolute counts (not population-normalized rates).
- Iterative future prediction: XGBoost feeds back its own predictions for multi-step horizons.
- Serialization: single pickle with both Prophet and XGBoost models + hyperparameters.

### Stacking (Prophet + ETS + LightGBM + Ridge)

- Three expert models generate out-of-fold (OOF) predictions independently:
  - **ProphetExpert**: Prophet with custom seasonality and COVID holidays.
  - **ETSExpert**: Exponential Smoothing (statsmodels) with additive trend and seasonality.
  - **LGBMExpert**: LightGBM with lag features (1-4 weeks) and rolling statistics.
- **Ridge meta-learner** learns optimal expert weights from OOF predictions (regularized, non-negative).
- Confidence intervals derived from expert prediction spread.
- Operates on absolute counts (not population-normalized rates).
- Configuration: `config/models/stacking.yaml`.

### Configuration

All configuration is managed via OmegaConf YAMLs in `config/`. The active model is controlled by `modelo_activo` in `config/base.yaml`. CLI overrides are supported:

```bash
python -m scripts.entrena modelo_activo='deepar' padecimiento.tipo='Alzheimer'
```

---

## Dengue (Fourth Condition, Extra Deliverable)

Beyond the three neurological/mental-health conditions, EpiForecast-MX incorporates **Dengue (ICD-10 A97)** as a fourth, vector-borne condition: an extra deliverable that exercises the platform's extensibility on a disease with fundamentally different dynamics (climate-driven seasonality, multi-year epidemic cycles, near-zero off-season series). Dengue is **fully in production**: trained, model-selected, served on the public site, and answered by the EpiBot assistant.

**Modeling decision (evidence-based).** Dengue is reported under the WHO 2009 classification across three severity tiers: non-severe (`A97.0`), with warning signs (`A97.1`), and severe (`A97.2`). A literature review concluded that incidence should be modeled as **total dengue (the three tiers aggregated)**, not as separate severity series: severe dengue is a tiny fraction of cases (~0.1-0.2% in the Americas), so per-severity series are sparse and near-zero; predictive skill comes from the autocorrelation and seasonality of the aggregate. Dengue is modeled as **absolute counts** (not population-normalized rates).

**Data: series 2018-2026 (~414 bulletins through 2026-W42).** A dedicated extractor parses the per-entity Dengue table from SINAVE bulletins (a separate page with its own layout), validated cell-by-cell against the printed `TOTAL` row:

- `src/epiforecast/data/extraction/dengue_extractor.py`: locates the table by ICD codes (`A97.0/A97.1/A97.2`), aggregates the three tiers per state and sex. Supports two WHO-2009 layouts: production 2020+ (12 columns) and historical 2018-W27..2019 (10 columns, `dengue_historico.py`).
- `scripts/extrae_dengue.py` / `scripts/merge_dengue.py`: batch extraction with a dataset-level audit, then an idempotent merge into the DVC-versioned consolidated dataset (13,248 Dengue rows through 2026-W42). `extrae_dengue --incremental` parses only bulletins not yet in the manifest (the weekly refresh path: seconds instead of re-reading every PDF).
- A separate WHO-1997 `A90/A91` series (2014-2018, confirmed-by-sex) is extracted for **context/EDA only** (`dengue_historico_a9091.py`) and does not feed the production pipeline.

**Cohort-aware modeling (neuro path untouched).** Dengue belongs to a "count-log" cohort (`utils.cohorts.is_count_log_cohort`): Prophet runs **with** `log_transform` and **without** rate normalization (the multiplicative trend otherwise collapses to ~0 when extrapolated), with a fixed `changepoint_prior_scale=0.05`, no COVID holiday, uniform CV weights, and **no regional fallback** (if a state has no transmission, it forecasts zero). The neurological flows stay byte-identical via `constants.NEURO_CONDITIONS` / `filter_neuro`.

**Production = DeepAR + Prophet.** NB-GLM was suspended in round W37 for recursive instability (45/99 W37 forecasts above 3× the historical maximum). Out-of-sample assignment on W28-W37: DeepAR 53 / Prophet 46; national = DeepAR. The leave-one-epidemic-out backtest result (NB-GLM SMAPE 52 vs Prophet+ENSO 76 vs plain Prophet 102) is kept as research evidence, not as a production claim. Ensemble and Stacking are excluded because their tree learners do not extrapolate the epidemic dynamic to 52 weeks (a seasonal-envelope guard, `models/forecast_guards.py`, caps them but they are never chosen).

**Horizon: 52 weeks, no multi-year projection.** The former 5-year NB-GLM band and the El Niño scenario were withdrawn from the public product in round W37 (`ENMIENDA_DENGUE_NBGLM_W37`, 13-Oct-2026): they reused the suspended recursive predictor and had no validation of their own.

**Live.** Public forecast page at **epiforecast.mx/dengue** (`dengue_forecast.json` + `dengue_serie.json` + showcase/EDA charts), and the **EpiBot** assistant answers Dengue questions (`answerDengue` handler, fed by a `dengue` section in `knowledge.json`). Per-engine error metrics from the W28-W37 selection window are a selection diagnostic and are not published; they stay in the review evidence.

```bash
# End-to-end Dengue pipeline
make dengue-extract            # parse A97.x tables from bulletins
make dengue-merge              # idempotent merge into the consolidated (+ DVC)
make dengue-prep               # filter -> clean -> transform -> INEGI map
make dengue-train-estatal MODELO=prophet   # (and deepar / ensemble / stacking)
make predict-all ARGS="padecimiento.tipo='Dengue' padecimiento.modelado_hibrido=False"
make dengue-produccion         # DeepAR/Prophet per-series selector
make dengue-web                # public charts + JSON + EpiBot knowledge.json
```

---

## CI/CD

La cola técnica vigente (separada de las bitácoras históricas) está en
[`docs/DEUDAS_VIGENTES.md`](docs/DEUDAS_VIGENTES.md).

GitHub Actions runs on pushes to `main` and `refactor/*`, pull requests to `main`, and a
weekly Monday 06:00 UTC schedule:

1. **Code Quality** (`ci.yml`): Ruff lint + format check + mypy type checking.
2. **Tests** (`ci.yml`): 3,249 collected tests; slow and integration tests are deselected.
   Coverage is declared by this job and enforced from the single canonical
   `[tool.coverage.report] fail_under = 70` setting. The current clean Ubuntu runner result
   is 2,687 passed, 496 skipped, 66 deselected, and 79.02% coverage (`main` run
   `42664206931`, `d715de54`). A skip ceiling of 497 makes any new omission an explicit decision.
3. **Integration Tests** (`ci.yml`): Legacy, manual-only (`workflow_dispatch`). It requires
   the sealed `runs/` chain, which is absent from clean runners, so scheduled, push, and PR
   workflows report this job as **skipped**, not as a misleading green integration check.
   Scheduled runs use a distinct concurrency group and are not cancelled by pushes to `main`.
4. **Bulletin Scraping** (`scrape_boletines.yml`): SINAVE bulletin download via Selenium, Tuesday to Thursday at 20:00 UTC plus manual dispatch.
5. **Bulletin Processing** (`process_boletines.yml`): Camelot PDF extraction and dataset consolidation.
6. **Google Sheets** (`gsheets.yml`): Publishes Tableau data to shared spreadsheet.

---

## Team

| Name | Role | Organization |
|------|------|--------------|
| Javier Augusto Rebull Saucedo | Technical lead and MLOps pipeline architect | Santander Bank US |
| Juan Carlos Pérez Nava | EDA, feature engineering, and Prophet base model | Instituto Mexicano del Seguro Social (IMSS) |
| Luis Gerardo Sánchez Salazar | Dashboard design, development, and optimization | Tesla |

---

## License

MIT
