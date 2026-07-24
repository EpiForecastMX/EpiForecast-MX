# PLAN BRUTAL — Obesidad E66 ASAP y plataforma funcional N+1

> Estado de referencia: backend `ad98225a`, frontend `179bbe36`.
> Objetivo: entrenar Obesidad correctamente cuanto antes y convertir el flujo en una plataforma
> genérica para padecimientos del boletín.
> Estado: Fase 0 cerrada; TransformContract v1 terminado; Obesidad sigue **NO-GO** para publicación.

Este documento **reemplaza completamente** el plan anterior.

---

## 1. Qué cambia respecto al plan anterior

### Se conserva

- Contención de Fase 0 y preservación del legacy.
- Extracción E66 existente: 653 tablas válidas y 20,896 filas.
- Registry, lifecycle gate y TransformContract.
- Evaluación OOS con folds comunes.
- Seasonal Naive como motor elegible.
- Refit final con toda la historia.
- Entrenamiento de 64 series base y derivación de 47 productos.
- Artefactos aislados por `run_id`.
- F50 como prueba N+1.
- Publicación únicamente con aprobación explícita.

### Se elimina o saca de la ruta crítica

- Endurecimiento contra ataques locales, TOCTOU, señales y carreras improbables.
- Más rondas adversariales del writer.
- DeepAR D0–D3 como requisito para entrenar Obesidad.
- Los ocho estados de lifecycle; se conservan `configured`, `trained`, `published`.
- Las once fases secuenciales del plan anterior.
- Entrenar 111 modelos independientes.
- Frontend, RAG, Tableau y DVC como prerequisitos del benchmark local.
- Reextraer los 654 PDF si la extracción existente pasa validación.
- Nuevas dependencias neuronales antes de tener baselines válidos.
- Reutilizar modelos, métricas, forecasts o selección actuales de Obesidad.
- Interpretar hashes como seguridad: se usarán únicamente para reproducibilidad.
- Añadir metadatos de artefacto antes de reparar calendario y datos.

### Ruta crítica reducida

1. Validar el checkpoint actual.
2. Reparar calendario y dataset.
3. Crear runner genérico aislado.
4. Ejecutar baselines y Prophet con backtest común.
5. Refit y forecast preliminar de Obesidad.
6. Probar F50 como N+1.
7. Publicar solo después de aprobación.

---

## 2. Gate V0 — validación de baseline (solo lectura)

Todo este bloque es de solo lectura. No entrena, publica ni modifica DVC.

### V0.1 Estado de los repositorios

- MX (`EpiForecast-MX`): rama `feat/registry-padecimientos-obesidad`, HEAD `ad98225a`, sin cambios
  rastreados ni staged (los untracked del usuario pueden existir y no se tocan).
- Dashboard (`EpiForecast-IMSS-Dashboard`): rama `main`, HEAD `179bbe36`, sin cambios rastreados
  (untracked preservados).

### V0.2 Calidad del backend

- `make lint`, `make typecheck` verdes.
- `make test-fast`: 1,112 aprobadas, 7 deseleccionadas. `make test`: 1,119 aprobadas. Cobertura ~81%.
- Focalizado del contrato de transformaciones (85 pruebas):
  `tests/unit/artifacts/test_transforms.py`, `tests/unit/models/test_prophet_model.py`,
  `tests/unit/test_predice_transform_context.py`.
- Caso numérico cubierto: Casos 496, Exposición 126,014,024, valor transformado ≈ 0.33189533899263346,
  inversa ≈ 496 casos.

### V0.3 Legacy preservado

- 4 motores × 432 series únicas (`meta_padecimiento`/`meta_entidad`/`meta_modo`), diseases =
  {Alzheimer, Dengue, Depresión, Parkinson}, sin Obesidad en agregados canónicos.
- `reports/ProdDetails/produccion_obesidad.csv` ausente; el preliminar vive en
  `reports/ProdDetails/_preliminar_NO_GO/produccion_obesidad_PRELIMINAR.csv`.
- DVC dirigido (`reports/forecasts.dvc`, `data/processed/tableau_model.xlsx.dvc`) actualizado. No
  ejecutar `dvc add`, `dvc push` ni checkout global.

### Decisión V0

- Si cualquier validación falla: detener el entrenamiento y corregir únicamente el contrato funcional
  que falló; repetir V0 completo.
- Si todo pasa: aceptar `ad98225a` como baseline e iniciar F1.
- Una diferencia en archivos no rastreados no es fallo mientras no se modifiquen.
- Los defectos conocidos del frontend no bloquean el entrenamiento local.

---

## 3. Ejecución después de V0 PASS

### F1 — Calendario y dataset E66 v2

Único P0 real antes de entrenar. Elimina la inferencia por máximo de semanas observado y el uso
incorrecto del calendario ISO.

**Calendario epidemiológico.** Semana domingo→sábado; semana 1 comienza el domingo en o antes del
4 de enero. `period_start` = domingo epidemiológico; `ds` = lunes siguiente (solo timestamp de
modelado). El boletín E66 tiene `observation_lag_weeks: 1` declarado en configuración. Identidad
canónica: `(epi_year, epi_week)`, no la fecha ISO ni el máximo observado.

Ejemplos obligatorios:

- Fuente 2025-W53 → objetivo 2025-W52 → `ds=2025-12-22`.
- Fuente 2026-W01 → objetivo 2025-W53 → `ds=2025-12-29`.
- Fuente 2026-W02 → objetivo 2026-W01 → `ds=2026-01-05`.

Gate: 653 periodos objetivo únicos; cero duplicados `(epi_year, epi_week, entidad)`; exactamente 32
entidades por periodo; sin colisión 52/53/1; pruebas para 2014, 2020, 2025 y fronteras de año; las
anomalías históricas se clasifican, no se borran silenciosamente.

**Target semanal.** Una sola definición alimenta entrenamiento, CV, selección y validación.
`Casos_semana` es el total semanal autoritativo. Los acumulados de hombres/mujeres se convierten en
deltas causales; con ambos deltas válidos se usa su proporción para repartir el total; si la
proporción no es válida: (1) mediana causal de la proporción masculina de las últimas 13 semanas del
estado; (2) proporción nacional previa; (3) 0.5 solo si no hay historia. Asignación a enteros por
mayor residuo; siempre `hombres + mujeres = general`. Tabla completa en cero entre semanas nacionales
no nulas → fuente faltante, no cero real. Imputación del total con la misma semana epidemiológica de
años anteriores; fallback: mediana causal de 13 semanas. Negativos, revisiones y `n.e.` se conservan
con `quality_flags`. Sin z-score/IQR/clipping/reemplazos silenciosos en la primera corrida válida.

Dataset largo base: 64 series (32 estados × hombres/mujeres). Campos mínimos: fuente/año/semana,
año/semana epidemiológica, `period_start`, `ds`, entidad INEGI, sexo, `y_cases`, exposición,
`observed`, `quality_flags`. Conservar valor fuente, valor reconciliado y motivo del ajuste. Digest
del dataset reutilizado en entrenamiento y evaluación.

**Exposición.** Columna seleccionada por registry (hombres→Hombres, mujeres→Mujeres, general
derivado→Total), no por condicionales de Obesidad. Primera corrida: snapshot estático disponible;
registrar fuente, fecha de corte, columna y digest; sin fingir evolución anual de población; toda
exposición positiva; `Hombres + Mujeres = Total`; round-trip tasa→casos verificado por sexo.

Salida F1: `EpiDatasetV2` válido y versionado dentro de un run local; no reemplaza aún el dataset
productivo.

### F2 — Runner genérico y artefactos mínimos

No reutilizar `scripts/entrena.py` (entrena 111 modelos, mezcla configuración, oculta excepciones,
considera la existencia de un PKL como éxito).

**Interfaces públicas.** `SeriesKey` (disease_id, geography_level, geography_id, sex, frequency);
`TrainingSpec` (config común + bloque namespaced por motor, seed, folds, horizonte, TransformContract
efectivo, límites de recursos); `ForecastFrame` (run_id, motor, padecimiento, SeriesKey, ds,
yhat_cases, límites opcionales, método de intervalo, lineage); `EvaluationFrame` (fold/split,
SeriesKey, ds, y_true_cases, y_pred_cases, métricas centrales).

Metadata externa mínima por artefacto: schema_version, run_id, disease_id, engine_id, SeriesKey o
global_model_id, TransformContract efectivo, política/fuente/vintage de exposición, inicio/fin de
entrenamiento, digest de dataset/spec/código, seed, final_refit, archivo y digest del modelo, fecha
de creación. El loader obedece metadata; `stem.split("_")` queda solo como adaptador legacy explícito.

**Ejecución.**

```
python -m scripts.disease_run validate-data --disease obesidad
python -m scripts.disease_run benchmark --disease obesidad --stage smoke
python -m scripts.disease_run benchmark --disease obesidad --stage full
python -m scripts.disease_run refit --disease obesidad
python -m scripts.disease_run forecast --disease obesidad --horizon 52
```

Obligatorio: cada ejecución crea `runs/<run_id>/`; no escribe en `models/`, agregados globales,
Tableau ni rutas canónicas; un manifest registra pending/running/succeeded/failed por job; una
excepción termina con código ≠ 0; un archivo existente no equivale a job terminado; reanudación solo
de jobs con manifest válido; escritura normal (temporal + replace, sin más hardening adversarial);
cada motor en subprocess limpio.

**Arquitectura 64 + 47.** Entrenar exclusivamente 32 estados × 2 sexos = 64 series base. Materializar
por suma exacta: 32 generales estatales; 4 regiones × 3 sexos = 12; 1 nacional × 3 sexos = 3. Gate:
64 ajustes base únicos; cero modelos directos para generales/regiones/nacional; 47 derivadas; 111
productos finales; reconciliación exacta en cada fecha.

### F3 — Backtest común y modelos locales

**Folds.** Desarrollo: años completos 2021–2024, 52 semanas/fold. Test final bloqueado: 2025
completo. Stress: 2020 (solo reporte). Prospectivo: semanas de 2026 (solo reporte). Transformaciones,
imputaciones y features se ajustan dentro del train de cada fold; todos los motores usan los mismos
cutoffs y observaciones.

Métricas en casos absolutos: sMAPE (primaria), MASE, MAE, RMSE, WAPE, bias. MAPE no es criterio
primario.

**Primera ola de modelos (en orden):** (1) Seasonal Naive lag 52; (2) media/mediana de la misma
semana de los últimos 3 y 5 años; (3) ETS independiente; (4) regresión armónica Ridge; (5) Prophet
(count+log1p y rate_per_100k+log1p). **No** usar aún: ETSExpert actual con fallback a cero, Ridge de
stacking, LGBMExpert por serie, Ensemble/Stacking legacy, NB-GLM (hasta corregir su contrato),
N-HiTS, DeepAR. LightGBM global directo entra en 2.ª ola si los simples no dan margen o tras el primer
forecast preliminar.

**Selección.** Todo candidato produce predicciones para las 64 series. Elección por SeriesKey sobre
folds 2021–2024. Seasonal Naive es fallback y puede ganar producción. Un challenger sustituye al
baseline solo con mejora relativa mínima de 5% en sMAPE; dentro de la banda de 5% se desempata por
MASE, RMSE y tiempo. Congelar la selección antes de abrir 2025; 2025 es gate de aceptación, no fuente
de retuning. Si el conjunto seleccionado degrada la mediana sMAPE de Seasonal Naive más de 5% o el
nacional General más de 10%, se rechazan challengers y se conserva Seasonal Naive; no se ajustan
hiperparámetros con 2025. Predicciones negativas o no finitas invalidan el motor. Los intervalos
pueden quedar nulos en el benchmark preliminar; se declaran honestamente.

### F4 — Entrenamiento Obesidad ASAP

**Smoke.** Seasonal Naive sobre las 64 series; motores ajustables sobre seis series elegidas por
datos (volumen alto/medio/bajo, ambos sexos); un fold, una configuración; 10–15 min objetivo;
cualquier fallo preserva el run y bloquea solo el motor afectado.

**Full benchmark (M3 Pro 12 CPU / 36 GB).** Límite RSS 24 GB (reservar ~12 GB para sistema);
BLAS/OpenMP a 1 thread antes de importar librerías en el subprocess; nunca `n_jobs=-2`. Seasonal:
1×1; ETS: hasta 6 workers × 1 thread; Ridge armónico: 1×2; Prophet: 4 workers × 1 thread (máx 6 tras
smoke); LightGBM global futuro: 1×6. No paralelizar simultáneamente series, folds y grids. Prophet en
dos etapas: (1) grid corto sobre las 6 sentinel; (2) una o dos mejores configuraciones sobre 64
series × 4 folds. Prohibido repetir el grid de 18×64×4. Tiempos objetivo: Seasonal <2 min, ETS
<20 min, Ridge <10 min, Prophet <60 min, benchmark completo <2 h. Superar el tiempo es fallo de
eficiencia, no motivo para borrar evidencia.

**Refit y forecast.** Tras congelar ganadores: refit con toda la historia aprobada hasta el último
periodo; artefacto con `final_refit=true`; verificar que el modelo guardado contiene el último
periodo; 52 semanas futuras para las 64 bases; derivar y reconciliar las 47 restantes; exactamente
111 series; guardar solo bajo el `run_id`; reporte preliminar (métricas, tiempos, anomalías, modelo
ganador por serie); lifecycle de Obesidad pasa como máximo a `trained`, fuera de rutas públicas.

Gate Obesidad entrenada: dataset y calendario válidos; 64/64 bases; 111/111 productos; cero
duplicados; cero negativos/no finitos; reconciliación exacta; evaluación OOS común; refit final
comprobado; forecast y metadata cargables desde entorno limpio; legacy byte-idéntico; ninguna salida
canónica modificada.

### F5 — Prueba real N+1 con F50

Usar el bloque `anorexia_f50` deshabilitado en `config/data/cuadros.yaml`. Permite:
habilitar/configurar el padecimiento, añadir su definición de cuadro, declarar target/calendario/
exposición/lifecycle. No permite: editar lógica Python genérica, añadir condicionales por F50, editar
JavaScript para hacerlo visible, publicar F50. Gate N+1: extracción y validación de datos;
compilación del registry; manifest de 64 series o estructura declarada; smoke con Seasonal Naive;
artefactos por las mismas interfaces; cero cambios en código genérico. F50 puede quedar `configured`
o `trained`; no necesita publicarse para demostrar N+1.

### F6 — Publicación (separada del entrenamiento)

Requiere aprobación explícita del usuario sobre el `run_id` elegido. Antes de publicar: corregir las
11 pruebas frontend y `npm run check`; regenerar/sincronizar corpus RAG; manifest público desde el
registry; selección canónica desde resultados OOS reales; materializar agregados por shards + upsert
preservando legacy; intervalos documentados o declarar point-only si el frontend lo admite;
revalidar 432 series legacy + 111 Obesidad sin pérdida; suites completas backend/frontend; revisar
diff DVC por target concreto; promover código/datos/modelos/frontend en commits separados; sin
`dvc push`/`git push`/despliegue sin gate final. Rollback: el manifest público conserva el `run_id`
anterior; revertir = seleccionar el manifest previo, no reconstruir modelos.

---

## 4. Secuencia de implementación y commits

1. **C1 — Calendar + EpiDatasetV2**: calendario epidemiológico, lag configurable, target reconciliado,
   exposiciones por sexo y pruebas de fronteras.
2. **C2 — Runner + contratos**: SeriesKey, TrainingSpec, manifests, metadata, salida por run_id,
   errores visibles y 64+47.
3. **C3 — Evaluador + baselines**: folds comunes, métricas centrales, Seasonal Naive, ventanas
   estacionales, ETS y armónica.
4. **C4 — Prophet corregido**: dos TransformContracts, tuning en dos etapas, subprocess aislado y smoke.
5. **C5 — Benchmark/refit/forecast Obesidad**: full CV, 2025 bloqueado, selección, refit y 111 series
   preliminares.
6. **C6 — F50 N+1**: configuración, datos y smoke sin cambios genéricos.
7. **C7 — Publicación**: solo tras aprobación; frontend, RAG, DVC y manifests públicos.

Cada commit pasa lint, typecheck y pruebas focalizadas. C1–C6 no autorizan push, DVC ni publicación.

---

## 5. Definición final de éxito

El trabajo está terminado cuando: Obesidad tiene un dataset semanal sin colisiones; el mismo target
alimenta train/CV/evaluación; las exposiciones son correctas por sexo; se entrenan 64 series y se
derivan 47; Seasonal Naive compite en igualdad y puede ganar; los motores comparados usan folds y
métricas comunes; el modelo elegido tiene refit final; el forecast preliminar contiene 111 series
reconciliadas; cualquier run se reproduce desde metadata y digests; F50 atraviesa el mismo flujo sin
editar código genérico; legacy permanece intacto; ningún padecimiento aparece públicamente antes de
`lifecycle=published` y aprobación explícita.
