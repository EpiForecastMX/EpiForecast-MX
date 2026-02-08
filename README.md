<p align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/IMSS.svg/1200px-IMSS.svg.png" alt="IMSS Logo" width="120"/>
</p>

<h1 align="center">EpiForecast-MX</h1>

<p align="center">
  <strong>Sistema de Pronóstico Epidemiológico para Enfermedades Neurológicas y de Salud Mental en México</strong>
</p>

<p align="center">
  <em>Proyecto Capstone · Maestría en Inteligencia Artificial Aplicada · Tecnológico de Monterrey</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-006341?style=flat&logo=python&logoColor=white" alt="Python 3.12"/>
  <img src="https://img.shields.io/badge/Prophet-Meta-006341?style=flat&logo=meta&logoColor=white" alt="Prophet"/>
  <img src="https://img.shields.io/badge/DVC-S3-006341?style=flat&logo=dvc&logoColor=white" alt="DVC"/>
  <img src="https://img.shields.io/badge/CI%2FCD-GitHub_Actions-006341?style=flat&logo=githubactions&logoColor=white" alt="GitHub Actions"/>
  <img src="https://img.shields.io/badge/Licencia-MIT-006341?style=flat" alt="MIT License"/>
</p>

<p align="center">
  <a href="#descripción">Descripción</a> •
  <a href="#arquitectura">Arquitectura</a> •
  <a href="#instalación">Instalación</a> •
  <a href="#comandos">Comandos</a> •
  <a href="#cicd">CI/CD</a> •
  <a href="#stack-tecnológico">Stack</a> •
  <a href="#equipo">Equipo</a>
</p>

---

## Descripción

**EpiForecast-MX** es una plataforma de inteligencia epidemiológica desarrollada en colaboración con el **Instituto Mexicano del Seguro Social (IMSS)** para el pronóstico de casos de enfermedades neurológicas y de salud mental en México.

### Objetivo

Predecir la incidencia de **Depresión (F32)**, **Parkinson (G20)** y **Alzheimer (G30)** mediante modelos de series de tiempo, utilizando datos históricos (2012-2026) del Sistema Nacional de Vigilancia Epidemiológica (SINAVE) e indicadores demográficos del INEGI.

El sistema genera **proyecciones a nivel nacional y estatal** (32 entidades federativas) con intervalos de predicción confiables, proporcionando herramientas para la **planificación estratégica en salud pública**.

### Características Principales

- **Extracción automatizada** de datos desde boletines epidemiológicos oficiales (PDF)
- **Pipeline CI/CD completo** que detecta, descarga y procesa nuevos boletines diariamente
- **Modelado predictivo** con Facebook Prophet segmentado por región y sexo
- **Versionado de datos** con DVC sobre Amazon S3 para reproducibilidad total
- **Notificaciones automáticas** vía Amazon SNS al equipo cuando se actualizan datos

---

## Arquitectura

### Flujo de Datos

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PIPELINE AUTOMATIZADO                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   SINAVE (Boletines PDF)                                                        │
│           │                                                                      │
│           ▼                                                                      │
│   ┌───────────────────┐      ┌───────────────────┐      ┌──────────────────┐   │
│   │  Scraper Diario   │─────▶│  Extracción PDF   │─────▶│  Dataset CSV     │   │
│   │  (Selenium)       │      │  (Camelot)        │      │  (2012-2026)     │   │
│   └───────────────────┘      └───────────────────┘      └──────────────────┘   │
│           │                          │                          │               │
│           ▼                          ▼                          ▼               │
│   ┌───────────────────────────────────────────────────────────────────────┐    │
│   │                         Amazon S3 (DVC)                                │    │
│   │                    s3://epiforecast-mx-data                            │    │
│   └───────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PIPELINE DE MODELADO                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Dataset CSV ──▶ Limpieza ──▶ Feature Engineering ──▶ INEGI Mapping            │
│                                                              │                   │
│                                                              ▼                   │
│                                    ┌─────────────────────────────────────┐      │
│                                    │         Prophet Model               │      │
│                                    │   (por región × sexo × enfermedad)  │      │
│                                    └─────────────────────────────────────┘      │
│                                                              │                   │
│                                                              ▼                   │
│                                                     Pronósticos CSV              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Componentes Principales

| Módulo | Descripción |
|--------|-------------|
| `src/extraccion/` | Extracción de tablas desde PDFs con Camelot y búsqueda por keywords |
| `src/datos/` | Limpieza, filtrado por padecimiento y feature engineering |
| `src/modelado/` | Implementación de Prophet con validación cruzada temporal |
| `src/configuraciones/` | Carga de configuración YAML y logging con Loguru |
| `scripts/` | Orquestadores para Makefile y CI/CD |

---

## Estructura del Proyecto

```
EpiForecast-MX/
│
├── .github/workflows/          # Pipelines CI/CD
│   ├── scrape_boletines.yml    #   └─ Scraper diario SINAVE (2 PM CDMX)
│   └── process_boletines.yml   #   └─ Extracción y merge automático
│
├── config/                     # Configuración YAML
│   ├── params.yaml             #   └─ Parámetros generales
│   ├── modelado.yaml           #   └─ Hiperparámetros Prophet
│   ├── limpieza.yaml           #   └─ Reglas de limpieza de datos
│   ├── FE.yaml                 #   └─ Feature engineering
│   └── logging.yaml            #   └─ Configuración de logs
│
├── data/
│   ├── raw_PDFs/               # 630+ boletines epidemiológicos 2012-2026 (~1GB, DVC)
│   ├── processed/              # Dataset consolidado 60,000+ filas (DVC)
│   ├── interim/                # Datos intermedios
│   ├── external/               # Datos externos (INEGI)
│   └── registry.json           # Registro de boletines descargados
│
├── src/
│   ├── configuraciones/        # Gestión de configuración
│   ├── datos/                  # Limpieza y preparación
│   ├── extraccion/             # Pipeline de extracción PDF
│   ├── modelado/               # Modelos Prophet
│   └── utils/                  # Utilidades compartidas
│
├── scripts/                    # Scripts de orquestación
├── models/                     # Modelos entrenados (.pkl)
├── notebooks/                  # Análisis exploratorio
├── reports/figures/            # Visualizaciones generadas
│
├── Makefile                    # Automatización de tareas
├── requirements.txt            # Dependencias Python
└── pyproject.toml              # Metadatos del proyecto
```

---

## Instalación

### Requisitos Previos

- **Python 3.12**
- **Git**
- **AWS CLI** (configurado con credenciales del equipo)
- **Ghostscript** (para procesamiento de PDFs)

### macOS

```bash
# 1. Clonar repositorio
git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
cd EpiForecast-MX

# 2. Configurar AWS (solicitar credenciales al equipo)
aws configure

# 3. Setup completo (instala Ghostscript, dependencias y descarga datos)
make setup
```

### Linux / WSL

```bash
# 1. Clonar repositorio
git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
cd EpiForecast-MX

# 2. Configurar AWS
aws configure

# 3. Setup completo
make setup-linux
```

### Instalación Manual

```bash
# Crear entorno virtual
make create_environment        # Con venv
make create_environment_conda  # Con Conda

# Activar entorno
source integrador/bin/activate  # venv
conda activate integrador       # Conda

# Instalar dependencias
make requirements

# Descargar datos desde S3
make data-pull
```

---

## Comandos

### Pipeline de Datos

| Comando | Descripción |
|---------|-------------|
| `make preprocess` | Ejecuta pipeline completo: filtrar → limpiar → transformar → mapear INEGI |
| `make filter` | Filtra dataset por padecimiento configurado en `params.yaml` |
| `make clean` | Limpia datos: elimina nulos, duplicados, formatea columnas |
| `make transform` | Aplica feature engineering |
| `make get_inegi` | Descarga datos demográficos del INEGI |
| `make mapper` | Mapea entidades con regiones INEGI |
| `make train` | Entrena modelo Prophet |

### Gestión de Datos (DVC)

| Comando | Descripción |
|---------|-------------|
| `make data-pull` | Descarga datos desde S3 |
| `make data-push` | Sube datos a S3 |
| `make data-status` | Muestra estado de sincronización |
| `make data-add PDF=ruta/archivo.pdf` | Agrega nuevo boletín al tracking |
| `make data-commit` | Commitea y sube cambios de datos |
| `make data-weekly PDF=ruta/archivo.pdf` | Flujo semanal completo |

### Calidad de Código

| Comando | Descripción |
|---------|-------------|
| `make lint` | Verifica código con Ruff |
| `make format` | Formatea código con Ruff |
| `make clean_py` | Elimina archivos `.pyc` y `__pycache__` |

### Utilidades

| Comando | Descripción |
|---------|-------------|
| `make help` | Muestra todos los comandos disponibles |
| `make reset_logs` | Reinicia carpeta de logs |
| `make reset_interim` | Reinicia carpeta de datos intermedios |

---

## CI/CD

El proyecto cuenta con un pipeline completamente automatizado mediante **GitHub Actions**.

### Pipeline de Scraping

**Workflow:** `scrape_boletines.yml`
**Schedule:** Diario a las 14:00 hrs (CDMX)

```
┌──────────────────────────────────────────────────────────────┐
│  1. Selenium navega página SINAVE                            │
│  2. Compara con registry.json                                │
│  3. Descarga PDFs nuevos a data/raw_PDFs/                    │
│  4. DVC add + push a S3                                      │
│  5. Git commit (registry.json + raw_PDFs.dvc)                │
│  6. Notificación SNS al equipo                               │
└──────────────────────────────────────────────────────────────┘
```

### Pipeline de Procesamiento

**Workflow:** `process_boletines.yml`
**Trigger:** Automático al completar scraping (o manual)

```
┌──────────────────────────────────────────────────────────────┐
│  1. DVC pull (PDFs + dataset actual)                         │
│  2. Detecta PDFs no procesados                               │
│  3. Extrae tablas con Camelot (keywords: F32, G20, G30)      │
│  4. Merge incremental al dataset principal                   │
│  5. DVC add + push dataset actualizado                       │
│  6. Git commit (.dvc pointer)                                │
│  7. Notificación SNS al equipo                               │
└──────────────────────────────────────────────────────────────┘
```

### GitHub Secrets Requeridos

| Secret | Descripción |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | Credencial de acceso AWS |
| `AWS_SECRET_ACCESS_KEY` | Credencial secreta AWS |
| `AWS_REGION` | Región AWS (`us-east-1`) |
| `SNS_TOPIC_ARN` | ARN del topic SNS (opcional) |

### Sincronización Local

Cuando el pipeline actualice el dataset, sincroniza tu entorno local:

```bash
git pull && dvc pull
```

---

## Stack Tecnológico

### Lenguaje y Entorno

| Tecnología | Versión | Uso |
|------------|---------|-----|
| Python | 3.12 | Lenguaje principal |
| Conda / venv | - | Gestión de entornos |

### Procesamiento de Datos

| Librería | Versión | Uso |
|----------|---------|-----|
| pandas | 2.3.0 | Manipulación de datos |
| NumPy | 2.0.0 | Computación numérica |
| SciPy | 1.14.1 | Funciones estadísticas |
| Camelot | 0.11.0 | Extracción de tablas PDF |
| pypdf | 4.3.1 | Manipulación de PDFs |

### Machine Learning

| Librería | Versión | Uso |
|----------|---------|-----|
| Prophet | 1.3.0 | Pronóstico de series de tiempo |
| scikit-learn | 1.5.0 | Validación cruzada y métricas |
| statsmodels | 0.14.4 | Análisis estadístico |

### Visualización

| Librería | Versión | Uso |
|----------|---------|-----|
| Matplotlib | 3.10.0 | Gráficos estáticos |
| Seaborn | 0.13.2 | Visualización estadística |
| Plotly | 5.24.0 | Gráficos interactivos |

### Infraestructura

| Tecnología | Uso |
|------------|-----|
| DVC | Versionado de datos |
| Amazon S3 | Almacenamiento de datos |
| Amazon SNS | Notificaciones |
| GitHub Actions | CI/CD |
| Selenium | Web scraping |

### Calidad de Código

| Herramienta | Versión | Uso |
|-------------|---------|-----|
| Ruff | 0.14.10 | Linter y formateador |
| Loguru | 0.7.3 | Logging estructurado |
| OmegaConf | 2.3.0 | Gestión de configuración |

---

## Fuentes de Datos

| Fuente | Descripción | URL |
|--------|-------------|-----|
| SINAVE | Boletín Epidemiológico Semanal | [gob.mx/salud](https://www.gob.mx/salud/acciones-y-programas/direccion-general-de-epidemiologia-boletin-epidemiologico) |
| SINAVE Histórico | Archivo de boletines previos | [gob.mx/salud/historico](https://www.gob.mx/salud/acciones-y-programas/historico-boletin-epidemiologico) |
| INEGI | Datos demográficos regionales | [inegi.org.mx](https://www.inegi.org.mx/) |

---

## Infraestructura AWS

| Recurso | Valor |
|---------|-------|
| Bucket S3 | `s3://epiforecast-mx-data` |
| Región | `us-east-1` |
| SNS Topic | Configurado vía GitHub Secrets |

---

## Equipo

### Desarrolladores

| Nombre | Afiliación Profesional |
|--------|------------------------|
| **Juan Carlos Pérez Nava** | IT Professional, IMSS |
| **Luis Gerardo Sánchez Salazar** | Sr. Controls Engineer, Tesla |
| **Javier Augusto Rebull Saucedo** | Sr. Associate Development Application, Santander Bank US |

### Asesoría Académica

| Nombre | Institución |
|--------|-------------|
| **Dra. Grettel Barceló Alonso** | Tecnológico de Monterrey |

### Stakeholders IMSS

| Nombre | Rol |
|--------|-----|
| **Dra. Ruth Pérez** | Project Leader |
| **Dra. Lina Díaz Castro** | Investigadora en Psiquiatría |

---

## Licencia

Este proyecto está licenciado bajo la [MIT License](https://opensource.org/licenses/MIT).

---

<p align="center">
  <sub>Desarrollado con el apoyo del Instituto Mexicano del Seguro Social y el Tecnológico de Monterrey</sub>
</p>
