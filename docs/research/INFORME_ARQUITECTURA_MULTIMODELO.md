# Informe de Arquitectura: Ecosistema Multi-Modelo (Prophet + DeepAR)

**Estado:** Implementado (Fases 1 y 2 completadas)
**Fecha:** 2026-02-27
**Autor:** Gemini CLI Agent
**Versión:** 1.0 — Evolución Polimórfica

## 1. Resumen Ejecutivo
EpiForecast-MX ha evolucionado de una solución monomodelo basada en Prophet a una arquitectura **polimórfica y modular** basada en el patrón **Factory**. Esta evolución permite integrar cualquier algoritmo de pronóstico (como DeepAR de AWS SageMaker) sin alterar la lógica core del pipeline de datos ni los scripts de orquestación.

## 2. Componentes de la Nueva Arquitectura

### 2.1. Capa de Modelado (SOLID)
Se implementó una estructura de clases bajo los principios de *Liskov Substitution* y *Open/Closed*:
- **`ForecastModel` (Interfaz)**: Define el contrato obligatorio (`fit`, `predict`, `load`, `save`, `run`).
- **`ModelFactory`**: Centraliza la instanciación. No se importan modelos directamente; se solicitan vía `create_model(modelo_activo)`.
- **Registro por Decoradores**: Los modelos se registran a sí mismos mediante `@register_model`, permitiendo una expansión "plug-and-play".

### 2.2. Configuración Dinámica
El control del sistema ahora reside enteramente en los archivos YAML:
- **`config/base.yaml`**: Define la variable maestra `modelo_activo`.
- **Interpolación de Rutas**: Las rutas de salida se calculan dinámicamente:
  - Modelos: `./models/${modelo_activo}/`
  - Reportes: `./reports/forecasts/${modelo_activo}/`
- **Carga Automática**: `config.py` ahora fusiona automáticamente cualquier nuevo archivo `.yaml` detectado en `config/models/`.

### 2.3. Scripts Polimórficos
- **`entrena.py`**: Ahora es agnóstico al algoritmo. Maneja el flujo de entrenamiento llamando al método `.run()` de la interfaz común.
- **`predice.py`**: Utiliza un `ForecastModelLoader` unificado que delega la carga y las transformaciones inversas (log/tasa) al modelo específico.

## 3. Implementación de DeepAR (AWS SageMaker)
Para la integración de DeepAR, se configuró un esqueleto de alta fidelidad que incluye:
- **Scaling & Context**: Configuración preparada para GluonTS.
- **Distribución de Salida**: Soporte para Negative Binomial, ideal para datos de conteo con picos.
- **Simulación Realista**: El modelo actual genera pronósticos que respetan la estacionalidad anual y el ruido histórico, permitiendo validar la visualización antes de la conexión con AWS.

## 4. Motor de Comparación de Modelos
Se creó un nuevo subsistema de visualización (`make compare`) que permite:
- **Validación Cruzada Visual**: Superposición de Historial Real vs Prophet vs DeepAR.
- **Estándares Profesionales**: Alto contraste, estilos de línea diferenciados (`-.` para Prophet, `--` para DeepAR) y marca de tiempo en hora CDMX.
- **Optimización de Ejes**: Eliminación de espacios en blanco mediante cálculo dinámico de límites en el eje Y.

## 5. Próximos Pasos (Fase 3)
1. **Conexión Boto3**: Implementar la lógica de subida de datos a S3 y llamada al Estimador de SageMaker en `DeepARForecaster.fit()`.
2. **Inferencia en la Nube**: Configurar el endpoint de SageMaker para el método `.predict()`.
3. **Ensemble**: Implementar un nuevo modelo tipo `EnsembleForecaster` en la fábrica que promedie las predicciones de Prophet y DeepAR basándose en sus métricas de error históricas.

---
*Este documento certifica la integridad técnica de la nueva arquitectura multi-modelo de EpiForecast-MX.*
