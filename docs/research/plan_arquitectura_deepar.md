# Arquitectura Multi-Modelo: Integración de DeepAR (AWS SageMaker)

Este documento detalla el plan arquitectónico para evolucionar **EpiForecast-MX** de un sistema monomodelo (únicamente Prophet) a un ecosistema MLOps multi-modelo (Prophet + DeepAR), respetando estrictamente los principios SOLID y el estándar Cookiecutter Data Science v2.

## 1. Evolución de la Configuración (`config/`)
En lugar de "hardcodear" qué modelo se usa, la configuración central dictará el motor algorítmico activo.

*   **Nuevo archivo `config/models/deepar.yaml`:**
    Contendrá los hiperparámetros específicos de AWS DeepAR (epochs, context_length, prediction_length, num_layers) en un formato idéntico a cómo se estructuró `prophet.yaml`.
*   **Actualización en `config/base.yaml`:**
    Añadir una llave maestra de control de flujo.
    ```yaml
    modelo_activo: "prophet"  # Opciones: prophet, deepar, ensemble
    ```

## 2. Expansión del Patrón Factory (Capa MLOps / SOLID)
El sistema actual respeta el *Open/Closed Principle (OCP)* a través de `ModelFactory`. Debemos crear el "plugin" para DeepAR sin alterar la lógica de Prophet.

*   **Crear `src/epiforecast/models/deepar/model.py`:**
    Esta clase heredará de `AbstractModel` (la interfaz base).
*   **Sobrescribir métodos abstractos:**
    Se implementarán `train()`, `predict()`, y `save()` para que, por debajo, utilicen la API de AWS SageMaker (boto3) o GluonTS localmente, pero expongan la misma firma que Prophet hacia el resto del pipeline.
*   **Registrar en la Fábrica (`src/epiforecast/models/factory.py`):**
    ```python
    if model_type == "deepar":
        from epiforecast.models.deepar.model import DeepARForecaster
        return DeepARForecaster(**kwargs)
    ```

## 3. Reestructuración de Carpetas (Aislamiento de Outputs)
Para evitar que las predicciones y artefactos se sobrescriban o mezclen, los scripts inyectarán el nombre del `modelo_activo` en las rutas de DVC dinámicamente.

*   **Directorio de Modelos (`models/`):**
    *   `models/prophet/{Padecimiento}/Nacional/...`
    *   `models/deepar/{Padecimiento}/Nacional/...`
*   **Directorio de Reportes (`reports/forecasts/`):**
    *   `reports/forecasts/prophet/all_forecast_prophet.csv` (y sus respectivos PNGs)
    *   `reports/forecasts/deepar/all_forecast_deepar.csv` (y sus respectivos PNGs)

## 4. Adaptación de los Scripts (`scripts/`)
Se modificará el código imperativo existente para que sea verdaderamente polimórfico (DRY - Don't Repeat Yourself).

*   **`scripts/entrena.py`:**
    Leerá `conf["modelo_activo"]`, solicitará a la `ModelFactory` la instancia correcta y guardará los `.pkl` o `.tar.gz` en su subcarpeta respectiva.
*   **`scripts/predice.py`:**
    Cosechará únicamente la subcarpeta del modelo activo, ejecutará el método `predict()` de la interfaz abstracta y arrojará el CSV específico del algoritmo.
*   **`scripts/build_tableau.py`:**
    Tendrá la capacidad de leer ambos CSVs predictivos (`prophet` y `deepar`) y unirlos como columnas separadas (`yhat_prophet`, `yhat_deepar`), permitiendo alternar curvas en un solo dashboard de Tableau.

## 5. Orquestación del Makefile
Se agregarán *targets* amigables o comandos parametrizados aprovechando la funcionalidad de overrides CLI `$(ARGS)`:

```makefile
# Entrenar algoritmos por separado compartiendo la misma tubería de datos
train-prophet:
	$(PYTHON) -m scripts.entrena ARGS="modelo_activo='prophet'"

train-deepar:
	$(PYTHON) -m scripts.entrena ARGS="modelo_activo='deepar'"

# Entrenar pipeline multi-modelo
train-all: train-prophet train-deepar
```

---
*Este documento sirve como referencia para la implementación y debe considerarse el esquema de trabajo oficial de desarrollo futuro.*
