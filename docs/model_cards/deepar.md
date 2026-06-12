# Model Card: DeepAR

## Descripcion

Modelo autorregresivo recurrente probabilistico basado en **DeepAR** (GluonTS + PyTorch). Entrena en modo **multi-series** (las 32 entidades como series simultaneas comparten parametros), con distribucion de salida Student-t y muestreo para bandas de incertidumbre. Es uno de los motores productivos de la cohorte neurologica y de Dengue.

## Inputs

- Serie temporal semanal (`ds`, `y`) por entidad; a nivel nacional se entrena multi-series (un `item_id` por estado).
- Opcionalmente normalizacion a tasa/100k (`normalizar_tasa`) usando poblacion INEGI.
- Relleno de huecos cohort-aware: `gap_fill="zero"` (neuro, los huecos son ceros reales) o `gap_fill="interpolate"` (cohortes de historia corta como Dengue, los huecos son semanas sin boletin).

## Outputs

- Pronostico semanal (`yhat`, `yhat_lower`, `yhat_upper`) a horizonte configurable (52 por defecto), generado por chunks de `prediction_length`.
- Ajuste in-sample via backtest de ventana expansiva.
- Metricas: RMSE, MAE, MAPE, SMAPE, MASE. Artefacto `.pkl` con metadata.

## Hiperparametros principales

| Parametro | Default | Descripcion |
|-----------|---------|-------------|
| epochs | 300 | Epocas de entrenamiento (early stopping con paciencia 15) |
| context_length | 104 | Ventana de contexto (52 en cohorte `short_series`) |
| prediction_length | 52 | Longitud de cada bloque de pronostico |
| num_layers / num_cells | 2 / 80 | Profundidad y ancho de la RNN |
| dropout_rate | 0.15 | Regularizacion |
| learning_rate | 5e-4 | Tasa de aprendizaje |
| distr_output | student-t | Distribucion de salida (conserva tasa+Student-t en Dengue) |
| num_samples | 200 | Muestras para estimar media y cuantiles |
| short_series.max_lag | 53 | Lag maximo en cohortes cortas (conserva el lag anual) |

## Computo

- Prioridad de dispositivo: **CUDA (SageMaker) > CPU**. **MPS (Apple Silicon) deshabilitado por defecto** (ops de muestreo Student-t no implementadas en MPS + riesgo de deadlock); forzar con `deepar.allow_mps: true`.
- No correr dos entrenamientos DeepAR locales concurrentes.

## Metricas de referencia

- Motor lider en varias series neuro; en Dengue es uno de los tres productivos (con Prophet y NB-GLM).
- MASE < 1.0 indica mejor desempeno que el naive estacional.

## Limitaciones

- Estocastico en el muestreo: las bandas dependen de `num_samples`; las semillas se fijan en `fit` (`RANDOM_SEED=42`) pero el muestreo de `predict` introduce varianza menor.
- Requiere historia suficiente: `past_length = context_length + lags` debe caber en la serie disponible (limita el horizonte a ~52 semanas en cohortes cortas).
- Costo de entrenamiento alto frente a Prophet/NB-GLM; se beneficia de GPU.
