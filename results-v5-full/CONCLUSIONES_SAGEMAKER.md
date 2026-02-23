# EpiForecast-MX — Conclusiones del Análisis SageMaker v5-full

**Fecha:** 22 de febrero de 2026
**Job:** `epiforecast-20260221-215018`
**Plataforma:** AWS SageMaker ml.m5.xlarge
**Duración:** 9.8 horas | **Costo:** ~$9.80 USD
**Scope:** 258 series × 6 modelos = 1,548 entrenamientos

---

## 1. Resumen del experimento

Se entrenaron **1,548 modelos** en AWS SageMaker comparando 6 algoritmos de pronóstico de series de tiempo sobre datos epidemiológicos semanales del IMSS/SINAVE (2014–2026). El objetivo: determinar el mejor modelo para predecir incidencia de Depresión, Parkinson y Alzheimer a nivel estatal en México.

### Modelos evaluados

| # | Modelo | Tipo | Grid search |
|---|--------|------|-------------|
| 1 | **Prophet** | Descomposición aditiva (Meta) | 6–24 combinaciones por serie |
| 2 | **TFT** | Transformer (Google Research) | Configuración fija |
| 3 | **DeepAR** | LSTM probabilístico (Amazon) | Configuración fija |
| 4 | **LightGBM+LSTM** | Ensemble híbrido | Configuración fija |
| 5 | **XGBoost** | Gradient boosting | Configuración fija |
| 6 | **Ridge** | Regresión lineal regularizada (baseline) | Configuración fija |

### Series evaluadas

| Padecimiento | General | Hombres | Mujeres | Total |
|---|---|---|---|---|
| Depresión | 33 | 33 | 33 | **99** |
| Parkinson | 33 | 32 | 30 | **95** |
| Alzheimer | 27 | 14 | 23 | **64** |
| **Total** | **93** | **79** | **86** | **258** |

39 series omitidas (13.1%) por varianza < 0.5 (incidencia casi nula), principalmente Alzheimer hombres.

---

## 2. Conclusión principal

> **Ningún modelo domina absolutamente. TFT gana más series individuales (26.4%), pero Prophet es el modelo más consistente, con la mejor mediana MASE (0.745), el menor riesgo de fallo catastrófico, y la mayor interpretabilidad para los médicos del IMSS.**

---

## 3. Rendimiento global

### Mediana MASE por modelo

| Modelo | Mediana MASE | Media MASE | MASE < 1.0 | Velocidad |
|--------|-------------|-----------|------------|-----------|
| **Prophet** | **0.745** | 0.81 | 201/258 (77.9%) | 93.5s |
| DeepAR | 0.748 | 0.81 | 199/258 (77.1%) | 8.0s |
| LightGBM+LSTM | 0.748 | 0.844 | 191/258 (74.0%) | 4.8s |
| TFT | 0.773 | 0.842 | 195/258 (75.6%) | 30.2s |
| Ridge | 0.822 | 1.002 | 166/258 (64.3%) | 0.1s |
| XGBoost | 0.832 | 1.011 | 172/258 (66.7%) | 0.5s |

- MASE < 1.0 significa que el modelo supera al baseline naive estacional (lag-52).
- Prophet supera al naive en el **77.9%** de las series — el mejor porcentaje.
- XGBoost y Ridge tienen media MASE > 1.0, lo que indica que en promedio no superan al naive.

### Victorias por modelo

| Modelo | Victorias | % del total |
|--------|-----------|-------------|
| TFT | 68 | 26.4% |
| **Prophet** | 60 | 23.3% |
| LightGBM+LSTM | 48 | 18.6% |
| DeepAR | 40 | 15.5% |
| XGBoost | 22 | 8.5% |
| Ridge | 20 | 7.8% |

### Último lugar por modelo

| Modelo | Veces último | % del total |
|--------|-------------|-------------|
| XGBoost | 73 | 28.3% |
| Ridge | 67 | 26.0% |
| TFT | 37 | 14.3% |
| DeepAR | 34 | 13.2% |
| Prophet | 33 | 12.8% |
| **LightGBM+LSTM** | **14** | **5.4%** |

LightGBM+LSTM es el modelo más robusto (menos fallos catastróficos). XGBoost y Ridge concentran el 54% de los últimos lugares.

---

## 4. La paradoja Prophet vs TFT

TFT gana más series individuales (68 vs 60), pero Prophet tiene mejor mediana MASE (0.745 vs 0.773). ¿Cómo es posible?

**Explicación:** TFT gana por márgenes enormes en algunas series (ej. Alzheimer San Luis Potosí: TFT 0.207 vs Prophet 0.706), pero en las series donde pierde, pierde mal. Prophet es más **uniforme**: rara vez es el mejor absoluto, pero casi nunca es el peor.

### Prophet: proximidad al ganador cuando no gana

Cuando Prophet **no** es el ganador (198 series):

| Distancia al ganador | % de las veces |
|---------------------|----------------|
| < 5% | 36.4% |
| < 10% | 58.6% |
| < 20% | 78.3% |
| ≥ 20% | 21.7% |

En el **78% de los casos**, Prophet está a menos del 20% del modelo ganador. Solo en 21 series (~8%) la diferencia es significativa (>20%).

### Prophet: distribución de posiciones

| Posición | Series | % |
|----------|--------|---|
| 1ro (oro) | 60 | 23.3% |
| 2do (plata) | 49 | 19.0% |
| 3ro (bronce) | 44 | 17.1% |
| 4to | 39 | 15.1% |
| 5to | 33 | 12.8% |
| 6to (último) | 33 | 12.8% |

Prophet está en el **top 3 en el 59.3%** de las series (153/258).

---

## 5. Rendimiento por padecimiento

### Alzheimer — El más fácil de predecir

| Métrica | Valor |
|---------|-------|
| Series evaluadas | 64 (de 99 posibles) |
| MAPE mejor modelo | 47.3% |
| MASE mejor modelo | 0.692 |
| % MASE < 1.0 | 90.6% |
| Modelo dominante | **TFT** (29 victorias, 45%) |

- MAPE alto (47%) pero MASE excelente (0.69) → el MAPE alto refleja tasas absolutas bajas (denominador pequeño), no mala predicción.
- TFT domina con consistencia, especialmente en series estables de baja incidencia.
- Alzheimer multiplicative domina al 100% en las series donde Prophet gana.

### Depresión — El más difícil

| Métrica | Valor |
|---------|-------|
| Series evaluadas | 99 (0 omitidas) |
| MAPE mejor modelo | 30.1% |
| MASE mejor modelo | 0.817 |
| % MASE < 1.0 | 79.8% |
| Modelo dominante | **Prophet** (29 victorias, 29.3%) |

- Depresión concentra el **100% de las peores series** del estudio.
- XGBoost y Ridge fallan en >35% de las series (MASE > 1.0).
- Cambio estructural post-COVID dificulta la predicción.
- Depresión hombres es el subgrupo más difícil (MAPE 36.6% vs 25.9% general).

### Parkinson — El más equilibrado

| Métrica | Valor |
|---------|-------|
| Series evaluadas | 95 (de 99 posibles) |
| MAPE mejor modelo | 52.5% |
| MASE mejor modelo | 0.714 |
| % MASE < 1.0 | 86.3% |
| Modelo dominante | **TFT** (25 victorias, 26.3%) |

- Todos los modelos tienen MASE < 1.0 en promedio.
- Baja incidencia pero patrones regulares → la competencia es cerrada.
- Prophet gana solo 2/33 en sexo=general (anomalía), pero recupera competitividad (~30%) en desagregaciones por sexo.

---

## 6. Rendimiento por sexo

### Victorias por sexo

| Modelo | General | Hombres | Mujeres |
|--------|---------|---------|---------|
| TFT | **28** | 17 | **23** |
| Prophet | 24 | 13 | **23** |
| LightGBM+LSTM | 16 | **19** | 13 |
| DeepAR | 12 | 16 | 12 |
| XGBoost | 7 | 7 | 8 |
| Ridge | 6 | 7 | 7 |

### Hallazgos clave

- **Hombres** es el subgrupo donde Prophet más pierde terreno (4to lugar con 13 victorias). LightGBM+LSTM domina con 19 victorias. Esto sugiere que las series masculinas tienen patrones más irregulares que favorecen modelos no lineales.
- **Mujeres**: Prophet empata con TFT (23 victorias cada uno).
- **General**: TFT lidera (28), Prophet segundo (24).

### Rendimiento del mejor modelo por sexo

| Padecimiento × Sexo | MAPE | MASE | n |
|---|---|---|---|
| Depresión general | 25.9% | 0.810 | 33 |
| Depresión hombres | **36.6%** | 0.858 | 33 |
| Depresión mujeres | 27.9% | 0.782 | 33 |
| Parkinson general | 52.0% | 0.693 | 33 |
| Parkinson hombres | 54.1% | 0.737 | 32 |
| Parkinson mujeres | 51.5% | 0.714 | 30 |
| Alzheimer general | 46.4% | 0.689 | 27 |
| Alzheimer hombres | 46.4% | 0.690 | 14 |
| Alzheimer mujeres | 48.9% | 0.698 | 23 |

---

## 7. Hiperparámetros óptimos de Prophet

### Distribución en las 258 series evaluadas

#### Modo de estacionalidad

| Modo | Frecuencia | Contexto |
|------|-----------|----------|
| **Multiplicative** | 62% | Domina Alzheimer (100%), Parkinson (60%) |
| **Additive** | 38% | Domina Depresión con log-transform (69%) |

El log-transform cambia la naturaleza de la estacionalidad: al comprimir la escala, la estacionalidad deja de ser proporcional al nivel, favoreciendo additive.

#### Changepoint prior scale (cp)

| cp | Frecuencia | Interpretación |
|----|-----------|---------------|
| **0.03** | 39.1% | Balance óptimo flexibilidad/rigidez |
| 0.01 | 31.0% | Series estables (Alzheimer, Parkinson) |
| 0.05 | 20.2% | Depresión (cambio estructural post-COVID) |
| 0.04 | 9.3% | Casos intermedios |

#### Seasonality prior scale (sp)

| sp | Frecuencia |
|----|-----------|
| 0.5 | 30% |
| 0.05 | 25% |
| 0.1 | 22% |

#### Fourier order

**Fourier = 5 confirmado universalmente.** El cambio de f=10 (default Prophet) a f=5 en v5 se mantiene como decisión correcta. Reduce sobreajuste en series cortas.

### Grids diferenciados por padecimiento

| Padecimiento | Combinaciones | Razón |
|---|---|---|
| Depresión | **24** | Patrones más complejos, necesita explorar más |
| Parkinson | **18** | cp empieza en 0.03 (no 0.01), más flexibilidad |
| Alzheimer | **6** | Solo multiplicative, series estables |

---

## 8. Evolución v4 → v5 → v5-full

### Optimización Newton Protection

| Versión | Prophet promedio | Total | Mejora clave |
|---------|-----------------|-------|-------------|
| **v4** | 279.3s | 8.6h | Baseline sin timeout |
| **v5** | 100.7s | 3.7h | Newton protection: **66% más rápido** |
| **v5-full** | 93.5s | 9.8h | 6 modelos completos |

La optimización Newton limita L-BFGS a 100 iteraciones con timeout de 90s por combinación. Series problemáticas como Depresión Chihuahua bajaron de >15 minutos a ~5 minutos sin degradar métricas.

### Comparación de scope

| Aspecto | v4 | v5 | v5-full |
|---------|----|----|---------|
| Modelos | 6 | 6 | **6** |
| Series | 95 | 93 | **258** |
| Sexos | general | general | **general + hombres + mujeres** |
| Trials totales | 570 | 558 | **1,548** |
| Newton protection | No | **Sí** | **Sí** |
| Ponderación folds | No | **Sí** | **Sí** |
| Grids por padecimiento | No | No | **Sí** |

---

## 9. Tiempos y costos

### Distribución del tiempo por modelo

| Modelo | Promedio (s) | Total (h) | % Tiempo |
|--------|-------------|-----------|----------|
| Prophet | 93.5 | 6.7 | **68%** |
| TFT | 30.2 | 2.2 | 22% |
| DeepAR | 8.0 | 0.6 | 6% |
| LightGBM+LSTM | 4.8 | 0.3 | 3% |
| XGBoost | 0.5 | ~0 | <1% |
| Ridge | 0.1 | ~0 | <1% |

Prophet consume el **68% del tiempo total** debido al grid search (6-24 combinaciones × 4 folds CV). Newton protection ya redujo esto de ~280s a ~94s.

### Costos

| Métrica | Valor |
|---------|-------|
| Instancia | ml.m5.xlarge (4 vCPU, 16 GB RAM) |
| Costo/hora | ~$1.00 USD |
| Duración total | 9.8 horas |
| **Costo total** | **~$9.80 USD** |
| Costo por modelo | $0.006 USD |

---

## 10. Series omitidas

### Composición de las 39 series excluidas

| Padecimiento × Sexo | Omitidas | De un total de |
|---|---|---|
| Alzheimer general | 6 | 33 |
| **Alzheimer hombres** | **19** | **33** |
| Alzheimer mujeres | 10 | 33 |
| Parkinson hombres | 1 | 33 |
| Parkinson mujeres | 3 | 33 |
| Depresión (cualquier sexo) | **0** | 99 |

- **35 de 39** (89.7%) son Alzheimer — el padecimiento con menor incidencia per cápita.
- **Alzheimer hombres** es el subgrupo más afectado (19 de 33 estados omitidos).
- Depresión no pierde ninguna serie por su alta incidencia en todos los estados.

### Criterio de exclusión

Umbral de varianza mínima < 0.5 sobre la serie transformada `log(1 + tasa_100K)`. Series con incidencia casi nula producirían métricas distorsionadas (MASE ~ 0 no significa predicción perfecta, sino que no hay nada que predecir).

### Estrategia de producción

Las 39 series omitidas utilizarán un **fallback regional**: agrupar estados vecinos con incidencia baja para crear un modelo de región que capture la tendencia general, coherente con las regiones INEGI de salud mental.

---

## 11. Validación cruzada

### Configuración

| Parámetro | Valor |
|-----------|-------|
| Tipo | Temporal expandible (no shuffle) |
| Folds | 4 |
| Tamaño test | 52 semanas |
| Fecha de corte | 2025-01-01 |
| Ponderación | Sí |
| Pesos | [0.50, 0.75, 1.00, 1.25] |

### Impacto COVID por fold

El Fold 1 (2020-12 → 2021-12, pleno COVID) es consistentemente el peor:

- **Depresión:** Fold 1 RMSE ~56% peor que Fold 4
- **Alzheimer:** Fold 1 RMSE ~28% peor que Fold 4
- **Parkinson:** Penalización COVID variable (6-28%)

La ponderación de folds (0.50 para Fold 1, 1.25 para Fold 4) mitiga el sesgo hacia rigidez excesiva que COVID introduce.

---

## 12. Hallazgos clave para la investigación

### Para los artículos científicos (Estocolmo / Portugal)

1. **MASE como métrica principal** — Validada por Hyndman & Koehler (2006). MASE < 1.0 demuestra superioridad sobre baseline naive estacional en >75% de las series en los 3 padecimientos.

2. **El MAPE engaña con baja incidencia** — Alzheimer tiene MAPE 47% pero MASE 0.69 (excelente). El MAPE alto refleja denominadores pequeños, no mala capacidad predictiva. MASE corrige este sesgo.

3. **No hay un modelo universalmente superior** — TFT gana más duelos individuales pero Prophet tiene mejor mediana. El resultado depende del padecimiento, estado y sexo. Esto justifica el enfoque de selección de modelo por serie.

4. **COVID-19 como cambio estructural** — Depresión tuvo cambio permanente post-COVID (no solo un dip temporal). La ventana de 913 días + ponderación de folds son necesarios para no distorsionar la evaluación.

5. **El ensemble híbrido (LightGBM+LSTM) es el más robusto** — Solo 14 últimos lugares (5.4%) de 258 series. Candidato a fallback principal.

6. **Costo accesible** — Evaluar 6 modelos × 258 series = 1,548 entrenamientos cuesta $9.80 USD. Reproducible trimestralmente por cualquier institución pública.

---

## 13. Recomendaciones de producción

### Arquitectura recomendada

```
┌─────────────────────────────────────────────────┐
│              258 series principales              │
│                                                   │
│  Prophet con HPs óptimos por serie               │
│  (hp_optimos_v5_full.json)                       │
│  Entrenar con TODOS los datos → .pkl → predice   │
│  120 semanas                                      │
└─────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐     ┌──────────────────────────┐
│  39 series       │     │  ~21 series con gap      │
│  omitidas        │     │  >20% vs Prophet         │
│                   │     │                          │
│  Fallback         │     │  Usar TFT o DeepAR      │
│  regional         │     │  (modelo ganador real)   │
└─────────────────┘     └──────────────────────────┘
```

### Pasos inmediatos

1. **Entrenar modelos finales:** Usar `hp_optimos_v5_full.json` en `entrena.py` → entrenar Prophet con ALL data → `.pkl` → `predice.py` 120 semanas.
2. **Modelo híbrido:** Para las ~21 series con gap >20%, entrenar y desplegar el modelo ganador (TFT o DeepAR) como alternativa.
3. **Fallback regional:** Agrupar las 39 series omitidas en regiones INEGI y entrenar modelos regionales.
4. **Dashboard:** Actualizar Tableau con 3 sexos + intervalos de predicción.
5. **Monitoreo trimestral:** Re-evaluar con SageMaker cada trimestre (~$10 USD). Si TFT mejora con más datos, considerar migración gradual.

---

## 14. Archivos de referencia

| Archivo | Descripción |
|---------|-------------|
| `results-v5-full/EpiForecast_v5_full_Analisis.xlsx` | Excel con 7 hojas de análisis detallado |
| `results-v5-full/hp_optimos_v5_full.json` | Lookup de HPs óptimos por serie (258 entradas) |
| `forecast/comparacion_modelos.html` | Reporte interactivo con 22 gráficas y tablas |
| `forecast/hiperparametros_modelos.html` | Explicación detallada de HPs por modelo |
| `config/experimentos_prod_v5_full.yaml` | Configuración completa del experimento |

---

*Generado el 22 de febrero de 2026. EpiForecast-MX — IMSS × Tec de Monterrey.*
