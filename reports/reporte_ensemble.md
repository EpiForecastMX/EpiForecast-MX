# Reporte Detallado: Ensemble (Prophet + XGBoost)

## EpiForecast-MX | IMSS | Febrero 2026

---

## 1. Resumen ejecutivo

El modelo Ensemble es el tercer motor de pronostico de EpiForecast-MX. Combina
Prophet como modelo base (captura tendencia y estacionalidad) con XGBoost como
corrector de residuos (captura volatilidad y patrones no lineales que Prophet pierde).

Este enfoque hibrido fue desarrollado como Avance 5 del proyecto integrador. Opera
sobre conteos absolutos (no tasas por 100k), lo que facilita la interpretacion directa
de las predicciones.

---

## 2. Arquitectura del modelo

### 2.1 Clase principal: `EnsembleForecaster`

**Archivo**: `src/epiforecast/models/ensemble/model.py` (300 lineas)

Implementa la interfaz `ForecastModel` (patron Factory/SOLID):

| Metodo | Descripcion |
|--------|-------------|
| `fit(train_data)` | Entrena Prophet base + XGBoost sobre residuos |
| `predict(horizon)` | Prophet futuro + XGBoost iterativo |
| `cross_validate(data)` | Evalua en hold-out temporal (test set) |
| `save(path)` | Serializa Prophet + XGBoost + params a pickle |
| `load(path)` | Restaura ambos modelos desde pickle |
| `get_params()` | Retorna HP de ambos sub-modelos |
| `run()` | Pipeline completo: datos -> fit -> evaluar |

Registrado en la factory con `@register_model("ensemble")`.

### 2.2 Funciones auxiliares: `helpers.py`

**Archivo**: `src/epiforecast/models/ensemble/helpers.py` (251 lineas)

Extraido de `model.py` para cumplir con SRP (max 300 lineas por modulo):

| Funcion | Descripcion |
|---------|-------------|
| `construir_features_xgb(y, dates)` | Lags (1, 2, 4) + rolling means (4, 8, 12) + month + week |
| `construir_holidays(config)` | DataFrame de periodos atipicos para Prophet |
| `preparar_datos_ensemble(df, pad, sexo, cutoff)` | Filtrar, agregar, train/test split |
| `generar_predicciones_insample(prophet, xgb, train, test)` | Predicciones para graficos |
| `calcular_metricas_ensemble(test, pred, train, nombre, t)` | Metricas del ensemble |
| `calcular_metricas_prophet_base(test, pred, train, t)` | Metricas del Prophet solo |

### 2.3 Flujo de entrenamiento

```
1. Prophet base:
   - yearly_seasonality=False (se agrega custom con period=365.25, fourier_order=10)
   - weekly_seasonality=False
   - Holidays: periodos atipicos desde config (COVID, etc.)
   - Hiperparametros: changepoint_prior_scale=0.05, seasonality_prior_scale=0.1,
     seasonality_mode=additive

2. Calcular residuos:
   residuos = y_train - prophet.predict(train)["yhat"]

3. XGBoost sobre residuos:
   Features: lag_1, lag_2, lag_4, roll_4, roll_8, roll_12, month, week_of_year
   HP: n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.8

4. Prediccion final:
   yhat_ensemble = prophet.predict(future)["yhat"] + xgb.predict(features_future)
```

### 2.4 Prediccion iterativa a futuro

Para generar pronosticos mas alla de los datos disponibles, XGBoost opera de forma
iterativa:

1. Se construyen features con toda la serie historica
2. XGBoost predice el ajuste residual del siguiente paso
3. Se agrega la prediccion combinada (Prophet + XGBoost) a la serie extendida
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

| Parametro | Valor |
|-----------|-------|
| `n_estimators` | 200 |
| `max_depth` | 4 |
| `learning_rate` | 0.05 |
| `subsample` | 0.8 |
| `colsample_bytree` | 0.8 |

### 3.3 Features de XGBoost

| Feature | Descripcion |
|---------|-------------|
| `lag_1` | Valor de y en t-1 |
| `lag_2` | Valor de y en t-2 |
| `lag_4` | Valor de y en t-4 |
| `roll_4` | Media movil de 4 semanas |
| `roll_8` | Media movil de 8 semanas |
| `roll_12` | Media movil de 12 semanas |
| `month` | Mes del anio (1-12) |
| `week_of_year` | Semana ISO del anio (1-53) |

---

## 4. Evaluacion

### 4.1 Metodo de evaluacion

El ensemble usa hold-out temporal (no CV con folds) para evaluar rendimiento:

1. **Train**: Datos anteriores a `FECHA_CORTE_ENTRENAMIENTO` (2025-01-01)
2. **Test**: Datos posteriores al corte
3. **Metricas**: RMSE, MAE, SMAPE, MASE via `compute_forecast_metrics()`

Se comparan las metricas del ensemble completo contra las del Prophet base solo
para cuantificar la mejora que aporta XGBoost.

### 4.2 Metricas Prophet base vs Ensemble

Las metricas se calculan sobre el test set. El script `avance5_modelo_final.py` imprime
una tabla Rich en consola mostrando la comparacion lado a lado para cada padecimiento.

---

## 5. Script de ejecucion: `avance5_modelo_final.py`

**Archivo**: `scripts/avance5_modelo_final.py` (542 lineas)

### 5.1 Flujo principal

```python
for padecimiento in ["Alzheimer", "Depresion", "Parkinson"]:
    df = _cargar_datos()

    # Factory pattern (SOLID)
    forecaster = EnsembleForecaster(df=df, padecimiento=pad, sexo="incrementos_total")
    _, metrics_ensemble, params = forecaster.run()

    # Guardar modelo (MLOps)
    forecaster.save(models_dir / pad / f"Ensemble_{pad}_general.pkl")

    # Guardar serie sidecar + metadata CSV
    forecaster.serie.to_csv(ruta_csv, index=False)
    pd.DataFrame([metrics_ensemble]).to_csv(ruta_completo, index=False)

    # Metricas Prophet base
    metrics_prophet = forecaster.get_prophet_metrics()

    # Tabla Rich + graficos
    _imprimir_tabla_rich([metrics_prophet, metrics_ensemble], pad)
    _graficar_individual(...)        # Prophet solo
    _graficar_individual(...)        # Ensemble solo
    _graficar_importancia(...)       # Feature importance XGBoost
    _graficar_comparativa(...)       # Prophet vs Ensemble
    _graficar_comparativa(...)       # Zoom 2020-2027
```

### 5.2 Visualizaciones generadas

| Grafico | Ruta |
|---------|------|
| Prophet individual | `reports/forecasts/prophet/{pad}/pronostico_{pad}.png` |
| Ensemble individual | `reports/forecasts/ensemble/{pad}/pronostico_{pad}.png` |
| Importancia features | `reports/forecasts/ensemble/{pad}/importancia_features_{pad}.png` |
| Comparativa completa | `reports/forecasts/comparacion_modelos/{pad}/comparativa_{pad}.png` |
| Comparativa reciente | `reports/forecasts/comparacion_modelos/{pad}/comparativa_{pad}_reciente.png` |

### 5.3 Estilo visual

- **Paleta IMSS**: Colores leidos de `conf["IMSS_COLORS"]` (plots.yaml)
  - Real: neutral_black (#231F20)
  - Prophet: teal (#00524E) con linestyle dashdot
  - Ensemble: burgundy (#9B2242) con linestyle solid
  - XGBoost importancia: gold (#B58500)
  - Cutoff: cool_gray (#97999B)
- **Franja COVID**: Desde `conf["COVID"]["inicio"]` hasta `conf["COVID"]["fin"]`
- **Divisores**: Reutiliza `_anotar_divisores()` de `chart_annotations.py`
- **Timestamp**: Zona horaria CDMX (`America/Mexico_City`)
- **DPI**: `VIZ_DPI_SCREEN` (200) de `constants.py`

---

## 6. Serializacion y artefactos

### 6.1 Formato de guardado

```python
payload = {
    "prophet": self._prophet,           # Modelo Prophet entrenado
    "xgb": self._xgb,                   # XGBRegressor entrenado
    "params": self.get_params(),         # Hiperparametros
    "features": self._feature_names,     # Nombres de features XGBoost
}
pickle.dump(payload, path)
```

### 6.2 Artefactos generados

```
models/ensemble/
  Alzheimer/
    Ensemble_Alzheimer_general.pkl       # Prophet + XGBoost serializados
    Ensemble_Alzheimer_general.csv       # Serie historica (sidecar)
    Ensemble_Alzheimer_completo.csv      # Metadata: metricas, HP, tiempo
  Depresion/
    ...
  Parkinson/
    ...
```

---

## 7. Estructura de archivos

```
src/epiforecast/models/ensemble/
  __init__.py              # Import para registro en factory
  model.py                 # EnsembleForecaster (300 lineas)
  helpers.py               # Feature engineering, datos, metricas (251 lineas)

scripts/
  avance5_modelo_final.py  # CLI script para entrenamiento y graficos (542 lineas)

models/ensemble/           # Artefactos serializados (por padecimiento)

reports/forecasts/
  prophet/{pad}/           # Graficos Prophet individual
  ensemble/{pad}/          # Graficos Ensemble individual + feature importance
  comparacion_modelos/{pad}/  # Graficos comparativos
```

---

## 8. Tests unitarios

**Archivo**: `tests/unit/models/test_ensemble_model.py`

| Clase de test | Cobertura |
|---------------|-----------|
| `TestEnsembleInit` | Constructor, df copied, config keys loaded |
| `TestConstruirFeaturesXgb` | Columnas esperadas, lags correctos, rolling mean |
| `TestConstruirHolidays` | DataFrame valido, COVID presente, config vacia |
| `TestGetParams` | Retorna dict con claves prophet y xgboost |
| `TestSaveLoad` | RuntimeError sin modelo, crea archivo, restaura modelos |
| `TestFactoryRegistration` | Registrado en factory, create_model retorna EnsembleForecaster |

Todos los tests usan mocks de Prophet y XGBoost para evitar entrenamiento real.

---

## 9. Integracion con el ecosistema

### 9.1 Factory pattern

El modelo se registra automaticamente al importar el modulo:

```python
# src/epiforecast/models/__init__.py
from epiforecast.models.ensemble import model as _ensemble  # noqa: F401
```

Esto permite instanciar via:
```python
from epiforecast.models.factory import create_model
model = create_model("ensemble", df=df, sexo="incrementos_total", padecimiento="Alzheimer")
```

### 9.2 Makefile

```bash
make avance5                                              # Todos los padecimientos
make avance5 ARGS="padecimiento.tipo='Alzheimer'"         # Solo Alzheimer
```

---

## 10. Decisiones de diseno y trade-offs

### 10.1 Conteos absolutos vs tasas

- **Decision**: El ensemble trabaja con conteos absolutos (incrementos), no tasas.
- **Razon**: Para el Avance 5, el objetivo es predecir directamente el numero de casos.
  La normalizacion a tasas es relevante para comparaciones inter-estatales pero el
  ensemble opera solo a nivel nacional.

### 10.2 Hold-out vs CV con folds

- **Decision**: Evaluacion por hold-out temporal simple en vez de CV con multiples folds.
- **Razon**: XGBoost se entrena sobre residuos de Prophet. Hacer CV con folds requeriria
  reentrenar Prophet en cada fold (costoso) sin beneficio claro dado que los HP son fijos.

### 10.3 Prediccion iterativa de XGBoost

- **Decision**: Para el futuro (mas alla de datos reales), XGBoost predice de forma
  iterativa (un paso a la vez, alimentandose de sus propias predicciones).
- **Trade-off**: Propagacion de errores en horizontes largos. Mitigado porque Prophet
  aporta la tendencia principal y XGBoost solo ajusta residuos pequenios.

### 10.4 Features simples

- **Decision**: Solo 8 features (lags + rolling means + calendario).
- **Razon**: Con datos semanales y ~300 puntos de entrenamiento, mas features llevan a
  overfitting. Los lags y rolling means capturan la autocorrelacion que Prophet pierde.

---

## 11. Refactorizaciones aplicadas

### 11.1 SRP compliance (max 300 lineas)

El `model.py` original tenia 537 lineas. Se extrajo a `helpers.py`:
- `construir_features_xgb()`, `construir_holidays()`
- `preparar_datos_ensemble()`, `generar_predicciones_insample()`
- `calcular_metricas_ensemble()`, `calcular_metricas_prophet_base()`

Resultado: `model.py` = 300 lineas, `helpers.py` = 251 lineas.

### 11.2 Script avance5 refactorizado

El script original (~800 lineas) se redujo a 542 lineas:
- Colores: De hardcoded a `conf["IMSS_COLORS"]`
- COVID: De hardcoded a `conf["COVID"]`
- Constantes: `RANDOM_SEED` y `VIZ_DPI_SCREEN` de `epiforecast.constants`
- Annotations: Reutiliza `_anotar_divisores()` y `_TZ_CDMX` de `chart_annotations`
- Modelo: Toda la logica de entrenamiento encapsulada en `EnsembleForecaster`

### 11.3 Correccion mypy

Se corrigieron 24 errores de tipo en `model.py`:
- `.values` -> `.to_numpy()` para compatibilidad con `ArrayLike`
- `compute_forecast_metrics()` en vez de calculo manual
- `dict[str, float]` con `or 0.0` para valores `float | None`

---

## 12. Comando de ejecucion

```bash
# Ejecutar Avance 5 completo
make avance5

# Solo un padecimiento
make avance5 ARGS="padecimiento.tipo='Alzheimer'"

# Tests
make test-fast
```
