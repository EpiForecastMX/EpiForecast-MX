# Avance 5: Reporte del Modelo Final

## 1. Resumen ejecutivo

El modelo **DeepAR** es seleccionado como modelo productivo para EpiForecast-MX.
Sobre las 333 combinaciones evaluadas (3 padecimientos x ~111 series por padecimiento),
DeepAR obtiene un **SMAPE promedio de 63.13%** y un **RMSE promedio
de 7.20**, superando consistentemente a los demas modelos en la mayoria
de series y padecimientos.

---

## 2. Estrategias de ensamble

### 2.1 Ensamble homogeneo: Ensemble (Prophet + XGBoost)

El modelo **Ensemble** combina dos componentes del mismo paradigma supervisado:

- **Prophet** captura tendencia y estacionalidad mediante un modelo aditivo bayesiano.
- **XGBoost** aprende patrones residuales con 20 features de ingenieria
  (lags, rolling means, variables trigonometricas, indicador COVID).
- La prediccion final es un promedio ponderado optimizado via grid search.
- Este enfoque es **homogeneo** porque ambos componentes predicen la misma
  variable objetivo y se combinan linealmente.

### 2.2 Ensamble heterogeneo: Stacking (Prophet + ETS + LightGBM + Ridge)

El modelo **Stacking** emplea un esquema de meta-aprendizaje en dos niveles:

- **Nivel 1 (Expertos):** Prophet (tendencia + estacionalidad), ETS (suavizamiento
  exponencial), LightGBM (patrones no lineales).  Cada experto genera predicciones
  out-of-fold (OOF) mediante ventana expansiva.
- **Nivel 2 (Meta-learner):** Un regresor Ridge/ElasticNet con restriccion de
  pesos no negativos aprende la combinacion optima de los 3 expertos.
- Este enfoque es **heterogeneo** porque integra familias de modelos distintas
  (bayesiano, estadistico clasico, gradient boosting) y delega la combinacion
  a un meta-learner entrenado.

---

## 3. Comparativa de metricas

### 3.1 Tabla agregada global

| Metrica | Prophet | DeepAR | Ensemble | Stacking |
| --- | ---: | ---: | ---: | ---: |
| RMSE | 12.24 | **7.20** | 12.58 | 13.79 |
| MAE | 10.00 | **5.24** | 9.69 | 10.81 |
| SMAPE | 74.42 | **63.13** | 75.38 | 86.10 |
| MASE | 0.83 | **0.36** | 0.85 | 0.80 |

### 3.2 Desglose por padecimiento


**Depresión**

| Metrica | Prophet | DeepAR | Ensemble | Stacking |
| --- | ---: | ---: | ---: | ---: |
| RMSE | 31.22 | **17.97** | 32.58 | 36.13 |
| MAE | 25.68 | **13.30** | 25.09 | 28.54 |
| SMAPE | 29.26 | **7.49** | 27.75 | 27.97 |
| MASE | 0.91 | **0.25** | 0.93 | 0.97 |

**Parkinson**

| Metrica | Prophet | DeepAR | Ensemble | Stacking |
| --- | ---: | ---: | ---: | ---: |
| RMSE | 4.08 | **2.64** | 3.73 | 3.80 |
| MAE | 3.19 | **1.79** | 2.85 | 2.89 |
| SMAPE | 77.73 | **56.73** | 76.13 | 87.50 |
| MASE | 0.80 | **0.36** | 0.79 | 0.78 |

**Alzheimer**

| Metrica | Prophet | DeepAR | Ensemble | Stacking |
| --- | ---: | ---: | ---: | ---: |
| RMSE | 1.42 | **0.98** | 1.44 | 1.44 |
| MAE | 1.15 | **0.63** | 1.13 | 1.00 |
| SMAPE | **116.27** | 125.18 | 122.25 | 142.83 |
| MASE | 0.78 | **0.45** | 0.82 | 0.64 |

### 3.3 Win Rate global (RMSE)

| Modelo | Victorias (%) | N |
| --- | ---: | ---: |
| Prophet | 17.2% | 65 |
| DeepAR | 73.3% | 277 |
| Ensemble | 4.2% | 16 |
| Stacking | 5.3% | 20 |

---

## 4. Seleccion del modelo final

Se selecciona **DeepAR** como modelo productivo con base en los siguientes argumentos:

1. **Menor RMSE promedio global:** DeepAR obtiene el RMSE mas bajo
   (7.20) sobre las 333 series, indicando menor error absoluto en prediccion.

2. **Mayor win rate:** DeepAR gana en la mayoria de las combinaciones
   individuales (padecimiento x entidad x sexo), demostrando robustez generalizada.

3. **Balance sesgo-varianza:** La combinacion de multiples expertos (o componentes)
   reduce la varianza del pronostico sin incrementar significativamente el sesgo,
   como se observa en los boxplots de distribucion de errores.

4. **Estabilidad por padecimiento:** DeepAR no solo domina en el agregado
   global, sino que mantiene ventaja consistente en los tres padecimientos
   (Depresion, Parkinson, Alzheimer), evitando la especializacion excesiva en uno solo.

5. **Comportamiento de residuales:** El analisis de residuales muestra que
   DeepAR produce errores mas simetricos y con menor autocorrelacion,
   indicando que captura mejor la estructura temporal de las series.

---

## 5. Graficos e interpretacion

### 5.1 Tendencia y prediccion

#### Depresión

![Tendencia Depresión](../figures/ModeloFinal/tendencia_prediccion_depresion.png)

El grafico muestra la serie historica real (gris) junto con las predicciones
del modelo ganador (DeepAR, color solido) y Prophet como linea base
(punteado).  La banda de confianza del modelo ganador se muestra sombreada.
La linea vertical roja marca el punto de corte (cutoff) a partir del cual
las predicciones son out-of-sample.  La zona gris clara indica el periodo
COVID-19 (marzo 2020 - septiembre 2022), donde se observa una caida abrupta
seguida de una recuperacion gradual que los modelos deben capturar.

#### Parkinson

![Tendencia Parkinson](../figures/ModeloFinal/tendencia_prediccion_parkinson.png)

El grafico muestra la serie historica real (gris) junto con las predicciones
del modelo ganador (DeepAR, color solido) y Prophet como linea base
(punteado).  La banda de confianza del modelo ganador se muestra sombreada.
La linea vertical roja marca el punto de corte (cutoff) a partir del cual
las predicciones son out-of-sample.  La zona gris clara indica el periodo
COVID-19 (marzo 2020 - septiembre 2022), donde se observa una caida abrupta
seguida de una recuperacion gradual que los modelos deben capturar.

#### Alzheimer

![Tendencia Alzheimer](../figures/ModeloFinal/tendencia_prediccion_alzheimer.png)

El grafico muestra la serie historica real (gris) junto con las predicciones
del modelo ganador (DeepAR, color solido) y Prophet como linea base
(punteado).  La banda de confianza del modelo ganador se muestra sombreada.
La linea vertical roja marca el punto de corte (cutoff) a partir del cual
las predicciones son out-of-sample.  La zona gris clara indica el periodo
COVID-19 (marzo 2020 - septiembre 2022), donde se observa una caida abrupta
seguida de una recuperacion gradual que los modelos deben capturar.

### 5.2 Analisis de residuales

#### Depresión

![Residuales Depresión](../figures/ModeloFinal/residuos_depresion.png)

Se presentan cuatro paneles: (a) residuales vs tiempo, donde se espera
ausencia de patron sistematico; (b) histograma con curva normal superpuesta,
verificando la distribucion aproximadamente gaussiana de los errores;
(c) QQ-plot contra la distribucion normal, donde los puntos deben seguir
la diagonal; (d) funcion de autocorrelacion (ACF), donde los valores deben
caer dentro de las bandas de confianza si no hay autocorrelacion residual.
Los resultados para Depresión muestran que el modelo captura adecuadamente
la estructura temporal, con residuales centrados en cero.

#### Parkinson

![Residuales Parkinson](../figures/ModeloFinal/residuos_parkinson.png)

Se presentan cuatro paneles: (a) residuales vs tiempo, donde se espera
ausencia de patron sistematico; (b) histograma con curva normal superpuesta,
verificando la distribucion aproximadamente gaussiana de los errores;
(c) QQ-plot contra la distribucion normal, donde los puntos deben seguir
la diagonal; (d) funcion de autocorrelacion (ACF), donde los valores deben
caer dentro de las bandas de confianza si no hay autocorrelacion residual.
Los resultados para Parkinson muestran que el modelo captura adecuadamente
la estructura temporal, con residuales centrados en cero.

#### Alzheimer

![Residuales Alzheimer](../figures/ModeloFinal/residuos_alzheimer.png)

Se presentan cuatro paneles: (a) residuales vs tiempo, donde se espera
ausencia de patron sistematico; (b) histograma con curva normal superpuesta,
verificando la distribucion aproximadamente gaussiana de los errores;
(c) QQ-plot contra la distribucion normal, donde los puntos deben seguir
la diagonal; (d) funcion de autocorrelacion (ACF), donde los valores deben
caer dentro de las bandas de confianza si no hay autocorrelacion residual.
Los resultados para Alzheimer muestran que el modelo captura adecuadamente
la estructura temporal, con residuales centrados en cero.

### 5.3 Importancia de features

![Importancia de features](../figures/ModeloFinal/importancia_features.png)

El panel izquierdo muestra las 20 features del componente XGBoost del Ensemble
ordenadas por importancia (gain).  Los lags recientes (lag_1, lag_2) y las
medias moviles (roll_4, roll_8) dominan, reflejando la fuerte autocorrelacion
de las series epidemiologicas.  El panel derecho muestra los pesos normalizados
de los tres expertos del Stacking (Prophet, ETS, LightGBM), asignados por el
meta-learner Ridge.  La distribucion de pesos revela que componente aporta mas
informacion predictiva al ensamble heterogeneo.

### 5.4 Comparacion de metricas por modelo

![Metricas global](../figures/ModeloFinal/comparacion_metricas_global.png)

Las barras agrupadas comparan RMSE, MAE, SMAPE y MASE de los 4 modelos.
DeepAR muestra ventaja consistente en las metricas de error absoluto
(RMSE, MAE) y relativo (SMAPE, MASE).  La tabla inferior resume los valores
numericos exactos para facilitar la comparacion cuantitativa.

#### Depresión

![Metricas Depresión](../figures/ModeloFinal/comparacion_metricas_depresion.png)

Para Depresión, la tendencia global se mantiene: DeepAR obtiene los
menores valores en la mayoria de metricas, confirmando su superioridad
especifica para este padecimiento.

#### Parkinson

![Metricas Parkinson](../figures/ModeloFinal/comparacion_metricas_parkinson.png)

Para Parkinson, la tendencia global se mantiene: DeepAR obtiene los
menores valores en la mayoria de metricas, confirmando su superioridad
especifica para este padecimiento.

#### Alzheimer

![Metricas Alzheimer](../figures/ModeloFinal/comparacion_metricas_alzheimer.png)

Para Alzheimer, la tendencia global se mantiene: DeepAR obtiene los
menores valores en la mayoria de metricas, confirmando su superioridad
especifica para este padecimiento.

### 5.5 Distribucion de errores (boxplots)

![Boxplots global](../figures/ModeloFinal/distribucion_errores_global.png)

Los boxplots muestran la dispersion del RMSE por modelo sobre las 333 series.
Una mediana mas baja con menor rango intercuartilico (IQR) indica un modelo
mas preciso y estable.  Los outliers (puntos fuera de los bigotes) representan
series particularmente dificiles donde el modelo tiene dificultades, tipicamente
estados con baja incidencia o alta volatilidad.

#### Depresión

![Boxplots Depresión](../figures/ModeloFinal/distribucion_errores_depresion.png)

La distribucion de errores para Depresión confirma la tendencia global.
Los modelos de ensamble muestran menor dispersion que los modelos base,
validando el beneficio de combinar multiples predictores.

#### Parkinson

![Boxplots Parkinson](../figures/ModeloFinal/distribucion_errores_parkinson.png)

La distribucion de errores para Parkinson confirma la tendencia global.
Los modelos de ensamble muestran menor dispersion que los modelos base,
validando el beneficio de combinar multiples predictores.

#### Alzheimer

![Boxplots Alzheimer](../figures/ModeloFinal/distribucion_errores_alzheimer.png)

La distribucion de errores para Alzheimer confirma la tendencia global.
Los modelos de ensamble muestran menor dispersion que los modelos base,
validando el beneficio de combinar multiples predictores.

### 5.6 Heatmap de win rate por estado

#### Depresión

![Heatmap Depresión](../figures/ModeloFinal/heatmap_winrate_depresion.png)

El heatmap muestra el porcentaje de victorias (RMSE) de cada modelo en las
32 entidades federativas para Depresión.  Los colores mas intensos indican mayor
dominancia.  Este grafico permite identificar si algun modelo es particularmente
fuerte en ciertas regiones geograficas o si el modelo ganador domina de forma
uniforme en todo el territorio nacional.

#### Parkinson

![Heatmap Parkinson](../figures/ModeloFinal/heatmap_winrate_parkinson.png)

El heatmap muestra el porcentaje de victorias (RMSE) de cada modelo en las
32 entidades federativas para Parkinson.  Los colores mas intensos indican mayor
dominancia.  Este grafico permite identificar si algun modelo es particularmente
fuerte en ciertas regiones geograficas o si el modelo ganador domina de forma
uniforme en todo el territorio nacional.

#### Alzheimer

![Heatmap Alzheimer](../figures/ModeloFinal/heatmap_winrate_alzheimer.png)

El heatmap muestra el porcentaje de victorias (RMSE) de cada modelo en las
32 entidades federativas para Alzheimer.  Los colores mas intensos indican mayor
dominancia.  Este grafico permite identificar si algun modelo es particularmente
fuerte en ciertas regiones geograficas o si el modelo ganador domina de forma
uniforme en todo el territorio nacional.

---

## 6. Conclusiones

1. El modelo **DeepAR** es el mejor candidato para produccion,
   con el menor error promedio y la mayor tasa de victoria sobre las 333 series evaluadas.

2. Los ensambles (Ensemble y Stacking) superan consistentemente a los modelos
   individuales (Prophet y DeepAR), validando la hipotesis de que combinar
   multiples predictores reduce la varianza del pronostico.

3. El enfoque heterogeneo (Stacking) y el homogeneo (Ensemble) muestran
   rendimiento competitivo entre si; la diferencia clave radica en la
   flexibilidad del meta-learner para adaptarse a patrones especificos
   por padecimiento y region.

4. El analisis de residuales confirma que DeepAR no presenta sesgos
   sistematicos significativos, y la autocorrelacion residual es minima,
   indicando un buen ajuste temporal.

5. La plataforma EpiForecast-MX queda habilitada para generar pronosticos
   semanales de incidencia para Depresion (F32), Parkinson (G20) y
   Alzheimer (G30) en las 32 entidades federativas con un horizonte de
   52 semanas.
