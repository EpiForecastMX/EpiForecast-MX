# Reporte de Hallazgos — Modelado Prophet v5

**Fecha:** 2026-02-21
**Modelos entrenados:** 297 (3 padecimientos x 33 entidades x 3 sexos)
**Tiempo total:** 44.5 minutos (n_jobs=-2, joblib loky)
**Horizonte de prediccion:** 120 semanas

---

## 1. Resumen Ejecutivo

| Padecimiento | Total | Normal | Insuficiente | Tiempo | RMSE medio |
|---|---|---|---|---|---|
| **Alzheimer** | 99 | 64 | 35 | ~2 min | 0.033 |
| **Depresion** | 99 | 99 | 0 | ~28 min | 0.206 |
| **Parkinson** | 99 | 94 | 5 | ~14 min | 0.064 |
| **Total** | **297** | **257** | **40** | **44.5 min** | — |

### Comparacion v4 → v5

| Metrica | v4 | v5 | Cambio |
|---|---|---|---|
| Modelos normales | 213 | **257** | +44 modelos |
| Modelos insuficientes | 84 | **40** | -52% |
| Tiempo total | 57 min | **44.5 min** | -22% |
| Chihuahua-Dep CV max | 2,319s (39 min) | **266s (4.4 min)** | -89% |
| Combos totales | 52 | 48 | -8% |

---

## 2. Configuracion del Entrenamiento (v5)

### 2.1 Transformaciones del target
1. **Normalizacion a tasa por 100K hab.** — iguala escala entre estados
2. **Log-transform:** `y = log(1 + tasa)` — estabiliza varianza
3. **Prophet entrena sobre espacio log-tasa**

### 2.2 Cross-validation
- **4 folds** temporales (TimeSeriesSplit), test_size=53 semanas
- **Pesos progresivos:** `[0.5, 0.75, 1.0, 1.25]` — prioriza folds recientes
- **Timeout por combo:** 90s max por combinacion de HP (v4: 120s)
- **Timeout por fold:** 35s max por fold individual (nuevo en v5)
- **MAPE clipeado** a 999% maximo

### 2.3 Proteccion anti-Newton (3 capas, nuevo en v5)

1. **Ordenar combos por cp descendente** — cp alto (0.05) converge rapido con L-BFGS, cp bajo (0.01) es donde Newton aparece
2. **Budget por fold (35s)** — si UN fold tarda >35s, es Newton seguro → skip combo inmediatamente con `ThreadPoolExecutor`
3. **Deteccion Newton-prone** — si un combo hizo timeout, skip combos con cp estrictamente menor (cp < umbral). Si Newton aparecio en cp=0.03, cp=0.01 sera peor
4. **Fallback total** — si TODOS los combos hacen timeout, usar params default con cp mas alto (evita crash)

### 2.4 Parametros regionales (modelado por estado)
- `fourier_order_regional: 3` (vs 5 nacional)
- `n_changepoints_regional: 12` (vs 25 default Prophet)

### 2.5 Grids de hiperparametros v5

| Padecimiento | Combos | seasonality_mode | changepoint_prior_scale | seasonality_prior_scale |
|---|---|---|---|---|
| Alzheimer | 6 | multiplicative | 0.01, 0.03 | **0.05**, 0.1, 0.5 |
| Depresion | 24 | additive, multiplicative | 0.01, 0.03, 0.05 | **0.025**, 0.05, 0.1, 0.5 |
| Parkinson | 18 | multiplicative, additive | 0.03, **0.04**, 0.05 | 0.1, 0.5, 1.0 |

**Cambios v4 → v5:**
- Alzheimer: +sp=0.05 (patron exitoso de Depresion)
- Depresion: sp=1.0 eliminado + sp=0.025 explorado
- Parkinson: cp=0.01 (Newton-prone) y cp=0.07 (nunca gana) eliminados + cp=0.04 interpolado

### 2.6 Periodos atipicos (holidays Prophet)
- **Pandemia COVID-19:** 2020-03-23, ventana 913 dias (~2.5 anos)
- **Atipico 2016:** 2016-05-16, ventana 182 dias
- **Cambio regimen Tabasco:** 2023-01-09, ventana 365 dias (solo Depresion)

### 2.7 Clasificacion de confianza
- Series con promedio < **0.5** casos/semana → `confianza: "insuficiente"` (v4: 1.0)
- Se entrenan con params default (skip CV) para que exista .pkl para Tableau
- **40/297 modelos son insuficientes (13%)** — v4 era 84 (28%)

---

## 3. Resultados por Padecimiento

### 3.1 Alzheimer

**Nacional (3 modelos):**

| Sexo | RMSE | MAE | MAPE | seasonality_mode | cp | sp |
|---|---|---|---|---|---|---|
| hombres | 0.0041 | 0.0033 | 30.9% | multiplicative | 0.01 | 0.1 |
| mujeres | 0.0065 | 0.0052 | 32.0% | multiplicative | 0.01 | 0.5 |
| total | 0.0095 | 0.0078 | 27.9% | multiplicative | 0.01 | 0.1 |

**Regional (61 normal / 35 insuficiente):**
- RMSE: min=0.0085 | media=0.0334 | max=0.1564
- **100% multiplicative** en todos los modelos normales
- HP dominantes: `cp=0.01` (52%) y `cp=0.03` (48%), `sp=0.05` lidera (41%)
- **sp=0.05 (nuevo v5) es el ganador #1** — valida la exploracion

**Impacto del umbral 0.5:** Recupero 29 modelos que eran insuficientes con umbral 1.0 (v4: 64 insuf → v5: 35 insuf)

**Tiempos:** CV promedio 22.6s, max 29.2s. Sin Newton fallbacks.

### 3.2 Depresion

**Nacional (3 modelos):**

| Sexo | RMSE | MAE | MAPE | seasonality_mode | cp | sp |
|---|---|---|---|---|---|---|
| hombres | 0.0660 | 0.0502 | 12.9% | additive | 0.03 | 0.5 |
| mujeres | 0.1224 | 0.0940 | 11.5% | additive | 0.05 | 0.5 |
| total | 0.1335 | 0.1004 | 10.1% | multiplicative | 0.03 | 0.1 |

**Regional (96 normal / 0 insuficiente):**
- RMSE: min=0.066 | media=0.206 | max=0.392
- **100% cobertura** — Depresion tiene volumen en todos los estados
- HP equilibrados: additive 53% vs multiplicative 47%
- **sp=0.025 (nuevo v5) es el ganador #1 (29/99)** — gran exito de exploracion
- `cp=0.01` dominante (52%)

**Impacto anti-Newton en Chihuahua:**

| Sexo | v4 CV | v5 CV | Ahorro | RMSE |
|---|---|---|---|---|
| hombres | 121s | **151s** | — | 0.204 |
| mujeres | 1,555s | **216s** | -86% | 0.279 |
| total | 2,319s | **260s** | -89% | 0.306 |

El sistema detecto Newton en fold 1 (>35s), cortó la combo y skipeo cp=0.03/0.01. Encontro RMSE validos con cp=0.05 que pasaron.

**Tiempos:** CV promedio 177s, max 266s (v4 max: 2,319s).

### 3.3 Parkinson

**Nacional (3 modelos):**

| Sexo | RMSE | MAE | MAPE | seasonality_mode | cp | sp |
|---|---|---|---|---|---|---|
| hombres | 0.0184 | 0.0143 | — | multiplicative | 0.04 | 0.5 |
| mujeres | 0.0194 | 0.0155 | — | additive | 0.03 | 0.1 |
| total | 0.0332 | 0.0271 | 28.6% | additive | 0.04 | 0.1 |

**Regional (91 normal / 5 insuficiente):**
- RMSE: min=0.018 | media=0.064 | max=0.196
- **71% multiplicative**, 29% additive
- **cp=0.03 dominante (45%)**, cp=0.05 (35%), **cp=0.04 (nuevo v5) gana 20%**
- `sp=0.1` dominante (43%)

**Impacto del umbral 0.5:** Recupero 15 modelos (v4: 20 insuf → v5: 5 insuf)
**cp=0.04 (nuevo v5) gana en 19 modelos** — valida la interpolacion

**Tiempos:** CV promedio 92.6s, max 144.9s. Sin Newton extremos.

---

## 4. Distribucion de Hiperparametros Ganadores (v5)

### 4.1 seasonality_mode

| Padecimiento | multiplicative | additive |
|---|---|---|
| Alzheimer | **100%** | 0% |
| Depresion | 47% | **53%** |
| Parkinson | **71%** | 29% |

### 4.2 changepoint_prior_scale

| Padecimiento | 0.01 | 0.03 | 0.04 | 0.05 |
|---|---|---|---|---|
| Alzheimer | **52%** | 48% | — | — |
| Depresion | **52%** | 20% | — | 28% |
| Parkinson | — | **45%** | 20% | 35% |

### 4.3 seasonality_prior_scale

| Padecimiento | 0.025 | 0.05 | 0.1 | 0.5 | 1.0 |
|---|---|---|---|---|---|
| Alzheimer | — | **41%** | 27% | 33% | — |
| Depresion | **29%** | 21% | 21% | 28% | — |
| Parkinson | — | — | **43%** | 31% | 27% |

**Hallazgo clave v5:** Los nuevos valores explorados (sp=0.025, sp=0.05, cp=0.04) son ganadores en sus categorias. La exploracion fue exitosa.

---

## 5. Problemas Identificados y Estado

### 5.1 MAPE no confiable en series de baja incidencia
- **Estado:** Persiste. Usar RMSE/MAE como metricas principales para Alzheimer y Parkinson
- Columna `mape_confiable` en CSV para filtrar

### 5.2 Newton fallbacks en Chihuahua-Depresion
- **Estado: RESUELTO** con proteccion anti-Newton de 3 capas
- v4: 39 min → v5: 4.4 min (-89%)
- No mas crashes por `best_param = None`

### 5.3 Alzheimer: modelos insuficientes
- **Estado: MEJORADO** — umbral 0.5 recupero 29 modelos (v4: 64 insuf → v5: 35 insuf)
- Aun hay 35 insuficientes (12 estados). Considerar modelado por region INEGI para estos

### 5.4 Warnings de CSV de entrenamiento faltante
- 3 modelos nacionales de Parkinson sin CSV sidecar
- **Impacto:** Menor — predict funciona sin ellos

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
| `promedio_semanal` | float | Promedio casos/semana (conteo crudo) |
| `tiempo_cv_seg` | float | Segundos en cross-validation |
| `tiempo_train_seg` | float | Segundos en entrenamiento final |
| `tiempo_total_seg` | float | Total segundos |
| `Entidad` | str | Nombre del estado (solo regionales) |
| `poblacion` | int | Poblacion usada para normalizar |
| `normalizado` | bool | True (siempre con tasa por 100K) |
| `archivo_modelo` | str | Nombre del .pkl generado |

---

## 7. Tiempos de Entrenamiento

| Padecimiento | CV promedio | CV max | Wall time |
|---|---|---|---|
| Alzheimer | 22.6s | 29.2s | ~2 min |
| Depresion | 177.1s | 265.6s | ~28 min |
| Parkinson | 92.6s | 144.9s | ~14 min |
| **Total** | — | — | **44.5 min** |

vs v4: 57 min → 44.5 min (-22%). El ahorro principal viene de Chihuahua anti-Newton.

---

## 8. Infraestructura

- **Paralelismo:** joblib.Parallel con backend loky, n_jobs=-2
- **Anti-Newton:** 3 capas (sort cp desc, fold timeout 35s, Newton-prone threshold)
- **Compatibilidad cross-platform:** Imports locales en `entrenar()` para cloudpickle
- **Progreso:** `[i/total] %` visible en paralelo y secuencial
- **Versionado:** DVC + S3 para modelos (.pkl) y forecast (.csv)

---

## 9. Changelog v4 → v5

| Cambio | Detalle | Impacto |
|---|---|---|
| Grids v5 | 52 → 48 combos, nuevos sp/cp | sp=0.025 y cp=0.04 son ganadores |
| Anti-Newton 3 capas | Sort + fold timeout + threshold | Chihuahua 39 min → 4 min |
| Umbral 0.5 | 1.0 → 0.5 casos/semana | +44 modelos normales |
| Timeouts agresivos | combo: 120→90s, fold: 45→35s | Deteccion Newton mas rapida |
| Fallback Newton | Default params si todos timeout | Evita crash TypeError |
| Threshold estricto | `<=` → `<` | Prueba otros combos al mismo cp |
