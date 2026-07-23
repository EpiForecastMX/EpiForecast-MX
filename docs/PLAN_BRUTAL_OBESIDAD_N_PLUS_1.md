# PLAN BRUTAL — Obesidad E66 y onboarding N+1 de padecimientos

Estado: Fase 0 CERRADA (PASS material + documental). Siguiente: Fase 1 (lifecycle gate del selector). Obesidad permanece NO-GO.
Fecha de auditoría: 2026-07-22
Repositorio backend auditado: EpiForecast-MX
Rama backend: feat/registry-padecimientos-obesidad
HEAD backend auditado: 7798c0e7
HEAD backend de contención verificado: 0f58fe71
HEAD backend de cierre de Fase 0: e1d77c4a (local, ahead 2, sin push); este plan ahora trackeado en git
Base backend: b535b525
Repositorio web auditado: EpiForecast-IMSS-Dashboard
HEAD web auditado: a90ad9f5
HEAD web de contención verificado: 179bbe36
Hardware local objetivo: Apple M3 Pro, 12 CPU, 18 GPU, 36 GB RAM

Este documento reemplaza como plan operativo a:

/Users/haowei/.claude/plans/crea-un-plan-compiled-lemon.md

Versión auditada del plan anterior:

- 267 líneas.
- SHA-256: 14e2187d8484fe7cd8bfcdafeb6df8dfeda3ef6a9d9371ef3557db1dd8dd410a.
- Modificado: 2026-07-22 00:51:24 EDT.

El plan anterior sigue siendo contexto histórico, pero ya no describe el estado real
del workspace. Este documento es la nueva fuente de continuidad para corregir la
implementación antes de publicar Obesidad o incorporar otro padecimiento.

---

## 1. Veredicto ejecutivo

### Decisión de release

NO-GO.

Obesidad no está lista para ser publicada, no tiene una selección productiva válida y
no existe todavía un flujo N+1 en el que un padecimiento nuevo pueda incorporarse solo
mediante configuración y contenido.

La rama contiene trabajo útil:

- registry inicial;
- extracción E66 sobre 653 boletines;
- modelos completos de Prophet, Ensemble y Stacking;
- 59 artefactos parciales de DeepAR;
- selector puro básico;
- catálogo base;
- manifiesto web aditivo;
- contenido preliminar de EpiBot y zoom.

Sin embargo, la integración fue mayormente aditiva. Se añadieron 3,322 líneas y solo se
eliminaron 40. Los nuevos componentes conviven con rutas legacy que siguen tomando las
decisiones reales. Como resultado, hay configuración decorativa, hardcodes duplicados,
artefactos sin contrato y salidas que aparentan estar listas aunque sus invariantes de
producción están rotas.

### Daños P0 ya confirmados

1. Prophet, Ensemble y Stacking perdieron sus agregados legacy en el workspace:
   all_forecast_<motor>.csv fue sobrescrito y ahora contiene únicamente Obesidad.
2. Prophet Obesidad predice con una inversión de transformación incorrecta:
   el mismo modelo produce un promedio futuro de 3,201 casos con el loader actual y
   14,825 al restaurar correctamente expm1. El error es de aproximadamente 4.6 veces.
3. El calendario genera fechas duplicadas y suma semanas distintas en un mismo día.
   Obesidad tiene 64 claves Fecha × Entidad duplicadas.
4. produccion_obesidad.csv declara rolling_cv_v1, pero nunca se ejecutó rolling CV.
5. Ensemble y Stacking guardaron expertos entrenados solo con datos pre-2025; no
   hicieron refit final con aproximadamente 18 meses recientes.
6. Obesidad sigue en lifecycle configured, pero ya fue expuesta manualmente en el
   dashboard desplegable. La publicación atómica no existe.
7. DeepAR no dejó evidencia de un deadlock MPS/StudentT. La causa demostrable es
   sobreparalelización extrema, dos corridas solapadas, ausencia de locks y posterior
   interrupción.
8. El workspace DVC está sucio en datos, modelos, forecasts, figuras y otros productos.
   No se debe hacer dvc add, commit ni push del estado actual.

### Principio rector

No se continuará “terminando Obesidad” encima de esta base. Primero se restaurarán
integridad, contratos y evaluación. Después se reentrenará y se decidirá, con evidencia,
qué motores merecen ser elegibles.

---

## 2. Evidencia verificada

### 2.1 Calidad automatizada

Backend:

- make lint: verde.
- Ruff manual sobre los scripts nuevos: verde.
- make typecheck: verde.
- make test-fast: 980 aprobadas, 7 deseleccionadas.
- make test: 987 aprobadas, 64 warnings, cobertura total 79.11%.
- cuadro_extractor.py: 0% de cobertura.
- DeepAR model.py: 52% de cobertura completa.
- DeepAR cross_validator.py: 26% de cobertura.

Frontend:

- npm test: 605 aprobadas, 11 fallidas, 616 totales.
- npm run check: falla por drift del corpus RAG.
- Corpus actual: 455 chunks.
- Índice actual: 452 chunks.
- Faltantes reportados por el check: 20 referencias/chunks.

Los tests verdes del backend no detectan los daños P0 porque no ejercitan preservación
de forecasts, inversión de transformaciones desde metadata, calendario de fronteras de
año, rolling CV real ni publicación atómica.

### 2.2 Estado de artefactos Obesidad

| Motor | PKL esperados | PKL encontrados | CSV completo |
|---|---:|---:|---|
| Prophet | 111 | 111 | sí |
| Ensemble | 111 | 111 | sí |
| Stacking | 111 | 111 | sí |
| DeepAR | 111 | 59 | no |

produccion_obesidad.csv contiene 111 filas:

| Motor etiquetado como productivo | Series |
|---|---:|
| Ensemble | 62 |
| Prophet | 26 |
| Stacking | 23 |
| DeepAR | 0 |

Todas las filas declaran motores_evaluados=ensemble,prophet,stacking. El registry
declara cuatro motores elegibles. La ausencia de DeepAR no bloqueó el comando.

### 2.3 Forecasts globales actuales

| Agregado | Filas | Series | Contenido |
|---|---:|---:|---|
| Prophet | 78,033 | 111 | solo Obesidad |
| Ensemble | 78,033 | 111 | solo Obesidad |
| Stacking | 78,033 | 111 | solo Obesidad |
| DeepAR | 270,963 | 432 | neuro + Dengue |
| NBGLM | 43,857 | 99 | Dengue |

La causa está en scripts/predice.py: filtra modelos por padecimiento, pero termina
escribiendo directamente el agregado completo en la misma ruta.

### 2.4 Datos E66

- 654 PDFs inspeccionados.
- 653 contienen el cuadro E66.
- 2014_sem01.pdf es el único no_page esperado.
- 20,896 filas extraídas.
- 32 entidades por boletín exitoso.
- 1 NA real en Casos_semana:
  2016 semana 50, Querétaro, valor fuente n.e.
- 1,696 NA esperados en Acumulado_anio_anterior para el layout histórico.
- Acumulados de hombres y mujeres sin NA.
- 32 entidades × 653 registros cada una.
- Menos de 0.1% de ceros: no es una serie intermitente.

El extractor produjo el conteo esperado, pero el código actual no demuestra todas esas
propiedades ni bloquea si dejan de cumplirse.

### 2.5 Corrupción temporal

data_inegi_Obesidad.csv tiene:

- 20,896 filas;
- 653 filas por entidad;
- solo 651 fechas únicas;
- 128 filas involucradas en duplicados;
- 64 claves duplicadas Fecha × Entidad.

Fronteras afectadas:

- 2014-12-29;
- 2025-12-29.

En 2025-12-29 se agrupan dos observaciones nacionales distintas:

- 9,586 casos;
- 12,064 casos;
- total artificial después del groupby: 21,650.

El problema también existe en General y Dengue. No es específico de Obesidad.

### 2.6 Diagnóstico provisional de modelos

Estas cifras describen artefactos producidos con el calendario actual. No autorizan
selección productiva.

Métricas almacenadas:

| Motor | sMAPE mediana | MASE mediana | % con MASE < 1 |
|---|---:|---:|---:|
| Ensemble | 28.024 | 0.871 | 63.1% |
| Prophet | 32.373 | 1.012 | 46.8% |
| Stacking | 35.266 | 1.058 | 45.9% |
| DeepAR parcial | no comparable completo | 1.269 | 20 de 59 |

DeepAR parcial:

- tiempo mediano por serie: 40.7 minutos;
- rango observado: 40 a 108 minutos;
- tiempo acumulado de resultados únicos: más de 47.7 horas;
- 39 de 59 series fueron iguales o peores que Seasonal Naive;
- MASE nacional General: 1.609;
- MASE nacional hombres: 1.452;
- MASE nacional mujeres: 1.720.

Baseline independiente para el horizonte contractual de 52 semanas:

| Seasonal Naive lag 52 | Valor |
|---|---:|
| sMAPE mediana, 111 productos | 27.815 |
| MASE mediana, 111 productos | 0.806 |
| MASE nacional General | 0.703 |
| MASE nacional hombres | 0.730 |
| MASE nacional mujeres | 0.688 |

El baseline es provisional hasta reparar 2025-12-29, pero muestra una señal inequívoca:
ningún modelo complejo puede declararse productivo si ni siquiera compite contra una
regla estacional explícitamente elegible.

El holdout actual de Ensemble, Stacking y DeepAR estatal usa las 77 semanas disponibles
después del corte, aunque el contrato declara 52. En esa ventana accidental comparable,
Seasonal Naive tiene MASE mediana 0.858 frente a 0.871 de Ensemble y gana claramente
las tres series nacionales. Las métricas de Prophet usan otro protocolo, por lo que no
se deben rankear juntas.

---

## 3. Auditoría brutal por capa

### 3.1 Configuración global

Problema raíz:

src/epiforecast/utils/config.py carga todos los YAML de config/models y los fusiona en
un único diccionario plano. Las claves del último archivo pisan las anteriores y una
opción destinada a un motor puede gobernar a otro.

Caso confirmado:

- config/models/prophet.yaml define n_jobs_train=-2.
- scripts/entrena.py lee conf.n_jobs_train sin namespace.
- DeepAR heredó el paralelismo de Prophet.

Riesgos:

- orden de glob no convertido en contrato;
- colisiones silenciosas;
- configuración efectiva difícil de reproducir;
- CLI overrides sin schema;
- un cambio en un motor altera a otros;
- artefactos cargados bajo la configuración actual, no la de entrenamiento.

Remediación:

- configuración base global mínima;
- namespace obligatorio por motor;
- namespace obligatorio por perfil de padecimiento;
- compilación tipada antes de ejecutar;
- profile resuelto e inmutable;
- digest del profile dentro de cada run y artefacto;
- error ante claves desconocidas o colisiones.

### 3.2 Registry de padecimientos

Lo positivo:

- centraliza identidad básica;
- introduce lifecycle, aliases, engines y traits;
- permite resolver nombres;
- conserva algunos shims legacy.

Lo incompleto:

- registry.py tiene 435 líneas y viola el máximo de 300;
- solo unos pocos consumidores usan traits reales;
- la mayoría de los gates sigue en cohortes o literales;
- dataclasses frozen contienen mappings mutables;
- trait acepta strings arbitrarios;
- trait_or falla abierto;
- validate_config no valida el contrato completo;
- version y motores_conocidos no se hacen cumplir;
- no se rechazan claves superiores desconocidas;
- no se validan referencias cruzadas con cuadros;
- no se validan canales, políticas, layouts ni perfiles completos;
- el doctor no distingue configuración válida de readiness de release.

El falso verde es reproducible: registry_doctor solo inspecciona artefactos cuando el
lifecycle ya es trained o published. Como Obesidad sigue configured, el doctor omite
precisamente DeepAR incompleto, forecasts sobrescritos, evaluación falsa y canales web
ausentes, y aun así puede terminar satisfactoriamente.

Semántica incorrecta:

- Obesidad declara Ensemble y Stacking como motores de tasa, contradiciendo la decisión
  confirmada de conservar conteos;
- neuro y Dengue también contienen valores motor_rate que no coinciden con el código
  efectivo;
- esos errores están ocultos porque el trait todavía no se consume.

Hardcodes que continúan vivos:

- listas de padecimientos en constants.py;
- tasa y ENSO en Prophet;
- holidays COVID en Prophet y Ensemble;
- pesos CV;
- clamps;
- outliers;
- inversión log en predice.py;
- rosters, conteos y fuentes en catalog.py;
- Tableau, validación semanal y prospectiva;
- aliases y handlers web;
- pipeline semanal.

Conclusión:

El registry actual es una capa de metadatos parcial, no la fuente única de verdad.

### 3.3 Extracción

La salida E66 actual es útil, pero el subsistema todavía depende de coincidencias del
layout observado:

- cuadros.yaml dice que lo carga cuadro_registry.py, archivo que no existe;
- block_index y onboard no controlan la extracción;
- layout_variants y backend se declaran, pero no gobiernan el parser;
- el layout se infiere solo por conteo de columnas;
- no se valida el conjunto exacto de estados;
- no se valida TOTAL impreso;
- no se valida unicidad de clave;
- no se validan dtypes ni rangos;
- no existe regla tipada para n.e.;
- no hay checksum de PDF;
- no hay versión de extractor ni digest de config;
- el CLI captura Exception, continúa y devuelve código 0;
- extrae_cuadro.py elimina duplicados silenciosamente;
- merge_cuadro.py detecta duplicados y luego también los elimina;
- el merge no exige un manifest verde;
- no hay tests del nuevo extractor;
- weekly todavía no lo ejecuta.

El próximo layout distinto o un PDF parcialmente extraído puede generar una salida
plausible pero incorrecta.

### 3.4 Preprocesamiento y calendario

El calendario no conserva una identidad epidemiológica canónica. Se modifica Semana y
Anio según máximos observados y después se convierte el resultado a fecha ISO. Esto
permite colisiones en fronteras de año.

Otros riesgos:

- filter.py usa contains en lugar de identidad canónica exacta;
- reglas de outliers viven fuera del registry;
- el preprocesamiento no emite manifest;
- no guarda digest de entrada/config;
- no separa source period de epidemiological period;
- población parece ser una foto estática repetida, sin as-of explícito;
- una transformación puede mirar datos fuera del fold si no se vuelve a ajustar dentro
  del backtest.

### 3.5 Entrenamiento y persistencia

scripts/entrena.py:

- no valida que el motor sea elegible para el padecimiento;
- no resuelve siempre aliases a identidad canónica;
- construye 111 jobs independientes;
- mezcla paralelismo externo e interno;
- no tiene lock de run;
- no tiene run_id;
- no tiene timeout;
- no tiene heartbeat estructurado;
- no registra pending/running/success/failed/timeout;
- no hace checkpoint por serie;
- omite PKL existentes devolviendo None;
- al final sobrescribe el CSV completo solo con los resultados nuevos;
- si el proceso muere, el resumen no se reconstruye;
- puede dejar PKL parciales y procesos huérfanos.

Artifact metadata:

- no contiene artifact_schema_version;
- no contiene disease_id;
- no contiene SeriesKey;
- no contiene espacio objetivo;
- no contiene transformaciones forward/inverse;
- no contiene digest del profile;
- no contiene digest de datos;
- no contiene cutoff real;
- no contiene estado de evaluación;
- no contiene semilla completa;
- no contiene versión del schema de forecast.

La identidad se reconstruye desde filenames con split. Eso no es un contrato.

### 3.6 Defectos por motor

Prophet:

- el entrenamiento de Obesidad activa tasa + log1p;
- el loader productivo recibe None y desactiva log_transform;
- no aplica expm1;
- parámetros “regionales” pueden aplicarse al nacional cuando modelado_estados=True;
- varios gates aún dependen de cohortes legacy.

Ensemble:

- se ajusta solo con train_data pre-2025;
- calcula holdout;
- no refitea sobre serie completa antes de guardar;
- intervalos lower/mean/upper no representan incertidumbre real;
- OOF puede repetir semanas;
- fallos o datos insuficientes pueden terminar con métricas cero.

Stacking:

- mismo defecto de no-refit;
- expertos Prophet, ETS y LightGBM quedan desactualizados;
- intervalos no son probabilísticos;
- folds OOF se solapan;
- métricas cero pueden parecer un ganador;
- su desempeño nacional actual es peor que Seasonal Naive.

NBGLM:

- cross_validate llama predict, que devuelve histórico ajustado + futuro;
- toma las primeras predicciones históricas para compararlas contra el fold futuro;
- las métricas CV genéricas resultantes no corresponden al mismo periodo;
- no debe reutilizarse como candidato universal hasta corregir y probar este contrato.

DeepAR:

- análisis causal completo en la sección 4;
- modelo monolítico de 1,056 líneas;
- early stopping sobre train_loss, no validation loss;
- métricas train con alineamiento dudoso;
- fitting/backfill puede copiar realidad o enmascarar huecos;
- inferencia intenta MPS aunque entrenamiento lo deshabilita;
- usa 99 redes estatales single-series y desaprovecha el carácter global de DeepAR.

### 3.7 Evaluación y selección

produccion_padecimiento.py no implementa políticas:

- lee métricas ya guardadas;
- no crea folds;
- no reentrena por fold;
- no garantiza ausencia de leakage;
- no convierte todos los motores al mismo espacio de casos;
- no valida el mismo horizonte;
- no llama realmente la política de baja incidencia;
- tolera motores elegibles faltantes;
- siempre llama al mismo selector;
- copia el nombre de selection_policy al CSV;
- puede devolver éxito con una selección incompleta.

Las fuentes comparadas son heterogéneas:

- Prophet: CV multifold propia;
- Ensemble: tramo post-2025 completo;
- Stacking: tramo post-2025 completo;
- DeepAR estatal: holdout rápido adicional;
- DeepAR nacional: CV distinta;
- NBGLM: CV actualmente mal alineada.

La etiqueta rolling_cv_v1 es falsa y debe retirarse del artefacto actual.

### 3.8 Predicción y agregación

scripts/predice.py:

- escribe directamente el agregado global;
- no usa temp + validate + replace;
- no hace upsert por padecimiento;
- permite salida parcial aunque modelos fallen;
- infiere identidad desde nombres de archivo;
- decide inversión desde cohortes/config actual;
- no valida cobertura esperada;
- no valida claves duplicadas;
- no valida escala;
- no valida coherencia jerárquica;
- genera figuras como side effect;
- puede destruir productos ajenos al target.

### 3.9 Catálogo y publicación

catalog.py:

- hardcodea neuro y Dengue;
- no ingiere produccion_obesidad.csv;
- no puede llegar a 543 sin cambios de código;
- tiene loader y validaciones específicas por cohorte;
- usa un fallback mágico de 111 elementos si la galería falla;
- infiere el repo web mediante una ruta de padres;
- puede ocultar errores y emitir conteos plausibles.

build_obesidad_zoom.py:

- es un fork específico;
- hardcodea Obesidad y tres motores;
- omite DeepAR sin bloquear;
- escribe en ambos repos;
- no elimina entradas obsoletas;
- no es atómico;
- puede terminar con salida parcial.

Frontend:

- lifecycle configured fue ignorado;
- entities.js y kb.js contienen ramas manuales de Obesidad;
- RAG sigue limitado al roster anterior;
- landing aún anuncia conteos legacy;
- Reports y Tableau no están completos;
- kb.js tiene 5,102 líneas;
- app.js tiene 4,090 líneas;
- entities.js tiene 327 líneas;
- cache versions se incrementan manualmente;
- conocimiento, aliases, rosters y mensajes se duplican.

### 3.10 Pipeline semanal y MLOps

- ci_process_boletines.py hardcodea neuro;
- considera procesada una semana si existe cualquier padecimiento en esa semana;
- actualiza_semanal.sh contiene ruta absoluta;
- incluye pasos específicos de Dengue;
- hace git pull/commit/push dentro de un script operativo;
- usa dvc add con tolerancia de fallo;
- no existe matriz de frescura por fuente y padecimiento;
- DVC no refleja el estado local actual;
- no hay rollback de release;
- no hay promoción separada de build.

### 3.11 Calidad de código y documentación

Módulos por encima del estándar:

| Archivo | Líneas |
|---|---:|
| registry.py | 435 |
| entrena.py | 416 |
| predice.py | 462 |
| build_web_knowledge.py | 1,068 |
| DeepAR model.py | 1,056 |
| dashboard app.js | 4,090 |
| dashboard kb.js | 5,102 |

Problemas adicionales:

- scripts críticos no entran en el gate oficial de mypy;
- tests golden reconstruyen predicados, no congelan comportamiento end-to-end;
- no hay tests de preservación de otras enfermedades;
- no hay test de kill/resume;
- no hay test del corpus completo de extracción;
- no hay test de release;
- documentación de progreso contradice el código;
- AGENTS.md afirma que la implementación no empezó;
- OBESIDAD_PENDIENTES.md llama cerrado a un flujo todavía preliminar;
- build_web_knowledge.py publica parámetros DeepAR que ya no coinciden con config.

---

## 4. DeepAR: análisis causal y protocolo de decisión

### 4.1 Qué ocurrió

Cronología observada:

1. 05:46: inició una corrida con n_jobs=-2.
2. joblib/loky abrió aproximadamente 11 procesos.
3. Cada proceso PyTorch usó 6 threads intra-op y 12 inter-op sobre 12 cores físicos.
4. Cada serie ejecutó hasta:
   - 300 épocas × 50 batches para el fit final;
   - 75 épocas × 50 batches para el holdout adicional.
5. 10:14: comenzó una segunda corrida n_jobs=-2 mientras la primera seguía activa.
6. Desde ese momento hubo aproximadamente 22 procesos DeepAR compitiendo.
7. Diez series fueron entrenadas dos veces y escribieron el mismo PKL.
8. La ejecución fue interrumpida sin traceback causal.
9. Quedaron procesos loky/resource_tracker huérfanos con PPID 1.

Todos los logs inspeccionados dicen accelerator: cpu.

No existe:

- excepción MPS;
- error _standard_gamma;
- excepción StudentT;
- stack trace de deadlock;
- timeout;
- dump de threads;
- evidencia de que el proceso seguía avanzando durante los silencios.

### 4.2 Diagnóstico

Causa demostrada:

paralelismo loky exterior
× paralelismo PyTorch/BLAS interior
× corrida duplicada
× trabajo excesivo por serie
× ausencia de lock, heartbeat, timeout y journal.

Hipótesis no demostrada:

deadlock StudentT sobre MPS.

MPS estaba desactivado en entrenamiento. No debe seguir presentándose esa hipótesis como
causa raíz sin una reproducción aislada.

### 4.3 Decisión inmediata

No completar los 52 PKL faltantes con el runner actual.

No usar SageMaker para ocultar el problema.

El camino SageMaker tampoco está listo para Obesidad: el launcher mantiene un roster de
tres padecimientos, resuelve el CSV de General antes que una fuente específica, contiene
cuenta/bucket/región en código y el entrypoint puede lanzar varios entrenadores sobre una
sola T4. Cloud se habilitará únicamente después del mismo compiler, RunManifest, locks,
dataset explícito y harness que rigen local.

No promover DeepAR como elegible por obligación del registry.

Primero debe pasar el protocolo local siguiente.

### 4.4 Protocolo D0 — harness reproducible

Construir un comando aislado que:

- recibe run_id, disease_id, series_id, seed y device;
- resuelve un EngineProfile inmutable;
- fija concurrencia exterior en 1;
- fija threads PyTorch y BLAS explícitamente;
- registra versiones Python, Torch, Lightning y GluonTS;
- registra device real;
- registra CPU, RSS y memoria MPS;
- emite heartbeat por época;
- escribe stack dump si no hay progreso;
- tiene timeout duro;
- guarda error estructurado;
- escribe a temporal y renombra al completar;
- no reutiliza PKL sin validar su envelope;
- impide dos leases para la misma SeriesKey.

Configuración CPU inicial:

- outer workers: 1;
- torch intra-op: 6;
- torch inter-op: 1;
- OMP_NUM_THREADS: 6;
- MKL_NUM_THREADS: 6;
- sin callbacks Rich transitorios;
- start method explícito y probado;
- warnings no silenciados durante diagnóstico.

### 4.5 Protocolo D1 — matriz de dispositivo y distribución

Una sola serie representativa, cinco épocas, veinte batches, horizonte 52:

| Device | Distribución | Resultado requerido |
|---|---|---|
| CPU | Normal | fit + predict + save/load |
| CPU | StudentT | fit + predict + save/load |
| MPS | Normal | fit + predict + save/load o error reproducible |
| MPS | StudentT | fit + predict + save/load o error reproducible |

Cada celda debe registrar:

- wall time;
- CPU time;
- RSS pico;
- memoria MPS;
- loss train;
- loss validation;
- excepción completa;
- stack;
- hash de forecast;
- cobertura de 52 semanas;
- repetición tres veces.

PYTORCH_ENABLE_MPS_FALLBACK debe formar parte del profile y del resultado, no ser un
detalle implícito.

### 4.6 Protocolo D2 — tamaño y estabilidad

Tres series:

- nacional de volumen alto;
- estado de volumen medio;
- estado de volumen bajo.

Tres seeds, 50/75/100 épocas, early stopping sobre validation loss real.

No se continúa si:

- un run excede timeout;
- hay drift de claves;
- save/load cambia el forecast fuera de tolerancia;
- memoria crece de forma no acotada;
- una repetición queda sin estado terminal;
- el proceso padre muere y deja workers.

### 4.7 Protocolo D3 — rediseño global

DeepAR debe evaluarse como modelo global, no como 99 LSTM estatales independientes.

Diseños a comparar:

1. una red para las 64 series base de Obesidad;
2. una red por sexo con 32 estados;
3. una red única con estado y sexo como categorías estáticas.

La salida base será estado × sexo. General, regiones y nacional se derivan o reconcilian.

Distribuciones:

- Normal y StudentT sobre espacio continuo transformado;
- Negative Binomial solo sobre conteos crudos con exposición explícita;
- nunca usar una distribución de conteos sobre tasas fraccionarias sin contrato.

### 4.8 Gate de supervivencia DeepAR

DeepAR solo podrá pasar de experimental a eligible si:

- completa el fleet definido;
- no deja procesos ni estados indeterminados;
- mejora al menos 5% frente a Seasonal Naive en el agregado objetivo;
- MASE < 1;
- gana al menos 3 de 4 orígenes principales;
- ningún fold supera 1.5 veces el error del baseline;
- intervalos cumplen el gate de calibración;
- tres seeds muestran estabilidad;
- runtime local cumple el presupuesto;
- el modelo global supera o iguala el mejor diseño simple.

Si no cumple, se registra la decisión y se publica Obesidad sin DeepAR. El registry debe
representar esa decisión honestamente.

---

## 5. Arquitectura objetivo N+1

### 5.1 Regla de aceptación N+1

Después de construir la plataforma, incorporar un padecimiento que reutiliza un perfil y
un grupo de extracción existentes debe requerir únicamente:

- una entrada de configuración;
- contenido clínico/editorial;
- fixtures o datos;
- aprobación de release.

No debe requerir:

- editar Python genérico;
- editar JavaScript genérico;
- añadir handlers por enfermedad;
- modificar listas de rosters;
- modificar contadores;
- modificar el predictor;
- modificar el selector;
- crear scripts build_<padecimiento>.

Si el nuevo padecimiento introduce un layout, motor o política realmente nuevos, se
agrega una implementación de plugin tipada; no una condición por nombre.

### 5.2 Qué hardcode sí se permite

Permitido:

- CIE y aliases dentro de DiseaseSpec;
- contenido clínico dentro de fuentes de contenido;
- parámetros de un perfil con nombre;
- fixtures de fuente conocidos;
- implementaciones propias de un motor;
- reglas regulatorias versionadas y explícitas.

Prohibido:

- listas de enfermedades en código;
- comparaciones disease == Obesidad en rutas genéricas;
- conteos 432, 543, 444 o 555 como lógica;
- rutas absolutas de repositorios;
- selección de motor por nombre de cohorte;
- transformaciones inferidas del filename;
- lifecycle decidido desde JavaScript;
- cache versions manuales;
- nombres de archivos usados como identidad;
- fallbacks que inventan conteos;
- tolerar un motor elegible faltante;
- retornar código 0 con un producto parcial.

### 5.3 Registry compilado y tipado

Separar:

- schema.py: modelos Pydantic y enums;
- loader.py: lectura y validación de YAML;
- compiler.py: resolución de referencias y defaults;
- queries.py: API de consulta inmutable;
- legacy.py: shims generados;
- doctor.py: config doctor;
- release_doctor.py: readiness real.

DiseaseSpec resuelto debe incluir:

- schema_version;
- id canónico;
- data_name;
- artifact_key;
- slug;
- display_name;
- CIE;
- aliases;
- source/extraction spec;
- preprocessing spec;
- universe spec;
- engine profiles resueltos;
- evaluation policy;
- reconciliation policy;
- product channels;
- lifecycle;
- expected coverage;
- content references;
- profile_digest.

EngineProfile debe incluir por motor:

- target_space: count, rate o transformed;
- forward transforms;
- inverse transforms;
- population/exposure;
- features;
- outlier policy;
- cutoff y horizon;
- train/refit policy;
- runtime limits;
- engine-specific hyperparameters;
- distribution;
- eligible/training/shadow status;
- interval strategy.

El compilador debe:

- rechazar unknown keys;
- rechazar motores desconocidos;
- validar referencias cruzadas;
- validar perfiles completos;
- validar channels;
- validar policies;
- validar source groups;
- validar que toda transformación tenga inversa;
- producir JSON canónico;
- producir digest;
- producir assets generados para Python y web.

Ningún consumidor de producción leerá YAML crudo de forma independiente.

### 5.4 Configuración por namespaces

Estructura conceptual:

    config/
      runtime.yaml
      engines/
        prophet.yaml
        deepar.yaml
        ensemble.yaml
        stacking.yaml
        nbglm.yaml
      profiles/
        neuro.yaml
        dengue.yaml
        chronic_dense.yaml
      diseases/
        depresion.yaml
        parkinson.yaml
        alzheimer.yaml
        dengue.yaml
        obesidad.yaml
      sources/
        neuro_boletin.yaml
        dengue_boletin.yaml
        trastornos_nutricion.yaml

La forma exacta puede ajustarse, pero no se permite volver al merge plano.

### 5.5 Identidad única de series

SeriesKey v1:

- disease_id;
- target;
- geography_level;
- geography_id;
- sex;
- frequency;

Valores canónicos:

- geography_level: state, macroregion, national;
- sex: male, female, general;
- target: weekly_cases;
- geography_id no contiene labels de presentación.

Labels en español pertenecen al presentation layer.

### 5.6 Universo coherente

Obesidad tiene 64 series base:

32 estados × 2 sexos.

Productos derivados:

- 32 estados × general = 32;
- 4 macroregiones × 3 sexos = 12;
- nacional × 3 sexos = 3.

Total:

64 base + 47 derivadas = 111 productos.

Invariantes:

- state.general = state.male + state.female;
- region = suma de sus estados;
- national = suma de los 32 estados;
- national.general = national.male + national.female;
- una fecha por periodo;
- no negativos;
- floats internos, enteros solo en el boundary de publicación;
- intervalos también coherentes o marcados como no reconciliados.

Se compararán:

- Bottom-Up como baseline de coherencia;
- MinTrace/otra reconciliación solo si mejora OOS.

No se entrenarán 111 modelos independientes por inercia.

### 5.7 Run Manifest

Cada ejecución tendrá:

- run_id;
- stage;
- disease_id;
- engine;
- profile_digest;
- data_digest;
- code_commit;
- environment lock digest;
- seed;
- started_at;
- finished_at;
- status;
- expected SeriesKeys;
- completed SeriesKeys;
- failures;
- artifacts;
- parent run;
- warnings;
- promotion state.

Estados:

- pending;
- running;
- success;
- failed;
- timeout;
- cancelled;
- superseded.

El manifest se actualiza de forma atómica y sirve para resume.

### 5.8 Artifact Envelope v2

Cada artefacto debe tener envelope sidecar:

- artifact_schema_version;
- run_id;
- disease_id;
- engine_id;
- SeriesKey o global_model_id;
- training universe;
- target_space;
- transforms;
- inverse transforms;
- exposure;
- data cutoff;
- data digest;
- profile digest;
- code commit;
- library versions;
- seed;
- fit scope;
- refit status;
- evaluation manifest;
- model file digest;
- created_at.

El loader obedece el envelope. La configuración actual no puede cambiar cómo se invierte
un modelo ya entrenado.

Artefactos legacy usarán un adaptador explícito y versionado. No se inferirá metadata a
partir de split del stem durante producción.

### 5.9 ForecastFrame v2

Formato canónico, preferentemente Parquet:

- run_id;
- disease_id;
- engine_id;
- SeriesKey;
- ds;
- horizon;
- yhat;
- lower;
- upper;
- target_space=cases;
- model_artifact_digest;
- reconciliation_method;
- status;

Reglas:

- una clave única por SeriesKey × ds × engine;
- salida siempre en casos absolutos antes de evaluar;
- no NaN/inf;
- no negativos;
- cobertura exacta;
- schema versionado;
- sin escritura parcial.

### 5.10 Shards y agregados

Ruta conceptual:

    reports/forecasts/runs/<run_id>/<engine>/<disease_id>.parquet

Los CSV all_forecast legacy pasan a ser vistas materializadas:

1. leer shards aprobados;
2. validar;
3. concatenar/upsert por disease_id;
4. demostrar preservación de claves ajenas;
5. escribir temporal;
6. releer y validar;
7. rename atómico.

Nunca se vuelve a predecir un padecimiento directamente sobre el agregado global.

### 5.11 Evaluation Manifest

Debe contener:

- BacktestSpec digest;
- orígenes exactos;
- horizonte exacto;
- train windows;
- validation windows;
- preprocessing fit por fold;
- modelos y artefactos por fold;
- seeds;
- target space;
- métricas por SeriesKey/fold;
- runtime;
- cobertura;
- interval calibration;
- baseline;
- leakage checks;
- failure status.

### 5.12 Release Manifest

Debe unir:

- DiseaseSpec compilado;
- data manifest;
- train manifests;
- evaluation manifest;
- selection manifest;
- forecast manifest;
- catalog manifest;
- Tableau;
- Reports;
- EpiBot;
- RAG;
- landing;
- gallery/zoom;
- assets;
- checksums;
- rollback pointer.

La publicación ocurre desde staging y se promueve solo si el release doctor queda verde.

---

## 6. Portafolio local recomendado para Obesidad

### 6.1 Orden de inversión

No comenzar por otra red pesada. El orden correcto es:

1. baselines;
2. modelos estadísticos densos;
3. modelo global de árboles;
4. reconciliación;
5. red global pequeña;
6. DeepAR global experimental;
7. transformers solo como shadow research.

### 6.2 Candidatos

| Candidato | Diseño | Escala | Presupuesto M3 Pro | Prioridad |
|---|---|---|---:|---|
| Seasonal Naive 52 | lag anual | casos | <1 min | obligatoria |
| Seasonal window mean/median | misma semana, 2–3 años | casos | <1 min | obligatoria |
| ETS/Holt-Winters | por serie base | casos o log | 2–15 min | alta |
| Theta/AutoTheta | por serie base | casos o log | 2–15 min | alta |
| MSTL + ETS | tendencia + anual | casos o log | 5–30 min | alta |
| Regresión armónica | Fourier, tendencia, lags, Ridge/ElasticNet | casos/log | 1–5 min | alta |
| NB-GLM generalizado | Fourier, lags, offset de población | conteos | 3–15 min | alta |
| LightGBM global directo | una familia de modelos para 64 series | casos/log | 5–30 min | alta |
| AutoARIMA | por serie, acotado | casos/log | 15–90 min | media |
| Prophet corregido | envelope + refit | tasa/log | 10–20 min | challenger |
| Ensemble corregido | solo tras refit y folds comunes | casos | 10–40 min | challenger |
| N-HiTS global pequeño | 64 series compartidas | escalado | >2 h | experimental |
| DeepAR global | una red o una por sexo | escalado/conteos | 1–3 h fit | experimental |
| PatchTST/TiDE | shadow, no default | escalado | medir | backlog |

No usar Croston como candidato principal: Obesidad tiene menos de 0.1% de ceros.

### 6.3 Seasonal baselines como motores elegibles

Seasonal Naive no será solo el denominador de MASE. Debe poder ganar selección.

Baselines mínimos:

- Naive;
- Seasonal Naive lag 52;
- promedio estacional de 2 años;
- mediana estacional de 3 años;
- drift estacional opcional.

Cada baseline usa el mismo ForecastFrame y el mismo backtest.

### 6.4 Estadísticos locales

Primer paquete:

- AutoETS;
- AutoTheta;
- MSTL + AutoETS;
- AutoARIMA con presupuesto;
- regresión armónica Ridge/ElasticNet;
- NB-GLM corregido y generalizado.

NB-GLM para Obesidad:

- conteos semanales;
- offset log de población si se modela incidencia;
- Fourier anual;
- lags 1, 2, 4, 13, 26, 52 y 53;
- tendencia flexible y changepoints declarados;
- intervenciones de régimen solo si se conocen as-of;
- forecast futuro sin covariables desconocidas.

No se heredará ENSO por pertenecer a otra cohorte.

### 6.5 LightGBM global directo

Diseño prioritario:

- dataset largo de 64 series base;
- categorías estáticas de estado y sexo;
- población/exposición as-of;
- lags y rolling features ajustados sin leakage;
- 52 horizontes directos o estrategia multi-output explícita;
- no recursive-only como único diseño;
- validación temporal común;
- intervalos conformales después de calibración;
- threads acotados;
- un artifact envelope por familia global.

Debe compararse contra:

- XGBoost equivalente;
- regresión lineal global;
- Seasonal Naive.

### 6.6 N-HiTS antes que transformers

Si los modelos simples dejan margen:

- entrenar N-HiTS global pequeño;
- 64 items;
- input 104/156/208 a comparar;
- horizonte 52;
- pocos bloques;
- validation loss real;
- tres seeds;
- CPU y MPS medidos;
- early stopping;
- quantile loss opcional.

PatchTST y TiDE quedan en shadow hasta que N-HiTS justifique el costo de una familia
neural.

### 6.7 Coherencia

Cada candidato genera forecast base. Después:

1. Bottom-Up;
2. MinTrace no negativo si existe suficiente residual OOS;
3. comparación de error y calibración.

La selección productiva debería ocurrir en las 64 series base. Las 47 series derivadas
registran lineage de componentes. Si un producto agregado mezcla motores base, se etiqueta
como reconciled_mixed, no se inventa un único motor ganador.

### 6.8 Criterio de entrada a producción

Un modelo candidato debe:

- completar todos los folds;
- producir 52 semanas exactas;
- mejorar al baseline de forma estable;
- no depender de datos futuros;
- mantener coherencia;
- cumplir runtime;
- tener envelope;
- soportar save/load;
- producir intervalos reales o declarar point-only;
- pasar tres seeds si es estocástico;
- no tener fallos silenciosos.

---

## 7. Backtest y selección universales

### 7.1 BacktestSpec para Obesidad

Después de reparar el calendario, congelar orígenes exactos derivados del periodo
epidemiológico:

- cuatro o cinco folds anuales completos de 52 semanas;
- stress fold 2020 separado, no mezclado en el score principal;
- 2026 parcial solo como evaluación prospectiva;
- último bloque final fuera del tuning;
- mismo train/test para todos los motores;
- features, outliers y scalers ajustados dentro de cada fold.

La cantidad exacta de folds se fija en config y se valida contra cobertura. No se deriva
silenciosamente del número de filas.

### 7.2 Métricas

Primaria:

- sMAPE por SeriesKey y fold.

Desempate confirmado:

1. banda de 5% en sMAPE;
2. menor MASE;
3. menor RMSE.

Reporte adicional:

- MAE;
- WAPE;
- bias;
- p90 del error;
- Poisson deviance para conteos;
- cobertura 80/95;
- ancho de intervalos;
- runtime;
- estabilidad entre seeds;
- error nacional;
- error macro por estado y sexo.

### 7.3 Política de selección

selection_policy debe hacer dispatch real:

- legacy_neuro_2026;
- legacy_dengue_2026;
- rolling_cv_v1;
- cualquier policy nueva implementa la misma interfaz.

rolling_cv_v1:

- recibe EvaluationManifest;
- verifica folds idénticos;
- verifica casos absolutos;
- verifica horizonte 52;
- rechaza motores incompletos;
- incluye baselines;
- aplica banda y desempates;
- emite razón y trazabilidad;
- distingue selected, fallback y degraded;
- nunca cambia lifecycle.

### 7.4 Estados de selección

- valid: todos los candidatos requeridos completos;
- degraded: exclusión aprobada y documentada;
- preliminary: resultados exploratorios;
- invalid: contrato roto.

preliminary y degraded no pueden promover a published sin aprobación explícita y un
ReleaseManifest que explique la excepción.

El produccion_obesidad.csv actual debe renombrarse conceptualmente como preliminary e
invalidarse para release.

---

## 8. Plan de ejecución por fases

Las fases son secuenciales por gate. Puede haber trabajo paralelo dentro de una fase,
pero no se promueve a la siguiente si el criterio de salida no está cumplido.

### Fase 0 — Contención y preservación

Estado al 2026-07-22: **CERRADA** (PASS material + documental; HEAD e1d77c4a, ahead 2, sin push).
Los forecasts legacy y el dashboard público están recuperados; SHA256SUMS valida 4/4; la selección
inválida salió de la ruta canónica; forecasts y Tableau coinciden con sus punteros. El delta
documental quedó cerrado: se neutralizaron las recetas de entrenamiento/predicción y los `dvc
checkout` amplios de los documentos operativos, y este plan quedó trackeado.

Objetivo:

detener propagación de artefactos corruptos sin destruir evidencia.

Trabajo:

- inventariar hashes de DVC y archivos locales afectados;
- guardar una copia de evidencia de forecasts Obesidad fuera de rutas canónicas;
- comparar outputs canónicos de DVC en un directorio temporal;
- restaurar agregados legacy solo después de validar hashes y cobertura;
- prohibir predice sobre agregados globales mediante un guard temporal;
- ocultar Obesidad del dashboard público o colocarla detrás de preview no indexado;
- marcar produccion_obesidad.csv como preliminary;
- corregir documentos que dicen cerrado;
- registrar los procesos huérfanos observados antes de decidir su terminación;
- no ejecutar dvc add/push;
- no ejecutar entrenamiento;
- no regenerar Tableau, Reports ni web.

Pruebas:

- 432 SeriesKeys legacy presentes en Prophet/DeepAR/Ensemble/Stacking según sus contratos;
- 99 Dengue preservadas donde corresponda;
- ninguna salida Obesidad en productos published;
- hashes de evidencia registrados;
- diff web controlado.

Criterio de salida:

- baseline legacy recuperable y verificado;
- Obesidad no visible como published;
- daño documentado;
- no se perdió ningún artefacto de usuario.

### Fase 1 — Baseline verde y tests que sí detectan producción rota

Objetivo:

crear una red de seguridad antes de refactorizar.

Trabajo backend:

- tests de no-overwrite por target;
- test de que configured/preliminary no puede crear produccion_<slug>.csv en la ruta
  canónica ni declarar una política OOS no ejecutada;
- hacer que produccion_padecimiento falle cerrado por lifecycle y destino;
- tests fail-closed del guard temporal de predice ante schema inválido y destino
  inexistente;
- test de upsert preservando enfermedades ajenas;
- test save/load con transforms;
- test de fronteras epidemiológicas;
- test de cobertura exacta;
- test de CLI non-zero en partial failure;
- golden de SeriesKeys reales desde main;
- golden numérico representativo con tolerancia;
- caracterizar y fijar un test para la ausencia legacy de 2027-01-25 en las 111
  series Stacking·Alzheimer antes de decidir si se corrige;
- incluir scripts críticos en Ruff y mypy;
- corregir warnings que ocultan errores relevantes.

Trabajo frontend:

- resolver las 11 pruebas existentes;
- reconstruir índice RAG;
- dejar npm run check verde;
- capturar baseline real de landing, EpiBot, Reports y search;
- separar fallos preexistentes de cambios de Obesidad.

Criterio de salida:

- backend completo verde;
- frontend 616/616;
- RAG sin drift;
- tests P0 rojos sobre la implementación vieja y verdes solo con fixes posteriores;
- ningún golden autorreferencial.

### Fase 2 — Configuración namespaced y registry v2

Objetivo:

convertir configuración en contrato real.

Trabajo:

- eliminar merge plano de motores;
- introducir schemas Pydantic;
- separar registry en módulos menores de 300 líneas;
- corregir target_space por motor;
- compilar profiles;
- generar digest;
- fail closed para desconocidos;
- generar shims legacy desde registry;
- migrar constantes sin romper API;
- implementar config doctor estricto;
- añadir fixture disabled para probar resolución;
- añadir lint de hardcodes con allowlist.

Consumidores a migrar:

- entrenamiento;
- Prophet;
- DeepAR;
- Ensemble;
- Stacking;
- NBGLM;
- preprocessing;
- selección;
- predicción;
- catálogo;
- weekly;
- publisher;
- frontend manifest.

Criterio de salida:

- ningún motor hereda claves de otro;
- profile Obesidad resuelto muestra Prophet/DeepAR según decisión y
  Ensemble/Stacking en conteos;
- unknown keys fallan;
- enfermedad desconocida falla;
- shims legacy conservan resultados;
- añadir un disease fixture no exige editar Python.

### Fase 3 — Identidad temporal, extracción y datos

Objetivo:

producir un dataset E66 verificable y sin colisiones.

Trabajo temporal:

- conservar source_year/source_week;
- definir epi_year/epi_week;
- calcular period_start una sola vez;
- eliminar la regla basada en max observado;
- fixtures para 2014/2015 y 2025/2026;
- clave única por enfermedad, entidad y periodo;
- migración explícita de datos existentes;
- validar que no se suman dos periodos.

Trabajo extractor:

- source registry tipado;
- consumir block_index, onboard, layouts y backend;
- validación exacta de 32 entidades;
- validación del TOTAL impreso;
- validación de columnas y dtypes;
- regla explícita n.e.;
- checksum PDF;
- extractor_version;
- config_digest;
- atomic output;
- non-zero ante fallos no esperados;
- incremental por checksum;
- manifest obligatorio.

Trabajo merge/preprocess:

- abortar ante duplicados;
- exigir manifest verde con excepciones declaradas;
- relectura y validación después de escribir;
- cleanup de temporales;
- preprocessing manifest;
- population as-of explícita;
- ajustes dentro de fold.

Tests:

- corpus completo de 654 PDFs;
- 653 ok + 1 no_page esperado;
- 20,896 filas;
- 32 estados exactos;
- 1 NA n.e.;
- 1,696 NA históricos;
- TOTAL diff 0;
- cero duplicados epidemiológicos;
- invariantes hombres + mujeres.

Criterio de salida:

- dataset v2 con digest;
- calendario único;
- extracción reproducible;
- weekly puede detectar si E66 falta aunque otras enfermedades estén presentes.

### Fase 4 — Runs, artifacts y entrenamiento reanudable

Objetivo:

hacer que todo entrenamiento sea identificable, recuperable e idempotente.

Trabajo:

- RunManifest;
- leases/locks por run y SeriesKey;
- Artifact Envelope v2;
- temp + fsync/rename donde aplique;
- journal incremental;
- resume por estado, no por existencia de PKL;
- reconstrucción del summary desde envelopes;
- timeout y heartbeat;
- resource budgets;
- cancellation limpia;
- no side effects de gráficos;
- comando genérico train --disease --engine --run-id;
- validación de elegibilidad;
- adaptador legacy.

Refit:

- separar evaluate_fit de final_fit;
- Ensemble y Stacking deben refitear sobre toda la serie aprobada;
- el envelope registra final_refit=true;
- NBGLM corrige alineamiento antes de usarse.

Tests:

- matar una ejecución a mitad;
- reanudar sin repetir completados;
- impedir dos corridas sobre la misma clave;
- summary completo tras resume;
- no procesos huérfanos;
- save/load paridad;
- error terminal si falta un artefacto.

Criterio de salida:

- fleet de prueba completa tras kill/resume;
- summaries son upserts;
- transforms y refit verificables desde metadata.

### Fase 5 — Forecast shards e inversión correcta

Objetivo:

eliminar escrituras destructivas y hacer la escala auditable.

Trabajo:

- ForecastFrame v2;
- shards por run/engine/disease;
- loader metadata-first;
- inversión de tasa/log desde envelope;
- cobertura esperada;
- validación de fechas;
- validación de no negativos;
- coherencia;
- atomic promotion;
- generador de CSV legacy;
- upsert preservando otras enfermedades;
- separar generación de figuras.

Regresiones obligatorias:

- mismo PKL Prophet Obesidad produce la inversa correcta;
- reload no depende de config actual;
- predecir Obesidad no cambia hashes de neuro/Dengue;
- un fallo de un modelo bloquea promoción;
- nombre compuesto no afecta identidad;
- forecast target tiene 52 semanas exactas.

Criterio de salida:

- cero sobrescrituras ajenas;
- 111 productos Obesidad por engine aprobado;
- agregados legacy reconstruibles;
- forecast escala cases verificada.

### Fase 6 — Evaluador común y políticas reales

Objetivo:

obtener una comparación honesta.

Trabajo:

- BacktestSpec;
- runner de folds común;
- transforms dentro de fold;
- adapter ForecastFrame por motor;
- horizons idénticos;
- baselines elegibles;
- interval metrics;
- reconciliación por fold;
- EvaluationManifest;
- dispatch de SelectionPolicy;
- low-incidence policy real;
- bloqueo de motor faltante;
- modos preliminary/degraded explícitos.

Corregir antes:

- NBGLM slicing futuro;
- holdout 77 vs contrato 52;
- OOF solapado;
- métricas cero por fallo;
- intervalos ficticios;
- cualquier uso de fitted values como OOS.

Criterio de salida:

- cada motor usa las mismas fechas;
- cada score está en casos;
- Seasonal Naive puede ganar;
- no hay leakage detectado;
- selection manifest reproduce la decisión;
- la etiqueta rolling_cv_v1 solo aparece si realmente se ejecutó.

### Fase 7 — Benchmark local de Obesidad

Objetivo:

elegir un portafolio eficiente para el M3 Pro.

Orden:

1. Seasonal baselines.
2. ETS/Theta/MSTL.
3. regresión armónica.
4. NB-GLM corregido.
5. LightGBM global directo.
6. Prophet corregido.
7. Ensemble corregido.
8. AutoARIMA presupuestado.
9. N-HiTS pequeño.

Trabajo:

- ejecutar folds comunes;
- registrar runtime/RSS;
- tres seeds para estocásticos;
- comparar Bottom-Up y MinTrace;
- bootstrap pareado de errores;
- reportar macro, nacional, p90 y bias;
- decidir eligible/shadow/rejected;
- no preservar cuatro motores por obligación histórica.

Criterio de salida:

- shortlist gana al baseline de manera material;
- presupuesto local aceptable;
- coherencia exacta;
- decision record por motor.

### Fase 8 — Experimento DeepAR

Objetivo:

resolver con evidencia si DeepAR aporta valor.

Trabajo:

- D0 harness;
- D1 device/distribution;
- D2 estabilidad;
- D3 global;
- early stopping validation;
- threads acotados;
- locks;
- tres seeds;
- benchmark contra shortlist;
- decisión eligible o experimental.

Criterio de salida:

- no “hangs” sin diagnóstico;
- no duplicados;
- no workers huérfanos;
- resultado completo;
- gate de supervivencia evaluado.

### Fase 9 — Catálogo y publisher atómico

Objetivo:

publicar desde datos declarativos, no desde forks.

Trabajo backend:

- catálogo itera published diseases;
- fuentes de selección declaradas;
- conteos calculados;
- sin fallback mágico;
- Tableau genérico;
- Reports genérico;
- validación semanal genérica;
- prospectiva genérica;
- gallery manifest;
- release doctor.

Trabajo frontend:

- diseases.generated.json;
- aliases generados;
- roster generado;
- contenido separado de lógica;
- EpiBot sin handler por enfermedad cuando la respuesta es genérica;
- RAG usa el mismo manifest;
- landing usa conteos compilados;
- content-hash cache bust;
- app.js y kb.js divididos por responsabilidad;
- preview separado de published.

Publisher:

1. construir staging;
2. validar todos los canales;
3. ejecutar tests;
4. comparar expected counts;
5. generar ReleaseManifest;
6. promover con swap;
7. conservar rollback pointer.

No escribir del dashboard hacia el backend.

Criterio de salida:

- Obesidad solo visible si lifecycle efectivo es published;
- catálogo esperado calculado: 432 + 111 = 543;
- galería esperada calculada: 444 + 111 = 555;
- landing, Tableau, Reports, EpiBot, exact search y RAG consistentes;
- frontend 100% verde;
- rollback probado.

### Fase 10 — Weekly, DVC y operación

Objetivo:

hacer sostenible el siguiente boletín.

Trabajo:

- pipeline semanal dirigido por sources del registry;
- freshness matrix por disease/source;
- descubrimiento incremental por checksum;
- validación antes de merge;
- no git push desde build;
- no tolerar dvc add fallido;
- promoción DVC separada y revisable;
- observabilidad por stage;
- run summaries;
- alertas de cobertura;
- rollback;
- prospective validation antes de retrain;
- reproducibility drill desde clone + dvc pull.

Criterio de salida:

- dry-run semanal no modifica nada;
- corrida con un PDF nuevo actualiza solo targets correctos;
- fallo de E66 no queda oculto por filas neuro;
- DVC reproduce el release;
- no secrets/rutas/cuentas hardcodeadas.

### Fase 11 — Prueba N+1 con F50

Objetivo:

demostrar que la arquitectura es genérica.

F50 ya está descrito como bloque vecino en cuadros.yaml, pero su id no existe en el
registry. Se usará como prueba disabled.

Trabajo:

- añadir DiseaseSpec F50 disabled;
- usar el mismo source group;
- extraer fixtures representativos;
- compilar registry;
- ejecutar config doctor;
- construir universe y manifests;
- no publicar;
- inspeccionar git diff.

Gate brutal:

la prueba solo pasa si no fue necesario editar Python o JavaScript genéricos.

Si hubo que añadir una condición por F50, se registra el gap y se vuelve a la fase
correspondiente.

---

## 9. Matriz de pruebas obligatoria

### Config

- schema versions;
- unknown keys;
- unknown engines;
- references;
- digest determinista;
- no merge collisions;
- shims legacy;
- fail closed.

### Data

- exact states;
- totals;
- source exception;
- dtypes;
- duplicate periods;
- year boundary;
- incremental checksum;
- manifest;
- atomic merge;
- non-target preservation.

### Model

- fit/predict/save/load;
- refit complete;
- transform roundtrip;
- target space;
- seed;
- timeout;
- resume;
- lock;
- partial failure;
- resource cap.

### Forecast

- schema;
- exact keys;
- exact horizon;
- scale cases;
- no NaN/inf;
- nonnegative;
- hierarchy;
- upsert;
- preserve unrelated;
- atomic write.

### Evaluation

- same folds;
- no future data;
- preprocessing per fold;
- baseline eligible;
- metrics on matching timestamps;
- intervals;
- seed stability;
- missing engine blocks.

### Publish

- lifecycle;
- catalog;
- counts;
- all channels;
- RAG parity;
- cache hashes;
- staging;
- rollback;
- no cross-repo reverse writes.

### End-to-end

- Obesidad from PDF fixture to preview;
- kill/resume training;
- single-disease forecast without collateral changes;
- release doctor red on missing artifact;
- F50 config-only dry run.

---

## 10. Gates de lifecycle

Reemplazar configured/trained/published manual por estados verificables:

### draft

- spec incompleto o no aprobado.

### configured

- schema y referencias válidos;
- no implica datos ni visibilidad.

### data_ready

- extracción y preprocessing manifests verdes;
- universe completo;
- data digest congelado.

### trained

- todos los motores training requeridos con runs completos;
- envelopes y refit válidos.

### evaluated

- backtest común completo;
- baselines incluidos;
- selection manifest válido.

### approved

- decisión humana registrada;
- excepciones explícitas;
- prospective plan.

### published

- ReleaseManifest completo;
- todos los canales verdes;
- promoción atómica.

### retired

- fuera de roster activo;
- artefactos y lineage conservados.

El estado se calcula desde manifests. No se obtiene solo cambiando una palabra en YAML.

---

## 11. Definition of Done para Obesidad

### Datos

- 653 boletines E66 válidos y una ausencia esperada;
- 20,896 filas fuente o nuevo conteo explicado por boletines posteriores;
- 32 entidades exactas;
- TOTAL 0 diferencia;
- n.e. preservado;
- cero duplicados epidemiológicos;
- period mapping probado;
- manifest y digests.

### Universo

- 64 series base;
- 111 productos;
- hombres + mujeres = general;
- regiones y nacional coherentes;
- cero claves faltantes/duplicadas.

### Modelos

- baselines completos;
- shortlist local completa;
- refit final;
- envelopes;
- DeepAR decidido, no simplemente incompleto;
- runtime registrado.

### Evaluación

- folds comunes de 52;
- casos absolutos;
- sin leakage;
- baseline elegible;
- intervalos evaluados;
- selección reproducible;
- motor faltante bloquea.

### Forecast

- shards;
- upsert seguro;
- no cambio a 432 legacy fuera del release aprobado;
- inverse transforms correctas;
- cobertura 52;
- nonnegative;
- coherent.

### Productos

- catálogo 543 calculado;
- galería 555 calculada;
- landing;
- Tableau;
- Reports;
- EpiBot;
- búsqueda exacta;
- RAG;
- weekly validation;
- prospective validation;
- content hashes.

### Calidad

- backend verde;
- scripts en lint/typecheck;
- dashboard 616/616 o mayor;
- RAG check verde;
- módulos nuevos <=300 líneas;
- monolitos tocados reducidos por responsabilidad;
- docs generadas o sincronizadas.

### Reproducibilidad

- run manifests;
- data/model/config/code digests;
- DVC reproducible;
- environment lock;
- release rollback;
- clone-to-release drill.

No se considera terminada si falla una sola sección.

---

## 12. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Restaurar DVC encima de evidencia | pérdida irreversible | backup + hashes + checkout temporal |
| Romper neuro/Dengue al centralizar | producción legacy | golden real + adapters + diff por SeriesKey |
| Registry incorrecto rompe motores al consumirse | forecasts en escala errónea | corregir target spaces antes de migrar |
| Calendario cambia métricas históricas | decisiones se mueven | versionar dataset y repetir todos los folds |
| Transformación no invertida | magnitudes falsas | Artifact Envelope + roundtrip tests |
| Global model filtra futuro | score optimista | feature pipeline dentro de fold |
| Selección por agregado rompe coherencia | totales contradictorios | seleccionar base y reconciliar |
| DeepAR vuelve a saturar equipo | horas perdidas | lock, worker=1, budgets, watchdog |
| MPS fallback oculta costo/bugs | diagnóstico falso | registrar device y fallback por operación/run |
| Frontend manual evade lifecycle | preview en producción | generated manifest + release gate |
| Conteos hardcodeados quedan stale | mensajes inconsistentes | calcular desde catálogo |
| DVC sucio se publica | artefactos no reproducibles | scoped status + promoción separada |
| Fuente cambia layout | extracción plausible incorrecta | schema/layout versionado + TOTAL + fixtures |
| Modelos complejos no ganan baseline | costo sin valor | baseline elegible y rejection record |
| Intervalos falsos | falsa confianza | point-only explícito o calibración real |

---

## 13. Estrategia de cambios y commits

Cada fase debe producir commits pequeños y reversibles.

Orden recomendado:

1. docs/audit + guards de contención;
2. tests P0;
3. config namespaces;
4. registry schema/compiler;
5. temporal/data contracts;
6. run/artifact contracts;
7. forecast shards;
8. evaluator/selector;
9. model fixes;
10. local candidates;
11. DeepAR experiment;
12. catalog/publisher;
13. weekly/DVC;
14. F50 proof;
15. Obesidad release manifest.

Reglas:

- backend y dashboard en commits separados;
- artefactos generados separados del código;
- no mezclar DVC pointer con código no revisado;
- no auto-commit desde scripts;
- cada commit declara tests;
- cada migración tiene rollback;
- no usar un commit masivo “finish obesity”.

---

## 14. Decisiones ya tomadas por esta auditoría

1. Obesidad actual es preliminary, no production.
2. produccion_obesidad.csv actual no es una selección rolling válida.
3. No se completará DeepAR con el runner actual.
4. “Deadlock MPS/StudentT” no se acepta como causa demostrada.
5. Seasonal Naive es candidato elegible.
6. La unidad base de Obesidad será estado × sexo, 64 series.
7. Los 111 son productos, no obligación de 111 modelos independientes.
8. General, regiones y nacional deben ser coherentes.
9. Un motor puede ser rechazado aunque sea histórico.
10. Cloud solo después de corrección local y harness reproducible.
11. El dashboard no puede publicar una enfermedad configured.
12. El siguiente padecimiento debe probar configuración-only.

---

## 15. Preguntas que deben resolverse con experimento, no por opinión

- ¿Conteos o tasa producen mejor OOS para Prophet una vez corregido el calendario?
- ¿NB-GLM con offset supera ETS/Theta?
- ¿LightGBM directo supera Seasonal Naive en nacional y p90 estatal?
- ¿Bottom-Up basta o MinTrace mejora sin crear negativos?
- ¿N-HiTS justifica su costo?
- ¿DeepAR global mejora al menos 5% de forma estable?
- ¿Normal o StudentT es más robusta localmente?
- ¿MPS aporta velocidad real después de fallback?
- ¿Qué fold debe considerarse stress COVID y cómo se pondera?
- ¿Se debe publicar un aggregate como reconciled_mixed en vez de un motor único?

Las respuestas deben quedar en Decision Records con links a manifests.

---

## 16. Fuentes técnicas oficiales para los candidatos

- StatsForecast, modelos estadísticos:
  https://nixtlaverse.nixtla.io/statsforecast/src/core/models.html
- StatsForecast, catálogo y capacidades:
  https://nixtlaverse.nixtla.io/statsforecast/src/core/models_intro.html
- MLForecast, pipeline y lags:
  https://nixtlaverse.nixtla.io/mlforecast/forecast.html
- MLForecast, un modelo por horizonte:
  https://nixtlaverse.nixtla.io/mlforecast/docs/how-to-guides/one_model_per_horizon.html
- MLForecast, intervalos conformales:
  https://nixtlaverse.nixtla.io/mlforecast/docs/tutorials/prediction_intervals_in_forecasting_models.html
- NeuralForecast N-HiTS:
  https://nixtlaverse.nixtla.io/neuralforecast/models.nhits.html
- NeuralForecast PatchTST:
  https://nixtlaverse.nixtla.io/neuralforecast/models.patchtst.html
- HierarchicalForecast:
  https://nixtlaverse.nixtla.io/hierarchicalforecast/index.html
- GluonTS DeepAREstimator:
  https://ts.gluon.ai/stable/api/gluonts/gluonts.torch.model.deepar.html
- PyTorch MPS:
  https://docs.pytorch.org/docs/stable/notes/mps.html
- PyTorch MPS fallback y memoria:
  https://docs.pytorch.org/docs/stable/mps_environment_variables.html
- PyTorch multiprocessing:
  https://docs.pytorch.org/docs/stable/notes/multiprocessing.html
- statsmodels ExponentialSmoothing:
  https://www.statsmodels.org/stable/generated/statsmodels.tsa.holtwinters.ExponentialSmoothing.html
- scikit-learn Ridge:
  https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html
- LightGBM parameters:
  https://lightgbm.readthedocs.io/en/stable/Parameters.html

Estas fuentes justifican disponibilidad y capacidades. No sustituyen el benchmark local.

---

## 17. Siguiente acción autorizable

La primera acción de implementación no fue entrenar ni publicar.

Fue cerrar el delta documental de Fase 0 — **✅ COMPLETADO en e1d77c4a**:

1. ✅ retirado el `dvc checkout --force` global y todo checkout sin target explícito;
2. ✅ bloqueadas/reescritas las recetas de train, SageMaker, predice y publicación de los
   documentos históricos (banner NO-GO antes de su aparición);
3. ✅ corregidos el encabezado ambiguo, los conteos de modelos/tests y las afirmaciones
   end-to-end que la auditoría invalidó;
4. ✅ este plan quedó **trackeado en git**;
5. ✅ gate documental revalidado sin tocar datos, modelos ni DVC.

**Fase 0 CERRADA.** Ahora sí puede iniciar **Fase 1** (con OK formal). El primer test debe demostrar
que un padecimiento configured/preliminary **no** puede recrear una selección canónica — es decir, el
**lifecycle gate del selector** (`produccion_padecimiento.py` ignora hoy `lifecycle`). No entrenar ni
publicar durante ese trabajo.
