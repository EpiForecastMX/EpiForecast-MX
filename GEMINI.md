# GEMINI.md: Contexto de EpiForecast-MX

Este archivo actúa como una guía y contexto permanente para el agente Gemini CLI al interactuar con el repositorio **EpiForecast-MX**.

## 1. Propósito
**EpiForecast-MX** es una plataforma de inteligencia epidemiológica desarrollada en colaboración con el **Instituto Mexicano del Seguro Social (IMSS)**. Su objetivo principal es pronosticar la incidencia semanal de tres padecimientos neurológicos y de salud mental (Depresión [F32], Parkinson [G20] y Alzheimer [G30]) en las 32 entidades federativas de México, con un horizonte de predicción de 52 semanas.

Resuelve el problema de la planeación y asignación de recursos médicos al proveer visibilidad a futuro con granularidad a nivel estatal y regional, utilizando datos históricos del Sistema Nacional de Vigilancia Epidemiológica (SINAVE) e indicadores demográficos del INEGI.

## 2. Arquitectura
El proyecto sigue una estructura modular orientada a producción y MLOps:

- `src/epiforecast/`: Paquete principal de Python (src-layout). Contiene el código core:
  - `data/`: Extracción (Camelot/PDFs), ingesta (API del INEGI) y preprocesamiento (limpieza, transformación, imputación).
  - `models/`: Implementación de modelos (principalmente Prophet), optimización de hiperparámetros y validación cruzada temporal. Utiliza un patrón Factory para extender o instanciar modelos.
  - `evaluation/`: Cálculo de métricas de rendimiento (RMSE, MAE, MASE).
  - `features/`: Ingeniería de características y cruce de datos con información demográfica.
  - `visualization/`: Generación de gráficos (series temporales, EDA, reportes adaptados al estilo visual del IMSS).
  - `pipelines/` y `utils/`: Pipelines abstractos, utilidades de pathing, helpers y configuración (OmegaConf/Loguru).
- `scripts/`: Puntos de entrada CLI para la ejecución del pipeline (entrenamiento, limpieza, reportes, etc.), los cuales están mapeados en el `Makefile`.
- `config/`: Archivos YAML que controlan todo el comportamiento del proyecto (rutas, hiperparámetros, configuración visual, flags del pipeline), evitando valores en duro (hardcoded) en el código.
- `data/`: Artefactos de datos gestionados por DVC (raw_PDFs, raw, interim, processed).
- `models/`: Modelos entrenados (archivos `.pkl`) y sus resultados de validación, versionados con DVC y almacenados en AWS S3.
- `tests/`: Pruebas unitarias y de integración robustas (+600 pruebas) que aseguran la fiabilidad del pipeline.
- `reports/`: Resultados de predicciones (`reports/forecasts/`), gráficos exploratorios (`reports/figures/`), reportes en PDF y tableros de control (`reports/dashboards/`). Se eliminaron las carpetas obsoletas `forecast/`, `viz/` y `outputs/` en favor de este estándar unificado.

## 3. Stack Tecnológico
- **Lenguaje Principal:** Python 3.12
- **Modelado & Machine Learning:** Prophet (con cmdstanpy), Scikit-Learn.
- **Procesamiento de Datos:** Pandas, Numpy, Scipy.
- **Extracción de Información de PDFs:** Camelot-py (requiere Ghostscript y OpenCV), PyPDF.
- **Visualización:** Matplotlib, Seaborn, Plotly, ReportLab, Rich.
- **MLOps & Control de Versiones de Datos:** DVC (con soporte S3 para almacenamiento remoto).
- **CI/CD:** GitHub Actions (workflows automatizados para extracción diaria de boletines y ejecución de pruebas de calidad).
- **Calidad y Testing:** Ruff (linter y formatter), Mypy (type checking estricto), Pytest (pruebas y cobertura), Cookiecutter Data Science.

## 4. Flujo de Datos
El pipeline de datos opera de manera secuencial y automatizada, orquestado principalmente a través del `Makefile`:

1. **Extracción e Ingesta:** Diariamente, un web scraper descarga PDFs de boletines del SINAVE. Se extraen tablas y se unen en un CSV maestro (Dataset Raw) utilizando Camelot (`make get-dataset`).
2. **Preprocesamiento:**
   - **Filtrado:** Filtrar el dataset general por padecimiento específico (ej. F32) (`make filter`).
   - **Limpieza:** Normalización de columnas, tratamiento de valores nulos y duplicados (`make clean`).
   - **Transformación:** Detección y corrección de outliers (con IQR/Z-score) y agregación a nivel semanal (`make transform`).
   - **Cruce Demográfico:** Integración con datos descargados del INEGI para obtener población, densidad y región de salud mental (`make get-inegi`, `make mapper`).
3. **Modelado Predictivo:** La serie de tiempo resultante sufre transformaciones (tasa por 100K habitantes y logaritmo) antes de alimentar a Prophet. Se entrenan 297 modelos (Estado × Padecimiento × Sexo). Se aplica una estrategia de "fallback híbrido", donde los estados con datos insuficientes caen automáticamente a modelos de nivel región (`make train`).
4. **Predicción y Generación de Reportes:** El modelo proyecta 52 semanas hacia el futuro. Se aplican transformaciones inversas para volver a la escala real de conteo de casos. Finalmente, se exportan resultados a CSV y se elaboran gráficos o tableros de control (`make predict`, `make report`, `make bitacora`).

## 5. Convenciones y Buenas Prácticas
Para mantener la consistencia y la integridad del repositorio, adhiérete a estas convenciones:

- **100% Estricto con Calidad y Arquitectura:** Somos implacables en la aplicación de principios **MLOps**, **SOLID code** y **Clean Code**. Todo código o cambio debe ser altamente mantenible, modular, testeable y ajustarse a los más altos estándares de ingeniería para sistemas en producción.
- **Configuración Centralizada:** Nunca "hardcodear" parámetros, rutas de archivos o banderas de ejecución. Utiliza el módulo de configuración que lee desde `config/*.yaml` usando `OmegaConf`.
- **Gate de Calidad Riguroso:** El proyecto persigue altos estándares (Coverage > 80%, Compliance A+). Antes de finalizar, asegúrate de que el código pase el comando `make quality`, que valida:
  - **Linting y Formateo:** Ejecuta **Ruff** para asegurar el estilo (`ruff check`, `ruff format`).
  - **Tipado Estático:** Emplea "type hints" en Python y valídalos usando **Mypy**.
  - **Pruebas:** Escribe tests (pytest) al añadir características y asegúrate de no romper las pruebas existentes.
- **Versionado Dual:** El código fuente va en Git. Los artefactos pesados (`data/`, `models/`, y ciertos outputs en `forecast/`) **SIEMPRE** se versionan con **DVC** (`dvc add`, `dvc push`). No intentes comitear PDFs, modelos `.pkl` ni grandes CSVs a Git.
- **Commits Convencionales:** El repositorio usa *pre-commit hooks* y sigue la especificación de *Conventional Commits* (ej. `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`).
- **Uso de Makefile:** Emplea los comandos y targets del `Makefile` para ejecutar cualquier parte del pipeline (ej. `make train`, `make filter`, `make test-fast`). Puedes inyectar configuración dinámica mediante `ARGS` (ej. `make train ARGS="padecimiento.tipo='Depresión'"`).
- **Entorno Virtual:** Siempre utilizar y activar el entorno estándar `.venv` (creado vía `make setup`).
