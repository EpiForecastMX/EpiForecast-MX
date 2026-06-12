<p align="center">
  <img src="https://images.seeklogo.com/logo-png/7/1/imss-logo-png_seeklogo-70988.png" alt="IMSS Logo" width="110"/>
</p>

<h1 align="center">EpiForecast-MX</h1>

<p align="center">
  <strong>Epidemiological Intelligence Platform for Neurological Disease Forecasting in Mexico</strong>
</p>

<p align="center">
  <em>Capstone Project - Master's in Applied Artificial Intelligence - Tecnologico de Monterrey</em><br>
  <em>In collaboration with the Instituto Mexicano del Seguro Social (IMSS)</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat&logo=python&logoColor=white" alt="Python 3.12"/>
  <img src="https://img.shields.io/badge/Models-Prophet_%2B_DeepAR_%2B_Ensemble_%2B_Stacking-orange?style=flat" alt="Multi-Model"/>
  <img src="https://img.shields.io/badge/GPU-SageMaker_T4-76b900?style=flat&logo=nvidia&logoColor=white" alt="GPU SageMaker"/>
  <img src="https://img.shields.io/badge/Tests-907-brightgreen?style=flat" alt="907 Tests"/>
  <img src="https://img.shields.io/badge/DVC-S3-945DD6?style=flat&logo=dvc&logoColor=white" alt="DVC + S3"/>
</p>

---

## Project Description

**EpiForecast-MX** is a production-grade epidemiological intelligence platform developed in partnership with the **Instituto Mexicano del Seguro Social (IMSS)** to forecast the weekly incidence of neurological and mental-health conditions across Mexico's 32 states with a 52-week horizon.

The platform uses a **polymorphic Factory pattern** to support multiple forecasting engines (**Prophet**, **DeepAR**, **Ensemble**, and **Stacking**), ensuring scalability and ease of integration for future algorithms. DeepAR training runs on AWS SageMaker with NVIDIA T4 GPUs for fast iteration. The Ensemble model combines Prophet with XGBoost residual correction, while the Stacking model uses Prophet + ETS + LightGBM experts with a Ridge meta-learner for optimal weight combination.

| Condition | ICD-10 | Challenge |
|-----------|--------|-----------|
| Depression | F32 | High baseline, seasonal patterns, COVID disruption |
| Parkinson's disease | G20 | Low incidence, volatile per-state series |
| Alzheimer's disease | G30 | Aging-population trends, underreporting |
| Dengue *(extra deliverable)* | A97 | Vector-borne, ~4-5 year epidemic cycle, near-zero off-season series |

The three neurological/mental-health conditions are the core production cohort (333 models). **Dengue** was incorporated as a fourth, vector-borne condition with its own count-based pipeline — see [Dengue (Fourth Condition)](#dengue-fourth-condition--extra-deliverable).

---

## Key Features

- **Multi-Model Orchestration** -- Seamlessly switch between Prophet, DeepAR, Ensemble, and Stacking via central configuration (`config/base.yaml`) or CLI arguments.
- **GPU Training on SageMaker** -- DeepAR trains on `ml.g4dn.xlarge` (NVIDIA T4, CUDA 12.4) via a single `make train-sagemaker` command. Local CPU/MPS training also supported.
- **EPI Interactive Console** -- AI-powered CLI (`python epi.py`) with natural-language command translation (Gemini), local KnowledgeBase for data queries, Rich TUI with IMSS institutional branding, risk-based command approval, session statistics, and persistent command history.
- **End-to-End ML Pipeline** -- Automated from PDF scraping (SINAVE bulletins) through INEGI demographic mapping to forecast charts and HTML reports.
- **Model Comparison Engine** -- High-contrast professional charts comparing Real vs. Prophet vs. DeepAR vs. Ensemble vs. Stacking performance across all states and conditions.
- **Weekly Validation** -- Automated comparison of model forecasts against real SINAVE bulletin data for the most recent epidemiological week (`make tabla-produccion`).
- **Reality-Calibrated Model Selection** -- Production engine selection uses SMAPE on the most recent SINAVE Boletin weeks (canonical since 2026-04-30 via `scripts/reselect_motor_2026.py`): series with >=10 real 2026 weeks and >=10 cases pick the engine with lowest 2026 SMAPE; noisy series (<10 cases) default to Ensemble; series without recent reality keep the CV assignment. Engines within a 5% SMAPE band of the best are treated as tied and broken by MAE, so a noise-level margin does not flip the selection to an engine that tracks the signal worse. The Tableau dataset exposes `modelo_productivo`. Distribution shifts each bulletin (week 21: DeepAR 157, Prophet 124, Ensemble 90, Stacking 64). Audit trail in `reports/ProdDetails/auditoria_motores_2026.xlsx`.
- **Production Model Table** -- Excel with 2 sheets: (1) 333 production models with diagnostics, overfitting/leakage, precision historica, and weekly validation columns; (2) 52-week detail with real vs forecast vs % accuracy per week. IMSS 2026 styling.
- **Overfitting and Data Leakage Detection** -- Train metrics (RMSE, SMAPE) computed in-sample for all 4 models. HTML report shows diagnostic badges: Overfitting (test/train SMAPE ratio) and Leakage (suspiciously low train SMAPE).
- **Hybrid Fallback** -- Zero-incidence and low-confidence (<5 cases/52 weeks) state models automatically defer to regional aggregates to ensure 100% forecast coverage. Integer-rounded predictions (no fractional cases).
- **MLflow Experiment Tracking** -- Optional integration logs all training runs (metrics, hyperparameters, elapsed time) to MLflow. Non-intrusive: no-op when not installed. Install with `pip install -e ".[mlflow]"`, browse with `mlflow server --backend-store-uri ./mlruns`.
- **Automated Bulletin Pipeline** -- GitHub Actions scrapes new SINAVE bulletins daily, processes PDFs with Camelot, and merges into the consolidated dataset.
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
|   |   +-- stacking/             #     StackingForecaster (Prophet + ETS + LightGBM + Ridge)
|   |-- data/                     #   PDF extraction, INEGI ingestion, preprocessing
|   |-- evaluation/               #   Metrics (RMSE, MAE, MAPE, SMAPE, MASE)
|   |-- visualization/            #   IMSS publication-quality charts and reports
|   |-- features/                 #   Demographic feature engineering
|   |-- utils/                    #   Configuration loader, path management, helpers
|   +-- pipelines/                #   Pipeline base
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
|-- tests/                        # Test suite (55 files, 907 tests, 70%+ coverage)
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
|   |-- reports/                  #   Markdown reports and production CSV
|   +-- docs/                     #   PDF reports
|
|-- .github/workflows/            # CI/CD
|   |-- ci.yml                    #   Quality gate (lint + typecheck + tests)
|   |-- scrape_boletines.yml      #   Daily automated bulletin scraping
|   |-- process_boletines.yml     #   Bulletin PDF processing (Camelot)
|   +-- gsheets.yml               #   Google Sheets publishing
|
|-- epi.py                        # EPI interactive console entry point
|-- Makefile                      # MLOps orchestration (~55 targets)
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
git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
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

The production Excel (`reports/ProdDetails/tabla_333_modelos_produccion.xlsx`) has 2 sheets:

**Sheet 1 - Produccion** (333 rows x ~50 columns):
- Per-model metrics (RMSE, MAE, SMAPE, MASE) for all 4 algorithms
- `casos_52_semanas_futuro`: Total projected cases for 52-week horizon (integer)
- `smape_prod`, `mase_prod`, `rmse_prod`, `mae_prod`: Metrics of the selected model (recomputed after re-selection)
- `overfitting`: Diagnostic (Alto >2x, Moderado >1.3x, OK) based on smape_test/smape_train
- `leakage`: Diagnostic (Sospechoso if smape_train < 0.5%, else OK)
- `casos_prev_52_semanas_real / _pronos`: Historical 52-week comparison (integer)
- `precision_historica`: Forecast/real ratio as percentage
- `pron_sem_previa / realidad_sem_previa`: Last week values for live validation
- `modelo_produccion`, `tipo_modelo`, `region_asignada`, `justificacion`
- **2026 reality audit columns** (added by `reselect_motor_2026.py`): `n_semanas_real_2026`, `total_real_2026`, `smape_2026_{prophet,deepar,ensemble,stacking}`, `smape_real_2026_ganador`, `motor_anterior`, `criterio_seleccion`

**Sheet 2 - Detalle Semanal** (333 rows x 163 columns):
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

# Re-select productive engine using 2026 SINAVE Boletin reality (canonical)
python3 scripts/reselect_motor_2026.py

# Generate HTML results report
make report

# Generate modeling log (Prophet iterations v1-v6)
make bitacora

# Generate Avance 5 report (Markdown + 18 charts + production CSV with 333 models)
make reporte-avance5

# Code quality audit (Cookiecutter DS structure + SOLID + MLOps compliance)
python scripts/compliance_check.py
```

Comparison charts are saved in `reports/forecasts/comparacion_modelos/` using CDMX timezone (UTC-6) for audit logs. The Avance 5 report generates `reports/ProdDetails/avance5_modelo_final.md`, `reports/ProdDetails/tabla_333_modelos_produccion.xlsx` (Excel with 2 sheets: production summary + 52-week detail), and 18 analysis charts in `reports/figures/ModeloFinal/`.

#### Prospective Out-of-Sample Validation (frozen forecast)

> **Read this before trusting `smape_real_2026`.** The engine-selection metric is
> **in-sample**: production models are refit on the full series (2026 H1 included)
> and scored on their own in-sample fit. To measure honest out-of-sample skill we
> freeze today's forecast and compare it against bulletins that arrive **later**.
> Full audit: `docs/research/hallazgos/DENGUE_AUDITORIA_LEAKAGE.md`.

```bash
# Freeze the current productive forecast (future tail only, ds > cutoff = unseen).
# Covers all 4 conditions (neuro via tabla_333 + Dengue via produccion_dengue.csv).
make congela-pronostico

# Validate the frozen forecast against the current bulletin (honest OOS SMAPE/MAE).
# Only scores weeks AFTER the freeze cutoff (genuinely unseen when frozen).
make valida-prospectivo
```

`freeze` writes `reports/ProdDetails/congelado/forecast_congelado_<YYYYMMDD>.csv`
plus the `forecast_congelado_latest.txt` pointer; `validar` writes
`reports/ProdDetails/validacion_prospectiva.html` (+ `.csv`).

**Golden rule (do not forget):** after each new bulletin, run `make valida-prospectivo`
**before** retraining. The weekly pipeline retrains on the new data, so if you retrain
first, the newly arrived week becomes in-sample again and the test is lost. **Do not
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
make update-week     # End-to-end weekly sync (see section 8)
```

### 8. Weekly Update Flow (`make update-week`)

One-command, end-to-end weekly refresh (~6 minutes, **no retraining**) that keeps
the working copy, DVC artifacts and the public dashboard in lockstep with the
latest SINAVE bulletin ingested by the CI scraper. Delegates to
`scripts/actualiza_semanal.sh` and runs 11 ordered steps:

1. **Git pull** on `main` to pick up commits from the `scrape_boletines` /
   `process_boletines` workflows.
2. **`dvc pull --force`** to materialize the new raw PDFs and the consolidated dataset.
3. **Dengue extract (`--incremental`) → merge → prep** (best-effort). Incremental
   extraction parses only the *new* bulletin PDF (it skips the ~648 already in the
   manifest), so Dengue advances in seconds instead of re-parsing every PDF.
4. **Re-select the productive engine** on the recent SINAVE reality
   (`reselect_motor_2026.py`). The CV backtest table (`tabla-produccion`, ~19 min)
   is **not** rebuilt here — its cross-validation metrics depend only on the frozen
   models and the 2014-2025 history, not on the new bulletin. Pass
   `RETRAIN=1 make update-week` to rebuild it after an actual retrain.
5. **Rebuild** the Tableau dataset and the weekly validation HTML.
6. **Regenerate the neuro gallery** (333 charts + `zoom_data_neuro.json`).
7. **Dengue production + web** (gallery, forecast JSON, knowledge.json).
8. **Rebuild the EpiBot zoom** — *after* the Dengue web, so it is not stale.
9. **Regenerate** `knowledge.json` and copy it to `EpiForecast-IMSS-Dashboard/epibot/`.
10. **Auto-update the dashboard date bar** (`actualiza_barra_fechas.py`) — derived
    from the chart data, no hardcoded dates.
11. **Publish**: commit + push the dashboard repo (gallery, zoom, knowledge, index)
    and version the consolidated dataset + production tables in DVC/S3.

Run it after a CI boletin lands to propagate everything to stakeholders without
manual intervention:

```bash
make update-week              # weekly refresh (no retrain)
RETRAIN=1 make update-week    # also rebuild the CV backtest table (after retraining)
```

> **Before retraining on a new bulletin, run `make valida-prospectivo`** to score
> the frozen forecast against the just-arrived weeks while they are still genuinely
> out-of-sample. Retraining first turns those weeks into in-sample data and the
> honest OOS check is lost. See section 5 ("Prospective Out-of-Sample Validation").

Requires: local `.venv` with project installed, AWS credentials for DVC/S3 pull,
and a clone of `EpiForecast-IMSS-Dashboard` at the expected sibling path with
push permission to `main`.

### Current Data Snapshot

- **Latest epidemiological week:** 21/2026 for all four conditions. Dengue lives in a separate bulletin table that the CI does not extract, so it only advances when `make update-week` runs its incremental Dengue extraction from the same bulletin PDF — after which it is current with neuro
- **Consolidated dataset:** 74,688 rows (`data/processed/dataset_boletin_epidemiologico.csv`) — 62,112 neuro (3 × 20,704) + 12,576 Dengue
- **Knowledge base:** ~220 KB — 333 neuro production models + a `dengue` section, 51 stats keys, 6 boletin sections
- **Forecast horizon:** 52 weeks ahead (rolling, regenerated per weekly update); Dengue adds a 5-year illustrative seasonal projection

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

Models register themselves with `@register_model("name")` and are instantiated via `create_model(name, **kwargs)`. This allows transparent switching between algorithms without modifying pipeline code. Currently registered models: `prophet`, `deepar`, `ensemble`, `stacking`, `nbglm` (the count-correct Negative-Binomial GLM + Fourier + El Niño/ONI engine used for Dengue; see the Dengue section below).

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

## Dengue (Fourth Condition — Extra Deliverable)

Beyond the three neurological/mental-health conditions, EpiForecast-MX incorporates **Dengue (ICD-10 A97)** as a fourth, vector-borne condition — an extra deliverable that exercises the platform's extensibility on a disease with fundamentally different dynamics (climate-driven seasonality, multi-year epidemic cycles, near-zero off-season series). Dengue is **fully in production**: trained, model-selected, served on the public site, and answered by the EpiBot assistant.

**Modeling decision (evidence-based).** Dengue is reported under the WHO 2009 classification across three severity tiers: non-severe (`A97.0`), with warning signs (`A97.1`), and severe (`A97.2`). A literature review concluded that incidence should be modeled as **total dengue (the three tiers aggregated)**, not as separate severity series: severe dengue is a tiny fraction of cases (~0.1-0.2% in the Americas), so per-severity series are sparse and near-zero; predictive skill comes from the autocorrelation and seasonality of the aggregate. Dengue is modeled as **absolute counts** (not population-normalized rates).

**Data — series 2018-2026 (~392 national weeks).** A dedicated extractor parses the per-entity Dengue table from SINAVE bulletins (a separate page with its own layout), validated cell-by-cell against the printed `TOTAL` row:

- `src/epiforecast/data/extraction/dengue_extractor.py` — locates the table by ICD codes (`A97.0/A97.1/A97.2`), aggregates the three tiers per state and sex. Supports two WHO-2009 layouts: production 2020+ (12 columns) and historical 2018-W27..2019 (10 columns, `dengue_historico.py`).
- `scripts/extrae_dengue.py` / `scripts/merge_dengue.py` — batch extraction with a dataset-level audit, then an idempotent merge into the DVC-versioned consolidated dataset (**74,688 rows = 62,112 neuro + 12,576 Dengue**). `extrae_dengue --incremental` parses only bulletins not yet in the manifest (the weekly refresh path: seconds instead of re-reading every PDF).
- A separate WHO-1997 `A90/A91` series (2014-2018, confirmed-by-sex) is extracted for **context/EDA only** (`dengue_historico_a9091.py`) and does not feed the production pipeline.

**Cohort-aware modeling (neuro path untouched).** Dengue belongs to a "count-log" cohort (`utils.cohorts.is_count_log_cohort`): Prophet runs **with** `log_transform` and **without** rate normalization (the multiplicative trend otherwise collapses to ~0 when extrapolated), with a fixed `changepoint_prior_scale=0.05`, no COVID holiday, uniform CV weights, and **no regional fallback** (if a state has no transmission, it forecasts zero). The neurological flows stay byte-identical via `constants.NEURO_CONDITIONS` / `filter_neuro`.

**Production = DeepAR + Prophet + NB-GLM.** Five engines are trained per series (33 geographies × 3 sexes = 99 series), and the productive selector (`scripts/produccion_dengue.py`, by SMAPE on 2026 reality with a 5% tie band broken by MAE) keeps **DeepAR, Prophet and NB-GLM** (week 21 distribution **DeepAR 45 / NB-GLM 33 / Prophet 21**; national = DeepAR). The tie band matters in a low-incidence year: without it, a 0.13-point SMAPE margin once flipped the national series to Prophet, which badly overshoots the epidemic peak (in-sample fit ~1,895 vs ~1,154 observed) while DeepAR tracks it (~1,125); MAE breaks the tie back to DeepAR. The **NB-GLM** engine (`models/nbglm/` — Negative-Binomial GLM + Fourier seasonality + lags + an **El Niño/ONI** regressor) is the best in leave-one-epidemic-out backtest (SMAPE 52 vs Prophet+ENSO 76 vs plain Prophet 102): it is count-correct, extrapolates without tree divergence, is deterministic, and carries the inter-annual epidemic signal (ENSO) that purely autoregressive models cannot see. Prophet (Dengue) also gained the ONI regressor. Ensemble and Stacking are excluded because their tree learners do not extrapolate the epidemic dynamic to 52 weeks (a seasonal-envelope guard, `models/forecast_guards.py`, caps them but they are never chosen).

**Horizon: 1-year precise + 5-year illustrative.** The accurate forecast is 52 weeks. A 5-year band (flat-growth Prophet on `log1p`) is **illustrative**: with only two epidemic cycles in the data the ~4-5 year cycle is not learnable, so it shows the expected seasonal pattern, not the magnitude of the next epidemic.

**Live.** Public forecast page at **epiforecast.mx/dengue** (`dengue_forecast.json` + `dengue_serie.json` + showcase/EDA charts), and the **EpiBot** assistant answers Dengue questions (`answerDengue` handler, fed by a `dengue` section in `knowledge.json` generated from the production artifacts).

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

GitHub Actions runs on every push to `main` and on pull requests:

1. **Code Quality** (`ci.yml`): Ruff lint + format check + mypy type checking.
2. **Tests** (`ci.yml`): Pytest with 907 tests, coverage minimum 70%, excluding slow and integration tests.
3. **Integration Tests** (`ci.yml`): Manual trigger only (`workflow_dispatch`).
4. **Bulletin Scraping** (`scrape_boletines.yml`): Daily automated SINAVE bulletin download via Selenium.
5. **Bulletin Processing** (`process_boletines.yml`): Camelot PDF extraction and dataset consolidation.
6. **Google Sheets** (`gsheets.yml`): Publishes Tableau data to shared spreadsheet.

---

## Team

| Name | Role | Organization |
|------|------|--------------|
| Javier Augusto Rebull Saucedo | Technical lead and MLOps pipeline architect | Santander Bank US |
| Juan Carlos Perez Nava | EDA, feature engineering, and Prophet base model | Instituto Mexicano del Seguro Social (IMSS) |
| Luis Gerardo Sanchez Salazar | Dashboard design, development, and optimization | Tesla |

---

## License

MIT
