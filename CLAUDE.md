# CLAUDE.md: Guía de Desarrollo EpiForecast-MX

## Comandos de Ejecución (Makefile)

### Pipeline de Datos
- `make preprocess`: Ejecuta todo el flujo de limpieza y mapeo INEGI.
- `make get-dataset`: Descarga el dataset RAW (SINAVE).
- `make filter ARGS="padecimiento.tipo='Depresión'"`: Filtra por padecimiento.

### Entrenamiento y Modelado (Multi-Modelo)
- `make train`: Entrena según el `modelo_activo` en `config/base.yaml`.
- `make train-prophet`: Fuerza entrenamiento con Prophet.
- `make train-deepar`: Fuerza entrenamiento con DeepAR (AWS SageMaker).
- `make train-all`: Entrena ambos modelos secuencialmente.
- `make predict ARGS="modelo_activo='deepar'"`: Genera pronósticos para un modelo específico.
- `make compare`: Genera gráficos de alta calidad comparando Real vs Prophet vs DeepAR.

### Calidad y Pruebas
- `make quality`: Ejecuta lint (Ruff), typecheck (Mypy) y tests (Pytest).
- `make format`: Formatea el código automáticamente.
- `make test-fast`: Ejecuta solo pruebas unitarias rápidas.

## Arquitectura y Estándares

### Patrón Factory (SOLID)
- Los modelos heredan de `epiforecast.models.base.ForecastModel`.
- Se registran mediante el decorador `@register_model("nombre")`.
- Se instancian vía `epiforecast.models.factory.create_model(name, **kwargs)`.

### Configuración Dinámica
- `config/base.yaml`: Controla el `modelo_activo`.
- `config/models/*.yaml`: Configuraciones específicas por algoritmo (Prophet, DeepAR).
- Las rutas en `config/base.yaml` usan interpolación: `./models/${modelo_activo}`.

### Visualización
- Los gráficos comparativos se guardan en `reports/forecasts/comparacion_modelos/`.
- Usan la zona horaria `America/Mexico_City` (UTC-6) para las marcas de tiempo.
- Estilo: Historial Real (Gris grueso), Prophet (Teal #004d40 dash-dot), DeepAR (Vino #880e4f dashed).

### Convenciones de Código
- **Imports**: Agrupar stdlib, luego terceros, luego locales.
- **Tipado**: Uso estricto de `mypy`. Retornos de funciones deben estar tipados.
- **Logging**: Usar `loguru.logger` para trazas de depuración y errores.
