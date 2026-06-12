# Model Card: NB-GLM

## Descripcion

Modelo lineal generalizado **Negative-Binomial** con estacionalidad de **Fourier**, lags y un regresor exogeno de **El Nino (ENSO/ONI)**. Es count-correcto (modela conteos enteros sobredispersos), **determinista** y extrapola sin divergencia gracias a su componente estacional parametrico. Es el mejor motor del estudio de Dengue en backtest *leave-one-epidemic-out* y uno de los tres productivos para Dengue (con DeepAR y Prophet). No se usa en la cohorte neurologica.

## Inputs

- Serie temporal semanal de conteos (`ds`, `y`) de Dengue (cohorte de conteos-log).
- Regresor **ONI** (`src/epiforecast/data/enso.py`): ONI mensual de NOAA interpolado a semanal, rezagado `enso_lag_weeks=16`. El ONI futuro = observado + persistencia amortiguada hacia neutral (o `data/external/oni_forecast.csv` si esta disponible). El corte `as_of` evita leakage climatico en backtest.

## Outputs

- Ajuste in-sample + pronostico futuro (`yhat`, `yhat_lower`, `yhat_upper`); la produccion evalua el ajuste 2026 H1.
- Proyeccion multi-anual ilustrativa con `predict(freeze_trend=True)` (congela la tendencia para no extrapolar la pendiente inflada por el pico 2024).
- Fallback constante para series degeneradas (sin transmision): "si es 0, es 0".

## Hiperparametros / opciones principales

| Parametro | Default | Descripcion |
|-----------|---------|-------------|
| enso_regressor | True (Dengue) | Activa el regresor ONI (cohort-gated `is_count_log_cohort`) |
| enso_lag_weeks | 16 | Rezago del ONI respecto a la incidencia |
| freeze_trend | False | Congela la tendencia lineal en su ultimo nivel (proyeccion estable) |
| trend_anchor_weeks | None | Semana donde anclar la tendencia (None => sin anclaje) |
| future_oni | None | Escenario ONI inyectado para el futuro (override de la persistencia) |

## Metricas de referencia

- Backtest *leave-one-epidemic-out* nacional (`dengue_backtest.py`, ONI `as_of=cutoff`, limpio/OOS): **SMAPE 52** vs Prophet+ENSO 76 vs Prophet plano 102.
- La senal inter-anual de ENSO (ausente en los conteos autorregresivos) explica la ganancia en el pico epidemico.

## Limitaciones

- Especifico de la cohorte de conteos (Dengue); no aplica a las series neuro.
- El ciclo epidemico de ~4 anos no es aprendible con solo 2 ciclos observados (2019, 2024): la proyeccion multi-anual muestra el patron estacional, no la magnitud de la proxima epidemia.
- La metrica de seleccion productiva `smape_real_2026` es in-sample (ver `docs/research/hallazgos/DENGUE_AUDITORIA_LEAKAGE.md`); la validacion honesta es el backtest OOS y `pronostico_congelado.py`.
- Depende de la disponibilidad del ONI de NOAA (cacheado en `data/external/`; en tests se usa un fixture versionado).
