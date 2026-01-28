#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = integrador
PYTHON_VERSION = 3.12
PYTHON_INTERPRETER = python
ACTIVATE := bin/activate

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Instalar dependencias
.PHONY: requirements
requirements:
	$(PYTHON_INTERPRETER) -m pip install -U pip
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt
	

# Elimina archivos compilados de Python (*.pyc, *.pyo) y carpetas __pycache__
.PHONY: clean_py
clean_py:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete


# Analiza el código con Ruff para verificar formato y calidad del código
.PHONY: lint
lint:
	ruff format --check
	ruff check

# Format source code with ruff
.PHONY: format
format:
	ruff check --fix
	ruff format


## Configurar el entorno con conda
.PHONY: create_environment_conda
create_environment_conda:
	@echo ">>> Creando entorno conda..."
	conda create --name $(PROJECT_NAME) python=$(PYTHON_VERSION) -c conda-forge --override-channels -y
	@echo ">>> Entorno creado. Activando e instalando dependencias..."
	conda run -n $(PROJECT_NAME) $(PYTHON_INTERPRETER) -m pip install -U pip
	conda run -n $(PROJECT_NAME) $(PYTHON_INTERPRETER) -m pip install -r requirements.txt
	@echo ">>> conda env created. Activate with:\nconda activate $(PROJECT_NAME)"

## Configurar el entorno con venv
.PHONY: create_environment
create_environment:
	@echo ">>> Creando entorno virtual con venv..."
	$(PYTHON_INTERPRETER)$(PYTHON_VERSION) -m venv $(PROJECT_NAME)
	@echo ">>> Entorno creado. Activando e instalando dependencias..."
	. $(PROJECT_NAME)/$(ACTIVATE) && pip install --upgrade pip && pip install -r requirements.txt
	@echo ">>> venv creado. Activa con: source $(PROJECT_NAME)/$(ACTIVATE)"

## Reinicia la carpeta de registros (logs)
.PHONY: reset_logs
reset_logs:
	@echo ">>> Reiniciando carpeta de logs..."
	@rm -rf ./logs
	@mkdir -p ./logs
	@echo ">>> Carpeta de logs reiniciada."

.PHONY: reset_interim
reset_interim:
	@echo ">>> Reiniciando carpeta interim"
	@rm -rf ./data/interim
	@mkdir -p ./data/interim
	@echo ">>> Carpeta interim reiniciada."

#################################################################################
# DATA VERSION CONTROL (DVC)                                                    #
#################################################################################

## Descargar datos desde S3 (para nuevos colaboradores o sync)
.PHONY: data-pull
data-pull:
	@echo ">>> Descargando datos desde S3..."
	dvc pull
	@echo ">>> Datos sincronizados."

## Subir datos a S3 (después de agregar nuevos PDFs)
.PHONY: data-push
data-push:
	@echo ">>> Subiendo datos a S3..."
	dvc push
	@echo ">>> Datos subidos a S3."

## Agregar nuevo PDF semanal y sincronizar (uso: make data-add PDF=path/to/file.pdf)
.PHONY: data-add
data-add:
ifndef PDF
	$(error Uso: make data-add PDF=ruta/al/archivo.pdf)
endif
	@echo ">>> Agregando nuevo PDF: $(PDF)"
	cp "$(PDF)" data/raw_PDFs/
	dvc add data/raw_PDFs
	@echo ">>> PDF agregado. Ejecuta 'make data-commit' para commitear."

## Commitear cambios de datos y push a remotes
.PHONY: data-commit
data-commit:
	@echo ">>> Commiteando cambios de datos..."
	git add data/raw_PDFs.dvc data/.gitignore
	git commit -m "data: add new weekly PDF $$(date +%Y-%W)"
	dvc push
	git push
	@echo ">>> Datos commiteados y sincronizados."

## Flujo completo semanal: agregar PDF, commitear y push (uso: make data-weekly PDF=path/to/file.pdf)
.PHONY: data-weekly
data-weekly: data-add data-commit
	@echo ">>> Flujo semanal completado."

## Ver estado de DVC
.PHONY: data-status
data-status:
	@echo ">>> Estado de DVC:"
	dvc status
	@echo ""
	@echo ">>> Archivos trackeados:"
	dvc list . --dvc-only

#################################################################################
# PROJECT RULES                                                                 #
#################################################################################

## Obtiene el dataset original para iniciar el flujo de análisis.
.PHONY: get_dataset
get_dataset: 
	$(PYTHON_INTERPRETER) -m scripts.get_dataset

## Filtrar dataset con el padecimiento configurado
.PHONY: filter
filter:
	@echo ">>> Filtrando dataset con el padecimiento configurado..."
	$(PYTHON_INTERPRETER) -m scripts.padecimiento
	@echo ">>> Filtrado completado."

## Limpia y prepara el dataset eliminando valores nulos, duplicados y formateando columnas.
.PHONY: clean
clean:
	@echo ">>> Iniciando limpieza del dataset"
	$(PYTHON_INTERPRETER) -m scripts.limpieza_dataset
	@echo ">>> Limpieza del dataset completada."

## Aplica las conversiones requeridas y acondiciona la información para su procesamiento posterior.
.PHONY: transform
transform:
	@echo ">>> Iniciando extracción y transformación de características..."
	$(PYTHON_INTERPRETER) -m scripts.realiza_prep
	@echo ">>> Preparación completada."

## Ejecuta el flujo completo: filtrar, limpiar y transformar dataset
.PHONY: preprocess
preprocess: reset_logs reset_interim filter clean transform
	@echo ">>> Flujo completo ejecutado."


#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)

## Instalar dependencias del sistema (macOS)
.PHONY: setup_mac
setup_mac:
	brew install ghostscript
	@echo ">>> Dependencias del sistema instaladas."

## Instalar dependencias del sistema (Linux)
.PHONY: setup_linux
setup_linux:
	sudo apt-get install -y ghostscript
	@echo ">>> Dependencias del sistema instaladas."

## Setup completo para nuevos colaboradores (macOS)
.PHONY: setup
setup: setup_mac requirements data-pull
	@echo ">>> Setup completo. Proyecto listo para trabajar."

## Setup completo para nuevos colaboradores (Linux)
.PHONY: setup-linux
setup-linux: setup_linux requirements data-pull
	@echo ">>> Setup completo. Proyecto listo para trabajar."