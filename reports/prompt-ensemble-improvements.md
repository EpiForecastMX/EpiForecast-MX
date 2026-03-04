# Prompt: Mejoras Ensemble & Stacking — EpiForecast-MX

> **Objetivo**: Mejorar los modelos Ensemble (Prophet + XGBoost) y Stacking (Prophet + ETS + LightGBM) para que compitan con Prophet standalone. Actualmente Prophet gana en la mayoría de las 297 series (3 padecimientos × 32 estados × 3 sexos). Las mejoras deben seguir los principios SOLID, Clean Code, y la estructura Cookiecutter Data Science v2 existente.

---

## CONTEXTO DEL PROYECTO

EpiForecast-MX predice tasas semanales de incidencia de Depresión (F32), Parkinson (G20) y Alzheimer (G30) en los 32 estados de México, desagregados por sexo. Las series tienen ~600 observaciones semanales (2012–2025). Los datos son incrementos (conteos absolutos), no tasas por 100K.

### Arquitectura actual

```
src/epiforecast/
├── models/
│   ├── base.py                      # ForecastModel ABC
│   ├── factory.py                   # @register_model decorator + create_model()
│   ├── ensemble/
│   │   ├── model.py                 # EnsembleForecaster (Prophet base + XGBoost residual)
│   │   ├── feature_builder.py       # construir_features_xgb(), FEATURE_NAMES
│   │   ├── helpers.py               # preparar_datos, predicciones, métricas
│   │   ├── oof_residuals.py         # generate_oof_residuals() expanding-window
│   │   └── xgb_tuner.py            # EnsembleXGBTuner grid search + temporal CV
│   ├── stacking/
│   │   ├── model.py                 # StackingForecaster (Prophet + ETS + LightGBM → Ridge)
│   │   ├── meta_learner.py          # StackingMetaLearner OOF expanding-window
│   │   └── experts.py              # ProphetExpert, ETSExpert, LGBMExpert
│   └── prophet/
│       └── model.py                 # ProphetForecaster (standalone, el benchmark a superar)
├── evaluation/
│   └── metrics.py                   # rmse, mae, mape, smape, mase, compute_forecast_metrics
├── constants.py                     # RANDOM_SEED=42, CONDITIONS, STATES, etc.
└── utils/
    └── config.py                    # OmegaConf loader → conf dict + logger
```

### Configuración YAML relevante

**config/models/ensemble.yaml:**
```yaml
prophet_base:
  changepoint_prior_scale: 0.05
  seasonality_prior_scale: 0.1
  seasonality_mode: additive
  yearly_custom:
    period: 365.25
    fourier_order: 10

xgboost:
  n_estimators: 200
  max_depth: 4
  learning_rate: 0.05
  subsample: 0.8
  colsample_bytree: 0.8

oof_residual_folds: 3

param_grid_xgboost:
  max_depth: [3, 4, 5, 6]
  learning_rate: [0.01, 0.05, 0.1]
  subsample: [0.7, 0.8, 0.9]

xgb_cv_splits: 4
xgb_cv_test_size: 26
xgb_early_stopping_rounds: 15
xgb_n_estimators_max: 500
```

**config/models/stacking.yaml:**
```yaml
stacking:
  prophet: {changepoint_prior_scale: 0.05, seasonality_prior_scale: 0.1, seasonality_mode: additive, yearly_custom: {period: 365.25, fourier_order: 10}}
  ets: {seasonal_periods: 52, trend: "add", seasonal: "add"}
  lgbm: {n_estimators: 300, max_depth: 4, learning_rate: 0.05, subsample: 0.8, num_leaves: 31}
  meta_learner: {alpha: 1.0}
  oof_cutoff: "2024-01-01"
  oof_n_folds: 4
  oof_min_train_weeks: 104
```

---

## MEJORAS A IMPLEMENTAR (en orden de prioridad)

### 1. FEATURE ENGINEERING TEMPORAL — Enriquecer `feature_builder.py`

**Problema actual**: XGBoost solo tiene 8 features básicos (3 lags, 3 rolling means, month, week_of_year). Con ~600 observaciones, puede soportar 15-20 features sin overfitting.

**Archivo a modificar**: `src/epiforecast/models/ensemble/feature_builder.py`

**Features a agregar** (mantener los existentes + añadir):

```python
# Lags adicionales para capturar estacionalidad
FEATURE_NAMES = [
    # --- Existentes ---
    "lag_1", "lag_2", "lag_4",
    "roll_4", "roll_8", "roll_12",
    "month", "week_of_year",
    # --- Nuevos lags estacionales ---
    "lag_8",                # 2 meses
    "lag_13",               # trimestre
    "lag_26",               # semestre
    "lag_52",               # año (estacionalidad anual explícita)
    # --- Rolling windows ampliados ---
    "roll_26",              # media semestral
    "roll_52",              # media anual
    # --- Estadísticos rolling ---
    "roll_std_13",          # volatilidad trimestral
    # --- Codificación cíclica (reemplazar month/week_of_year lineales) ---
    "sin_week",             # sin(2π * week / 52)
    "cos_week",             # cos(2π * week / 52)
    # --- Rate of change ---
    "roc_4",                # (y - lag_4) / lag_4
    "roc_52",               # cambio interanual
    # --- COVID indicator ---
    "covid_flag",           # 1 si 2020-03-15 <= ds <= 2022-09-22
]
```

**Implementación en `construir_features_xgb()`**:
```python
def construir_features_xgb(y_series: pd.Series, dates: pd.Series) -> pd.DataFrame:
    feats = pd.DataFrame(index=y_series.index)
    # Lags
    for lag in [1, 2, 4, 8, 13, 26, 52]:
        feats[f"lag_{lag}"] = y_series.shift(lag)
    # Rolling (sobre shifted para evitar leakage)
    shifted = y_series.shift(1)
    for w in [4, 8, 12, 26, 52]:
        feats[f"roll_{w}"] = shifted.rolling(w).mean()
    # Rolling std
    feats["roll_std_13"] = shifted.rolling(13).std()
    # Cíclicas (NO lineales)
    week = dates.dt.isocalendar().week.astype(int).values
    feats["sin_week"] = np.sin(2 * np.pi * week / 52)
    feats["cos_week"] = np.cos(2 * np.pi * week / 52)
    # Mantener month y week_of_year para backward compat
    feats["month"] = dates.dt.month
    feats["week_of_year"] = week
    # Rate of change
    feats["roc_4"] = (y_series - y_series.shift(4)) / y_series.shift(4).replace(0, np.nan)
    feats["roc_52"] = (y_series - y_series.shift(52)) / y_series.shift(52).replace(0, np.nan)
    # COVID flag
    covid_start = pd.Timestamp("2020-03-15")
    covid_end = pd.Timestamp("2022-09-22")
    feats["covid_flag"] = ((dates >= covid_start) & (dates <= covid_end)).astype(int)
    return feats
```

**Actualizar `FEATURE_NAMES`** para que coincida con las columnas generadas. Actualizar `_feature_names` en `EnsembleForecaster.__init__`.

**Actualizar `ensemble.yaml`** añadiendo sección de features configurables:
```yaml
features:
  lags: [1, 2, 4, 8, 13, 26, 52]
  rolling_windows: [4, 8, 12, 26, 52]
  rolling_std_windows: [13]
  cyclic_encoding: true
  rate_of_change: [4, 52]
  covid_flag: true
```

---

### 2. HIPERPARÁMETROS XGBoost — Tunear para series cortas

**Archivo a modificar**: `config/models/ensemble.yaml`

**Cambios en defaults**:
```yaml
xgboost:
  n_estimators: 300           # era 200
  max_depth: 3                # era 4 — reducir overfitting
  learning_rate: 0.03         # era 0.05 — más conservador
  subsample: 0.8
  colsample_bytree: 0.7      # era 0.8 — más regularización
  min_child_weight: 5         # NUEVO — evitar splits con pocas muestras
  reg_alpha: 0.1              # NUEVO — L1 regularización
  reg_lambda: 1.0             # NUEVO — L2 regularización (default XGBoost)
```

**Actualizar param_grid**:
```yaml
param_grid_xgboost:
  max_depth: [3, 4, 5]            # quitar 6 (overfitting en 600 obs)
  learning_rate: [0.01, 0.03, 0.05]  # quitar 0.1 (muy agresivo)
  subsample: [0.7, 0.8]           # quitar 0.9 (poco regularización)
  min_child_weight: [5, 10]       # NUEVO
```

**Archivo a modificar**: `src/epiforecast/models/ensemble/model.py` — actualizar `_xgb_hp` dict en `__init__` para leer `min_child_weight`, `reg_alpha`, `reg_lambda`.

**Archivo a modificar**: `src/epiforecast/models/ensemble/xgb_tuner.py` — en el loop de grid search, pasar `min_child_weight` desde la combo (ya no hardcodear `colsample_bytree=0.8`).

---

### 3. ENSEMBLE PARALELO — Predicciones independientes con pesos optimizados

**Problema actual**: El Ensemble es secuencial (Prophet → XGBoost corrige residuos). Si Prophet falla en capturar un patrón, XGBoost hereda el sesgo. Cambiar a predicciones paralelas con pesos aprendidos.

**Nuevo enfoque**:
- Prophet genera `yhat_prophet` (como ahora)
- XGBoost genera `yhat_xgb` directo sobre la serie (NO sobre residuos) usando features temporales enriquecidos
- Pesos optimizados por Ridge(positive=True) via OOF validation (patrón ya probado en Stacking)

**Archivos a crear/modificar**:

#### 3a. Nuevo: `src/epiforecast/models/ensemble/xgb_direct.py`
```python
"""XGBoost direct forecaster for parallel ensemble."""
class XGBDirectForecaster:
    """XGBoost que predice y directamente (no residuos)."""
    def fit(self, train_data: pd.DataFrame) -> None: ...
    def predict(self, dates: pd.DataFrame, train_data: pd.DataFrame) -> np.ndarray: ...
    def predict_recursive(self, train_data, test_data) -> np.ndarray: ...
```
- `fit()`: Construir features con `construir_features_xgb()`, entrenar XGBRegressor
- `predict_recursive()`: Predicción step-by-step extendiendo y_ext como en `_predecir_test_recursivo`

#### 3b. Nuevo: `src/epiforecast/models/ensemble/weight_optimizer.py`
```python
"""OOF weight optimization for parallel ensemble."""
class EnsembleWeightOptimizer:
    """Aprende pesos [w_prophet, w_xgb] via expanding-window OOF + Ridge(positive=True)."""
    def fit_oof(self, train_data, cutoff) -> tuple[np.ndarray, Ridge]: ...
```
- Reutilizar patrón de `StackingMetaLearner._compute_oof_folds()` y `fit_oof()`
- Cada fold: entrenar Prophet temporal + XGBDirect temporal → predicciones OOF → Ridge

#### 3c. Modificar: `src/epiforecast/models/ensemble/model.py`
- Añadir flag en config: `ensemble_mode: "parallel"` (default) vs `"sequential"` (legacy)
- En `run()`:
  ```python
  if mode == "parallel":
      # 1. Prophet base
      # 2. XGBDirect (con features mejorados)
      # 3. EnsembleWeightOptimizer → pesos
      # 4. yhat_ensemble = w[0]*yhat_prophet + w[1]*yhat_xgb
  else:
      # legacy: Prophet + XGBoost sobre residuos
  ```
- `predict()` y `cross_validate()` deben soportar ambos modos
- `save()`/`load()` deben serializar `_weights` + `_xgb_direct`

#### 3d. Actualizar: `config/models/ensemble.yaml`
```yaml
ensemble_mode: "parallel"    # "parallel" | "sequential"

# Pesos dinámicos por horizonte (Prophet mejor >8 sem, XGBoost <4 sem)
dynamic_weights:
  enabled: false              # activar después de validar el modo paralelo
  short_horizon_threshold: 4  # semanas
  long_horizon_threshold: 8   # semanas
```

---

### 4. MEJORAS STACKING — ElasticNet + features al meta-learner

**Problema actual**: El meta-learner Ridge solo recibe 3 columnas (pred_prophet, pred_ets, pred_lgbm). No tiene contexto temporal para ajustar pesos dinámicamente.

#### 4a. Modificar: `src/epiforecast/models/stacking/meta_learner.py`
- Cambiar Ridge por ElasticNet(positive=True, l1_ratio=0.5)
- Añadir features al meta-learner: week_of_year (sin/cos encoded)
- El input al Ridge/ElasticNet pasa de 3 columnas a 5: [pred_prophet, pred_ets, pred_lgbm, sin_week, cos_week]

```python
from sklearn.linear_model import ElasticNet

# En fit_oof():
sin_week = np.sin(2 * np.pi * fold_val["ds"].dt.isocalendar().week.astype(int).values / 52)
cos_week = np.cos(2 * np.pi * fold_val["ds"].dt.isocalendar().week.astype(int).values / 52)
x_fold = np.column_stack([*fold_preds, sin_week, cos_week])

# En ridge:
meta = ElasticNet(positive=True, fit_intercept=False, alpha=self._alpha, l1_ratio=0.5)
```

**CUIDADO**: Los pesos ya no son directamente interpretables como "peso por experto". La predicción final usa `meta.predict(x_stack)` en vez de `x_stack @ weights`.

#### 4b. Actualizar: `config/models/stacking.yaml`
```yaml
stacking:
  meta_learner:
    type: "elasticnet"        # "ridge" | "elasticnet"
    alpha: 1.0
    l1_ratio: 0.5
    add_temporal_features: true
```

#### 4c. Modificar: `src/epiforecast/models/stacking/model.py`
- `predict()` y `cross_validate()` deben añadir sin_week/cos_week al x_stack
- `get_params()` debe reflejar tipo de meta-learner

---

## RESTRICCIONES CRÍTICAS

1. **NO modificar `src/epiforecast/models/base.py`** — la interfaz ForecastModel es estable
2. **NO modificar `src/epiforecast/models/prophet/`** — Prophet es el benchmark, no lo tocamos
3. **Backward compatibility**: el modo `"sequential"` del Ensemble debe seguir funcionando idéntico
4. **Tests**: actualizar `tests/unit/models/test_ensemble_model.py` y `test_stacking_model.py`
5. **Max 300 líneas por módulo** — extraer a archivos nuevos si se excede
6. **Imports lazy** para Prophet, XGBoost, LightGBM (solo dentro de métodos que los usan)
7. **Docstrings en español** para todas las funciones/clases nuevas
8. **Type hints** en todas las firmas
9. **Usar `from epiforecast.constants import RANDOM_SEED`** — nunca hardcodear 42
10. **Usar `from epiforecast.constants import COVID_START, COVID_END`** para el covid_flag

---

## ORDEN DE EJECUCIÓN

```
Paso 1: Feature Engineering (feature_builder.py + ensemble.yaml)
         → Correr tests existentes → Verificar que no rompe nada
Paso 2: Hiperparámetros XGBoost (ensemble.yaml + model.py + xgb_tuner.py)
         → Correr tests
Paso 3: Ensemble Paralelo (xgb_direct.py + weight_optimizer.py + model.py)
         → Nuevos tests + correr suite completa
Paso 4: Stacking ElasticNet (meta_learner.py + model.py + stacking.yaml)
         → Nuevos tests + correr suite completa
```

---

## ARCHIVOS COMPLETOS DE REFERENCIA

A continuación se incluyen los archivos actuales completos para que tengas contexto total sin necesidad de preguntar. Modifica quirúrgicamente solo lo necesario.

<details>
<summary>src/epiforecast/models/ensemble/feature_builder.py (ACTUAL)</summary>

```python
"""XGBoost feature engineering for the Ensemble model.

Extracted from helpers.py for SRP compliance (max 300 lines per module).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Features que construye XGBoost
FEATURE_NAMES: list[str] = [
    "lag_1",
    "lag_2",
    "lag_4",
    "roll_4",
    "roll_8",
    "roll_12",
    "month",
    "week_of_year",
]


def construir_features_xgb(y_series: pd.Series, dates: pd.Series) -> pd.DataFrame:
    """Construye features temporales y de lags para XGBoost."""
    feats = pd.DataFrame(index=y_series.index)
    feats["lag_1"] = y_series.shift(1)
    feats["lag_2"] = y_series.shift(2)
    feats["lag_4"] = y_series.shift(4)
    shifted = y_series.shift(1)
    feats["roll_4"] = shifted.rolling(4).mean()
    feats["roll_8"] = shifted.rolling(8).mean()
    feats["roll_12"] = shifted.rolling(12).mean()
    feats["month"] = dates.dt.month
    feats["week_of_year"] = dates.dt.isocalendar().week.astype(int).values
    return feats


def construir_holidays(config: dict[str, Any]) -> pd.DataFrame:
    """Construye DataFrame de holidays desde config (periodos atipicos)."""
    periodos = config.get("peridos_atipicos", [])
    if not periodos:
        return pd.DataFrame(columns=["holiday", "ds", "lower_window", "upper_window"])

    rows = []
    for p in periodos:
        rows.append(
            {
                "holiday": p["holiday"],
                "ds": pd.Timestamp(p["ds"]),
                "lower_window": p.get("lower_window", 0),
                "upper_window": p.get("upper_window", 0),
            }
        )
    return pd.DataFrame(rows)
```
</details>

<details>
<summary>src/epiforecast/models/ensemble/model.py (ACTUAL)</summary>

```python
"""Ensemble forecasting model: Prophet base + XGBoost residual correction."""

from __future__ import annotations

import logging
from pathlib import Path
import pickle
import time
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from epiforecast.constants import RANDOM_SEED
from epiforecast.evaluation.metrics import compute_forecast_metrics

if TYPE_CHECKING:
    from prophet import Prophet
    from xgboost import XGBRegressor
from epiforecast.models.base import ForecastModel
from epiforecast.models.ensemble.helpers import (
    FEATURE_NAMES,
    _predecir_test_recursivo,
    calcular_metricas_ensemble,
    calcular_metricas_prophet_base,
    construir_features_xgb,
    construir_holidays,
    generar_prediccion_completa,
    generar_predicciones_insample,
    preparar_datos_ensemble,
)
from epiforecast.models.ensemble.oof_residuals import generate_oof_residuals
from epiforecast.models.factory import register_model
from epiforecast.utils.config import conf, logger

logging.getLogger("cmdstanpy").disabled = True


@register_model("ensemble")
class EnsembleForecaster(ForecastModel):
    """Ensemble: Prophet base + XGBoost sobre residuos (ForecastModel/LSP)."""

    def __init__(
        self,
        df: pd.DataFrame | None = None,
        sexo: str = "incrementos_total",
        entidad: str | None = None,
        padecimiento: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        self._conf = config if config is not None else conf
        self.df = df.copy() if df is not None else pd.DataFrame()
        self.sexo = sexo
        self.entidad = entidad
        self.padecimiento = padecimiento

        # Config ensemble-specific
        self.cutoff: str = self._conf.get(
            "FECHA_CORTE_ENTRENAMIENTO_ENSEMBLE",
            self._conf.get("FECHA_CORTE_ENTRENAMIENTO", "2025-01-01"),
        )
        self.horizon: int = self._conf.get("HORIZON_ENSEMBLE", 52)

        # Prophet HP
        pb = self._conf.get("prophet_base", {})
        self._prophet_hp: dict[str, Any] = {
            "changepoint_prior_scale": pb.get("changepoint_prior_scale", 0.05),
            "seasonality_prior_scale": pb.get("seasonality_prior_scale", 0.1),
            "seasonality_mode": pb.get("seasonality_mode", "additive"),
        }
        yc = pb.get("yearly_custom", {})
        self._yearly_period: float = yc.get("period", 365.25)
        self._yearly_fourier: int = yc.get("fourier_order", 10)

        # OOF residual folds (0 = legacy in-sample)
        self._oof_residual_folds: int = int(self._conf.get("oof_residual_folds", 0))

        # XGBoost HP
        xgb_hp = self._conf.get("xgboost", {})
        self._xgb_hp: dict[str, Any] = {
            "n_estimators": xgb_hp.get("n_estimators", 200),
            "max_depth": xgb_hp.get("max_depth", 4),
            "learning_rate": xgb_hp.get("learning_rate", 0.05),
            "subsample": xgb_hp.get("subsample", 0.8),
            "colsample_bytree": xgb_hp.get("colsample_bytree", 0.8),
        }

        # Holidays
        self._holidays: pd.DataFrame = construir_holidays(self._conf)

        # Internal state
        self._prophet: Prophet | None = None
        self._xgb: XGBRegressor | None = None
        self._feature_names: list[str] = list(FEATURE_NAMES)

        # Data placeholders
        self.serie: pd.DataFrame = pd.DataFrame()
        self.train_data: pd.DataFrame = pd.DataFrame()
        self.test_data: pd.DataFrame = pd.DataFrame()
        self.pred_train: pd.DataFrame = pd.DataFrame()
        self.pred_test: pd.DataFrame = pd.DataFrame()
        self._t_prophet: float = 0.0
        self._t_ensemble: float = 0.0

    # ... (resto del archivo — ver referencia completa arriba)
```
</details>

<details>
<summary>src/epiforecast/models/ensemble/xgb_tuner.py (ACTUAL)</summary>

```python
"""XGBoost hyperparameter tuner with temporal cross-validation."""
# (ver archivo completo en el contexto proporcionado arriba)
```
</details>

<details>
<summary>src/epiforecast/models/stacking/meta_learner.py (ACTUAL)</summary>

```python
"""Meta-learner para Stacking: OOF validation + Ridge(positive=True)."""
# (ver archivo completo en el contexto proporcionado arriba)
```
</details>

<details>
<summary>src/epiforecast/models/stacking/model.py (ACTUAL)</summary>

```python
"""Stacking forecasting model: Prophet + ETS + LightGBM con Ridge meta-learner."""
# (ver archivo completo en el contexto proporcionado arriba)
```
</details>

<details>
<summary>src/epiforecast/models/stacking/experts.py (ACTUAL)</summary>

```python
"""Expertos para Stacking: Prophet, ETS (Holt-Winters), LightGBM."""
# (ver archivo completo en el contexto proporcionado arriba)
```
</details>

<details>
<summary>src/epiforecast/constants.py (ACTUAL)</summary>

```python
"""Project-wide constants for EpiForecast-MX."""
from typing import Final

RANDOM_SEED: Final[int] = 42
COVID_START: Final[str] = "2020-03-15"
COVID_END: Final[str] = "2022-09-22"
# ... (resto del archivo)
```
</details>

<details>
<summary>src/epiforecast/evaluation/metrics.py (ACTUAL)</summary>

```python
"""Forecasting evaluation metrics."""
# rmse, mae, mape, smape, mase, compute_forecast_metrics
# (ver archivo completo en el contexto proporcionado arriba)
```
</details>

---

## RESUMEN DE CAMBIOS POR ARCHIVO

| Archivo | Acción | Prioridad |
|---------|--------|-----------|
| `ensemble/feature_builder.py` | Modificar: agregar features | P1 |
| `config/models/ensemble.yaml` | Modificar: HP + features config + mode | P1-P3 |
| `ensemble/model.py` | Modificar: leer nuevos HP + modo paralelo | P2-P3 |
| `ensemble/xgb_tuner.py` | Modificar: pasar min_child_weight en grid | P2 |
| `ensemble/xgb_direct.py` | **CREAR**: XGBoost directo (no residuos) | P3 |
| `ensemble/weight_optimizer.py` | **CREAR**: OOF weight learning | P3 |
| `stacking/meta_learner.py` | Modificar: ElasticNet + temporal features | P4 |
| `stacking/model.py` | Modificar: pasar temporal features | P4 |
| `config/models/stacking.yaml` | Modificar: meta_learner config | P4 |
| `constants.py` | Sin cambios (ya tiene COVID_START/END) | — |
| `evaluation/metrics.py` | Sin cambios | — |
| `models/base.py` | **NO TOCAR** | — |
| `models/prophet/` | **NO TOCAR** | — |
