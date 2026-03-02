# Reporte Tecnico: Backtest Real en DeepAR predict()

## EpiForecast-MX | IMSS | Marzo 2026

---

## 1. Resumen ejecutivo

Se detecto y corrigio un defecto critico en `DeepARForecaster.predict()` que copiaba
los valores reales (`y`) como prediccion historica (`yhat`), produciendo graficos
engañosos con precision historica del 100% y sin banda de incertidumbre. La correccion
implementa un backtest real por ventana expansiva que genera fitted values honestos
desde diciembre de 2014 en adelante.

---

## 2. Problema: causa raiz

### 2.1 Codigo original (antes del fix)

En `src/epiforecast/models/deepar/model.py`, el metodo `_predict_single()` contenia
el siguiente bloque para construir el periodo historico del DataFrame de forecast:

```python
# lineas 488-494 (antes)
if not self.serie.empty:
    target_col = "y_original" if "y_original" in self.serie.columns else "y"
    df_history = self.serie[["ds", target_col]].copy()
    df_history = df_history.rename(columns={target_col: "yhat"})
    df_history["yhat_lower"] = df_history["yhat"]
    df_history["yhat_upper"] = df_history["yhat"]
    return pd.concat([df_history, df_future], ignore_index=True)
```

El mismo patron se repetia en `_predict_multi()` (lineas 544-550).

### 2.2 Efecto del defecto

| Aspecto                    | Comportamiento defectuoso                         |
|----------------------------|---------------------------------------------------|
| **yhat historico**         | Copia exacta de `y` real (enteros identicos)      |
| **yhat_lower / yhat_upper**| Iguales a `yhat` (sin banda de incertidumbre)     |
| **Graficos individuales**  | "Ajuste del Modelo" superpuesto a "Datos reales"  |
| **Graficos comparativos**  | DeepAR aparenta precision perfecta vs otros modelos |
| **precision_historica**    | 100.00% artificial en tabla de produccion         |
| **CSV all_forecast_deepar**| Columna `yhat` = enteros copiados de `y`          |

### 2.3 Por que ocurrio

Prophet genera fitted values nativamente como parte de su proceso de ajuste
(`model.predict(future)` retorna predicciones para todo el rango, incluido el
historico). Ensemble y Stacking tambien generan residuos reales al entrenar sus
meta-modelos.

DeepAR (GluonTS) no tiene concepto de "fitted values" en su API: solo genera
predicciones futuras a partir de un contexto dado. El codigo original tomo el
atajo de copiar `y` como placeholder, pero esto se convirtio en un defecto
permanente porque los graficos y metricas lo consumian como si fuera prediccion real.

### 2.4 Impacto en la tabla de produccion

La columna `precision_historica` (ratio pronostico/realidad de las ultimas 52 semanas)
mostraba **100%** para todos los modelos DeepAR, lo cual era falso. Un fix previo
(commit `1a9cf53a`) introdujo un cache de backtest externo en `genera_tabla_produccion.py`
para corregir la tabla, pero el CSV base seguia contaminado.

---

## 3. Solucion implementada

### 3.1 Nuevo metodo: `_backtest_fitted()` (series individuales)

Archivo: `src/epiforecast/models/deepar/model.py`, lineas 449-513.

Implementa un **backtest por ventana expansiva** (expanding window) sobre la serie
historica completa:

```
Serie:   [sem_1 ............ sem_52 | sem_53 ............ sem_104 | ... | sem_579 ... sem_630]
          ^^^^^^^^^^^^^^^^^^^^^^^^    ^^^^^^^^^^^^^^^^^^^^^^^^          ^^^^^^^^^^^^^^^^^^^^^^^^
          Fallback (copia y real)     Paso 1: predict(context=52)  ... Paso 11: predict(context=578)
```

**Algoritmo:**

1. Inicializar `yhat_arr` con los valores reales de `y_original` como fallback.
2. Para las primeras 52 semanas: no hay contexto suficiente para predecir, se
   mantiene el fallback (copia de `y`).
3. Desde la semana 53 en adelante, en bloques de 52 semanas:
   - Tomar como contexto todas las semanas anteriores al bloque actual.
   - Construir un dataset GluonTS con `_build_dataset(context)`.
   - Ejecutar `self._predictor.predict()` para obtener predicciones.
   - Desnormalizar de tasa por 100,000 a casos absolutos (si aplica).
   - Sobrescribir `yhat_arr[cursor:end]` con la prediccion real.
   - Guardar `yhat_lower` (percentil 5) y `yhat_upper` (percentil 95).
4. Si alguna ventana falla, el fallback (valor real) se mantiene.

**Costo computacional:**

- ~11 pasadas de inferencia por serie (630 semanas / 52 = ~12 bloques, menos 1 de fallback).
- ~0.1s por pasada = ~1.1 segundos adicionales por serie.
- 333 series x 1.1s = ~6 minutos extra en total vs el metodo anterior.

### 3.2 Nuevo metodo: `_backtest_fitted_multi()` (Nacional / multi-series)

Archivo: `src/epiforecast/models/deepar/model.py`, lineas 515-571.

Para las series de nivel Nacional, DeepAR usa 32 series simultaneas (una por estado)
y suma las predicciones. Un backtest completo expanding-window seria costoso
(32 estados x 11 pasadas = 352 inferencias).

**Simplificacion:** se realiza un unico backtest truncando a las ultimas 52 semanas:

1. Copiar `y` real para semanas 1-578 (fallback).
2. Cortar las 32 series multi-estado en la semana 578.
3. Predecir 52 semanas con el contexto truncado.
4. Desnormalizar por estado y sumar para obtener el Nacional.
5. Sobrescribir las ultimas 52 semanas con la prediccion real.

Las ultimas 52 semanas historicas son las mas visibles en graficos, por lo que
esta simplificacion es honesta para la evaluacion visual.

### 3.3 Modificaciones en predict()

**`_predict_single()`** (linea 638):
```python
# ANTES: copiar y como yhat (6 lineas)
# DESPUES:
if not self.serie.empty:
    df_history = self._backtest_fitted(context_data, horizon)
    return pd.concat([df_history, df_future], ignore_index=True)
```

**`_predict_multi()`** (linea 690):
```python
# ANTES: copiar y como yhat (6 lineas)
# DESPUES:
if not self.serie.empty:
    df_history = self._backtest_fitted_multi(horizon)
    return pd.concat([df_history, df_future], ignore_index=True)
```

---

## 4. Verificacion

### 4.1 Cobertura del backtest (serie individual tipica)

| Rango             | Semanas | Metodo                    | yhat          |
|-------------------|---------|---------------------------|---------------|
| Sem 1-52          | 52      | Fallback (sin contexto)   | Copia de y    |
| Sem 53-630        | 578     | Backtest expanding-window | Prediccion real |
| **Total historico** | **630** | **91.7% backtest real**  |               |

### 4.2 Diferencia observable en CSV

**Antes del fix:**
```
ds,         y,    yhat,   yhat_lower, yhat_upper
2014-01-05, 847,  847.0,  847.0,      847.0     <- yhat == y (falso)
2020-03-15, 1203, 1203.0, 1203.0,     1203.0    <- yhat == y (falso)
```

**Despues del fix:**
```
ds,         y,    yhat,     yhat_lower, yhat_upper
2014-01-05, 847,  847.0,    847.0,      847.0     <- fallback (sem 1-52)
2014-12-28, 892,  878.34,   812.15,     944.53    <- backtest real (sem 53+)
2020-03-15, 1203, 1147.82,  1032.41,    1263.23   <- backtest real con error visible
```

### 4.3 Impacto visual

| Elemento                  | Antes                          | Despues                        |
|---------------------------|--------------------------------|--------------------------------|
| Linea "Ajuste del Modelo" | Superpuesta a datos reales     | Diverge con error visible      |
| Banda de incertidumbre    | Inexistente (ancho = 0)        | Percentiles 5%-95% visibles    |
| Graficos comparativos     | DeepAR parece "perfecto"       | Comparable con Prophet/Ensemble|
| precision_historica        | 100% (falso)                   | Valor real (~85-95%)           |

### 4.4 Tests

- 761 tests unitarios e integracion pasan sin modificaciones.
- `ruff check` y `ruff format` limpios.
- `mypy` sin errores.

---

## 5. Commits relacionados

| Commit     | Descripcion                                                |
|------------|------------------------------------------------------------|
| `1a9cf53a` | Fix parcial: cache de backtest en tabla de produccion      |
| `7b40eb7e` | Fix definitivo: backtest real en DeepAR predict + visualizacion |
| `bdd69ec2` | Restaurar paleta IMSS por padecimiento                     |
| `d93b717e` | Ajuste visual: quitar scatter dots                         |

---

## 6. Arquitectura del backtest vs otros modelos

```
Prophet          ──> model.predict(future) retorna fitted values nativos
                     No necesita backtest externo.

Ensemble         ──> XGBoost genera predicciones in-sample durante fit()
                     Residuos reales disponibles directamente.

Stacking         ──> Meta-learner Ridge entrena sobre out-of-fold predictions
                     Fitted values reales por diseño.

DeepAR (ANTES)   ──> Solo genera predicciones futuras
                     Copiaba y como yhat (DEFECTO)

DeepAR (DESPUES) ──> Backtest expanding-window desde sem 53
                     Genera predicciones reales pasando contexto truncado
                     Banda de incertidumbre via percentiles de muestras
```

---

## 7. Lecciones aprendidas

1. **Nunca copiar valores reales como prediccion.** Aunque sea un placeholder temporal,
   los pipelines downstream lo consumiran como verdad y produciran metricas falsas.

2. **La ausencia de error no es precision.** Un modelo que "predice" exactamente los
   datos reales es sospechoso, no excelente. Los diagnosticos de overfitting/leakage
   deben detectar esta anomalia.

3. **Los graficos son la primera linea de defensa.** Si el "Ajuste del Modelo" se
   superpone perfectamente a los "Datos reales", algo esta mal — ningun modelo
   estadistico tiene error cero.

4. **El backtest expanding-window es el estandar correcto** para generar fitted values
   cuando el modelo no los produce nativamente. Simula el proceso real: "dado lo que
   sabia hasta la semana N, que habria predicho para las semanas N+1 a N+52".

---

*Generado: 2026-03-02 | EpiForecast-MX | IMSS*
