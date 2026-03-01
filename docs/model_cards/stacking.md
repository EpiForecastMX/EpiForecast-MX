# Model Card: Stacking (Prophet + ETS + LightGBM + Ridge)

## Descripcion

Modelo de stacking que combina tres expertos heterogeneos con un meta-learner Ridge/ElasticNet. Cada experto aporta una perspectiva diferente sobre la serie temporal.

## Arquitectura

1. **ProphetExpert**: tendencia + estacionalidad anual personalizada.
2. **ETSExpert**: Holt-Winters (ExponentialSmoothing) con estacionalidad semanal (periodo 52).
3. **LGBMExpert**: LightGBM con features trigonometricos (sin_sem, cos_sem, trend).
4. **StackingMetaLearner**: aprende pesos optimos via expanding-window OOF con Ridge(positive=True) o ElasticNet.

## Inputs

- DataFrame epidemiologico con columnas: Fecha, Padecimiento, Entidad, incrementos_total.
- Configuracion en `config/models/stacking.yaml` y `config/base.yaml`.

## Outputs

- Pronostico semanal a 52 semanas (yhat ponderado de 3 expertos).
- Pesos del stacking (w_prophet, w_ets, w_lgbm).
- Metricas: RMSE, MAE, SMAPE, MASE.
- Artefacto `.pkl` + sidecar `.csv` con metadata de version.

## Hiperparametros principales

| Parametro | Default | Descripcion |
|-----------|---------|-------------|
| prophet.changepoint_prior_scale | 0.05 | Flexibilidad de tendencia |
| ets.seasonal_periods | 52 | Periodo de estacionalidad ETS |
| lgbm.n_estimators | 300 | Numero de arboles LightGBM |
| meta_learner.type | elasticnet | Tipo de meta-learner (ridge/elasticnet) |
| meta_learner.alpha | 1.0 | Regularizacion del meta-learner |
| meta_learner.l1_ratio | 0.5 | Ratio L1/L2 para ElasticNet |
| meta_learner.add_temporal_features | true | Agregar sin_week/cos_week al meta-learner |

## Metricas de referencia

- SMAPE tipico: 10-30%, competitivo con Ensemble.
- Los pesos tipicamente reflejan la fortaleza relativa de cada experto por grupo.

## Limitaciones

- ETSExpert requiere al menos 104 semanas (2x seasonal_periods); series cortas usan fallback zeros.
- El meta-learner Ridge(positive=True) fuerza pesos no-negativos pero puede ignorar expertos utiles si la regularizacion es alta.
- deepcopy de expertos en OOF puede ser costoso en memoria para series largas.
