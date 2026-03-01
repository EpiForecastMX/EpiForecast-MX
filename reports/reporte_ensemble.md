# Reporte Detallado: Ensemble (Prophet + XGBoost)

## EpiForecast-MX | IMSS | Marzo 2026

---

## 1. Resumen ejecutivo

El modelo Ensemble es el tercer motor de pronostico de EpiForecast-MX. Opera en dos
modos: **paralelo** (default) y **secuencial** (legacy).

- **Modo paralelo** (v2, marzo 2026): Prophet y XGBDirect predicen independientemente.
  Los pesos `[w_prophet, w_xgb]` se aprenden via Ridge OOF (out-of-fold).
  `yhat = w_prophet * prophet + w_xgb * xgb_direct`.

- **Modo secuencial** (v1): Prophet como modelo base + XGBoost como corrector de
  residuos. `yhat = prophet + xgb(residuos)`.

Opera sobre conteos absolutos (no tasas por 100k). Genera 333 modelos (3 padecimientos
x 111 combinaciones entidad/sexo).

---

## 2. Arquitectura del modelo

### 2.1 Clase principal: `EnsembleForecaster`

**Archivo**: `src/epiforecast/models/ensemble/model.py` (547 lineas)

Implementa la interfaz `ForecastModel` (patron Factory/SOLID):

| Metodo | Descripcion |
|--------|-------------|
| `fit(train_data)` | Paralelo: XGBDirect + Ridge OOF. Secuencial: Prophet + XGBoost residuos |
| `predict(horizon)` | Combinacion ponderada (paralelo) o Prophet + XGBoost iterativo (secuencial) |
| `cross_validate(data)` | Evalua en hold-out temporal (test set) |
| `save(path)` | Serializa modelos + pesos + modo a pickle |
| `load(path)` | Restaura desde pickle (backward compatible con v1) |
| `get_params()` | Retorna HP, modo y pesos |
| `run()` | Pipeline completo: datos -> fit -> evaluar |

Registrado en la factory con `@register_model("ensemble")`.

### 2.2 Modulos auxiliares

| Archivo | Lineas | Descripcion |
|---------|--------|-------------|
| `feature_builder.py` | 105 | 20 features temporales y exogenos para XGBoost |
| `helpers.py` | 329 | Preparacion de datos, predicciones insample, metricas |
| `xgb_direct.py` | 84 | XGBDirectForecaster: predice y directamente (no residuos) |
| `weight_optimizer.py` | 120 | EnsembleWeightOptimizer: Ridge OOF para aprender pesos |
| `xgb_tuner.py` | 253 | Grid search CV temporal para XGBoost |
| `oof_residuals.py` | — | Residuos OOF para modo secuencial |

### 2.3 Flujo de entrenamiento: modo paralelo (default)

```
1. Prophet base:
   - yearly_seasonality custom (period=365.25, fourier_order=10)
   - Holidays: periodos atipicos desde config
   - HP: changepoint_prior_scale=0.05, seasonality_prior_scale=0.1, additive

2. XGBDirect (independiente, NO sobre residuos):
   - 20 features de construir_features_xgb()
   - Predice y directamente con early stopping (20% eval set)
   - HP: max_depth=3, learning_rate=0.03, min_child_weight=5

3. EnsembleWeightOptimizer (expanding-window OOF):
   - 4 folds, cutoff 2024-01-01, min 104 semanas train
   - Ridge(positive=True, fit_intercept=False)
   - Normaliza pesos a sum=1. Fallback [0.5, 0.5]

4. Prediccion final:
   yhat = w_prophet * prophet(dates) + w_xgb * xgb_direct(features)
```

### 2.4 Flujo de entrenamiento: modo secuencial (legacy)

```
1. Prophet base (identico)

2. Calcular residuos OOF:
   residuos = y_train - prophet.predict(train)["yhat"]

3. XGBoost sobre residuos:
   Features: 20 features de construir_features_xgb()
   HP optimizados por grid search (36 combinaciones)

4. Prediccion final:
   yhat = prophet.predict(future)["yhat"] + xgb.predict(features)
```

### 2.5 Prediccion iterativa a futuro

Para ambos modos, la prediccion mas alla de datos disponibles opera de forma
iterativa (recursiva):

1. Se construyen features con toda la serie historica
2. Se predice el siguiente paso
3. Se agrega la prediccion a la serie extendida
4. Se repite para las siguientes `horizon` semanas

---

## 3. Hiperparametros

### 3.1 Prophet base

| Parametro | Valor |
|-----------|-------|
| `changepoint_prior_scale` | 0.05 |
| `seasonality_prior_scale` | 0.1 |
| `seasonality_mode` | additive |
| `yearly_custom.period` | 365.25 |
| `yearly_custom.fourier_order` | 10 |

### 3.2 XGBoost

| Parametro | Valor | Nota |
|-----------|-------|------|
| `n_estimators` | 200 | Max 500 con early stopping |
| `max_depth` | 3 | Reducido de 4 para evitar overfitting |
| `learning_rate` | 0.03 | Reducido de 0.05 |
| `subsample` | 0.8 | |
| `colsample_bytree` | 0.7 | Reducido de 0.8 |
| `min_child_weight` | 5 | Nuevo: regularizacion para series cortas |
| `reg_alpha` | 0.1 | Nuevo: L1 regularization |
| `reg_lambda` | 1.0 | Nuevo: L2 regularization |

### 3.3 Modo paralelo

| Parametro | Valor |
|-----------|-------|
| `ensemble_mode` | parallel |
| `parallel_alpha` | 1.0 |
| `parallel_oof_folds` | 4 |
| `parallel_oof_cutoff` | 2024-01-01 |
| `parallel_min_train_weeks` | 104 |

### 3.4 Features de XGBoost (20 total)

| Feature | Descripcion |
|---------|-------------|
| `lag_1` | Valor de y en t-1 |
| `lag_2` | Valor de y en t-2 |
| `lag_4` | Valor de y en t-4 |
| `lag_8` | Valor de y en t-8 |
| `lag_13` | Valor de y en t-13 (trimestral) |
| `lag_26` | Valor de y en t-26 (semestral) |
| `lag_52` | Valor de y en t-52 (anual) |
| `roll_4` | Media movil 4 sem (shifted) |
| `roll_8` | Media movil 8 sem (shifted) |
| `roll_12` | Media movil 12 sem (shifted) |
| `roll_26` | Media movil 26 sem (shifted) |
| `roll_52` | Media movil 52 sem (shifted) |
| `roll_std_13` | Volatilidad trimestral (std shifted) |
| `month` | Mes del anio (1-12) |
| `week_of_year` | Semana ISO del anio (1-53) |
| `sin_week` | Codificacion ciclica seno (semana) |
| `cos_week` | Codificacion ciclica coseno (semana) |
| `roc_4` | Tasa de cambio 4 semanas (pct_change) |
| `roc_52` | Tasa de cambio 52 semanas (pct_change) |
| `covid_flag` | Binario: 1 durante COVID (2020-03 a 2023-05) |

Las rolling means usan `shift(1)` para evitar data leakage. Los `roc_*` reemplazan
`inf` por `NaN` para evitar crash de XGBoost en series con semanas de cero incidencia.

### 3.5 Grid search (modo secuencial)

36 combinaciones (3x3x2x2):

| Parametro | Valores |
|-----------|---------|
| `max_depth` | [3, 4, 5] |
| `learning_rate` | [0.01, 0.03, 0.05] |
| `subsample` | [0.7, 0.8] |
| `min_child_weight` | [5, 10] |

---

## 4. Evaluacion

### 4.1 Metodo de evaluacion

1. **Train**: Datos anteriores a `FECHA_CORTE_ENTRENAMIENTO` (2025-01-01)
2. **Test**: Datos posteriores al corte
3. **Metricas**: RMSE, MAE, SMAPE, MASE via `compute_forecast_metrics()`

### 4.2 Resultados (promedio sobre 111 series por padecimiento)

| Padecimiento | RMSE | MAE | SMAPE | MASE |
|-------------|------|-----|-------|------|
| Alzheimer | 1.414 | 1.079 | 125.3% | 0.739 |
| Depresion | 29.42 | 21.40 | 27.2% | 0.887 |
| Parkinson | 3.766 | 2.807 | 81.1% | 0.775 |

### 4.3 Comparacion vs Prophet (mejora del Ensemble)

| Padecimiento | Metrica | Prophet | Ensemble | Mejora |
|-------------|---------|---------|----------|--------|
| Alzheimer | RMSE | 1.424 | 1.414 | -0.7% |
| Alzheimer | MAE | 1.145 | 1.079 | -5.8% |
| Alzheimer | MASE | 0.776 | 0.739 | -4.8% |
| Depresion | RMSE | 31.22 | 29.42 | -5.8% |
| Depresion | MAE | 25.68 | 21.40 | -16.7% |
| Depresion | SMAPE | 29.26 | 27.19 | -7.1% |
| Parkinson | RMSE | 4.082 | 3.766 | -7.7% |
| Parkinson | MAE | 3.186 | 2.807 | -11.9% |
| Parkinson | MASE | 0.796 | 0.775 | -2.6% |

El Ensemble mejora consistentemente en RMSE, MAE y MASE. SMAPE es mixto en
padecimientos de baja incidencia (Alzheimer, Parkinson) donde la division por
valores cercanos a cero infla la metrica.

---

## 5. Serializacion y artefactos

### 5.1 Formato de guardado

```python
# Modo paralelo
payload = {
    "prophet": self._prophet,
    "xgb_direct": self._xgb_direct,
    "ensemble_weights": self._ensemble_weights,
    "ensemble_mode": self._ensemble_mode,
    "params": self.get_params(),
    "features": self._feature_names,
}

# Modo secuencial (legacy)
payload = {
    "prophet": self._prophet,
    "xgb": self._xgb,
    "params": self.get_params(),
    "features": self._feature_names,
}
```

### 5.2 Artefactos generados

```
models/ensemble/
  Alzheimer/
    Ensemble_Alzheimer_general.pkl       # Modelos serializados
    Ensemble_Alzheimer_general.csv       # Serie historica (sidecar)
    Ensemble_Alzheimer_completo.csv      # Metadata: metricas, HP, pesos, tiempo
    ... (111 series total: 3 nacional + 96 regional + 12 por region salud mental)
  Depresion/ ...
  Parkinson/ ...
```

---

## 6. Estructura de archivos

```
src/epiforecast/models/ensemble/
  __init__.py              # Import para registro en factory
  model.py                 # EnsembleForecaster (547 lineas)
  feature_builder.py       # 20 features temporales y exogenos (105 lineas)
  helpers.py               # Preparacion datos, predicciones, metricas (329 lineas)
  xgb_direct.py            # XGBDirectForecaster para modo paralelo (84 lineas)
  weight_optimizer.py      # Ridge OOF para aprender pesos (120 lineas)
  xgb_tuner.py             # Grid search CV temporal (253 lineas)
  oof_residuals.py         # Residuos OOF para modo secuencial

config/models/ensemble.yaml   # Hiperparametros, grid, modo

models/ensemble/               # Artefactos serializados (333 modelos)

reports/forecasts/ensemble/    # 333 graficos de pronostico
```

---

## 7. Tests unitarios

**Archivos**:
- `tests/unit/models/test_ensemble_model.py`
- `tests/unit/models/test_xgb_direct.py`
- `tests/unit/models/test_weight_optimizer.py`

| Clase de test | Cobertura |
|---------------|-----------|
| `TestEnsembleInit` | Constructor, config keys, modo paralelo/secuencial |
| `TestConstruirFeaturesXgb` | 20 columnas, lags, rolling, ciclicos, COVID flag, ROC |
| `TestConstruirHolidays` | DataFrame valido, COVID presente, config vacia |
| `TestGetParams` | Dict con claves prophet, xgboost, modo, pesos |
| `TestSaveLoad` | RuntimeError sin modelo, crea archivo, restaura, backward compat |
| `TestFactoryRegistration` | Registrado en factory, create_model retorna EnsembleForecaster |
| `TestOOFResiduals` | Residuos out-of-fold con mock XGBoost |
| `TestParallelMode` | Fit paralelo, predict, CV, save/load, pesos, get_params |
| `TestXGBDirect` | Fit, predict_insample, predict_recursive, features, early stopping |
| `TestWeightOptimizer` | Expanding-window OOF, fallback pesos iguales, normalizacion |

Todos los tests usan mocks de Prophet y XGBoost para evitar entrenamiento real.

---

## 8. Integracion con el ecosistema

### 8.1 Factory pattern

```python
from epiforecast.models.factory import create_model
model = create_model("ensemble", df=df, sexo="incrementos_total", padecimiento="Alzheimer")
```

### 8.2 Makefile

```bash
make train-ensemble                                    # 297 jobs -> 333 modelos
make predict ARGS="modelo_activo='ensemble'"           # 333 graficos
make compare                                           # Comparativas 4 modelos
```

---

## 9. Decisiones de diseno y trade-offs

### 9.1 Modo paralelo vs secuencial

- **Decision**: Modo paralelo como default (v2).
- **Razon**: En modo secuencial, si Prophet falla en capturar un patron, XGBoost
  hereda el sesgo al operar sobre residuos. En modo paralelo, ambos modelos predicen
  independientemente y los pesos se optimizan via Ridge OOF.
- **Resultado**: Mejora de hasta 16.7% en MAE (Depresion) respecto a Prophet solo.

### 9.2 20 features vs 8 originales

- **Decision**: Expandir de 8 a 20 features (lags estacionales, volatilidad, ciclicos,
  ROC, COVID flag).
- **Razon**: Los lags cortos (1, 2, 4) no capturan patrones estacionales. Agregar
  lag_52, roll_52, sin/cos_week permite a XGBoost capturar estacionalidad anual.
  covid_flag evita que el modelo interprete la pandemia como patron recurrente.

### 9.3 Regularizacion reforzada

- **Decision**: min_child_weight=5, reg_alpha=0.1, reg_lambda=1.0, max_depth=3.
- **Razon**: Con ~300 puntos de entrenamiento y 20 features, el riesgo de overfitting
  es alto. La regularizacion adicional previene que XGBoost memorice ruido.

### 9.4 Backward compatibility

- **Decision**: `load()` detecta automaticamente si el pickle es v1 (secuencial) o v2
  (paralelo) y restaura correctamente.
- **Razon**: Modelos entrenados con la version anterior siguen siendo usables.

---

## 10. Comando de ejecucion

```bash
make train-ensemble    # Entrena 333 modelos (modo paralelo, ~3.5 min)
make predict ARGS="modelo_activo='ensemble'"   # Genera 333 graficos
make compare-metrics   # Excel comparativo 4 modelos
```
