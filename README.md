<p align="center">
  <img src="https://images.seeklogo.com/logo-png/7/1/imss-logo-png_seeklogo-70988.png" alt="IMSS Logo" width="110"/>
</p>

<h1 align="center">EpiForecast-MX</h1>

<p align="center">
  <strong>Epidemiological Intelligence Platform for Neurological Disease Forecasting in Mexico</strong>
</p>

<p align="center">
  <em>Capstone Project · Master's in Applied Artificial Intelligence · Tecnológico de Monterrey</em><br>
  <em>In collaboration with the Instituto Mexicano del Seguro Social (IMSS)</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat&logo=python&logoColor=white" alt="Python 3.12"/>
  <img src="https://img.shields.io/badge/Models-Prophet_%2B_DeepAR-orange?style=flat" alt="Multi-Model"/>
  <img src="https://img.shields.io/badge/Coverage-93%25-brightgreen?style=flat" alt="Coverage 93%"/>
  <img src="https://img.shields.io/badge/Compliance-A%2B%20(96%25)-brightgreen?style=flat" alt="Grade A+"/>
  <img src="https://img.shields.io/badge/DVC-S3-945DD6?style=flat&logo=dvc&logoColor=white" alt="DVC + S3"/>
</p>

---

## Project Description

**EpiForecast-MX** is a production-grade epidemiological intelligence platform developed in partnership with the **Instituto Mexicano del Seguro Social (IMSS)** to forecast the weekly incidence of neurological and mental-health conditions across Mexico.

The platform evolved from a single-model approach to a **polymorphic MLOps ecosystem**, supporting both **Prophet** (Meta) and **DeepAR** (AWS SageMaker). It utilizes a Factory pattern to ensure scalability and ease of integration for future forecasting algorithms.

| Condition | ICD-10 | Challenge |
|-----------|--------|-----------|
| Depression | F32 | High baseline, seasonal patterns, COVID disruption |
| Parkinson's disease | G20 | Low incidence, volatile per-state series |
| Alzheimer's disease | G30 | Aging-population trends, underreporting |

---

## Key Features

- **Multi-Model Orchestration** — Seamlessly switch between Prophet and DeepAR via central configuration (`config/base.yaml`) or CLI arguments.
- **End-to-end ML pipeline** — automated from PDF scraping (SINAVE) to forecast charts.
- **Model Comparison Engine** — Generation of high-contrast professional charts comparing Real vs. Prophet vs. DeepAR performance.
- **Hybrid fallback** — Low-incidence models automatically defer to regional aggregates to ensure 100% forecast coverage.
- **IMSS Institutional Branding** — All visualizations and reports follow official IMSS 2026 chromatic and styling guidelines.

---

## Project Structure

```
EpiForecast-MX/
│
├── config/                        # Unified YAML configuration
│   ├── base.yaml                  #   Active model and global paths
│   └── models/                    #   Specific HP for Prophet and DeepAR
├── src/epiforecast/               # Core Python package
│   ├── models/                    #   Factory pattern and Model implementations
│   │   ├── prophet/               #     Meta/Facebook Prophet logic
│   │   ├── deepar/                #     AWS SageMaker DeepAR integration
│   │   └── factory.py             #     Polymorphic ModelFactory
│   ├── visualization/             #   IMSS publication-quality charts
│   └── data/                      #   PDF extraction and INEGI ingestion
├── scripts/                       # CLI Entry points (entrena, predice, compara)
└── Makefile                       # MLOps orchestration (make train-all, make compare)
```

---

## Usage (MLOps Commands)

### 1. Training
```bash
# Train only Prophet
make train-prophet

# Train only DeepAR
make train-deepar

# Train everything
make train-all
```

### 2. Prediction
```bash
make predict ARGS="modelo_activo='deepar'"
```

### 3. Comparison
```bash
# Generate high-contrast professional comparison charts
make compare
```

The comparison charts are saved in `reports/forecasts/comparacion_modelos/`, using **CDMX Timezone** for audit logs.
