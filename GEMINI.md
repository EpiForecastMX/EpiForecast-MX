# GEMINI.md: Contexto de EpiForecast-MX (Multi-Model Evolution)

Este archivo actúa como una guía y contexto permanente para el agente Gemini CLI.

## 1. Propósito y Alcance
**EpiForecast-MX** es una plataforma de inteligencia epidemiológica multi-modelo para el **IMSS**. Pronostica la incidencia semanal de Depresión (F32), Parkinson (G20) y Alzheimer (G30) en las 32 entidades federativas de México con un horizonte de 52 semanas.

## 2. Arquitectura Polimórfica (SOLID)
El proyecto utiliza un patrón **Factory** para gestionar múltiples motores de pronóstico:

- **ProphetForecaster**: Implementación basada en Meta Prophet, optimizada para series con fuerte estacionalidad.
- **DeepARForecaster**: Integración con AWS SageMaker/GluonTS, utilizando redes neuronales recurrentes para capturar dependencias complejas.
- **ModelFactory**: Punto único de instanciación que permite intercambiar algoritmos sin alterar el pipeline.

## 3. Flujo de Datos y MLOps
1. **Extracción e Ingesta**: Scraper de PDFs del SINAVE y API del INEGI.
2. **Preprocesamiento**: Limpieza, normalización de tasas y detección de outliers.
3. **Orquestación**: El `Makefile` coordina el entrenamiento (`make train-all`), la predicción (`make predict`) y la comparativa (`make compare`).
4. **Aislamiento de Outputs**: Los artefactos se guardan en subcarpetas dinámicas basadas en el `modelo_activo` (ej. `models/prophet/`, `reports/forecasts/deepar/`).

## 4. Estándares de Calidad y Visualización
- **Calidad**: Implacables con **SOLID**, **Clean Code** y tipado estático (`mypy`).
- **Visualización**: Los gráficos deben seguir la paleta IMSS 2026. Los reportes comparativos deben usar la hora de la **CDMX** (UTC-6) y estilos de alto contraste para diferenciar los modelos.
- **Versionado**: Código en Git, artefactos pesados (`.pkl`, `.csv`) en **DVC (S3)**.

## 5. Instrucciones Críticas para el Agente
- **Configuración**: Siempre leer de `config/*.yaml` usando `epiforecast.utils.config`.
- **Polimorfismo**: No importar clases de modelos directamente en scripts; usar `create_model` de la fábrica.
- **Consistencia**: Al añadir modelos, asegurar que implementen la interfaz `ForecastModel` y retornen tanto el historial como el pronóstico en `.predict()`.
- **Validación**: Antes de finalizar tareas, ejecutar `make quality` y verificar la generación de imágenes en `reports/forecasts/`.
