#################################################################################
# EpiForecast-MX — Makefile MLOps                                              #
#################################################################################

PROJECT_NAME = integrador
PYTHON_VERSION = 3.12
# Usar el venv del proyecto: el python3 del sistema (homebrew) no tiene epiforecast/joblib.
# Override: make <target> PYTHON=python3 si tu entorno ya está activado.
PYTHON ?= .venv/bin/python
MODELO ?= prophet
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
setup-linux: setup-linux-deps requirements
	@echo ">>> Instalando DVC[s3]..."
	. $(PROJECT_NAME)/$(ACTIVATE) && pip install "dvc[s3]"
	$(MAKE) data-pull
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
	$(PYTHON) -m scripts.filtra_padecimiento $(ARGS)

## Limpiar dataset (nulos, duplicados, formato)
.PHONY: clean
clean:
	@echo ">>> Limpiando dataset..."
	$(PYTHON) -m scripts.limpieza_dataset $(ARGS)

## Feature engineering (outliers, regiones, agrupación)
.PHONY: transform
transform:
	@echo ">>> Transformando dataset..."
	$(PYTHON) -m scripts.realiza_prep $(ARGS)

## Descargar datos demográficos INEGI
.PHONY: get-inegi
get-inegi:
	@echo ">>> Descargando datos INEGI..."
	$(PYTHON) -m scripts.descarga_inegi

## Mapear entidades con INEGI → CSV + XLSX
.PHONY: mapper
mapper:
	@echo ">>> Mapeando entidades con INEGI..."
	$(PYTHON) -m scripts.mapea $(ARGS)

## Pipeline completo de preprocesamiento (secuencial)
.PHONY: preprocess
preprocess: reset get-dataset filter clean transform get-inegi mapper
	@echo ">>> Preprocesamiento completo."

#################################################################################
# DENGUE (en preparacion — pipeline propio, separado del neuro)                 #
#################################################################################
# El Dengue vive en una tabla aparte del boletin SINAVE (3 severidades A97.x) y se
# incorpora con su propio flujo. El prep lee del CONSOLIDADO (que ya contiene Dengue),
# NO del data_raw.csv neuro; por eso el override de data.raw_data_file=${data.boletin}
# (interpolacion OmegaConf -> fuente unica, sin duplicar la ruta del consolidado).
DASHBOARD_DENGUE   := ../EpiForecast-IMSS-Dashboard/Reports/dengue
DASHBOARD_EPIBOT   := ../EpiForecast-IMSS-Dashboard/epibot
DASHBOARD_MOTORES  := ../EpiForecast-IMSS-Dashboard/Reports/motores

## Donas de distribucion de motores por padecimiento neuro (EpiBot)
.PHONY: donas-motores
donas-motores:
	@echo ">>> Generando donas de motores (Depresion/Parkinson/Alzheimer)..."
	$(PYTHON) scripts/genera_donas_motores.py --out $(DASHBOARD_MOTORES)
	@echo ">>> → Reports/motores/*_motores_dona.png"

## Regenera la galeria neuro en estilo LIMPIO (real + motor productivo, como Dengue)
.PHONY: neuro-gallery
neuro-gallery:
	@echo ">>> Regenerando galeria neuro (estilo limpio, real + motor productivo)..."
	$(PYTHON) -m scripts.build_neuro_gallery --out ../EpiForecast-IMSS-Dashboard/Reports
	@echo ">>> Re-llaveando zoom por serie para el EpiBot (estado x sexo)..."
	$(PYTHON) scripts/build_epibot_zoom.py --reports ../EpiForecast-IMSS-Dashboard/Reports --out $(DASHBOARD_EPIBOT)
	@echo ">>> → Reports/{Depresión,Parkinson,Alzheimer}/*/ (sobrescritos) + epibot/zoom_series.json"

## Re-llave los zoom_data_*.json de la galeria a epibot/zoom_series.json (zoom del bot por estado/sexo)
.PHONY: epibot-zoom
epibot-zoom:
	$(PYTHON) scripts/build_epibot_zoom.py --reports ../EpiForecast-IMSS-Dashboard/Reports --out $(DASHBOARD_EPIBOT)

## Entrena DeepAR nativo por region de Dengue (una a la vez, ~80 min) y cachea su pronostico.
## El backtest OOS mostro que DeepAR nativo es el mejor para las regiones (MAE 460 vs 3.7k-10k de
## la agregacion). Correr antes de build_dengue_gallery para que las regiones usen DeepAR nativo.
.PHONY: dengue-deepar-regiones
dengue-deepar-regiones:
	$(PYTHON) -m scripts.build_dengue_deepar_regiones

## Extraer la serie de Dengue (agregada A97.0+A97.1+A97.2) de los boletines SINAVE
.PHONY: dengue-extract
dengue-extract:
	@echo ">>> Extrayendo Dengue de los boletines... (ARGS='--incremental' para solo los nuevos)"
	$(PYTHON) -m scripts.extrae_dengue $(ARGS)

## Serie historica A90/A91 (OMS 1997, 2014->2018-W26) SEPARADA para contexto/EDA (no entrena)
.PHONY: dengue-historico-a9091
dengue-historico-a9091:
	@echo ">>> Extrayendo serie historica Dengue A90/A91 (contexto, no se mergea)..."
	$(PYTHON) -m scripts.extrae_dengue_a9091

## Integrar la serie de Dengue al dataset consolidado (idempotente)
.PHONY: dengue-merge
dengue-merge:
	@echo ">>> Integrando Dengue al consolidado..."
	$(PYTHON) -m scripts.merge_dengue
	@echo ">>> Recuerda versionar: dvc add + dvc push del consolidado, luego commit del .dvc (push ANTES del commit)"

## Prep de Dengue (filter->clean->transform->mapper) desde el consolidado -> data_inegi_Dengue.csv
.PHONY: dengue-prep
dengue-prep:
	@echo ">>> Preprocesando Dengue (outliers off, INEGI)..."
	$(PYTHON) -m scripts.filtra_padecimiento padecimiento.tipo='Dengue' data.raw_data_file='$${data.boletin}'
	$(PYTHON) -m scripts.limpieza_dataset padecimiento.tipo='Dengue'
	$(PYTHON) -m scripts.realiza_prep padecimiento.tipo='Dengue'
	$(PYTHON) -m scripts.mapea padecimiento.tipo='Dengue'

## Entrenar Dengue NACIONAL para un motor (ARGS, p.ej. ARGS="modelo_activo=prophet")
.PHONY: dengue-train-nacional
dengue-train-nacional:
	@echo ">>> Entrenando Dengue nacional..."
	$(PYTHON) -m scripts.entrena padecimiento.tipo='Dengue' padecimiento.solo_nacional=True $(ARGS)

## Entrenar Dengue ESTATAL (los 4 motores; idempotente con entrena_modelo=False)
.PHONY: dengue-train-estatal
dengue-train-estatal:
	@echo ">>> Entrenando Dengue estatal ($(MODELO))..."
	$(PYTHON) -m scripts.entrena padecimiento.tipo='Dengue' padecimiento.solo_nacional=False modelo_activo=$(MODELO) $(ARGS)

## Seleccionar motor productivo por serie (DeepAR/Prophet) via SMAPE 2026 real
.PHONY: dengue-produccion
dengue-produccion:
	@echo ">>> Seleccionando motor productivo de Dengue..."
	$(PYTHON) -m scripts.produccion_dengue
	@echo ">>> -> reports/ProdDetails/produccion_dengue.{csv,xlsx}"

## Regenerar artefactos web de Dengue (charts + JSON tabla en vivo + galeria EDA)
.PHONY: dengue-web
dengue-web:
	@echo ">>> Regenerando web de Dengue..."
	$(PYTHON) -m scripts.build_dengue_web --out $(DASHBOARD_DENGUE) --generado $$(date +%Y-%m-%d)
	$(PYTHON) -m scripts.build_dengue_forecast_web --out $(DASHBOARD_DENGUE) --generado $$(date +%Y-%m-%d)
	$(PYTHON) -m scripts.eda_dengue_charts --out $(DASHBOARD_DENGUE)
	$(PYTHON) -m scripts.dengue_showcase_charts --out $(DASHBOARD_DENGUE)
	$(PYTHON) scripts/dengue_pronostico_nino.py --out $(DASHBOARD_DENGUE)
	$(PYTHON) scripts/build_dengue_gallery.py --out $(DASHBOARD_DENGUE)
	@echo ">>> Galeria por entidad generada. Inyecta los items en Reports/index.html (ver _gallery_items.json)."
	@echo ">>> Regenerando knowledge.json del EpiBot (incluye la seccion 'dengue')..."
	$(PYTHON) scripts/build_web_knowledge.py
	cp web_dashboard/knowledge.json $(DASHBOARD_EPIBOT)/knowledge.json
	@echo ">>> EpiBot knowledge.json actualizado. Si tocaste kb.js/entities.js, sube el cache-bust (?v=N)."

## Pipeline Dengue: extract -> merge -> prep (luego: dvc push, dengue-train-nacional, dengue-web)
.PHONY: dengue-pipeline
dengue-pipeline: dengue-extract dengue-merge dengue-prep
	@echo ">>> Pipeline Dengue (extract+merge+prep) completo. Falta: dvc push, entrenamiento y web."

#################################################################################
# 🤖 MODELING                                                                  #
#################################################################################

## Entrenar modelos según config (CV + train final)
.PHONY: train
train:
	@echo ">>> Entrenando modelos..."
	$(PYTHON) -m scripts.entrena $(ARGS)

## Entrenar modelos Prophet
.PHONY: train-prophet
train-prophet:
	@echo ">>> Entrenando modelos Prophet..."
	$(PYTHON) -m scripts.entrena modelo_activo='prophet' $(ARGS)

## Entrenar modelos DeepAR
.PHONY: train-deepar
train-deepar:
	@echo ">>> Entrenando modelos DeepAR..."
	$(PYTHON) -m scripts.entrena modelo_activo='deepar' $(ARGS)

## Entrenar modelos Stacking (Prophet + ETS + LightGBM)
.PHONY: train-stacking
train-stacking:
	@echo ">>> Entrenando modelos Stacking..."
	$(PYTHON) -m scripts.entrena modelo_activo='stacking' $(ARGS)

## Entrenar modelos Ensemble (Prophet + XGBoost)
.PHONY: train-ensemble
train-ensemble:
	@echo ">>> Entrenando modelos Ensemble..."
	$(PYTHON) -m scripts.entrena modelo_activo='ensemble' $(ARGS)

## Entrenar todos los modelos (secuencial)
.PHONY: train-all
train-all: train-prophet train-deepar train-ensemble train-stacking

## Entrenar DeepAR en SageMaker (build + launch)
.PHONY: train-sagemaker
train-sagemaker:
	@echo ">>> Build imagen Docker + lanzar en SageMaker..."
	$(PYTHON) aws/sagemaker_launcher.py --build --launch

## Solo build imagen Docker para SageMaker
.PHONY: train-sagemaker-build
train-sagemaker-build:
	@echo ">>> Build imagen Docker..."
	$(PYTHON) aws/sagemaker_launcher.py --build

## 3 jobs paralelos en SageMaker (1 por padecimiento, ~15 min total)
.PHONY: train-sagemaker-parallel
train-sagemaker-parallel:
	@echo ">>> Lanzando 3 jobs en paralelo (Alzheimer, Depresion, Parkinson)..."
	$(PYTHON) aws/sagemaker_launcher.py --parallel

## Build + 3 jobs paralelos en SageMaker
.PHONY: train-sagemaker-fast
train-sagemaker-fast:
	@echo ">>> Build + 3 jobs paralelos en SageMaker..."
	$(PYTHON) aws/sagemaker_launcher.py --build --parallel

## Test local con Docker (simula SageMaker)
.PHONY: train-sagemaker-local
train-sagemaker-local:
	@echo ">>> Build + test local con Docker..."
	docker build -t epiforecast-mx-deepar -f aws/Dockerfile .
	$(PYTHON) aws/sagemaker_launcher.py --local

## Generar predicciones (52 semanas, desnormalizadas)
.PHONY: predict
predict:
	@echo ">>> Generando predicciones..."
	$(PYTHON) -m scripts.predice $(ARGS)

## Generar predicciones de los 4 modelos (Prophet, DeepAR, Ensemble, Stacking)
.PHONY: predict-all
predict-all:
	@echo ">>> Predicciones Prophet..."
	$(PYTHON) -m scripts.predice modelo_activo='prophet' $(ARGS)
	@echo ">>> Predicciones DeepAR..."
	$(PYTHON) -m scripts.predice modelo_activo='deepar' $(ARGS)
	@echo ">>> Predicciones Ensemble..."
	$(PYTHON) -m scripts.predice modelo_activo='ensemble' $(ARGS)
	@echo ">>> Predicciones Stacking..."
	$(PYTHON) -m scripts.predice modelo_activo='stacking' $(ARGS)
	@echo ">>> Predicciones completas para los 4 modelos."

## Construir dataset Tableau
.PHONY: tableau
tableau:
	@echo ">>> Construyendo dataset Tableau..."
	$(PYTHON) -m scripts.build_tableau

## Generar reporte HTML de resultados
.PHONY: report
report:
	@echo ">>> Generando reporte HTML (multi-modelo neuro + Dengue, desde tabla_333 + produccion_dengue)..."
	$(PYTHON) -m scripts.genera_reporte
	@echo ">>> → reports/forecasts/reporte_resultados.html + ../EpiForecast-IMSS-Dashboard/reporte_resultados.html"

## Generar bitácora HTML del modelado Prophet v1-v6
.PHONY: bitacora
bitacora:
	@echo ">>> Generando bitácora..."
	$(PYTHON) -m scripts.genera_bitacora
	@echo ">>> → reports/forecasts/bitacora_modelado.html"

## Comparar modelos (Real vs Prophet vs DeepAR)
.PHONY: compare
compare:
	@echo ">>> Generando comparativa de modelos..."
	$(PYTHON) -m scripts.compara_modelos
	@echo ">>> → reports/forecasts/comparacion_modelos/"

## Generar tabla de 333 modelos de producción (Excel IMSS)
.PHONY: tabla-produccion
tabla-produccion:
	@echo ">>> Generando tabla de producción (333 modelos)..."
	$(PYTHON) -m scripts.genera_tabla_produccion
	@echo ">>> → reports/ProdDetails/tabla_333_modelos_produccion.xlsx"

## Congela el pronóstico productivo vigente (snapshot OOS, 4 padecimientos)
.PHONY: congela-pronostico
congela-pronostico:
	@echo ">>> Congelando pronóstico productivo (cola futura, ds > corte)..."
	$(PYTHON) scripts/pronostico_congelado.py freeze
	@echo ">>> → reports/ProdDetails/congelado/"

## Valida el congelado contra boletines posteriores al corte (desempeño honesto OOS)
.PHONY: valida-prospectivo
valida-prospectivo:
	@echo ">>> Validando pronóstico congelado vs realidad no vista..."
	$(PYTHON) scripts/pronostico_congelado.py validar
	@echo ">>> → reports/ProdDetails/validacion_prospectiva.html"

## Comparar métricas entre modelos (Excel + HTML)
.PHONY: compare-metrics
compare-metrics:
	@echo ">>> Generando comparativa de métricas..."
	$(PYTHON) -m scripts.compara_metricas
	@echo ">>> → reports/forecasts/comparacion_modelos/comparacion_metricas.xlsx"
	@echo ">>> → reports/forecasts/comparacion_modelos/comparacion_modelos.html"

## Avance 5: Prophet Base vs Ensemble (Prophet + XGBoost)
.PHONY: avance5
avance5:
	@echo ">>> Avance 5 — Modelo Final..."
	$(PYTHON) -m scripts.avance5_modelo_final $(ARGS)
	@echo ">>> → reports/forecasts/{prophet,ensemble,comparacion_modelos}/"

## Reporte Avance 5: Modelo Final (tablas + 18 graficos + Markdown)
.PHONY: reporte-avance5
reporte-avance5:
	@echo ">>> Reporte Avance 5 — Modelo Final..."
	$(PYTHON) -m scripts.genera_reporte_avance5 $(ARGS)
	@echo ">>> → reports/ProdDetails/avance5_modelo_final.md"
	@echo ">>> → reports/figures/ModeloFinal/"

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

## Refresh semanal COMPLETO (sin retrain): pull CI+DVC, Dengue extract/merge,
## reselect motor, tableau, validacion, galeria neuro+Dengue, zoom, knowledge,
## barra de fechas (auto) y publish dashboard + versionado DVC/S3.
.PHONY: update-week
update-week:
	bash scripts/actualiza_semanal.sh

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
	@echo ">>> Versionando archivos de forecast..."
	@find reports/forecasts -name "all_forecast_*.csv" | xargs -I {} dvc add {}
	dvc push
	@echo ">>> Forecasts versionados y subidos."

## Sync CSVs directo a S3 (sin DVC, acceso rápido)
.PHONY: s3-sync
s3-sync:
	aws s3 cp data/processed/data_inegi_General.csv s3://epiforecast-mx-data/latest/
	aws s3 cp data/processed/tableau.csv s3://epiforecast-mx-data/latest/
	aws s3 sync reports/forecasts/ s3://epiforecast-mx-data/latest/forecasts/ --exclude "*.png"
	@echo ">>> CSVs disponibles en s3://epiforecast-mx-data/latest/"

#################################################################################
# WEB DASHBOARD                                                                #
#################################################################################

## Web Knowledge Base
web-build:
	$(PYTHON) scripts/build_web_knowledge.py

web-dev: web-build
	cd web_dashboard && npx serve -l 3000

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
