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
  <img src="https://img.shields.io/badge/Coverage-70%25-brightgreen?style=flat" alt="Coverage 70%"/>
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
- **End-to-End ML Pipeline** -- Automated from PDF scraping (SINAVE bulletins) through INEGI demographic mapping to forecast charts and HTML reports.
- **Model Comparison Engine** -- High-contrast professional charts comparing Real vs. Prophet vs. DeepAR vs. Ensemble vs. Stacking performance across all states and conditions.
- **SMAPE-Based Model Selection** -- The Tableau dataset automatically selects the best-performing model per group (condition, state, mode) based on SMAPE, exposing a `modelo_productivo` column. Production CSV (`tabla_333_modelos_produccion.csv`) uses SMAPE-primary selection with MASE/RMSE tiebreakers.
- **Production Model Table** -- 333 production models with SMAPE-based selection, 52-week case projections (`casos_52_semanas`), confidence classification (propio/regional), and automated justification text.
- **Overfitting and Data Leakage Detection** -- Train metrics (RMSE, SMAPE) computed in-sample for all 4 models. HTML report shows diagnostic badges: Overfitting (test/train SMAPE ratio) and Leakage (suspiciously low train SMAPE).
- **Hybrid Fallback** -- Zero-incidence and low-confidence (<5 cases/52 weeks) state models automatically defer to regional aggregates to ensure 100% forecast coverage. Integer-rounded predictions (no fractional cases).
- **MLflow Experiment Tracking** -- Optional integration logs all training runs (metrics, hyperparameters, elapsed time) to MLflow. Non-intrusive: no-op when not installed. Install with `pip install -e ".[mlflow]"`, browse with `mlflow server --backend-store-uri ./mlruns`.
- **Cross-Validation** -- Prophet uses weighted time-series CV (4 folds, progressive weights). DeepAR uses multi-series CV with early stopping.
- **IMSS Institutional Branding** -- All visualizations and reports follow official IMSS 2026 chromatic and styling guidelines.

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
|-- scripts/                      # CLI entry points
|   |-- entrena.py                #   Main training orchestrator
|   |-- entrena_sagemaker.py      #   SageMaker entry point (adapts /opt/ml/ environment)
|   |-- predice.py                #   Forecast generation (52 weeks, denormalized)
|   |-- compara_modelos.py        #   Visual model comparison
|   |-- avance5_modelo_final.py    #   Ensemble training + visualization
|   |-- compara_metricas.py       #   Metrics comparison (Excel + HTML with diagnostics)
|   |-- genera_reporte.py         #   HTML results report
|   |-- genera_bitacora.py        #   Modeling log (Prophet v1-v6)
|   |-- genera_reporte_avance5.py #   Avance 5 report (Markdown + 18 charts)
|   |-- genera_tabla_produccion.py#   Production model table (333 models, SMAPE selection)
|   |-- build_tableau.py          #   Tableau dataset builder
|   |-- patch_train_metrics.py    #   Patch CSVs with train metrics (no retraining)
|   |-- get_dataset.py            #   RAW data download (SINAVE)
|   |-- filtra_padecimiento.py    #   Disease filter
|   |-- limpieza_dataset.py       #   Data cleaning
|   |-- realiza_prep.py           #   Feature engineering
|   |-- descarga_inegi.py         #   INEGI demographic download
|   |-- mapea.py                  #   State-INEGI mapping
|   +-- scrape_boletines.py       #   SINAVE bulletin scraper
|
|-- tests/                        # Test suite (~34 files, 70%+ coverage, 761 tests)
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
|   |-- forecasts/                #   Forecast CSVs and comparison charts
|   |-- figures/                  #   EDA and analysis plots (ModeloFinal/ for Avance 5)
|   |-- reports/                  #   Markdown reports and production CSV
|   +-- docs/                     #   PDF reports
|
|-- .github/workflows/            # CI/CD
|   |-- ci.yml                    #   Quality gate (lint + typecheck + tests)
|   |-- scrape_boletines.yml      #   Automated bulletin scraping
|   |-- process_boletines.yml     #   Bulletin processing
|   +-- gsheets.yml               #   Google Sheets publishing
|
|-- Makefile                      # MLOps orchestration
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

### 1. Data Preprocessing

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

### 2. Training

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

### 3. Prediction and Tableau

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

The production table (`reports/reports/tabla_333_modelos_produccion.csv`) includes:
- Per-model metrics (RMSE, MAE, SMAPE, MASE) for all 4 algorithms
- `modelo_produccion`: Best model per series (SMAPE-primary, MASE/RMSE tiebreaker)
- `casos_52_semanas`: Total projected cases for 52-week horizon (integer)
- `tipo_modelo`: `propio` (state-level) or `regional` (fallback for zero/low-incidence)
- `justificacion`: Automated reasoning for model selection

### 4. Comparison and Reports

```bash
# Generate high-contrast comparison charts (Real vs all 4 models)
make compare

# Generate metrics comparison (Excel + HTML report with Overfitting/Leakage badges)
make compare-metrics

# Generate HTML results report
make report

# Generate modeling log (Prophet iterations v1-v6)
make bitacora

# Generate Avance 5 report (Markdown + 18 charts + production CSV with 333 models)
make reporte-avance5
```

Comparison charts are saved in `reports/forecasts/comparacion_modelos/` using CDMX timezone (UTC-6) for audit logs. The Avance 5 report generates `reports/reports/avance5_modelo_final.md`, `reports/reports/tabla_333_modelos_produccion.csv` (333 production models with SMAPE-based selection), and 18 analysis charts in `reports/figures/ModeloFinal/`.

### 5. Code Quality

```bash
# Full quality gate (lint + typecheck + tests)
make quality

# Individual checks
make lint          # Ruff check (format + lint rules)
make format        # Auto-format code
make typecheck     # mypy strict type checking
make test-fast     # Fast unit tests only
```

### 6. Data Versioning (DVC)

```bash
make data-pull       # Download data from S3
make data-push       # Upload data to S3
make models-push     # Version and upload trained models
make s3-sync         # Quick sync CSVs + forecasts to S3 (no DVC)
```

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

## CI/CD

GitHub Actions runs on every push to `main` and on pull requests:

1. **Code Quality**: Ruff lint + format check + mypy type checking.
2. **Tests**: Pytest with 761 tests, coverage minimum 70%, excluding slow and integration tests.
3. **Integration Tests**: Manual trigger only (`workflow_dispatch`).

Additional workflows automate SINAVE bulletin scraping and Google Sheets publishing.

---

## Team

| Name | Role |
|------|------|
| Javier Augusto Rebull Saucedo | Developer |
| Juan Carlos Perez Nava | Developer |
| Luis Gerardo Sanchez Salazar | Developer |

---

## License

MIT
