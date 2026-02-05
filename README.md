# EpiForecast-MX

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

Proyecto para predecir casos de Enfermedades Neurológicas y de Salud Mental en México mediante modelos de aprendizaje automático y análisis demográfico.

## 📂 Organización del proyecto

```
├── .github
│   └── workflows
│       └── scrape_boletines.yml  <- GitHub Actions: scraper automatizado SINAVE (diario 2PM CDMX)
│
├── config              <- Archivos de configuración en formato YAML
│
├── data
│   ├── external        <- Datos obtenidos de fuentes externas (no generados internamente)
│   ├── interim         <- Resultados temporales de transformaciones, útiles para depuración y trazabilidad
│   ├── processed       <- Conjuntos de datos definitivos y estandarizados listos para análisis y modelado
│   ├── raw             <- Captura inicial de datos sin modificaciones
│   ├── raw_PDFs        <- Boletines epidemiológicos en formato PDF (versionados con DVC)
│   └── registry.json   <- Registro de boletines descargados por el scraper (git-tracked)
│
├── docs                <- Proyecto base de documentación
│
├── logs                <- Registros generados automáticamente durante la ejecución del proyecto
│
├── models              <- Modelos entrenados y serializados
│
├── notebooks           <- Notebooks de Jupyter para exploración y análisis
│
├── references          <- Diccionarios de datos, manuales y materiales explicativos
│
├── reports             <- Resultados de análisis exportados en formatos reproducibles (HTML, PDF, LaTeX)
│   └── figures         <- Visualizaciones generadas automáticamente para documentación y reportes
│
├── scripts             <- Carpeta que contiene los archivos en Python utilizados para instanciar clases y orquestar flujos
│   └── scrape_boletines.py  <- Scraper automatizado de boletines SINAVE
│
├── src
│   ├── configuraciones <- Módulos que gestionan parámetros y configuraciones del proyecto desde archivos YAML
│   ├── datos           <- Módulos con clases para limpieza, transformación y preparación de datos
│   ├── extraccion      <- Módulo para extracción de tablas epidemiológicas desde PDFs
│   └── utils           <- Funciones auxiliares para directorios, visualización y generación automatizada de reportes
│
├── Makefile            <- Archivo Makefile que centraliza comandos para automatizar tareas del proyecto
│
├── pyproject.toml      <- Archivo de configuración principal para dependencias y metadatos del proyecto
│
├── README.md           <- Documento inicial con instrucciones, dependencias y guías para configurar y ejecutar el proyecto
│
└── requirements.txt    <- Lista de dependencias en Python necesarias para ejecutar el proyecto
```

## 🐍 Requisitos

- Python 3.12
- Conda o venv
- Git
- AWS CLI (para acceso a datos versionados)

## 🖥️ Dependencias del Sistema

Antes de instalar las dependencias de Python, es necesario instalar **Ghostscript** para el procesamiento de PDFs.

### macOS
```bash
brew install ghostscript
```

Si no tienes Homebrew instalado:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Windows (WSL / Ubuntu)
```bash
sudo apt-get update
sudo apt-get install -y ghostscript
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y ghostscript
```

---

## 📦 Versionado de Datos (DVC + S3)

Este proyecto utiliza **DVC (Data Version Control)** para versionar los datos y almacenarlos en **Amazon S3**. Esto permite:

- Reproducibilidad total del pipeline
- Colaboración eficiente (no subir GBs a Git)
- Historial de cambios en los datos

### Datos versionados

| Dataset | Ubicación | Descripción |
|---------|-----------|-------------|
| `raw_PDFs/` | `data/raw_PDFs/` | 630+ boletines epidemiológicos (~1GB) |
| `dataset_boletin_epidemiologico.csv` | `data/processed/` | Dataset consolidado (60,288+ filas) |

### Configurar acceso a S3

Solicita las credenciales de AWS al equipo y configura:

```bash
aws configure
# AWS Access Key ID: <proporcionado>
# AWS Secret Access Key: <proporcionado>
# Default region: us-east-1
# Default output format: json
```

### Descargar datos

```bash
dvc pull
```

Esto descarga todos los datos versionados (~1GB) a tu máquina local.

### Infraestructura AWS

| Recurso | Valor |
|---------|-------|
| Bucket S3 | `s3://epiforecast-mx-data` |
| DVC cache | `files/md5/` (content-addressed storage) |
| SNS Topic | `arn:aws:sns:us-east-1:564141855321:sinave-alertas` |
| IAM user | `textract-sly-user` |
| Región | `us-east-1` |

---

## 🤖 Scraper Automatizado SINAVE

El proyecto incluye un scraper automatizado que detecta y descarga nuevos boletines epidemiológicos del SINAVE cada día, los versiona con DVC y notifica al equipo por email.

### Arquitectura

```
┌─────────────────────┐     ┌──────────────┐     ┌─────────────┐
│  GitHub Actions      │     │  gob.mx      │     │  AWS S3     │
│  (cron 2PM CDMX)    │────▶│  SINAVE      │     │  DVC cache  │
│                      │     │  boletines   │     │             │
│  1. Scrape           │     └──────────────┘     │             │
│  2. Download PDF     │                          │             │
│  3. DVC pull (629+)  │◀────────────────────────▶│             │
│  4. DVC add + push   │────────────────────────▶│             │
│  5. Git commit       │                          └─────────────┘
│  6. SNS notify       │────────────────────────▶ 📧 Email
└─────────────────────┘
```

### Flujo detallado

1. **Detección**: Selenium scrapes la página de boletines SINAVE, compara con `data/registry.json`
2. **Descarga**: Si hay boletines nuevos, descarga PDFs a `data/raw_PDFs/`
3. **Versionado**: `dvc pull --force` restaura PDFs existentes, agrega los nuevos, `dvc add` + `dvc push`
4. **Commit**: GitHub Actions commitea `registry.json` y `raw_PDFs.dvc` automáticamente
5. **Notificación**: SNS envía email al equipo con detalles de los nuevos boletines

### Archivos del scraper

| Archivo | Descripción |
|---------|-------------|
| `scripts/scrape_boletines.py` | Script principal del scraper (Selenium + requests) |
| `.github/workflows/scrape_boletines.yml` | Workflow de GitHub Actions |
| `data/registry.json` | Registro de boletines descargados (git-tracked) |

### Schedule

El workflow corre automáticamente **todos los días a las 2:00 PM hora CDMX** (20:00 UTC). También se puede disparar manualmente desde la pestaña Actions del repositorio.

### GitHub Secrets requeridos

| Secret | Descripción |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | Credencial de acceso AWS |
| `AWS_SECRET_ACCESS_KEY` | Credencial secreta AWS |
| `AWS_REGION` | Región AWS (`us-east-1`) |
| `SNS_TOPIC_ARN` | ARN del topic SNS para notificaciones (opcional) |

### Sincronizar datos después del scraper

Cuando el scraper descargue un nuevo boletín, sincroniza tu local:

```bash
git pull && dvc pull
```

### Correr el scraper manualmente (local)

```bash
python scripts/scrape_boletines.py
```

Variables de entorno opcionales:
- `SNS_TOPIC_ARN` — ARN del topic SNS para notificaciones
- `AWS_REGION` — Región AWS (default: `us-east-1`)

### Verificar estado

```bash
# Ver cuántos PDFs están versionados
cat data/raw_PDFs.dvc | grep nfiles

# Ver últimos archivos en S3
aws s3 ls s3://epiforecast-mx-data/ --recursive | sort -k1,2 -r | head -10

# Ver registro de boletines
cat data/registry.json
```

---

## 🍎 Configuración en macOS

### 1. Clonar el repositorio
```bash
git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
cd EpiForecast-MX
```

### 2. Crear entorno virtual
Con **venv**:
```bash
make create_environment
```

Con **Conda**:
```bash
make create_environment_conda
```

### 3. Activar el entorno
Con **venv**:
```bash
source integrador/bin/activate
```

Con **Conda**:
```bash
conda activate integrador
```

### 4. Instalar dependencias y descargar datos
```bash
make requirements
aws configure  # Configurar credenciales AWS
dvc pull       # Descargar datos desde S3
```

O en un solo comando (requiere AWS configurado):
```bash
make setup
```

---

## 🐧 Configuración en Windows (WSL)

### 1. Instalar WSL
Ejecuta en PowerShell (como administrador):
```bash
wsl --install Ubuntu
```

### 2. Preparar el script de instalación
Asegúrate de tener el archivo `setup_wsl.sh` en la ruta:
```
\\wsl.localhost\Ubuntu\home\<usuario>\
```

Dale permisos de ejecución al script:
```bash
chmod +x setup_wsl.sh
```

### 3. Ejecutar el script
```bash
./setup_wsl.sh
```

Esto instala: build-essential, Ghostscript, AWS CLI y Miniconda.

### 4. Configurar AWS y clonar repositorio
```bash
aws configure  # Ingresar credenciales proporcionadas por el equipo

git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
cd EpiForecast-MX
```

### 5. Setup completo
```bash
make setup-linux
```

Esto instala dependencias y descarga los datos desde S3.

---

## 📊 Módulo de Extracción de Datos (PDFs)

El proyecto incluye un módulo integrado para extraer tablas epidemiológicas desde los boletines PDF del SINAVE.

### Uso con CLI (Recomendado para automatización)

```bash
# Sincronizar datos desde S3 y ejecutar pipeline
python -m src.extraccion.cli run --sync

# Solo ejecutar (asume datos ya descargados)
python -m src.extraccion.cli run

# Con todas las opciones
python -m src.extraccion.cli run --sync --save-pages --save-tables

# Ver estado de sincronización
python -m src.extraccion.cli status
```

O usando el Makefile:

```bash
make extract-sync   # Sincroniza desde S3 y ejecuta
make extract        # Solo ejecuta (datos locales)
make extract-full   # Ejecuta con todos los outputs
```

### Uso con Interfaz Gráfica

```bash
python -m src.extraccion.gui
```

La GUI permite:
- Seleccionar carpeta de entrada (PDFs)
- Seleccionar carpeta de salida
- Definir keywords (enfermedades a buscar)
- Activar/desactivar guardado de páginas extraídas y CSVs individuales

### Salidas Generadas

| Archivo | Descripción |
|---------|-------------|
| `dataset_boletin_epidemiologico.csv` | Dataset consolidado con todos los datos extraídos |
| `csv_tablas_individuales/` | CSVs por cada PDF procesado (opcional) |
| `pdf_matched_pages/` | PDFs de 1 página con las tablas encontradas (opcional) |

---

## 🔄 Flujo Semanal (Agregar nuevo boletín)

Cada semana se publica un nuevo boletín epidemiológico. Existen dos formas de incorporarlo:

### Opción 1: Automático (recomendado)

El scraper automatizado detecta y descarga nuevos boletines diariamente. Solo necesitas sincronizar tu local:

```bash
git pull && dvc pull
```

Recibirás una notificación por email (SNS) cuando se detecte un nuevo boletín.

### Opción 2: Comando único (manual)
```bash
make data-weekly PDF=~/Downloads/sem01_2025.pdf
```

### Opción 3: Paso a paso (manual)
```bash
# 1. Agregar PDF al tracking
make data-add PDF=~/Downloads/sem01_2025.pdf

# 2. Commit y push a S3
make data-commit
```

Esto:
1. Copia el PDF a `data/raw_PDFs/`
2. Actualiza el tracking de DVC
3. Sube a S3
4. Hace commit y push a Git

---

## 📚 Comandos del Makefile

### Gestión de Datos (DVC)

| Comando | Descripción |
|---------|-------------|
| `make data-pull` | Descarga datos desde S3 |
| `make data-push` | Sube datos a S3 |
| `make data-add PDF=...` | Agrega nuevo PDF al tracking |
| `make data-commit` | Commit y push de cambios de datos |
| `make data-weekly PDF=...` | Flujo completo semanal |
| `make data-status` | Ver estado de sincronización DVC |

### Extracción de PDFs

| Comando | Descripción |
|---------|-------------|
| `make extract` | Ejecuta pipeline de extracción |
| `make extract-sync` | Sincroniza S3 y ejecuta pipeline |
| `make extract-full` | Ejecuta con todos los outputs |

### Setup y Entorno

| Comando | Descripción |
|---------|-------------|
| `make setup` | Setup completo macOS (deps + datos) |
| `make setup-linux` | Setup completo Linux/WSL |
| `make requirements` | Instala dependencias de Python |
| `make create_environment` | Crea entorno con venv |
| `make create_environment_conda` | Crea entorno con Conda |

### Preprocesamiento

| Comando | Descripción |
|---------|-------------|
| `make preprocess` | Flujo completo: filtrar, limpiar, transformar |
| `make filter` | Filtra dataset por padecimiento |
| `make clean` | Limpia dataset (nulos, duplicados) |
| `make transform` | Aplica transformaciones |

### Utilidades

| Comando | Descripción |
|---------|-------------|
| `make help` | Muestra comandos disponibles |
| `make lint` | Analiza código con Ruff |
| `make format` | Formatea código con Ruff |
| `make reset_logs` | Reinicia carpeta de logs |
| `make reset_interim` | Reinicia carpeta interim |
| `make clean_py` | Limpia archivos .pyc y __pycache__ |

---

## 📚 Fuentes de Información

Para la obtención, verificación y actualización de los datos epidemiológicos utilizados en este proyecto, se consultan las siguientes fuentes oficiales:

- **Boletín Epidemiológico Actual**
  Publicado semanalmente por la Dirección General de Epidemiología (DGE).
  Disponible en: https://www.gob.mx/salud/acciones-y-programas/direccion-general-de-epidemiologia-boletin-epidemiologico

- **Histórico de Boletines Epidemiológicos**
  Archivo completo de ediciones previas del boletín epidemiológico.
  Disponible en: https://www.gob.mx/salud/acciones-y-programas/historico-boletin-epidemiologico

Estas fuentes garantizan el acceso a información confiable y actualizada proporcionada por la Secretaría de Salud de México.

---

## 👥 Equipo

- Juan Carlos Pérez Nava
- Luis Gerardo Sánchez
- Javier Augusto Rebull Saucedo

**Asesora:** Dra. Grettel Barceló Alonso - Tecnológico de Monterrey

**Stakeholders IMSS:**
- Dra. Ruth Pérez (Project Leader)
- Dra. Lina Díaz Castro (Psychiatry Researcher)
