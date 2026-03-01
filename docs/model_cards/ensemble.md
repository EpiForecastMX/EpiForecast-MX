# Model Card: Ensemble (Prophet + XGBoost)

## Descripcion

Modelo ensemble que combina **Prophet** (tendencia y estacionalidad) con **XGBoost** (correccion de residuos via features de lags y temporales). Opera en modo paralelo con pesos aprendidos via expanding-window OOF Ridge regression.

## Arquitectura

1. **Prophet base**: genera pronosticos de tendencia + estacionalidad.
2. **XGBDirect**: modelo de lags (1,2,4,8,13,26,52 semanas) + features temporales (20 features).
3. **ParallelEngine**: combina ambos con pesos `[w_prophet, w_xgb]` aprendidos via OOF.
4. **EnsembleWeightOptimizer**: expanding-window CV con Ridge(positive=True).

## Inputs

- DataFrame epidemiologico con columnas: Fecha, Padecimiento, Entidad, incrementos_total.
- Configuracion en `config/models/ensemble.yaml` y `config/base.yaml`.

## Outputs

- Pronostico semanal a 52 semanas (yhat_ensemble, yhat_prophet).
- Pesos del ensemble (w_prophet, w_xgb).
- Metricas: RMSE, MAE, SMAPE, MASE.
- Artefacto `.pkl` + sidecar `.csv` con metadata de version.

## Hiperparametros principales

| Parametro | Default | Descripcion |
|-----------|---------|-------------|
| prophet_base.changepoint_prior_scale | 0.05 | Flexibilidad de tendencia |
| xgboost.n_estimators | 300 | Numero de arboles XGBoost |
| xgboost.max_depth | 4 | Profundidad maxima |
| parallel.alpha | 1.0 | Regularizacion Ridge para pesos |
| parallel.oof_folds | 4 | Folds de expanding-window OOF |
| parallel.min_train_weeks | 104 | Minimo de semanas para OOF |

## Metricas de referencia

- SMAPE tipico: 12-35%, generalmente mejor que Prophet standalone.
- Los pesos OOF tipicamente asignan 40-70% a Prophet y 30-60% a XGBoost.

## Limitaciones

- Requiere al menos 104 semanas para modo paralelo; con menos, usa pesos iguales.
- XGBoost recursivo puede acumular error en horizontes largos (>26 semanas).
- Los residuos OOF asumen estacionariedad local de los errores de Prophet.
