# Model Card: Prophet

## Descripcion

Modelo de series de tiempo basado en **Facebook Prophet** con estacionalidad anual personalizada (yearly_custom). Configurable con grid search de hiperparametros via cross-validation temporal.

## Inputs

- Serie temporal semanal (ds, y) con al menos 104 semanas de historia.
- Holidays/cambios de regimen configurados en `config/base.yaml`.
- Estacionalidad anual con periodo y orden Fourier configurables.

## Outputs

- Pronostico semanal a 52 semanas (yhat, yhat_lower, yhat_upper).
- Metricas: RMSE, MAE, MAPE, SMAPE, MASE.
- Artefacto `.pkl` serializado con metadata de version.

## Hiperparametros principales

| Parametro | Default | Descripcion |
|-----------|---------|-------------|
| changepoint_prior_scale | 0.05 | Flexibilidad de cambios de tendencia |
| seasonality_prior_scale | 0.1 | Fuerza de la estacionalidad |
| seasonality_mode | additive | Modo de estacionalidad (additive/multiplicative) |
| yearly_custom.period | 365.25 | Periodo de estacionalidad anual |
| yearly_custom.fourier_order | 10 | Orden Fourier (6 para regional) |

## Metricas de referencia

- SMAPE tipico: 15-40% dependiendo del padecimiento y entidad.
- MASE < 1.0 indica mejor rendimiento que naive seasonal.

## Limitaciones

- No captura interacciones entre entidades.
- Sensible a series con pocos datos (< 104 semanas genera fallback).
- Los holidays deben configurarse manualmente.
