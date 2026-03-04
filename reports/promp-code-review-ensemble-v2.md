# Code Review: Mejoras Ensemble & Stacking — EpiForecast-MX

## Resumen

7 archivos modificados. **Las mejoras P1 (Feature Engineering), P2 (HP XGBoost) y P4 (Stacking ElasticNet) están bien implementadas.** La P3 (Ensemble Paralelo) está parcialmente implementada — falta lo más importante.

---

## 🔴 CRÍTICO — Archivos faltantes (P3 no funciona)

`model.py` importa dos módulos que **NO EXISTEN**:

```python
from epiforecast.models.ensemble.weight_optimizer import EnsembleWeightOptimizer
from epiforecast.models.ensemble.xgb_direct import XGBDirectForecaster
```

**Resultado**: `ImportError` al instanciar `EnsembleForecaster` en cualquier modo (el import es top-level, no lazy). Todo el pipeline de Ensemble está roto, incluyendo el modo sequential legacy.

### Acción requerida

Claude Code debe crear estos dos archivos:

**1. `src/epiforecast/models/ensemble/xgb_direct.py`** — XGBoost que predice y directamente:
```python
class XGBDirectForecaster:
    def __init__(self, xgb_hp: dict): ...
    def fit(self, train_data: pd.DataFrame) -> None: ...
    def predict_insample(self, data: pd.DataFrame) -> np.ndarray: ...
    def predict_recursive(self, history: pd.DataFrame, future_dates: np.ndarray) -> np.ndarray: ...
```

**2. `src/epiforecast/models/ensemble/weight_optimizer.py`** — OOF weight learning:
```python
class EnsembleWeightOptimizer:
    def __init__(self, alpha, n_folds, min_train_weeks): ...
    def fit_oof(self, train_data, prophet_builder, xgb_builder, oof_cutoff) -> np.ndarray: ...
```

### Fix alternativo rápido (si quieres que el código al menos no crashee)

Cambiar los imports a lazy (dentro de los métodos que los usan):

```python
# En model.py, QUITAR las líneas 33-34 del top-level y moverlas:
def _fit_parallel(self, train_data):
    from epiforecast.models.ensemble.weight_optimizer import EnsembleWeightOptimizer
    from epiforecast.models.ensemble.xgb_direct import XGBDirectForecaster
    ...
```

Esto permite que el modo `"sequential"` funcione mientras se crean los archivos faltantes. Pero el modo `"parallel"` seguirá roto.

---

## 🟡 BUG — Data leakage en `roc_4` y `roc_52` (feature_builder.py)

```python
feats["roc_4"] = y_series.pct_change(4).replace([np.inf, -np.inf], np.nan)
feats["roc_52"] = y_series.pct_change(52).replace([np.inf, -np.inf], np.nan)
```

`pct_change(4)` en fila t calcula `(y[t] - y[t-4]) / y[t-4]`. El feature **usa el valor actual y[t], que es el target**. XGBoost aprende que `roc_4 ≈ (y - lag_4) / lag_4` y obtiene acceso directo a y → métricas artificialmente buenas en entrenamiento, malo en producción.

### Fix

Usar la serie desplazada (como hacen los lags y rolling):

```python
shifted = y_series.shift(1)
feats["roc_4"] = shifted.pct_change(3).replace([np.inf, -np.inf], np.nan)
feats["roc_52"] = shifted.pct_change(51).replace([np.inf, -np.inf], np.nan)
```

Esto calcula `(y[t-1] - y[t-4]) / y[t-4]` — sin leakage.

---

## 🟡 BUG — `_cv_parallel` usa `predict_insample` en test data

```python
def _cv_parallel(self, test_df):
    xgb_pred = self._xgb_direct.predict_insample(test_df)  # ← PROBLEMA
```

`predict_insample` construye features usando `test_df["y"]` — los valores reales del test. Para evaluación honesta debería usar predicción recursiva (como `_predecir_test_recursivo` hace en el modo sequential).

Mismo problema en `_gen_parallel_insample()` para la parte de test.

### Fix

Para test data, usar `predict_recursive`:
```python
xgb_pred = self._xgb_direct.predict_recursive(self.train_data, test_df)
```

---

## 🟡 ISSUE — Inconsistencia de escala en Stacking weights (meta_learner.py)

Cuando `add_temporal_features=True`:
- `fit_oof()` retorna `weights` = primeros 3 coeficientes del modelo, **normalizados** (divididos por suma)
- `self._ridge` = modelo completo con 5 coeficientes, **sin normalizar**

En `_predict_combined()`:
- Con temporal features → usa `self._ridge.predict(x_aug)` (coeficientes crudos)
- Sin temporal features → usa `x_stack @ self._weights` (coeficientes normalizados)

La escala de las predicciones es inconsistente entre ambos paths. Si el Ridge/ElasticNet fue entrenado con coeficientes que suman a (ej) 0.9, `predict()` produce valores ~10% menores que `weights @ x`.

### Fix

Si `add_temporal_features=True`, usar siempre `self._ridge.predict()`:
```python
def _predict_combined(self, x_stack, dates):
    if self._ridge is not None and self._add_temporal_features:
        x_aug = StackingMetaLearner._augment_with_temporal(x_stack, dates)
        return np.clip(self._ridge.predict(x_aug), 0, None)
    elif self._ridge is not None:
        return np.clip(self._ridge.predict(x_stack), 0, None)
    else:
        return np.clip(x_stack @ self._weights, 0, None)
```

---

## ✅ BIEN IMPLEMENTADO

### P1 — Feature Engineering (feature_builder.py)
- 20 features (vs 8 originales) ✓
- Lags estacionales (8, 13, 26, 52) ✓
- Rolling 26, 52 + std_13 ✓
- Sin/cos encoding ✓
- COVID flag usando constantes ✓
- Limpieza de inf residual ✓
- `construir_holidays` intacta ✓

### P2 — HP XGBoost
- `ensemble.yaml`: max_depth 3, lr 0.03, colsample 0.7, min_child_weight, reg_alpha/lambda ✓
- `xgb_tuner.py`: grid actualizado, lee reg_alpha/lambda de config, ya no hardcodea colsample_bytree=0.8 ✓
- `model.py`: lee nuevos HP ✓

### P4 — Stacking ElasticNet (parcial, ver issues arriba)
- `meta_learner.py`: ElasticNet con positive=True ✓
- Features temporales (sin_week, cos_week) al meta-learner ✓
- `stacking.yaml`: config type + l1_ratio + add_temporal_features ✓
- `model.py`: `_predict_combined()` + backward compat ✓
- `save/load`: persiste meta_type y add_temporal_features ✓

### Backward compatibility
- Modo `"sequential"` preservado en model.py ✓
- `load()` con `payload.get("ensemble_mode", "sequential")` para pickles viejos ✓
- Stacking fallback a Ridge cuando type="ridge" ✓

### Calidad de código
- `valid_mask.values.nonzero()[0]` → `np.flatnonzero(valid_mask.to_numpy())` (más claro) ✓
- Lazy import de EnsembleXGBTuner solo en modo sequential ✓
- Type hints en nuevos métodos ✓

---

## CHECKLIST PARA COMPLETAR

| # | Prioridad | Acción | Estado |
|---|-----------|--------|--------|
| 1 | 🔴 | Crear `xgb_direct.py` | FALTANTE |
| 2 | 🔴 | Crear `weight_optimizer.py` | FALTANTE |
| 3 | 🔴 | O convertir imports a lazy para no romper sequential | ALTERNATIVA |
| 4 | 🟡 | Fix leakage en roc_4/roc_52 (usar shifted) | BUG |
| 5 | 🟡 | Fix `_cv_parallel` usar predict_recursive en test | BUG |
| 6 | 🟡 | Fix escala inconsistente en stacking weights | BUG |
| 7 | ⚪ | Tests para nuevos features y modo paralelo | NO VERIFICADO |
