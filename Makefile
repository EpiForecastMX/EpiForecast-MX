#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = Alzheimer
PYTHON_VERSION = 3.14
PYTHON_INTERPRETER = python

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Instalar dependencias
.PHONY: requirements
requirements:
	$(PYTHON_INTERPRETER) -m pip install -U pip
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt
	



## Elimina archivos compilados de Python (*.pyc, *.pyo) y carpetas __pycache__
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete


## Analiza el código con Ruff para verificar formato y calidad del código
.PHONY: lint
lint:
	ruff format --check
	ruff check

## Format source code with ruff
.PHONY: format
format:
	ruff check --fix
	ruff format


## Set up Python interpreter environment
.PHONY: create_environment
create_environment:
	
	conda create --name $(PROJECT_NAME) python=$(PYTHON_VERSION) -y
	
	@echo ">>> conda env created. Activate with:\nconda activate $(PROJECT_NAME)"
	



#################################################################################
# PROJECT RULES                                                                 #
#################################################################################


## Obtiene el dataset original para iniciar el flujo de análisis.
.PHONY: data
data: 
	$(PYTHON_INTERPRETER) -m scripts.get_dataset

# Ejecuta el análisis exploratorio de datos (EDA).
.PHONY: eda
eda:
	$(PYTHON_INTERPRETER) -m scripts.realiza_EDA

## Limpia y prepara el dataset eliminando valores nulos, duplicados y formateando columnas.
.PHONY: clean_dataset
clean_dataset:
	$(PYTHON_INTERPRETER) -m scripts.limpieza_dataset



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
