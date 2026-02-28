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
  <img src="https://img.shields.io/badge/Models-Prophet_%2B_DeepAR-orange?style=flat" alt="Multi-Model"/>
  <img src="https://img.shields.io/badge/GPU-SageMaker_T4-76b900?style=flat&logo=nvidia&logoColor=white" alt="GPU SageMaker"/>
  <img src="https://img.shields.io/badge/Coverage-93%25-brightgreen?style=flat" alt="Coverage 93%"/>
  <img src="https://img.shields.io/badge/DVC-S3-945DD6?style=flat&logo=dvc&logoColor=white" alt="DVC + S3"/>
</p>

---

## Project Description

**EpiForecast-MX** is a production-grade epidemiological intelligence platform developed in partnership with the **Instituto Mexicano del Seguro Social (IMSS)** to forecast the weekly incidence of neurological and mental-health conditions across Mexico's 32 states with a 52-week horizon.

The platform uses a **polymorphic Factory pattern** to support multiple forecasting engines (**Prophet** and **DeepAR**), ensuring scalability and ease of integration for future algorithms. DeepAR training runs on AWS SageMaker with NVIDIA T4 GPUs for fast iteration.

| Condition | ICD-10 | Challenge |
|-----------|--------|-----------|
| Depression | F32 | High baseline, seasonal patterns, COVID disruption |
| Parkinson's disease | G20 | Low incidence, volatile per-state series |
| Alzheimer's disease | G30 | Aging-population trends, underreporting |

---

## Key Features

- **Multi-Model Orchestration** -- Seamlessly switch between Prophet and DeepAR via central configuration (`config/base.yaml`) or CLI arguments.
- **GPU Training on SageMaker** -- DeepAR trains on `ml.g4dn.xlarge` (NVIDIA T4, CUDA 12.4) via a single `make train-sagemaker` command. Local CPU/MPS training also supported.
- **End-to-End ML Pipeline** -- Automated from PDF scraping (SINAVE bulletins) through INEGI demographic mapping to forecast charts and HTML reports.
- **Model Comparison Engine** -- High-contrast professional charts comparing Real vs. Prophet vs. DeepAR performance across all states and conditions.
- **Hybrid Fallback** -- Low-incidence state models automatically defer to regional aggregates to ensure 100% forecast coverage.
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
|   |   +-- deepar.yaml           #     DeepAR epochs, layers, dropout, context length
|   |-- data/                     #   Preprocessing parameters
|   |-- visualization/            #   Plot styling (IMSS palette)
|   +-- infrastructure/           #   Logging configuration
|
|-- src/epiforecast/              # Core Python package
|   |-- models/                   #   Factory pattern + model implementations
|   |   |-- base.py               #     Abstract ForecastModel interface
|   |   |-- factory.py            #     create_model() + @register_model decorator
|   |   |-- prophet/              #     ProphetForecaster + cross-validator + tuner
|   |   |-- deepar/               #     DeepARForecaster + cross-validator
|   |   +-- ensemble/             #     (future)
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
|   |-- compara_metricas.py       #   Metrics comparison (Excel)
|   |-- genera_reporte.py         #   HTML results report
|   |-- genera_bitacora.py        #   Modeling log (Prophet v1-v6)
|   |-- build_tableau.py          #   Tableau dataset builder
|   |-- get_dataset.py            #   RAW data download (SINAVE)
|   |-- filtra_padecimiento.py    #   Disease filter
|   |-- limpieza_dataset.py       #   Data cleaning
|   |-- realiza_prep.py           #   Feature engineering
|   |-- descarga_inegi.py         #   INEGI demographic download
|   |-- mapea.py                  #   State-INEGI mapping
|   +-- scrape_boletines.py       #   SINAVE bulletin scraper
|
|-- tests/                        # Test suite (~43 files, 80%+ coverage)
|   |-- unit/                     #   Unit tests for all modules
|   +-- integration/              #   End-to-end pipeline tests
|
|-- data/                         # Data stages (managed by DVC)
|   |-- raw/                      #   Original SINAVE data
|   |-- interim/                  #   Cleaned intermediate data
|   +-- processed/                #   Final datasets (data_inegi_*.csv)
|
|-- models/                       # Trained model artifacts (.pkl, managed by DVC)
|   |-- prophet/                  #   Prophet models per disease/state/sex
|   +-- deepar/                   #   DeepAR models per disease/state/sex
|
|-- reports/                      # Generated outputs
|   |-- forecasts/                #   Forecast CSVs and comparison charts
|   |-- figures/                  #   EDA and analysis plots
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
make train-all        # Both models sequentially

# Train DeepAR on AWS SageMaker with GPU (recommended for speed)
make train-sagemaker          # Build Docker image + launch on ml.g4dn.xlarge
make train-sagemaker-build    # Only build + push image to ECR
make train-sagemaker-local    # Test locally with Docker
```

After SageMaker training completes, download the trained models:
```bash
aws s3 sync s3://epiforecast-mx-data/training/<JOB_NAME>/output/ ./models/deepar/
```

### 3. Prediction

```bash
# Generate 52-week forecasts (denormalized to original scale)
make predict ARGS="modelo_activo='deepar'"
make predict ARGS="modelo_activo='prophet'"
```

### 4. Comparison and Reports

```bash
# Generate high-contrast comparison charts (Real vs Prophet vs DeepAR)
make compare

# Generate metrics comparison spreadsheet
make compare-metrics

# Generate HTML results report
make report

# Generate modeling log (Prophet iterations v1-v6)
make bitacora
```

Comparison charts are saved in `reports/forecasts/comparacion_modelos/` using CDMX timezone (UTC-6) for audit logs.

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
make s3-sync         # Quick sync CSVs to S3 (no DVC)
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

Models register themselves with `@register_model("name")` and are instantiated via `create_model(name, **kwargs)`. This allows transparent switching between algorithms without modifying pipeline code.

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

### Configuration

All configuration is managed via OmegaConf YAMLs in `config/`. The active model is controlled by `modelo_activo` in `config/base.yaml`. CLI overrides are supported:

```bash
python -m scripts.entrena modelo_activo='deepar' padecimiento.tipo='Alzheimer'
```

---

## CI/CD

GitHub Actions runs on every push to `main` and on pull requests:

1. **Code Quality**: Ruff lint + format check + mypy type checking.
2. **Tests**: Pytest with coverage (minimum 80%), excluding slow and integration tests.
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
