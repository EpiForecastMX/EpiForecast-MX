# EpiForecast-MX

Sistema de pronóstico epidemiológico para **Depresión (F32)**, **Parkinson (G20)** y **Alzheimer (G30)** en México, desarrollado en colaboración con el **IMSS** como proyecto integrador de la Maestría en Inteligencia Artificial Aplicada del Tecnológico de Monterrey.

## Resumen

EpiForecast-MX genera pronósticos semanales de incidencia para 32 estados × 3 padecimientos × 3 categorías de sexo (297 modelos Prophet) con intervalos de predicción, alimentados por datos de vigilancia epidemiológica SINAVE (2012–2025) y datos demográficos INEGI.

## Quickstart

```bash
# Clonar y configurar
git clone https://github.com/<org>/EpiForecast-MX.git
cd EpiForecast-MX
make setup          # macOS (instala Ghostscript + deps + DVC pull)
# make setup-linux  # Linux/WSL

# Pipeline completo
make preprocess     # datos → limpieza → features → INEGI
make train          # Prophet CV + entrenamiento final
make predict        # pronósticos 52 semanas
make report         # reporte HTML de resultados
```

## Estructura del proyecto

```
EpiForecast-MX/
├── src/epiforecast/       # Paquete principal
│   ├── data/              # Extracción, ingesta, preprocesamiento
│   ├── features/          # Feature engineering (INEGI merge)
│   ├── models/            # Prophet forecaster, tuner, cross-validator
│   ├── evaluation/        # Métricas (MASE, RMSE, MAPE)
│   ├── visualization/     # Gráficos publicación IMSS + reportes
│   ├── pipelines/         # Orquestación
│   └── utils/             # Config YAML, paths, helpers
├── config/                # Archivos YAML de configuración
├── tests/                 # 536 unit tests (84% coverage)
├── scripts/               # Entry points CLI
├── data/                  # Datos (DVC-tracked)
├── models/                # Modelos serializados (DVC-tracked)
└── forecast/              # Pronósticos generados
```

## Calidad de código

| Métrica | Estado |
|---|---|
| Tests | 536 passing |
| Coverage | 84% |
| Linter (Ruff) | 0 errores |
| Type checking (Mypy) | 0 errores propios |
| Docstrings | 100% funciones públicas |
| Pre-commit hooks | Ruff + Mypy + conventional commits |

```bash
make quality        # lint + typecheck + test
make format         # auto-format con ruff
make hooks          # instalar pre-commit
```

## Data Pipeline

Los datos crudos son boletines PDF semanales de SINAVE. El pipeline extrae tablas, normaliza y transforma:

```bash
make data-add PDF=ruta/boletin.pdf   # agregar nuevo boletín
make data-weekly                      # flujo semanal completo
make data-status                      # ver estado DVC
```

Datos versionados con **DVC** + **S3** como remote storage.

## Stack técnico

- **Python 3.12** · Prophet · scikit-learn · pandas
- **AWS**: SageMaker (training), S3 (storage)
- **MLOps**: DVC (data versioning), GitHub Actions (CI), pre-commit
- **Visualización**: matplotlib/seaborn, Plotly, Tableau Public

## Equipo

- **Javier Augusto Rebull Saucedo** — ML Engineer
- **Juan Carlos Pérez Nava** — IT IMSS
- **Luis Gerardo Sánchez Salazar** — Controls Engineer (Tesla)
- **Dra. Grettel Barceló Alonso** — Asesora académica

## Licencia

MIT — ver [LICENSE](LICENSE).
