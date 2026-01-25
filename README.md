# Enfermedades Neurológicas y de Salud

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

Proyecto para predecir casos de Enfermedades Neurológicas y de Salud en México mediante modelos de aprendizaje automático y análisis demográfico.

## 📂 Organización del proyecto

```
├── config              <- Archivos de configuración en formato YAML
│
├── data
│   ├── external        <- Datos obtenidos de fuentes externas (no generados internamente)
│   ├── interim         <- Resultados temporales de transformaciones, útiles para depuración y trazabilidad
│   ├── processed       <- Conjuntos de datos definitivos y estandarizados listos para análisis y modelado
│   └── raw             <- Captura inicial de datos sin modificaciones
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
│   └── configuraciones <- Módulos que gestionan parámetros y configuraciones del proyecto desde archivos YAML
│   └── datos           <- Módulos con clases para limpieza, transformación y preparación de datos
│   └── utils           <- Funciones auxiliares para directorios, visualización y generación automatizada de reportes
│
├── Makefile            <- Archivo Makefile que centraliza comandos para automatizar tareas del proyecto (descarga de datos, entrenamiento, etc.)
│
├── pyproject.toml      <- Archivo de configuración principal para dependencias y metadatos del proyecto en Python
│
├── README.md           <- Documento inicial con instrucciones, dependencias y guías para configurar y ejecutar el proyecto
│
└── requirements.txt    <- Lista de dependencias en Python necesarias para ejecutar el proyecto


```

## 🐍 Requisitos

- Python 3.12
- WSL
- Conda

## 🐧 Pasos para configurar WSL y Miniconda

1. **Instalar WSL**
   - Ejecuta en PowerShell (como administrador):
     ```bash
     wsl --install Ubuntu
     ```
   - Esto instalará la última versión de WSL junto con una distribución de Linux por defecto (generalmente Ubuntu).  
   - Una vez configurado el usuario principal

2. **Preparar el script de instalación de Miniconda**
   - Asegúrate de tener el archivo `setup_wsl.sh` en la ruta:
     
     ```
     \\wsl.localhost\Ubuntu\home\<usuario>\
     ```

   - Donde `<usuario>` corresponde al nombre de usuario principal que configuraste al instalar WSL.

   - Dale permisos de ejecución al script:
     ```bash
     chmod +x setup_wsl.sh
     ```

3. **Ejecutar el script**
   - Lanza el script para instalar Miniconda:
     ```bash
     ./setup_wsl.sh
     ```
   - Este script descargará e instalará Miniconda, configurando tu entorno de Python.

4. **Verificar la instalación**
   - Comprueba que Miniconda está disponible:
     ```bash
     conda --version
     ```

## 📥 Clonar repositorio

```bash
git clone https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
```
Para la extracción de datos desde los archivos PDF de los boletines epidemiológicos sobre enfermedades mentales se utiliza también el siguiente proyecto:

```bash
git clone https://github.com/luisgss10/data-extraction-mx-enfermedades-mentales.git
```

## 📚 Makefile

### 🔧 Configurar entorno de Python
Crea el entorno del intérprete de Python (compatible con Mac/Linux y Windows):

```bash
make create_environment
```

### 📂 Descargar dataset
Obtén los datos requeridos para el análisis:
```bash
make data
```

## 🔄 Preparación del dataset
Ejecuta el flujo completo de filtrado, limpieza y transformación del dataset:
```bash
make prepara
```

## 📚 Fuentes de Información

Para la obtención, verificación y actualización de los datos epidemiológicos utilizados en este proyecto, se consultan las siguientes fuentes oficiales:

- **Boletín Epidemiológico Actual**  
  Publicado semanalmente por la Dirección General de Epidemiología (DGE).  
  Disponible en: https://www.gob.mx/salud/acciones-y-programas/direccion-general-de-epidemiologia-boletin-epidemiologico

- **Histórico de Boletines Epidemiológicos**  
  Archivo completo de ediciones previas del boletín epidemiológico.  
  Disponible en: https://www.gob.mx/salud/acciones-y-programas/historico-boletin-epidemiologico

Estas fuentes garantizan el acceso a información confiable y actualizada proporcionada por la Secretaría de Salud de México.
