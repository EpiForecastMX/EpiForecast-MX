# 🧠 MASTER PROMPT — EpiForecast-MX: Avance 6 — Conclusiones Clave

> **Target model:** Claude (Opus/Sonnet)
> **Output language:** Spanish (Mexico) — impeccable orthography, proper use of ñ, accents, and formal academic register.
> **Deliverable:** A single LaTeX file named `Avance6_01.tex` + any auxiliary HTML/chart files needed as figure assets.
> **Number format convention:** Use `,` for thousands separator and `.` for decimals (e.g., `1,782 models`, `14.6%`).

---

## 1. ROLE & PERSONA

You are a senior MLOps engineer, data scientist, and LaTeX typographer working on **EpiForecast-MX** — a capstone project for the **Maestría en Inteligencia Artificial Aplicada** at **Tecnológico de Monterrey**, developed in strategic collaboration with the **Instituto Mexicano del Seguro Social (IMSS)**. This is Avance 6: "Conclusiones Clave" (Key Conclusions). The document must be a **masterpiece** of academic writing, data visualization, and technical depth — the kind of deliverable that makes reviewers stop and take notice.

---

## 2. PROJECT CONTEXT (USE THIS AS YOUR KNOWLEDGE BASE)

### 2.1 What EpiForecast-MX Is

EpiForecast-MX is an epidemiological forecasting system for three neurological and mental health conditions in Mexico:

| ICD-10 | Condition | Spanish Name |
|--------|-----------|-------------|
| F32 | Major Depressive Disorder | Depresión Mayor |
| G20 | Parkinson's Disease | Enfermedad de Parkinson |
| G30 | Alzheimer's Disease | Enfermedad de Alzheimer |

**Scope:** 37 geographies × 3 conditions × 3 demographic segments (general, male, female) = **333 production series**. The 37 geographies break down as:

| Geographic Level | Count | Description | Models |
|-----------------|-------|-------------|--------|
| State (Estatal) | 32 | All 32 Mexican federal entities | 32 × 3 × 3 = **288** |
| Regional (INEGI Fallback) | 4 | INEGI mental health regions | 4 × 3 × 3 = **36** |
| National | 1 | Country-wide aggregate | 1 × 3 × 3 = **9** |
| **Total** | **37** | | **333** |

**Why 333 and not 288?** The 36 regional + 9 national models serve two critical functions:
1. **100% coverage guarantee:** Regional models act as fallback when a state series has insufficient incidence (<5 cases in 52 weeks). In production, **8 of 333 series** required this mechanism (7 Alzheimer + 1 Parkinson in Campeche).
2. **Multi-level planning:** IMSS requires forecasts at state, regional, AND national levels for budget allocation and logistics.

**4 INEGI Mental Health Regions (Fallback):**
- **Metropolitana Alta (4 states):** CDMX, Jalisco, Estado de México, Nuevo León
- **Urbana Media (15 states):** Aguascalientes, Baja California, BCS, Chihuahua, Coahuila, Colima, Durango, Guanajuato, Morelos, Querétaro, SLP, Sinaloa, Sonora, Tamaulipas, Zacatecas
- **Rural / Dispersa (7 states):** Guerrero, Hidalgo, Michoacán, Nayarit, Puebla, Tlaxcala, Veracruz
- **Sur-Sureste Vulnerable (6 states):** Campeche, Chiapas, Oaxaca, Quintana Roo, Tabasco, Yucatán

**Competition architecture:** 4 engines (Prophet, DeepAR, Ensemble, Stacking) compete for each of the 333 series, generating **4 × 333 = 1,332 evaluations**, but only the winner per series goes to production.

**LaTeX REFERENCE for the 333 composition (adapt this style):**
Use an equation showing `37 geographies × 3 conditions × 3 demographic segments = 333`, followed by a breakdown table with `\rowcolor` alternation, and an `insightbox` (custom environment) explaining why 333 and not 288. Include the INEGI regions table with all 32 states classified. Use a footnote for the fallback activation criterion: series with <5 cases in 52 weeks are reassigned to their regional model.

**Data source:** SINAVE (Sistema Nacional de Vigilancia Epidemiológica) weekly epidemiological bulletins, 2012–2025. Data is extracted from PDF bulletins using `camelot-py`, normalized to rates per 100,000 inhabitants using INEGI census data.

**Institutional partners:**
- **IMSS:** Dr. Ruth Pérez-Hernández, Dr. Lina Díaz Castro (domain experts)
- **Tec de Monterrey:** Dra. Grettel Barceló Alonso (academic advisor)

**Team (Equipo 01):**
- Javier Rebull Sánchez (A01794560) — Project lead, MLOps architect
- Juan Carlos Pérez Nava (A01795084) — IMSS IT professional
- Luis Gerardo Sánchez Salazar (A01795556) — Tesla controls engineer

**Web presence:** [https://proyectointegrador.org](https://proyectointegrador.org) and [https://proyectointegrador.org/epidashboard](https://proyectointegrador.org/epidashboard) (Tableau Public dashboard)

### 2.2 Baseline Prophet Pipeline (Local Production)

- **333 individual Prophet models** trained with temporal cross-validation (288 state + 36 regional + 9 national)
- **CV parameters:** 730-day initial window, 56-day period, 168-day horizon, capturing annual seasonality
- **Hyperparameter grid:** `seasonality_mode` (additive/multiplicative), `changepoint_prior_scale`, `seasonality_prior_scale`, `fourier_order`
- **Anti-Newton 3-layer protection:** sort by `cp` descending, per-fold timeout 35s, per-combo timeout 90s, Newton-prone threshold propagation
- **Preprocessing:** Log-transform `y = log(1 + y)`, rate normalization (cases / population × 100,000), IQR outlier treatment, cumulative-to-weekly conversion
- **Fourier seasonality:** 20 components yearly (vs Prophet default 10)
- **COVID handling:** 5 changepoints placed in COVID period, weighted cross-validation folds [0.5, 0.75, 1.0, 1.25] (COVID fold penalized)

**Baseline MAPE results (333 Prophet production models — 288 state + 36 regional + 9 national):**

| Condition | Mean MAPE | Best State MAPE | Worst State MAPE | Median MAPE |
|-----------|-----------|-----------------|------------------|-------------|
| Depression (F32) | 14.6% | CDMX: 4.8% | ~35% | ~12% |
| Parkinson (G20) | 27.8% | — | — | — |
| Alzheimer (G30) | 28.3% | — | σ = 8.6% | — |

**Key insight:** Alzheimer and Parkinson have higher MAPE due to low signal-to-noise ratio (sparse events in small states). Female models consistently outperform male models for these conditions.

### 2.3 AWS SageMaker Model Comparison Pipeline

The project runs a **dual-pipeline architecture**:

**Pipeline 1 — SageMaker (model selection):**
- Instance: `ml.g4dn.xlarge` (GPU), Docker on ECR
- **6 models compared:** Prophet, XGBoost, Ridge, TFT (Temporal Fusion Transformer), DeepAR, LightGBM+LSTM
- Temporal CV: 4 folds, test_size=52 weeks, `fecha_corte=2025-01-01`
- Metrics: RMSE (selection), MAPE, MAE, **MASE** (Hyndman & Koehler, 2006 — naive lag-52 benchmark)
- Weighted folds: [0.5, 0.75, 1.0, 1.25] (COVID fold penalized)

**Pipeline 2 — Local production (`entrena.py` → `predice.py`):**
- Uses only Prophet with optimal HPs from Pipeline 1
- Features: Log-transform, Fourier seasonality, COVID holiday, regime changes
- Hybrid mode: Regional fallback for sparse Alzheimer series
- Output: `.pkl` serialized models → forecasts 120 weeks ahead
- Dashboard: Tableau Public at `proyectointegrador.org/epidashboard`

**SageMaker Run History:**

| Version | Scope | Trials | Duration | Cost | Key Result |
|---------|-------|--------|----------|------|------------|
| v4 (baseline) | 95 series (general only) | 570 | 8.6h | ~$8.50 | Dep MAPE 6.8%, Park 31.3%, Alz 40.8% |
| v5 (optimized grids) | 93 series (general only) | 558 | 3.7h (-57%) | ~$3.70 | CV RMSE −0.7%, Prophet winner 46.2% |
| v5-full (production) | 297 series (3 sexes × 33 regions) | 1,782 | ~12h | ~$12 | Full demographic coverage + MASE |

**Note:** The v5-full SageMaker run evaluated 297 series (32 states + 1 national × 3 conditions × 3 sexes). The additional 36 regional fallback models bring the production total to **333 series**.

**Model ranking (Aguascalientes Depression test — sanity check):**

| Rank | Model | CV RMSE | Test RMSE | Test MAPE |
|------|-------|---------|-----------|-----------|
| 1 | Prophet | 0.337 | 0.293 | 6.95% |
| 2 | DeepAR | 0.377 | **0.235** | **5.45%** |
| 3 | LightGBM+LSTM | 0.405 | 0.293 | 6.75% |
| 4 | Ridge | 0.415 | 0.321 | 7.53% |
| 5 | XGBoost | 0.449 | 0.299 | 6.96% |
| 6 | TFT | 0.542 | 0.374 | 8.90% |

### 2.4 Ensemble & Stacking Improvements

- Enhanced feature engineering: expanded from 8 to 20 temporal features
- XGBoost hyperparameter optimization
- Parallel ensemble architecture with learned weights via Ridge regression
- ElasticNet regularization for ensemble weight selection

### 2.5 Weekly Validation (Real-Time, Unseen Data)

The team performed weekly validation using **real epidemiological data that the models had never seen** — data published AFTER training cutoff. This is referenced in the HTML report at `reports/ProdDetails/validacion_semanal.html`. This validation demonstrated that the models generalize to real-world future data, not just held-out test sets. **Emphasize this heavily** — models had zero access to this data, it is genuine out-of-sample forecasting validated against ground truth.

### 2.6 MLOps Infrastructure

**Repository structure:** Cookiecutter Data Science v2

**Code quality:**
- 536+ tests, 82%+ coverage
- Zero ruff errors, zero mypy errors
- Pre-commit hooks: ruff, mypy, trailing-whitespace, end-of-file-fixer, check-yaml, large-files
- Every file < 300 lines (SRP)
- Every module has docstrings
- No `print()` in package — uses `loguru` structured logging
- No wildcard imports
- GitHub Actions CI/CD pipeline

**SOLID Principles implementation:**
- **S** (Single Responsibility): Each module handles one concern (cleaner.py, filter.py, transformer.py, etc.)
- **O** (Open/Closed): `ForecastModel` abstract base class — new models extend without modifying existing code
- **L** (Liskov Substitution): All forecasters interchangeable via `ForecastModel` interface
- **I** (Interface Segregation): Separate interfaces for training, prediction, evaluation
- **D** (Dependency Inversion): `ModelFactory` instantiates from config, no hardcoded dependencies

**Clean Code practices:**
- Meaningful variable names in Spanish for domain concepts
- Functions < 20 lines, classes < 300 lines
- Configuration-driven via OmegaConf YAML files
- Immutable data pipelines (no side effects)
- Comprehensive error handling with custom exceptions

**EPI Console (Makefile CLI):**
The project includes a comprehensive Makefile-based CLI console with 40+ commands:
- `make preprocess` — Full preprocessing pipeline (filter → clean → transform)
- `make train` — Train all 333 Prophet models with cross-validation
- `make predict` — Generate 120-week forecasts
- `make quality` — Full quality gate (lint + typecheck + test)
- `make model-pipeline` — Complete modeling flow
- `make data-weekly PDF=file.pdf` — Weekly data ingestion workflow
- `make s3-sync` — Push to AWS S3
- `make report` — Generate HTML monitoring reports
- `make bitacora` — Generate modeling log (HTML)
- `make tableau` — Build Tableau dataset
- `make data-pull` / `make data-push` — DVC sync with S3

**Data versioning:** DVC with AWS S3 backend (`epiforecast-mx-data` bucket)

**Monitoring & reporting HTMLs built:**
- Weekly validation HTML reports
- Model comparison dashboards
- Cross-validation performance visualizations
- Bitácora (modeling log) with all training iterations
- Prophet forecast charts with prediction intervals per state/condition/gender

### 2.7 Key Learnings & Discoveries

1. **Accuracy metrics are inappropriate** for continuous forecasting — regression metrics (MAPE, RMSE, MAE, MASE) measure proximity, not exact matches
2. **Prophet seasonality `period` parameter** must account for day-based interpretation, not week-based — prevents sawtooth artifacts
3. **COVID-period data creates bias** toward rigid hyperparameters — must be carefully managed with weighted CV folds
4. **Log-transform fundamentally changes** seasonality mode selection — additive wins significantly more often post-transform
5. **State-level modeling > regional** — better granularity, captures local patterns
6. **Data represents rates per 100,000 inhabitants**, not absolute numbers — fundamental insight shaping all analysis
7. **MASE < 1** means the model beats the seasonal naive baseline (lag-52 weeks) — critical benchmark per Hyndman & Koehler (2006)

---

## 3. DELIVERABLE OBJECTIVES (RUBRIC ALIGNMENT)

The Avance 6 must address three rubric dimensions at the **"Excelente"** level:

### 3.1 Model Analysis (Análisis del Modelo)
- Present results compared against success criteria defined in Phase 0 (Avance 0)
- Answer with justification:
  - Is model performance sufficient for production deployment? → **YES, with evidence**
  - Is there room for further improvement? → **YES, describe specific paths**
  - What are the key recommendations for implementation?
- Reference Avance 0 success criteria explicitly

### 3.2 Actionables (Accionables)
- Specific, clear tasks/procedures for each stakeholder:
  - **IMSS (Dr. Ruth Pérez-Hernández, Dr. Lina Díaz Castro):** Data pipeline integration, variable expansion, policy recommendations
  - **Academic (Dra. Grettel Barceló Alonso):** Publication strategy, conference presentations (Stockholm, Portugal)
  - **Technical team:** Production deployment, monitoring, model retraining schedule
  - **Mexico's Health Secretary (Secretaría de Salud):** Potential integration, additional variables

### 3.3 Cloud Implementation Analysis (Implementación)
- **Compare at least 2 cloud providers** with clear evaluation factors
- **Primary recommendation: AWS SageMaker** (we are already using it — show why it's the best choice with hard evidence)
- **Secondary: Google Cloud Vertex AI**
- Also briefly evaluate: Azure ML, IBM Watson
- **Factors:** Cost, scalability, specific ML services, ease of use, integration with existing infrastructure, GPU availability, managed endpoints
- **Include references** from official cloud provider documentation
- **Cite the reference PDFs:** Korolov (2022) from CIO, Miller (2022) from Project Leadership and Society

---

## 4. DOCUMENT STRUCTURE & CONTENT REQUIREMENTS

### 4.0 Cover Page (Carátula)
- Same institutional style as Avance 5: Tecnológico de Monterrey logo (`postgradotec.png`), course info, team names with student IDs
- Color: `tecblue` RGB(0,51,102)
- Leave placeholders for team photos (`JARCOS3.png`, `JARS3.png`, `Luis3.png`) and logo — we will upload them manually
- Include: "Maestría en Inteligencia Artificial Aplicada", "TC5035.10 Proyecto Integrador", "Semana 8", "Avance 6. Conclusiones Clave", "Equipo #01"
- **Add the project web URL:** `https://proyectointegrador.org`

### 4.1 Table of Contents + List of Figures + List of Tables

### 4.2 Executive Summary (Resumen Ejecutivo)
- 1-page maximum
- Key findings, recommendation to deploy, cloud selection

### 4.3 Introduction & Project Context
- Brief project recap
- Link to Avance 0 success criteria
- Mention web presence and Tableau dashboard
- Define the three conditions with ICD-10 codes
- Mention IMSS collaboration and institutional significance
- **First-mention definitions:** Define every technical term the first time it appears (MAPE, RMSE, Prophet, cross-validation, etc.) in parenthetical explanations for non-technical readers

### 4.4 MLOps Infrastructure Deep Dive
This is a MAJOR section. Cover:
- **Cookiecutter Data Science v2** structure with directory tree diagram
- **SOLID principles** — explain each one with concrete examples from the codebase
- **Clean Code practices** — naming conventions, function size limits, documentation standards
- **GitHub Actions CI/CD** — automated testing on every push, quality gates
- **EPI Console** — the Makefile CLI with 40+ commands, show the full command list
- **DVC + AWS S3** — data versioning workflow
- **Testing:** 536+ tests, 82%+ coverage, zero linter/type errors
- **Pre-commit hooks** — automated quality enforcement
- **Monitoring & reporting HTMLs** — describe each HTML report built for pipeline monitoring
- **Generate an impressive architectural diagram** of the entire system (use TikZ or a generated image)

### 4.5 Model Performance Analysis
- **Baseline Prophet results** (333 models) with tables and charts
- **SageMaker comparison** (6 models × 333 series = 1,332 evaluations) — present the ranking
- **MAPE, RMSE, MAE, MASE** breakdown by condition, state, and gender
- **Semaphore classification** of model quality per state (Excellent < 10%, Acceptable 10–20%, Needs Improvement 20–30%, Insufficient > 30%)
- **Cross-validation details** with fold visualization
- **Gender analysis:** How female vs male models compare
- **State-level heatmap** of performance
- **COVID impact analysis** on model performance

### 4.6 Weekly Validation with Real Data (CRITICAL SECTION)
- **This week's validation results** against real, unseen SINAVE data
- **Emphasize:** Models had ZERO access to this data. It was published after training cutoff.
- Show comparison tables: predicted vs actual
- Discuss prediction interval coverage
- Reference `validacion_semanal.html`
- This section should be emotionally compelling — this is the moment the models proved themselves on genuinely unseen real-world data

### 4.7 Condition-Specific Conclusions (Conclusiones por Padecimiento)
**For each condition (Depression, Parkinson, Alzheimer):**
- Epidemiological insights discovered
- Best/worst performing states and why
- Gender differential analysis
- Seasonal patterns identified
- Clinical and policy implications
- Recommendations for IMSS resource allocation

### 4.8 Cloud Provider Analysis
- **Comparative table** with weighted scoring across at least 8 factors: cost, scalability, GPU availability, managed training jobs, Docker/container support, MLOps tooling, free tier, community/documentation
- **AWS SageMaker (PRIMARY):** Deep analysis — already in use, show specific services used (ECR, SageMaker Training Jobs, S3, CloudWatch), cost analysis from REAL runs ($3.70–$12 per batch), GPU availability (`ml.g4dn.xlarge` at $0.736/hr), Docker/ECR integration. Include our `sagemaker_launcher.py` workflow. Show that migration cost = $0 because infrastructure already exists.
- **Google Cloud Vertex AI (SECONDARY):** Managed notebooks, AutoML time series ($0.20/1K data points), $300 free credits, Vertex AI Forecast service, pipeline runs ($0.03/run), BigQuery integration. Compare custom training at ~$0.22/hr CPU.
- **Azure ML:** No additional ML service charge (pay compute only), GPU from $0.90/hr (T4), low-priority VMs at 80% discount, Designer no-code interface, Azure DevOps integration. $200 free credits.
- **IBM watsonx.ai:** Essentials at $1,050/month minimum, CUH billing model, opaque enterprise pricing, strong governance but significantly more expensive. Lite tier limited to 20 CUH/month.
- **Final recommendation with justification** — AWS wins because of: (1) existing infrastructure with zero migration cost, (2) proven cost efficiency from real production runs, (3) Docker/ECR-native workflow matching our Cookiecutter structure, (4) SageMaker managed training jobs perfectly suited for our 1,332-evaluation comparison pipeline, (5) S3 already integrated with DVC for data versioning
- **Use the data from Section 6.2** — all pricing figures, URLs, and references are provided there
- **References:** Official documentation URLs from Section 6.2, Korolov (2022), Miller (2022)

### 4.9 Actionable Tasks for Stakeholders
- Formatted as a clear assignment matrix
- Each task: WHO does WHAT by WHEN with WHAT resources
- Stakeholder groups: IMSS Clinical, IMSS IT, Academic Team, Technical Team, Health Secretary

### 4.10 Production Deployment Proposal
- Architecture diagram for production environment
- Model retraining schedule (weekly with new SINAVE data)
- Monitoring strategy (drift detection, performance degradation alerts)
- Scalability plan (new conditions, new data sources)
- Cost projection for 12-month operation

### 4.11 Future Work & Expansion
- Age range disaggregation
- Mortality data integration
- Pharmacological cost analysis
- Additional conditions beyond F32, G20, G30
- Integration with IMSS operational systems
- Publication roadmap (Stockholm, Portugal conferences)

### 4.12 Team Reflections (Reflexiones Personales)
- Leave placeholder text for each team member with their photo (wrapfigure)
- We will fill these in manually

### 4.13 References (APA 7, Strictest Format)
- All web references must include retrieval date
- Use DOI when available
- Include: Korolov (2022), Miller (2022), Hyndman & Koehler (2006), Prophet documentation, AWS/GCP/Azure/IBM official docs
- **Search the web** for any additional references you cite — every claim must be backed

### 4.14 Glossary (Glosario)
- Alphabetical glossary of all technical terms for non-technical readers
- Include at minimum: MAPE, RMSE, MAE, MASE, Prophet, Cross-Validation, SINAVE, ICD-10, DVC, MLOps, CI/CD, Docker, ECR, SageMaker, Fourier Seasonality, Changepoint, Hyperparameter, Log-Transform, SOLID, API, Cookiecutter, GitHub Actions, OmegaConf, Ridge Regression, XGBoost, DeepAR, TFT, LightGBM, LSTM, Ensemble, Stacking

### 4.15 Appendices
- Full EPI Console command reference
- Complete SageMaker run logs summary
- Model performance tables (all 333 models)

---

## 5. LaTeX STYLE REQUIREMENTS

### 5.1 Follow the Avance 5 Style
Match the style from `Avance5_main.tex`:
- `\documentclass[12pt,letterpaper]{article}`
- `\usepackage[spanish]{babel}` with `\usepackage[utf8]{inputenc}`
- Color scheme: `tecblue` RGB(0,51,102), `tecgreen` RGB(0,76,70)
- Fancy headers with project name and team number
- Section formatting with `\titleformat` colored in `tecblue`
- Professional tables with `booktabs` (`\toprule`, `\midrule`, `\bottomrule`)
- Figures with proper captions and labels
- `\hyperref` links in `tecblue`

### 5.2 Visual Excellence Requirements
- **Every table** must use `booktabs` styling
- **Every figure** must have a descriptive caption and label
- **Color-coded sections** for each condition (suggest: blue for Depression, green for Parkinson, purple for Alzheimer)
- **Professional charts** — generate them as standalone HTML files or Python-generated PNGs
- **Architecture diagrams** — use TikZ or generate as high-res images
- **Heatmaps** for state-level performance
- **Semaphore tables** with color-coded cells (green/yellow/orange/red)
- **Box plots** or violin plots for MAPE distribution by condition

### 5.3 Charts & Figures to Generate
Create these as auxiliary files (HTML or Python-generated PNGs) that will be included in the LaTeX:

1. **System architecture diagram** — Full MLOps pipeline from SINAVE PDF → Prophet/SageMaker → Tableau dashboard
2. **Model comparison radar chart** — 6 models across multiple metrics
3. **MAPE heatmap by state** — 32 states × 3 conditions, color-coded
4. **Cross-validation fold diagram** — Visual showing the temporal CV strategy
5. **Cloud provider comparison chart** — Weighted scoring visualization
6. **Stakeholder action matrix** — Visual Gantt-like timeline
7. **Weekly validation comparison** — Predicted vs actual overlay
8. **Gender performance comparison** — Grouped bar chart
9. **COVID impact timeline** — Performance degradation during COVID period
10. **Pipeline flow diagram** — Makefile command chain visualization

### 5.4 Images We Will Upload Manually
For these, just leave `\includegraphics` placeholders with clear filenames and add a LaTeX comment `% MANUAL: Upload screenshot of [description]`:
- Cover page logo: `postgradotec.png`
- Team photos: `JARCOS3.png`, `JARS3.png`, `Luis3.png`
- Any Tableau dashboard screenshots
- Any terminal/console screenshots
- Weekly validation HTML screenshots
- GitHub Actions CI/CD screenshots
- SageMaker console screenshots

---

## 6. REFERENCES TO CONSULT & CITE

### 6.1 Required Reference PDFs (provided by instructor)
- Korolov, M. (2022, September 7). Measuring the business impact of AI. *CIO*. https://www.cio.com/article/405620/measuring-the-business-impact-of-ai.html
- Miller, G. (2022, December). Stakeholder roles in artificial intelligence projects. *Project Leadership and Society*, Volume 3. https://doi.org/10.1016/j.plas.2022.100068

### 6.2 Cloud Provider Official Sources & Pricing Data

**Use ALL of this data in the cloud comparison section. Search the web for updated pricing if needed.**

#### AWS SageMaker (PRIMARY — already in use by EpiForecast-MX)
- **Official site:** https://aws.amazon.com/sagemaker/
- **Pricing page:** https://aws.amazon.com/sagemaker/ai/pricing/
- **Key pricing facts from our REAL runs:**
  - Instance used: `ml.g4dn.xlarge` — $0.736/hour (1 NVIDIA T4 GPU, 4 vCPUs, 16 GiB memory)
  - v4 run (95 series, 570 trials): 8.6 hours → ~$8.50
  - v5 run (93 series, 558 trials): 3.7 hours → ~$3.70 (57% cost reduction via grid optimization)
  - v5-full run (297 series, 1,782 trials): ~12 hours → ~$12
  - **Pay-as-you-go**, billed per second, no upfront commitments
  - Free tier: 250 hours t2/t3.medium notebooks, 50 hours m4/m5.xlarge training
  - S3 storage for DVC data versioning: ~$0.023/GB/month
  - ECR for Docker images: standard container registry pricing
  - CloudWatch for monitoring: $0.50/GB ingested
  - SageMaker Savings Plans: up to 64% discount with 1-3 year commitment
- **Key services we use:** SageMaker Training Jobs, ECR (Docker), S3 (DVC + data), CloudWatch (monitoring)
- **Why it wins:** We already have working Docker containers, ECR images, S3 bucket (`epiforecast-mx-data`), and a tested `sagemaker_launcher.py` — zero migration cost
- **References:**
  - Amazon Web Services. (2025). *Amazon SageMaker AI pricing*. https://aws.amazon.com/sagemaker/ai/pricing/
  - Amazon Web Services. (2025). *Amazon SageMaker developer guide*. https://docs.aws.amazon.com/sagemaker/latest/dg/whatis.html
  - Amazon Web Services. (2025). *Amazon SageMaker Training*. https://aws.amazon.com/sagemaker/train/

#### Google Cloud Vertex AI (SECONDARY recommendation)
- **Official site:** https://cloud.google.com/vertex-ai
- **Pricing page:** https://cloud.google.com/vertex-ai/pricing
- **Key pricing facts:**
  - Custom-trained models: ~$0.22/hour (CPU), GPU instances vary by type
  - Vertex AI Forecast (AutoML time series): $0.20 per 1,000 data points
  - AutoML models: $3.465 per node hour
  - Pipeline runs: $0.03 per run
  - Free tier: $300 in credits for 90 days, limited training hours, 5 GB online prediction
  - Pay-as-you-go, billed in 30-second increments
  - Named a Leader in 2024 Gartner Magic Quadrant for Cloud AI Developer Services (5th consecutive year)
  - Named a Leader in 2024 Gartner Magic Quadrant for Data Science and Machine Learning Platforms
  - Supports AutoML for tabular, image, text, video data
  - Integration with BigQuery, TensorBoard, Vertex AI Pipelines
  - Vertex AI Model Monitoring for drift detection
- **Pros vs AWS:** Native AutoML for time series, BigQuery integration, strong MLOps tooling
- **Cons vs AWS:** No existing infrastructure for EpiForecast-MX, would require full migration, less Docker/ECR-native
- **References:**
  - Google Cloud. (2025). *Vertex AI pricing*. https://cloud.google.com/vertex-ai/pricing
  - Google Cloud. (2025). *Vertex AI platform overview*. https://cloud.google.com/vertex-ai
  - Google Cloud. (2025). *Vertex AI documentation*. https://cloud.google.com/vertex-ai/docs
  - Wikipedia. (2025). *Vertex AI*. https://en.wikipedia.org/wiki/Vertex_AI

#### Microsoft Azure Machine Learning
- **Official site:** https://azure.microsoft.com/en-us/products/machine-learning
- **Pricing page:** https://azure.microsoft.com/en-us/pricing/details/machine-learning/
- **Key pricing facts:**
  - No additional charge for Azure ML service itself — pay only for underlying compute/storage
  - GPU instances: Tesla T4 from ~$0.90/hour, V100 from ~$3.06/hour, A100 up to ~$24.48/hour
  - Low-priority VMs: up to 80% discount (interruptible)
  - Spot instances: even deeper discounts but may be preempted
  - Blob Storage: ~$0.018/GB/month (hot tier), ~$0.01/GB/month (cool tier)
  - Free tier: $200 in credits for 30 days
  - Reserved instances: 1 or 3 year commitments for savings
  - Azure ML Designer: drag-and-drop no-code/low-code interface
  - Integration with Azure DevOps for CI/CD
  - Azure Container Instances (ACI) for testing, Azure Kubernetes Service (AKS) for production
- **Pros:** Strong enterprise integration, DevOps pipeline, no-code Designer option, comprehensive monitoring
- **Cons vs AWS:** No existing infrastructure, steeper learning curve for Python-centric teams, container registry has fixed costs
- **References:**
  - Microsoft. (2025). *Azure Machine Learning pricing*. https://azure.microsoft.com/en-us/pricing/details/machine-learning/
  - Microsoft. (2025). *Azure Machine Learning documentation*. https://learn.microsoft.com/en-us/azure/machine-learning/

#### IBM watsonx.ai (formerly Watson Studio)
- **Official site:** https://www.ibm.com/mx-es/watson (Mexico)
- **Pricing page:** https://www.ibm.com/products/watsonx-ai/pricing
- **Key pricing facts:**
  - 3 pricing tiers: Lite (free, 20 CUH/month limit), Essentials ($1,050/month), Standard (contact sales)
  - Resources measured in Capacity Unit Hours (CUH)
  - Free tier: 50,000 tokens/month inference + 20 CUH/month
  - Foundation model inference: per 1,000 tokens (Resource Units)
  - Enterprise plans: "contact us for pricing" — opaque pricing model
  - Watson Machine Learning: Lite, Standard (pay-as-you-go), Professional (flat-rate enterprise)
  - Supports deployment on IBM Cloud, AWS, Azure, or on-premises
  - AutoAI for automated model building
  - IBM Cloud Pak for Data integration
  - Strong governance and explainability tools
- **Pros:** Enterprise governance, hybrid/multi-cloud deployment, strong in regulated industries (healthcare)
- **Cons vs AWS:** Significantly more expensive ($1,050/month minimum for Essentials), steep learning curve, opaque enterprise pricing, smaller ML community, limited GPU instance variety, no existing infrastructure for EpiForecast-MX
- **References:**
  - IBM. (2025). *IBM watsonx.ai pricing*. https://www.ibm.com/products/watsonx-ai/pricing
  - IBM. (2025). *Watson Machine Learning plans*. https://dataplatform.cloud.ibm.com/docs/content/wsj/getting-started/wml-plans.html
  - IBM. (2025). *Watson Studio pricing*. https://www.ibm.com/products/watson-studio/pricing

### 6.3 Technical References
- Taylor, S. J., & Letham, B. (2018). Forecasting at scale. *The American Statistician*, 72(1), 37–45. https://doi.org/10.1080/00031305.2017.1380080 (Prophet paper)
- Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting*, 22(4), 679–688. https://doi.org/10.1016/j.ijforecast.2006.03.001 (MASE)
- Search the web for any additional references needed (SINAVE, INEGI, epidemiological surveillance in Mexico, etc.)

### 6.4 Past Team References (for context, can be cited as antecedents)
- Avance 0 (Phase 0): `Avance0.#Equipo01_vFinal.pdf` — success criteria definition
- Previous team Depression work: `Depresion_PassTeam_Avance6.Equipo16.pdf`
- Previous team Alzheimer work: `Alzheimer_PassTeam_Conclusiones Clave.pdf`

---

## 7. FORMATTING & ORTHOGRAPHY RULES

1. **Spanish orthography must be flawless** — proper ñ, accents (á, é, í, ó, ú), ü where needed
2. **Number format:** Comma for thousands (`1,782`), period for decimals (`14.6%`)
3. **APA 7 references** — strictest compliance, include retrieval dates for web sources
4. **First-mention rule:** Every technical term must be defined in parentheses the first time it appears
5. **Glossary consistency:** Every term in the glossary must also be defined at first mention in the body
6. **Figure/table references:** Always use `\ref{}` — never hardcode figure numbers
7. **No orphan lines** — use `\needspace` or manual breaks where needed
8. **LaTeX comments** for any section requiring manual input: `% TODO: Upload [X]` or `% MANUAL: [description]`

---

## 8. QUALITY CHECKLIST (VERIFY BEFORE DELIVERING)

- [ ] Cover page matches Avance 5 institutional style
- [ ] All three rubric dimensions addressed at "Excelente" level
- [ ] Success criteria from Avance 0 explicitly referenced
- [ ] At least 2 cloud providers compared with clear factors and scoring
- [ ] AWS SageMaker justified as primary choice with cost data from real runs
- [ ] Stakeholder actionables are specific, assigned, and clear
- [ ] Weekly validation with real data highlighted as key evidence
- [ ] Architecture diagram generated
- [ ] All technical terms defined at first mention AND in glossary
- [ ] APA 7 references complete with retrieval dates
- [ ] Spanish orthography verified (ñ, accents)
- [ ] Number format: comma thousands, period decimals
- [ ] Every figure has caption and label
- [ ] Every table uses booktabs styling
- [ ] Placeholder comments for manual screenshots clearly marked
- [ ] Project web URL included
- [ ] IMSS institutional context maintained throughout
- [ ] Monitoring HTML reports and EPI Console documented
- [ ] SOLID principles and Clean Code practices explained with examples
- [ ] Cross-references to previous Avances where relevant
- [ ] Glossary is comprehensive and alphabetically ordered

---

## 9. OUTPUT INSTRUCTIONS

1. **Primary output:** A single `.tex` file named `Avance6_01.tex` ready for Overleaf compilation
2. **Auxiliary outputs:** Any HTML files, Python scripts for chart generation, or TikZ diagrams needed as figure assets
3. **All auxiliary files** should be saved to `reports/ConclusionesClave/` directory
4. **The LaTeX file** should compile cleanly with standard packages available on Overleaf
5. **Target length:** 25–35 pages (comprehensive but not padded)
6. **Leave clear `% MANUAL:` comments** for every image that requires a manual screenshot upload

---

## 10. FINAL INSTRUCTION

Take your time. This is the culmination of 8 weeks of work on a project that could reshape how Mexico's public health system forecasts neurological disease burden. Every sentence should reflect the gravity and ambition of this work. The LaTeX must be technically impeccable, visually stunning, and academically rigorous. Make the reader feel the weight of 1,332 model evaluations across 333 production series, the elegance of a 40-command MLOps console, and the thrill of watching predictions match reality on data the models had never seen.

**Go.**
