# Reporte de Hallazgos — Modelado Prophet v2.0

**Proyecto:** EpiForecast-MX (IMSS × Tec de Monterrey)
**Fecha de corrida:** 20 de febrero de 2026
**Autor:** Equipo de modelado
**Modelos entrenados:** 297 (3 padecimientos × 33 geografías × 3 segmentos de sexo)

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

Se entrenaron **297 modelos Prophet** para predecir la incidencia semanal de tres padecimientos neurológicos/salud mental (Depresión F32, Alzheimer G30, Parkinson G20) a nivel estatal y nacional en México, segmentados por sexo.

### Resultados clave

| Métrica | Valor |
|---------|-------|
| Modelos totales | 297 |
| RMSE medio global | 0.1008 (en espacio log-tasa) |
| RMSE mediano global | 0.0595 |
| Modelos con RMSE < 0.10 | 192 (64.6%) |
| Modelos con RMSE > 0.30 | 14 (4.7%, todos Depresión) |
| Modelos con RMSE > 0.40 | 2 (0.7%) |
| Errores de entrenamiento | 0 |
| Errores de predicción | 0 |
| Tiempo total de entrenamiento | 4h 5m 44s |

### Mejoras implementadas en esta corrida (vs. corrida anterior)

| Mejora | Impacto en Depresión |
|--------|---------------------|
| Normalización a tasa por 100K habitantes | RMSE comparable entre estados grandes y pequeños |
| Log-transform `log(1+y)` | RMSE mean: -64%, RMSE max: -83% |
| Modo aditivo en grid de CV | Elegido en 49% de modelos de Depresión |
| **Resultado combinado** | **0 modelos con RMSE > 1.0 (antes: 11)** |

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
    ↓ Entrenamiento Prophet con CV temporal
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

### 3.3 Eventos atípicos configurados

| Evento | Fecha inicio | Ventana (días) | Duración efectiva |
|--------|-------------|----------------|-------------------|
| Pandemia COVID-19 | 2020-03-23 | 913 | ~2.5 años (hasta ~Sep 2022) |
| Atípico 2016 | 2016-05-16 | 182 | ~6 meses |

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

### 3.6 Fallback de L-BFGS

Si el optimizador L-BFGS falla durante el entrenamiento final (después de CV), el sistema reintenta automáticamente con `changepoint_prior_scale=0.05` como respaldo. En esta corrida: **0 modelos necesitaron fallback**.

### 3.7 Inventario de modelos

| Padecimiento | Modelos nacionales | Modelos estatales | Total |
|--------------|-------------------|-------------------|-------|
| Alzheimer | 3 (hombres, mujeres, general) | 96 (32 estados × 3) | 99 |
| Depresión | 3 | 96 | 99 |
| Parkinson | 3 | 96 | 99 |
| **Total** | **9** | **288** | **297** |

Cada modelo genera: 1 archivo `.pkl` (modelo serializado) + 1 archivo `.csv` (datos de entrenamiento con columnas `ds`, `y`, `Total`, `y_original`).

---

## 4. Resultados Globales

### 4.1 RMSE descriptivo por padecimiento

> RMSE reportado en espacio log-tasa (después de normalización + log-transform). Es la métrica con la que Prophet optimiza vía CV.

| Estadístico | Alzheimer | Depresión | Parkinson |
|-------------|-----------|-----------|-----------|
| **n** | 99 | 99 | 99 |
| **Media** | 0.0304 | 0.2100 | 0.0620 |
| **Mediana** | 0.0252 | 0.2041 | 0.0525 |
| **Desv. Est.** | 0.0222 | 0.0766 | 0.0344 |
| **Mínimo** | 0.0000 | 0.0681 | 0.0153 |
| **Q25** | 0.0176 | 0.1609 | 0.0367 |
| **Q75** | 0.0367 | 0.2456 | 0.0766 |
| **Máximo** | 0.1481 | 0.4115 | 0.1923 |

**Interpretación:** Alzheimer es el padecimiento más fácil de modelar (RMSE medio 0.030), seguido de Parkinson (0.062). Depresión es significativamente más difícil (0.210), con un rango 3-7x mayor que los otros dos.

### 4.2 Nacional vs. Estatal

| Padecimiento | Nacional (media) | Estatal (media) | Ratio Estatal/Nacional |
|--------------|-----------------|-----------------|----------------------|
| Alzheimer | 0.0069 | 0.0311 | 4.5x |
| Depresión | 0.1128 | 0.2131 | 1.9x |
| Parkinson | 0.0197 | 0.0633 | 3.2x |

Los modelos nacionales son consistentemente mejores porque agregan 32 estados, reduciendo la varianza por ley de grandes números.

### 4.3 RMSE por segmento de sexo

| Padecimiento | Hombres | Mujeres | General (total) |
|--------------|---------|---------|-----------------|
| Alzheimer | 0.0231 | 0.0293 | 0.0387 |
| Depresión | 0.1607 | 0.2233 | 0.2462 |
| Parkinson | 0.0547 | 0.0525 | 0.0787 |

**Hallazgo:** El modelo "general" (ambos sexos combinados) tiene peor RMSE que los modelos por sexo. Esto sugiere que la dinámica de hombres y mujeres difiere lo suficiente para que combinarlos genere ruido adicional.

**Parkinson es la excepción:** las mujeres tienen RMSE ligeramente menor que los hombres (0.052 vs 0.055), a pesar de que Parkinson es más prevalente en hombres (ratio H/M = 1.12). La serie femenina de Parkinson es más estable y predecible.

### 4.4 RMSE ponderado por población (solo modelos estatales)

| Padecimiento | Media simple | Media ponderada por población |
|--------------|-------------|-------------------------------|
| Alzheimer | 0.0311 | 0.0240 |
| Depresión | 0.2131 | 0.1870 |
| Parkinson | 0.0633 | 0.0510 |

La media ponderada es menor porque los estados grandes (CDMX, México, Jalisco, Nuevo León) tienen mejores modelos, y atienden a la mayoría de la población.

### 4.5 Distribución de modelos por umbrales de RMSE

| Umbral | Alzheimer | Depresión | Parkinson | Total | % del total |
|--------|-----------|-----------|-----------|-------|-------------|
| RMSE < 0.05 | 80 | 0 | 55 | 135 | 45.5% |
| 0.05 ≤ RMSE < 0.10 | 16 | 6 | 35 | 57 | 19.2% |
| 0.10 ≤ RMSE < 0.20 | 3 | 43 | 9 | 55 | 18.5% |
| 0.20 ≤ RMSE < 0.30 | 0 | 36 | 0 | 36 | 12.1% |
| 0.30 ≤ RMSE < 0.40 | 0 | 12 | 0 | 12 | 4.0% |
| RMSE ≥ 0.40 | 0 | 2 | 0 | 2 | 0.7% |

> **64.6% de los modelos tienen RMSE < 0.10** y todos los modelos con RMSE > 0.10 en Alzheimer y Parkinson son outliers aislados.

---

## 5. Análisis por Padecimiento

### 5.1 Depresión (CIE-10: F32) — El padecimiento más difícil

**Por qué Depresión es más difícil de modelar:**

1. **Alto volumen y alta volatilidad:** ~2,220 casos/semana nacional vs ~47 para Alzheimer, con coeficiente de variación de 0.5-0.6 en estados pequeños
2. **Tendencia estructural ascendente:** La incidencia de depresión ha crecido sostenidamente desde 2018, con aceleración post-COVID (2,425/sem en 2019 → 2,882/sem en 2024)
3. **Cambios de régimen abruptos:** Algunos estados (Nayarit, Tabasco) muestran duplicación de incidencia en 1-2 años sin explicación clara
4. **Estacionalidad irregular:** Depresión tiene patrones estacionales más variables año a año que Alzheimer o Parkinson
5. **COVID heterogéneo:** El impacto del COVID fue -40% nacional para Depresión, pero varió de -20% a -60% entre estados

**Distribución de RMSE:**
- Media: 0.2100, Mediana: 0.2041
- IQR: [0.1609, 0.2456]
- 49.5% de modelos eligieron modo aditivo (vs 23% en Alzheimer, 28% en Parkinson)

**Ratios por sexo (acumulado nacional):**
- Mujeres: 944,873 casos (2.87x más que hombres)
- Hombres: 329,192 casos
- La mayor brecha de sexo de los tres padecimientos

**Top 5 estados más difíciles (modelo general):**

| Estado | RMSE | Población | Casos/semana (prom.) | Problema identificado |
|--------|------|-----------|---------------------|----------------------|
| Nayarit | 0.4097 | 1,235,456 | ~42 | Cambio de régimen 2018 (se duplica la incidencia) |
| Colima | 0.3875 | 731,391 | ~18 | Población muy pequeña, alta volatilidad |
| Baja California Sur | 0.3833 | 798,447 | ~19 | Ídem, estado menos poblado |
| Tabasco | 0.3548 | 2,402,598 | ~42 | Cambio brusco de tendencia |
| Chihuahua | 0.3295 | 3,741,869 | ~54 | Estacionalidad errática |

### 5.2 Alzheimer (CIE-10: G30) — El más estable

**Características:**
- Serie de baja volatilidad, tendencia ligeramente descendente post-COVID
- ~47 casos/semana nacional, series suaves
- 77% de modelos eligieron modo multiplicativo
- Cambio estacional consistente año a año

**Datos de volumen por sexo (nacional):**
- Mujeres: 16,037 casos acumulados (ratio M/H = 1.49x)
- Hombres: 10,762 casos acumulados

**Caso especial — Baja California Sur:**
- **RMSE = 0.0000** en los 3 modelos (hombres, mujeres, general)
- **0 casos de Alzheimer reportados** en las 574 semanas de entrenamiento
- El modelo aprendió una serie plana (y=0), dando RMSE perfecto trivialmente
- Esto no es un error de modelo sino un **vacío de datos**: BCS es el estado menos poblado y probablemente tiene sub-reporte IMSS de Alzheimer

**Top 3 estados más difíciles (modelo general):**

| Estado | RMSE | Total casos | Casos/semana |
|--------|------|------------|-------------|
| Colima | 0.1481 | ~524 | 0.9 |
| Campeche | 0.0814 | ~301 | 0.5 |
| Nayarit | 0.0731 | ~689 | 1.2 |

Todos comparten la misma causa: **volumen extremadamente bajo** (<1.5 casos/semana).

### 5.3 Parkinson (CIE-10: G20) — Intermedio

**Características:**
- ~145 casos/semana nacional, tendencia relativamente estable
- Serie más regular que Depresión pero con más volumen que Alzheimer
- 72% multiplicativo, 28% aditivo
- Recuperación completa post-COVID (2023: 184.7/sem vs pre-COVID 183.6/sem)

**Datos de volumen por sexo (nacional):**
- Hombres: 44,049 (predomina, ratio H/M = 1.12)
- Mujeres: 39,267

**Top 3 estados más difíciles (modelo general):**

| Estado | RMSE | Problema |
|--------|------|---------|
| Colima | 0.1923 | Población muy pequeña, ~4 casos/semana |
| Durango | 0.1508 | Tendencia irregular, datos inconsistentes |
| Puebla | 0.1461 | 6.6M hab. pero serie irregular (posible problema de reporte) |

---

## 6. Análisis por Estado

### 6.1 Tabla completa — RMSE modelo "general" por estado y padecimiento

| Estado | Población | Alzheimer | Depresión | Parkinson | Promedio |
|--------|-----------|-----------|-----------|-----------|---------|
| Aguascalientes | 1,425,607 | 0.0402 | 0.2584 | 0.0754 | 0.1247 |
| Baja California | 3,769,020 | 0.0394 | 0.1842 | 0.0622 | 0.0953 |
| Baja California Sur | 798,447 | **0.0000** | 0.3833 | 0.1134 | 0.1656 |
| Campeche | 928,363 | 0.0814 | 0.2597 | 0.1215 | 0.1542 |
| Chiapas | 5,543,828 | 0.0200 | 0.1877 | 0.0357 | 0.0811 |
| Chihuahua | 3,741,869 | 0.0476 | 0.3295 | 0.0855 | 0.1542 |
| Ciudad de México | 9,209,944 | 0.0186 | 0.2269 | 0.0514 | 0.0990 |
| Coahuila | 3,146,771 | 0.0483 | 0.2669 | 0.0746 | 0.1299 |
| **Colima** | **731,391** | **0.1481** | **0.3875** | **0.1923** | **0.2426** |
| Durango | 1,832,650 | 0.0564 | 0.3331 | 0.1508 | 0.1801 |
| Guanajuato | 6,166,934 | 0.0157 | 0.1799 | 0.0337 | 0.0764 |
| Guerrero | 3,540,685 | 0.0244 | 0.2732 | 0.0568 | 0.1181 |
| Hidalgo | 3,082,841 | 0.0252 | 0.2216 | 0.0525 | 0.0998 |
| Jalisco | 8,348,151 | 0.0332 | 0.1626 | 0.0757 | 0.0905 |
| México | 16,992,418 | 0.0149 | 0.2169 | 0.0397 | 0.0905 |
| Michoacán | 4,748,846 | 0.0292 | 0.2133 | 0.0586 | 0.1004 |
| Morelos | 1,971,520 | 0.0469 | 0.2456 | 0.1252 | 0.1392 |
| **Nayarit** | **1,235,456** | 0.0731 | **0.4097** | 0.1180 | **0.2003** |
| Nuevo León | 5,784,442 | 0.0279 | 0.1757 | 0.0429 | 0.0822 |
| Oaxaca | 4,132,148 | 0.0308 | 0.1986 | 0.0513 | 0.0936 |
| Puebla | 6,583,278 | 0.0274 | 0.2453 | 0.1461 | 0.1396 |
| Querétaro | 2,368,467 | 0.0227 | 0.1874 | 0.0390 | 0.0830 |
| Quintana Roo | 1,857,985 | 0.0317 | 0.2272 | 0.0676 | 0.1088 |
| San Luis Potosí | 2,822,255 | 0.0349 | 0.2154 | 0.0715 | 0.1073 |
| Sinaloa | 3,026,943 | 0.0624 | 0.2222 | 0.0997 | 0.1281 |
| Sonora | 2,944,840 | 0.0428 | 0.2761 | 0.0605 | 0.1265 |
| Tabasco | 2,402,598 | 0.0432 | 0.3548 | 0.0920 | 0.1633 |
| Tamaulipas | 3,527,735 | 0.0535 | 0.2071 | 0.0961 | 0.1189 |
| Tlaxcala | 1,342,977 | 0.0322 | 0.2314 | 0.0888 | 0.1175 |
| Veracruz | 8,062,579 | 0.0244 | 0.1745 | 0.0501 | 0.0830 |
| Yucatán | 2,320,898 | 0.0423 | 0.2771 | 0.0911 | 0.1368 |
| Zacatecas | 1,622,138 | 0.0300 | 0.2494 | 0.0506 | 0.1100 |

### 6.2 Mejores estados (RMSE promedio más bajo)

| Rank | Estado | Promedio 3 padecimientos | Población |
|------|--------|-------------------------|-----------|
| 1 | Guanajuato | 0.0764 | 6,166,934 |
| 2 | Chiapas | 0.0811 | 5,543,828 |
| 3 | Nuevo León | 0.0822 | 5,784,442 |
| 4 | Querétaro | 0.0830 | 2,368,467 |
| 5 | Veracruz | 0.0830 | 8,062,579 |

### 6.3 Peores estados (RMSE promedio más alto)

| Rank | Estado | Promedio 3 padecimientos | Población | Causa principal |
|------|--------|-------------------------|-----------|----------------|
| 1 | **Colima** | **0.2426** | 731,391 | Población más pequeña, alta volatilidad |
| 2 | **Nayarit** | **0.2003** | 1,235,456 | Cambio de régimen Depresión 2018 |
| 3 | Durango | 0.1801 | 1,832,650 | Series irregulares |
| 4 | Baja California Sur | 0.1656 | 798,447 | 0 casos Alzheimer + baja población |
| 5 | Tabasco | 0.1633 | 2,402,598 | Salto de tendencia en Depresión |

### 6.4 Correlación RMSE vs. Población

Existe una correlación negativa moderada entre población y RMSE: los estados más poblados generalmente tienen mejores modelos. Sin embargo, la normalización a tasa por 100K ha reducido significativamente esta dependencia comparado con la corrida anterior donde se usaban conteos absolutos.

**Estados que rompen la tendencia:**
- **Puebla** (6.6M hab.) tiene RMSE alto en Parkinson (0.146) a pesar de su tamaño — posible problema de reporte
- **Chiapas** (5.5M hab.) tiene RMSE bajo a pesar de menor acceso a servicios IMSS — series estables
- **Querétaro** (2.4M hab.) tiene RMSE bajo a pesar de población mediana — datos consistentes

---

## 7. Análisis por Región INEGI de Salud Mental

| Región INEGI | Estados | n estados | Alzheimer (media) | Depresión (media) | Parkinson (media) |
|-------------|---------|-----------|-------------------|--------------------|-------------------|
| Metropolitana alta | CDMX, Jalisco, México, Nuevo León | 4 | 0.0237 | 0.1955 | 0.0524 |
| Rural / dispersa | Guerrero, Hidalgo, Michoacán, Nayarit, Puebla, Tlaxcala, Veracruz | 7 | 0.0337 | 0.2527 | 0.0815 |
| Sur-Sureste vulnerable | Campeche, Chiapas, Oaxaca, Quintana Roo, Tabasco, Yucatán | 6 | 0.0416 | 0.2508 | 0.0765 |
| Urbana media | 15 estados restantes | 15 | 0.0459 | 0.2617 | 0.0887 |

**Hallazgo:** La región Metropolitana alta tiene el mejor ajuste en los tres padecimientos, con ventaja de 30-50% sobre las otras regiones. Esto se explica por:
1. Mayor población → series más estables
2. Mayor infraestructura IMSS → reporte más consistente
3. Menor sub-reporte

**Urbana media tiene el peor promedio** a pesar de incluir 15 estados, porque incluye a los outliers principales: Colima, Baja California Sur, Durango, Sinaloa.

---

## 8. Análisis de Hiperparámetros

### 8.1 Modo de estacionalidad (multiplicativo vs. aditivo)

| Padecimiento | Multiplicativo | Aditivo | % Aditivo |
|--------------|---------------|---------|-----------|
| Alzheimer | 76 (76.8%) | 23 (23.2%) | 23.2% |
| Depresión | 50 (50.5%) | 49 (49.5%) | **49.5%** |
| Parkinson | 71 (71.7%) | 28 (28.3%) | 28.3% |

**Hallazgo importante:** Antes de agregar `additive` al grid, el 100% de los modelos eran multiplicativos. La adición de este modo fue crucial para Depresión, donde casi la mitad de los modelos lo prefieren. Esto tiene sentido epidemiológico: la estacionalidad de Depresión (patrones ligados a estaciones del año) puede ser más aditiva (efecto fijo en casos) que multiplicativa (efecto proporcional a la tendencia).

### 8.2 Changepoint Prior Scale

| Valor | Alzheimer | Depresión | Parkinson | Total |
|-------|-----------|-----------|-----------|-------|
| 0.01 | 54 (54.5%) | 60 (60.6%) | 61 (61.6%) | 175 (58.9%) |
| 0.03 | 22 (22.2%) | 14 (14.1%) | 20 (20.2%) | 56 (18.9%) |
| 0.05 | 23 (23.2%) | 25 (25.3%) | 18 (18.2%) | 66 (22.2%) |

**cp=0.01 domina ampliamente (59%).** Esto indica que Prophet funciona mejor con tendencias suaves y cambios graduales en estas series epidemiológicas. Valores más altos (0.03, 0.05) ganan en series con cambios de tendencia más abruptos, como ciertos estados de Depresión.

### 8.3 Seasonality Prior Scale

| Valor | Alzheimer | Depresión | Parkinson | Total |
|-------|-----------|-----------|-----------|-------|
| 0.1 | 41 (41.4%) | 23 (23.2%) | 40 (40.4%) | 104 (35.0%) |
| 0.5 | 28 (28.3%) | 24 (24.2%) | 27 (27.3%) | 79 (26.6%) |
| 1.0 | 15 (15.2%) | 29 (29.3%) | 18 (18.2%) | 62 (20.9%) |
| 2.0 | 15 (15.2%) | 23 (23.2%) | 14 (14.1%) | 52 (17.5%) |

**Alzheimer y Parkinson prefieren sp=0.1** (mayor regularización estacional), lo cual tiene sentido para enfermedades neurodegenerativas donde la estacionalidad es sutil y estable.

**Depresión distribuye más uniformemente**, con ligera preferencia por sp=1.0 (29.3%). Esto refleja la necesidad de mayor flexibilidad estacional para capturar los patrones variables de Depresión.

### 8.4 Mejores combinaciones de hiperparámetros

**Top 3 combinaciones más frecuentes (entre los 297 modelos):**

| Rank | seasonality_mode | cp | sp | Veces ganadora |
|------|-----------------|-----|-----|----------------|
| 1 | multiplicative | 0.01 | 0.5 | 33 (11.1%) |
| 2 | multiplicative | 0.01 | 0.1 | 31 (10.4%) |
| 3 | additive | 0.01 | 0.1 | 19 (6.4%) |

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

### 11.1 Clasificación de modelos por nivel de confianza

| Nivel | Criterio | Modelos | % |
|-------|----------|---------|---|
| **Alta confianza** | RMSE < 0.10 | 192 | 64.6% |
| **Confianza media** | 0.10 ≤ RMSE < 0.25 | 78 | 26.3% |
| **Confianza baja** | 0.25 ≤ RMSE < 0.35 | 19 | 6.4% |
| **Muy baja confianza** | RMSE ≥ 0.35 | 8 | 2.7% |

### 11.2 Top 20 modelos con mayor RMSE

| # | Padecimiento | Estado | Sexo | RMSE | Mode | cp | sp | Causa probable |
|---|-------------|--------|------|------|------|-----|-----|----------------|
| 1 | Depresión | Nayarit | mujeres | 0.4115 | add | 0.05 | 2.0 | Cambio de régimen 2018 |
| 2 | Depresión | Nayarit | general | 0.4097 | add | 0.03 | 2.0 | Cambio de régimen 2018 |
| 3 | Depresión | BCS | hombres | 0.3921 | add | 0.05 | 1.0 | Baja población |
| 4 | Depresión | Colima | general | 0.3875 | mul | 0.01 | 0.1 | Baja población |
| 5 | Depresión | BCS | general | 0.3833 | add | 0.05 | 1.0 | Baja población |
| 6 | Depresión | Nayarit | hombres | 0.3635 | add | 0.03 | 0.5 | Cambio de régimen 2018 |
| 7 | Depresión | Tabasco | general | 0.3548 | mul | 0.05 | 0.1 | Cambio de tendencia |
| 8 | Depresión | Colima | mujeres | 0.3540 | mul | 0.03 | 2.0 | Baja población |
| 9 | Depresión | Tabasco | mujeres | 0.3492 | mul | 0.05 | 0.1 | Cambio de tendencia |
| 10 | Depresión | Durango | hombres | 0.3416 | add | 0.05 | 1.0 | Serie errática |
| 11 | Depresión | Durango | general | 0.3331 | add | 0.01 | 1.0 | Serie errática |
| 12 | Depresión | Chihuahua | general | 0.3295 | mul | 0.01 | 0.1 | Estacionalidad irregular |
| 13 | Depresión | Chihuahua | mujeres | 0.3267 | mul | 0.01 | 0.5 | Estacionalidad irregular |
| 14 | Depresión | Durango | mujeres | 0.3216 | add | 0.01 | 2.0 | Serie errática |
| 15 | Depresión | Colima | hombres | 0.3147 | mul | 0.01 | 0.1 | Baja población |
| 16 | Depresión | Tabasco | hombres | 0.3092 | add | 0.05 | 0.5 | Cambio de tendencia |
| 17 | Depresión | BCS | mujeres | 0.3052 | mul | 0.01 | 1.0 | Baja población |
| 18 | Depresión | Sonora | general | 0.2761 | mul | 0.01 | 0.5 | Serie volátil |
| 19 | Depresión | Yucatán | general | 0.2771 | add | 0.01 | 0.5 | Variabilidad alta |
| 20 | Depresión | Guerrero | general | 0.2732 | add | 0.01 | 0.1 | Estacionalidad irregular |

**100% de los modelos con RMSE > 0.25 son de Depresión.**

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

### 11.4 Casuística: Baja California Sur — Cero casos de Alzheimer

- **574 semanas de datos (2013-2024): 0 casos de Alzheimer reportados al SINAVE**
- BCS tiene 798,447 habitantes y es el estado menos poblado después de Colima
- Es estadísticamente improbable que no haya habido ningún caso de Alzheimer en 11 años
- **Explicación más probable:** Sub-reporte, ya sea porque:
  - Los casos se reportan bajo otro código CIE-10 (F00, G30.1, etc.)
  - Los pacientes son atendidos en el sector privado o ISSSTE en lugar de IMSS
  - Existen barreras geográficas para el diagnóstico especializado

### 11.5 Casuística: Colima — El outlier universal

Colima aparece entre los 5 peores modelos en **los tres padecimientos**:
- Alzheimer: RMSE 0.148 (peor de todos)
- Depresión: RMSE 0.388 (4to peor)
- Parkinson: RMSE 0.192 (peor de todos)

Con 731,391 habitantes (el estado menos poblado de México), Colima genera series de muy bajo volumen:
- Alzheimer: ~0.9 casos/semana promedio
- Parkinson: ~4.0 casos/semana
- Depresión: ~18 casos/semana

**Cuando el promedio es <5 casos/semana**, la serie se domina por ruido Poisson. Un solo caso más o menos representa un cambio del 20-100% en la tasa, haciendo que Prophet (diseñado para series continuas) tenga dificultad.

### 11.6 Casuística: Puebla — Alta población pero RMSE elevado en Parkinson

Puebla tiene 6.6M habitantes pero un RMSE de Parkinson de 0.146, inusualmente alto para su tamaño. Al revisar los datos:
- La serie de Parkinson en Puebla muestra **irregularidades en 2018-2019** con picos inexplicados
- Posible cambio en la cobertura IMSS o en las prácticas de diagnóstico
- No se observa el mismo patrón en Alzheimer (0.027) ni Depresión (0.245), lo que descarta un problema general de datos

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

### 13.1 Mejora 1: Normalización a tasa por 100K habitantes

**Archivos modificados:**
- `config/modelado.yaml` — flags `normalizar_tasa`, `columna_poblacion`, `tasa_por`
- `src/modelado/prophet.py` — `agrupa()` preserva columna `Total`; `crea_train_test()` calcula tasa
- `scripts/entrena.py` — guarda `poblacion` y `normalizado` en resultados
- `src/modelado/forecast.py` — desnormaliza predicciones

**Impacto:**
- RMSE dejó de estar dominado por el tamaño poblacional
- CDMX (9M hab.) ya no tiene RMSE 10x mayor que Colima (731K hab.)
- Las métricas reflejan la calidad del ajuste, no el volumen de casos

### 13.2 Mejora 2: Log-transform log(1+y)

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

### 13.3 Mejora 3: Modo aditivo en el grid

**Antes:** Solo `multiplicative` en el grid (12 combinaciones).
**Después:** `multiplicative` + `additive` (24 combinaciones).

**Impacto por padecimiento (% de modelos que eligieron aditivo):**
- Alzheimer: 23.2% (aditivo mejora algunos estados pequeños)
- **Depresión: 49.5%** (cerca de mitad y mitad — impacto significativo)
- Parkinson: 28.3%

El modo aditivo es especialmente útil para Depresión porque su estacionalidad se comporta como un **efecto fijo** (X casos más/menos en invierno) en lugar de un **efecto proporcional** (Y% más/menos).

### 13.4 Otras mejoras previas (sesiones anteriores)

| Mejora | Impacto |
|--------|---------|
| Reducción de `fourier_order` de 8 a 5 | Estabilizó L-BFGS, eliminó overfitting estacional |
| Adición de `cp=0.01` al grid | Ahora gana en 59% de modelos |
| Adición de `sp=0.1` al grid | Gana en 35% de modelos (mejor regularización) |
| Fallback automático de L-BFGS | 0 fallos de entrenamiento en esta corrida |
| Holiday de COVID con ventana 913d | Absorbe el impacto pandémico sin contaminar estacionalidad |

---

## 14. Pronósticos Generados

### 14.1 Archivo de salida

- **Ruta:** `forecast/all_forecast.csv`
- **Filas:** 206,118 (297 modelos × 694 filas cada uno)
- **Columnas:** 29 (incluye descomposición Prophet completa)
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
| `meta_padecimiento` | Padecimiento del modelo |
| `meta_entidad` | Estado (vacío para nacional) |
| `meta_modo` | Segmento de sexo (hombres/mujeres/general) |

---

## 15. Sugerencias de Mejora Futura

### 15.1 Alta prioridad / Alto impacto

#### 1. Excluir o marcar series con >90% de ceros
**Problema:** BCS-Alzheimer (100% ceros) y otros estados con <1 caso/semana promedio producen modelos triviales o inútiles.
**Solución:** Implementar un umbral mínimo (e.g., promedio ≥ 1 caso/semana) bajo el cual el modelo no se entrena y se marca como "insuficiente". Alternativamente, agregar flag de "baja confianza" al forecast.
**Impacto estimado:** Elimina modelos espurios, mejora la interpretación.
**Esfuerzo:** Bajo (2-3 horas).

#### 2. Agregar changepoints manuales para cambios de régimen
**Problema:** Nayarit-Depresión tiene un cambio estructural en 2018 que Prophet no puede modelar solo con holidays.
**Solución:** Usar `changepoints` explícitos en Prophet para estados con cambios de régimen detectados, o agregar un holiday de "cambio de régimen" con ventana larga.
**Impacto estimado:** Reducción de RMSE en 5-10 modelos específicos.
**Esfuerzo:** Medio (requiere análisis por estado).

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

### 15.3 Baja prioridad / Mejoras incrementales

#### 7. Fourier order adaptativo
**Problema:** `fourier_order=5` es fijo. Algunos estados con estacionalidad simple podrían usar 3, otros con patrones complejos podrían necesitar 7.
**Solución:** Agregar fourier_order al grid de CV.
**Esfuerzo:** Bajo, pero expande el grid significativamente.

#### 8. Regresores externos dinámicos
**Problema:** Actualmente no se usan regresores externos (la población es constante).
**Solución:** Si se obtienen datos CONAPO (temporales), integrar población como regresor. También explorar: temperatura media, índice de marginación, PIB estatal.
**Esfuerzo:** Alto (requiere fuentes de datos adicionales).

#### 9. Modelos alternativos (benchmark)
**Problema:** No se tiene punto de comparación para saber si Prophet es el mejor modelo.
**Solución:** Implementar baselines (ARIMA/SARIMA, ETS) y comparar RMSE head-to-head con Prophet.
**Esfuerzo:** Medio.

#### 10. Detección automática de outliers en pronóstico
**Problema:** Algunos pronósticos pueden generar valores negativos o implausibles (especialmente con log-transform invertido).
**Solución:** Post-procesamiento que clipea valores negativos a 0 y aplica sanity checks.
**Esfuerzo:** Muy bajo.

### 15.4 Resumen de priorización

| # | Mejora | Impacto | Esfuerzo | Prioridad |
|---|--------|---------|----------|-----------|
| 1 | Excluir/marcar series vacías | Alto | Bajo | **Inmediata** |
| 2 | Changepoints para cambios de régimen | Alto | Medio | **Alta** |
| 3 | Población temporal CONAPO | Medio | Medio | **Alta** |
| 4 | Grid por padecimiento | Medio | Bajo | **Media** |
| 5 | Métricas adicionales en CV | Medio | Bajo | **Media** |
| 6 | Ensamble por región | Alto | Alto | **Media** |
| 7 | Fourier order adaptativo | Bajo | Bajo | Baja |
| 8 | Regresores dinámicos | Medio | Alto | Baja |
| 9 | Modelos alternativos (benchmark) | Medio | Medio | Baja |
| 10 | Clip de pronósticos negativos | Bajo | Muy bajo | Baja |

---

## 16. Anexos

### Anexo A: Tiempos de ejecución

| Fase | Inicio | Fin | Duración |
|------|--------|-----|----------|
| Alzheimer (99 modelos) | 09:44:50 | 11:03:12 | 78 min |
| Depresión (99 modelos) | 11:03:12 | 12:28:19 | 85 min |
| Parkinson (99 modelos) | 12:28:19 | 13:50:34 | 82 min |
| **Entrenamiento total** | **09:44:50** | **13:50:34** | **4h 6min** |
| Predicción (297 modelos) | 14:17:44 | 14:18:29 | 45 seg |

Tiempo promedio por modelo: ~49.6 segundos (incluye CV con 24 combinaciones × 4 folds = 96 fits).

### Anexo B: Estructura de archivos generados

```
models/
├── Alzheimer/
│   ├── Prophet_Alzheimer_completo.csv          # Resultados (99 filas)
│   ├── Prophet_Alzheimer_hombres.pkl           # Modelo nacional hombres
│   ├── Prophet_Alzheimer_hombres.csv           # Datos train (sidecar)
│   ├── Prophet_Alzheimer_mujeres.pkl
│   ├── Prophet_Alzheimer_mujeres.csv
│   ├── Prophet_Alzheimer_general.pkl
│   ├── Prophet_Alzheimer_general.csv
│   ├── Prophet_Alzheimer_Aguascalientes_hombres.pkl
│   ├── Prophet_Alzheimer_Aguascalientes_hombres.csv
│   └── ... (32 estados × 3 sexos = 96 pares .pkl/.csv)
├── Depresion/
│   └── ... (misma estructura)
└── Parkinson/
    └── ... (misma estructura)

forecast/
└── all_forecast.csv                            # 206,118 filas
```

### Anexo C: Columnas del CSV de entrenamiento (sidecar)

| Columna | Descripción |
|---------|-------------|
| `ds` | Fecha (lunes de cada semana) |
| `y` | Target en espacio log-tasa (lo que Prophet ve) |
| `Total` | Población del estado/nacional (para desnormalizar) |
| `y_original` | Conteo absoluto original (para referencia) |

### Anexo D: Configuración YAML completa

**`config/modelado.yaml`:**
```yaml
normalizar_tasa: true
columna_poblacion: "Total"
tasa_por: 100000
log_transform: true

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

# 4. Entrenar 297 modelos (~4 horas)
make train

# 5. Generar predicciones
make predict

# 6. Sincronizar artefactos
make data-push && make s3-sync
```

**Commit de referencia:** `905dd76` — "feat: log-transform + additive mode para mejorar Depresión"

---

*Reporte generado el 20 de febrero de 2026 como parte del proyecto EpiForecast-MX.*
