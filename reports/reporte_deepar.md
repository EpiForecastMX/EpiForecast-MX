# Reporte Detallado: DeepAR (GluonTS + PyTorch)

## EpiForecast-MX | IMSS | Febrero 2026

---

## 1. Resumen ejecutivo

DeepAR es el segundo motor de pronostico de EpiForecast-MX. Utiliza redes recurrentes
(LSTM) implementadas sobre GluonTS con backend PyTorch para predecir la incidencia
semanal de Depresion (F32), Parkinson (G20) y Alzheimer (G30) en las 32 entidades
federativas de Mexico con un horizonte de 52 semanas.

A diferencia de Prophet (modelo aditivo univariado), DeepAR entrena todas las series
estatales simultaneamente (multi-series), lo que le permite aprender patrones compartidos
entre entidades y transferir informacion de estados con alta incidencia hacia estados con
datos mas escasos.

---

## 2. Arquitectura del modelo

### 2.1 Clase principal: `DeepARForecaster`

**Archivo**: `src/epiforecast/models/deepar/model.py` (842 lineas)

Implementa la interfaz `ForecastModel` (patron Factory/SOLID) con los siguientes metodos:

| Metodo | Descripcion |
|--------|-------------|
| `fit(train_data)` | Entrena el estimador DeepAR sobre datos de entrenamiento |
| `predict(horizon)` | Genera pronostico a futuro (single o multi-series) |
| `cross_validate(data)` | Delega a `DeepARCrossValidator` para CV temporal |
| `save(path)` | Serializa predictor + metadata con `torch.save()` |
| `load(path)` | Restaura predictor con manejo CUDA->CPU automatico |
| `get_params()` | Retorna hiperparametros actuales como diccionario plano |
| `run()` | Pipeline completo: agrupa -> split -> CV -> fit -> eval |

### 2.2 Hiperparametros (config/models/deepar.yaml)

| Parametro | Valor | Justificacion |
|-----------|-------|---------------|
| `epochs` | 300 | Early stopping frena si converge antes |
| `context_length` | 104 | 2 anios de historia (captura ciclos anuales completos) |
| `prediction_length` | 52 | Horizonte de 1 anio |
| `num_layers` | 2 | Capas recurrentes LSTM |
| `num_cells` | 80 | Celdas por capa (capacidad para patrones complejos) |
| `dropout_rate` | 0.15 | Regularizacion |
| `learning_rate` | 5e-4 | Convergencia estable |
| `weight_decay` | 1e-6 | Regularizacion L2 |
| `batch_size` | 32 | Balance entre velocidad y estabilidad |
| `scaling` | true | Normalizacion interna de GluonTS (mean scaling) |
| `distr_output` | student-t | Robusto a outliers |
| `num_samples` | 200 | Muestras Monte Carlo para intervalos de confianza |
| `nonnegative_pred_samples` | true | Predicciones siempre >= 0 |
| `num_batches_per_epoch` | 50 | Default de GluonTS |
| `early_stopping_patience` | 15 | Detener si train_loss no mejora en 15 epochs |
| `multi_series` | true | Entrenar con 32 series estatales |
| `skip_cv_estatal` | true | Omitir CV por estado (DeepAR no hace HP tuning) |

### 2.3 Entrenamiento multi-series

La innovacion clave de DeepAR frente a Prophet es el entrenamiento multi-series:

1. **Nivel nacional**: Se construyen 32 series (una por entidad) como `item_id` en GluonTS.
   Cada serie contiene la incidencia semanal normalizada a tasa por 100,000 habitantes.
2. **Nivel estatal**: Serie unica por estado (single-series).
3. **Agregacion**: Para el pronostico nacional, se generan 200 muestras Monte Carlo por
   estado, se desnormalizan (tasa -> conteo absoluto) y se suman para obtener el
   pronostico nacional con intervalos de confianza empiricos (P5-P95).

### 2.4 Acelerador automatico

El modelo detecta automaticamente el hardware disponible:

```
CUDA (Windows/Linux GPU) > MPS (Apple Silicon) > CPU
```

Para MPS, se establece `PYTORCH_ENABLE_MPS_FALLBACK=1` porque la distribucion Student-t
utiliza operaciones (`_standard_gamma`) no soportadas nativamente en el backend MPS.

---

## 3. Validacion cruzada

### 3.1 `DeepARCrossValidator`

**Archivo**: `src/epiforecast/models/deepar/cross_validator.py` (319 lineas)

- **Estrategia**: `TimeSeriesSplit` con 4 folds y test_size de 53 semanas.
- **Epochs reducidos**: `max(25, epochs_completos // 4)` por fold para velocidad.
- **Multi-series CV**: Los folds se definen por fechas en la serie nacional y se aplican
  a las 32 series estatales. Las metricas se evaluan sobre el pronostico nacional
  agregado (suma de estados desnormalizados).
- **Metricas**: RMSE, MAE, MAPE, SMAPE, MASE (mismas que Prophet para comparabilidad).

### 3.2 Optimizaciones de CV

- **`skip_cv_estatal`**: En SageMaker y localmente, la CV por estado no aporta porque
  DeepAR no hace tuning de hiperparametros (los HP son fijos). Se usa `eval_rapida()`
  post-entrenamiento como proxy.
- **`eval_rapida()`**: Predice sobre test_data con el predictor ya entrenado en la serie
  completa. Las metricas son ligeramente optimistas (el modelo vio test), pero el sesgo
  es consistente para todos los modelos estatales, permitiendo comparacion valida.

---

## 4. Infraestructura SageMaker

### 4.1 Componentes

| Componente | Archivo | Descripcion |
|------------|---------|-------------|
| Dockerfile | `aws/Dockerfile` | `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime` |
| Dependencias | `aws/requirements_sagemaker.txt` | GluonTS, Prophet, sagemaker-training |
| Launcher | `aws/sagemaker_launcher.py` | Build ECR + lanzar Training Job |
| Entry point | `scripts/entrena_sagemaker.py` | Adaptador SageMaker -> pipeline existente |

### 4.2 Flujo de ejecucion

```
make train-sagemaker
  -> Build Docker image
  -> Push a Amazon ECR (564141855321.dkr.ecr.us-east-1.amazonaws.com)
  -> Lanzar Training Job en ml.g4dn.xlarge (NVIDIA T4, CUDA 12.4)
  -> Entry point: entrena_sagemaker.py
    -> Detecta entorno (/opt/ml/)
    -> Copia datos de /opt/ml/input/ al workspace
    -> Fuerza modelo_activo='deepar'
    -> Invoca pipeline de entrenamiento
    -> Copia modelos a /opt/ml/model/
  -> Descargar modelos con aws s3 sync
```

### 4.3 Paralelismo en SageMaker

Se optimizo el launcher para ejecutar 3 jobs paralelos (uno por padecimiento) y con
`n_jobs_train=4` internamente. Con `skip_cv_estatal=true`, el entrenamiento completo
de 3 padecimientos x 32 estados se completa en aproximadamente 2-3 horas en GPU.

---

## 5. Serializacion y carga

### 5.1 Formato de guardado

```python
# save():
payload = {
    "predictor": self._predictor,    # GluonTS predictor completo
    "config": self.get_params(),     # Hiperparametros
    "freq": "W-MON",
    "prediction_length": 52,
    "multi_series": True/False,
}
torch.save(payload, path)
```

Archivos adicionales (sidecar):
- `{stem}.csv`: Serie historica nacional (ds, y, y_original, Total)
- `{stem}_multi.csv`: Serie multi-series (ds, y, item_id, Total) — solo nivel nacional

### 5.2 Carga CUDA -> CPU

El metodo `_load_pickle_cpu()` maneja la compatibilidad CUDA -> CPU para modelos
entrenados en SageMaker (GPU) y cargados en macOS (MPS/CPU):

1. Intenta `torch.load(path, map_location="cpu", weights_only=False)`
2. Si falla, usa un `_CpuUnpickler` custom que redirige `torch.cuda.*` a `torch.*`

Ademas, despues de cargar, el predictor se mueve explicitamente a CPU/MPS para evitar
un bug de GluonTS donde no todos los tensores de entrada se mueven al device CUDA.

---

## 6. Normalizacion y desnormalizacion

### 6.1 Flujo de normalizacion

1. **Entrada**: Conteos absolutos por estado (`incrementos_total`)
2. **Normalizacion**: `tasa = (conteo / poblacion) * 100,000`
3. **Entrenamiento**: DeepAR entrena sobre tasas (comparables entre estados)
4. **Prediccion**: DeepAR produce tasas
5. **Desnormalizacion**: `conteo = (tasa * poblacion) / 100,000`

### 6.2 Desnormalizacion multi-series

Para el pronostico nacional:
1. Se generan 200 muestras por estado (en espacio tasa)
2. Cada estado se desnormaliza con su poblacion especifica
3. Se suman las 32 series desnormalizadas -> pronostico nacional en conteos
4. Se calculan media e intervalos P5/P95 sobre las muestras nacionales

---

## 7. Supresion de ruido en logs

DeepAR genera una cantidad significativa de output verbose de PyTorch Lightning y GluonTS.
Se implementaron las siguientes supresiones:

- Lightning loggers: `setLevel(logging.ERROR)` + `propagate = False`
- `warnings.filterwarnings("ignore")` para: indexacion multidimensional de GluonTS,
  `validation_step`, Tensor Cores, `float32_matmul_precision`, LeafSpec, checkpoint
  directory, MPS backend.
- `cmdstanpy` logger deshabilitado (afecta a Prophet que importa cmdstanpy).

Se implemento una barra de progreso Rich (`_RichEpochProgress`) como callback de
Lightning que muestra epoch actual, loss y tiempo restante sin el ruido de Lightning.

---

## 8. Estructura de archivos

```
src/epiforecast/models/deepar/
  __init__.py              # Import para registro en factory
  model.py                 # DeepARForecaster (842 lineas)
  cross_validator.py       # DeepARCrossValidator (319 lineas)

config/models/
  deepar.yaml              # Hiperparametros DeepAR

aws/
  Dockerfile               # Imagen Docker para SageMaker
  requirements_sagemaker.txt  # Dependencias del container
  sagemaker_launcher.py    # Build ECR + lanzar Training Job

scripts/
  entrena_sagemaker.py     # Entry point SageMaker

models/deepar/
  {Padecimiento}/
    DeepAR_{pad}_{sexo}.pkl         # Modelo nacional
    DeepAR_{pad}_{sexo}.csv         # Serie historica (sidecar)
    DeepAR_{pad}_{sexo}_multi.csv   # Serie multi-series (sidecar)
    DeepAR_{pad}_{sexo}_completo.csv  # Metadata + metricas
    {Entidad}/
      DeepAR_{pad}_{sexo}_{ent}.pkl   # Modelo estatal
      ...
```

---

## 9. Decisions de diseno y trade-offs

### 9.1 Multi-series vs single-series

- **Decision**: Multi-series para nivel nacional, single-series para nivel estatal.
- **Razon**: El entrenamiento multi-series permite transferir patrones entre estados.
  Para nivel estatal individual, no hay multiples series que agregar.

### 9.2 Distribucion Student-t

- **Decision**: Student-t como distribucion de salida por defecto.
- **Razon**: Mas robusta a outliers que Normal. Los datos epidemiologicos tienen picos
  atipicos (COVID, subregistro estacional) que una distribucion Normal penalizaria
  excesivamente.

### 9.3 Prediccion siempre en CPU

- **Decision**: Cargar y predecir siempre en CPU/MPS, incluso si el modelo se entreno
  en CUDA.
- **Razon**: GluonTS tiene un bug donde no mueve todos los tensores de entrada al device
  CUDA durante prediccion. La inferencia en CPU es rapida (< 1s por modelo) y evita
  errores de device mismatch.

### 9.4 Early stopping sobre train_loss

- **Decision**: Monitor `train_loss` en vez de `val_loss`.
- **Razon**: GluonTS no soporta un `val_dataloader` nativo en `DeepAREstimator`. El
  training loss es un proxy razonable para convergencia.

---

## 10. Lessons learned

### 10.1 Compatibilidad CUDA -> CPU

**Problema**: Modelos entrenados en SageMaker (GPU CUDA) fallaban al cargar en macOS.
`pickle.load()` intentaba reconstruir tensores CUDA en un entorno sin CUDA.

**Solucion**: Implementar `_load_pickle_cpu()` con dos intentos:
1. `torch.load(map_location="cpu")` — funciona en la mayoria de los casos.
2. `_CpuUnpickler` custom — redirige `torch.cuda.*` a `torch.*` para pickles
   con formatos legacy.

**Leccion**: Siempre serializar modelos PyTorch con `torch.save()` en vez de
`pickle.dump()`, y siempre cargar con `map_location="cpu"` para portabilidad.

### 10.2 MPS (Apple Silicon) y Student-t

**Problema**: La operacion `_standard_gamma` requerida por la distribucion Student-t no
esta implementada en el backend MPS de PyTorch.

**Solucion**: Establecer `PYTORCH_ENABLE_MPS_FALLBACK=1` al inicio del modulo para
que las operaciones no soportadas caigan automaticamente a CPU.

**Leccion**: MPS no tiene paridad completa con CUDA. Para distribuciones probabilisticas,
verificar que las operaciones necesarias esten soportadas.

### 10.3 Metricas en escala correcta

**Problema**: Inicialmente las metricas de DeepAR se calculaban en espacio de tasas
(por 100k) mientras que Prophet las calculaba en conteos absolutos. Esto hacia
la comparacion invalida.

**Solucion**: Desnormalizar las predicciones antes de calcular metricas. Usar
`compute_forecast_metrics()` compartido con y_true y y_pred en conteos absolutos.

**Leccion**: Siempre verificar que las metricas de diferentes modelos esten en la
misma escala antes de compararlas. Definir un espacio comun (conteos absolutos) y
documentarlo.

### 10.4 CV estatal no aporta en DeepAR

**Problema**: La validacion cruzada por estado tardaba horas sin mejorar los resultados.
DeepAR no hace tuning de HP (los hiperparametros son fijos), asi que la CV solo
servia para medir rendimiento, no para seleccionar parametros.

**Solucion**: Implementar `skip_cv_estatal=true` y usar `eval_rapida()` como proxy.
Las metricas de eval_rapida son ligeramente optimistas pero consistentes entre modelos.

**Leccion**: La CV es costosa. Si no se usa para seleccionar hiperparametros, considerar
alternativas mas rapidas como hold-out temporal.

### 10.5 Supresion de logs de Lightning

**Problema**: PyTorch Lightning genera lineas de GPU/TPU/HPU info que contaminan la
consola. Ademas, reinicializa sus loggers en cada creacion de Trainer.

**Solucion**: Suprimir en dos puntos: (1) al importar el modulo, (2) justo antes de
crear el estimador con `_silence_lightning()`.

**Leccion**: Los frameworks de deep learning son verbose por defecto. Invertir tiempo
en suprimir ruido mejora significativamente la experiencia del usuario.

### 10.6 GluonTS requiere frecuencia consistente

**Problema**: Series con semanas faltantes causaban errores en `PandasDataset`.

**Solucion**: Resamplear con `.resample(freq).sum().fillna(0)` antes de construir
el dataset para garantizar un `DatetimeIndex` con frecuencia regular.

**Leccion**: GluonTS es estricto con la frecuencia temporal. Siempre pre-procesar
las series para eliminar gaps antes de alimentar al modelo.

### 10.7 Paralelismo en SageMaker

**Problema**: Entrenar 3 padecimientos secuencialmente en GPU tardaba demasiado.

**Solucion**: Modificar el launcher para lanzar 3 jobs de SageMaker en paralelo
(uno por padecimiento) con `n_jobs_train=4` internamente.

**Leccion**: El costo de SageMaker es por tiempo de instancia. Paralelizar reduce
el tiempo total (y potencialmente el costo si las instancias se apagan antes).

### 10.8 mypy y numpy tipos

**Problema**: `.values` en pandas retorna `ndarray | ExtensionArray`, incompatible
con parametros tipados como `ArrayLike` o `ndarray`.

**Solucion**: Usar `.to_numpy()` en lugar de `.values` en todos los puntos donde
los arrays se pasan a funciones de metricas o numpy.

**Leccion**: Para compatibilidad mypy estricto, preferir `.to_numpy()` sobre
`.values` en pandas.

---

## 11. Resultados y rendimiento

### 11.1 Tiempos de entrenamiento

| Plataforma | Nacional (3 pads x multi-series) | Estatal (3 x 32 x 3 sexos) |
|------------|----------------------------------|-----------------------------|
| macOS M2 (MPS) | ~15 min | ~4 horas (sin CV) |
| SageMaker T4 | ~5 min | ~1.5 horas (sin CV) |

### 11.2 Comparacion con Prophet

DeepAR y Prophet se comparan con las mismas 5 metricas (RMSE, MAE, MAPE, SMAPE, MASE)
calculadas en espacio de conteos absolutos. Los resultados completos se encuentran en:

- Excel: `reports/forecasts/comparacion_modelos/comparacion_metricas.xlsx`
- HTML: `reports/forecasts/comparacion_modelos/comparacion_modelos.html`
- Graficos: `reports/forecasts/comparacion_modelos/{padecimiento}/CMP_*.png`

---

## 12. Comandos de referencia

```bash
# Entrenamiento local
make train-deepar

# Entrenamiento en SageMaker
make train-sagemaker

# Prediccion
make predict ARGS="modelo_activo='deepar'"

# Comparacion visual
make compare

# Solo un padecimiento
make train-deepar ARGS="padecimiento.tipo='Alzheimer'"

# Tests unitarios
make test-fast
```
