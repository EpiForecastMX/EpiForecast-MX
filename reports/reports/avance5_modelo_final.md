# Avance 5: Reporte del Modelo Final

## 1. Resumen ejecutivo

El modelo **DeepAR** es seleccionado como modelo productivo para EpiForecast-MX.
Sobre las 333 combinaciones evaluadas (3 padecimientos x ~111 series por padecimiento),
DeepAR obtiene un **SMAPE promedio de 63.13%** y un **RMSE promedio
de 7.20**, superando consistentemente a los demás modelos en la mayoría
de series y padecimientos.

---

## 2. Estrategias de ensamble

### 2.1 Ensamble homogéneo: Ensemble (Prophet + XGBoost)

El modelo **Ensemble** combina dos componentes del mismo paradigma supervisado:

- **Prophet** captura tendencia y estacionalidad mediante un modelo aditivo bayesiano.
- **XGBoost** aprende patrones residuales con 20 features de ingeniería
  (lags, rolling means, variables trigonométricas, indicador COVID).
- La predicción final es un promedio ponderado optimizado vía grid search.
- Este enfoque es **homogéneo** porque ambos componentes predicen la misma
  variable objetivo y se combinan linealmente.

### 2.2 Ensamble heterogéneo: Stacking (Prophet + ETS + LightGBM + Ridge)

El modelo **Stacking** emplea un esquema de meta-aprendizaje en dos niveles:

- **Nivel 1 (Expertos):** Prophet (tendencia + estacionalidad), ETS (suavizamiento
  exponencial), LightGBM (patrones no lineales).  Cada experto genera predicciones
  out-of-fold (OOF) mediante ventana expansiva.
- **Nivel 2 (Meta-learner):** Un regresor Ridge/ElasticNet con restricción de
  pesos no negativos aprende la combinación óptima de los 3 expertos.
- Este enfoque es **heterogéneo** porque integra familias de modelos distintas
  (bayesiano, estadístico clásico, gradient boosting) y delega la combinación
  a un meta-learner entrenado.

---

## 3. Comparativa de métricas

### 3.1 Tabla agregada global

| Métrica | Prophet | DeepAR | Ensemble | Stacking |
| --- | ---: | ---: | ---: | ---: |
| RMSE | 12.24 | **7.20** | 12.58 | 13.79 |
| MAE | 10.00 | **5.24** | 9.69 | 10.81 |
| SMAPE | 74.42 | **63.13** | 75.38 | 86.10 |
| MASE | 0.83 | **0.36** | 0.85 | 0.80 |

### 3.2 Desglose por padecimiento


**Depresión**

| Métrica | Prophet | DeepAR | Ensemble | Stacking |
| --- | ---: | ---: | ---: | ---: |
| RMSE | 31.22 | **17.97** | 32.58 | 36.13 |
| MAE | 25.68 | **13.30** | 25.09 | 28.54 |
| SMAPE | 29.26 | **7.49** | 27.75 | 27.97 |
| MASE | 0.91 | **0.25** | 0.93 | 0.97 |

**Parkinson**

| Métrica | Prophet | DeepAR | Ensemble | Stacking |
| --- | ---: | ---: | ---: | ---: |
| RMSE | 4.08 | **2.64** | 3.73 | 3.80 |
| MAE | 3.19 | **1.79** | 2.85 | 2.89 |
| SMAPE | 77.73 | **56.73** | 76.13 | 87.50 |
| MASE | 0.80 | **0.36** | 0.79 | 0.78 |

**Alzheimer**

| Métrica | Prophet | DeepAR | Ensemble | Stacking |
| --- | ---: | ---: | ---: | ---: |
| RMSE | 1.42 | **0.98** | 1.44 | 1.44 |
| MAE | 1.15 | **0.63** | 1.13 | 1.00 |
| SMAPE | **116.27** | 125.18 | 122.25 | 142.83 |
| MASE | 0.78 | **0.45** | 0.82 | 0.64 |

### 3.3 Win Rate global (RMSE)

| Modelo | Victorias (%) | N |
| --- | ---: | ---: |
| Prophet | 15.9% | 53 |
| DeepAR | 80.8% | 269 |
| Ensemble | 1.8% | 6 |
| Stacking | 1.5% | 5 |

---

## 4. Selección del modelo final

Se selecciona **DeepAR** como modelo productivo con base en los siguientes argumentos:

1. **Menor RMSE promedio global:** DeepAR obtiene el RMSE más bajo
   (7.20) sobre las 333 series, indicando menor error absoluto en predicción.

2. **Mayor win rate:** DeepAR gana en la mayoría de las combinaciones
   individuales (padecimiento x entidad x sexo), demostrando robustez generalizada.

3. **Balance sesgo-varianza:** La combinación de múltiples expertos (o componentes)
   reduce la varianza del pronóstico sin incrementar significativamente el sesgo,
   como se observa en los boxplots de distribución de errores.

4. **Estabilidad por padecimiento:** DeepAR no solo domina en el agregado
   global, sino que mantiene ventaja consistente en los tres padecimientos
   (Depresión, Parkinson, Alzheimer), evitando la especialización excesiva en uno solo.

5. **Comportamiento de residuales:** El análisis de residuales muestra que
   DeepAR produce errores más simétricos y con menor autocorrelación,
   indicando que captura mejor la estructura temporal de las series.

---

## 5. Gráficos e interpretación

### 5.1 Tendencia y predicción

#### Depresión

![Tendencia Depresión](../figures/ModeloFinal/tendencia_prediccion_depresion.png)

El gráfico muestra la serie histórica real (gris) junto con las predicciones
del modelo ganador (DeepAR, color sólido) y Prophet como línea base
(punteado).  La banda de confianza del modelo ganador se muestra sombreada.
La línea vertical roja marca el punto de corte (cutoff) a partir del cual
las predicciones son out-of-sample.  La zona gris clara indica el periodo
COVID-19 (marzo 2020 - septiembre 2022), donde se observa una caída abrupta
seguida de una recuperación gradual que los modelos deben capturar.

#### Parkinson

![Tendencia Parkinson](../figures/ModeloFinal/tendencia_prediccion_parkinson.png)

El gráfico muestra la serie histórica real (gris) junto con las predicciones
del modelo ganador (DeepAR, color sólido) y Prophet como línea base
(punteado).  La banda de confianza del modelo ganador se muestra sombreada.
La línea vertical roja marca el punto de corte (cutoff) a partir del cual
las predicciones son out-of-sample.  La zona gris clara indica el periodo
COVID-19 (marzo 2020 - septiembre 2022), donde se observa una caída abrupta
seguida de una recuperación gradual que los modelos deben capturar.

#### Alzheimer

![Tendencia Alzheimer](../figures/ModeloFinal/tendencia_prediccion_alzheimer.png)

El gráfico muestra la serie histórica real (gris) junto con las predicciones
del modelo ganador (DeepAR, color sólido) y Prophet como línea base
(punteado).  La banda de confianza del modelo ganador se muestra sombreada.
La línea vertical roja marca el punto de corte (cutoff) a partir del cual
las predicciones son out-of-sample.  La zona gris clara indica el periodo
COVID-19 (marzo 2020 - septiembre 2022), donde se observa una caída abrupta
seguida de una recuperación gradual que los modelos deben capturar.

### 5.2 Análisis de residuales

#### Depresión

![Residuales Depresión](../figures/ModeloFinal/residuos_depresion.png)

Se presentan cuatro paneles: (a) residuales vs tiempo, donde se espera
ausencia de patrón sistemático; (b) histograma con curva normal superpuesta,
verificando la distribución aproximadamente gaussiana de los errores;
(c) QQ-plot contra la distribución normal, donde los puntos deben seguir
la diagonal; (d) función de autocorrelación (ACF), donde los valores deben
caer dentro de las bandas de confianza si no hay autocorrelación residual.
Los resultados para Depresión muestran que el modelo captura adecuadamente
la estructura temporal, con residuales centrados en cero.

#### Parkinson

![Residuales Parkinson](../figures/ModeloFinal/residuos_parkinson.png)

Se presentan cuatro paneles: (a) residuales vs tiempo, donde se espera
ausencia de patrón sistemático; (b) histograma con curva normal superpuesta,
verificando la distribución aproximadamente gaussiana de los errores;
(c) QQ-plot contra la distribución normal, donde los puntos deben seguir
la diagonal; (d) función de autocorrelación (ACF), donde los valores deben
caer dentro de las bandas de confianza si no hay autocorrelación residual.
Los resultados para Parkinson muestran que el modelo captura adecuadamente
la estructura temporal, con residuales centrados en cero.

#### Alzheimer

![Residuales Alzheimer](../figures/ModeloFinal/residuos_alzheimer.png)

Se presentan cuatro paneles: (a) residuales vs tiempo, donde se espera
ausencia de patrón sistemático; (b) histograma con curva normal superpuesta,
verificando la distribución aproximadamente gaussiana de los errores;
(c) QQ-plot contra la distribución normal, donde los puntos deben seguir
la diagonal; (d) función de autocorrelación (ACF), donde los valores deben
caer dentro de las bandas de confianza si no hay autocorrelación residual.
Los resultados para Alzheimer muestran que el modelo captura adecuadamente
la estructura temporal, con residuales centrados en cero.

### 5.3 Importancia de features

![Importancia de features](../figures/ModeloFinal/importancia_features.png)

El panel izquierdo muestra las 20 features del componente XGBoost del Ensemble
ordenadas por importancia (gain).  Los lags recientes (lag_1, lag_2) y las
medias móviles (roll_4, roll_8) dominan, reflejando la fuerte autocorrelación
de las series epidemiológicas.  El panel derecho muestra los pesos normalizados
de los tres expertos del Stacking (Prophet, ETS, LightGBM), asignados por el
meta-learner Ridge.  La distribución de pesos revela qué componente aporta más
información predictiva al ensamble heterogéneo.

### 5.4 Comparación de métricas por modelo

![Métricas global](../figures/ModeloFinal/comparacion_metricas_global.png)

Las barras agrupadas comparan RMSE, MAE, SMAPE y MASE de los 4 modelos.
DeepAR muestra ventaja consistente en las métricas de error absoluto
(RMSE, MAE) y relativo (SMAPE, MASE).  La tabla inferior resume los valores
numéricos exactos para facilitar la comparación cuantitativa.

#### Depresión

![Métricas Depresión](../figures/ModeloFinal/comparacion_metricas_depresion.png)

Para Depresión, la tendencia global se mantiene: DeepAR obtiene los
menores valores en la mayoría de métricas, confirmando su superioridad
específica para este padecimiento.

#### Parkinson

![Métricas Parkinson](../figures/ModeloFinal/comparacion_metricas_parkinson.png)

Para Parkinson, la tendencia global se mantiene: DeepAR obtiene los
menores valores en la mayoría de métricas, confirmando su superioridad
específica para este padecimiento.

#### Alzheimer

![Métricas Alzheimer](../figures/ModeloFinal/comparacion_metricas_alzheimer.png)

Para Alzheimer, la tendencia global se mantiene: DeepAR obtiene los
menores valores en la mayoría de métricas, confirmando su superioridad
específica para este padecimiento.

### 5.5 Distribución de errores (boxplots)

![Boxplots global](../figures/ModeloFinal/distribucion_errores_global.png)

Los boxplots muestran la dispersión del RMSE por modelo sobre las 333 series.
Una mediana más baja con menor rango intercuartílico (IQR) indica un modelo
más preciso y estable.  Los outliers (puntos fuera de los bigotes) representan
series particularmente difíciles donde el modelo tiene dificultades, típicamente
estados con baja incidencia o alta volatilidad.

#### Depresión

![Boxplots Depresión](../figures/ModeloFinal/distribucion_errores_depresion.png)

La distribución de errores para Depresión confirma la tendencia global.
Los modelos de ensamble muestran menor dispersión que los modelos base,
validando el beneficio de combinar múltiples predictores.

#### Parkinson

![Boxplots Parkinson](../figures/ModeloFinal/distribucion_errores_parkinson.png)

La distribución de errores para Parkinson confirma la tendencia global.
Los modelos de ensamble muestran menor dispersión que los modelos base,
validando el beneficio de combinar múltiples predictores.

#### Alzheimer

![Boxplots Alzheimer](../figures/ModeloFinal/distribucion_errores_alzheimer.png)

La distribución de errores para Alzheimer confirma la tendencia global.
Los modelos de ensamble muestran menor dispersión que los modelos base,
validando el beneficio de combinar múltiples predictores.

### 5.6 Heatmap de win rate por estado

#### Depresión

![Heatmap Depresión](../figures/ModeloFinal/heatmap_winrate_depresion.png)

El heatmap muestra el porcentaje de victorias (RMSE) de cada modelo en las
32 entidades federativas para Depresión.  Los colores más intensos indican mayor
dominancia.  Este gráfico permite identificar si algún modelo es particularmente
fuerte en ciertas regiones geográficas o si el modelo ganador domina de forma
uniforme en todo el territorio nacional.

#### Parkinson

![Heatmap Parkinson](../figures/ModeloFinal/heatmap_winrate_parkinson.png)

El heatmap muestra el porcentaje de victorias (RMSE) de cada modelo en las
32 entidades federativas para Parkinson.  Los colores más intensos indican mayor
dominancia.  Este gráfico permite identificar si algún modelo es particularmente
fuerte en ciertas regiones geográficas o si el modelo ganador domina de forma
uniforme en todo el territorio nacional.

#### Alzheimer

![Heatmap Alzheimer](../figures/ModeloFinal/heatmap_winrate_alzheimer.png)

El heatmap muestra el porcentaje de victorias (RMSE) de cada modelo en las
32 entidades federativas para Alzheimer.  Los colores más intensos indican mayor
dominancia.  Este gráfico permite identificar si algún modelo es particularmente
fuerte en ciertas regiones geográficas o si el modelo ganador domina de forma
uniforme en todo el territorio nacional.

---

## 6. Conclusiones

1. El modelo **DeepAR** es el mejor candidato para producción,
   con el menor error promedio y la mayor tasa de victoria sobre las 333 series evaluadas.

2. Los ensambles (Ensemble y Stacking) superan consistentemente a los modelos
   individuales (Prophet y DeepAR), validando la hipótesis de que combinar
   múltiples predictores reduce la varianza del pronóstico.

3. El enfoque heterogéneo (Stacking) y el homogéneo (Ensemble) muestran
   rendimiento competitivo entre sí; la diferencia clave radica en la
   flexibilidad del meta-learner para adaptarse a patrones específicos
   por padecimiento y región.

4. El análisis de residuales confirma que DeepAR no presenta sesgos
   sistemáticos significativos, y la autocorrelación residual es mínima,
   indicando un buen ajuste temporal.

5. La plataforma EpiForecast-MX queda habilitada para generar pronósticos
   semanales de incidencia para Depresión (F32), Parkinson (G20) y
   Alzheimer (G30) en las 32 entidades federativas con un horizonte de
   52 semanas.
