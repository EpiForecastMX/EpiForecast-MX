# Reporte Detallado: Stacking (Prophet + ETS + LightGBM + ElasticNet)

## EpiForecast-MX | IMSS | Marzo 2026

---

## 1. Resumen ejecutivo

El modelo Stacking es el cuarto motor de pronostico de EpiForecast-MX. Combina tres
expertos independientes — Prophet, ETS (Holt-Winters) y LightGBM — mediante un
meta-learner ElasticNet que aprende pesos optimos via validacion cruzada expanding-window
(OOF). A diferencia del Ensemble (2 modelos), Stacking usa 3 expertos con enfoques
complementarios: modelo aditivo bayesiano (Prophet), modelo de suavizamiento exponencial
(ETS) y gradient boosting (LightGBM).

Opera sobre conteos absolutos (no tasas por 100k). Genera 333 modelos (3 padecimientos
x 111 combinaciones entidad/sexo).

---

## 2. Arquitectura del modelo

### 2.1 Clase principal: `StackingForecaster`

**Archivo**: `src/epiforecast/models/stacking/model.py` (277 lineas)

Implementa la interfaz `ForecastModel` (patron Factory/SOLID):

| Metodo | Descripcion |
|--------|-------------|
| `fit(train_data)` | Entrena OOF meta-learner + re-entrena expertos en train completo |
| `predict(horizon)` | Prediccion historica (in-sample) + futura via combinacion ponderada |
| `cross_validate(data)` | Evalua stacking sobre hold-out temporal |
| `save(path)` | Serializa expertos + meta-learner + pesos a pickle |
| `load(path)` | Restaura desde pickle (backward compatible con Ridge legacy) |
| `get_params()` | Retorna HP, pesos, tipo de meta-learner |
| `run()` | Pipeline completo: datos -> fit -> evaluar |

Registrado en la factory con `@register_model("stacking")`.

### 2.2 Expertos: `experts.py`

**Archivo**: `src/epiforecast/models/stacking/experts.py` (163 lineas)

| Experto | Descripcion |
|---------|-------------|
| `ProphetExpert` | Prophet con yearly_custom seasonality. Predice `yhat` sobre fechas |
| `ETSExpert` | Holt-Winters (statsmodels). Seasonal_periods=52, trend=add, seasonal=add |
| `LGBMExpert` | LightGBM con trend lineal. n_estimators=300, max_depth=4, lr=0.05 |

Cada experto implementa `fit(train_data)` y `predict(dates)`. Los expertos son
independientes y no comparten informacion entre si.

### 2.3 Meta-learner: `meta_learner.py`

**Archivo**: `src/epiforecast/models/stacking/meta_learner.py` (158 lineas)

`StackingMetaLearner`: Aprende pesos optimos via expanding-window OOF.

| Paso | Descripcion |
|------|-------------|
| 1. Folds | Genera N cutoffs equidistantes entre (oof_cutoff - 18 meses) y oof_cutoff |
| 2. Por fold | Deep copy de cada experto, fit en fold_train, predict en fold_val |
| 3. Apilar | `x_oof = [pred_prophet, pred_ets, pred_lgbm]` (N_oof x 3) |
| 4. Augmentar | Si `add_temporal_features`: agrega sin_week, cos_week (N_oof x 5) |
| 5. Ajustar | ElasticNet(positive=True, fit_intercept=False, alpha, l1_ratio) |
| 6. Normalizar | Pesos = coef_[:3] / sum(coef_[:3]) |

### 2.4 Flujo de entrenamiento

```
1. Expanding-window OOF (4 folds, cutoff 2024-01-01):
   - Cada fold: entrenar 3 expertos en fold_train, predecir fold_val
   - Apilar predicciones: x_oof = [prophet, ets, lgbm]
   - Augmentar con sin_week, cos_week si add_temporal_features=true
   - ElasticNet(positive=True) sobre (x_oof, y_oof) -> pesos

2. Re-entrenar expertos en train completo

3. Prediccion:
   - Si add_temporal_features: yhat = ridge.predict([prophet, ets, lgbm, sin, cos])
   - Si no: yhat = w_prophet * prophet + w_ets * ets + w_lgbm * lgbm
```

---

## 3. Hiperparametros

### 3.1 Prophet (experto)

| Parametro | Valor |
|-----------|-------|
| `changepoint_prior_scale` | 0.05 |
| `seasonality_prior_scale` | 0.1 |
| `seasonality_mode` | additive |
| `yearly_custom.period` | 365.25 |
| `yearly_custom.fourier_order` | 10 |

### 3.2 ETS (experto)

| Parametro | Valor |
|-----------|-------|
| `seasonal_periods` | 52 |
| `trend` | add |
| `seasonal` | add |

### 3.3 LightGBM (experto)

| Parametro | Valor |
|-----------|-------|
| `n_estimators` | 300 |
| `max_depth` | 4 |
| `learning_rate` | 0.05 |
| `subsample` | 0.8 |
| `num_leaves` | 31 |

### 3.4 Meta-learner

| Parametro | Valor | Nota |
|-----------|-------|------|
| `type` | elasticnet | Antes era ridge (v1) |
| `alpha` | 1.0 | Fuerza de regularizacion |
| `l1_ratio` | 0.5 | Balance L1/L2 en ElasticNet |
| `add_temporal_features` | true | Agrega sin/cos_week al stack |
| `oof_cutoff` | 2024-01-01 | Inicio de ventana OOF |
| `oof_n_folds` | 4 | Numero de folds expanding |
| `oof_min_train_weeks` | 104 | Minimo 2 anios de train por fold |

---

## 4. Evaluacion

### 4.1 Metodo de evaluacion

1. **Train**: Datos anteriores a `FECHA_CORTE_ENTRENAMIENTO_STACKING` (2025-01-01)
2. **Test**: Datos posteriores al corte
3. **Metricas**: RMSE, MAE, SMAPE, MASE via `compute_forecast_metrics()`

### 4.2 Resultados (promedio sobre 111 series por padecimiento)

| Padecimiento | RMSE | MAE | SMAPE | MASE |
|-------------|------|-----|-------|------|
| Alzheimer | 1.446 | 1.007 | 142.8% | 0.647 |
| Depresion | 36.13 | 28.54 | 28.0% | 0.972 |
| Parkinson | 3.804 | 2.885 | 87.5% | 0.780 |

### 4.3 Distribucion de pesos por padecimiento (promedio)

| Padecimiento | Prophet | ETS | LightGBM |
|-------------|---------|-----|----------|
| Alzheimer | 22.4% | 20.3% | 17.7% |
| Depresion | 45.4% | 27.3% | 27.4% |
| Parkinson | 28.8% | 35.6% | 26.5% |

**Observaciones**:
- Depresion se apoya mas en Prophet (45%) dado su mayor volumen y tendencia clara.
- Parkinson favorece ETS (36%) por sus patrones estacionales estables.
- Alzheimer distribuye equilibradamente entre los 3 expertos.

### 4.4 Comparacion vs Prophet

| Padecimiento | Metrica | Prophet | Stacking | Mejora |
|-------------|---------|---------|----------|--------|
| Alzheimer | MAE | 1.145 | 1.007 | -12.1% |
| Alzheimer | MASE | 0.776 | 0.647 | -16.6% |
| Depresion | SMAPE | 29.26 | 27.97 | -4.4% |
| Parkinson | RMSE | 4.082 | 3.804 | -6.8% |
| Parkinson | MAE | 3.186 | 2.885 | -9.4% |

Stacking destaca especialmente en Alzheimer (baja incidencia) donde la diversidad
de expertos mejora la robustez. En Depresion (alta incidencia), el Ensemble paralelo
supera a Stacking.

---

## 5. Serializacion y artefactos

### 5.1 Formato de guardado

```python
payload = {
    "experts": self._experts,           # [ProphetExpert, ETSExpert, LGBMExpert]
    "ridge": self._ridge,               # ElasticNet o Ridge entrenado
    "weights": self._weights,           # np.ndarray [w_prophet, w_ets, w_lgbm]
    "params": self.get_params(),        # Hiperparametros
    "serie": self.serie,                # Serie historica
    "n_train": self._n_train,           # Tamano del train set
    "meta_type": self._meta_type,       # "elasticnet" o "ridge"
    "add_temporal_features": self._add_temporal_features,
}
```

Ademas genera un CSV sidecar con la serie historica para desnormalizacion.

### 5.2 Artefactos generados

```
models/stacking/
  Alzheimer/
    Stacking_Alzheimer_general.pkl       # 3 expertos + meta-learner serializados
    Stacking_Alzheimer_general.csv       # Serie historica (sidecar)
    Stacking_Alzheimer_completo.csv      # Metadata: metricas, pesos, HP, tiempo
    ... (111 series total)
  Depresion/ ...
  Parkinson/ ...
```

---

## 6. Estructura de archivos

```
src/epiforecast/models/stacking/
  __init__.py              # Import para registro en factory
  model.py                 # StackingForecaster (277 lineas)
  experts.py               # ProphetExpert, ETSExpert, LGBMExpert (163 lineas)
  meta_learner.py          # StackingMetaLearner: OOF + ElasticNet (158 lineas)

config/models/stacking.yaml   # Hiperparametros expertos + meta-learner

models/stacking/               # Artefactos serializados (333 modelos)

reports/forecasts/stacking/    # 333 graficos de pronostico
```

---

## 7. Tests unitarios

**Archivo**: `tests/unit/models/test_stacking_model.py`

| Clase de test | Cobertura |
|---------------|-----------|
| `TestStackingInit` | Constructor, config keys, experts creados |
| `TestStackingFitPredict` | OOF meta-learner, pesos validos, prediccion shape |
| `TestStackingCrossValidate` | Metricas sobre hold-out, keys esperados |
| `TestStackingSaveLoad` | Pickle + sidecar CSV, restaura pesos/expertos |
| `TestStackingGetParams` | Dict con pesos, cutoff, meta_type, l1_ratio |
| `TestStackingFactory` | Registrado en factory, create_model retorna StackingForecaster |
| `TestElasticNetMetaLearner` | Config elasticnet, backward compat ridge, temporal augment, load legacy |

Todos los tests usan mocks para evitar entrenamiento real de Prophet/ETS/LightGBM.

---

## 8. Integracion con el ecosistema

### 8.1 Factory pattern

```python
from epiforecast.models.factory import create_model
model = create_model("stacking", df=df, sexo="incrementos_total", padecimiento="Alzheimer")
```

### 8.2 Makefile

```bash
make train-stacking                                    # 297 jobs -> 333 modelos (~8.5 min)
make predict ARGS="modelo_activo='stacking'"           # 333 graficos
make compare-metrics                                   # Excel comparativo 4 modelos
```

---

## 9. Decisiones de diseno y trade-offs

### 9.1 ElasticNet vs Ridge

- **Decision**: ElasticNet(l1_ratio=0.5) como meta-learner default.
- **Razon**: Ridge asigna peso a todos los expertos siempre. ElasticNet con L1 puede
  efectivamente desactivar un experto que no aporte (coeficiente = 0) en series donde
  uno de los expertos domina. Esto es util para las 333 series heterogeneas.
- **Backward compat**: `meta_type: "ridge"` sigue funcionando. Pickles legacy se
  cargan con defaults seguros.

### 9.2 Features temporales en meta-learner

- **Decision**: Agregar sin_week, cos_week como features adicionales al meta-learner.
- **Razon**: Permite que los pesos de los expertos varien estacionalmente. Por ejemplo,
  ETS puede ser mejor en ciertos meses que Prophet. El meta-learner con 5 features
  (3 predicciones + 2 temporales) captura esta variacion.
- **Trade-off**: Mas parametros a estimar con datos OOF limitados. Mitigado por la
  regularizacion del ElasticNet.

### 9.3 Tres expertos complementarios

- **Prophet**: Captura tendencia y estacionalidad con changepoints adaptativos.
- **ETS**: Captura patrones estacionales estables sin complejidad bayesiana.
- **LightGBM**: Captura relaciones no lineales y patrones que los modelos lineales pierden.
- La diversidad de enfoques reduce el riesgo de que un solo modelo falle
  sistematicamente en cierto tipo de serie.

### 9.4 Expanding-window vs rolling-window

- **Decision**: Expanding-window (cada fold usa todo el historial hasta su cutoff).
- **Razon**: Con solo ~300 puntos de entrenamiento, una ventana fija (rolling) perderia
  datos valiosos. Expanding-window simula el escenario real de produccion donde siempre
  se entrena con todo el historial disponible.

---

## 10. Comando de ejecucion

```bash
make train-stacking    # Entrena 333 modelos (ElasticNet + temporal, ~8.5 min)
make predict ARGS="modelo_activo='stacking'"   # Genera 333 graficos
make compare-metrics   # Excel comparativo 4 modelos
```
