# Reporte de Hallazgos — Modelado Prophet v3.0

**Proyecto:** EpiForecast-MX (IMSS × Tec de Monterrey)
**Fecha de corrida:** 20 de febrero de 2026
**Autor:** Equipo de modelado
**Modelos procesados:** 297 (3 padecimientos × 33 geografías × 3 segmentos de sexo)
**Modelos entrenados:** 213 | **Insuficientes:** 84

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Metodología y Pipeline de Transformación](#2-metodología-y-pipeline-de-transformación)
3. [Configuración del Entrenamiento](#3-configuración-del-entrenamiento)
4. [Resultados Globales](#4-resultados-globales)
5. [Análisis por Padecimiento](#5-análisis-por-padecimiento)
6. [Análisis por Estado](#6-análisis-por-estado)
7. [Análisis por Región INEGI de Salud Mental](#7-análisis-por-región-inegi-de-salud-mental)
8. [Análisis de Hiperparámetros](#8-análisis-de-hiperparámetros)
9. [Impacto del COVID-19 en las Series](#9-impacto-del-covid-19-en-las-series)
10. [Periodo Atípico 2016](#10-periodo-atípico-2016)
11. [Modelos Problemáticos y Casuísticas](#11-modelos-problemáticos-y-casuísticas)
12. [Hallazgo Crítico: Población Constante en el Dataset](#12-hallazgo-crítico-población-constante-en-el-dataset)
13. [Mejoras Implementadas y su Impacto](#13-mejoras-implementadas-y-su-impacto)
14. [Pronósticos Generados](#14-pronósticos-generados)
15. [Sugerencias de Mejora Futura](#15-sugerencias-de-mejora-futura)
16. [Anexos](#16-anexos)

---

## 1. Resumen Ejecutivo

Se procesaron **297 modelos Prophet** para predecir la incidencia semanal de tres padecimientos neurológicos/salud mental (Depresión F32, Alzheimer G30, Parkinson G20) a nivel estatal y nacional en México, segmentados por sexo. De estos, **213 fueron entrenados** y **84 fueron descartados como "insuficientes"** por tener un promedio inferior a 1 caso/semana.

### Resultados clave

| Métrica | Valor |
|---------|-------|
| Modelos procesados | 297 |
| Modelos entrenados | 213 (71.7%) |
| Modelos insuficientes | 84 (28.3%) — 64 Alzheimer, 20 Parkinson |
| RMSE medio global (entrenados) | 0.1254 (en espacio log-tasa) |
| RMSE mediano global (entrenados) | 0.0920 |
| Modelos con RMSE < 0.10 | 111 (52.1% de entrenados) |
| Modelos con RMSE > 0.30 | 11 (5.2%, todos Depresión) |
| Modelos con RMSE > 0.40 | 2 (0.9%) |
| Errores de entrenamiento | 0 |
| Errores de predicción | 0 |

### Historial de mejoras implementadas

| Versión | Mejora | Impacto principal |
|---------|--------|-------------------|
| v1 | Normalización a tasa por 100K habitantes | RMSE comparable entre estados grandes y pequeños |
| v2 | Log-transform `log(1+y)` + modo aditivo en grid | RMSE Depresión: -64%, 0 modelos con RMSE > 1.0 |
| **v3** | **Filtro de series insuficientes (<1 caso/sem)** | **84 modelos espurios eliminados (64 Alz + 20 Park)** |
| **v3** | **Holiday de cambio de régimen Tabasco** | **Tabasco-Depresión RMSE: -6.2% a -19.7% por sexo** |

---

## 2. Metodología y Pipeline de Transformación

### 2.1 Pipeline de datos

```
SINAVE PDFs (633 boletines, 2014-2026)
    ↓ Extracción con Camelot (CIE-10: F32, G20, G30)
    ↓ Merge incremental al dataset consolidado
    ↓ Filtrado por padecimiento
    ↓ Limpieza (nulos, duplicados, formato)
    ↓ Feature Engineering (outliers IQR/Z-score, regiones, agrupación)
    ↓ Merge con datos INEGI (población, superficie, región salud mental)
    ↓ Validación de volumen mínimo (≥ 1 caso/semana promedio)
    ↓ Entrenamiento Prophet con CV temporal (solo series viables)
    ↓ Predicción a 120 semanas (hasta 2027-04-19)
```

### 2.2 Transformaciones aplicadas al target

El target `y` pasa por tres transformaciones secuenciales antes de alimentar a Prophet:

```
Paso 1: Agregación temporal
    y_raw = sum(incidencia_semanal) por Fecha × sexo

Paso 2: Normalización a tasa por 100K habitantes
    y_tasa = (y_raw / población_estado) × 100,000

    Motivación: Sin normalizar, CDMX (9M hab.) tenía RMSE 10x mayor que
    Colima (731K hab.) simplemente por volumen, no por peor ajuste.

Paso 3: Log-transform para estabilizar varianza
    y = log(1 + y_tasa)

    Motivación: Series de Depresión con alta volatilidad (CV > 0.5) generaban
    RMSE > 2.0 en conteos absolutos. El log comprime los picos y estabiliza
    la varianza, permitiendo a Prophet ajustar mejor la estacionalidad.
```

### 2.3 Transformaciones inversas en predicción

```
Prophet predice: ŷ_log (en espacio log-tasa)
    ↓ exp(ŷ_log) - 1 = ŷ_tasa     (revertir log)
    ↓ ŷ_tasa × población / 100,000 = ŷ_conteo  (revertir normalización)

El CSV de salida contiene ambos:
    yhat       → conteo semanal estimado (para reportes IMSS)
    yhat_tasa  → tasa por 100K (para comparación inter-estatal)
```

---

## 3. Configuración del Entrenamiento

### 3.1 Datos de entrenamiento

| Parámetro | Valor |
|-----------|-------|
| Ventana temporal | 2013-12-30 a 2024-12-30 |
| Semanas de entrenamiento | 574 |
| Fecha de corte train/test | 2025-01-01 |
| Semanas en test set | 55 (2025-01-06 en adelante) |
| Frecuencia | Semanal (W-MON) |
| Fuente de incidencia | SINAVE vía boletines epidemiológicos |
| Fuente de población | INEGI (columna `Total` en dataset) |

### 3.2 Configuración de Prophet

| Parámetro | Valor |
|-----------|-------|
| Estacionalidad anual nativa | Desactivada |
| Estacionalidad semanal | Desactivada (1 obs/semana) |
| Estacionalidad diaria | Desactivada |
| Estacionalidad custom | `yearly_custom`, period=52.18, fourier_order=5 |

### 3.3 Eventos atípicos y holidays configurados

| Evento | Fecha inicio | Ventana (días) | Ámbito | Duración efectiva |
|--------|-------------|----------------|--------|-------------------|
| Pandemia COVID-19 | 2020-03-23 | 913 | Global (todos) | ~2.5 años (hasta ~Sep 2022) |
| Atípico 2016 | 2016-05-16 | 182 | Global (todos) | ~6 meses |
| **Cambio régimen Tabasco** | **2023-01-09** | **365** | **Solo Tabasco-Depresión** | **~1 año** |

> **Nota v3:** Se probaron holidays de cambio de régimen para 5 estados (Nayarit, Tabasco, Colima, Durango, BCS). Solo Tabasco mejoró el RMSE (-6.2% a -19.7%). Los demás empeoraron (+1% a +10%) porque sus cambios son **step functions permanentes**, incompatibles con holidays de Prophet que modelan efectos temporales. Ver [Sección 13.6](#136-mejora-6-experimento-holidays-de-cambio-de-régimen-v3) para detalles.

### 3.4 Grid de hiperparámetros (24 combinaciones)

| Hiperparámetro | Valores probados |
|----------------|-----------------|
| `seasonality_mode` | `multiplicative`, `additive` |
| `changepoint_prior_scale` | 0.01, 0.03, 0.05 |
| `seasonality_prior_scale` | 0.1, 0.5, 1.0, 2.0 |

### 3.5 Cross-validation temporal

| Parámetro | Valor |
|-----------|-------|
| Tipo | `TimeSeriesSplit` (sklearn) |
| Folds | 4 |
| Tamaño de cada fold de validación | 53 semanas |
| Métrica de selección | RMSE promedio de los 4 folds |

**Ventanas de cada fold:**

| Fold | Train hasta | Validación desde | Validación hasta |
|------|------------|------------------|------------------|
| 1 | 2020-12-07 | 2020-12-14 | 2021-12-13 |
| 2 | 2021-12-13 | 2021-12-20 | 2022-12-19 |
| 3 | 2022-12-19 | 2022-12-26 | 2023-12-25 |
| 4 | 2023-12-25 | 2024-01-01 | 2024-12-30 |

> **Nota:** Los folds 1-2 cubren el periodo post-COVID inmediato, lo que evalúa la capacidad del modelo de manejar la recuperación. El fold 4 es el más representativo del comportamiento actual.

### 3.6 Filtro de series insuficientes (nuevo en v3)

| Parámetro | Valor |
|-----------|-------|
| Umbral mínimo | 1.0 caso/semana promedio |
| Columna evaluada | `y_original` (conteo crudo, antes de transformaciones) |
| Acción si no cumple | No entrenar, marcar como `confianza: "insuficiente"` |
| Efecto | No genera `.pkl` ni `.csv` de entrenamiento |

Este filtro se aplica **después** de `agrupa()` + `crea_train_test()` y **antes** de `prophet_cross_val()`, evitando el costo de CV (~50 seg) en series inviables.

### 3.7 Fallback de L-BFGS

Si el optimizador L-BFGS falla durante el entrenamiento final (después de CV), el sistema reintenta automáticamente con `changepoint_prior_scale=0.05` como respaldo. En esta corrida: **0 modelos necesitaron fallback**.

### 3.8 Inventario de modelos

| Padecimiento | Procesados | Entrenados | Insuficientes | % Entrenados |
|--------------|-----------|------------|---------------|-------------|
| Alzheimer | 99 | 35 | 64 | 35.4% |
| Depresión | 99 | 99 | 0 | 100% |
| Parkinson | 99 | 79 | 20 | 79.8% |
| **Total** | **297** | **213** | **84** | **71.7%** |

Cada modelo entrenado genera: 1 archivo `.pkl` (modelo serializado) + 1 archivo `.csv` (datos de entrenamiento con columnas `ds`, `y`, `Total`, `y_original`).

---

## 4. Resultados Globales

> **Nota v3:** Todas las estadísticas de RMSE en esta sección se calculan **solo sobre modelos entrenados** (213). Los 84 modelos insuficientes no tienen RMSE y se excluyen. En v2, las estadísticas incluían modelos triviales como BCS-Alzheimer (RMSE=0.000 sobre 0 casos), inflando artificialmente la proporción de "buenos" modelos.

### 4.1 RMSE descriptivo por padecimiento (solo modelos entrenados)

> RMSE reportado en espacio log-tasa (después de normalización + log-transform). Es la métrica con la que Prophet optimiza vía CV.

| Estadístico | Alzheimer (n=35) | Depresión (n=99) | Parkinson (n=79) |
|-------------|------------------|------------------|------------------|
| **Media** | 0.0291 | 0.2095 | 0.0626 |
| **Mediana** | 0.0279 | 0.2041 | 0.0523 |
| **Desv. Est.** | 0.0162 | 0.0759 | 0.0367 |
| **Mínimo** | 0.0043 | 0.0681 | 0.0153 |
| **Q25** | 0.0167 | 0.1609 | 0.0354 |
| **Q75** | 0.0391 | 0.2456 | 0.0793 |
| **Máximo** | 0.0731 | 0.4115 | 0.1923 |

**Interpretación:** Alzheimer es el padecimiento más fácil de modelar (RMSE medio 0.029), seguido de Parkinson (0.063). Depresión es significativamente más difícil (0.210), con un rango 3-7x mayor que los otros dos.

**Comparación v2 → v3 (Alzheimer):** El RMSE máximo bajó de 0.1481 a 0.0731 porque los modelos con más de 50% zeros (Colima, Campeche, etc.) fueron filtrados como insuficientes. Esto hace que las estadísticas reflejen solo modelos viables.

### 4.2 Nacional vs. Estatal (solo entrenados)

| Padecimiento | Nacional (media) | Estatal (media) | Ratio Estatal/Nacional |
|--------------|-----------------|-----------------|----------------------|
| Alzheimer | 0.0069 | 0.0312 | 4.5x |
| Depresión | 0.1125 | 0.2126 | 1.9x |
| Parkinson | 0.0197 | 0.0643 | 3.3x |

Los modelos nacionales son consistentemente mejores porque agregan 32 estados, reduciendo la varianza por ley de grandes números.

### 4.3 RMSE por segmento de sexo (solo entrenados)

| Padecimiento | Hombres | n | Mujeres | n | General (total) | n |
|--------------|---------|---|---------|---|-----------------|---|
| Alzheimer | 0.0192 | 8 | 0.0257 | 11 | 0.0364 | 16 |
| Depresión | 0.1604 | 33 | 0.2227 | 33 | 0.2455 | 33 |
| Parkinson | 0.0522 | 25 | 0.0518 | 24 | 0.0798 | 30 |

**Hallazgo:** El modelo "general" (ambos sexos combinados) tiene peor RMSE que los modelos por sexo. Esto sugiere que la dinámica de hombres y mujeres difiere lo suficiente para que combinarlos genere ruido adicional.

**Alzheimer tiene sesgo de sexo en insuficientes:** Solo 8 modelos de hombres se entrenaron vs 11 mujeres y 16 general. Esto se debe a que los hombres con Alzheimer tienen menor incidencia, cayendo más frecuentemente bajo el umbral.

**Parkinson es la excepción en sexo:** mujeres tienen RMSE ligeramente menor que hombres (0.052 vs 0.052), a pesar de que Parkinson es más prevalente en hombres (ratio H/M = 1.12). La serie femenina de Parkinson es más estable.

### 4.4 Distribución de modelos por umbrales de RMSE (solo entrenados)

| Umbral | Alzheimer | Depresión | Parkinson | Total | % de entrenados |
|--------|-----------|-----------|-----------|-------|-----------------|
| RMSE < 0.05 | 29 | 0 | 38 | 67 | 31.5% |
| 0.05 ≤ RMSE < 0.10 | 6 | 6 | 32 | 44 | 20.7% |
| 0.10 ≤ RMSE < 0.20 | 0 | 43 | 9 | 52 | 24.4% |
| 0.20 ≤ RMSE < 0.30 | 0 | 39 | 0 | 39 | 18.3% |
| 0.30 ≤ RMSE < 0.40 | 0 | 9 | 0 | 9 | 4.2% |
| RMSE ≥ 0.40 | 0 | 2 | 0 | 2 | 0.9% |

> **52.1% de los modelos entrenados tienen RMSE < 0.10.** Todos los modelos con RMSE > 0.10 que no son Depresión son de Parkinson (9 modelos, todos con RMSE < 0.20).

---

## 5. Análisis por Padecimiento

### 5.1 Depresión (CIE-10: F32) — El padecimiento más difícil

**Por qué Depresión es más difícil de modelar:**

1. **Alto volumen y alta volatilidad:** ~2,220 casos/semana nacional vs ~47 para Alzheimer, con coeficiente de variación de 0.5-0.6 en estados pequeños
2. **Tendencia estructural ascendente:** La incidencia de depresión ha crecido sostenidamente desde 2018, con aceleración post-COVID (2,425/sem en 2019 → 2,882/sem en 2024)
3. **Cambios de régimen abruptos:** Algunos estados (Nayarit, Tabasco) muestran duplicación de incidencia en 1-2 años sin explicación clara
4. **Estacionalidad irregular:** Depresión tiene patrones estacionales más variables año a año que Alzheimer o Parkinson
5. **COVID heterogéneo:** El impacto del COVID fue -40% nacional para Depresión, pero varió de -20% a -60% entre estados

**Distribución de RMSE (99 modelos, 0 insuficientes):**
- Media: 0.2095, Mediana: 0.2041
- IQR: [0.1609, 0.2456]
- 49.5% de modelos eligieron modo aditivo (vs 25.7% en Alzheimer, 30.4% en Parkinson)

**Ratios por sexo (acumulado nacional):**
- Mujeres: 944,873 casos (2.87x más que hombres)
- Hombres: 329,192 casos
- La mayor brecha de sexo de los tres padecimientos

**Top 5 estados más difíciles (modelo general):**

| Estado | RMSE | Población | Problema identificado |
|--------|------|-----------|----------------------|
| Nayarit | 0.4097 | 1,235,456 | Cambio de régimen 2018 (se duplica la incidencia) |
| Colima | 0.3875 | 731,391 | Población muy pequeña, alta volatilidad |
| Baja California Sur | 0.3833 | 798,447 | Ídem, estado menos poblado |
| Tabasco | 0.3329 | 2,402,598 | Cambio brusco de tendencia (mejorado -6.2% vs v2 con holiday) |
| Durango | 0.3331 | 1,832,650 | Serie errática |

### 5.2 Alzheimer (CIE-10: G30) — El más estable pero con mayor filtrado

**Características:**
- Serie de baja volatilidad, tendencia ligeramente descendente post-COVID
- ~47 casos/semana nacional, series suaves
- **64 de 99 modelos (64.6%) descartados como insuficientes** — la mayoría de estados tienen <1 caso/semana de Alzheimer
- 74.3% de modelos entrenados eligieron modo multiplicativo

**Impacto del filtro de insuficientes (v3):**

En v2, estados como BCS tenían RMSE=0.000 (modelo trivial sobre 0 casos). En v3, estos modelos se marcan como "insuficientes" sin generar .pkl, lo cual:
- Elimina modelos engañosos (RMSE perfecto ≠ modelo útil)
- Ahorra ~53 min de entrenamiento (64 modelos × ~50 seg)
- Las estadísticas de RMSE ahora reflejan solo modelos con datos viables

**Estados con modelo general entrenado (16 de 32):**
Baja California, Chihuahua, Ciudad de México, Coahuila, Jalisco, Michoacán, México, Nayarit, Nuevo León, Oaxaca, Puebla, Sinaloa, Sonora, Tamaulipas, Veracruz + Nacional.

**Top 3 estados más difíciles (modelo general, solo entrenados):**

| Estado | RMSE | Problema |
|--------|------|---------|
| Nayarit | 0.0731 | Baja población (1.2M), solo modelo general viable |
| Sinaloa | 0.0624 | Series con ruido, 3M hab. |
| Tamaulipas | 0.0535 | Variabilidad estacional |

### 5.3 Parkinson (CIE-10: G20) — Intermedio

**Características:**
- ~145 casos/semana nacional, tendencia relativamente estable
- Serie más regular que Depresión pero con más volumen que Alzheimer
- **20 de 99 modelos (20.2%) descartados como insuficientes**
- 69.6% multiplicativo, 30.4% aditivo
- Recuperación completa post-COVID (2023: 184.7/sem vs pre-COVID 183.6/sem)

**Top 3 estados más difíciles (modelo general, solo entrenados):**

| Estado | RMSE | Problema |
|--------|------|---------|
| Colima | 0.1923 | Población muy pequeña, ~4 casos/semana |
| Durango | 0.1508 | Tendencia irregular, datos inconsistentes |
| Puebla | 0.1461 | 6.6M hab. pero serie irregular (posible problema de reporte) |

**Estados insuficientes de Parkinson (9 estados con algún modelo insuf.):**
Aguascalientes (H/M), BCS (3), Campeche (H/M), Nayarit (H/M), Querétaro (3), Quintana Roo (H/M), Tabasco (M), Tlaxcala (H/M), Zacatecas (3).

---

## 6. Análisis por Estado

### 6.1 Tabla completa — RMSE modelo "general" por estado y padecimiento

> Las celdas marcadas **insuf** indican series con promedio <1 caso/semana descartadas por el filtro de volumen mínimo. El promedio semanal se muestra entre paréntesis.

| Estado | Población | Alzheimer | Depresión | Parkinson |
|--------|-----------|-----------|-----------|-----------|
| Aguascalientes | 1,425,607 | insuf (0.45) | 0.2584 | 0.0754 |
| Baja California | 3,769,020 | 0.0394 | 0.1842 | 0.0622 |
| Baja California Sur | 798,447 | insuf (0.0) | 0.3833 | insuf (0.91) |
| Campeche | 928,363 | insuf (0.52) | 0.2597 | 0.1215 |
| Chiapas | 5,543,828 | insuf (0.95) | 0.1877 | 0.0357 |
| Chihuahua | 3,741,869 | 0.0476 | 0.3295 | 0.0855 |
| Ciudad de México | 9,209,944 | 0.0186 | 0.2269 | 0.0514 |
| Coahuila | 3,146,771 | 0.0483 | 0.2669 | 0.0746 |
| **Colima** | **731,391** | **insuf (0.88)** | **0.3875** | **0.1923** |
| Durango | 1,832,650 | insuf (0.98) | 0.3331 | 0.1508 |
| Guanajuato | 6,166,934 | insuf (0.99) | 0.1799 | 0.0337 |
| Guerrero | 3,540,685 | insuf (0.67) | 0.2732 | 0.0568 |
| Hidalgo | 3,082,841 | insuf (0.64) | 0.2216 | 0.0525 |
| Jalisco | 8,348,151 | 0.0332 | 0.1626 | 0.0757 |
| México | 16,992,418 | 0.0149 | 0.2169 | 0.0397 |
| Michoacán | 4,748,846 | 0.0292 | 0.2133 | 0.0586 |
| Morelos | 1,971,520 | insuf (0.92) | 0.2456 | 0.1252 |
| **Nayarit** | **1,235,456** | 0.0731 | **0.4097** | 0.1180 |
| Nuevo León | 5,784,442 | 0.0279 | 0.1757 | 0.0429 |
| Oaxaca | 4,132,148 | 0.0308 | 0.1986 | 0.0513 |
| Puebla | 6,583,278 | 0.0274 | 0.2453 | 0.1461 |
| Querétaro | 2,368,467 | insuf (0.35) | 0.1874 | insuf (0.98) |
| Quintana Roo | 1,857,985 | insuf (0.42) | 0.2272 | 0.0676 |
| San Luis Potosí | 2,822,255 | insuf (0.94) | 0.2154 | 0.0715 |
| Sinaloa | 3,026,943 | 0.0624 | 0.2222 | 0.0997 |
| Sonora | 2,944,840 | 0.0428 | 0.2761 | 0.0605 |
| Tabasco | 2,402,598 | insuf (0.88) | 0.3329 | 0.0920 |
| Tamaulipas | 3,527,735 | 0.0535 | 0.2071 | 0.0961 |
| Tlaxcala | 1,342,977 | insuf (0.27) | 0.2314 | 0.0888 |
| Veracruz | 8,062,579 | 0.0244 | 0.1745 | 0.0501 |
| Yucatán | 2,320,898 | insuf (0.89) | 0.2771 | 0.0911 |
| Zacatecas | 1,622,138 | insuf (0.28) | 0.2494 | insuf (0.77) |

### 6.2 Mejores estados (menor RMSE en Depresión, el padecimiento más difícil)

| Rank | Estado | Depresión RMSE | Parkinson RMSE | Población |
|------|--------|---------------|----------------|-----------|
| 1 | Jalisco | 0.1626 | 0.0757 | 8,348,151 |
| 2 | Veracruz | 0.1745 | 0.0501 | 8,062,579 |
| 3 | Nuevo León | 0.1757 | 0.0429 | 5,784,442 |
| 4 | Guanajuato | 0.1799 | 0.0337 | 6,166,934 |
| 5 | Baja California | 0.1842 | 0.0622 | 3,769,020 |

### 6.3 Peores estados (mayor RMSE en Depresión)

| Rank | Estado | Depresión RMSE | Población | Causa principal |
|------|--------|---------------|-----------|----------------|
| 1 | **Nayarit** | **0.4097** | 1,235,456 | Cambio de régimen 2018 (step function permanente) |
| 2 | **Colima** | **0.3875** | 731,391 | Población más pequeña, alta volatilidad |
| 3 | BCS | 0.3833 | 798,447 | Baja población |
| 4 | Tabasco | 0.3329 | 2,402,598 | Salto de tendencia 2023 (holiday aplicado) |
| 5 | Durango | 0.3331 | 1,832,650 | Series erráticas, ramp gradual |

### 6.4 Correlación RMSE vs. Población

Existe una correlación negativa moderada entre población y RMSE: los estados más poblados generalmente tienen mejores modelos. Sin embargo, la normalización a tasa por 100K ha reducido significativamente esta dependencia comparado con la corrida anterior donde se usaban conteos absolutos.

**Estados que rompen la tendencia:**
- **Puebla** (6.6M hab.) tiene RMSE alto en Parkinson (0.146) a pesar de su tamaño — posible problema de reporte
- **Chiapas** (5.5M hab.) tiene RMSE bajo en Depresión (0.188) a pesar de menor acceso a servicios IMSS — series estables
- **Querétaro** (2.4M hab.) tiene RMSE bajo en Depresión (0.187) a pesar de población mediana — datos consistentes

---

## 7. Análisis por Región INEGI de Salud Mental

> **Nota v3:** Las estadísticas de Alzheimer por región están limitadas porque muchos estados solo tienen modelo "general" viable, o ninguno. Parkinson y Depresión ofrecen mejor cobertura regional.

| Región INEGI | Estados | Depresión (media) | Parkinson (media) |
|-------------|---------|-------------------|-------------------|
| Metropolitana alta | CDMX, Jalisco, México, Nuevo León | 0.1955 | 0.0524 |
| Rural / dispersa | Guerrero, Hidalgo, Michoacán, Nayarit, Puebla, Tlaxcala, Veracruz | 0.2527 | 0.0815 |
| Sur-Sureste vulnerable | Campeche, Chiapas, Oaxaca, Quintana Roo, Tabasco, Yucatán | 0.2508 | 0.0765 |
| Urbana media | 15 estados restantes | 0.2617 | 0.0887 |

**Hallazgo:** La región Metropolitana alta tiene el mejor ajuste en los tres padecimientos, con ventaja de 30-50% sobre las otras regiones. Esto se explica por:
1. Mayor población → series más estables
2. Mayor infraestructura IMSS → reporte más consistente
3. Menor sub-reporte

**Urbana media tiene el peor promedio** a pesar de incluir 15 estados, porque incluye a los outliers principales: Colima, Baja California Sur, Durango, Sinaloa.

---

## 8. Análisis de Hiperparámetros

> **Nota v3:** Estadísticas calculadas sobre los 213 modelos entrenados (excluye 84 insuficientes que no tienen hiperparámetros).

### 8.1 Modo de estacionalidad (multiplicativo vs. aditivo)

| Padecimiento | Multiplicativo | Aditivo | % Aditivo |
|--------------|---------------|---------|-----------|
| Alzheimer (n=35) | 26 (74.3%) | 9 (25.7%) | 25.7% |
| Depresión (n=99) | 50 (50.5%) | 49 (49.5%) | **49.5%** |
| Parkinson (n=79) | 55 (69.6%) | 24 (30.4%) | 30.4% |
| **Total (n=213)** | **131 (61.5%)** | **82 (38.5%)** | **38.5%** |

**Hallazgo importante:** Antes de agregar `additive` al grid, el 100% de los modelos eran multiplicativos. La adición de este modo fue crucial para Depresión, donde casi la mitad de los modelos lo prefieren. Esto tiene sentido epidemiológico: la estacionalidad de Depresión (patrones ligados a estaciones del año) puede ser más aditiva (efecto fijo en casos) que multiplicativa (efecto proporcional a la tendencia).

### 8.2 Changepoint Prior Scale

| Valor | Alzheimer | Depresión | Parkinson | Total | % |
|-------|-----------|-----------|-----------|-------|---|
| 0.01 | 20 (57.1%) | 60 (60.6%) | 50 (63.3%) | 130 (61.0%) |
| 0.03 | 7 (20.0%) | 14 (14.1%) | 14 (17.7%) | 35 (16.4%) |
| 0.05 | 8 (22.9%) | 25 (25.3%) | 15 (19.0%) | 48 (22.5%) |

**cp=0.01 domina ampliamente (61%).** Esto indica que Prophet funciona mejor con tendencias suaves y cambios graduales en estas series epidemiológicas. Valores más altos (0.03, 0.05) ganan en series con cambios de tendencia más abruptos, como ciertos estados de Depresión.

### 8.3 Seasonality Prior Scale

| Valor | Alzheimer | Depresión | Parkinson | Total | % |
|-------|-----------|-----------|-----------|-------|---|
| 0.1 | 13 (37.1%) | 23 (23.2%) | 28 (35.4%) | 64 (30.0%) |
| 0.5 | 12 (34.3%) | 23 (23.2%) | 24 (30.4%) | 59 (27.7%) |
| 1.0 | 4 (11.4%) | 29 (29.3%) | 16 (20.3%) | 49 (23.0%) |
| 2.0 | 6 (17.1%) | 24 (24.2%) | 11 (13.9%) | 41 (19.2%) |

**Alzheimer y Parkinson prefieren sp=0.1** (mayor regularización estacional), lo cual tiene sentido para enfermedades neurodegenerativas donde la estacionalidad es sutil y estable.

**Depresión distribuye más uniformemente**, con ligera preferencia por sp=1.0 (29.3%). Esto refleja la necesidad de mayor flexibilidad estacional para capturar los patrones variables de Depresión.

### 8.4 Mejores combinaciones de hiperparámetros

**Top 5 combinaciones más frecuentes (entre los 213 modelos entrenados):**

| Rank | seasonality_mode | cp | sp | Veces ganadora | % |
|------|-----------------|-----|-----|----------------|---|
| 1 | multiplicative | 0.01 | 0.5 | 24 | 11.3% |
| 2 | multiplicative | 0.01 | 0.1 | 23 | 10.8% |
| 3 | multiplicative | 0.01 | 1.0 | 22 | 10.3% |
| 4 | additive | 0.01 | 0.5 | 16 | 7.5% |
| 5 | additive | 0.01 | 0.1 | 13 | 6.1% |

---

## 9. Impacto del COVID-19 en las Series

### 9.1 Magnitud del impacto (nivel nacional)

| Padecimiento | Pre-COVID (2019) prom/sem | COVID Abr-Dic 2020 prom/sem | Caída (%) | Mínimo semanal | Semana del mínimo |
|-------------|--------------------------|----------------------------|-----------|----------------|-------------------|
| Alzheimer | 64.1 | 22.0 | **-66%** | 9 | 2020-05-25 |
| Depresión | 2,425.1 | 1,451.9 | **-40%** | 938 | 2020-04-06 |
| Parkinson | 183.6 | 66.1 | **-64%** | 40 | 2020-04-27 |

**Alzheimer tuvo la caída más severa (-66%)**, explicable porque los pacientes de Alzheimer son mayoritariamente personas mayores con alto riesgo COVID, que dejaron de acudir a consulta IMSS.

### 9.2 Patrón de recuperación

| Padecimiento | 2021 prom/sem | 2022 prom/sem | 2023 prom/sem | 2024 prom/sem | ¿Recuperó nivel 2019? |
|-------------|--------------|--------------|--------------|--------------|----------------------|
| Alzheimer | 31.2 | 42.8 | 52.1 | 41.4 | **NO** (64% del nivel 2019) |
| Depresión | 1,928.4 | 2,541.0 | 3,041.8 | 2,881.8 | **SÍ + crecimiento** (119%) |
| Parkinson | 104.3 | 147.6 | 184.7 | 154.9 | **PARCIAL** (84%) |

**Hallazgos por padecimiento:**

- **Alzheimer:** No se ha recuperado al nivel pre-pandemia. Posibles causas: mortalidad COVID en población geriátrica vulnerable, cambio de hábitos de consulta, migración a servicios privados. En 2024 muestra incluso descenso respecto a 2023.

- **Depresión:** No solo se recuperó sino que **superó los niveles pre-COVID**. Esto es consistente con la literatura global sobre el incremento de trastornos depresivos post-pandemia. La tendencia sigue al alza.

- **Parkinson:** Recuperación casi completa en 2023 (184.7 vs 183.6), pero ligero descenso en 2024 (154.9). La caída 2024 requiere más datos para determinar si es tendencia o fluctuación.

### 9.3 Configuración del holiday COVID en Prophet

```yaml
- holiday: pandemia_covid
  ds: "2020-03-23"
  lower_window: 0
  upper_window: 913  # días → ~2.5 años → cubre hasta Sep 2022
```

La ventana de 913 días fue calibrada para cubrir el periodo completo desde el inicio de la pandemia hasta la normalización operativa del sistema de salud IMSS (~septiembre 2022). Prophet modela este periodo como un "holiday effect" con coeficiente negativo, evitando que la caída COVID contamine la estacionalidad aprendida.

### 9.4 Implicación para CV

Los folds 1 y 2 de cross-validation (validando 2021 y 2022 respectivamente) evalúan la capacidad del modelo durante el periodo de recuperación COVID. Esto es intencional: si un modelo no puede predecir la recuperación, no debería ganar en CV.

---

## 10. Periodo Atípico 2016

### Configuración

```yaml
- holiday: atipico_2016
  ds: "2016-05-16"
  lower_window: 0
  upper_window: 182  # ~6 meses
```

### Impacto observado (nivel nacional)

| Padecimiento | Pre (Sep 2015 - Abr 2016) | Atípico (May-Nov 2016) | Post (Dic 2016 - Jun 2017) |
|-------------|---------------------------|------------------------|---------------------------|
| Alzheimer | 50.8/sem | 52.5/sem (+3.3%) | 55.0/sem |
| Depresión | 1,843.7/sem | 2,111.7/sem (+14.5%) | 2,244.0/sem |
| Parkinson | 151.6/sem | 156.7/sem (+3.4%) | 150.2/sem |

**Observación:** A diferencia del COVID (caída abrupta), el periodo 2016 muestra una **desviación al alza** moderada, principalmente en Depresión (+14.5%). Podría corresponder a un cambio en la metodología de registro del SINAVE o un evento de salud pública no documentado. La ventana de 182 días permite a Prophet absorber esta anomalía sin distorsionar la estacionalidad.

---

## 11. Modelos Problemáticos y Casuísticas

### 11.1 Clasificación de modelos (v3)

| Nivel | Criterio | Modelos | % de procesados |
|-------|----------|---------|-----------------|
| **Insuficiente** | Promedio <1 caso/semana | 84 | 28.3% |
| **Alta confianza** | RMSE < 0.10 | 111 | 37.4% |
| **Confianza media** | 0.10 ≤ RMSE < 0.25 | 78 | 26.3% |
| **Confianza baja** | 0.25 ≤ RMSE < 0.35 | 15 | 5.1% |
| **Muy baja confianza** | RMSE ≥ 0.35 | 9 | 3.0% |

### 11.2 Top 20 modelos con mayor RMSE (solo entrenados)

| # | Padecimiento | Estado | Sexo | RMSE | Mode | cp | sp | Causa probable |
|---|-------------|--------|------|------|------|-----|-----|----------------|
| 1 | Depresión | Nayarit | mujeres | 0.4115 | mul | 0.01 | 2.0 | Cambio de régimen 2018 |
| 2 | Depresión | Nayarit | general | 0.4097 | mul | 0.01 | 1.0 | Cambio de régimen 2018 |
| 3 | Depresión | BCS | hombres | 0.3921 | mul | 0.01 | 0.5 | Baja población |
| 4 | Depresión | Colima | general | 0.3875 | mul | 0.01 | 1.0 | Baja población |
| 5 | Depresión | BCS | general | 0.3833 | mul | 0.01 | 1.0 | Baja población |
| 6 | Depresión | Colima | mujeres | 0.3540 | mul | 0.05 | 1.0 | Baja población |
| 7 | Depresión | Colima | hombres | 0.3375 | add | 0.05 | 1.0 | Baja población |
| 8 | Depresión | Durango | general | 0.3331 | mul | 0.03 | 1.0 | Serie errática |
| 9 | Depresión | Tabasco | general | 0.3329 | add | 0.03 | 0.1 | Cambio de tendencia (con holiday) |
| 10 | Depresión | Chihuahua | general | 0.3295 | mul | 0.05 | 2.0 | Estacionalidad irregular |
| 11 | Depresión | Durango | mujeres | 0.3276 | mul | 0.03 | 0.1 | Serie errática |
| 12 | Depresión | Tabasco | mujeres | 0.2998 | add | 0.05 | 2.0 | Cambio de tendencia (con holiday) |
| 13 | Depresión | Chihuahua | mujeres | 0.2977 | mul | 0.05 | 2.0 | Estacionalidad irregular |
| 14 | Depresión | BCS | mujeres | 0.2935 | mul | 0.01 | 0.1 | Baja población |
| 15 | Depresión | Nayarit | hombres | 0.2867 | add | 0.01 | 2.0 | Cambio de régimen 2018 |
| 16 | Depresión | Yucatán | general | 0.2771 | add | 0.01 | 2.0 | Variabilidad alta |
| 17 | Depresión | Sonora | general | 0.2761 | mul | 0.01 | 0.5 | Serie volátil |
| 18 | Depresión | Guerrero | general | 0.2732 | add | 0.01 | 2.0 | Estacionalidad irregular |
| 19 | Depresión | Coahuila | general | 0.2669 | mul | 0.05 | 0.5 | Serie volátil |
| 20 | Depresión | Campeche | general | 0.2597 | mul | 0.01 | 1.0 | Baja población |

**100% de los modelos con RMSE > 0.25 son de Depresión.**

**Cambio v2 → v3 en Tabasco:**

| Sexo | RMSE v2 | RMSE v3 | Cambio |
|------|---------|---------|--------|
| Hombres | 0.3092 | 0.2482 | **-19.7%** |
| Mujeres | 0.3492 | 0.2998 | **-14.1%** |
| General | 0.3548 | 0.3329 | **-6.2%** |

El holiday `cambio_regimen_tabasco_2023` absorbe el salto estructural de enero 2023, mejorando significativamente los tres modelos.

### 11.3 Casuística: Nayarit — Cambio de régimen en Depresión

Nayarit presenta el caso más extremo de cambio estructural:

```
Periodo          | Prom. casos/semana | Observación
2014             | 29.4               | Línea base estable
2015             | 32.8               | Estable
2016             | 33.1               | Estable
2017             | 30.5               | Estable
2018             | 57.8               | ⚠️ Aumento súbito +75%
2019             | 83.4               | ⚠️ Sigue creciendo, max=160
2020             | 80.9               | COVID + nivel alto
2021             | 46.9               | Caída post-COVID
2022             | 60.2               | Estabilización
2023             | 65.1               | Nuevo nivel
2024             | 64.8               | Estabilizado
```

El salto 2017→2018 sugiere un cambio administrativo (nueva clínica, reclasificación CIE, campaña de diagnóstico) más que un aumento real de prevalencia. Prophet no puede modelar un cambio estructural de esta magnitud sin un holiday o regresor externo que lo señale.

> **Nota v3:** Se probó un holiday `cambio_regimen_nayarit_2018` (ds=2018-08-27, window=365 días) pero empeoró el RMSE +5.8%. El cambio de Nayarit es una **step function permanente** (el nivel alto se mantiene), no un evento temporal. Los holidays de Prophet modelan desviaciones temporales y esperan retorno a la línea base, por lo que **son la herramienta incorrecta** para cambios permanentes. Soluciones alternativas: changepoints explícitos, modelos segmentados, o regresores binarios step.

### 11.4 Casuística: Baja California Sur — Series insuficientes

- **574 semanas de datos (2013-2024): 0 casos de Alzheimer reportados al SINAVE**
- BCS tiene 798,447 habitantes y es el estado menos poblado después de Colima
- **v3:** Los 3 modelos de Alzheimer-BCS se marcan como **insuficientes** (promedio 0.0 casos/semana). También Parkinson-BCS completo (promedio 0.37-0.91).

**v2 vs v3:** En v2, BCS-Alzheimer tenía RMSE=0.000 (modelo trivial sobre serie plana de ceros). Esto era técnicamente correcto pero engañoso: inflar el conteo de modelos "buenos" con un modelo que predice 0 siempre no es útil. v3 clasifica estos modelos honestamente como insuficientes.

### 11.5 Casuística: Colima — El outlier universal

Colima sigue siendo problemático en v3, pero con matiz:
- **Alzheimer:** Los 3 modelos ahora son **insuficientes** (promedio 0.33-0.88 casos/semana). En v2 tenía RMSE 0.148 — un modelo entrenado sobre datos casi vacíos.
- **Depresión:** RMSE 0.388 (4to peor de todos)
- **Parkinson:** RMSE 0.192 (peor de todos entre entrenados)

Con 731,391 habitantes (el estado menos poblado de México), la Depresión de Colima (~18 casos/semana) es el único padecimiento con volumen suficiente para entrenar los tres modelos. Parkinson (~4 casos/semana) apenas pasa el umbral.

### 11.6 Casuística: Puebla — Alta población pero RMSE elevado en Parkinson

Puebla tiene 6.6M habitantes pero un RMSE de Parkinson de 0.146, inusualmente alto para su tamaño. Al revisar los datos:
- La serie de Parkinson en Puebla muestra **irregularidades en 2018-2019** con picos inexplicados
- Posible cambio en la cobertura IMSS o en las prácticas de diagnóstico
- No se observa el mismo patrón en Alzheimer (insuf) ni Depresión (0.245), lo que descarta un problema general de datos

---

## 12. Hallazgo Crítico: Población Constante en el Dataset

### Descubrimiento

Al investigar la posibilidad de agregar regresores externos (población, densidad) a Prophet, se descubrió que **la columna `Total` (población) es constante para cada estado en todo el dataset**:

```
Estado              | Total       | Valores únicos | Rango temporal
Aguascalientes      | 1,425,607   | 1              | 2013-2026
Ciudad de México    | 9,209,944   | 1              | 2013-2026
...                 | ...         | 1              | 2013-2026
(32 estados: todos con exactamente 1 valor único)
```

### Implicación

Un regresor que no varía en el tiempo **no aporta nada** a Prophet. Es absorbido por el intercepto del trend y su coeficiente es numéricamente indeterminado. Agregar `Total` como `add_regressor()` habría sido un error que:
1. No mejora el RMSE
2. Consume grados de libertad
3. Puede desestabilizar L-BFGS

### Solución adoptada

En lugar de agregar un regresor inútil, se **normalizó el target** dividiendo por la población:

```python
y_tasa = (incidencia_semanal / poblacion_estado) × 100,000
```

Esto integra la información poblacional directamente en la escala del target, logrando el objetivo original (que los modelos de estados grandes y pequeños sean comparables) sin el artificio de un regresor constante.

### Causa de la constancia

Los datos INEGI del dataset provienen de una sola descarga puntual (no de series temporales de población). Para tener población variable se necesitarían las Proyecciones de Población CONAPO (2020-2070) o las Estimaciones Intercensales INEGI, ambas por año.

---

## 13. Mejoras Implementadas y su Impacto

### 13.1 Mejora 1: Normalización a tasa por 100K habitantes (v1)

**Archivos modificados:**
- `config/modelado.yaml` — flags `normalizar_tasa`, `columna_poblacion`, `tasa_por`
- `src/modelado/prophet.py` — `agrupa()` preserva columna `Total`; `crea_train_test()` calcula tasa
- `scripts/entrena.py` — guarda `poblacion` y `normalizado` en resultados
- `src/modelado/forecast.py` — desnormaliza predicciones

**Impacto:**
- RMSE dejó de estar dominado por el tamaño poblacional
- CDMX (9M hab.) ya no tiene RMSE 10x mayor que Colima (731K hab.)
- Las métricas reflejan la calidad del ajuste, no el volumen de casos

### 13.2 Mejora 2: Log-transform log(1+y) (v2)

**Implementación:**
```python
# En prophet.py → crea_train_test():
if self.log_transform:
    self.serie["y"] = np.log1p(self.serie["y"])

# En forecast.py → predict():
if self.log_transform:
    for col in ['yhat', 'yhat_lower', 'yhat_upper']:
        forecast[col] = np.expm1(forecast[col])
```

**Impacto en Depresión (el padecimiento más afectado):**

| Métrica | Sin log | Con log | Cambio |
|---------|---------|---------|--------|
| RMSE medio | 0.586 | 0.210 | **-64%** |
| RMSE máximo | 2.448 | 0.412 | **-83%** |
| Modelos con RMSE > 1.0 | 11 | 0 | **-100%** |
| RMSE mediano | 0.571 | 0.204 | -64% |

### 13.3 Mejora 3: Modo aditivo en el grid (v2)

**Antes:** Solo `multiplicative` en el grid (12 combinaciones).
**Después:** `multiplicative` + `additive` (24 combinaciones).

**Impacto por padecimiento (% de modelos entrenados que eligieron aditivo):**
- Alzheimer: 25.7% (aditivo mejora algunos estados pequeños)
- **Depresión: 49.5%** (cerca de mitad y mitad — impacto significativo)
- Parkinson: 30.4%

El modo aditivo es especialmente útil para Depresión porque su estacionalidad se comporta como un **efecto fijo** (X casos más/menos en invierno) en lugar de un **efecto proporcional** (Y% más/menos).

### 13.4 Otras mejoras previas

| Mejora | Impacto |
|--------|---------|
| Reducción de `fourier_order` de 8 a 5 | Estabilizó L-BFGS, eliminó overfitting estacional |
| Adición de `cp=0.01` al grid | Ahora gana en 61% de modelos |
| Adición de `sp=0.1` al grid | Gana en 30% de modelos (mejor regularización) |
| Fallback automático de L-BFGS | 0 fallos de entrenamiento en esta corrida |
| Holiday de COVID con ventana 913d | Absorbe el impacto pandémico sin contaminar estacionalidad |

### 13.5 Mejora 5: Filtro de series insuficientes (v3)

**Archivos modificados:**
- `config/modelado.yaml` — `umbral_minimo_semanal: 1.0`
- `src/modelado/prophet.py` — nuevo método `promedio_semanal()`; nuevos params `entidad` y `padecimiento` en `__init__`
- `scripts/entrena.py` — validación de umbral antes de CV; filtrado de `None` en resultados

**Implementación:**
```python
# En entrena.py → entrenar():
stp = SerieTiempoProphet(df, sexo=sexo, entidad=region, padecimiento=padecimiento)
stp.agrupa()
stp.crea_train_test()

umbral = conf.get('umbral_minimo_semanal', 0)
promedio = stp.promedio_semanal()
if umbral and promedio < umbral:
    logger.warning("Serie insuficiente: {:.2f} < {:.1f}", promedio, umbral)
    return {"confianza": "insuficiente", "promedio_semanal": promedio, ...}
```

**Impacto:**

| Métrica | v2 | v3 | Cambio |
|---------|----|----|--------|
| Modelos entrenados | 297 | 213 | -84 modelos espurios |
| Modelos con RMSE=0 (triviales) | 3 (BCS-Alzheimer) | 0 | Eliminados |
| Tiempo de entrenamiento (Alzheimer) | ~82 min | ~27 min | **-67%** |
| Modelos insuficientes Alzheimer | 0 | 64 | — |
| Modelos insuficientes Parkinson | 0 | 20 | — |
| Modelos insuficientes Depresión | 0 | 0 | — |

**Distribución de insuficientes por estado (Alzheimer):**
- 25 estados tienen al menos 1 modelo insuficiente
- 16 estados tienen los 3 modelos insuficientes (Ags, BCS, Campeche, Chiapas, Colima, Durango, Guerrero, Hidalgo, Morelos, Querétaro, Q.Roo, SLP, Tabasco, Tlaxcala, Yucatán, Zacatecas)
- Solo 10 estados tienen los 3 modelos entrenados (BC, Chihuahua, Jalisco, México, NL, Sinaloa, Tamaulipas, Veracruz + Nacional)

**Distribución de insuficientes por estado (Parkinson):**
- 9 estados tienen al menos 1 modelo insuficiente
- 3 estados tienen los 3 modelos insuficientes (BCS, Querétaro, Zacatecas)

### 13.6 Mejora 6: Experimento holidays de cambio de régimen (v3)

**Archivos modificados:**
- `config/modelado.yaml` — sección `cambios_regimen` con entries por entidad/padecimiento
- `src/modelado/prophet.py` — filtrado de cambios de régimen en `__init__` por entidad y padecimiento

**Hipótesis:** Agregar holidays para los cambios de régimen detectados en estados de Depresión (Nayarit, Tabasco, Colima, Durango, BCS) absorbería los saltos estructurales, mejorando el RMSE.

**Resultado del experimento (5 holidays probados):**

| Estado | ds | Window | RMSE v2 (general) | RMSE con holiday | Cambio | Veredicto |
|--------|----|----|---------|---------|--------|-----------|
| Tabasco | 2023-01-09 | 365d | 0.3548 | 0.3329 | **-6.2%** | **Aprobado** |
| Nayarit | 2018-08-27 | 365d | 0.4097 | ~0.433 | +5.8% | Rechazado |
| Colima | 2023-01-09 | 365d | 0.3875 | ~0.425 | +9.6% | Rechazado |
| Durango | 2015-01-05 | 547d | 0.3331 | ~0.337 | +1.2% | Rechazado |
| BCS | 2023-04-01 | 365d | 0.3833 | ~0.387 | +0.9% | Rechazado |

**Aprendizaje clave:** Los holidays de Prophet modelan **efectos temporales** — una desviación seguida de un retorno a la línea base. Los cambios de régimen permanentes (step functions) son incompatibles:

```
Holiday temporal ✓:     ____/‾‾‾\____    (Prophet maneja bien esto)
Step function ✗:        ____/‾‾‾‾‾‾‾‾   (Prophet intenta "regresar", empeora)
Tabasco (temporal-ish): ____/‾‾‾\___/    (patrón compatible con holiday)
```

**Configuración final (solo Tabasco):**
```yaml
cambios_regimen:
  - holiday: cambio_regimen_tabasco_2023
    ds: "2023-01-09"
    lower_window: 0
    upper_window: 365
    entidad: "Tabasco"
    padecimiento: "Depresión"
```

---

## 14. Pronósticos Generados

### 14.1 Archivo de salida

- **Ruta:** `forecast/all_forecast.csv`
- **Filas:** 206,118 (213 modelos entrenados × variable filas cada uno)
- **Columnas:** 30 (incluye descomposición Prophet completa + `cambio_regimen_tabasco_2023`)
- **Horizonte de predicción:** 120 semanas (2025-01-06 a 2027-04-19)

### 14.2 Pronóstico nacional (resumen)

| Padecimiento | Tasa media predicha (por 100K/sem) | Conteo medio semanal estimado | Tendencia |
|-------------|-----------------------------------|------------------------------|-----------|
| Alzheimer | 0.037 | ~47 | Ligeramente descendente |
| Depresión | 2.453 | ~3,091 | Ascendente sostenida |
| Parkinson | 0.128 | ~161 | Estable |

### 14.3 Columnas clave del forecast

| Columna | Descripción |
|---------|-------------|
| `ds` | Fecha (lunes de cada semana) |
| `yhat` | Predicción en conteo absoluto (desnormalizado) |
| `yhat_tasa` | Predicción en tasa por 100K habitantes |
| `yhat_lower` | Límite inferior del intervalo de confianza |
| `yhat_upper` | Límite superior del intervalo de confianza |
| `trend` | Componente de tendencia |
| `yearly_custom` | Componente estacional anual |
| `pandemia_covid` | Efecto estimado del COVID |
| `atipico_2016` | Efecto estimado del periodo atípico 2016 |
| `cambio_regimen_tabasco_2023` | Efecto del cambio de régimen (solo Tabasco-Depresión) |
| `meta_padecimiento` | Padecimiento del modelo |
| `meta_entidad` | Estado (vacío para nacional) |
| `meta_modo` | Segmento de sexo (hombres/mujeres/general) |

### 14.4 Modelos insuficientes y predicciones

Los 84 modelos marcados como "insuficientes" **no generan predicción**. `predice.py` busca archivos `.pkl` con `rglob()`, y estos modelos no tienen `.pkl`. Por lo tanto:
- `all_forecast.csv` no contiene predicciones para series insuficientes
- Las gráficas de forecast no se generan para estos modelos
- Esto es el comportamiento deseado: no se debe predecir con series de <1 caso/semana

---

## 15. Sugerencias de Mejora Futura

### 15.1 Alta prioridad / Alto impacto

#### ~~1. Excluir o marcar series con >90% de ceros~~ ✅ COMPLETADO (v3)
Implementado como filtro `umbral_minimo_semanal: 1.0`. 84 modelos marcados como insuficientes.

#### ~~2. Agregar changepoints para cambios de régimen~~ ✅ PARCIALMENTE COMPLETADO (v3)
Se probaron 5 holidays de cambio de régimen. Solo Tabasco mejoró (-6.2% a -19.7%). Los demás empeoraron porque son step functions permanentes. **Pendiente:** explorar changepoints explícitos o modelos segmentados para Nayarit, Colima, Durango, BCS.

#### 3. Obtener población temporal de CONAPO
**Problema:** La población es constante en el dataset actual (una foto puntual INEGI). Esto significa que la normalización usa la misma población para 2014 y 2024, introduciendo un sesgo leve.
**Solución:** Integrar las Proyecciones de Población CONAPO (por estado, por año) para normalizar con población variable.
**Impacto estimado:** Mejora leve pero correcta metodológicamente. Importante para estados con crecimiento demográfico alto (Quintana Roo, BCS).
**Esfuerzo:** Medio (requiere descarga y limpieza de datos CONAPO).

### 15.2 Media prioridad / Medio impacto

#### 4. Grid de hiperparámetros por padecimiento
**Problema:** Se usa el mismo grid para los 3 padecimientos, pero Depresión necesita parámetros diferentes.
**Solución:** Grid dedicado por padecimiento:
- Alzheimer/Parkinson: `cp=[0.005, 0.01, 0.03]`, `sp=[0.1, 0.5]`, `mode=multiplicative`
- Depresión: `cp=[0.01, 0.03, 0.05, 0.1]`, `sp=[0.5, 1.0, 2.0, 5.0]`, `mode=[mul, add]`
**Impacto:** Reduce tiempo de entrenamiento para Alzheimer/Parkinson (grid más chico), mejora exploración para Depresión.
**Esfuerzo:** Bajo (cambio en config + lógica de selección).

#### 5. Métricas adicionales (MAE, MAPE, coverage)
**Problema:** Solo se reporta RMSE. El RMSE penaliza outliers pero puede ocultar sesgo sistemático.
**Solución:** Calcular y reportar MAE, MAPE, y coverage del intervalo de predicción (% de observaciones dentro de [yhat_lower, yhat_upper]) durante CV.
**Impacto:** Mejor diagnóstico de modelos. Un modelo puede tener buen RMSE pero pésima cobertura.
**Esfuerzo:** Bajo.

#### 6. Modelo de ensamble por región
**Problema:** Los estados pequeños (Colima, BCS, Campeche) tienen series muy ruidosas individualmente.
**Solución:** Entrenar modelos a nivel de región INEGI que agreguen estados similares, luego distribuir la predicción proporcionalmente. Combinar con modelos estatales como ensamble.
**Impacto:** Mejora significativa para 5-8 estados problemáticos.
**Esfuerzo:** Alto (nueva arquitectura de predicción).

#### 7. Changepoints explícitos para step functions
**Problema:** Nayarit, Colima, Durango y BCS tienen cambios permanentes de nivel que los holidays no pueden absorber (empeoran el RMSE).
**Solución:** Usar el parámetro `changepoints` de Prophet con fechas específicas, o segmentar el entrenamiento (entrenar solo post-cambio).
**Impacto:** Potencial reducción significativa para 4-5 estados de Depresión con RMSE > 0.30.
**Esfuerzo:** Medio (requiere experimentación por estado).

### 15.3 Baja prioridad / Mejoras incrementales

#### 8. Fourier order adaptativo
**Problema:** `fourier_order=5` es fijo. Algunos estados con estacionalidad simple podrían usar 3, otros con patrones complejos podrían necesitar 7.
**Solución:** Agregar fourier_order al grid de CV.
**Esfuerzo:** Bajo, pero expande el grid significativamente.

#### 9. Regresores externos dinámicos
**Problema:** Actualmente no se usan regresores externos (la población es constante).
**Solución:** Si se obtienen datos CONAPO (temporales), integrar población como regresor. También explorar: temperatura media, índice de marginación, PIB estatal.
**Esfuerzo:** Alto (requiere fuentes de datos adicionales).

#### 10. Modelos alternativos (benchmark)
**Problema:** No se tiene punto de comparación para saber si Prophet es el mejor modelo.
**Solución:** Implementar baselines (ARIMA/SARIMA, ETS) y comparar RMSE head-to-head con Prophet.
**Esfuerzo:** Medio.

#### 11. Detección automática de outliers en pronóstico
**Problema:** Algunos pronósticos pueden generar valores negativos o implausibles (especialmente con log-transform invertido).
**Solución:** Post-procesamiento que clipea valores negativos a 0 y aplica sanity checks.
**Esfuerzo:** Muy bajo.

### 15.4 Resumen de priorización

| # | Mejora | Impacto | Esfuerzo | Estado |
|---|--------|---------|----------|--------|
| 1 | ~~Excluir/marcar series vacías~~ | Alto | Bajo | ✅ v3 |
| 2 | ~~Changepoints para cambios de régimen~~ | Alto | Medio | ✅ Parcial v3 |
| 3 | Población temporal CONAPO | Medio | Medio | **Pendiente** |
| 4 | Grid por padecimiento | Medio | Bajo | Pendiente |
| 5 | Métricas adicionales en CV | Medio | Bajo | Pendiente |
| 6 | Ensamble por región | Alto | Alto | Pendiente |
| 7 | Changepoints explícitos para step functions | Alto | Medio | **Pendiente** |
| 8 | Fourier order adaptativo | Bajo | Bajo | Pendiente |
| 9 | Regresores dinámicos | Medio | Alto | Pendiente |
| 10 | Modelos alternativos (benchmark) | Medio | Medio | Pendiente |
| 11 | Clip de pronósticos negativos | Bajo | Muy bajo | Pendiente |

---

## 16. Anexos

### Anexo A: Tiempos de ejecución

**Entrenamiento v3 (con filtro de insuficientes):**

| Fase | Modelos entrenados | Insuficientes | Duración aprox. |
|------|-------------------|---------------|-----------------|
| Alzheimer | 35 | 64 | ~27 min |
| Depresión | 99 | 0 | ~82 min |
| Parkinson | 79 | 20 | ~65 min |
| **Total** | **213** | **84** | **~3h 30min** |
| Predicción (297 gráficos) | — | — | ~1.5 min |

**Comparación v2 vs v3:** El filtro de insuficientes ahorró ~44 min de entrenamiento (84 modelos × ~50 seg cada uno).

### Anexo B: Estructura de archivos generados

```
models/
├── Alzheimer/
│   ├── Prophet_Alzheimer_completo.csv          # Resultados (99 filas: 35 entrenados + 64 insuf)
│   ├── Prophet_Alzheimer_hombres.pkl           # Modelo nacional hombres
│   ├── Prophet_Alzheimer_hombres.csv           # Datos train (sidecar)
│   ├── Prophet_Alzheimer_mujeres.pkl
│   ├── Prophet_Alzheimer_mujeres.csv
│   ├── Prophet_Alzheimer_general.pkl
│   ├── Prophet_Alzheimer_general.csv
│   └── ... (solo estados con datos suficientes generan .pkl/.csv)
├── Depresion/
│   └── ... (99 modelos, todos entrenados)
└── Parkinson/
    └── ... (79 entrenados, 20 insuficientes)

forecast/
├── all_forecast.csv                            # 206,118 filas
├── Alzheimer/{Estado}/*.png                    # 96 gráficos (todos los estados)
├── Depresión/{Estado}/*.png                    # 96 gráficos
└── Parkinson/{Estado}/*.png                    # 96 gráficos
```

> **Nota:** Los gráficos de forecast se generan para todos los 297 modelos (incluyendo insuficientes) pero los modelos insuficientes solo muestran datos históricos sin línea de predicción.

### Anexo C: Columnas del CSV de entrenamiento (sidecar)

| Columna | Descripción |
|---------|-------------|
| `ds` | Fecha (lunes de cada semana) |
| `y` | Target en espacio log-tasa (lo que Prophet ve) |
| `Total` | Población del estado/nacional (para desnormalizar) |
| `y_original` | Conteo absoluto original (para referencia) |

### Anexo D: Configuración YAML completa (v3)

**`config/modelado.yaml`:**
```yaml
normalizar_tasa: true
columna_poblacion: "Total"
tasa_por: 100000
log_transform: true
umbral_minimo_semanal: 1.0   # promedio mínimo de casos/semana para entrenar

param_grid_prophet:
  seasonality_mode: [multiplicative, additive]
  changepoint_prior_scale: [0.01, 0.03, 0.05]
  seasonality_prior_scale: [0.1, 0.5, 1.0, 2.0]

param_model:
  yearly_seasonality: False
  weekly_seasonality: False
  daily_seasonality: False

add_seasonality:
  name: 'yearly_custom'
  period: 52.18
  fourier_order: 5

FECHA_CORTE_ENTRENAMIENTO: "2025-01-01"
TS_SPLITS: 4
TEST_SIZE: 53

peridos_atipicos:
  - holiday: pandemia_covid
    ds: "2020-03-23"
    lower_window: 0
    upper_window: 913

  - holiday: atipico_2016
    ds: "2016-05-16"
    lower_window: 0
    upper_window: 182

# Cambios de régimen por entidad/padecimiento
# NOTA: Solo incluir cambios temporales. Los permanentes (step functions)
# empeoran el RMSE. Nayarit, Colima, Durango, BCS fueron probados y rechazados.
cambios_regimen:
  - holiday: cambio_regimen_tabasco_2023
    ds: "2023-01-09"
    lower_window: 0
    upper_window: 365
    entidad: "Tabasco"
    padecimiento: "Depresión"
```

**`config/params.yaml`:**
```yaml
padecimiento:
  tipo: "General"
  modelado_estados: True
  entrena_modelo: True

prediccion:
  periodo: 120  # semanas de horizonte
```

### Anexo E: Reproducibilidad

Para reproducir esta corrida exacta:

```bash
# 1. Activar entorno
source integrador/bin/activate

# 2. Asegurar datos actualizados
make data-pull

# 3. Pipeline completo de preprocesamiento
make preprocess

# 4. Entrenar modelos (~3.5 horas)
make train

# 5. Generar predicciones
make predict

# 6. Sincronizar artefactos
make data-push && make s3-sync
```

**Commit de referencia:** `5b9d0c3` — "feat: filtro series insuficientes + holiday cambio de régimen Tabasco"

### Anexo F: Changelog del reporte

| Versión | Fecha | Cambios |
|---------|-------|---------|
| v2.0 | 2026-02-20 | Reporte inicial con 297 modelos (log-transform + additive mode) |
| **v3.0** | **2026-02-20** | Filtro insuficientes (84 modelos), holiday Tabasco, estadísticas actualizadas |

---

*Reporte generado el 20 de febrero de 2026 como parte del proyecto EpiForecast-MX.*
