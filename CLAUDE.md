# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EpiForecast-MX is an epidemiological forecasting system for predicting neurological disease cases (Alzheimer's, Parkinson's, Depression) in Mexico. It uses Facebook Prophet for time series forecasting with data from SINAVE (Sistema Nacional de Vigilancia Epidemiológica).

## Common Commands

### Setup
```bash
make setup          # Full macOS setup (deps + Python + DVC data)
make setup-linux    # Linux/WSL setup
make requirements   # Install Python dependencies only
make data-pull      # Download data from S3 via DVC
```

### Code Quality
```bash
make lint           # Run Ruff linter (check + format check)
make format         # Auto-format with Ruff
```

### Data Pipeline
```bash
make preprocess     # Full pipeline: filter → clean → transform → INEGI mapping
make filter         # Filter by disease (config/params.yaml → padecimiento)
make clean          # Clean dataset (nulls, duplicates, formatting)
make transform      # Feature engineering
make get_inegi      # Download INEGI demographic data
make mapper         # Map entities with INEGI regions
make train          # Train Prophet model
```

### DVC Data Management
```bash
make data-pull      # Pull data from S3
make data-push      # Push data to S3
make data-status    # View sync status
make data-add PDF=path/to/file.pdf  # Track new PDF
```

## Architecture

### Data Flow
```
SINAVE PDFs → Extraction (Camelot) → Merge → Clean → Feature Engineering → Prophet Model
     ↓                                                        ↓
  registry.json                                    models/ + forecasts/
```

### Key Modules

- **`src/datos/`** - Data cleaning (`clean_dataset.py`), filtering (`filtrar_padecimiento.py`), feature engineering (`preparacion.py`), INEGI integration (`get_inegi.py`)
- **`src/extraccion/`** - PDF table extraction (`pipeline.py`), dataset merging (`merge_datasets.py`), CLI/GUI interfaces
- **`src/modelado/`** - Prophet time series model (`prophet.py`), model loading utilities (`forecast.py`)
- **`src/configuraciones/`** - YAML config loading and logging setup (`config_params.py`)
- **`scripts/`** - Entry points for Makefile targets

### Configuration Files (config/)

- **`params.yaml`** - Main config: disease selection, file paths, metadata
- **`modelado.yaml`** - Prophet hyperparameters, cross-validation splits, atypical periods (COVID-19)
- **`limpieza.yaml`** - Columns to drop, value substitutions
- **`FE.yaml`** - Feature engineering rules, regional mappings, outlier treatment
- **`logging.yaml`** - Loguru dual-sink config (console + rotating files)

### Automated CI/CD (GitHub Actions)

1. **`scrape_boletines.yml`** - Daily scraper (2 PM CDMX) downloads new SINAVE bulletins
2. **`process_boletines.yml`** - Triggered after scraper; extracts tables and merges to dataset

Both pipelines use DVC for S3 sync and send SNS notifications on completion.

## Key Patterns

- **Configuration:** All parameters in YAML files, loaded via OmegaConf in `config_params.py`
- **Logging:** Loguru with structured format, configured per `logging.yaml`
- **Data Versioning:** Large files (PDFs, datasets) tracked by DVC in S3 (`s3://epiforecast-mx-data/`)
- **PDF Extraction:** Camelot library with keyword search for disease tables

## Data Files

- **`data/raw_PDFs/`** - 630+ epidemiological bulletins (DVC-versioned)
- **`data/processed/dataset_boletin_epidemiologico.csv`** - Main dataset (60k+ rows)
- **`data/registry.json`** - Tracks processed bulletins (prevents duplicates)

## Dependencies

Python 3.12 required. Key libraries: pandas, prophet, camelot-py, selenium, dvc[s3], omegaconf, loguru, ruff.

System dependency: Ghostscript (for PDF processing) - installed via `make setup`.
