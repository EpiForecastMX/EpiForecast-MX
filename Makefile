#################################################################################
# EpiForecast-MX — Makefile MLOps                                              #
#################################################################################

PROJECT_NAME = integrador
PYTHON_VERSION = 3.12
PYTHON = python
ACTIVATE := bin/activate
SRC = src/epiforecast

.DEFAULT_GOAL := help

#################################################################################
# 🔧 SETUP & ENVIRONMENT                                                       #
#################################################################################

## Instalar dependencias (editable + dev)
.PHONY: requirements
requirements:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -e ".[dev]"

## Setup completo macOS (Ghostscript + deps + data)
.PHONY: setup
setup: setup-mac requirements data-pull
	@echo ">>> Setup completo. Proyecto listo."

## Setup completo Linux/WSL
.PHONY: setup-linux
setup-linux: setup-linux-deps requirements data-pull
	@echo ">>> Setup completo. Proyecto listo."

## Instalar dependencias sistema (macOS)
.PHONY: setup-mac
setup-mac:
	brew install ghostscript
	@echo ">>> Ghostscript instalado."

## Instalar dependencias sistema (Linux)
.PHONY: setup-linux-deps
setup-linux-deps:
	sudo apt-get install -y ghostscript
	@echo ">>> Ghostscript instalado."

## Crear entorno virtual (venv)
.PHONY: create-env
create-env:
	$(PYTHON)$(PYTHON_VERSION) -m venv $(PROJECT_NAME)
	. $(PROJECT_NAME)/$(ACTIVATE) && pip install --upgrade pip && pip install -e ".[dev]"
	@echo ">>> venv creado. Activa con: source $(PROJECT_NAME)/$(ACTIVATE)"

## Crear entorno virtual (conda)
.PHONY: create-env-conda
create-env-conda:
	conda create --name $(PROJECT_NAME) python=$(PYTHON_VERSION) -c conda-forge --override-channels -y
	conda run -n $(PROJECT_NAME) $(PYTHON) -m pip install -e ".[dev]"
	@echo ">>> conda env creado. Activa con: conda activate $(PROJECT_NAME)"

#################################################################################
# 📊 DATA PIPELINE                                                             #
#################################################################################

## Reiniciar logs y carpetas temporales
.PHONY: reset
reset:
	@rm -rf ./logs && mkdir -p ./logs
	@rm -rf ./data/interim && mkdir -p ./data/interim
	@echo ">>> Logs e interim reiniciados."

## Obtener dataset base
.PHONY: get-dataset
get-dataset:
	$(PYTHON) -m scripts.get_dataset

## Filtrar por padecimiento (config/params.yaml)
.PHONY: filter
filter:
	@echo ">>> Filtrando dataset..."
	$(PYTHON) -m scripts.filtra_padecimiento

## Limpiar dataset (nulos, duplicados, formato)
.PHONY: clean
clean:
	@echo ">>> Limpiando dataset..."
	$(PYTHON) -m scripts.limpieza_dataset

## Feature engineering (outliers, regiones, agrupación)
.PHONY: transform
transform:
	@echo ">>> Transformando dataset..."
	$(PYTHON) -m scripts.realiza_prep

## Descargar datos demográficos INEGI
.PHONY: get-inegi
get-inegi:
	@echo ">>> Descargando datos INEGI..."
	$(PYTHON) -m scripts.descarga_inegi

## Mapear entidades con INEGI → CSV + XLSX
.PHONY: mapper
mapper:
	@echo ">>> Mapeando entidades con INEGI..."
	$(PYTHON) -m scripts.mapea

## Pipeline completo de preprocesamiento (secuencial)
.PHONY: preprocess
preprocess: reset get-dataset filter clean transform get-inegi mapper
	@echo ">>> Preprocesamiento completo."

#################################################################################
# 🤖 MODELING                                                                  #
#################################################################################

## Entrenar modelos Prophet (CV + train final)
.PHONY: train
train:
	@echo ">>> Entrenando modelos..."
	$(PYTHON) -m scripts.entrena $(ARGS)

## Generar predicciones (52 semanas, desnormalizadas)
.PHONY: predict
predict:
	@echo ">>> Generando predicciones..."
	$(PYTHON) -m scripts.predice $(ARGS)

## Construir dataset Tableau
.PHONY: tableau
tableau:
	@echo ">>> Construyendo dataset Tableau..."
	$(PYTHON) -m scripts.build_tableau

## Generar reporte HTML de resultados
.PHONY: report
report:
	@echo ">>> Generando reporte HTML..."
	$(PYTHON) -m scripts.genera_reporte
	@echo ">>> → reports/forecasts/reporte_resultados.html"

## Generar bitácora HTML del modelado Prophet v1-v6
.PHONY: bitacora
bitacora:
	@echo ">>> Generando bitácora..."
	$(PYTHON) -m scripts.genera_bitacora
	@echo ">>> → reports/forecasts/bitacora_modelado.html"

## Flujo completo de modelado
.PHONY: model-pipeline
model-pipeline: train models-push predict report forecast-push
	@echo ">>> Pipeline de modelado completo."

#################################################################################
# ✅ CODE QUALITY                                                               #
#################################################################################

## Lint: verificar formato y calidad
.PHONY: lint
lint:
	ruff format --check src/epiforecast/ tests/
	ruff check src/epiforecast/ tests/
	@echo ">>> Lint passed."

## Format: auto-formatear código
.PHONY: format
format:
	ruff check --fix src/epiforecast/ tests/
	ruff format src/epiforecast/ tests/
	@echo ">>> Formatted."

## Type check con mypy
.PHONY: typecheck
typecheck:
	mypy src/epiforecast/
	@echo ">>> Type check passed."

## Ejecutar tests
.PHONY: test
test:
	pytest tests/
	@echo ">>> Tests passed."

## Tests rápidos (sin slow/integration)
.PHONY: test-fast
test-fast:
	pytest tests/ -m "not slow and not integration" -x
	@echo ">>> Fast tests passed."

## Quality gate completo (lint + typecheck + test)
.PHONY: quality
quality: lint typecheck test
	@echo ">>> Quality gate passed."

## Instalar pre-commit hooks
.PHONY: hooks
hooks:
	pre-commit install
	@echo ">>> Pre-commit hooks instalados."

## Limpiar archivos compilados
.PHONY: clean-py
clean-py:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	@echo ">>> Python cache limpiado."

#################################################################################
# 📦 DATA VERSION CONTROL (DVC)                                                #
#################################################################################

## Descargar datos desde S3
.PHONY: data-pull
data-pull:
	dvc pull
	@echo ">>> Datos sincronizados."

## Subir datos a S3
.PHONY: data-push
data-push:
	dvc push
	@echo ">>> Datos subidos a S3."

## Agregar nuevo PDF semanal (uso: make data-add PDF=ruta/archivo.pdf)
.PHONY: data-add
data-add:
ifndef PDF
	$(error Uso: make data-add PDF=ruta/al/archivo.pdf)
endif
	cp "$(PDF)" data/raw_PDFs/
	dvc add data/raw_PDFs
	@echo ">>> PDF agregado. Ejecuta 'make data-commit'."

## Commitear datos + push Git y S3
.PHONY: data-commit
data-commit:
	git add data/raw_PDFs.dvc data/.gitignore
	git commit -m "data: add new weekly PDF $$(date +%Y-%W)"
	dvc push
	git push
	@echo ">>> Datos commiteados y sincronizados."

## Flujo semanal completo (uso: make data-weekly PDF=ruta/archivo.pdf)
.PHONY: data-weekly
data-weekly: data-add data-commit
	@echo ">>> Flujo semanal completado."

## Ver estado de DVC
.PHONY: data-status
data-status:
	dvc status
	dvc list . --dvc-only

## Versionar modelos y subir a S3
.PHONY: models-push
models-push:
	dvc add models/
	dvc push
	@echo ">>> Modelos versionados y subidos."

## Versionar forecast y subir a S3
.PHONY: forecast-push
forecast-push:
	dvc add reports/forecasts/all_forecast.csv
	dvc push
	@echo ">>> Forecast versionado y subido."

## Sync CSVs directo a S3 (sin DVC, acceso rápido)
.PHONY: s3-sync
s3-sync:
	aws s3 cp data/processed/data_inegi_General.csv s3://epiforecast-mx-data/latest/
	aws s3 cp reports/forecasts/all_forecast.csv s3://epiforecast-mx-data/latest/
	@echo ">>> CSVs disponibles en s3://epiforecast-mx-data/latest/"

#################################################################################
# 📖 HELP                                                                      #
#################################################################################

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('EpiForecast-MX — Available commands:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)
