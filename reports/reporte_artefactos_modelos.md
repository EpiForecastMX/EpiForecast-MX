# Reporte Tecnico: Artefactos de Modelos en EpiForecast-MX

## IMSS | Marzo 2026

---

## 1. Resumen

EpiForecast-MX entrena **4 motores de pronostico** para cada combinacion de
padecimiento, entidad y sexo. Cada motor genera artefactos `.pkl` (modelo
serializado) y `.csv` (datos de entrenamiento y metricas). Este documento
explica la estructura, el conteo de archivos y por que DeepAR tiene archivos
adicionales respecto a los otros tres modelos.

---

## 2. Desglose de los 111 modelos por padecimiento

Cada padecimiento (Depresion, Parkinson, Alzheimer) genera **111 modelos**
entrenados independientemente:

| Nivel          | Combinaciones              | Modelos |
|----------------|----------------------------|---------|
| **Estatal**    | 32 estados x 3 sexos       | 96      |
| **Nacional**   | 1 pais x 3 sexos           | 3       |
| **Regional**   | 4 regiones INEGI x 3 sexos | 12      |
| **Total**      |                            | **111** |

Los 3 sexos son: `general` (ambos), `hombres`, `mujeres`.

Las 4 regiones INEGI son: Metropolitana alta, Urbana media, Sur-Sureste
vulnerable, Rural / dispersa.

**Total global:** 3 padecimientos x 111 = **333 modelos**.

---

## 3. Conteo de archivos por modelo

### 3.1 Archivos por padecimiento

| Modelo   | .pkl | .csv | Total | CSV extra vs pkl |
|----------|------|------|-------|------------------|
| Prophet  | 111  | 112  | 223   | +1               |
| DeepAR   | 111  | 115  | 226   | +4               |
| Ensemble | 111  | 112  | 223   | +1               |
| Stacking | 111  | 112  | 223   | +1               |

### 3.2 Que contiene cada tipo de archivo

**`.pkl` (111 por padecimiento)** — Modelo serializado con pickle. Contiene
el objeto entrenado listo para generar predicciones. Es el artefacto de
produccion: `scripts/predice.py` carga el `.pkl`, ejecuta `predict()` y
genera el forecast de 52 semanas.

**`.csv` individual (111 por padecimiento)** — Dataset de entrenamiento
preprocesado para cada combinacion (padecimiento, entidad, sexo). Columnas:
`ds` (fecha semanal), `y` (tasa normalizada por 100,000 hab.),
`y_original` (casos absolutos), `Total` (poblacion INEGI).

**`_completo.csv` (+1, todos los modelos)** — Tabla consolidada de metricas
de cross-validation de los 111 modelos. Una fila por modelo con: RMSE, MAE,
MAPE, SMAPE, MASE, hiperparametros, tiempo de entrenamiento, nivel de
confianza, entidad, y metricas de entrenamiento (rmse_train, smape_train).
Este CSV alimenta los reportes de comparacion y la tabla de produccion.

**`_multi.csv` (+3, solo DeepAR)** — Dataset multi-series exclusivo de
DeepAR. Contiene las 32 series estatales concatenadas verticalmente con una
columna `item_id` que identifica cada estado. Hay uno por cada sexo
(general, hombres, mujeres).

---

## 4. Por que DeepAR tiene 3 archivos extra

### 4.1 La diferencia arquitectonica

Los 4 modelos entrenan series individuales para los niveles estatal y
regional (un modelo por cada combinacion estado-sexo). Pero para el nivel
**Nacional**, cada modelo agrega de forma distinta:

| Modelo   | Prediccion Nacional                                        |
|----------|------------------------------------------------------------|
| Prophet  | Entrena 1 serie univariada con los datos nacionales        |
| Ensemble | Entrena 1 modelo con features del total nacional           |
| Stacking | Entrena 1 meta-learner con la serie nacional               |
| **DeepAR** | **Entrena 32 series estatales simultaneamente y suma**   |

Prophet, Ensemble y Stacking tratan el nivel Nacional como una serie mas:
toman los totales nacionales pre-agregados, entrenan un modelo y predicen
directamente. Un solo CSV de entrada, un solo `.pkl`.

DeepAR hace algo fundamentalmente distinto: **entrena un unico modelo
multi-series con las 32 series estatales como entradas simultaneas**. Luego,
para obtener el pronostico Nacional, genera una prediccion por cada estado y
las suma. Este enfoque le permite aprender patrones compartidos entre estados
(estacionalidad, efecto COVID, tendencias demograficas) y transferir
informacion de estados con alta incidencia hacia estados con datos escasos.

### 4.2 Que contienen los CSV multi-series

Cada `_multi.csv` tiene la siguiente estructura:

```
ds,item_id,incrementos_total,Total,y_original,y
2013-12-30,Aguascalientes,1,1425607,1,0.07014
2013-12-30,Baja California,5,3769020,5,0.13265
2013-12-30,Campeche,0,899931,0,0.00000
...
2026-01-04,Zacatecas,2,1622138,2,0.12330
```

| Columna            | Descripcion                                        |
|--------------------|----------------------------------------------------|
| `ds`               | Fecha semanal (lunes de la semana epidemiologica)  |
| `item_id`          | Nombre del estado (32 valores unicos)              |
| `incrementos_total`| Casos semanales absolutos del estado               |
| `Total`            | Poblacion del estado (INEGI, ultimo censo)         |
| `y_original`       | Igual a `incrementos_total` (casos absolutos)      |
| `y`                | Tasa normalizada: (casos / poblacion) x 100,000    |

**Dimensiones:** 20,161 filas = 1 header + 32 estados x 630 semanas.

Hay **3 archivos multi** por padecimiento (uno por sexo):
- `Deepar_Depresion_general_multi.csv`
- `Deepar_Depresion_hombres_multi.csv`
- `Deepar_Depresion_mujeres_multi.csv`

### 4.3 Flujo de prediccion Nacional en DeepAR

```
                    Deepar_Depresion_general_multi.csv
                    (32 estados x 630 semanas)
                              |
                              v
                    +-----------------------+
                    |  DeepAR multi-series  |
                    |  (1 modelo LSTM)      |
                    |  Entrena 32 series    |
                    |  simultaneamente      |
                    +-----------------------+
                              |
                    predict() con 32 contextos
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
         Ags: 52 sem     BC: 52 sem  ...  Zac: 52 sem
         (tasa norm.)    (tasa norm.)     (tasa norm.)
              |               |               |
              v               v               v
         Desnormalizar   Desnormalizar    Desnormalizar
         x pob_Ags       x pob_BC         x pob_Zac
         / 100,000       / 100,000        / 100,000
              |               |               |
              +-------+-------+-------+-------+
                      |
                      v
                SUMAR 32 estados
                      |
                      v
              Forecast Nacional
              (casos absolutos)
```

### 4.4 Ventaja del enfoque multi-series

1. **Transferencia de informacion:** Estados con baja incidencia (ej. Colima
   con ~0.5 casos/semana de Parkinson) se benefician de los patrones
   aprendidos de estados con alta incidencia (ej. Ciudad de Mexico con ~50
   casos/semana).

2. **Estacionalidad compartida:** Los 32 estados comparten el mismo calendario
   (vacaciones, semana santa, efecto COVID), y el modelo LSTM aprende este
   patron una sola vez para las 32 series.

3. **Coherencia jerarquica:** La suma de las predicciones estatales es
   consistente con el total nacional por construccion, algo que un modelo
   Nacional univariado no garantiza.

4. **Regularizacion natural:** Entrenar con mas series reduce el sobreajuste
   a patrones espurios de estados individuales.

### 4.5 Por que los otros modelos no necesitan multi-series

- **Prophet** es un modelo aditivo bayesiano diseñado para series univariadas.
  No tiene mecanismo para entrenar multiples series simultaneamente.

- **Ensemble (Prophet + XGBoost)** hereda la limitacion de Prophet. XGBoost
  podria recibir features de otros estados, pero el diseño actual entrena
  cada serie independientemente para mantener simplicidad.

- **Stacking (Prophet + ETS + LightGBM + Ridge)** combina expertos
  univariados. El meta-learner Ridge opera sobre las predicciones OOF de
  cada experto, no sobre datos crudos de otros estados.

- **DeepAR** es el unico modelo de la plataforma con capacidad nativa
  multi-series gracias a su arquitectura de red recurrente (LSTM) que
  procesa multiples secuencias en paralelo durante el entrenamiento.

---

## 5. Resumen de conteo total de archivos

| Modelo   | pkl (x3 pad.) | csv (x3 pad.) | Total archivos |
|----------|---------------|----------------|----------------|
| Prophet  | 333           | 336            | 669            |
| DeepAR   | 333           | 345            | 678            |
| Ensemble | 333           | 336            | 669            |
| Stacking | 333           | 336            | 669            |
| **Total**| **1,332**     | **1,353**      | **2,685**      |

Los 1,332 `.pkl` son los modelos de produccion. Los 1,353 `.csv` son datos
de entrenamiento (1,332), consolidados de metricas (12) y datasets
multi-series de DeepAR (9).

---

*Generado: 2026-03-02 | EpiForecast-MX | IMSS*
