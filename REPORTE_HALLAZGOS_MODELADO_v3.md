# Reporte de Hallazgos — Modelado Prophet v6

**Fecha:** 2026-02-21
**Modelos entrenados:** 297 estatales + fallback regionales (modo hibrido)
**Tiempo total estimado:** ~45 minutos (n_jobs=-2, joblib loky)
**Horizonte de prediccion:** 120 semanas

---

## 1. Resumen Ejecutivo

### Cambios v5 → v6

| Cambio | Descripcion | Impacto |
|---|---|---|
| **MASE** | Nueva metrica escala-independiente en CV | Evalua si modelo supera baseline naive lag-52 |
| **Modo hibrido** | Fallback regional para estados insuficientes | Elimina predicciones planas en 40 modelos |
| **Fix normalizar()** | Sanitiza `/` en nombres de region | Evita error de ruta en "Rural / dispersa" |

### Metricas v5 vs v6

| Metrica | v5 | v6 | Cambio |
|---|---|---|---|
| Modelos insuficientes (sin prediccion util) | 40 | **0** | -100% |
| Cobertura estatal con prediccion informada | 87% | **100%** | +13pp |
| Metricas de CV | RMSE, MAE, MAPE | RMSE, MAE, MAPE, **MASE** | +1 metrica |

---

## 2. Nueva Metrica: MASE (Mean Absolute Scaled Error)

### 2.1 Definicion

```
MASE = MAE_modelo / MAE_naive_seasonal
```

Donde `MAE_naive_seasonal` es el error medio absoluto de un baseline naive con lag de 52 semanas (prediccion = valor de hace 1 ano).

### 2.2 Interpretacion

| MASE | Significado |
|---|---|
| < 1.0 | Modelo es **mejor** que el baseline naive estacional |
| = 1.0 | Modelo es **igual** al baseline naive |
| > 1.0 | Modelo es **peor** que el baseline naive |

### 2.3 Ventajas sobre MAPE

- **Escala-independiente:** funciona igual para series con valores grandes y pequenos
- **Funciona con ceros:** MAPE explota cuando `y=0`; MASE no tiene ese problema
- **Baseline interpretable:** compara contra un predictor concreto (naive lag-52), no contra una escala arbitraria
- **Recomendado por Hyndman & Koehler (2006)** como metrica principal para series de tiempo

### 2.4 Implementacion

- Se computa en cada fold de CV usando los datos de entrenamiento del fold
- Se requieren >52 observaciones en el fold de entrenamiento (siempre se cumple con series de 500+ semanas)
- Se promedia con los mismos `cv_weights` progresivos que RMSE/MAE/MAPE
- Si `MAE_naive = 0` (serie constante), MASE retorna `None`
- Columna `mase` agregada al CSV de resultados (`_completo.csv`)

---

## 3. Modo Hibrido — Fallback Regional

### 3.1 Problema

En v5, 40 modelos estatales (35 Alzheimer + 5 Parkinson) tenian `confianza: "insuficiente"` (promedio < 0.5 casos/semana). Estos modelos se entrenaban con params default (sin CV) y producian predicciones casi planas, sin valor predictivo real.

### 3.2 Solucion

El **modo hibrido** combina modelos estatales (para estados con datos suficientes) con modelos regionales de fallback (para estados insuficientes):

1. **Entrenamiento estatal normal** — como en v5, 297 modelos por estado x sexo
2. **Identificacion de insuficientes** — estados con promedio < 0.5 casos/semana
3. **Agrupacion por region INEGI** — se identifican las regiones afectadas
4. **Entrenamiento regional** — se entrenan modelos Prophet por region INEGI (agrupando todos los estados de la region)
5. **Prediccion con desnormalizacion estatal** — el modelo regional predice tasa por 100K; se desnormaliza con la poblacion del estado individual

### 3.3 Por que funciona

- El modelo regional ve **mas datos** (suma de varios estados) → serie mas robusta
- La tasa por 100K es **escala-independiente** → una tasa regional aplica razonablemente a cada estado
- Para estados con <0.5 casos/semana, **cualquier prediccion informada** es mejor que la prediccion plana del modelo insuficiente
- El experimento `exp/regional-alzheimer` demostro: RMSE **3.5x mejor** que modelos estatales, y **0 insuficientes**

### 3.4 Configuracion

```yaml
# config/params.yaml
padecimiento:
  modelado_estados: True     # modelos por estado (prerequisito)
  modelado_hibrido: True     # activa fallback regional para insuficientes
```

### 3.5 Nombres de archivo

- Modelos regionales: `Prophet_{Padecimiento}_region_{Region}_{sexo}.pkl`
- Ejemplo: `Prophet_Alzheimer_region_Sur-Sureste_vulnerable_hombres.pkl`
- El CSV `_completo.csv` incluye columna `usar_regional` que mapea cada modelo insuficiente a su .pkl regional

### 3.6 Regiones INEGI afectadas

| Region | Estados insuficientes (Alzheimer) |
|---|---|
| Sur-Sureste vulnerable | Campeche, Chiapas, Guerrero, Oaxaca, Quintana Roo, Tabasco, Yucatan |
| Rural / dispersa | Aguascalientes, Colima, Durango, Nayarit, San Luis Potosi, Tlaxcala, Zacatecas |
| Urbana media | Baja California Sur, Hidalgo, Morelos, Queretaro, Sonora, Tamaulipas |
| Metropolitana alta | Solo algunos modelos de sexo especifico |

---

## 4. Experimentos Descartados

### 4.1 Rolling Mean Smoothing (`exp/smoothing-sparse`)

- **Hipotesis:** suavizar series sparse con rolling mean de ventana 4-8 semanas podria reducir ruido
- **Resultado:** 0% mejora en RMSE. El log-transform ya suaviza lo necesario
- **Conclusion:** descartado. No implementado en v6

---

## 5. Fix normalizar() — Sanitizacion de `/`

La region INEGI "Rural / dispersa" contiene `/` que causa error al crear rutas de archivo.

**Antes:** `normalizar("Rural / dispersa")` → `"Rural_/_dispersa"` (ruta invalida)
**Despues:** `normalizar("Rural / dispersa")` → `"Rural_-_dispersa"` (ruta valida)

Fix aplicado en dos funciones que deben coincidir:
- `scripts/entrena.py` → `normalizar()`
- `src/modelado/forecast.py` → `_normalizar_nombre()`

---

## 6. Estructura del CSV de Resultados (v6)

Un CSV por padecimiento: `models/{Padecimiento}/Prophet_{Padecimiento}_completo.csv`

| Columna | Tipo | Descripcion |
|---|---|---|
| `padecimiento` | str | Alzheimer, Depresion, Parkinson |
| `sexo` | str | incrementos_hombres / incrementos_mujeres / incrementos_total |
| `rmse` | float/null | RMSE de CV (null si insuficiente) |
| `mae` | float/null | MAE de CV |
| `mape` | float/null | MAPE de CV, clipeado a 999% max |
| `mase` | float/null | **MASE de CV (nuevo v6)** — <1 = mejor que naive lag-52 |
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
| `usar_regional` | str/null | **Nombre del .pkl regional de fallback (nuevo v6)** |

---

## 7. Changelog v5 → v6

| Cambio | Detalle | Impacto |
|---|---|---|
| MASE | Nueva metrica en CV y CSV | Evalua vs baseline naive lag-52 |
| Modo hibrido | Fallback regional para insuficientes | 40 modelos con prediccion informada |
| Fix normalizar() | `"/"` → `"-"` en nombres de region | Evita error de ruta |
| Columna `mase` | En `_completo.csv` | Metrica adicional para evaluacion |
| Columna `usar_regional` | En `_completo.csv` | Mapea insuficiente → .pkl regional |
| `modelado_hibrido` | Nuevo parametro en `params.yaml` | Activa/desactiva fallback |
