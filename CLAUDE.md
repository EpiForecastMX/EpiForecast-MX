# CLAUDE.md — EpiForecast-MX Project Instructions

> Last updated: 2026-02-25
> Compliance: A+ (153/153 — 100%) | Coverage: 84% (536 tests) | Branch: main

---

## Project Overview

**EpiForecast-MX** is a production-grade epidemiological intelligence platform developed in partnership with the **Instituto Mexicano del Seguro Social (IMSS)** as a Capstone project for the Master's in Applied Artificial Intelligence (MNA) at Tecnológico de Monterrey.

**What it does:** Forecasts weekly incidence of three neurological/mental-health conditions across all 32 Mexican states:
- Depression (ICD-10: F32) — high baseline, seasonal, COVID-disrupted
- Parkinson's disease (ICD-10: G20) — low incidence, volatile per-state series
- Alzheimer's disease (ICD-10: G30) — aging-population trends, underreporting

**Scale:** 297 Prophet models × 3 conditions × 3 gender categories (male/female/all) × 32 states + national + 4 INEGI mental-health regions = 312 forecast charts, 52-week horizon.

**Data:** SINAVE epidemiological bulletins (PDF, 2014–2026, ~633 files) + INEGI demographic data. Target: **rates per 100,000 inhabitants** (not absolute counts) to normalize across states.

---

## Architecture

### Design Principles (Cookiecutter Data Science v2 + SOLID)

- **src-layout**: package installed as `epiforecast` via `pip install -e ".[dev]"` — no `sys.path` hacks
- **SRP**: every file < 300 lines, single responsibility
- **OCP**: `ModelFactory` in `models/factory.py` — add models without modifying core
- **LSP**: `AbstractModel` base class; all models interchangeable
- **DIP**: scripts depend on abstractions, not Prophet directly
- **ISP**: Prophet split into `model.py` / `tuner.py` / `cross_validator.py`

### Package Structure (`src/epiforecast/`)

```
src/epiforecast/
├── constants.py               # ICD-10 codes, 32 states, sex modes, RATE_PER=100_000, RANDOM_SEED, COVID_START/END, VIZ_DPI
├── data/
│   ├── extraction/
│   │   ├── pdf_extractor.py   # Table detection + parsing (Camelot + regex)
│   │   ├── extraction_pipeline.py  # Multi-PDF orchestration
│   │   └── merger.py          # Incremental merge into master CSV
│   ├── ingestion/
│   │   ├── inegi.py           # PxWeb API client + surface area download
│   │   ├── inegi_utils.py     # Parsing, validation helpers
│   │   ├── inegi_constants.py # State abbreviations + mental-health region mapping
│   │   └── base.py            # AbstractIngestion interface
│   ├── preprocessing/
│   │   ├── cleaner.py         # Column normalization, substitution, row deletion
│   │   ├── filter.py          # ICD-10 / condition filtering (FiltraPadecimiento)
│   │   ├── transformer.py     # Weekly aggregation, cumulative→weekly, FE
│   │   ├── imputation.py      # IQR + Z-score outlier correction
│   │   └── base.py            # AbstractPreprocessor interface
│   └── loaders/               # (placeholder, future data loaders)
├── models/
│   ├── prophet/
│   │   ├── model.py           # SerieTiempoProphet — CV + train + eval + hybrid fallback
│   │   ├── tuner.py           # ProphetTuner — grid search over HP combos
│   │   └── cross_validator.py # ProphetCrossValidator — weighted CV folds (RMSE/MAE/MASE)
│   ├── deepar/                # (placeholder, future DeepAR)
│   ├── ensemble/              # (placeholder, future ensemble)
│   ├── factory.py             # ModelFactory — OCP-compliant model registry
│   ├── prediction.py          # ForecastModelLoader — load .pkl + inverse transforms
│   └── base.py                # AbstractModel ABC
├── evaluation/
│   └── metrics.py             # compute_rmse, compute_mae, compute_mape, compute_mase
├── features/
│   └── demographic.py         # MapeaInegi — merge state data + INEGI demographics
├── visualization/
│   ├── forecast_chart.py      # graficar_pronostico — Prophet forecast PNG (IMSS branding)
│   ├── chart_annotations.py   # _anotar_divisores, _anotar_zona_cv, _render_ficha_tecnica
│   ├── series_plots.py        # serie_tiempo — historical time-series plots
│   ├── eda_plots.py           # ReportData, SeccionNota, EDA distributions
│   ├── inegi_plots.py         # barras_inegi, boxplots_inegi — INEGI bar/box charts
│   ├── inegi_tables.py        # Rich console tabular EDA (_fmt, _print_df, eda_inegi)
│   ├── reporters.py           # PDFReportGenerator — reportlab PDF reports
│   ├── report_tables.py       # crear_tabla, tabla_kv — IMSS-styled reportlab tables
│   └── base.py                # GraficosHelper ABC + IMSS palette + matplotlib rcParams
├── pipelines/
│   └── base.py                # AbstractPipeline interface
├── infrastructure/
│   └── aws/                   # (placeholder, future SageMaker utilities)
└── utils/
    ├── config.py              # OmegaConf YAML loader + Loguru setup (loads config/base.yaml)
    ├── paths.py               # asegurar_ruta, existe_archivo, limpia_carpeta
    └── dataframe_helpers.py   # OperacionesDatos — IQR/Z-score stats + outlier detection
```

### Scripts (`scripts/`)

| Script | Makefile target | Purpose |
|--------|----------------|---------|
| `get_dataset.py` | `make get-dataset` | Copy/download raw master CSV |
| `filter.py` | `make filter` | Filter by ICD-10 condition |
| `clean.py` | `make clean` | Entity normalization, null handling |
| `transform.py` | `make transform` | Weekly agg, cumulative→weekly, IQR/Z-score |
| `ingest_inegi.py` | `make get-inegi` | Download INEGI demographic data |
| `build_features.py` | `make mapper` | INEGI merge → data_inegi_*.csv + .xlsx |
| `train.py` | `make train` | 297 Prophet models with CV (~45 min) |
| `predict.py` | `make predict` | 52-week forecasts + 312 PNG charts |
| `report.py` | `make report` | Interactive HTML results report |
| `bitacora.py` | `make bitacora` | HTML modeling journal v1–v6 |
| `build_tableau.py` | `make tableau` | Export Tableau-ready CSV |
| `compliance_check.py` | — | Cookiecutter DS v2 compliance audit |
| `scrape.py` | CI daily | Selenium SINAVE bulletin downloader |
| `ci_process.py` | CI trigger | Extract + merge new bulletins |

---

## Development Setup

```bash
# 1. Clone
git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
cd EpiForecast-MX

# 2. Create virtual environment (called 'integrador', NOT .venv)
python3.12 -m venv integrador
source integrador/bin/activate       # macOS/Linux
# OR
make setup                           # macOS: also installs Ghostscript via brew

# 3. Install package + dev deps
pip install -e ".[dev]"

# 4. Install pre-commit hooks
pre-commit install                   # OR: make hooks

# 5. Pull data/models from S3 (requires AWS credentials)
make data-pull

# 6. Verify everything works
make quality                         # ruff + mypy + pytest — must all pass
python scripts/compliance_check.py  # should be 153/153 A+
```

**Requirements:**
- Python 3.12 exactly (`.python-version` file enforces this)
- Ghostscript (for Camelot PDF parsing): `brew install ghostscript`
- AWS credentials for DVC + S3 (`~/.aws/credentials` or env vars)

---

## Configuration

All parameters live in `config/` — no hardcoded values in source code. OmegaConf merges them into a single `conf` dict loaded by `src/epiforecast/utils/config.py`.

### Config files

| File | What it contains |
|------|-----------------|
| `config/base.yaml` | Entry point — defines `padecimiento`, `paths`, `data`, `download`, `prediccion`, `inegi` |
| `config/data/preprocessing.yaml` | `columnas_eliminar`, `valores_sustituir`, `registros_eliminar` |
| `config/models/prophet.yaml` | HP grids, CV params, seasonality, COVID period, `FECHA_CORTE_ENTRENAMIENTO` |
| `config/features/feature_engineering.yaml` | `opciones_FE`, `regiones`, outlier config, INEGI region mapping |
| `config/visualization/plots.yaml` | `IMSS_COLORS`, `PALETTE_MAIN`, `PALETTE_PADECIMIENTO`, `PALETTE_SEXO`, matplotlib rcParams |
| `config/infrastructure/logging.yaml` | Loguru dual-sink config (console + rotating file) |

### Key `conf` keys (real values)

```yaml
# Condition + modeling mode
padecimiento.tipo: "General"        # General | Depresión | Parkinson | Alzheimer
padecimiento.modelado_estados: true # true=state models, false=regional models
padecimiento.modelado_hibrido: true # v6: auto-fallback to regional for low-incidence states
padecimiento.entrena_modelo: true   # train final model on full series after CV
padecimiento.solo_nacional: false   # true = national-only models

# Paths (OmegaConf interpolation)
paths.data: "./data"
paths.models: "./models"
paths.forecast: "./forecast"

# Key data files
data.boletin: "./data/processed/dataset_boletin_epidemiologico.csv"
data.data_prepare: "./data/processed/data_prepare_${padecimiento.tipo}.csv"
data.data_inegi: "./data/processed/data_inegi_${padecimiento.tipo}.csv"
data.forecast: "./forecast/all_forecast.csv"

# Model transforms
normalizar_tasa: true               # model rate per 100K (not absolute counts)
columna_poblacion: "Total"
tasa_por: 100000
log_transform: true                 # y = log(1 + y_rate) before Prophet
umbral_minimo_semanal: 0.5          # < 0.5 cases/week → "insuficiente" (v5: lowered from 1.0)

# Cross-validation
TS_SPLITS: 4
TEST_SIZE: 53                       # weeks (≈1 year)
cv_weights: [0.5, 0.75, 1.0, 1.25] # progressive weights — recent folds matter more
cv_timeout_por_fold: 35             # seconds; >35s = Newton → skip combo
cv_timeout_por_combo: 90            # seconds total per HP combo
FECHA_CORTE_ENTRENAMIENTO: "2025-01-01"  # used in forecast chart CV zone annotation

# Parallelism
n_jobs_train: -2                    # joblib: all cores minus one
```

---

## Data Pipeline

```
make preprocess   ← runs steps 1–5 sequentially (do NOT use -j flag)
```

| Step | Command | Input | Output |
|------|---------|-------|--------|
| 1. Get dataset | `make get-dataset` | Google Drive / S3 | `data/processed/dataset_boletin_epidemiologico.csv` |
| 2. Filter | `make filter` | dataset_boletin... | `data/raw/data_raw_${tipo}.csv` |
| 3. Clean | `make clean` | data_raw_*.csv | `data/interim/data_clean.csv` |
| 4. Transform | `make transform` | data_clean.csv | `data/processed/data_prepare_*.csv` |
| 5. INEGI | `make get-inegi && make mapper` | data_prepare_*.csv + INEGI API | `data/processed/data_inegi_*.csv` |
| 6. Train | `make train` | data_inegi_*.csv | `models/*.pkl` + `models/*.csv` |
| 7. Predict | `make predict` | models/*.pkl | `forecast/all_forecast.csv` + 312 PNGs |
| 8. Report | `make report` | all_forecast.csv | `forecast/reporte_resultados.html` |
| 9. Sync | `make s3-sync` | forecast/ + models/ | S3 `epiforecast-mx-data/latest/` |

**Full automation:**
```bash
make model-pipeline   # train → predict → report → s3-sync
```

### Transform chain (steps 3–4)

1. **Entity normalization** — standardize state names (e.g., "Distrito Federal" → "Ciudad de México")
2. **Cumulative → weekly** — `Acumulado_año_anterior` removed; weekly increment computed
3. **IQR outlier treatment** — configurable per column in `opciones_FE`
4. **Population normalization** — `y_rate = (cases / population) × 100,000`
5. **Log transform** — `y = log(1 + y_rate)` — stabilizes variance especially in Depression
6. **Prophet trains on `y`** (log-rate space)

**Inverse on prediction:** `exp(ŷ) − 1` → denormalize with state population → case counts in `all_forecast.csv`.

---

## Model Details

### Prophet cross-validation protocol

```
Series: weekly incidence (log-rate, per 100K inhabitants), 2014–2026
CV: 4 temporal folds, weights [0.5, 0.75, 1.0, 1.25]
HP selection: weighted-average RMSE across 4 folds
Final model: retrained on FULL series (no holdout leakage)
Output: .pkl + .csv sidecar (for inverse transform and chart metadata)
```

### Hyperparameter grids (config/models/prophet.yaml)

```yaml
param_grid_prophet:
  alzheimer:     # 6 combos; multiplicative-only (additive +51% RMSE)
    changepoint_prior_scale: [0.01, 0.03]
    seasonality_prior_scale: [0.05, 0.1, 0.5]
  depresion:     # 24 combos; both modes competitive
    seasonality_mode: [additive, multiplicative]
    changepoint_prior_scale: [0.01, 0.03, 0.05]
    seasonality_prior_scale: [0.025, 0.05, 0.1, 0.5]
  parkinson:     # 18 combos; multiplicative dominant
    seasonality_mode: [multiplicative, additive]
    changepoint_prior_scale: [0.03, 0.04, 0.05]
    seasonality_prior_scale: [0.1, 0.5, 1.0]
```

### Newton-optimizer protection (3 layers)

Prophet falls back to Newton (~500× slower) when L-BFGS fails. Three layers prevent this:

| Layer | Mechanism |
|-------|-----------|
| 1. Sort | Test high `changepoint_prior_scale` combos first (faster convergence) |
| 2. Fold timeout | Each fold capped at 35 s via `ThreadPoolExecutor` |
| 3. Newton threshold | If combo with `cp=X` times out, skip all combos with `cp < X` |

**Result:** Chihuahua-Depression 39 min (v4) → 4 min (v5).

### Hybrid fallback (v6)

States with average incidence < `umbral_minimo_semanal` (0.5 cases/week) = `"insuficiente"`. With `modelado_hibrido: true`, these 41 state-models defer to the corresponding INEGI mental-health regional model at prediction time, while using individual state population for denormalization.

### Seasonality configuration

```yaml
add_seasonality:
  name: 'yearly_custom'
  period: 52.18             # exact annual (365.25/7 weeks)
  fourier_order: 5          # national/state models
  fourier_order_regional: 3 # regional models (less overfitting on shorter series)
n_changepoints_regional: 12 # vs Prophet default 25 (reduces overfitting < 1M states)
```

### Results (v6 — 2026-02-21)

| Condition | Models | Insufficient | Fallback | Median RMSE | Median MASE | Training |
|-----------|--------|-------------|---------|-------------|-------------|---------|
| Alzheimer | 99 | 36 | 36 | 0.027 | 0.74 | ~2 min |
| Depression | 99 | 0 | 0 | 0.183 | 0.80 | ~28 min |
| Parkinson | 99 | 5 | 5 | 0.057 | 0.75 | ~14 min |

**MASE < 1 across all three conditions** — every model outperforms seasonal naïve (lag-52).

---

## Code Quality

### Commands

```bash
make quality         # full gate: ruff check + ruff format --check + mypy + pytest
make lint            # ruff check + ruff format --check (no tests)
make format          # ruff format --fix (auto-format)
make typecheck       # mypy src/epiforecast/
make test            # pytest --cov (full coverage report)
make test-fast       # pytest -x -m "not slow and not integration"
python scripts/compliance_check.py  # Cookiecutter DS v2 audit
```

### Tools

| Tool | Version | Config |
|------|---------|--------|
| ruff | 0.14.10 (pinned) | `[tool.ruff]` in pyproject.toml, line-length=99 |
| mypy | 1.19.1 | `[tool.mypy]` in pyproject.toml, gradual typing |
| pytest | 8.x | `[tool.pytest.ini_options]`, markers: `slow`, `integration` |
| pre-commit | hooks on commit | `.pre-commit-config.yaml` |

### Pre-commit hooks (`.pre-commit-config.yaml`)

```
ruff check --fix          (src/epiforecast/ + tests/)
ruff format               (src/epiforecast/ + tests/)
mypy                      (src/epiforecast/ only)
trailing-whitespace
end-of-file-fixer
check-yaml
check-added-large-files   (max 500 KB)
```

### Standards

- Every file < 300 lines (SRP — enforced by compliance checker)
- Every public module has a docstring
- No `print()` in package — use `from loguru import logger`
- No wildcard imports in `src/epiforecast/`
- Canonical imports: `from epiforecast.X import Y` (not `from src.epiforecast`)
- Spanish is intentional in: config keys, commit messages, some variable names (IMSS stakeholders)

---

## Testing

### Structure

```
tests/
├── conftest.py            # pytest_configure hook — mocks config module to prevent sys.exit
├── unit/
│   ├── data/              # cleaner, filter, transformer, imputation, extraction_pipeline, merger, pdf_extractor
│   ├── evaluation/        # metrics (RMSE, MAE, MAPE, MASE)
│   ├── features/          # demographic (MapeaInegi)
│   ├── models/            # factory, prediction, prophet_model, tuner, cross_validator
│   ├── utils/             # paths, dataframe_helpers
│   ├── visualization/     # all 9 visualization modules
│   ├── test_bases.py      # ABC interface tests
│   └── test_constants.py  # constants validation
└── integration/           # end-to-end smoke tests (manual trigger in CI)
```

### Coverage (84% — 1871/2232 statements)

| Module | Coverage | Notes |
|--------|---------|-------|
| constants, filter, imputation, transformer | 100% | |
| metrics, paths, dataframe_helpers | 100% | |
| forecast_chart, inegi_plots, inegi_tables, report_tables | 100% | |
| demographic, factory, prediction, base modules | 100% | |
| cleaner, reporters, tuner | 96–98% | |
| extraction_pipeline, cross_validator, chart_annotations | 94–95% | |
| merger | 23% | I/O heavy — requires real PDF files |
| forecast_plots | 30% | Requires real model CSV files to orchestrate |
| config.py | 0% | sys.exit at module scope — untestable without real YAMLs |

### Key testing patterns

```python
# 1. Inject mock conf (avoids sys.exit on missing YAML)
with patch.object(module, "conf", {"key": "value"}):
    obj = MyClass()

# 2. conftest.py pytest_configure hook pre-injects mock at collection time
# (protects all modules that import conf at module scope)

# 3. Use tmp_path for real file I/O
def test_creates_pdf(tmp_path):
    gen = PDFReportGenerator(data, str(tmp_path / "out.pdf"))
    gen.run()
    assert (tmp_path / "out.pdf").exists()

# 4. Prophet always mocked — never instantiate real Prophet in unit tests
mock_model = MagicMock()
forecaster._create_prophet.return_value = mock_model
```

### Running tests

```bash
pytest tests/                                               # all 536 tests
pytest tests/ -m "not slow and not integration"            # fast only
pytest tests/unit/models/ -v                               # specific module
pytest tests/ --cov=src/epiforecast --cov-report=term-missing  # with coverage
```

---

## CI/CD

### GitHub Actions (`.github/workflows/ci.yml`)

| Job | Trigger | Steps |
|-----|---------|-------|
| Code Quality | push to `main`/`refactor/*`, PR to `main` | ruff check + format + mypy |
| Tests | after Quality passes | pytest (excludes slow + integration) + coverage artifact |
| Integration | `workflow_dispatch` only | pytest -m integration (requires AWS) |

### Scraping workflows

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `scrape_boletines.yml` | Daily 2 PM CDMX | Selenium downloads new SINAVE PDFs → DVC push → SNS |
| `process_boletines.yml` | Post-scrape | Camelot extraction → incremental merge → DVC push → SNS |

---

## Data Versioning (DVC + S3)

```
Remote: s3://epiforecast-mx-data  (default)

Tracked artifacts:
  data/raw_PDFs.dvc                                        # ~633 bulletins (~1 GB)
  data/raw.dvc
  data/processed/dataset_boletin_epidemiologico.csv.dvc   # master CSV
  models.dvc                                               # 297 .pkl + .csv sidecars (~109 MB)
  forecast/all_forecast.csv.dvc                            # 52-week forecasts (~180 MB)
```

```bash
make data-pull      # dvc pull — download all artifacts from S3
make data-push      # dvc push — upload local changes to S3
make models-push    # version trained models: dvc add models/ + push
make forecast-push  # version forecasts: dvc add forecast/ + push
make s3-sync        # boto3 sync processed CSVs to s3://epiforecast-mx-data/latest/
make data-status    # dvc status — check what's out of sync
```

---

## Common Tasks

### Run full pipeline from scratch

```bash
source integrador/bin/activate
make preprocess           # steps 1–5, ~5 min
make train                # 297 models, ~45 min (n_jobs=-2)
make predict              # forecasts + 312 PNGs, ~2 min
make s3-sync              # push to S3
make report               # HTML report
```

### Check code quality before pushing

```bash
make quality                        # must exit 0
python scripts/compliance_check.py  # target: A+ (153/153)
```

### Debug config loading

```bash
source integrador/bin/activate
python -c "from epiforecast.utils.config import conf; print(list(conf.keys()))"
```

### Add a new condition

1. Add ICD-10 code to `src/epiforecast/constants.py` (`CONDITIONS` dict)
2. Add HP grid to `config/models/prophet.yaml` under `param_grid_prophet`
3. Add key to `ProphetTuner._GRID_KEY_MAP` in `src/epiforecast/models/prophet/tuner.py`
4. Run `make preprocess && make train`

### Update hyperparameters

Edit `config/models/prophet.yaml` → `param_grid_prophet.{alzheimer|depresion|parkinson}`. The grid is loaded at `ProphetTuner.__init__` time via `conf["param_grid_prophet"]`.

---

## Dependency Versions

| Package | Version | Notes |
|---------|---------|-------|
| Python | 3.12.3 | `.python-version` enforces this |
| prophet | 1.3.0 | cmdstanpy backend |
| pandas | 2.3.0 | |
| numpy | 2.0.0 | |
| scikit-learn | 1.5.0 | TimeSeriesSplit for CV |
| omegaconf | 2.3.0 | YAML config loader |
| loguru | 0.7.3 | Logging (dual-sink: console + rotating file) |
| ruff | 0.14.10 | Pinned — format consistency across environments |
| mypy | 1.19.1 | |
| reportlab | 4.x | PDF report generation |
| camelot-py | 0.11+ | PDF table extraction (requires Ghostscript) |
| rich | 13.7+ | Console EDA output (`inegi_tables.py`) |

---

## Team

| Name | Role | Organization |
|------|------|-------------|
| **Javier Augusto Rebull Saucedo** | Lead Developer | Sr. Associate, Santander Bank US |
| **Juan Carlos Pérez Nava** | ML Engineer | IT Professional, IMSS |
| **Luis Gerardo Sánchez Salazar** | Data Engineer | Sr. Controls Engineer, Tesla |
| **Dr. Grettel Barceló Alonso** | Academic Advisor | Tecnológico de Monterrey |
| **Dr. Ruth Pérez** | IMSS Project Leader | IMSS |
| **Dr. Lina Díaz Castro** | Psychiatry Researcher | IMSS |

---

## Critical Gotchas

1. **Rates, not counts** — all Prophet models train on `log(1 + cases/population × 100,000)`. Never pass raw case counts. Inverse on prediction: `exp(ŷ) − 1` × population / 100,000.

2. **`make preprocess` must run sequentially** — do NOT use `-j`. Steps depend on each other's output files.

3. **COVID bias** — folds 1–2 (2020–2022) have systematically worse RMSE. CV weights `[0.5, 0.75, 1.0, 1.25]` mitigate this by down-weighting those folds.

4. **Log-transform changes HP selection** — with log-transform, additive mode wins 67% of Alzheimer models (vs 6% without). This is expected behavior, not a bug.

5. **`config.py` has module-level `sys.exit(1)`** — importing it without the YAML files crashes pytest collection. The `pytest_configure` hook in `tests/conftest.py` pre-injects a mock module to prevent this.

6. **`FECHA_CORTE_ENTRENAMIENTO`** — required by `chart_annotations._anotar_zona_cv`. Tests for `forecast_chart.py` must patch `ca_mod.conf` with this key (see `test_forecast_chart.py::patch_ca_conf` autouse fixture).

7. **Spanish naming is intentional** — commit messages, config keys, variable names in `data/` modules. Do not rename to English — IMSS stakeholders read the code.

8. **Virtual env is `integrador/`**, not `.venv` or `venv`. Always activate with `source integrador/bin/activate`.

9. **Tabasco-Depression regime change** (2023-01-09, 365-day window) is added as a Prophet holiday — gives −6.2% RMSE. Other step-change states (Nayarit, Colima, Durango, BCS) were tested and worsened RMSE; they are excluded.

10. **`n_changepoints_regional: 12`** (vs Prophet default 25) reduces overfitting for states < 1M inhabitants. `fourier_order_regional: 3` (vs 5) serves the same purpose for regional models.
