# Reporte de Hallazgos — Modelado Prophet v4

**Fecha:** 2026-02-21
**Modelos entrenados:** 297 (3 padecimientos x 33 entidades x 3 sexos)
**Tiempo total:** 57 minutos (n_jobs=-2, 11 cores)
**Horizonte de prediccion:** 120 semanas

---

## 1. Resumen Ejecutivo

| Padecimiento | Total | Normal | Insuficiente | Tiempo | MAPE Nacional (general) |
|---|---|---|---|---|---|
| **Alzheimer** | 99 | 35 | 64 | ~1 min | 27.9% |
| **Depresion** | 99 | 99 | 0 | ~40 min | 10.1% |
| **Parkinson** | 99 | 79 | 20 | ~16 min | 20.5% |
| **Total** | **297** | **213** | **84** | **57 min** | — |

---

## 2. Configuracion del Entrenamiento (v4)

### 2.1 Transformaciones del target
1. **Normalizacion a tasa por 100K hab.** — iguala escala entre estados
2. **Log-transform:** `y = log(1 + tasa)` — estabiliza varianza
3. **Prophet entrena sobre espacio log-tasa**

### 2.2 Cross-validation
- **4 folds** temporales (TimeSeriesSplit), test_size=53 semanas
- **Pesos progresivos:** `[0.5, 0.75, 1.0, 1.25]` — prioriza folds recientes
- **Timeout:** 120s por combinacion de HP (evita Newton fallbacks de 10+ min)
- **MAPE clipeado** a 999% maximo

### 2.3 Parametros regionales (modelado por estado)
- `fourier_order_regional: 3` (vs 5 nacional)
- `n_changepoints_regional: 12` (vs 25 default Prophet)

### 2.4 Grids de hiperparametros

| Padecimiento | Combos | seasonality_mode | changepoint_prior_scale | seasonality_prior_scale |
|---|---|---|---|---|
| Alzheimer | 4 | multiplicative | 0.01, 0.03 | 0.1, 0.5 |
| Depresion | 24 | additive, multiplicative | 0.01, 0.03, 0.05 | 0.05, 0.1, 0.5, 1.0 |
| Parkinson | 24 | multiplicative, additive | 0.01, 0.03, 0.05, 0.07 | 0.1, 0.5, 1.0 |

### 2.5 Periodos atipicos (holidays Prophet)
- **Pandemia COVID-19:** 2020-03-23, ventana 913 dias (~2.5 anos)
- **Atipico 2016:** 2016-05-16, ventana 182 dias
- **Cambio regimen Tabasco:** 2023-01-09, ventana 365 dias (solo Depresion)

### 2.6 Clasificacion de confianza
- Series con promedio < 1 caso/semana → `confianza: "insuficiente"`
- Se entrenan con params default (skip CV) para que exista .pkl para Tableau
- 84/297 modelos son insuficientes (28%)

---

## 3. Resultados por Padecimiento

### 3.1 Alzheimer

**Nacional (3 modelos):**

| Sexo | RMSE | MAE | MAPE | seasonality_mode | cp | sp |
|---|---|---|---|---|---|---|
| hombres | 0.0041 | 0.0033 | 30.9% | multiplicative | 0.01 | 0.1 |
| mujeres | 0.0065 | 0.0052 | 32.0% | multiplicative | 0.01 | 0.5 |
| total | 0.0095 | 0.0078 | 27.9% | multiplicative | 0.01 | 0.1 |

**Regional (32 normal / 64 insuficiente):**
- RMSE: min=0.0085 (Mexico-hombres) | mediana=0.0289 | max=0.0741 (Nayarit-total)
- Solo 3 modelos regionales tienen MAPE confiable (<999%)
- **100% multiplicative** en todos los modelos normales
- HP dominantes: `cp=0.01` (56%) y `sp=0.1/0.5` (50/50)

**Insuficientes (64 modelos, 25 estados):**
Los estados con 0 o menos de 1 caso/semana promedio:
- BCS: 0.00 casos/sem (cero total)
- Tlaxcala: 0.18, Zacatecas: 0.19, Quintana Roo: 0.28
- Solo 7 estados tienen suficientes datos para al menos 1 modelo de Alzheimer

**Hallazgo:** Alzheimer es demasiado infrecuente a nivel estatal para modelar individualmente. Considerar modelado por region INEGI (4 regiones) para agregar suficiente volumen.

**Tiempos:** CV total 497s (~8 min), promedio 14.2s/modelo. Sin Newton fallbacks.

### 3.2 Depresion

**Nacional (3 modelos):**

| Sexo | RMSE | MAE | MAPE | seasonality_mode | cp | sp |
|---|---|---|---|---|---|---|
| hombres | 0.0660 | 0.0502 | 12.9% | additive | 0.03 | 0.5 |
| mujeres | 0.1224 | 0.0940 | 11.5% | additive | 0.05 | 0.5 |
| total | 0.1335 | 0.1004 | 10.1% | multiplicative | 0.03 | 0.1 |

**Regional (96 normal / 0 insuficiente):**
- RMSE: min=0.0749 (Chiapas-hombres) | mediana=0.2017 | max=0.3926 (Nayarit-total)
- MAPE: min=11.7% (CDMX-total) | mediana=25.3% | max=523.0% (Tlaxcala-hombres)
- **100% cobertura** — Depresion tiene volumen en todos los estados
- HP equilibrados: multiplicative 51% vs additive 49%
- `cp=0.01` dominante (54%), `sp` distribuido uniformemente

**Top 5 mejores RMSE regionales:**

| Estado | Sexo | RMSE | MAPE |
|---|---|---|---|
| Chiapas | hombres | 0.0749 | 176.5% |
| Veracruz | hombres | 0.0844 | 26.8% |
| Guanajuato | hombres | 0.0881 | 28.0% |
| Queretaro | hombres | 0.0883 | 391.5% |
| Hidalgo | hombres | 0.0971 | 387.3% |

**Top 5 peores RMSE regionales:**

| Estado | Sexo | RMSE | MAPE |
|---|---|---|---|
| Nayarit | total | 0.3926 | 21.8% |
| BCS | total | 0.3901 | 29.3% |
| Colima | total | 0.3808 | 19.0% |
| BCS | hombres | 0.3759 | 517.4% |
| Nayarit | mujeres | 0.3695 | 26.5% |

**Problema Newton — Chihuahua:**

| Sexo | CV (seg) | RMSE | HP ganadores |
|---|---|---|---|
| hombres | 121s | 0.2010 | multiplicative, cp=0.03, sp=1.0 |
| mujeres | 1,555s (26 min) | 0.2788 | multiplicative, cp=0.05, sp=0.5 |
| total | 2,319s (39 min) | 0.3056 | additive, cp=0.05, sp=0.5 |

Chihuahua-total consumio 39 min de CV (16% del tiempo total de Depresion). La causa: L-BFGS falla y cae a Newton optimizer (~100-500x mas lento). El timeout de 120s mitiga parcialmente, pero no puede interrumpir un fold ya iniciado.

**Cambio de regimen Tabasco:**
- CV=160s (vs promedio 151s) — no causo problemas de rendimiento
- RMSE=0.2501 (hombres), 0.2994 (mujeres), 0.3337 (total)
- El holiday de cambio de regimen funciona correctamente

**Tiempos:** CV total 14,993s (~4.2h), promedio 151s/modelo, max 2,319s (Chihuahua-total).

### 3.3 Parkinson

**Nacional (3 modelos):**

| Sexo | RMSE | MAE | MAPE | seasonality_mode | cp | sp |
|---|---|---|---|---|---|---|
| hombres | 0.0168 | 0.0132 | 23.5% | multiplicative | 0.01 | 1.0 |
| mujeres | 0.0171 | 0.0134 | 28.5% | multiplicative | 0.01 | 1.0 |
| total | 0.0270 | 0.0211 | 20.5% | multiplicative | 0.01 | 0.1 |

**Regional (76 normal / 20 insuficiente):**
- RMSE: min=0.0219 (Guanajuato-mujeres) | mediana=0.0545 | max=0.1956 (Colima-total)
- Solo 26/76 modelos tienen MAPE confiable; mediana 385% — MAPE no es util aqui
- **76% multiplicative**, 24% additive
- `cp=0.01` dominante (50%), luego `cp=0.07` (18%)

**Insuficientes (20 modelos, 9 estados):**
- BCS: 3 modelos (0.61 casos/sem)
- Queretaro: 3 modelos (0.65 casos/sem)
- Zacatecas: 3 modelos (0.51 casos/sem)
- Aguascalientes, Campeche, Nayarit, Quintana Roo, Tlaxcala, Tabasco: 1-2 modelos

**Top 5 peores RMSE regionales:**

| Estado | Sexo | RMSE | MAPE |
|---|---|---|---|
| Colima | total | 0.1956 | 38.2% |
| Colima | mujeres | 0.1614 | 999.0% |
| Colima | hombres | 0.1557 | 382.9% |
| Durango | total | 0.1551 | 382.1% |
| Puebla | total | 0.1527 | 999.0% |

Colima domina los peores modelos por su baja poblacion (731K) y pocos casos.

**Tiempos:** CV total 8,142s (~2.3h), promedio 103s/modelo, max 227s (Yucatan-total). Sin Newton extremos.

---

## 4. Distribucion de Hiperparametros Ganadores

### 4.1 seasonality_mode

| Padecimiento | multiplicative | additive |
|---|---|---|
| Alzheimer | **100%** | 0% |
| Depresion | 51% | 49% |
| Parkinson | **76%** | 24% |

**Hallazgo:** Multiplicative domina en Alzheimer y Parkinson. Depresion es la unica donde additive compite (series mas estables post-normalizacion).

### 4.2 changepoint_prior_scale

| Padecimiento | 0.01 | 0.03 | 0.05 | 0.07 |
|---|---|---|---|---|
| Alzheimer | 56% | 44% | — | — |
| Depresion | **54%** | 19% | 27% | — |
| Parkinson | **50%** | 18% | 13% | 18% |

**Hallazgo:** `cp=0.01` es el ganador consistente en todos los padecimientos. Valores mas altos (0.05+) causan Newton fallbacks sin mejorar RMSE significativamente.

### 4.3 seasonality_prior_scale

| Padecimiento | 0.05 | 0.1 | 0.5 | 1.0 |
|---|---|---|---|---|
| Alzheimer | — | 50% | 50% | — |
| Depresion | 24% | 24% | 29% | 23% |
| Parkinson | — | 39% | 37% | 24% |

**Hallazgo:** Distribucion relativamente uniforme. No hay un valor dominante claro.

---

## 5. Problemas Identificados

### 5.1 MAPE no confiable en series de baja incidencia
- **Causa:** Log-transform + valores cercanos a 0 → MAPE explota (division por ~0)
- **Afectados:** 29 modelos Alzheimer + 50 Parkinson = 79 modelos con `mape_confiable: False`
- **Mitigacion:** MAPE clipeado a 999%. Columna `mape_confiable` en CSV para filtrar
- **Recomendacion:** Usar RMSE y MAE como metricas principales para Alzheimer y Parkinson

### 5.2 Newton fallbacks en Chihuahua-Depresion
- **Causa:** Ciertas combinaciones de HP (especialmente `cp=0.05 + multiplicative`) causan que L-BFGS no converja, cayendo a Newton (~100-500x mas lento)
- **Impacto:** Chihuahua-total tardo 2,319s (39 min) vs promedio 151s
- **Mitigacion:** Timeout de 120s/combo descarta combos lentas. No puede interrumpir fold en ejecucion
- **Mejora futura:** Considerar eliminar `cp=0.05` del grid de Depresion (nunca gana en nacional, pero si en ~27% de regionales)

### 5.3 Alzheimer: exceso de modelos insuficientes
- **64/96 modelos regionales** (67%) son insuficientes
- Solo 7 de 32 estados tienen suficientes casos para los 3 sexos
- **Recomendacion:** Evaluar modelado por region INEGI (4 regiones) en vez de por estado para Alzheimer

### 5.4 MAPE alto en hombres (Depresion)
- Varios estados tienen MAPE > 100% solo para hombres: Chiapas (176%), Guerrero (395%), Hidalgo (387%), Puebla (393%), Queretaro (391%)
- **Causa:** Incidencia masculina de depresion es ~3-4x menor que femenina; el MAPE se infla por denominador chico
- El RMSE de estos modelos es bueno (0.07-0.14), confirmando que el ajuste es razonable

### 5.5 Warnings de CSV de entrenamiento faltante
- 3 modelos nacionales de Parkinson no tienen CSV sidecar (`Prophet_Parkinson_Nacional_*.csv`)
- **Causa:** Los nacionales de la corrida anterior ya existian; el script no regenero el CSV
- **Impacto:** Menor — el predict funciona sin el CSV si no necesita desnormalizar

---

## 6. Estructura del CSV de Resultados

Un CSV por padecimiento: `models/{Padecimiento}/Prophet_{Padecimiento}_completo.csv`

| Columna | Tipo | Descripcion |
|---|---|---|
| `padecimiento` | str | Alzheimer, Depresion, Parkinson |
| `sexo` | str | incrementos_hombres / incrementos_mujeres / incrementos_total |
| `rmse` | float/null | RMSE de CV (null si insuficiente) |
| `mae` | float/null | MAE de CV |
| `mape` | float/null | MAPE de CV, clipeado a 999% max |
| `mape_confiable` | bool | False si MAPE fue clipeado a 999% |
| `seasonality_mode` | str | additive / multiplicative |
| `changepoint_prior_scale` | float | HP ganador de CV |
| `seasonality_prior_scale` | float | HP ganador de CV |
| `nivel` | str | "nacional" / "regional" |
| `confianza` | str | "normal" / "insuficiente" |
| `promedio_semanal` | float | Promedio casos/semana (conteo crudo, antes de transformaciones) |
| `tiempo_cv_seg` | float | Segundos en cross-validation |
| `tiempo_train_seg` | float | Segundos en entrenamiento final |
| `tiempo_total_seg` | float | Total segundos |
| `Entidad` | str | Nombre del estado (solo regionales) |
| `poblacion` | int | Poblacion usada para normalizar |
| `normalizado` | bool | True (siempre con tasa por 100K) |
| `archivo_modelo` | str | Nombre del .pkl generado |

---

## 7. Archivos Generados por Modelo

Por cada modelo se generan en `models/{Padecimiento}/`:
- **`.pkl`** — Modelo Prophet serializado
- **`.csv`** — Datos de entrenamiento (ds, y) usados para el fit

Total: ~594 archivos (297 .pkl + 297 .csv), ~109 MB en S3.

---

## 8. Tiempos de Entrenamiento

| Padecimiento | CV total | CV promedio | CV max | Train total | Total wall |
|---|---|---|---|---|---|
| Alzheimer | 497s (8 min) | 14.2s | 17.8s | 32s | ~1 min |
| Depresion | 14,993s (4.2h) | 151.4s | 2,318.7s | 119s | ~40 min |
| Parkinson | 8,142s (2.3h) | 103.1s | 227.2s | 75s | ~16 min |

Nota: El wall time es mucho menor que CV total gracias al paralelismo (11 cores).

---

## 9. Infraestructura de Entrenamiento

- **Paralelismo:** joblib.Parallel con backend loky, n_jobs=-2 (todos los cores - 1)
- **Compatibilidad cross-platform:** Imports locales en `entrenar()` para evitar PicklingError de OmegaConf/Loguru con cloudpickle
- **Progreso:** `[i/total] %` visible en ambos modos (paralelo y secuencial)
- **Flag solo_nacional:** `params.yaml → solo_nacional: True` para pruebas rapidas (solo 9 modelos nacionales)

---

## 10. Recomendaciones para v5

1. **Alzheimer por region INEGI:** Modelar las 4 regiones en vez de 32 estados para agregar volumen
2. **Reducir grid de Depresion:** Eliminar `cp=0.05` reduciria combos de 24 a 16 y evitaria la mayoria de Newton fallbacks
3. **Timeout a nivel de fold:** Implementar timeout dentro del fold (no solo por combo) para cortar Newton inmediatamente
4. **Metricas alternativas al MAPE:** Usar sMAPE o MASE para series de baja incidencia
5. **Cambios de regimen adicionales:** Evaluar Nayarit y Colima como step functions (no holidays) en Prophet
6. **Dashboard Tableau:** Filtrar modelos insuficientes o mostrarlos con banner de advertencia
