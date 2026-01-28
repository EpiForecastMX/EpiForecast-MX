# EpiForecast-MX

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

Proyecto para predecir casos de Enfermedades Neurológicas y de Salud Mental en México mediante modelos de aprendizaje automático y análisis demográfico.

## 📂 Organización del proyecto

```
├── config              <- Archivos de configuración en formato YAML
│
├── data
│   ├── external        <- Datos obtenidos de fuentes externas (no generados internamente)
│   ├── interim         <- Resultados temporales de transformaciones, útiles para depuración y trazabilidad
│   ├── processed       <- Conjuntos de datos definitivos y estandarizados listos para análisis y modelado
│   ├── raw             <- Captura inicial de datos sin modificaciones
│   └── raw_PDFs        <- Boletines epidemiológicos en formato PDF (entrada para extracción)
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

### 4. Instalar dependencias de Python
```bash
make requirements
```

---

## 🐧 Configuración en Windows (WSL)

### 1. Instalar WSL
Ejecuta en PowerShell (como administrador):
```bash
wsl --install Ubuntu
```

### 2. Preparar el script de instalación de Miniconda
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

### 4. Verificar la instalación
```bash
conda --version
```

### 5. Clonar el repositorio
```bash
git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
cd EpiForecast-MX
```

### 6. Crear entorno e instalar dependencias
```bash
make create_environment_conda
conda activate integrador
make requirements
```

---

## 📊 Módulo de Extracción de Datos (PDFs)

El proyecto incluye un módulo integrado para extraer tablas epidemiológicas desde los boletines PDF del SINAVE.

### Uso con Interfaz Gráfica (Recomendado)

```bash
python -m src.extraccion.gui
```

La GUI permite:
- Seleccionar carpeta de entrada (PDFs)
- Seleccionar carpeta de salida
- Definir keywords (enfermedades a buscar)
- Activar/desactivar guardado de páginas extraídas y CSVs individuales

### Uso por Línea de Comandos

Colocar los PDFs en `data/raw_PDFs/` y ejecutar:

```bash
python -m src.extraccion.extraer_tabla
```

### Salidas Generadas

| Archivo | Descripción |
|---------|-------------|
| `dataset_boletin_epidemiologico.csv` | Dataset consolidado con todos los datos extraídos |
| `csv_tablas_individuales/` | CSVs por cada PDF procesado (opcional) |
| `pdf_matched_pages/` | PDFs de 1 página con las tablas encontradas (opcional) |

---

## 📚 Comandos del Makefile

| Comando | Descripción |
|---------|-------------|
| `make help` | Muestra los comandos disponibles |
| `make requirements` | Instala las dependencias de Python |
| `make create_environment` | Crea entorno virtual con venv |
| `make create_environment_conda` | Crea entorno virtual con Conda |
| `make get_dataset` | Descarga el dataset original |
| `make preprocess` | Ejecuta el flujo completo: filtrar, limpiar y transformar |
| `make filter` | Filtra el dataset por padecimiento |
| `make clean` | Limpia el dataset (nulos, duplicados) |
| `make transform` | Aplica transformaciones al dataset |
| `make lint` | Analiza el código con Ruff |
| `make format` | Formatea el código con Ruff |
| `make reset_logs` | Reinicia la carpeta de logs |
| `make reset_interim` | Reinicia la carpeta interim |

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
- Sly (Haowei)

**Asesora:** Dra. Grettel Barceló Alonso - Tecnológico de Monterrey

**Stakeholders IMSS:**
- Dra. Ruth Pérez (Project Leader)
- Dra. Lina Díaz Castro (Psychiatry Researcher)
