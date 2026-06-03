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
  <img src="https://img.shields.io/badge/Tests-849-brightgreen?style=flat" alt="849 Tests"/>
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

---

## Key Features

- **Multi-Model Orchestration** -- Seamlessly switch between Prophet, DeepAR, Ensemble, and Stacking via central configuration (`config/base.yaml`) or CLI arguments.
- **GPU Training on SageMaker** -- DeepAR trains on `ml.g4dn.xlarge` (NVIDIA T4, CUDA 12.4) via a single `make train-sagemaker` command. Local CPU/MPS training also supported.
- **EPI Interactive Console** -- AI-powered CLI (`python epi.py`) with natural-language command translation (Gemini), local KnowledgeBase for data queries, Rich TUI with IMSS institutional branding, risk-based command approval, session statistics, and persistent command history.
- **End-to-End ML Pipeline** -- Automated from PDF scraping (SINAVE bulletins) through INEGI demographic mapping to forecast charts and HTML reports.
- **Model Comparison Engine** -- High-contrast professional charts comparing Real vs. Prophet vs. DeepAR vs. Ensemble vs. Stacking performance across all states and conditions.
- **Weekly Validation** -- Automated comparison of model forecasts against real SINAVE bulletin data for the most recent epidemiological week (`make tabla-produccion`).
- **Reality-Calibrated Model Selection** -- Production engine selection uses SMAPE on the most recent SINAVE Boletin weeks (canonical since 2026-04-30 via `scripts/reselect_motor_2026.py`): series with >=10 real 2026 weeks and >=10 cases pick the engine with lowest 2026 SMAPE; noisy series (<10 cases) default to Ensemble; series without recent reality keep the CV assignment. The Tableau dataset exposes `modelo_productivo`. Current distribution: Prophet 126, Ensemble 95, DeepAR 78, Stacking 34. Audit trail in `reports/ProdDetails/auditoria_motores_2026.xlsx`.
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
|-- tests/                        # Test suite (~46 files, 849 tests, 70%+ coverage)
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

One-command orchestration that keeps the working copy, DVC artifacts and the
public dashboard in lockstep with the latest SINAVE bulletin ingested by the
CI scraper. Delegates to `scripts/actualiza_semanal.sh` and runs 5 steps:

1. **Git pull** on `main` to pick up commits pushed by the `scrape_boletines` /
   `process_boletines` workflows (updates `data/processed/*.dvc`, `data/raw_PDFs.dvc`,
   `data/registry.json`).
2. **`dvc pull --force`** to materialize the new raw PDFs and the refreshed
   consolidated dataset (`dataset_boletin_epidemiologico.csv`). Prints total
   rows and the latest epidemiological week detected.
3. **Regenerate** `web_dashboard/knowledge.json` via `scripts/build_web_knowledge.py`
   (333 production models, boletin stats, weekly comparisons).
4. **Copy** `knowledge.json` into the sibling `EpiForecast-IMSS-Dashboard/kb/`
   folder.
5. **Commit + push** the dashboard repo if `knowledge.json` changed
   (`data: actualizar knowledge.json con datos semana <N>/<YYYY>`).

Run it after a CI boletin lands (or any time new forecasts are generated) to
propagate data to stakeholders without manual intervention:

```bash
make update-week
```

Requires: local `.venv` with project installed, AWS credentials for DVC/S3 pull,
and a clone of `EpiForecast-IMSS-Dashboard` at the expected sibling path with
push permission to `main`.

### Current Data Snapshot

- **Latest epidemiological week:** 13/2026
- **Consolidated dataset:** 61,345 rows (`data/processed/dataset_boletin_epidemiologico.csv`)
- **Knowledge base:** 172 KB — 333 production models, 51 stats keys, 6 boletin sections
- **Forecast horizon:** 52 weeks ahead (rolling, regenerated per weekly update)

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

Models register themselves with `@register_model("name")` and are instantiated via `create_model(name, **kwargs)`. This allows transparent switching between algorithms without modifying pipeline code. Currently registered models: `prophet`, `deepar`, `ensemble`, `stacking`.

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

## Dengue Expansion (In Progress)

EpiForecast-MX is extending its multi-model pipeline to **Dengue (ICD-10 A97)**, the platform's first vector-borne disease and one of Mexico's highest-impact arboviral threats. This broadens the project beyond its three neurological and mental-health conditions.

**Modeling decision (evidence-based).** Dengue is reported under the WHO 2009 classification across three severity tiers: non-severe (`A97.0`), with warning signs (`A97.1`), and severe (`A97.2`). A literature review of dengue forecasting concluded that incidence should be modeled as **total dengue (the three tiers aggregated)**, not as separate severity series. Severe dengue is a very small fraction of cases (roughly 0.1 to 0.2 percent in the Americas), producing sparse, near-zero per-state weekly series that are intrinsically hard to forecast; predictive skill comes from the autocorrelation and seasonality of the aggregate series. Forecasting severity strata is a clinical classification problem, distinct from incidence forecasting.

**Phase 1 (complete): extraction and validation.** A dedicated extractor parses the per-entity Dengue table from SINAVE bulletins, which lives on a separate page from the neurological table and carries a different layout.

- `src/epiforecast/data/extraction/dengue_extractor.py` — locates the per-entity table by ICD codes (`A97.0/A97.1/A97.2`), aggregates the three severity tiers per state and sex, and emits the same schema as the consolidated bulletin dataset.
- `scripts/extrae_dengue.py` — batch entry point over `data/raw_PDFs/`, with a dataset-level audit (duplicate, completeness, and weekly-vs-accumulated consistency checks).
- `scripts/build_dengue_web.py` — generates the public Phase 1 page artifacts (preliminary charts plus `dengue_serie.json`, which the website fetches so the live table refreshes whenever the series is regenerated).

```bash
# Extract the validated Dengue series from all bulletins
python scripts/extrae_dengue.py

# Or a subset by glob
python scripts/extrae_dengue.py --pattern "202[3-6]_*.pdf"
```

Each bulletin is validated against its printed `TOTAL` row, and a guard rejects bulletins exhibiting a column-duplication artifact. The resulting series (`data/interim/dengue_boletin.csv`) covers **2020 to 2026 across the 32 states**, audited cell-by-cell against the source PDFs. Bulletins before 2020 use the older WHO 1997 scheme (`A90/A91`) and are not yet supported. A documented source correction (`_SOURCE_CORRECTIONS`) fixes a known bulletin typo (Zacatecas 2024-W41).

**Phase 2 (in progress): analysis and preparation.** The series was merged into the consolidated dataset (`scripts/merge_dengue.py`, idempotent; DVC-versioned, 72,256 rows). EDA confirmed strong seasonality and autocorrelation (see `docs/research/hallazgos/EDA_DENGUE_FASE2.md`). Feature engineering is made per-disease: outlier clipping is **disabled for Dengue** (the epidemic peak is the signal, not noise to median-replace). Because the consolidated now contains Dengue, the neuro pipeline is made Dengue-aware via `constants.NEURO_CONDITIONS`: `filter` ("General" mode), `entrena`, `reselect_motor_2026`, `genera_validacion_semanal`, and `build_web_knowledge` all restrict to the neuro production cohort, so Dengue is trained only when requested explicitly (`padecimiento.tipo='Dengue'`).

**Next phases.** Dengue-specific model configuration (seasonality, changepoints, no COVID regime, `_GRID_KEY_MAP` entry), training and validation of the four engines (no regional fallback: a state with no transmission forecasts zero), and 52-week forecasts.

---

## CI/CD

GitHub Actions runs on every push to `main` and on pull requests:

1. **Code Quality** (`ci.yml`): Ruff lint + format check + mypy type checking.
2. **Tests** (`ci.yml`): Pytest with 849 tests, coverage minimum 70%, excluding slow and integration tests.
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
