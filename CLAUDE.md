# CLAUDE.md: Guia de Desarrollo EpiForecast-MX

## Estado P0 del flujo semanal — 2026-09-02 (tercera tanda: correctiva, cerrada en local)

Esta sección sustituye cualquier instrucción inferior que presente `make update-week` como
receta activa. Backend: rama `p0/namespace-e-inmutabilidad-del-sello`, **26 commits rebased
sobre el `main` remoto `16476a98`** (tip `f88a065e`; respaldo local del tip previo `584cf72d`
en `respaldo/p0-584cf72d-2026-09-02`), árbol limpio, **enviada a `origin`**. PR draft **#14** (https://github.com/EpiForecastMX/EpiForecast-MX/pull/14) abierta en `f88a065e`, con el CI remoto `33634940281` verde: Code Quality PASS, Tests PASS (2 324 passed, 497 skipped exactos, 66 deselected, cobertura 77,00 %), Integration skipped por diseño. **Sin merge, sin DVC, sin publicación ni deploy.**
El remoto `16476a98` sólo traía dos commits de datos del CI (registry W33 y punteros DVC
W33 de neuro, sin Dengue); `origin/main` local sigue en `a9a694c8` porque no se ha hecho
pull. Frontend: `main@0e777995`, intacto, sin worktrees.

`make update-week` sigue bloqueado en preflight **por autorización, no por código**: P0.1,
P0.2 y P0.8 están cerrados; correr el carril real exige red (pull, `dvc pull`,
sincronización aditiva, API de Gemini para el índice RAG) y la decisión de publicar (P1).
Flujo cableado y probado: `materialize` (git archive de los HEAD; escribe
`materializacion.json`, que `hydrate`, `bump-cache`, `run-gates` y `seal` exigen con sus
HEAD y política) → `hydrate` (sandbox con SOLO la allowlist `entradas/2`: 44 entradas
reales incluidas `dengue_boletin.csv`, su manifiesto, `inegi.csv`, `models/*/*/*_completo.csv`
por patrón y el ONI cacheado; directorios scratch; contrato del HEAD: catálogo, registry y
profundidad mínima 52 con continuidad MMWR) → generadores en el sandbox con `--out` →
`bump-cache` (DATA_VERSION y cada `?v=`, imports anidados incluidos, plan en memoria) →
`run-gates` (evidencia en `gates.en_curso/` con marcador; huérfanos por pgid+arranque;
residuos apartados, nunca borrados; digest del ejecutable gobernante) → `seal` (evidencia,
cobertura, cadena de caché, inmutables, `revisa_aditivo` base ⊆ candidato, semanas atadas
a los cortes y a `boletin.ultima_semana`, y la poda PREVISTA con retirables/lápidas, todo
ANTES de podar) → `prepare-worktrees` (rollback; revalida gates contra la política del
HEAD canónico) → `apply` (re-liga bajo el lock; composición del par antes de `aplicado`,
también en el no-op) → `check-completeness` → `discard-worktrees --manifiesto` (ligado a
run_id, digest, lock, estado y a que git reconozca cada worktree). `CONFINAMIENTO_LISTO =
True`; P0.11 = opción C.

Datos: la tabla 333 rastreada quedó **reparada** (432 filas, `76d3e311…`, commit
`dd54d51b`, autoridad `produccion_dengue.csv` documentada en `catalog.py`) y la causa raíz
corregida en `merge_all_models` (`4962e582`). `WEEKS_LIMIT = 15` en
`reselect_motor_2026.py` **queda como decisión pendiente documentada**: el comentario dice
«= boletín más reciente» pero ningún contrato canónico fija la ventana, y cambiarla
re-selecciona motores de 333 series.

Gate vigente: 902 pruebas de publicación; `make test-fast` = **2,820 passed, 1 skipped, 66
deselected** (cero skips nuevos); Ruff, mypy, `bash -n` y `git diff --check` verdes; **85
mutaciones del código (las 42 originales con anclas al día, 28 de las defensas nuevas y
16 de la auditoría final), 85 vistas caer**; auditoría adversarial final por tres agentes
ciegos: sus hallazgos alto/medio corregidos en `83950f96` y `a0fb313b`.

Ensayo real del 2-sep (evidencia en `planes/ensayo_P012_2026-09-02/`, con `SHA256SUMS`):
**tramo 1**, la cadena de generación completa sobre W31 sin red —materialize, hidratación
real (44 entradas, contratos PASS), los diez pasos de generación en el sandbox, `bump-cache`
(DATA_VERSION 20260824→20260825, kb.js?v=104→105, app.js?v=138→139) y `run-gates`: `cifras`
PASS y **`rag` FAIL** porque el índice RAG rastreado no cubre el `knowledge.json` regenerado
y reconstruirlo exige GEMINI_API_KEY (red): fallo cerrado, sin sello. **Tramo 2**, sello →
par desechable sobre la composición real con un cambio fuera del corpus RAG: gates PASS,
run `e147ff8deb914b4a`, prepare/apply/check en clones locales con composición aplicada ==
sellada, no-op verificado, byte alterado → check falla y apply deja el par inválido,
discard ligado al manifiesto; repos reales con un solo worktree y frontend limpio. Los tres
hallazgos que el ensayo destapó (directorios scratch, ONI sin red, NB-GLM constante) están
corregidos en `98faf4d3` y `a0fb313b`.

Plan auditado:

- `../planes/PLAN_ACTUALIZACION_SEMANAL_UNIFICADA_2026-09-01_v4.md`, SHA256
  `5cfdf5a4a2d8e5ed1acf004e8c90a00e929dfd217ba051fff925e742fe9e233d`.

## Estado CI semanal — 2026-09-01

- PR #12 quedó en `main` mediante merge commit `59488c57`; la rama de trabajo ya fue
  borrada local y remotamente. Después se creó `ci/skip-budget-ets-legacy`, hoy mergeada
  pero todavía presente local y remotamente.
- Runs remotos verificados: PR #13 `33466506664` y push final a `main` `33467472543`,
  ambos con Code Quality PASS, Tests PASS e Integration Tests SKIPPED.
- En Ubuntu: 2,509 colectadas = 1,946 passed + 497 skipped + 66 deselected; cobertura
  74.50% con umbral canónico único de 70. El presupuesto de skips es exactamente 497.
- El cron del lunes ejecuta Quality y Tests. Integration es legacy y sólo corre con
  `workflow_dispatch`; en schedule debe aparecer SKIPPED, no verde.
- El incidente está arreglado en push/PR, pero su cierre operativo espera el schedule
  del 7-sep-2026. La rutina `trig_0182z2jL5YUwBbmTmHnbPS3t` lo comprueba a las 06:50 UTC.
- Rollback únicamente por causalidad demostrada: `git revert -m 1 59488c57` en rama y
  PR; nunca reset ni force-push de `main`.
- Los checkpoints `main@cb7695d9` y frontend `main@5f8666dc` describen el cierre histórico
  de esa tanda, no el worktree actual; usar la sección P0 superior para reanudar. Persisten
  dos ramas ya mergeadas, locales y remotas:
  `ci/skip-budget-ets-legacy` y `fix/frontend-deudas`.
- Los cuatro agregados legacy ya no tienen doble guarda: viven en `tests/integration/`,
  se deseleccionan en el job normal y fallan por ausencia en el manual. Pendiente después
  del schedule: política de skips/restauración del carril Integration, readiness 1/4→4/4,
  prototipo de cadena sintética y sólo entonces acotar
  los 460 nodeids en
  156 grupos que siguen pendientes en D1. Índice vigente: `docs/DEUDAS_VIGENTES.md`.

## Resumen del Proyecto

**EpiForecast-MX** es una plataforma de inteligencia epidemiologica multi-modelo para el **IMSS**. Pronostica la incidencia semanal de Depresion (F32), Parkinson (G20) y Alzheimer (G30) en las 32 entidades federativas de Mexico con un horizonte de 52 semanas. Utiliza **Prophet**, **DeepAR** (GluonTS + PyTorch), **Ensemble** (Prophet + XGBoost) y **Stacking** (Prophet + ETS + LightGBM + Ridge) como motores de pronostico. Cada modelo genera 333 artefactos .pkl (3 padecimientos x ~111 combinaciones estado/region/sexo).

## Comandos de Ejecucion (Makefile)

### Pipeline de Datos
- `make preprocess`: Ejecuta todo el flujo de limpieza y mapeo INEGI (secuencial).
- `make get-dataset`: Descarga el dataset RAW (SINAVE).
- `make filter ARGS="padecimiento.tipo='Depresion'"`: Filtra por padecimiento.
- `make clean`: Limpieza de nulos, duplicados y formato.
- `make transform`: Feature engineering (outliers, regiones, agrupacion).
- `make get-inegi`: Descarga datos demograficos INEGI.
- `make mapper`: Mapea entidades con INEGI.

### Entrenamiento y Modelado (Multi-Modelo)
- `make train`: Entrena segun el `modelo_activo` en `config/base.yaml`.
- `make train-prophet`: Fuerza entrenamiento con Prophet (CPU, paralelo con joblib).
- `make train-deepar`: Fuerza entrenamiento con DeepAR (local, CPU/MPS).
- `make train-ensemble`: Fuerza entrenamiento con Ensemble (Prophet + XGBoost).
- `make train-stacking`: Fuerza entrenamiento con Stacking (Prophet + ETS + LightGBM + Ridge).
- `make train-all`: Entrena los 4 modelos secuencialmente.
- `make avance5`: Entrena el Ensemble con visualizaciones comparativas para los 3 padecimientos.
- `make avance5 ARGS="padecimiento.tipo='Alzheimer'"`: Ensemble para un solo padecimiento.
- `make train-sagemaker`: Build imagen Docker + lanzar entrenamiento DeepAR en AWS SageMaker (GPU).
- `make train-sagemaker-build`: Solo build + push imagen Docker a ECR.
- `make train-sagemaker-local`: Build imagen + test local con Docker.
- `make train-sagemaker-parallel`: 3 jobs paralelos (1 por padecimiento).
- `make train-sagemaker-fast`: Build + 3 jobs paralelos.

### Prediccion y Comparacion
- `make predict ARGS="modelo_activo='deepar'"`: Genera pronosticos para un modelo especifico.
- `make predict-all`: Genera pronosticos de los 4 modelos secuencialmente (Prophet, DeepAR, Ensemble, Stacking).
- `make tableau`: Construye dataset Tableau con seleccion automatica de modelo productivo (SMAPE).
- `make compare`: Genera graficos de alta calidad comparando Real vs los 4 modelos.
- `make compare-metrics`: Genera comparativa de metricas (Excel + HTML con badges Overfitting/Leakage).
- `make tabla-produccion`: Genera tabla de 333 modelos de produccion (SMAPE, validacion semanal).
- `make report`: Genera reporte HTML de resultados.
- `make bitacora`: Genera bitacora HTML del modelado Prophet v1-v6.
- `make reporte-avance5`: Genera reporte Avance 5 (Markdown + 18 graficos + CSV de 333 modelos de produccion).

### Calidad y Pruebas
- `make quality`: Ejecuta lint (Ruff), typecheck (Mypy) y tests (Pytest).
- `make format`: Formatea el codigo automaticamente con Ruff.
- `make test-fast`: Ejecuta solo pruebas unitarias rapidas (sin slow/integration).
- `make lint`: Verifica formato y calidad sin modificar.
- `make typecheck`: Type check con mypy.

### DVC y Datos
- `make data-pull`: Descarga datos desde S3 via DVC.
- `make data-push`: Sube datos a S3 via DVC.
- `make models-push`: Versiona modelos y sube a S3.
- `make s3-sync`: Sync CSVs + forecasts directo a S3 (sin DVC, acceso rapido para Tableau/dashboard).
- `make data-weekly`: Agrega y versiona nuevos datos semanales del boletin.

### Pipeline Compuesto
- `make model-pipeline`: Pipeline completo (train -> models-push -> predict -> report -> forecast-push).

## Arquitectura y Estandares

### Patron Factory (SOLID)
- Los modelos heredan de `epiforecast.models.base.ForecastModel`.
- Interfaz: `fit()`, `predict()`, `cross_validate()`, `save()`, `load()`, `get_params()`, `run()`.
- Se registran mediante el decorador `@register_model("nombre")`.
- Se instancian via `epiforecast.models.factory.create_model(name, **kwargs)`.
- Implementaciones: `ProphetForecaster` (Prophet), `DeepARForecaster` (GluonTS + PyTorch), `EnsembleForecaster` (Prophet + XGBoost), `StackingForecaster` (Prophet + ETS + LightGBM + Ridge).
- No importar clases de modelos directamente en scripts; siempre usar `create_model`.

### Configuracion Dinamica
- `config/base.yaml`: Controla `modelo_activo`, padecimiento, rutas y opciones globales.
- `config/models/prophet.yaml`: Hiperparametros Prophet, grid de CV, estacionalidad, cambios de regimen.
- `config/models/deepar.yaml`: Hiperparametros DeepAR (epochs, capas, dropout, etc.).
- `config/models/ensemble.yaml`: Hiperparametros Ensemble (Prophet + XGBoost).
- `config/models/stacking.yaml`: Hiperparametros Stacking (Prophet, ETS, LightGBM, Ridge meta-learner).
- `config/data/preprocessing.yaml`: Parametros de preprocesamiento.
- `config/features/feature_engineering.yaml`: Parametros de feature engineering.
- `config/visualization/plots.yaml`: Estilos de graficos.
- `config/infrastructure/logging.yaml`: Configuracion de loguru.
- Las rutas en `config/base.yaml` usan interpolacion OmegaConf: `./models/${modelo_activo}`.
- Overrides CLI: `python -m scripts.entrena modelo_activo='deepar' padecimiento.tipo='Alzheimer'`.
- La config se carga via `from epiforecast.utils.config import conf, logger`.

### Entrenamiento SageMaker (DeepAR con GPU)
- Imagen Docker: `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime` (NVIDIA T4 en `ml.g4dn.xlarge`).
- Entry point: `scripts/entrena_sagemaker.py` — detecta entorno, copia datos, fuerza `modelo_activo=deepar`.
- Launcher: `aws/sagemaker_launcher.py` — build ECR, lanzar job, test local.
- Cuenta AWS: `564141855321`, bucket `s3://epiforecast-mx-data`, region `us-east-1`.
- Dependencias del container: `aws/requirements_sagemaker.txt` (sin DVC, sin dev tools).
- Flujo: `make train-sagemaker` → build + push ECR + lanzar job → descargar modelos con `aws s3 sync`.

### Estructura del Proyecto
```
EpiForecast-MX/
├── aws/                          # Infraestructura SageMaker (Dockerfile, launcher)
├── config/                       # Configuracion YAML unificada
│   ├── base.yaml                 #   Modelo activo, rutas, padecimiento
│   ├── models/                   #   Hiperparametros por algoritmo
│   ├── data/                     #   Preprocesamiento
│   ├── features/                 #   Feature engineering
│   ├── visualization/            #   Estilos de graficos
│   └── infrastructure/           #   Logging
├── src/epiforecast/              # Paquete Python principal
│   ├── models/                   #   Factory + Prophet + DeepAR + Ensemble + Stacking + base
│   ├── data/                     #   Extraccion PDF, ingestion INEGI, preprocesamiento
│   ├── evaluation/               #   Metricas (RMSE, MAE, MAPE, SMAPE, MASE)
│   ├── visualization/            #   Graficos estilo IMSS
│   ├── features/                 #   Feature engineering demografico
│   ├── utils/                    #   Config, paths, helpers
│   └── pipelines/                #   Pipeline base
├── epi_modules/                  # Consola interactiva EPI
│   ├── engine.py                 #   EpiEngine (Makefile, traduccion Gemini, ejecucion)
│   ├── intent.py                 #   Clasificador de intents, typos, fuzzy matching
│   ├── theme.py                  #   Tema Rich IMSS (PANTONE verde, dorado, guinda)
│   ├── features/                 #   Modulos de funcionalidad
│   │   ├── ai_chat.py            #     Chat con KnowledgeBase local + Gemini fallback
│   │   ├── dashboard.py          #     Dashboard multi-panel Rich Layout
│   │   ├── data_cache.py         #     Cache lazy-loading de datos del proyecto
│   │   ├── data_explorer.py      #     Explorador interactivo del boletin
│   │   ├── forecast_viewer.py    #     Visor de pronosticos con sparklines
│   │   ├── knowledge_base.py     #     Base de conocimiento local (sin IA externa)
│   │   └── model_browser.py      #     Navegador paginado de 333 modelos
│   └── views/                    #   Modulos de presentacion
│       ├── approval.py           #     Gate de aprobacion por nivel de riesgo
│       ├── banner.py             #     Banner ASCII de bienvenida
│       ├── common.py             #     Logs, pipeline, stats, scripts, historial
│       ├── health.py             #     Dashboard de salud del sistema
│       ├── help_menu.py          #     Menu de ayuda multi-seccion
│       └── targets.py            #     Navegador de targets Makefile
├── scripts/                      # Entry points CLI (~24 scripts)
├── tests/                        #   unit/ + integration/ (136 archivos test, 2,509 colectados)
├── data/                         # raw/ → interim/ → processed/ (DVC)
├── models/                       # Artefactos .pkl (DVC, 4x333 = 1332 modelos)
├── reports/                      # Graficos, reportes HTML, forecasts, ProdDetails/
├── epi.py                        # Entry point de la consola interactiva EPI
└── Makefile                      # Orquestacion MLOps (~55 targets)
```

### Consola Interactiva EPI
- Entry point: `python epi.py`. REPL con Rich TUI y tema IMSS 2026.
- Flujo: entrada → `normalize_typos()` → `classify_intent()` → router a handler o `engine.translate()`.
- **Intent classifier** (`epi_modules/intent.py`): 17+ intents (saludo, salir, limpiar, banner, dashboard, chat, datos, modelos, pronostico, scripts, ayuda, targets, stats, logs, pipeline, salud, historial).
- **KnowledgeBase** (`epi_modules/features/knowledge_base.py`): Responde con datos reales del proyecto (metricas, boletin, modelos, equipo, semanas epidemiologicas). 18+ handlers en cadena de prioridad.
- **Chat IA** (`epi_modules/features/ai_chat.py`): KnowledgeBase local primero, Gemini como fallback con contexto enriquecido e historial conversacional.
- **Dashboard** (`epi_modules/features/dashboard.py`): Panel multi-seccion con datos del boletin, inventario de modelos, metricas forecast, stats de sesion.
- **Data explorer** (`epi_modules/features/data_explorer.py`): Navegador del boletin con filtros y barras Unicode.
- **Model browser** (`epi_modules/features/model_browser.py`): Tabla paginada de 333 modelos con SMAPE color-coded y badges diagnosticos.
- **Forecast viewer** (`epi_modules/features/forecast_viewer.py`): Sparklines de pronosticos a 52 semanas.
- **Aprobacion** (`epi_modules/views/approval.py`): Gate de confirmacion con clasificacion de riesgo (safe/modify/destructive).
- **Historial persistente**: Ultimos 100 comandos en `.epi_history.json`.
- **Logging**: `logs/epi.log` con timestamps ISO.

### Visualizacion
- Los graficos comparativos se guardan en `reports/forecasts/comparacion_modelos/`.
- Los graficos del Avance 5 (18 PNGs) se guardan en `reports/figures/ModeloFinal/`.
- Paneles individuales (barras, zoom, produccion) en subcarpetas de `comparacion_modelos/`.
- Usan la zona horaria `America/Mexico_City` (UTC-6) para las marcas de tiempo.
- Estilo: Historial Real (Gris grueso), Prophet (Teal #004d40 dash-dot), DeepAR (Vino #880e4f dashed), Ensemble (Naranja #FF6F00), Stacking (Indigo #1A237E).
- La ficha tecnica al pie de cada grafico forecast muestra el nombre real del modelo (detectado desde `meta_modelo` del CSV).
- Todos los reportes siguen la paleta IMSS 2026.

### Seleccion de Modelo de Produccion
- `scripts/genera_tabla_produccion.py` genera la base inicial de `reports/ProdDetails/tabla_333_modelos_produccion.xlsx` por SMAPE de validacion cruzada.
- **`scripts/reselect_motor_2026.py` (canónico desde 2026-04-30)**: re-selecciona el motor productivo usando SMAPE sobre realidad reciente del Boletin SINAVE 2026.
  - Regla 1: serie con >=10 sem reales 2026 y total >=10 casos -> SMAPE 2026 real es criterio primario; MASE como desempate.
  - Regla 2: serie con >=10 sem pero <10 casos (ruidosa, divisiones cercanas a cero infladas) -> forzar Ensemble como default seguro.
  - Regla 3: serie con <10 sem reales (4 regiones agregadas y huecos puntuales) -> respetar asignacion CV anterior.
  - Genera `reports/ProdDetails/auditoria_motores_2026.xlsx` con auditoria de los 333 combos: motor anterior, motor nuevo, SMAPE **y MASE** de los 4 motores en 2026 real (MASE = naive estacional lag 52 sobre la historia previa), criterio de seleccion.
  - Distribucion productiva actual (post 2026-04-30, 227 cambios sobre los 333): Prophet 126, Ensemble 95, DeepAR 78, Stacking 34. `motor_ganador` global = Prophet.
- **Hoja 1 (Produccion)**: 333 filas x ~50 columnas. Metricas por modelo, diagnosticos, comparativa historica + 13 columnas de auditoria 2026 (9 originales + 4 `mase_2026_*`).
  - `casos_52_semanas_futuro`: suma de yhat del horizonte futuro (entero).
  - `smape_prod/mase_prod/rmse_prod/mae_prod`: metricas CV del modelo seleccionado (recalculadas tras la re-asignacion).
  - `overfitting`: ratio smape_test/smape_train — Alto (>2x), Moderado (>1.3x), OK.
  - `leakage`: smape_train < 0.5% = Sospechoso, else OK.
  - `casos_prev_52_semanas_real / _pronos`: comparativa historica (enteros).
  - `precision_historica`: ratio pronos/real como porcentaje.
  - `pron_sem_previa / realidad_sem_previa`: ultima semana para validar con boletin nuevo.
  - `modelo_produccion`, `tipo_modelo`, `region_asignada` (n/a si propio), `justificacion`.
  - `n_semanas_real_2026`, `total_real_2026`, `smape_2026_{prophet,deepar,ensemble,stacking}`, `mase_2026_{prophet,deepar,ensemble,stacking}`, `smape_real_2026_ganador`, `motor_anterior`, `criterio_seleccion`.
- Series con incidencia cero o baja confianza (<5 casos/52sem) se reasignan al modelo regional.
- Predicciones redondeadas a enteros. Formato Excel con paleta IMSS 2026, filtros y paneles congelados.
- Graficos embebidos: `scripts/excel_produccion_charts.py` genera 6 PNGs con paleta IMSS.
- Formateo: `scripts/excel_produccion_fmt.py` aplica estilos institucionales.
- **Pipeline canonico tras nuevo boletin**: `make tabla-produccion` -> `python3 scripts/reselect_motor_2026.py` -> `python3 scripts/build_tableau.py` -> `python3 scripts/build_web_knowledge.py` -> `python3 scripts/genera_validacion_semanal.py` -> `make compare` (PNGs).
- **Cuadros de rendimiento 2026 en el EpiBot**: `build_web_knowledge.py` emite la seccion `rendimiento_2026` en `knowledge.json` (por padecimiento × motor: SMAPE y MASE mediana/promedio + fila Productivo). Neuro (Alzheimer/Depresion/Parkinson) desde `auditoria_motores_2026.xlsx`; **Dengue** (cohorte propia, motores DeepAR/Prophet/NBGLM) desde `produccion_dengue.csv`, que ahora guarda `mase_real_<motor>` (via `produccion_dengue.py`, mismo naive estacional lag 52). Agregacion robusta a MASE degenerado (`_MASE_CAP=20`: en Dengue año-bajo una serie casi-cero puede disparar el MASE a miles y contaminar el promedio). El EpiBot los dibuja con `answerRendimientoPorPadecimiento` (+ `_cuadroDengue`); disparadores: "rendimiento por padecimiento", "smape y mase por padecimiento", "cuadro de dengue". Se regenera solo en `make update-week` (paso 4 reselect, paso 7 dengue-produccion, paso 9 knowledge). Validado por recomputo independiente from-scratch (metricas propias) contra lo desplegado: 0 discrepancias.

### Validacion Semanal
- `scripts/genera_validacion_semanal.py` genera `reports/ProdDetails/validacion_semanal.html`.
- Compara pronosticos de los 4 modelos vs datos reales del boletin SINAVE mas reciente.
- Desglose por sexo (Nacional y Regional) para cada padecimiento.
- Actualiza columna `realidad_sem_previa` en el Excel de produccion.

### Validacion Prospectiva OOS (pronostico congelado)
- `scripts/pronostico_congelado.py` (`make congela-pronostico` / `make valida-prospectivo`), cubre los 4 padecimientos (neuro via tabla_333 + Dengue via produccion_dengue.csv).
- Existe porque `smape_real_2026` (la metrica de seleccion de motor) es IN-SAMPLE: el modelo se entrena sobre la serie completa incluyendo 2026 H1 y se puntua su ajuste in-sample. Ver `docs/research/hallazgos/DENGUE_AUDITORIA_LEAKAGE.md`.
- `freeze`: guarda el pronostico del motor productivo por serie SOLO para la cola futura (ds > corte = no vista) en `reports/ProdDetails/congelado/forecast_congelado_<fecha>.csv` + puntero `forecast_congelado_latest.txt`. Snapshot inicial (2026-06-05): corte W20, 396 series, 16,032 filas.
- `validar`: confronta el congelado vs el boletin vigente, reporta SMAPE/MAE OOS por serie y nacional en `reports/ProdDetails/validacion_prospectiva.html` (+ `.csv`). Solo puntua semanas posteriores al corte (genuinamente no vistas).
- **Operacion:** correr `make valida-prospectivo` tras cada boletin nuevo ANTES de re-entrenar, para acumular desempeno OOS honesto. NO re-congelar cada semana (reiniciaria la prueba); re-congelar solo para fijar un nuevo punto de partida. Criterio: si OOS se mantiene ~ in-sample, la seleccion es valida; si OOS > 2x in-sample, migrar la seleccion a `smape_prod` (CV rolling) o a forecast bloqueado corte fin-2025.

### Tableau y Modelo Productivo
- `scripts/build_tableau.py` genera `data/processed/tableau.csv` con datos de los 4 modelos.
- Seleccion automatica de `modelo_productivo` basada en SMAPE por grupo (padecimiento, entidad, modo).
- Columnas: `yhat` (mejor prediccion, entero), `modelo_productivo`, `yhat_{modelo}` (enteros), `{metrica}_{modelo}`, metricas standalone.
- Todas las columnas `yhat*` se redondean a enteros antes de guardar (no existen fracciones de caso).
- Metricas calculadas in-situ desde `y_real` vs `yhat_{modelo}` (no depende de `*_completo.csv`).

### MLflow (Experiment Tracking)
- Integracion opcional: `pip install -e ".[mlflow]"`. No-op si no esta instalado.
- `epiforecast/utils/mlflow_logger.py`: wrapper que registra cada run de entrenamiento (metricas, parametros, tiempo).
- Se invoca automaticamente en `scripts/entrena.py` despues de cada modelo entrenado.
- Runs almacenados en `mlruns/` (local, no requiere servidor). Visualizar con `mlflow server --backend-store-uri ./mlruns`.
- Naming: `{modelo}_{padecimiento}_{entidad}` (ej: `stacking_Depresion_Baja California`).
- Metricas registradas: rmse, mae, mape, smape, mase, elapsed_seconds.

### CI/CD (GitHub Actions)
- `ci.yml`: `quality` (ruff+mypy) → `test` (todo lo no `slow/integration`, con cobertura)
  → `integration`.
  Los dos primeros corren en push a main/refactor/*, PRs y el cron de los **lunes 06:00 UTC**.
  **`integration` SOLO con `workflow_dispatch`**: es el carril legacy, exige la cadena sellada
  de `runs/` (gitignored) y en un runner limpio se salta el 87% de sus pruebas; aparece como
  **omitido** en las corridas programadas en vez de reportar un verde que no se comprueba.
  `concurrency` agrupa por `event_name` y **exime al `schedule` de la cancelación**, para que un
  push a main no se lleve por delante el run semanal.
- `scrape_boletines.yml`: Scraping diario automatizado de boletines SINAVE (Selenium + Chrome).
- `process_boletines.yml`: Procesamiento de PDFs con Camelot, merge al dataset consolidado.
- `gsheets.yml`: Publicacion de datos Tableau a Google Sheets (service account).

### Dengue (4.o padecimiento, EN PRODUCCION)
> Estado: COMPLETO y en vivo. Serie 2018-2026, 4 motores cohort-aware, productivos DeepAR+Prophet, web en epiforecast.mx/dengue y EpiBot responde Dengue (handler `answerDengue`). Detalles abajo.
- **Cohorte:** `epiforecast.constants.NEURO_CONDITIONS` = [Depresion, Parkinson, Alzheimer] es la cohorte neurologica de produccion (333 modelos). Dengue se incorpora con pipeline propio. Usar `epiforecast.utils.cohorts.is_neuro(pad)` / `filter_neuro(df)` para distinguir (NO repetir `df.isin(NEURO_CONDITIONS)`). Los flujos neuro (filter modo "General", entrena, reselect_motor_2026, genera_validacion_semanal, build_web_knowledge, build_tableau) filtran a la cohorte neuro; Dengue se entrena solo con `padecimiento.tipo='Dengue'` explicito.
- **Extraccion:** Dengue vive en una tabla aparte del boletin (Cuadro 7.2, 3 severidades A97.0/A97.1/A97.2) que `dengue_extractor.py` agrega en un solo "Dengue". Soporte esquema OMS 2009 (A97.x) con dos layouts segun el año: **producción 2020+** (12 col, "acum. año anterior" por severidad) e **histórico 2018-W27..2019** (10 col, "acum. año anterior" solo en la 1ª severidad, etiquetas M/F; ver `dengue_historico.py`); el branch por año en `extract_dengue_from_pdf` conmuta reshape/validación. Serie resultante: **2018-W27..2026 (~391 sem nacionales)**. El esquema viejo OMS 1997 (A90/A91, 2014→2018-W26) usa otra tabla (por estatus de caso Confirmados/En Estudio, layouts de 2 bloques en 2014-2015 y 3 en 2016-2018H1) y NO se mergea al pipeline de producción (cambia taxonomía y definición). `_SOURCE_CORRECTIONS` corrige erratas de fuente conocidas (Zacatecas 2024-W41).
- **Serie histórica A90/A91 SEPARADA (contexto/EDA, NO entrena):** `dengue_historico_a9091.py` extrae Dengue **confirmado por sexo** del esquema viejo por **posición** (pdfplumber: camelot/extract_table fallan porque el espacio es separador de miles). Agrupa palabras en renglones por hueco vertical y en columnas por banda de x; suma SOLO las columnas con encabezado M/F (confirmados del año en curso, excluye año anterior y "En Estudio"); valida vs el renglón TOTAL impreso. `make dengue-historico-a9091` -> `scripts/extrae_dengue_a9091.py` -> `data/interim/dengue_a90a91_{historico,nacional,manifest}.csv` (gitignored, regenerables; `Padecimiento="Dengue_A90A91"`). Cobertura validada ~226/235 sem 2014-2018H1.
- **Pipeline Dengue (Makefile):** `make dengue-extract` -> `make dengue-merge` (+ dvc add/push del consolidado + commit .dvc) -> `make dengue-prep` (lee del CONSOLIDADO via override `data.raw_data_file`, NO del data_raw.csv neuro) -> `make dengue-train-estatal MODELO=<prophet|deepar|ensemble|stacking>` (los 4) -> `make predict-all ARGS="padecimiento.tipo='Dengue' padecimiento.modelado_hibrido=False"` -> `make dengue-produccion` (selector DeepAR/Prophet) -> `make dengue-web`. **`make dengue-web` tambien regenera `knowledge.json` (via `build_web_knowledge.py`, que incluye la seccion `dengue` del EpiBot) y lo copia a `epibot/knowledge.json`** — el EpiBot ya responde sobre Dengue (handler `answerDengue`) y asi no queda stale tras un boletin nuevo; si tocas `kb.js`/`entities.js` sube el cache-bust `?v=N`. O `make dengue-pipeline` (extract+merge+prep). El `Makefile` ya usa `.venv/bin/python` por default (`PYTHON ?=`); ya NO hace falta pasar `PYTHON=.venv/bin/python` (override con `make ... PYTHON=python3` si tu venv ya está activo).
- **Helper de cohorte:** `epiforecast.utils.cohorts.is_count_log_cohort(pad)` (hoy = Dengue) centraliza el literal: la cohorte de conteos-log activa log_transform, desactiva normalizar_tasa, acota con el clamp estacional e invierte el log en predict. Usar este helper, NO `== "Dengue"` repetido.
- **Modelado Dengue (per-cohorte, neuro intacto):** grid `dengue` en `prophet.yaml` (multiplicativo, `changepoint_prior_scale=0.05` FIJO) + `_GRID_KEY_MAP`. SIN holiday COVID, cv_weights uniformes, SIN fallback regional ("si es 0, es 0"). **Prophet Dengue va CON log_transform y SIN normalizar_tasa** (cohort-aware en `prophet/model.py`: `is_neuro(pad) or pad=="Dengue"`): sin log la tendencia multiplicativa colapsa a ~0 al extrapolar, y la tasa/100k comprime la señal en log → ratio yhat/real nacional 0.00 → 1.01 con el fix. La inversión expm1 en predict requiere que `ForecastModelLoader` reciba `padecimiento` (predice.py lo pasa SOLO para Dengue; neuro conserva su path histórico padecimiento=None, byte-idéntico).
- **Prophet Dengue lleva regresor El Niño/ONI** (`src/epiforecast/data/enso.py`, cohort-gated `is_count_log_cohort`; neuro byte-idéntico). El ciclo inter-anual del dengue sigue a ENSO (señal ausente en los conteos): backtest leave-one-epidemic-out nacional SMAPE 102→76 (pico 2024 ratio 1.61→0.87). ONI futuro = observado + persistencia amortiguada hacia neutral (o `data/external/oni_forecast.csv` IRI). Config `enso_regressor`/`enso_lag_weeks=16` en `prophet.yaml`.
- **Nuevo motor `nbglm` (Negative-Binomial GLM + Fourier + ONI), `src/epiforecast/models/nbglm/`:** count-correcto, extrapola sin divergencia (Fourier paramétrico), determinista, con regresor El Niño. **El mejor del estudio** (backtest leave-one-epidemic-out SMAPE 52 vs Prophet+ENSO 76 vs Prophet 102). `predict()` emite ajuste in-sample + futuro (producción evalúa el ajuste 2026 H1); fallback constante para series degeneradas. Probados y DESCARTADOS por empeorar: bridge a 2014 (otra definición/régimen) y NegBin en DeepAR.
- **Producción Dengue = DeepAR + Prophet + NBGLM** (selector `scripts/produccion_dengue.py`, por serie vía SMAPE 2026 real alineado por semana ISO; **distribución DeepAR 46 / NBGLM 31 / Prophet 22, Nacional=DeepAR** — NBGLM gana 31 series, el nacional sigue DeepAR porque 2026 es año bajo y los motores con ENSO anticipan más magnitud). Ensemble y Stacking siguen FUERA (árboles no extrapolan). **Ensemble y Stacking quedan FUERA**: los árboles (XGBoost/LightGBM) no extrapolan la dinámica epidémica a 52 sem (divergen ~33x/99x) y el log1p amplifica el overshoot. Guard `forecast_guards.clamp_seasonal_envelope` (cohort-aware Dengue) los acota a la envolvente estacional histórica (33x/99x→~10x) pero NO se eligen como productivos.
- **CAVEAT de leakage en la selección (auditoría 2026-06-05, ver `docs/research/hallazgos/DENGUE_AUDITORIA_LEAKAGE.md`):** la métrica `smape_real_2026` con la que `produccion_dengue.py`/`reselect_motor_2026.py` eligen motor es **in-sample**, no OOS: el modelo final se entrena sobre la serie COMPLETA incluyendo 2026 H1 (`run()` hace `self.fit(self.serie)`; el corte `FECHA_CORTE_ENTRENAMIENTO=2025-01-01` solo parte train/test para CV) y `predict()` emite el ajuste in-sample de 2026; la selección compara ese ajuste vs el real 2026 → optimista + sesgo de selección (mejor de 3-4 motores sobre el mismo periodo). **Mismo patrón en neuro (333 series).** El **backtest** NBGLM (`dengue_backtest.py`, leave-one-epidemic-out, ONI `as_of=cutoff`) SÍ es limpio: la afirmación "NBGLM es el mejor" se sostiene. Decisión 2026-06-05: NO corregir, validar prospectivo OOS en las próximas 4-8 semanas no vistas (pendiente: congelar el forecast vigente antes del re-entrenamiento semanal). Fix futuro si OOS>2x in-sample: seleccionar por `smape_prod` (CV rolling, ya honesta) o por forecast bloqueado corte fin-2025.
- **Horizonte Dengue: 1 año productivo + proyección 5 años ilustrativa.** El pronóstico preciso es 52 sem (DeepAR no puede más: `past_length=context+lags+pred_length > 390 sem de datos`). La proyección multi-año (`build_dengue_forecast_web.py`) ahora la genera **NB-GLM con `predict(freeze_trend=True)`** (paramétrico Fourier+ONI, extrapola >52 sem sin divergir; reemplazó la antigua banda plana de Prophet). `freeze_trend` congela la tendencia lineal en su último nivel para no extrapolar la pendiente inflada por 2024: con solo 2 ciclos epidémicos (2019, 2024) el ciclo de ~4 años no es aprendible, así que muestra el patrón estacional a nivel estable, no la magnitud de la próxima epidemia. El eje del chart arranca el año previo al último real (`chart_from_year`) para que la escala no la aplaste el pico 2024. Web: `dengue_forecast.json` → sección de pronóstico en `dengue.html`.
- **DeepAR Dengue:** bloque `short_series` en `deepar.yaml` (cohort-aware via `is_neuro`): cohortes de menor historia que la neuro usan context_length=104, lags acotados (`max_lag=53`, conserva el lag anual), CV ligera (2x26) y `gap_fill=interpolate` (semanas sin boletin se interpolan; semana real con 0 se conserva en 0). DeepAR usa CUDA (SageMaker) > CPU; MPS (Apple Silicon) queda DESHABILITADO por defecto (ops de muestreo StudentT no implementados en MPS + riesgo de deadlock con procesos concurrentes); forzar con `deepar.allow_mps: true`. NO correr dos entrenamientos DeepAR locales concurrentes.

### Carril E66 / Obesidad (runner genérico aislado — NO productivo, NO-GO)
> **Obesidad (E66) es NO-GO**: no se entrena de verdad, publica, `git push`, `dvc add/push` ni se marca `published` sin **OK formal explícito**. Este carril vive APARTE del pipeline neuro/Dengue (no lo toca; legacy byte-idéntico). Desde **2026-08-18 el carril vive en `main`**: ambos repos convergieron a una sola rama y la rama `feat/registry-padecimientos-obesidad` se borró tras quedar contenida en main (CI verde). **Integrar el código NO publica Obesidad**: lo que la mantiene invisible es el gate de lifecycle (`trained` + `gallery_enabled: false`), que es configuración y viaja con el código; verificado en vivo (0 menciones en el sitio). Cada micro-commit se revisa por diff.

- **Datos nuevos (`src/epiforecast/data/`)**, sin tocar el legacy:
  - `epi_calendar.py`: calendario **MMWR** (semana dom→sáb; `weeks_in_year`, `week_start`, `shift`, `ds_for`, `target_period(observation_lag_weeks)`). Semanas verificadas: 2020/2025=53, 2021-24=52.
  - `epi_geo_exposure.py`: catálogo geográfico TRACKEADO `config/geografia/entidades_mx.csv` (32 entidades; `macroregion_id` identidad ≠ `macroregion_name` display, sin slugify) + snapshot de exposición `inegi_cpv2020_static` (`config/exposicion.yaml`, join estricto 1:1 + digest). `GeoCatalog`: resolve/entity/cve_ents/macroregion_ids/states_in_macroregion/macroregion_of.
  - `epi_reconcile.py`: reconciliación causal H+M=total (deltas de acumulados, fallbacks, imputación).
  - `epi_dataset.py`: `build_epi_dataset_v2(disease)` → **41,792 filas** (32 estados × 2 sexos × 653 periodos, 2014-W01..2026-W26), versionado en `runs/<dataset_id>/`.
  - `epi_aggregate.py`: `build_products` deriva **111 productos** (64 base + 32 estado-general + 12 región[4×3sexos] + 3 nacional) SOLO de las 64 bases; reconciliación con **tolerancia cero**.
- **Runner genérico (`src/epiforecast/runner/`)**:
  - `contracts.py`: **único** `SeriesKey` + `TrainingSpec` (solo 64 bases) + validadores `ForecastFrame`/`EvaluationFrame`/`MetricFrame` (fila-a-fila; intervalos conjuntamente nulos/válidos, no negativos; NaN+flag nunca inf).
  - `manifest.py`: `DatasetManifest` (`runs/<dataset_id>/`) + `RunManifest` v1 (`runs/<run_id>/`, dir DISTINTO). `dataset_id`=digest del dataset; `run_id`=digest(dataset+comando+stage+política+motores+seed+commit). Escritura atómica.
  - `policy.py` + `config/evaluation/rolling_cv_v1.yaml`: backtest OOS rolling-origin declarativo (folds dev 2021-24 de 52 sem, ≥260 previas; test 2025/stress 2020/prospective 2026 solo reporte). **sMAPE principal**; MASE lag-52 **train-only**.
  - `evaluation.py`: derivación 64→111 de pronósticos (recon `atol=1e-9`) + alineación verdad↔pred + métricas zero-safe (sMAPE/MASE/MAE/RMSE/WAPE**%**/bias firmado).
  - `engines/` = **harness compartido** (`harness.py`) + motores; cada motor solo aporta su `PredictFn(SeriesRequest)->SeriesForecast`. `SeriesRequest` lleva el **`TrainingSpec` real** (SeriesKey, fold, digests dataset/política, seed, horizonte, `TransformContract`, params, límites) + `train` **cortado estrictamente en `fold.train_end`** (ningún predictor ve el holdout: la invariancia post-origen es estructural) + holdout + origen. El harness valida por serie: cobertura EXACTA del holdout, casos finitos y no negativos → si no, rc≠0. `SeriesForecast.diagnostics` (opcional) → `fit_diagnostics.csv` (una fila por serie/fold, con `n_train` + `transform_digest` + `config_digest`). `spec.json` registra `engine_params`/`resource_limits`/`transform`/`transform_digest`/`config_digest`/`n_diagnostics`. Registrados: `seasonal_naive_lag52`, `seasonal_{mean,median}_{3,5}y` (`config/engines/seasonal_windows.yaml`), `ets_add_damped_log1p` (`config/engines/ets.yaml`) y `ridge_harmonic_log1p` (`config/engines/ridge_harmonic.yaml`). Adapters declaran `supports()` (solo benchmark; refit/forecast → **rc=3**). Invariantes compartidos, una sola implementación: `harness.train_series` (contigüidad MMWR del train, fail-closed) y `evaluation.smape_percent` (fórmula única de sMAPE, la usan el MetricFrame y la validación interna de los motores).
  - **Motor ETS `ets_add_damped_log1p`** (primero que AJUSTA de verdad: 64×4 = **256 ajustes OOS**): statsmodels Holt-Winters, tendencia aditiva **amortiguada** + estacionalidad aditiva periodo 52, init estimada, optimizado, sin `remove_bias`. log1p/expm1 **gobernados por el `TransformContract`**, nunca hardcodeados. Reintento **único** declarado (variante sin tendencia) si la primaria no converge, emite `ConvergenceWarning` o su pronóstico no es usable; si ninguna variante da conteos finitos no negativos → `EtsFitError` → **rc≠0** (sin clipping, sin redondeo, **sin fallback a cero/Seasonal Naive**: por eso NO se reutiliza el `ETSExpert` legacy, que devuelve ceros). Fail-closed también ante hueco en el train o < 2 estaciones. Limitación declarada: periodo 52 fijo → los años MMWR de 53 semanas (2014/2020/2025) desplazan la fase una semana.
  - **Motor Ridge armónico `ridge_harmonic_log1p`** (primero que SELECCIONA hiperparámetros): `sklearn.Ridge` solver **svd** (cerrado, determinista) sobre log1p; diseño = tendencia lineal estandarizada + armónicos de Fourier del **ds MMWR** (periodo 365.25 d), **sin lags**. **Selección temporal interna**: las últimas 52 semanas del train exterior son inner-validation, la rejilla (orders [2,4,6] × alphas [0.1,1,10] = 9) se ajusta sobre el inner-train, se puntúa con **sMAPE en casos** y se desempata por **menor orden → mayor alpha**; luego refit sobre TODO el train exterior. El escalador se ajusta con el set de ajuste de cada fit: **el holdout nunca entra en la selección**. Candidato con conteos negativos/no finitos = inválido (se descarta, **no se recorta**); sin candidatos válidos o refit inutilizable → `RidgeFitError` → **rc≠0**. Diagnóstico: orden, alpha, sMAPE interna, `n_inner_train`/`n_inner_validation`, candidatos totales/válidos, norma de coeficientes e intercepto; `spec.json` registra la versión de scikit-learn.
  - **Motores Prophet `prophet_{count,rate}_log1p`** (`config/engines/prophet.yaml`; NO es el `config/models/prophet.yaml` legacy): dos perfiles idénticos salvo su `TransformContract` — conteo+log1p frente a **tasa/100k+log1p** (escala del registry). Ajuste **MAP** (`uncertainty_samples=0`, `mcmc_samples=0`), crecimiento lineal, estacionalidades nativas **desactivadas** y una sola declarada `annual_mmwr` de 365.25 d sobre el ds MMWR. **Sin ENSO, sin holidays COVID, sin regresores**; no reutiliza CV, pesos ni fallbacks del `ProphetForecaster` legacy. Hiperparámetros **congelados por el comando `tune`**: el benchmark nunca reabre la rejilla y sin `frozen` falla cerrado. Pronóstico negativo/no finito o ajuste fallido → rc≠0. `spec.json` guarda las versiones de prophet y cmdstanpy.
  - **Comando `tune`** (`runner/tuning.py`, genérico): congela hiperparámetros ANTES del benchmark, sobre el mismo corte causal (reutiliza `harness.series_requests`). **Centinelas deterministas**: media semanal del TRAIN del fold (nunca el holdout), orden por (media, `geography_id`), y por sexo mínimo/mediana superior/máximo → en E66 hombres 29/31/15 y mujeres 29/11/15. Rejilla completa sobre los 6 centinelas; una configuración es válida solo si las 6 dan pronóstico utilizable. Selección **declarativa**: mediana → media de sMAPE y luego los desempates del YAML del motor. Sin ninguna válida → rc≠0 (jamás congela un default mudo). Artefactos: `sentinels.csv`, `tuning_results.csv`, `selected_config.json`, `tuning_spec.json`.
  - **Exposición**: `SeriesRequest` lleva `train_exposure` y `holdout_exposure` por periodo. La del holdout SÍ viaja (es el denominador poblacional del periodo objetivo, no una observación futura del target); los casos del holdout nunca. Si el contrato requiere exposición, el harness exige cobertura exacta y valores finitos positivos.
  - **Telemetría ≠ resultados**: la duración por serie es wall-clock y no puede ser byte-reproducible, así que vive en `jobs/<engine>.fit_timing.csv` (**sin digest**, no es artefacto) y no debilita el gate "mismos digests entre corridas". Los subprocess de motor se lanzan con **un solo thread numérico** (OMP/OPENBLAS/MKL/NUMEXPR/VECLIB=1).
  - `report.py`: `comparison.csv` (mediana sMAPE/MASE bases/111/nacional + runtime + mejora vs baseline; **no elige ganador**).
- **CLI `python -m scripts.disease_run`** (todo bajo `runs/<...>/`, gitignored):
  - `validate-data Obesidad` → dataset + 111 productos (FUNCIONAL, rc0).
  - `benchmark Obesidad --stage smoke|full [--engines a,b] [--allow-dirty]` → un subprocess LIMPIO por motor; el run oficial exige **árbol trackeado limpio** (`--allow-dirty` para dev). Reanudación solo si el job está succeeded + artefactos **re-verificados en disco** (un .pkl no cuenta).
  - `tune Obesidad --stage smoke|full --engines a,b` → congela hiperparámetros por motor (centinelas + rejilla); solo lo soportan los motores que lo declaran (el resto → **rc=3**).
- **Baselines canónicos** (commits limpios): Seasonal Naive `obesidad_benchmark_full_7952e226c10a` @ `cf97301b`; run conjunto 5 motores `obesidad_benchmark_full_fc70f5f15b7b` @ `1e0709fd`; run 6 motores `6ff688593915` @ `52fc07af`; run 7 motores `b0c4b6e18c50` @ `7ff41b04`; **run vigente 9 motores `obesidad_benchmark_full_301981b4c42c` @ `08d554cd`**. Mediana sMAPE_all: naive 39.5 · median_3y 36.7 · mean_3y 32.5 · **prophet_count 31.9** · ETS 30.0 · **prophet_rate 28.5** · median_5y 28.3 · **mean_5y 28.02** · **Ridge 28.00 (−29.07%)**; en las 64 bases: mean_5y 28.99 < Ridge 29.70 ≈ median_5y 29.71 < prophet_rate 30.24 < ETS 30.50 < prophet_count 32.09. `prophet_rate` es el **mejor en nacional General (19.58) y en MASE_all (0.81)**. Cada motor: 13,312 predicciones base / 23,088 derivadas / 444 métricas / **solo 64 modeladas** / `n_train` por fold 366/418/470/522; los cuatro que ajustan emiten 256 diagnósticos. **Tuning oficial** de Prophet: `obesidad_tune_smoke_3398a12d14c8` @ `a72acf27` (36 configs × 6 centinelas = 216 ajustes por perfil, 36/36 válidas; ambos perfiles congelan additive · cp=0.01 · sp=0.5 · Fourier=5). Los 7 motores previos conservan `metrics.csv` **byte-idéntico**. Verificado reproducible: mismo `run_id` y los 40 artefactos con el mismo digest en otro `runs_root`. **Sigue sin elegirse ganador** (la selección por SeriesKey con umbral de 5% es C5).
- **Registry**: Obesidad declara `training_engines=(prophet,deepar,ensemble,stacking)` (legacy, NO gobierna el benchmark) y `selection_policy=rolling_cv_v1`, `exposure_source_id=inegi_cpv2020_static`, **`lifecycle=trained`** (C5 cerrado; nunca `published`).

### Carril N+1 — Anorexia F50 (C6: demostración, NO productiva)

> **F50 es una DEMOSTRACIÓN de N+1**: se dio de alta **sin una línea de Python**, para probar que el
> runner absorbe un padecimiento nuevo por configuración. `lifecycle=configured`, `channels: []`,
> `training_engines: []`, invisible en todo filtro `published_only`. NO-GO como Obesidad.

- **Alta por configuración** (`c5803acd`): perfil `baja_incidencia_semanal` en `config/padecimientos.yaml`
  (conteos, `rate_scale` disponible pero **ningún motor en tasa**, y TODOS los traits legacy apagados —
  sin log1p/COVID/ENSO/clamp/short_series y **sin `fallback_regional`**, que en baja incidencia sería lo
  peor) + entrada `anorexia_f50` (CIE F50, alias clínicos incl. TCA/bulimia, grupo `trastornos_nutricion`,
  exposición `inegi_cpv2020_static`, política **`rolling_cv_v1` reutilizada intacta**). En
  `config/data/cuadros.yaml` cambia **solo** `onboard: false → true`: F50 es el **bloque 1** del cuadro
  14.1, co-ubicado con Obesidad (bloque 0).
- **Extracción** (`scripts/extrae_cuadro --disease anorexia_f50`): 654 PDFs → **653 ok**, único fallido
  `2014_sem01.pdf` (`no_page`); **20,896 filas**, 32 entidades por boletín, 0 duplicados, fuente
  2014-W02…2026-W27; layouts **53** de 3 columnas y **600** de 4; una sola ausencia de `Casos_semana`
  (Querétaro 2016-W50) y 1,696 ausencias esperadas de año anterior. **Determinista**: dos corridas
  independientes dan `sha256 2a7bb815…` byte a byte. Copiado tal cual a `data/raw/data_raw_Anorexia_F50.csv`
  (sin `merge_cuadro.py`, sin tocar el consolidado, sin operaciones DVC).
- **Guard anti-confusión de bloque** (imprescindible): como F50 y Obesidad salen del MISMO cuadro, todos
  los conteos del gate pasarían igual leyendo el bloque equivocado. Contraste directo: **0.2%** de celdas
  coinciden (35 de 20,896) y los totales difieren 160× (**47,143** vs 7,542,552).
- **Dataset** `anorexia_f50_05a3b9cfde27`: 41,792 filas base / 64 series / 653 obs por serie
  (2014-W01…2026-W26), 72,483 filas y 111 productos, 47 derivados; 1 total estado-periodo imputado
  (Querétaro) → 2 filas base; cero negativos o nulos; general=H+M, Σ estados=región, Σ regiones=nacional.
  **57.3% de ceros**: son datos de baja incidencia, nunca faltantes.
- **Smoke OOS** `anorexia_f50_benchmark_smoke_06ee26150ba1` @ `7c374d49` (checkpoint funcional C6.2):
  fold único `development_2024`, rc=0, **64 series base modeladas** y **cero series derivadas modeladas
  directamente** (los 47 productos derivados SÍ se materializan, por suma de las bases), 3,328
  predicciones base, 5,772 filas de evaluación sobre los 111 productos, 111 métricas, `n_fallback=0`,
  `disease_id=anorexia_f50` en todo artefacto y
  mismo `run_id`+digests en otro `runs_root`. **Sin umbral de sMAPE**: C6 demuestra reutilización
  funcional, no calidad productiva (la mediana sale ~93, esperable en series casi-cero).
- **Preservación verificada**: el diff de C6 toca `config/`, `tests/` y `CLAUDE.md` (documentación) —
  cero cambios en `src/`, `scripts/`, frontend y `rolling_cv_v1.yaml` (digest `dd6d4a02…` intacto);
  los 4 agregados legacy
  byte-idénticos; runs canónicos C5 de Obesidad intactos; estado dirigido de DVC sin cambios.


### Convenciones de Codigo
- **Imports**: Agrupar stdlib, luego terceros, luego locales (isort via Ruff).
- **Tipado**: Uso estricto de `mypy`. Retornos de funciones deben estar tipados.
- **Logging**: Usar `loguru.logger` para trazas de depuracion y errores.
- **Lint**: Ruff con line-length=99, target Python 3.12.
- **SRP**: Maximo 300 lineas por modulo. Unica excepcion documentada: `models/deepar/model.py` (complejidad inherente de GluonTS). Los God-modules de visualizacion se particionaron (metodo cubrir->partir, con tests smoke/estructurales de red): `comparison_builders.py` -> `comparison_panels` + `comparison_metrics` + `comparison_builders`; `comparison_bars.py` -> `comparison_bars_helpers` + `comparison_prod_bars` + `comparison_bars`; `avance5_charts.py` -> `avance5_panels` + `avance5_metric_charts` + `avance5_charts`; `avance5_tables.py` -> `avance5_data` (carga/merge/win-rate) + `avance5_tables` (markdown).
- **Tests**: Pytest con cuatro marcadores — `unit` (funciones puras), `contract` (contrato entre
  componentes o estado trackeado del repo), `slow` e `integration`. `--strict-markers` está activo:
  usar un marcador sin registrarlo en `pyproject.toml` es un **error**, no un aviso.
  **Gate de cobertura: `fail_under = 70` en `[tool.coverage.report]` es la ÚNICA cifra.** `--cov`
  ya NO viaja en `addopts`: la cobertura se declara en el *call site* (job `Tests` y `make test`),
  porque el piso global se aplicaba a cualquier invocación midiera lo que midiera — y eso tuvo el
  cron en rojo 12 lunes con cero pruebas fallidas. `scripts/compliance_check.py` queda fuera a
  propósito (`--cov-fail-under=0`): es diagnóstico con sus propios mínimos, no un consumidor del gate.
  2,509 tests colectados en 136 archivos test; el último CI previo a los cuatro controles nuevos
  colectó 2,505 y obtuvo cobertura **74.5%** (selección `not slow and not
  integration`, medida en runner limpio). Ojo: en local, con `runs/` y el bundle restaurados, la
  cifra sube varios puntos y los skips caen de ~500 a ~1 — **no confundir esa medición con la de CI**.
- **Pre-commit**: Ruff check + format, mypy, trailing whitespace, YAML/TOML check.

### Dependencias Clave
- **Core**: pandas, numpy, omegaconf, loguru, scikit-learn, rich, pydantic.
- **Prophet**: prophet, cmdstanpy.
- **DeepAR**: gluonts[torch], torch (PyTorch).
- **Visualizacion**: matplotlib, seaborn, plotly, kaleido.
- **Datos**: camelot-py, pypdf, reportlab, openpyxl.
- **Infraestructura**: boto3, sagemaker (opcional), dvc[s3] (opcional), mlflow (opcional).
- **Ensemble**: xgboost.
- **Stacking**: lightgbm, statsmodels.
- **EPI Console**: rich, google-generativeai.
- **Dev**: pytest, ruff, mypy, pre-commit.
- Instalar: `pip install -e ".[dev]"`. DVC opcional: `pip install -e ".[dvc]"`. MLflow opcional: `pip install -e ".[mlflow]"`.

### Scripts Adicionales
- `scripts/compliance_check.py`: Auditoria de calidad (Cookiecutter DS + SOLID + MLOps).
- `scripts/excel_produccion_charts.py`: Graficos embebidos para Excel de produccion (6 PNGs).
- `scripts/excel_produccion_fmt.py`: Formateo IMSS 2026 para workbook de produccion.
- `scripts/genera_paneles_barras_prod.py`: Barras individuales del modelo productivo ganador.
- `scripts/genera_paneles_barras_semana.py`: Paneles de barras semanales (2x2 grids).
- `scripts/genera_paneles_zoom.py`: Paneles con zoom desde 2020.
- `scripts/genera_validacion_semanal.py`: Validacion semanal Real vs Forecast (HTML).
- `scripts/patch_train_metrics.py`: Parche metricas train en CSVs sin re-entrenar.
- `scripts/scrape_boletines.py`: Scraper SINAVE (Selenium).
- `scripts/ci_process_boletines.py`: Procesamiento CI/CD de boletines (Camelot).
- `scripts/publish_gsheets.py`: Publicacion a Google Sheets.

### Modulos SRP (archivos extraidos para cumplir limite de 300 lineas)
- `prophet/data_prep.py`: Funciones de preparacion de datos extraidas de `prophet/model.py`.
- `ensemble/helpers.py`: Feature engineering, preparacion de datos y metricas extraidas de `ensemble/model.py`.
- `stacking/experts.py`: Expertos individuales (ProphetExpert, ETSExpert, LGBMExpert) extraidos de `stacking/model.py`.
- `stacking/meta_learner.py`: Meta-learner Ridge/ElasticNet con pesos no negativos extraido de `stacking/model.py`.
- `visualization/comparison_report.py`: Generacion de reporte HTML extraida de `comparison_plots.py`.
- `visualization/comparison_html.py`: Templates HTML del reporte comparativo (tablas, badges, hero, footer).
- `visualization/comparison_css.py`: Estilos CSS del reporte comparativo (paleta IMSS 2026, badges diagnosticos).
- `visualization/chart_constants.py`: Constantes de estilo (tamaños, margenes, alphas) extraidas de `forecast_chart.py`.
- `visualization/chart_renderer.py`: Renderizado de series (capas, bandas, COVID, outliers) extraido de `forecast_chart.py`.
- `visualization/chart_annotations.py`: Anotaciones (divisores, zona CV, ficha tecnica con deteccion automatica de modelo) extraidas de `forecast_chart.py`.
- `visualization/avance5_data.py` + `avance5_tables.py`: carga de metricas + merge N-way + win-rate (data) y generacion de tablas/Markdown del Avance 5 (tables).
- `visualization/avance5_charts.py` + `avance5_metric_charts.py` + `avance5_panels.py`: 6 builders puros de graficos del Avance 5 (tendencia/residuales en charts; importancia/barras/boxplots/heatmap en metric_charts; primitivas de capa en panels).
- `visualization/comparison_{panels,metrics,builders}.py` y `comparison_{bars_helpers,prod_bars,bars}.py`: builders de comparacion multi-modelo particionados (capas, metricas/residuales, small-multiples/overlay, barras semanales y panel del ganador).
- `features/demographic.py`: Feature builder demografico extraido para SRP.
- `utils/mlflow_logger.py`: Wrapper opcional de MLflow para tracking de experimentos (no-op sin mlflow).

### Articulos y Congresos (`Congresos/`, gitignored)
- Los papers del proyecto viven bajo `Congresos/` y **NO estan en git** (`.gitignore` excluye `Congresos/`). Cuatro tracks: **MICAI** (`Congresos/MICAI/`, metodologico, depresion sola, LNCS ingles), **PLOS ONE** (`Congresos/OnePlus/`, sistemas/utilidad, 3 padecimientos, espanol), **WCP/Mundial** (`Congresos/Mundial/`) e **IMSS/Protocolo**.
- **PLOS ONE:** manuscrito en `Congresos/OnePlus/PLOS_build/latex/manuscrito_plos.tex`; envio generado con `scripts/build_submission.py`; guard de integridad cientifica `scripts/verify_ruta_b.py` (de-escalada Ruta B: la comparacion entre motores no es homogenea y las metricas CV de DeepAR son in-sample). Estado detallado, decisiones y pendientes: en la memoria del asistente (`project_plos_one_submission.md`), no aqui.
- **No duplicar entre papers:** MICAI (depresion, metodo) y PLOS (3 padecimientos, sistema) comparten el hallazgo "el ganador in-sample no persiste OOS"; enmarcar distinto y declarar el relacionado en Editorial Manager (ver `Congresos/OnePlus/COMPARACION_MICAI_PLOS.md`).
