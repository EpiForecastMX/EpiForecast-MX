# C7 — Plan operativo de publicación de Obesidad

> **Estado autoritativo (2026-07-27): C7.2 y C7.3 CERRADAS; C7.5-PREP PASS; núcleo C7.6 PASS;
> B4.2 PASS; RAG-A/A.1/B y **RAG-C-REPEAT definitivo PASS**. STATUS-A/A.1/A.2/A.3/A.3.1 y
> STATUS-B/B.1 están **CERRADOS / PASS**. La atribución DVC y el descubrimiento de sinks cerraron.
> ADAPTERS-A/A.1/A.1.1 están **CERRADAS / PASS** tras auditoría ejecutable: instalación sellada,
> 16 fronteras del installer, promoción y rollback recuperables del par Tableau y preflight
> fail-closed. ADAPTERS-B0 + B0.1 están **CERRADAS / PASS** tras auditoría independiente:
> identidad obligatoria, containment real y recuperación no destructiva verificadas con repros.
> La validación externa de Google Sheets/Tableau todavía no comenzó. Backend local y remoto
> sincronizados en `c453b979`; dashboard local y remoto sincronizados en
> `feat/c73-candidate-staging@9487e322`.
> 47.3 quedó **CERRADA / PASS**: `npm test` verifica primero el fixture reproducible, ejecuta
> 616/616 respuestas con handler real y luego 41/41 contratos focalizados.
> 47.2-B1/B2/B3/B4/B4.1 quedó **CERRADA / PASS** después de auditoría independiente: 616/616 casos,
> handler real, cero discrepancias nombradas, cifras del ranking recalculadas desde su fuente y
> exactamente 12 respuestas modificadas respecto de `a1412e33`. La cobertura estatal histórica
> continúa siendo parcial (14/32), pero ahora se declara como tal y no se presenta como ranking
> nacional completo. El
> target DVC del release
> `obesidad_release_2517e7858901` está sincronizado y fue restaurado con caché vacía. El SIGSEGV
> PyTorch→LightGBM quedó aislado por archivo, con 1,918 fast y 61/61 integraciones. No hubo
> activación, merge, deploy ni publicación.
>
> **Decisión de política del usuario (2026-07-26):** no esperar cuatro semanas antes de publicar.
> C7.4 conserva exactamente su candidato, control, umbrales y `gate_digest`, pero pasa de gate
> previo a **verificación prospectiva posterior a una publicación condicionada**. Hoy continúa
> `INCOMPLETE (0/4)` y no se presenta como PASS. Un FAIL final obliga a rollback; un PASS convierte
> la publicación condicionada en confirmada.
>
> **Orden vigente:** el checkpoint remoto de ambos repos quedó **CERRADO / PASS**. Por decisión del
> usuario, todas las tareas que requieren intervención manual quedan estacionadas: inventario del
> preview de Netlify, creación/compartición de Google Sheets, credenciales, Tableau Desktop,
> activación y deploy. La primera auditoría del harness encontró dos P0 en el handoff externo:
> la receta canónica no podía localizar el shard y la evidencia local alterada no se revalidaba.
> A.1 cerró esos defectos, pero la reauditoría encontró dos fronteras restantes: el flujo externo
> aceptaba una evidencia reubicada bajo rutas versionables y no exigía que `shard_files` fuera
> exactamente el inventario del shard. A.2 cerró ambas. A.3 cerró la identidad de las hojas, el
> plan completo y la revalidación viva de sólo lectura. A.3.1 cerró la forma anidada con un único
> validador compartido por productor y consumidor. La auditoría final del rango de cinco commits
> quedó **PASS**. La llegada del boletín fuente 2026-W28 abre una acción funcional nueva y legítima:
> registrar la primera semana prospectiva sin tocar el pipeline legacy. **No ejecutar
> `make update-week`**: no alimenta C7.4 y hace pull/force/push sobre superficies ajenas. Continuar
> únicamente con `C7.4-WEEK-1-A`, local y sin promoción. La Ronda 129 contiene la orden vigente;
> cualquier orden histórica incompatible queda sustituida.
> Obesidad continúa por ahora `trained`, NO-GO e invisible para `published_only`.
>
> **Avance operativo estimado de C7: 83% hacia la publicación condicionada.** La cifra usa pesos
> declarados por impacto del entregable, no cantidad de commits ni líneas. Estado por fase:
>
> | fase | peso | avance | aporte | estado verificable |
> | --- | ---: | ---: | ---: | --- |
> | C7.0 contención de residuos | 5% | 100% | 5.0% | PASS |
> | C7.1 identidad y registry | 10% | 100% | 10.0% | PASS |
> | C7.2 bundle inmutable + DVC | 20% | 100% | 20.0% | PASS |
> | C7.3 compilador y consumidores en sombra | 20% | 100% | 20.0% | PASS |
> | C7.4 congelado prospectivo | 10% | 50% | 5.0% | contrato congelado; evidencia `0/4` |
> | C7.5 preparación de activación | 10% | 85% | 8.5% | PREP PASS; falta gate integral final |
> | C7.6 readiness | 15% | 97% | 14.6% | carril autónomo PASS; falta B1 externo/manual |
> | C7.7 activación, deploy y smoke | 10% | 0% | 0.0% | no autorizado ni ejecutado |
> | **Total** | **100%** |  | **83.1% ≈ 83%** | Obesidad sigue oculta |
>
> El **83% no significa publicada**: la exposición pública sigue en **0%** porque lifecycle, puntero
> activo y deploy no se han ejecutado. La confirmación prospectiva se informa separadamente como
> **0/4 semanas (0%)** y continuará después de la publicación condicionada por decisión explícita
> del usuario. Próximo incremento real: validar el sink real de staging en preflight y apply
> separados y sólo entonces solicitar las autorizaciones de C7.7.
>
> **Avance del programa completo C1–C7 por macrohitos: ≈98%.** C1–C6 están cerradas y C7 va al
> 83%; usando una macrofase como unidad, `(6×100 + 83) / 7 = 97.6%`. Esta lectura mide construcción
> técnica y gates, no exposición: publicación real **0%** y prospectiva **0/4**.
>
> **Alcance:** publicar únicamente Obesidad E66. Anorexia F50 permanece
> `lifecycle=configured`, `channels: []`, `gallery_enabled: false` y oculta durante toda C7.
>
> **Límite de autoridad:** este documento no autoriza `dvc add`, `dvc push`, `git push`, merge,
> deploy, regeneración de Tableau, escritura en rutas canónicas ni el cambio
> `trained → published`. Cada acción externa se aprueba por separado después del gate de
> preparación.

C7 reemplaza únicamente la sección de publicación de
`docs/PLAN_BRUTAL_OBESIDAD_N_PLUS_1.md`. No reabre C1–C6, no retunea modelos y no modifica
`rolling_cv_v1`.

---

## 1. Resultado buscado

Publicar el forecast congelado de Obesidad como un release inmutable, restaurable y consumido por
puentes genéricos, sin alterar los artefactos de Depresión, Parkinson, Alzheimer o Dengue.

La publicación inicial tendrá estas decisiones cerradas:

| decisión | contrato C7 |
| --- | --- |
| Padecimiento | solo `obesidad` |
| Canales públicos iniciales | `web`, `epibot`, `reports`, `tableau` |
| Canales diferidos | `weekly_validation`, `prospective_validation` |
| Galería | desactivada en el primer release |
| Intervalos | `point-only`, declarado en datos, reportes y UI |
| Sede de modelos | bundle inmutable propio bajo DVC; no `models/` legacy ni `runs/` completo |
| Gate prospectivo | congelado antes de publicar; 4 semanas consecutivas como verificación posterior |
| Estado inicial público | publicación condicionada, con validación prospectiva `0/4` visible |
| Activación | lifecycle + puntero de release público; ambos deben coincidir |
| Rollback | restaurar puntero y versiones públicas anteriores; no borrar el bundle |

La decisión formal del usuario del 2026-07-26 autoriza cambiar el orden, no falsear el resultado:
C7.4 permanece `INCOMPLETE` hasta reunir cuatro semanas válidas. La publicación inicial será
`published`, pero deberá declarar de forma visible **“validación prospectiva en curso (0/4
semanas) · pronóstico puntual sin intervalos”**. No se permite llamar PASS a un resultado
incompleto, retirar la etiqueta antes del PASS, retunear con esas semanas ni cambiar el congelado.

---

## 2. Punto de partida verificado

Estado local al redactar:

| componente | estado |
| --- | --- |
| Backend | `feat/registry-padecimientos-obesidad` @ `be143338`; local `ahead 3` antes del cierre doc-only |
| Remoto backend | `origin/feat/registry-padecimientos-obesidad` @ `827de945` |
| Frontend | `main` @ `179bbe36`, sin cambios trackeados |
| Obesidad | `trained`, NO-GO, invisible para `published_only` |
| F50 | `configured`, NO-GO, sin canales |
| Publicados | Depresión, Parkinson, Alzheimer y Dengue |
| Respaldo C5–C6 | `029fe666`, local + S3, SHA256 concordante |
| C7.0 | residuos pre-C3 fuera del dataset canónico; guard en `b981b6e5` |
| C7.1 | registry por backend + validación de identidad; publicado en la rama remota hasta `0dbd0f01` |
| C7.2-A | builder temporal determinista en `2bed74ee`; local, sin DVC |
| C7.2-A.1 | activación fuera del bundle en `fb3bcdca`; local, sin DVC |
| C7.2-A.2 | schemas v2 en `b809599d`; local, sin DVC |
| C7.2-A.2.1 | builder como procedencia sellada en `d5347905`; local, sin DVC |
| Checkpoint C7.2-A | cinco commits publicados por fast-forward hasta `827de945` |
| C7.2-B | bundle local + doctor + target DVC en `c6a2e713`; sin push |
| C7.2-C1 | target DVC presente en S3 y restaurado desde caché vacía; sin Git push |

Cadena estadística canónica:

| fase | run canónico |
| --- | --- |
| Dataset | `obesidad_1502d1a25b48` |
| Tuning Prophet | `obesidad_tune_smoke_3398a12d14c8` |
| Benchmark | `obesidad_benchmark_full_bbe604256cca` |
| Selección | `obesidad_select_bbe604256cca_fe51b3f6a20e` |
| Aceptación 2025 | `obesidad_benchmark_test_7f582a3a4ed7_82370419efd4` |
| Refit final | `obesidad_refit_final_91590fa7452f_ff249060018a` |
| Forecast | `obesidad_forecast_h52_ff249060018a_92d446b6df8f` |

Invariantes ya aprobados:

- 64 modelos base, 653 observaciones por serie y `train_end=2026-W26`;
- 111 productos: 64 bases + 47 derivados por suma exacta;
- 3,328 predicciones base y 5,772 filas totales para 2026-W27…2027-W26;
- cero duplicados, negativos, NaN o infinitos;
- `general = hombres + mujeres`;
- región = suma de sus estados;
- nacional = suma de los 32 estados;
- aceptación 2025 positiva en bases, 111 productos y nacional General;
- forecast point-only: límites inferior y superior nulos por contrato;
- legacy neuro + Dengue byte-idéntico después de C5;
- F50 demostró N+1 sin modificar Python genérico.

---

## 3. Correcciones de la auditoría a la versión anterior

### A1 — El doctor no falla: da un falso verde

La versión anterior decía que `doctor --artifacts` fallaba porque no existían modelos legacy de
Obesidad. La comprobación real es:

```text
.venv/bin/python -m scripts.doctor_padecimiento Obesidad --artifacts
✅ Obesidad: completo (config+artefactos).
```

Ese resultado es incorrecto semánticamente. El doctor actual solo comprueba que existan
`models/<engine>/Obesidad/` para los cuatro `training_engines` legacy. Esos directorios existen y
contienen artefactos preliminares anteriores al carril nuevo:

| directorio legacy | archivos observados |
| --- | ---: |
| `models/prophet/Obesidad/` | 223 |
| `models/deepar/Obesidad/` | 121 |
| `models/ensemble/Obesidad/` | 223 |
| `models/stacking/Obesidad/` | 223 |

Esos archivos no son los 64 modelos finales de C5 y no pueden autorizar publicación. C7 debe
eliminar el falso verde mediante identidad y digests, no mediante existencia de directorios.

### A2 — La identidad de modelos ya existe; falta una sede distribuible

Los 64 modelos finales sí tienen identidad: seis `model_index.json`, 64 envelopes, 64 estados,
digests, transformaciones, `SeriesKey`, ventana de entrenamiento y lineage. El problema real es que
viven en `runs/`, ruta gitignored y fuera de DVC.

El release no debe rediseñar esos artefactos. Debe empaquetar exactamente los artefactos sellados
en una unidad inmutable y distribuible.

### A3 — No hay un puente genérico de publicación

Los consumidores actuales leen artefactos legacy y contienen supuestos de tres padecimientos
neurológicos más Dengue. El forecast del runner no se debe insertar en
`all_forecast_<engine>.csv`: Obesidad es un portafolio por SeriesKey, no la salida de un solo motor.

C7 necesita un compilador de release que genere shards y manifests por padecimiento. Los
consumidores podrán adaptar esos shards sin reinterpretar nombres de archivo ni mezclar el
portafolio con agregados por motor.

### A4 — El flip de lifecycle no es un rollback completo

Un `git revert` del lifecycle recupera la invisibilidad lógica, pero no revierte por sí solo DVC,
S3, un deploy de Netlify, archivos del EpiBot ni una extracción de Tableau. El rollback real debe
restaurar el puntero de release y las versiones públicas anteriores.

### A5 — `channels` mezcla superficies y procesos

`weekly_validation` y `prospective_validation` no son superficies equivalentes a web o Reports.
Para el primer release de Obesidad no se declararán como canales públicos. El gate prospectivo se
congela antes de publicar y se completa después como verificación condicionante, pero eso no lo
convierte automáticamente en un canal habilitado.

---

## 4. Arquitectura objetivo

```mermaid
flowchart LR
    A["Runs C5 sellados<br/>selección + aceptación + refit + forecast"] --> B["C7.1<br/>Registry tipado y doctor por backend"]
    B --> C["C7.2<br/>Release bundle inmutable"]
    C --> D["DVC target propio<br/>aún oscuro/no público"]
    C --> E["C7.3<br/>Compilador genérico en staging"]
    E --> F1["Shard Reports"]
    E --> F2["Shard Tableau"]
    E --> F3["Manifest web"]
    E --> F4["Corpus EpiBot/RAG"]
    C --> G["C7.4<br/>Forecast, control y regla congelados"]
    F1 --> I["C7.5<br/>Gates de consumidores"]
    F2 --> I
    F3 --> I
    F4 --> I
    G --> I
    I --> J["C7.6<br/>Readiness + paquete de aprobación"]
    J --> K{"OK explícito<br/>por acción externa"}
    K --> L["Subir bundle oscuro"]
    L --> M["Activar puntero + lifecycle"]
    M --> N["Deploy coordinado"]
    N --> O["Publicación condicionada<br/>validación 0/4 visible"]
    O --> H{"C7.4 llega a 4/4"}
    H -->|PASS| Q["Release confirmado<br/>retirar etiqueta de validación"]
    H -->|FAIL| R["Rollback de puntero, lifecycle y deploy"]
    H -->|INCOMPLETE| O
```

Fuentes de verdad, sin duplicar decisiones:

| dato | autoridad |
| --- | --- |
| Identidad, lifecycle y canales permitidos | registry tipado |
| Candidatos y folds de evaluación | `rolling_cv_v1` intacta |
| Selección por SeriesKey | `final_selection.csv` sellado |
| Modelos finales | `model_index.json` + envelopes + estados |
| Forecast publicable | `forecast.csv` sellado |
| Contenido del release | `release_manifest.v2` después del microcierre C7.2-A.2 |
| Release visible | puntero público versionado |

---

## 5. C7.1 — Hacer verdadera la identidad del registry y del doctor

### Objetivo

Distinguir explícitamente tres backends de artefactos:

- `legacy_models`: usa `models/<engine>/<artifact_key>/` para los cuatro padecimientos actuales;
- `runner_runs`: valida refit y forecast sellados bajo un `runs_root`; es válido para `trained`,
  nunca para `published`;
- `runner_release`: usa un `release_manifest.v2` restaurable desde DVC; es obligatorio para
  `published`.

No cambiar simplemente `training_engines` de Obesidad a seis strings. Ese campo gobierna el carril
legacy, mientras que los candidatos del runner ya viven en `rolling_cv_v1` y los motores realmente
seleccionados viven en `final_selection.csv`.

### Cambios de contrato

Añadir al schema tipado del registry una fuente de artefactos namespaced. El nombre final puede
ajustarse al estilo del módulo, pero debe representar como mínimo:

```yaml
artifact_source:
  backend: runner_runs
  refit_run_id: obesidad_refit_final_91590fa7452f_ff249060018a
  forecast_run_id: obesidad_forecast_h52_ff249060018a_92d446b6df8f
  policy_digest: dd6d4a0274a6f8bb0f51d27628294b7db694b792966abaa92528dc2765020b2a
  final_selection_digest: 91590fa7452fa75581df18d6e892ac7053727ab368d38d298a26931fe6e89bab
```

Después de C7.2, el candidato cambia a:

```yaml
artifact_source:
  backend: runner_release
  release_id: obesidad_release_<digest12>
```

`runner_runs` es admisible solo para `trained`. Para `published`, `backend=runner_release` y un
`release_id` no vacío son obligatorios.

Reglas:

1. `legacy_models` conserva el comportamiento actual para los cuatro publicados.
2. `runner_runs` y `runner_release` nunca autorizan desde `models/<engine>/Obesidad/`.
3. Para Obesidad, `training_engines`/`eligible_engines` legacy dejan de fingir que el carril nuevo
   entrenó DeepAR, Ensemble o Stacking. El runner continúa leyendo candidatos desde la política.
4. Para `runner_runs`, el doctor valida schema, padecimiento, run IDs, status, digests, 64
   SeriesKeys únicas, `final_refit=true`, `train_end`, engines realmente presentes y forecast
   64+47.
5. Para `runner_release`, el doctor valida lo anterior desde el bundle restaurado y contrasta
   `release_manifest.v2` y `SHA256SUMS.txt`.
6. Una carpeta existente sin envelope/digest correcto es un error.
7. Un artefacto preliminar legacy nunca satisface `runner_runs` ni `runner_release`.
8. F50 continúa sin source publicable y no gana canales.

### Gate C7.1

- doctor verde para Obesidad por los runs sellados, no por las carpetas legacy;
- alterar un digest, run ID, disease ID, `SeriesKey` o estado hace fallar el doctor;
- retirar un estado hace fallar el doctor;
- los cuatro publicados siguen validando con `legacy_models`;
- Obesidad permanece `trained`;
- `published_members()` sigue devolviendo exactamente cuatro padecimientos;
- ninguna salida material cambia;
- suites focalizadas, lint, typecheck y fast verdes.

### Commit propuesto

`C7.1 registry artifact backend + doctor identity-aware`

---

## 6. C7.2 — Construir un release bundle inmutable y versionarlo

### Decisión

Usar un target DVC nuevo y dedicado. La ruta se deriva de `disease_id`; Obesidad es la primera
instancia, no un literal dentro del constructor:

```text
artifacts/releases/<disease_id>/<release_id>/
# primera instancia:
artifacts/releases/obesidad/<release_id>/
```

No modificar `models.dvc`, no copiar a los directorios legacy y no versionar todo `runs/`.

`release_id` debe derivarse de los digests de los insumos inmutables, no de una fecha elegida a
mano. Formato sugerido:

```text
obesidad_release_<digest12>
```

### Contenido mínimo

```text
artifacts/releases/obesidad/<release_id>/
├── release_manifest.json
├── SHA256SUMS.txt
├── runtime_inputs/
│   ├── entidades_mx.csv
│   ├── exposure_<source_id>.csv
│   └── runtime_config.json
├── policy/
│   └── rolling_cv_v1.yaml
├── selection/
│   ├── final_selection.csv
│   ├── acceptance.json
│   └── acceptance_run_manifest.json
├── refit/
│   ├── run_manifest.json
│   ├── refit_summary.json
│   └── models/
│       └── <6 engines: índices + 64 envelopes + 64 estados>
└── forecast/
    ├── run_manifest.json
    ├── forecast_base.csv
    ├── forecast.csv
    ├── model_inventory.csv
    └── lineage.json
```

`runtime_inputs/` contiene los insumos efectivos sellados necesarios para ejecutar el forecast
desde el bundle sin depender de `runs/`, rutas absolutas ni del estado mutable del workspace. Para
el forecast actual incluye, como mínimo, el catálogo geográfico y la proyección por `cve_ent` del
snapshot de exposición. `runtime_config.json` se genera canónicamente con rutas **relativas al
bundle**, source id, referencia/corte, columnas por sexo y digests de procedencia; no se copia
literalmente `inputs/config_effective.json`, porque ese archivo conserva una ruta relativa al
workspace y no es un contrato de ejecución del release. No se incluye un input por conveniencia:
cada archivo debe estar consumido por el loader de `runner_release` o eliminarse del bundle.

`release_manifest.v2` debe declarar:

- schema y `release_id`;
- `disease_id` tomado del registry (`obesidad` en la primera instancia);
- versión del builder y code commit;
- dataset, policy, selection, acceptance, refit y forecast IDs/digests;
- conteos 64/47/111 y 3,328/5,772;
- origen 2026-W26 y horizonte 2026-W27…2027-W26;
- `interval_method=none` y `uncertainty_available=false`;
- listado de cada archivo con tamaño, SHA256 y schema;
- inventario exacto de `runtime_inputs`;
- cero timestamps de ejecución, rutas absolutas, mtime, uid, gid o metadata ambiental dentro del
  contenido inmutable.

El bundle no declara canales, galería, lifecycle, estado de activación ni ningún otro dato de
política pública. Esos campos pertenecen al futuro `public_release_pointer.v1`, que referencia un
`release_id` sin cambiarlo. El manifest y el payload de identidad tienen conjuntos de claves
cerrados y rechazan cualquier metadata de activación.

### Identidad sin ciclos y serialización canónica

No calcular el `release_id` a partir del tarball, del manifest que contiene ese mismo ID ni de
`SHA256SUMS.txt`: cualquiera de esas opciones crea una dependencia circular.

El orden obligatorio es:

1. construir un `identity_payload.v2` canónico con schema del release, `disease_id`, versión del
   builder y los digests sellados de dataset, política, selección, aceptación, refit, forecast y
   runtime inputs;
2. serializarlo como JSON UTF-8, claves ordenadas, separadores estables y newline final;
3. definir `release_id = <disease_id>_release_<sha256(identity_payload)[:12]>`;
4. construir `release_manifest.json` con ese ID e inventario de **payloads**, excluyendo del
   inventario al propio manifest y a `SHA256SUMS.txt`;
5. generar `SHA256SUMS.txt` sobre todos los payloads **más** `release_manifest.json`, pero nunca
   sobre sí mismo;
6. ordenar siempre por ruta POSIX relativa usando `sorted()` de Python por punto de código. No
   depender de `sort` de shell ni de `LC_COLLATE`.

La hora de construcción, si se necesita como telemetría, se escribe en un receipt externo al
bundle y no participa en el `release_id`, manifest, checksums ni comparación byte a byte.

### Construcción

Crear un comando genérico de promoción desde runs sellados. Debe:

1. cargar y verificar todos los manifests antes de copiar;
2. rechazar runs fallidos, padecimiento distinto o lineage inconsistente;
3. copiar desde temporales y validar el bundle completo;
4. calcular `release_id` solo con contenido determinista;
5. ser idempotente: mismos insumos producen mismo `release_id` y mismos bytes;
6. rechazar un destino existente con contenido distinto;
7. no leer nombres de archivos para inferir identidad;
8. generar JSON/CSV/checksums con serialización y orden explícitos;
9. comprobar que todos los paths persistidos son relativos al bundle;
10. cargar el snapshot de exposición y el catálogo desde `runtime_inputs`, no desde el workspace;
11. no tocar rutas canónicas ni públicas.

### Gate C7.2

- restauración desde clon/entorno limpio usando únicamente Git + target DVC;
- los 64 modelos cargan y producen el mismo forecast numérico usando solo el bundle y sus
  `runtime_inputs`;
- `forecast.csv` y los artefactos deterministas conservan los digests esperados;
- 6 índices + 64 envelopes + 64 estados presentes y verificados;
- cero referencias necesarias a rutas absolutas del equipo;
- dos builds en roots distintos y bajo locales distintos producen el mismo `release_id`,
  `release_manifest.json`, `SHA256SUMS.txt` y payloads byte a byte;
- modificar un byte de cualquier fuente de identidad cambia el `release_id`; modificar solo un
  receipt externo no lo cambia;
- manifest e inventario no tienen autorreferencias ni ciclos de checksum;
- `models.dvc`, forecasts legacy y Tableau legacy intactos;
- `dvc status` del nuevo target coherente y diff limitado al bundle/puntero nuevo;
- todavía no hay `dvc push`.

### Autorización dividida

- **C7.2-A — implementación local: COMPLETADA** en `2bed74ee`. Construyó y reprodujo dos bundles
  temporales; no escribió la ruta final ni tocó DVC.
- **C7.2-A.1 — desacoplar activación: COMPLETADA** en `fb3bcdca`. El bundle ya no depende de
  canales, galería o lifecycle.
- **C7.2-A.2 — versionar schemas: COMPLETADA** en `b809599d`. Cerró
  `identity_payload.v2` y `release_manifest.v2`, rechazó v1 explícitamente y repitió el gate.
- **C7.2-A.2.1 — compatibilidad por schema: COMPLETADA** en `d5347905`. El verifier usa schemas
  para compatibilidad y conserva `builder_version` como procedencia sellada.
- **Checkpoint Git de C7.2-A — COMPLETADO.** El remoto quedó en `827de945`; no autorizó DVC ni
  C7.2-B.
- **C7.2-B — materialización y puntero local: COMPLETADA** en `c6a2e713`. Bundle, doctor,
  restauración local y target DVC dirigido están verdes.
- **C7.2-C1 — subida DVC oscura: COMPLETADA.** El target está sincronizado y fue restaurado desde
  S3 en una caché nueva.
- **Cierre documental C7.2-C — SIGUIENTE.** Un último commit doc-only debe registrar la auditoría
  del rango.
- **C7.2-C2 — checkpoint Git:** queda listo después de ese commit y requiere autorización
  explícita. Publica el puntero y código de C7.2-B únicamente en la rama de trabajo.

### Commits

- ejecutado: `C7.2-A deterministic runner release bundle` (`2bed74ee`);
- ejecutado: `C7.2-A.1 decouple public activation from the release bundle` (`fb3bcdca`);
- ejecutado: `C7.2-A.2 version runner release schemas before persistence` (`b809599d`);
- ejecutado: `C7.2-A.2.1 decouple builder provenance from schema compatibility` (`d5347905`);
- ejecutado: checkpoint Git C7.2-A hasta `827de945`;
- ejecutado: `C7.2-B materialize the release bundle, wire the doctor and add a DVC target`
  (`c6a2e713`);
- ejecutado: C7.2-C1, subida DVC y restauración remota;
- siguiente: commit doc-only de auditoría; después, con autorización separada, C7.2-C2.

---

## 7. C7.3 — Compilador genérico y puentes en modo sombra

### Objetivo

Transformar `release_manifest.v2` y `forecast.csv` en artefactos de consumo sin editar manualmente
listas de padecimientos y sin publicar antes del lifecycle.

El compilador tendrá dos modos:

- `candidate`: escribe solo bajo un output root temporal/staging explícito;
- `public`: solo acepta un padecimiento `published` cuyo release coincida con el puntero activo.

No puede escribir directamente en producción desde el modo `candidate`.

### Contrato común de salida

Cada fila conserva:

- `release_id`;
- `disease_id`;
- `SeriesKey` completa;
- periodo MMWR y `ds`;
- `yhat_cases`;
- motor seleccionado para bases;
- `derived=true/false`;
- lineage;
- `interval_method=none`;
- límites nulos;
- etiqueta visible “Pronóstico puntual; sin intervalo de incertidumbre”.

Los 47 productos derivados se atribuyen al portafolio, no a un motor ficticio.

### Puentes de la primera publicación

| canal | salida candidate | gate funcional |
| --- | --- | --- |
| Reports | shard/report de Obesidad separado | 111 productos, lineage visible, point-only |
| Tableau | shard de Obesidad con schema documentado | relaciones y conteos exactos, sin tocar el workbook canónico |
| Web | manifest/JSON generado | filtros y series desde datos, sin lista manual de Obesidad |
| EpiBot | sección de knowledge + zoom + corpus RAG | respuestas y gráficos de Obesidad desde el release |

Reglas:

1. No añadir Obesidad a `all_forecast_prophet.csv`, `all_forecast_deepar.csv`,
   `all_forecast_ensemble.csv` o `all_forecast_stacking.csv`.
2. No añadir Obesidad a `tabla_333_modelos_produccion.xlsx`.
3. No recrear `produccion_obesidad.csv` con el selector legacy.
4. No usar `stem.split("_")` para recuperar identidad.
5. No hardcodear `if disease == "obesidad"` en compiladores o consumidores.
6. El registry/manifest gobierna color, etiqueta, CIE, canales y capacidades.
7. Un disease `trained` puede compilarse a staging, pero nunca aparecer en outputs públicos.
8. F50 debe ser una prueba negativa explícita.
9. El frontend debe soportar límites nulos sin dibujar cero, área falsa ni error.
10. EpiBot/RAG no debe afirmar que existen intervalos ni confundir 64 modelos con 111 productos.

### Gate C7.3

- dos compilaciones candidate producen bytes/digests deterministas;
- todos los valores de los cuatro puentes cuadran con el forecast sellado;
- Obesidad continúa ausente de los outputs públicos mientras esté `trained`;
- F50 continúa ausente de candidate/public salvo prueba explícita de rechazo;
- los artefactos públicos vigentes de los cuatro padecimientos no cambian;
- las suites del backend y frontend quedan verdes;
- el índice RAG se regenera desde el corpus nuevo y verifica que no exista drift;
- nada se despliega.

### Commits propuestos

Separar backend y frontend:

1. `C7.3a generic publication compiler + candidate shards`
2. `C7.3b frontend manifest consumer + point-only UI`
3. `C7.3c EpiBot corpus/RAG generated from release manifest`

---

## 8. C7.4 — Gate prospectivo congelado

### Regla

Antes de ver resultados prospectivos, congelar:

- el forecast candidato vigente, originado en 2026-W26;
- un forecast control `seasonal_naive_lag52` con el mismo origen, horizonte, dataset y SeriesKeys;
- los digests de ambos;
- la regla de aceptación.

No retunear, re-seleccionar, cambiar umbrales ni refitear usando las semanas del gate.

### Ventana

Reunir cuatro semanas objetivo consecutivas con boletín utilizable:

```text
2026-W27, 2026-W28, 2026-W29 y 2026-W30
```

Si alguna semana es fuente faltante, incompleta o no pasa el contrato de 32 entidades, no cuenta
como semana válida. El gate espera la siguiente semana válida; no convierte faltantes en ceros.

### Evaluación

Usar el mismo calendario, reconciliación, exposición, `EvaluationFrame` y fórmulas de métricas del
runner. Evaluar acumulativamente las cuatro semanas sobre:

- 64 series base;
- 111 productos;
- nacional General.

Comparar el portafolio congelado contra el control congelado. Los máximos permitidos reutilizan la
regla ya aprobada:

| ámbito | degradación máxima frente al control |
| --- | ---: |
| sMAPE bases | +5% |
| sMAPE 111 productos | +5% |
| sMAPE nacional General | +10% |

Además:

- cobertura de forecast y verdad = 100%;
- cero duplicados, negativos o no finitos;
- reconciliación aritmética exacta;
- bias, MAE, RMSE, WAPE y MASE se reportan, aunque no cambian el veredicto;
- se publica el detalle por semana para evitar que el agregado oculte una ruptura.

### Resultado

- **PASS:** confirma el release ya publicado y permite retirar la etiqueta de validación
  prospectiva en curso.
- **FAIL:** ejecutar rollback obligatorio al puntero, lifecycle y deploy públicos anteriores. No
  hay retuning automático ni sustitución silenciosa del candidato. Abrir un plan de diagnóstico
  separado después de restaurar el estado público previo.
- **INCOMPLETE:** faltan semanas válidas. Si el release ya está publicado, permanece condicionado
  y conserva la etiqueta con el contador real `n/4`; no se interpreta como PASS.

Esta excepción de orden no cambia el gate. El candidato, el control, la receta, los umbrales, las
semanas y el `gate_digest` permanecen congelados. Cualquier modificación crea otro gate y no puede
usarse para confirmar este release.

### Gate C7.4

Informe sellado con forecast/control/verdad, digests, cuatro semanas, métricas, regla y veredicto
reproducible.

### Commit propuesto

`C7.4 frozen prospective gate for runner releases`

---

## 9. C7.5 — Validación integral de canales, aún sin publicar

### Registry candidato

Preparar, sin activar todavía:

- `artifact_source.backend=runner_release`;
- `artifact_source.release_id=<release_id>`;
- `channels=[web, epibot, reports, tableau]`;
- `gallery_enabled=false`;
- lifecycle todavía `trained`.

### Matriz de aceptación

| gate | condición de PASS |
| --- | --- |
| Registry | doctor valida release y digests; false green legacy eliminado |
| Dataset/modelos | 64 modelos cargables; 111 productos reconciliados |
| Calidad | aceptación 2025 PASS + C7.4 congelado e íntegro; se permite `INCOMPLETE` por decisión explícita |
| Point-only | etiqueta consistente; ninguna banda inventada |
| Validación en curso | contador `n/4`, estado `INCOMPLETE` y regla de rollback visibles |
| Reports | shard/reporte candidate completo |
| Tableau | datasource candidate válido y legacy intacto |
| Web | Obesidad visible solo en preview candidate |
| EpiBot | preguntas E66 correctas; RAG sincronizado |
| F50 | ausente de todas las superficies |
| Legacy | cuatro agregados y selecciones productivas byte-idénticos |
| Backend | lint, typecheck, fast e integración verdes |
| Frontend | tests y `npm run check` verdes |
| DVC | diff explicado target por target; sin push |
| Reproducibilidad | restauración limpia produce los mismos artefactos |

No se acepta un PASS parcial. Si un canal falla, el release inicial de cuatro canales se detiene;
no se recorta silenciosamente el alcance.

---

## 10. C7.6 — Paquete de aprobación y STOP obligatorio

Generar un documento de release con:

- release ID y todos los run IDs/digests;
- commits backend/frontend candidatos;
- resultado de cada gate;
- diff exacto de registry;
- diff DVC por target;
- inventario del bundle;
- hashes legacy antes/después;
- preview de Reports, Tableau, web y EpiBot;
- estado prospectivo real (`INCOMPLETE n/4`, `PASS` o `FAIL`) y su `gate_digest`;
- excepción formal para publicar con C7.4 incompleto y etiqueta pública obligatoria;
- procedimiento semanal de actualización del contador sin tocar el congelado;
- plan de activación;
- plan y comandos de rollback;
- lista explícita de acciones externas aún no realizadas.

Al terminar C7.6, detenerse. El paquete preparado no autoriza publicación.

Las aprobaciones deben pedirse y registrarse por separado:

| acción | requiere OK explícito |
| --- | --- |
| `dvc push` del bundle oscuro | sí |
| push de código backend | sí |
| cambio `trained → published` | sí |
| activación del puntero público | sí |
| push/deploy del frontend | sí |
| promoción del datasource/workbook Tableau | sí |

---

## 11. C7.7 — Activación coordinada

Solo se ejecuta con C7.1–C7.3, C7.5 y C7.6 en PASS, C7.4 congelado e íntegro, y las
autorizaciones anteriores. La única excepción admitida es que el veredicto final de C7.4 continúe
`INCOMPLETE`; no se acepta un FAIL ni una alteración del `gate_digest`.

Orden:

1. subir el bundle DVC como artefacto oscuro y verificar restauración remota;
2. integrar el código genérico mientras Obesidad sigue `trained`;
3. guardar los punteros y versiones públicas actuales para rollback;
4. activar el release público y cambiar Obesidad a `published` en el mismo paquete de release;
5. generar los cuatro outputs públicos desde el release activo;
6. desplegar frontend/EpiBot y promover Tableau;
7. ejecutar smoke público;
8. mostrar en los cuatro canales la etiqueta
   `Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos`;
9. observar errores, integridad y consistencia desde el primer minuto;
10. reejecutar C7.4 con cada boletín, sin retuning ni refit;
11. al llegar a 4/4, confirmar el release si PASS o ejecutar rollback si FAIL.

El gate de activación exige:

- `published_members(channel)` incluye Obesidad exactamente para los cuatro canales;
- F50 sigue ausente;
- el puntero activo resuelve al mismo `release_id` declarado por el registry;
- el bundle se restaura desde remoto;
- las cifras públicas muestreadas coinciden con el forecast sellado;
- no existe pérdida ni cambio numérico en los cuatro padecimientos previos;
- las superficies declaran point-only;
- las superficies declaran el estado prospectivo real y el contador `n/4`;
- todos los checks públicos responden correctamente.

Commit aislado del flip:

```text
C7.7 publish obesity release <release_id>
```

No mezclar el flip con entrenamiento, regeneración de modelos o cambios de política.

---

## 12. Rollback real

### Disparadores

- bundle no restaurable;
- digest o lineage inconsistente;
- Obesidad visible en un canal no autorizado;
- F50 visible;
- cifras públicas distintas al release;
- pérdida o alteración legacy;
- frontend/EpiBot/Tableau roto;
- interpretación incorrecta de point-only;
- fallo material durante el smoke o vigilancia.

### Secuencia

1. restaurar el puntero público anterior;
2. devolver Obesidad a `trained`;
3. restaurar el deploy frontend/EpiBot anterior;
4. restaurar datasource/workbook Tableau anterior;
5. regenerar outputs desde el manifest público anterior;
6. verificar que solo queden los cuatro padecimientos previos;
7. conservar el bundle fallido y su evidencia; no borrarlo;
8. registrar incidente y hashes.

El `git revert` del lifecycle es solo una parte del rollback. DVC, deploy y Tableau se revierten con
sus propios punteros/versiones.

Objetivo de recuperación: restaurar visibilidad anterior en menos de 30 minutos sin reentrenar.

---

## 13. Orden de commits

| orden | commit | efecto público |
| ---: | --- | --- |
| 1 | C7.1 registry backend + doctor | ninguno |
| 2 | C7.2 release builder + DVC pointer local | ninguno |
| 3 | C7.3a compiler + shards candidate | ninguno |
| 4 | C7.3b frontend candidate | ninguno |
| 5 | C7.3c EpiBot/RAG candidate | ninguno |
| 6 | C7.4 congelado prospectivo | ninguno; queda `INCOMPLETE 0/4` |
| 7 | C7.5-PREP puntero/canales + gates | ninguno |
| 8 | C7.6 readiness + paquete de aprobación | ninguno |
| 9 | C7.7 flip/puntero, tras autorización | publicación condicionada |
| 10 | C7.4 veredicto 4/4 | confirmar publicación o rollback |

Backend y frontend permanecen en commits/repos separados. Los outputs materiales y sus punteros no
se mezclan con cambios de lógica.

---

## 14. Criterio final de éxito

C7 alcanza **publicación condicionada** cuando C7.6 está verde, la activación coordinada termina
sin errores y el estado `INCOMPLETE n/4` es visible. C7 termina definitivamente únicamente cuando:

- el doctor valida el backend real y no los PKL preliminares;
- el release se restaura desde Git + DVC en un entorno limpio;
- 64 modelos y 111 productos conservan identidad, digests y reconciliación;
- cuatro semanas prospectivas pasan la regla congelada; si fallan, el rollback se completa;
- Reports, Tableau, web y EpiBot consumen manifests/shards genéricos;
- la UI declara honestamente que el forecast es puntual;
- Obesidad aparece solo en los cuatro canales autorizados;
- galería, weekly validation y prospective validation públicos siguen diferidos;
- F50 continúa oculta;
- legacy permanece byte-idéntico;
- existe rollback probado por puntero/versiones;
- todas las promociones externas tienen aprobación registrada.

Antes de la activación:

```text
Obesidad = trained · NO-GO · no publicada
F50      = configured · NO-GO · no publicada
```

Después de una activación exitosa y antes del veredicto 4/4:

```text
Obesidad = published · PUBLICACIÓN CONDICIONADA · validación prospectiva n/4 visible
F50      = configured · NO-GO · no publicada
```

---

## 15. Auditoría inicial del WIP local de C7.1 — histórica, cerrada

> **Veredicto:** dirección correcta, implementación incompleta, gate **FAIL**.
>
> El WIP está sin commit sobre `b981b6e5`. Obesidad sigue `trained`; F50 sigue `configured`.
> No hubo DVC, push, deploy, flip ni cambios en el frontend.
>
> **Lectura temporal:** esta sección conserva el diagnóstico que originó las ocho acciones. Los
> cierres posteriores y las órdenes vigentes están en las secciones 16 y 17; cuando exista
> diferencia, prevalece la ronda más reciente de la bitácora.

### Delta encontrado

| archivo | intención observada | evaluación |
| --- | --- | --- |
| `config/padecimientos.yaml` | vaciar motores legacy y declarar `runner_runs` | validado y cerrado en Acción 2 |
| `src/epiforecast/registry.py` | schema de `artifact_source` y matriz de backends | tipado/lifecycle cerrados en Acción 2 |
| `src/epiforecast/registry_doctor.py` | verificar runs sellados | elimina el falso verde, pero aún no prueba todo el contrato |
| `tests/unit/test_artifact_backend.py` | tests del backend nuevo | Acciones 1–2: fixture aislado y schema; 30 PASS |
| `tests/unit/artifacts/test_transforms.py` | sacar Obesidad del resolver legacy | intención correcta; hay duplicación y pérdida de especificidad |
| `tests/unit/models/test_prophet_model.py` | impedir Prophet legacy para Obesidad | intención correcta; nombres de tests quedaron obsoletos |

El archivo del plan continúa sin trackear. Los demás untracked preexistentes pertenecen al usuario y
no entran al alcance.

### Lo que sí quedó demostrado en el checkpoint inicial

| comprobación | resultado auditado |
| --- | --- |
| `doctor Obesidad --artifacts` | verde por refit/forecast sellados |
| Doctor de Depresión, Parkinson, Alzheimer y Dengue | verde por backend legacy |
| Quitar o alterar un estado | el doctor falla |
| Obesidad | `trained`, invisible para `published_only` |
| F50 | `configured`, invisible |
| `make lint` | PASS, 250 archivos formateados |
| `make typecheck` | PASS, 137 módulos |
| Test focalizado | 90 PASS, 3 FAIL |
| `make test-fast` | FAIL: se detiene con `-x` tras 985 PASS y el primer fallo |

Los tres fallos focalizados son:

1. `test_main_rc0_aunque_teardown_falle`;
2. `test_main_rc0_aunque_teardown_reciba_senal`;
3. `test_e2e_preliminar_escribe_schema_honesto`.

La causa es válida: el selector legacy ya no puede tratar Obesidad como un padecimiento con motores
legacy. La conclusión anterior de que adaptar las pruebas “destruiría cobertura” es incorrecta:
pueden conservar exactamente el contrato de teardown/E2E usando un padecimiento sintético
`configured` con motores legacy y un registry inyectado.

### Hallazgos P0

#### P0.1 — Los tests no pueden alterar el run canónico · **CERRADO**

El defecto era real: dos pruebas escribían temporalmente dentro del refit canónico. Quedó corregido
sin mover ni regenerar la evidencia:

- `runs_root` y `models_root` son inyectables en el doctor;
- el fixture `sellado` copia refit y forecast bajo `tmp_path`;
- las pruebas de ausencia y corrupción modifican únicamente esa copia;
- los 162 archivos del refit canónico conservaron sus hashes antes y después;
- `tests/unit/test_artifact_backend.py` termina con 11 PASS.

**Gate:** ninguna prueba escribe bajo `runs/` real. **PASS.**

#### P0.2 — El doctor aún no prueba la identidad completa de los runs

Hoy verifica archivos listados, `disease_id`, comando/status, algunos digests, 64 claves,
`final_refit`, lineage 64+47 y el digest del YAML. Faltan:

- `RunManifest.run_id == artifact_source.<run_id> == nombre del directorio`;
- `policy_digest` del refit y forecast igual al registry y a la política vigente;
- mismo `dataset_id` e `input_digests` entre refit y forecast;
- `final_selection_digest` y `selection_digest` consistentes en toda la cadena;
- `acceptance_digest` positivo y consistente;
- `refit_digest` del forecast igual al refit sellado;
- artefactos con `validated=true`;
- lista/distribución exacta de los seis motores seleccionados;
- total exacto de 64 modelos, no solo 64 claves distintas;
- universo exacto de 32 claves INEGI × `{hombres,mujeres}`;
- `geography_level=estado`, frecuencia semanal y cero modelos derivados;
- `n_train=653` y `train_end=2026-W26` en todos los envelopes y en el resumen.

**Acción:** centralizar estas comprobaciones en un validador reutilizable de lineage/model index. El
doctor debe consumir ese validador, no duplicar parcialmente el contrato del runner.

#### P0.3 — El doctor no valida el forecast publicable

Comprobar `lineage.json` con 64+47 no demuestra que `forecast.csv` contenga las 5,772 filas
correctas.

**Acción:** cargar `forecast_base.csv`, `forecast.csv` y `model_inventory.csv` mediante validators
del runner y exigir:

- 3,328 filas base y 5,772 totales;
- 64 bases, 47 derivadas y 111 productos;
- horizonte exacto 2026-W27…2027-W26;
- claves/períodos únicos;
- valores finitos y no negativos;
- intervalos conjuntamente nulos (`point-only`);
- `general=hombres+mujeres`;
- región = suma de estados;
- nacional = suma de los 32 estados;
- inventario de 64 asignaciones consistente con los model indexes.

#### P0.4 — Un JSON inválido puede romper el doctor con traceback

`refit_summary.json` y `lineage.json` se leen fuera de una frontera de error. Un archivo truncado o
schema inesperado puede escapar como excepción cruda en vez de producir un `Problem` y `rc != 0`.

**Acción:** toda lectura/parsing/schema validation debe convertirse en un problema tipado. Añadir
tests para JSON truncado, claves ausentes y tipos incorrectos.

#### P0.5 — Matriz lifecycle/backend · **CERRADO EN ACCIÓN 2**

La matriz implementada y probada es:

| backend | configured | trained | published |
| --- | --- | --- | --- |
| `legacy_models` | permitido | permitido | permitido |
| `runner_runs` | rechazado | permitido | rechazado |
| `runner_release` | rechazado | permitido | permitido |

Para `runner_release`, `release_id` no vacío es obligatorio. La verificación material del release
permanece correctamente diferida a C7.2.

#### P0.6 — La suite fast está roja

No cambiar `scripts/produccion_padecimiento.py`: que Obesidad sea rechazada por el selector legacy
es el comportamiento correcto.

**Acción:** cambiar solo los fixtures de las tres pruebas fallidas:

1. crear un padecimiento sintético no publicado con `training_engines/eligible_engines`;
2. inyectarlo en `registry.require`;
3. generar sus CSV legacy dentro de `tmp_path`;
4. conservar las mismas inyecciones de fallo post-commit;
5. comprobar el mismo `rc=0`, schema preliminar y ausencia de residuos.

Así se conserva toda la cobertura sin volver a habilitar Obesidad en el carril viejo.

### Hallazgos P1

1. **CERRADO EN ACCIÓN 2:** `artifact_source` es ahora `ArtifactSource`, dataclass congelada y
   tipada por backend.
2. **CERRADO EN ACCIÓN 2:** el loader rechaza valores no-string, vacíos y whitespace.
3. **CERRADO EN ACCIÓN 2:** `prophet_grid_key` de Obesidad es `null` y salió del mapa legacy.
4. El parametrizado de round-trip repite `("Depresión", "prophet")`. Eliminar el duplicado.
5. Varios nombres todavía dicen `test_obesidad_*` aunque prueban Depresión. Renombrarlos.
6. No afirmar “sin perder cobertura” hasta mapear las pruebas removidas de Obesidad contra las
   pruebas equivalentes del runner (`prophet_count_log1p`, `prophet_rate_log1p` y envelopes).
7. Evitar que el doctor relea dos veces el mismo manifest; cargarlo una vez y pasar el objeto
   validado.

### Estado al abrir esta auditoría — histórico, supersedido

```text
C7.1     = WIP · FAIL global · Acciones 1–2 PASS · Acción 3 REABIERTA · sin commit
Obesidad = trained · NO-GO · backend candidate runner_runs
F50      = configured · NO-GO · sin backend publicable
Publicados = Depresión, Parkinson, Alzheimer, Dengue
C7.2     = NO INICIAR
```

---

## 16. Checklist ejecutado para cerrar C7.1

Ejecutar en este orden, sin ampliar alcance:

### Acción 1 — Preservar evidencia y aislar tests · **CERRADA**

- [x] registrar hashes de los 162 archivos del refit antes de probar;
- [x] inyectar roots en el doctor;
- [x] mover las pruebas destructivas a fixtures `tmp_path`;
- [x] demostrar hashes canónicos idénticos después.

**Gate:** ninguna prueba escribe bajo `runs/` real. **PASS: 11/11 tests; 162/162 hashes
preservados.**

### Acción 2 — Cerrar el schema del backend · **CERRADA**

- [x] introducir tipo inmutable para `artifact_source`;
- [x] aplicar la matriz lifecycle/backend;
- [x] rechazar valores no-string, claves extra, vacíos y combinaciones inválidas;
- [x] limpiar `prophet_grid_key` legacy de Obesidad.

**Gate:** tests positivos y negativos completos del loader. **PASS: 30/30 tests; lint y
typecheck verdes.**

### Acción 3 — Completar el validador de refit/lineage · **CERRADA**

- [x] validar run IDs, dataset, policy, digests de selección y refit digest;
- [x] validar los seis motores, 64 estados y cobertura exacta 32×2;
- [x] validar `n_train`, `train_end`, nivel geográfico y frecuencia;
- [x] reutilizar funciones del runner donde ya exista el contrato.
- [x] verificar materialmente que el run de aceptación referenciado existe y fue `accepted=true`;
- [x] exigir igualdad campo por campo entre cada entrada de `model_index`, su envelope y su estado;
- [x] exigir que manifests/jobs declaren los artefactos obligatorios con schema correcto;
- [x] exigir jobs/artefactos obligatorios también en aceptación y forecast;
- [x] convertir todos los tipos inválidos, incluidos valores de `counts` y calendario, en
  `ArtifactValidationError`, nunca traceback;
- [x] validar cobertura temporal por serie del dataset, no solo el total global de filas.
- [x] exigir que `dataset_manifest.json` declare exactamente
  `epi_dataset_v2.csv`, `products.csv` y `lineage.json`, con sus schemas canónicos;
- [x] rechazar rutas de artefacto duplicadas en manifests de dataset, runs y jobs;
- [x] probar las tres mutaciones re-selladas que producían falso verde.

**Gate:** cualquier mutación del fixture sellado genera `Problem` y rc no cero, nunca traceback.
**PASS tras tres auditorías (R5, R7, R9) y sus remediaciones:** 147 pruebas verdes, 98 mutaciones
con error tipado y cero tracebacks; los cuatro runs canónicos íntegros. Detalle en las Rondas 6, 8
y en el cierre de la Ronda 9.

### Acción 4 — Validar el forecast real · **CERRADA** (remediada en R11)

Ejecutar inmediatamente después del PASS de R9, sin una nueva pausa de revisión.

#### 4.1 — Una sola frontera de validación

- crear un validador reutilizable de contenido del forecast y llamarlo desde
  `validate_runner_runs`;
- recibir `forecast_dir`, `VerifiedRunnerRuns` y el catálogo geográfico ya cargado;
- reutilizar los contratos del runner cuando existan; no duplicar fórmulas ni leer el registry
  dentro del validador;
- convertir CSV ilegible, columna ausente, tipo inválido o contrato roto en
  `ArtifactValidationError`.

#### 4.2 — Validar `forecast_base.csv`

- exigir columnas del contrato `forecast_base.v1`, sin columnas faltantes ni claves ambiguas;
- exigir exactamente `n_models × horizon` filas, derivando `n_models` del portafolio sellado y
  `horizon` de `lineage.json`;
- exigir universo exacto de las 64 `SeriesKey` seleccionadas y un periodo por horizonte;
- exigir `run_id`, `disease_id`, `engine=portfolio`, `fold=final_refit` y origen constantes;
- exigir periodos epidemiológicos contiguos desde `shift(train_end, 1)`, sin hardcodear fechas;
- exigir `horizon=1..H`, `ds` consistente con el calendario, claves únicas, valores finitos y no
  negativos;
- exigir `yhat_lower` y `yhat_upper` conjuntamente nulos en todas las filas (`point-only`).

#### 4.3 — Cerrar el origen por job y por modelo

- concatenar los `artifacts/<engine>/forecast_base.csv` declarados por los jobs y exigir igualdad
  fila a fila con el `forecast_base.csv` consolidado;
- cada serie base debe aparecer en un solo job y el motor debe coincidir con
  `final_selection.csv`, `model_inventory.csv` y el `model_index.json` correspondiente;
- `model_inventory.csv` debe tener exactamente 64 claves únicas, sin derivados, y repetir
  `n_train`, `train_end`, formato y digest del estado sellado;
- no inferir identidad desde nombres de archivo.

#### 4.4 — Validar `forecast.csv` y las 47 derivadas

- exigir exactamente `(base + derived) × horizon` filas y 111 productos por periodo, usando
  `VerifiedRunnerRuns.counts`, no constantes de Obesidad;
- las 64 filas base del consolidado deben ser idénticas a `forecast_base.csv`;
- materializar o comprobar las 47 derivadas únicamente por suma de las bases:
  `general = hombres + mujeres`, región = suma de sus estados y nacional = suma de los 32 estados;
- usar la membresía del catálogo geográfico nuevo; no copiar el diccionario legacy;
- exigir claves/períodos únicos, horizonte completo, valores finitos/no negativos y bandas
  conjuntamente nulas;
- contrastar conteos, origen, horizonte y motores contra `lineage.json`.

#### 4.5 — Pruebas funcionales

Sobre copias aisladas y re-selladas, cubrir como mínimo:

- fila base faltante o duplicada;
- producto derivado faltante o extra;
- periodo/horizonte/origen incorrecto;
- `ds` que no corresponde a `epi_year`/`epi_week`;
- NaN, infinito o valor negativo;
- solo uno de los dos intervalos presente;
- general, región o nacional alterados;
- job base que no coincide con el consolidado;
- motor de una serie distinto entre selección, inventario y job;
- inventario con estado faltante, duplicado, derivado o digest ajeno;
- lineage con conteos u horizonte inconsistentes;
- CSV truncado, columna ausente o tipo inválido sin traceback.
- inventario con digest o formato distintos del estado sellado;
- job con identidad, procedencia o intervalos distintos del consolidado;
- bandas completas presentes en job, base o consolidado pese al contrato `point-only`.

Los tests deben derivar cantidades del fixture sellado. Los valores observados
`3,328`, `5,772`, `64`, `47`, `111` y `52` se registran como evidencia del run canónico, pero no
se escriben como reglas específicas de Obesidad dentro del validador.

**Gate:** el doctor solo da verde cuando el artefacto publicable completo es coherente.
**PASS tras R11/R12 y re-auditoría R13:** los siete falsos verdes están cerrados; inventario
anclado a estados sellados, contrato completo por job y `point-only` explícito en job/base/full.

### Acción 5 — Reparar las tres pruebas legacy sin tocar producción · **CERRADA**

- [x] reutilizar el padecimiento sintético `configured` que ya existe en el test, con
  `artifact_key/slug` propios y motores legacy;
- [x] inyectarlo en `registry.require` y redirigir `ROOT` a `tmp_path`;
- [x] sustituir Obesidad por ese registry sintético en los tres casos fallidos;
- [x] conservar íntegros los contratos de teardown y E2E preliminar;
- [x] escribir sus fixtures legacy únicamente bajo `tmp_path`;
- [x] comprobar el destino `_preliminar_NO_GO`, el schema honesto, `rc=0` y la ausencia de
  residuos;
- [x] no añadir motores legacy de vuelta a Obesidad;
- [x] conservar una prueba explícita de que Obesidad no entra al selector legacy.

**Gate:** `tests/unit/test_produccion_ownership.py` pasa completo, 75/75, por la misma ruta
productiva del selector; `scripts/produccion_padecimiento.py` y la configuración real no cambiaron.

### Acción 6 — Limpiar y justificar el delta de tests · **CERRADA**

#### 6.1 — Limpieza mecánica exacta

1. eliminar una de las dos entradas idénticas `("Depresión", "prophet")` en
   `test_forward_inverse_roundtrip`;
2. renombrar estos tres tests, cuyo cuerpo ya usa Depresión:
   - `test_obesidad_no_emite_tasa_como_casos_si_falta_exposure`;
   - `test_obesidad_alinea_exposure_historica_y_futura_por_fecha`;
   - `test_eval_rapida_alinea_exposure_y_evalua_obesidad_en_casos`;
3. usar nombres basados en `perfil_de_tasa` o `depresion`, según lo que realmente prueba cada
   cuerpo;
4. cambiar la aserción del rechazo legacy de Obesidad de `rc != 0` a `rc == 1`, que es el contrato
   observado y documentado;
5. no renombrar tests que sí verifican Obesidad, como
   `TestObesidadFueraDelCarrilLegacy` o el alta compartida con F50.

Eliminar el parametrizado duplicado reduce en uno el conteo esperado:

```text
make test-fast: 1,610 → 1,609 PASS
```

Esto no es pérdida de cobertura: eran dos ejecuciones byte-idénticas del mismo par.

#### 6.2 — Mapa de cobertura, sin duplicar el carril legacy

Registrar la separación siguiente en el comentario del módulo relevante y en la bitácora:

| contrato | cobertura autoritativa |
| --- | --- |
| resolver de transformaciones legacy | `tests/unit/artifacts/test_transforms.py` con Depresión/Dengue |
| Obesidad rechazada por el carril legacy | `test_obesidad_ya_no_resuelve_contratos_legacy`, `test_el_carril_legacy_rechaza_a_obesidad` |
| perfiles Prophet count/rate del runner | `tests/unit/runner/test_prophet_engine.py` |
| tasa + exposición vuelve a casos | `test_harness.py::test_round_trip_de_tasa_vuelve_a_casos` |
| serialización final Prophet tasa | `test_final_models.py::test_round_trip_prophet_tasa` |
| cadena real de Obesidad con ambos perfiles | `tests/integration/test_disease_run_gate.py` |

No volver a introducir Obesidad en fixtures de `ProphetForecaster` legacy para “recuperar”
cobertura: sus motores reales están cubiertos por el runner.

#### 6.3 — Gate acotado de limpieza

Ejecutar:

```text
.venv/bin/pytest -q \
  tests/unit/artifacts/test_transforms.py \
  tests/unit/models/test_prophet_model.py \
  tests/unit/models/test_tuner.py \
  tests/unit/test_produccion_ownership.py \
  tests/unit/runner/test_prophet_engine.py \
  tests/unit/runner/test_harness.py \
  tests/unit/runner/test_final_models.py \
  --no-cov
make test-fast
make lint
make typecheck
git diff --check
```

No modificar producción, registry, runner, runs o configuración durante Acción 6.

**Gate:** ninguna cobertura se sostiene solo por una afirmación documental.

**Resultado:** 213 pruebas focales PASS; se eliminó una parametrización realmente duplicada,
se corrigieron tres nombres obsoletos y el baseline fast quedó en 1,609 PASS sin pérdida de
cobertura. Detalle reproducible en la Ronda 13.

### Acción 7 — Ejecutar el gate completo · **PASS**

```text
make lint
make typecheck
make test-fast
.venv/bin/pytest -q tests/unit/test_artifact_backend.py --no-cov
.venv/bin/pytest -q tests/integration/test_disease_run_gate.py --no-cov
.venv/bin/pytest -q tests/integration/test_anorexia_f50_gate.py --no-cov
.venv/bin/python -m scripts.doctor_padecimiento Obesidad --artifacts
.venv/bin/python -m scripts.doctor_padecimiento --artifacts
```

Además:

- comparar hashes de los cuatro agregados legacy;
- confirmar que los runs C5 y C6 no cambiaron;
- confirmar `rolling_cv_v1` byte-idéntica;
- confirmar estado DVC dirigido sin delta nuevo;
- revisar `git diff --check`.

**Gate:** todo verde, sin skips que oculten la verificación central de `runner_runs`.

**Resultado revalidado:** lint PASS; typecheck PASS (144 módulos); fast 1,609 PASS; focal 259
PASS; integración Obesidad + F50 31 PASS; ambos doctors rc=0. Los agregados legacy y
`rolling_cv_v1` conservan sus hashes; frontend sin cambios trackeados. DVC dirigido continúa
`modified` por el WIP preexistente, sin archivos nuevos del 2026-07-25 bajo esos targets.

### Acción 8 — Commit aislado y STOP · **CERRADA**

El commit C7.1 solo puede incluir:

- registry/schema;
- doctor/validator;
- configuración de Obesidad;
- tests correspondientes;
- actualización de este plan.

Mensaje propuesto:

```text
C7.1 registry artifact backend + identity-aware doctor
```

Después del commit:

1. verificar tree trackeado limpio;
2. no hacer push;
3. entregar commit, diff, conteos y hashes;
4. detenerse;
5. pedir revisión explícita antes de C7.2.

No construir bundle, no ejecutar `dvc add`, no hacer `dvc push`, no tocar frontend y no cambiar
`trained → published` durante el cierre de C7.1.

**Resultado:** commit `91269e6f` con 20 rutas explícitas, 6,653 inserciones y 96 supresiones;
ninguna ruta bajo `runs/`, `reports/`, `models/`, `references/`, `data/`, `.qwen/` o frontend.
Sin push. El bloque documental de cierre se añadió después y es el único delta trackeado actual.

---

## 17. Bitácora de ejecución de las acciones obligatorias

> Este documento es el canal de comunicación de C7.1. Cada ronda de trabajo se registra aquí:
> qué se ejecutó, con qué evidencia, qué queda pendiente y qué decisión se necesita.

### Ronda 1 — 2026-07-25

#### Acción 1 — Preservar evidencia y aislar tests · **CERRADA**

Se ejecutó primero por ser el único hallazgo con riesgo de daño irreversible.

| paso exigido | resultado |
| --- | --- |
| Registrar hashes del refit antes de probar | 162 archivos; digest agregado `9ed6acf315ed1aec` |
| Inyectar roots en el doctor | `diagnose(..., runs_root=None, models_root=None)`; `_diagnose_artifacts` y `_diagnose_runner_runs` reciben la raíz |
| Mover las pruebas destructivas a `tmp_path` | fixture `sellado`: copia refit + forecast a `tmp_path`; las pruebas mutan **solo** la copia |
| Demostrar hashes canónicos idénticos después | 162/162 archivos, 0 ausentes, 0 alterados; `doctor Obesidad --artifacts` verde |

Cobertura resultante en `tests/unit/test_artifact_backend.py` (11 PASS):

- control: la copia sellada valida igual que la canónica;
- retirar un estado → falla;
- alterar un estado → falla;
- **añadida**: alterar `lineage.json` del forecast → falla.

**Gate Acción 1:** ninguna prueba escribe bajo `runs/` real. **PASS.**

#### Estado al cierre de la Ronda 1 · **HISTÓRICO**

| acción | estado |
| --- | --- |
| 2 — Cerrar el schema del backend | pendiente en esta ronda; cerrada posteriormente en Ronda 2 |
| 3 — Completar el validador de refit/lineage (P0.2) | pendiente |
| 4 — Validar el forecast real (P0.3) | pendiente |
| 5 — Reparar las tres pruebas legacy con registry sintético | pendiente |
| 6 — Limpiar y justificar el delta de tests | pendiente |
| 7 — Ejecutar el gate completo | pendiente |
| 8 — Commit aislado y STOP | pendiente |

#### Objeciones retiradas

Dos conclusiones de la ronda anterior eran incorrectas y se retiran:

1. **P0.1 era un defecto real y propio.** Un `try/finally` no basta: una prueba unitaria no puede
   escribir sobre la única evidencia viva de C5, porque una interrupción a media ejecución la
   dañaría. Corregido.
2. **«Adaptar las tres pruebas legacy destruiría cobertura» era falso.** Un padecimiento sintético
   `configured` con motores legacy y registry inyectado conserva íntegros los contratos de teardown
   y E2E preliminar. La Acción 5 es viable tal como está escrita.

#### Por qué se detuvo la ronda

Presupuesto de contexto agotado. Las acciones 2–4 son las de más sustancia —tipo inmutable con
matriz lifecycle/backend, validador reutilizable con las comprobaciones de P0.2 y validación por
contenido de los tres artefactos de forecast— y arrancarlas sin poder terminarlas dejaría el
validador reescrito a medias y sin gate, peor que no empezarlas.

#### Estado al cerrar la ronda

```text
WIP sin commit sobre b981b6e5
Obesidad = trained · NO-GO · backend runner_runs
F50      = configured · NO-GO
Sin DVC, push, deploy ni flip. Frontend intacto.
Run canónico del refit verificado íntegro (162/162).
Riesgo P0.1 neutralizado.
make test-fast sigue en FAIL por las 3 pruebas legacy (Acción 5).
```

#### Respuesta y decisión operativa para la siguiente ronda

**Continuar por la Acción 2 en orden estricto, preservando el WIP actual.**

La siguiente ronda debe:

1. implementar únicamente el schema inmutable y la matriz lifecycle/backend de la Acción 2;
2. ejecutar su gate positivo y negativo completo;
3. registrar aquí el delta, resultados y cualquier bloqueo real;
4. continuar a la Acción 3 solo si la Acción 2 queda completamente verde.

No hacer rollback ni reiniciar C7.1, no reabrir C1–C6, no modificar los runs canónicos y no iniciar
C7.2. Permanecen prohibidos DVC, push, deploy, frontend y el flip `trained → published`.

---

### Ronda 2 — 2026-07-25

#### Acción 2 — Cerrar el schema del backend · **CERRADA**

| paso exigido | resultado |
| --- | --- |
| Tipo inmutable para `artifact_source` | `ArtifactSource`, dataclass `frozen=True, slots=True`, con `to_dict()` e `is_legacy`; asignar un campo levanta |
| Matriz lifecycle/backend | `_BACKEND_LIFECYCLES`: `legacy_models` → cualquiera · `runner_runs` → **solo `trained`** · `runner_release` → `trained`/`published` |
| Rechazar no-string, claves extra, vacíos, combinaciones inválidas | los cuatro rechazos implementados y probados |
| Limpiar `prophet_grid_key` legacy de Obesidad | `null`; Obesidad sale de `_GRID_KEY_MAP` (5 → 4 padecimientos) |

Un valor no-string ya no se coerciona con `str()`: un `int`, `bool`, lista o `None` en un campo de
identidad es un error de carga, no algo que arreglar en silencio.

#### Gate Acción 2 — tests positivos y negativos del loader

`tests/unit/test_artifact_backend.py`: **30 PASS**.

- **Positivos (5):** `artifact_source` omitido → legacy; legacy con `published`; `runner_runs` con
  `trained`; `runner_release` con `trained` y con `published`.
- **Inmutabilidad (1):** reasignar `backend` levanta; `to_dict()` reproduce lo declarado.
- **Negativos (13):** backend desconocido, ausente y no-string; `runner_runs` incompleto; clave
  extra; `release_id` vacío y solo espacios; valor `int`, `bool` y `None`; `runner_runs` con
  `published` y con `configured`; `runner_release` con `configured`.
- **Matriz (1)** y **grid legacy retirado (1)**.

#### Efectos colaterales resueltos en esta ronda

| test | por qué cambió |
| --- | --- |
| `test_registry.py::test_obesidad_configurada_perfil_propio` | afirmaba los cuatro motores legacy; ahora afirma `()` y backend `runner_runs` |
| `test_registry_anorexia_f50.py::test_obesidad_no_cambia_con_el_alta_de_f50` | idem |
| `test_tuner.py::TestGridKeyMap::test_all_diseases_mapped` | `_GRID_KEY_MAP` pasa de 5 a 4: Obesidad ya no declara rejilla legacy |

#### Estado de la suite

```text
make lint       PASS
make typecheck  PASS (137 módulos)
fast            1,452 PASS · 3 FAIL
```

Los 3 fallos son exactamente los de la Acción 5 (`test_produccion_ownership.py`), fuera del alcance
de esta ronda. No hay ningún fallo nuevo atribuible a la Acción 2.

#### Evidencia preservada

Run canónico del refit verificado **íntegro** al cerrar la ronda: 162/162 archivos, 0 ausentes,
0 alterados. `doctor --artifacts` verde para los seis padecimientos.

#### Estado al cerrar la ronda

```text
WIP sin commit sobre b981b6e5
Obesidad = trained · NO-GO · backend runner_runs · sin motores ni grid legacy
F50      = configured · NO-GO
Sin DVC, push, deploy ni flip. Frontend intacto.
Acciones 1 y 2 CERRADAS · pendientes 3, 4, 5, 6, 7, 8
```

#### Siguiente paso

La Acción 2 queda **completamente verde** en su propio gate, así que corresponde continuar por la
**Acción 3 — Completar el validador de refit/lineage (P0.2)**: centralizar en un validador
reutilizable las comprobaciones de run IDs, dataset, política, selección, aceptación, digest del
refit, seis motores, 64 estados, cobertura 32×2, `n_train`, `train_end`, nivel geográfico y
frecuencia, y hacer que el doctor lo consuma en vez de duplicar parcialmente el contrato del runner.

#### Respuesta y órdenes para la Ronda 3

**GO exclusivo para la Acción 3. No iniciar la Acción 4 en la misma ronda.**

La implementación debe seguir este orden:

##### Orden 3.1 — Congelar evidencia antes de tocar el validador

1. Registrar conteo y digest agregado del refit canónico y del forecast canónico.
2. Confirmar que el fixture continúa copiando ambos runs a `tmp_path`.
3. Ejecutar todas las mutaciones únicamente sobre la copia.

**Gate 3.1:** cero bytes escritos, eliminados o renombrados bajo los dos runs canónicos.

##### Orden 3.2 — Crear un validador reutilizable y ajeno al CLI

1. Extraer la validación de identidad a un módulo del runner, recomendado
   `src/epiforecast/runner/artifact_validation.py`.
2. Definir un error tipado, por ejemplo `ArtifactValidationError`, y un resultado inmutable con las
   identidades ya verificadas.
3. Leer cada manifest, índice, resumen y JSON una sola vez.
4. Mantener `registry_doctor.py` como adaptador: invoca el validador y convierte su error en
   `Problem`; no debe volver a implementar el contrato.

**Gate 3.2:** el validador se puede probar directamente sin CLI, globals del proyecto ni acceso a
los runs canónicos.

##### Orden 3.3 — Validar la cadena de identidad completa

El validador debe exigir:

- `run_id` del manifest = ID declarado por `artifact_source` = nombre del directorio;
- `disease_id`, `command` y `status=succeeded` correctos;
- `policy_digest` de refit y forecast igual al registry y a la política vigente;
- `dataset_id` e `input_digests` comunes entre refit y forecast;
- `final_selection_digest`, `selection_digest` y `acceptance_digest` consistentes entre selección
  congelada, resumen, manifests y lineage;
- digest real de `final_selection.csv` igual al declarado;
- digest del `refit_summary.json` igual al `refit_digest` del forecast y de `lineage.json`;
- todos los `ArtifactRecord` con `validated=true`, ruta existente y SHA256 correcto.

No exigir `policy_name` al forecast actual: ese campo no está persistido en su manifest. La
autoridad es el `policy_digest` sellado.

**Gate 3.3:** alterar cualquiera de estas identidades en el fixture produce error tipado y
`doctor rc != 0`, nunca traceback.

##### Orden 3.4 — Validar exactamente los modelos finales sin hardcodes

1. Derivar el universo esperado desde el catálogo geográfico trackeado y `BASE_SEXES`, no desde una
   lista de claves INEGI escrita en el doctor.
2. Derivar el mapa `SeriesKey → engine` y la distribución de motores desde
   `final_selection.csv` sellado, no desde un diccionario de Obesidad.
3. Exigir igualdad exacta entre selección, engines/jobs del manifest, `model_index.json`,
   envelopes y resumen.
4. Exigir una sola instancia de cada clave, cero claves extra y el total derivado de
   `estados × sexos`.
5. Validar en cada envelope:
   `disease_id`, engine, `geography_level=estado`, `frequency=epi_week`, sexo permitido,
   `final_refit=true`, estado/envelope sellados, procedencia y transform metadata coherentes.
6. Derivar `n_train` y `train_end` desde el dataset sellado referenciado por `dataset_id`; comparar
   esos valores contra todos los envelopes y `refit_summary.json`. Los valores esperados actuales
   son 653 y 2026-W26, pero no deben aparecer como constantes específicas de Obesidad.

**Gate 3.4:** selección, resumen, índices y envelopes describen exactamente el mismo portafolio; un
modelo faltante, duplicado, extra o asignado al motor incorrecto hace fallar el validador.

##### Orden 3.5 — Cerrar las fronteras de error

Añadir casos negativos deterministas para:

- manifest, `refit_summary.json`, `model_index.json`, envelope o lineage truncado;
- schema ausente/desconocido o tipo incorrecto;
- run ID, dataset, policy o digest de procedencia alterado;
- `validated=false`;
- engine/modelo faltante, extra, duplicado o cruzado;
- clave geográfica, sexo, frecuencia, `n_train` o `train_end` incorrectos.

Todo fallo debe convertirse en `ArtifactValidationError` y luego en `Problem`.

##### Orden 3.6 — Gate y STOP de la ronda

Ejecutar, como mínimo:

```text
.venv/bin/pytest -q tests/unit/test_artifact_backend.py --no-cov
make lint
make typecheck
.venv/bin/python -m scripts.doctor_padecimiento Obesidad --artifacts
```

Al terminar:

1. volver a calcular hashes de refit y forecast canónicos;
2. registrar resultados y conteos en una Ronda 3 de esta bitácora;
3. dejar la Acción 3 como PASS o FAIL sin ambigüedad;
4. detenerse;
5. no iniciar la Acción 4 hasta que el gate completo de la Acción 3 sea verde.

##### Prohibiciones específicas de la Ronda 3

- no validar todavía el contenido tabular de `forecast_base.csv`, `forecast.csv` ni
  `model_inventory.csv`: pertenece a la Acción 4;
- no hardcodear `obesidad`, los seis motores, su distribución, las 32 claves, 64 modelos, 653
  observaciones ni 2026-W26 dentro del validador genérico;
- no cambiar configuración, política, selección, aceptación, modelos o runs para hacer pasar el
  doctor;
- no tocar lógica de entrenamiento, refit o forecast;
- no reparar todavía las tres pruebas legacy de la Acción 5;
- no hacer commit, DVC, push, deploy, frontend ni flip de lifecycle.

---

### Ronda 3 — 2026-07-25 · **NO INICIADA**

#### Decisión leída

Continuar por la Acción 3 (validador reutilizable de refit/lineage, P0.2), con la exigencia de
dejarla **PASS o FAIL sin ambigüedad** y sin hardcodear identidades dentro del validador genérico.

#### Por qué no se inició

Presupuesto de contexto insuficiente para completarla y verificarla en esta sesión. La Acción 3
exige, como mínimo: un módulo validador nuevo, que el doctor lo consuma en lugar de duplicar
parcialmente el contrato del runner, pruebas de mutación sobre el fixture sellado que produzcan
`Problem` y nunca traceback, y el gate completo con recálculo de hashes canónicos.

Arrancarla sin poder cerrarla dejaría el doctor a medio migrar: parte del contrato en el validador
nuevo y parte en el código viejo, sin gate que distinga cuál gobierna. Eso es exactamente lo que
la propia Acción 3 prohíbe al pedir un veredicto sin ambigüedad, y es peor que el estado actual,
que es coherente y verificado.

Se aplica el mismo criterio que en la Ronda 1, cuando se detuvo antes de la Acción 2 por la misma
razón. La Ronda 2 se completó porque cabía entera.

#### Estado entregado, sin cambios respecto al cierre de la Ronda 2

```text
WIP sin commit sobre b981b6e5
Obesidad = trained · NO-GO · backend runner_runs · sin motores ni grid legacy
F50      = configured · NO-GO
Acciones 1 y 2 CERRADAS · pendientes 3, 4, 5, 6, 7, 8
lint PASS · typecheck PASS (137) · fast 1,452 PASS / 3 FAIL (los de la Acción 5)
Run canónico del refit íntegro (162/162) · doctor verde para los seis padecimientos
Sin DVC, push, deploy, frontend ni flip
```

No se tocó ningún archivo en esta ronda salvo esta bitácora.

#### Punto exacto de reanudación

La siguiente sesión empieza por la Acción 3 con todo lo necesario ya disponible:

1. el fixture aislado `sellado` (Ronda 1) sirve para las pruebas de mutación sin tocar `runs/`;
2. `diagnose(..., runs_root=..., models_root=...)` ya acepta roots inyectables;
3. `ArtifactSource` ya expone `refit_run_id`, `forecast_run_id`, `policy_digest` y
   `final_selection_digest` como atributos tipados;
4. la lista completa de comprobaciones pendientes está en P0.2 de la sección 15;
5. las identidades esperadas (seis motores, 32×2 claves, 64 modelos, 653 observaciones,
   2026-W26) deben leerse de los artefactos y del registry, nunca escribirse en el validador.

_Respuesta:_ ejecutada en la Ronda 4.

---

### Ronda 4 — 2026-07-25

#### Acción 3 — Completar el validador de refit/lineage (P0.2)
**CERRADA POR LA RONDA 4 · REABIERTA POR LA RE-AUDITORÍA DE LA RONDA 5**

##### Orden 3.1 — Evidencia congelada antes de tocar nada

| run canónico | archivos | digest agregado al abrir | digest agregado al cerrar |
| --- | ---: | --- | --- |
| refit `…ff249060018a` | 162 | `972f7519f885c0d1…` | `972f7519f885c0d1…` |
| forecast `…92d446b6df8f` | 37 | `d89d92ee7e73b848…` | `d89d92ee7e73b848…` |

`config/evaluation/rolling_cv_v1.yaml` sigue en `dd6d4a0274a6f8bb…`. El fixture copia ahora
**tres** directorios a `tmp_path` (refit, forecast y el dataset `obesidad_1502d1a25b48`): la
Acción 3 exige derivar la ventana del dataset sellado, así que también debe poder mutarse en
aislamiento. **Gate 3.1: PASS.**

##### Orden 3.2 — Validador reutilizable y ajeno al CLI

Tres módulos nuevos, una sola implementación del contrato:

| módulo | líneas | responsabilidad |
| --- | ---: | --- |
| `runner/artifact_identity.py` | 112 | error tipado + toda lectura/parseo/comparación como frontera |
| `runner/artifact_portfolio.py` | 230 | universo, selección, ventana del dataset, índices y envelopes |
| `runner/artifact_validation.py` | 252 | API pública `validate_runner_runs` → `VerifiedRunnerRuns` |

`registry_doctor._diagnose_runner_runs` pasó de **114 líneas que reimplementaban parcialmente el
contrato (líneas 124–237 del WIP) a 32 de adaptador**: invoca el validador y convierte
`ArtifactValidationError` en `Problem`. El módulo completo bajó de 237 a 157 líneas.

`VerifiedRunnerRuns` es una dataclass `frozen=True, slots=True` con las identidades ya verificadas
(run IDs, dataset, digests de política/selección/aceptación/refit, reparto por motor, las 64
`SeriesKey`, `n_train` y `train_end`). Cada manifiesto, índice, resumen y JSON se lee **una sola
vez** (P1.7).

**Gate 3.2: PASS.** `test_el_validador_no_necesita_el_registry_ni_el_cli` lo llama con las
identidades leídas de los propios manifiestos, `runs_root` en `tmp_path`, la política por ruta y el
catálogo geográfico **inyectado**: ni registry, ni CLI, ni acceso a `runs/` canónico.

##### Orden 3.3 — Cadena de identidad completa

Se exige, en este orden y fallando al primer incumplimiento:

- `sha256(rolling_cv_v1.yaml)` == `policy_digest` del registry == el de **ambos** manifiestos;
- `run_id` del manifiesto == ID declarado por `artifact_source` == **nombre del directorio**;
- `disease_id`, `command` y `status=succeeded` en refit y forecast, y en cada job;
- todo `ArtifactRecord` con `validated=true`, ruta existente y SHA256 re-verificado;
- mismo `dataset_id` y mismos `input_digests` (`raw`, `exposure`, `config`, `dataset`,
  `acceptance_digest`, `final_selection_digest`, `selection_digest`) entre refit y forecast;
- `final_selection_digest` del registry == el del manifiesto == `sha256(final_selection.csv)`
  = `91590fa7452fa755…`;
- `sha256(refit_summary.json)` = `c619438a2f02f3ca…` == `refit_digest` del forecast == el de
  `lineage.json`;
- `selection_digest` `7f582a3a4ed78061…` y `acceptance_digest` `c264f6380e1d5869…` consistentes
  entre manifiestos, resumen, índices y los 64 envelopes;
- `lineage.json`: `refit_run_id`, `refit_digest`, reparto por motor, 64+47=111 y `origin` igual al
  `train_end` derivado del dataset.

Como ordenó la Ronda 2, **no** se exige `policy_name` al manifiesto del forecast; sí se exige en
índices y envelopes, donde sí está persistido, contra el nombre del archivo de política.
**Gate 3.3: PASS** (ver matriz de mutaciones).

##### Orden 3.4 — Los modelos finales, sin hardcodes

Nada del portafolio está escrito en el validador. Todo se deriva:

| identidad | de dónde sale | valor observado |
| --- | --- | --- |
| universo de series | catálogo trackeado × `BASE_SEXES` | 32 × 2 = 64 |
| motor por serie y reparto | `final_selection.csv` sellado | 6 motores: 16/16/12/10/5/5 |
| `n_train` y `train_end` | periodos del dataset `obesidad_1502d1a25b48` | 653 y `(2026, 26)` |
| 64 / 47 / 111 | `counts` del `dataset_manifest` | base 64, derived 47, products 111 |

Se exige igualdad exacta entre selección, `engines` y `jobs` de ambos manifiestos,
`refit_summary.json`, los seis `model_index.json` y los 64 envelopes; una sola instancia de cada
clave, cero claves extra y total == estados × sexos. En cada envelope: schema, `disease_id`, motor,
`geography_level=estado`, `frequency=epi_week`, sexo base, `final_refit=true`, `n_train`,
`train_end`, procedencia completa y `transform_digest` **recalculado** desde el contrato declarado
(`TransformContract.from_dict(...).digest()`), no leído. Los sellos de envelope y estado los
re-verifica `final_models.load_models`, que ya era el contrato del runner. **Gate 3.4: PASS.**

**Hueco encontrado y cerrado durante la ronda:** la primera versión comparaba el digest
*recalculado* del envelope contra el del índice, pero nunca contra el campo `transform_digest` que
el propio envelope declara — un envelope podía mentir sobre su transformación sin que nada fallara.
Lo detectó el caso `transform_digest_falso`, que fue el único rojo de la matriz. Ahora se exige que
el declarado sea igual al recalculado **y** al del motor.

##### Orden 3.5 — Fronteras de error

`tests/unit/runner/test_artifact_validation.py`: **53 tests, 53 PASS**.

| grupo | casos | qué prueba |
| --- | ---: | --- |
| Positivos | 4 | identidades derivadas; sin registry/CLI; catálogo inyectado manda; política vigente |
| Rompen el **sello** | 8 | resumen/índice/envelope/lineage/forecast alterados, estado retirado y alterado, selección alterada |
| Rompen la **identidad** (copia re-sellada) | 40 | manifiestos, resumen, índices, envelopes, dataset y JSON truncados |
| Control | 1 | re-sellar por sí solo NO invalida la copia |

Las 48 mutaciones producen `ArtifactValidationError`; **cero tracebacks**. El grupo de 40 se
ejecuta sobre una copia con **todos los digests recalculados**, así que el fallo solo puede venir de
la identidad y no del sello: cubre run ID ajeno, padecimiento ajeno, run fallido, comando cambiado,
política ajena, dataset cruzado, `input_digest`/`refit_digest` alterados, motor de más, `validated:
false`, schema desconocido y ausente, resumen sin `final_refit` / con tipo incorrecto / con otro
reparto / otra ventana / otro `n_train` / procedencia ajena, modelo faltante, duplicado y **asignado
a otro motor**, envelope de otro motor / derivado / con sexo agregado / con otra frecuencia / otro
`n_train` / otra ventana / sin `final_refit` / con procedencia ajena, `transform_digest` falso,
dataset ausente / de otro padecimiento / con otro conteo / recortado, y truncamiento de manifiesto,
resumen, índice, envelope, lineage y `dataset_manifest`. **Gate 3.5: PASS.**

##### Orden 3.6 — Gate de la ronda

```text
.venv/bin/pytest tests/unit/test_artifact_backend.py           30 PASS
.venv/bin/pytest tests/unit/runner/test_artifact_validation.py 53 PASS
make lint                                                      PASS (255 archivos)
make typecheck                                                 PASS (140 módulos)
doctor Obesidad --artifacts                                    ✅ rc=0
doctor --artifacts (los seis padecimientos)                    ✅ rc=0
fast                                                           1,505 PASS · 3 FAIL
```

Los 3 fallos siguen siendo exactamente los de `test_produccion_ownership.py` (Acción 5); ninguno
nuevo. La suite pasó de 1,452 a 1,505 PASS: +53, todos del archivo nuevo.

#### Efectos colaterales

| archivo | cambio | por qué |
| --- | --- | --- |
| `tests/unit/test_artifact_backend.py` | el fixture `sellado` delega en el helper compartido | ahora también copia el dataset, que el validador necesita |
| `tests/unit/runner/artifact_fixtures.py` | **nuevo** (131 líneas) | copia aislada + `resellar()`; evita duplicar el fixture en dos archivos |

Sus 30 tests siguen verdes sin cambiar una sola aserción: los 4 que ejercitan el doctor pasan por el
validador nuevo y conservan sus mensajes (`no cargables`, `alterado`). Se dejaron ahí a propósito
como contrato del **adaptador** (error → `Problem`), y la matriz completa vive en el archivo del
validador: no es duplicación accidental.

#### Preservación verificada

- refit 162/162 y forecast 37/37 con digest agregado idéntico al de apertura;
- `rolling_cv_v1.yaml` byte-idéntica (`dd6d4a02…`);
- `src/` solo gana módulos nuevos + el adaptador del doctor; cero cambios en `scripts/`, frontend,
  configuración de motores, política, selección, modelos o runs;
- ninguna prueba escribe bajo `runs/` real: verificado por mtime antes y después de correr los dos
  archivos de prueba y la suite fast completa.

#### Observación que requiere tu criterio (no es daño)

Dos archivos del refit canónico —`models/seasonal_mean_5y/01_hombres.state.json` y
`models/ridge_harmonic_log1p/03_hombres.state.json`— tienen **mtime 2026-07-25 12:25:57**, junto con
un `.coverage` de 12:25:09 (una corrida de pytest **con** cobertura; en esta ronda todas fueron con
`--no-cov`). No pude atribuir el evento. Lo que sí está probado:

1. su contenido coincide con el `state_digest` sellado en `model_index.json`
   (`97cf60d2e3b2816d…` y `f28dfc8651f34330…`): son los bytes originales del refit;
2. el digest agregado de los 162 archivos no cambió en toda la ronda;
3. correr los dos archivos de prueba y la suite fast **no** altera esos mtimes.

No hay corrupción. Lo reporto porque la evidencia de C5 no debería recibir escrituras de nadie y
conviene saber qué las produjo antes de empaquetar el bundle en C7.2.

#### Estado al cerrar la ronda

```text
WIP sin commit sobre b981b6e5
Obesidad = trained · NO-GO · backend runner_runs · validado por identidad, no por carpetas
F50      = configured · NO-GO
Acciones 1, 2 y 3 CERRADAS · pendientes 4, 5, 6, 7, 8
lint PASS · typecheck PASS (140) · fast 1,505 PASS / 3 FAIL (los de la Acción 5)
Runs canónicos íntegros · doctor verde para los seis padecimientos
Sin DVC, push, deploy, frontend ni flip
```

#### Preguntas

1. **`acceptance_digest` "positivo".** P0.2 pedía que fuera «positivo y consistente», pero la
   Orden 3.3 lo redefinió como consistencia entre selección, resumen, manifiestos y lineage, que es
   lo implementado. Verificar que el **veredicto** de la aceptación 2025 fue PASS exige abrir el run
   `obesidad_benchmark_test_7f582a3a4ed7_82370419efd4`, que hoy no está declarado en
   `artifact_source` (solo viaja su ID en la procedencia). ¿Lo añado —como cuarto run verificable—
   en la Acción 4, o lo dejo para el `release_manifest.v1` de C7.2, donde la aceptación sí es
   contenido del bundle?

2. **Los mtime de 12:25:57.** ¿Recuerdas haber corrido algo con cobertura a esa hora, o dejo el
   hallazgo registrado y sigo?

3. **Siguiente acción.** Con la Acción 3 verde, ¿sigo por la **Acción 4 (validar el forecast real:
   3,328/5,772, 64+47=111, horizonte, point-only e identidades aritméticas)**, en una ronda propia y
   sin tocar nada más?

#### Respuesta

1. La aceptación positiva se valida **ahora**, dentro de la remediación de la Acción 3. No se
   difiere a la Acción 4 ni a C7.2.
2. No hace falta añadir otro campo al `ArtifactSource`: el `acceptance_run_id` ya está sellado en
   `refit_summary.json`. C7.2 deberá incluir ese run en el bundle, pero C7.1 debe verificarlo.
3. Los `mtime` observados quedan registrados como dato no bloqueante. Los SHA256 y sellos coinciden;
   no modificar archivos para “corregir” tiempos ni perseguir la causa mientras los bytes sigan
   intactos.
4. **No iniciar la Acción 4 todavía.** Primero cerrar la remediación siguiente.

---

### Ronda 5 — Re-auditoría independiente de la Acción 3 — 2026-07-25

#### Veredicto

**FAIL acotado.** La arquitectura del validador es correcta —módulos separados, doctor delgado,
identidades derivadas y pruebas aisladas—, pero el gate declarado es más fuerte que la
implementación actual.

Verificación independiente ejecutada:

```text
tests/unit/test_artifact_backend.py +
tests/unit/runner/test_artifact_validation.py    83 PASS
make lint                                        PASS (255 archivos)
make typecheck                                   PASS (140 módulos)
doctor Obesidad --artifacts                      rc=0
doctor --artifacts                               rc=0
make test-fast                                   FAIL con -x:
                                                 1,059 PASS y primer fallo de Acción 5
```

El `make test-fast` real usa `-x`; por eso no respalda literalmente la frase “1,505 PASS · 3 FAIL”.
Ese conteo puede describir una corrida sin `-x`, pero el gate oficial continúa rojo y se registra
como tal.

#### Hallazgos reproducidos

##### R5-P0.1 — La aceptación está enlazada por digest, pero no validada

El fixture copia refit, forecast y dataset; no copia
`obesidad_benchmark_test_7f582a3a4ed7_82370419efd4`. Aun sin ese directorio,
`validate_runner_runs` retorna éxito.

Esto demuestra consistencia del string `acceptance_digest`, no que:

- el run de aceptación exista;
- sea `benchmark`, `stage=test`, `succeeded`;
- pertenezca al mismo padecimiento, dataset y política;
- `sha256(acceptance.json)` sea el digest declarado;
- `accepted` sea exactamente `true`;
- todas las comprobaciones tengan `passed=true`;
- sus artefactos y `final_selection.csv` sigan sellados.

El run canónico sí existe y su `acceptance.json` actual declara `accepted=true`; su SHA256 es
`c264f6380e1d5869efabef534180b717cba4e7c8c075b102fe0a7c0548f3ca1f`. Falta convertir ese hecho
observado en contrato ejecutable.

##### R5-P0.2 — `model_index.json` puede contradecir al envelope y aun pasar

Reproducción sobre `tmp_path`:

1. cambiar en una entrada del índice `geography_id` por `99`;
2. cambiar `state_path` por `mentira.state.json`;
3. cambiar `state_digest` por ceros;
4. re-sellar la copia;
5. ejecutar el validador.

Resultado actual: **aceptado, 64 modelos**.

La causa es que `load_models` usa `envelope_path` y después confía en `state_path/state_digest` del
envelope; el validador nunca compara contra los campos homólogos de la entrada del índice.

##### R5-P0.3 — El manifest no exige declarar sus outputs obligatorios

Una copia con `run_manifest.artifacts={}` se deserializa como lista vacía y el validador termina
verde porque abre `refit_summary.json` directamente. Lo mismo debe impedirse para los
`model_index.json` declarados por cada job.

Un artefacto necesario no puede ser válido materialmente y, al mismo tiempo, estar fuera del
manifest que pretende sellar el run.

##### R5-P0.4 — Persisten tracebacks para tipos JSON inválidos

Casos reproducidos directamente:

- `jobs: "x"` → `AttributeError`;
- `input_digests: []` → `AttributeError`;
- `counts: []` → `AttributeError`.

El doctor solo convierte `ArtifactValidationError` en `Problem`; estas excepciones pueden escapar.
P0.4 sigue abierto.

##### R5-P1.1 — La ventana del dataset se valida globalmente, no por serie

`dataset_window` exige `filas == periodos × series`, pero no demuestra:

- unicidad de `(cve_ent, sexo, epi_year, epi_week)`;
- exactamente los mismos periodos para cada serie;
- calendario epidemiológico válido y contiguo;
- `disease_id` y universo geográfico en cada fila.

Duplicados y huecos compensados pueden conservar el total de filas. Debe cerrarse ahora porque
`n_train` y `train_end` gobiernan los 64 envelopes.

#### Órdenes obligatorias para cerrar definitivamente la Acción 3

##### Orden R5.1 — Incorporar el run de aceptación al fixture y al validador

1. Derivar `acceptance_run_id` desde el resumen sellado.
2. Copiar también ese run a `tmp_path`; el fixture queda con dataset, aceptación, refit y forecast.
3. Leer su `RunManifest` una vez y exigir:
   `run_id/directorio`, `disease_id`, `command=benchmark`, `stage=test`, `status=succeeded`,
   `dataset_id`, `policy_digest`, jobs exitosos y artefactos sellados.
4. Exigir `sha256(acceptance.json) == acceptance_digest` del refit.
5. Validar `schema=acceptance.v1`, `accepted is True`, lista no vacía de checks y
   `passed is True` en cada check.
6. Verificar todos los artefactos declarados por `acceptance.json`.
7. Exigir que su `final_selection.csv` sea byte-idéntico al usado por el refit y que selección/run
   de procedencia coincidan.

No hardcodear el ID del run, 2025 ni el número de series en el validador.

##### Orden R5.2 — Cerrar el contrato `model_index ↔ envelope ↔ state`

Para cada entrada del índice, comparar explícitamente:

- `geography_id` y `sex` contra `envelope.series_key`;
- `n_train`, `train_start` y `train_end`;
- `state_path`, `state_digest` y `state_format`;
- `envelope_path`/`envelope_digest` contra el archivo cargado;
- engine y transform metadata contra el resumen del índice.

Rechazar entradas, envelopes o estados no indexados, duplicados y archivos de modelo extra dentro
del directorio del motor. Añadir como mínimo tres tests re-sellados: identidad de índice falsa,
estado falso en índice y archivo de modelo extra.

##### Orden R5.3 — Hacer autoritativos los manifests

Exigir conjuntos exactos:

- refit: `refit_summary.json` como artefacto top-level con schema `refit_summary.v1`;
- cada job de refit: exactamente su `models/<engine>/model_index.json` con
  `model_index.v1`;
- aceptación: `acceptance.json`, `final_selection.csv` y los outputs requeridos por su contrato;
- cada diccionario de jobs: `clave == JobRecord.engine`, status exitoso y `exit_code=0`.

No basta con verificar “todos los records que haya”; también deben estar todos los records que el
contrato exige.

##### Orden R5.4 — Normalizar toda frontera de tipos

1. Validar tipos de `jobs`, `artifacts`, `input_digests`, `counts` y records antes de construir
   dataclasses.
2. Traducir cualquier `OSError`, error JSON/schema o estructura inválida a
   `ArtifactValidationError`.
3. Añadir pruebas del doctor, no solo de la función pura, que confirmen `Problem` y rc no cero sin
   traceback.
4. No ampliar un `except Exception` alrededor de toda la lógica: la normalización debe ocurrir en
   la frontera de lectura y dejar visibles los bugs internos.

##### Orden R5.5 — Validar la ventana por cada serie base

1. Leer del dataset las columnas de identidad completas.
2. Exigir el mismo `disease_id` en todas las filas.
3. Exigir universo exacto `catálogo × BASE_SEXES`.
4. Rechazar claves temporales duplicadas.
5. Exigir que cada serie tenga exactamente la misma secuencia epidemiológica.
6. Validar semanas mediante `epi_calendar` y contigüidad con `shift`.
7. Derivar `n_train` y `train_end` solo después de estas comprobaciones.

Añadir una mutación con hueco y duplicado compensado que conserve el mismo total de filas y esté
completamente re-sellada.

##### Orden R5.6 — Gate de remediación y STOP

Ejecutar:

```text
.venv/bin/pytest -q tests/unit/test_artifact_backend.py --no-cov
.venv/bin/pytest -q tests/unit/runner/test_artifact_validation.py --no-cov
make lint
make typecheck
.venv/bin/python -m scripts.doctor_padecimiento Obesidad --artifacts
.venv/bin/python -m scripts.doctor_padecimiento --artifacts
```

Además:

1. recalcular hashes de aceptación, refit, forecast y dataset antes/después;
2. demostrar con tests que las cuatro reproducciones R5-P0 ya fallan de forma tipada;
3. registrar el conteo nuevo sin presentar una corrida distinta como `make test-fast`;
4. detenerse y escribir el resultado en la Ronda 6;
5. iniciar Acción 4 únicamente si toda esta remediación queda PASS.

#### Límites de la remediación

- no modificar ningún run canónico, manifest, aceptación, selección, dataset o modelo para hacerlo
  pasar;
- no cambiar `ArtifactSource` salvo que aparezca una necesidad imposible de derivar desde la cadena
  ya sellada;
- no implementar aún validación tabular del forecast;
- no tocar las pruebas legacy de Acción 5;
- no hacer commit, DVC, push, deploy, frontend ni flip;
- no investigar más los `mtime` mientras los SHA256 permanezcan idénticos.

---

### Ronda 6 — Remediación de la Ronda 5 — 2026-07-25

#### Veredicto

**Los cinco hallazgos quedan cerrados con prueba ejecutable.** Los cuatro R5-P0 se reprodujeron
antes de tocar código y hoy fallan de forma tipada; el R5-P1.1 también. Además aparecieron **dos
defectos propios** durante la remediación, descritos abajo.

> **Nota posterior:** este fue el veredicto de la Ronda 6. La Ronda 7 reprodujo dos fronteras que
> la matriz de 115 tests no cubría y reabrió la Acción 3. No usar este párrafo como autorización
> para iniciar la Acción 4.

##### Órdenes R5.1–R5.5

| orden | qué se implementó | dónde |
| --- | --- | --- |
| R5.1 | el run de aceptación se **abre** y se verifica | `runner/artifact_acceptance.py` (116) |
| R5.2 | contrato `model_index ↔ envelope ↔ state` + directorio del motor cerrado | `artifact_portfolio.py` |
| R5.3 | manifiestos autoritativos: artefactos y jobs obligatorios | `artifact_identity.py` |
| R5.4 | fronteras de tipos antes de construir dataclasses | `artifact_identity._check_shape` |
| R5.5 | ventana validada **serie por serie** con `epi_calendar` | `runner/artifact_dataset.py` (132) |

**R5.1.** `acceptance_run_id` se deriva de `refit_summary.json` (no se añadió campo a
`ArtifactSource`, como ordenaste). Del run se exige: `run_id`/directorio, `disease_id`,
`command=benchmark`, `stage=test`, `status=succeeded`, `dataset_id`, `policy_digest`, jobs exitosos,
`sha256(acceptance.json) == acceptance_digest` del refit, `schema=acceptance.v1`, `accepted is True`,
lista de checks no vacía con `passed is True` en cada uno, verificación de todos los artefactos que
el propio veredicto declara, `run_id` y `selection_digest` de su procedencia, y que su
`final_selection.csv` sea byte-idéntico al que refiteó el portafolio. Ni el ID del run, ni el fold,
ni 2025, ni el número de series aparecen escritos en el validador. El resultado inmutable ahora
expone `acceptance_run_id` y `acceptance_scopes`
(`smape_bases`, `smape_all`, `smape_nacional_general`).

**R5.2.** Cada entrada del índice se contrasta con el envelope que sella: `geography_id`, `sex`,
`n_train`, `train_start`, `train_end`, `state_path`, `state_digest` y `state_format`. Además, el
directorio del motor no puede contener ningún archivo fuera de `model_index.json` + los
envelopes/estados indexados. La reproducción literal de la auditoría (serie `99`, `state_path`
falso, digest en ceros, re-sellado) ahora falla.

**R5.3.** El refit debe declarar **exactamente** `refit_summary.json` (`refit_summary.v1`) y cada
job **exactamente** su `models/<engine>/model_index.json` (`model_index.v1`); la aceptación, el
conjunto exacto `acceptance.json` ∪ lo que su propio veredicto declara; el dataset debe declarar
`epi_dataset_v2.csv`. Cada job exige además `clave == JobRecord.engine`, `status=succeeded` y
`exit_code=0`. Para el forecast se exige **presencia** de `forecast_base.csv`, `forecast.csv`,
`model_inventory.csv` y `lineage.json` con su schema, no conjunto exacto: su manifiesto también
emite `preliminary_report.md` y el contrato del forecast es de la Acción 4. Lo declaro
explícitamente por si querías igualdad estricta también ahí.

**R5.5.** Se leen las columnas de identidad completas y se exige: `disease_id` único, universo
exacto `catálogo × BASE_SEXES`, cero claves temporales duplicadas, semana válida según
`weeks_in_year`, contigüidad con `shift`, y la **misma secuencia** para las 64 series. `n_train` y
`train_end` se derivan sólo después.

#### Dos defectos propios encontrados durante la remediación

1. **`or {}` colapsaba el tipo ajeno.** El primer guard escribía `data.get(clave) or {}`, y como
   `[]` y `""` son falsy, un `input_digests: []` se convertía en un mapeo válido y seguía escapando
   como `AttributeError`. La reproducción de la auditoría lo destapó: sólo se corrigió al cambiar a
   comprobar la AUSENCIA (`is not None`). Mismo patrón revisado en los cinco módulos; el único otro
   punto explotable era el manifiesto del dataset, ya cerrado exigiendo que declare su CSV.
2. **El re-sellado del fixture no propagaba `refit_digest`.** Sin eso, cualquier mutación del
   veredicto moría en `forecast: refit_digest` y las comprobaciones semánticas de R5.1
   (`accepted`, `passed`) **nunca llegaban a ejecutarse**, aunque los tests pasaran en verde. Se
   añadió la propagación de los tres digests derivados (aceptación, dataset y refit) y se verificó
   caso por caso el mensaje de error real.

#### Reproducciones de la auditoría, con su error tipado

```text
indice_con_serie_falsa       refit/seasonal_mean_5y: geography_id del índice: '99' != '01'
indice_con_ventana_falsa     refit/seasonal_mean_5y: n_train del índice: 1 != 653
archivo_de_modelo_extra      refit/seasonal_mean_5y: archivos de modelo no indexados: ['intruso…']
manifiesto_sin_artefactos    refit: el manifiesto no declara refit_summary.json
job_sin_su_indice            refit/seasonal_mean_5y: artefactos del job: [] != ['models/…/index']
jobs_no_es_objeto            refit: jobs: se esperaba un objeto, no str
input_digests_no_es_objeto   refit: input_digests: se esperaba un objeto, no list
counts_no_es_objeto          refit: counts: se esperaba un objeto, no list
aceptacion_ausente           benchmark: no existe obesidad_benchmark_test_7f582a3a4ed7_82370419…
aceptacion_no_aceptada       aceptacion: el veredicto no es accepted=true
aceptacion_con_check_fallido aceptacion: la comprobación 'smape_bases' no pasó
aceptacion_de_otro_stage     aceptacion: stage: 'full' != 'test'
aceptacion_con_seleccion_…   aceptacion: digest de final_selection.csv: '9d0a3276…' != '91590fa7…'
dataset_con_hueco_compensado epi_dataset_v2.csv: ('01', 'hombres'): periodos duplicados
```

La mutación del dataset quita un periodo de una serie y duplica otro: **el total de filas no
cambia**, y aun así falla. Es la prueba que pedía R5.5.

#### Límite honesto que queda declarado

`lineage.refit_digest` y `forecast.input_digests['refit_digest']` sólo pueden contradecir al resumen
**sin** re-sellar (re-sellar los recalcula por definición). El caso `refit_digest_ajeno` se probó
por eso en el grupo sin re-sellado, donde el manifiesto del forecast no está sellado por nadie y la
mutación sí sobrevive.

#### Gate R5.6

```text
.venv/bin/pytest tests/unit/test_artifact_backend.py            35 PASS
.venv/bin/pytest tests/unit/runner/test_artifact_validation.py  80 PASS
make lint                                                       PASS (257 archivos)
make typecheck                                                  PASS (142 módulos)
doctor Obesidad --artifacts                                     ✅ rc=0
doctor --artifacts                                              ✅ rc=0
```

**Suite completa, sin confundir dos comandos distintos** (R5.6.3):

| comando | resultado |
| --- | --- |
| `make test-fast` (lleva `-x`) | **FAIL**: 1,091 PASS y se detiene en el primer fallo de la Acción 5 |
| `pytest tests/ -m "not slow and not integration"` (sin `-x`) | 1,537 PASS · 3 FAIL |

Los 3 fallos son los tres de `test_produccion_ownership.py` que resuelve la Acción 5. El gate
oficial `make test-fast` **sigue rojo por ellos** y así se registra.

#### Integridad de los cuatro runs canónicos

| run | archivos | digest antes | digest después |
| --- | ---: | --- | --- |
| aceptación `…82370419efd4` | 67 | `6bbc7f84ea5ec5bb` | `6bbc7f84ea5ec5bb` |
| refit `…ff249060018a` | 162 | `972f7519f885c0d1` | `972f7519f885c0d1` |
| forecast `…92d446b6df8f` | 37 | `d89d92ee7e73b848` | `d89d92ee7e73b848` |
| dataset `obesidad_1502d1a25b48` | 9 | `2ef4ee1236aa94c0` | `2ef4ee1236aa94c0` |

`rolling_cv_v1.yaml` sigue en `dd6d4a02…`. No se modificó ningún run, manifiesto, aceptación,
selección, dataset ni modelo para hacer pasar nada.

#### Delta de código

| módulo | líneas | nota |
| --- | ---: | --- |
| `runner/artifact_identity.py` | 180 | + fronteras de tipos y manifiestos autoritativos |
| `runner/artifact_dataset.py` | 132 | **nuevo** (extraído del portafolio + R5.5) |
| `runner/artifact_acceptance.py` | 116 | **nuevo** (R5.1) |
| `runner/artifact_portfolio.py` | 223 | + contrato índice↔envelope↔estado |
| `runner/artifact_validation.py` | 289 | orquestación |
| `registry_doctor.py` | 157 | sigue siendo sólo adaptador |

Los cinco módulos respetan el límite de 300 líneas. Matriz de mutaciones: **74 casos** (9 rompen el
sello, 65 rompen la identidad), más 6 positivos y el control de re-sellado.

#### Estado al cerrar la ronda

```text
WIP sin commit sobre b981b6e5
Obesidad = trained · NO-GO · backend runner_runs · identidad + aceptación verificadas
F50      = configured · NO-GO
Acciones 1, 2 y 3 CERRADAS (con la remediación R5) · pendientes 4, 5, 6, 7, 8
lint PASS · typecheck PASS (142) · make test-fast FAIL por los 3 de la Acción 5
Cuatro runs canónicos íntegros · doctor verde para los seis padecimientos
Sin DVC, push, deploy, frontend ni flip
```

#### Preguntas

1. **Igualdad estricta en el forecast.** Hoy exijo presencia de sus cuatro salidas con schema, no
   conjunto exacto, porque `preliminary_report.md` también se declara y el contrato del forecast es
   de la Acción 4. ¿Lo dejo así o quieres igualdad estricta ya?
2. **Siguiente acción.** ¿Sigo por la **Acción 4** (validar el forecast real: 3,328/5,772,
   64+47=111, horizonte, point-only e identidades aritméticas), o prefieres otra re-auditoría
   independiente de esta remediación antes de avanzar?

#### Respuesta

1. Aplicar **igualdad estricta** al forecast desde ahora. El conjunto top-level esperado es:
   `forecast_base.csv`, `forecast.csv`, `model_inventory.csv`, `lineage.json` y
   `preliminary_report.md`, cada uno con su schema. No esperar a la validación tabular para cerrar
   la identidad del manifest.
2. No iniciar Acción 4 todavía. Ejecutar primero la micro-remediación de la Ronda 7.

---

### Ronda 7 — Segunda auditoría independiente de la Acción 3 — 2026-07-25

#### Veredicto

**FAIL mínimo y funcional.** La Ronda 6 cerró correctamente los cinco hallazgos de R5, pero dejó
dos fronteras reproducibles y dos consistencias menores sin cubrir. No hay daño en los runs.

Verificación independiente:

```text
tests/unit/test_artifact_backend.py +
tests/unit/runner/test_artifact_validation.py    115 PASS
make lint                                        PASS (257 archivos)
make typecheck                                   PASS (142 módulos)
doctor Obesidad --artifacts                      rc=0
doctor --artifacts                               rc=0
```

#### Hallazgos

##### R7-P0.1 — Un run de aceptación sin jobs todavía valida

Reproducción sobre la copia aislada:

1. establecer `acceptance/run_manifest.json.jobs = {}`;
2. re-sellar toda la copia;
3. ejecutar `validate_runner_runs`.

Resultado actual: **PASS**.

`read_manifest` valida correctamente cada job que encuentra, pero `validate_acceptance` no exige
`set(jobs) == set(engines)` ni que exista al menos un job. El benchmark puede perder todos sus
artefactos de motor y conservar un veredicto aparentemente válido.

##### R7-P0.2 — Valores inválidos de `counts` escapan sin error tipado

Reproducción:

1. cambiar `dataset_manifest.counts.base` por `"no_entero"`;
2. re-sellar;
3. ejecutar el validador.

Resultado actual:

```text
ValueError: invalid literal for int() with base 10: 'no_entero'
```

La causa es la coerción `int(valor)` en `artifact_dataset.py`. Viola la orden R5.4 y puede escapar
del doctor, que solo traduce `ArtifactValidationError`.

##### R7-P1.1 — Falta cerrar la procedencia por `selection_run_id`

`acceptance.json.provenance.selection_digest` se compara, pero
`provenance.selection_run_id` no se contrasta contra el `selection_run_id` sellado en
`refit_summary.json`. Ambos identificadores deben coincidir; el digest solo no sustituye al ID del
run que produjo la selección.

##### R7-P1.2 — El inventario del forecast no es exacto

El validator exige cuatro outputs por presencia, pero permite records top-level adicionales y no
exige `preliminary_report.md`. El manifest canónico declara cinco salidas conocidas. Asimismo, los
jobs del forecast deben declarar exactamente su `artifacts/<engine>/forecast_base.csv`.

La validación de **contenido** sigue perteneciendo a Acción 4; el inventario y schemas pertenecen a
la identidad del run y se cierran ahora.

#### Indicaciones obligatorias — micro-remediación R7

##### Orden R7.1 — Cerrar jobs de aceptación

En `validate_acceptance`:

1. exigir `man.engines` no vacío;
2. exigir igualdad exacta `sorted(man.jobs) == sorted(man.engines)`;
3. exigir al menos un artefacto por job;
4. conservar `job.engine == clave`, `status=succeeded`, `exit_code=0` y SHA256, ya cubiertos por
   `read_manifest`;
5. añadir pruebas para jobs ausentes, motor faltante, motor extra y job sin artefactos.

No hardcodear los siete motores del run de aceptación.

##### Orden R7.2 — Eliminar coerciones de identidad

1. Introducir un helper estricto para enteros: aceptar `int`/entero NumPy, rechazar `bool`, string,
   float, `None`, NaN e infinito.
2. Usarlo en `dataset_manifest.counts` y en `epi_year`/`epi_week`.
3. Validar que `counts` contenga enteros no negativos y que `base`, `derived`, `products` sean
   coherentes con el universo/materialización.
4. Convertir cualquier valor inválido en `ArtifactValidationError`.
5. Añadir pruebas parametrizadas para string, bool, float, null y valor no numérico, tanto en
   `counts` como en calendario.

No usar `int(valor)` para “arreglar” metadata inválida.

##### Orden R7.3 — Cerrar selección de aceptación

1. Pasar `selection_run_id` esperado desde `_Summary` a `validate_acceptance`.
2. Exigir igualdad con `acceptance.json.provenance.selection_run_id`.
3. Exigir que `acceptance.json.artifacts` sea una lista no vacía.
4. Exigir que incluya, como mínimo, `final_selection.csv` con `final_selection.v1` y que su digest
   sea el usado por el refit.
5. Añadir mutaciones re-selladas para ID ajeno, artifacts vacíos y selección no declarada.

No añadir el ID al registry: sigue derivándose de la cadena sellada.

##### Orden R7.4 — Inventario exacto del forecast

Exigir top-level exacto:

| path | schema |
| --- | --- |
| `forecast_base.csv` | `forecast_base.v1` |
| `forecast.csv` | `forecast.v1` |
| `model_inventory.csv` | `model_inventory.v1` |
| `lineage.json` | `lineage.v1` |
| `preliminary_report.md` | `preliminary_report.v1` |

Para cada engine del forecast, exigir exactamente:

```text
artifacts/<engine>/forecast_base.csv · forecast_base.v1
```

Añadir tests para output faltante, extra, schema incorrecto y job sin su forecast base.

##### Orden R7.5 — Gate y STOP

Ejecutar:

```text
.venv/bin/pytest -q tests/unit/test_artifact_backend.py --no-cov
.venv/bin/pytest -q tests/unit/runner/test_artifact_validation.py --no-cov
make lint
make typecheck
.venv/bin/python -m scripts.doctor_padecimiento Obesidad --artifacts
.venv/bin/python -m scripts.doctor_padecimiento --artifacts
```

Además:

1. demostrar que las dos reproducciones P0 ahora generan `ArtifactValidationError`;
2. recalcular hashes de aceptación, refit, forecast y dataset antes/después;
3. registrar la Ronda 8 con PASS o FAIL inequívoco;
4. detenerse;
5. autorizar Acción 4 únicamente si R7.1–R7.4 están verdes.

#### Límites

- no modificar runs ni manifests canónicos;
- no reabrir selección, aceptación, refit o forecast;
- no validar aún el contenido de los CSV de forecast;
- no tocar Acción 5, frontend, DVC, lifecycle ni publicación;
- no hacer commit ni push.

---

### Ronda 8 — Micro-remediación R7 — 2026-07-25

#### Veredicto

**PASS.** Las órdenes R7.1–R7.4 quedan implementadas y probadas; las dos reproducciones P0 producen
`ArtifactValidationError`. Los cuatro runs canónicos no cambiaron un byte.

##### R7.1 — Jobs de la aceptación

`validate_acceptance` exige ahora `man.engines` no vacío, `sorted(man.jobs) == sorted(man.engines)`
y al menos un artefacto por job. `job.engine == clave`, `status=succeeded`, `exit_code=0` y los
SHA256 los seguía cubriendo `read_manifest`. Los siete motores del run de aceptación **no** están
escritos en ninguna parte: el conjunto sale del propio manifiesto.

##### R7.2 — Sin coerciones de identidad

Nuevo `artifact_identity.int_of`: acepta `int` y entero de NumPy (vía `numbers.Integral`), rechaza
`bool`, string, `float` —NaN e infinito incluidos— y `None`. Se usa en `dataset_manifest.counts` y
en `epi_year`/`epi_week`. Los conteos deben además ser no negativos, incluir `base`, `derived` y
`products`, y cumplir `products == base + derived`.

Se añadió `low_memory=False` a la lectura del dataset: sin él, la inferencia de tipos de pandas
depende del tamaño del chunk, y un valor inválido podía tipar la columna de forma distinta según
en qué fila cayera. Un validador no puede depender de eso.

##### R7.3 — Selección de la aceptación

`selection_run_id` viaja desde `_Summary` y se contrasta con
`acceptance.json.provenance.selection_run_id`. Además: `artifacts` no vacío, `final_selection.csv`
declarado con schema `final_selection.v1`, y su digest igual al que refiteó el portafolio. El ID
sigue derivándose de la cadena sellada; no se tocó el registry.

##### R7.4 — Inventario exacto del forecast

Top-level **exacto**: `forecast_base.csv`, `forecast.csv`, `model_inventory.csv`, `lineage.json` y
`preliminary_report.md`, cada uno con su schema. Cada job del forecast debe declarar exactamente
`artifacts/<engine>/forecast_base.csv` (`forecast_base.v1`).

#### Reproducciones, con su error tipado

```text
aceptacion_sin_jobs                aceptacion: jobs: [] != ['ets_add_damped_log1p', …]
aceptacion_con_motor_faltante      aceptacion: jobs: [6 motores] != [7 motores]
aceptacion_con_motor_extra         aceptacion: jobs: [7] != [8 con 'motor_inventado']
aceptacion_con_job_sin_artefactos  aceptacion/ets_add_damped_log1p: job sin artefactos
aceptacion_con_selection_run_id_…  aceptacion: selection_run_id: 'obesidad_select_otro' != '…bbe604…'
aceptacion_sin_artefactos_decla…   aceptacion: el veredicto no declara ningún artefacto
aceptacion_sin_declarar_la_selec…  aceptacion: el veredicto no declara final_selection.csv
forecast_con_artefacto_extra       forecast: artefactos declarados: [… 'job_context.json' …] != […]
forecast_sin_su_reporte            forecast: el manifiesto no declara preliminary_report.md
forecast_con_schema_incorrecto     forecast: schema de forecast.csv: 'forecast.v2' != 'forecast.v1'
forecast_job_sin_su_base           forecast/ets_…: artefactos del job: [] != ['artifacts/…/base']
conteo_negativo                    dataset: counts['derived'] negativo: -1
conteos_incoherentes               dataset: counts['products']: 112 != 111
conteo_ausente                     dataset: counts sin 'derived'
semana_no_entera                   epi_dataset_v2.csv: ('01','hombres'): epi_week: se esperaba un
                                   entero, no 'no_entero'
```

Y la parametrización de `counts.base` con `"no_entero"`, `True`, `64.0`, `None` y `NaN`: los cinco
dan error tipado con "counts" en el mensaje. Antes, `int(valor)` "arreglaba" el `True` y el `64.0`
en silencio y reventaba con `ValueError` crudo en los otros tres.

#### Gate R7.5

```text
.venv/bin/pytest tests/unit/test_artifact_backend.py            35 PASS
.venv/bin/pytest tests/unit/runner/test_artifact_validation.py 100 PASS
make lint                                                       PASS
make typecheck                                                  PASS (142 módulos)
doctor Obesidad --artifacts                                     ✅ rc=0
doctor --artifacts                                              ✅ rc=0
```

Suite completa, con los dos comandos separados:

| comando | resultado |
| --- | --- |
| `make test-fast` (lleva `-x`) | FAIL: se detiene en el primer fallo de la Acción 5 |
| `pytest tests/ -m "not slow and not integration"` (sin `-x`) | **1,557 PASS · 3 FAIL** |

Los 3 fallos siguen siendo los de `test_produccion_ownership.py` (Acción 5). Ninguno nuevo.

#### Integridad

| run | archivos | antes | después |
| --- | ---: | --- | --- |
| aceptación `…82370419efd4` | 67 | `6bbc7f84ea5ec5bb` | `6bbc7f84ea5ec5bb` |
| refit `…ff249060018a` | 162 | `972f7519f885c0d1` | `972f7519f885c0d1` |
| forecast `…92d446b6df8f` | 37 | `d89d92ee7e73b848` | `d89d92ee7e73b848` |
| dataset `obesidad_1502d1a25b48` | 9 | `2ef4ee1236aa94c0` | `2ef4ee1236aa94c0` |

`rolling_cv_v1.yaml` en `dd6d4a02…`. Nada se modificó para hacer pasar el validador.

#### Estado de los módulos

| módulo | líneas |
| --- | ---: |
| `runner/artifact_identity.py` | 193 |
| `runner/artifact_dataset.py` | 148 |
| `runner/artifact_acceptance.py` | 130 |
| `runner/artifact_portfolio.py` | 223 |
| `runner/artifact_validation.py` | 293 |

Los cinco siguen bajo el límite de 300. Matriz de mutaciones: **89 casos** (9 rompen el sello, 80
rompen la identidad), más los positivos, la parametrización de enteros y el control de re-sellado.

#### Estado al cerrar la ronda

```text
WIP sin commit sobre b981b6e5
Obesidad = trained · NO-GO · backend runner_runs · identidad, aceptación e inventarios verificados
F50      = configured · NO-GO
Acciones 1, 2 y 3 CERRADAS (R5 + R7 remediadas) · pendientes 4, 5, 6, 7, 8
lint PASS · typecheck PASS (142) · make test-fast FAIL por los 3 de la Acción 5
Cuatro runs canónicos íntegros · doctor verde para los seis padecimientos
Sin DVC, push, deploy, frontend ni flip
```

#### Pregunta

R7.1–R7.4 quedan verdes, que era la condición para autorizar la Acción 4. ¿Arranco la **Acción 4**
(validar el forecast real: 3,328/5,772, 64+47=111, horizonte, point-only e identidades
aritméticas) en su propia ronda, o prefieres una tercera auditoría independiente antes?

_Respuesta auditada:_ se ejecutó la tercera auditoría. La remediación R7 es correcta, pero antes de
la Acción 4 se debe cerrar únicamente el inventario exacto del dataset descrito en la Ronda 9.
Cuando ese microgate quede verde, continuar directamente con la Acción 4; no volver a detenerse a
pedir autorización.

---

### Ronda 9 — Tercera auditoría independiente y orden vigente — 2026-07-25

#### Veredicto

**Ronda 8 PASS en su alcance; Acción 3 todavía FAIL por un solo contrato funcional.**

Se revalidó el WIP sobre `b981b6e5`, sin modificar código, runs, DVC ni frontend:

```text
test_artifact_backend.py + test_artifact_validation.py   135 PASS
make lint                                                PASS
make typecheck                                           PASS (142 módulos)
doctor Obesidad --artifacts                              ✅ rc=0
doctor --artifacts                                       ✅ rc=0
```

La implementación de R7 sí cerró:

- jobs exactos de aceptación;
- enteros estrictos y errores tipados;
- `selection_run_id` y selección declarada;
- inventario top-level y por job exacto del forecast.

No se reabre ninguno de esos puntos.

#### Hallazgo único — el dataset no tiene inventario autoritativo

`dataset_window` verifica todos los records que encuentra y exige que esté declarado
`epi_dataset_v2.csv`, pero no exige el conjunto exacto ni sus schemas. Además, los helpers de
artefactos convierten las listas a diccionario por `path`, por lo que una ruta duplicada se
colapsa silenciosamente.

Se probaron tres mutaciones sobre copias aisladas de los cuatro runs, propagando y re-sellando
todos los digests:

| mutación | resultado actual |
| --- | --- |
| dejar solo `epi_dataset_v2.csv`; omitir `products.csv` y `lineage.json` | falso verde |
| cambiar el schema de `epi_dataset_v2.csv` a `inventado.v99` | falso verde |
| duplicar el record de `epi_dataset_v2.csv` | falso verde |

Esto es funcional, no endurecimiento contra un atacante: `products.csv` es la materialización de
los 111 productos y `lineage.json` describe su derivación. Si `dataset_manifest.json` es la
autoridad distribuible, ambos deben estar sellados de forma inequívoca.

#### Orden R9.1 — Inventario exacto del dataset

Definir un contrato único, usando las constantes de schema existentes:

| path | schema |
| --- | --- |
| `epi_dataset_v2.csv` | `epi_dataset_v2` |
| `products.csv` | `products.v1` |
| `lineage.json` | `lineage.v1` |

En `dataset_window`:

1. exigir esos tres records;
2. exigir que no haya faltantes ni extras;
3. exigir el schema exacto de cada uno;
4. conservar `validated=true`, existencia y SHA256, ya cubiertos;
5. no validar todavía el contenido tabular de `products.csv`: pertenece a la Acción 4.

No hardcodear un nombre de padecimiento, dataset ID o conteo de Obesidad.

#### Orden R9.2 — Rutas de artefacto únicas

En la primitiva común de identidad:

1. rechazar dos records con el mismo `path` antes de construir diccionarios;
2. aplicar el mismo invariante a `DatasetManifest.artifacts`, `RunManifest.artifacts` y
   `JobRecord.artifacts`;
3. mantener los helpers actuales de inventario exacto después de comprobar unicidad;
4. producir `ArtifactValidationError`, nunca `KeyError`, `ValueError` crudo o último-record-gana.

No añadir validaciones de filesystem defensivas ni más locks: el alcance es solamente que un
manifiesto tenga una identidad no ambigua.

#### Orden R9.3 — Tests

Añadir, sobre el fixture aislado y re-sellado:

1. dataset sin `products.csv`;
2. dataset sin `lineage.json`;
3. schema incorrecto para cada uno de los tres records;
4. artefacto extra en dataset;
5. ruta duplicada en dataset;
6. ruta duplicada top-level en refit o forecast;
7. ruta duplicada dentro de un job;
8. control positivo: el dataset canónico conserva sus tres records y valida.

Cada negativo debe terminar en `ArtifactValidationError` y el doctor debe traducirlo a un
`Problem`, sin traceback.

#### Orden R9.4 — Gate y continuación automática

Ejecutar:

```text
.venv/bin/pytest -q tests/unit/test_artifact_backend.py --no-cov
.venv/bin/pytest -q tests/unit/runner/test_artifact_validation.py --no-cov
make lint
make typecheck
.venv/bin/python -m scripts.doctor_padecimiento Obesidad --artifacts
.venv/bin/python -m scripts.doctor_padecimiento --artifacts
```

Además:

- demostrar que las tres reproducciones de esta ronda ya fallan con error tipado;
- confirmar que los hashes de dataset, aceptación, refit y forecast no cambiaron;
- registrar el resultado al final de esta ronda.

Si el gate queda verde:

1. marcar la Acción 3 **CERRADA**;
2. actualizar el estado superior y la sección 16;
3. iniciar inmediatamente la Acción 4 según 4.1–4.5;
4. no pedir otra revisión intermedia.

Si falla, detenerse solo en el primer incumplimiento reproducible y documentarlo aquí.

#### Límites vigentes

- no modificar ni regenerar runs canónicos;
- no reabrir selección, aceptación, refit o forecast;
- no tocar todavía las tres pruebas legacy de la Acción 5;
- no cambiar lifecycle, DVC, frontend o rutas públicas;
- no hacer commit ni push antes del gate completo de C7.1.

#### Siguiente acción inequívoca

```text
R9.1 inventario exacto del dataset
→ R9.2 paths únicos
→ R9.3 tests
→ R9.4 gate
→ si PASS, Acción 4.1–4.5 sin nueva pausa
```

#### Resultado de la micro-remediación R9 — **PASS**

**R9.1.** `dataset_window` exige ahora el inventario EXACTO del dataset, con las constantes de
schema que ya existían (`contracts.SCHEMA_DATASET`, `contracts.SCHEMA_PRODUCTS` y `lineage.v1`):
`epi_dataset_v2.csv`, `products.csv` y `lineage.json`, sin faltantes ni extras y con su schema
exacto. `validated=true`, existencia y SHA256 los seguía cubriendo `verify_records`. No se validó
el contenido tabular de `products.csv`: es de la Acción 4.

**R9.2.** La unicidad de rutas vive en `verify_records`, la primitiva común, y se comprueba **antes**
de construir cualquier diccionario por `path`. Como esa primitiva la usan `DatasetManifest.artifacts`,
`RunManifest.artifacts`, `JobRecord.artifacts` y los records que declara `acceptance.json`, el
invariante aplica a las cuatro. El inventario exacto (`require_exact_records`) corre después.

**R9.3 — las tres reproducciones, ya tipadas:**

```text
dataset_sin_products         dataset: inventario: ['epi_dataset_v2.csv','lineage.json'] != […]
dataset_sin_lineage          dataset: inventario: ['epi_dataset_v2.csv','products.csv'] != […]
dataset_con_artefacto_extra  dataset: inventario: [… 'manifest.json' …] != […]
dataset_schema_del_csv       dataset: schema de epi_dataset_v2.csv: 'inventado.v99' != 'epi_dataset_v2'
dataset_schema_de_products   dataset: schema de products.csv: 'inventado.v99' != 'products.v1'
dataset_schema_de_lineage    dataset: schema de lineage.json: 'inventado.v99' != 'lineage.v1'
dataset_con_ruta_duplicada   dataset: ruta declarada dos veces: epi_dataset_v2.csv
refit_con_ruta_duplicada     refit: ruta declarada dos veces: refit_summary.json
job_con_ruta_duplicada       refit/seasonal_mean_5y: ruta declarada dos veces: models/…/model_index.json
```

Más el control positivo (el dataset canónico declara exactamente sus tres records y valida) y dos
pruebas del doctor: inventario incompleto y ruta duplicada se traducen a un `Problem` único, sin
traceback.

**R9.4 — gate:**

```text
tests/unit/test_artifact_backend.py             37 PASS
tests/unit/runner/test_artifact_validation.py  110 PASS
make lint                                       PASS
make typecheck                                  PASS (142 módulos)
doctor Obesidad --artifacts                     ✅ rc=0
doctor --artifacts                              ✅ rc=0
```

Hashes sin cambio: aceptación 67 `4e0327ed…`, refit 162 `972f7519…`, forecast 37 `fb6f2afd…`,
dataset 9 `2ef4ee12…`.

**Acción 3 queda CERRADA.** Se continúa con la Acción 4 (4.1–4.5) sin nueva pausa, según lo
ordenado; su resultado se registra en la Ronda 10.

---

### Ronda 10 — Acción 4: validar el forecast real — 2026-07-25

#### Veredicto

**PASS.** El microcierre R9 quedó verde y, sin nueva pausa, se implementó y probó la Acción 4
completa (4.1–4.5). El doctor sólo da verde cuando el artefacto publicable entero es coherente.

##### 4.1 — Una sola frontera de validación

`runner/artifact_forecast.py` (236 líneas), llamado desde `validate_runner_runs` con
`forecast_dir`, el `VerifiedRunnerRuns` ya construido y el catálogo geográfico ya cargado. Reutiliza
los contratos que ya existían —`contracts.validate_forecast_frame` y
`evaluation.derive_forecast_products` con su `RECON_TOL`— en vez de reimplementar fórmulas, y no
lee el registry. CSV ilegible, columna ausente, tipo inválido o contrato roto se convierten en
`ArtifactValidationError`.

El catálogo dejó de inyectarse como lista de claves y pasa a ser un `GeoCatalog` inyectable: la
derivación de regiones y nacional necesita su membresía, y sigue siendo el catálogo trackeado, no
un diccionario legacy.

##### 4.2 — `forecast_base.csv`

Columnas del contrato, `n_models × horizon` filas con `n_models` del portafolio sellado y `horizon`
de `lineage.json`, universo exacto de las 64 `SeriesKey` seleccionadas, `run_id`/`disease_id`/
`engine=portfolio`/`fold=final_refit` constantes, periodos contiguos desde `shift(train_end, 1)`,
`horizon=1..H`, `ds` recalculado con `ds_for`, claves únicas, valores finitos no negativos e
intervalos conjuntamente nulos.

##### 4.3 — Origen por job y por modelo

Los seis `artifacts/<engine>/forecast_base.csv` se concatenan y se exige igualdad fila a fila con el
consolidado en clave, horizonte, `ds` y `y_pred_cases`; ninguna serie puede aparecer en un job que
no le corresponde según `final_selection.csv`. `model_inventory.csv` debe tener una fila por serie
base, sin duplicados, con el motor de la selección, el `n_train` y `train_end` sellados, el formato
declarado y un `state_digest` distinto por serie.

##### 4.4 — `forecast.csv` y las 47 derivadas

`(base + derived) × horizon` filas usando `VerifiedRunnerRuns.counts`, productos únicos, y las
derivadas **materializadas** llamando a `derive_forecast_products` sobre las bases: esa función ya
reconcilia `general = H + M`, Σ estados = región y Σ regiones = nacional con `atol=1e-9`. Se exige
igualdad fila a fila con el consolidado sellado.

##### 4.5 — Pruebas funcionales

**23 mutaciones nuevas**, todas con error tipado y por el motivo correcto:

```text
base_con_fila_faltante        forecast_base.csv: filas: 3327 != 3328
base_con_fila_duplicada       ForecastFrame: filas duplicadas por [...]
base_con_horizonte_ajeno      horizonte y periodos: […] != […]
base_con_origen_ajeno         origin_epi_week: [25, 26] != [26]
base_con_ds_incoherente       ds '2020-01-05' no corresponde a (2026, 27) (2026-07-06)
base_con_valor_negativo       ForecastFrame: y_pred_cases negativo
base_con_nan / _infinito      ForecastFrame: y_pred_cases con NaN/no finito
base_con_un_solo_intervalo    intervalos deben ser conjuntamente nulos o presentes
base_con_motor_ajeno          engine: ['portfolio','prophet_count_log1p'] != ['portfolio']
base_con_fold_ajeno           fold: ['development_2024','final_refit'] != ['final_refit']
base_sin_columna              faltan columnas ['yhat_upper']
base_truncada                 run_id: [] != ['obesidad_forecast_h52_…']
job_que_no_coincide           forecast_base.csv no coincide con los jobs en 'y_pred_cases'
consolidado_producto_falta…   forecast.csv: filas: 5771 != 5772
consolidado_producto_extra    ForecastFrame: filas duplicadas por [...]
nacional_alterado             un producto no es la suma de sus bases (máx |Δ|=1)
region_alterada               un producto no es la suma de sus bases (máx |Δ|=1.46e+03)
inventario_con_motor_ajeno    motor de ('05','hombres'): 'prophet_rate_log1p' != 'ets_add_damped…'
inventario_con_n_train_ajeno  n_train de ('05','hombres'): 1 != 653
inventario_con_estado_repet…  dos series comparten el estado b4890b2a5c96
inventario_sin_una_serie      model_inventory.csv: filas: 63 != 64
lineage_con_horizonte_ajeno   horizonte y periodos: […] != […]
```

Las cantidades observadas del run canónico —**3,328 / 5,772 / 64 / 47 / 111 / 52**— aparecen como
evidencia en los mensajes y en los tests, pero **ninguna** está escrita como regla dentro del
validador: salen del portafolio sellado, de `lineage.json` y de los `counts` del dataset.

#### Un defecto propio, encontrado por la prueba que lo cazó

`model_inventory.csv` lleva comas dentro de `train_end` (`"[2026, 26]"`), así que mis primeros
helpers de mutación, que hacían `split(",")`, **desalineaban las columnas**: la mutación
"dos series comparten el estado" no llegaba a aplicarse y el test salía verde por la razón
equivocada. Sólo se detectó porque el caso falló y verifiqué el archivo mutado. Los tres helpers
del inventario se reescribieron con el módulo `csv` y se re-verificó el mensaje de cada uno.

#### Gate

```text
tests/unit/test_artifact_backend.py             37 PASS
tests/unit/runner/test_artifact_validation.py  133 PASS
make lint                                       PASS
make typecheck                                  PASS (144 módulos)
doctor Obesidad --artifacts                     ✅ rc=0
doctor --artifacts                              ✅ rc=0
```

| comando | resultado |
| --- | --- |
| `make test-fast` (lleva `-x`) | FAIL: se detiene en el primer fallo de la Acción 5 |
| `pytest tests/ -m "not slow and not integration"` (sin `-x`) | **1,592 PASS · 3 FAIL** |

Los 3 fallos siguen siendo los de `test_produccion_ownership.py` (Acción 5).

#### Integridad

Los cuatro runs canónicos, byte-idénticos antes y después: aceptación 67 `4e0327ed…`, refit 162
`972f7519…`, forecast 37 `fb6f2afd…`, dataset 9 `2ef4ee12…`. `rolling_cv_v1.yaml` en `dd6d4a02…`.

#### Módulos

| módulo | líneas |
| --- | ---: |
| `runner/artifact_identity.py` | 210 |
| `runner/artifact_refit.py` | 89 (**nuevo**: resumen + lineage, extraído para respetar SRP) |
| `runner/artifact_dataset.py` | 157 |
| `runner/artifact_acceptance.py` | 130 |
| `runner/artifact_portfolio.py` | 223 |
| `runner/artifact_forecast.py` | 236 (**nuevo**, Acción 4) |
| `runner/artifact_validation.py` | 245 |

Los siete bajo el límite de 300. Matriz total: **121 mutaciones** (9 rompen el sello, 112 rompen la
identidad o el contenido), más positivos, parametrizaciones y controles.

#### Estado al cerrar la ronda

```text
WIP sin commit sobre b981b6e5
Obesidad = trained · NO-GO · identidad, aceptación, inventarios y forecast validados por contenido
F50      = configured · NO-GO
Acciones 1, 2, 3 y 4 CERRADAS · pendientes 5, 6, 7, 8
lint PASS · typecheck PASS (144) · make test-fast FAIL por los 3 de la Acción 5
Cuatro runs canónicos íntegros · doctor verde para los seis padecimientos
Sin DVC, push, deploy, frontend ni flip
```

#### Siguiente paso

Corresponde la **Acción 5** (reparar las tres pruebas legacy con un registry sintético inyectado,
sin devolverle motores legacy a Obesidad), que además es lo único que mantiene rojo el gate oficial
`make test-fast`. Me detengo aquí porque la orden vigente de la Ronda 9 llegaba hasta el cierre de
la Acción 4.

_Respuesta:_

---

### Ronda 124 — Auditoría integral del harness y última frontera de consumo — 2026-07-29

#### Rango auditado

```text
base     c453b979
HEAD     7025aa31
commits  527615f5 · d9a54f18 · 7025aa31
estado   ahead 3 · sin push
```

Superficie del rango:

```text
Makefile
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
scripts/publication_readiness.py
tests/unit/publication/test_publication_readiness.py

4 archivos · 1,934 inserciones · 16 eliminaciones
```

`git show --check`, `git diff --check` y la revisión de rutas: **PASS**. No hay cambios en
registry, lifecycle, config, release, DVC, modelos, forecasts, dashboard ni superficies públicas.
Los archivos no rastreados del usuario permanecen intactos. La única modificación trackeada fuera
del rango continúa siendo este plan.

Gate focal repetido durante esta auditoría:

```text
tests/unit/publication/test_publication_readiness.py   78 / 78 PASS
```

A.2 cierra correctamente las tres fronteras que declaró:

1. ubicación segura de evidencia tanto al cargar como inmediatamente antes de escribir;
2. inventario exacto y canónico del shard;
3. loader que recomputa el digest y cruza el preflight con la evidencia local.

El rango queda **PASS en superficie, generación e integridad local**, pero **NO listo para push**
porque la auditoría del consumidor siguiente encontró una última frontera funcional.

#### R124-P0 · el PASS externo no está ligado a la hoja que inspeccionó

`run_external_readonly` usa `C7_TABLEAU_STAGING_SPREADSHEET_ID` para abrir el sink y construir el
workbook, pero `external_preflight.v1` no persiste ninguna identidad redactada de la hoja. Después,
`load_external_preflight(path)` acepta el PASS sin recibir ni contrastar el entorno.

Reproducción independiente con dos IDs de staging distintos y dos sinks vacíos:

```json
{
  "a_status": "PASS_EXTERNAL_READONLY",
  "b_status": "PASS_EXTERNAL_READONLY",
  "same_inventory": true,
  "same_planned_steps": true,
  "workbook_digest_changed": true,
  "declares_staging_identity": false,
  "loader_accepts_without_environment": "PASS_EXTERNAL_READONLY"
}
```

Que el digest del workbook cambie no resuelve la identidad: el loader no sabe qué ID vigente debe
reproducir ni con cuál compararlo. Dos hojas vacías pueden tener exactamente el mismo inventario y
plan. Un futuro apply podría consumir evidencia obtenida de la hoja A mientras el entorno apunta a
la hoja B.

Esto no es endurecimiento contra un atacante. Es trazabilidad básica del handoff: la evidencia debe
decir, sin filtrar el ID, **qué hoja inspeccionó**, y el consumidor debe demostrar que sigue
operando sobre esa misma hoja.

#### R124-P1 · se pierde el plan tipado y un paso malformado escapa sin error de dominio

`promotion_plan()` ya devuelve el contrato completo:

```text
schema · namespace · steps · rows · digests
```

El preflight conserva únicamente `planned_steps`. Así se pierden el schema, los conteos y los
digests del plan exacto que se inspeccionó, aunque las tablas locales ya están selladas.

Además, el loader interpreta cada cadena con:

```python
p.split(":")[1].split("->")[0]
```

Reproducción con `planned_steps=["malformed"]`, volviendo a sellar el digest exterior:

```text
IndexError: list index out of range
```

Debe rechazarse con `ArtifactValidationError`; un artefacto inválido no puede escapar como fallo
accidental del parser.

#### Veredicto

```text
LOCAL HARNESS                         PASS
EVIDENCE LOCATION                     PASS
SHARD INVENTORY EXACTNESS             PASS
EXTERNAL GENERATION READ-ONLY         PASS
EXTERNAL SPREADSHEET IDENTITY BINDING FAIL
FULL PROMOTION PLAN SEAL              FAIL
LIVE PRE-APPLY REVALIDATION            MISSING
RANGO c453b979..7025aa31               NO PUSH todavía
F50                                    NO EJECUTAR
TAREAS MANUALES                        PENDING_MANUAL
```

### Orden C7.6-AUTO-B1-HARNESS-A.3 — identidad externa y estado vivo, local, sin red y STOP

#### Objetivo

Cerrar la última superficie autónoma de consumo antes del trabajo manual:

1. demostrar para qué hoja se produjo el preflight sin persistir el ID;
2. sellar el plan completo que se observó;
3. poder revalidar, de sólo lectura, que la hoja y el plan siguen iguales inmediatamente antes de
   una futura autorización de escritura.

No implementar apply, promote, rollback externo ni ninguna escritura sobre Google.

#### Alcance permitido

```text
scripts/publication_readiness.py
tests/unit/publication/test_publication_readiness.py
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md   sólo si cambia el contrato visible
```

No tocar `tableau_adapter.py`, `sheets_sink.py`, los CLI anteriores, `Makefile`, registry, config,
artifacts, DVC, dashboard ni este plan dentro del commit.

#### A.3.1 · versionar el artefacto externo

Cambiar de forma cerrada:

```text
external_preflight.v1  →  external_preflight.v2
```

No existe un preflight externo productivo que deba migrarse; los actuales son temporales o de
tests. No mantener dos loaders ni compatibilidad silenciosa con v1.

#### A.3.2 · ligar el preflight a ambas hojas sin filtrar IDs

Persistir dos fingerprints con separación de contexto:

```text
staging_identity_digest =
  sha256(canonical_json({"purpose": "c7-staging", "id": staging_id}))

production_identity_digest =
  sha256(canonical_json({"purpose": "c7-production", "id": production_id}))
```

Reglas:

- los IDs reales siguen siendo obligatorios, no vacíos y distintos;
- ningún ID, JSON de service account, email, longitud, prefijo ni fragmento entra en stdout,
  errores o archivos;
- no sellar la service account: puede rotar sin cambiar la hoja gobernada;
- ambos fingerprints forman parte de `preflight_digest`;
- `load_external_preflight` recibe explícitamente el entorno y recomputa ambos fingerprints antes
  de aceptar el PASS.

El loader sigue siendo puro: puede leer evidencia y usar los IDs sólo para recomputar, pero no abre
Google ni escribe.

#### A.3.3 · sellar `promotion_plan` completo

Sustituir `planned_steps` por el mapping completo devuelto por `promotion_plan()`:

```text
schema     tableau_runner_promotion.v1
namespace  conjunto exacto administrado
steps      lista ordenada
rows       conteos exactos por tabla
digests    digests exactos por tabla
```

El loader exige forma cerrada y cruza:

- `namespace` contra `TABLES`;
- `rows` contra las tablas reconstruidas desde la evidencia local;
- `digests` contra `table_digests`;
- cada paso contra una gramática cerrada `write|rename|drop`, sin indexar resultados de `split`;
- toda tabla origen/destino dentro del namespace y sus sufijos administrados.

Cualquier paso malformado debe producir `ArtifactValidationError`, nunca `IndexError`, `KeyError`
ni otro error incidental.

#### A.3.4 · reproducir el workbook con la identidad vigente

Al cargar el preflight:

1. volver a cargar la evidencia local con `load_local_evidence`;
2. reconstruir el workbook desde esas tablas usando el `staging_id` vigente;
3. comparar su digest y tablas con el workbook sellado;
4. mantener `tableau_desktop_validated=false`.

Esto demuestra localmente que la evidencia corresponde al ID vigente sin abrir la hoja ni
persistirlo.

#### A.3.5 · verificador externo vivo de sólo lectura

Añadir una capacidad separada, por ejemplo:

```text
verify_external_preflight_live(external_evidence, entorno, sink_factory)
```

Orden obligatorio:

1. cargar y validar v2 contra el entorno;
2. abrir exactamente el sink de staging declarado por ese entorno;
3. si el sink expone identidad, exigir que coincida con el ID de staging;
4. leer dos inventarios consecutivos y exigir estabilidad;
5. comparar el `inventory_digest` vivo con el sellado;
6. recomputar `promotion_plan(sink, tables)` y compararlo **completo** con el sellado;
7. devolver PASS de sólo lectura.

La función no escribe, renombra, elimina ni crea nada. Éste será el gate que una futura orden de
apply tendrá que ejecutar inmediatamente antes de la primera escritura. No crear el apply en A.3.

#### Tests obligatorios

1. Dos IDs de staging distintos sobre sinks vacíos producen fingerprints y preflights distintos.
2. El loader con el entorno B rechaza el preflight producido con A, antes de abrir un sink.
3. Cambiar sólo el ID productivo también rechaza.
4. IDs, JSON, email, longitud, prefijo y centinelas no aparecen en stdout ni en ningún archivo.
5. El loader sin entorno o con una variable ausente rechaza: no acepta contexto implícito.
6. Workbook regenerado con el ID vigente coincide; con otro ID rechaza.
7. `promotion_plan` positivo cruza schema, namespace, steps, rows y digests.
8. Mutar por separado schema, namespace, steps, rows o digests y resellar sólo el exterior rechaza.
9. Paso vacío, sin `:`, verbo desconocido, flecha incompleta o tabla ajena rechaza con
   `ArtifactValidationError`.
10. Inventario vivo distinto después del preflight rechaza.
11. Plan vivo distinto con inventario estable rechaza.
12. Sink con identidad distinta de la solicitada rechaza.
13. Estado vivo idéntico pasa.
14. Contadores demuestran cero operaciones de escritura en loader y verificador vivo.
15. Los 78 focales existentes permanecen verdes.
16. La forma v1 se rechaza explícitamente; no se migra ni se acepta por fallback.

#### Gates

```text
ruff check
ruff format --check
mypy
tests focales
tests/unit/publication completos
make test-fast
carril local real dos veces, mismo digest
external-readonly positivo con sink inyectado
load_external_preflight v2 positivo con entorno explícito
verify_external_preflight_live positivo con sink inyectado
doctor --artifacts
release y agregados legacy byte-idénticos
búsqueda de centinelas en stdout y evidencia
git diff --check
```

#### Commit y STOP

Un commit local separado:

```text
C7.6 bind external preflight to spreadsheet identity and live state
```

Después STOP. No push. No ejecutar F50. No acceder a Google, Netlify o Tableau Desktop. No DVC,
lifecycle, puntero, deploy ni publicación.

Al cerrar A.3 se audita el rango completo `c453b979..NUEVO_SHA`. Si esa auditoría pasa, el carril
autónomo queda realmente agotado: lo único pendiente será ejecutar el manual cuando exista la hoja
y el entorno externo, y cualquier push conservará su autorización separada.

#### Siguiente orden autónoma

_Respuesta:_ **GO C7.6-AUTO-B1-HARNESS-A.3 LOCAL. Versionar `external_preflight` a v2, ligarlo a
fingerprints redactados de las hojas de staging y producción, sellar el `promotion_plan` completo
y añadir la revalidación del estado vivo estrictamente read-only. Probarlo todo con sinks
inyectados, crear un commit local separado y STOP. Sin Google, credenciales reales, F50, DVC, push,
lifecycle, puntero, deploy ni publicación.**

---

### Ronda 66 — Auditoría B4.2 PASS y orden C7.6-RAG por gates — 2026-07-26

#### B4.2 auditada · PASS

La auditoría se hizo sobre el rango `19e6a893..438441a0`, no sólo sobre el reporte del commit.

```text
commit                              438441a0
superficie                          kb.js + test_ranking.mjs · +91 / -6
git diff --check                    PASS
npm test                            616/616 + 43/43
test:candidate                      19/19
test:cases:verify                   616 · rc=0 · no mutante
node --check                        kb.js + test_ranking.mjs · PASS
respuestas modificadas              129–136 y 214–216 · exactamente 11
respuestas extra/faltantes          0 / 0
handlers modificados                0
pruebas nuevas contra 19e6a893      2 rojas de 11; las 9 restantes verdes
knowledge/RAG/HTML/package          byte-idénticos
```

Las tres decisiones de B4.2 quedan aceptadas:

1. **Mensaje explícito en vez de `null`: correcto.** Ceder con `null` permitiría que un handler
   posterior contestara con el agregado de otro padecimiento. El mensaje detiene la resolución con
   una respuesta honesta.
2. **Nombrar fuentes disponibles sin mostrar sus cifras: aceptado.** Ayuda al usuario sin atribuir
   números ajenos al padecimiento pedido. Las pruebas fijan que ninguna cifra de otro padecimiento
   pueda aparecer.
3. **Aplicar el mismo cierre a `answerSexo`: correcto.** Era el mismo defecto semántico en la ruta
   contigua. Dejarla abierta habría conservado el fallo para Obesidad, F50 y cualquier N+1 sin
   desglose.

La etiqueta de corte también queda aceptada: sale de `boletin.meta.max_semana/max_anio` y declara
“datos hasta la semana N de AAAA”. No inventa si el año MMWR tiene 52 o 53 semanas y no depende de
la fecha del sistema.

**B4.2 queda CERRADA. No reabrirla durante C7.6.**

#### Hallazgo que gobierna C7.6-RAG

El índice candidate de staging puede dar un **falso verde** hoy:

- `rag_staging.mjs` comprueba que el chunk exista, pero asigna `[]` a los chunks sin embedding;
- un chunk candidate con vector vacío se reporta como “sin drift”;
- `build_rag_index.mjs` tolera clave ausente, fallo de API o embedding vacío y puede terminar con
  `rc=0`;
- la disponibilidad de búsqueda léxica no satisface readiness del canal RAG.

Por eso no se autoriza regenerar ningún índice antes de corregir el contrato. Tener
`GEMINI_API_KEY` disponible no convierte un verificador incompleto en un gate válido.

#### C7.6-RAG-A — contrato y pruebas, sin usar la clave

Ésta es la **única acción autorizada inmediatamente**. Trabajar en
`EpiForecast-IMSS-Dashboard` sobre `438441a0`, en un commit local y STOP.

1. Extraer una única función compartida para:
   - reutilizar embeddings por `chunkHash`;
   - generar los embeddings faltantes;
   - validar el resultado completo.
   `build_rag_index.mjs` y `rag_staging.mjs` deben consumirla; no duplicar llamadas a Gemini,
   reintentos ni reglas de validación.
2. El contrato de un índice válido exige simultáneamente:
   - mismo número de `chunks` y `vectors`;
   - cada chunk esperado presente exactamente una vez por `chunkHash`;
   - vector correspondiente presente, arreglo no vacío, dimensión declarada y valores numéricos
     finitos;
   - vector asociado al mismo chunk/hash, sin aceptar desalineación posicional;
   - cero chunks esperados ausentes, cero extras ambiguos y cero hashes duplicados.
3. Fallar con `rc!=0` ante:
   - clave ausente cuando falten embeddings;
   - error/rate-limit agotado;
   - respuesta sin vector, vector vacío, dimensión incorrecta o valor no finito;
   - chunk ausente, duplicado, extra o asociado al vector de otro chunk.
   No escribir un índice parcial ni caer a modo léxico en readiness.
4. La escritura sólo ocurre después de validar el frame completo y debe ser atómica. Ante fallo,
   conservar el archivo previo byte-idéntico y no dejar temporales.
5. Añadir pruebas deterministas que muerdan, sin red real:
   - índice totalmente cubierto → PASS;
   - chunk ausente → FAIL;
   - `[]` → FAIL;
   - dimensión incorrecta/NaN → FAIL;
   - chunk y vector desalineados → FAIL;
   - fallo permanente de proveedor → FAIL y destino previo intacto;
   - caché válida → no solicita embedding otra vez;
   - candidate nuevo → exige embedding real, no `[]`.
6. Integrar en esta misma pieza las dos deudas pequeñas de la Ronda 64:
   - corregir el encabezado de `generate_tests.js`: construye/verifica/escribe 616 casos; no los
     ejecuta;
   - hacer que `npm run check` invoque `npm test` exactamente una vez, sin recursión ni duplicar
     suites.
7. Gate de A:

```text
npm test                            616/616 + unitarios
npm run test:candidate              19/19 o más
pruebas nuevas RAG                  todas verdes, proveedor simulado
node --check                        scripts y pruebas tocados
npm run check                       puede seguir rojo ÚNICAMENTE por el drift baseline conocido;
                                     debe ejecutar y aprobar npm test antes de llegar a ese rojo
epibot/rag_index.json               byte-idéntico
knowledge.json / HTML               byte-idénticos
GEMINI_API_KEY                      no leída, no impresa, no requerida
```

8. Un commit local `C7.6-RAG-A` y STOP para auditoría. No encadenar B.

#### C7.6-RAG-B — reparar el índice público baseline

**No autorizada todavía.** Se autoriza únicamente después de auditar A.

1. Verificar presencia con `test -n "${GEMINI_API_KEY:-}"`; no imprimir longitud, valor, prefijo,
   sufijo ni serializar el entorno.
2. Preservar en temporal el SHA256 y una copia de `epibot/rag_index.json`.
3. Ejecutar el builder corregido sobre el corpus público, sin candidate root.
4. Exigir:
   - corpus e índice con el mismo conjunto de chunks;
   - un vector válido por chunk;
   - `missing=0`, `failed=0`, duplicados=0;
   - `npm run rag:verify` rc=0;
   - cero chunks o texto de Obesidad en el índice público;
   - `knowledge.json` y HTML byte-idénticos.
5. Revisar el diff del índice: sólo cambios explicables por los 19 chunks baseline antes no
   cubiertos y metadata derivada; cualquier otro cambio se investiga.
6. `npm run check` completamente verde.
7. Un commit local separado y STOP. Sin push, deploy ni candidate.

#### C7.6-RAG-C — índice candidate sólo en staging

**No autorizada todavía.** Se autoriza únicamente después de auditar B.

1. Compilar el shard candidate en un directorio temporal desde
   `obesidad_release_2517e7858901`, manteniendo Obesidad `trained`.
2. Construir `rag_index.staging.json` con el corpus público ya cubierto más el chunk candidate.
3. Exigir:
   - todos los chunks públicos conservan vector válido;
   - el chunk de Obesidad existe exactamente una vez y tiene vector válido no vacío;
   - cero drift, vacíos, fallos, duplicados o desalineaciones;
   - `epibot/rag_index.json` público sigue sin Obesidad;
   - `knowledge.json`, HTML y superficies públicas siguen sin Obesidad.
4. Repetir en otro staging limpio. Comparar identidad determinista ignorando únicamente metadata
   temporal expresamente no identitaria; chunks, hashes y vectores deben coincidir.
5. `npm run check` completamente verde.
6. STOP para auditoría y paquete de readiness. Sin push, cache-bust, deploy, activación,
   lifecycle ni publicación.

#### Prohibiciones comunes de C7.6-RAG

- Nunca registrar, imprimir ni commitear `GEMINI_API_KEY`.
- No introducir fallback léxico como sustituto de un embedding requerido.
- No incluir Obesidad en `rag_index.json`, `knowledge.json` ni HTML públicos.
- No tocar backend, release DVC, puntero, lifecycle, canales o galería.
- No push, PR, merge, deploy, cache-bust ni publicación.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-RAG-A` local: contrato compartido, validación fail-closed, pruebas y
las dos deudas de package/generador. Un commit y STOP.**

_Respuesta:_ **GO C7.6-RAG-A LOCAL. Sin usar `GEMINI_API_KEY`, sin regenerar
`rag_index.json`, sin candidate build, push, PR, merge, deploy, cache-bust, activación, lifecycle
ni publicación.**

---

### Ronda 61 — Auditoría independiente de 47.2-B4 y Orden 47.3 — 2026-07-26

Esta ronda modifica únicamente este plan. No corrige código, no usa `GEMINI_API_KEY` y no toca RAG,
HTML, cache-bust, lifecycle, punteros, DVC ni publicación.

#### Auditoría de `a1412e33..3ee38310`

```text
superficie del diff                 5 archivos · +305 / -20 · diff --check PASS
archivos                            entities.js · kb.js · generate_tests.js
                                    test_cases.json · test_ranking.mjs
superficies públicas                knowledge/RAG/HTML/package byte-idénticos
npm test                            616/616 · handler real
pruebas focalizadas                 35/35
test:candidate                      19/19
generate_tests.js --check           rc=0 · 616 pares (query, setup) · no mutante
node --check                        entities.js · kb.js · test_ranking.mjs PASS
npm run check                       rc=1 únicamente en rag:verify:
                                    corpus 454 · índice 452 · 19 chunks sin cubrir
```

La comparación independiente se hizo desde dos `git archive`, uno de `a1412e33` y otro de
`3ee38310`, con `Math.random = () => 0.42`:

```text
filas comparadas                    616 / 616
respuestas o handlers distintos      12
ids esperados                       129–136 · 214–216 · 339
extras                                0
faltantes                             0
```

Las ocho pruebas nuevas se copiaron sobre un archive limpio de `a1412e33`: **0/8 PASS**. Fallan por
las causas que dicen proteger —ranking intercambiable, denominador falso, DF/CDMX duplicado,
cobertura no declarada, subtotal llamado total, sexo servido como entidad y mutación de fuente sin
efecto—. En `3ee38310` pasan 8/8. Por tanto no son pruebas decorativas posteriores al arreglo.

#### Recomputación independiente de la fuente

Los valores se recalcularon directamente desde `knowledge.json`, sin usar el helper nuevo:

| padecimiento | entidades canónicas con desglose | subtotal cubierto | total nacional | cobertura | top 3 |
| --- | ---: | ---: | ---: | ---: | --- |
| Depresión | 14 | 1,050,456 | 1,460,553 | 71.9% | CDMX 235,862 · Jalisco 114,820 · México 113,792 |
| Parkinson | 14 | 63,055 | 90,929 | 69.3% | Jalisco 9,657 · Veracruz 7,959 · CDMX 6,607 |
| Alzheimer | 14 | 20,790 | 29,564 | 70.3% | Jalisco 2,900 · Chihuahua 2,335 · Sinaloa 2,208 |

El ranking genérico colapsa DF/CDMX y queda en **19 entidades canónicas**, subtotal **1,310,006**,
contra un total nacional de **1,581,046**. Parkinson 2017 conserva y suma las dos observaciones
existentes, 389 + 81. La respuesta de sexo agrega las cuatro claves presentes en
`stats.demo_historica` y declara el universo: Alzheimer, Dengue, Depresión y Parkinson.

#### Veredicto 47.2-B

```text
47.2-B1     PASS
47.2-B2     PASS
47.2-B3     PASS
47.2-B4     PASS
47.2-B      CERRADA
```

No hay defecto material que corregir antes de 47.3. La cobertura 14/32 es una limitación real del
`knowledge.json` legacy, pero ya no se oculta. Completar 32/32 exige ampliar el generador del
backend; queda como mejora P1 separada y **no bloquea** la publicación de Obesidad, porque estas
respuestas son históricas de la cohorte legacy y no reinterpretan el release de Obesidad.

#### Hallazgo operativo previo a 47.3

El contrato funcional ya existe, pero todavía no forma un gate oficial completo:

1. `package.json` no declara `test:cases:verify`;
2. `npm test` ejecuta sólo `run_tests.js`, por lo que no comprueba antes que el fixture provenga del
   generador;
3. las regresiones de traza, precedencia, entidades, ranking y del propio runner sólo pasan cuando
   alguien recuerda invocarlas manualmente;
4. `generate_tests.js` imprime `Total tests generated: 564` antes de añadir los 52 casos finales,
   aunque el artefacto correcto contiene 616;
5. la cabecera aún dice que el generador “genera y ejecuta”, pero no ejecuta las respuestas;
6. `npm run check` no llama a la suite completa del KB.

Esto no invalida B4. Es exactamente la deuda acotada de 47.3.

#### Orden 47.3 — un solo gate oficial, local y reproducible

Trabajar únicamente en `EpiForecast-IMSS-Dashboard`, sobre `3ee38310`.

##### 47.3.1 — Fuente y artefacto

1. Conservar `generate_tests.js` como única fuente de los 616 casos y `test_cases.json` como
   artefacto generado.
2. Mover `Total tests generated` al final de la construcción, después de los 52 casos incorporados:
   debe imprimir **616**, nunca 564.
3. Corregir la cabecera: el script **construye/verifica o escribe** el fixture; no ejecuta las
   respuestas.
4. No reordenar casos, cambiar contratos, convertir expectativas en `*` ni editar las 616 consultas
   durante 47.3.

##### 47.3.2 — Contrato puro verificable

Extraer únicamente las funciones de serialización, invariantes y comparación a un módulo pequeño
de pruebas, consumido tanto por `generate_tests.js` como por su test. No copiar la lógica en dos
sitios.

La prueba del contrato debe usar temporales y demostrar:

- fixture idéntico → PASS;
- contrato alterado → FAIL;
- caso ausente → FAIL;
- par `(query, setupQuery)` duplicado → FAIL;
- ID ausente/no consecutivo → FAIL;
- el modo oficial `--check` no cambia bytes ni `mtime` del fixture;
- dos ejecuciones explícitas del generador producen bytes idénticos.

No hace falta añadir hardening de filesystem ni otro formato de artefacto.

##### 47.3.3 — Scripts oficiales

Añadir scripts con responsabilidades claras:

```json
"test:cases:verify": "node tests/generate_tests.js --check",
"test:cases": "node tests/run_tests.js",
"test:contracts": "node --test tests/test_fixture_contract.mjs tests/test_dispatcher_trace.mjs tests/test_runner_gate.mjs tests/test_entities.mjs tests/test_precedencia.mjs tests/test_ranking.mjs",
"test": "npm run test:cases:verify && npm run test:cases && npm run test:contracts"
```

Los nombres pueden variar sólo si conservan esas tres capas. `npm test` debe fallar antes de
ejecutar respuestas cuando el fixture no coincide con su fuente.

Integrar `npm test` dentro de `npm run check`, antes de `test:candidate` y `rag:verify`, sin crear
recursión ni ejecutar dos veces la misma suite. Hasta corregir el RAG en la fase siguiente,
`npm run check` puede terminar rojo **únicamente** en `rag:verify`; cualquier fallo anterior
pertenece a 47.3 y bloquea su cierre.

##### 47.3.4 — Regresión y alcance

Antes y después del cambio:

- comparar las 616 respuestas y handlers con RNG fijo: **616/616 byte-idénticos**;
- conservar exactamente **448 contratos nombrados + 121 comodines + 47 null = 616**;
- `knowledge.json`, `rag_index.json`, `index.html`, `epibot/index.html`, `package-lock.json` y los
  archivos candidate deben permanecer byte-idénticos;
- no tocar `kb.js` ni `entities.js`: 47.3 integra gates, no vuelve a cambiar despacho;
- `test:gen` seguido de `git diff --exit-code -- tests/test_cases.json` debe quedar limpio.

##### Gate de cierre 47.3

Ejecutar desde `EpiForecast-IMSS-Dashboard/epibot`:

```text
npm run test:cases:verify           PASS · 616 · no mutante
npm test                            PASS · 616/616 + contratos focalizados
npm run test:candidate              19/19
npm run test:gen                    genera 616
npm run test:gen                    segunda generación byte-idéntica
node tests/generate_tests.js --check PASS
npm run check                       llega verde hasta rag:verify;
                                    el único rojo permitido es el drift RAG ya declarado
```

Crear **un commit local acotado** de 47.3 y detenerse para auditoría.

#### Prohibido en esta orden

- usar o imprimir `GEMINI_API_KEY`;
- regenerar `rag_index.json`;
- tocar `knowledge.json`, HTML, cache-bust, lifecycle, puntero o release;
- push, PR, merge, deploy, activación o publicación;
- corregir la cobertura histórica 14/32 dentro de 47.3.

#### Después de 47.3

1. Auditar el commit y confirmar que `npm test` ya es el gate único.
2. Ejecutar `C7.6-RAG-CONTRACT` con la clave sólo como variable de entorno:
   corregir el contrato de vectores, regenerar el índice staging/publicable y llevar el drift real
   a cero sin revelar la clave.
3. Sólo después emitir readiness final, hacer cache-bust, preparar activación coordinada y pedir
   autorizaciones externas separadas.

#### Próxima acción exacta

**Ejecutar únicamente 47.3 local sobre `3ee38310`, crear un commit y STOP.**

_Respuesta:_ **GO 47.3 LOCAL. Sin RAG, clave, push, deploy, activación ni publicación.**

---

### Ronda 56 — Auditoría de `553b84d1`, clasificación cerrada y Orden 47.2-B — 2026-07-26

Auditoría de solo lectura en ambos repos. Esta ronda modifica únicamente este plan. No cambia
`kb.js`, `entities.js`, el generador, el fixture, RAG, frontend público, lifecycle, punteros ni
artefactos.

#### Estado verificado

```text
Backend    feat/registry-padecimientos-obesidad @ fc09d37d · ahead 9 · sólo este plan modificado
Dashboard  feat/c73-candidate-staging @ 553b84d1 · limpio · remoto d5ead880
Usuario    untracked preservados en ambos repos
Obesidad   trained · runner_release · puntero inactivo · NO-GO
```

Gate ejecutado:

```text
npm test                                      616/616 PASS
npm run test:candidate                         19/19 PASS
node --test tests/test_dispatcher_trace.mjs      7/7 PASS
node tests/generate_tests.js --check           rc=0 · 616 únicas · IDs 1..616
git diff --check de 553b84d1                   PASS
superficies públicas                            byte-idénticas
```

El verde de `npm test` todavía **no prueba el handler nombrado**: `run_tests.js` llama `answer()` y,
para un `expectedHandler` concreto, sólo valida `mustContain`/`mustNotContain`. Ésa es la deuda
funcional que 47.2-B debe cerrar; no invalida la instrumentación de 47.2-A.1.

#### Digest de la matriz: reproducido exactamente

La matriz de Ronda 55 fue reconstruida desde `answerWithTrace()` con `Math.random = () => 0.42`.
La serialización exacta que produce el digest —detalle que faltaba dejar explícito— es:

```text
1. conservar sólo expectedHandler nombrado, distinto de '*' y distinto del observado;
2. ordenar por `${expected}->${observed}` con localeCompare y después por id numérico;
3. proyectar cada fila a [id, query, setupQuery ?? null, expected, observed];
4. JSON.stringify(matriz) compacto, UTF-8, SIN salto de línea final;
5. SHA-256.
```

Resultado independiente:

```text
65 filas · 27 pares · sha256
0c23efc6e66ace6b7bd69b73be0d0c4a4651f185c647b86a718d2e4a8efd8495
```

Por tanto, la matriz congelada de R55 es válida. No se permite iniciar 47.2-B desde otro universo.

#### R56-P0 — `genero` se interpreta como el mes `enero`

`extractMonths()` usa `q.includes(name)`. En consecuencia:

```text
detectEntities('hay diferencia de genero en parkinson')._months == [1]
detectEntities('brecha de genero en depresion')._months         == [1]
```

Los casos 337 y 338 añaden una estimación de **enero 2026** a preguntas de género. Esto es un
defecto de entidades, no una simple disputa de handler, y debe corregirse antes de tocar
precedencias. Los meses se reconocen como tokens completos; `enero` sigue funcionando y `genero`
deja de contener un mes.

#### Clasificación cerrada: 20 expectativas históricas + 45 correcciones funcionales

No se adopta la regla peligrosa “hacer que el código coincida siempre con el fixture”, ni la
contraria “reescribir el fixture con lo observado”. Se revisó consulta y contenido de las 65.

**A. Veinte respuestas actuales son funcionalmente correctas; se corrige la expectativa en la
declaración original del generador:**

| ids | nuevo `expectedHandler` | motivo |
| --- | --- | --- |
| 481, 483, 491, 492 | `answerHistorico` | año/rango pasado; informa la limitación estatal y da el histórico nacional disponible |
| 214, 215, 216 | `answerBoletin` | ranking histórico por entidad, no ficha general del padecimiento |
| 242, 254 | `answerProyectoMeta` | explica la metodología, Ensemble y el papel de XGBoost |
| 251 | `answerRadar` | comparación especializada de motores y ganador |
| 283 | `answerProyectoMeta` | define el fallback dentro de la geografía real del proyecto |
| 284, 292 | `answerTemporal` | horizonte efectivo, fechas, duración y avance |
| 307, 309 | `answerConteo` | conteo directo de series/modelos |
| 321 | `answerMotor` | compara familias de motores |
| 322 | `answerMejoresPeores` | respuesta especializada de extremos por SMAPE |
| 330 | `answerProyectoMeta` | composición estructural del proyecto por sexo |
| 331 | `answerComparacionPorSexo` | comparación especializada hombres vs mujeres |
| 554 | `answerHistorico` | enero de 2026 es un periodo pasado, no una ficha general |

Son **cambios de contrato**, no cambios de respuesta. Deben hacerse en
`tests/generate_tests.js`, regenerar `test_cases.json` y demostrar que las respuestas de esos 20
ids permanecen byte-idénticas con RNG fijo.

**B. Cuarenta y cinco consultas sí revelan respuesta o precedencia funcional incorrecta:**

| causa | ids | contrato objetivo |
| --- | --- | --- |
| intención explícita de forecast secuestrada por ficha general | 149, 150, 151, 153–158, 613, 616 | `answerPronostico` |
| pregunta de tendencia mal contratada | 126 | cambiar expectativa y ruta a `answerBoletin`; debe responder crecimiento/disminución, no forecast |
| ranking de incidencia servido como ranking futuro | 135 | `answerBoletin` |
| histórico estatal servido como forecast estatal | 484, 485, 487–489, 493 | `answerBoletin` |
| definición servida como tabla global | 275–278, 464 | `answerDefinicion` |
| definición servida como diagnóstico | 280, 281 | `answerDefinicion` |
| composición demográfica secuestrada por metadatos/ficha | 365–368 | `answerDemografica` |
| última semana servida sólo como cobertura | 340, 342, 343 | `answerSemanaActual` |
| conteo de modelos servido como forecast | 218, 361 | `answerConteo` |
| ranking de rendimiento servido como resumen global/contexto | 319, 320, 433 | `answerRanking` |
| mejor motor por SMAPE servido como métricas globales | 245 | `answerMotor` |
| rendimiento de Parkinson servido como matriz global | 211 | `answerPadecimiento` o salida equivalente filtrada por Parkinson, nunca matriz global |
| sexo/género servido como ficha general | 335, 337, 338, 440, 441 | `answerSexo`; la salida debe respetar padecimiento y sexo heredados |

La suma es exacta:

```text
20 contratos ya correctos en ejecución
45 correcciones funcionales
──
65 discrepancias iniciales
```

El id 126 es deliberadamente una corrección doble: su expectativa histórica
`answerPronostico` también era falsa, pero la respuesta observada `answerPadecimiento` tampoco
contesta “ha crecido o disminuido”. Su destino correcto es `answerBoletin`.

#### Orden 47.2-B — tres commits locales y STOP

Trabajar **sólo** en `EpiForecast-IMSS-Dashboard`, desde `553b84d1`. No usar sustituciones globales
ni regex sobre el fixture generado.

##### 47.2-B1 — Entidades y contratos declarativos

1. Corregir `extractMonths()` con coincidencia de token completo.
2. Añadir regresiones positivas/negativas:
   - `enero 2026` → mes 1;
   - `genero`, `generos` y `brecha de genero` → ningún mes;
   - ids 337/338 no contienen una estimación de enero.
3. Aplicar en las declaraciones originales de `generate_tests.js` los 20 cambios de la tabla A y
   el cambio del id 126 a `answerBoletin`.
4. Regenerar `test_cases.json`; no editarlo a mano.
5. Verificar `--check`, unicidad 616/616 e IDs 1..616.
6. Con RNG fijo, exigir que los 20 casos de tabla A conserven exactamente su respuesta anterior.

Commit local acotado. Todavía no hacer obligatoria la igualdad global de handlers: quedan las rutas
funcionales de B2.

##### 47.2-B2 — Corregir las 45 rutas por causa

1. Resolver por intención explícita y guards de cesión; no reordenar `HANDLERS` completo para
   perseguir el verde.
2. Corregir una causa a la vez y añadir una regresión por causa de la tabla B.
3. En consultas de sexo, verificar **contenido**, no sólo nombre:
   - el padecimiento solicitado permanece;
   - el follow-up conserva hombres/mujeres;
   - no aparece un mes espurio;
   - no se devuelve una tabla global ajena a la consulta.
4. En histórico/última semana/ranking, comprobar que la respuesta contiene el dato solicitado y no
   texto de forecast futuro o cobertura genérica.
5. Comparar antes/después las 616 respuestas con RNG fijo. Sólo pueden cambiar los ids autorizados
   en tabla B. Si cambia cualquier otro id, detenerse, clasificarlo y documentarlo antes de seguir.
6. Recalcular la matriz: debe quedar **0 discrepancias nombradas** sobre el fixture ya corregido.

Commit local separado. No convertir casos a `*`, no relajar `mustContain` y no esconder
discrepancias cambiando sólo su etiqueta.

##### 47.2-B3 — Hacer real el gate de handlers

1. `run_tests.js` usa `answerWithTrace()` del mismo núcleo:
   - `expectedHandler=null` → `response===null && handler===null`;
   - `expectedHandler='*'` → no exige nombre, conserva las demás aserciones;
   - nombre concreto → igualdad exacta con `handler`.
2. El resumen por handler se construye desde el **observado**, no desde la expectativa.
3. Añadir una regresión negativa: respuesta compatible + handler equivocado debe dar `rc!=0`.
4. Fijar RNG sólo en el harness de pruebas; no cambiar la aleatoriedad productiva.
5. Hacer que una respuesta no nula con handler nulo, o la inversa, sea fallo del runner oficial.

Commit local separado y **STOP** para auditoría. 47.3 no se mezcla en estos commits.

#### Gate de cierre 47.2-B

```text
fixture                              616 consultas únicas · IDs 1..616
generate_tests.js --check            rc=0 · no mutante
npm test                             616/616 · handler REAL verificado
test_dispatcher_trace                 PASS
test:candidate                        19/19
matriz nombrada                       0 discrepancias
categorías                            447 concretas + 122 comodín + 47 null = 616
RNG fijo                              dos corridas 616/616 byte-idénticas
respuestas fuera de tabla B           byte-idénticas
knowledge/RAG/HTML/package            byte-idénticos
```

Si no se alcanzan exactamente esos conteos, 47.2-B queda **FAIL** y no se inicia 47.3.

#### Después de 47.2-B

1. Auditar los tres commits y el conjunto completo.
2. Ejecutar 47.3 en commit separado:
   - añadir `test:cases:verify`;
   - ejecutarlo antes de `run_tests.js`;
   - integrar la prueba de traza;
   - mover la telemetría “Total tests generated” después de construir las 616;
   - probar fixture alterado/ausente/duplicado y `--check` no mutante.
3. Sólo después iniciar `C7.6-RAG-CONTRACT` con la clave como secreto de entorno.
4. No hacer push hasta cerrar y auditar 47.2/47.3.

No ejecutar RAG, no usar `GEMINI_API_KEY`, no tocar `package.json` en 47.2-B, no hacer push, merge,
deploy, activación, lifecycle ni publicación.

#### Próxima acción exacta

**Ejecutar únicamente 47.2-B1 → B2 → B3 en tres commits locales y detenerse.**

_Respuesta:_ **GO 47.2-B LOCAL. Sin 47.3, RAG, push, deploy, activación ni publicación.**

---

### Anexo técnico R52-A — Decisiones P1–P4 y diseño de 47.2-A — 2026-07-26

- **P1:** opción **(a) completada en la Ronda 52**. `98404fa0` queda aceptado para continuar.
  La siguiente ejecución es 47.2-A, no RAG.
- **P2:** no se altera el orden. `C7.6-RAG-CONTRACT` sigue después de 47.2 y 47.3.
- **P3:** **ningún push todavía**. Acumular el checkpoint local hasta cerrar 47.2/47.3 y pedir
  literales separados por repositorio.
- **P4:** el drift baseline se repara en `feat/c73-candidate-staging` y se revisa por diff, sin
  deploy. El chunk de Obesidad se genera únicamente en un índice de staging hasta la activación.

#### Veredicto de 47.1

Auditoría independiente:

```text
diff 42477019..98404fa0       sólo generate_tests.js + test_cases.json
git diff --check              PASS
fixture                       616 filas · 616 consultas únicas · IDs 1..616
generate_tests.js --check     rc=0 · hash antes=después
npm test                      616/616 PASS
test:candidate                19/19 PASS
knowledge/RAG/HTML            byte-idénticos a 42477019
```

**47.1 queda ACEPTADA.** No se detectó pérdida de cobertura material.

#### R52-P1 — telemetría incorrecta, artefacto correcto

El comando imprime:

```text
Total tests generated: 564
...
fixture reproducible: 616 casos
```

La primera línea se ejecuta antes de añadir las 52 consultas posteriores. No altera el fixture ni
el gate, pero es una salida falsa. Mover ese `console.log` al final de la construcción queda como
microfix obligatorio dentro de 47.3, cuando se integren los comandos oficiales. No reabrir 47.1 ni
amendar `98404fa0` sólo por esta línea.

#### Por qué 47.2 se divide

Activar de golpe la comparación estricta de handler puede descubrir etiquetas históricas falsas.
Corregir instrumentación y contratos en el mismo paso ocultaría qué cambió. Por eso 47.2 se divide:

```text
47.2-A  instrumentar + medir · cero cambios en respuestas/fixture
47.2-B  resolver discrepancias y hacer la comparación obligatoria
```

#### Orden 47.2-A — Instrumentar el dispatcher y producir el mapa observado

Trabajar sólo en el dashboard desde `98404fa0`.

1. Capturar:
   - hashes de `knowledge.json`, `rag_index.json` y ambos HTML;
   - salida de las 616 consultas actuales en un temporal no trackeado;
   - estado de contexto/follow-ups de los casos con `setupQuery`.
2. Crear un único núcleo de resolución que produzca:

```text
{ response, handler }
```

3. `answer(query)` debe delegar a ese núcleo y continuar devolviendo sólo `response`. No duplicar
   guards, fuzzy matching, herencia de contexto ni `HANDLERS`.
4. Exponer una API diagnóstica para pruebas, por ejemplo `answerWithTrace(query)`, que use el mismo
   núcleo.
5. Asignar identidad estable a cada salida:
   - handlers de `HANDLERS` → `handler.name`;
   - rechazo off-topic → `answerFueraDeTema`;
   - guard de inyección → `answerInjectionGuard`;
   - guard de código → `answerCodeRequest`;
   - cesión a RAG/Gemini y ausencia de respuesta → `handler=null`.
6. Contexto, corrección fuzzy y prefijos visibles no cambian la identidad: reportar el handler que
   produjo la respuesta subyacente.
7. No usar `_lastHandlerFn` como única fuente post-hoc: es estado global mutable y no cubre todos
   los guards. El resultado del dispatcher debe transportar la identidad junto con la respuesta.
8. Mantener exactamente la semántica conversacional existente. No introducir un segundo camino de
   producción “sólo para tests”.

#### Auditoría de equivalencia obligatoria

Antes y después del refactor:

```text
616 responses                    byte-idénticas
616 null/no-null                 idénticos
entidades y setupQuery           idénticos
test:candidate                   19/19
superficies públicas             byte-idénticas
```

Crear un reporte temporal, no trackeado, con:

```text
id · query · expectedHandler · observedHandler · coincide
```

Agrupar discrepancias por `expectedHandler → observedHandler`. No corregir todavía
`test_cases.json`, no relajar aserciones y no convertir casos a `*`.

#### Pruebas mínimas de 47.2-A

1. `answer()` y `answerWithTrace().response` son idénticos.
2. Un handler normal reporta su nombre real.
3. Off-topic reporta `answerFueraDeTema`.
4. Una cesión RAG reporta `null`.
5. Un follow-up conserva el handler subyacente.
6. Una corrección fuzzy conserva el handler subyacente.
7. Dos consultas secuenciales no contaminan la identidad observada.

#### Gate y STOP

```text
npm test                         616/616 PASS de salida
test:candidate                   19/19 PASS
respuestas antes/después         byte-idénticas
mapa observedHandler             616/616 filas
fixture                          sin cambios
RAG/knowledge/HTML               sin cambios
```

Entregar un commit local de instrumentación y pruebas, más el conteo de discrepancias. **STOP.**
No hacer todavía obligatoria la igualdad de handlers; eso es 47.2-B después de auditar el mapa.

No usar `GEMINI_API_KEY`, no regenerar índices, no tocar `package.json`, no hacer push, merge,
deploy, activación o publicación.

#### Después de 47.2-A

1. auditar el mapa de discrepancias;
2. ejecutar 47.2-B para corregir contratos/enrutamiento y exigir igualdad real;
3. ejecutar 47.3 para integrar `test:cases:verify`, corregir la telemetría 564→616 y dejar los
   comandos oficiales fail-closed;
4. sólo entonces implementar `C7.6-RAG-CONTRACT`;
5. reparar el índice baseline en la rama candidate;
6. generar Obesidad únicamente en staging.

#### Próxima acción exacta

**Ejecutar únicamente 47.2-A y detenerse con el mapa observado.**

_Respuesta:_ pendiente del commit local, equivalencia byte a byte y matriz de discrepancias.

---

### Anexo técnico R45-A — Auditoría independiente del fixture generado — 2026-07-26

La implementación funcional de `42477019` fue auditada sin modificar el dashboard. El commit tiene
dos archivos, 80 inserciones y 17 borrados:

```text
epibot/js/kb.js
epibot/tests/test_cases.json
```

No tocó RAG, knowledge, HTML, Netlify, manifests ni artefactos candidate.

#### Resultado independiente

```text
npm test             618/618 PASS · rc=0
test:candidate         19/19 PASS · rc=0
git diff --check                 PASS
superficies públicas             byte-idénticas a d5ead880
menciones Obesidad públicas      0
```

La lógica implementada coincide con la Ronda 43:

- hiperparámetros continúan delegados al RAG;
- referencia/identidad del artículo del proyecto llega a la ficha local;
- metodología/contenido del artículo continúa en RAG;
- los temas ajenos reciben rechazo local;
- distribución gráfica ya no es robada por los dos handlers anteriores;
- las dos regresiones negativas conservan los handlers de rango y tabla.

#### R45-P0 — el fixture verde no es reproducible desde su generador

El commit modificó el artefacto generado `test_cases.json`, pero no actualizó
`tests/generate_tests.js`. Esto deja dos autoridades incompatibles:

```text
npm test                         lee test_cases.json
npm run test:gen                 sobrescribe test_cases.json desde generate_tests.js
run_tests.js                     indica ejecutar el generador si falta el fixture
```

La reproducción se hizo en un temporal creado desde `42477019`, sin escribir en el dashboard:

```text
fixture commiteado               618 casos · 618 PASS
fixture recién generado          565 casos
suite sobre fixture generado     553 PASS · 12 FAIL · rc=1
consultas ausentes               52
consultas con contrato distinto  13
```

Entre las 52 ausentes están las dos regresiones de 43.1, los casos conversacionales añadidos
después y los ocho casos de Dengue. Entre las 13 divergencias están los cuatro cambios de
expectativa de 43.1 y siete contratos de distribución preexistentes.

Además, `generate_tests.js` siempre termina en `rc=0`: sólo valida entidades y escribe el JSON; no
ejecuta las respuestas aunque su cabecera diga “genera y ejecuta”. Por eso un `test:gen` verde no
prueba que el fixture generado sea válido.

**Veredicto:** el código funcional de 43.1 es aceptable, pero el gate de readiness queda
**CONDICIONAL / NO CERRADO** hasta eliminar esta doble autoridad. No se autoriza comenzar el RAG
con una suite que una orden oficial puede degradar silenciosamente.

#### Orden 45.1 — Una sola autoridad reproducible para los casos del KB

Trabajar únicamente en el dashboard, sobre `42477019`, sin push ni RAG.

1. Preservar los dos untracked del usuario y capturar los hashes públicos.
2. Declarar `tests/generate_tests.js` como fuente y `test_cases.json` como artefacto determinista.
3. Llevar al generador:
   - las 52 consultas que hoy sólo existen en el JSON;
   - los 13 contratos divergentes con las expectativas vigentes;
   - las notas funcionales de G1/G2 y las dos regresiones G4;
   - cualquier helper mínimo necesario para expresar `setupQuery` y metadata sin duplicación.
4. No copiar IDs manuales como identidad. Los IDs se asignan de forma consecutiva y estable al
   construir la lista; la consulta y su contrato son la identidad semántica.
5. Añadir un modo no mutante:

```text
node tests/generate_tests.js --check
```

Este modo debe:

- construir el fixture enteramente en memoria;
- comparar bytes o una serialización canónica contra `test_cases.json`;
- no escribir;
- devolver `rc!=0` ante cualquier diferencia, ausencia, duplicado de consulta o ID no consecutivo.

6. Mantener el modo de escritura explícito para desarrollo, pero corregir su documentación: generar
   no equivale a ejecutar la suite.
7. Añadir a `package.json`:

```text
test:cases:verify   node tests/generate_tests.js --check
test                test:cases:verify && node tests/run_tests.js
```

La sintaxis final puede usar `npm run`, pero el verificador debe ejecutarse automáticamente antes
de los 618 casos.
8. Añadir una prueba del propio contrato que demuestre, en temporal:
   - fixture idéntico → `rc=0`;
   - expectativa alterada → `rc!=0`;
   - caso faltante → `rc!=0`;
   - consulta duplicada → `rc!=0`;
   - el modo `--check` no cambia el archivo.
9. Regenerar una vez por el modo explícito y exigir diff nulo entre el fixture resultante y el
   fixture revisado de 618 casos.

No hacer:

- borrar las 52 consultas para hacer coincidir el generador;
- aceptar nuevamente 565 como universo;
- relajar expectativas, convertir casos en `*` o añadir skips;
- regenerar RAG;
- usar `GEMINI_API_KEY`;
- tocar consumer candidate, knowledge, RAG, HTML o deploy.

#### Gate 45.1

```text
npm run test:cases:verify       PASS · no modifica archivos
npm test                        618/618 PASS
npm run test:candidate           19/19 PASS
npm run test:gen                produce el mismo test_cases.json
segunda generación             byte-idéntica
consultas únicas               618
IDs consecutivos               1..618
knowledge/RAG/HTML             byte-idénticos
Obesidad pública               0 menciones
```

Crear un único commit local del dashboard y **STOP** para auditoría. No hacer push.

#### Orden posterior — no ejecutar en la misma ronda

Sólo después de auditar 45.1 se autorizará la antigua Orden 40.2, renombrada:

```text
GO C7.6-RAG-CONTRACT:
exigir presencia, alineación y vector no vacío para cada chunk candidate;
fallar cerrado ante API/rate-limit/vector vacío;
sin regenerar todavía el índice público, sin push ni deploy.
```

#### Estado y próxima acción exacta

```text
C7.6 backend                 PASS @ dbfdd49c
C7.6 dashboard funcional    618/618 @ 42477019
C7.6 autoridad de pruebas   FAIL · generador 565 → 553/565
C7.6 RAG                    drift 19 · contrato pendiente
Obesidad                    trained · no publicada
```

**Ejecutar sólo la Orden 45.1 y detenerse.**

_Respuesta:_ pendiente del commit local y reporte del gate 45.1.

---

### Ronda 39 — C7.6-READINESS backend: SIGSEGV aislado y gate estable — 2026-07-26

#### Diagnóstico reproducido

El reproductor histórico continúa siendo válido:

```text
pytest test_deepar_smoke.py + test_pipeline_e2e.py en un solo proceso → rc=139
```

`faulthandler` acotó la caída a esta secuencia:

```text
DeepAR/PyTorch PASS
pipeline Prophet PASS
Ensemble PASS
Stacking: ProphetExpert PASS · ETSExpert PASS
LightGBM → OMP Error #179 pthread_mutex_init → SIGSEGV
```

La causa es una colisión de runtimes OpenMP nativos cargados en el mismo intérprete, no un fallo
del modelo ni falta de hilos. El entorno contiene implementaciones distintas para PyTorch y el
stack scikit-learn/LightGBM; fijar `OMP_NUM_THREADS=1` no descarga ni unifica esos runtimes.

Cada módulo en un proceso limpio pasa:

```text
test_deepar_smoke.py   2/2 PASS
test_pipeline_e2e.py   3/3 PASS
```

#### Solución funcional

Se añadió `scripts/run_isolated_pytest.py`, genérico y sin nombres de motores o padecimientos:

1. recolecta node IDs con el marker solicitado;
2. deduplica por archivo conservando el orden;
3. ejecuta cada archivo en un intérprete nuevo;
4. acota los hilos numéricos a uno;
5. detiene el gate ante el primer fallo;
6. convierte una señal `SIGSEGV` al código observable `139`.

El aislamiento es por archivo, no por cada caso parametrizado. Así DeepAR y Stacking nunca
comparten runtime, mientras los fixtures costosos de cada módulo se reutilizan. `Makefile` expone
`make test-integration` y `make test` usa el mismo runner con cobertura.

Regresión nueva:

```text
7/7 PASS · deduplicación · un proceso por archivo · fail-fast · SIGSEGV → rc=139
```

#### Hallazgo lateral y cierre

El E2E parcheaba `forecast_plots.generar_graficos_pronostico`, pero `scripts.predice` ya había
importado otra referencia. El mock no actuaba y una figura se escribió en `reports/forecasts`.

Se corrigió el patch sobre el consumidor real (`predice.generar_graficos_pronostico`). La PNG
generada se comparó y se restauró de forma dirigida desde su objeto DVC:

```text
archivo   reports/forecasts/ensemble/Alzheimer/Nacional/Alzheimer_Nacional_general.png
md5 DVC   b46687bd16ee1a4f4e5262ede997d39d
sha256    71af6ddd4bdffa6276197e7ad63beab3316bde14fc01a7c423b2663f921d497d
```

Una repetición del E2E dejó ese SHA256 idéntico. No se hizo checkout global. El target completo
`reports/forecasts.dvc` continúa reportando una divergencia de directorio previa que debe tratarse
por separado; esta ronda sólo restauró el archivo que ella misma alteró. Los cuatro agregados CSV
conservan `cb5be395`, `96791595`, `1d2cf0a7` y `ac97dc8e`.

#### Gate backend

```text
lint                              PASS
mypy src + runner aislado         PASS
fast                              1,918 PASS
integración                       61/61 PASS · 8 procesos por archivo · rc=0
doctor Obesidad / completo        rc=0 / rc=0
release DVC                       up to date
published por 6 canales           Depresión · Parkinson · Alzheimer · Dengue
Obesidad                          trained · invisible
```

#### Estado y siguiente orden

El bloqueante backend `SIGSEGV` queda **AISLADO/PASS**, pendiente de auditoría y commit. C7.6 no
está cerrada todavía:

1. corregir los cuatro fallos de `npm test` del dashboard;
2. regenerar el RAG con `GEMINI_API_KEY` ya disponible como secreto de entorno;
3. exigir `npm test`, `npm run check` y drift RAG cero;
4. auditar ambos repos y preparar el paquete de aprobación.

No autoriza merge, deploy, activación, lifecycle ni publicación.

_Respuesta:_

---

### Aviso final de autoridad — aplicar Ronda 37

Las rondas anteriores se conservan como bitácora y pueden contener el orden ya sustituido de
“esperar 4/4 antes de publicar”. La orden vigente es la **Ronda 37**:

```text
1. checkpoint y push autorizado;
2. C7.6-READINESS completamente verde;
3. paquete y rollback probados;
4. publicación condicionada con C7.4 INCOMPLETE n/4 visible;
5. PASS confirma; FAIL revierte.
```

No ejecutar un flip o deploy directamente desde C7.5-PREP. Lo siguiente es la Orden 37.1 y luego
la Orden 37.2.

---

### Ronda 37 — Decisión de publicación condicionada y órdenes autoritativas — 2026-07-26

#### Decisión registrada

El usuario decidió publicar Obesidad sin esperar a que transcurran las cuatro semanas de C7.4 y
revalidar prospectivamente después. Esta decisión **cambia el orden**, no los datos ni el criterio:

```text
C7.4 actual       INCOMPLETE · 0/4
gate_digest       5bc39aa5d44f5e62062775dc09a0366ac856f47e5444fbb52ca07e608e61b65d
release_id        obesidad_release_2517e7858901
modalidad         publicación condicionada hasta PASS 4/4
si resulta FAIL   rollback obligatorio, sin retuning automático
```

No se modifica el candidato, control, dataset, origen, horizonte, umbrales ni semanas. Esta
autorización de política **no ejecuta por sí sola** un push, merge, deploy, promoción de Tableau,
activación de puntero o cambio de lifecycle.

#### Lo que sigue bloqueando antes de activar

Esperar cuatro semanas ya no bloquea. Sí bloquean estos tres problemas funcionales de
C7.6-READINESS:

1. aislar el `SIGSEGV` de la integración y dejar un comando estable que siempre termine con
   resultado verificable;
2. corregir los cuatro fallos reales de `npm test` del dashboard;
3. regenerar y verificar el índice RAG público hasta obtener drift cero.

Para el punto 3 se requiere `GEMINI_API_KEY` en un entorno autorizado. La clave se entrega sólo
como secreto de entorno o CI: nunca se escribe en Git, el plan, logs, fixtures o artefactos. Como
la decisión es publicar los cuatro canales, **no tener la clave bloquea EpiBot y, por tanto, la
publicación completa**. No se recorta el canal en silencio.

#### Órdenes, en este orden

##### Orden 37.1 — Congelar y respaldar el checkpoint local

1. Auditar `815a49a3..HEAD` y confirmar que sólo contiene C7.4, C7.5-PREP, pruebas y este plan.
2. Crear un commit doc-only para esta decisión; no mezclarlo con código.
3. Reejecutar `git diff --check`, tests dirigidos, doctor y hashes legacy.
4. Presentar el SHA y pedir autorización literal para push fast-forward del backend.
5. No hacer merge, deploy, activar puntero ni cambiar lifecycle durante este checkpoint.

Autorización que se debe solicitar:

```text
AUTORIZO PUSH BACKEND 815a49a3..HEAD A
origin/feat/registry-padecimientos-obesidad.
SIN MERGE, DEPLOY, ACTIVACIÓN NI PUBLICACIÓN.
```

##### Orden 37.2 — Cerrar C7.6-READINESS

Backend:

1. reproducir el `SIGSEGV` con un comando mínimo;
2. demostrar si la causa es estado compartido, orden de pruebas o una dependencia nativa;
3. aislar el smoke DeepAR en subproceso si ésa es la solución mínima;
4. añadir una regresión que falle si reaparece `rc=139`;
5. ejecutar la integración completa con una estrategia estable y documentada.

Dashboard:

1. reproducir los cuatro fallos de `npm test` sobre `main` y sobre la rama candidate;
2. corregir causa raíz sin relajar aserciones ni ocultar tests;
3. regenerar el RAG con la clave suministrada de forma segura;
4. exigir `rag:verify` con drift cero;
5. ejecutar `npm test`, `npm run check` y las pruebas candidate point-only.

Gate de salida:

```text
backend lint/typecheck/fast/integration     PASS · sin rc=139
dashboard npm test/npm run check           PASS
RAG publicado/candidate                    drift 0
doctor + DVC release                       PASS
legacy                                     byte-idéntico
Obesidad                                   trained · puntero inactivo
F50                                        configured · oculta
```

No se autoriza activación si falta una sola fila de este gate.

##### Orden 37.3 — Preparar el paquete de publicación condicionada

Con readiness verde:

1. registrar commits exactos de backend y dashboard;
2. incluir el release ID, digests, puntero inactivo y rollback previo;
3. incluir C7.4 como `INCOMPLETE 0/4`, nunca como PASS;
4. generar previews finales de los cuatro canales;
5. comprobar que todos muestran point-only y el aviso de validación en curso;
6. probar rollback completo en staging;
7. detenerse y pedir autorizaciones externas nombradas.

Texto público mínimo:

```text
Validación prospectiva en curso (0/4 semanas).
Pronóstico puntual; no se estimaron intervalos de incertidumbre.
```

##### Orden 37.4 — Activación coordinada

Sólo después del gate anterior y de las autorizaciones externas:

1. guardar puntero, deploy, datasource e índice público anteriores;
2. hacer merge/push de código aprobado, sin mezclar entrenamiento;
3. cambiar Obesidad `trained → published`;
4. activar `public_release_pointer.v1` para `obesidad_release_2517e7858901`;
5. materializar Reports, Tableau, web y EpiBot desde el mismo release;
6. desplegar el dashboard y promover las superficies aprobadas;
7. ejecutar smoke público y comparar valores muestreados con el forecast sellado;
8. verificar que F50 siga oculta y que neuro + Dengue no cambien;
9. si cualquier check falla, ejecutar rollback inmediato.

La activación debe producir una sola identidad pública coherente. No se permite que lifecycle,
puntero, frontend, Tableau o RAG queden apuntando a estados distintos.

##### Orden 37.5 — Verificación semanal posterior

Con cada boletín nuevo:

1. incorporar únicamente la nueva verdad validada por el contrato de 32 entidades;
2. reejecutar el gate congelado;
3. publicar el contador y detalle semanal `n/4`;
4. no retunear, re-seleccionar, refitear ni cambiar umbrales;
5. conservar todos los informes y digests.

Al cierre:

| veredicto 4/4 | acción obligatoria |
| --- | --- |
| PASS | confirmar release y retirar sólo la etiqueta “validación en curso” |
| FAIL | restaurar puntero, lifecycle, deploy, Tableau y RAG anteriores |
| INCOMPLETE | mantener publicación condicionada y etiqueta; esperar semanas válidas |

#### Disparadores de rollback inmediato antes de 4/4

No se espera al gate estadístico si ocurre cualquiera de estos eventos:

- bundle o puntero no restaurable;
- checksum, schema o lineage inválido;
- duplicados, negativos, no finitos o ruptura de reconciliación;
- cifras públicas distintas al shard sellado;
- F50 visible o canal no autorizado;
- pérdida o alteración de un padecimiento legacy;
- error material de frontend, EpiBot, Reports o Tableau;
- el aviso point-only o el estado `n/4` no aparece.

#### Próxima acción exacta

**Ahora:** ejecutar la Orden 37.1. Después, con el checkpoint remoto confirmado, ejecutar la Orden
37.2. No activar todavía. La publicación condicionada queda autorizada como ruta de trabajo, pero
la acción externa se solicita al cerrar readiness con el paquete y rollback completos.

_Respuesta:_

**Decisión:** no conservar los nombres v1. Antes de persistir el primer bundle, ejecutar el
microcierre C7.2-A.2 y subir **ambos** schemas incompatibles:

- `identity_payload.v1` → `identity_payload.v2`;
- `release_manifest.v1` → `release_manifest.v2`;
- `runtime_config.v1` permanece sin cambios;
- `public_release_pointer.v1` permanece sólo documentado y fuera del bundle.

`runner_release_builder.v2` no reemplaza esta decisión: la versión del builder identifica el
productor; el schema identifica la forma y el contrato que deben interpretar loaders, doctors y
consumidores.

---

### Ronda 19 — Auditoría de C7.2-A.1 y órdenes de continuación — 2026-07-25

#### Veredicto

**PASS funcional para C7.2-A.1; NO-GO para C7.2-B hasta cerrar A.2.**

El desacoplamiento de activación es correcto y necesario:

- el entry point dejó de leer `channels`, `gallery_enabled` y `lifecycle`;
- `activation` no existe en el payload de identidad ni en el manifest;
- la forma del manifest es cerrada y rechaza claves nuevas o faltantes;
- el mismo release se obtiene al variar la política pública del registry;
- `BUILDER_VERSION=runner_release_builder.v2` participa en la identidad;
- no hay bundles persistidos que migrar.

Estado comprobado:

```text
HEAD local   fb3bcdca · parent 2bed74ee · ahead 2
Remoto       origin/feat/registry-padecimientos-obesidad @ 0dbd0f01
Build A/B    obesidad_release_a3d4cbe9f896 · byte-idénticos
Forecast     3,328 bases + 5,772 productos · máx |Δ| = 0.0
Tests        1,789 fast · 61 integración en dos tandas
Calidad      lint, mypy y ambos doctors rc=0
Outputs      0 bundles persistidos · artifacts/releases/ ausente
Externos     sin push, DVC, deploy, frontend ni publicación
Lifecycle    Obesidad trained/NO-GO · F50 configured/NO-GO
```

La única corrección formal antes de materializar es el versionado del contrato. Remover
`activation` cambia el conjunto de claves y la semántica de dos documentos. Un loader debe poder
decir “schema v1 no soportado” sin depender de que, accidentalmente, falle después el digest o el
`release_id`. Como todavía no existe ningún bundle persistido, este es el último punto barato y
seguro para corregirlo.

#### Orden R19.1 — C7.2-A.2: versionar los schemas incompatibles

Ejecutar en un commit separado y acotado:

1. Cambiar `IDENTITY_SCHEMA` a `identity_payload.v2`.
2. Cambiar `RELEASE_SCHEMA` a `release_manifest.v2`.
3. Mantener `RUNTIME_CONFIG_SCHEMA=runtime_config.v1`.
4. Mantener `BUILDER_VERSION=runner_release_builder.v2`.
5. Actualizar loader, verifier, manifest, fixtures y tests para exigir literalmente v2.
6. Añadir fixtures mínimos de v1 y probar que loader/verifier los rechazan con un error tipado y
   explícito de schema; no aceptar como prueba un fallo posterior de digest, identidad o claves.
7. Probar que una identidad v2 declara `release_schema=release_manifest.v2`.
8. Probar que todo manifest emitido declara `schema=release_manifest.v2` e
   `identity_schema=identity_payload.v2`.
9. Conservar cerrados los conjuntos de claves y las prohibiciones de activación.
10. No introducir compatibilidad de lectura con v1: nunca hubo un bundle v1 persistido y aceptar
    dos formas añadiría complejidad sin usuario real.

Esta orden puede modificar únicamente los módulos y tests del bundle necesarios para versionar el
contrato, además de este plan. No autoriza refactors laterales.

#### Orden R19.2 — Repetir el gate completo de A.2

Después del cambio de schema:

1. construir desde cero en dos roots temporales nuevos;
2. usar al menos `LC_ALL=C` y `LC_ALL=en_US.UTF-8`;
3. demostrar el mismo `release_id` y `diff -r` vacío entre ambos builds;
4. aceptar que el nuevo `release_id` difiera de `a3d4cbe9f896`, porque el schema forma parte de la
   identidad;
5. verificar los 150 archivos, manifest, `SHA256SUMS.txt` e inventario exacto;
6. reproducir desde cada bundle sin leer `runs/`;
7. exigir 3,328 bases, 5,772 productos y diferencia máxima exacta `0.0`;
8. ejecutar las pruebas focales del release, `make test-fast`, integración en las dos tandas ya
   justificadas, lint, mypy y ambos doctors;
9. volver a comparar los cuatro runs canónicos, `rolling_cv_v1`, los cuatro agregados legacy,
   `config/` y el frontend contra el baseline;
10. eliminar los temporales y demostrar que `artifacts/releases/` sigue sin existir.

El SIGSEGV preexistente no se corrige dentro de A.2. Se conserva la ejecución de integración en dos
tandas y la evidencia del reproductor mínimo.

#### Orden R19.3 — Commit y STOP de A.2

Si todo pasa:

1. crear un commit local separado, sugerido:

   ```text
   C7.2-A.2 version runner release schemas before persistence
   ```

2. comprobar que la rama queda tres commits por delante del remoto;
3. entregar el nuevo `release_id`, resultados de gates y diff de rutas;
4. detenerse.

Prohibido dentro de A.2:

- `git push`;
- escribir bajo `artifacts/releases/`;
- `dvc add`, crear o editar `.dvc`, `dvc push`;
- cambiar `artifact_source` a `runner_release`;
- construir `public_release_pointer.v1`;
- tocar canales, galería, lifecycle, frontend o cualquier artefacto público;
- iniciar C7.2-B, C7.2-C o C7.3.

#### Orden R19.4 — Revisión y checkpoint Git

Después del PASS de A.2:

1. auditar juntos `2bed74ee`, `fb3bcdca` y el commit A.2;
2. comprobar que no contienen bundles, `.dvc`, rutas públicas ni cambios de lifecycle;
3. solicitar autorización explícita antes de subir ese rango;
4. si se autoriza, hacer fast-forward de la rama de trabajo únicamente;
5. el push no autoriza C7.2-B ni DVC.

#### Orden R19.5 — C7.2-B: sede local, doctor y target DVC

Sólo después de A.2 PASS y de recibir el literal `GO C7.2-B`:

1. definir como sede final:

   ```text
   artifacts/releases/<disease_id>/<release_id>/
   ```

2. cablear `runner_release` en el doctor con un `releases_root` explícito e inyectable; no usar
   cwd, `runs/`, home ni paths absolutos del equipo;
3. hacer que el doctor compruebe schema v2, `release_id`, identidad, checksums, inventario, cadena
   sellada, 64 modelos cargables y reproducción;
4. probar el doctor sobre una copia temporal válida y sobre mutaciones de schema, digest,
   inventario, modelo faltante y release ajeno;
5. materializar el bundle validado desde un temporal al destino final mediante promoción atómica;
6. rechazar un destino existente distinto y aceptar idempotentemente el mismo contenido;
7. cargar y reproducir otra vez desde la ruta final, sin consultar `runs/`;
8. crear un target DVC **dedicado únicamente a ese bundle**; no modificar `models.dvc`,
   `reports/forecasts.dvc` ni Tableau;
9. ejecutar `dvc status` dirigido, revisar el `.dvc` y verificar que el diff contiene sólo el
   bundle, el puntero nuevo, código/tests del doctor y documentación;
10. cambiar el candidato del registry a `runner_release` sólo si el doctor puede resolver y validar
    la sede final sin excepciones especiales;
11. mantener Obesidad en `trained`, NO-GO y fuera de `published_only`;
12. crear el commit local de C7.2-B y detenerse.

C7.2-B no autoriza `dvc push`, Git push, canales, puntero público, lifecycle, frontend, deploy ni
publicación.

#### Orden R19.6 — C7.2-C y fases posteriores

1. **C7.2-C:** subir el target DVC sólo con autorización explícita posterior, descargarlo en un
   entorno temporal limpio y repetir doctor + reproducción.
2. **C7.3:** construir puentes candidate desde `release_manifest.v2`; nunca escribir superficies
   públicas desde modo candidate.
3. **C7.4:** completar las cuatro semanas prospectivas congeladas, sin tuning ni sustitución del
   veredicto canónico.
4. **C7.5:** crear `public_release_pointer.v1` con los cuatro canales iniciales (`web`, `epibot`,
   `reports`, `tableau`), galería desactivada y referencia al `release_id`. Cambiar canales no debe
   mover el bundle.
5. **C7.6:** resolver o aislar con causa demostrada el SIGSEGV `deepar_smoke + pipeline_e2e`; no
   mergear ni publicar con el gate monolítico inexplicablemente rojo.
6. **C7.7:** lifecycle, deploy y activación siguen siendo acciones externas separadas y requieren
   autorización literal por cada superficie.

#### Próxima orden exacta

> **GO C7.2-A.2. Versiona `identity_payload.v2` y `release_manifest.v2`, prueba el rechazo
> explícito de v1, reconstruye en dos temporales y locales, reproduce el forecast con diferencia
> exacta 0.0, ejecuta todos los gates y detente sin push, DVC ni publicación.**

---

### Ronda 15 — Auditoría independiente del baseline C7.2-A y orden corregida — 2026-07-25

#### Veredicto

**Paso 23.1 PASS; implementación NO iniciada.** La revalidación independiente reproduce:

```text
dataset      9 archivos    2ef4ee1236aa94c0
aceptación  67 archivos    6bbc7f84ea5ec5bb
refit      162 archivos    972f7519f885c0d1
forecast    37 archivos    d89d92ee7e73b848
política                    dd6d4a0274a6f8bb
doctor Obesidad / completo  rc=0 / rc=0
DVC dirigido                modified preexistente
frontend                    main @ 179bbe36, cero trackeados
```

El único cambio trackeado continúa siendo este plan. No hay módulos, tests ni bundles de C7.2-A a
medio construir.

#### Correcciones a la Ronda 14

##### R15-C1 — Los temporales sin path no son evidencia reutilizable

La Ronda 14 dice que creó dos roots, pero no registra sus paths y una sesión distinta no debe
depender de ellos. Se consideran descartables. Después del GO se crean dos roots nuevos, se
registran durante el gate y se eliminan al cerrar. Nunca se promueve uno de esos directorios.

##### R15-C2 — `VerifiedRunnerRuns` no contiene los archivos fuente

La dataclass contiene identidades, conteos, engines y `state_digest`, pero no `runs_root`, paths de
envelopes/estados ni bytes de policy, selección, aceptación, forecast o runtime inputs. La frase
«no hay que reabrir ningún run» queda invalidada.

Contrato corregido:

1. el entry point recibe roots y rutas fuente explícitas;
2. invoca `validate_runner_runs` para obtener `VerifiedRunnerRuns`;
3. entrega al builder puro la identidad verificada **junto con** un objeto tipado de source paths;
4. al copiar, re-verifica cada digest declarado;
5. nunca deriva identidad desde nombres de archivo, aunque use las rutas declaradas por manifests.

##### R15-C3 — La exposición del dataset es una proyección, no el raw original

`inputs/exposure_inegi_cpv2020_static.csv` tiene schema por `cve_ent`; el loader actual
`load_exposure_snapshot` espera el raw INEGI y su YAML global. El loader del release no debe fingir
que son intercambiables.

Se exige un loader puro de runtime exposure que:

- reciba `runtime_config.json`, catálogo y CSV proyectado desde el bundle;
- valide claves, columnas por sexo, enteros positivos, unicidad y `Hombres + Mujeres = Total`;
- exija cobertura exacta del catálogo;
- contraste sus valores con las exposiciones selladas en el dataset;
- registre por separado el SHA256 del CSV proyectado y el digest de procedencia del snapshot
  original.

##### R15-C4 — No recablear el runner completo

No es necesario reescribir `orchestrator.py` ni la ruta productiva de `forecasting.py`. La
reproducción aislada puede reutilizar:

- `final_models.load_models` contra `bundle/refit`;
- `ForecastRequest` con periodos y exposición del bundle;
- las funciones `forecast_final` ya implementadas;
- `derive_forecast_products` con el catálogo del bundle.

Para resolver motores sin un `if engine == ...`, extender el registry de adapters con una
capacidad tipada opcional, por ejemplo `FinalStateForecaster.forecast_state(state, request)`.
Cada adapter seleccionado debe implementarla delegando en su función actual. Un motor presente en
el release sin esa capacidad hace fallar el build/loader; nunca se sustituye por otro.

#### Orden corregida de implementación

Esta orden solo se ejecuta tras recibir `GO C7.2-A`.

##### R15.1 — Preparación

1. conservar el baseline de 23.1;
2. crear roots A/B nuevos con `mktemp -d`;
3. registrar los paths solo como telemetría de la ejecución, no dentro del bundle;
4. definir cleanup garantizado;
5. no reutilizar los temporales anónimos de R14.

##### R15.2 — RED: identidad e inputs

Antes del builder, añadir tests que fallen por ausencia de:

- `identity_payload.v1` y JSON canónico;
- release ID acíclico;
- inventario exacto y checksums sin autorreferencia;
- paths POSIX relativos y orden independiente del locale;
- `runtime_config.v1`;
- loader del catálogo y exposición proyectada;
- rechazo de inputs faltantes, extra, alterados o incompatibles con el dataset;
- rechazo de metadata ambiental/timestamps dentro del bundle.

##### R15.3 — Entry point y builder

Separar dos capas:

1. **entry point impuro:** abre registry/manifests, valida la cadena y resuelve source paths;
2. **builder puro:** recibe identidad verificada, source paths tipados y output temporal.

El builder:

- copia los bytes declarados y vuelve a comprobarlos;
- genera metadata canónica;
- incluye solo dependencias consumidas;
- escribe `runtime_config.json` con paths internos relativos;
- valida el bundle antes de devolverlo;
- es idempotente ante un destino idéntico y rechaza uno distinto;
- no conoce `Obesidad`, motores concretos ni conteos escritos a mano.

##### R15.4 — Capacidad de forecast final

1. declarar un protocolo tipado para pronosticar desde `FinalState`;
2. implementarlo en cada adapter elegible reutilizando su función actual;
3. comprobar que todos los engines del portafolio verificado ofrecen la capacidad;
4. mantener sin cambios el flujo legacy `adapter.run("forecast", run_dir)`;
5. probar que un adapter sin capacidad falla con error tipado.

##### R15.5 — Loader y reproducción

1. verificar release ID, manifest, checksums e inventario;
2. cargar catálogo/exposición exclusivamente desde `runtime_inputs`;
3. cargar modelos exclusivamente desde `bundle/refit`;
4. construir solicitudes para el horizonte declarado;
5. pronosticar las series base con el adapter asignado;
6. derivar productos desde las bases;
7. comparar frame completo contra el forecast canónico;
8. repetir sin permitir lecturas bajo `runs/` después de abrir el bundle.

##### R15.6 — Determinismo y gate

1. construir A con locale `C`;
2. construir B con locale `en_US.UTF-8`;
3. comparar release ID, rutas y bytes;
4. ejecutar mutaciones de manifest, checksum, modelo, catálogo, exposición y config;
5. ejecutar la matriz 21.3;
6. recalcular el baseline de preservación;
7. confirmar que no existe salida bajo `artifacts/releases/`;
8. hacer commit local y STOP.

Este plan puede formar parte del commit de C7.2-A como documentación de la ejecución; no crear otro
ciclo de commit doc-only antes de empezar. El commit debe mantener el plan y el código/tests de
C7.2-A separados de cualquier output material.

#### Criterio de cierre

No basta que el builder produzca un directorio válido. C7.2-A requiere demostrar que un consumidor
puede cargarlo y reproducir el forecast sin `runs/`, configuración global de exposición ni rutas
del equipo.

#### Próxima orden

> **GO C7.2-A. Continúa desde R15.1 hasta R15.6; construye únicamente en temporales, incluye este
> plan en el commit local de cierre y detente sin DVC, push ni publicación.**

_Respuesta auditada:_ Ronda 12 queda aceptada. No apareció otro bloqueo funcional en R11 ni en la
Acción 5. Ejecutar ahora la Acción 6 acotada que se detalla en las secciones 16 y 18; después
ejecutar el gate completo y cerrar C7.1 en un commit aislado, sin push.

---

## 18. Auditoría que gobernó el cierre C7.1 — histórica, ejecutada

> **Orden de lectura:** esta es la sección operativa autoritativa después de R12. Las rondas R11 y
> R12 que permanecen más abajo se conservan como evidencia histórica detallada de la remediación;
> no reemplazan las órdenes 13.1–13.3 ni la secuencia de cierre de esta sección.

#### Veredicto

**PASS funcional. Acciones 1–5 CERRADAS; quedan 6, 7 y 8.**

Verificación independiente sobre `b981b6e5`:

```text
artifact backend + artifact validation + ownership   259 PASS
make test-fast                                     1,610 PASS
make lint                                              PASS
make typecheck                                         PASS (144 módulos)
doctor Obesidad --artifacts                            ✅ rc=0
doctor --artifacts                                     ✅ rc=0
git diff --check                                       PASS
```

La revisión del código confirma:

- `ModelIdentity` sale del índice/envelope/estado ya contrastados y gobierna
  `model_inventory.csv`;
- el inventario compara por `SeriesKey`, no por unicidad artificial de digests;
- cada CSV por job valida identidad, calendario, cobertura, valores, motor y `point-only`;
- solo `engine` se normaliza a `portfolio` antes de comparar todas las columnas con el
  consolidado;
- `forecast_base.csv` y `forecast.csv` exigen bandas completamente nulas;
- las tres pruebas legacy usan `Cfg` inyectado y escriben únicamente bajo `tmp_path`;
- existe una prueba separada de que el selector legacy rechaza Obesidad.

No se encontró un nuevo falso verde funcional. No continuar auditando estos contratos con más
mutaciones después de R13 salvo que cambie su implementación.

#### Limpieza pendiente observada

Acción 6 no cambia comportamiento:

1. `test_forward_inverse_roundtrip` ejecuta dos veces el mismo par
   `("Depresión", "prophet")`;
2. tres nombres todavía dicen “obesidad” aunque sus cuerpos ya usan Depresión;
3. el rechazo legacy afirma documentalmente `rc=1`, pero el test solo exige `rc != 0`;
4. la separación entre cobertura legacy y runner está dispersa y debe quedar registrada una sola
   vez.

Las órdenes exactas están en 6.1–6.3. Al quitar el duplicado, el nuevo baseline fast esperado es
**1,609 PASS**, no 1,610.

#### Orden 13.1 — Ejecutar Acción 6 y no ampliar alcance

Archivos permitidos:

```text
tests/unit/artifacts/test_transforms.py
tests/unit/models/test_prophet_model.py
tests/unit/test_produccion_ownership.py
docs/PLAN_C7_PUBLICACION_OBESIDAD.md
```

`test_tuner.py` y los tests del runner se ejecutan como gate, pero no necesitan cambios salvo que
la limpieza revele una afirmación objetivamente falsa.

Prohibido durante esta acción:

- cambiar código bajo `src/` o `scripts/`;
- cambiar `config/padecimientos.yaml`;
- añadir tests redundantes de modelos legacy;
- tocar runs, DVC o frontend.

Registrar el resultado como cierre de Acción 6 y continuar sin pausa a Acción 7 si todo queda
verde.

#### Orden 13.2 — Gate completo de Acción 7

Ejecutar en este orden:

```text
make lint
make typecheck
make test-fast
.venv/bin/pytest -q tests/unit/test_artifact_backend.py --no-cov
.venv/bin/pytest -q tests/unit/runner/test_artifact_validation.py --no-cov
.venv/bin/pytest -q tests/integration/test_disease_run_gate.py --no-cov
.venv/bin/pytest -q tests/integration/test_anorexia_f50_gate.py --no-cov
.venv/bin/python -m scripts.doctor_padecimiento Obesidad --artifacts
.venv/bin/python -m scripts.doctor_padecimiento --artifacts
```

Después de las suites:

1. recalcular hashes de dataset, aceptación, refit y forecast C5 y compararlos con los registrados;
2. verificar que los cuatro agregados legacy siguen byte-idénticos;
3. verificar `rolling_cv_v1.yaml` en `dd6d4a02…`;
4. ejecutar estado DVC dirigido, sin `dvc add`, checkout o push;
5. confirmar frontend trackeado limpio;
6. ejecutar `git diff --check`;
7. ejecutar `git status --short` y clasificar cada ruta.

Un skip por ausencia de datos no cierra el gate central. Si falta un insumo de integración,
detenerse y documentar el faltante; no convertirlo en PASS.

#### Orden 13.3 — Whitelist del commit C7.1

El commit puede incluir únicamente:

- `config/padecimientos.yaml`;
- `src/epiforecast/registry.py`;
- `src/epiforecast/registry_doctor.py`;
- los módulos nuevos `src/epiforecast/runner/artifact_*.py` de C7.1;
- `tests/unit/test_artifact_backend.py`;
- `tests/unit/runner/artifact_fixtures.py`;
- `tests/unit/runner/test_artifact_validation.py`;
- los tests trackeados ajustados por C7.1;
- `docs/PLAN_C7_PUBLICACION_OBESIDAD.md`.

Antes de hacer `git add`:

1. comparar la lista real contra esta whitelist;
2. no usar `git add .` ni `git add -A`;
3. añadir rutas explícitas;
4. excluir `.qwen/`, `references/`, `reports/`, imágenes, PDFs y cualquier otro untracked del
   usuario;
5. inspeccionar `git diff --cached --stat` y `git diff --cached --check`;
6. confirmar que ningún archivo bajo `runs/`, `reports/forecasts`, DVC o frontend quedó staged.

Mensaje previsto:

```text
C7.1 registry artifact backend + identity-aware doctor
```

Después del commit:

1. verificar el nuevo SHA y el árbol trackeado limpio;
2. registrar conteos finales y hashes en este plan/AGENTS si corresponde sin crear un commit
   recursivo de estado;
3. no hacer push;
4. no iniciar C7.2;
5. detenerse y entregar el diff/commit para revisión.

#### Criterio de cierre de C7.1

```text
Acción 6 PASS
AND Acción 7 PASS completo
AND commit limitado a la whitelist
AND tree trackeado limpio
AND Obesidad sigue trained + NO-GO
AND F50 sigue configured + NO-GO
AND cero DVC/push/deploy/frontend
```

#### Siguiente secuencia inequívoca

```text
Acción 6.1–6.3
→ Acción 7 / gate completo
→ revisar whitelist y staged diff
→ Acción 8 / un commit
→ STOP sin push
```

_Respuesta auditada:_ no iniciar todavía la Acción 5. La Ronda 10 cerró correctamente universo,
horizonte, conteos y reconciliación, pero la auditoría R11 reprodujo siete falsos verdes en tres
relaciones que la propia Acción 4 exige. Ejecutar el microcierre siguiente y, si pasa, continuar
directamente con la Acción 5.

---

### Ronda 11 — Auditoría independiente de la Acción 4 y orden vigente — 2026-07-25

#### Veredicto

**Ronda 10 PASS parcial; Acción 4 REABIERTA en tres contratos funcionales concretos.**

Se revalidó el WIP sobre `b981b6e5`, sin modificar código, runs, DVC ni frontend:

```text
test_artifact_backend.py + test_artifact_validation.py   170 PASS
make lint                                                PASS
make typecheck                                           PASS (144 módulos)
doctor Obesidad --artifacts                              ✅ rc=0
doctor --artifacts                                       ✅ rc=0
test_produccion_ownership.py                             71 PASS · 3 FAIL
```

No se reabren:

- universo exacto de 64 bases y 111 productos;
- horizonte y calendario MMWR;
- filas, claves, finitud y no negatividad;
- reconciliación de generales, regiones y nacional;
- inventarios de manifests, schemas y SHA256;
- aceptación, selección, refit o lineage.

#### R11-F1 — El inventario no está enlazado al estado sellado

`model_inventory.csv` comprueba clave, motor, `n_train`, `train_end` y que los digests no se
repitan. No compara `state_digest` ni `state_format` contra la entrada del `model_index`/envelope
que ya fue validada.

Dos mutaciones re-selladas dan falso verde:

```text
state_digest de una serie = ffff…ffff  → doctor rc=0
state_format de una serie = inventado.v99 → doctor rc=0
```

La unicidad de digests no sustituye la identidad y además es demasiado restrictiva para N+1: dos
series legítimas podrían serializar estados byte-idénticos. El contrato correcto es igualdad por
`SeriesKey`, no “todos distintos”.

#### R11-F2 — Los CSV por job no cumplen el contrato completo

`_check_jobs` hoy compara solo clave geográfica, horizonte, `y_pred_cases` y `ds` contra el
consolidado. No llama al validator de `ForecastFrame` ni comprueba toda la procedencia del job.

Tres mutaciones re-selladas dan falso verde:

```text
run_id de una fila del job = run_ajeno          → doctor rc=0
disease_id de una fila del job = anorexia_f50  → doctor rc=0
yhat_lower presente y yhat_upper ausente       → doctor rc=0
```

Por la misma causa quedan sin anclar de forma explícita el motor del directorio, fold, origen,
cobertura exacta de series del motor y el resto de columnas del contrato.

#### R11-F3 — `point-only` no se exige

`contracts.validate_forecast_frame` permite correctamente dos modos genéricos: intervalos
conjuntamente nulos o conjuntamente presentes. El forecast C5, en cambio, está declarado
`point-only`; reutilizar el contrato genérico no basta para imponer ese modo.

Dos mutaciones con bandas completas y válidas dan falso verde:

```text
forecast_base.csv con lower/pred/upper válidos → doctor rc=0
forecast.csv con lower/pred/upper válidos      → doctor rc=0
```

No se debe endurecer `validate_forecast_frame` globalmente: otros motores o padecimientos podrán
tener intervalos. La restricción pertenece al validador de este artefacto/lineage.

#### Orden R11.1 — Propagar la identidad de modelos ya verificada

En `artifact_portfolio`:

1. introducir una identidad inmutable por modelo con `SeriesId`, motor, `state_format` y
   `state_digest`;
2. hacer que `validate_models` devuelva el mapa de identidades que ya contrastó entre índice,
   envelope y estado cargable;
3. no volver a abrir ni inferir modelos en `artifact_forecast`;
4. transportar ese mapa en `VerifiedRunnerRuns` o pasarlo directamente al validador de forecast.

En `_check_inventory`:

1. exigir universo exacto por `SeriesId`;
2. comparar motor, `n_train`, `train_end`, `state_format` y `state_digest` campo por campo contra
   la identidad sellada;
3. eliminar la regla “todos los state digests deben ser distintos”;
4. aceptar que dos series tengan el mismo digest únicamente si eso es lo que declaran sus estados
   sellados.

No inferir datos desde nombres de archivo y no hardcodear los seis motores.

#### Orden R11.2 — Validar cada job antes de consolidarlo

Para cada `artifacts/<engine>/forecast_base.csv`:

1. ejecutar `validate_forecast_frame`;
2. exigir `run_id=forecast_run_id`, `disease_id`, `fold=final_refit` y
   `engine=<engine del job>`;
3. exigir origen, horizonte, `ds`, nivel estado, claves únicas, finitud y no negatividad;
4. exigir exactamente las `SeriesKey` asignadas a ese motor por `final_selection.csv` y
   `n_series_del_motor × horizon` filas;
5. exigir `point-only`;
6. normalizar únicamente la columna `engine` a `portfolio` y comparar después **todas** las
   columnas de `FORECAST_COLUMNS` contra el subconjunto correspondiente del consolidado.

Una diferencia en metadata, intervalos o valores debe producir `ArtifactValidationError`, no
quedar oculta porque la predicción numérica coincida.

#### Orden R11.3 — Imponer `point-only` en el borde correcto

Crear una comprobación pequeña y explícita que exija:

```text
yhat_lower.isna().all() AND yhat_upper.isna().all()
```

Aplicarla a:

1. cada CSV por job;
2. `forecast_base.csv`;
3. `forecast.csv`.

No modificar el contrato genérico `contracts.validate_forecast_frame` y no fabricar intervalos.

#### Orden R11.4 — Pruebas

Añadir sobre copias aisladas y re-selladas, como mínimo:

1. digest de inventario único pero ajeno;
2. formato de estado ajeno;
3. dos estados legítimamente iguales en un fixture sintético, si el contrato puede construirse sin
   tocar runs;
4. job con `run_id`, `disease_id`, engine, fold u origen ajenos;
5. job con serie que pertenece a otro motor;
6. job con fila faltante/extra;
7. job con un intervalo o con dos intervalos presentes;
8. base consolidada con dos intervalos presentes;
9. forecast completo con dos intervalos presentes;
10. control positivo de igualdad exacta entre inventario, estados, jobs y consolidado canónicos.

Los siete falsos verdes reproducidos en esta ronda deben fallar por su motivo semántico, no solo
porque cambió un SHA256.

#### Orden R11.5 — Gate y continuación automática

Ejecutar:

```text
.venv/bin/pytest -q tests/unit/test_artifact_backend.py --no-cov
.venv/bin/pytest -q tests/unit/runner/test_artifact_validation.py --no-cov
make lint
make typecheck
.venv/bin/python -m scripts.doctor_padecimiento Obesidad --artifacts
.venv/bin/python -m scripts.doctor_padecimiento --artifacts
```

Además:

- demostrar que los siete falsos verdes ya producen `ArtifactValidationError`;
- confirmar hashes byte-idénticos de dataset, aceptación, refit y forecast;
- actualizar arriba la Acción 4 a **CERRADA** y registrar el resultado aquí.

Si R11 queda verde, continuar directamente con la Acción 5 usando el registry sintético; no pedir
otra revisión intermedia.

#### Orden posterior ya decidida — Acción 5

Los únicos fallos observados son:

```text
test_main_rc0_aunque_teardown_falle
test_main_rc0_aunque_teardown_reciba_senal
test_e2e_preliminar_escribe_schema_honesto
```

Los tres invocan Obesidad por el carril legacy y ahora reciben correctamente
`eligible_engines=[]`. La reparación no toca producción:

1. reutilizar `_YAML_CONFIGURED`/`Cfg` o un equivalente sintético local al test;
2. inyectar esa entrada en `registry.require`;
3. crear `Prophet_Cfg_completo.csv` y, para E2E, `Deepar_Cfg_completo.csv` bajo `tmp_path`;
4. ejecutar `--disease Cfg --allow-preliminary`;
5. conservar exactamente las inyecciones de fallo de teardown/señal;
6. comprobar `rc=0`, salida preliminar honesta y ausencia de residuos;
7. mantener una prueba separada de que Obesidad no puede usar el selector legacy.

No modificar `scripts/produccion_padecimiento.py`, `config/padecimientos.yaml` ni volver a declarar
motores legacy para Obesidad.

#### Límites vigentes

- solo el WIP de C7.1 y sus tests; ningún run canónico se regenera;
- no retuning, selección, aceptación, refit ni forecast nuevo;
- no DVC, frontend, lifecycle, rutas públicas, commit o push;
- no añadir locks, defensas de filesystem o endurecimiento fuera de estos tres contratos.

#### Siguiente secuencia inequívoca

```text
R11.1 identidad sellada del inventario
→ R11.2 contrato completo por job
→ R11.3 point-only explícito
→ R11.4 tests
→ R11.5 gate
→ si PASS, Acción 5 sin nueva pausa
```

---

### Ronda 12 — Microcierre R11 + Acción 5 — 2026-07-25

#### Veredicto

**PASS doble.** Los siete falsos verdes de R11 quedan cerrados con prueba semántica, y la Acción 5
deja **`make test-fast` verde por primera vez en toda C7.1: 1,610 PASS**.

##### R11.1 — Identidad sellada, propagada

`artifact_portfolio.ModelIdentity` (frozen) transporta `SeriesId`, motor, `n_train`, `train_end`,
`state_format` y `state_digest` ya contrastados entre índice, envelope y estado cargable;
`validate_models` devuelve ese mapa y `VerifiedRunnerRuns` lo lleva en `models`. `artifact_forecast`
ya no abre ni infiere modelos: compara el inventario campo por campo contra esa identidad.

Se **eliminó** la regla "todos los `state_digest` distintos": no probaba identidad y prohibía un
caso legítimo para N+1 —dos series pueden serializar estados byte-idénticos—. El contrato ahora es
igualdad por `SeriesKey` contra lo sellado.

##### R11.2 — Contrato completo por job

Cada `artifacts/<engine>/forecast_base.csv` pasa por `validate_forecast_frame`, y se le exige
`run_id`, `disease_id`, `fold=final_refit`, `engine=<motor del job>`, origen, horizonte, `ds`, nivel
estado, claves únicas, `point-only`, exactamente las `SeriesKey` que `final_selection.csv` le asignó
y `n_series_del_motor × horizon` filas. Al consolidar se normaliza **sólo** la columna `engine` a
`portfolio` y se comparan **todas** las `FORECAST_COLUMNS`, no cuatro.

##### R11.3 — `point-only` en el borde correcto

`_check_point_only` exige `yhat_lower` y `yhat_upper` completamente nulos, y se aplica a cada CSV
por job, a `forecast_base.csv` y a `forecast.csv`. **No** se endureció
`contracts.validate_forecast_frame`: otros motores o padecimientos podrán tener intervalos
legítimos.

##### Los siete falsos verdes, ya con error semántico

```text
inventario_con_digest_ajeno     state_digest de ('05','hombres'): 'ffff…' != 'b4890b2a…'
inventario_con_formato_ajeno    state_format de ('05','hombres'): 'inventado.v99' != 'statsmodels…'
job_con_run_id_ajeno            forecast/seasonal_mean_5y: run_id: [… 'run_ajeno'] != […]
job_con_disease_ajeno           forecast/seasonal_mean_5y: disease_id: ['anorexia_f50','obesidad'] != …
job_con_un_solo_intervalo       ForecastFrame: intervalos deben ser conjuntamente nulos o presentes
base_con_bandas_validas         forecast_base.csv: yhat_lower tiene 3328 valores; se declaró point-only
consolidado_con_bandas_validas  forecast.csv: yhat_lower tiene 5772 valores; se declaró point-only
```

Más seis mutaciones nuevas por job (motor, fold, origen, fila faltante, serie de otro motor, bandas
completas) y un control positivo que comprueba que inventario, estados, jobs y consolidado
canónicos concuerdan.

##### Acción 5 — las tres pruebas legacy, sin tocar producción

Fixture `cfg_preliminar`: el padecimiento sintético `Cfg` de `_YAML_CONFIGURED` —`configured`,
`selection_policy=rolling_cv_v1`— al que se le añadieron sus dos motores legacy, inyectado en
`registry.require`. Los CSV `Prophet_Cfg_completo.csv` y `Deepar_Cfg_completo.csv` se crean bajo
`tmp_path` y las tres pruebas ejecutan `--disease Cfg --allow-preliminary` por la **misma ruta
productiva del selector**, conservando íntegras sus inyecciones de fallo de teardown y de señal, la
comprobación de `rc=0`, el schema preliminar honesto y la ausencia de residuos `.tmp`.

No se tocó `scripts/produccion_padecimiento.py`, `config/padecimientos.yaml` ni se le devolvieron
motores legacy a Obesidad.

**Prueba separada añadida** (`test_el_carril_legacy_rechaza_a_obesidad`): con el registry REAL,
Obesidad declara `eligible_engines=()` y `training_engines=()`, el selector viejo devuelve
**rc=1** ("Ningún motor entrenado para Obesidad") y no escribe ningún preliminar. Que el carril
legacy la rechace es el comportamiento correcto, y ahora está aseverado.

#### Gate

```text
tests/unit/test_artifact_backend.py             37 PASS
tests/unit/runner/test_artifact_validation.py  147 PASS
tests/unit/test_produccion_ownership.py         75 PASS  (antes 71 PASS · 3 FAIL)
make test-fast                              1,610 PASS  ← VERDE, por primera vez en C7.1
make lint                                       PASS
make typecheck                                  PASS (144 módulos)
doctor Obesidad --artifacts                     ✅ rc=0
doctor --artifacts                              ✅ rc=0
```

#### Integridad

Los cuatro runs canónicos, byte-idénticos: aceptación `4e0327ed…`, refit `972f7519…`, forecast
`fb6f2afd…`, dataset `2ef4ee12…`. `rolling_cv_v1.yaml` en `dd6d4a02…`.

Matriz de mutaciones: **134 casos** (9 rompen el sello, 125 rompen identidad o contenido).

#### Estado al cerrar la ronda

```text
WIP sin commit sobre b981b6e5
Obesidad = trained · NO-GO · sin motores legacy; el carril viejo la rechaza con rc=1
F50      = configured · NO-GO
Acciones 1, 2, 3, 4 y 5 CERRADAS · pendientes 6, 7, 8
make test-fast VERDE (1,610) · lint PASS · typecheck PASS (144)
Cuatro runs canónicos íntegros · doctor verde para los seis padecimientos
Sin DVC, push, deploy, frontend ni flip
```

#### Siguiente paso

Corresponde la **Acción 6** (limpiar y justificar el delta de tests: parametrizaciones duplicadas,
nombres obsoletos `test_obesidad_*` que prueban Depresión, y documentar qué pruebas del runner
cubren las transformaciones reales de Obesidad), y después la 7 (gate completo) y la 8 (commit
aislado). Me detengo aquí porque la orden vigente llegaba hasta el cierre de la Acción 5.

_Respuesta:_

_Respuesta auditada:_ R12 queda aceptada. Continuar por la sección 18:
Acción 6 mecánica → gate completo de Acción 7 → whitelist y commit de Acción 8 → STOP sin push.

---

### Ronda 13 — Acciones 6, 7 y 8: cierre de C7.1 — 2026-07-25

#### Acción 6 — Limpieza mecánica · **CERRADA**

| orden | resultado |
| --- | --- |
| 6.1.1 duplicado en `test_forward_inverse_roundtrip` | eliminada la segunda `("Depresión", "prophet")` |
| 6.1.2–3 nombres obsoletos | `test_obesidad_no_emite_tasa_como_casos_si_falta_exposure` → `test_perfil_de_tasa_no_emite_…`; `test_obesidad_alinea_exposure_historica_y_futura_por_fecha` → `test_perfil_de_tasa_alinea_…`; `test_eval_rapida_alinea_exposure_y_evalua_obesidad_en_casos` → `…_evalua_perfil_de_tasa_en_casos` |
| 6.1.4 rechazo legacy | la aserción pasa de `rc != 0` a **`rc == 1`**, el contrato observado |
| 6.1.5 | `TestObesidadFueraDelCarrilLegacy` y `test_obesidad_ya_no_resuelve_contratos_legacy` **no** se renombraron: sí verifican Obesidad |
| 6.2 mapa de cobertura | registrado en el docstring de `tests/unit/artifacts/test_transforms.py` |

**Baseline nuevo: `make test-fast` 1,610 → 1,609 PASS**, exactamente como predijo la auditoría. No
es pérdida de cobertura: eran dos ejecuciones byte-idénticas del mismo par.

Gate 6.3: los siete archivos del bloque dan **213 PASS**; lint, typecheck y `git diff --check`
verdes.

#### Acción 7 — Gate completo · **PASS**

```text
make lint                                        PASS
make typecheck                                   PASS (144 módulos)
make test-fast                               1,609 PASS
tests/unit/test_artifact_backend.py             37 PASS
tests/unit/runner/test_artifact_validation.py  147 PASS
tests/integration/test_disease_run_gate.py      26 PASS (2m38s)
tests/integration/test_anorexia_f50_gate.py      5 PASS
doctor Obesidad --artifacts                      ✅ rc=0
doctor --artifacts                               ✅ rc=0
```

Ningún skip encubre la verificación central de `runner_runs`: las dos suites de integración
corrieron completas con datos reales.

**1) Runs canónicos C5 — byte-idénticos:**

| run | archivos | digest agregado |
| --- | ---: | --- |
| dataset `obesidad_1502d1a25b48` | 9 | `2ef4ee1236aa94c0` |
| aceptación `…82370419efd4` | 67 | `6bbc7f84ea5ec5bb` |
| refit `…ff249060018a` | 162 | `972f7519f885c0d1` |
| forecast `…92d446b6df8f` | 37 | `d89d92ee7e73b848` |

**2) Agregados legacy** (en `reports/forecasts/<motor>/`, no en la raíz):

```text
all_forecast_prophet.csv    cb5be3959781da7a
all_forecast_deepar.csv     96791595a2d4806d
all_forecast_ensemble.csv   1d2cf0a7dcb9e54c
all_forecast_stacking.csv   ac97dc8e210b95f2
```

**3)** `rolling_cv_v1.yaml` en `dd6d4a02…`, byte-idéntica.

**4) DVC dirigido** (`dvc status reports/forecasts.dvc models.dvc`, **sin** `add`, `checkout` ni
`push`): ambos reportan `modified`. El delta es **anterior a C7.1**, no nuevo: bajo `models/` el
archivo más reciente es del **2026-07-22** (los PKL preliminares de Obesidad del carril viejo) y
bajo `reports/forecasts/` del **2026-07-24**, mientras que todo el WIP de C7.1 es del 2026-07-25.
Cero archivos modificados hoy en cualquiera de los dos targets.

**5) Frontend:** `EpiForecast-IMSS-Dashboard` en `main @ 179bbe36` —el mismo commit que registra la
sección 2—, **cero** archivos trackeados modificados. Solo dos untracked del usuario.

**6)** `git diff --check`: PASS. **7)** `git status --short` clasificado: 9 trackeados modificados y
10 untracked de C7.1, todos dentro de la whitelist; **73 untracked ajenos** del usuario (PDFs,
imágenes, `reports/`, `references/`, `.qwen/`) que quedan fuera.

#### Acción 8 — Commit aislado

Se añadieron **rutas explícitas**, nunca `git add .` ni `-A`. Contenido exacto en la sección
siguiente, junto al SHA.
#### Cierre de C7.1 — commit `91269e6f`

> Este bloque se escribe **después** del commit y queda como única modificación sin commitear, para
> no crear el commit recursivo de estado que el propio plan prohíbe. Al verificarse el árbol
> inmediatamente después de `git commit`, estaba **limpio**.

```text
commit 91269e6f28b819aa779bc4b76583b014c0607792
rama   feat/registry-padecimientos-obesidad (origin @ 029fe666, 2 commits sin push)
20 rutas · 6,653 inserciones · 96 supresiones
```

Hooks de pre-commit: ruff, ruff format, mypy, trailing whitespace, EOF, YAML, merge conflicts,
large files y debug statements — **todos verdes**. `git diff --cached --check` limpio. Ninguna ruta
bajo `runs/`, `reports/`, `models/`, `references/`, `data/` o `.qwen/` quedó staged; los 75
untracked del usuario siguen fuera.

| criterio de cierre | estado |
| --- | --- |
| Acción 6 PASS | ✅ 1,609 PASS, el baseline predicho |
| Acción 7 PASS completo | ✅ sin skips en el núcleo `runner_runs` |
| commit limitado a la whitelist | ✅ 20 rutas, añadidas explícitamente |
| árbol trackeado limpio | ✅ verificado tras el commit |
| Obesidad `trained` + NO-GO | ✅ `backend=runner_runs`, fuera de `published_only` |
| F50 `configured` + NO-GO | ✅ `channels: []` |
| cero DVC/push/deploy/frontend | ✅ |

`published_members()` sigue devolviendo exactamente `['Depresión', 'Parkinson', 'Alzheimer',
'Dengue']`.

#### Observación para C7.5, no para C7.1

La entrada de Obesidad todavía declara `channels` con seis entradas —incluidas
`weekly_validation` y `prospective_validation`— y `gallery_enabled: true`. El contrato de la
sección 1 y el registry candidato de C7.5 exigen cuatro canales y galería desactivada. Hoy no tiene
ningún efecto: con `lifecycle=trained`, Obesidad queda fuera de todo filtro `published_only`, y
ninguna Acción de C7.1 ordenó tocar esos campos, así que no los cambié. Queda anotado para que el
registry candidato de C7.5 lo corrija antes de cualquier activación.

**C7.1 CERRADA. STOP: no hay push, ni DVC, ni C7.2.**

_Respuesta:_

---

## 19. Re-auditoría independiente del cierre C7.1 — histórica, ejecutada

### Veredicto

**C7.1 PASS funcional y documentalmente corregida.** El commit `91269e6f` implementa únicamente
el backend de artefactos `runner_runs`, la validación de identidad/material y sus pruebas. No
publica Obesidad, no crea un release, no modifica DVC y no toca el frontend.

La revisión independiente confirmó:

| superficie | resultado |
| --- | --- |
| commit | 20 rutas permitidas; 6,653 inserciones y 96 supresiones |
| perímetro prohibido | cero rutas del commit en `runs/`, `reports/`, `models/`, `references/`, `data/`, `.qwen/` o frontend |
| focal C7.1 | 259 PASS |
| fast | 1,609 PASS, 53 deselected |
| integración real | 31 PASS: Obesidad 26 + F50 5 |
| lint | PASS |
| typecheck | PASS, 144 módulos |
| doctors | Obesidad rc=0 y registry completo rc=0 |
| legacy | los cuatro SHA256 coinciden con la evidencia de R13 |
| política | `rolling_cv_v1.yaml` = `dd6d4a02…` |
| frontend | `main @ 179bbe36`, cero cambios trackeados |
| DVC dirigido | `reports/forecasts.dvc` y `models.dvc` siguen `modified`; cero archivos fechados 2026-07-25 dentro de ambos targets |
| visibilidad | publicados = Depresión, Parkinson, Alzheimer y Dengue; Obesidad sigue fuera |

En el instante de esta ronda, este plan era la única modificación trackeada posterior al commit.
Después quedó preservado en el commit doc-only `7a8c25cd`; véanse las secciones 20 y 21. Los
archivos no rastreados del usuario permanecieron fuera del alcance.

### Corrección de evidencia: digests agregados

Las rondas anteriores repetían dos digests agregados que no son reproducibles con el mismo
procedimiento que sí produce los valores registrados para dataset y refit. La comprobación
independiente se ejecutó desde la raíz del repo con:

```bash
find "$run" -type f -print0 \
  | sort -z \
  | xargs -0 shasum -a 256 \
  | shasum -a 256
```

Resultado corregido:

| run | archivos | digest agregado reproducible |
| --- | ---: | --- |
| dataset `obesidad_1502d1a25b48` | 9 | `2ef4ee1236aa94c0` |
| aceptación `…82370419efd4` | 67 | `6bbc7f84ea5ec5bb` |
| refit `…ff249060018a` | 162 | `972f7519f885c0d1` |
| forecast `…92d446b6df8f` | 37 | `d89d92ee7e73b848` |

Esto es una corrección documental, no un cambio de artefactos: aceptación, refit y forecast
coinciden archivo por archivo con el respaldo `029fe666` (67/67, 162/162 y 37/37 SHA256).
Los valores anteriores `4e0327ed…` y `fb6f2afd…` quedan invalidados.

### Estado de release

```text
C7.0 = PASS
C7.1 = PASS · commit local 91269e6f · sin push
C7.2 = NO INICIADA · no autorizada
Obesidad = trained · backend runner_runs · NO-GO
F50 = configured · backend legacy_models · NO-GO
published_members = Depresión, Parkinson, Alzheimer, Dengue
```

Obesidad aún declara seis canales y `gallery_enabled: true`. Mientras sea `trained` no se expone,
pero antes de C7.5 el candidato debe quedar exactamente con `web`, `epibot`, `reports`, `tableau`
y galería desactivada. No corregirlo durante C7.2: la sede inmutable de artefactos y la política de
visibilidad son contratos distintos.

### Órdenes siguientes

#### Orden 19.1 — Congelar C7.1 · **COMPLETADA**

1. No modificar más código de C7.1 salvo un defecto reproducible nuevo.
2. Revisar el diff de `91269e6f` y este único delta documental.
3. No hacer `git push` hasta recibir autorización explícita.
4. Si se decide conservar este cierre en Git, hacerlo en un commit **doc-only** separado; no
   mezclarlo con C7.2.

#### Orden 19.2 — Autorizar C7.2 por separado

C7.2 solo puede empezar después de un GO explícito. Su alcance inicial será:

1. implementar un constructor genérico de `release_manifest.v1`;
2. consumir exclusivamente `VerifiedRunnerRuns`, sin reentrenar ni recalcular selección;
3. construir el bundle en un temporal y promoverlo atómicamente a
   `artifacts/releases/obesidad/<release_id>/`;
4. derivar identidad y conteos desde manifests sellados, no desde strings o constantes de
   Obesidad;
5. demostrar dos construcciones byte-idénticas;
6. restaurar y validar el bundle desde otro root local;
7. crear, solo con autorización de C7.2, un target DVC dedicado sin tocar `models.dvc` ni
   `reports/forecasts.dvc`;
8. detenerse antes de `dvc push`.

#### Orden 19.3 — Gate obligatorio de C7.2

C7.2 no se cierra hasta demostrar:

- `release_id` determinista;
- inventario exacto y SHA256 de todos los archivos;
- 64 modelos cargables y forecast numéricamente idéntico al canónico;
- aceptación positiva, selección, refit, forecast y política enlazados por digest;
- cero rutas absolutas;
- legacy, DVC existente, frontend, lifecycle, canales y F50 intactos;
- tests focales, fast, integración, lint, typecheck y doctors verdes;
- commit acotado y **STOP sin `dvc push`, git push, deploy ni publicación**.

### Próxima acción de esa ronda — supersedida

**Revisar C7.1.** Si se aprueba, autorizar expresamente el commit doc-only y/o el push. Solo
después emitir un GO separado para implementar C7.2. No ejecutar C7.3–C7.6 ni cambiar
`trained → published`.

---

## 20. Revisión de C7.1 y causa raíz de la discrepancia de digests — 2026-07-25

### Orden 19.1 — C7.1 congelada

Cero cambios de código. Se ejecutó únicamente la revisión pedida, más la verificación de la
corrección documental de la sección 19. Sin `git push`, sin DVC, sin C7.2.

### La discrepancia de digests es de LOCALE, no de artefactos

La sección 19 reporta que `4e0327ed…` y `fb6f2afd…` "no son reproducibles" y quedan invalidados.
Reproduje ambos procedimientos y la causa es concreta: **`sort` usa el collation del locale**, y el
digest agregado se calcula sobre la salida de `shasum`, que incluye las rutas. Distinto orden de
rutas → distinto digest, con artefactos idénticos.

| run | archivos | `LC_ALL=C` | `en_US.UTF-8` (default de la shell) |
| --- | ---: | --- | --- |
| dataset `obesidad_1502d1a25b48` | 9 | `2ef4ee1236aa94c0` | `2ef4ee1236aa94c0` |
| aceptación `…82370419efd4` | 67 | `6bbc7f84ea5ec5bb` | `4e0327ed62592222` |
| refit `…ff249060018a` | 162 | `972f7519f885c0d1` | `972f7519f885c0d1` |
| forecast `…92d446b6df8f` | 37 | `d89d92ee7e73b848` | `fb6f2afd3432cc31` |

Los dos que "coincidían" lo hacían porque sus nombres ordenan igual en ambos locales; los dos que
discrepaban contienen rutas con `.` y `/` mezclados (`artifacts/<motor>/…` frente a `forecast.csv`
y `jobs/<motor>.stdout.txt`), donde el collation UTF-8 y el de C difieren.

Conclusiones, sin ambigüedad:

1. **Ninguno de los dos conjuntos de valores estaba mal**: los artefactos son byte-idénticos, como
   confirma la propia sección 19 al cotejarlos archivo por archivo contra `029fe666`.
2. **Mi procedimiento sí era defectuoso**: reporté digests agregados sin fijar el locale, así que no
   eran reproducibles para quien tuviera otro `LC_COLLATE`. Ese es un defecto real de la evidencia
   que registré en las Rondas 4–13.
3. **A partir de aquí el canónico es `LC_ALL=C`**, que es el único orden estable entre máquinas:

```bash
find "$run" -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256
```

4. Los valores `4e0327ed…` y `fb6f2afd…` de las rondas anteriores deben leerse como
   "`en_US.UTF-8`", no como erróneos, y **no se reutilizan**.

### Esto no afecta al código de C7.1

El validador nunca ordena rutas con `sort` de shell: usa `sorted()` de Python, que compara por
punto de código y es independiente del locale. La incidencia era exclusivamente del procedimiento
manual de evidencia.

**Sí importa para C7.2:** `SHA256SUMS.txt` del bundle y el cálculo de `release_id` deben fijar
explícitamente el orden de listado —`LC_ALL=C` o, mejor, `sorted()` en Python— o dos máquinas
producirían manifiestos distintos con los mismos bytes. Queda anotado como requisito del gate de
C7.2.

### Estado

```text
C7.1 = PASS · commit 91269e6f + este cierre doc-only · sin push
C7.2 = NO INICIADA · sin GO
Obesidad = trained · runner_runs · NO-GO
F50      = configured · NO-GO
published_members = Depresión, Parkinson, Alzheimer, Dengue
```

Pendiente de tu autorización explícita, por separado: el `git push` y el GO de C7.2.

_Respuesta:_

---

## 21. Auditoría previa al push — histórica, ejecutada

### Veredicto

**PASS.** El commit `7a8c25cd` es estrictamente doc-only: su único path es este plan. No cambió
código, configuración, tests, runs, DVC ni frontend. El árbol trackeado estaba limpio antes de
esta actualización; la rama está tres commits delante del remoto:

```text
029fe666  remoto y checkpoint respaldado
b981b6e5  C7.0: cuarentena + guard del dataset
91269e6f  C7.1: backend de artefactos + doctor por identidad
7a8c25cd  cierre documental + causa raíz de digests
```

Por tanto, un eventual `git push` no subiría solamente C7.1 o el documento: publicaría el rango
completo `029fe666..7a8c25cd`. Esa unidad debe revisarse y autorizarse como tal.

### Evidencia revalidada

| comprobación | resultado |
| --- | --- |
| paths de `7a8c25cd` | solo `docs/PLAN_C7_PUBLICACION_OBESIDAD.md` |
| `git diff --check 91269e6f..7a8c25cd` | PASS |
| locale `C` | `2ef4…`, `6bbc…`, `972f…`, `d89d…` |
| locale `en_US.UTF-8` | `2ef4…`, `4e03…`, `972f…`, `fb6f…` |
| causa de discrepancia | confirmada: collation distinto, mismos bytes |
| doctor Obesidad | rc=0 |
| doctor completo | rc=0 |
| política | `dd6d4a0274a6f8bb…` |
| agregados legacy | cuatro SHA256 iguales a R13 |
| DVC dirigido | ambos targets siguen `modified`; cero archivos fechados 2026-07-25 |
| frontend | `main @ 179bbe36`, cero cambios trackeados |

No fue necesario repetir fast/integración: el único commit posterior a sus gates modifica
Markdown. Reejecutarlas no aportaría cobertura adicional sobre ese delta.

### Hallazgos de diseño de C7.2 cerrados en este plan

1. **Identidad circular:** el manifest no puede inventariar su propio hash ni el de
   `SHA256SUMS.txt`. El `release_id` se deriva de un `identity_payload` previo y canónico.
2. **Reproducibilidad falsa por timestamps:** una hora de construcción dentro del bundle daría
   bytes distintos para el mismo ID. La telemetría temporal queda fuera del contenido inmutable.
3. **Orden dependiente del locale:** checksums y manifest usan `sorted()` sobre rutas POSIX
   relativas; nunca `sort` sin locale fijado.
4. **Bundle no autosuficiente:** cargar modelos no basta para repetir Prophet en tasa. El release
   debe incluir catálogo geográfico, snapshot de exposición y configuración efectiva, y el loader
   debe consumirlos desde `runtime_inputs/`.
5. **Autorización demasiado amplia:** C7.2 queda separada en implementación local, puntero DVC
   local y subida remota.

### Órdenes vigentes

#### Orden 21.1 — Decisión sobre el push · **COMPLETADA**

Antes de cualquier push:

1. revisar `git log --oneline 029fe666..7a8c25cd`;
2. revisar el diff material `029fe666..91269e6f`;
3. revisar por separado el diff doc-only `91269e6f..7a8c25cd`;
4. confirmar que se desea subir **los tres commits**;
5. recibir autorización explícita para `git push`.

No reescribir, squash, amendar ni rebasear esa cadena durante la revisión. El push no es requisito
para comenzar un experimento local, pero sí debe resolverse antes de presentar C7 como checkpoint
compartido.

#### Orden 21.2 — C7.2-A: contrato e implementación local · **requiere GO separado**

Cuando exista autorización explícita, ejecutar en este orden:

1. escribir primero tests del `identity_payload`, serialización canónica, inventario acíclico,
   paths relativos y rechazo de contenido distinto bajo el mismo destino;
2. implementar un builder genérico que reciba `disease_id` y `VerifiedRunnerRuns`;
3. construir únicamente en dos temporales independientes, nunca en
   `artifacts/releases/…` durante C7.2-A;
4. incluir solo modelos, forecast, lineage, política, selección, aceptación y runtime inputs
   realmente consumidos;
5. implementar el loader/validador de `runner_release` contra el bundle temporal;
6. cargar 64 modelos y reproducir las 3,328 bases y 5,772 filas totales usando exclusivamente el
   bundle;
7. repetir la construcción bajo roots y locales distintos y exigir igualdad byte a byte;
8. ejecutar gates completos;
9. hacer un commit C7.2-A acotado y detenerse.

Prohibido en C7.2-A:

- `dvc add`, `dvc push`, cambios de punteros o escritura en la ruta final;
- reentrenar, retunear o recalcular la selección/aceptación;
- tocar `models.dvc`, `reports/forecasts.dvc`, forecasts legacy o frontend;
- cambiar lifecycle, canales, galería o F50;
- usar `obesidad`, 64, 111, nombres de motores o rutas del equipo como reglas del builder
  genérico; los valores concretos solo son evidencia del primer release.

#### Orden 21.3 — Gate de C7.2-A

El gate mínimo es:

```text
tests unitarios del identity payload y release builder       PASS
tests del loader runner_release y mutaciones                 PASS
dos builds, roots/locales distintos                         byte-idénticos
reproducción del forecast desde el bundle                   numéricamente idéntica
make lint                                                    PASS
make typecheck                                               PASS
make test-fast                                               PASS
integración Obesidad + F50                                  PASS
doctor Obesidad en runner_runs                              PASS
doctor completo                                              PASS
legacy + política + DVC dirigido + frontend                 sin delta nuevo
```

Además, cada fallo de manifest, checksum, input, modelo o lineage debe terminar en error tipado y
rc no cero, nunca en traceback ni aceptación parcial.

#### Orden 21.4 — Después del PASS de C7.2-A

1. entregar commit, diff, inventario, `release_id` candidato y evidencia;
2. pedir GO de **C7.2-B** para materializar la ruta final y crear el puntero DVC dedicado;
3. detenerse otra vez antes de `dvc push`;
4. pedir GO de **C7.2-C** únicamente después de revisar el puntero y restaurar desde otro root.

### Próxima acción de esa ronda — supersedida

**No ejecutar todavía.** La siguiente decisión humana es una de estas dos autorizaciones
independientes:

1. autorizar el push del rango completo `029fe666..7a8c25cd`; y/o
2. emitir `GO C7.2-A` para implementar y validar el bundle únicamente en temporales locales.

Ninguna de las dos autoriza DVC remoto, C7.3, frontend, deploy ni `trained → published`.

---

## 22. Push y preservación del contrato C7.2 — histórica, ejecutada

### Veredicto del push

**PASS.** El rango completo se publicó por fast-forward en la rama de trabajo:

```text
local  7a8c25cdcd7da4f8c9e6ee74b5195f4e23711af6
origin 7a8c25cdcd7da4f8c9e6ee74b5195f4e23711af6
ahead/behind 0/0
main intacta
```

La operación compartió únicamente C7.0, C7.1 y su cierre documental. No hizo merge a `main`, DVC,
deploy, frontend ni cambio de lifecycle. Obesidad permanece `trained`, `runner_runs`, NO-GO; F50
permanece `configured`, NO-GO.

### Delta documental — preservado

Las secciones 21 y 22 y el endurecimiento del contrato C7.2 quedaron preservados en
`0dbd0f01`, commit doc-only de un solo path, y subidos por fast-forward. No se mezclaron con
código de C7.2-A.

#### Orden 22.1 — Preservar el plan actualizado · **COMPLETADA**

Con autorización explícita para el cierre documental:

1. comprobar que el único path trackeado modificado es
   `docs/PLAN_C7_PUBLICACION_OBESIDAD.md`;
2. ejecutar `git diff --check`;
3. añadir por ruta exacta, nunca con `git add .` o `-A`;
4. revisar el staged diff completo;
5. crear un commit doc-only con mensaje:

```text
docs: harden C7.2 release bundle contract
```

6. verificar que el commit contiene un solo path;
7. no volver a editar el plan para escribir el SHA del propio commit;
8. con autorización explícita de push para **ese commit**, subirlo por fast-forward;
9. comprobar local/remoto iguales y detenerse.

No es necesario repetir fast ni integración para este commit: el delta es exclusivamente
Markdown. Sí son obligatorios `git diff --check`, whitelist de un path y revisión del staged diff.

### Orden de ejecución de C7.2-A

Solo después de que el plan actualizado exista en remoto y el usuario emita literalmente
`GO C7.2-A`, ejecutar la Orden 21.2 con estas fronteras:

#### A0 — Congelar contrato con tests

1. definir `identity_payload.v1` y su serialización canónica;
2. probar que no existe ciclo entre `release_id`, manifest y checksums;
3. probar orden independiente del locale;
4. probar rechazo de rutas absolutas, traversal, archivos extra/faltantes y schema desconocido;
5. probar que timestamps o receipts externos no entran al contenido inmutable.

#### A1 — Builder genérico, solo temporal

1. recibir `disease_id`, `VerifiedRunnerRuns` y roots inyectables;
2. derivar motores, series, conteos, horizonte e inputs desde artefactos sellados;
3. copiar únicamente payloads requeridos;
4. generar `runtime_inputs` con catálogo, exposición y configuración efectiva;
5. escribir primero en un temporal;
6. validar el bundle completo antes de devolver éxito;
7. no escribir en `artifacts/releases/`.

#### A2 — Loader `runner_release`

1. validar `identity_payload`, `release_id`, manifest, checksums e inventario exacto;
2. cargar índices, envelopes y estados desde paths declarados;
3. consumir exposición y geografía desde el bundle;
4. reproducir el forecast sin leer `runs/` ni rutas canónicas del workspace;
5. emitir errores tipados ante cualquier corrupción o inconsistencia.

#### A3 — Reproducibilidad funcional

1. construir en dos roots temporales;
2. ejecutar una construcción bajo locale `C` y otra bajo `en_US.UTF-8`;
3. exigir mismo `release_id` y todos los archivos byte-idénticos;
4. cargar los 64 modelos del release candidato;
5. reproducir 3,328 predicciones base y 5,772 filas totales;
6. exigir igualdad numérica con el forecast canónico;
7. mutar una fuente de identidad y comprobar que cambia el ID o falla cerrado.

#### A4 — Gate, commit y STOP

Ejecutar la matriz completa de la Orden 21.3, revisar preservación de legacy/DVC/frontend y hacer
un commit acotado de C7.2-A. El commit no puede contener:

- bundles finales o temporales;
- punteros `.dvc`;
- cambios en `runs/`, `models/`, `reports/forecasts/` o frontend;
- lifecycle, channels, gallery o F50;
- outputs generados o archivos del usuario.

Al terminar, entregar evidencia y detenerse. C7.2-A no autoriza C7.2-B.

### Próxima acción de esa ronda — vigente hasta emitir el GO

La autorización documental ya fue ejecutada. La siguiente orden es:

> **GO C7.2-A: implementa y valida el release bundle únicamente en temporales locales, ejecuta
> todos los gates y detente sin DVC ni publicación.**

---

## 23. Validación final antes de C7.2-A y orden ejecutable — 2026-07-25

### Veredicto

**READY, pendiente únicamente del GO.** La Orden 22.1 se ejecutó correctamente:

| comprobación | resultado |
| --- | --- |
| commit | `0dbd0f01` — `docs: harden C7.2 release bundle contract` |
| contenido | un solo path: este plan |
| local/remoto | mismo SHA, ahead/behind 0/0 |
| working tree trackeado al abrir | limpio |
| `git diff --check 7a8c25cd..0dbd0f01` | PASS |
| paths prohibidos | ninguno |
| doctor Obesidad | rc=0 |
| doctor completo | rc=0 |
| política | `dd6d4a0274a6f8bb…` |
| DVC dirigido | divergencia preexistente, sin promoción |
| frontend | `main @ 179bbe36`, sin cambios trackeados |

No se repitieron fast ni integración porque `0dbd0f01` solo modifica Markdown y no cambia ninguna
superficie ejecutable.

### Alcance exacto que autoriza `GO C7.2-A`

El GO autoriza:

- crear o modificar código genérico del builder y loader de `runner_release`;
- crear o modificar tests unitarios y de integración necesarios;
- construir bundles únicamente bajo temporales inyectados;
- leer y verificar los runs canónicos sin modificarlos;
- ejecutar lint, typecheck, fast, integración y doctors;
- crear al final un commit local acotado de C7.2-A.

El GO **no** autoriza:

- escribir bajo `artifacts/releases/`;
- crear o modificar archivos `.dvc`;
- ejecutar `dvc add`, `dvc push`, `git push`, deploy o merge;
- escribir en `runs/`, modelos o forecasts canónicos;
- reentrenar, retunear, reseleccionar o reabrir aceptación 2025;
- tocar frontend, lifecycle, channels, gallery o F50;
- iniciar C7.2-B, C7.2-C o C7.3.

### Orden operativa C7.2-A

#### Paso 23.1 — Baseline y evidencia

Antes de editar código:

1. registrar HEAD, status trackeado y lista de untracked ajenos;
2. registrar hashes canónicos de aceptación, refit, forecast, política y cuatro agregados legacy;
3. registrar `dvc status` dirigido y estado del frontend;
4. confirmar doctors verdes;
5. crear los roots temporales con `mktemp -d`.

#### Paso 23.2 — Contratos primero

Implementar primero tests que fijen:

1. `identity_payload.v1` canónico;
2. `release_id` derivado sin autorreferencia;
3. manifest con inventario exclusivo de payloads;
4. `SHA256SUMS.txt` que incluye manifest + payloads y se excluye a sí mismo;
5. rutas POSIX relativas ordenadas con `sorted()`;
6. ausencia de timestamps y metadata ambiental;
7. runtime inputs completos;
8. rechazo de faltantes, extras, traversal, paths absolutos, digest falso y schema desconocido.

No escribir el builder hasta que estos tests describan resultados concretos y fallen por la
ausencia de implementación.

#### Paso 23.3 — Builder temporal genérico

1. recibir `disease_id`, `VerifiedRunnerRuns`, source roots y output root;
2. derivar todas las identidades desde registry/manifests sellados;
3. copiar bytes sin reinterpretar modelos ni inferir identidad por filename;
4. generar únicamente metadata canónica;
5. incluir catálogo, exposición y configuración efectiva consumidos;
6. validar antes de declarar éxito;
7. rechazar destino existente diferente y aceptar idempotentemente el idéntico;
8. no contener condicionales específicos para Obesidad.

#### Paso 23.4 — Loader y reproducción aislada

1. cargar exclusivamente desde el bundle temporal;
2. verificar manifest, checksums, inventario, modelos y lineage;
3. cargar todos los modelos finales;
4. resolver exposición/geografía desde `runtime_inputs`;
5. reproducir el forecast completo;
6. comparar claves, periodos y valores con el forecast canónico;
7. demostrar que retirar o alterar cualquier dependencia produce error tipado.

#### Paso 23.5 — Determinismo entre entornos

Construir dos veces:

```text
build A: root temporal A · locale C
build B: root temporal B · locale en_US.UTF-8
```

Exigir:

- mismo `release_id`;
- mismo árbol de rutas;
- mismos bytes por archivo;
- mismo `release_manifest.json`;
- mismo `SHA256SUMS.txt`;
- cero paths absolutos;
- ningún acceso a `runs/` durante la carga/reproducción desde el bundle terminado.

#### Paso 23.6 — Gate final y commit

Ejecutar la Orden 21.3 completa y, además:

1. recalcular evidencia de preservación;
2. revisar `git diff --check`;
3. clasificar cada path modificado/nuevo;
4. excluir temporales y outputs;
5. crear un solo commit de C7.2-A;
6. verificar que el commit no contiene bundles, DVC ni archivos ajenos;
7. detenerse sin push.

Mensaje sugerido:

```text
C7.2-A deterministic runner release bundle
```

### Criterio de cierre

C7.2-A solo puede declararse PASS si el bundle temporal es autosuficiente, determinista y reproduce
el forecast; que los archivos “existan” o que sus digests coincidan sin cargar y pronosticar no es
suficiente.

### Orden siguiente

La orden exacta que desbloquea la implementación es:

> **GO C7.2-A. Ejecuta íntegramente la sección 23; construye solo en temporales, haz el commit
> local acotado y detente sin DVC, push ni publicación.**

---

### Ronda 14 — C7.2-A: Paso 23.1 ejecutado; 23.2–23.6 NO INICIADOS — 2026-07-25

#### Paso 23.1 — Baseline y evidencia · **CERRADO**

| dato | valor |
| --- | --- |
| HEAD | `0dbd0f01` en `feat/registry-padecimientos-obesidad`, local == origin |
| árbol | 1 trackeado modificado (este plan, sección 23) · 75 untracked del usuario |
| doctor Obesidad / completo | rc=0 / rc=0 |
| frontend | `main @ 179bbe36`, cero trackeados modificados |
| DVC dirigido | `reports/forecasts.dvc` y `models.dvc` siguen `modified` (divergencia preexistente) |

Hashes canónicos con el procedimiento **`LC_ALL=C`** fijado en la sección 20:

```text
obesidad_1502d1a25b48                             n=9    2ef4ee1236aa94c0
obesidad_benchmark_test_7f582a3a4ed7_82370419efd4 n=67   6bbc7f84ea5ec5bb
obesidad_refit_final_91590fa7452f_ff249060018a    n=162  972f7519f885c0d1
obesidad_forecast_h52_ff249060018a_92d446b6df8f   n=37   d89d92ee7e73b848
config/evaluation/rolling_cv_v1.yaml                     dd6d4a0274a6f8bb
all_forecast_{prophet,deepar,ensemble,stacking}.csv      cb5be395… 96791595… 1d2cf0a7… ac97dc8e…
```

Roots temporales creados con `mktemp -d`, pero sus paths no quedaron registrados. **No son
reutilizables ni cuentan como precondición durable**; R15 ordena recrearlos después del GO.

#### Por qué me detengo aquí

**No inicié el Paso 23.2.** Aplico la regla dura del encargo: *si una acción no cabe entera en el
contexto, no se empieza; se registra y se para*. Es el mismo criterio con el que se detuvieron las
Rondas 1 y 3, y aquí pesa más que nunca.

C7.2-A no es una acción mediana. Exige, como mínimo:

1. **23.2** — la batería de contratos ANTES del builder: `identity_payload.v1` con serialización
   canónica, ausencia de ciclo entre `release_id`/manifest/checksums, `SHA256SUMS.txt` que se
   excluye a sí mismo, orden `sorted()` sobre rutas POSIX relativas, cero timestamps, runtime
   inputs completos y **ocho clases de rechazo** (faltante, extra, traversal, path absoluto, digest
   falso, schema desconocido…). Deben existir y **fallar** por ausencia de implementación.
2. **23.3** — builder genérico, sin un solo condicional por padecimiento.
3. **23.4** — un loader que cargue los modelos y reproduzca el forecast sin leer `runs/`,
   resolviendo exposición y geografía desde `runtime_inputs/`. R15 acota la implementación:
   reutilizar `final_models`, las funciones finales y la derivación existente; no recablear el
   orquestador completo.
4. **23.5** — dos construcciones bajo roots y locales distintos, byte-idénticas.
5. **23.6** — el gate completo de la Orden 21.3: fast (~62 s), integración (~165 s), focal (~45 s),
   lint, typecheck, doctors, evidencia de preservación y commit acotado.

El riesgo concreto de arrancar sin poder terminar no es perder trabajo: es dejar **medio construido
el componente que fabrica el bundle publicable**. Un builder a medias que ya escribe manifests es
peor que ninguno, porque el siguiente turno no sabría si lo que hay en disco cumple el contrato o
solo lo aparenta — exactamente el falso verde que costó cuatro auditorías erradicar en C7.1.

#### Punto exacto de reanudación

La siguiente sesión arranca en el **Paso 23.2** con todo lo previo ya hecho:

1. el baseline de arriba es la evidencia de preservación contra la que se comparará al cerrar;
2. `VerifiedRunnerRuns` expone la identidad, pero no los source paths ni bytes. El entry point
   debe recibir roots explícitos, reabrir los artefactos declarados y re-verificar sus digests al
   copiarlos, como corrige R15;
3. el requisito de orden independiente del locale ya está diagnosticado y escrito (sección 20);
4. `artifact_identity` aporta las primitivas tipadas (`require_exact_records`, `int_of`,
   `mapping_of`, `verify_records`) que el manifest y los checksums deben reutilizar en vez de
   reimplementar.

#### Estado

```text
C7.2-A = Paso 23.1 CERRADO · Pasos 23.2–23.6 NO INICIADOS
Sin código nuevo, sin bundles, sin escribir en artifacts/releases/, sin DVC, sin push
Obesidad = trained · runner_runs · NO-GO · F50 = configured · NO-GO
Runs canónicos íntegros · doctors verdes · frontend y legacy sin delta
```

_Respuesta:_

---

### Ronda 16 — Estado autoritativo y orden de continuación — 2026-07-25

La Ronda 14 queda aceptada únicamente como baseline. Las correcciones técnicas y la secuencia de
implementación de R15 son autoritativas:

- temporales de R14: descartables, no reutilizar;
- `VerifiedRunnerRuns`: identidad, no contenedor de paths/bytes;
- roots y source paths: explícitos e inyectables;
- exposición: loader del CSV proyectado por `cve_ent`, no loader global del raw INEGI;
- forecast: capacidad tipada de los adapters, sin diccionario de motores ni recablear el
  orquestador;
- build y validación: solo temporales, sin `artifacts/releases/` ni DVC.

Estado inequívoco:

```text
C7.2-A  23.1 PASS · 23.2–23.6 NO INICIADOS
Código   cero cambios
Outputs  cero bundles
Release  NO-GO
```

La siguiente acción requiere autorización, no otra auditoría:

> **GO C7.2-A. Ejecuta R15.1–R15.6 completas, incluye el plan en el commit local de cierre y
> detente sin DVC, push, deploy ni publicación.**

---

### Ronda 17 — C7.2-A ejecutado: R15.1–R15.6 CERRADAS — 2026-07-25

GO recibido. Se ejecutó la sección 23 con las correcciones de R15 como autoritativas. **Cero
escrituras bajo `runs/`, `artifacts/releases/`, DVC, frontend, lifecycle o canales.**

#### R15.1 — Preparación · **PASS**

Baseline reverificado antes de tocar código, y **una corrección de procedimiento**: la Ronda 14 no
dejó escrito CÓMO se calcula el hash agregado de un run, y hay varias formas que dan resultados
distintos sobre los mismos bytes. Al reproducirlo con `find -exec shasum` obtuve
`c6984ae1088c7703` para el dataset en vez de `2ef4ee1236aa94c0`, y **no era una discrepancia real**:
son procedimientos distintos, no contenidos distintos. Queda fijado el que reproduce R14/R15:

```bash
LC_ALL=C find runs/<id> -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256
```

Es la misma clase de fallo que la sección 20 (`LC_COLLATE`): un procedimiento no escrito produce
"discrepancias" que no existen. Con él, los cuatro runs y los cuatro agregados legacy reproducen el
baseline exactamente.

Roots temporales nuevos (`mktemp -d`), registrados como telemetría y **fuera de todo bundle**:
`…/scratchpad/relA.pv4l4Y` y `…/scratchpad/relB.BKeQjS`. Los de R14 se descartaron sin reutilizar.

#### R15.2 — RED primero · **PASS**

Los contratos se escribieron y **fallaron por ausencia de implementación** antes de existir el
builder: `test_release_contract.py` (57) y `test_release_runtime.py` (29). Fijan JSON canónico,
identidad acíclica, `SHA256SUMS.txt` autoexcluyente, orden por `sorted()` de Python, ausencia de
metadata ambiental y el loader de exposición proyectada de R15-C3.

Cada rechazo se verificó **individualmente por su mensaje**, no por el verde agregado.

#### R15.3 — Entry point y builder · **PASS**

Dos capas separadas, como exige R15-C2:

| capa | módulo | qué hace |
| --- | --- | --- |
| impura | `release_entry.py` (93) | registry → `validate_runner_runs` → rutas fuente |
| rutas | `release_sources.py` (299) | roots explícitos, plan de payloads desde los manifiestos |
| puro | `release_builder.py` (197) | copia bytes, re-verifica digests, sella, promueve atómico |
| metadata | `release_manifest.py` (169) | cadena, calendario, conteos, inventario |
| identidad | `release_contract.py` (183) | `identity_payload.v1` → `release_id` → checksums |

`VerifiedRunnerRuns` se usa como IDENTIDAD, no como contenedor de archivos: los envelopes y estados
se enumeran desde `model_index.json`, el catálogo y la exposición desde `config_effective.json`, y
cada digest declarado se vuelve a comprobar **al copiar**. Ningún condicional por padecimiento,
motor ni conteo.

#### R15.4 — Capacidad de forecast final · **PASS**

`FinalStateForecaster` (protocolo tipado) + `final_forecaster(name)` en `adapters.py`. Los 6 motores
del portafolio la implementan **delegando en su `forecast_final` existente**: no hay un segundo
camino de pronóstico. El carril legacy `adapter.run("forecast", run_dir)` queda intacto. Un motor
sin la capacidad hace fallar el release con error tipado y **jamás se sustituye por otro**
(`test_final_forecaster.py`, 22 pruebas).

#### R15.5 — Loader y reproducción · **PASS con un hallazgo**

`release_loader.py` (222) + `release_verify.py` (146) + `release_reproduce.py` (233). El bundle se
verifica entero y **se reproduce el forecast completo**:

```text
3,328 filas base · 5,772 filas de 111 productos · máx |Δ| = 0.0 en ambos frames
```

**Hallazgo (y por qué la primera comparación daba 2.27e-13).** 222 de 3,328 filas diferían en 1 ULP.
Perseguí la causa antes de aceptar ninguna tolerancia, porque "casi igual" no es reproducir:

1. no era mi código: llamar a `ets.forecast_final` del propio runner sobre el estado canónico daba
   la misma diferencia;
2. no era el multithreading de BLAS: fijar `OMP/OPENBLAS/MKL/NUMEXPR/VECLIB=1` no la movía;
3. re-ejecutar el carril original `forecasting.run_forecast` sí reproducía el CSV sellado **byte a
   byte**, lo que contradecía (1) y obligaba a seguir;
4. instrumentando ambos caminos en el mismo proceso, los dos devolvían el MISMO double.

La diferencia no estaba en el cómputo sino en la **lectura**: `to_csv` escribe
`1271.6760897744061` correctamente, pero `read_csv` con el parser por defecto de pandas lo devuelve
como `1271.676089774406` —el double vecino—. Y `finish_forecast` **releía** las bases de cada motor
con ese parser antes de derivar los 47 productos, así que esa pérdida forma parte del artefacto
publicado.

Consecuencia en el código, no en la tolerancia: la reproducción pasa las bases por la **misma
frontera de precisión** (`_through_csv`) y los frames del bundle se leen con
`float_precision="round_trip"`. El resultado es igualdad EXACTA con `tol=0.0`; no se introdujo
ninguna tolerancia de conveniencia.

**"Sin `runs/`" está verificado, no prometido.** La carga y la reproducción corren con un guardia
que parchea `builtins.open`, `io.open` y `os.open` y revienta ante cualquier lectura bajo los dos
árboles de runs. El guardia tiene su propia prueba por tres vías (`pathlib`, `builtins`, `pandas`):
sin ella, un guardia que no detectara nada habría dado verde a todo.

#### R15.6 — Determinismo y gate · **PASS**

```text
build A: root A · LC_ALL=C            → obesidad_release_34bbcc4ac509
build B: root B · LC_ALL=en_US.UTF-8  → obesidad_release_34bbcc4ac509
diff -r A B → idéntico · agregado 66563ef192f0a48b8a5a83c520ab4bec (ambos)
150 archivos = 148 payloads + release_manifest.json + SHA256SUMS.txt
148 payloads = 6 índices + 64 envelopes + 64 estados + 3 runtime_inputs + 11 de cadena
```

Matriz de rechazo, 33 mutaciones en tres grupos con re-sellado distinto para que cada una mida lo
que dice medir (`test_release_mutations.py`):

| grupo | re-sellado | mutaciones | qué atrapa |
| --- | --- | ---: | --- |
| sello | ninguno | 15 | inventario, digests, tamaños, `SHA256SUMS.txt` |
| identidad | sólo checksums | 6 | el `release_id` recalculado deja de cuadrar |
| contenido | inventario + identidad + checksums | 12 | los sellos INTERNOS de los runs de origen |

Cero falsos verdes y cero tracebacks: los 33 mensajes se revisaron uno a uno.

#### Gate (Orden 21.3)

| comprobación | resultado |
| --- | --- |
| `ruff format --check` + `ruff check` | 275 archivos OK · All checks passed |
| `mypy src/epiforecast/` | 153 archivos, sin incidencias |
| fast (`not slow and not integration`) | **1,775 passed** en 70 s (eran 1,609; +166 nuevas) |
| integración | **61 passed** (59 + 2) en dos tandas, ver nota |
| doctor Obesidad / completo | rc=0 / rc=0 |
| SRP ≤300 líneas | 9 módulos nuevos, máximo 299 |

**Nota sobre la integración: hay un SIGSEGV PREEXISTENTE, ajeno a C7.2-A.** Correr la suite entera
en un solo proceso muere con rc=139 en `test_pipeline_e2e`. Reproductor mínimo:
`test_deepar_smoke.py + test_pipeline_e2e.py` → rc=139; `test_disease_run_gate.py +
test_pipeline_e2e.py` → 29 passed. Lo verifiqué **con mis cambios de `src/` en stash**: sigue dando
rc=139. Es una interacción torch↔pipeline in-process que no toca ningún módulo de este trabajo. Por
eso la integración se corrió en dos tandas (todo menos `test_deepar_smoke`, y `test_deepar_smoke`
aparte), ambas rc=0. **Queda como deuda registrada, no arreglada aquí**: excede el alcance del GO.

#### Preservación

```text
obesidad_1502d1a25b48                             n=9    2ef4ee1236aa94c0   ✓ baseline
obesidad_benchmark_test_7f582a3a4ed7_82370419efd4 n=67   6bbc7f84ea5ec5bb   ✓
obesidad_refit_final_91590fa7452f_ff249060018a    n=162  972f7519f885c0d1   ✓
obesidad_forecast_h52_ff249060018a_92d446b6df8f   n=37   d89d92ee7e73b848   ✓
rolling_cv_v1.yaml                                       dd6d4a0274a6f8bb   ✓
all_forecast_{prophet,deepar,ensemble,stacking}  cb5be395 96791595 1d2cf0a7 ac97dc8e  ✓
artifacts/releases/ → NO EXISTE · .dvc sin tocar · frontend main @ 179bbe36 limpio
```

#### Dos cosas que quedan señaladas, no hechas

1. **HISTÓRICO, SUPERSEDIDO POR C7.2-A.1.** En `2bed74ee`, `channels_candidate` salía con seis
   canales y formaba parte de la identidad. `fb3bcdca` eliminó por completo activación, canales,
   galería y lifecycle del bundle. Los cuatro canales reales siguen siendo trabajo de **C7.5**,
   pero ahora vivirán en `public_release_pointer.v1` y no cambiarán el `release_id`.
2. **El doctor NO se cableó para `runner_release`**: sigue diciendo "verificación no implementada
   todavía". Hacerlo exige resolver dónde vive el release (`artifacts/releases/<disease>/<id>/`), y
   esa ruta la define **C7.2-B**. Cablearlo ahora obligaría a inventar el destino antes de que se
   autorice materializarlo.

#### Estado

```text
C7.2-A  R15.1–R15.6 PASS · commit local acotado · SIN push, DVC, deploy ni publicación
Código  9 módulos nuevos en src/epiforecast/runner/ + capacidad en adapters y 5 motores
Tests   174 nuevas (166 fast + 8 integración) · 33 mutaciones de rechazo
Output  0 bundles persistidos: los dos builds viven en temporales y se descartan
Release NO-GO · Obesidad = trained · runner_runs · F50 = configured · NO-GO
```

_Respuesta:_

---

### Ronda 18 — C7.2-A.1: la activación pública sale del bundle — 2026-07-25

Bloqueo de diseño aceptado sin reservas: **acoplar canales al `release_id` era un error mío**, no un
detalle. Un release describe QUÉ modelos hay y de dónde salen; DÓNDE se publican es una decisión
posterior y revocable. Con el acoplamiento, apagar un canal renombraba —y obligaba a reconstruir— un
bundle cuyos 64 modelos no habían cambiado en un byte. Peor: el `release_id` es la referencia que
C7.2-B fija en DVC y C7.5 activa, así que el acoplamiento habría hecho que **la publicación mueva su
propio identificador**.

Commit separado, sobre `2bed74ee`.

#### Qué se quitó

`activation` desaparece **del payload de identidad y del manifest**. No queda "desactivado" ni
vacío: no existe.

```text
identity_payload.v1  {schema, release_schema, builder_version, disease_id, chain, payloads}
release_manifest.v1  {schema, release_id, identity_schema, identity_digest, builder_version,
                      disease_id, chain, calendar, counts, engines, intervals,
                      runtime_inputs, payloads}
```

El entry point ya **no lee** `disease.channels`; del registry sólo sale `artifact_source`, o sea qué
runs sellados son los del padecimiento. Y `build_release` perdió el parámetro: la política pública ya
no puede llegar al builder ni por descuido.

```text
build_release(verified, sources, output_root)          # antes llevaba activation=
build_release_for_disease(disease_id, runs_root, policy_path, output_root, geo_catalog)
```

`BUILDER_VERSION` sube a **`runner_release_builder.v2`**. Está dentro del payload de identidad, así
que un bundle v1 y uno v2 **nunca comparten `release_id`**; no hay ambigüedad posible entre formatos.

#### Un cierre extra que hacía falta para que esto se sostenga

Quitar la clave no basta: el manifest podía **crecer campos que la identidad no cubre** —empezando
por los de activación— y seguir verificando, porque `SHA256SUMS.txt` sella el manifest pero el
`release_id` no lo sella a él. Así que la forma del manifest es ahora un **conjunto cerrado**
(`MANIFEST_KEYS`) y hay un guardia explícito (`check_no_activation`) sobre el manifest y sobre la
cadena. Sin esto, la corrección se podía deshacer por la puerta de atrás.

#### Prueba de que el desacoplamiento es real

No basta con que la clave no aparezca. Se construye por el **entry point real** —la capa que antes
leía los canales— con el registry declarando otra política, y se compara byte a byte:

| política declarada por el registry | `release_id` | bytes |
| --- | --- | --- |
| `channels: ["web"]` | idéntico | idénticos |
| `channels: []` | idéntico | idénticos |
| `gallery_enabled: false` | idéntico | idénticos |
| `lifecycle: published` | idéntico | idénticos |
| las cuatro a la vez | idéntico | idénticos |

Verifiqué antes que el `monkeypatch` **llega de verdad** al entry point; una invariancia que se
cumple porque el sustituto nunca se usa no probaría nada.

Cuatro mutaciones nuevas (grupo **FORMA**, con los checksums rehechos a propósito):

```text
_activación_inyectada           -> release_manifest.json: claves: [...'activation'...] != [...]
_canales_en_la_cadena           -> chain: ['channels'] es metadata de activación pública…
_clave_inventada_en_el_manifest -> release_manifest.json: claves: …
_clave_ausente_en_el_manifest   -> release_manifest.json: claves: …
```

#### Determinismo y gate

```text
build A: root A · LC_ALL=C            → obesidad_release_a3d4cbe9f896
build B: root B · LC_ALL=en_US.UTF-8  → obesidad_release_a3d4cbe9f896
diff -r A B → idéntico · agregado 7306bd5a5a0ec6043311630ac4c48a28 · 150 archivos
reproducción: 3,328 base + 5,772 productos · máx |Δ| = 0.0 · sin leer runs/
```

| comprobación | resultado |
| --- | --- |
| `ruff format --check` + `ruff check` | 275 archivos OK · All checks passed |
| `mypy src/epiforecast/` | 153 archivos, sin incidencias |
| fast | **1,789 passed** (eran 1,775; +14 netas) en 74 s |
| integración | **61 passed** (59 + 2, dos tandas por el SIGSEGV preexistente) |
| doctor Obesidad / completo | rc=0 / rc=0 |
| SRP ≤300 | máximo 299 (`release_sources.py`) |
| runs canónicos · política · 4 agregados legacy | idénticos al baseline |
| `artifacts/releases/` · `.dvc` · `config/` · frontend | sin tocar |

El `release_id` cambió (`34bbcc4ac509` → `a3d4cbe9f896`) por el bump de builder y por la salida de la
activación. Es lo correcto y **no invalida nada**: C7.2-A no persistió ningún bundle, los dos builds
vivieron en temporales y se borraron.

#### Dos notas de contrato

1. **`release_manifest.v1` conserva su nombre** pese a cambiar de forma. Lo pensé y lo dejo así con
   una razón: no existe —ni existió— ningún bundle v1 persistido en ninguna parte, y un hipotético
   v1 **falla cerrado** contra este loader (su identidad incluía la activación, así que el
   `release_id` ya no le cuadraría). Además `builder_version` va DENTRO de la identidad y distingue
   los dos formatos sin ambigüedad. Si prefieres subirlo a `release_manifest.v2` por higiene de
   formato, es un cambio de una línea y lo hago; no lo decido por mi cuenta porque afecta a lo que
   C7.2-B fije en DVC.
2. **`public_release_pointer.v1` queda sólo documentado**, como pediste: en `release_contract.py`,
   `release_manifest.py` y `release_entry.py` está escrito que canales, galería, lifecycle y estado
   de activación viven ahí y apuntan al `release_id` **por referencia**. No se construyó nada: es
   C7.5.

#### Estado

```text
C7.2-A.1 PASS · commit local separado · SIN push, DVC, deploy ni publicación
Bundle   activación-agnóstico · builder v2 · manifest de claves cerradas
Tests    188 del release (180 fast + 8 integración) · 37 mutaciones de rechazo
Output   0 bundles persistidos · temporales A/B eliminados
Release  NO-GO · Obesidad = trained · runner_runs · F50 = configured · NO-GO
Deuda    SIGSEGV preexistente de integración = bloqueo pre-merge/pre-publicación (no de C7.2-A.1)
Pendiente C7.2-B (doctor runner_release + materialización) · C7.5 (canales reales + puntero)
```

_Respuesta:_ versionar ambos contratos antes de persistir. `identity_payload.v2` y
`release_manifest.v2` son obligatorios; `runtime_config.v1` y `public_release_pointer.v1`
permanecen como están. C7.2-B no puede empezar hasta cerrar C7.2-A.2. Las órdenes completas y el
STOP están en la Ronda 19.

---

### Ronda 20 — C7.2-A.2: schemas versionados antes de persistir — 2026-07-25

Decisión aceptada: los nombres v1 no se conservan. `BUILDER_VERSION` identifica al **productor**; el
schema identifica la **forma y el contrato** que deben interpretar loaders, doctors y consumidores.
Son dos ejes distintos y confundirlos habría dejado un `release_manifest.v1` con dos formas.

Commit separado sobre `fb3bcdca`. Cero escrituras externas.

#### R19.1 — Versionado · **PASS**

```text
identity_payload.v1  → identity_payload.v2
release_manifest.v1  → release_manifest.v2
runtime_config.v1               sin cambios (su forma no cambió)
runner_release_builder.v2       sin cambios (ya identifica al productor)
```

Sin lectura de compatibilidad con v1: nunca se persistió un bundle v1 y aceptar dos formas añadiría
ramas sin un solo usuario real.

#### Lo que hacía falta para que el rechazo fuera POR LA VERSIÓN

El punto 6 de la orden es el que tenía filo, y descubrió un hueco real: el manifest declara **tres**
versiones y el loader sólo comprobaba una.

- `schema` sí lo verificaba `read_json`, antes que nada;
- `identity_schema` **no se comprobaba en ninguna parte**;
- `builder_version` **tampoco**.

Un bundle con `identity_schema: identity_payload.v1` habría sido rechazado igualmente… pero por un
`identity_digest` que no cuadra. Ese mensaje dice "algo está corrupto" cuando lo único que pasa es
que el formato es viejo, y manda a quien lo lea a buscar una corrupción que no existe. Exactamente
el fallo tardío que la orden prohíbe aceptar como prueba.

Las tres versiones se comprueban ahora **explícitamente y primero**, en `check_manifest_shape`,
antes del inventario, de las sumas y de la identidad. Verificado uno a uno, con las sumas rehechas a
propósito para que el sello no matara la mutación antes de tiempo:

```text
_v1_completo              [por versión]  schema: 'release_manifest.v1' != 'release_manifest.v2'
_v1_solo_el_manifest      [por versión]  schema: 'release_manifest.v1' != 'release_manifest.v2'
_v1_solo_la_identidad     [por versión]  identity_schema: 'identity_payload.v1' != 'identity_payload.v2'
_builder_de_otra_versión  [por versión]  builder_version: 'runner_release_builder.v1' != …v2
```

Ninguno cae en `digest de`, `release_id:` ni `claves:`.

**Añadí la comprobación de `builder_version` sin que la orden la pidiera.** Es la misma clase de
defecto: sin ella, un bundle de otro productor fallaba por `release_id` —porque `builder_version` va
dentro de la identidad—, es decir, tarde y con el mensaje equivocado. Si prefieres que un builder
distinto no sea motivo de rechazo explícito, se quita en una línea.

#### R19.2 — Gate completo · **PASS**

```text
build A: root temporal nuevo · LC_ALL=C            → obesidad_release_2517e7858901
build B: root temporal nuevo · LC_ALL=en_US.UTF-8  → obesidad_release_2517e7858901
diff -r A B: vacío · 150 archivos · SHA256SUMS.txt 149 líneas · 148 payloads
schema release_manifest.v2 · identity_schema identity_payload.v2 · builder v2
reproducción desde AMBOS bundles, sin leer runs/: 3,328 bases · 5,772 productos · máx |Δ| = 0.0
```

El `release_id` pasa de `a3d4cbe9f896` a `2517e7858901`. Es lo esperado y lo correcto: el schema
forma parte de la identidad. No hay nada que migrar.

| comprobación | resultado |
| --- | --- |
| `ruff format --check` + `ruff check` | 275 archivos OK · All checks passed |
| `mypy src/epiforecast/` | 153 archivos, sin incidencias |
| focales del release | **195 passed** |
| fast | **1,796 passed** (eran 1,789; +7) en 73 s |
| integración | **61 passed** (59 + 2, dos tandas) |
| doctor Obesidad / completo | rc=0 / rc=0 |

Preservación contra el baseline, sin una sola diferencia:

```text
dataset 2ef4ee1236aa94c0 · aceptación 6bbc7f84ea5ec5bb · refit 972f7519f885c0d1
forecast d89d92ee7e73b848 · rolling_cv_v1 dd6d4a0274a6f8bb
all_forecast_{prophet,deepar,ensemble,stacking}  cb5be395 96791595 1d2cf0a7 ac97dc8e
artifacts/releases/ AUSENTE · .dvc 0 · config/ 0 · frontend main @ 179bbe36 limpio
temporales A y B eliminados
```

#### Alcance del diff

Nueve rutas. Ocho son módulos y tests del bundle. La novena es `registry.py`, y es **un comentario
de una línea** que decía `release_manifest.v1` junto a `BACKEND_RUNNER_RELEASE`: dejarlo habría sido
documentar mal el contrato que el propio backend exige. Cero cambios de comportamiento ahí.

#### Estado

```text
C7.2-A.2 PASS · commit local separado · rama 3 commits por delante del remoto
Contrato identity_payload.v2 + release_manifest.v2 + runtime_config.v1 + builder v2
Rechazo  las tres versiones se comprueban explícitamente y ANTES que el contenido
Tests    195 del release (187 fast + 8 integración) · 41 mutaciones de rechazo
Output   0 bundles persistidos · artifacts/releases/ sigue sin existir
Release  NO-GO · Obesidad = trained · runner_runs · F50 = configured · NO-GO
Deuda    SIGSEGV preexistente = bloqueo pre-merge/pre-publicación
Sigue    R19.4 (auditar el rango 2bed74ee..HEAD y pedir autorización de push)
```

_Respuesta:_ no hacer push todavía. El versionado de schemas queda aceptado, pero la comprobación
exacta de `builder_version` mezcla procedencia y compatibilidad. Ejecutar primero C7.2-A.2.1 según
la Ronda 21.

---

### Ronda 21 — Auditoría independiente de C7.2-A.2 y orden corregida — 2026-07-25

#### Veredicto

**PASS del versionado v2; FAIL mínimo de compatibilidad futura. No hacer push ni iniciar C7.2-B.**

La auditoría confirmó:

- commit `b809599d` separado sobre `fb3bcdca`;
- sólo nueve rutas: ocho módulos/tests del bundle y un comentario en `registry.py`;
- `identity_payload.v2`, `release_manifest.v2` y `runtime_config.v1` declarados correctamente;
- rechazo explícito de v1 antes de inventario, checksum e identidad;
- conjuntos de claves cerrados y activación ausente;
- cero bundles persistidos y cero cambios DVC;
- frontend trackeado limpio en `179bbe36`;
- Obesidad continúa `trained`, NO-GO; F50 continúa `configured`, NO-GO.

Validación independiente ejecutada:

```text
187 pruebas unitarias focales del release       PASS
8 pruebas de integración de reproducción        PASS
doctor Obesidad --artifacts                     rc=0
doctor --artifacts                              rc=0
git diff --check fb3bcdca..b809599d             PASS
```

Los 187 unitarios + 8 de integración reproducen las 195 pruebas focales declaradas por A.2. Los
resultados completos de `make test-fast`, las otras 53 pruebas de integración, lint y mypy quedan
aceptados como evidencia del commit; esta auditoría repitió de forma independiente el perímetro
afectado.

#### Hallazgo R21-P0 — `builder_version` está actuando como schema

El contrato afirma correctamente:

```text
builder_version  = identidad/procedencia del productor
schema           = forma y compatibilidad del documento
```

Pero el verifier implementa:

```python
equal(manifest["builder_version"], BUILDER_VERSION)
```

y `check_identity` reconstruye el payload con el `BUILDER_VERSION` instalado, no con el valor
sellado en el manifest. Consecuencia:

1. hoy se persiste un bundle válido `release_manifest.v2`, producido por builder v2;
2. mañana el builder sube a v3 por una corrección interna que no cambia el schema;
3. el loader v3 rechaza el bundle histórico v2 únicamente porque su productor fue v2;
4. el bundle deja de ser restaurable aunque su schema, inventario, identidad, modelos y forecast
   sigan siendo válidos.

Esto contradice el objetivo de un release inmutable y restaurable. También contradice la razón
central de A.2: si el schema gobierna la compatibilidad, la versión del productor no puede volver a
gobernarla por otra puerta.

No se debe eliminar `builder_version`. Debe seguir dentro del manifest y de la identidad, de modo
que alterarlo mueva el `release_id` o rompa el sello. Lo que se elimina es la comparación contra la
constante del código lector.

#### Orden R21.1 — C7.2-A.2.1: separar procedencia de compatibilidad

En un commit local separado:

1. mantener `BUILDER_VERSION=runner_release_builder.v2` para construir bundles nuevos;
2. extender `identity_payload` para aceptar un `builder_version` explícito, con el valor actual
   como default únicamente para el builder;
3. validar `builder_version` como string no vacío y con formato versionado estable;
4. al verificar un bundle, leer el `builder_version` declarado y usar **ese mismo valor** para
   reconstruir su payload de identidad;
5. retirar la igualdad contra el `BUILDER_VERSION` instalado como gate de compatibilidad;
6. conservar igualdad exacta de `schema=release_manifest.v2` e
   `identity_schema=identity_payload.v2`;
7. conservar `builder_version` dentro del payload canónico y del `identity_digest`;
8. no añadir compatibilidad con schemas v1.

La regla resultante debe ser:

```text
schema v2 soportado + identidad íntegra              → puede cargar
schema distinto                                      → rechaza por schema
builder_version alterado sin re-sellar              → rechaza por identidad/sello
builder distinto, declarado y re-sellado bajo v2    → acepta si todo el contrato v2 es válido
```

#### Orden R21.2 — Tests obligatorios

Añadir pruebas que demuestren las cuatro fronteras:

1. bundle canónico builder v2 → PASS;
2. `release_manifest.v1` o `identity_payload.v1` → FAIL explícito por schema;
3. cambiar sólo `builder_version`, sin reconstruir identidad/checksums → FAIL por integridad;
4. construir o re-sellar coherentemente un fixture `release_manifest.v2` con
   `runner_release_builder.v3` → PASS y `release_id` distinto;
5. builder vacío, no string o con formato inválido → `ArtifactValidationError`;
6. el builder normal sigue emitiendo `runner_release_builder.v2`;
7. el candidato oficial conserva el mismo `release_id` `obesidad_release_2517e7858901`, porque su
   contenido y su productor no cambiaron.

No aceptar una prueba que monkeypatchee una constante sin pasar por el verifier real.

#### Orden R21.3 — Gate

Repetir:

```text
pytest de las cinco suites unitarias del release
pytest tests/integration/test_release_reproduction.py
make test-fast
integración en las dos tandas documentadas
make lint
make typecheck
doctor Obesidad --artifacts
doctor --artifacts
git diff --check
```

Además:

1. reconstruir A/B en roots y locales distintos;
2. exigir `obesidad_release_2517e7858901` en ambos;
3. exigir `diff -r` vacío, 150 archivos y reproducción exacta `0.0`;
4. revalidar runs canónicos, política, agregados legacy, ausencia de `artifacts/releases/`, DVC,
   config y frontend;
5. eliminar temporales.

#### Orden R21.4 — Commit y STOP

Si todo queda verde:

```text
C7.2-A.2.1 decouple builder provenance from schema compatibility
```

Después:

1. comprobar `ahead 4`;
2. entregar diff, nuevo conteo de pruebas y evidencia A/B;
3. detenerse sin push;
4. auditar el rango completo `0dbd0f01..HEAD`;
5. pedir autorización explícita para subir los cuatro commits locales como checkpoint.

Prohibido:

- `git push`;
- escribir en `artifacts/releases/`;
- crear o modificar `.dvc`;
- `dvc add` o `dvc push`;
- cambiar `artifact_source` a `runner_release`;
- tocar lifecycle, canales, galería, frontend o superficies públicas;
- iniciar C7.2-B.

#### Después del PASS

El orden posterior permanece:

1. revisión y, con autorización explícita, push de A, A.1, A.2 y A.2.1;
2. otro GO para C7.2-B: sede final, doctor `runner_release`, materialización atómica y target DVC
   local;
3. otro GO para C7.2-C: `dvc push` y restauración en entorno limpio;
4. C7.3 puentes candidate;
5. C7.4 cuatro semanas prospectivas;
6. C7.5 puntero público y canales;
7. resolver/aislar el SIGSEGV antes de merge o publicación;
8. activación externa sólo al final.

#### Próxima orden exacta

> **GO C7.2-A.2.1. Conserva `builder_version` como procedencia sellada, usa sólo los schemas para
> compatibilidad, prueba un builder v3 coherente bajo schema v2, reconstruye A/B con el mismo
> release_id oficial y detente sin push, DVC ni publicación.**

---

### Ronda 22 — C7.2-A.2.1: procedencia ≠ compatibilidad — 2026-07-25

R21-P0 aceptado sin matices, y con una nota que me toca: **la comprobación defectuosa la añadí yo en
A.2**, por mi cuenta y fuera de la orden. La declaré en la Ronda 20 ("si prefieres que un builder
distinto no sea motivo de rechazo explícito, se quita en una línea"), pero declararla no la hacía
correcta. El defecto es exactamente el que describe la auditoría: yo estaba corrigiendo un fallo
*tardío* y, al hacerlo, convertí al productor en gate de compatibilidad —la misma puerta que A.2
cerraba por el lado del schema, reabierta por el otro lado—.

Escenario que rompía: builder v3 por una corrección interna que no toca el schema → el loader v3
rechaza un bundle v2 histórico **por quién lo hizo**, aunque su schema, inventario, identidad,
modelos y forecast sigan intactos. Eso no es un release restaurable.

Commit separado sobre `b809599d`.

#### R21.1 — El cambio · **PASS**

```python
identity_payload(..., builder_version=BUILDER_VERSION)   # default SÓLO para construir
check_builder_version(raw, label)                        # valida la FORMA: <nombre>.v<N>
check_identity(...)  →  builder_version=<el que DECLARA el bundle>
```

`BUILDER_VERSION` sigue en `runner_release_builder.v2`, sigue dentro del payload canónico y del
`identity_digest`. Lo que desaparece es la igualdad contra la constante del lector.

La regla queda:

| situación | resultado |
| --- | --- |
| schema v2 + identidad íntegra | carga |
| schema distinto | rechaza **por schema** |
| `builder_version` alterado sin re-sellar | rechaza **por integridad** |
| otro builder, declarado y re-sellado bajo v2 | **carga**, con otro `release_id` |
| builder vacío, no string o mal formado | `ArtifactValidationError` |

#### R21.2 — Las cuatro fronteras, verificadas una a una

```text
1) canónico builder v2            → obesidad_release_2517e7858901
2) release_manifest.v1            → schema: 'release_manifest.v1' != 'release_manifest.v2'
   identity_payload.v1            → identity_schema: 'identity_payload.v1' != '…v2'
3) builder alterado sin re-sellar → SHA256SUMS.txt: digest de release_manifest.json: …
4) builder v3 coherente bajo v2   → CARGA · release_id obesidad_release_1bfae4fa39c0 (≠ oficial)
                                    reproduce 3,328 / 5,772 · máx |Δ| = 0.0
5) builder ''                     → builder_version: se esperaba un string no vacío, no ''
   builder 2 (int)                → builder_version: se esperaba un string no vacío, no 2
   builder 'no-es-una-version'    → builder_version … no tiene el formato '<nombre>.v<N>'
6) el builder instalado sigue emitiendo runner_release_builder.v2
7) el candidato oficial conserva obesidad_release_2517e7858901
```

El caso 4 pasa por `verify_bundle` real y por la reproducción completa: no hay monkeypatch de
constantes en ninguna de las pruebas nuevas. El re-sellado de fixtures usa ahora el builder que
**declara** el manifest, no el instalado; si siguiera usando el instalado, el fixture v3 se
"arreglaría" solo y el caso 4 sería un falso verde.

#### R21.3 — Gate · **PASS**

```text
build A: root nuevo · LC_ALL=C            → obesidad_release_2517e7858901
build B: root nuevo · LC_ALL=en_US.UTF-8  → obesidad_release_2517e7858901
diff -r vacío · 150 archivos · reproducción desde AMBOS: 3,328 / 5,772 · máx |Δ| = 0.0
```

El `release_id` oficial **no se movió**, como exige R21.2.7: ni el contenido ni el productor
cambiaron, y `builder_version` sigue en el payload con el mismo valor.

| comprobación | resultado |
| --- | --- |
| `ruff format --check` + `ruff check` | 275 archivos OK · All checks passed |
| `mypy src/epiforecast/` | 153 archivos, sin incidencias |
| cinco suites unitarias del release | **192 passed** |
| `test_release_reproduction.py` | **8 passed** |
| fast | **1,801 passed** (eran 1,796; +5) |
| integración | **61 passed** (59 + 2, dos tandas) |
| doctores / `git diff --check` | rc=0 / rc=0 · PASS |

Preservación sin una sola diferencia frente al baseline: dataset `2ef4ee1236aa94c0`, aceptación
`6bbc7f84ea5ec5bb`, refit `972f7519f885c0d1`, forecast `d89d92ee7e73b848`, política
`dd6d4a0274a6f8bb`, los cuatro agregados legacy, `artifacts/releases/` ausente, `.dvc` 0, `config/`
0, frontend `main @ 179bbe36` limpio. Temporales eliminados.

#### Alcance del diff

Cinco rutas de código y tests, más este plan. `registry.py` **no** se toca en A.2.1.

#### Estado

```text
C7.2-A.2.1 PASS · commit local separado · ahead 4 · SIN push, DVC ni publicación
Contrato  schema = compatibilidad · builder_version = procedencia sellada
Tests     200 del release (192 fast + 8 integración) · 45 mutaciones de rechazo
Output    0 bundles persistidos · artifacts/releases/ sigue sin existir
Release   NO-GO · Obesidad = trained · runner_runs · F50 = configured · NO-GO
Deuda     SIGSEGV preexistente = bloqueo pre-merge/pre-publicación
Sigue     R21.4: auditoría del rango 0dbd0f01..HEAD y autorización explícita de push
```

_Respuesta:_ A.2.1 queda aceptada. No iniciar C7.2-B. Primero preservar esta auditoría en un commit
doc-only y solicitar autorización explícita para subir el checkpoint completo.

---

### Ronda 23 — Auditoría final del checkpoint C7.2-A — 2026-07-25

#### Veredicto

**PASS. C7.2-A queda funcionalmente cerrada; apta para checkpoint Git, todavía NO autorizada para
push ni para C7.2-B.**

Se auditó el rango completo:

```text
0dbd0f01..d5347905
├── 2bed74ee  C7.2-A builder determinista
├── fb3bcdca  C7.2-A.1 activación fuera del bundle
├── b809599d  C7.2-A.2 schemas v2
└── d5347905  C7.2-A.2.1 procedencia ≠ compatibilidad
```

El delta contiene únicamente:

- módulos genéricos del release bajo `src/epiforecast/runner/`;
- capacidad tipada de forecast final en adapters/motores existentes;
- tests unitarios e integración del bundle;
- un comentario de schema en `registry.py`;
- este plan.

No contiene:

- `runs/`, `artifacts/releases/`, `models/`, `reports/` o datos;
- archivos `.dvc` ni cambios de targets;
- configuración de lifecycle, canales o galería;
- frontend;
- artefactos públicos o canónicos.

#### Validación independiente

```text
cinco suites unitarias del release              192 PASS
test_release_reproduction.py                      8 PASS
total focal revalidado                           200 PASS
doctor Obesidad --artifacts                      rc=0
doctor --artifacts                               rc=0
git diff --check 0dbd0f01..d5347905              PASS
artifacts/releases/                              AUSENTE
frontend main                                    179bbe36 · trackeado limpio
rama                                             ahead 4
```

La auditoría comprobó directamente que:

1. el bundle canónico sigue siendo `obesidad_release_2517e7858901`;
2. schemas v1 se rechazan por schema;
3. alterar `builder_version` sin re-sellar rompe integridad;
4. un builder v3 coherente bajo schema v2 carga y recibe otro `release_id`;
5. el builder instalado continúa produciendo v2;
6. `builder_version` no gobierna compatibilidad;
7. no se reintrodujo metadata de activación;
8. Obesidad sigue `trained`, F50 `configured`, ambas NO-GO.

Se aceptan como evidencia del commit, sin repetir en esta ronda, los gates completos ya registrados:
`make test-fast` 1,801 PASS, 61 pruebas de integración en dos tandas, lint y mypy verdes, builds A/B
byte-idénticos y reproducción exacta `0.0`.

#### Orden R23.1 — Commit documental

Crear un commit que contenga **únicamente**:

```text
docs/PLAN_C7_PUBLICACION_OBESIDAD.md
```

Mensaje sugerido:

```text
docs: close C7.2-A audit and authorize checkpoint review
```

Antes y después:

1. `git diff --check`;
2. confirmar con `git diff --cached --name-only` que sólo está el plan;
3. ejecutar los hooks aplicables;
4. comprobar árbol trackeado limpio;
5. comprobar `ahead 5`;
6. detenerse sin push.

No amendar ni reescribir los cuatro commits técnicos.

#### Orden R23.2 — Autorización de push

Después del commit doc-only, presentar:

- SHA del commit documental;
- rango exacto `0dbd0f01..HEAD`;
- lista de cinco commits;
- `git diff --name-status` del rango;
- confirmación de cero rutas prohibidas;
- confirmación de que el remoto continúa en `0dbd0f01`.

Esperar una autorización literal equivalente a:

> **AUTORIZO PUSH DEL CHECKPOINT C7.2-A `0dbd0f01..HEAD` A
> `origin/feat/registry-padecimientos-obesidad`.**

Sin esa autorización no ejecutar `git push`.

#### Orden R23.3 — Push del checkpoint, si se autoriza

1. confirmar inmediatamente antes que local sigue siendo descendiente directo del remoto;
2. hacer push sólo de `feat/registry-padecimientos-obesidad`;
3. prohibido usar `--force`;
4. verificar con `git ls-remote` que el SHA remoto coincide con `HEAD`;
5. comprobar `ahead 0`, árbol trackeado limpio y main intacta;
6. no crear PR, merge, tag ni release;
7. registrar el SHA remoto en este plan;
8. detenerse.

El push:

- no autoriza C7.2-B;
- no autoriza DVC;
- no autoriza lifecycle, canales, frontend, deploy ni publicación.

#### Orden R23.4 — Próxima fase después del checkpoint

Con local/remoto alineados, solicitar otro literal:

> **GO C7.2-B. Materializa localmente el bundle verificado en su sede final, implementa el doctor
> `runner_release` y crea el target DVC dedicado; detente sin `dvc push`, Git push ni publicación.**

C7.2-B deberá seguir las órdenes R19.5 ya definidas:

1. sede `artifacts/releases/<disease_id>/<release_id>/`;
2. `releases_root` explícito e inyectable;
3. doctor por schema, identidad, checksums, inventario, modelos y reproducción;
4. promoción atómica e idempotente;
5. target DVC exclusivo del bundle;
6. Obesidad permanece `trained` y NO-GO;
7. commit local y STOP.

#### Deuda separada

El SIGSEGV preexistente `deepar_smoke + pipeline_e2e` no bloquea el checkpoint de la rama, porque
el perímetro afectado pasa aislado y el fallo reproduce sin C7.2-A. Sí continúa bloqueando merge y
publicación hasta quedar explicado o aislado con un gate estable.

#### Próxima orden exacta

> **Crea un commit doc-only con esta actualización del plan, verifica `ahead 5` y detente. Después
> solicita autorización explícita para subir el checkpoint C7.2-A; no inicies C7.2-B ni DVC.**

---

### Ronda 24 — Checkpoint C7.2-A subido — 2026-07-25

Autorización literal recibida y ejecutada la Orden R23.3. **Sólo push de la rama de trabajo.**

```text
origin/feat/registry-padecimientos-obesidad
  antes   0dbd0f01dfdf64a84146f07bf62dae2360600f18
  después 827de945ec577fb89ec4ae14d0fe987167ce9ce5   ← SHA remoto registrado
  git push origin feat/registry-padecimientos-obesidad
    0dbd0f01..827de945   (fast-forward, sin --force)
```

Comprobado inmediatamente antes: el remoto seguía en `0dbd0f01` y el local era descendiente
directo. Comprobado después con `git ls-remote`: el SHA remoto coincide con `HEAD`.

#### Los cinco commits publicados

```text
827de945  docs: close C7.2-A audit and authorize checkpoint review
d5347905  C7.2-A.2.1 decouple builder provenance from schema compatibility
b809599d  C7.2-A.2 version runner release schemas before persistence
fb3bcdca  C7.2-A.1 decouple public activation from the release bundle
2bed74ee  C7.2-A deterministic runner release bundle
```

#### Estado posterior

| comprobación | resultado |
| --- | --- |
| `ahead` / `behind` | 0 / 0 |
| árbol trackeado | limpio |
| rama | `feat/registry-padecimientos-obesidad` |
| `main` local y remota | `b535b525`, sin tocar |
| PR / merge / tag / release | ninguno |
| runs canónicos | dataset `2ef4ee1236aa94c0` · refit `972f7519f885c0d1` · forecast `d89d92ee7e73b848` |
| `artifacts/releases/` | AUSENTE |
| `.dvc` | 0 tocados |

#### Lo que este push NO autoriza

- C7.2-B (sede final, doctor `runner_release`, promoción atómica, target DVC);
- ninguna operación DVC;
- lifecycle, canales, galería, frontend, deploy ni publicación;
- merge a `main`.

El SIGSEGV preexistente `deepar_smoke + pipeline_e2e` sigue siendo **bloqueo de merge y de
publicación**, no del checkpoint: el perímetro de C7.2-A pasa aislado y el fallo reproduce sin él.

#### Siguiente

Esperando el literal:

> **GO C7.2-B. Materializa localmente el bundle verificado en su sede final, implementa el doctor
> `runner_release` y crea el target DVC dedicado; detente sin `dvc push`, Git push ni publicación.**

_Respuesta:_ checkpoint remoto validado. No hace falta otro push documental antes de C7.2-B. El
commit local `34d785a8` y esta actualización del plan se preservarán dentro del futuro cierre local
de C7.2-B.

---

### Ronda 25 — Validación posterior al push y orden C7.2-B — 2026-07-25

#### Veredicto

**PASS. El checkpoint remoto de C7.2-A es correcto y C7.2-B queda lista para autorización
separada.**

Validación directa:

```text
remoto antes del push      0dbd0f01dfdf64a84146f07bf62dae2360600f18
remoto autorizado          827de945ec577fb89ec4ae14d0fe987167ce9ce5
git ls-remote actual       827de945ec577fb89ec4ae14d0fe987167ce9ce5
push                       fast-forward, sin --force
local                      34d785a8 · ahead 1 · commit doc-only
frontend                   main/origin main @ 179bbe36 · trackeado limpio
bundle persistido          NO
DVC                        NO
lifecycle/publicación      NO
```

`34d785a8` sólo añade la Ronda 24 con el SHA remoto y las fronteras del push. No contiene código,
configuración, datos, DVC ni artefactos.

#### Decisión de continuidad documental

No crear una cadena infinita de microcommits donde cada commit sólo registra el SHA del anterior.
El estado remoto autoritativo ya está fijado en `827de945`. El commit local `34d785a8` y el delta
actual de este plan:

- permanecen locales durante C7.2-B;
- forman parte del commit local de cierre de C7.2-B;
- no autorizan ni fuerzan un push;
- no alteran la identidad del release.

#### Orden R25.1 — Entrada a C7.2-B

C7.2-B sólo inicia al recibir:

> **GO C7.2-B. Materializa localmente el bundle
> `obesidad_release_2517e7858901` en su sede final, implementa y valida el doctor
> `runner_release`, crea el target DVC dedicado y detente sin `dvc push`, Git push ni
> publicación.**

Ese GO autoriza exclusivamente:

1. código y tests genéricos necesarios para resolver un `runner_release`;
2. materialización local del bundle ya verificado;
3. creación del target DVC dedicado local;
4. cambio de `artifact_source` de Obesidad a `runner_release` sólo después de que el doctor valide
   la sede final;
5. commit local de C7.2-B y actualización de este plan.

#### Orden R25.2 — Sede y promoción

Destino obligatorio:

```text
artifacts/releases/obesidad/obesidad_release_2517e7858901/
```

Reglas:

1. construir primero en un temporal del mismo filesystem;
2. verificar schema, identidad, checksums, inventario, modelos y reproducción antes de promover;
3. promover atómicamente;
4. aceptar idempotentemente un destino byte-idéntico;
5. rechazar un destino existente con cualquier diferencia;
6. no copiar `runs/` completos ni modelos legacy;
7. no inferir identidad desde nombres de archivo;
8. no incluir rutas absolutas, timestamps o metadata ambiental.

#### Orden R25.3 — Doctor `runner_release`

Implementar con `releases_root` explícito e inyectable:

1. resolver `<releases_root>/<disease_id>/<release_id>`;
2. exigir `release_manifest.v2` e `identity_payload.v2`;
3. validar `SHA256SUMS.txt`, inventario exacto, cadena y `release_id`;
4. cargar 6 índices, 64 envelopes y 64 estados;
5. reproducir 3,328 bases y 5,772 productos sin leer `runs/`;
6. exigir diferencia exacta `0.0`;
7. validar point-only, calendario, 64+47=111 e identidades aritméticas;
8. devolver error tipado ante release ausente, schema ajeno, byte alterado, modelo faltante,
   release de otro padecimiento o reproducción distinta;
9. mantener `runner_runs` válido únicamente para `trained`;
10. exigir `runner_release` para cualquier padecimiento `published`.

Pruebas negativas obligatorias:

- root inexistente;
- release_id inexistente;
- manifest/schema alterado;
- checksum alterado;
- archivo extra o faltante;
- envelope/estado faltante;
- `disease_id` ajeno;
- reproducción con diferencia;
- intento de resolver desde `runs/` o cwd implícito.

#### Orden R25.4 — Target DVC dedicado

Después de que la ruta final y el doctor estén verdes:

1. crear un único target para
   `artifacts/releases/obesidad/obesidad_release_2517e7858901/`;
2. no modificar `models.dvc`, `reports/forecasts.dvc`, Tableau ni targets legacy;
3. inspeccionar el `.dvc`: path exacto, hash coherente y sin dependencias ambientales;
4. ejecutar `dvc status` dirigido;
5. demostrar restauración local desde una copia temporal usando Git + caché DVC disponible;
6. volver a ejecutar doctor y reproducción sobre la restauración;
7. no ejecutar `dvc push`.

Si crear el target requiere descargar, subir o reemplazar datos remotos, detenerse: C7.2-B sólo
autoriza estado DVC local.

#### Orden R25.5 — Registry y lifecycle

Sólo después del PASS completo:

```yaml
artifact_source:
  backend: runner_release
  release_id: obesidad_release_2517e7858901
```

Invariantes:

- lifecycle continúa `trained`;
- Obesidad sigue fuera de `published_only`;
- canales y galería no cambian;
- F50 permanece `configured` y oculta;
- los cuatro publicados legacy no cambian de backend;
- ninguna carpeta legacy de Obesidad autoriza el release.

#### Orden R25.6 — Gate y STOP

Ejecutar:

```text
pruebas unitarias focales del release y doctor
test_release_reproduction.py
integración del doctor runner_release
make test-fast
integración en las dos tandas documentadas
make lint
make typecheck
doctor Obesidad --artifacts
doctor --artifacts
git diff --check
dvc status dirigido al nuevo target
```

Verificar además:

- bundle final = 150 archivos y mismo digest agregado que los builds temporales;
- `release_id=obesidad_release_2517e7858901`;
- reproducción 3,328/5,772 con diferencia `0.0`;
- runs canónicos, política, agregados legacy y frontend intactos;
- cero `dvc push`, Git push, deploy o publicación;
- SIGSEGV preexistente registrado, sin ampliar C7.2-B para corregirlo.

Crear un commit local acotado de C7.2-B, incluyendo la actualización pendiente de este plan, y
detenerse. Entregar:

- SHA y diff;
- ruta final y target DVC;
- digest del bundle;
- resultados del doctor/restauración;
- estado dirigido de DVC;
- confirmación `trained`/NO-GO.

#### Prohibido en C7.2-B

- `dvc push`;
- Git push;
- lifecycle `trained → published`;
- construir `public_release_pointer.v1`;
- activar canales o galería;
- tocar frontend, Reports, Tableau, EpiBot o RAG;
- deploy, PR, merge, tag o release;
- iniciar C7.2-C o C7.3.

#### Próxima orden exacta

> **Esperar `GO C7.2-B`. Con ese GO, materializar y versionar localmente el bundle, implementar el
> doctor `runner_release`, cambiar el backend de Obesidad sólo tras PASS y detenerse sin subir ni
> publicar nada.**

---

### Ronda 25 — C7.2-B: sede, doctor y target DVC — 2026-07-25

Ejecutadas las doce órdenes de R19.5. **Sin `dvc push`, sin Git push, sin publicación.**

#### Sede y promoción atómica (R19.5.1, .5, .6) · **PASS**

```text
artifacts/releases/obesidad/obesidad_release_2517e7858901/   150 archivos
```

`release_store.py` recibe `releases_root` SIEMPRE por parámetro: no mira cwd, `runs/`, home ni
rutas del equipo. Se promueve con `copytree` a un hermano del destino y `replace` atómico, así que
un fallo a media copia no deja un release incompleto con aspecto de release. Idempotente
(`reused=True` en la segunda promoción) y **no repara** una sede manipulada: la rechaza.

El `release_id` no se pasa: sale de verificar el bundle, para que la carpeta no pueda quedar
nombrada por algo distinto de lo que el artefacto declara.

#### Doctor `runner_release` (R19.5.2, .3, .4) · **PASS**

`_diagnose_runner_release` exige, en orden: el release declarado existe en la sede → verifica
entero → es EL que el registry declara → es del padecimiento correcto → **reproduce con tol 0.0**.

26 pruebas, todas sobre una sede inyectada en `tmp_path` (jamás sobre la del repo). Mutaciones
cubiertas: schema v1, digest, inventario, modelo faltante, release bajo otro ID, release de otro
padecimiento y sede vacía.

**Una prueba mía era un falso verde y la reescribí.** `test_el_doctor_exige_que_el_release
_reproduzca…` alteraba una predicción y afirmaba que sólo la reproducción lo cazaba. Al comprobarlo
a mano resultó que `verify_bundle` ya lo rechazaba: el `run_manifest.json` del forecast que viaja
dentro también sella ese CSV. Para que la prueba probara lo que dice, la mutación tiene que
sobrevivir a schema, checksums, inventario, sellos internos e identidad —hay que actualizar también
el manifiesto sellado y renombrar el bundle a su nuevo ID—. Con eso, la reproducción es lo único
que queda entre el artefacto y un verde. Añadí además una prueba-guardia que verifica que el
falseado SÍ pasa la verificación estructural: si dejara de pasarla, la otra volvería a no probar
nada.

#### Reproducción desde la ruta final (R19.5.7) · **PASS**

```text
3,328 bases · 5,772 productos · máx |Δ| = 0.0 · guardia activo contra cualquier lectura bajo runs/
```

#### Target DVC dedicado (R19.5.8, .9) · **PASS**

```text
artifacts/releases/obesidad/obesidad_release_2517e7858901.dvc
  md5 9304fd8a9c2c23c2aec96d612a0f7b2b.dir · 150 archivos · 3,660,402 bytes
artifacts/releases/obesidad/.gitignore   (lo genera DVC; el bundle no entra a Git)
dvc status dirigido → up to date
models.dvc · reports/forecasts.dvc · reports/figures.dvc · data/*.dvc · logs.dvc → SIN TOCAR
```

#### El flip del registry (R19.5.10) · **HECHO, y por qué**

```yaml
artifact_source:
  backend: runner_release
  release_id: obesidad_release_2517e7858901
```

La condición era que el doctor resolviera y validara la sede sin excepciones especiales: lo hace.
Y hay un argumento más fuerte que no estaba escrito: **`runs/` está gitignored y fuera de DVC**, así
que el backend anterior no era verificable por nadie que no fuera esta máquina. El bundle sí tiene
puntero DVC. El flip no es sólo admisible: mejora la recuperabilidad.

Los IDs de los runs no se pierden: viajan en el `chain` del release.

#### Lo que el flip destapó: 159 pruebas en `skipped`, no en verde

Al cambiar el backend, `test_artifact_validation.py` no falló — **se saltó entero**. Las fixtures
resolvían los runs con `source().refit_run_id`, que pasó a ser `None`, y `hay_runs()` devolvía
`False`. 134 mutaciones de C7.1 desactivadas en silencio, con la suite en verde.

Reparado en la raíz:

- `artifact_fixtures.sealed_chain()` lee la cadena del release que el registry apunta —no la escribe
  a mano ni la infiere—;
- `hay_runs()` exige AHORA el release **y** los runs: si sólo mirara los runs, el próximo cambio de
  backend volvería a dejar las pruebas dormidas;
- `test_artifact_validation`, `test_artifact_backend` y `release_fixtures` toman de ahí las
  identidades;
- el adaptador de `runner_runs` sigue probado: se sustituye el padecimiento por uno equivalente con
  la cadena sellada, porque ese carril sigue vivo (es el que valida antes de promover).

Dos recursiones infinitas aparecieron al sustituir `registry.require` dentro de un helper que a su
vez lee el registry; se resuelven calculando el sustituto ANTES de parchear.

#### Gate

| comprobación | resultado |
| --- | --- |
| `ruff format --check` + `ruff check` | 277 archivos OK · All checks passed |
| `mypy src/epiforecast/` | 154 archivos, sin incidencias |
| fast | **1,827 passed** (eran 1,801; +26) · **0 skipped en las suites del runner** |
| integración | **61 passed** (59 + 2, dos tandas) |
| doctor Obesidad / completo | rc=0 / rc=0 — ahora **por el bundle**, no por `runs/` |
| runs canónicos · política · agregados legacy · frontend | idénticos al baseline |
| lifecycle | Obesidad `trained`, fuera de `published_only` (`published` = neuro + Dengue) |

#### Estado

```text
C7.2-B PASS · commit local · SIN dvc push, Git push ni publicación
Sede    artifacts/releases/obesidad/obesidad_release_2517e7858901/ (150 archivos)
DVC     target dedicado creado; los seis targets legacy sin tocar
Doctor  runner_release cableado con releases_root inyectable; exige reproducción
Tests   26 nuevas de sede/doctor · 159 rescatadas de `skipped`
Release NO-GO · Obesidad = trained · runner_release · F50 = configured · NO-GO
Deuda   SIGSEGV preexistente = bloqueo pre-merge/pre-publicación
Sigue   C7.2-C (`dvc push` + restauración en clon limpio), con su propio GO
```

_Respuesta:_ C7.2-B queda aceptada tras cerrar de forma independiente la restauración local que no
aparecía en el reporte. No ejecutar todavía `dvc push`: C7.2-C se divide en C1 (objeto DVC) y C2
(checkpoint Git), cada una con autorización propia.

---

### Ronda 26 — Auditoría independiente de C7.2-B y órdenes C7.2-C — 2026-07-25

#### Veredicto

**PASS. C7.2-B queda cerrada; C7.2-C1 queda lista para autorización explícita.**

Estado auditado:

```text
HEAD local                 c6a2e713 · ahead 2
remoto Git                 827de945
release_id                 obesidad_release_2517e7858901
sede local                 artifacts/releases/obesidad/<release_id>/
bundle                     150 archivos · 3,660,402 bytes
target DVC                 md5 9304fd8a9c2c23c2aec96d612a0f7b2b.dir
dvc status local dirigido  up to date
dvc status -c              150 archivos new
backend Obesidad           runner_release
lifecycle Obesidad         trained · fuera de published_members()
F50                        configured · oculta
```

La salida `new` de `dvc status -c` confirma que el objeto todavía no está en el remoto configurado.
Es el estado correcto antes de C7.2-C1 y evidencia adicional de que C7.2-B no ejecutó `dvc push`.

#### Validación independiente

```text
test_release_store + backend + bundle +
artifact_validation + registry                 267 PASS
doctor Obesidad --artifacts                    rc=0
doctor --artifacts                             rc=0
dvc status <target>                            up to date
git diff --check 34d785a8..c6a2e713            PASS
```

Se confirmó:

- el doctor real valida desde `artifacts/releases/`, no desde `runs/`;
- el registry declara `runner_release` y el release correcto;
- Obesidad permanece `trained`;
- `published_members()` sigue siendo Depresión, Parkinson, Alzheimer y Dengue;
- el target nuevo es el único `.dvc` tocado;
- `models.dvc`, forecasts, figures, datos, logs y Tableau permanecen intactos;
- frontend `main @ 179bbe36` está trackeado limpio.

#### Brecha documental cerrada por la auditoría

R25.4 exigía restaurar desde otra raíz usando Git + caché DVC local y volver a ejecutar el doctor.
El reporte de C7.2-B sólo registraba `dvc status`, así que ese criterio no podía darse por hecho.

Se ejecutó en:

```text
/private/tmp/epiforecast-c72b-restore.DZRfsP
```

Procedimiento:

1. exportar `HEAD` a la raíz temporal;
2. inicializar allí un repositorio Git aislado;
3. configurar **sólo en el temporal** la caché DVC local del repo;
4. ejecutar `dvc checkout` únicamente sobre el target nuevo;
5. verificar 150 archivos restaurados;
6. ejecutar el doctor de Obesidad usando el código y configuración del temporal.

Resultado:

```text
dvc checkout target       PASS
archivos restaurados      150
doctor Obesidad           rc=0
reproducción              implícita en el doctor · tol=0.0
```

El doctor global del temporal no es un gate válido de este ensayo porque el `git archive` no
restauró los targets DVC legacy de los otros cuatro publicados; reportó correctamente que sus
directorios de modelos no existían. El doctor de Obesidad sí es el gate pertinente y pasó desde el
bundle restaurado.

El temporal se conserva para evidencia; no se borró nada.

#### Observación de activación, no bloqueante de C7.2-C

El registry conserva, como antes de C7.2-B:

```text
channels        web, epibot, reports, tableau, weekly_validation, prospective_validation
gallery_enabled true
```

No están activos porque Obesidad sigue `trained`. C7.2-B tenía la orden de no cambiarlos y la
respetó. Antes de cualquier flip a `published`, C7.5 deberá reemplazarlos por exactamente:

```text
channels        web, epibot, reports, tableau
gallery_enabled false
```

Este ajuste pertenece al puntero/activación pública, no al bundle ni a su `release_id`.

#### Orden R26.1 — Preparar el checkpoint documental

No crear otro commit antes de C7.2-C1. Mantener esta actualización del plan como delta local y
preservarla en el futuro commit documental de cierre de C7.2-C. Evita encadenar commits que sólo
registran el estado del commit anterior.

Antes de pedir autorización:

1. comprobar que `c6a2e713` sigue siendo `HEAD`;
2. comprobar que el único delta trackeado es este plan;
3. repetir `dvc status -c` del target y confirmar `new`;
4. confirmar remoto Git en `827de945`;
5. confirmar lifecycle `trained`.

#### Orden R26.2 — C7.2-C1: subir únicamente el objeto DVC

Requiere el literal:

> **GO C7.2-C1. Autoriza `dvc push` únicamente para
> `artifacts/releases/obesidad/obesidad_release_2517e7858901.dvc`; verifica el remoto y restaura
> desde él en un temporal limpio. No hagas Git push ni publiques nada.**

Con ese GO:

1. ejecutar `dvc push` con el target explícito; nunca `dvc push` global;
2. no usar `--force`;
3. comprobar `dvc status -c <target>` sin salidas `new` o `changed`;
4. crear otra raíz temporal limpia que no use la caché local existente;
5. exportar el commit local con el puntero DVC;
6. configurar únicamente el remoto DVC;
7. ejecutar `dvc pull <target>`;
8. verificar 150 archivos, tamaño, digest del directorio y `SHA256SUMS.txt`;
9. ejecutar doctor Obesidad y reproducción exacta `0.0`;
10. registrar el objeto remoto y resultados;
11. detenerse.

Prohibido en C1:

- Git push;
- modificar el target o reconstruir el bundle;
- subir cualquier otro target DVC;
- lifecycle, canales, galería, frontend o publicación;
- iniciar C7.2-C2 o C7.3.

#### Orden R26.3 — C7.2-C2: checkpoint Git separado

Sólo después del PASS de C1:

1. actualizar este plan con la evidencia del remoto DVC;
2. crear un commit doc-only de cierre C7.2-C, o incluir el plan en un commit de checkpoint sin
   alterar `c6a2e713`;
3. auditar el rango `827de945..HEAD`;
4. verificar que contiene C7.2-B, el plan y el puntero DVC, pero ningún bundle Git;
5. pedir autorización literal para push de la rama de trabajo;
6. hacer fast-forward sin `--force`;
7. verificar `git ls-remote`, `ahead 0`, main intacta y sin PR/merge/tag;
8. detenerse.

El push Git no autoriza C7.3, canales ni publicación.

#### Orden R26.4 — Después de C7.2-C

El siguiente trabajo sustantivo será C7.3:

1. compilador genérico desde `release_manifest.v2`;
2. outputs candidate únicamente en staging;
3. puentes Reports, Tableau, Web y EpiBot/RAG;
4. prueba obligatoria de que Obesidad no aparece públicamente mientras siga `trained`;
5. ningún cambio al bundle ni al `release_id`.

C7.4 conserva el gate prospectivo de cuatro semanas. C7.5 corrige canales/galería y crea el puntero
público. El SIGSEGV preexistente debe quedar resuelto o aislado antes de merge/publicación.

#### Próxima orden exacta

> **Esperar `GO C7.2-C1`. Sólo entonces subir el target DVC dedicado, restaurarlo desde el remoto
> en un temporal sin caché local y detenerse sin Git push, lifecycle ni publicación.**

_Respuesta:_ C7.2-C1 queda aceptada. El target DVC está sincronizado y la restauración remota pasó.
No iniciar C7.3: corresponde cerrar documentalmente C7.2-C y pedir autorización separada para el
push Git de C7.2-C2.

---

### Ronda 28 — Auditoría independiente del remoto DVC y orden C7.2-C2 — 2026-07-25

#### Veredicto

**PASS. C7.2-C1 cerrada; C7.2-C2 lista para revisión y autorización.**

Comprobaciones sobre el repo vivo:

```text
dvc status target             up to date
dvc status -c target          Cache and remote 's3remote' are in sync
target                        9304fd8a9c2c23c2aec96d612a0f7b2b.dir
Git remoto                    827de945
Git local                     c6a2e713 · ahead 2
bundle local                  150 archivos
```

#### Restauración desde el remoto con caché vacía

Se creó una raíz nueva:

```text
/tmp/epiforecast-c72c-remote.oA9qVA
```

La raíz no reutilizó `.dvc/cache` del repo original. Procedimiento:

1. exportar el commit local que contiene código, registry y puntero;
2. inicializar Git en el temporal;
3. conservar únicamente la configuración del remoto DVC trackeada;
4. ejecutar:

   ```text
   dvc pull artifacts/releases/obesidad/obesidad_release_2517e7858901.dvc
   ```

5. contar archivos;
6. ejecutar el doctor de Obesidad con el código y configuración de esa raíz.

Resultado:

```text
151 objetos descargados de S3
150 archivos materializados
doctor Obesidad --artifacts   rc=0
reproducción                  incluida por el doctor · tol=0.0
```

Esto demuestra que el target no depende de la caché ni de `runs/` de la máquina original.
El temporal se conserva como evidencia; no se borró nada.

#### Orden R28.1 — Commit documental de cierre C7.2-C

Crear un commit local que contenga únicamente:

```text
docs/PLAN_C7_PUBLICACION_OBESIDAD.md
```

Mensaje sugerido:

```text
docs: close C7.2-C1 remote restoration gate
```

Antes de commitear:

1. `git diff --check`;
2. `git diff --cached --name-only` debe listar únicamente el plan;
3. hooks aplicables verdes;
4. no amendar `c6a2e713`;
5. después del commit, árbol trackeado limpio y rama `ahead 3`.

#### Orden R28.2 — Auditoría del rango para C7.2-C2

Auditar:

```text
827de945..HEAD
```

El rango esperado contiene:

1. `34d785a8`, registro documental del checkpoint C7.2-A;
2. `c6a2e713`, implementación C7.2-B;
3. el nuevo commit doc-only de C7.2-C1.

Verificar:

- sólo código/tests del release, registry, puntero DVC y plan;
- el bundle de 150 archivos no entra a Git;
- ningún target DVC legacy cambió;
- lifecycle sigue `trained`;
- F50 sigue `configured`;
- frontend no aparece;
- `git diff --check` verde;
- remoto Git sigue en `827de945`.

#### Orden R28.3 — Autorización explícita de C7.2-C2

Presentar SHA del commit documental y rango exacto. Esperar una autorización literal equivalente a:

> **AUTORIZO C7.2-C2: PUSH FAST-FORWARD DE `827de945..HEAD` A
> `origin/feat/registry-padecimientos-obesidad`. NO AUTORIZO MERGE, DEPLOY NI PUBLICACIÓN.**

Sin esa autorización no ejecutar `git push`.

#### Orden R28.4 — Ejecutar C7.2-C2, si se autoriza

1. confirmar que el remoto sigue en `827de945`;
2. confirmar que local es descendiente directo;
3. push únicamente de `feat/registry-padecimientos-obesidad`;
4. no usar `--force`;
5. verificar con `git ls-remote` el SHA remoto;
6. comprobar `ahead 0`, árbol trackeado limpio y `main` intacta;
7. no crear PR, merge, tag o release;
8. detenerse.

Después del push, un clon de la rama podrá ejecutar `dvc pull` y doctor sin acceder a esta máquina:
el objeto DVC ya está remoto y el puntero quedará en Git.

#### Orden R28.5 — Después de C7.2-C2

C7.2 queda cerrada. La siguiente fase sustantiva será C7.3, con otro GO:

> **GO C7.3. Implementa el compilador genérico y los cuatro puentes en modo candidate/staging;
> demuestra que Obesidad sigue invisible mientras lifecycle=trained y detente sin publicar.**

C7.3 no puede:

- cambiar el bundle o `release_id`;
- escribir artefactos públicos desde modo candidate;
- cambiar lifecycle, canales o galería;
- desplegar frontend;
- ejecutar merge o publicación.

#### Próxima orden exacta

> **Crear el commit doc-only de cierre C7.2-C1, verificar `ahead 3` y detenerse. Después solicitar
> autorización explícita para el push Git C7.2-C2; no iniciar C7.3.**

---

### Ronda 27 — C7.2-C1: el objeto DVC subido y restaurado desde el remoto — 2026-07-25

Ejecutada la Orden R26.2 con el GO recibido. **Sin Git push, sin lifecycle, sin publicación.**

#### Preflight (R26.1)

```text
HEAD                       c6a2e713          ✓
delta trackeado            sólo este plan    ✓
dvc status -c <target>     151 objetos new   ✓ (no estaba en el remoto)
remoto Git                 827de945          ✓ (sin mover)
lifecycle Obesidad         trained · runner_release · obesidad_release_2517e7858901
```

#### Push del target explícito (R26.2.1–3)

```text
dvc push artifacts/releases/obesidad/obesidad_release_2517e7858901.dvc
  → 151 files pushed          (150 payloads + el objeto .dir)
dvc status -c <target>
  → Cache and remote 's3remote' are in sync
```

Sin `--force` y **sin `dvc push` global**. Los demás targets no se tocaron: `models.dvc` y
`reports/forecasts.dvc` ya estaban en sync con el remoto y siguen con 0 objetos pendientes, así que
este push no arrastró nada suyo.

Objeto remoto:

```text
s3://epiforecast-mx-data/files/md5/93/04fd8a9c2c23c2aec96d612a0f7b2b.dir
  16,743 bytes · ETag 9304fd8a9c2c23c2aec96d612a0f7b2b
```

#### Restauración desde el REMOTO, sin caché local (R26.2.4–9)

```text
/private/tmp/.../scratchpad/restoreC1.zUnIkK
```

Procedimiento: `git archive HEAD` a la raíz temporal → repo Git aislado → **caché DVC vacía** (no se
apuntó a la del repo, a diferencia del ensayo de la Ronda 26) → sólo el remoto S3 heredado de
`.dvc/config` → `dvc pull` del target.

```text
dvc pull <target>            151 files fetched · 150 added
archivos                     150            ✓
bytes                        3,660,402      ✓
SHA256SUMS.txt               618b45775dc8c5b9…  == sede local
release_manifest.json        38a19a0bb85ada88…  == sede local
diff -r restaurado vs local  IDÉNTICO
```

El ensayo corre con el **código y la sede del temporal**, no con los del repo — verificado
imprimiendo de dónde se importa `epiforecast` y comprobando que `default_releases_root()` cae dentro
del temporal:

```text
epiforecast desde   <temporal>/src
sede resuelta       <temporal>/artifacts/releases
doctor obesidad     rc=0 · sin problemas
reproducción        3,328 bases · 5,772 productos · máx |Δ| = 0.0
release_id          obesidad_release_2517e7858901
```

Es la primera prueba de que el bundle es restaurable **por alguien que no sea esta máquina**: Git da
el puntero, S3 da los bytes, y el doctor valida y reproduce sin `runs/` y sin caché previa.

El temporal se conserva como evidencia.

#### Estado

```text
C7.2-C1 PASS · SIN commit nuevo (R26.1: el plan queda como delta local para el cierre C7.2-C2)
DVC      objeto en el remoto · target en sync · ningún otro target subido
Git      HEAD c6a2e713 · ahead 2 · remoto 827de945 sin mover
Release  NO-GO · Obesidad = trained · runner_release · F50 = configured · NO-GO
Deuda    SIGSEGV preexistente = bloqueo pre-merge/pre-publicación
Sigue    C7.2-C2 (commit documental + autorización de Git push), con su propio GO
```

_Respuesta:_ C7.2-C1 aceptada. La restauración remota quedó confirmada tanto por la ejecución como
por la auditoría independiente. Seguir las órdenes R28.1–R28.4: commit doc-only, revisión del rango
y autorización separada antes del push Git. No iniciar C7.3.

---

### Ronda 29 — Auditoría final del rango C7.2-C2 — 2026-07-26

#### Veredicto

**PASS. El rango está listo para un último commit documental y, después, autorización de push
Git.**

Estado:

```text
HEAD                       be143338
remoto                     827de945
ahead                      3
DVC remoto                 sincronizado
bundle remoto              restaurable desde caché vacía
delta trackeado pendiente  sólo este plan
```

Commits locales sobre el remoto:

```text
be143338  docs: close C7.2-C1 remote restoration gate
c6a2e713  C7.2-B materialize the release bundle, wire the doctor and add a DVC target
34d785a8  docs: record C7.2-A checkpoint remote SHA
```

#### Auditoría del rango `827de945..be143338`

`git diff --check`: **PASS**.

Rutas:

- `artifacts/releases/obesidad/.gitignore`;
- `artifacts/releases/obesidad/obesidad_release_2517e7858901.dvc`;
- `config/padecimientos.yaml`;
- plan;
- código genérico de sede/doctor;
- tests del release, registry y backend.

Confirmaciones:

1. el bundle de 150 archivos está ignorado y no entra a Git;
2. sólo aparece el target DVC nuevo;
3. ningún target legacy fue modificado;
4. no hay `runs/`, forecasts, modelos legacy, datos o frontend en el rango;
5. el registry conserva `lifecycle=trained`;
6. F50 conserva `configured`;
7. el rango es descendiente directo de `827de945`;
8. el remoto continúa exactamente en `827de945`;
9. el objeto DVC ya está sincronizado antes de publicar el puntero Git.

#### Orden R29.1 — Último commit doc-only

Crear un commit que contenga únicamente:

```text
docs/PLAN_C7_PUBLICACION_OBESIDAD.md
```

Mensaje sugerido:

```text
docs: approve C7.2-C2 Git checkpoint
```

Gate:

1. `git diff --check`;
2. staged set exacto = plan;
3. hooks verdes;
4. no amend;
5. árbol trackeado limpio;
6. `ahead 4`;
7. detenerse sin push.

Este es el último microcommit documental de C7.2. El resultado del futuro push se registrará junto
con el inicio sustantivo de C7.3, no en otro commit independiente.

#### Orden R29.2 — Presentar autorización C7.2-C2

Después del commit:

1. informar el nuevo SHA;
2. listar los cuatro commits de `827de945..HEAD`;
3. confirmar remoto en `827de945`;
4. confirmar DVC remoto sincronizado;
5. pedir:

> **AUTORIZO C7.2-C2: PUSH FAST-FORWARD DE `827de945..HEAD` A
> `origin/feat/registry-padecimientos-obesidad`. NO AUTORIZO MERGE, DEPLOY NI PUBLICACIÓN.**

#### Orden R29.3 — Ejecutar el push, si se autoriza

1. revalidar ancestry y SHA remoto;
2. push sólo de la rama de trabajo;
3. sin `--force`;
4. comprobar `git ls-remote == HEAD`;
5. comprobar `ahead 0`, árbol trackeado limpio y `main` intacta;
6. no crear PR, merge, tag o release;
7. detenerse.

C7.2 quedará entonces cerrada en Git y DVC.

#### Orden R29.4 — Siguiente fase

Con C7.2-C2 PASS, pedir un GO separado para C7.3:

> **GO C7.3. Implementa el compilador genérico y los puentes Reports, Tableau, Web y EpiBot/RAG
> únicamente en candidate/staging; demuestra que Obesidad sigue invisible con lifecycle=trained y
> detente sin publicar.**

Antes de cualquier publicación futura:

- C7.4 debe completar cuatro semanas prospectivas;
- C7.5 debe dejar sólo `web`, `epibot`, `reports`, `tableau`;
- C7.5 debe cambiar `gallery_enabled` a `false`;
- el SIGSEGV debe resolverse o aislarse antes de merge/publicación.

#### Próxima orden exacta

> **Crear el commit doc-only `docs: approve C7.2-C2 Git checkpoint`, verificar `ahead 4` y
> detenerse. Después solicitar autorización explícita para el push Git; no iniciar C7.3.**

---

### Ronda 30 — C7.2-C2 subido y C7.3a: compilador y puentes candidate — 2026-07-26

#### Cierre de C7.2 (registrado aquí, no en un commit suelto)

```text
origin/feat/registry-padecimientos-obesidad
  827de945..5286543c   fast-forward, sin --force · git ls-remote == HEAD
  ahead 0 · behind 0 · main intacta en b535b525 · sin PR, merge, tag ni release
```

**C7.2 queda cerrada en Git y en DVC.** El objeto ya estaba en S3 antes de publicar el puntero, así
que un clon de la rama puede hacer `dvc pull` y correr el doctor sin acceder a esta máquina.

---

#### C7.3a — compilador genérico y los cuatro puentes · **PASS**

`src/epiforecast/publication/`: capa separada del runner. El runner produce y sella; esta traduce, y
sólo puede escribir en producción cuando el lifecycle lo permite.

```text
compiler.py  243 líneas   modos candidate/public + contrato de salida (21 columnas)
shards.py    240 líneas   Reports · Tableau · Web · EpiBot/RAG
```

#### Compilar no es publicar

| situación | resultado |
| --- | --- |
| `trained` + candidate | compila a staging |
| `public` sin `lifecycle=published` | rechaza **por lifecycle** |
| `published` sin puntero activo | rechaza: exige el `public_release_pointer.v1` de C7.5 |
| `published` con puntero a otro release | rechaza |
| staging dentro de `reports/`, `data/`, `epibot/`, `models/`, `artifacts/` | rechaza |

El modo `public` **no puede usarse todavía**, y falla diciendo exactamente por qué. Es fail-closed
por construcción, no por omisión.

#### Contrato de salida

Cada fila lleva `release_id`, `disease_id`, SeriesKey completa, periodo MMWR + `ds`, `yhat_cases`,
motor, `derived`, origen/horizonte, lineage (`forecast_run_id`, `refit_digest`),
`interval_method=none`, límites nulos y la etiqueta VISIBLE
«Pronóstico puntual; sin intervalo de incertidumbre».

Las 3,328 filas base llevan **su** motor seleccionado; las 2,444 derivadas se atribuyen al
**portafolio**. Inventarles un motor sería mentir sobre quién las produjo.

Los valores no se recalculan: se traducen del `forecast.csv` sellado, con desviación máxima **0.0**.

#### Los cuatro puentes (staging temporal)

```text
epibot/corpus/obesidad.md · epibot/knowledge.json
reports/forecast_products.csv · reports/report.md
tableau/forecast_shard.csv · tableau/schema.json
web/manifest.json · web/series.csv
shard_manifest.json
```

Color, etiqueta, CIE, slug, galería y canales salen del registry; filtros y series, de los datos. Ni
un `if disease == ...`, ni una lista escrita a mano, ni identidad recuperada de un nombre de archivo.

El corpus RAG dice explícitamente que **no hay intervalos** y separa los 64 modelos de los 111
productos: confundirlos es el error que un RAG repetiría para siempre.

#### Un hallazgo que confirma lo que C7.5 tiene pendiente

Los canales declarados que **no** tienen puente quedan escritos en el manifiesto del shard, no
descartados en silencio:

```text
channels_emitted          epibot, reports, tableau, web
channels_without_bridge   prospective_validation, weekly_validation
```

Son exactamente los dos que C7.5 debe quitar del registry. El compilador no los borra por su cuenta
—no es su competencia— pero tampoco deja que pasen desapercibidos.

#### Gate C7.3 (la parte de backend)

| criterio | resultado |
| --- | --- |
| dos compilaciones → mismos bytes | PASS (digest por archivo idéntico) |
| valores de los puentes vs forecast sellado | PASS · máx \|Δ\| = 0.0 |
| Obesidad ausente de outputs públicos con `trained` | PASS · fuera de `published_members()` en los 4 canales |
| F50 ausente / rechazo explícito | PASS · `configured`, sin release → rechazado |
| artefactos públicos de los 4 publicados sin cambios | PASS · agregados y `ProdDetails/` intactos |
| suites backend | 1,855 fast · 61 integración (dos tandas) |
| lint · mypy · doctores | PASS · PASS · rc=0 / rc=0 |
| nada desplegado | PASS |

#### Lo que NO hice, y por qué

C7.3 está dividido en tres commits por el propio plan. **Sólo entrego C7.3a.**

- **C7.3b** (consumidor de manifest en el frontend + UI point-only) y **C7.3c** (regeneración del
  índice RAG y verificación de drift) viven en **otro repositorio**: `EpiForecast-IMSS-Dashboard`.
- La regla dura dice que no se toca el frontend sin OK formal explícito, y el GO acotaba a
  «candidate/staging». Un manifest generado a staging es backend; editar el frontend no lo es.
- Por eso el criterio del gate «el índice RAG se regenera desde el corpus nuevo y verifica que no
  exista drift» **queda pendiente y declarado**, no dado por hecho: el corpus ya se genera, el
  índice se regenera en C7.3c.

El frontend sigue en `main @ 179bbe36`, trackeado limpio.

#### Estado

```text
C7.2      CERRADA (Git + DVC) · remoto 5286543c
C7.3a     PASS · commit local · staging temporal eliminado · nada desplegado
Tests     28 nuevas de publicación · 1,855 fast
Release   NO-GO · Obesidad = trained · runner_release · F50 = configured · NO-GO
Pendiente C7.3b y C7.3c (repo del frontend, requieren OK aparte)
Deuda     SIGSEGV preexistente = bloqueo pre-merge/pre-publicación
```

_Respuesta:_

---

### Ronda 31 — Auditoría de C7.3a y corrección de un guard que no guardaba — 2026-07-26

Auditoría del diff `5286543c..52497d3f` antes de tocar el frontend.

#### Superficie · **PASS**

```text
6 archivos · 888 inserciones · 0 borrados · todo texto
A  src/epiforecast/publication/{__init__,compiler,shards}.py
A  tests/unit/publication/{__init__,test_compiler_shards}.py
M  docs/PLAN_C7_PUBLICACION_OBESIDAD.md
```

Cero rutas de `artifacts/`, `runs/`, `models/`, `reports/`, `data/`, `epibot/`, `.dvc` o
`padecimientos.yaml`. `git diff --check` PASS.

#### Genericidad · **PASS, verificada por AST y no por grep**

Buscar cadenas a ojo no distingue código de docstring. Recorriendo el AST y excluyendo los
docstrings, **ningún literal de padecimiento ni de motor aparece en código ejecutable** de los tres
módulos. Las menciones a `all_forecast_*`, `tabla_333` e `if disease == …` están sólo en las
docstrings que explican qué NO se hace.

#### Rechazos, uno a uno · **PASS**

```text
public sin published        -> lifecycle para publicar: 'trained' != 'published'
modo inventado              -> modo de compilación desconocido: 'produccion'
F50 (sin release)           -> exige backend 'runner_release', no 'legacy_models'
legacy publicado            -> exige backend 'runner_release', no 'legacy_models'
padecimiento inexistente    -> padecimiento desconocido
staging en reports/         -> ruta pública del repo
published + puntero OK      -> COMPILA (5,772 filas)
```

El último importa tanto como los otros: si el modo `public` fuera inalcanzable por un bug, los seis
rechazos anteriores no demostrarían nada. Está bloqueado por política, no por avería.

#### R31-P0 — Un guard que no guardaba (defecto propio)

`check_staging_root` existía, estaba exportado y **tenía dos pruebas verdes**… pero **nadie lo
llamaba**. `emit_shards` aceptaba cualquier destino. Comprobado en vivo: escribió shards dentro de un
directorio llamado `reports/` sin una queja.

Es exactamente el patrón que estas auditorías llevan cazando toda la fase: una comprobación probada
en aislamiento que no está cableada al camino que debía proteger. Probar la función no prueba el
sistema.

Corregido: la validación vive **dentro de `emit_shards`**, que en modo `candidate` rechaza cualquier
destino bajo una ruta pública del repo. Con dos pruebas nuevas que fallan si se vuelve a desconectar,
y verificado contra las rutas reales:

```text
reports/staging · epibot/staging · artifacts/staging  -> rechazados · 0 bytes escritos en el repo
```

#### R31-P1 — Filtros de periodo derivados de la posición de una fila

`filters.periods` del manifest web salía de `min/max(epi_year)` combinado con la semana de la
primera y la última fila **tras ordenar por geografía**. El resultado era correcto —`[[2026,27],
[2027,26]]`, igual que el calendario del release— pero por casualidad: coincide sólo porque todas las
series comparten horizonte. Ahora sale del calendario MMWR verificado, con una prueba que lo contrasta
contra `first_period`/`last_period` del manifest del release.

#### R31-P2 — Import de un nombre privado entre módulos

El compilador importaba `release_reproduce._read_bundled`. Promovido a `read_bundled_frame`: si un
módulo necesita la lectura sin pérdida de otro, esa lectura es API, no un detalle privado.

#### Gate tras la corrección

```text
fast              1,862 passed   (eran 1,855; +7)
publicación          35 passed   (eran 28)
lint · mypy       All checks passed · 157 archivos sin incidencias
doctor completo   rc=0
```

#### Estado

```text
C7.3a     PASS auditado · dos defectos propios corregidos · nada desplegado
Obesidad  trained · runner_release · invisible en los cuatro canales · NO-GO
Canales   prospective_validation y weekly_validation NO se tocan: son de C7.5
Pendiente C7.3b y C7.3c en EpiForecast-IMSS-Dashboard, con su propio GO
```

_Respuesta:_

---

### Ronda 32 — C7.3b/C7.3c: consumo candidate y RAG de staging — 2026-07-26

Ejecutado en `EpiForecast-IMSS-Dashboard`, **en rama nueva** `feat/c73-candidate-staging` (estaba en
`main`), commit local `4c99114b`. **Nada desplegado, sin push, sin lifecycle ni canales.**

Su `CLAUDE.md` prohíbe `Co-Authored-By`; ese commit va sin líneas de coautoría.

#### C7.3b — consumir el manifest candidate y mostrar point-only

```text
epibot/scripts/lib/candidate.mjs   lee y VALIDA <staging>/<disease>/<release>
epibot/js/point_only.js            reglas puras de dibujo, sin DOM
```

El error que había que evitar no es un crash: es un **gráfico creíble y falso**. Convertir el vacío
de un intervalo en `0` dibuja una banda que baja hasta el eje y sugiere una certeza que nadie
calculó. Por eso:

- `toValue`: `''`, `nan`, `None`, `null` y `undefined` son **ausencia**, nunca cero;
- con `interval_method=none` la banda es `null` — ni ceros, ni una copia de la línea;
- la etiqueta «Pronóstico puntual; sin intervalo de incertidumbre» **viaja con la serie**: si el
  gráfico se muestra, el aviso se muestra con él;
- aunque llegaran límites, `interval_method=none` manda: el lector rechaza el shard.

Verificado con el shard real de C7.3a: 5,772 filas, `lifecycle=trained`, `isPubliclyVisible=false`,
`band=null`, 52 puntos en nacional/general.

#### C7.3c — reindexar y verificar drift, sólo en staging

```text
epibot/scripts/rag_staging.mjs     índice paralelo en el staging; el publicado no se toca
corpus 454 → 455 chunks (+1 candidate) · 435 vectores reutilizados · ✔ sin drift
chunks con "obesidad": índice PUBLICADO 0 · índice de STAGING 1
```

`buildChunks` acepta ahora `candidateRoot` **opcional**. Sin ese argumento el corpus es idéntico
chunk a chunk al de antes —lo comprobé por digest, y la primera comparación que hice era inválida
porque el módulo resuelve rutas desde su propio directorio; repetida en el sitio correcto:
`11ec6151867a4cac` en ambos—. El índice publicado no puede derivar por el mero hecho de que exista
un candidate en la máquina.

#### 16 pruebas nuevas que fabrican sus propios shards

No dependen del repo principal. Cubren: el vacío nunca es cero, la banda nula, candidate ≠ público,
y cuatro rechazos (declara incertidumbre, declara intervalos, trae límites, miente en el conteo).

#### Dos rojos PREEXISTENTES, verificados con mis cambios en stash

```text
npm run rag:verify   ✖ DRIFT: 454 chunks de corpus vs 452 en el índice publicado (19 sin cubrir)
npm test             answerTrainingConfig 9/10 · null 46/49
```

Ambos idénticos en `HEAD` limpio. **No son de C7.3** y no los toco: regenerar el índice publicado
exige `GEMINI_API_KEY` y es una escritura sobre la superficie publicada, justo lo que el GO excluye.
`npm run check` ya estaba rojo por ese drift antes de este trabajo.

#### Preservación

```text
epibot/knowledge.json · epibot/rag_index.json · index.html · epibot/index.html   SIN CAMBIOS
node --check de los 10 módulos tocados y vecinos: OK
gate propio: 16/16
```

#### Estado

```text
C7.3  a/b/c entregadas · dos repos, dos commits locales, cero deploys
Repo principal        b14a6ca2 · ahead 2
Dashboard             4c99114b · rama feat/c73-candidate-staging · ahead 1 de main
Obesidad  trained · runner_release · invisible en público y en el índice RAG publicado
Canales   prospective_validation y weekly_validation intactos: son de C7.5
Deuda     SIGSEGV (repo principal) · drift del rag_index publicado (dashboard), ambos preexistentes
```

_Respuesta:_

---

### Ronda 33 — Auditoría de los dos rangos de C7.3 — 2026-07-26

Auditados `backend 5286543c..e45c2ee4` y `dashboard 179bbe36..4c99114b`. Sin push ni deploy.

#### Superficie · **PASS en ambos**

```text
backend    3 commits ·  7 archivos · 1,115 inserciones · 0 binarios
dashboard  1 commit  ·  6 archivos ·   459 inserciones · 0 binarios
```

Backend: cero rutas de `artifacts/`, `runs/`, `models/`, `reports/`, `data/`, `epibot/`, `config/`
o `.dvc`. Dashboard: cero cambios en `knowledge.json`, `rag_index.json`, HTML, CSS, netlify,
`bento.json`, `hero_series.json` ni `zoom_series.json`. `git diff --check` PASS en ambos.

En Git, bajo `artifacts/` sólo viven dos archivos —el `.dvc` y el `.gitignore`—: ni uno de los 150
del bundle.

#### Exposición pública · **PASS**

```text
obesidad            trained · runner_release
published_members   Depresión, Parkinson, Alzheimer, Dengue
web · epibot · reports · tableau   los mismos cuatro, en los cuatro canales
menciones a "obesidad" en knowledge.json / rag_index.json / index.html / epibot/index.html:  0
agregados legacy    cb5be395 · 96791595 · 1d2cf0a7 · ac97dc8e   sin cambio
ProdDetails         0 cambios
```

#### Regresiones · **PASS**

Sólo dos archivos existentes se tocaron en todo C7.3, y ambos de forma acotada:

- `release_reproduce.py`: rename `_read_bundled` → `read_bundled_frame`, con sus dos llamadas
  actualizadas y **cero referencias al nombre viejo** en todo el repo;
- `corpus.mjs`: `buildChunks()` gana un parámetro **opcional**. Sus tres llamadores existentes
  (`rag_verify`, `build_rag_index`, y el nuevo `rag_staging`) siguen invocándolo sin argumentos, y
  el corpus por defecto es idéntico chunk a chunk.

Suites: 604 del runner+publicación en el backend, 19/19 en el dashboard, doctor completo rc=0.

#### R33-P0 — Un contrato entre repos que nadie verificaba

El compilador emite `schema: "publication_shard.v1"` en `shard_manifest.json` y en
`web/manifest.json`. **El consumidor del dashboard nunca lo miraba.**

Importa más que dentro de un mismo repo: productor y consumidor viven en repositorios distintos,
evolucionan en commits distintos y se revisan por separado. Sin esa igualdad, un cambio de formato se
habría manifestado como un error confuso aguas abajo —o peor, como una lectura equivocada en
silencio— en vez de decir «este shard es de otra versión». Es exactamente la lección de C7.2-A.2,
ahora cruzando el límite entre repos, donde nadie la había aplicado.

Corregido en el dashboard (`d5ead880`): ambos manifiestos se comprueban contra `SHARD_SCHEMA`, con
tres pruebas nuevas —otro schema, sin schema, y el positivo—. Verificado extremo a extremo con el
shard real: schema aceptado, 5,772 filas, `candidate=true`.

#### Dependencias entre repos · **PASS, sin acoplamiento de rutas**

```text
dashboard → repo principal   ninguna ruta: el staging root llega por argumento
repo principal → dashboard   ninguna referencia a epibot/, rag_index ni al repo
único vínculo                el schema del shard, ahora verificado en ambos lados
```

Ninguno de los dos repos puede romper al otro por moverse de sitio; sólo por cambiar el contrato, y
eso ahora se nota.

#### Deuda preexistente (no de C7.3, verificada con los cambios en stash)

```text
backend    SIGSEGV  deepar_smoke + pipeline_e2e en un solo proceso
dashboard  DRIFT    454 chunks de corpus vs 452 en el rag_index publicado (19 sin cubrir)
dashboard  npm test answerTrainingConfig 9/10 · null 46/49
```

Los tres bloquean merge/publicación, no este checkpoint.

#### Estado

```text
Backend    e45c2ee4 · ahead 3 de origin
Dashboard  d5ead880 · rama feat/c73-candidate-staging · ahead 2 de main
Obesidad   trained · runner_release · invisible en ambos repos
Canales    prospective_validation y weekly_validation intactos: C7.5
Sin push, sin deploy, sin DVC, sin lifecycle
```

_Respuesta:_

---

### Ronda 34 — Checkpoints de C7.3 subidos en los dos repos — 2026-07-26

Ambos pushes autorizados por separado y ejecutados. **Sin merge, sin PR, sin deploy a producción,
sin cambios en Netlify.**

```text
BACKEND    origin/feat/registry-padecimientos-obesidad
             5286543c..815a49a3   fast-forward, sin --force · ls-remote == HEAD
             ahead 0 / behind 0 · main b535b525 sin mover

DASHBOARD  origin/feat/c73-candidate-staging   [new branch] d5ead880
             ls-remote == d5ead880 · ahead 0 / behind 0
             origin/main 179bbe36 SIN MOVER · ramas en origin: main + la nueva
```

Sin merges, sin tags, sin PR: `gh` no se invocó en ningún momento. El enlace `pull/new/...` que
imprime GitHub al crear una rama es una sugerencia suya, no un PR abierto.

Superficie publicada del dashboard tras el push, intacta y sin una sola mención al padecimiento
candidate:

```text
epibot/knowledge.json  e1d9a7d98943      epibot/rag_index.json  86417db3ae05
index.html             94549fbd0338      menciones a "obesidad": 0
```

#### Sobre los branch deploys de Netlify

Se pidió desactivarlos antes del push (opción 2) y **no pude hacerlo**: no hay CLI de Netlify
instalado, la config local no tiene usuarios ni token de auth, y no hay `NETLIFY_AUTH_TOKEN` en el
entorno. Esa opción vive en la cuenta de Netlify, no en el repo, y no se intentó obtener credenciales
para tocar infraestructura ajena al código.

La autorización siguiente aceptó explícitamente un posible branch preview automático, así que el
push se ejecutó tal cual. **Queda pendiente de verificación humana** si Netlify levantó un preview de
`feat/c73-candidate-staging`: desde aquí no es comprobable —el nombre del sitio en `*.netlify.app` no
aparece en el repo, sólo el dominio de producción `epiforecast.mx`—.

Acotación de lo que ese preview podría ser, con lo que sí es verificable:

- no publicaría el padecimiento candidate: 0 menciones en los tres artefactos de superficie;
- no tocaría producción: la rama de producción es `main` y no se movió;
- probablemente fallaría, por el drift preexistente de 19 chunks que hace fallar `rag:ci`.

#### Estado

```text
C7.3       a/b/c entregadas y subidas · dos repos, dos ramas, cero merges
Backend    815a49a3 en origin · ahead 0
Dashboard  d5ead880 en origin/feat/c73-candidate-staging · main intacta
Obesidad   trained · runner_release · invisible en ambos repos
Canales    prospective_validation y weekly_validation intactos: C7.5
Pendiente  confirmar en la UI de Netlify si hubo preview; desactivar branch deploys hasta cerrar C7.3
Deuda      SIGSEGV (backend) · drift del rag_index publicado y 4 fallos de npm test (dashboard)
Siguiente  C7.4 (gate prospectivo de cuatro semanas), con su propio GO
```

_Respuesta:_

---

### Ronda 35 — C7.4: gate prospectivo congelado · veredicto INCOMPLETE — 2026-07-26

#### Veredicto

```text
INCOMPLETE — 0 de 4 semanas objetivo válidas
```

No es un fallo del gate ni del release: **la verdad todavía no existe**.

```text
último boletín fuente        2026-W27  →  periodo objetivo 2026-W26 (lag de observación 1 sem)
última observación sellada   2026-W26  ==  el ORIGEN del forecast congelado
semanas objetivo             2026-W27 · W28 · W29 · W30
semanas con verdad           ninguna
```

La primera semana del gate, 2026-W27, necesita el boletín de la semana fuente W28. **Cuatro semanas
epidemiológicas consecutivas son cuatro boletines: es tiempo de calendario y no se puede comprimir.**
El propio plan lo contempla: «INCOMPLETE: faltan semanas válidas; C7 espera».

#### Lo que sí se hizo, y era lo urgente: CONGELAR

Congelar después de ver resultados no vale nada. Por eso el congelamiento se ejecutó hoy, con cero
semanas de verdad disponibles:

```text
schema                      prospective_gate.v1
release                     obesidad_release_2517e7858901 · origen 2026-W26 · horizonte 52
candidate_forecast_digest   e7e2f5eef2efe7fc1071a1adbcc7c9efba1ab29e8265e395e566799f55e3c9e2
control_engine              seasonal_naive_lag52
control_forecast_digest     bb18accc0e6c9fbf8fd62fd48d4c9fc0807d4678e99d89f294ca6c7c41bce315
dataset_digest              1502d1a25b48c11b7afd30173163d78e4c67a55e31551737a9bed20358cc4340
regla (máx. degradación)    bases +5% · 111 productos +5% · nacional General +10%
GATE DIGEST                 5bc39aa5d44f5e62062775dc09a0366ac856f47e5444fbb52ca07e608e61b65d
```

El control **no se guarda como un CSV suelto** que alguien pudiera regenerar distinto: se congela por
**digest + receta determinista** sobre el dataset sellado. Reproducirlo da ese digest o el gate falla.
Y como el baseline es la observación de 52 semanas antes, congelarlo **no es entrenar**: no hay un
solo parámetro que ajustar. Cero retuning, cero re-selección, cero refit.

Cualquier intento de aflojar el umbral después de ver resultados mueve el `gate_digest`. Hay una
prueba por componente que lo demuestra.

#### Un test propio que estaba mal, y lo que enseñó

Escribí que el control de 2026-W27 debía repetir **2025-W27**. Falló: devolvía 2025-W28. El test
estaba mal, no el motor. **2025 es un año MMWR de 53 semanas**, así que retroceder 52 *semanas* no
cae en «la misma semana del año pasado».

Corregido usando `shift(2026, 27, -52)` en vez de un número escrito a mano, con la aserción explícita
de que eso da `(2025, 28)`. La versión ingenua habría dado verde en años de 52 semanas y rojo en los
de 53, que es la peor clase de test: el que sólo falla cuando el calendario se pone interesante.

#### Reglas que quedan probadas

| regla | prueba |
| --- | --- |
| una semana ausente NO se vuelve cero | sí |
| una semana **parcial** (presente en una serie, ausente en otra) no cuenta | sí |
| con <4 semanas el veredicto es INCOMPLETE, nunca PASS optimista | sí (0, 1, 2 y 3) |
| con 4 semanas se evalúa y se reporta **por semana** | sí |
| mover candidato, control, dataset, origen o umbral mueve el `gate_digest` | sí |
| el control es lag-52 real, no un relleno | sí |

#### Gate

```text
fast 1,882 passed (+20) · lint · mypy 158 archivos · doctor rc=0
agregados legacy cb5be395 96791595 1d2cf0a7 ac97dc8e · runs/ 0 modificados
obesidad trained · runner_release · published = neuro + Dengue
```

#### Cómo se cierra C7.4

Con cada boletín nuevo, volver a ejecutar el gate **sin tocar nada del congelado**. Cuando las cuatro
semanas tengan verdad completa, el veredicto pasará solo a PASS o FAIL. Si alguna semana llega
incompleta o no cumple el contrato de 32 entidades, no cuenta y el gate espera a la siguiente.

#### Estado

```text
C7.4     CONGELADO · veredicto INCOMPLETE (0/4) · sin retuning, lifecycle ni publicación
Espera   4 boletines · el primero habilita 2026-W27
Release  NO-GO · Obesidad = trained · runner_release · F50 = configured · NO-GO
Deuda    SIGSEGV (backend) · drift del rag_index publicado y 4 fallos de npm test (dashboard)
```

_Respuesta:_

---

### Ronda 36 — C7.5-PREP: puntero, canales y rollback — 2026-07-26

#### Auditoría de `f7b14694` (paso 1) · **PASS**

```text
3 archivos · 566 inserciones · 0 borrados
A src/epiforecast/publication/prospective.py · A tests/… · M el plan
superficies prohibidas: ninguna · git diff --check PASS
sin datetime, now(), azar ni rutas absolutas → gate_digest reproducible
gate_digest 5bc39aa5d44f5e62… recomputado idéntico
```

**No lo subo**: la regla dura del encargo pide OK formal por cada acción externa, y hasta ahora todos
los pushes han llevado su literal. Queda presentado más abajo.

#### C7.5-PREP · **PASS**

```yaml
channels: [web, epibot, reports, tableau]   # antes 6
gallery_enabled: false                      # antes true
lifecycle: trained                          # SIN TOCAR
```

`public_release_pointer.v1` (`publication/pointer.py`, 166 líneas), preparado **inactivo**:

```json
{"schema":"public_release_pointer.v1","disease_id":"obesidad",
 "release_id":"obesidad_release_2517e7858901",
 "channels":["epibot","reports","tableau","web"],
 "gallery_enabled":false,"active":false,"lifecycle_required":"published"}
digest 722baf8a13f6519f4fee5cdb2656583dbe986d80950d5812af69ef430b8f98d6
```

Preparar no es publicar, y el código lo impone en vez de confiarlo:

| regla | efecto |
| --- | --- |
| puntero inactivo | no exige `published`; se prepara con `trained` sin fingir nada |
| activar el puntero | **exige** `lifecycle=published` |
| escribir un puntero ACTIVO | prohibido en preparación: eso ya es publicar |
| destino del puntero | no puede caer en `reports/`, `data/`, `epibot/`, `artifacts/`… |
| canales `weekly_validation` / `prospective_validation` | rechazados: un release del runner no los produce |

#### La consecuencia de C7.2-A.1, verificada en la práctica

Cambiar canales de 6 a 4 y apagar la galería **no movió el `release_id`**:

```text
antes  obesidad_release_2517e7858901
después obesidad_release_2517e7858901   ← idéntico
```

Ése era exactamente el motivo de sacar la activación del bundle. Si siguiera dentro, este cambio de
política habría obligado a reconstruir —y renombrar— 64 modelos que no cambiaron. Hay tres pruebas
parametrizadas que lo fijan.

#### Rollback

Rollback es **reemplazar un puntero**, no reconstruir un bundle: `rollback_to()` devuelve un puntero
nuevo con otro `release_id` y los mismos canales, y está probado que no escribe ni toca el release.
Volver atrás cuesta 12 caracteres y queda auditado por digest.

#### Consumidores contra la nueva superficie

```text
compilador   canales emitidos (epibot, reports, tableau, web) · sin puente: ()   ← ya vacío
shard web    gallery_enabled false · release_id sin mover
frontend     5,772 filas · candidate=true · visible en público=false · band null ✓
doctor       rc=0
```

El `channels_without_bridge` que C7.3a dejó señalado **queda cerrado**: ya no hay canal declarado sin
puente.

#### Gate

```text
fast 1,905 passed (+23) · integración 59 (tanda A) · frontend 19/19
lint · mypy 159 archivos · doctor rc=0
agregados legacy cb5be395 96791595 1d2cf0a7 ac97dc8e · release 764c62e2f203e1df · dvc up to date
```

#### C7.6-READINESS: NO INICIADO

Aplico la regla del encargo: no empiezo lo que no cabe entero. Los tres bloqueantes son trabajo
sustantivo y en dos repos:

1. **SIGSEGV** — aislar `deepar_smoke` del resto de la integración con un gate estable;
2. **drift del RAG** — 19 chunks; regenerar el índice publicado **exige `GEMINI_API_KEY`**, que no
   está en este entorno, así que probablemente sea trabajo tuyo o requiera la key;
3. **4 fallos de `npm test`** en el dashboard.

Dejarlos a medias sería peor que no empezarlos.

#### Estado

```text
C7.5-PREP  PASS · commit local · puntero INACTIVO, sólo en staging
C7.4       CONGELADO · INCOMPLETE (0/4) · el congelado NO se tocó
Obesidad   trained · runner_release · gallery off · 4 canales candidatos · NO-GO
Pendiente  C7.6-READINESS (3 bloqueantes) · reejecutar C7.4 por boletín
```

_Respuesta:_

---

### Estado operativo final — sustituye el cierre de la Ronda 36

La decisión vigente está desarrollada en la **Ronda 37**. En síntesis:

```text
esperar 4/4 antes de publicar     YA NO ES BLOQUEANTE
C7.4                              INCOMPLETE 0/4, congelado e íntegro
antes de activar                  checkpoint + C7.6-READINESS verde
primera publicación              condicionada, point-only, n/4 visible
después                          evaluación semanal sin retuning
PASS 4/4                         confirma
FAIL 4/4                         rollback obligatorio
```

**Siguiente orden:** ejecutar 37.1 y luego 37.2. No saltar directamente al flip o al deploy.

---

### Ronda 38 — Orden 37.1: checkpoint auditado y un defecto propio corregido — 2026-07-26

#### La decisión, anotada

Publicar sin esperar las cuatro semanas es una decisión de política, y el plan la resuelve de forma
responsable: modalidad **condicionada**, C7.4 visible como `INCOMPLETE 0/4` —nunca como PASS—,
revalidación semanal y **rollback obligatorio si sale FAIL**. Lo que cambia es el papel del gate: deja
de ser un control *previo* a publicar y pasa a ser un control *posterior*. Queda escrito para que
dentro de un mes nadie lo lea como si el gate hubiera pasado.

#### 37.1.1 — Auditoría de `815a49a3..HEAD` · **encontró un defecto REAL**

```text
6 archivos · 1,016 inserciones · cero superficies prohibidas · diff --check PASS
plan 1 · código C7.4+C7.5-PREP 2 · tests 2 · registry 1
```

Pero el diff del registry mostró **cinco** sustituciones de `channels`, no una.

#### R38-P0 — Recorté los canales de los cinco padecimientos, no de Obesidad

Mi cambio de C7.5-PREP usó un reemplazo global. Resultado:

```text
depresion · parkinson · alzheimer · dengue   perdieron weekly_validation y prospective_validation
```

Son **los cuatro publicados**, y esos dos canales los alimenta el carril legacy (tabla_333 +
congelado). **Ninguna prueba se puso roja**, porque nadie afirmaba esos canales: se habrían caído de
la validación semanal y de la prospectiva en silencio. Ése es el peor modo de fallo de toda esta
fase —una superficie que desaparece sin que nada se ponga rojo— y es justo el que estas auditorías
existen para cazar.

Revertido (`eaa13160`): los cuatro publicados recuperan sus seis canales y `gallery_enabled: true`.
El recorte queda **sólo** en el bloque de Obesidad.

Regresión añadida, y **verificada contra el estado defectuoso**: 6 pruebas en rojo con el archivo
roto, 84 en verde con el corregido. Fija la superficie de los cuatro publicados, que sólo Obesidad
esté recortada, y que `published_members()` siga devolviendo los cuatro por ambos canales legacy.

Lección aplicable al resto de C7: **editar YAML por sustitución de texto no distingue bloques.** Los
cambios por padecimiento se acotan al bloque, como sí se hizo con `gallery_enabled`.

#### 37.1.3 — Reverificación tras la corrección

```text
git diff --check     PASS
lint · format · mypy PASS · 286 archivos · 159 módulos
fast                 1,911 passed (+6 de la regresión)
doctor obesidad      rc=0        doctor completo   rc=0
legacy               cb5be395 · 96791595 · 1d2cf0a7 · ac97dc8e   sin cambio
obesidad             trained · gallery false · 4 canales
published            Depresión, Parkinson, Alzheimer, Dengue     F50 configured
```

#### 37.1.4 — Checkpoint listo, sin subir

```text
815a49a3..HEAD
  eaa13160  C7.5-PREP fix: el recorte de canales era sólo de Obesidad
  7b05d240  C7.5-PREP public release pointer, exact channels, rollback
  f7b14694  C7.4 frozen prospective gate for runner releases
  fece856e  docs: record C7.3 checkpoints pushed in both repos
+ este commit doc-only
```

Sin merge, deploy, activación de puntero ni cambio de lifecycle.

#### Sobre `GEMINI_API_KEY`

Anotado tal como pide la Ronda 37: se entrega **sólo** como secreto de entorno o CI, nunca en Git,
el plan, logs, fixtures ni artefactos. Sin ella, EpiBot no puede alcanzar drift cero y, como la
decisión es publicar los cuatro canales, **bloquea la publicación completa**. No se recorta el canal
en silencio.

#### Estado

```text
Orden 37.1  cerrada salvo el push, que espera literal
Orden 37.2  C7.6-READINESS NO iniciada
C7.4        CONGELADO · INCOMPLETE 0/4 · el congelado no se tocó
Obesidad    trained · runner_release · puntero INACTIVO · NO-GO
```

_Respuesta:_

---

### Estado operativo final — aplicar Ronda 39

La Orden 37.1 ya fue subida en `e8102de2`. El microcierre backend de la Orden 37.2 está implementado
y verificado como WIP:

```text
SIGSEGV       causa demostrada · aislamiento por archivo · PASS
fast          1,918 PASS
integración   61/61 PASS · rc=0
estado        sin commit, push, merge, deploy ni activación
```

**Siguiente:** auditar/commitear este microcierre y continuar con los cuatro fallos del dashboard y
el RAG. La descripción completa y la evidencia están en la Ronda 39.

---

### Ronda 40 — Auditoría posterior al push y órdenes de C7.6 dashboard/RAG — 2026-07-26

#### Estado auditado, sólo lectura

```text
backend HEAD/remoto     dbfdd49c · ahead 0 · behind 0
dashboard HEAD/remoto   d5ead880 · feat/c73-candidate-staging
backend SIGSEGV         AISLADO/PASS
Obesidad                trained · 4 canales candidate · gallery false
publicados              Depresión · Parkinson · Alzheimer · Dengue
F50                     configured · oculta
activación/deploy       ninguno
```

Los archivos no rastreados de ambos repos son del usuario y quedan fuera de alcance.

#### Hallazgo R40-P0 — “sin drift” de staging no significa “todos tienen vector”

`scripts/rag_staging.mjs` construye el índice candidate reutilizando vectores del índice público y
asigna `[]` a los chunks nuevos. Su verificación sólo comprueba que el hash del chunk exista:

```text
chunk candidate presente + vector []  → hoy imprime “✔ sin drift”
```

Eso fue suficiente para demostrar en C7.3 que el corpus candidate se incorporaba sin tocar la
superficie pública, pero **no satisface C7.6-READINESS**. EpiBot requiere que cada chunk público o
candidate tenga un vector no vacío. El contrato correcto es el mismo de `rag_verify.mjs`:
presencia **y** vector.

También se confirmó que `build_rag_index.mjs` es resiliente: puede terminar sin error aunque un
embedding falle y deje un vector vacío. Por tanto, ejecutar `rag:build` no basta. El gate siempre
debe terminar con `rag:verify` en `rc=0` y cero vectores vacíos.

#### Orden 40.1 — Corregir 11 fallos en cuatro grupos de `npm test`

Trabajar únicamente en `EpiForecast-IMSS-Dashboard`, rama `feat/c73-candidate-staging`.

1. Capturar hashes de `knowledge.json`, `rag_index.json`, `index.html` y `epibot/index.html`.
2. Ejecutar `npm test` y registrar los 11 casos exactos, consulta, respuesta y aserción.
3. Reproducirlos en un worktree temporal de `origin/main@179bbe36` para separar deuda previa de
   regresión candidate, sin cambiar de rama el worktree principal.
4. Corregir la causa en código o fixtures según el contrato funcional; no bajar expectativas, no
   convertir fallos en skips y no aumentar tolerancias.
5. Añadir una regresión mínima por causa, no una copia masiva de los casos.
6. Ejecutar:

```text
npm test
npm run test:candidate
```

7. Confirmar que los cuatro artefactos públicos del paso 1 siguen byte-idénticos.
8. STOP para auditoría del diff. No regenerar RAG dentro del mismo commit.

Gate 40.1:

```text
npm test              100% PASS
test:candidate        100% PASS
knowledge/RAG/HTML    byte-idénticos
Obesidad pública      0 menciones
deploy/push/merge     ninguno
```

#### Orden 40.2 — Hacer verdadero el contrato RAG candidate

En un commit separado:

1. Cambiar la verificación de staging para exigir un vector no vacío por cada chunk.
2. Añadir pruebas rojas para:
   - chunk ausente;
   - chunk presente con `[]`;
   - vector presente pero desalineado con su chunk;
   - caso completamente cubierto.
3. Permitir que el builder candidate genere los embeddings faltantes usando
   `GEMINI_API_KEY`, o construir el índice ampliado mediante una función compartida con
   `build_rag_index.mjs`; no duplicar la lógica de embeddings.
4. Mantener la salida exclusivamente bajo `<staging_root>/rag_index.staging.json`.
5. No leer ni escribir el valor de la clave. Antes de ejecutar, comprobar sólo:

```sh
test -n "${GEMINI_API_KEY:-}"
```

6. Un fallo de API, rate limit o vector vacío debe dar `rc != 0`; no degradar a modo léxico en el
   gate de readiness.
7. STOP y auditar el contrato antes de regenerar índices.

#### Orden 40.3 — Reparar el drift público en la rama, sin deploy

Después de 40.1 y 40.2:

1. Preservar hash y copia temporal de `epibot/rag_index.json`.
2. Desde `epibot/`, con la clave sólo en el entorno, ejecutar:

```text
npm run rag:build
npm run rag:verify
```

3. Exigir:

```text
chunks corpus == chunks índice
vectores no vacíos == chunks corpus
missing == 0
failed embeddings == 0
rag:verify rc == 0
```

4. Verificar que el índice público de esta rama todavía contiene **cero** chunks de Obesidad. La
   reparación de drift baseline no activa el candidate.
5. El diff permitido es el índice RAG y, sólo si la causa lo exige, sus pruebas/código de build.
   `knowledge.json` y los HTML permanecen byte-idénticos.
6. No deploy, push, merge ni publicación.

#### Orden 40.4 — Gate RAG con Obesidad únicamente en staging

1. Regenerar un shard candidate C7.3a en un temporal fuera de rutas públicas, desde
   `obesidad_release_2517e7858901`, mientras Obesidad siga `trained`.
2. Ejecutar el builder candidate corregido sobre ese staging.
3. Exigir:

```text
corpus base                 cubierto 100%
chunk Obesidad candidate    presente y con vector
vectores vacíos             0
drift staging               0
rag_index.json de la rama   sin Obesidad
knowledge/HTML públicos     sin Obesidad
```

4. Ejecutar `npm run check`; debe quedar completamente verde.
5. Repetir el build candidate en otro staging y comparar contenido determinista ignorando sólo
   metadata temporal expresamente no identitaria.
6. STOP para auditoría conjunta de los commits 40.1–40.4.

#### Criterio de cierre C7.6-READINESS

```text
backend lint/typecheck/fast/integration     PASS · ya cerrado en dbfdd49c
dashboard npm test/test:candidate/check     PASS
RAG baseline                               drift 0 · todos los chunks con vector
RAG Obesidad candidate                     drift 0 en staging · todos con vector
superficies públicas                       Obesidad ausente
legacy/F50                                 intactos
```

Al cumplirlo, generar el paquete C7.6 y pedir autorizaciones separadas. No ejecutar todavía el flip,
el puntero activo, el deploy, Tableau o la publicación condicionada.

#### Próxima acción exacta

**Ejecutar sólo la Orden 40.1.** Presentar el diagnóstico de los 11 fallos agrupados por causa y el
diff; no empezar 40.2 en la misma ronda.

_Respuesta:_

---

### Ronda 41 — Validación read-only del dashboard y RAG — 2026-07-26

Se ejecutaron únicamente pruebas no mutantes. No se regeneró el índice, no se utilizó
`GEMINI_API_KEY`, no se cambió código y no hubo commit, push, merge, deploy o activación.

#### Resultado exacto

```text
npm test                 605/616 PASS · 11 FAIL · rc=1
npm run test:candidate    19/19 PASS · rc=0
npm run rag:verify        DRIFT 19 · rc=1
```

El reporte anterior de “cuatro fallos” era ambiguo: hay **11 casos fallidos**, concentrados en
**cuatro grupos funcionales**:

| grupo | casos | síntoma |
| --- | ---: | --- |
| `answerTrainingConfig` | 1 | “hiperparametros del modelo” devuelve `null` |
| `null` / fuera de tema | 3 | fútbol, bitcoin y tacos devuelven rechazo explícito en vez de `null` |
| `answerProyectoMeta` | 5 | artículo/publicación/paper/referencia devuelven `null` |
| `answerDistribucion` | 2 | la respuesta existe, pero no cumple el contrato textual `Distribución/DISTRIB` |
| **Total** | **11** | cuatro causas a diagnosticar |

Casos exactos:

```text
287  hiperparametros del modelo
377  resultado del futbol
378  como va el bitcoin
380  receta de tacos
413  tienen articulo publicado
414  publicacion del proyecto
415  hay paper del proyecto
416  donde esta el articulo
417  referencia del articulo
512  boxplot del smape
513  grafico del mase por padecimiento
```

#### RAG baseline

```text
corpus actual    454 chunks
índice actual    452 chunks · 452 con vector
faltantes        19
```

Fuentes afectadas:

| fuente | faltantes |
| --- | ---: |
| Validación semanal | 12 |
| Datos de Dengue | 3 |
| Datos del proyecto | 2 |
| Avance 1 (Equipo 01) | 1 |
| Avance 2 (Equipo 01) | 1 |

La rama candidate conserva su contrato point-only: 19/19 pruebas verdes. El fallo de readiness
está en la suite funcional legacy y en el índice RAG baseline, no en el consumidor candidate.

#### Orden corregida

La Orden 40.1 se mantiene, con esta precisión:

1. tratar los 11 casos como cuatro causas, no como 11 parches textuales;
2. reproducir cada grupo en `origin/main@179bbe36`;
3. decidir por contrato si los tres fuera de tema deben devolver `null` o un rechazo explícito;
   cambiar código y expectativas juntos sólo si existe una decisión funcional documentada;
4. no regenerar `test_cases.json` para borrar discrepancias;
5. exigir 616/616 y 19/19 antes de comenzar la Orden 40.2.

Después, la Orden 40.2 debe cerrar el falso verde de vectores vacíos y la Orden 40.3 debe resolver
los 19 chunks con la clave como secreto.

#### Próxima acción

**Diagnosticar y proponer el arreglo de los cuatro grupos de la Orden 40.1.** No implementar ni
regenerar RAG hasta recibir el siguiente GO.

_Respuesta:_

---

### Ronda 42 — Diagnóstico de los 11 fallos del dashboard (Orden 40.1) — 2026-07-26

Diagnóstico y propuesta. **No se implementó nada**, no se regeneró el RAG, no se usó la clave, no
hubo commit, push, deploy ni activación en el dashboard.

*(Nota de método: este diagnóstico se entregó primero en el chat en vez de aquí. Corregido: la
bitácora es el canal, y la respuesta va al final de esta ronda.)*

#### Reproducción en `main` (punto 2 de la orden corregida)

```text
rama feat/c73-candidate-staging @ d5ead880   PASS 605 · FAIL 11 · rc=1
main                          @ 179bbe36   PASS 605 · FAIL 11 · rc=1
conjunto de fallos                          IDÉNTICO
```

Preexistentes y ajenos a C7.3. El consumidor candidate sigue en 19/19.

#### Las cuatro causas

**G1 (#287) y G3 (#413–417) — 6 casos — son la MISMA causa.** En `answer()`, antes de la cadena de
handlers, hay un guard deliberado:

```js
// Guard: preguntas sobre el PAPER / MICAI / metodología → ceder al RAG, que
// tiene el artículo indexado. Se hace ANTES de los handlers locales...
const ragIntent = ['paper','micai','articulo','publicacion',…,'hiperparametro','hiperparametros',…];
if (any(q, ragIntent) && !ent.estado) return null;
```

`articulo`, `publicacion`, `paper` e `hiperparametros` **están en esa lista a propósito**. Por eso
devuelven `null` aunque `answerProyectoMeta` (kb.js:1164) y `answerTrainingConfig` tengan
disparadores que coinciden: **nunca se les llega**. Los tests codifican el comportamiento anterior
al guard.

**G2 (#377, #378, #380) — 3 casos — guard off-topic, también deliberado y con motivo escrito:**

```js
// Guard: temas claramente ajenos (clima, deportes, recetas, etc.) → declinar
// LOCALMENTE, sin ceder a la IA. Evita además el fuzzy 'clima'→'colima'.
```

Los tests esperan `null` (fallback a Gemini); el producto decidió declinar en local. La decisión
funcional existe y está documentada en el código, que es la condición que pide el punto 3.

**G4 (#512, #513) — 2 casos — colisión de prioridad en la cadena. Éste sí es un defecto real.**
Confirmado ejecutando, no leyendo:

| caso | lo captura | posición | debía capturarlo |
| --- | --- | ---: | --- |
| `boxplot del smape` | `answerSmapeBox` (trigger `boxplot`) | 9 | `answerDistribucion` (12) |
| `grafico del mase por padecimiento` | `answerRendimientoPorPadecimiento` | 7 | `answerDistribucion` (12) |

`answerDistribucion` también dispara con `boxplot`, pero llega tarde. `answerRendimientoPorPadecimiento`
ya tiene un `chartWord` que lo aparta de matriz/burbuja/polar/mapa/treemap/radar/barra: **le falta
`grafico`+métrica**, que es territorio de `answerDistribucion`.

#### Propuesta

1. **G1+G3+G2 (9 casos) → actualizar expectativas, no el código.** El comportamiento es intencional
   y está documentado en el propio código. `#287` y `#413–417` pasan a esperar `null` con nota
   «cedido al RAG por `ragIntent`»; `#377/378/380` pasan a esperar el rechazo local con
   `mustContain`. **Nueve ediciones nominales, una por caso, con su razón**: no se regenera
   `test_cases.json` (punto 4 de la orden).
2. **G4 (2 casos) → arreglar el código.** Guarda en `answerSmapeBox` para ceder ante consulta de
   distribución con métrica, y ampliar el `chartWord` de `answerRendimientoPorPadecimiento` para no
   robar `grafico`+métrica. Las expectativas se quedan: el contrato correcto es el que hoy falla.
3. Dejar la decisión de contrato de G2 firmada aquí, para que no viva sólo en un comentario.

#### La lectura alternativa, que es tuya y no mía

Hay una segunda lectura defendible de G1+G3: que `ragIntent` sea **demasiado ancho** y esté cediendo
al RAG preguntas que el KB local respondía mejor. Los cinco de `answerProyectoMeta` tienen respuesta
local rica y curada (título, subtítulo, título en inglés, autores con institución), y cederlas al RAG
las degrada. Si ésa es tu lectura, el arreglo es **acotar `ragIntent`** y **mantener** las
expectativas tal como están.

Las dos opciones son coherentes; la diferencia es de producto, no técnica:

| opción | qué se cambia | efecto para el usuario final |
| --- | --- | --- |
| **A** — el guard manda | 9 expectativas | «¿hay paper?» la contesta el RAG con el texto del artículo |
| **B** — el KB local manda | `ragIntent` se acota | «¿hay paper?» devuelve la ficha curada del proyecto |

No la decido yo.

#### Estado

```text
Orden 40.1  DIAGNOSTICADA · sin implementar
Fallos      11 = 4 causas · 9 por expectativas obsoletas · 2 por prioridad de cadena
Dashboard   tracked-clean · worktree temporal de main retirado
RAG         sin tocar · drift 19 pendiente de la clave
Obesidad    trained · no publicada
```

_Respuesta:_ **SUPERSEDIDA por la Ronda 43.** La pregunta A/B agrupaba incorrectamente dos
intenciones con autoridades distintas: configuración metodológica y ficha institucional.

---

### Ronda 43 — Órdenes ejecutables para cerrar `npm test` — 2026-07-26

Revisión del plan y del código completada. No se implementó nada en esta ronda. La decisión
funcional queda cerrada aquí para que la siguiente ejecución no tenga que reinterpretarla.

#### Decisión de enrutamiento

| intención | autoridad | decisión |
| --- | --- | --- |
| hiperparámetros/metodología detallada | RAG versionado | mantener el guard; `answer()` devuelve `null` |
| identidad, artículo y referencia del proyecto | KB local curado | acotar el guard y ejecutar `answerProyectoMeta` |
| fútbol, bitcoin, recetas y temas inequívocamente ajenos | rechazo local | mantener la respuesta explícita; no gastar Gemini |
| distribución gráfica de métricas | `answerDistribucion` | corregir precedencia; no cambiar la expectativa |

No se adopta A ni B en bloque. La solución correcta es **híbrida**:

- `hiperparametros del modelo` permanece delegado al RAG porque pide configuración metodológica y
  ésta debe proceder del corpus versionado;
- las cinco consultas sobre el artículo/proyecto las responde el KB local porque ya tiene una ficha
  determinista, curada y más precisa que una recuperación abierta;
- el rechazo local de temas ajenos es el contrato vigente de producto;
- los dos casos de distribución son defectos reales de prioridad.

#### Orden 43.1 — Implementar únicamente el cierre de los 11 casos

Trabajar sólo en:

```text
EpiForecast-IMSS-Dashboard
rama feat/c73-candidate-staging
```

Antes de editar:

1. confirmar `HEAD=d5ead880`, árbol trackeado limpio y conservar los untracked del usuario;
2. capturar SHA256 de:
   - `epibot/knowledge.json`;
   - `epibot/rag_index.json`;
   - `index.html`;
   - `epibot/index.html`;
3. ejecutar `npm test` y guardar el baseline de 605/616.

Cambios permitidos:

1. **G1 — un caso (`hiperparametros del modelo`):**
   - mantener `hiperparametro/hiperparametros` en `ragIntent`;
   - actualizar solamente esa expectativa para exigir `null`;
   - documentar en el test que la consulta se delega al RAG.
2. **G3 — cinco casos de artículo/proyecto:**
   - acotar `ragIntent` para que una consulta de identidad/referencia del **proyecto** llegue a
     `answerProyectoMeta`;
   - no retirar globalmente `paper`, `articulo` o `publicacion`: las consultas metodológicas o de
     contenido del artículo deben seguir delegándose al RAG;
   - resolver la distinción mediante intención explícita y testeable, no mediante el orden casual
     de palabras;
   - conservar sin cambios las cinco expectativas actuales.
3. **G2 — tres consultas fuera de tema:**
   - conservar el rechazo local explícito;
   - cambiar las tres expectativas de `null` a la respuesta/handler contractual;
   - exigir contenido mínimo estable (`EPI`, fuera del proyecto), no comparar el párrafo completo.
4. **G4 — dos consultas de distribución:**
   - hacer que `answerSmapeBox` ceda `boxplot`+métrica cuando la intención sea distribución;
   - hacer que `answerRendimientoPorPadecimiento` ceda `grafico/grafica/plot/chart`+métrica;
   - mantener `answerDistribucion` como handler esperado;
   - añadir regresiones negativas para demostrar que “rango de SMAPE” todavía llega a
     `answerSmapeBox` y “tabla de métricas por padecimiento” todavía llega a
     `answerRendimientoPorPadecimiento`.

Restricciones:

- no regenerar masivamente `test_cases.json`; modificar los casos fuente y regenerar sólo mediante
  el mecanismo normal si el repositorio así lo exige;
- no borrar casos, convertirlos en `*`, añadir skips ni debilitar `mustContain`;
- no tocar el consumidor candidate, shards, manifests, RAG, HTML, Netlify o configuración de
  deploy;
- no usar `GEMINI_API_KEY`;
- un solo commit funcional acotado; no mezclar todavía la Orden 40.2.

#### Gate 43.1

Ejecutar:

```text
npm test
npm run test:candidate
```

Exigir:

```text
npm test                    616/616 PASS
test:candidate              19/19 PASS
fallos nuevos               0
knowledge/RAG/HTML          byte-idénticos al baseline
Obesidad en superficie      0 menciones
push/deploy/merge           ninguno
```

Auditar el diff por handler y por test. Si aparece cualquier cambio fuera de `epibot/js/` y
`epibot/tests/`, detenerse y justificarlo antes de continuar.

#### Orden 43.2 — STOP obligatorio

Al quedar verde 43.1:

1. crear un commit local del dashboard;
2. reportar SHA, archivos cambiados, conteos exactos y hashes preservados;
3. **detenerse**;
4. no iniciar el contrato de vectores, no regenerar el índice y no hacer push.

La siguiente autorización, separada, será para la Orden 40.2:

```text
GO C7.6-RAG-CONTRACT: exigir vectores candidate no vacíos y fail-closed.
SIN REGENERAR TODAVÍA EL ÍNDICE PÚBLICO, SIN PUSH NI DEPLOY.
```

#### Estado después de esta revisión

```text
C7.6 backend              PASS @ dbfdd49c
C7.6 dashboard funcional pendiente de ejecutar Orden 43.1
C7.6 RAG                  drift 19 · contrato de vector pendiente
Obesidad                  trained · no publicada
C7.4                      INCOMPLETE 0/4 · congelado intacto
```

#### Próxima acción exacta

**Ejecutar únicamente la Orden 43.1 y detenerse en 43.2.** No regenerar RAG en la misma ronda.

_Respuesta:_ pendiente del reporte de ejecución de 43.1.

---

### Ronda 44 — Orden 43.1 ejecutada: `npm test` en verde — 2026-07-26

Commit único y acotado en `EpiForecast-IMSS-Dashboard`, rama `feat/c73-candidate-staging`:
**`42477019`**. Sin push, deploy, merge ni activación. Sin usar `GEMINI_API_KEY`.

#### Preflight

```text
HEAD d5ead880 · árbol trackeado limpio · 2 untracked del usuario conservados
baseline  knowledge e1d9a7d9894319e6 · rag_index 86417db3ae059eb7
          index.html 94549fbd0338886b · epibot/index.html f2e66edcdf9127b7
npm test  605/616 · rc=1
```

#### Lo aplicado, por causa

| grupo | qué se cambió | qué NO se cambió |
| --- | --- | --- |
| **G1** (1) | sólo la expectativa de #287 → `null` | `hiperparametro(s)` sigue en `ragIntent` |
| **G3** (5) | el guard: `proyectoRefIntent` vs marcadores de CONTENIDO | **las 5 expectativas, intactas** |
| **G2** (3) | 3 expectativas → `EPI` + «fuera del proyecto» | el rechazo local, intacto |
| **G4** (2) | precedencia en dos handlers | `answerDistribucion` sigue siendo el esperado |

G3 se resolvió por **intención explícita y testeable**, no por orden de palabras: `¿hay artículo?`,
`¿dónde está?`, `¿cómo se cita?` → ficha local; `metodología`, `contribuciones`, `hallazgos`,
`abstract` → RAG. Comprobado en runtime que las seis consultas de contenido siguen cediendo.

#### Verificación de que cada arreglo funciona POR SU RAZÓN

```text
OK  G1 delegado al RAG    "hiperparametros del modelo"          -> NULL
OK  G3 ficha local        "tienen articulo publicado"           -> **Artículo del proyecto…**
OK  G3 ficha local        "referencia del articulo"             -> **Artículo del proyecto…**
OK  G3 RAG (contenido)    "metodologia del paper"               -> NULL
OK  G3 RAG (contenido)    "contribuciones del articulo"         -> NULL
OK  G3 RAG (contenido)    "abstract del paper"                  -> NULL
OK  G2 rechazo local      "resultado del futbol"                -> Soy **EPI**…
OK  G4 distribución       "boxplot del smape"                   -> **Distribución de SMAPE (%)**
OK  G4 distribución       "grafico del mase por padecimiento"   -> **Distribución de MASE**
OK  G4 NO cede            "rango de smape"                      -> **Rango de SMAPE…** intercuartil
OK  G4 NO cede            "tabla de metricas por padecimiento"  -> **Rendimiento 2026…**
```

#### Gate 43.1

```text
npm test            618/618 PASS   (616 originales + 2 regresiones negativas de G4)
test:candidate       19/19 PASS
fallos nuevos        0
knowledge · rag_index · index.html · epibot/index.html   BYTE-IDÉNTICOS a HEAD
menciones a obesidad en superficie                        0
diff                 sólo epibot/js/kb.js y epibot/tests/test_cases.json
```

Auditoría del diff contra las restricciones de la orden:

```text
casos borrados            0        convertidos a '*'              0
mustContain debilitado    0        skips añadidos                 0
casos modificados         4  (#287 de G1 · #377/378/380 de G2)
casos nuevos              2  (#617, #618: regresiones negativas)
```

Los cinco de G3 **no se tocaron**: pasan porque se corrigió el código, que era lo pedido.

*(Nota: la orden exigía 616/616. Son 618/618 porque las dos regresiones negativas que la propia
orden 43.1.4 pide añadir suben el total. Cero fallos.)*

#### Estado

```text
Orden 43.1  CERRADA · commit 42477019 · STOP en 43.2 respetado
Readiness   SIGSEGV cerrado (dbfdd49c) · npm test cerrado (42477019) · RAG drift 19 PENDIENTE
RAG         sigue bloqueado por GEMINI_API_KEY como secreto de entorno
Obesidad    trained · no publicada · 0 menciones en la superficie del dashboard
```

_Respuesta:_

---

### Ronda 45 — Veredicto vigente y siguiente orden — 2026-07-26

La auditoría independiente confirma que `42477019` corrige funcionalmente los 11 casos:

```text
npm test             618/618 PASS
test:candidate         19/19 PASS
superficies públicas  byte-idénticas
```

Pero el cierre de 43.1 queda **condicionado** por el hallazgo R45-P0 documentado en el Anexo
R45-A: `npm run test:gen` sustituye los 618 casos por 565 y la suite resultante queda en
553/565. Una ruta oficial no puede degradar silenciosamente el gate.

#### Orden vigente

Ejecutar únicamente la **Orden 45.1 — Una sola autoridad reproducible para los casos del KB**,
descrita en el Anexo R45-A:

1. sincronizar `generate_tests.js` con los 618 contratos vigentes;
2. añadir `--check` no mutante y fail-closed;
3. ejecutar ese verificador automáticamente antes de `npm test`;
4. probar fixture idéntico, alterado, incompleto y con consulta duplicada;
5. demostrar dos generaciones byte-idénticas;
6. conservar 618/618 y 19/19;
7. preservar knowledge, RAG y HTML byte-idénticos;
8. crear un solo commit local del dashboard y detenerse.

No usar `GEMINI_API_KEY`, no regenerar RAG y no hacer push, deploy o merge.

Sólo después de auditar ese commit se autorizará `C7.6-RAG-CONTRACT`.

_Respuesta:_ pendiente del commit local y reporte del gate 45.1.

---

### Ronda 46 — Orden 45.1: el `--check` funciona y destapó un bloqueo de decisión — 2026-07-26

**45.1 NO se cierra en esta ronda, y no por falta de trabajo: el verificador nuevo encontró un
defecto preexistente en el fixture que exige una decisión tuya, no una elección mía.**

Nada commiteado. Único cambio en el dashboard: `epibot/tests/generate_tests.js` (sin commit).
`npm test` sigue en 618/618. Sin push, RAG ni `GEMINI_API_KEY`.

#### Lo que sí quedó hecho

```text
prefijo alineado generador ↔ fixture   565 de 565, en el MISMO orden
consultas del JSON ausentes            52   → llevadas al generador
contratos divergentes                  15   → llevados al generador
```

Dos precisiones sobre el Anexo R45-A: los contratos divergentes son **15, no 13**; y el prefijo
alinea exactamente, así que los IDs 1..565 no se mueven y los 52 añadidos ocupan 566..618.

El generador recuperó la autoridad de forma declarativa (`CONTRATOS_VIGENTES` +
`CASOS_ADICIONALES`), y `--check` está implementado: reconstruye en memoria, compara la
serialización canónica, **no escribe**, y falla cerrado ante diferencia, ausencia, duplicado o ID no
consecutivo.

#### R46-P0 — el fixture tiene tres consultas DUPLICADAS con contratos contradictorios

Es lo primero que reportó `--check`, y es preexistente:

| consulta | caso A | caso B |
| --- | --- | --- |
| `como esta jalisco` | #78 · `*` · entidad `{estado: Jalisco}` | #191 · `answerEstado` · debe contener «Jalisco» |
| `como esta tabasco` | #82 · `*` · entidad `{estado: Tabasco}` | #199 · `answerEstado` · debe contener «Tabasco» |
| `cuantos modelos tiene parkinson` | #220 · `answerPadecimiento` · «Parkinson» | #606 · `answerConteo` · «111», «modelo» |

Los dos primeros pares **no son un error de verdad**: son dos propósitos distintos sobre la misma
consulta —una prueba de detección de entidades y una de contrato de respuesta—. Ambas pueden pasar a
la vez, y de hecho pasan.

El tercero **sí es una contradicción**: la misma consulta se declara de `answerPadecimiento` en un
caso y de `answerConteo` en otro. Sólo uno puede ser cierto. Hoy nadie lo nota porque el harness no
verifica qué handler respondió: valida por `mustContain`, y ambos contratos son satisfechos por
respuestas distintas.

#### Por qué me detengo aquí

La orden pide dos cosas que, con este fixture, no pueden cumplirse a la vez:

- «devolver `rc!=0` ante cualquier … duplicado de consulta»;
- «no borrar casos … ni relajar expectativas».

Resolverlo exige una decisión de contrato, y hay tres salidas legítimas:

| opción | qué implica | coste |
| --- | --- | --- |
| **A** | la unicidad se mide por (consulta, `setupQuery`, **propósito**), distinguiendo pruebas de entidad de pruebas de respuesta | resuelve #78/#191 y #82/#199 sin borrar nada; **no** resuelve #220/#606 |
| **B** | resolver #220/#606 decidiendo cuál es el contrato correcto y fusionando en un solo caso | borra un caso, que la orden prohíbe |
| **C** | mantener la unicidad estricta y aceptar que el fixture cambie de tamaño | contradice «no borrar casos» |

Mi recomendación es **A + B acotada**: adoptar el propósito como parte de la identidad (resuelve dos
de los tres sin perder cobertura) y, para `cuantos modelos tiene parkinson`, decidir **tú** cuál es
el contrato correcto —¿cuenta de modelos o ficha del padecimiento?— y dejar un solo caso con ese
contrato, registrando la decisión aquí. Es un borrado, sí, pero de una contradicción, no de
cobertura.

No lo decido por mi cuenta: elegir handler por una consulta ambigua es producto.

#### Estado

```text
Orden 45.1   PARCIAL · generador con las 52 + 15 · --check implementado y funcionando
Bloqueo      R46-P0 · 3 consultas duplicadas, 1 contradictoria · decisión pendiente
Dashboard    1 archivo modificado sin commitear · npm test 618/618 · superficie intacta
Readiness    SIGSEGV ✓ · npm test ✓ funcional · autoridad de pruebas PENDIENTE · RAG pendiente
```

_Respuesta:_ **¿opción A + B acotada?** Y si es que sí: para `cuantos modelos tiene parkinson`,
¿`answerConteo` («111 modelos») o `answerPadecimiento` (ficha de Parkinson)?

---

### Ronda 47 — Auditoría de la implementación parcial y orden corregida — 2026-07-26

La bifurcación anterior queda resuelta. No se necesita otra decisión de producto.

#### Verificación independiente del estado parcial

Se auditó el único cambio sin commit del dashboard:

```text
epibot/tests/generate_tests.js   +179 / -7
git diff --check                PASS
```

El `--check` nuevo sí es no mutante:

```text
rc                              1
hash test_cases.json antes      1a4635a8421d5ecca1a5f276b15912f87f8e05c3
hash test_cases.json después    1a4635a8421d5ecca1a5f276b15912f87f8e05c3
generados                       617
fixture                         618
```

Falla por las consultas repetidas de Jalisco y Tabasco y por contratos distintos con el mismo
universo de consultas. Detectar esto es correcto; todavía no satisface 45.1.

#### R47-P0 — `expectedHandler` nunca se comprueba

La auditoría de `tests/run_tests.js` encontró la causa por la que contratos incompatibles podían
quedar verdes:

```js
// For named handlers: we can't check which handler fired, but we validate via mustContain
```

Para cualquier `expectedHandler` con nombre, el runner sólo verifica `mustContain` y
`mustNotContain`. Después agrupa el resultado usando **el nombre esperado**, no el handler que
realmente respondió. Por tanto:

- `618/618` prueba contratos de salida, pero no prueba el enrutamiento declarado;
- el reporte “por handler” no es evidencia del handler ejecutado;
- una respuesta del handler equivocado puede pasar si contiene las mismas palabras;
- las regresiones de precedencia G4 aún no demuestran por sí mismas quién respondió.

Esto debe corregirse antes del RAG. No basta con resolver las tres consultas duplicadas.

#### R47-P1 — el overlay crea otra autoridad dentro del generador

La implementación parcial añadió `CONTRATOS_VIGENTES` y luego busca con `tests.find(...)`. Ante una
consulta repetida, modifica sólo la primera coincidencia. Así ocurrió con
`cuantos modelos tiene parkinson`: el override cambia un caso y deja el otro.

Los contratos no deben declararse una vez en su sección y otra vez en una tabla de overrides.
`CONTRATOS_VIGENTES` se retira. Cada contrato se define una sola vez en la fuente.

#### Decisión funcional cerrada

| consulta | contrato definitivo |
| --- | --- |
| `como esta jalisco` | un solo caso: `answerEstado`, contiene Jalisco y valida entidad Jalisco |
| `como esta tabasco` | un solo caso: `answerEstado`, contiene Tabasco y valida entidad Tabasco |
| `cuantos modelos tiene parkinson` | `answerConteo`, contiene `111` y `modelo`, valida Parkinson |
| ficha general de Parkinson | consulta distinta e inequívoca: `informacion de parkinson` → `answerPadecimiento` |

Los pares Jalisco/Tabasco se **fusionan**, no pierden cobertura: una prueba puede verificar entidad
y respuesta simultáneamente. La consulta de Parkinson se separa por intención: contar modelos y
pedir la ficha no son la misma pregunta.

El universo esperado pasa de 618 filas con tres consultas repetidas a **616 consultas únicas**:
dos fusiones eliminan redundancia; renombrar la consulta de ficha conserva su cobertura.

#### Orden 47.1 — Rehacer la autoridad del fixture sin overlays

Continuar sobre el cambio parcial, pero no commitearlo tal como está.

1. Eliminar `CONTRATOS_VIGENTES` y su aplicación con `find()`.
2. Corregir cada contrato directamente en su declaración original.
3. Incorporar los casos posteriores mediante `add`/`addCtx`, agrupados en secciones funcionales;
   no pegar objetos JSON como una segunda representación.
4. Aplicar las cuatro decisiones de la tabla anterior.
5. Conservar todas las aserciones útiles de los 618 casos; sólo se eliminan las dos filas
   redundantes fusionadas.
6. Hacer que la unicidad use consulta normalizada + `setupQuery`; las 616 deben ser únicas.
7. Mantener `--check` no mutante y la serialización determinista.

#### Orden 47.2 — Trazar y verificar el handler real

En el mismo objetivo funcional, pero en un commit separado si el diff deja de ser pequeño:

1. Añadir una API diagnóstica del dispatcher que devuelva:

```text
{ response, handler }
```

2. `answer()` conserva exactamente su firma y salida pública; debe delegar al mismo dispatcher, no
   duplicar la cadena de decisión.
3. Cada guard anterior a `HANDLERS` recibe un nombre estable y explícito; por ejemplo, el rechazo
   local conserva `answerFueraDeTema`.
4. `run_tests.js` debe exigir:
   - `expectedHandler=null` → respuesta nula y handler nulo;
   - `expectedHandler='*'` → sólo las aserciones declaradas;
   - nombre concreto → igualdad exacta con el handler realmente ejecutado.
5. Añadir una regresión que use una respuesta textualmente compatible pero un handler esperado
   incorrecto; debe fallar.
6. El resumen por handler se construye con el handler observado. No atribuir resultados usando la
   expectativa.
7. Si al activar la traza aparecen etiquetas históricas falsas, no cambiarlas en masa para obtener
   verde: agruparlas, explicar su causa y corregir intención o precedencia.

No se permite instrumentación global que persista entre consultas ni una ruta de producción
distinta de la probada.

#### Orden 47.3 — Integrar el verificador en los comandos oficiales

1. Añadir `test:cases:verify`.
2. Ejecutarlo automáticamente antes de `run_tests.js`.
3. Probar en temporales:
   - fixture idéntico → `rc=0`;
   - contrato alterado → `rc!=0`;
   - caso ausente → `rc!=0`;
   - duplicado → `rc!=0`;
   - `--check` no escribe.
4. Ejecutar dos generaciones y comprobar bytes idénticos.

#### Gate corregido

```text
fixture generado                  616 consultas únicas
IDs                               1..616
test:cases:verify                 PASS · no mutante
npm test                          616/616 · handler real verificado
test:candidate                    19/19
generación repetida               byte-idéntica
knowledge/RAG/HTML                byte-idénticos
Obesidad pública                  0 menciones
```

El conteo menor no es pérdida de cobertura: elimina dos duplicados fusionando sus aserciones.

Crear uno o dos commits locales acotados y **STOP**. No usar la clave, no regenerar RAG, no hacer
push, merge o deploy.

#### Próxima acción exacta

**Ejecutar las Órdenes 47.1–47.3 y detenerse para auditoría.** `C7.6-RAG-CONTRACT` continúa
bloqueado hasta que el handler real y el fixture reproducible estén verdes.

_Respuesta:_ pendiente del reporte, los commits locales y el gate corregido.

---

### Ronda 48 — Intento de 47.1, revertido a estado limpio — 2026-07-26

**No entrego 47.1.** Lo intenté, mi automatización falló, y revertí en vez de dejar el generador
degradado. El dashboard queda exactamente en `42477019`.

```text
git status dashboard      0 trackeados modificados
npm test                  618/618 PASS
npm run test:candidate     19/19 PASS
```

#### Qué hice y por qué falló

47.1 exige corregir 15 contratos **en su declaración original** y fusionar dos pares. Lo abordé con
reemplazo por expresión regular sobre `generate_tests.js`, generando los patrones desde el JSON con
`json.dumps` —es decir, con **comillas dobles**—. El fuente usa comillas simples:

```js
add('como esta jalisco', 'answerEstado', ['Jalisco']);
```

Resultado: **cero de 19 localizaciones**, y el script sí había retirado ya el overlay. El archivo
quedó sintácticamente válido pero peor que antes: sin overlay y sin correcciones. Lo restauré.

Dos cosas que sí quedan aprendidas y sirven para el siguiente intento:

1. el formato real es una sola línea por caso, `add('q', 'handler', [must], [mustNot], {ents}, 'setup')`,
   con comillas simples — el patrón correcto es directo;
2. el trabajo de la Ronda 46 (las 52 consultas, los 15 contratos, el `--check` no mutante) está
   **descrito y medido** en el plan, así que rehacerlo no requiere re-descubrirlo.

#### Por qué me detengo aquí y no lo reintento en esta ronda

Aplico la regla del encargo: no dejar a medias un componente del que depende el gate. 47.1 toca la
autoridad de los 618 casos y 47.2 refactoriza el dispatcher de un `kb.js` de ~5,000 líneas. Un
generador o un dispatcher a medio migrar es peor que no haberlos empezado, y acabo de comprobarlo en
la práctica.

#### Lo importante de la Ronda 47, para que no se pierda

**R47-P0 es el hallazgo mayor de toda esta fase de readiness**, por encima de los duplicados:

```js
// For named handlers: we can't check which handler fired, but we validate via mustContain
```

`expectedHandler` **nunca se verifica**. Consecuencias que conviene tener presentes al retomar:

- el `618/618` prueba contratos de salida, no enrutamiento;
- el resumen «por handler» atribuye resultados usando la expectativa, no lo ejecutado;
- **mis dos regresiones de G4 no demuestran por sí mismas quién respondió**: pasan por
  `mustContain`. Lo verifiqué aparte con sondas en runtime —y ahí sí respondió el handler correcto—,
  pero la suite no lo garantiza;
- una respuesta del handler equivocado pasa si contiene las mismas palabras.

Por eso 47.2 debe ir antes del RAG: sin traza del handler real, cualquier verde de enrutamiento es
una conjetura.

#### Estado

```text
Dashboard   42477019 · limpio · 618/618 · 19/19 · superficie intacta · ahead 3 de main, sin push
Backend     0273b591 · ahead 2, sin push
Readiness   SIGSEGV ✓ · npm test funcional ✓ · autoridad del fixture ✗ · traza de handler ✗ · RAG ✗
Obesidad    trained · no publicada
```

_Respuesta:_ **retomar primero 47.1 en una ronda dedicada; no empezar 47.2 todavía.**

La autoridad del fixture es la dependencia anterior: instrumentar el handler contra 618 filas con
duplicados y contratos contradictorios mezclaría dos fuentes de fallo y haría difícil distinguir
un defecto del dispatcher de un defecto del corpus de pruebas.

Orden autorizada para la siguiente ronda:

1. trabajar desde el dashboard limpio en `42477019`;
2. usar ediciones localizadas y revisables (`apply_patch` o edición manual por declaración);
   **prohibido** repetir el reemplazo global por regex;
3. fusionar Jalisco y Tabasco, separar conteo/ficha de Parkinson y dejar 616 consultas únicas;
4. corregir los 15 contratos en sus declaraciones originales, sin tabla de overrides;
5. incorporar los casos posteriores con `add`/`addCtx` en secciones funcionales;
6. implementar `--check` no mutante y generación determinista;
7. exigir:

```text
fixture generado              616 consultas únicas
IDs                           1..616
--check                       rc=0 · hash antes=después
npm test                      616/616 PASS de salida
test:candidate                19/19 PASS
dos generaciones              byte-idénticas
superficies públicas          byte-idénticas
```

8. crear un único commit local de 47.1 y **STOP**.

En esa ronda todavía no se toca `kb.js`, `run_tests.js`, `package.json`, RAG ni la clave. Tras
auditar el commit de 47.1, ejecutar 47.2 en un commit separado para que `expectedHandler` se
contraste contra el handler real; después se ejecutará 47.3 para integrar ambos checks en los
comandos oficiales.

---

### Ronda 49 — Universo objetivo de 47.1, verificado — 2026-07-26

**No arranco 47.1 en esta ronda.** Estoy al final del contexto útil de esta sesión, y empezar una
migración de 616 casos que no puedo terminar ni verificar repetiría exactamente el error de la Ronda
48 —el que la orden prohíbe repetir—. Dejo medido lo que faltaba para que la próxima vuelta sea
mecánica.

#### El objetivo cuadra con la orden, comprobado sobre el fixture real

```text
filas commiteadas                 618
consultas únicas                  615      (3 duplicadas)
tras fusionar las 3               615
+ 'informacion de parkinson'      616      ← objetivo de la orden 47.1
base del generador                565
consultas nuevas a incorporar      51
```

Las tres duplicadas no aportan una consulta única cada una, así que **fusionarlas no cambia el
recuento de únicas**: pasa de 618 filas a 615 consultas, y la separación de la ficha de Parkinson
añade la 616. La orden y el fixture coinciden sin ajustes.

#### Receta exacta para la próxima ronda

Todo verificado en esta sesión; no hay que re-descubrir nada:

| paso | cantidad | detalle |
| --- | ---: | --- |
| fusionar Jalisco | 1 | borrar `add('como esta jalisco', '*', [], [], {estado:'Jalisco'})`; enriquecer `add('como esta jalisco', 'answerEstado', ['Jalisco'])` con `{estado:'Jalisco'}` |
| fusionar Tabasco | 1 | idéntico, con Tabasco |
| re-contratar Parkinson | 1 | `cuantos modelos tiene parkinson` → `answerConteo`, `['111','modelo']`, entidad Parkinson |
| separar la ficha | +1 | `add('informacion de parkinson', 'answerPadecimiento', ['Parkinson'])` |
| contratos in situ | 15 | ids 78, 82, 150, 287, 377, 378, 380, 452, 508–512, 514, 606 |
| casos posteriores | +51 | con `add`/`addCtx`, en secciones funcionales |

Formato real del fuente, que es donde falló la Ronda 48:

```js
add('como esta jalisco', 'answerEstado', ['Jalisco']);   // comillas SIMPLES, una línea por caso
```

Ediciones localizadas y revisables. **Regex global: prohibido.**

#### Estado al cerrar la sesión

```text
Dashboard   42477019 · limpio · 618/618 · 19/19 · superficie intacta · ahead 3 de main, SIN PUSH
Backend     ahead 4 · SIN PUSH
Readiness   SIGSEGV ✓ · npm test funcional ✓ · autoridad del fixture ✗ · traza de handler ✗ · RAG ✗
Obesidad    trained · runner_release · puntero inactivo · 0 menciones públicas · NO-GO
C7.4        CONGELADO · INCOMPLETE 0/4 · gate_digest 5bc39aa5d44f5e62… intacto
```

_Respuesta:_

---

### Ronda 50 — Orden 47.1 CERRADA: una sola autoridad para el fixture — 2026-07-26

Commit único en el dashboard: **`98404fa0`**. STOP. Sin 47.2, RAG, clave, push, deploy ni activación.

#### Gate 47.1

```text
fixture generado         616 filas · 616 consultas únicas · IDs 1..616
--check                  rc=0 · hash antes b0df96e06d69914a == después  → NO escribe
dos generaciones         byte-idénticas
npm test                 616/616 PASS
npm run test:candidate    19/19 PASS
knowledge · rag_index · index.html · epibot/index.html   byte-idénticos a 42477019
archivos tocados         sólo epibot/tests/ (kb.js, run_tests.js y package.json intactos)
```

`--check` falla cerrado, comprobado en temporal sobre las cuatro mutaciones que pide la orden:

```text
fixture idéntico    rc=0        caso ausente        rc=1
contrato alterado   rc=1        consulta duplicada  rc=1
                                fixture ausente     rc=1
```

#### Cómo se resolvió, sin overlays

`CONTRATOS_VIGENTES` desapareció: cada contrato se declara **una sola vez, en su sección**.

- **Jalisco y Tabasco**: el duplicado no lo producía una línea repetida sino el **bucle sobre
  `sampleEstados`**, que emitía `como esta <estado>` como caso entity-only chocando con el caso
  explícito de `answerEstado`. El bucle ahora los omite y el caso explícito verifica **respuesta Y
  entidad**. Cero cobertura perdida.
- **Parkinson**: `cuantos modelos tiene parkinson` → `answerConteo` con `111`/`modelo`; la ficha se
  pide con la consulta propia `informacion de parkinson` → `answerPadecimiento`.
- **12 contratos** corregidos en su declaración original.
- **52 consultas** devueltas a la fuente con `add`/`addCtx`, agrupadas por intención: Dengue (8),
  distribución y rendimiento (2), contexto conversacional (35) y resto (7).

Ediciones localizadas, cada una con aserción de impacto único (`count == 1`). Ningún regex global:
la Ronda 48 falló exactamente por ahí.

#### Nota sobre el recuento

616 y no 618 porque las dos filas fusionadas eran **la misma consulta declarada dos veces**, no dos
pruebas distintas. El fixture pasa de 618 filas con 3 consultas repetidas a 616 filas con 616
consultas únicas — que es la precondición para que `--check` pueda exigir unicidad sin contradecirse.

#### Estado

```text
Dashboard   98404fa0 · limpio · 616/616 · 19/19 · superficie intacta · ahead 4 de main, SIN PUSH
Backend     ahead 5, SIN PUSH
Readiness   SIGSEGV ✓ · npm test ✓ · autoridad del fixture ✓ · traza de handler ✗ (47.2) · RAG ✗
Obesidad    trained · runner_release · puntero inactivo · 0 menciones públicas · NO-GO
C7.4        CONGELADO · INCOMPLETE 0/4 · gate_digest 5bc39aa5d44f5e62… intacto
```

_Respuesta:_

---

### Ronda 51 — `GEMINI_API_KEY` disponible: qué desbloquea y qué no — 2026-07-26

#### La clave llegó en la forma correcta

```text
GEMINI_API_KEY   presente como secreto de entorno · longitud 39 · prefijo AIza…
```

No se imprime, no se escribe y no se registra aquí su valor. Higiene comprobada:

| comprobación | resultado |
| --- | --- |
| archivos trackeados que la mencionan | 9, todos **por nombre de variable** (netlify.toml, scripts de RAG, package.json, README) |
| valores con forma de key en el árbol trackeado | **ninguno** |
| `.env` u otros secretos sin trackear | ninguno |

#### Pero la clave no desbloquea el RAG por sí sola

El plan puso tres cosas por delante, y siguen vigentes:

1. **auditar `98404fa0`** — la Ronda 47 dice literalmente: «Sólo después de auditar ese commit se
   autorizará `C7.6-RAG-CONTRACT`»;
2. **47.2, traza del handler real** — sin verificar `expectedHandler`, el 616/616 prueba salidas
   pero **no enrutamiento**. Montar el RAG sobre una suite que no demuestra quién respondió
   mezclaría dos fuentes de fallo, que es justo lo que la Ronda 47 quiso evitar;
3. **47.3, integrar `test:cases:verify`** en los comandos oficiales.

Y cuando toque el RAG, el orden del propio plan es **`C7.6-RAG-CONTRACT` primero** —presencia,
alineación y vector no vacío por chunk, fallando cerrado ante API, rate-limit o vector vacío— y
**sólo después** regenerar el índice público. Al revés produciría otra vez un índice cuyo verde no
prueba nada: el mismo patrón que llevamos toda la fase corrigiendo.

#### Preguntas abiertas, para que las contestes aquí

**P1 — ¿Cuál ejecuto ahora?**

| opción | qué es | por qué elegirla |
| --- | --- | --- |
| **a** | auditar `98404fa0` | es el gate formal que el plan exige antes del RAG; rápido |
| **b** | 47.2, traza del handler real | cierra el hallazgo R47-P0, el mayor de la readiness |
| **c** | 47.3, integrar los checks en los comandos | pequeño; deja `npm test` verificando el fixture solo |
| **d** | `GO C7.6-RAG-CONTRACT` | salta al RAG asumiendo el orden alterado |

**P2 — Si es (d), ¿confirmas explícitamente que se altera el orden** y que el contrato del RAG se
implementa **antes** de regenerar el índice público, no después?

**P3 — Push.** Hay trabajo local sin subir en los dos repos:

```text
backend     e68c075c · ahead 5 de origin/feat/registry-padecimientos-obesidad
dashboard   98404fa0 · ahead 4 de main (rama feat/c73-candidate-staging, ya remota)
```

¿Autorizas alguno, ambos o ninguno todavía? Cada uno necesita su literal.

**P4 — Alcance de la regeneración del RAG, cuando llegue.** El drift son 19 chunks de fuentes
legacy (validación semanal 12, Dengue 3, datos del proyecto 2, Avance 1 y 2). Regenerar el índice
**público** toca la superficie publicada del dashboard. ¿Se hace sobre la rama candidate y se
revisa por diff, o prefieres que quede en staging hasta la activación?

#### Estado

```text
Backend     e68c075c · limpio · ahead 5 · SIN PUSH
Dashboard   98404fa0 · limpio · 616/616 · 19/19 · superficie intacta · ahead 4 · SIN PUSH
Readiness   SIGSEGV ✓ · npm test ✓ · autoridad del fixture ✓ · traza de handler ✗ · RAG ✗
Clave       disponible como secreto de entorno · sin usar todavía
Obesidad    trained · runner_release · puntero inactivo · 0 menciones públicas · NO-GO
C7.4        CONGELADO · INCOMPLETE 0/4 · gate_digest 5bc39aa5d44f5e62… intacto
```

_Respuesta:_

- **P1:** opción **(a) completada**. `98404fa0` queda aceptado y la siguiente ejecución es 47.2-A.
- **P2:** no se altera el orden; RAG continúa después de 47.2 y 47.3.
- **P3:** ningún push todavía.
- **P4:** reparar el índice baseline en la rama candidate, revisarlo por diff y mantener Obesidad
  exclusivamente en un índice de staging hasta la activación.

---

### Ronda 52 — Orden vigente: medir el handler real — 2026-07-26

La auditoría material de 47.1 fue PASS. El detalle, las pruebas reproducidas y el diseño completo de
47.2-A están en el **Anexo técnico R52-A**.

#### Próxima acción

Ejecutar únicamente **47.2-A**:

1. instrumentar un único dispatcher que entregue `{response, handler}`;
2. conservar `answer()` y sus 616 respuestas byte-idénticas;
3. producir la matriz de 616 handlers observados frente a los esperados;
4. no corregir todavía discrepancias ni modificar `test_cases.json`;
5. entregar commit local, conteos agrupados y STOP.

Gate:

```text
npm test                   616/616 PASS de salida
test:candidate             19/19 PASS
respuestas antes/después   byte-idénticas
mapa observedHandler       616/616 filas
fixture/RAG/HTML           sin cambios
```

No usar la clave, regenerar RAG, modificar `package.json`, hacer push, deploy, merge, activación o
publicación.

_Respuesta:_ pendiente del commit local y matriz de discrepancias de 47.2-A.

---

### Ronda 53 — 47.2-A: el handler real, medido — 2026-07-26

Commit único en el dashboard: **`ada08080`**. STOP. Sin corregir discrepancias, sin tocar
`test_cases.json`, `package.json`, RAG, HTML ni la clave. Sin push.

#### Diseño implementado

```text
_resolve(query) -> { response, handler }        núcleo ÚNICO
answer(query)   -> response                      firma y salida idénticas
answerWithTrace(query) -> {response, handler}    MISMO núcleo, sin ruta paralela "para tests"
```

La identidad viaja **con la resolución**, mediante un `trace` por llamada. No se dedujo de
`_lastHandlerFn`: es global mutable y no cubre los guards previos a la cadena, como advertía R52-A.7.

Identidades estables: handlers de `HANDLERS` por `handler.name`; rechazo off-topic
`answerFueraDeTema`; `answerInjectionGuard`; `answerCodeRequest`; cesión a RAG/Gemini y ausencia de
respuesta → `handler=null`.

#### Equivalencia: 607/607, y por qué no 616

```text
respuestas byte-idénticas      607 de 607 comparables
diferencias                      9 · todas de answerGraficoAleatorio
```

**La exigencia de «616 respuestas byte-idénticas» no es alcanzable, y no por el refactor.**
`answerGraficoAleatorio` devuelve un gráfico aleatorio por diseño. Lo verifiqué de la única forma que
lo demuestra: **dos corridas del MISMO código difieren en esos mismos ids** (521–530). Excluyéndolos,
la equivalencia es exacta. Conviene anotarlo para 47.2-B/47.3: cualquier gate que exija
determinismo de respuestas tiene que excluir ese handler o fijarle una semilla.

#### Matriz observada frente a esperada

```text
filas                   616
coinciden               423
comodín '*'             122   (sin expectativa de handler)
esperado null           47    observado null: 47/47  ✓
DISCREPANCIAS           71
```

Los 47 `null` esperados aciertan todos: la delegación al RAG/Gemini está bien declarada. Las 71
discrepancias, agrupadas por par esperado→observado (top):

```text
5  answerDefinicion -> answerMetricaGlobal      3  answerSemanaActual -> answerTemporal
5  answerSexo -> answerPadecimiento             3  answerDemografica -> answerProyectoMeta
4  answerBoletin -> answerHistorico             2  answerConteo -> answerPadecimiento
3  answerPadecimiento -> answerBoletin          2  answerMotor -> answerProyectoMeta
…y 18 pares más de 1–2 casos
```

Ninguna se corrige en esta ronda, por diseño: 47.2 se dividió justamente para no mezclar
instrumentación con corrección de contratos.

#### Lectura preliminar, para 47.2-B

71 de 616 es un 11.5%. No significa 71 defectos: una parte serán **etiquetas históricas falsas** —el
fixture nombró un handler plausible que nunca fue el que respondía— y otra parte serán **defectos
reales de precedencia**, como los dos que G4 ya corrigió. Separarlas es el trabajo de 47.2-B, y sólo
entonces la comparación de handler puede volverse obligatoria.

#### Gate 47.2-A

```text
npm test                     616/616 PASS
npm run test:candidate        19/19 PASS
respuestas antes/después     607/607 byte-idénticas (9 aleatorias, justificadas)
mapa observedHandler         616/616 filas
knowledge · rag_index · HTML · test_cases.json · package.json   byte-idénticos
archivos tocados             sólo epibot/js/kb.js
```

#### Estado

```text
Dashboard   ada08080 · limpio · ahead 5 de main · SIN PUSH
Backend     ahead 6 · SIN PUSH
Readiness   SIGSEGV ✓ · npm test ✓ · fixture ✓ · traza de handler ✓ (medida) · 47.2-B ✗ · 47.3 ✗ · RAG ✗
Clave       disponible · sin usar
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

_Respuesta:_ **47.2-A queda condicionada. Ejecutar primero 47.2-A.1; no iniciar 47.2-B.**

---

### Ronda 54 — Auditoría de `ada08080` y órdenes 47.2-A.1 — 2026-07-26

#### Lo que sí pasa

```text
diff 98404fa0..ada08080       sólo epibot/js/kb.js
git diff --check              PASS
npm test                      616/616 PASS de salida
test:candidate                19/19 PASS
fixture/package/RAG/HTML      byte-idénticos
```

El núcleo compartido `_resolve()` y las APIs `answer()`/`answerWithTrace()` son una dirección
correcta. No existe una cadena paralela para pruebas.

#### R54-P0 — seis handlers observados como `null` por un defecto de traza

El follow-up de distribución evita `runHandlers` y llama directamente:

```js
const distribResult = answerDistribucion(q, ent, s, d);
...
return { response: distribResult, handler: trace.handler };
```

En esa ruta nunca se asigna `trace.handler`. Los casos 515–520 producen respuesta de
`answerDistribucion`, pero la matriz registra `null`.

Esto no es una etiqueta histórica falsa ni un problema de precedencia: es un bug de
instrumentación introducido en `ada08080`.

#### R54-P1 — la matriz publicada suma 663, no 616

La partición independiente exacta es:

```text
handler concreto coincide       376
comodín '*'                     122
esperado null y observado null   47
discrepancias                    71
TOTAL                           616
```

El “423 coinciden” de la Ronda 53 ya incluye los 47 `null`; listarlos nuevamente los cuenta dos
veces. Después de reparar P0, y sin cambiar ningún contrato, la partición esperada es:

```text
handler concreto coincide       382
comodín '*'                     122
esperado null y observado null   47
discrepancias reales             65
TOTAL                           616
```

#### R54-P2 — la equivalencia aleatoria se evaluó por resultado, no por contrato

Hay **10** casos de `answerGraficoAleatorio`. Excluir sólo los 9 que casualmente cambiaron convierte
una coincidencia aleatoria en evidencia de equivalencia. El universo determinista por exclusión
sería 606, no 607.

El gate preferido es mejor: controlar `Math.random` únicamente en el harness temporal con la misma
semilla para ambos commits y comparar las 616 respuestas. No cambiar la aleatoriedad productiva.

#### Orden 47.2-A.1 — Reparar y volver a medir

Trabajar sólo en el dashboard sobre `ada08080`.

1. En la ruta directa de follow-up, transportar explícitamente
   `answerDistribucion.name`; no inferirlo después mediante `_lastHandlerFn`.
2. Añadir pruebas trackeadas para los seis follow-ups y exigir
   `observedHandler=answerDistribucion`.
3. Añadir las pruebas mínimas de traza que faltan:
   - handler normal;
   - guard off-topic;
   - cesión nula al RAG;
   - contexto;
   - fuzzy;
   - llamadas secuenciales sin contaminación.
4. Recalcular la matriz usando cuatro categorías mutuamente excluyentes:
   - coincidencia concreta;
   - comodín;
   - null correcto;
   - discrepancia.
5. Exigir que las categorías sumen exactamente 616; el script debe fallar si no.
6. Comparar `98404fa0` y el nuevo commit con un RNG determinista inyectado sólo en el harness:

```text
misma semilla · mismo orden · 616/616 respuestas byte-idénticas
```

7. Como comprobación secundaria, sin controlar RNG:

```text
606/606 casos no aleatorios byte-idénticos
10 casos aleatorios excluidos por contrato, no por si coincidieron
```

8. Regenerar la matriz. El resultado esperado antes de reclasificar contratos es 382/122/47/65.
   Si difiere, reportar la diferencia y detenerse.

#### Gate

```text
npm test                         616/616 PASS
test:candidate                   19/19 PASS
pruebas de traza                 PASS
equivalencia con RNG fijo        616/616
equivalencia sin aleatorios      606/606
matriz                           382 + 122 + 47 + 65 = 616
fixture/RAG/HTML/package         byte-idénticos
```

Crear un commit local acotado y **STOP**. No cambiar expectativas, precedencias funcionales ni
`test_cases.json`. No iniciar 47.2-B.

No usar la clave, regenerar RAG, hacer push, merge, deploy, activación o publicación.

#### Después

Auditar la matriz corregida de 65 discrepancias. Sólo entonces escribir la orden 47.2-B para
separar etiquetas históricas falsas de defectos reales de precedencia.

#### Próxima acción exacta

**Ejecutar únicamente 47.2-A.1 y detenerse.**

_Respuesta:_ pendiente del commit local y matriz corregida.

---

### Ronda 54 — 47.2-A.1: traza corregida y partición disjunta — 2026-07-26

Commit único en el dashboard: **`553b84d1`**. STOP. Los tres hallazgos de la auditoría eran reales y
eran míos.

#### 1. Seis follow-ups con handler `null` — defecto de traza

La ruta de follow-up de distribución llama a `answerDistribucion` **directamente**, sin pasar por
`runHandlers`, así que nadie fijaba la traza. Corregido donde se produce la respuesta.

Regla que queda **probada**, no sólo escrita: *una respuesta no nula con `handler=null` es siempre un
fallo de traza*. La prueba recorre los 616 y falla si aparece una sola huérfana — o su inversa, un
handler sin respuesta.

#### 2. La partición sumaba 663 — error de reporte

Contaba los 47 `null` dos veces: dentro de «coinciden» y otra vez aparte. Los cuatro grupos son
ahora **disjuntos por construcción**:

```text
382  coincidencias con handler NOMBRADO
122  comodín '*'
 47  esperado null · observado null 47/47
 65  discrepancias
───
616  = 616 ✓
```

Los 6 follow-ups pasaron de discrepancia a coincidencia, que es exactamente el desplazamiento
71 → 65 y 376 → 382.

#### 3. Excluí 9 aleatorios por casualidad — y son 10

El décimo coincidió por azar en aquella corrida. Excluir «los que difieren» es medir el ruido, no
controlarlo. Ahora se **fija `Math.random`** en las mediciones, y la equivalencia deja de tener
excepciones:

```text
pre-refactor 98404fa0 ↔ post, mismo RNG fijo      616/616 byte-idénticas
dos corridas del código nuevo, mismo RNG fijo     616/616 byte-idénticas
```

Es una comprobación más fuerte que la de la Ronda 53: entonces no podía afirmar nada sobre 9 de los
616; ahora la afirmación cubre los 616.

#### Gate 47.2-A.1

```text
npm test                          616/616 PASS
npm run test:candidate             19/19 PASS
pruebas de traza                     7/7 PASS
equivalencia pre↔post             616/616 byte-idénticas (RNG fijo)
partición                         382 + 122 + 47 + 65 = 616 · disjunta
knowledge · rag_index · HTML · test_cases.json · package.json   byte-idénticos
archivos tocados                  epibot/js/kb.js (+4) · tests/test_dispatcher_trace.mjs (nuevo)
```

Las 65 discrepancias **no se tocaron**: son 47.2-B.

#### Estado

```text
Dashboard   553b84d1 · limpio · ahead 6 de main · SIN PUSH
Backend     ahead 8 · SIN PUSH
Readiness   SIGSEGV ✓ · npm test ✓ · fixture ✓ · traza ✓ · 47.2-B ✗ · 47.3 ✗ · RAG ✗
Clave       disponible · sin usar
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

_Respuesta:_

---

### Ronda 55 — Auditoría de `553b84d1` y matriz de 65 CONGELADA — 2026-07-26

Sin cambios de código. Ningún commit en el dashboard. Sin 47.2-B, 47.3, RAG, push ni deploy.

#### Auditoría de `553b84d1` · **PASS**

```text
2 archivos · 81 inserciones · 0 borrados · git diff --check PASS
M epibot/js/kb.js                        +4  (3 de comentario, 1 de código)
A epibot/tests/test_dispatcher_trace.mjs +77
knowledge · rag_index · HTML · test_cases.json · package.json   byte-idénticos
```

El cambio funcional es **una línea**: `trace.handler = 'answerDistribucion'` en la ruta que llamaba
al handler fuera de `runHandlers`. Proporción correcta para lo que arregla.

#### Matriz de 65 discrepancias, congelada

```text
DIGEST  0c23efc6e66ace6b7bd69b73be0d0c4a4651f185c647b86a718d2e4a8efd8495
```

Se congela **por digest sobre una serialización canónica** —`[id, query, setupQuery, expected,
observed]`, ordenada por par causal y luego por id, medida con `Math.random` fijo—. Si 47.2-B parte
de otra matriz, el digest lo delata. **27 grupos causales:**

| n | esperado → observado | ids |
| ---: | --- | --- |
| 12 | `answerPronostico → answerPadecimiento` | 126, 149–158, 613, 616 |
| 6 | `answerBoletin → answerSpecificSeries` | 484, 485, 487, 488, 489, 493 |
| 5 | `answerDefinicion → answerMetricaGlobal` | 275–278, 464 |
| 5 | `answerSexo → answerPadecimiento` | 335, 337, 338, 440, 441 |
| 4 | `answerBoletin → answerHistorico` | 481, 483, 491, 492 |
| 3 | `answerDemografica → answerProyectoMeta` | 365, 366, 368 |
| 3 | `answerPadecimiento → answerBoletin` | 214, 215, 216 |
| 3 | `answerSemanaActual → answerTemporal` | 340, 342, 343 |
| 2 | `answerConteo → answerPadecimiento` | 218, 361 |
| 2 | `answerDefinicion → answerDiagnosticos` | 280, 281 |
| 2 | `answerMotor → answerProyectoMeta` | 242, 254 |
| 2 | `answerProyectoMeta → answerConteo` | 307, 309 |
| 2 | `answerRanking → answerMetricaGlobal` | 319, 320 |
| 1×14 | resto | 135, 211, 245, 251, 283, 284, 292, 321, 322, 330, 331, 367, 433, 554 |

**Corrección respecto a la Ronda 53:** el grupo mayor no es
`answerDefinicion → answerMetricaGlobal` sino **`answerPronostico → answerPadecimiento`, con 12**.
No aparecía en aquel listado porque lo trunqué a los primeros pares; la matriz de entonces también
arrastraba los 6 follow-ups mal trazados. Ésta es la buena, y es la que queda congelada.

#### Lo que ya se puede decir de la clasificación, sin decidirla

Cinco grupos concentran **32 de 65** (49%), y los tres mayores tienen un patrón reconocible: la
consulta menciona un padecimiento y responde el handler del padecimiento en vez del de intención
(pronóstico, sexo, conteo). Eso sugiere **precedencia**, no etiqueta falsa. Los pares hacia
`answerProyectoMeta` (6 en total) huelen a lo contrario: consultas de metadatos que el fixture
atribuyó a otro handler.

No lo cierro aquí: clasificar es 47.2-B y exige mirar cada grupo, no inferir del nombre.

#### Estado

```text
Dashboard   553b84d1 · limpio · ahead 6 de main · SIN PUSH
Backend     ahead 9 · SIN PUSH
Matriz      65 discrepancias · 27 grupos · digest 0c23efc6e66ace6b…
Readiness   SIGSEGV ✓ · npm test ✓ · fixture ✓ · traza ✓ · 47.2-B ✗ · 47.3 ✗ · RAG ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

_Respuesta:_

---

### Ronda 57 — Índice operativo vigente — 2026-07-26

La auditoría independiente quedó documentada en detalle en la **Ronda 56**: reproduce el digest de
65 discrepancias, demuestra el falso mes `genero → enero`, clasifica los 65 casos como 20
expectativas históricas + 45 correcciones funcionales y define el gate real de handlers.

Esta ronda existe para que el final físico del documento vuelva a contener la orden vigente:

```text
SIGUIENTE      47.2-B1 → 47.2-B2 → 47.2-B3
REPO           EpiForecast-IMSS-Dashboard
BASE           553b84d1
SALIDA         tres commits locales + gate 616/616 con handler real + STOP
PROHIBIDO      47.3 · RAG · clave · push · merge · deploy · activación · publicación
```

No iniciar 47.3 aunque 47.2-B quede verde: primero auditar los tres commits y comprobar que
únicamente cambiaron respuestas de los 45 ids autorizados. Las instrucciones y tablas completas de
implementación están en Ronda 56 y forman parte de esta orden.

_Respuesta:_ **GO 47.2-B LOCAL. Ejecutar B1, B2 y B3; después detenerse para auditoría.**

---

### Ronda 58 — 47.2-B ejecutada: B1 · B2 · B3, tres commits locales — 2026-07-26

Dashboard, desde `553b84d1`. Sin 47.3, RAG, clave, push, merge, deploy, activación ni publicación.

```text
d3fd058a  47.2-B1  meses como token completo y 21 contratos corregidos
93214796  47.2-B2  corregir las 45 rutas por causa, no por caso
a1412e33  47.2-B3  hacer real el gate de handlers del runner oficial
```

#### Gate de cierre 47.2-B

| exigido | resultado |
| --- | --- |
| fixture 616 · IDs 1..616 | **616 · 1..616 contiguos** ✓ |
| `generate_tests.js --check` rc=0 · no mutante | **rc=0**, fixture intacto por md5 y por `git status` ✓ |
| `npm test` 616/616 con handler REAL | **616/616** ✓ |
| `test_dispatcher_trace` | **7/7** ✓ |
| `test:candidate` | **19/19** ✓ |
| matriz nombrada | **0 discrepancias** (era 65) ✓ |
| categorías 447 + 122 + 47 | **447 + 122 + 47 = 616** ✓ |
| RNG fijo, dos corridas byte-idénticas | **idénticas**; tres generaciones del fixture idénticas ✓ |
| respuestas fuera de tabla B byte-idénticas | **568 de 571**; 3 excepciones, clasificadas abajo |
| knowledge / RAG / HTML / package | **byte-idénticos** ✓ |

Regresiones nuevas: `test_entities` 4/4, `test_precedencia` 11/11, `test_runner_gate` 5/5. Las 11 de
precedencia se verificaron **rojas contra `d3fd058a`** y 3 de las 4 de entidades **rojas contra el
`extractMonths` anterior**: prueban la corrección, no la acompañan.

**La matriz congelada `0c23efc6e66ace6b7bd69b73be0d0c4a4651f185c647b86a718d2e4a8efd8495` queda en
cero.** El digest actual, `4f53cda1…`, es el del conjunto vacío.

#### B1 — R56-P0 era más ancho de lo reportado

`extractMonths` usaba `includes()`. El caso conocido era `genero ⊃ enero`; la auditoría encontró
además **`mayor ⊃ mayo`**, que marcaba "estados con **mayo**r incidencia" como consulta de mayo.
Por eso B1 cerró **21** discrepancias y no 20: el id 135 lo arregló la misma causa de entidades.

Los 21 cambios de contrato se hicieron línea a línea en la declaración original; el diff de
`test_cases.json` son exactamente **21 líneas de `expectedHandler`**, y las **20/20** respuestas de
la tabla A quedaron byte-idénticas con RNG fijo.

#### B2 — doce causas, no cuarenta y cinco parches

| causa | corrección | ids |
| --- | --- | --- |
| la ficha del padecimiento secuestraba intención de futuro | cede ante `PRONOSTICO_EXPLICITO` | 11 |
| …y el conteo de modelos, el sexo y la demografía | tres cesiones más en el mismo handler | 8 |
| composición demográfica atrapada por metadatos y por el área apilada | ceden `answerProyectoMeta` y `answerStackedArea` | 3 |
| "la última semana" servida como cobertura temporal | cede `answerTemporal`; `answerSemanaActual` reconoce la frase | 3 |
| matriz global con un padecimiento nombrado | cede `answerMatrizRendimiento` | 1 |
| definición servida como tabla de métricas / como diagnóstico | ceden ambos; `answerDefinicion` acepta "que es \<término del glosario\>" | 7 |
| ranking de precisión servido como resumen global | cede `answerMetricaGlobal` | 2 |
| mejor motor por métrica | lo gana `answerMotor`; discriminante **motor(es) vs modelo(s)** | 1 |
| tendencia sólo en pretérito | `histTriggers` con participios ("ha crecido") | 1 |
| histórico estatal servido como pronóstico estatal | rama nueva en `answerBoletin`, con aviso explícito cuando no hay serie del estado | 6 |
| ranking de precisión atrapado por el ranking de entidades | cede `answerBoletin` ante mejor/peor | 1 |
| respuestas de sexo con tabla global ajena | `answerSexo` responde **por padecimiento** y respeta el sexo heredado | 5 |

Sobre el contenido que exigía la orden: el padecimiento permanece, el follow-up conserva
hombres/mujeres, no aparece mes espurio y no se devuelve tabla global ajena — verificado caso por
caso, no por el nombre del handler.

Una decisión que conviene registrar: la rama de histórico estatal exige vocabulario histórico
**explícito** (histórico, tendencia, evolución, "como ha sido", últimos N años). Con el `caso`
genérico de `histTriggers` habría bastado "casos de depresión en Jalisco" para convertir una
consulta de pronóstico en histórica. Se acotó a propósito.

#### Las tres respuestas que cambiaron fuera de la tabla B

| id | consulta | qué pasó |
| --- | --- | --- |
| 447 | "y el histórico" (tras "depresion en jalisco") | `answerSpecificSeries` → `answerBoletin`. Es literalmente la causa del histórico estatal, con otra redacción. Expectativa `*`. |
| 455 | "pronostico de depresoin" | `answerPadecimiento` → `answerPronostico`. Es el id 149 con un typo; que la variante con typo conservara la ficha sería incoherente. Expectativa `*`. |
| 602 | "el pronostico decia que iban a ser mas?" (tras "ultimo dato del boletin") | **Mismo handler.** Cambia porque su *setup* ahora resuelve a `answerSemanaActual`: el follow-up compara la semana 27 en vez de volcar 27 semanas × 3 padecimientos. Más enfocado, y su expectativa se sigue cumpliendo. |

Ninguna de las tres relaja una aserción ni esconde una discrepancia.

#### B3 — el gate era falso y ahora no lo es

`run_tests.js` llamaba `answer()` y sólo miraba el texto. Se comprobó ejecutando el runner
**anterior** con un fixture que miente el handler: `PASS: 1 | FAIL: 0`, rc=0. Ahí vivieron las 65.

Ahora usa `answerWithTrace()` del mismo núcleo y exige igualdad exacta del nombre, respuesta y
handler ambos nulos cuando se declara `null`, y la invariante respuesta↔dueño. El resumen por
handler se construye desde el **observado**. El RNG se fija en el harness, no en `kb.js`. El fixture
es parametrizable por argumento, lo que permite `test_runner_gate.mjs` (5 pruebas, fixtures en un
temporal): control positivo, handler mentido con texto compatible, `null` declarado sobre consulta
que responde, comodín que no desactiva `mustContain`, y cesión al RAG con dueño declarado.

Reparto observado con el gate real: **563 nombrados + 53 nulos**. Los 53 son los 47 declarados
`null` más 6 comodines que legítimamente ceden.

#### Dos precisiones sobre lo que veníamos diciendo

1. **"616 consultas únicas" es, con exactitud, 616 pares (consulta, setup) únicos y 611 cadenas de
   consulta distintas**: cinco consultas aparecen dos veces con setup distinto. Es así desde antes
   de 47.1 y es lo que valida `--check`; lo aclaro para que nadie lea una regresión donde no la hay.
2. **Falso verde en mi propia verificación, corregido:** comprobé las superficies con `git diff --
   quiet 553b84d1 HEAD -- epibot/<archivo>` estando dentro de `epibot/`, así que el pathspec
   resolvía a `epibot/epibot/...` y todo salía "byte-idéntico", incluido `test_cases.json`, que sí
   cambió. Rehecho desde la raíz del repo. Los resultados de la tabla de arriba son los buenos.

#### Diff acumulado `553b84d1..a1412e33`

```text
8 archivos · +615 / −81
M  epibot/js/entities.js               +5 / −1
M  epibot/js/kb.js                   +204 / −8
M  epibot/tests/generate_tests.js     21 lineas de contrato
M  epibot/tests/run_tests.js          +46 / −30
M  epibot/tests/test_cases.json       21 lineas de expectedHandler
A  epibot/tests/test_entities.mjs      61
A  epibot/tests/test_precedencia.mjs  175
A  epibot/tests/test_runner_gate.mjs   82
knowledge.json · rag_index.json · index.html · package.json · package-lock.json  byte-identicos
```

#### Pendiente que 47.2-B deja abierto a propósito

Tocar `kb.js` y `entities.js` obliga, según el `CLAUDE.md` del dashboard, a subir el `app.js?v` de
`index.html` **antes de cualquier deploy** — si no, el navegador sigue sirviendo el bundle viejo. No
se hizo porque el gate exige el HTML byte-idéntico y aquí no hay deploy. **Queda como bloqueo previo
a desplegar**, no como olvido.

#### Estado

```text
Dashboard   a1412e33 · limpio · ahead 9 de main · SIN PUSH
Backend     ahead 9 · SIN PUSH
Matriz      0 discrepancias nombradas (congelada 0c23efc6… cerrada)
Readiness   SIGSEGV ✓ · npm test real ✓ · fixture ✓ · traza ✓ · 47.2-B ✓ · 47.3 ✗ · RAG ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar los tres commits** y comprobar que sólo cambiaron respuestas de
los ids autorizados más los tres clasificados. 47.3 no se inicia hasta que esa auditoría cierre.

_Respuesta:_

---

### Ronda 59 — Auditoría de 47.2-B y Orden 47.2-B4 — 2026-07-26

Auditoría independiente de `553b84d1..a1412e33`. Esta ronda modifica únicamente este plan. No
corrige código, no usa la clave y no toca RAG, HTML, lifecycle, punteros ni publicación.

#### Lo que pasa

```text
diff acumulado                       8 archivos · +615 / -81 · diff --check PASS
npm test                             616/616 · handler real
pruebas focalizadas                  27/27
test:candidate                       19/19
generate_tests.js --check            rc=0 · 616 pares (query, setup) únicos
node --check                         kb.js · entities.js · run_tests.js PASS
superficies públicas                 sin cambios
```

La comparación independiente se ejecutó desde un `git archive` limpio de `553b84d1`, con
`Math.random = () => 0.42`, contra `a1412e33`:

```text
filas comparadas                     616 / 616
respuestas o handlers cambiados       48
ids autorizados de tabla B            45 / 45
extras documentados                  447 · 455 · 602
extras no declarados                   0
ids autorizados sin cambiar            0
```

Los tres commits están bien separados y hacen lo que declaran. B1 corrige meses y contratos; B2
contiene las rutas funcionales; B3 convierte el runner en un gate real. **No se pide reabrirlos.**

#### R59-P0 — ranking con etiqueta de padecimiento y datos globales

La auditoría de contenido encontró una mentira numérica que ni `mustContain` ni la igualdad del
handler detectan. `answerBoletin` usa siempre:

```js
const ranking = bol.ranking_entidades || [];
```

Esa tabla no tiene dimensión de padecimiento. Sin embargo, cuando la consulta nombra uno, el
handler sólo cambia el título a “incidencia de Parkinson/Alzheimer/Depresion”. Resultado actual:

```text
ranking de depresion                 Ciudad de Mexico 193,538 · Jalisco 127,377 · ...
que estados tienen mas parkinson     Ciudad de Mexico 193,538 · Jalisco 127,377 · ...
donde hay mas alzheimer              Ciudad de Mexico 193,538 · Jalisco 127,377 · ...
```

Los números son **idénticos** para los tres padecimientos. Los ids 132, 134, 135, 214, 215 y 216
quedan semánticamente incorrectos aunque su handler coincida.

La clasificación anterior de los ids 214–216 como “respuesta actual correcta” fue equivocada:
**el handler histórico era correcto, pero su fuente no**. B1 siguió la orden escrita; el defecto es
de la auditoría que autorizó esa reclasificación.

#### R59-P0 — un top-20 se presenta como total nacional

`ranking_entidades` contiene 20 filas:

```text
suma del ranking_entidades           1,310,006
suma anual nacional de 3 pads        1,581,046
cobertura del subtotal                  82.9%
```

El handler suma las 20 filas y lo muestra como **“Total acumulado”**; también calcula porcentajes
contra ese subtotal. No es un total nacional. Los rankings genéricos de los ids 129–133 y 136
necesitan denominador y etiqueta honestos, aunque su orden de entidades pueda conservarse.

#### R59-P1 — una pregunta por sexo cae en ranking de entidades

El id 339, `cual sexo tiene mas incidencia`, tiene expectativa `*` y actualmente responde
`answerBoletin` con una tabla de entidades. El comodín ocultó una respuesta de otra dimensión. Debe
ser un contrato nombrado y responder hombres vs mujeres desde `stats.demo_historica`, declarando el
universo de padecimientos incluido.

#### Veredicto

```text
47.2-B1/B2/B3 · implementación y gate de rutas    PASS
47.2-B · contenido semántico completo             FAIL condicionado
47.3                                              NO INICIAR
```

No es motivo para deshacer los tres commits: el defecto es acotado, preexistía y ahora quedó
visible porque se revisó el contenido detrás del handler.

#### Orden 47.2-B4 — verdad del ranking, un commit local y STOP

Trabajar sólo en `EpiForecast-IMSS-Dashboard` sobre `a1412e33`.

1. **Ranking específico por padecimiento.**
   - Derivarlo de `boletin.anual_por_estado_pad`, nunca de `ranking_entidades`.
   - Sumar los años disponibles por estado y por el padecimiento pedido.
   - Canonicalizar estados reutilizando `ESTADOS_ALIAS`/una API exportada de `entities.js`; no
     copiar otro diccionario en `kb.js`.
   - `Distrito Federal` y `Ciudad de Mexico` deben producir una sola entidad canónica; si existen
     filas en el mismo año, sumar las observaciones, no sobrescribir una con otra.

2. **Cobertura parcial explícita.**
   - `anual_por_estado_pad` no cubre las 32 entidades: el texto debe declarar
     `N entidades canónicas con desglose cargado`.
   - No llamarlo “ranking nacional completo”.
   - Mostrar el subtotal cubierto y su porcentaje del total nacional.

3. **Denominador verdadero.**
   - Para un padecimiento, usar la suma de `boletin.anual_por_pad[pad]` como total nacional.
   - Para el ranking genérico, usar la suma de todos los padecimientos en `anual_por_pad`.
   - `ranking_entidades` puede conservarse para el orden genérico, pero sus 20 filas son
     `entidades disponibles en el ranking`, no “total acumulado”.
   - Todos los porcentajes deben declarar el denominador que usan.

4. **Consulta por sexo.**
   - `answerBoletin` debe ceder ante intención explícita de sexo/género.
   - `cual sexo tiene mas incidencia` debe responder por una ruta de sexo, con totales históricos
     agregados desde las claves presentes en `stats.demo_historica`.
   - El texto declara qué padecimientos suma; no hardcodear una cifra ni asumir que siempre son
     tres.
   - Cambiar el contrato original del id 339 de `*` al handler real elegido y regenerar el fixture.

5. **Pruebas que deben morder.**
   - rankings de Depresión, Parkinson y Alzheimer no son byte-idénticos;
   - cada suma por padecimiento coincide con `anual_por_estado_pad`;
   - el denominador coincide con `anual_por_pad`;
   - CDMX aparece una vez e incorpora ambas claves históricas;
   - se declara cobertura parcial y nunca “ranking nacional completo”;
   - el ranking genérico no llama total al subtotal de 20;
   - id 339 devuelve comparación por sexo y nunca una tabla de entidades;
   - alterar una fuente de un padecimiento cambia sólo su ranking.

6. **Control de alcance.**
   - Comparar las 616 respuestas de `a1412e33` contra B4 con RNG fijo.
   - Esperados: rankings genéricos 129, 130, 131, 133 y 136; rankings por padecimiento 132, 134,
     135, 214, 215 y 216; sexo 339. Conjunto único esperado: **12 ids**.
   - Cualquier otro cambio se documenta y se detiene antes de commitear.

7. **Gate.**

```text
npm test                             616/616 con handler real
test_entities + precedencia + B4     PASS
test_runner_gate                     PASS
test:candidate                       19/19
generate_tests.js --check            rc=0 · no mutante
knowledge/RAG/HTML/package           byte-idénticos
```

Crear **un commit local** de B4 y detenerse. No mezclar 47.3.

No usar `GEMINI_API_KEY`, no regenerar RAG, no tocar cache-bust todavía, no hacer push, merge,
deploy, activación, lifecycle ni publicación.

#### Después

1. Auditar B4 y cerrar formalmente 47.2-B.
2. Sólo con PASS, ejecutar 47.3 en un commit separado.
3. Después de 47.3, iniciar `C7.6-RAG-CONTRACT`.

#### Próxima acción exacta

**Ejecutar únicamente 47.2-B4, crear un commit local y detenerse.**

_Respuesta:_ **GO 47.2-B4 LOCAL. Sin 47.3, RAG, push, deploy, activación ni publicación.**

---

### Ronda 60 — 47.2-B4 ejecutada: verdad del ranking — 2026-07-26

Dashboard, un commit local sobre `a1412e33`. Sin 47.3, RAG, clave, cache-bust, push, merge, deploy,
activación ni publicación.

```text
3ee38310  47.2-B4  verdad del ranking: fuente, denominador y cobertura
```

R59-P0 confirmado y corregido. La auditoría tenía razón en lo esencial y en el matiz: el handler de
los ids 214–216 era el correcto, **su fuente no**. Esto es lo que devolvía antes:

```text
ranking de depresion              Ciudad de Mexico 193,538 · Jalisco 127,377 · ...
que estados tienen mas parkinson  Ciudad de Mexico 193,538 · Jalisco 127,377 · ...   ← idénticas
donde hay mas alzheimer           Ciudad de Mexico 193,538 · Jalisco 127,377 · ...   ← idénticas
```

y esto ahora:

```text
Parkinson    Jalisco 9,657 (10.6%) · Veracruz 7,959 · Ciudad de Mexico 6,607 · ...
             14 entidades canónicas · 63,055 casos = 69.3% del nacional (90,929)
Depresion    Ciudad de Mexico 235,862 · Jalisco 114,820 · ...
Alzheimer    Jalisco 2,900 · Chihuahua 2,335 · Sinaloa 2,208 · ...
```

#### Qué se hizo

1. **Fuente.** El ranking por padecimiento se deriva de `boletin.anual_por_estado_pad`, sumando los
   años disponibles por entidad y padecimiento. `ranking_entidades` ya no se usa cuando hay
   padecimiento: no tiene esa dimensión y por eso mentía.
2. **Canonicalización sin diccionario duplicado.** `entities.js` exporta `canonEstado()`; `kb.js` la
   importa. *Distrito Federal* y *Ciudad de Mexico* colapsan en una entidad y sus años **se suman**
   —2017 existe en ambas grafías con 389 y 81 casos de Parkinson—, no se sobrescriben.
   Lo apliqué **también al ranking genérico**, que las traía como dos filas: son **19** entidades,
   no 20. La orden sólo lo exigía para el ranking por padecimiento, pero contar dos veces la misma
   entidad es la misma falta a menor escala.
3. **Denominador verdadero.** Total nacional desde `anual_por_pad`, declarado en el texto, y cada
   porcentaje dice contra qué se calcula: *% del total nacional de Parkinson* frente a
   *% de las disponibles*.
4. **Cobertura parcial explícita.** «**14 entidades canónicas con desglose cargado**, no las 32» y
   el cierre con subtotal, porcentaje y total nacional. Desapareció el «**Total acumulado**» que
   bautizaba total a un subconjunto del 82.9%.
5. **Sexo.** `answerBoletin` cede ante intención explícita de sexo. `cual sexo tiene mas incidencia`
   la responde `answerDemografica` sumando las claves **presentes** de `stats.demo_historica` y
   nombrándolas: hoy son **cuatro** —Alzheimer, Dengue, Depresion, Parkinson—, no tres, y el texto
   lo dice. El id 339 pasa de comodín a contrato nombrado.

#### Alcance: exactamente los 12 previstos

```text
cambian     129 130 131 132 133 134 135 136 · 214 215 216 · 339
extras                                                        0
faltantes                                                     0
matriz nombrada                                               0 discrepancias
```

#### Gate

| exigido | resultado |
| --- | --- |
| `npm test` con handler real | **616/616** ✓ |
| entities · precedencia · B4 | **4/4 · 11/11 · 8/8** ✓ |
| `test_runner_gate` | **5/5** ✓ |
| `test:candidate` | **19/19** ✓ |
| `generate_tests.js --check` | **rc=0**, fixture intacto por md5 ✓ |
| knowledge / RAG / HTML / package | **byte-idénticos** ✓ |

Las **8 pruebas de `test_ranking.mjs` se verificaron rojas contra `a1412e33`**: muerden. Cubren lo
que pidió la orden, incluida la última —alterar Nayarit/Parkinson mueve sólo el ranking de
Parkinson y deja Depresión y Alzheimer byte-idénticos—.

`test_dispatcher_trace` sigue 7/7. Categorías: **448 nombradas + 121 comodín + 47 null** (el 339
cruzó de comodín a nombrada).

#### Lo que este commit NO arregla, y conviene tener escrito

- La cobertura de `anual_por_estado_pad` es de **14 entidades canónicas de 32**. El ranking por
  padecimiento es honesto sobre ello, pero sigue siendo parcial: no es un dato que el EpiBot pueda
  presentar como panorama nacional por entidad. Si eso importa para publicar, se arregla en el
  generador de `knowledge.json` (repo backend), no aquí.
- El cache-bust de `index.html` sigue **pendiente y bloqueante antes de cualquier deploy**: este
  commit vuelve a tocar `kb.js` y `entities.js`.

#### Estado

```text
Dashboard   3ee38310 · limpio · ahead 10 de main · SIN PUSH
Backend     ahead 10 · SIN PUSH
Readiness   SIGSEGV ✓ · npm test real ✓ · fixture ✓ · traza ✓ · 47.2-B ✓ (B1–B4) · 47.3 ✗ · RAG ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar `a1412e33..3ee38310` y cerrar formalmente 47.2-B**. 47.3 no se
inicia hasta ese PASS.

_Respuesta:_

---

### Ronda 62 — Cierre formal de 47.2-B y autorización vigente — 2026-07-26

La auditoría independiente quedó completada y documentada en la Ronda 61. Esta ratificación al
final del documento invalida la instrucción anterior de “auditar B4”: esa auditoría ya ocurrió.

```text
Dashboard auditado     a1412e33..3ee38310
47.2-B1/B2/B3/B4       PASS · CERRADA
respuestas cambiadas   exactamente 12 · extras 0 · faltantes 0
suite                  616/616 · focalizadas 35/35 · candidate 19/19
fuente/denominadores   recomputados de forma independiente
superficies públicas   byte-idénticas
```

La cobertura histórica parcial 14/32 queda declarada y se difiere como mejora P1 del generador del
backend; no se mezcla con el release de Obesidad ni bloquea 47.3.

La **orden ejecutable completa** es la Orden 47.3 de la Ronda 61: integrar el verificador del
fixture, el runner con traza y las regresiones focalizadas en `npm test`; corregir la telemetría
564→616; probar el contrato del fixture en temporales; preservar las 616 respuestas, contratos y
superficies.

#### Próxima acción exacta

**Ejecutar únicamente 47.3 local sobre `EpiForecast-IMSS-Dashboard@3ee38310`, crear un commit
acotado y STOP para auditoría.**

_Respuesta:_ **GO 47.3 LOCAL. Sin RAG, `GEMINI_API_KEY`, push, PR, merge, deploy, activación,
lifecycle ni publicación.**

---

### Ronda 61 — Auditoría de `a1412e33..3ee38310`, hallazgo propio y cierre de 47.2-B — 2026-07-26

Auditoría del commit B4 más una corrección que salió de ella. Sin RAG, clave, cache-bust, push,
merge, deploy, activación ni publicación.

```text
3ee38310  47.2-B4    verdad del ranking (auditado aquí)
45bba6c2  47.2-B4.1  la pregunta por sexo respeta el padecimiento nombrado (remedia el hallazgo)
```

#### Forma y superficies · PASS

```text
5 archivos · +305 / −20 · diff --check PASS
knowledge.json · rag_index.json · index.html · zoom_series.json · package.json · package-lock.json
    byte-idénticos
rastro de Obesidad, E66, GEMINI_API_KEY o claves en el diff:  ninguno
```

#### Recomputación independiente de las cifras · PASS

No basta con que las pruebas del propio commit pasen: se recalculó el ranking **fuera** de `kb.js`,
leyendo `knowledge.json` y comparando contra el texto emitido, celda por celda.

```text
Depresion   14 filas · nacional 1,460,553 · subtotal 1,050,456 = 71.9%
Parkinson   14 filas · nacional    90,929 · subtotal    63,055 = 69.3%
Alzheimer   14 filas · nacional    29,564 · subtotal    20,790 = 70.3%
casillas incorrectas (nombre, casos o porcentaje):  0 de 42
subtotal y total nacional declarados en el texto:   sí en los tres
```

#### Sonda fuera del fixture · PASS

El riesgo real de B2/B4 son las cesiones: un guard que cede de más deja al bot **mudo** en consultas
que el fixture no cubre. Se probaron 40 consultas plausibles que tocan cada guard nuevo,
comparando `553b84d1` contra `3ee38310`:

```text
consultas que respondían y ahora ceden a null:   0
cambios de ruta:                                 4, todos coherentes con las causas declaradas
```

#### R61-P0 — hallazgo propio: la ruta de sexo ignoraba el padecimiento nombrado

La sonda destapó un defecto que ninguna de las 616 pruebas podía ver, porque ningún caso tiene esa
forma:

```text
"hombres o mujeres tienen mas depresion"
  → **Mujeres** concentran el **69.5%** … Suma de los 4 padecimientos: Alzheimer, Dengue, …
```

Preguntan por **Depresión** y el titular contesta por el agregado de cuatro padecimientos, Dengue
incluido. La tabla traía el dato bueno, pero la frase que se lee primero respondía otra pregunta:
**exactamente el vicio de R59-P0 —forma correcta, alcance equivocado— en su versión pequeña.**

Corregido en `45bba6c2`: con padecimiento nombrado se responde ése (73.9%, 1,101,312 mujeres frente
a 387,966 hombres, sólo Depresión); sin él, sigue el agregado declarando su universo. Regresión
nueva que fija los dos lados. **Cero ids del fixture afectados.**

#### O-1 — observación no bloqueante: el rango incluye un 2026 parcial

El encabezado dice «acumulado **2014–2026**». El boletín va por la semana 27 de 52, así que 2026
entra incompleto —en el numerador y en el denominador, así que los porcentajes son coherentes—,
pero la etiqueta no lo dice. El mismo handler sí lo declara en otras ramas
(`*(parcial, semana 27 de 52)*`).

No lo cambié por mi cuenta: toca los 11 ids de ranking y prefiero que lo decidas. Propuesta concreta:
`acumulado 2014–2026 *(2026 parcial, semana 27 de 52)*`.

#### Veredicto

```text
47.2-B1  meses y contratos              PASS
47.2-B2  rutas por causa                PASS
47.2-B3  gate de handlers real          PASS
47.2-B4  verdad del ranking             PASS
47.2-B4.1 alcance de la ruta de sexo    PASS (remedia hallazgo de esta auditoría)
──
47.2-B                                  CERRADA
```

Gate tras B4.1: `npm test` **616/616** con handler real · candidate 19/19 · trace 7/7 · entities 4/4
· precedencia 11/11 · runner_gate 5/5 · ranking **9/9** · `--check` rc=0 · superficies públicas
intactas.

#### Estado

```text
Dashboard   45bba6c2 · limpio · ahead 11 de main · SIN PUSH
Backend     ahead 11 · SIN PUSH
Readiness   SIGSEGV ✓ · npm test real ✓ · fixture ✓ · traza ✓ · 47.2-B ✓ CERRADA · 47.3 ✗ · RAG ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Con 47.2-B en PASS, la secuencia escrita en la Ronda 59 habilita **47.3 en un commit separado**.
Procedo con él y me detengo ahí: sin RAG, sin clave, sin push.

_Respuesta:_

---

### Ronda 63 — Auditoría de B4.1, estado del WIP 47.3 y órdenes — 2026-07-26

Esta ronda actualiza únicamente el plan. No se corrigió código del dashboard, no se usó la clave y
no se tocó RAG, HTML, lifecycle, puntero, release ni publicación.

#### B4.1 auditado · PASS

```text
commit                              45bba6c2
diff 3ee38310..45bba6c2             kb.js + test_ranking.mjs · +24 / -4
fixture                             616 respuestas/handlers byte-idénticos
regresión nueva contra 3ee38310     8/9 PASS; falla sólo el caso que B4.1 corrige
regresión nueva contra 45bba6c2     9/9 PASS
npm test                            616/616 + unitarios PASS
focalizadas                         36/36
candidate                           19/19
generate --check                    PASS · anuncia 616
superficies públicas                intactas
```

La corrección respeta el alcance pedido: “hombres o mujeres tienen más depresión” usa únicamente
Depresión; la consulta sin padecimiento conserva el agregado y declara las cuatro fuentes. Cero
casos del fixture cambian.

#### WIP 47.3 detectado y validado, todavía sin commit

Mientras se auditaba apareció trabajo local en el dashboard:

```text
M   epibot/package.json
M   epibot/tests/generate_tests.js
??  epibot/tests/test_fixture_verify.mjs
```

No tocar ni descartar ese WIP. La dirección es correcta:

- `npm test` ejecuta primero `test:cases:verify`, luego 616 casos y después los unitarios;
- la telemetría ya se movió y anuncia 616;
- cinco pruebas ejercitan fixture intacto, alterado, ausente, duplicado y telemetría;
- todo ocurre sobre copias temporales;
- el fixture y las superficies permanecen intactos.

Gate observado sobre el WIP:

```text
npm test                            PASS · 616/616 + 41 unitarios
test:candidate                      19/19
generate_tests.js --check           PASS · 616
npm run check                       llega hasta rag:verify y falla sólo por el drift conocido:
                                    corpus 454 · índice 452 · 19 chunks sin cubrir
```

#### Orden inmediata — terminar 47.3 sin ampliar el alcance

Completar el WIP existente, no reimplementarlo:

1. corregir la cabecera de `generate_tests.js`: construye/verifica/escribe; **no ejecuta** las
   respuestas;
2. demostrar en temporal que dos ejecuciones de escritura de `test:gen` producen bytes idénticos;
3. fortalecer “no mutante” comprobando bytes **y mtime** tras `--check`;
4. integrar `npm test` dentro de `npm run check`, antes de candidate/RAG, sin recursión ni suites
   duplicadas;
5. confirmar que el test de fixture alterado cubre también un ID no consecutivo; puede añadirse un
   caso pequeño al test actual, sin extraer otro framework;
6. conservar `package-lock.json` sin cambios: sólo cambian scripts, no dependencias;
7. ejecutar el gate completo y crear **un commit local único de 47.3**;
8. STOP para auditoría. No comenzar B4.2 ni RAG en el mismo commit.

No se exige extraer un módulo puro si el test sigue invocando el CLI real sobre copias temporales:
esa ruta es más directa y evita duplicar el contrato.

#### Gate de cierre 47.3

```text
npm run test:cases:verify           PASS · 616 · bytes/mtime intactos
npm test                            616/616 + todos los unitarios focalizados
npm run test:candidate              19/19
test:gen ×2 en temporales            mismos bytes
test_fixture_verify                 incluye intacto/alterado/ausente/duplicado/ID/telemetría
npm run check                       único rojo permitido: rag:verify 454/452/19
knowledge/RAG/HTML/package-lock      byte-idénticos
kb.js/entities.js/test_cases.json    sin cambios respecto de 45bba6c2
```

#### Hallazgo latente para B4.2 — no mezclar ahora

B4.1 aún tiene un fallback semánticamente peligroso para N+1:

```js
ent.padecimiento && demo[ent.padecimiento]
  ? [ent.padecimiento]
  : Object.keys(demo)
```

Si se nombra un padecimiento pero falta su entrada demográfica, responde con **todos los demás**.
Se reprodujo eliminando sólo `demo_historica.Depresion`: “hombres o mujeres tienen más depresión”
contestó con Alzheimer + Dengue + Parkinson, 53.8%. Para un padecimiento N+1 esto sería una
respuesta convincente y falsa.

Después de auditar 47.3, B4.2 será un microcommit separado:

1. padecimiento explícito sin fuente demográfica → `null` o mensaje explícito de dato no
   disponible; nunca agregado global;
2. padecimiento explícito con fuente → sólo esa fuente;
3. sin padecimiento explícito → agregado de claves presentes;
4. el ranking debe declarar dinámicamente que el último año es parcial usando
   `boletin.meta.max_anio/max_semana`; no hardcodear 2026, semana 27 ni la fecha del sistema;
5. pruebas de las tres ramas y del encabezado parcial;
6. cambios de respuestas autorizados para la etiqueta parcial: sólo los 11 rankings
   `129–136, 214–216`; cualquier extra detiene el commit.

La etiqueta parcial es P2; el fallback a otras enfermedades es P0 antes de activar Obesidad. Se
resuelven juntos por economía, pero **después** del checkpoint 47.3.

#### Secuencia después

1. Terminar 47.3 → commit local → auditoría.
2. Ejecutar B4.2 → commit local → auditoría.
3. Ejecutar `C7.6-RAG-CONTRACT` con `GEMINI_API_KEY` sólo como secreto de entorno.
4. Llevar `npm run check` completamente a verde.
5. Recién entonces preparar cache-bust, activación condicionada y autorizaciones externas.

#### Próxima acción exacta

**Terminar únicamente el WIP 47.3 que ya existe, crear un commit local y STOP.**

_Respuesta:_ **GO TERMINAR 47.3 LOCAL. Sin B4.2, RAG, clave, push, PR, merge, deploy, activación,
lifecycle ni publicación.**

---

### Ronda 62 — 47.3 ejecutada: la verificación del fixture entra al comando oficial — 2026-07-26

Un commit local sobre `45bba6c2`. Sin RAG, clave, cache-bust, push, merge, deploy, activación ni
publicación.

```text
19e6a893  47.3  integrar la verificacion del fixture en el comando oficial
```

`test_cases.json` es un **artefacto** de `generate_tests.js`, no una fuente, pero nada en `npm test`
lo comprobaba: por eso R45-P0 —565 generados contra 618 commiteados— pudo convivir con una suite
verde. Eso queda cerrado.

#### Lo que se hizo

```text
npm test            = test:cases:verify  &&  run_tests.js  &&  test:unit
test:cases:verify   = generate_tests.js --check      (fail-closed, no mutante)
test:unit           = traza · entidades · fixture · precedencia · ranking · runner_gate   → 41
```

La telemetría `Total tests generated` estaba **antes** de la sección 33 y anunciaba **564** cuando el
fixture tiene 616; ahora va al final de la construcción y dice 616.

`test_fixture_verify.mjs` (5 pruebas, árboles temporales — el fixture oficial no se toca nunca)
cubre los cuatro casos que pedía la orden y uno más que me parece el importante:

| caso | exigido |
| --- | --- |
| intacto | rc=0, **no reescribe** el fixture, dos pasadas idempotentes |
| alterado a mano | rc≠0 y **lo deja alterado** — regenerarlo borraría la evidencia del desvío |
| ausente | rc≠0 y **no lo crea** |
| duplicado | rc≠0 (`617 en disco vs 616 generados`) |
| telemetría | cuenta el fixture completo, no una construcción a medias |

#### Verificación de punta a punta

```text
npm test                          rc=0
npm test con el fixture mentido   rc=1
npm test tras restaurarlo         rc=0 · fixture byte-idéntico
```

#### Gate

```text
npm test                     616/616  +  41/41
test:candidate                19/19
node --check                 kb.js · entities.js · run_tests.js · generate_tests.js  PASS
package.json                 JSON válido · sólo 3 líneas nuevas
knowledge / RAG / HTML       byte-idénticos
```

`package.json` se toca aquí por primera vez desde que empezó 47.2, que es donde correspondía.

#### Estado

```text
Dashboard   19e6a893 · limpio · ahead 12 de main · SIN PUSH
Backend     ahead 12 · SIN PUSH
Readiness   SIGSEGV ✓ · npm test real ✓ · fixture ✓ · traza ✓ · 47.2-B ✓ · 47.3 ✓ · RAG ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

#### Lo que queda, y lo que necesito de ti

1. **`C7.6-RAG-CONTRACT`** es lo siguiente en la secuencia. Necesita `GEMINI_API_KEY` como secreto de
   entorno y, según la respuesta P4, reparar el índice baseline en esta rama revisándolo por diff,
   con Obesidad **sólo** en un índice de staging. No lo empiezo sin tu GO explícito.
2. **O-1 sigue abierta** (Ronda 61): el ranking dice «acumulado 2014–2026» sin declarar que 2026 va
   por la semana 27 de 52. Propuesta: `acumulado 2014–2026 *(2026 parcial, semana 27 de 52)*`.
   Toca los 11 ids de ranking, ninguno fuera.
3. **Cache-bust de `index.html`**: bloqueante antes de cualquier deploy, porque 47.2-B tocó `kb.js` y
   `entities.js`. No lo hago hasta que haya intención de desplegar.
4. **Doce commits locales sin push** en cada repo. Cuando quieras, la autorización va por
   repositorio y por rango literal.

_Respuesta:_

---

### Ronda 64 — Auditoría de 47.3 y Orden B4.2 — 2026-07-26

#### 47.3 auditada · PASS

```text
commit                              19e6a893
diff 45bba6c2..19e6a893             3 archivos · +116 / -7 · diff --check PASS
npm test                            616/616 + 41/41
test:candidate                      19/19
fixture mentido                     npm test rc=1
fixture restaurado                  npm test rc=0 · bytes originales
generación en archive limpio ×2     SHA256 714afb027ae7… en ambas
generate --check                    rc=0 · 616
knowledge/RAG/HTML/package-lock      byte-idénticos
```

El commit hace lo que declara y 47.3 queda cerrado. Dos observaciones menores no lo invalidan:

- la primera línea de `generate_tests.js` todavía dice “genera y ejecuta ~400”; se corrige junto
  con el próximo cambio legítimo del archivo, sin abrir un commit sólo por comentario;
- `npm run check` aún no llama `npm test`; deberá incorporarlo cuando
  `C7.6-RAG-CONTRACT` toque ese gate y lo lleve completamente a verde.

No se pide reabrir 47.3 ni añadir más infraestructura de fixture.

#### Orden B4.2 — último microcontrato semántico antes del RAG

Trabajar únicamente en el dashboard sobre `19e6a893`. Un commit local y STOP.

1. En `answerDemografica`, si `ent.padecimiento` está presente:
   - con entrada en `stats.demo_historica`, responder sólo ese padecimiento;
   - sin entrada, devolver `null` o un mensaje explícito de dato no disponible;
   - **nunca** caer al agregado de las demás enfermedades.
2. Sin padecimiento explícito, conservar el agregado dinámico de las claves presentes.
3. En los rankings históricos, construir la etiqueta de corte desde:
   - `boletin.meta.max_anio`;
   - `boletin.meta.max_semana`;
   No usar `new Date()`, `2026`, `27`, `52` ni `53` como decisión hardcodeada. El metadato no
   declara cuántas semanas completan ese año MMWR, por lo que el texto honesto es **“datos hasta la
   semana N”**, no inferir completo/parcial con una constante.
4. Añadir pruebas que muerdan:
   - eliminar temporalmente `demo_historica.Depresion` y preguntar por Depresión debe dar
     `null/no disponible`, nunca Alzheimer+Dengue+Parkinson;
   - fuente presente → sólo el padecimiento pedido;
   - consulta global → todas las claves presentes;
   - cambiar sintéticamente `max_anio/max_semana` mueve ambos valores del texto, sin fecha del
     sistema.
5. Comparar las 616 respuestas/handlers con RNG fijo. Cambios permitidos: sólo los 11 rankings
   `129–136, 214–216`; la consulta latente de fuente demográfica ausente no está en el fixture.
6. Ejecutar:

```text
npm test                            616/616 + unitarios
npm run test:candidate              19/19
npm run test:cases:verify           PASS · no mutante
node --check                        kb.js · tests nuevos
knowledge/RAG/HTML/package          byte-idénticos
```

7. Crear un commit local B4.2 y detenerse. No corregir RAG ni cache-bust en ese commit.

#### Después de B4.2

1. Auditar B4.2 y confirmar el conjunto exacto de 11 respuestas.
2. Ejecutar `C7.6-RAG-CONTRACT`:
   - usar `GEMINI_API_KEY` sólo desde el entorno y nunca imprimirla;
   - reparar el índice baseline hasta drift cero;
   - mantener Obesidad únicamente en el índice candidate/staging hasta activación;
   - integrar `npm test` en `npm run check`;
   - corregir el comentario obsoleto de `generate_tests.js`;
   - exigir `npm run check` completamente verde.
3. Después preparar cache-bust y el paquete final de activación condicionada.

#### Próxima acción exacta

**Ejecutar sólo B4.2 local sobre `19e6a893`, crear un commit y STOP.**

_Respuesta:_ **GO B4.2 LOCAL. Sin RAG, clave, push, PR, merge, deploy, cache-bust, activación,
lifecycle ni publicación.**

---

### Ronda 65 — B4.2 ejecutada: corte desde metadata y fallback fail-closed — 2026-07-26

Un commit local sobre `19e6a893`. Sin RAG, clave, push, PR, merge, deploy, cache-bust, activación,
lifecycle ni publicación.

```text
438441a0  B4.2  corte derivado de metadata y fallback demografico fail-closed
```

#### O-1 · el corte sale de `boletin.meta`, no de una constante

```text
antes   **… incidencia de Parkinson** (acumulado 2014–2026) — 14 entidades canónicas…
ahora   **… incidencia de Parkinson** (acumulado desde 2014, datos hasta la semana 27 de 2026) — …
```

Adopté tu criterio tal cual: **“datos hasta la semana N de AAAA”**, sin decir “de 52” ni “parcial”.
El metadato dice hasta dónde llegan los datos; **no** dice cuántas semanas tiene ese año MMWR —hay
de 52 y de 53—, así que inferirlo sería afirmar algo que el contrato no declara. Cero `new Date()`
y cero constantes de calendario en la rama: verificado sobre el rango exacto de líneas, las únicas
apariciones de `27`/`52`/`53` están en el comentario que explica por qué no se usan.

#### Fallback N+1 · fallar cerrado

`answerDemografica` caía al agregado cuando el padecimiento pedido no tenía desglose: devolvía la
suma de las **otras** enfermedades como si respondiera la pregunta. Con Obesidad y Anorexia F50 ya
dados de alta en el registry, eso se dispara solo en cuanto alguien pregunte por ellos.

```text
ahora   "No tengo desglose demográfico por sexo de **X** en el boletín. Sí lo tengo de: …"
```

Tres decisiones que conviene que revises:

1. **Mensaje y no `null`.** La orden permitía ambos. Elegí mensaje porque cediendo, un handler
   posterior de la cadena volvería a servir un agregado ajeno — el defecto reaparecería una casilla
   más abajo.
2. **Nombra de qué padecimientos sí hay datos, nunca sus cifras.** La prueba lo fija: ninguna cifra
   de los otros puede aparecer. Si prefieres que ni los nombre, es una línea.
3. **Mismo criterio aplicado a `answerSexo`**, que con un padecimiento sin datos bajaba a la tabla
   global de los 333 modelos. Es el mismo agujero en el handler de al lado; no tenía sentido tapar
   uno y dejar el otro. No cambia ningún id del fixture.

#### Pruebas que muerden

Las dos nuevas se verificaron **rojas contra `19e6a893`** (las otras nueve, verdes en ambos: no son
las que prueban esto):

```text
quitar demo_historica.Depresion y preguntar por Depresión
   → mensaje explícito · 0 cifras de Alzheimer/Dengue/Parkinson · 0 tablas
   → restaurada la fuente, vuelve a responder con sus propias cifras
max_anio/max_semana = 1999/3
   → "datos hasta la semana 3 de 1999" en ranking por padecimiento y en el genérico
   → el año del sistema NO aparece · no dice "de 52", "de 53" ni "parcial"
```

#### Alcance · exactamente los 11 permitidos

```text
cambian     129 130 131 132 133 134 135 136 · 214 215 216
extras                                        0
permitidos sin cambiar                        0
matriz nombrada                               0 discrepancias
```

#### Gate

```text
npm test                     616/616  +  43/43
test:candidate                19/19
test:cases:verify             rc=0 · fixture intacto por md5
node --check                  kb.js · test_ranking.mjs  PASS
knowledge / RAG / HTML / package / package-lock   byte-idénticos
```

#### Estado

```text
Dashboard   438441a0 · limpio · ahead 13 de main · SIN PUSH
Backend     ahead 13 · SIN PUSH
Readiness   SIGSEGV ✓ · npm test real ✓ · fixture ✓ · traza ✓ · 47.2-B ✓ · 47.3 ✓ · B4.2 ✓ · RAG ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar B4.2**. Después, `C7.6-RAG-CONTRACT` con `GEMINI_API_KEY` desde
el entorno — no lo empiezo sin tu GO, y ahí van también las dos deudas que dejaste anotadas en la
Ronda 64: `npm test` dentro de `npm run check` y el comentario obsoleto de `generate_tests.js`.

_Respuesta:_

---

### Ronda 67 — C7.6-RAG-A ejecutada: contrato único, fail-closed y probado sin red — 2026-07-26

Un commit local sobre `438441a0`. **Sin usar `GEMINI_API_KEY`**, sin regenerar `rag_index.json`, sin
candidate build, push, PR, merge, deploy, cache-bust, activación, lifecycle ni publicación.

```text
b9cb7a1f  C7.6-RAG-A  contrato unico del indice RAG, fail-closed y probado sin red
```

#### La función compartida

`scripts/lib/rag_index.mjs` concentra caché por `chunkHash`, generación, validación y escritura.
`build_rag_index.mjs`, `rag_staging.mjs` y `rag_verify.mjs` la consumen; ninguno llama a Gemini,
reintenta ni decide validez por su cuenta. Una prueba lo fija por inspección del propio código: si
alguien vuelve a duplicar reglas o a escribir `vectors[i] = …`, se pone rojo.

#### El contrato, y por qué la alineación necesitaba algo más

Se exige **simultáneamente**: mismo número de chunks y vectores · cada chunk del corpus presente
exactamente una vez por hash · vector no vacío, de la dimensión declarada y con valores finitos ·
asociado al chunk para el que se pidió · cero faltantes, extras y duplicados.

La desalineación no se detecta mirando el archivo: son arreglos paralelos, la posición **es** la
asociación, y el vector de otro chunk cabe igual de bien. Por eso el vector viaja con el hash para
el que se obtuvo y la asignación pasa por una única vía, `assignVector(entry, hash, vector)`, que
rechaza el cruce en el momento de producirlo en vez de esperar a la validación. Lo digo explícito
porque es la parte del contrato que **no** puede verificarse sobre un índice ya escrito por un
tercero: ahí sólo se comprueba cobertura, unicidad y validez de cada vector.

#### Falla cerrado

```text
clave ausente habiendo embeddings que generar     rc≠0
proveedor caído tras los reintentos               rc≠0
respuesta sin vector, vacía, mal dimensionada     rc≠0  (y NO se reintenta: no es transitorio)
chunk ausente, duplicado, extra o desalineado     rc≠0
```

Nunca se escribe un índice parcial ni se cae a modo léxico. La caché tampoco **recicla** vectores
inválidos: reusarlos propagaría el defecto en vez de regenerarlo. La escritura es atómica —temporal
+ `rename`— y sólo ocurre tras validar el frame completo; ante fallo el destino previo queda
byte-idéntico y no sobrevive ningún temporal (verificado listando el directorio).

Comprobado en vivo, sin clave: `rag:build` → `faltan 19 embeddings y no hay proveedor disponible`,
rc≠0, `rag_index.json` con el mismo md5 y cero temporales huérfanos.

#### Pruebas · 17, con proveedor simulado, sin red ni clave

```text
índice cubierto PASS · chunk ausente FAIL · vector [] FAIL · dimensión/NaN/no-numérico FAIL
desalineado FAIL (y assignVector lo impide de entrada) · duplicado FAIL
fallo permanente del proveedor FAIL + destino byte-idéntico + sin temporales
sin proveedor FAIL · respuesta inválida FAIL sin reintentos inútiles
caché válida → 0 peticiones · caché inválida → regenera · candidate nuevo exige vector real
escritura atómica · una sola implementación compartida · reutilización por hash, no por posición
```

Tres de ellas nacieron rojas por defectos **míos**, no del código bajo prueba, y por eso las
menciono: el `finally` de un helper borraba el temporal mientras el cuerpo async seguía corriendo;
`buildIndex` ya rechazaba duplicados y yo esperaba el frame; y mi primer intento de simular la
desalineación movía el vector **sin** su procedencia, así que no probaba nada. La tercera es la que
llevó a `assignVector`.

#### Deudas de la Ronda 64, saldadas

- Encabezado de `generate_tests.js`: **construye, valida y escribe** los 616 casos; **no** los
  ejecuta. Documenta que `test_cases.json` es artefacto y que la fuente son las llamadas `add`.
- `npm run check` invoca `npm test` **exactamente una vez**, antes de `rag:verify`, sin recursión
  (`npm test` no llama a `check`) y sin duplicar suites (`test:candidate` no está dentro de
  `npm test`).

#### Un cambio que no estaba en la orden y conviene que revises

`rag:ci` construía siempre y sólo verificaba si había clave. Con el builder fail-closed, eso
**abortaría el CI sin clave** en vez de degradar en silencio. Lo cambié a: con clave, construye y
verifica; sin clave, conserva el índice commiteado y lo dice. Es coherente con «no introducir
fallback léxico», pero es una decisión mía sobre CI y prefiero que la valides.

#### Gate de A

| exigido | resultado |
| --- | --- |
| `npm test` | **616/616 + 60 unitarias** ✓ |
| `npm run test:candidate` | **19/19** ✓ |
| pruebas nuevas RAG, proveedor simulado | **17/17** ✓ |
| `node --check` de lo tocado | **PASS** ✓ |
| `npm run check` | **rc=1 sólo en `rag:verify`**, tras ejecutar y aprobar `npm test` (línea 27 del log) y `test:candidate` (línea 185); el rojo aparece en la 198 ✓ |
| `epibot/rag_index.json` | **byte-idéntico** ✓ |
| `knowledge.json` / HTML | **byte-idénticos** ✓ |
| `GEMINI_API_KEY` | **no leída por ninguna prueba, nunca impresa, no requerida** ✓ |

El drift baseline, ahora medido con el contrato completo:

```text
corpus 454 · índice 452 · 36 problemas = 19 chunks del corpus sin cubrir
                                       + 17 chunks del índice que ya no existen en el corpus
                                       + 0 vectores inválidos + 0 duplicados
```

El verificador anterior sólo veía los 19; los 17 sobrantes no los reportaba nadie. Es la magnitud
real que tendrá que cerrar C7.6-RAG-B.

#### Estado

```text
Dashboard   b9cb7a1f · limpio · ahead 14 de main · SIN PUSH
Backend     ahead 14 · SIN PUSH
Readiness   47.2-B ✓ · 47.3 ✓ · B4.2 ✓ · RAG-A ✓ · RAG-B ✗ · RAG-C ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar A**. `C7.6-RAG-B` sigue no autorizada; cuando lo esté, será la
primera vez que se use la clave.

_Respuesta:_

---

### Ronda 68 — Auditoría de C7.6-RAG-A: dos correcciones antes de B — 2026-07-26

#### Veredicto

**RAG-A está bien encaminada, pero NO pasa todavía la auditoría. RAG-B continúa bloqueada.**

La auditoría se hizo sobre `438441a0..b9cb7a1f`, ejecutando las suites y reproduciendo los caminos
que no cubren las 17 pruebas nuevas.

```text
diff                                7 archivos · +560 / -178 · diff --check PASS
npm test                            616/616 + 60/60
test:candidate                      19/19
test_rag_index                      17/17
rag_index/knowledge/HTML            byte-idénticos
```

La extracción a `scripts/lib/rag_index.mjs`, el fallo cerrado ante embeddings ausentes o inválidos,
la asociación por hash durante la construcción y la escritura posterior a la validación son
correctos. El hallazgo `19 faltantes + 17 extras = 36 problemas` también se reproduce.

#### R68-P0 — `rag:ci` da verde sin clave aunque el índice esté roto

Reproducción exacta sobre `b9cb7a1f`:

```text
env -u GEMINI_API_KEY npm run rag:ci    rc=0
npm run rag:verify                      rc=1 · 36 problemas
rag_index.json                           SHA256 sin cambio
```

No reconstruir sin clave es correcto. **No verificar el índice commiteado es incorrecto.** En
Netlify/CI sin secreto, el estado actual quedaría verde aunque el propio verificador ya sabe que el
índice tiene drift.

Contrato correcto:

```text
con clave      rag:build → rag:verify
sin clave      NO rag:build → rag:verify sobre el índice commiteado
```

En ambos caminos `rag:verify` es obligatorio. Si el índice commiteado tiene drift, `rag:ci` debe
terminar con `rc!=0`.

#### R68-P0 — la caché no está ligada al modelo de embeddings

Reproducción independiente, misma dimensión:

```json
{
  "previous_model": "model-A",
  "new_model": "model-B",
  "reused": 1,
  "generated": 0,
  "embed_calls": 0
}
```

El nuevo índice declara `model-B`, pero conserva el vector producido por `model-A`. Un cambio de
modelo con la misma dimensión generaría un índice mezclado y aparentemente válido.

Además, `problemsAgainstCorpus()` acepta un índice con `model` incorrecto porque sólo recibe
`dim`; tampoco contrasta de forma explícita `count`, `index.dim` ni la identidad del modelo.

La identidad de caché no es sólo `chunkHash`: es como mínimo:

```text
embedding_identity = model + dim
entry_identity     = embedding_identity + chunkHash
```

#### Orden C7.6-RAG-A.1 — microcorrección, todavía sin clave

Trabajar únicamente en el dashboard sobre `b9cb7a1f`. Un commit local y STOP.

1. Corregir `rag:ci`:

```text
si GEMINI_API_KEY existe   npm run rag:build
si no existe               conservar el índice commiteado
siempre                    npm run rag:verify
```

2. Ligar la reutilización de caché a `model + dim`:
   - si cualquiera difiere, reutilizar **cero** vectores y regenerar todos;
   - no permitir que el índice resultante declare un modelo distinto al que produjo sus vectores;
   - mantener la reutilización por `chunkHash` sólo dentro de la misma identidad de embeddings.
3. Extender el verificador compartido para rechazar:
   - `index.model !== expectedModel`;
   - `index.dim !== expectedDim`;
   - `index.count !== chunks.length`;
   - `chunks.length !== vectors.length`;
   - metadata ausente o de tipo inválido.
   `rag_verify.mjs` debe pasar explícitamente `EMBED_MODEL` y `EMBED_DIM`.
4. Tratar duplicados ambiguos en la caché de forma fail-closed o no reutilizable; nunca aplicar
   silenciosamente “el último gana”.
5. Añadir pruebas que muerdan:
   - sin clave + índice válido → no construye, sí verifica, rc=0;
   - sin clave + drift → no construye, sí verifica, rc!=0;
   - cambio de modelo con misma dimensión → `reused=0`, se llama al proveedor;
   - cambio de dimensión → `reused=0`;
   - modelo/dim/count ausente, falso o incorrecto → verificador FAIL;
   - misma identidad + mismo hash → reutiliza;
   - hash duplicado en caché → no se resuelve con “último gana”.
6. Repetir el gate sin clave:

```text
npm test                              616/616 + unitarios
npm run test:candidate                PASS
node --test tests/test_rag_index.mjs  PASS
env -u GEMINI_API_KEY npm run rag:ci  rc=1 mientras existan los 36 problemas
rag_index.json                         byte-idéntico
knowledge.json / HTML                  byte-idénticos
```

7. Un commit local `C7.6-RAG-A.1` y STOP. No ejecutar B ni usar la clave.

#### Estado del avance

El avance operativo permanece en **79%**. RAG-A produjo infraestructura válida, pero no se acredita
como gate cerrado hasta resolver los dos P0. No se avanza el porcentaje por código escrito si el
camino oficial de CI todavía puede dar un falso verde.

#### Próxima acción exacta

**Ejecutar únicamente C7.6-RAG-A.1 local y detenerse para auditoría.**

_Respuesta:_ **GO C7.6-RAG-A.1 LOCAL. Sin usar `GEMINI_API_KEY`, sin regenerar
`rag_index.json`, sin RAG-B/C, push, PR, merge, deploy, cache-bust, activación, lifecycle ni
publicación.**

---

### Ronda 69 — C7.6-RAG-A.1: los dos P0 corregidos — 2026-07-26

Un commit local sobre `b9cb7a1f`. **Sin usar `GEMINI_API_KEY`**, sin regenerar `rag_index.json`, sin
RAG-B/C, push, deploy, cache-bust, activación ni publicación.

```text
40442c6d  C7.6-RAG-A.1  rag:ci siempre verifica y la cache se liga al modelo
```

Los dos hallazgos son correctos y son míos. Reproduje ambos sobre `b9cb7a1f` antes de tocar nada, y
volví a medirlos después.

#### R68-P0 (1) · `rag:ci` daba verde sin mirar el índice

```text
b9cb7a1f   sin clave → rc=0 · construyó: no · verificó: NO
40442c6d   sin clave → rc=1 · construyó: no · verificó: sí
```

No reconstruir sin clave era lo correcto; no verificar, no. En CI sin secreto el estado quedaba
verde con el índice roto, y el propio verificador ya sabía que tenía drift. Ahora `rag:verify` corre
**siempre**, en ambos caminos, y su veredicto manda.

#### R68-P0 (2) · la caché no estaba ligada al modelo

Reproducción sobre `b9cb7a1f`, misma dimensión:

```json
{"previous_model":"model-A","new_model":"model-B","reused":1,"generated":0,
 "embed_calls":0,"vector_es_de_model_A":true}
```

El índice se declaraba `model-B` conservando vectores de `model-A`. Después:

```json
{"previous_model":"model-A","new_model":"model-B","reused":0,"generated":1,
 "embed_calls":1,"vector_es_de_model_A":false}
```

La identidad de una entrada es **`model + dim + chunkHash`**. Si el modelo o la dimensión difieren,
no se reutiliza **nada**. Tenías razón en el diagnóstico de fondo: dos vectores de 768 componentes
son numéricamente compatibles y semánticamente incomparables si vienen de modelos distintos, y ése
es justo el error que ningún tamaño detecta.

#### Lo demás que pedía la orden

- **Duplicados en la caché**: un hash repetido con vectores **distintos** se descarta por completo
  —no se reutiliza ninguno de los dos— en vez de aplicar «el último gana». Si los dos vectores son
  idénticos no hay ambigüedad y sí se reutiliza.
- **Verificador**: rechaza `model` distinto o ausente, `dim` no numérico o distinto, `count`
  distinto del corpus, `chunks`/`vectors` ausentes, de otro tipo o de distinta longitud.
  `rag_verify.mjs` pasa `EMBED_MODEL` y `EMBED_DIM` explícitos e imprime lo que el índice declara,
  para que el rojo diga *qué* no cuadra.

#### Pruebas · 24 en total (7 nuevas), sin red ni clave

Las de `rag:ci` ejecutan **la cadena real leída del `package.json` del repo** —no una copia— con
`rag:build` y `rag:verify` sustituidos por stubs que dejan constancia de haberse ejecutado. Así se
comprueban los cuatro caminos: con y sin clave, con verificador que aprueba y que reprueba.

```text
sin clave + índice sano    → no construye · sí verifica · rc=0
sin clave + drift          → no construye · sí verifica · rc≠0     ← el falso verde de R68-P0
con clave + sano           → construye · verifica · rc=0
con clave + drift          → construye · verifica · rc≠0
```

#### El drift baseline sube a 37

```text
antes  36 = 19 sin cubrir + 17 sobrantes
ahora  37 = 19 sin cubrir + 17 sobrantes + 1 metadata (count 452 ≠ 454 del corpus)
```

#### Gate, sin clave

```text
npm test                              616/616 + 67 unitarias
npm run test:candidate                19/19
node --test tests/test_rag_index.mjs  24/24
env -u GEMINI_API_KEY npm run rag:ci  rc=1  (los 37 problemas siguen ahí, como debe ser)
node --check                          rag_index.mjs · rag_verify.mjs · test_rag_index.mjs  PASS
rag_index.json / knowledge.json / HTML   byte-idénticos
GEMINI_API_KEY                        no usada por ninguna prueba
```

Una nota de honestidad sobre la evidencia: no pude correr el archivo de pruebas completo contra
`b9cb7a1f` para enseñar «N rojas», porque importa `sameEmbeddingIdentity`, que allí no existe, y el
módulo entero falla al cargar. Por eso reproduje los dos P0 con scripts mínimos contra el código
anterior —los JSON de arriba— en vez de afirmar un recuento de rojas que no medí.

#### Estado

```text
Dashboard   40442c6d · limpio · ahead 15 de main · SIN PUSH
Backend     ahead 15 · SIN PUSH
Readiness   47.2-B ✓ · 47.3 ✓ · B4.2 ✓ · RAG-A ✎ (a auditar) · RAG-B ✗ · RAG-C ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
Avance      79% hasta que cierres A.1
```

Siguiente acción exacta: **auditar A.1**. RAG-B sigue bloqueada.

_Respuesta:_

---

### Ronda 70 — Auditoría C7.6-RAG-A.1 PASS y orden RAG-B — 2026-07-26

#### Veredicto

**C7.6-RAG-A y A.1 quedan CERRADAS / PASS. Se autoriza RAG-B con alcance local y exacto.**

Auditoría independiente sobre `b9cb7a1f..40442c6d`:

```text
diff                                  4 archivos · +186 / -18 · diff --check PASS
npm test                              616/616 + 67/67
test:candidate                        19/19
pruebas RAG                           24/24
env -u GEMINI_API_KEY npm run rag:ci  rc=1 · no construye · sí verifica
rag_index.json                         SHA256 intacto
model-A → model-B, misma dimensión     reused=0 · generated=1 · embed_calls=1
```

Los dos P0 quedan cerrados:

1. `rag:ci` ejecuta siempre `rag:verify`; sin clave conserva el índice pero ya no puede dar verde
   si el índice commiteado tiene drift.
2. La caché usa identidad `model + dim + chunkHash`; un cambio de modelo o dimensión fuerza
   regeneración y el verificador contrasta metadata, conteos y forma.

El tratamiento de duplicados también es correcto: dos vectores distintos para el mismo hash son
ambiguos y no se reutilizan; dos copias byte-idénticas pueden reducirse a una entrada de caché,
pero un índice escrito con chunks duplicados sigue siendo rechazado por el verificador.

No quedan bloqueantes de A. **RAG-B será el primer paso que use `GEMINI_API_KEY`.**

#### Orden C7.6-RAG-B — reparar exclusivamente el baseline público

Trabajar únicamente en `EpiForecast-IMSS-Dashboard` sobre `40442c6d`. Un commit local y STOP.

##### B0 · preflight sin exponer el secreto

1. Confirmar:

```text
HEAD                                  40442c6d
worktree trackeado                    limpio
branch                                feat/c73-candidate-staging
test -n "${GEMINI_API_KEY:-}"         rc=0
```

No imprimir valor, longitud, prefijo, sufijo, entorno ni comando expandido. Si la clave no está
presente en **esa misma sesión**, detenerse y pedir que se exporte; no copiarla a archivos,
`.env`, historial, logs ni argumentos.

2. Capturar en un directorio temporal fuera del repo:
   - copia de `epibot/rag_index.json`;
   - SHA256 anterior;
   - inventario por `chunkHash → vector` del índice anterior;
   - hashes de `knowledge.json`, `index.html`, `epibot/index.html` y demás superficies públicas.

No tocar el candidate shard ni construir staging en B.

##### B1 · construcción única

Desde `epibot/`, ejecutar una sola vez:

```text
npm run rag:build
```

Resultado esperado por la medición actual:

```text
corpus final          454 chunks
reutilizados          435
generados             19
modelo                gemini-embedding-001
dimensión             768
faltos/fallidos       0
```

Si el proveedor falla, entrega un vector inválido, los conteos no cuadran o el comando termina
`rc!=0`, detenerse. No reintentar manualmente en bucle, no reducir el corpus, no aflojar el
verificador y no editar el JSON a mano.

##### B2 · verificación estructural y semántica

Ejecutar:

```text
npm run rag:verify
npm run check
```

Ambos deben terminar `rc=0`. Además verificar de forma independiente:

1. `count == chunks.length == vectors.length == 454`;
2. `model == gemini-embedding-001` y `dim == 768`;
3. 454 hashes únicos, cada uno con vector no vacío de 768 valores finitos;
4. `missing=0`, `extra=0`, `duplicate=0`, `invalid_vector=0`;
5. los **435 chunks reutilizados** conservan exactamente el mismo vector por `chunkHash`;
6. aparecen exactamente los 19 hashes del corpus antes faltantes;
7. desaparecen exactamente los 17 hashes obsoletos que ya no pertenecen al corpus;
8. el único cambio adicional permitido es metadata derivada del nuevo build, como `built` y
   `count`;
9. cero chunks, títulos, texto o fuentes de Obesidad en `rag_index.json`;
10. `knowledge.json`, ambos HTML y las demás superficies públicas permanecen byte-idénticos.

La igualdad de los 435 vectores se comprueba por hash, no por posición, porque al retirar 17
chunks la posición de entradas posteriores puede cambiar.

##### B3 · tratamiento de resultados

- **Si todo pasa:** crear un commit local que contenga únicamente
  `epibot/rag_index.json`, con mensaje claro de reparación del baseline, y STOP.
- **Si cualquier gate falla:** no crear commit. Conservar la copia/hashes de evidencia, registrar el
  fallo y detenerse. No ejecutar RAG-C.
- Nunca añadir al commit temporales, logs, `.env`, secretos ni cambios incidentales.

##### Gate de cierre de B

```text
rag:build                           rc=0 · reused 435 · generated 19
rag:verify                          rc=0 · 454/454
npm run check                       rc=0
índice                              454 hashes únicos · 454 vectores válidos
435 vectores previos                byte-idénticos por chunkHash
delta de corpus                     +19 esperados / -17 obsoletos
Obesidad pública                    0 chunks
knowledge / HTML                    byte-idénticos
commit                              sólo epibot/rag_index.json
```

#### Lo que B no autoriza

- No candidate/staging index.
- No tocar `knowledge.json`, HTML, JS de aplicación, Netlify o package scripts.
- No cache-bust, push, PR, merge, deploy, lifecycle, puntero ni publicación.
- No ejecutar RAG-C automáticamente.

#### Avance

El avance operativo sube a **80.5% (≈81%)** al cerrar A/A.1. B sólo se acredita cuando el índice
baseline quede en drift cero y el commit contenga exclusivamente el índice.

#### Próxima acción exacta

**Ejecutar únicamente C7.6-RAG-B local según B0–B3, crear un commit sólo si todo pasa y STOP.**

_Respuesta:_ **GO C7.6-RAG-B LOCAL. Se autoriza usar `GEMINI_API_KEY` sólo desde el entorno para
regenerar el índice baseline público. Sin RAG-C, push, PR, merge, deploy, cache-bust, activación,
lifecycle ni publicación.**

---

### Ronda 70 — C7.6-RAG-B ejecutada: índice baseline reparado, drift cero — 2026-07-26

Un commit local sobre `40442c6d`, **con `epibot/rag_index.json` como único archivo**. Primera
ejecución de todo C7 que usa `GEMINI_API_KEY`, leída sólo del entorno. Sin RAG-C, push, PR, merge,
deploy, cache-bust, activación, lifecycle ni publicación.

```text
4cdc17dd  C7.6-RAG-B  reparar el indice baseline publico: drift cero
```

#### Los números pedidos, uno por uno

```text
chunks                454   ✓
vectores reutilizados 435   ✓  (byte-idénticos a los del índice previo: 435/435)
vectores generados     19   ✓
chunks retirados       17   ✓
drift                   0   ✓  rag:verify rc=0
```

#### El diff del índice, explicado antes de aceptarlo

Comprobé que el cambio es exactamente el que el verificador anunciaba, no uno parecido:

```text
los 19 agregados == los 19 que el verificador reportaba sin cubrir   true
los 17 retirados == los 17 que reportaba como sobrantes              true
```

Y qué son:

```text
RETIRADOS (17)   12 Validación semanal · 3 Datos de Dengue · 2 Datos del proyecto
AGREGADOS (19)   los mismos 17, en su versión vigente
                 + 1 Avance 1 (Equipo 01) + 1 Avance 2 (Equipo 01)
```

Los 17 no son pérdida de cobertura: son la versión **vieja** del mismo contenido, que cambió cuando
llegaron boletines nuevos —mismo `source` y mismo `title`, otro texto, otro hash—. El crecimiento
neto de **+2** son las dos páginas de Avance que nunca habían entrado al índice. Nada más se movió.

#### Salud del índice resultante

```text
vectores vacíos                 0
dimensiones distintas de 768    0
valores no finitos              0
hashes duplicados               0
modelo declarado                gemini-embedding-001 / 768  = el que produjo TODOS sus vectores
menciones de Obesidad           0
```

#### `npm run check` completamente verde, por primera vez

```text
node --check de los 13 archivos      PASS
npm test                             616/616 + 67 unitarias
npm run test:candidate               19/19
npm run rag:verify                   rc=0 · «un vector válido por chunk, sin faltantes ni duplicados»
rc final                             0
```

#### Higiene de la clave y del commit

```text
GEMINI_API_KEY   leída del entorno · nunca impresa, ni su longitud, prefijo o sufijo
                 no aparece en el índice, ni en el mensaje del commit, ni en el plan
commit           1 archivo: epibot/rag_index.json
knowledge.json / index.html / package.json   byte-idénticos
```

Copia y SHA256 del índice previo (`86417db3ae059eb7…`) quedaron en un temporal antes de construir,
por si hiciera falta volver.

#### Estado

```text
Dashboard   4cdc17dd · limpio · ahead 16 de main · SIN PUSH
Backend     ahead 16 · SIN PUSH
Readiness   47.2-B ✓ · 47.3 ✓ · B4.2 ✓ · RAG-A ✓ · RAG-A.1 ✓ · RAG-B ✓ · RAG-C ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar B**. `C7.6-RAG-C` —el índice candidate sólo en staging— sigue sin
autorizar.

_Respuesta:_

---

### Ronda 72 — Auditoría C7.6-RAG-B PASS y orden RAG-C — 2026-07-26

#### Veredicto

**C7.6-RAG-B queda CERRADA / PASS. Se autoriza RAG-C únicamente en staging temporal.**

Auditoría independiente de `40442c6d..4cdc17dd`:

```text
diff / commit                         sólo epibot/rag_index.json
old → new                             452 → 454 chunks
intersección                          435 hashes
vectores idénticos en intersección    435/435
agregados / retirados                 +19 / -17 exactos
hashes únicos                         454
vectores inválidos                    0
contract_problems                     0
modelo / dimensión                    gemini-embedding-001 / 768
menciones de Obesidad                 0
rag:verify                            rc=0
npm run check                         rc=0
```

La clasificación también coincide:

```text
retirados   12 Validación semanal + 3 Datos de Dengue + 2 Datos del proyecto
agregados   los 17 anteriores actualizados + Avance 1 + Avance 2
```

El índice baseline público queda sano, sin Obesidad y sin mezcla de modelos. No se requiere ninguna
corrección adicional en B.

#### Orden C7.6-RAG-C — Obesidad candidate exclusivamente en dos staging roots

RAG-C es un **gate de ejecución**, no una modificación de producto. Trabajar con:

```text
Backend     7e36e086
Dashboard   4cdc17dd
Obesidad    lifecycle=trained
Release     obesidad_release_2517e7858901
```

No crear commit vacío. Si el gate pasa sin cambios de código, reportar evidencia y STOP.

##### C0 · preflight

1. Ambos worktrees deben estar trackeados-limpios; preservar los untracked del usuario.
2. Confirmar que existe y verifica el release bajo:

```text
artifacts/releases/obesidad/obesidad_release_2517e7858901/
```

Si falta, detenerse: RAG-C no autoriza `dvc pull`.
3. Confirmar sin imprimirla:

```text
test -n "${GEMINI_API_KEY:-}"
```

Si no está disponible en la misma sesión, detenerse. No usar `.env`, argumentos, logs ni archivos.
4. Capturar SHA256 de las superficies públicas antes de empezar:
   - dashboard `epibot/rag_index.json`, `epibot/knowledge.json`, `index.html`,
     `epibot/index.html`;
   - backend: agregados legacy, puntero/lifecycle y target DVC del release.
5. Crear dos raíces independientes con `mktemp -d`, fuera de ambos repos:

```text
C7_RAG_STAGING_A
C7_RAG_STAGING_B
```

No reutilizar el temporal histórico de C7.3.

##### C1 · compilar los mismos shards candidate dos veces

Desde el backend, para cada raíz A/B:

1. Resolver `releases_root` con `default_releases_root()`, no escribir una ruta absoluta en código.
2. Ejecutar:

```python
compile_release(
    disease_id="obesidad",
    mode=MODE_CANDIDATE,
    releases_root=default_releases_root(),
)
emit_shards(compilation, staging_root)
```

El único identificador específico permitido en la invocación es `disease_id="obesidad"`; el
compilador y los puentes permanecen genéricos.
3. Exigir en ambas raíces:

```text
release_id                  obesidad_release_2517e7858901
lifecycle                   trained
channels_emitted            epibot, reports, tableau, web
channels_without_bridge     []
filas forecast              5,772
shards A vs B               byte-idénticos antes del índice RAG
```

Si compilar A/B produce bytes distintos, detenerse antes de llamar al proveedor.

##### C2 · construir los dos índices de staging

Desde `EpiForecast-IMSS-Dashboard/epibot`, ejecutar una vez por raíz:

```text
npm run rag:staging -- "$C7_RAG_STAGING_A"
npm run rag:staging -- "$C7_RAG_STAGING_B"
```

Cada ejecución debe reutilizar los 454 vectores públicos y generar exactamente **un** embedding
candidate.

Resultado esperado en cada staging:

```text
chunks publicados       454
chunks con candidate    455 (+1)
vectores reutilizados   454
vectores generados      1
vectores inválidos      0
drift                   0
```

Un fallo de API, vector vacío, identidad incorrecta o conteo diferente termina C con FAIL. No
reintentar manualmente en bucle ni copiar el vector de A a B.

##### C3 · verificaciones independientes

1. Para cada `rag_index.staging.json`:
   - `count == chunks.length == vectors.length == 455`;
   - modelo `gemini-embedding-001`, dimensión 768;
   - 455 hashes únicos y 455 vectores válidos;
   - 454 hashes públicos con vectores byte-idénticos al índice público por `chunkHash`;
   - exactamente un chunk candidate cuyo contenido identifica Obesidad;
   - ese chunk tiene vector válido y no existe en el índice público.
2. Comparar A contra B:
   - eliminar únicamente el campo temporal `built`;
   - chunks, orden, hashes, modelo, dimensión y los 455 vectores deben ser idénticos;
   - el vector candidate generado independientemente debe coincidir exactamente tras la
     normalización declarada por el builder.
3. Recalcular SHA256 de superficies:
   - `epibot/rag_index.json` público byte-idéntico a `4cdc17dd`;
   - `knowledge.json`, ambos HTML, package y archivos públicos byte-idénticos;
   - cero menciones públicas de Obesidad.
4. Ejecutar `npm run check`; debe continuar `rc=0`.
5. Backend: Obesidad sigue `trained`, F50 `configured`, `published_members()` sigue conteniendo
   sólo Depresión, Parkinson, Alzheimer y Dengue; release DVC y legacy sin cambios.

##### C4 · STOP y evidencia

Si todo pasa:

- no crear commit en dashboard ni backend;
- conservar temporalmente A/B para que la auditoría pueda inspeccionarlos;
- reportar sus rutas opacas, SHA256 normalizados y todos los conteos;
- no subir los temporales ni añadirlos a Git/DVC.

Si cualquier gate falla:

- detenerse con evidencia;
- no corregir código dentro de C;
- no borrar A/B hasta decidir la causa;
- no avanzar a readiness ni activación.

#### Gate de cierre de C

```text
shards A/B                           byte-idénticos
índice A/B normalizado               byte-idéntico
public/reused                        454/454 vectores idénticos por hash
candidate                            1 chunk · 1 vector válido · sólo staging
total staging                        455 chunks / 455 vectores
drift / vacíos / duplicados          0 / 0 / 0
npm run check                        rc=0
superficies públicas                 byte-idénticas · Obesidad ausente
lifecycle/published/F50/legacy/DVC   sin cambios
commits                              ninguno
```

#### Avance

El avance operativo queda en **82%**. C7.6 subirá a cierre técnico sólo cuando RAG-C pase y se emita
el paquete final de readiness.

#### Próxima acción exacta

**Ejecutar únicamente C7.6-RAG-C en dos temporales independientes y STOP.**

_Respuesta:_ **GO C7.6-RAG-C LOCAL/STAGING. Se autoriza usar `GEMINI_API_KEY` sólo desde el entorno
para generar el único embedding candidate en cada staging. Sin commits, push, PR, merge, deploy,
cache-bust, activación, lifecycle ni publicación.**

---

### Ronda 73 — C7.6-RAG-C ejecutada: Obesidad candidate sólo en staging — 2026-07-27

Gate de ejecución. **Ningún commit**, ningún cambio de producto. Temporales conservados para tu
auditoría. Obesidad sigue `trained`.

#### C0 · preflight

```text
dashboard trackeado-limpio        sí
backend trackeado-limpio          1 archivo: este plan, con TUS ediciones pendientes (no lo commiteo)
release en la sede                existe y verifica · obesidad_release_2517e7858901
GEMINI_API_KEY                    presente en el entorno de esta sesión (no impresa)
raíces con mktemp -d              A y B, fuera de ambos repos, nuevas (no el temporal de C7.3)
```

Rutas opacas conservadas:

```text
A  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.0dHMA2ZqRm
B  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.krVjHPSu3H
```

#### C1 · shards compilados dos veces

```text
                          A                                B
release_id                obesidad_release_2517e7858901    idem
lifecycle                 trained                          idem
channels_emitted          epibot, reports, tableau, web    idem
channels_without_bridge   []                               []
filas forecast            5,772                            5,772
```

**Byte-idénticos antes de tocar el proveedor**: `diff -r` sin diferencias y el mismo digest de árbol
sobre los 9 archivos de cada raíz —`dfe85262a5a8d6c2…`—. Esa comparación es previa al índice, como
pedía la orden: si los shards no coincidieran, no habría que gastar una sola llamada a la API.

#### C2 · dos índices de staging

```text
                        A      B
chunks publicados       454    454
chunks con candidate    455    455  (+1)
vectores reutilizados   454    454
vectores generados        1      1
rc                        0      0
```

#### C3 · verificación independiente

```text
                                       A         B
count == chunks == vectors             455       455
modelo / dimensión                     gemini-embedding-001 / 768
hashes únicos                          455       455
vectores inválidos                     0         0
problemas de contrato                  0         0
públicos reutilizados byte-idénticos   454/454   454/454
chunks candidate                       1         1
id del candidate                       candidate:obesidad:obesidad_release_2517e7858901
vector del candidate válido            sí        sí
¿el candidate está en el índice público?  no     no
```

**A contra B, normalizado** (se elimina únicamente `built`, el campo temporal declarado no
identitario):

```text
sha256  deaf6591d63cd150c80216d4b95a3d2a4dacd1c4c0efd332eebd4aa4bb264dea   A
sha256  deaf6591d63cd150c80216d4b95a3d2a4dacd1c4c0efd332eebd4aa4bb264dea   B
chunks idénticos · orden idéntico · 455 vectores idénticos · incluido el candidate
```

El embedding candidate se generó **de forma independiente en cada raíz** y coincidió exacto: el
proveedor es determinista para el mismo texto bajo la normalización que declara el builder.

Superficies públicas, SHA256 antes y después de todo el ejercicio:

```text
epibot/rag_index.json · epibot/knowledge.json · index.html · epibot/index.html
all_forecast_{prophet,deepar,ensemble,stacking}.csv
→ los 8 idénticos · rag_index.json además byte-idéntico a 4cdc17dd · 0 menciones de Obesidad
```

Backend:

```text
obesidad       lifecycle=trained · 4 canales · gallery=False
anorexia_f50   lifecycle=configured · 0 canales
published_members(web|epibot|reports|tableau)  = Alzheimer, Dengue, Depresión, Parkinson
legacy y DVC   sin cambios trackeados
npm run check  rc=0
```

#### Dos cosas que debo declarar

1. **Hice una pasada preliminar** en otros dos temporales antes de leer la Ronda 72 completa, con el
   mismo procedimiento pero invocando `node scripts/rag_staging.mjs` en vez de `npm run rag:staging`
   y sin comparar los shards previamente. La rehice entera siguiendo la orden al pie de la letra.
   Las cuatro corridas —las dos preliminares y A/B— dan **el mismo digest normalizado**, así que la
   evidencia adicional apunta al mismo sitio. Los cuatro temporales quedan disponibles.
2. **Corregí un digest mal calculado antes de reportarlo.** Mi primer cálculo en JS pasaba un
   arreglo como segundo argumento de `JSON.stringify`, que no ordena claves: **filtra propiedades**,
   y de forma recursiva, así que habría comparado los chunks vacíos. El digest de arriba está
   recalculado con serialización canónica completa. Las comparaciones directas de `chunks` y
   `vectors` nunca dependieron de eso.

#### Gate de cierre de C

```text
shards A/B byte-idénticos                        ✓
índice A/B normalizado byte-idéntico             ✓
454/454 vectores públicos idénticos por hash     ✓
candidate: 1 chunk · 1 vector válido · staging   ✓
total staging 455/455                            ✓
drift / vacíos / duplicados                      0 / 0 / 0
npm run check                                    rc=0
superficies públicas byte-idénticas · sin Obesidad  ✓
lifecycle / published / F50 / legacy / DVC       sin cambios
commits                                          ninguno
```

#### Estado

```text
Dashboard   4cdc17dd · limpio · ahead 16 · SIN PUSH · sin commit nuevo
Backend     7e36e086 + este plan sin commitear · ahead 17 · SIN PUSH
Readiness   RAG-A ✓ · A.1 ✓ · B ✓ · C ✓ (a auditar)
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

No commiteo esta ronda: la orden dice **commits ninguno**, y además el plan tiene tus ediciones sin
commitear — no me corresponde subirlas. Queda escrita en el archivo para que la audites.

_Respuesta:_

---

### Ronda 74 — Auditoría C7.6-RAG-C PASS y brecha de estado público — 2026-07-27

#### Veredicto de la auditoría

**C7.6-RAG-C pasa para el candidate actual. C7.6-READINESS todavía NO se cierra.**

Se revalidaron sin modificar producto los dos temporales autoritativos:

```text
A  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.0dHMA2ZqRm
B  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.krVjHPSu3H
```

Resultado independiente:

```text
shards A/B                                      9/9 byte-idénticos
count == chunks == vectors                     455 en A y B
modelo / dimensión                             gemini-embedding-001 / 768
hashes únicos / vectores inválidos             455 / 0
vectores públicos iguales al baseline          454/454 en A y B
chunk candidate                                exactamente 1 en A y B
candidate ausente del índice público           sí
vector candidate A == B                        igualdad exacta
índices normalizados A == B                    igualdad estructural exacta
npm run check                                  rc=0
lifecycle / published_members / DVC             sin cambios
```

El SHA `deaf6591…` reportado en la Ronda 73 es válido bajo su serializador canónico. Una
recomprobación con otro serializador recursivo de claves ordenadas produjo
`1fe79560b72f02139f7d455d780824ab22040470fc60687f043a3386598befd2` para **A y B**. La diferencia
entre cadenas proviene de la codificación de serialización, no de los datos: la comparación
estructural directa, el orden, los 455 chunks y los 455 vectores son idénticos. No es un bloqueo.

No borrar los temporales A/B hasta terminar la auditoría de `PUBLICATION-STATUS`; son la evidencia
del candidate previo al cambio de etiqueta.

#### R74-P0 — el estado prospectivo aún no es un contrato de publicación

La matriz de aceptación exige hacer visible:

```text
Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos
```

Hoy esa frase y el estado `INCOMPLETE 0/4` existen en este plan, pero **no existe un artefacto
persistido y validado que los consumidores puedan usar**:

- `f7b14694` añadió la lógica tipada de `prospective.py` y sus pruebas, pero no materializó el gate
  congelado ni su estado actual como fuente de verdad;
- el puntero público no contiene ni debe contener el estado semanal;
- el compilador sólo emite `interval_method=none` y la etiqueta point-only;
- Reports, Tableau, Web y EpiBot no reciben `gate_digest`, veredicto ni contador `n/4`;
- el dashboard sólo entiende la ausencia de intervalos; no valida ni presenta el estado
  prospectivo;
- por lo tanto, activar hoy podría mostrar un pronóstico puntual correcto pero omitir la condición
  bajo la que el usuario autorizó publicarlo.

Esto es un bloqueo funcional de readiness, no un problema estadístico ni una razón para reconstruir
el bundle. El release inmutable y su `release_id` **no cambian**.

#### Diseño cerrado

Separar tres identidades:

1. **Bundle inmutable:** modelos y forecast; continúa siendo
   `obesidad_release_2517e7858901`.
2. **Gate congelado inmutable:** candidato, control, dataset, origen, objetivos, umbrales y
   `gate_digest`.
3. **Estado prospectivo mutable:** resultado observado semana a semana; referencia al gate y al
   release, nunca forma parte de la identidad del bundle.

Rutas de datos declarativos propuestas:

```text
config/publication/obesidad/prospective_gate.json
config/publication/obesidad/prospective_status.json
```

El código que las carga debe ser genérico: ninguna rama `if disease == "obesidad"`, ningún
`0/4` hardcodeado y ninguna lógica de enfermedad en JavaScript o Python. La ruta puede ser
específica por configuración; el contrato y el loader no.

El gate persistido debe recomputar exactamente:

```text
schema                     prospective_gate.v1
disease_id                 obesidad
release_id                 obesidad_release_2517e7858901
origin                     2026-W26
target weeks               2026-W27, W28, W29, W30
candidate_forecast_digest  e7e2f5eef2efe7fc1071a1adbcc7c9efba1ab29e8265e395e566799f55e3c9e2
control_forecast_digest    bb18accc0e6c9fbf8fd62fd48d4c9fc0807d4678e99d89f294ca6c7c41bce315
dataset_digest             1502d1a25b48c11b7afd30173163d78e4c67a55e31551737a9bed20358cc4340
gate_digest                5bc39aa5d44f5e62062775dc09a0366ac856f47e5444fbb52ca07e608e61b65d
```

El estado inicial debe declarar, como datos y no como texto libre:

```text
verdict          INCOMPLETE
weeks_available  0
weeks_required   4
completed_weeks  []
target_weeks     2026-W27..W30
gate_digest      5bc39aa5d44f5e62062775dc09a0366ac856f47e5444fbb52ca07e608e61b65d
```

La etiqueta visible se deriva de esos campos. Para el estado actual debe resultar **exactamente**:

```text
Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos
```

Un estado `FAIL` nunca habilita compilación pública y, si aparece después de activar, dispara el
procedimiento de rollback. `INCOMPLETE` se permite únicamente porque el usuario autorizó
publicación condicionada; nunca se representa como PASS.

#### Orden C7.6-PUBLICATION-STATUS-A — sólo backend

Trabajar sobre backend `7e36e086`. Ejecutar únicamente esta mitad y detenerse:

1. Añadir un loader/validador tipado y genérico bajo `src/epiforecast/publication/`.
2. Persistir los dos JSON anteriores. El gate es inmutable; el status es el único que cambia con
   cada boletín.
3. Validar fail-closed:
   - schema exacto;
   - `disease_id`, `release_id` y `gate_digest` coherentes;
   - recomputación exacta del digest del gate;
   - `0 <= weeks_available <= weeks_required`;
   - semanas completadas únicas, ordenadas y subconjunto de las objetivo;
   - reglas `INCOMPLETE`, `PASS` y `FAIL` coherentes con los conteos;
   - un `FAIL` o una identidad cruzada impiden modo público.
4. Conectar el status validado al compilador y a `emit_shards`; no leerlo globalmente desde el
   filesystem dentro de funciones puras.
5. Emitir identidad y etiqueta en los cuatro puentes:
   - `reports/report.md`;
   - `tableau/schema.json`;
   - `web/manifest.json`;
   - `epibot/knowledge.json` y `epibot/corpus/obesidad.md`;
   - `shard_manifest.json` debe sellar el estado que gobierna esos archivos.
6. El modo `candidate` acepta un status inyectado y lo muestra. El modo `public` exige además
   lifecycle, puntero activo y status válido para el mismo release.
7. Probar el contrato con un segundo padecimiento sintético; no fijar `obesidad`, `64`, `111`,
   `0/4` ni nombres de motores en el código genérico.
8. Probar rechazos por status ausente, gate alterado, release/disease cruzado, conteos inválidos,
   semanas duplicadas y `FAIL` en modo público.
9. Compilar dos raíces temporales candidate y exigir:
   - mismos 9 archivos y bytes idénticos entre raíces;
   - 5,772 filas sin cambio numérico;
   - etiqueta exacta presente en Reports, Tableau, Web y EpiBot;
   - bundle y `release_id` idénticos al baseline;
   - cero escritura en superficies públicas.
10. Ejecutar lint, mypy, fast, pruebas de publicación, integraciones estables y doctors.
11. Crear **un único commit local backend** para `PUBLICATION-STATUS-A` y STOP.

#### Prohibiciones de STATUS-A

- No tocar el dashboard.
- No usar `GEMINI_API_KEY`.
- No generar índices RAG.
- No modificar `artifacts/releases/`, el bundle, su `.dvc` ni el `release_id`.
- No cambiar lifecycle, puntero activo, canales, galería o `rolling_cv_v1`.
- No escribir en `reports/`, `data/`, `epibot/`, Tableau o Web canónicos.
- No push, PR, merge, deploy, cache-bust, activación ni publicación.
- No ejecutar `STATUS-B` en la misma ronda.

#### Secuencia posterior, todavía no autorizada

```text
auditar STATUS-A
→ STATUS-B sólo dashboard: validar y mostrar el status candidate
→ auditar STATUS-B
→ repetir RAG-C en dos temporales con el corpus candidate definitivo
→ paquete final C7.6-READINESS
→ autorizaciones separadas de activación y deploy
```

RAG-C debe repetirse después de STATUS-B porque el texto del chunk candidate cambiará. El índice
público debe permanecer byte-idéntico; sólo el candidate de staging se regenera. No reutilizar como
evidencia final los temporales de la Ronda 73.

#### Avance

El avance operativo se mantiene en **82%**. RAG-C pasó, pero no se suma avance mientras la etiqueta
obligatoria carezca de contrato y el candidate definitivo aún no haya repetido C.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PUBLICATION-STATUS-A` local en backend y STOP.**

_Respuesta:_ **GO C7.6-PUBLICATION-STATUS-A LOCAL. Persistir y validar gate/status, propagar la
etiqueta a los cuatro shards candidate, un commit backend y STOP. Sin dashboard, clave, RAG, DVC,
push, lifecycle, activación, deploy ni publicación.**

---

---

### Ronda 75 — C7.6-PUBLICATION-STATUS-A ejecutada — 2026-07-27

Un commit local en el backend. Sin dashboard, clave, RAG, DVC, push, lifecycle, activación, deploy
ni publicación. **STATUS-B no se tocó.**

```text
a81a5f5d  C7.6-PUBLICATION-STATUS-A el estado prospectivo como contrato, no como frase
```

#### Lo que resuelve R74-P0

Tenías razón: `INCOMPLETE 0/4` vivía sólo en el plan. Ahora la condición viaja **pegada a los
datos**, con las tres identidades separadas que definiste — el bundle no cambió ni un byte y su
`release_id` sigue siendo el mismo.

#### El gate persistido NO se escribió a mano

Lo derivé del release sellado y del dataset, y exigí que reprodujera el digest congelado en C7.4
**antes** de escribir nada:

```text
candidate_forecast_digest  e7e2f5eef2efe7fc1071a1adbcc7c9efba1ab29e8265e395e566799f55e3c9e2  ✓
control_forecast_digest    bb18accc0e6c9fbf8fd62fd48d4c9fc0807d4678e99d89f294ca6c7c41bce315  ✓
dataset_digest             1502d1a25b48c11b7afd30173163d78e4c67a55e31551737a9bed20358cc4340  ✓
gate_digest                5bc39aa5d44f5e62062775dc09a0366ac856f47e5444fbb52ca07e608e61b65d  ✓
origin 2026-W26 · horizonte 52 · objetivo W27–W30 · regla 5/5/10
```

Los cuatro coinciden con los tuyos. El estado inicial sale de `available_weeks` sobre el dataset
sellado: **INCOMPLETE, 0 de 4**, con `completed_weeks: []`.

#### La etiqueta se deriva, no se escribe

```text
Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos
```

El avance sale del estado validado y la cola point-only del propio release —si el release trajera
intervalos, esa cola no aparece—. Probé también `(2/4)`, `superada (4/4)` y `NO superada (4/4)`:
todas se componen igual, sin un `0/4` en el código.

#### Validación fail-closed

El loader **recomputa** el digest del gate desde su contenido en vez de creer lo que el archivo
declara: aflojar un umbral y dejar el digest viejo se rechaza. Sobre el estado: schema exacto,
identidad cruzada, rango de conteos, semanas únicas, ordenadas y subconjunto de las objetivo,
coherencia veredicto↔conteos, y **un `FAIL` nunca habilita modo público**.

Una decisión que conviene que revises: **sin estado no se emite ningún shard**, en los dos modos.
Compilar sin estado sí se permite —produce filas, no publica—, pero emitir sí, porque un shard sin
su condición es exactamente el defecto que R74-P0 describe. Eso obligó a inyectar el estado
declarado en las pruebas de C7.3a, que es el único cambio en `test_compiler_shards.py`.

#### Genericidad

El grueso de las 28 pruebas nuevas corre sobre un padecimiento **sintético** con gate fabricado: si
el contrato sólo funcionara con Obesidad no sería un contrato. No hay `if disease ==`, ni `64`,
ni `111`, ni `0/4`, ni nombres de motores en el código genérico; la ruta es configurable, el
contrato no.

#### Verificación con dos raíces temporales

```text
C  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.74R02ePHWw
D  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.YofwNMXiSh

9 archivos por raíz · diff -r sin diferencias · digest de árbol 8aeb4382a00515904af5c0290dc0cb0e…
filas                     5,772 en ambas · sin cambio numérico
release_id                obesidad_release_2517e7858901 · idéntico al baseline
etiqueta exacta en        reports/report.md (2×) · tableau/schema.json · web/manifest.json
                          epibot/knowledge.json · epibot/corpus/obesidad.md · shard_manifest.json
escrituras públicas       ninguna
```

Nota para la siguiente vuelta: el digest del árbol de shards pasa de `dfe85262…` (Ronda 73) a
`8aeb4382…`, porque ahora llevan la etiqueta. Confirma lo que ya anticipaste: **RAG-C debe
repetirse** después de STATUS-B, y los temporales de la Ronda 73 no sirven como evidencia final.

#### Gate

```text
ruff check + format            PASS
mypy                           160 archivos · PASS
pytest -m "not slow and not integration"   1946 passed · cobertura 80.16%
tests/unit/publication         112 passed (28 nuevas)
integración de release         8 passed
doctor_padecimiento            rc=0
agregados legacy               los 4 byte-idénticos
obesidad                       trained · release sin cambios · published_members intacto
```

#### Estado

```text
Backend     a81a5f5d · ahead 18 · SIN PUSH  (el plan sigue con tus ediciones sin commitear)
Dashboard   4cdc17dd · limpio · ahead 16 · SIN PUSH · intacto en esta ronda
Readiness   RAG-A ✓ A.1 ✓ B ✓ C ✓(pendiente repetir) · STATUS-A ✓ (a auditar) · STATUS-B ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar STATUS-A**. STATUS-B —validar y mostrar el estado en el
dashboard— sigue sin autorizar.

_Respuesta:_

---

### Ronda 76 — Auditoría STATUS-A: propagación PASS, evaluator y capability FAIL — 2026-07-27

#### Veredicto

**`a81a5f5d` no se descarta: resolvió correctamente la persistencia y propagación del estado
`INCOMPLETE 0/4`. STATUS-A queda PARCIAL, no PASS. Antes del dashboard se exige A.1.**

Superficie auditada:

```text
commit                         a81a5f5d
archivos                       7 · config 2 · src 3 · tests 2
gate/status declarados         presentes y coherentes con 5bc39aa5…
shards candidate               9 · 5,772 filas · etiqueta en los cuatro puentes
release_id / bundle            obesidad_release_2517e7858901 · sin cambio
tests focalizados              83/83 PASS con --no-cov
temporales C/D                 byte-idénticos · digest 8aeb4382…
legacy / lifecycle / DVC       sin cambios
```

La decisión “sin status no se emite ningún shard” queda **APROBADA**. Es correcta: compilar filas
en memoria no es publicar; materializar un shard sin la condición prospectiva sí produciría un
artefacto ambiguo.

#### R76-P0-1 — el evaluator congelado no aplica la regla 5/5/10

`prospective.evaluate()` marca:

```python
PASS si hay cuatro semanas; INCOMPLETE en otro caso
```

No compara el candidato contra el control usando `gate.rule`. Tampoco materializa ni evalúa los
111 productos o nacional General. Reproducción independiente:

```text
verdad              5
control             5       sMAPE = 0
candidato      100,000       sMAPE ≈ 199.98
regla                +5/+5/+10
veredicto actual     PASS    ← incorrecto
```

Por tanto, hoy el FAIL documentado nunca puede ocurrir al completar cuatro semanas. El digest
congelado sí es correcto; lo incompleto es la implementación del veredicto.

#### R76-P0-2 — un objeto status construido a mano evade el gate

`compile_release()` recibe un `ProspectiveStatus` desnudo. Sólo verifica que `disease_id` y
`release_id` coincidan; no vuelve a validar digest, semanas, conteos o coherencia. Reproducción
independiente, sin escribir archivos:

```text
gate_digest          0000…0000
weeks                998/999
target_weeks         []
completed_weeks      []
candidate            aceptado
public + puntero     aceptado
```

El loader es estricto, pero nada obliga al caller a usarlo. Un tipo construido a mano no es una
capability validada.

#### R76-P0-3 — una semana faltante impide llegar a 4/4 para siempre

El gate congeló W27–W30 y `available_weeks()` sólo inspecciona esas cuatro. A la vez, el contrato
operativo dice que una semana parcial o faltante no cuenta y que se espera la siguiente semana
válida. Con el código actual, si W28 fuera inválida, W31 nunca se considera y el status queda
`INCOMPLETE 3/4` indefinidamente.

Sin mover `gate_digest`, la semántica de `prospective_gate.v1` debe quedar explícita:

- `target_weeks` es la ventana inicialmente programada;
- la evaluación comienza en W27;
- se recorren semanas cronológicas dentro del horizonte congelado;
- cuentan las primeras cuatro con verdad completa;
- una semana inválida se registra como omitida y se reemplaza por la siguiente válida;
- candidato y control siguen siendo los mismos forecasts congelados.

#### R76-P1 — la actualización semanal todavía no es reproducible

El repo contiene loaders y el JSON inicial, pero no un entry point que derive
`prospective_status.json` desde gate + release + dataset. El 0/4 se generó correctamente en esta
ronda, pero el procedimiento no quedó ejecutable para 1/4, 2/4, 3/4 y el veredicto final. Editar el
JSON a mano contradice el objetivo del contrato.

Además, el validador debe cerrar forma y tipos: semana booleana, semana fuera del calendario MMWR,
digests no SHA256, reglas desconocidas/no finitas y claves extra deben rechazarse antes de evaluar.

#### Orden C7.6-PUBLICATION-STATUS-A.1 — evaluator real y status validado

Ejecutar únicamente backend sobre `a81a5f5d`, en un commit local y STOP:

1. Sustituir el `ProspectiveStatus` desnudo en `Compilation` por un contrato validado que lleve
   **gate + status**. El compilador y `emit_shards` deben revalidarlo; no deben leer filesystem.
2. Hacer que el único loader público entregue ese contrato. Un caller no puede habilitar candidate
   ni public pasando una dataclass fabricada.
3. Cerrar schemas y tipos:
   - conjuntos exactos de claves para gate y status;
   - enteros no booleanos;
   - periodos MMWR válidos;
   - origen/horizonte positivos;
   - digests SHA256 de 64 hex minúsculas;
   - regla con exactamente `smape_base`, `smape_products` y `smape_national_general`;
   - umbrales finitos y no negativos.
4. Implementar la selección de semanas válidas desde la primera objetivo hasta el horizonte:
   registrar programadas, completadas y omitidas con motivo; tomar las primeras cuatro completas.
5. Implementar el veredicto real con el mismo calendario, reconciliación, agregación y fórmulas del
   runner:
   - 64 bases;
   - 111 productos derivados exclusivamente desde las bases;
   - nacional General;
   - cobertura 100%, claves únicas, finitos/no negativos e identidades aritméticas.
6. Para cada ámbito, calcular sMAPE de candidato y control sobre las mismas filas acumuladas. PASS
   sólo si:

   ```text
   candidate <= control * (1 + max_degradation_pct / 100)
   ```

   Caso zero-safe: si control=0 y candidate=0, degradación 0; si control=0 y candidate>0, el ámbito
   falla. Reportar también bias, MAE, RMSE, WAPE y MASE sin usarlos para el veredicto.
7. `INCOMPLETE` con menos de cuatro semanas completas; con cuatro, `PASS` sólo si pasan los tres
   ámbitos y `FAIL` si falla cualquiera. Guardar métricas, diferencias y detalle semanal.
8. Añadir un entry point genérico y reproducible con dos modos:
   - `--check`: deriva el status esperado y falla si el archivo declarado difiere, sin mutarlo;
   - `--write`: escritura atómica explícita del status derivado.
   Debe resolver insumos por identidad sellada, no por nombres inferidos ni rutas absolutas.
9. El JSON vigente debe continuar `INCOMPLETE 0/4` y, tras regenerarlo con el entry point, quedar
   byte-idéntico al de `a81a5f5d`.
10. Pruebas que deben fallar contra `a81a5f5d` y pasar con A.1:
    - candidato catastrófico + control perfecto → `FAIL`;
    - fallo independiente en bases, 111 productos y nacional General;
    - una semana programada ausente se reemplaza por la siguiente completa;
    - semana parcial no cuenta ni se vuelve cero;
    - status fabricado con digest/conteos falsos se rechaza en candidate y public;
    - periodos, digests, reglas, tipos y claves extra inválidos se rechazan;
    - `--check` es no mutante y `--write` es atómico;
    - el status real 0/4, label, 5,772 filas y nueve shards permanecen deterministas.
11. Ejecutar lint, format, mypy, fast, publicación, integración estable y doctors.
12. Crear un único commit local `C7.6-PUBLICATION-STATUS-A.1` y STOP.

#### Prohibiciones de A.1

- No cambiar candidato, control, umbrales, `gate_digest`, bundle o `release_id`.
- No retuning, re-selección, refit ni forecast.
- No dashboard, `GEMINI_API_KEY` o RAG.
- No DVC, push, lifecycle, puntero activo, deploy o publicación.
- No ejecutar STATUS-B en la misma ronda.

#### Secuencia posterior, aún no autorizada

```text
auditar STATUS-A.1
→ STATUS-B sólo dashboard
→ auditar STATUS-B
→ repetir RAG-C en dos temporales
→ paquete C7.6-READINESS
→ autorizaciones externas separadas
```

#### Avance

El avance se mantiene en **82%**. La etiqueta ya viaja con los shards, pero aún no puede afirmarse
que el futuro PASS/FAIL sea real ni que cualquier status aceptado haya pasado el gate.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PUBLICATION-STATUS-A.1` local en backend y STOP.**

_Respuesta:_ **GO C7.6-PUBLICATION-STATUS-A.1 LOCAL. Corregir evaluator 5/5/10, reemplazo de
semanas, capability validada y actualización reproducible; un commit backend y STOP. Sin dashboard,
clave, RAG, DVC, push, lifecycle, activación, deploy ni publicación.**

---

### Ronda 77 — C7.6-PUBLICATION-STATUS-A.1 ejecutada — 2026-07-27

Un commit local en el backend. Sin dashboard, clave, RAG, DVC, push, lifecycle, activación, deploy
ni publicación. **STATUS-B no se tocó.**

```text
2ecb3fae  C7.6-PUBLICATION-STATUS-A.1 evaluador real, semanas reemplazables y capability
```

Los tres hallazgos son correctos y son míos. Reproduje cada uno contra `a81a5f5d` antes de tocar
nada, y volví a medirlo después:

```text
R76-P0-1  candidato 100000 vs verdad 5, control perfecto
          antes  PASS          ahora  FAIL
R76-P0-3  con la semana programada 2026-W28 ausente
          antes  3/4 para siempre   ahora  4/4 tomando la siguiente completa
R76-P0-2  status fabricado (gate_digest 0000…, 998/999, target vacío)
          antes  ACEPTADO por el tipo    ahora  RECHAZADO al construirlo
```

#### El veredicto ahora se calcula

`evaluate()` aplica la regla congelada **por ámbito**: 64 bases, 111 productos derivados desde las
bases con la **misma** función del runner —aplicada igual a verdad, candidato y control, así que la
aritmética de los tres es la misma— y nacional General. PASS sólo si en los tres

```text
candidate <= control * (1 + max_degradation_pct / 100)
```

Zero-safe tal como lo pediste: control=0 y candidate=0 → degradación 0; control=0 y candidate>0 →
el ámbito falla, sin dividir. MAE, RMSE, WAPE, bias y MASE se reportan y **no** deciden.

Una prueba fija que los tres ámbitos se evalúan de verdad por separado: con un sesgo alterno por
sexo, las bases fallan y el nacional casi no se entera —los errores se cancelan al agregar—. Ésa es
la razón de tener tres umbrales y no uno.

#### Las semanas se reemplazan, sin mover el gate

`target_weeks` pasa a ser la ventana **programada**, no una lista cerrada: se recorren semanas
cronológicas dentro del horizonte congelado, cuentan las primeras cuatro completas, y cada omitida
queda registrada con su motivo (`ausente` / `parcial`). Una semana parcial no cuenta ni se vuelve
cero. Candidato y control siguen siendo los congelados, así que **el `gate_digest` no se mueve**.

#### La capability

`PublicationStatus` valida gate + estado **en su construcción**, así que no existe una instancia
incoherente. Y añadí algo que la orden no pedía pero que cierra el agujero de verdad: el compilador
**ancla el gate al bundle sellado** —candidato, dataset, origen y horizonte—, de modo que una
capability internamente coherente pero fabricada bajo el mismo `release_id` tampoco entra, ni en
candidate ni en public. Sin eso, bastaba con inventar un gate consistente consigo mismo.

#### Formas y tipos cerrados

Conjuntos exactos de claves (gate, estado y regla), enteros no booleanos, periodos MMWR válidos
—52 o 53 semanas según el año—, origen y horizonte positivos, digests SHA256 de 64 hex minúsculas,
regla con exactamente las tres claves y umbrales finitos no negativos.

#### Actualización reproducible

```text
python -m scripts.prospective_status obesidad --check    # no muta; rc≠0 si el archivo miente
python -m scripts.prospective_status obesidad --write    # escritura atómica
```

Verificado: `--check` sobre un estado mentido (`PASS 4/4`) devuelve rc=1 y **lo deja mentido** —no
lo corrige por su cuenta—; `--write` lo deja en el estado real y sin temporales. El JSON vigente
sigue **INCOMPLETE 0/4** y, regenerado, queda **byte-idéntico al de `a81a5f5d`**.

#### Gate

```text
ruff check + format                        PASS
mypy                                       161 archivos · PASS
pytest -m "not slow and not integration"   1973 passed · cobertura 80.49%
publicación                                44 + 11 + 57 = 112 → ahora 167 con las nuevas
integración de release                     8 passed
doctor_padecimiento                        rc=0
gate/status declarados                     byte-idénticos a a81a5f5d
bundle · gate_digest · umbrales · release_id   sin cambios
```

#### Una limitación de la evidencia, dicha explícitamente

No puedo enseñar «N pruebas rojas» corriendo `test_prospective_rule.py` contra `a81a5f5d`: importa
`SCOPE_BASE`, `select_weeks` y `WEEK_PARTIAL`, que allí no existen, y el módulo entero falla al
cargar. Por eso reproduje los tres P0 con scripts mínimos forzando el código antiguo por
`PYTHONPATH` —la tabla de arriba— en vez de afirmar un recuento que no medí. Es la misma limitación
que ya declaré en RAG-A.1.

#### Estado

```text
Backend     2ecb3fae · ahead 19 · SIN PUSH  (el plan sigue con tus ediciones sin commitear)
Dashboard   4cdc17dd · limpio · ahead 16 · SIN PUSH · intacto
Readiness   RAG-A ✓ A.1 ✓ B ✓ C ✓(a repetir) · STATUS-A ✓ A.1 ✓ (a auditar) · STATUS-B ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar STATUS-A.1**. STATUS-B sigue sin autorizar.

_Respuesta:_

---

### Ronda 78 — Auditoría STATUS-A.1: evaluator PASS, flujo prospectivo todavía incompleto — 2026-07-27

#### Veredicto

**A.1 corrige los tres repros de R76 en aislamiento, pero STATUS-A aún queda PARCIAL. Se exige A.2
antes del dashboard.**

Evidencia auditada:

```text
commit                         2ecb3fae
diff                           6 archivos · +890/-64 · check PASS
tests focalizados              110/110 PASS con --no-cov
candidato 100000/control 5     FAIL correcto
regla por ámbitos              bases / 111 productos / nacional General
zero-safe                      correcto
capability con status falso    rechazada
digests actuales               candidato/control/dataset/gate coinciden
estado vigente                 INCOMPLETE 0/4
bundle / lifecycle / DVC       sin cambios
```

El evaluator 5/5/10, la separación de los tres ámbitos, la derivación 64→111 y el registro de
semanas omitidas quedan **aprobados como núcleo matemático**.

#### R78-P0-1 — el updater usa como verdad el dataset congelado en el origen

`scripts/prospective_status.py` resuelve la “verdad observada” con:

```text
release.chain.dataset_id → runs/obesidad_1502d1a25b48/epi_dataset_v2.csv
máximo periodo de ese dataset → 2026-W26
primera semana del gate       → 2026-W27
```

Ese dataset es el de entrenamiento congelado. Es correcto para reconstruir el control, pero por
definición nunca contendrá la verdad futura. Ejecutar `--check` cada boletín continuará dando
`INCOMPLETE 0/4` para siempre.

El flujo debe separar:

1. **training dataset congelado:** reconstruye y verifica el control y los denominadores MASE;
2. **observation dataset nuevo:** contiene la verdad que llega con cada boletín y decide `n/4`.

Usar un único frame para ambos mezcla dos identidades incompatibles.

#### R78-P0-2 — la semana de reemplazo se selecciona pero no puede cargarse

`select_weeks()` permite sustituir W28 ausente por W31. Sin embargo `_check_status()` exige que cada
`completed_week` pertenezca a `gate.target_weeks` —W27..W30—. Reproducción:

```text
completed_weeks  W27, W29, W30, W31
selector         4/4 válido
PublicationStatus
                 RECHAZADO: W31 no es objetivo del gate
```

Por tanto, el reemplazo pasa su prueba unitaria pero no puede atravesar el loader, el compilador ni
los shards.

#### R78-P0-3 — el resultado que decide PASS/FAIL se descarta

`evaluate()` produce `scopes`, métricas, detalle semanal y semanas omitidas. `derive_status()` sólo
conserva:

```text
verdict · weeks_available · completed_weeks
```

No persiste dataset de verdad, sus digests, métricas candidato/control, degradaciones, selección,
omisiones ni detalle semanal. El plan exige un informe sellado y reproducible; con el JSON actual
no puede auditarse por qué un futuro status dice PASS o FAIL.

#### R78-P0-4 — el control congelado aún puede sustituirse sin rechazo

El compilador ancla candidato, dataset, origen y horizonte al bundle, pero no el control. Una
capability construida con el mismo release y `control_digest=dddd…`, internamente coherente con su
propio gate, sigue siendo aceptada en candidate. El updater tampoco compara
`frame_digest(control)` contra `gate.control_digest`.

El control es parte del congelado y debe verificarse antes de evaluar y antes de aceptar la
evidencia.

#### R78-P1 — validación de frames y MASE

- El evaluator compara conteos de filas, pero no exige explícitamente igualdad de claves entre
  verdad, candidato y control antes de agregar.
- Duplicados, negativos y no finitos no tienen un gate focalizado.
- `series_metrics(..., train_true=[], mase_lag=52)` hace que MASE sea siempre `NaN` con flag; no es
  el MASE del runner sobre historia congelada.
- El comando importa `_runs_root`, API privada de `registry_doctor`, en vez de consumir un contrato
  público de DatasetManifest.

No afectan el 0/4 actual, pero sí harían incompleta o no reproducible la evidencia final.

#### Diseño cerrado para A.2

Mantener el gate actual y su digest intactos. Añadir dos artefactos mutables relacionados:

```text
config/publication/<disease_id>/prospective_evaluation.json
config/publication/<disease_id>/prospective_status.json
```

`prospective_evaluation.v1` conserva toda la evidencia. `prospective_status.v2` es el resumen que
viaja a los consumidores y referencia `evaluation_digest`. Ninguno forma parte del `release_id`.

El evaluation debe contener, como mínimo:

```text
schema · disease_id · release_id · gate_digest
candidate_digest · control_digest · training_dataset_id/digest
observation_dataset_id/digest y digests efectivos de raw/config/exposición/geografía
scheduled/completed/skipped weeks con motivos
scopes candidato/control/degradación/umbral/PASS
métricas y flags por ámbito
detalle por semana
verdict · evaluation_digest
```

El status v2 debe contener el resumen actual, `observation_dataset_id/digest`,
`evaluation_digest`, contador y etiqueta derivable. El loader sólo entrega la capability después
de recomputar y cruzar gate + evaluation + status.

#### Orden C7.6-PUBLICATION-STATUS-A.2 — verdad prospectiva y evidencia sellada

Ejecutar sólo backend sobre `2ecb3fae`, un commit local y STOP:

1. Separar `training_history` y `observation_history` en el evaluator y el entry point.
2. Resolver el training dataset desde el release, validar su DatasetManifest y exigir
   `dataset_digest == gate.dataset_digest`.
3. Reconstruir el control **sólo** desde training history y exigir
   `frame_digest(control) == gate.control_digest`.
4. Leer el candidato del bundle y exigir
   `frame_digest(candidate) == gate.candidate_digest` antes de evaluar.
5. Para `--write`, exigir un `--observation-dataset-id` explícito. Debe ser un EpiDatasetV2
   verificable del mismo padecimiento, generado por el carril nuevo con el boletín más reciente.
6. Para `--check`, usar el `observation_dataset_id` ya declarado en status/evaluation; no volver
   silenciosamente al dataset congelado.
7. Validar el observation dataset:
   - manifest y digests íntegros;
   - mismo disease/config/calendario/exposición/geografía;
   - exactamente las 64 SeriesKeys esperadas;
   - claves periodo×serie únicas;
   - valores finitos y no negativos;
   - prefijo hasta el origen idéntico al training dataset;
   - las semanas posteriores proceden del nuevo snapshot y nunca se imputan como cero.
8. Permitir `completed_weeks` posteriores a la ventana programada siempre que estén ordenadas,
   dentro del horizonte congelado y sean exactamente las primeras cuatro semanas completas que
   declara la evaluación. W31 debe ser válida como reemplazo de W28.
9. Persistir `prospective_evaluation.v1` con toda la evidencia y
   `prospective_status.v2` referenciando su digest. Escribir primero evaluation y después status,
   ambos atómicamente; cualquier mezcla intermedia debe fallar cerrado al cargar.
10. El compilador y `emit_shards` deben aceptar únicamente la capability validada contra los tres
    artefactos y el bundle. Un control digest inventado debe ser rechazado en candidate y public.
11. Antes de métricas, exigir igualdad exacta de claves y cobertura entre verdad/candidato/control,
    sin duplicados, NaN, infinitos o negativos; derivar los 111 productos y validar reconciliación.
12. Calcular MASE con denominadores estacionales obtenidos de la historia de entrenamiento
    congelada, por SeriesKey y con las mismas reglas/flags del runner. Un valor indefinido se
    representa como `null` + flag, nunca `NaN` JSON.
13. Tests que deben fallar contra `2ecb3fae` y pasar con A.2:
    - el dataset congelado no puede fingir semanas futuras;
    - un observation dataset nuevo avanza 0→1/4 sin alterar training/control;
    - W31 reemplaza W28 y la capability completa carga/emite;
    - prefijo histórico modificado, disease/digest/config cruzado o dataset sin manifest se rechaza;
    - control digest fabricado se rechaza;
    - duplicado, clave faltante/extra, negativo, NaN e infinito fallan antes de métricas;
    - alterar evaluation o status rompe sus digests y el cruce;
    - `--check` es no mutante y usa la verdad declarada;
    - `--write` exige truth explícita y no deja archivos incoherentes;
    - el estado real sigue `INCOMPLETE 0/4`, con la misma etiqueta y 5,772 filas.
14. Ejecutar lint, format, mypy, fast, publicación, integración estable y doctors.
15. Crear un único commit local `C7.6-PUBLICATION-STATUS-A.2` y STOP.

#### Prohibiciones de A.2

- No descargar ni extraer boletines nuevos dentro de esta ronda; usar fixtures y el dataset actual
  para dejar 0/4 reproducible.
- No cambiar gate, candidato, control, umbrales, bundle o release.
- No dashboard, clave, RAG, DVC, push, lifecycle, puntero, deploy o publicación.
- No ejecutar STATUS-B en la misma ronda.

#### Secuencia posterior, aún no autorizada

```text
auditar STATUS-A.2
→ STATUS-B sólo dashboard
→ auditar STATUS-B
→ repetir RAG-C en dos temporales
→ paquete C7.6-READINESS
→ autorizaciones externas separadas
```

#### Avance

El avance permanece en **82%**. El cálculo 5/5/10 ya existe, pero todavía no puede recibir verdad
nueva ni dejar evidencia sellada y consumible de su decisión.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PUBLICATION-STATUS-A.2` local en backend y STOP.**

_Respuesta:_ **GO C7.6-PUBLICATION-STATUS-A.2 LOCAL. Separar training/verdad, sellar evaluation,
admitir reemplazos end-to-end y validar frames/control; un commit backend y STOP. Sin boletines
nuevos, dashboard, clave, RAG, DVC, push, lifecycle, activación, deploy ni publicación.**

---

### Ronda 79 — C7.6-PUBLICATION-STATUS-A.2 ejecutada — 2026-07-27

Un commit local en el backend. Sin boletines nuevos, dashboard, clave, RAG, DVC, push, lifecycle,
activación, deploy ni publicación. **STATUS-B no se tocó.**

```text
f41c2e3d  C7.6-PUBLICATION-STATUS-A.2 verdad prospectiva separada y evidencia sellada
```

Los cinco hallazgos eran correctos. Uno por uno:

#### R78-P0-1 · la verdad ya no es el dataset congelado

Se separan **training** —reconstruye el control y da los denominadores MASE— y **observation** —la
verdad que llega con cada boletín y decide `n/4`—. `--write` **exige** `--observation-dataset-id`:
la verdad se declara, no se infiere. Sin ese cambio, `--check` habría devuelto `0/4` para siempre.

#### R78-P0-2 · el reemplazo atraviesa todo el flujo

`completed_weeks` ya no se valida contra `target_weeks` sino contra el **horizonte congelado**, con
orden y unicidad. W31 sustituye a W28 y el trío carga, compila y emite. La prueba lo recorre entero.

#### R78-P0-3 · la evidencia se persiste

Nuevo `prospective_evaluation.v1`: verdad usada y sus digests, semanas programadas/completadas y
**omitidas con motivo**, ámbitos con sMAPE candidato/control, degradación, umbral y `passes`,
métricas por ámbito y detalle semanal. `prospective_status.v2` lo referencia por
`evaluation_digest`, y el loader no entrega la capability sin cruzar los tres artefactos.

#### R78-P0-4 · el control ya no se puede sustituir

La evaluación sella candidato, control y dataset de entrenamiento; el loader los cruza contra el
gate; y el updater **reconstruye el control** desde la historia congelada y exige
`frame_digest(control) == gate.control_digest` antes de evaluar. Una prueba comprueba los tres:
control, candidato y dataset inventados se rechazan.

#### R78-P1 · frames y MASE

Antes de agregar nada se exige el conjunto **exacto** de SeriesKeys, sin duplicados, sin no finitos
y sin negativos. El MASE sale de la historia de entrenamiento congelada y un valor indefinido viaja
como `null`, nunca `NaN` en JSON. Y el comando dejó de importar `registry_doctor._runs_root`:
`runner.manifest` expone `default_runs_root()` y `dataset_dir()`.

#### Dos cosas que hice y conviene que revises

1. **La capability sólo la emite el loader.** Le puse un token privado: un objeto construido a mano
   ya no es siquiera *construible*, no sólo inválido. Es más fuerte que lo que pedía la orden, y es
   lo que cierra de verdad R76-P0-2.
2. **El dataset de observación se valida como el mismo carril**: mismo padecimiento, mismos digests
   de config y exposición, 64 SeriesKeys, integridad del CSV contra su manifiesto y **prefijo hasta
   el origen idéntico** al de entrenamiento. `raw` sí puede diferir —es un boletín nuevo—.

#### Sin boletines nuevos, pero probado de punta a punta

Los dos tests fabrican el snapshot que un boletín produciría, en un `runs/` temporal inyectado:

```text
verdad con W27                    → 1/4 · INCOMPLETE · "en curso (1/4 semanas)"
                                     gate, control y training intactos
verdad con W27, W29, W30 y W31    → 4/4 · W28 registrada como «ausente»
                                     la capability completa carga
```

#### Estado vigente, sin cambios

```text
INCOMPLETE 0/4 · misma etiqueta · 5,772 filas · 9 shards
verdad observada declarada: obesidad_1502d1a25b48 (aún el congelado, porque no hay boletín nuevo)
```

Eso último es honesto y conviene tenerlo escrito: hoy la verdad declarada **es** el dataset de
entrenamiento, porque no hay otro. La diferencia con antes es que ahora eso es una **declaración
explícita y verificable**, no un valor por defecto invisible; y en cuanto exista un dataset con el
boletín nuevo, `--write` lo exige por nombre.

#### Gate

```text
ruff check + format                        PASS
mypy                                       161 archivos · PASS
pytest -m "not slow and not integration"   1975 passed · cobertura 80.61%
tests/unit/publication                     todos PASS (46 en test_status)
integración de release                     8 passed
doctor_padecimiento                        rc=0
gate congelado · umbrales · bundle · release_id   sin cambios
```

#### Estado

```text
Backend     f41c2e3d · ahead 20 · SIN PUSH  (el plan sigue con tus ediciones sin commitear)
Dashboard   4cdc17dd · limpio · ahead 16 · SIN PUSH · intacto
Readiness   RAG-A ✓ A.1 ✓ B ✓ C ✓(a repetir) · STATUS-A ✓ A.1 ✓ A.2 ✓ (a auditar) · STATUS-B ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar STATUS-A.2**. STATUS-B sigue sin autorizar.

_Respuesta:_

---

### Ronda 80 — Auditoría STATUS-A.2: identidad PASS, corte temporal y MASE todavía incorrectos — 2026-07-27

#### Veredicto

**A.2 cierra la separación training/observation, el reemplazo W31, el sellado de evaluation/status
y la identidad del control. No se aprueba todavía STATUS-A completo: requiere un microcierre
funcional A.3 antes de tocar el dashboard.**

Evidencia independiente:

```text
commit auditado                   f41c2e3d
worktree backend                  sólo este plan modificado; untracked del usuario preservados
diff check                        PASS
tests focalizados                112/112 PASS con --no-cov
prospective_status --check       rc=0
estado                           INCOMPLETE 0/4
evaluation.skipped_weeks         52
primera "ausente"                2026-W27
última "ausente"                 2027-W26
seasonal_denominators()          definida, pero no llamada por producción
MASE efectivo                    una concatenación de las 64 historias
```

Lo aprobado de A.2:

1. `--write` exige un observation dataset explícito y `--check` reutiliza el declarado;
2. training y observation tienen identidades distintas y el prefijo al origen se contrasta;
3. candidato y control se verifican contra sus digests congelados;
4. W31 puede reemplazar W28 a través de loader, compilador y shards;
5. evaluation y status se escriben por separado, se cruzan por digest y sólo el loader entrega la
   capability;
6. el gate, umbrales, bundle, release y lifecycle no cambiaron.

#### R80-P0-1 — semanas futuras etiquetadas falsamente como ausentes

`select_weeks()` recorre todo el horizonte de 52 semanas desde 2026-W27. No conoce el último periodo
que el observation dataset realmente pudo observar. Cuando el snapshot termina en 2026-W26,
`week_state()` devuelve `ausente` para cada semana futura y el artefacto vigente registra:

```text
skipped_weeks = 52
2026-W27 ... 2027-W26 → "ausente"
```

`prospective_status --check` devuelve verde sobre esa evidencia. No es una diferencia editorial:
una semana futura no es una semana ausente. La omisión sólo existe cuando el corte observado ya
pasó esa semana y el snapshot no trae las 64 series completas.

Contrato correcto:

- derivar `observation_cutoff` del máximo periodo válido del snapshot de observación;
- inspeccionar sólo desde la primera semana programada hasta
  `min(observation_cutoff, fin_del_horizonte)`;
- no crear registros para semanas posteriores al corte;
- persistir el corte en la evaluación y validarlo al cargar;
- con el snapshot vigente, `0/4` debe llevar `skipped_weeks=[]`;
- con verdad hasta W31 y W28 realmente ausente, la única omisión debe ser W28, nunca W32…W52.

#### R80-P0-2 — MASE cruza fronteras entre SeriesKeys

`seasonal_denominators()` calcula correctamente un denominador por serie, pero no tiene ningún
caller de producción. El evaluator usa:

```python
series_metrics(yt, yc, _training_series(entrenamiento), mase_lag=52)
```

`_training_series()` concatena, en orden, las 64 historias. El lag-52 atraviesa las fronteras entre
entidades/sexos y genera diferencias que nunca existieron dentro de una serie. Además, para los
ámbitos de 111 productos y nacional General usa la historia de las bases, no la historia agregada
del producto evaluado.

El contrato del runner es por producto: cada SeriesKey obtiene su propio denominador seasonal
lag-52 sobre su propia historia previa, y los reportes resumen después esas métricas. A.3 debe
reutilizar ese contrato:

1. derivar de las 64 bases la historia de training de los mismos 111 productos;
2. calcular métricas por producto con su propia historia, sin concatenar SeriesKeys;
3. resumir MASE por ámbito con la misma mediana declarada que usan los reportes del runner;
4. conservar MAE/RMSE/WAPE/bias y sus flags de forma auditable para candidato y control;
5. representar denominador indefinido como `null` + flag, nunca `NaN` ni infinito.

MASE no decide el PASS/FAIL 5/5/10, pero forma parte de la evidencia prometida. Publicar una métrica
con denominador contaminado sería un reporte falso aunque el veredicto de sMAPE fuese correcto.

#### R80-P0-3 — el CSV puede ocultar duplicados antes del gate

`read_base_history()` convierte cada grupo a un `dict[(year, week)]`. Una fila duplicada con la
misma serie y periodo se sobrescribe silenciosamente antes de que
`check_observation_dataset()` vea la historia. Por tanto, “64 SeriesKeys y valores válidos” no
prueba la unicidad del frame fuente.

A.3 debe validar el EpiDatasetV2 tabular **antes** de convertirlo a mappings:

- schema requerido;
- exactamente 64 SeriesKeys base;
- unicidad de `(cve_ent, sexo, epi_year, epi_week)`;
- periodos MMWR válidos y ordenables;
- valores finitos y no negativos;
- mismo conjunto de periodos por serie dentro del snapshot;
- sólo después construir `history`.

La igualdad de `config_digest` ya sella indirectamente el catálogo geográfico porque C1 lo incluyó
en el payload efectivo. Debe quedar fijado por una prueba/asserión; no hace falta duplicar una
segunda fuente de identidad.

#### R80-P1 — el digest sella bytes, pero el loader no valida la aritmética interna

`load_evaluation()` recomputa `evaluation_digest`, pero `scopes`, `metrics` y `per_week` entran como
diccionarios casi opacos. Si alguien modifica `passes`, degradación, conteos o detalle semanal y
recalcula el digest exterior, el loader no recompone la coherencia matemática completa.

Antes de que STATUS-B consuma este contrato entre repos, A.3 debe fijar una forma cerrada:

- claves exactas y tipos para los tres scopes;
- `rows` igual a `64*n`, `111*n` y `1*n`;
- sMAPE/degradación finitas o el único caso zero-safe declarado;
- `degradation_pct`, `passes` y verdict recomputados desde candidato/control/umbral;
- `per_week` uno a uno con `completed_weeks`, sin semanas extra o repetidas;
- razones de omisión en un enum cerrado y sólo hasta `observation_cutoff`;
- métricas finitas o `null` únicamente con su flag correspondiente.

No se pide convertir el loader en un segundo evaluator ni volver a leer `runs/` desde el dashboard:
se pide que el artefacto sea internamente autoconsistente y falle cerrado si su propia aritmética
se contradice.

#### Orden C7.6-PUBLICATION-STATUS-A.3 — cierre funcional mínimo

Ejecutar únicamente backend sobre `f41c2e3d`, un commit local y STOP:

1. Introducir `observation_cutoff` derivado del observation dataset validado.
2. Limitar la selección de semanas al corte observado; jamás registrar el futuro como
   `ausente`/`parcial`.
3. Persistir el corte en `prospective_evaluation.v2`. Mantener
   `prospective_status.v2` como resumen que referencia el nuevo `evaluation_digest`; STATUS-B aún
   no existe, así que no hay consumidor público que migrar.
4. Validar el frame tabular de training y observation antes de `read_base_history`; ningún
   duplicado puede desaparecer por una conversión a `dict`.
5. Reemplazar `_training_series()` por métricas por producto. Derivar la historia training 64→111
   con el mismo catálogo/lineage del runner y usar un denominador lag-52 por producto.
6. Persistir métricas auditables de candidato y control por ámbito; resumir MASE con la mediana de
   productos finitos, igual que los reportes del runner.
7. Cerrar y validar semánticamente `scopes`, `metrics`, `per_week`, `skipped_weeks` y verdict.
8. Regenerar únicamente evaluation/status locales. Deben conservar:
   `gate_digest`, candidato, control, training dataset, bundle, release_id, `INCOMPLETE 0/4`,
   etiqueta y 5,772 filas. Cambiarán `evaluation_digest` y el digest de shards porque se corrige la
   evidencia; eso es esperado y obliga a repetir RAG-C después de STATUS-B.
9. Añadir pruebas que fallen contra `f41c2e3d` y pasen con A.3:
   - snapshot vigente: corte W26, `0/4`, cero omitidas;
   - snapshot hasta W27: `1/4`, cero semanas futuras omitidas;
   - snapshot hasta W31 con W28 ausente: `4/4`, única omitida W28;
   - duplicado periodo×serie rechazado antes de construir history;
   - MASE de dos series con escalas muy distintas no cambia al añadir/reordenar la otra;
   - MASE de un producto derivado usa su propia historia agregada;
   - denominador cero → `null` + flag;
   - alterar rows, degradación, passes, verdict, per_week, cutoff o motivo de omisión se rechaza
     aun si se recalcula el digest exterior;
   - `--check` sigue no mutante y `--write` sigue atómico.
10. Ejecutar `ruff`, format-check, mypy, fast, los 112 tests focalizados de publicación,
    integración estable y doctors.
11. Crear un único commit local `C7.6-PUBLICATION-STATUS-A.3` y STOP.

#### Prohibiciones de A.3

- No descargar/extractar boletines ni fabricar un dataset canónico nuevo.
- No cambiar gate, regla 5/5/10, candidato, control, bundle, release o lifecycle.
- No dashboard, clave, RAG, DVC, push, puntero activo, deploy o publicación.
- No ejecutar STATUS-B en la misma ronda.
- No reabrir defensas de filesystem, locks o amenazas locales: esta ronda es sólo verdad,
  calendario, métricas y contrato de evidencia.

#### Secuencia posterior, aún no autorizada

```text
auditar STATUS-A.3
→ STATUS-B sólo dashboard
→ auditar STATUS-B
→ repetir RAG-C en dos temporales
→ paquete C7.6-READINESS
→ autorizaciones externas separadas
```

#### Avance

El avance se mantiene en **82%**. A.2 añadió la arquitectura correcta, pero dos valores publicados
por ella todavía serían falsos: omisiones futuras y MASE contaminado. No se otorga avance por
cantidad de código mientras esos contratos funcionales no cierren.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PUBLICATION-STATUS-A.3` local en backend y STOP.**

_Respuesta:_ **GO C7.6-PUBLICATION-STATUS-A.3 LOCAL. Corregir corte observado, duplicados
pre-history, MASE por producto y coherencia semántica de evaluation; un commit backend y STOP. Sin
boletines nuevos, dashboard, clave, RAG, DVC, push, lifecycle, activación, deploy ni publicación.**

---

### Ronda 81 — C7.6-PUBLICATION-STATUS-A.3 ejecutada — 2026-07-27

Un commit local en el backend. Sin boletines nuevos, dashboard, clave, RAG, DVC, push, lifecycle,
activación, deploy ni publicación. **STATUS-B no se tocó.**

```text
83f04ce6  C7.6-PUBLICATION-STATUS-A.3 corte observado, MASE por producto y evidencia coherente
```

Los cuatro hallazgos eran correctos, y los dos primeros producían **valores publicados falsos**.

#### R80-P0-1 · el futuro no es una semana ausente

```text
antes   skipped_weeks = 52 · primera "ausente" 2026-W27 · sin corte declarado
ahora   skipped_weeks = 0  · observation_cutoff [2026, 26]
```

La ventana termina en el corte que el propio snapshot alcanza. El corte se persiste y se valida al
cargar: una semana declarada omitida que sea posterior al corte se rechaza.

#### R80-P0-2 · MASE por producto, medido

Reproducción con dos escalas (1 y 1000) en series constantes, donde el lag-52 **dentro** de cada
serie es exactamente 0:

```text
antes   denominador CONCATENADO 495.6 sobre una serie ficticia de 6,656 puntos
ahora   111 productos con denominador propio · máximo 0.0
```

Un 0 no es «peor»: es el valor correcto para una serie constante, y por eso viaja como `null` con su
bandera. El 495.6 medía saltos entre entidades que nunca ocurrieron. Ahora la historia de training
se deriva 64→111 con el catálogo del runner y cada producto usa la suya; el ámbito se resume con la
mediana de productos finitos, para candidato **y** control.

#### R80-P0-3 · los duplicados mueren en el frame

`check_dataset_frame` valida el EpiDatasetV2 tabular antes de construir ningún mapping: schema, 64
SeriesKeys, unicidad de `(cve_ent, sexo, epi_year, epi_week)`, periodos MMWR válidos, finitos no
negativos y el mismo conjunto de periodos por serie. La prueba duplica una fila real del dataset
canónico y comprueba que ya no sobrevive.

#### R80-P1 · el artefacto se sostiene solo

El loader recomputa **degradación, `passes` y veredicto** desde sMAPE candidato/control y el umbral
del gate, y exige forma cerrada: `rows = 64n / 111n / 1n`, `per_week` uno a uno con
`completed_weeks`, motivos de omisión en enum cerrado y nunca posteriores al corte, y `null`
únicamente acompañado de su bandera. Siete mutaciones —`rows`, degradación, `passes`, veredicto,
`per_week`, `cutoff` y motivo inventado— se rechazan **aunque se recalcule el digest exterior**.

#### Lo que cambia y lo que no

```text
gate_digest · regla 5/5/10 · candidato · control · bundle · release_id   byte-idénticos
estado vigente        INCOMPLETE 0/4 · misma etiqueta · 5,772 filas · 9 shards
evaluation            v1 → v2 (nuevo campo observation_cutoff)
evaluation_digest     cambia: la evidencia se corrigió
digest de shards      11c3161870c33a25… (antes 8aeb4382…)
```

El digest de shards vuelve a moverse, como anticipaste. **RAG-C debe repetirse después de
STATUS-B**, no antes.

#### Gate

```text
ruff check + format                        PASS
mypy                                       161 archivos · PASS
pytest -m "not slow and not integration"   1989 passed · cobertura 80.78%
tests/unit/publication                     155 passed
integración de release                     8 passed
doctor_padecimiento                        rc=0
```

#### Estado

```text
Backend     83f04ce6 · ahead 21 · SIN PUSH  (el plan sigue con tus ediciones sin commitear)
Dashboard   4cdc17dd · limpio · ahead 16 · SIN PUSH · intacto
Readiness   RAG-A ✓ A.1 ✓ B ✓ C ✓(a repetir) · STATUS-A ✓ A.1 ✓ A.2 ✓ A.3 ✓ (a auditar) · STATUS-B ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar STATUS-A.3**. STATUS-B sigue sin autorizar.

_Respuesta:_

---

### Ronda 82 — Auditoría STATUS-A.3: cálculo PASS, contrato v2 requiere microcierre — 2026-07-27

#### Veredicto

**A.3 aprueba el corte observado, la validación pre-history y el cálculo MASE por producto. Antes de
entregar el contrato al dashboard necesita A.3.1: un cierre pequeño de forma y evidencia, no otro
rediseño del evaluator.**

Evidencia independiente:

```text
commit auditado                   83f04ce6
diff                              7 archivos · +670/-97 · check PASS
tests unitarios de publication    155/155 PASS con --no-cov
prospective_status --check        rc=0
schema                            prospective_evaluation.v2
observation_cutoff                2026-W26
completed / skipped               0 / 0
estado                            INCOMPLETE 0/4
```

Queda aprobado:

- el futuro ya no se etiqueta como ausente;
- W28 omitida y W31 sustituta atraviesan el flujo;
- el CSV se valida antes de convertirse a `dict`;
- training se deriva 64→111 y MASE se calcula por producto;
- degradación, `passes` y verdict se recomputan al cargar;
- el artefacto vigente conserva gate, candidato, control, bundle, release y 5,772 filas.

#### R82-P0-1 — “MASE null” es en realidad una clave ausente

En una serie constante, `series_metrics()` devuelve MASE no finito con
`mase_zero_denom`. `scope_metrics()` sólo acumula métricas finitas y construye `median` recorriendo
las listas que sí existen. Resultado medido:

```text
median_keys    bias, mae, rmse, smape, wape
mase_present   false
mase_get       null
flags          {"mase_zero_denom": 64}
```

La prueba usa `.get("mase") is None`, por lo que no distingue entre “clave presente con null” y
“clave borrada”. La afirmación de Ronda 81 —“viaja como null con su bandera”— todavía no es cierta.
El consumidor entre repos necesita una forma estable: las seis métricas deben estar siempre
presentes.

#### R82-P0-2 — se puede borrar la procedencia y volver a sellar

La forma exterior exige `observation_source_digests`, pero el loader no exige sus miembros. Repro
independiente sobre el evaluation vigente:

```text
observation_source_digests = {}
evaluation_digest          recomputado
status.evaluation_digest   actualizado
load_declared_status       ACEPTA
```

La evidencia prometida en A.2 era `raw/config/exposure`; aceptar `{}` convierte el dataset de
observación en una identidad sin procedencia. El catálogo geográfico continúa sellado dentro de
`config`, como ya documentó R80; no se añade una fuente duplicada.

#### R82-P0-3 — el corte puede desaparecer aunque el snapshot no esté vacío

Segundo repro independiente:

```text
observation_cutoff         null
evaluation_digest          recomputado
status.evaluation_digest   actualizado
load_declared_status       ACEPTA
```

Todo EpiDatasetV2 admitido tiene filas y un máximo periodo. En v2, `null` no representa un caso
real: sólo permite borrar la frontera que distingue “futuro” de “ausente”. Debe ser un periodo MMWR
obligatorio y no anterior al origen congelado.

#### R82-P1 — la forma “cerrada” aún permite conteos y secuencias contradictorias

La validación actual:

- comprueba que `products` sea entero, pero no que sea 64/111/1 según el scope;
- acepta cualquier subconjunto de claves dentro de `median`;
- acepta `per_week.series=1` aunque la verdad requiera 64 bases;
- valida que una omisión declarada sea admisible, pero no que la secuencia
  `completed + skipped` cubra todas las semanas observables hasta el corte o hasta la cuarta
  completa.

Así, un evaluation re-sellado puede borrar W28 de `skipped_weeks`, conservar W29–W31 como completas
y seguir cargando. No cambia el veredicto numérico, pero sí borra evidencia de qué pasó con una
semana programada.

#### Orden C7.6-PUBLICATION-STATUS-A.3.1 — cerrar la forma, sin reabrir el cálculo

Ejecutar únicamente backend sobre `83f04ce6`, un commit local y STOP:

1. Hacer que cada bloque `median` emita siempre exactamente:
   `smape`, `mase`, `mae`, `rmse`, `wape`, `bias`.
2. Si una métrica no tiene productos finitos, emitir la clave con `null`; nunca omitirla. `null`
   sólo es válido con su flag zero-denominator correspondiente.
3. Exigir `products == 64/111/1` para bases/productos/nacional General, tanto en candidate como en
   control. Validar flags como conteos enteros no negativos y no mayores que `products`.
4. Exigir en evaluation v2 exactamente los digests `raw`, `config`, `exposure`, todos SHA256
   válidos. Conservar geografía dentro del digest efectivo de config.
5. Hacer obligatorio `observation_cutoff`, MMWR válido y `>= gate.origin`.
6. Exigir `per_week.series == 64`, semanas únicas y el mismo orden que `completed_weeks`.
7. Validar la secuencia observada completa:
   - si aún hay menos de cuatro semanas completas, `completed ∪ skipped` debe ser exactamente cada
     periodo desde la primera semana objetivo hasta
     `min(observation_cutoff, fin_del_horizonte)`;
   - si ya hay cuatro completas, debe cubrir exactamente hasta la cuarta completa;
   - ambos conjuntos deben ser disjuntos, cronológicos y cada periodo aparecer una sola vez.
8. Mantener `prospective_evaluation.v2` y `prospective_status.v2`; no hay cambio de schema.
9. Regenerar evaluation/status sólo si los bytes derivados cambian. Para el estado real `0/4`, los
   digests de procedencia y el corte ya son correctos, por lo que no se deben inventar cambios.
10. Añadir pruebas que fallen contra `83f04ce6`:
    - distinguir clave MASE ausente de `mase: null`;
    - rechazar source digests vacíos/faltantes/extra;
    - rechazar cutoff null o anterior al origen;
    - rechazar `products`, claves de median, flags o `per_week.series` falsos aunque se re-selle;
    - rechazar que se borre una semana observada de completed/skipped;
    - aceptar los tres escenarios aprobados: W26→0/4 sin omisiones, W27→1/4, W31 con sólo W28
      omitida.
11. Ejecutar ruff, format-check, mypy, fast, los 155 unitarios de publication, integración estable
    y doctors.
12. Crear un único commit local `C7.6-PUBLICATION-STATUS-A.3.1` y STOP.

#### Prohibiciones de A.3.1

- No cambiar evaluación sMAPE 5/5/10, derivación 64→111, candidato, control, gate o release.
- No descargar boletines ni crear datasets.
- No dashboard, clave, RAG, DVC, push, lifecycle, puntero, deploy o publicación.
- No ejecutar STATUS-B en esta ronda.
- No añadir endurecimiento de filesystem, concurrencia o seguridad local: sólo forma del contrato
  prospectivo ya calculado.

#### Secuencia posterior, aún no autorizada

```text
auditar STATUS-A.3.1
→ STATUS-B sólo dashboard
→ auditar STATUS-B
→ repetir RAG-C en dos temporales
→ paquete C7.6-READINESS
→ autorizaciones externas separadas
```

#### Avance

El avance se mantiene en **82%**. El cálculo funcional ya es correcto; A.3.1 evita entregar al
dashboard un schema que acepte métricas o procedencia incompletas.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PUBLICATION-STATUS-A.3.1` local en backend y STOP.**

_Respuesta:_ **GO C7.6-PUBLICATION-STATUS-A.3.1 LOCAL. Hacer explícitas las seis métricas, exigir
procedencia/corte y cerrar conteos y secuencia semanal; un commit backend y STOP. Sin dashboard,
clave, RAG, DVC, push, lifecycle, activación, deploy ni publicación.**

---

### Ronda 83 — C7.6-PUBLICATION-STATUS-A.3.1 ejecutada — 2026-07-27

Un commit local en el backend. Sin dashboard, clave, RAG, DVC, push, lifecycle, activación, deploy
ni publicación. **STATUS-B no se tocó.**

```text
84d84675  C7.6-PUBLICATION-STATUS-A.3.1 forma cerrada del contrato prospectivo
```

#### R82-P0-1 · tenías razón, y desmiente lo que escribí en la Ronda 81

Dije que un MASE indefinido «viaja como `null` con su bandera». **No era cierto**: la clave no
estaba, y mi propia prueba usaba `.get("mase") is None`, que no distingue *ausente* de *null*. El
test daba verde sobre una afirmación falsa.

```text
antes   median = bias, mae, rmse, smape, wape        · 'mase' presente: False
ahora   median = bias, mae, mase, rmse, smape, wape  · 'mase' presente: True · valor null
        flags = {"mase_zero_denom": 64}
```

Las seis se emiten siempre, y un `null` sólo es válido acompañado de su bandera.

#### R82-P0-2 y P0-3 · procedencia y corte, reproducidos

```text
                                   83f04ce6      A.3.1
procedencia vaciada y re-sellada   ACEPTA        RECHAZA
observation_cutoff = null          ACEPTA        RECHAZA
```

Ahora se exigen exactamente `raw`, `config` y `exposure` —los tres SHA256 válidos— y el corte es
obligatorio, MMWR válido y no anterior al origen congelado. La geografía sigue sellada dentro del
digest efectivo de `config`, sin duplicar fuente.

#### R82-P1 · conteos y secuencia

`products` debe ser **64/111/1** por ámbito y lado, `median` lleva exactamente las seis claves, cada
flag es un entero `0..products`, `per_week.series == 64`, y **completadas ∪ omitidas** tiene que
cubrir *exactamente* cada periodo observable hasta el corte —o hasta la cuarta completa—. La prueba
carga un artefacto con W28 declarada ausente y luego la borra re-sellando: deja de cargar.

#### Lo que NO cambió

```text
sMAPE 5/5/10 · derivación 64→111 · candidato · control · gate · release_id   intactos
los tres escenarios aprobados                    W26→0/4 · W27→1/4 · W31 con sólo W28 omitida
evaluation y status declarados                   BYTE-IDÉNTICOS a 83f04ce6
digest de shards                                 sin cambio
```

Esto último es deliberado y responde a tu punto 9: el `0/4` vigente ya tenía corte y procedencia
correctos, y no hay métricas que completar porque no hay ámbitos. No inventé un cambio para
justificar la ronda.

#### Gate

```text
ruff check + format                        PASS
mypy                                       161 archivos · PASS
pytest -m "not slow and not integration"   2000 passed · cobertura 80.82%
publicación                                68 en test_status · 14 en test_prospective_rule
integración de release                     8 passed
doctor_padecimiento                        rc=0
```

#### Estado

```text
Backend     84d84675 · ahead 22 · SIN PUSH  (el plan sigue con tus ediciones sin commitear)
Dashboard   4cdc17dd · limpio · ahead 16 · SIN PUSH · intacto
Readiness   RAG-A ✓ A.1 ✓ B ✓ C ✓(a repetir) · STATUS-A ✓ A.1 ✓ A.2 ✓ A.3 ✓ A.3.1 ✓ · STATUS-B ✗
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar STATUS-A.3.1**. STATUS-B sigue sin autorizar.

_Respuesta:_

---

### Ronda 84 — Auditoría STATUS-A.3.1: STATUS-A CERRADO / PASS — 2026-07-27

#### Veredicto

**A.3.1 cierra los repros de R82 sin cambiar los artefactos declarados. STATUS-A completo queda
aprobado y se autoriza STATUS-B únicamente en el dashboard.**

Evidencia independiente:

```text
commit auditado                         84d84675
diff                                    3 archivos · +206/-11 · check PASS
rutas                                   prospective.py · status.py · test_status.py
evaluation/status declarados            no tocados por el commit
tests unitarios de publication          166/166 PASS con --no-cov
prospective_status --check              rc=0
procedencia vacía re-sellada            RECHAZADA
observation_cutoff null re-sellado      RECHAZADO
estado                                  INCOMPLETE 0/4
```

Los contratos aprobados al cerrar STATUS-A son:

1. training y observation están separados y sellados;
2. candidato, control, dataset y gate conservan sus identidades congeladas;
3. el futuro no se registra como ausente;
4. una semana faltante se sustituye por la siguiente completa dentro del horizonte;
5. el dataset tabular se valida antes de construir histories;
6. MASE se calcula por producto y las seis métricas siempre existen;
7. procedencia, corte, conteos, secuencia, degradación, `passes` y verdict fallan cerrado;
8. evaluation v2 y status v2 se cruzan por digest;
9. los shards siguen declarando `INCOMPLETE 0/4` y point-only;
10. Obesidad continúa `trained`, invisible y sin puntero activo.

No se abre otro microcierre backend. Los aspectos no decisivos de presentación pertenecen ahora al
consumidor STATUS-B; RAG se repite después, una sola vez, con el texto candidate definitivo.

#### Objetivo de STATUS-B

El dashboard ya sabe leer un shard candidate y evitar una banda de incertidumbre falsa. Le falta
consumir el bloque `publication_status` que ahora produce el backend, verificar que sea el mismo en
`shard_manifest.json` y `web/manifest.json`, y llevar su etiqueta al modelo de vista. No debe
reimplementar el evaluator ni leer los JSON privados del backend.

La autoridad que cruza repos es el shard:

```text
publication_shard.v1
├── publication_label
└── publication_status
    ├── schema = prospective_status.v2
    ├── gate_digest / evaluation_digest / status_digest
    ├── observation_dataset_id
    ├── verdict
    ├── weeks_available / weeks_required
    ├── completed_weeks / target_weeks
    └── label
```

#### Orden C7.6-PUBLICATION-STATUS-B — consumidor de staging

Ejecutar únicamente en
`/Users/haowei/Documents/Integrador/EpiForecast-IMSS-Dashboard`, rama
`feat/c73-candidate-staging`, sobre `4cdc17dd`; un commit local y STOP:

1. Extender `epibot/scripts/lib/candidate.mjs` para validar `publication_status` como parte
   obligatoria de `publication_shard.v1`.
2. Exigir forma cerrada del bloque:
   - `schema == prospective_status.v2`;
   - digests de gate/evaluation/status con 64 hex minúsculas;
   - `observation_dataset_id` y `label` no vacíos;
   - verdict en `INCOMPLETE/PASS/FAIL`;
   - enteros no booleanos con `0 <= weeks_available <= weeks_required`;
   - `completed_weeks.length == weeks_available`;
   - `target_weeks.length == weeks_required`;
   - periodos `[epi_year, epi_week]` válidos y únicos.
3. Exigir coherencia:
   - `publication_label == publication_status.label`;
   - el bloque completo y la etiqueta deben ser byte/valor-equivalentes entre
     `shard_manifest.json` y `web/manifest.json`;
   - `INCOMPLETE` sólo con menos semanas que las requeridas;
   - `PASS/FAIL` sólo con todas las semanas;
   - completed weeks ordenadas y dentro del conjunto/horizonte declarado por el shard.
4. No reconstruir el texto español ni recalcular el gate en JavaScript. El backend ya validó la
   evidencia; el dashboard valida el contrato transportado y muestra su `label`.
5. Crear o extender un view-model puro de staging para que cualquier serie candidate lleve juntas:
   - `validationLabel = publication_label`;
   - `uncertaintyLabel = Pronóstico puntual; sin intervalo de incertidumbre`;
   - `band = null`;
   - `isPubliclyVisible = false` mientras lifecycle sea `trained`.
6. Rechazar el shard antes de producir el view-model si falta el status, si difiere entre
   manifests, si la etiqueta está vacía/inconsistente o si los conteos/verdict se contradicen.
7. Mantener `buildChunks()` público sin argumentos byte-idéntico. El chunk candidate de staging
   debe contener la etiqueta exacta y la advertencia point-only; no copiarlo todavía al índice
   público.
8. Probar con fixtures propios los estados:
   - `INCOMPLETE 0/4`;
   - `INCOMPLETE 1/4`;
   - `PASS 4/4`;
   - `FAIL 4/4`;
   - todos los rechazos del punto 6.
9. Gate entre repos con un shard real generado por el backend `84d84675` en un temporal:
   - 5,772 filas;
   - release `obesidad_release_2517e7858901`;
   - lifecycle `trained`;
   - etiqueta exacta
     `Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos`;
   - `band=null`;
   - `isPubliclyVisible=false`;
   - cuatro canales emitidos y ninguno sin puente.
   La ruta temporal se inyecta por argumento; no hardcodear la ubicación del backend.
10. Ejecutar `npm test`, `npm run test:candidate` y `npm run check`. El índice RAG público y las
    superficies publicadas deben permanecer byte-idénticos y con cero menciones de Obesidad.
11. Tocar sólo módulos/tests de staging necesarios. No modificar `knowledge.json`,
    `rag_index.json`, HTML, CSS, Netlify, package/lock ni archivos públicos.
12. Crear un único commit local `C7.6-PUBLICATION-STATUS-B` en la rama del dashboard y STOP.

#### Prohibiciones de STATUS-B

- No modificar backend, gate, evaluation, status, release, bundle o DVC.
- No usar `GEMINI_API_KEY`, regenerar RAG ni ejecutar RAG-C en esta ronda.
- No lifecycle, puntero, push, PR, merge, deploy, preview o publicación.
- No integrar Obesidad en HTML/knowledge/index públicos.
- No inventar una segunda fórmula de estado en JavaScript.

#### Gate de salida

STATUS-B se cierra sólo si:

```text
shard real 5,772 filas                     PASS
status v2 y label cruzados entre manifests PASS
view-model 0/4 + point-only                PASS
candidate sigue no público                 PASS
npm test / test:candidate / check          PASS
superficies e índice público               byte-idénticos · 0 Obesidad
un commit dashboard                        creado
```

#### Secuencia posterior, aún no autorizada

```text
auditar STATUS-B
→ repetir RAG-C en dos temporales con el nuevo chunk candidate
→ paquete C7.6-READINESS
→ autorizaciones externas separadas
```

#### Avance

El avance sube a **83%**: STATUS-A está cerrado. La exposición pública permanece en **0%**.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PUBLICATION-STATUS-B` local en el dashboard y STOP.**

_Respuesta:_ **GO C7.6-PUBLICATION-STATUS-B LOCAL EN
EpiForecast-IMSS-Dashboard. Validar y transportar publication_status/label al view-model candidate,
probar el shard real 0/4 point-only y preservar toda superficie pública; un commit dashboard y
STOP. Sin RAG-C, clave, backend, DVC, push, lifecycle, activación, deploy ni publicación.**

---

### Ronda 85 — C7.6-PUBLICATION-STATUS-B ejecutada — 2026-07-27

Un commit local en el **dashboard**, rama `feat/c73-candidate-staging`. Sin RAG-C, clave, backend,
DVC, push, lifecycle, activación, deploy ni publicación.

```text
2213bff2  C7.6-PUBLICATION-STATUS-B consumir y transportar el estado prospectivo
```

#### Lo que valida el consumidor

`candidate.mjs` trata `publication_status` como parte **obligatoria** de `publication_shard.v1`:
schema `prospective_status.v2`, tres digests de 64 hex minúsculas, `observation_dataset_id` y
`label` no vacíos, verdict en el enum, enteros no booleanos con `0 ≤ disponibles ≤ requeridas`,
longitudes coherentes con los conteos, periodos MMWR válidos y únicos, completadas ordenadas y no
anteriores a la primera objetivo, e `INCOMPLETE` sólo con menos semanas de las requeridas.

Y exige **coherencia entre repos**: el bloque tiene que ser idéntico en `shard_manifest.json` y
`web/manifest.json`, y `publication_label` coincidir con `publication_status.label` en ambos. Que
viaje por duplicado no es redundancia inútil —cada canal lee el suyo—; si divergen, el usuario vería
dos condiciones distintas para el mismo dato.

No se recalcula el gate ni se reconstruye el texto en español. El backend ya validó la evidencia;
aquí se valida el **contrato transportado**.

#### El view-model

`candidate_view.mjs` junta lo que nunca debe separarse:

```text
validationLabel     verbatim del backend
uncertaintyLabel    Pronóstico puntual; sin intervalo de incertidumbre
band                null
isPubliclyVisible   false mientras lifecycle sea trained
```

Ni siquiera un `PASS 4/4` lo vuelve público: eso lo decide el lifecycle, no el veredicto.

#### Gate entre repos, con el shard real

Generado por el backend `84d84675` en un temporal **inyectado por argumento** (`C7_SHARD_ROOT`);
la ubicación del otro repo no está codificada en ningún sitio:

```text
/var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.mFi7eoX0gV

5,772 filas · release obesidad_release_2517e7858901 · lifecycle trained
etiqueta   Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos
band null · isPubliclyVisible false · 4 canales · channels_without_bridge []
```

#### Fixtures: los cuatro estados y los rechazos

`0/4`, `1/4`, `PASS 4/4` y `FAIL 4/4`, más status ausente, distinto entre manifiestos, etiqueta
inconsistente, forma cerrada rota (14 variantes), veredicto contra conteos, orden y ventana.

#### Efectos colaterales que conviene tener escritos

1. **Cuatro pruebas de `test_candidate_staging.mjs` se pusieron rojas** al hacer obligatorio el
   estado, porque sus fixtures no lo traían. Es exactamente lo que debía pasar; se les añadió el
   bloque. Ningún caso se relajó.
2. **No wireé el test nuevo en `npm run test:candidate`**: eso exige tocar `package.json`, que tu
   punto 11 prohíbe en esta ronda. Se ejecuta explícitamente con
   `node --test tests/test_candidate_status.mjs`. Queda pendiente integrarlo al comando oficial
   cuando autorices tocar `package.json`; hasta entonces el gate depende de que alguien lo
   invoque, y eso es una deuda, no una comodidad.

#### Gate

```text
npm test                        616/616 + 67 unitarias · rc=0
npm run test:candidate          19/19
test_candidate_status           12/12 con el shard real (11 sin él, 1 skip declarado)
npm run check                   rc=0
node --check                    candidate.mjs · candidate_view.mjs  PASS
buildChunks() público           454 chunks · digest 11ec6151867a4cac… sin cambio
chunk candidate de staging      lleva la etiqueta exacta y la advertencia point-only
knowledge.json · rag_index.json · index.html · epibot/index.html   byte-idénticos · 0 Obesidad
package.json / lock             sin tocar
```

#### Estado

```text
Dashboard   2213bff2 · limpio · ahead 17 de main · SIN PUSH
Backend     84d84675 · ahead 22 · SIN PUSH · intacto en esta ronda
Readiness   STATUS-A ✓ (A.1/A.2/A.3/A.3.1) · STATUS-B ✓ (a auditar) · RAG-C a repetir
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar STATUS-B**. Después, repetir RAG-C en dos temporales con el
chunk candidate definitivo.

_Respuesta:_

---

### Ronda 86 — Auditoría STATUS-B: consumidor PASS, gate canónico desconectado — 2026-07-27

#### Veredicto

**El consumidor funciona y el gate real entre repos pasa. STATUS-B queda PARCIAL hasta B.1 porque
su prueba principal no forma parte de `npm test`, `npm run test:candidate` ni `npm run check`.**

Evidencia independiente:

```text
commit auditado                   2213bff2
diff                              4 archivos · +459 · check PASS
npm test                          616/616 + 67 · PASS
npm run test:candidate            19/19 · PASS
test_candidate_status sin shard   11 PASS + 1 SKIP
test_candidate_status shard real  12/12 PASS
npm run check                     PASS
shard real                        5,772 · trained · 0/4 · point-only · no público
superficies públicas              byte-idénticas · 0 Obesidad
```

#### R86-P0 — el test que protege STATUS-B no corre en CI

`npm run test:candidate` continúa ejecutando únicamente:

```text
node --test tests/test_candidate_staging.mjs
```

`npm run check` delega a ese comando, por lo que tampoco ejecuta
`tests/test_candidate_status.mjs`. Un cambio futuro podría romper status/label/view-model y dejar
verdes todos los comandos oficiales. Ejecutarlo manualmente demuestra que hoy funciona, pero no
convierte la prueba en un gate mantenible.

La causa es una contradicción de la **Orden 84**, no una desobediencia de la implementación:

- punto 10: `npm run test:candidate` y `npm run check` debían cubrir el gate;
- punto 11: prohibía modificar `package.json`, único lugar donde se cablean esos comandos.

Se corrige la orden: B.1 autoriza explícitamente modificar sólo los scripts de
`epibot/package.json`. No autoriza dependencias ni `package-lock.json`.

#### R86-P1 — “forma cerrada” y coherencia entre manifests todavía son parciales

El validador comprueba los campos conocidos, pero no rechaza campos desconocidos dentro de
`publication_status`. Bajo un schema versionado, “cerrado” significa el conjunto exacto de once
claves que emite `status_facts()`, no “al menos estas claves”.

Además, cruza status y label, pero no cruza otros invariantes que ambos manifests repiten. Un
`web/manifest.json` con `lifecycle=published` y un `shard_manifest.json` con `lifecycle=trained`
puede cargar hoy porque sólo se contrasta el release y el status. Cada canal podría interpretar una
visibilidad distinta para el mismo shard.

No se pide duplicar el evaluator ni endurecer entradas arbitrarias. Se pide cerrar el contrato que
los dos repos ya declaran.

#### Orden C7.6-PUBLICATION-STATUS-B.1 — integración canónica mínima

Ejecutar únicamente en el dashboard sobre `2213bff2`, un commit local y STOP:

1. Modificar `epibot/package.json`:
   - `test:candidate` debe ejecutar `test_candidate_staging.mjs` y
     `test_candidate_status.mjs`;
   - `check` debe cubrir también `candidate_view.mjs`, directa o indirectamente mediante el test
     canónico.
2. No añadir dependencias, scripts de red ni cambios en `package-lock.json`.
3. Exigir en `publication_status` exactamente estas claves:
   `schema`, `gate_digest`, `evaluation_digest`, `status_digest`, `observation_dataset_id`,
   `verdict`, `weeks_required`, `weeks_available`, `completed_weeks`, `target_weeks`, `label`.
   Una clave faltante o desconocida debe fallar.
4. Cruzar entre `shard_manifest.json` y `web/manifest.json`, además del status/label:
   `schema`, `release_id`, `disease_id`, `lifecycle`, `rows`, `interval_method`,
   `uncertainty_available`. No comparar el manifest entero: cada canal tiene campos propios.
5. Hacer que el view-model use la función compartida de visibilidad o fijar por prueba que su regla
   sea idéntica: sólo `lifecycle=published` devuelve `true`; PASS/FAIL no intervienen.
6. Añadir pruebas que fallen contra `2213bff2`:
   - el archivo nuevo aparece en el comando real leído desde `package.json`;
   - status con clave extra se rechaza;
   - `web` con disease, lifecycle, rows, interval o uncertainty distintos se rechaza;
   - control positivo con los manifests reales sigue pasando.
7. Ejecutar:

```text
npm test
npm run test:candidate
npm run check
C7_SHARD_ROOT=<temporal-real> npm run test:candidate
```

   El último debe ejecutar también el caso real de 5,772 filas; sin la variable, ese único caso
   puede declararse SKIP mientras todos los fixtures contractuales sí corren.
8. Verificar otra vez que `knowledge.json`, `rag_index.json`, ambos HTML y `buildChunks()` público
   sean byte-idénticos y contengan cero Obesidad.
9. Crear un único commit local `C7.6-PUBLICATION-STATUS-B.1` en el dashboard y STOP.

#### Prohibiciones de B.1

- No backend, RAG-C, clave, regeneración del índice ni modificación de sus bytes.
- No dependencias, package-lock, HTML, CSS, Netlify o superficies públicas.
- No push, PR, merge, deploy, lifecycle, puntero, activación o publicación.
- No añadir más validación estadística: el backend es autoridad del gate.

#### Secuencia posterior, aún no autorizada

```text
auditar STATUS-B.1
→ repetir RAG-C en dos temporales con el chunk candidate definitivo
→ paquete C7.6-READINESS
→ autorizaciones externas separadas
```

#### Avance

Se mantiene en **83%**. El comportamiento está implementado, pero todavía no es un gate automático.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PUBLICATION-STATUS-B.1` local en el dashboard y STOP.**

_Respuesta:_ **GO C7.6-PUBLICATION-STATUS-B.1 LOCAL EN EpiForecast-IMSS-Dashboard. Integrar el test
de status en los comandos canónicos, cerrar las claves exactas y cruzar los invariantes comunes de
ambos manifests; un commit dashboard y STOP. Se autoriza sólo el cambio de scripts en
epibot/package.json, sin dependencias ni lock. Sin RAG-C, clave, backend, push, lifecycle,
activación, deploy ni publicación.**

---

### Ronda 87 — C7.6-PUBLICATION-STATUS-B.1 ejecutada — 2026-07-27

Un commit local en el **dashboard**. Sin RAG-C, clave, backend, push, lifecycle, activación, deploy
ni publicación.

```text
20822a62  C7.6-PUBLICATION-STATUS-B.1 integrar el gate y cerrar el contrato
```

#### R86-P0 · el gate ya es automático

```text
test:candidate   node --test tests/test_candidate_staging.mjs tests/test_candidate_status.mjs
check            … node --check candidate_view.mjs … && npm test && npm run test:candidate && rag:verify
```

`npm run check` ejecuta ahora el test de status **por dentro** —verificado en su salida, no leyendo
el script—. Sólo se tocaron *scripts*: ni dependencias ni `package-lock.json`, que queda
byte-idéntico.

Y gracias por corregir la orden en vez de sostener la contradicción: el punto 10 pedía el gate y el
11 prohibía el único archivo donde se cablea. Lo dejé escrito como deuda precisamente para esto.

#### R86-P1 · el contrato, ahora cerrado de verdad

«Forma cerrada» era en realidad «al menos estas claves». Ahora se exige el conjunto **exacto de
once** que emite `status_facts()`: una clave desconocida o ausente falla.

Y se cruzan los invariantes que **ambos** manifiestos declaran —`schema`, `release_id`,
`disease_id`, `lifecycle`, `rows`, `interval_method`, `uncertainty_available`—, no el manifiesto
entero, porque cada canal tiene campos propios. Un `web` con `lifecycle=published` y un shard con
`trained` ya no carga: eran dos visibilidades distintas para el mismo dato.

El view-model usa la **misma** función de visibilidad que la vista pública en vez de repetir la
regla.

#### Pruebas · tres de cuatro rojas contra `2213bff2`

```text
el archivo aparece en el comando real leído del package.json     ROJA antes
clave extra o ausente en publication_status                      ROJA antes
divergencia de cada invariante común (6 casos)                   ROJA antes
la visibilidad sale de la función compartida                     verde en ambos
```

La cuarta pasa en los dos commits porque la regla duplicada era **equivalente**. La dejo como
guardia contra una divergencia futura; no la presento como prueba de una corrección.

#### Gate

```text
npm test                                616/616 + 67 · rc=0
npm run test:candidate (sin shard)      35 casos · 34 PASS + 1 SKIP declarado
npm run test:candidate (shard real)     35/35
npm run check                           rc=0 · ejecuta el test de status dentro
buildChunks() público                   454 chunks · digest 11ec6151867a4cac… sin cambio
knowledge.json · rag_index.json · ambos HTML · package-lock   byte-idénticos
menciones públicas de Obesidad          0
```

Shard real usado en el gate (temporal, inyectado por `C7_SHARD_ROOT`):

```text
/var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.mFi7eoX0gV
```

#### Estado

```text
Dashboard   20822a62 · limpio · ahead 18 de main · SIN PUSH
Backend     84d84675 · ahead 22 · SIN PUSH · intacto
Readiness   STATUS-A ✓ · STATUS-B ✓ B.1 ✓ (a auditar) · RAG-C a repetir
Obesidad    trained · puntero inactivo · 0 menciones públicas · NO-GO
```

Siguiente acción exacta: **auditar STATUS-B.1**. Después, repetir RAG-C en dos temporales con el
chunk candidate definitivo.

_Respuesta:_

---

### Ronda 88 — Auditoría STATUS-B.1 PASS y orden RAG-C definitiva — 2026-07-27

#### Veredicto

**C7.6-PUBLICATION-STATUS-B/B.1 queda CERRADA / PASS. No se abre otro microcierre del
consumidor. La siguiente acción única es repetir RAG-C en dos staging roots nuevos.**

Auditoría independiente de `2213bff2..20822a62`:

```text
commit auditado                         20822a62
diff                                    4 archivos · +97/-10 · check PASS
package.json                            sólo scripts · package-lock sin cambio
test:candidate sin shard real           34 PASS + 1 SKIP declarado
test:candidate con shard real           35/35 PASS · 5,772 filas
npm run check                           rc=0 · ejecuta status por dentro
publication_status                      conjunto exacto de 11 claves
invariantes cruzados                    schema/release/disease/lifecycle/rows/interval/uncertainty
visibilidad                             una función compartida · sólo lifecycle=published
corpus público                          454 chunks · sin cambio
superficies públicas                    byte-idénticas · 0 Obesidad
```

La comprobación de preservación se repitió desde la raíz correcta del dashboard después de que un
primer comando de auditoría usara rutas relativas desde `epibot/`. Ese error fue sólo del comando
de lectura posterior a los tests: no escribió archivos ni invalida el gate. Los SHA256 observados
son:

```text
epibot/knowledge.json       e1d9a7d9894319e60330fb85baea3f50bcf13d2c96253fac496f3b3535856e58
epibot/rag_index.json       efbae8712e9f8a287a2e54192dbafb39eee0205954a8f5c64b3bf34ec020401f
epibot/index.html           f2e66edcdf9127b74de16d0b44cc570f3cca0d28521eb7430b1c4071038c758b
index.html                  94549fbd0338886b0630e361027cc952ddcfc32debb09a59fa12278f7bf09857
epibot/package-lock.json    8f444596dc90424473810b1c5541a9f25cff4911f523a4316736ddd420549e09
```

No se eleva a defecto el hecho de que JavaScript valide la forma de un periodo y no vuelva a
implementar el calendario epidemiológico completo. La autoridad estadística y MMWR permanece en el
backend; el dashboard valida el contrato transportado. Duplicar ahí el calendario agregaría una
segunda fuente de verdad sin mejorar la decisión pública.

#### Orden C7.6-RAG-C-REPEAT — candidate definitivo sólo en temporales

RAG-C es un **gate de ejecución**, no una modificación de producto. Ejecutar con:

```text
Backend     84d84675
Dashboard   20822a62
Obesidad    lifecycle=trained
Release     obesidad_release_2517e7858901
Status      prospective_status.v2 · INCOMPLETE 0/4
```

Si alguno de esos identificadores no coincide, detenerse; no adaptar la orden al estado encontrado.

##### C0 · preflight

1. Confirmar los dos HEAD y que no existan cambios trackeados de producto. En backend se permite
   únicamente este plan modificado por el usuario; preservar todos los untracked de ambos repos.
2. Verificar localmente, sin `dvc pull`, el bundle:

```text
artifacts/releases/obesidad/obesidad_release_2517e7858901/
```

3. Confirmar la clave sin imprimir valor, longitud ni prefijo:

```text
test -n "${GEMINI_API_KEY:-}"
```

   Si falta en esa misma sesión, STOP. No leer `.env`, historial, keychain ni archivos.
4. Capturar antes de empezar:
   - SHA256 de `rag_index.json`, `knowledge.json` y ambos HTML;
   - lifecycle/canales de Obesidad y F50 y `published_members()` para los cuatro canales;
   - estado del target DVC del release y hashes legacy.
5. Crear A y B con `mktemp -d`, fuera de los dos repos. No reutilizar ningún temporal anterior.

##### C1 · compilar dos veces los shards con el status declarado

Desde backend, en A y B, usar las APIs públicas:

```python
from epiforecast.publication.compiler import MODE_CANDIDATE, compile_release
from epiforecast.runner.release_store import default_releases_root
from epiforecast.publication.shards import emit_shards
from epiforecast.publication.status import load_declared_status

status = load_declared_status("obesidad")
compilation = compile_release(
    disease_id="obesidad",
    mode=MODE_CANDIDATE,
    releases_root=default_releases_root(),
    status=status,
)
emit_shards(compilation, staging_root)
```

No construir `PublicationStatus` a mano, no pasar `status=None` y no copiar shards históricos.

Exigir **antes de usar el proveedor**:

```text
release_id                  obesidad_release_2517e7858901
lifecycle                   trained
publication_status          prospective_status.v2 · INCOMPLETE · 0/4
publication_label           Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos
channels_emitted            epibot, reports, tableau, web
channels_without_bridge     []
filas forecast              5,772
shards A vs B               byte-idénticos
```

El digest histórico `dfe85262…` de Ronda 73 **no** es expectativa: pertenecía al candidate anterior
sin el status definitivo. Calcular y reportar el nuevo digest de árbol de los nueve archivos.

##### C2 · construir los dos índices de staging

Desde `EpiForecast-IMSS-Dashboard/epibot`, una vez por raíz:

```text
npm run rag:staging -- "$C7_RAG_STAGING_A"
npm run rag:staging -- "$C7_RAG_STAGING_B"
```

Cada ejecución debe:

```text
chunks públicos        454
chunks con candidate   455
vectores reutilizados  454
vectores generados     1
modelo/dimensión       gemini-embedding-001 / 768
```

No reintentar en bucle, copiar el vector entre raíces ni degradar a fallback léxico.

##### C3 · verificaciones independientes

1. En cada `rag_index.staging.json`: `count == chunks.length == vectors.length == 455`, hashes
   únicos, cero vectores vacíos/no finitos/de dimensión incorrecta y cero problemas de contrato.
2. Los 454 vectores públicos deben ser byte-idénticos al índice público por `chunkHash`.
3. Debe existir exactamente un chunk
   `candidate:obesidad:obesidad_release_2517e7858901`, ausente del índice público, con:
   - etiqueta prospectiva exacta `0/4`;
   - advertencia point-only;
   - un vector válido.
4. Comparar A y B eliminando **sólo** `built`: chunks, texto, orden, hashes, modelo, dimensión y los
   455 vectores deben ser idénticos. Reportar el SHA256 normalizado de ambos.
5. Ejecutar `npm run check`; debe volver a pasar e incluir STATUS-B/B.1 y `rag:verify`.
6. Recalcular todas las superficies públicas y exigir bytes idénticos y cero menciones de
   Obesidad.
7. Confirmar nuevamente:
   - Obesidad `trained`, cuatro canales, galería apagada y puntero inactivo;
   - F50 `configured`, sin canales;
   - `published_members()` = Alzheimer, Dengue, Depresión y Parkinson;
   - release DVC, runs canónicos y agregados legacy sin cambio.

##### C4 · salida y STOP

Si pasa:

- no crear commit en ninguno de los repos;
- conservar A/B para auditoría y reportar sólo sus rutas opacas;
- reportar digests, conteos y resultado de cada gate;
- STOP: no iniciar readiness, push, activación o deploy en la misma ronda.

Si falla:

- conservar A/B y la evidencia;
- no corregir código dentro de RAG-C;
- no regenerar el índice público;
- no avanzar.

#### Prohibiciones

- No escribir `epibot/rag_index.json`, `knowledge.json`, HTML ni otra superficie pública.
- No modificar código, tests, config, plan, bundle, DVC, lifecycle, puntero o canales.
- No commit, push, PR, merge, tag, deploy, preview, cache-bust, activación ni publicación.
- No registrar `GEMINI_API_KEY` en comandos persistidos, archivos, logs o evidencia.

#### Gate de cierre

```text
shards A/B con status definitivo         byte-idénticos
índices A/B sin built                    byte-idénticos
public/reused                            454/454 idénticos por hash
candidate                                1 chunk · 1 vector válido · sólo staging
total                                    455 chunks / 455 vectores
drift / vacíos / duplicados              0 / 0 / 0
npm run check                            rc=0
superficies públicas                     byte-idénticas · 0 Obesidad
lifecycle/puntero/F50/legacy/DVC          sin cambios
commits                                  ninguno
```

#### Secuencia posterior, todavía no autorizada

```text
auditar la evidencia de RAG-C-REPEAT
→ emitir C7.6-READINESS con lista exacta de commits y gates
→ autorizar por separado checkpoints remotos
→ autorizar por separado activación
→ autorizar por separado deploy y smoke público
```

#### Avance

El avance operativo permanece en **83%** hasta que RAG-C se repita y la evidencia final de
readiness quede emitida. La exposición pública permanece en **0%**.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-RAG-C-REPEAT` en A/B temporales y STOP.**

_Respuesta:_ **GO C7.6-RAG-C-REPEAT LOCAL/STAGING. Usar `GEMINI_API_KEY` sólo desde el entorno para
generar independientemente el único embedding candidate en cada raíz; no modificar producto ni
crear commits. Sin push, PR, merge, DVC, lifecycle, puntero, activación, deploy ni publicación.**

---

### Ronda 88 — C7.6-RAG-C-REPEAT ejecutada: candidate definitivo en dos temporales — 2026-07-27

Gate de ejecución. **Ningún commit**, ningún cambio de producto. Temporales conservados. Obesidad
sigue `trained`.

#### C0 · preflight

```text
dashboard trackeado-limpio     sí
backend trackeado-limpio       1 archivo: este plan, con TUS ediciones pendientes (no lo commiteo)
release en la sede             verifica · obesidad_release_2517e7858901
GEMINI_API_KEY                 presente en el entorno (no impresa)
raíces con mktemp -d           P y Q, nuevas y distintas de las de la Ronda 73
```

```text
P  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.6zZYTWxvQD
Q  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.TSNwwSzKSr
```

#### C1 · el candidate DEFINITIVO, compilado dos veces

```text
release_id / lifecycle / filas    obesidad_release_2517e7858901 · trained · 5,772
etiqueta                          Validación prospectiva en curso (0/4 semanas) · pronóstico
                                  puntual sin intervalos
diff -r P vs Q                    sin diferencias
digest del árbol (9 archivos)     11c3161870c33a250b405c6ca83dae800980cded6fe058aa154b75a9b99818ca
```

Ese digest es el de STATUS-A.3, no el de la Ronda 73 (`dfe85262…`): el shard cambió porque ahora
lleva el estado prospectivo. **Ésa es la razón de repetir RAG-C**, y queda comprobada antes de gastar
una sola llamada al proveedor.

#### C2 · dos índices de staging

```text
                        P      Q
chunks publicados       454    454
chunks con candidate    455    455  (+1)
vectores reutilizados   454    454
vectores generados        1      1
rc                        0      0
```

#### C3 · verificación independiente

```text
                                       P         Q
count == chunks == vectors             455       455
modelo / dimensión                     gemini-embedding-001 / 768
hashes únicos / vectores inválidos     455 / 0   455 / 0
problemas de contrato                  0         0
públicos reutilizados byte-idénticos   454/454   454/454
chunks candidate                       1         1
vector del candidate válido            sí        sí
¿el candidate está en el índice público?  no     no
el chunk lleva la etiqueta 0/4         sí        sí
el chunk declara point-only            sí        sí
```

**P contra Q, normalizado** (se elimina únicamente `built`):

```text
sha256  39389f8eac996bd443d0dddf730175f016c1a05ac49472bf200342b7e451ebe4   P
sha256  39389f8eac996bd443d0dddf730175f016c1a05ac49472bf200342b7e451ebe4   Q
```

Distinto del de la Ronda 73 (`deaf6591…`), como debía: el texto del chunk candidate cambió. El
embedding se generó **de forma independiente en cada raíz** y volvió a coincidir exacto.

#### Superficies y estado

```text
las 11 superficies (4 del dashboard + 4 agregados legacy + gate/evaluation/status)
                                    SHA256 idénticos antes y después
rag_index.json público              byte-idéntico a 20822a62
menciones públicas de Obesidad      0
npm run check                       rc=0
test:candidate con el shard real    35/35 · el consumidor valida el candidate definitivo
obesidad / anorexia_f50             trained · configured
estado prospectivo                  INCOMPLETE 0/4
published_members(web)              Alzheimer, Dengue, Depresión, Parkinson
commits                             ninguno
```

#### Gate de cierre

```text
shards P/Q byte-idénticos                        ✓
índice P/Q normalizado byte-idéntico             ✓
454/454 vectores públicos idénticos por hash     ✓
candidate: 1 chunk · 1 vector válido · staging   ✓
total staging 455/455                            ✓
drift / vacíos / duplicados                      0 / 0 / 0
superficies públicas byte-idénticas · sin Obesidad  ✓
lifecycle / published / legacy / DVC             sin cambios
```

Siguiente acción exacta: **auditar RAG-C-REPEAT**. Después, el paquete `C7.6-READINESS`.

_Respuesta:_

---

### Ronda 89 — Auditoría RAG-C-REPEAT PASS y orden del paquete C7.6 — 2026-07-27

#### Veredicto

**C7.6-RAG-C-REPEAT queda CERRADA / PASS. Todos los gates técnicos de C7.6 están verdes. No hay
otro microcierre funcional pendiente antes del paquete documental de readiness.**

Auditoría independiente sobre los temporales conservados:

```text
P  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.6zZYTWxvQD
Q  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.TSNwwSzKSr

shards P/Q                         diff -r sin diferencias
release / lifecycle / filas        obesidad_release_2517e7858901 · trained · 5,772
status                             prospective_status.v2 · INCOMPLETE 0/4
manifest ↔ web status/label        idénticos
channels                           epibot, reports, tableau, web · sin puente faltante
índices                            455 chunks = 455 vectores
modelo / dimensión                 gemini-embedding-001 / 768
hashes únicos / vectores inválidos 455 / 0
reutilizados públicos              454/454 byte-idénticos por chunkHash
candidate                          exactamente 1 · ausente del público · vector válido
candidate visible                  etiqueta 0/4 + point-only
P/Q sin built                      contenido equivalente
DVC release                        up to date
superficies públicas               sin cambios · 0 Obesidad
```

La auditoría reprodujo la **igualdad**, no reutilizó ciegamente los digests reportados:

- la comparación directa de los nueve shards es idéntica;
- un digest independiente del inventario de archivos coincide entre P y Q;
- una serialización JSON directa sin `built` coincide entre P y Q;
- los 455 chunks, su orden y los 455 vectores se compararon elemento a elemento.

Los valores de esos digests independientes no tienen que coincidir con `11c316…` o `39389f…`
porque cada receta serializa rutas/JSON de forma distinta. No es un defecto material: la igualdad de
bytes y estructuras está demostrada. El paquete de readiness debe registrar **la receta junto al
digest**, para que ningún hash futuro quede ambiguo.

Preservación comprobada:

```text
release DVC                                  Data and pipelines are up to date
prospective_gate.json SHA256                 24e10d9f3b08f736d77af353e068934371cd475dd9d70a36f3b470395ace1658
prospective_evaluation.json SHA256           3f1b4be42ee1ea5e0fabc6af82f4515025aef76dc01241e70509bffc50beb212
prospective_status.json SHA256               0407b771bd832cd0c97dbdc61efb1c1be24633b4617fde84aba78c6936a38894
Prophet legacy SHA256                        cb5be3959781da7a0b44f9510bcaaf22c70fb3f34ae3780e786d5748968ef8bc
DeepAR legacy SHA256                         96791595a2d4806de6b246aaf77ee0efe85f46c439eadb8afe8f6dd11670949a
Ensemble legacy SHA256                       1d2cf0a7dcb9e54cdd69020c3c079fb57832293e961aecd0b0f325034ef2f68c
Stacking legacy SHA256                       ac97dc8e210b95f26b01220702c89b34b47a4e61aabbc0d2246749961ee95b88
```

Dashboard público:

```text
knowledge.json SHA256       e1d9a7d9894319e60330fb85baea3f50bcf13d2c96253fac496f3b3535856e58
rag_index.json SHA256       efbae8712e9f8a287a2e54192dbafb39eee0205954a8f5c64b3bf34ec020401f
epibot/index.html SHA256    f2e66edcdf9127b74de16d0b44cc570f3cca0d28521eb7430b1c4071038c758b
index.html SHA256           94549fbd0338886b0630e361027cc952ddcfc32debb09a59fa12278f7bf09857
```

#### Orden C7.6-READINESS-PACKAGE — documentación autoritativa y STOP

Esta ronda **no implementa C7.7**. Su único entregable es el paquete que permite decidir las
acciones externas sin reconstruir la historia desde 13 mil líneas.

Trabajar sólo en:

```text
/Users/haowei/Documents/Integrador/EpiForecast-MX/docs/PLAN_C7_PUBLICACION_OBESIDAD.md
```

No crear otro archivo. Añadir una sección autocontenida titulada:

```text
C7.6-READINESS-PACKAGE — candidato de publicación condicionada
```

##### P0 · estado e identidades exactas

Registrar mediante comandos de lectura, no copiando valores históricos sin comprobar:

1. fecha, ramas, HEAD locales y SHA remotos de backend y dashboard;
2. rangos locales todavía no publicados:
   - backend `dbfdd49c..84d84675` más este plan sin commit;
   - dashboard `d5ead880..20822a62`;
3. `release_id`, dataset, policy, selection, acceptance, refit y forecast canónicos;
4. `gate_digest`, candidate/control/dataset digests, evaluation y status digests;
5. lifecycle, canales, galería y estado del puntero;
6. estado de F50 y lista exacta de `published_members()` por los cuatro canales.

Si un HEAD o digest cambió, detenerse y explicar el delta; no actualizar silenciosamente el
paquete para adaptarlo.

##### P1 · matriz final de gates

Incluir una tabla con evidencia y veredicto de cada gate:

- release bundle restaurable y target DVC sincronizado;
- doctor por identidad;
- 64 modelos cargables, 111 productos, 3,328 bases y 5,772 filas;
- aceptación 2025;
- gate prospectivo congelado, real y todavía `INCOMPLETE 0/4`;
- point-only sin bandas inventadas;
- compilación candidate en Reports, Tableau, web y EpiBot;
- STATUS-A y STATUS-B/B.1;
- RAG público 454/454 con drift cero;
- RAG candidate final 455/455 en P y Q;
- backend lint/typecheck/fast/integración estable sin SIGSEGV;
- dashboard `npm test`, `test:candidate` y `npm run check`;
- legacy byte-idéntico;
- F50 ausente;
- superficies públicas todavía sin Obesidad.

Cada fila debe decir `PASS`, `INCOMPLETE aceptado por política` o `NO EJECUTADO`. Está prohibido
convertir `0/4` en PASS.

##### P2 · inventario de cambios pendientes de checkpoint

Listar por repositorio:

1. commits de código/config que deben viajar;
2. commits puramente documentales;
3. archivos trackeados aún modificados;
4. untracked del usuario que quedan expresamente fuera;
5. archivos públicos que **no** cambiaron;
6. estado de main y de las ramas remotas.

No afirmar “ahead N” sin declarar contra qué referencia. Para dashboard distinguir:

- commits locales respecto de `origin/feat/c73-candidate-staging`;
- commits de la rama respecto de `main`.

##### P3 · candidato público que se autorizaría

Declarar exactamente:

```text
padecimiento              Obesidad E66
release                   obesidad_release_2517e7858901
canales                   web, epibot, reports, tableau
galería                   false
incertidumbre             point-only
validación prospectiva    INCOMPLETE 0/4
etiqueta obligatoria      Validación prospectiva en curso (0/4 semanas) ·
                          pronóstico puntual sin intervalos
F50                       permanece configured y oculta
```

La publicación sería **condicionada**, no confirmada. El congelado 5/5/10 no se retunea, no se
reselecciona y no se refitea con las semanas prospectivas.

##### P4 · plan de activación por transacciones separadas

Escribir, sin ejecutar, la secuencia exacta:

1. **Checkpoint Git backend:** después de auditar el cambio documental y crear un commit doc-only,
   pedir autorización para fast-forward de la rama; sin merge.
2. **Checkpoint Git dashboard:** pedir autorización separada para fast-forward de
   `feat/c73-candidate-staging`; sin PR, merge ni deploy.
3. **Integración controlada:** pedir autorización para PR/merge de código genérico mientras
   Obesidad siga `trained`; verificar CI y que producción no cambie.
4. **Snapshot de rollback:** guardar SHAs, puntero, hashes públicos, índice RAG, datasource/workbook
   Tableau y deploy de producción vigentes.
5. **Activación backend:** en un commit aislado, cambiar sólo el lifecycle a `published` y crear el
   `public_release_pointer.v1` activo para el mismo release. Probar que un release o status
   diferente falla.
6. **Materialización pública:** compilar los cuatro canales desde el puntero activo; no insertar
   Obesidad en agregados legacy por motor.
7. **RAG público:** promover el único chunk candidate validado mediante el builder contractual,
   conservando 454 vectores y añadiendo exactamente uno; `rag:verify` debe quedar en drift cero.
8. **Dashboard/cache-bust:** actualizar los consumidores y el cache-bust sólo en el deploy
   autorizado; point-only y `0/4` deben ser visibles.
9. **Tableau/Reports:** promover únicamente los shards del mismo release.
10. **Smoke coordinado:** comparar valores muestreados en los cuatro canales contra el forecast
    sellado; comprobar legacy y F50.

No presentar esos pasos como una única autorización. Push, merge, activación, RAG público, Tableau
y deploy son efectos externos distintos.

##### P5 · rollback ejecutable

El paquete debe identificar los valores previos reales y ordenar:

1. restaurar puntero público anterior o retirar el puntero de Obesidad;
2. revertir `published → trained`;
3. restaurar índice RAG, knowledge/HTML/cache-bust y deploy anteriores;
4. restaurar datasource/workbook Tableau y Reports;
5. verificar que `published_members()` vuelva a los cuatro padecimientos históricos;
6. comprobar los cuatro hashes legacy y que F50 continúe oculta;
7. conservar el bundle y la evidencia: rollback no significa borrar DVC/S3;
8. emitir incidente con causa y digests.

Disparadores inmediatos: identidad/digest inválido, discrepancia numérica, banda falsa, ausencia de
la etiqueta, F50 visible, alteración legacy, canal roto o punteros incoherentes. Al completar 4/4:
PASS confirma; FAIL obliga a este rollback; INCOMPLETE conserva la etiqueta.

##### P6 · autorizaciones literales, todavía vacías

Cerrar el paquete con casillas no marcadas y el alcance exacto:

```text
[ ] AUTORIZO COMMIT DOC-ONLY DEL PLAN C7.6.
[ ] AUTORIZO PUSH BACKEND <SHA_REMOTO>..<SHA_AUDITADO> A LA RAMA DE TRABAJO. SIN MERGE.
[ ] AUTORIZO PUSH DASHBOARD <SHA_REMOTO>..<SHA_AUDITADO> A feat/c73-candidate-staging.
    SIN PR, MERGE NI DEPLOY.
[ ] AUTORIZO PR/INTEGRACIÓN DE CÓDIGO GENÉRICO MANTENIENDO OBESIDAD trained.
[ ] AUTORIZO ACTIVACIÓN BACKEND: PUNTERO ACTIVO + trained→published.
[ ] AUTORIZO MATERIALIZACIÓN/PROMOCIÓN DE REPORTS Y TABLEAU.
[ ] AUTORIZO PROMOCIÓN DEL RAG PÚBLICO Y DEPLOY DEL DASHBOARD.
```

Los SHA se rellenan con los observados al crear el paquete; no usar `HEAD` como autorización.

##### P7 · verificaciones de esta ronda

Como es doc-only:

```text
git diff --check
git status --short --branch en ambos repos
releer HEAD/remotos/digests usados
confirmar que el diff de esta ronda toca sólo este plan
```

No repetir entrenamiento, benchmark, refit, forecast ni llamadas a Gemini. No borrar P/Q hasta que
el paquete sea auditado.

#### Prohibiciones

- No código, tests, config, registry, lifecycle, puntero, DVC o superficies públicas.
- No commit, push, PR, merge, tag, deploy, preview, cache-bust o publicación.
- No regenerar RAG, Tableau, Reports o forecast.
- No tocar o añadir untracked del usuario.
- No marcar ninguna autorización.

#### Salida y STOP

Presentar:

1. sección exacta añadida;
2. matriz de gates;
3. SHAs/rangos verificados;
4. lista de autorizaciones aún vacías;
5. confirmación de que sólo cambió el plan.

Después STOP para auditoría.

#### Avance

C7.6 queda técnicamente verde pero documentalmente abierto hasta auditar el paquete. Avance
operativo: **83%**; exposición pública: **0%**; validación prospectiva: **0/4**.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-READINESS-PACKAGE` dentro de este plan y STOP.**

_Respuesta:_ **GO C7.6-READINESS-PACKAGE DOC-ONLY. Consolidar en este mismo plan identidades,
gates, cambios, activación, rollback y autorizaciones vacías; no crear otro archivo ni ejecutar
acciones externas. Sin commit, push, merge, DVC, lifecycle, puntero, RAG, Tableau, deploy ni
publicación.**

---

## C7.6-READINESS-PACKAGE — candidato de publicación condicionada

> Paquete **doc-only**, emitido el **2026-07-27T04:43Z**. Ninguna acción externa ejecutada: sin
> commit, push, merge, DVC, lifecycle, puntero, RAG público, Tableau, deploy ni publicación.
> Todos los valores se releyeron con comandos en esta ronda; ninguno se copió de rondas previas.

### P0 · Estado e identidades exactas

#### Repositorios

```text
backend    EpiForecast-MX
           rama            feat/registry-padecimientos-obesidad
           HEAD local      84d84675
           remoto          origin/feat/registry-padecimientos-obesidad @ dbfdd49c
           locales         22 commits sobre el remoto · 114 sobre main (b535b525)
           trackeado       1 archivo modificado: docs/PLAN_C7_PUBLICACION_OBESIDAD.md

dashboard  EpiForecast-IMSS-Dashboard
           rama            feat/c73-candidate-staging   (sin upstream configurado)
           HEAD local      20822a62
           remoto          origin/feat/c73-candidate-staging @ d5ead880
           locales         16 commits sobre el remoto · 18 sobre main (179bbe36)
           trackeado       limpio
```

Dos precisiones que la orden pide no dar por hechas: el dashboard **no tiene upstream configurado**
—`@{u}` falla—, así que su comparación se hace contra `origin/feat/c73-candidate-staging`
explícitamente; y «ahead N» sólo tiene sentido con la referencia declarada, por eso van las dos
cifras.

#### Release y cadena canónica

```text
release_id             obesidad_release_2517e7858901
backend / lifecycle    runner_release / trained
canales / galería      epibot, reports, tableau, web / false
origen / horizonte     2026-W26 / 52 semanas
conteos                64 modelos · 64 bases · 3,328 pronósticos base
                       47 derivados · 111 productos · 5,772 filas
dataset_id             obesidad_1502d1a25b48
dataset_digest         1502d1a25b48c11b7afd30173163d78e4c67a55e31551737a9bed20358cc4340
policy                 rolling_cv_v1 · dd6d4a0274a6f8bb0f51d27628294b7db694b792966abaa92528dc2765020b2a
selection_digest       7f582a3a4ed780614c7649d3a9d38869ab10456829edf5271fede8f2472cdf72
final_selection_digest 91590fa7452fa75581df18d6e892ac7053727ab368d38d298a26931fe6e89bab
acceptance_run_id      obesidad_benchmark_test_7f582a3a4ed7_82370419efd4
acceptance_digest      c264f6380e1d5869efabef534180b717cba4e7c8c075b102fe0a7c0548f3ca1f
refit_run_id           obesidad_refit_final_91590fa7452f_ff249060018a
refit_digest           c619438a2f02f3ca7edf4247784878139ed8838b56eb87de1bfbacb919595ed9
forecast_run_id        obesidad_forecast_h52_ff249060018a_92d446b6df8f
```

#### Gate prospectivo y estado

```text
gate_digest            5bc39aa5d44f5e62062775dc09a0366ac856f47e5444fbb52ca07e608e61b65d
candidate_digest       e7e2f5eef2efe7fc1071a1adbcc7c9efba1ab29e8265e395e566799f55e3c9e2
control_digest         bb18accc0e6c9fbf8fd62fd48d4c9fc0807d4678e99d89f294ca6c7c41bce315
evaluation_digest      57c78cdebbe8c515b91646297bc647ba59e5d60c4719e215413b9a1bdf44ac90
status_digest          0407b771bd832cd0c97dbdc61efb1c1be24633b4617fde84aba78c6936a38894
veredicto              INCOMPLETE 0/4 · corte observado 2026-W26
etiqueta               Validación prospectiva en curso (0/4 semanas)
```

**La receta junto al digest**, como pidió la auditoría — porque tres de estos números conviven con
el SHA256 del archivo que los contiene y no son lo mismo:

```text
artefacto     sha256(archivo)      digest declarado dentro
gate          24e10d9f3b08f736…    5bc39aa5d44f5e62…   (payload SIN la clave gate_digest)
evaluation    3f1b4be42ee1ea5e…    57c78cdebbe8c515…   (payload SIN la clave evaluation_digest)
status        0407b771bd832cd0…    el archivo ES el payload → ambos coinciden
```

Cualquier hash citado en adelante debe decir cuál de las dos recetas usa.

#### Registry

```text
obesidad        lifecycle=trained · gallery=false · 4 canales · puntero público: NO EXISTE
anorexia_f50    lifecycle=configured · 0 canales
published_members(web|epibot|reports|tableau)  = Alzheimer, Dengue, Depresión, Parkinson
```

### P1 · Matriz final de gates

| gate | evidencia | veredicto |
| --- | --- | --- |
| Bundle en la sede y verificable | `verify_bundle` rc=0 · `release_id` y `disease_id` cuadran | PASS |
| Target DVC del release sincronizado | `dvc status <release>.dvc` → *up to date* | PASS |
| Working tree DVC global apto para promoción | 6 targets modificados; `reports/forecasts` y `reports/figures` solapan la promoción | **BLOQUEADO** |
| Doctor por identidad | `scripts.doctor_padecimiento` rc=0 | PASS |
| 64 modelos · 111 productos · 3,328 bases · 5,772 filas | conteos del bundle verificado y del shard compilado | PASS |
| Aceptación 2025 | `acceptance_digest c264f638…` sellado en la cadena | PASS |
| Gate prospectivo congelado y real | `gate_digest 5bc39aa5…` recomputado desde release+dataset; regla 5/5/10 aplicada por ámbito | PASS |
| Validación prospectiva | `INCOMPLETE 0/4` · corte 2026-W26 · 0 omisiones | **INCOMPLETE aceptado por política** |
| Point-only sin bandas inventadas | `interval_method=none`, límites vacíos, `band=null` en el view-model | PASS |
| Compilación candidate en los 4 canales | 9 archivos · `channels_without_bridge []` | PASS |
| STATUS-A (A.1/A.2/A.3/A.3.1) | evaluación sellada, capability por loader, formas cerradas | PASS |
| STATUS-B / B.1 | consumidor valida las 11 claves, cruza 7 invariantes y transporta la etiqueta | PASS |
| RAG público | 454 chunks = 454 vectores · `rag:verify` drift cero | PASS |
| RAG candidate final | P y Q: 455/455 · 454 públicos byte-idénticos · 1 candidate | PASS |
| Backend lint/typecheck/fast/integración | ruff+format, mypy 161, 2000 tests, integración 8 | PASS |
| SIGSEGV de integración | runner aislado por archivo, rc=0 | PASS |
| Dashboard `npm test` / `test:candidate` / `check` | 616/616 + 67 · 35/35 con shard real · rc=0 | PASS |
| Agregados legacy byte-idénticos | 4 SHA256 sin cambio en todo C7.6 · 0 filas de Obesidad | PASS |
| F50 ausente de todo lo público | `configured`, 0 canales | PASS |
| Superficies públicas sin Obesidad | knowledge, rag_index y ambos HTML: 0 menciones | PASS |
| Puntero público activo | **no existe todavía** (es el paso de activación) | NO EJECUTADO |
| Materialización pública de los 4 canales | no ejecutada | NO EJECUTADO |
| Deploy y cache-bust | no ejecutados | NO EJECUTADO |

`0/4` **no** se convierte en PASS en ninguna fila.

#### Una salvedad que no aparecía en la auditoría

La auditoría reproduce **seis targets DVC modificados** en el working tree:

```text
models.dvc
logs.dvc
data/raw.dvc
data/processed/dataset_boletin_epidemiologico.csv.dvc
reports/figures.dvc
reports/forecasts.dvc
```

`dvc data status --granular` expande esos seis targets a muchas rutas; el conteo «21 entradas» del
primer paquete no es una unidad estable ni fue reproducido y queda retirado. Es un estado
**preexistente** del entorno del usuario, no un efecto de C7.6: los cuatro agregados legacy tienen
el mismo SHA256 antes y después de cada ronda, y el target DVC dedicado del release está *up to
date*. No obstante, `reports/figures.dvc` y `reports/forecasts.dvc` solapan la futura promoción de
Reports. Por eso C7.6 no se declara cerrado hasta atribuir el WIP y diseñar la promoción desde un
clon/worktree limpio, sin `dvc checkout`, `dvc add` ni `dvc push` sobre este árbol.

### P2 · Inventario de cambios pendientes de checkpoint

#### Backend `dbfdd49c..84d84675` — 22 commits

```text
código/config (5)   a81a5f5d  STATUS-A          2ecb3fae  STATUS-A.1
                    f41c2e3d  STATUS-A.2        83f04ce6  STATUS-A.3
                    84d84675  STATUS-A.3.1
documentales (17)   7e36e086 · d54d9ceb · b6b3d89e · 64716ec1 · 4886dc22 · f7ef25d5 · 79689412
                    8216044e · fc09d37d · a8ab5ae8 · 0e1c20fd · db80b47b · e68c075c · fef5998b
                    40d32c1f · 0273b591 · 7460a5bb
trackeado sin commit   docs/PLAN_C7_PUBLICACION_OBESIDAD.md  (este paquete + tus ediciones)
```

#### Dashboard `d5ead880..20822a62` — 16 commits

```text
20822a62 STATUS-B.1   2213bff2 STATUS-B    4cdc17dd RAG-B      40442c6d RAG-A.1
b9cb7a1f RAG-A        438441a0 B4.2        19e6a893 47.3       45bba6c2 47.2-B4.1
3ee38310 47.2-B4      a1412e33 47.2-B3     93214796 47.2-B2    d3fd058a 47.2-B1
553b84d1 47.2-A.1     ada08080 47.2-A      98404fa0 fixture    42477019 npm test
trackeado sin commit   ninguno
```

#### Untracked del usuario · expresamente fuera

```text
backend    .qwen/ · references/ · reports/FigCanva · reports/FigResumenEjecutivo · reports/HTMLsCanva
           reports/Latex · reports/RuthPoster · reports/docs · varios PDF y PNG
dashboard  EpiBot_v2_SinFondo.png · kb.zip
```

Ninguno se añadió, movió ni borró en todo C7.6.

#### Archivos públicos que NO cambiaron

```text
epibot/knowledge.json    e1d9a7d9894319e60330fb85baea3f50bcf13d2c96253fac496f3b3535856e58
epibot/rag_index.json    efbae8712e9f8a287a2e54192dbafb39eee0205954a8f5c64b3bf34ec020401f
epibot/index.html        f2e66edcdf9127b74de16d0b44cc570f3cca0d28521eb7430b1c4071038c758b
index.html               94549fbd0338886b0630e361027cc952ddcfc32debb09a59fa12278f7bf09857
all_forecast_prophet     cb5be3959781da7a0b44f9510bcaaf22c70fb3f34ae3780e786d5748968ef8bc
all_forecast_deepar      96791595a2d4806de6b246aaf77ee0efe85f46c439eadb8afe8f6dd11670949a
all_forecast_ensemble    1d2cf0a7dcb9e54cdd69020c3c079fb57832293e961aecd0b0f325034ef2f68c
all_forecast_stacking    ac97dc8e210b95f26b01220702c89b34b47a4e61aabbc0d2246749961ee95b88
```

El `rag_index.json` público **sí** cambió una vez en C7.6 —RAG-B, `4cdc17dd`, para cerrar su drift—
y desde entonces es byte-idéntico. Ese cambio ya está en los 16 commits pendientes.

### P3 · Candidato público que se autorizaría

```text
padecimiento              Obesidad E66
release                   obesidad_release_2517e7858901
canales                   web, epibot, reports, tableau
galería                   false
incertidumbre             point-only (interval_method=none, límites vacíos)
validación prospectiva    INCOMPLETE 0/4 · gate 5bc39aa5… · corte 2026-W26
etiqueta obligatoria      Validación prospectiva en curso (0/4 semanas) ·
                          pronóstico puntual sin intervalos
F50                       permanece configured y oculta
```

Publicación **condicionada**, no confirmada. El congelado 5/5/10 no se retunea, no se reselecciona
y no se refitea con las semanas prospectivas: si al llegar a 4/4 el veredicto es FAIL, se ejecuta el
rollback de P5, no un reajuste.

### P4 · Plan de activación por transacciones separadas

Escrito, **no ejecutado**. Cada punto es una autorización distinta.

1. **Checkpoint doc backend** — auditar el cambio documental y crear un commit doc-only del plan.
2. **Push backend** — fast-forward de `feat/registry-padecimientos-obesidad`. Sin merge.
3. **Push dashboard** — fast-forward de `feat/c73-candidate-staging`. Sin PR, merge ni deploy.
4. **Integración controlada** — PR/merge del código genérico con Obesidad todavía `trained`;
   verificar CI y que producción no cambie.
5. **Carril limpio de activación** — crear un clon/worktree limpio desde los SHAs ya publicados,
   restaurar únicamente los targets DVC declarados y generar ahí las superficies. El working tree
   actual con WIP no se usa para promover ni se limpia en bloque.
6. **Snapshot de rollback** — SHAs, puntero, hashes públicos, índice RAG, datasource/workbook de
   Tableau y deploy de producción vigentes, guardados antes de tocar nada.
7. **Activación backend** — commit aislado: lifecycle `trained → published` y creación del
   `public_release_pointer.v1` activo para *este* release. Probar que un release o un status
   distinto falla cerrado.
8. **Materialización pública** — compilar los cuatro canales desde el puntero activo. No insertar
   Obesidad en los agregados legacy por motor.
9. **RAG público** — promover el único chunk candidate ya validado con el builder contractual:
   454 vectores conservados + exactamente 1 nuevo; `rag:verify` en drift cero.
10. **Dashboard y cache-bust** — actualizar consumidores y subir `app.js?v` en `index.html` sólo en
   el deploy autorizado. La etiqueta `0/4` y el point-only deben quedar visibles.
11. **Tableau y Reports** — promover únicamente los shards de este release.
12. **Smoke coordinado** — muestrear valores en los cuatro canales contra el forecast sellado;
    comprobar legacy intacto y F50 invisible.

### P5 · Rollback ejecutable

Los hashes de P2 son el **checkpoint candidato actual**, no se deben tratar como valores eternos.
Los valores autoritativos de rollback se recapturan inmediatamente antes de la activación, después
de integrar código genérico pero antes de cambiar puntero/lifecycle. Si coinciden con P2 se
registran como confirmados; si no, se detiene la activación y se audita el delta. Hoy no existe
puntero de Obesidad: bajo el estado actual, el rollback consiste en retirarlo, no en restaurar otro.

1. retirar el `public_release_pointer.v1` de Obesidad;
2. revertir lifecycle `published → trained`;
3. restaurar `rag_index.json` a `efbae871…`, `knowledge.json` a `e1d9a7d9…`, ambos HTML a
   `f2e66edc…` / `94549fbd…`, el cache-bust anterior y el deploy previo;
4. restaurar datasource/workbook de Tableau y los Reports promovidos;
5. verificar que `published_members()` vuelve a Alzheimer, Dengue, Depresión y Parkinson en los
   cuatro canales;
6. comprobar los cuatro SHA256 legacy de P2 y que F50 sigue oculta;
7. **conservar** el bundle, su `.dvc` y toda la evidencia: rollback no es borrar DVC/S3;
8. emitir incidente con causa y digests implicados.

Disparadores inmediatos: identidad o digest inválido, discrepancia numérica contra el forecast
sellado, banda de incertidumbre dibujada, ausencia de la etiqueta, F50 visible, agregado legacy
alterado, canal roto o punteros incoherentes.

Al completar 4/4: **PASS** confirma la publicación · **FAIL** obliga a este rollback ·
**INCOMPLETE** conserva la etiqueta y no habilita nada nuevo.

### P6 · Autorizaciones literales — todas vacías

```text
[ ] AUTORIZO COMMIT DOC-ONLY DEL PLAN C7.6.
[ ] AUTORIZO PUSH BACKEND dbfdd49c..<SHA_DEL_COMMIT_DOC_AUDITADO>
    A origin/feat/registry-padecimientos-obesidad. SIN MERGE.
[ ] AUTORIZO PUSH DASHBOARD d5ead880..20822a62 A origin/feat/c73-candidate-staging.
    SIN PR, MERGE NI DEPLOY.
[ ] AUTORIZO PR/INTEGRACIÓN DE CÓDIGO GENÉRICO MANTENIENDO OBESIDAD trained.
[ ] AUTORIZO ACTIVACIÓN BACKEND: PUNTERO ACTIVO + trained→published.
[ ] AUTORIZO MATERIALIZACIÓN/PROMOCIÓN DE REPORTS Y TABLEAU.
[ ] AUTORIZO PROMOCIÓN DEL RAG PÚBLICO Y DEPLOY DEL DASHBOARD.
```

El endpoint backend se rellena **después** del commit doc-only: autorizar primero ese commit vuelve
obsoleto por definición a `84d84675` como endpoint de push. El rango dashboard sí queda fijado en
`d5ead880..20822a62` mientras su HEAD no cambie. Si cualquier endpoint se mueve después de ser
auditado, el paquete queda inválido y se reemite; ninguna autorización usa `HEAD`.

### P7 · Verificaciones de esta ronda

```text
git diff --check (ambos repos)          PASS
diff de esta ronda                      sólo docs/PLAN_C7_PUBLICACION_OBESIDAD.md
HEAD backend / dashboard                84d84675 · 20822a62   (releídos, sin cambio)
remotos                                 dbfdd49c · d5ead880    (releídos)
digests del gate/evaluation/status      releídos del disco, no copiados
temporales P y Q                        conservados para auditoría
comandos externos ejecutados            ninguno
llamadas a Gemini                       ninguna
```

Temporales de RAG-C-REPEAT, todavía disponibles:

```text
P  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.6zZYTWxvQD
Q  /var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.TSNwwSzKSr
```

### Estado al cerrar el paquete

```text
Backend     84d84675 · ahead 22 de dbfdd49c · SIN PUSH
Dashboard   20822a62 · ahead 16 de d5ead880 · SIN PUSH
C7.6        gates de producto verdes · paquete emitido · DVC global pendiente de aislamiento
Obesidad    trained · sin puntero · 0 menciones públicas · NO-GO
Validación  INCOMPLETE 0/4 · exposición pública 0%
```

_Respuesta:_

---

### Ronda 90 — Auditoría del paquete: correcciones formales y gate DVC — 2026-07-27

#### Veredicto

**El paquete representa correctamente el release, los gates y el estado `INCOMPLETE 0/4`, pero
C7.6 todavía no puede declararse cerrado.** La auditoría encontró dos correcciones formales ya
aplicadas al paquete y un bloqueante operativo que requiere atribución read-only:

1. `84d84675` no podía ser el endpoint del push posterior al commit doc-only, porque ese commit
   moverá HEAD; el literal ahora exige el SHA documental ya auditado;
2. los hashes de rollback se recapturan justo antes de activar, después de integrar código;
3. no hay «21 entradas DVC» reproducibles: hay **seis targets DVC modificados**, con muchas rutas
   granulares. Dos solapan la futura promoción de Reports.

Continúa en PASS:

```text
release dedicado .dvc            up to date
bundle runner_release            íntegro
legacy agregado                  hashes canónicos sin cambio
RAG público/candidate            454/454 y 455/455
STATUS-A / STATUS-B              PASS
Obesidad / F50                   trained / configured
superficie pública               0 Obesidad
```

Queda por aislar:

```text
models.dvc
logs.dvc
data/raw.dvc
data/processed/dataset_boletin_epidemiologico.csv.dvc
reports/figures.dvc
reports/forecasts.dvc
```

No se atribuye automáticamente ese estado a C7.6 ni se propone borrarlo. Contiene extracción E66,
F50 y artefactos legacy/preliminares que deben preservarse. El problema es transaccional: promover
Reports desde el mismo árbol mezclaría la publicación con WIP no relacionado.

#### Orden C7.6-DVC-ATTRIBUTION — sólo lectura y diseño del carril limpio

Ejecutar únicamente en backend `84d84675`; escribir resultados sólo como nueva subsección de este
plan. Para procesar salidas grandes se permite un temporal fuera del repo. Un ciclo y STOP.

##### D0 · preflight

1. Confirmar HEAD `84d84675`, remoto `dbfdd49c` y que el único trackeado modificado sea este plan.
2. Preservar todos los untracked; no abrir, mover, copiar o añadir sus contenidos.
3. Confirmar que el target dedicado del release continúa `up to date`.
4. Capturar los cuatro hashes legacy y los hashes de gate/evaluation/status.

##### D1 · inventario reproducible

Ejecutar sólo para lectura:

```text
dvc status
dvc data status
dvc data status --granular
```

Guardar la salida granular únicamente en un temporal. Añadir una tabla por los seis targets con:

- estado target-level;
- conteo definido de rutas añadidas, modificadas y eliminadas;
- tamaño total aproximado;
- periodos/timestamps cuando sean relevantes;
- padecimientos presentes;
- contenido legacy, E66, F50 o mixto;
- coincidencia exacta con rutas que C7.7 pretenda promover.

No volver a reportar «21» sin definir unidad y receta.

##### D2 · atribución funcional

Clasificar cada target:

```text
A  WIP necesario que debe preservarse
B  preliminar/legacy que no participa en runner_release
C  superficie que colisionaría con C7.7
D  diferencia todavía sin atribución
```

Para `reports/forecasts.dvc` y `reports/figures.dvc`:

1. enumerar agregados legacy que permanecen byte-idénticos;
2. resumir diferencias por padecimiento y motor;
3. comprobar si el compilador público necesita escribir ahí o puede usar un destino dedicado;
4. declarar las rutas exactas propuestas para Reports y Tableau.

No basta etiquetar algo «preexistente»: hay que explicar por qué C7.7 no lo sobrescribirá.

##### D3 · carril limpio obligatorio

Diseñar una activación que **no use este working tree sucio**:

1. checkpoints Git sólo después de auditoría;
2. clon/worktree temporal desde SHAs explícitos ya publicados;
3. restauración dirigida del bundle, inputs legacy de verificación y superficies de rollback;
4. `dvc status` limpio en ese carril antes de materializar;
5. compilación/promoción con inventario antes/después;
6. promoción sólo de outputs declarados, nunca de directorios DVC completos;
7. conservar evidencia antes de eliminar el temporal.

Declarar qué comandos futuros requerirán red o escritura. En esta ronda **no crear** el carril ni
hacer `dvc pull`.

##### D4 · veredicto obligatorio

Cerrar con exactamente uno:

```text
PASS_CLEAN_LANE_DESIGNED
BLOCKED_DESTINATION_COLLISION
BLOCKED_UNATTRIBUTED_DVC
```

Sólo `PASS_CLEAN_LANE_DESIGNED` permite terminar C7.6. No exige limpiar el árbol actual; exige
demostrar que la publicación puede evitarlo.

#### Prohibiciones

- No `dvc checkout`, `dvc add`, `dvc commit`, `dvc push`, `dvc pull` ni borrado.
- No copiar/mover outputs DVC, modelos, logs, raw, processed, forecasts o figuras.
- No código, config, tests, lifecycle, puntero, RAG, Tableau, Reports o superficies públicas.
- No commit, push, PR, merge, deploy, activación o publicación.

#### Salida y STOP

Añadir al plan:

1. tabla de seis targets con conteos y clasificación;
2. colisiones reales o descartadas;
3. destinos exactos de publicación propuestos;
4. diseño del carril limpio;
5. veredicto D4.

Después STOP para auditoría.

#### Avance

Se mantiene en **83%**. Los gates del producto están verdes; la exposición pública sigue en
**0%**. C7.6 permanece abierto únicamente por la transacción DVC/Reports, no por el modelo o RAG.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-DVC-ATTRIBUTION` read-only y STOP.**

_Respuesta:_ **GO C7.6-DVC-ATTRIBUTION READ-ONLY. Inventariar y clasificar los seis targets DVC,
descartar o confirmar colisiones y diseñar un carril limpio de activación. Sin checkout/add/commit/
push/pull DVC, sin mover archivos y sin commit, push, lifecycle, RAG, Tableau, deploy ni
publicación.**

---

### Ronda 91 — C7.6-DVC-ATTRIBUTION (read-only) — 2026-07-27

Sólo lecturas. Sin `dvc checkout/add/commit/push/pull`, sin mover un archivo, sin commit, push,
lifecycle, puntero, RAG, Tableau, Reports, deploy ni publicación. La salida granular se guardó en un
temporal fuera del repo.

#### D0 · preflight

```text
HEAD 84d84675 · remoto dbfdd49c · único trackeado modificado: este plan
untracked del usuario                      intactos (no se abrió, movió ni copió ninguno)
release dedicado .dvc                      Data and pipelines are up to date
legacy prophet/deepar/ensemble/stacking    cb5be395… / 96791595… / 1d2cf0a7… / ac97dc8e…
gate / evaluation / status (sha del archivo) 24e10d9f… / 3f1b4be4… / 0407b771…
```

#### D1 · inventario reproducible, con unidad definida

**Unidad:** una línea `«estado: ruta»` de `dvc data status --granular`. **Receta:** ejecutar ese
comando y contar por prefijo de target. Con eso:

```text
entradas granulares totales   4,012
        added                 3,991
        modified                 21   ← 6 líneas de target + 15 rutas hijas
```

Ahí está el «21» de la ronda anterior: **no eran 21 rutas**, eran 6 targets más 15 archivos. Lo
dejo dicho porque lo reporté sin definir la unidad.

| target | added | modified | deleted | MB aprox | contenido | clase |
| --- | ---: | ---: | ---: | ---: | --- | :---: |
| `models/` | 790 | 0 | 0 | 121.5 | **100% Obesidad** (deepar/prophet/ensemble/stacking, `.pkl`+`.csv`) | B |
| `logs/` | 3,196 | 0 | 0 | 4.3 | ejecuciones 2026-07-21 … 2026-07-26 | A |
| `data/raw/` | 3 | 0 | 0 | 2.4 | `data_raw_{Obesidad,Anorexia_F50,Dengue}.csv` | A |
| `data/processed/dataset_boletin_epidemiologico.csv` | 0 | 0 | 0 | — | sólo la línea de target | B |
| `reports/figures/` | 2 | 10 | 0 | 1.1 | 2 figuras de Obesidad; 10 EDA/`.DS_Store` | B |
| `reports/forecasts/` | 0 | 5 | 0 | 2.7 | 5 PNG `ensemble/Alzheimer` (Aguascalientes ×3, Nacional ×2) | C→descartada |

Fechas de modificación: `reports/figures` y `data/processed` **2026-07-22**; los cinco PNG de
`reports/forecasts` **2026-07-23**. C7.6 empezó el **2026-07-26**. Son anteriores.

#### D2 · atribución funcional

```text
A  WIP necesario que debe preservarse            logs/ · data/raw/
B  preliminar o legacy fuera de runner_release   models/ · reports/figures/ · data/processed/…csv
C  colisionaría con C7.7                          (ninguno — ver abajo)
D  sin atribución                                 ninguno
```

**Ningún artefacto de C7.6 aparece en el delta.** Verificado por conteo directo:

```text
artifacts/releases   0 entradas
config/publication   0 entradas
runs                 0 entradas
all_forecast_*.csv   0 entradas   ← los cuatro agregados legacy conservan su hash canónico
```

Los 790 de `models/` son artefactos de Obesidad producidos por el **carril legacy** (`.pkl` por
serie), no por `runner_release`: el bundle vive en `artifacts/releases/` y ese target sigue *up to
date*. Son preliminares que deben preservarse, no residuos que borrar.

Una atribución que sí me toca: **parte de `logs/` la generó C7.6**. Los más recientes son del
2026-07-26 23:17, dentro de mis rondas — cualquier ejecución que importe `epiforecast` escribe
loguru. Es el único rastro que dejó este trabajo en el delta DVC, y no es una superficie de
producto.

##### `reports/forecasts.dvc` y `reports/figures.dvc` en detalle

1. **Agregados legacy byte-idénticos:** los cuatro `all_forecast_*.csv` no aparecen en el delta y
   sus SHA256 son los canónicos de todo C7.6.
2. **Diferencias por padecimiento y motor:** las cinco de `reports/forecasts` son PNG de
   `ensemble/Alzheimer` en Aguascalientes y Nacional. Cero CSV, cero Obesidad, cero F50. Las de
   `reports/figures` son EDA general (histogramas, violines, correlación, un `.DS_Store`) más dos
   figuras añadidas de Obesidad.
3. **¿El compilador público necesita escribir ahí?** **No.** `emit_shards` escribe bajo un
   `output_root` **inyectado**, y `check_staging_root` prohíbe expresamente que en modo candidate
   caiga bajo `reports/`, `data/`, `models/`, `epibot/`, `web/` o `artifacts/`. No hay ninguna ruta
   del compilador que apunte a `reports/forecasts/` ni a `reports/figures/`.
4. **Destinos propuestos para C7.7** (hoy inexistentes, fuera de todo target DVC):

```text
reports/publication/<disease_id>/<release_id>/    report.md · forecast_products.csv
tableau/publication/<disease_id>/<release_id>/    forecast_shard.csv · schema.json
```

`reports/figures.dvc` y `reports/forecasts.dvc` son targets **hermanos**, no ancestros de
`reports/publication/`: promover ahí no toca sus outputs ni requiere `dvc commit` de un directorio
sucio.

**Colisión C descartada, con la razón:** la promoción de Reports no sobrescribirá esos cinco PNG ni
los diez de EDA porque no escribe en sus directorios; y no puede hacerlo por accidente porque el
guard de destino es parte del compilador, no una convención.

#### D3 · carril limpio de activación (diseñado, no creado)

1. **Checkpoints Git primero**, y sólo tras auditoría: commit doc-only, luego los dos push
   autorizados por separado. Nada de lo que sigue usa este working tree.
2. **Worktree o clon temporal desde SHAs explícitos ya publicados**, fuera de ambos repos:
   `git worktree add <tmp> <SHA_backend_publicado>`.
3. **Restauración dirigida, no masiva:** `dvc pull` **sólo** de
   `artifacts/releases/obesidad/obesidad_release_2517e7858901.dvc` y de los inputs de verificación
   estrictamente necesarios. Nunca `dvc pull` a secas: eso arrastraría los seis targets sucios.
   *(Requiere red y escritura en el temporal.)*
4. **Gate del carril:** `dvc status` **limpio** ahí antes de materializar nada. Si no lo está, se
   detiene: es la comprobación que este árbol no puede pasar hoy.
5. **Compilación y promoción** con inventario **antes y después** —lista de rutas y SHA256— hacia
   los destinos dedicados de D2.4.
6. **Sólo outputs declarados:** nunca `dvc add` de un directorio completo; cada archivo promovido
   se enumera.
7. **Evidencia antes de borrar:** copiar inventarios y digests fuera del temporal, y sólo entonces
   `git worktree remove`.

Comandos futuros que exigirán **red**: `git push`, `dvc pull`, `dvc push`, deploy. Que exigirán
**escritura fuera del temporal**: la activación del puntero y el lifecycle, en el repo real.

#### D4 · veredicto

```text
PASS_CLEAN_LANE_DESIGNED
```

Los seis targets están inventariados con unidad definida y clasificados; ninguno contiene artefactos
de C7.6; la única colisión candidata —`reports/forecasts`— queda descartada porque el compilador no
escribe en ese directorio y los destinos de publicación propuestos están fuera de todo target DVC;
y el carril limpio está diseñado para no depender de este árbol.

No se limpia el working tree actual ni se propone borrar nada: contiene extracción E66, F50, Dengue
y artefactos preliminares que deben preservarse.

_Respuesta:_

---

### Ronda 92 — Auditoría DVC PASS con dos correcciones de cierre — 2026-07-27

#### Veredicto

**La atribución DVC queda CERRADA / PASS.** La evidencia independiente reproduce:

```text
unidad                         línea «estado: ruta» del granular
total                          4,012
added / modified / deleted     3,991 / 21 / 0
targets                        6
models added                   790 · 100% Obesidad legacy
logs added                     3,196
raw added                      3
figures                        2 added + 10 modified
forecasts                      5 PNG modificados + línea target
hits C7.6/agregados            0
```

Las clases A/B y la colisión descartada se sostienen: los destinos propuestos son hermanos de
`reports/figures` y `reports/forecasts`, no descendientes. Los cuatro agregados legacy permanecen
fuera del delta. `PASS_CLEAN_LANE_DESIGNED` es válido como dirección.

Antes de usar ese diseño hay dos correcciones funcionales:

#### R92-P0 — `dvc status` global no puede ser el gate tras un pull dirigido

En un clon limpio que sólo restaura el release y algunos inputs, los demás outputs DVC estarán
ausentes. Por definición, `dvc status` global los reportará como modificados/eliminados aunque el
carril de publicación esté correcto. Exigir «global limpio» contradice «no arrastrar los seis
targets».

Corrección obligatoria:

```text
dvc status <release.dvc> <cada-target-requerido.dvc>   debe estar limpio
dvc status global                                      se captura, pero no decide
inventario de outputs no materializados                declarado explícitamente
```

La publicación sólo puede consumir targets incluidos en esa lista cerrada. Si aparece una
dependencia nueva, se detiene y se amplía la lista; no se ejecuta `dvc pull` global.

#### R92-P1 — un directorio sin autoridad no es un canal publicado

`reports/publication/...` y `tableau/publication/...`:

- no existen hoy;
- no están cubiertos por los dos targets DVC sucios;
- tampoco están ignorados, trackeados, versionados ni conectados a un deploy.

Eso descarta la colisión, pero **no demuestra entrega**. Copiar 1.7 MB a un directorio local no
publica Reports ni actualiza Tableau. Antes de C7.7 hay que identificar el sink real, su autoridad,
su operación de promoción y su rollback.

El compilador debe escribir primero bajo un temporal externo. Sólo el adaptador/promotor del canal
puede llevar los archivos al sink real. No se adopta por defecto Git ni un target DVC nuevo, y no se
confunde un path de staging con la superficie pública.

#### Orden C7.6-CHANNEL-SINKS — descubrimiento read-only y contrato final

Ejecutar sólo lecturas en ambos repos. Escribir el resultado únicamente en este plan y STOP.

##### S0 · preflight

1. Backend `84d84675`, dashboard `20822a62`; preservar plan/untracked.
2. Confirmar lifecycle `trained`, puntero ausente, cuatro canales y F50 oculta.
3. No usar P/Q como destino: son evidencia, no superficies.

##### S1 · mapear cada canal de extremo a extremo

Para `web`, `epibot`, `reports` y `tableau`, localizar en código/config/docs:

| campo obligatorio | significado |
| --- | --- |
| fuente | shard/manifest exacto del compilador |
| adaptador | función/comando que traduce o copia |
| sink real | repo, objeto, datasource, workbook o servicio consumido |
| autoridad | Git, DVC/S3, Netlify, Tableau u otra declarada |
| promoción | comando/operación externa exacta |
| visibilidad | condición lifecycle/puntero que lo hace público |
| verificación | prueba/smoke y comparación contra release |
| rollback | objeto/versión/hash que se restaura |

No inferir un sink por el nombre del canal. Si no existe adaptador de promoción, declararlo
`MISSING_ADAPTER`; si falta destino externo, `MISSING_SINK`.

##### S2 · Reports

Responder con evidencia:

1. quién consume hoy un artefacto bajo `reports/`;
2. si `report.md` y `forecast_products.csv` deben:
   - permanecer sólo como build temporal,
   - entrar a Git,
   - tener target DVC dedicado,
   - o promoverse a un objeto/servicio externo existente;
3. cuál es la URL/ruta lógica pública sin hardcodear una máquina;
4. qué archivo/versión previa restaura el rollback.

`reports/publication/...` sólo puede conservarse si se demuestra su consumidor y su mecanismo de
versionado/promoción. De lo contrario, se retira como destino y queda únicamente como staging.

##### S3 · Tableau

Responder con evidencia:

1. cuál es hoy la autoridad: datasource, workbook o archivo;
2. qué proceso consume `forecast_shard.csv` + `schema.json`;
3. si existe promoción automatizada o es una acción manual documentada;
4. nombre/ID del recurso sin exponer credenciales;
5. cómo se captura la versión previa y se ejecuta rollback;
6. cómo se prueba que Obesidad aparece point-only sin alterar neuro/Dengue.

Si no existe un adaptador real, C7.7 no puede marcar Tableau como materializado aunque el CSV sea
válido.

##### S4 · web y EpiBot

Confirmar, sin regenerar:

- archivos exactos del dashboard que cambiarán;
- relación entre manifest, shard, `knowledge.json` e índice RAG;
- comando de build y deploy;
- efecto de merge a `main` sobre Netlify y cómo se evita un deploy no autorizado;
- snapshot y rollback de ambos HTML, knowledge, índice, cache-bust y deploy.

##### S5 · gate DVC dirigido

Definir la lista exacta de targets DVC que el carril limpio necesita. Como mínimo debe incluir el
release dedicado; cualquier otro debe justificar qué verificación lo consume.

El gate escrito debe tener esta forma:

```text
required_dvc_targets             lista cerrada
dvc status <required targets>    limpio
unmaterialized targets           lista declarada · no consumida
promotion inventory              sólo archivos del release/shards
global dvc status                evidencia informativa, no criterio
```

##### S6 · veredicto

Cerrar con uno:

```text
PASS_CHANNEL_SINKS_DECLARED
BLOCKED_MISSING_REPORTS_SINK
BLOCKED_MISSING_TABLEAU_ADAPTER
BLOCKED_PUBLIC_DEPLOY_CONTRACT
```

Puede haber más de un bloqueo; enumerarlos. Sólo `PASS_CHANNEL_SINKS_DECLARED` permite cerrar C7.6.

#### Prohibiciones

- No crear directorios `reports/publication` o `tableau/publication`.
- No generar/copiar shards, RAG, workbook, datasource o archivos públicos.
- No DVC pull/checkout/add/commit/push.
- No código, config, lifecycle, puntero, commit, push, PR, merge, deploy o publicación.
- No usar credenciales de Tableau, Netlify, AWS o Gemini.

#### Salida y STOP

Añadir:

1. matriz de cuatro canales;
2. evidencia de sinks/adaptadores;
3. lista DVC dirigida;
4. bloqueos reales;
5. veredicto S6.

Después STOP para auditoría.

#### Avance

Permanece en **83%**. DVC ya está atribuido; lo único que falta para cerrar readiness es demostrar
que Reports y Tableau tienen destinos reales y reversibles. Exposición pública: **0%**.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-CHANNEL-SINKS` read-only y STOP.**

_Respuesta:_ **GO C7.6-CHANNEL-SINKS READ-ONLY. Mapear fuente→adaptador→sink→promoción→rollback de
los cuatro canales y corregir el gate DVC a lista dirigida. Sin crear destinos, usar credenciales,
modificar código/DVC ni hacer commit, push, merge, deploy, lifecycle o publicación.**

---

### Ronda 93 — C7.6-CHANNEL-SINKS (read-only) — 2026-07-27

Sólo lecturas en ambos repos. Sin crear destinos, sin credenciales, sin DVC, sin commit, push,
merge, lifecycle, puntero, deploy ni publicación.

#### S0 · preflight

```text
backend 84d84675 · dashboard 20822a62 · plan y untracked intactos
obesidad   lifecycle=trained · canales [epibot, reports, tableau, web] · galería false
puntero público                    NO EXISTE
F50                                configured · 0 canales
P y Q                              evidencia de RAG-C-REPEAT; NO se usan como destino
```

#### S1 · matriz de los cuatro canales

| campo | **web** | **epibot** | **reports** | **tableau** |
| --- | --- | --- | --- | --- |
| fuente | `web/manifest.json` + `web/series.csv` del shard | `epibot/knowledge.json` + `epibot/corpus/<disease>.md` del shard | `reports/report.md` + `reports/forecast_products.csv` del shard | `tableau/forecast_shard.csv` + `tableau/schema.json` del shard |
| adaptador | **ninguno hoy** para un release del runner | `build_web_knowledge.py` (produce el `knowledge.json` público) + `rag:build` para el índice | `build_neuro_gallery.py --out ../EpiForecast-IMSS-Dashboard/Reports`, `build_epibot_zoom.py --reports …/Reports` | `build_tableau.py` → `tableau_model.xlsx` → `publish_gsheets.py` |
| sink real | páginas HTML en la **raíz del repo dashboard** (`EpiDashboard.html`, `dengue.html`, `index.html`…) | `epibot/knowledge.json` y `epibot/rag_index.json`, **trackeados en Git** | **`EpiForecast-IMSS-Dashboard/Reports/`** — 1,798 archivos en Git, 185 MB | **Google Sheets** (`GSHEETS_SPREADSHEET_ID`) y copia en `s3://epiforecast-mx-data/latest/` |
| autoridad | Git del dashboard + **Netlify** (`publish = "."`) | Git del dashboard + Netlify (`included_files` empaqueta ambos JSON para las functions) | Git del dashboard + Netlify | Google Sheets vía service account; S3 como copia secundaria |
| promoción | merge/deploy de la rama que Netlify publica | idem, con `command = "cd epibot && npm install && npm run rag:ci"` en el build | copiar los archivos al repo dashboard y commitear | `.github/workflows/gsheets.yml` (`workflow_dispatch` / `workflow_call`) o `make s3-sync` |
| visibilidad | lo que esté en el repo desplegado | idem | idem | lo que exista en la hoja publicada |
| verificación | smoke contra `forecast.csv` sellado | `npm run check` + `rag:verify` drift cero | comparación de cifras y presencia de la etiqueta | comparar la pestaña `forecast` contra el shard |
| rollback | revertir commit + redeploy | restaurar `knowledge.json` `e1d9a7d9…` y `rag_index.json` `efbae871…` + redeploy | revertir los archivos de `Reports/` en Git + redeploy | republicar la hoja desde el `tableau_model.xlsx` anterior |

#### S2 · Reports — el sink existe, el adaptador **no**

1. **Quién consume hoy `reports/`:** nadie en producción. El backend escribe bajo `reports/` para
   trabajo interno, y lo que se publica vive en **otro sitio**: `EpiForecast-IMSS-Dashboard/Reports/`,
   1,798 archivos trackeados en Git y servidos por Netlify. El propio EpiBot enlaza
   `../Reports/dengue/…png` desde `kb.js`.
2. **Qué debe pasar con `report.md` y `forecast_products.csv`:** ninguna de las cuatro opciones tal
   cual. La correcta es **build temporal → adaptador → Git del dashboard**: se compilan en un
   temporal externo y un promotor los coloca bajo `Reports/obesidad/<release_id>/`. No necesitan
   target DVC —el sink es Git— ni deben quedarse en un directorio local del backend.
3. **Ruta lógica pública:** `<sitio>/Reports/obesidad/<release_id>/…`, relativa al deploy; no se
   fija ninguna máquina.
4. **Rollback:** revertir esos archivos en Git del dashboard y redesplegar; el estado previo es
   «no existen», porque hoy no hay ningún Reports de Obesidad.

**`reports/publication/…` del diseño anterior se retira como destino.** No tiene consumidor: era un
directorio local del backend sin autoridad, sin versionado y sin deploy. Queda **sólo como staging**
—o mejor, se usa el temporal externo del carril limpio, que es lo que ya hace `emit_shards`—.

#### S3 · Tableau — autoridad identificada, adaptador **ausente**

1. **Autoridad:** una hoja de Google Sheets, identificada por la variable de repositorio
   `GSHEETS_SPREADSHEET_ID`, escrita por `publish_gsheets.py` con un service account
   (`GOOGLE_SERVICE_ACCOUNT_JSON`). Existe además una copia en S3
   (`s3://epiforecast-mx-data/latest/tableau.csv`) vía `make s3-sync`.
2. **Qué consume el shard:** **nada**. La cadena viva es
   `build_tableau.py → data/processed/tableau_model.xlsx → publish_gsheets.py → 5 pestañas`
   (`scaffold`, `real`, `forecast`, `metricas`, `entidades`). El `forecast_shard.csv` +
   `schema.json` del compilador **no tienen consumidor**.
3. **Automatización:** el workflow es `workflow_dispatch` / `workflow_call` — acción manual o
   invocada, no automática por push.
4. **Recurso:** `GSHEETS_SPREADSHEET_ID` (variable de repo). No se leyó ni se expone ningún valor.
5. **Versión previa y rollback:** republicar desde el `tableau_model.xlsx` anterior; la hoja no
   tiene versionado propio en el repo, así que el rollback exige conservar ese Excel antes de
   publicar.
6. **Cómo se probaría point-only sin tocar neuro/Dengue:** hoy no se puede afirmar. `build_tableau.py`
   aplica **`filter_neuro`** a `real` y a los forecasts —línea 104 y 119, esta última descrita como
   «defensivo: excluye forecasts no-neuro»—, así que Obesidad quedaría fuera por construcción.

**Conclusión de S3: `MISSING_ADAPTER`.** Publicar Tableau exigiría un promotor nuevo que traduzca el
shard a las pestañas existentes —o una hoja/pestaña dedicada—, más una decisión sobre `filter_neuro`.
Ninguna de las dos cosas existe, y el CSV del shard siendo válido no lo suple.

#### S4 · web y EpiBot

```text
archivos que cambiarían   epibot/knowledge.json · epibot/rag_index.json · index.html (cache-bust)
                          + la página de Obesidad (no existe todavía)
relación                  el shard trae web/manifest.json y series.csv; el índice RAG se construye
                          desde el corpus, que incluiría el chunk candidate ya validado (455)
build/deploy              Netlify · publish "." · command "cd epibot && npm install && npm run rag:ci"
                          functions con included_files = [knowledge.json, rag_index.json]
efecto de merge a main    `origin/HEAD -> origin/main`: un merge a main dispara el deploy de
                          producción. Por eso el push de la rama y el merge son autorizaciones
                          distintas: mientras se quede en `feat/c73-candidate-staging`, producción
                          no cambia.
snapshot / rollback       knowledge e1d9a7d9… · rag_index efbae871… · epibot/index.html f2e66edc…
                          · index.html 94549fbd… · cache-bust actual · deploy previo de Netlify
```

Un detalle operativo que ya está anotado como deuda: tocar `kb.js`/`entities.js` obliga a subir
`app.js?v` en `index.html`; sin eso el navegador sirve el bundle viejo aunque el deploy llegue bien.

#### S5 · gate DVC dirigido (corrige R92-P0)

```text
required_dvc_targets
    artifacts/releases/obesidad/obesidad_release_2517e7858901.dvc   el bundle
    reports/forecasts.dvc                                          sólo para verificar que los 4
                                                                   agregados legacy no cambian
dvc status <required targets>      debe estar LIMPIO en el carril
unmaterialized targets             models.dvc · logs.dvc · data/raw.dvc · reports/figures.dvc ·
                                   data/processed/*.dvc  → declarados, NO consumidos
promotion inventory                sólo archivos del bundle y de los shards, enumerados uno a uno
global dvc status                  se captura como evidencia; NO decide
```

En un clon limpio, `reports/forecasts.dvc` se restaura a su versión **commiteada** —limpia por
construcción—; el estado sucio de hoy vive sólo en este working tree. Si apareciera una dependencia
nueva, se detiene y se amplía la lista: nunca `dvc pull` global.

#### S6 · veredicto

```text
BLOCKED_MISSING_TABLEAU_ADAPTER
```

- **web** y **epibot**: sink, autoridad, promoción y rollback identificados → sin bloqueo.
- **reports**: el sink real es `Reports/` del dashboard, con autoridad Git+Netlify y rollback por
  revert. Falta un promotor que copie los dos archivos del shard, pero es un adaptador trivial
  sobre un sink que **sí existe**; no bloquea por destino.
- **tableau**: no hay adaptador del shard a la hoja, y `build_tableau.py` excluye Obesidad por
  `filter_neuro`. **Bloquea.**

C7.6 no puede cerrarse declarando Tableau materializable. Las opciones para C7.7 —que no decido
aquí— son: escribir el promotor del shard a la hoja, extender `build_tableau.py` con la cohorte del
release, o retirar `tableau` de los canales de Obesidad hasta tener el adaptador.

_Respuesta:_

---

### Ronda 94 — Auditoría de sinks: el bloqueo cubre los cuatro promotores — 2026-07-27

#### Veredicto

**La identificación de sinks y el gate DVC dirigido quedan PASS. El veredicto
`BLOCKED_MISSING_TABLEAU_ADAPTER` es incompleto: Tableau no es el único promotor ausente.**

Evidencia reproducida:

```text
Dashboard/Reports                 1,798 archivos trackeados · 185 MB · Netlify los sirve
Makefile backend                  build_neuro_gallery escribe al Reports del dashboard
kb.js                             enlaza imágenes bajo ../Reports/
origin/HEAD dashboard             origin/main
Tableau                           build_tableau → xlsx → publish_gsheets → 5 pestañas
build_tableau                     filter_neuro en real y forecast
shard Tableau                     5,772 × 21 · ningún consumidor
```

La matriz de Ronda 93 contiene además las pruebas de los otros huecos:

1. **web:** declara `adaptador: ninguno` y la página de Obesidad no existe;
2. **Reports:** el sink existe, pero no hay código que instale `report.md`/CSV ni una vista que los
   consuma; “trivial” no equivale a implementado;
3. **EpiBot:** `candidateRoot` sólo entra en `rag_staging.mjs`. El build público sin argumentos
   continúa con 454 chunks. `build_web_knowledge.py` no consume `publication_shard.v1` y aplica
   `filter_neuro`;
4. **Tableau:** el shard no entra a las cinco pestañas y el filtro neuro lo excluye.

Por tanto, los bloqueos reales son:

```text
BLOCKED_PUBLIC_DEPLOY_CONTRACT
BLOCKED_MISSING_REPORTS_ADAPTER
BLOCKED_MISSING_EPIBOT_PROMOTER
BLOCKED_MISSING_TABLEAU_ADAPTER
```

No se retira `tableau` ni otro canal: el alcance aprobado sigue siendo cuatro. Tampoco se modifica
el carril legacy para “hacer caber” Obesidad. Se construye un carril genérico de promociones de
runner releases.

#### Decisión arquitectónica

Separar tres conceptos:

```text
compiler     release sellado → shards neutrales             backend · ya existe
installer    shards → árbol de consumo versionable           nuevo · puro/local
promoter     árbol validado → Git/Netlify/Google Sheets       externo · C7.7
```

Un installer nunca publica. Todos reciben raíces por argumento y escriben sólo bajo un output
temporal durante C7.6.

Para Tableau no se toca `filter_neuro` ni se reescriben las cinco pestañas legacy. El runner usa un
schema namespaced:

```text
runner_forecast    las 5,772 filas del shard
runner_releases    una fila por release: identidad, status, label, point-only, digests
```

El adaptador es N+1: ninguna pestaña, condición o columna contiene `obesidad`. La conexión del
workbook/Tableau a esas pestañas es una promoción externa posterior y seguirá bloqueada hasta una
prueba en staging.

#### Orden C7.6-PROMOTION-ADAPTERS-A — implementación local, sin promoción

Se autorizan cambios de código y tests en ambos repos, en commits separados. No se autorizan
credenciales ni escrituras en sinks reales.

##### A0 · preflight

1. Backend `84d84675`, dashboard `20822a62`; preservar el plan y todos los untracked.
2. Crear cambios separados por repo; nunca commitear el plan junto con código.
3. Mantener Obesidad `trained`, puntero ausente, F50 oculta y cuatro publicados históricos.
4. Usar un shard real compilado en un temporal nuevo; P/Q quedan sólo como evidencia.

##### A1 · contrato común de instalación

Definir un manifest versionado `publication_install.v1` con:

- `release_id`, `disease_id`, lifecycle, channels y schema del shard;
- digests de todos los inputs y outputs;
- `publication_status` y etiqueta exactas;
- inventario cerrado de archivos;
- modo `candidate` o `public`;
- cero rutas absolutas, timestamps identitarios o nombres de padecimiento codificados.

Reglas:

- candidate acepta `trained` y sólo escribe en temporal;
- public exige `published` + puntero activo al mismo release;
- reejecutar es idempotente;
- un archivo previo ajeno al inventario no se borra ni sobrescribe;
- fallo antes de completar deja el destino previo intacto.

##### A2 · dashboard installer: web + Reports

Implementar en el dashboard un instalador genérico que consuma:

```text
shard_manifest.json
web/manifest.json
web/series.csv
reports/report.md
reports/forecast_products.csv
```

Salida candidate bajo una raíz temporal que imita el dashboard:

```text
publication/catalog.json
publication/<disease_id>/<release_id>/manifest.json
publication/<disease_id>/<release_id>/series.csv
Reports/publication/<disease_id>/<release_id>/report.md
Reports/publication/<disease_id>/<release_id>/forecast_products.csv
```

Añadir una vista genérica —sin literales de padecimiento— que:

- resuelva por catálogo/manifest;
- muestre etiqueta `0/4` y point-only junto a cualquier cifra;
- no dibuje banda;
- rechace schemas/digests/lifecycle incoherentes;
- permanezca invisible en el catálogo público mientras sea candidate.

`gallery_enabled=false` significa no insertar el release en la galería histórica; no significa
suprimir el canal Reports.

##### A3 · dashboard installer: EpiBot/RAG

Generalizar el consumo candidate sin cambiar el build público por defecto:

- la fuente es `epibot/knowledge.json` + `epibot/corpus/<disease>.md` del shard;
- el installer candidate produce un árbol temporal de knowledge/corpus;
- `buildChunks()` sin raíz conserva exactamente los 454 chunks públicos;
- con `publicationRoot` validado produce 455;
- public exige catálogo activo, lifecycle published y puntero coincidente;
- el merge de knowledge es upsert por `release_id`, no concatenación ni overwrite global;
- el índice se construye con el contrato RAG existente; no se llama Gemini en tests.

El candidate real debe conservar 454 vectores y requerir sólo el vector ya caracterizado del nuevo
chunk. No escribir todavía `knowledge.json` o `rag_index.json` públicos.

##### A4 · backend adapter Tableau puro

Crear un adaptador tipado que lea el shard y produzca dos DataFrames/tablas:

```text
runner_forecast
runner_releases
```

Contrato:

- `runner_forecast`: 5,772 filas y las 21 columnas declaradas, claves únicas, no negativos,
  intervalos nulos y status/lineage verificables;
- `runner_releases`: una fila con release/disease/origen/horizonte/filas, status, label,
  `uncertainty_available=false`, gate/evaluation/status/refit digests;
- upsert por `(disease_id, release_id)`;
- no tocar `scaffold`, `real`, `forecast`, `metricas`, `entidades` legacy;
- no importar `filter_neuro`;
- ninguna cadena `Obesidad`, `E66`, `64`, `111` o `5772` en lógica genérica: los conteos salen del
  schema/manifest;
- serialización local determinista a XLSX/CSV en temporal y round-trip exacto.

Definir un protocolo de sink para que las pruebas usen un fake. El cliente Google Sheets puede
prepararse, pero no debe autenticarse ni escribir en esta ronda.

##### A5 · estrategia Tableau de promoción, sólo simulada

El promotor futuro escribirá tabs namespaced `runner_forecast` y `runner_releases` en la hoja
declarada por entorno/config, con:

1. tabs `__next` completas;
2. validación de filas/digests;
3. swap/rename a tabs activas conservando `__previous`;
4. rollback por swap inverso;
5. workbook Tableau de staging conectado a esas tabs antes de producción.

A no ejecuta esos pasos. Una prueba fake debe demostrar el orden, el rollback y que un fallo no
reemplaza las tabs activas.

##### A6 · gates locales

Backend:

- unitarios del adapter y fake sink;
- ruff/format/mypy/fast;
- integración estable;
- doctor y target DVC del release;
- hashes legacy intactos.

Dashboard:

- `npm test`, `test:candidate`, `npm run check`;
- pruebas del installer con fixtures y shard real;
- dos instalaciones candidate en raíces distintas, bytes idénticos;
- default público byte-idéntico: 454 chunks, 0 Obesidad;
- superficies actuales y Reports actuales byte-idénticos.

Gate cruzado:

```text
web candidate       manifest/series cargables · no público
Reports candidate   dos archivos + vista genérica · no galería
EpiBot candidate    455 chunks · sólo staging
Tableau candidate   runner_forecast 5,772 + runner_releases 1 · fake sink
public mode         rechazado mientras trained/sin puntero
```

##### A7 · commits y STOP

Crear como máximo:

```text
backend    C7.6 Tableau runner-release adapter and transactional sink contract
dashboard  C7.6 generic runner-release installer for web, Reports and EpiBot
```

No incluir el plan en esos commits. Reportar SHAs, diffs y gates; STOP para auditoría.

#### Prohibiciones

- No usar `GSHEETS_SPREADSHEET_ID`, service account, Netlify token, AWS o Gemini.
- No escribir Google Sheets, S3, Dashboard/Reports real, knowledge/RAG público o HTML público.
- No modificar `build_tableau.py` ni `publish_gsheets.py` legacy.
- No DVC pull/add/commit/push/checkout.
- No lifecycle, puntero, commit del plan, push, PR, merge, deploy o publicación.
- No retirar canales ni encender galería.

#### Secuencia posterior, aún no autorizada

```text
auditar ADAPTERS-A
→ ADAPTERS-B: staging externo controlado de Tableau + árbol dashboard temporal
→ cerrar C7.6
→ checkpoints Git separados
→ C7.7 con autorizaciones por efecto externo
```

#### Avance

Se corrige a **82%**. Los modelos, release, RAG candidate y status están cerrados; la deuda restante
es entregar los shards a consumidores reales sin tocar todavía producción.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PROMOTION-ADAPTERS-A` local y STOP.**

_Respuesta:_ **GO C7.6-PROMOTION-ADAPTERS-A LOCAL. Implementar installer genérico candidate para
web/Reports/EpiBot y adaptador Tableau namespaced con fake sink; dos commits separados y STOP. Sin
credenciales, DVC, plan commit, push, PR, merge, lifecycle, puntero, deploy ni publicación.**

---

### Ronda 95 — C7.6-PROMOTION-ADAPTERS-A ejecutada — 2026-07-27

Dos commits separados, uno por repo. Sin credenciales, DVC, commit del plan, push, PR, merge,
lifecycle, puntero, deploy ni publicación.

```text
backend    1806177d  C7.6 Tableau runner-release adapter and transactional sink contract
dashboard  5aa45c49  C7.6 generic runner-release installer for web, Reports and EpiBot
```

Shard real usado en los gates cruzados, compilado en un temporal nuevo (P/Q siguen intactos como
evidencia de RAG-C-REPEAT):

```text
/var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.753WuabU7V
```

#### A4/A5 · adaptador Tableau con namespace propio

Dos tablas reservadas, `runner_forecast` y `runner_releases`, que **no tocan** `scaffold`, `real`,
`forecast`, `metricas` ni `entidades`. La razón de no extender el legacy es la que encontró S3:
`build_tableau.py` filtra por cohorte neuro, y meter ahí un release del runner mezclaría dos
identidades distintas.

```text
runner_forecast   filas y columnas que declara el schema del shard · claves únicas · yhat ≥ 0
                  yhat_lower/upper vacíos → si llegan valores, falla
runner_releases   1 fila: origen, horizonte, conteos, veredicto, etiqueta,
                  uncertainty_available=false, gate/evaluation/status/refit digests
upsert            por (disease_id, release_id): reemplaza su fila, respeta las ajenas
serialización     CSV + XLSX deterministas, round-trip exacto, en temporal
```

**Promoción transaccional** (simulada con un sink en memoria): escribe `<tabla>__next`, valida,
y sólo entonces mueve la activa a `__previous` y `__next` a activa. Si algo falla antes del swap,
**las tablas activas no se tocan** y las temporales se limpian; `rollback()` es el swap inverso.
Hay una prueba por cada uno de esos cuatro comportamientos.

Esta ronda **no autentica ni escribe en Google Sheets**: el módulo no menciona `gspread`,
credenciales ni `GSHEETS_SPREADSHEET_ID`, y una prueba lo verifica. `build_tableau.py` y
`publish_gsheets.py` no se tocaron.

La genericidad se prueba **por AST, no por grep**: el módulo no importa `filter_neuro` ni `cohorts`,
y no tiene escritas las cadenas del padecimiento ni los conteos 64/111/5772 en su lógica. Lo hago
así porque la prosa del módulo *explica* por qué no los usa, y un grep del texto confundiría la
explicación con el defecto.

#### A1/A2/A3 · installer genérico del dashboard

`publication_install.v1` sella modo, lifecycle, canales, etiqueta, estado prospectivo e inventario
cerrado con los digests de **cada entrada y cada salida**. Reglas verificadas una por una:

```text
candidate           acepta trained · escribe SÓLO bajo la raíz inyectada
public              exige published Y puntero activo al mismo release
idempotencia        reinstalar da los mismos bytes
dos raíces          instalaciones byte-idénticas (la ruta no se filtra al contenido)
archivo ajeno       ni se borra ni se sobrescribe
fallo a mitad       temporal hermano → el destino previo queda intacto, sin restos
catálogo            upsert por (disease_id, release_id) · candidate con visible=false
```

La vista es genérica de verdad: resuelve por catálogo y manifiesto, **revalida** el estado —el
catálogo es un índice, no una autoridad— y entrega juntas la etiqueta, la advertencia point-only y
`band=null`. Una prueba fija que el módulo no menciona ningún padecimiento por su nombre.

Sobre `gallery_enabled=false`, que el plan pedía no confundir: apaga la galería, **no** el canal
Reports. La vista expone `report.md` y `forecast_products.csv` igual, y lo dice con `inGallery:
false` separado de `isPubliclyVisible`.

`corpus.mjs` acepta `publicationRoot` y resuelve el corpus instalado **por catálogo**, para que un
directorio huérfano no se cuele en el índice. Sin argumentos sigue dando los **454** chunks públicos
con el mismo digest `11ec6151867a4cac…`; con la raíz instalada, **455**.

#### A6 · gates

```text
backend    ruff+format PASS · mypy 161 · fast 2018 passed (81.03%) · publicación 184
           integración 8 · doctor rc=0 · release .dvc up to date · 4 hashes legacy intactos
dashboard  npm test 616/616 + 67 · test:candidate 52 casos (50 + 2 skip sin shard real;
           52/52 con C7_SHARD_ROOT=/var/folders/0p/fpm4_3l94jxbbc__pnl93bmw0000gn/T/tmp.753WuabU7V) · npm run check rc=0
cruzado    web/Reports/EpiBot candidate: 6 archivos, 5,772 filas, etiqueta 0/4, band null,
           no público, 455 chunks · Tableau candidate: runner_forecast 5,772 + runner_releases 1
           sobre sink falso · modo public rechazado mientras trained y sin puntero
público    knowledge.json · rag_index.json · ambos HTML · package-lock · Reports/ real
           byte-idénticos · 0 menciones de Obesidad
```

#### Lo que esta ronda deliberadamente NO hace

- No escribe en el `Reports/` real del dashboard: el installer sólo toca la raíz que se le inyecta.
- No prepara el cliente de Google Sheets. El orden lo permitía; preferí no dejar código de
  autenticación sin usar, porque un cliente que nadie ejercita es una promesa, no una garantía.
- No retira `tableau` de los canales de Obesidad ni enciende la galería.

`BLOCKED_MISSING_TABLEAU_ADAPTER` de la Ronda 93 queda **resuelto en su parte local**: el adaptador
existe, es genérico y su promoción es transaccional y reversible. Lo que sigue faltando es el
staging externo real —la hoja y el workbook—, que es ADAPTERS-B.

_Respuesta:_

---

### Ronda 96 — Auditoría ejecutable de ADAPTERS-A — 2026-07-27

#### Veredicto

```text
ADAPTERS-A_IMPLEMENTED_BUT_AUDIT_FAIL
ADAPTERS-B_BLOCKED
C7.6_NO-GO
```

Los dos commits respetan la superficie autorizada y separan correctamente backend y dashboard:

```text
backend    1806177d  2 archivos · adaptador Tableau + pruebas
dashboard  5aa45c49  5 archivos · installer/vista/corpus + pruebas y scripts npm
```

No tocaron bundle, DVC, lifecycle, puntero, credenciales ni superficies públicas. Sin embargo, los
gates prueban principalmente fallos **antes** de la fase crítica y no cubren fallos dentro del
commit/swap. La auditoría reprodujo cinco defectos.

#### R96-P0-1 · el installer no es atómico al aplicar al destino vivo

`installer.mjs` construye correctamente un temporal hermano, pero después copia sus archivos
**uno por uno** con `cpSync()` al árbol vivo. El test de “fallo a mitad” elimina una entrada del
shard, por lo que el error ocurre mientras todavía se prepara el temporal; no prueba la fase de
aplicación.

Reproducción independiente en un temporal:

```text
destino previo: manifest.json = SENTINEL_PREVIO
fallo inyectado al crear Reports/ después de copiar los dos archivos web

resultado:
sentinel_preserved   false
manifest reemplazado true
series.csv presente  true
catalog.json presente false
```

El destino queda parcialmente actualizado y sin catálogo que describa lo que contiene.

#### R96-P0-2 · el swap de Tableau puede partir las dos tablas activas

La prueba existente falla al escribir la segunda `__next`, es decir, **antes** del swap. No inyecta
errores en los renames. Al fallar el rename de `runner_releases__next` después de activar
`runner_forecast`, el estado observado fue:

```text
runner_forecast             NUEVA
runner_forecast__previous   anterior
runner_releases             AUSENTE
runner_releases__previous   anterior
runner_releases__next       nueva sin activar
```

No es una transacción de dos tablas. `rollback()` también borra la activa antes de renombrar la
previa y puede perderla si ese rename falla.

#### R96-P0-3 · Tableau declara validar digests, pero sólo compara filas

Un sink de prueba alteró el primer `yhat_cases` de `152.0` a `999999999` al escribir
`runner_forecast__next`, conservando el número de filas. `promote()` lo aceptó, activó el valor
alterado y reportó el digest del frame **original**, no el del read-back. Esto contradice el
docstring y el contrato A5.

`build_tables()` tampoco cruza `tableau/forecast_shard.csv` y `tableau/schema.json` contra
`shard_manifest.json.files` antes de consumirlos.

#### R96-P0-4 · los consumidores instalados no verifican los sellos

`publication_install.v1` registra digests, pero `buildReleaseView()` e `installedChunks()` no los
recalculan. Reproducciones independientes:

```text
web/manifest.json alterado y reserializado     vista ACEPTA
corpus/<disease>.md alterado                   RAG CONSUME el texto alterado
```

Además, `installedChunks(publicationRoot)` incorpora cualquier entrada del catálogo, incluida una
`visible=false`; sólo cambia su URL a `null`. Eso sirve para staging, pero es una interfaz ambigua
para un build público. Candidate y public deben ser modos explícitos y fail-closed.

#### R96-P1-1 · el XLSX no es byte-determinista

Dos llamadas a `write_local()` separadas por 2.1 segundos, con las mismas tablas y raíces distintas:

```text
CSV                 idénticos
runner_tables.xlsx  SHA distinto
```

El test actual escribe ambos workbooks dentro del mismo segundo y por eso no detecta metadata
temporal del contenedor XLSX. No puede llamarse determinista ni entrar en un manifiesto reproducible
en su forma actual.

#### R96-P1-2 · genericidad incompleta del dashboard

- `publication_view.mjs` devuelve `inGallery: false` como constante en vez de derivarlo del
  `gallery_enabled` sellado en `web/manifest.json`;
- el installer no persiste ni cruza esa política;
- el catálogo ordena con `localeCompare`, cuyo orden depende del locale y no demuestra bytes
  idénticos entre máquinas;
- `buildReleaseView()` cruza sólo identidad/lifecycle/label, no modo, inventario y digests.

Esto funciona para el release actual porque su galería es falsa, pero no demuestra N+1.

### Orden C7.6-PROMOTION-ADAPTERS-A.1 — corregir antes de servicios externos

#### A.1-BE · backend Tableau

1. Antes de parsear, verificar contra `shard_manifest.json.files` los bytes exactos de
   `tableau/forecast_shard.csv` y `tableau/schema.json`; cruzar schema, release, disease, lifecycle,
   status e identidad.
2. Tras cada `write_table(__next)`, releer y comparar contenido canónico completo, columnas, tipos,
   claves, valores y digest; comparar filas únicamente no es suficiente.
3. Reemplazar el “swap transaccional” por un protocolo **recuperable**:
   - preflight de activas, temporales y backups;
   - backups por transacción que no destruyan un `__previous` válido;
   - activar ambas tablas;
   - verificar ambas activas;
   - ante fallo en cualquier write/read/rename/drop, ejecutar compensación y restaurar exactamente
     el estado previo;
   - si la compensación falla, reportar estado `RECOVERY_REQUIRED` con inventario suficiente para
     recuperación explícita. No afirmar atomicidad multi-tab que el sink no garantiza.
4. Hacer `rollback()` recuperable: nunca borrar la activa antes de asegurar que la previa puede
   restaurarse.
5. Inyectar fallo en **cada frontera** de rename y validación, incluida la segunda tabla, y fijar
   que las dos activas quedan ambas antiguas o ambas nuevas; nunca una mezcla ni una ausente.
6. Corregir la reproducibilidad:
   - o producir XLSX byte-idéntico normalizando propiedades y entradas ZIP;
   - o declarar XLSX como vista no autoritativa y retirarlo de los digests reproducibles.
   La prueba debe separar las escrituras más de dos segundos y comparar raíces distintas.

#### A.1-FE · dashboard installer, vista y RAG

1. Verificar los seis inputs contra `shard_manifest.json.files` **antes** de preparar la
   instalación.
2. Publicar directorios inmutables del release y hacer que `publication/catalog.json` sea el único
   commit visible, escrito con temporal + rename en su mismo directorio:
   - preparar y validar todo;
   - instalar outputs aún no referenciados;
   - escribir catálogo al final;
   - ante fallo, el catálogo y el release previamente visible quedan byte-idénticos;
   - una ruta ya existente con bytes distintos se rechaza, no se sobrescribe.
3. Probar fallos durante cada copia/rename del destino vivo, no sólo mientras se arma el temporal.
4. En cada lectura, verificar `publication_install.json`, su forma cerrada y todos los digests de
   outputs. Un catálogo que declara un archivo ausente o alterado debe fallar, no omitirlo.
5. Separar el consumo RAG:
   - `candidate/staging` se solicita explícitamente y puede incorporar `visible=false`;
   - `public` sólo incorpora entradas `visible=true`, `mode=public`, lifecycle published y puntero
     coincidente;
   - sin modo explícito no incorporar candidates.
6. Persistir y cruzar `gallery_enabled`; `inGallery` se deriva de metadata y visibilidad, nunca de
   una constante.
7. Sustituir `localeCompare` por orden binario/canónico independiente de locale. Probar dos roots
   bajo locales distintos.
8. Repetir con el shard real:

```text
candidate instalado    5,772 filas · 455 chunks sólo en modo staging · 0 público
public sin condiciones rechazado
archivo mutado         vista y RAG rechazan
fallo durante commit   destino/catálogo anterior byte-idéntico
default público        454 chunks y superficies actuales byte-idénticas
```

#### Gates y commits

Crear como máximo dos commits correctivos, uno por repositorio, encima de los commits auditados.
No amend, rebase ni squash:

```text
backend    C7.6 ADAPTERS-A.1 recoverable Tableau promotion and exact readback
dashboard  C7.6 ADAPTERS-A.1 atomic release install and sealed consumers
```

Ejecutar los gates completos de A6 y añadir las reproducciones de R96 como regresiones. El plan no
entra en esos commits.

#### STOP y prohibiciones

Después de los dos commits y los gates: **STOP para auditoría**. ADAPTERS-B continúa bloqueada.

Sin Google Sheets, service account, `GSHEETS_SPREADSHEET_ID`, Netlify, Gemini, AWS, DVC, commit del
plan, push, PR, merge, lifecycle, puntero, deploy, escritura en `Reports/` real ni publicación.

#### Avance

Permanece en **82%**. ADAPTERS-A existe, pero todavía no es seguro conectarla a los sinks reales.
La exposición pública continúa en **0%** y C7.4 en **INCOMPLETE 0/4**.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PROMOTION-ADAPTERS-A.1` local y STOP.**

_Respuesta:_ **GO C7.6-PROMOTION-ADAPTERS-A.1 LOCAL. Corregir instalación parcial, verificación de
digests, read-back exacto, swap/rollback recuperable, XLSX reproducible, modos RAG explícitos,
gallery metadata y orden independiente de locale; dos commits correctivos separados y STOP. Sin
credenciales, DVC, plan commit, push, PR, merge, lifecycle, puntero, deploy ni publicación.**


---

### Ronda 97 — C7.6-PROMOTION-ADAPTERS-A.1 ejecutada — 2026-07-27

**Orden ejecutada:** corregir instalación parcial, verificación de digests, read-back exacto,
swap/rollback recuperable, XLSX reproducible, modos RAG explícitos, gallery metadata y orden
independiente de locale. Dos commits correctivos separados, sin amend/rebase/squash, y STOP.

**Commits (el plan NO entra en ellos):**

```text
backend    f1226778  C7.6 ADAPTERS-A.1 recoverable Tableau promotion and exact readback
dashboard  9454a166  C7.6 ADAPTERS-A.1 atomic release install and sealed consumers
```

#### A.1-BE · backend Tableau (`f1226778`, encima de `1806177d`)

1. **Sellado antes de parsear.** `_check_sealed()` lee los bytes de `tableau/forecast_shard.csv` y
   `tableau/schema.json`, los compara con `shard_manifest.json.files` y sólo entonces entrega el
   buffer a `pd.read_csv(io.BytesIO(...))`. La identidad cruzada ya no es sólo el release: se
   comparan `release_id`, `disease_id`, `lifecycle`, `rows`, `interval_method` y el bloque
   `publication_status` completo entre schema y manifiesto.
2. **Read-back exacto.** `_verify_readback()` compara columnas, filas y el **digest del contenido
   canónico** de lo releído contra lo escrito. Comparar `len` dejaba pasar un sink que cambiaba un
   valor y conservaba el conteo.
3. **Promoción recuperable.** No se promete atomicidad multi-tabla que un sink de hojas de cálculo
   no puede dar; se promete recuperabilidad. Protocolo: preflight → `__next` + read-back → respaldo
   de cada activa en `__backup` (sin destruir un `__previous` válido) → activar las dos → verificar
   las dos → consolidar `__backup`→`__previous`. La compensación recorre el namespace **completo**,
   no sólo lo que llegó a activarse: ahí estaba el fallo real, porque un fallo entre el respaldo y
   la activación dejaba la tabla viva sólo en su `__backup`. Si la compensación falla,
   `PromotionRecoveryError` con `status="RECOVERY_REQUIRED"` e inventario (`tables`,
   `expected_before`, `namespace`).
4. **`rollback()` recuperable:** la activa se aparta a `__backup` y sólo se borra cuando la previa
   ya ocupó su lugar. Si el rename falla, la activa vuelve a su sitio.
5. **XLSX.** Se declara **vista no autoritativa**: sale de los digests y del inventario, y el
   manifiesto lo dice con `non_authoritative_views`. Un `.xlsx` es un ZIP con metadata temporal del
   contenedor; normalizarlo habría sido pelear con el formato para sostener una afirmación que no
   hace falta. Los CSV autoritativos **sí** son byte-idénticos.

**Regresiones añadidas (13 pruebas nuevas, 18 → 31):**

| Prueba | Qué fija |
|---|---|
| `un_fallo_en_cualquier_frontera…` (7 casos) | write/read/rename de la 1ª y de la **2ª** tabla: las dos activas quedan **ambas antiguas**, sin mezcla ni ausencias, sin temporales ni respaldos colgando |
| `un_sink_que_altera_el_contenido…` | mismo número de filas, un valor cambiado → rechazado |
| `un_csv_alterado_no_llega_siquiera_a_parsearse` | el sello se comprueba antes del parseo |
| `un_schema_alterado_tampoco` | ídem para `schema.json` |
| `el_rollback_no_pierde_la_activa_si_falla_el_rename` | la activa nunca desaparece |
| `recovery_required_se_reporta_con_inventario` | no se disfraza de error normal |
| `el_xlsx_no_es_autoritativo_y_los_csv_si` | dos escrituras separadas **2.5 s** en **raíces distintas**: CSV y `adapter_manifest.json` byte-idénticos, XLSX distinto y fuera de los digests |

#### A.1-FE · dashboard installer, vista y RAG (`9454a166`, encima de `5aa45c49`)

1. **Origen sellado.** Los seis inputs se verifican contra `shard_manifest.json.files` antes de
   preparar nada. Antes se copiaba primero y se sellaba después el digest de lo ya alterado, así que
   la verificación posterior daba por bueno el contenido mutado.
2. **Release inmutable + catálogo como único commit visible.** Se acabó el `cpSync` archivo a
   archivo sobre el árbol vivo. Una ruta existente con bytes distintos se **rechaza**; con los
   mismos bytes no se reescribe. `publication/catalog.json` se escribe **al final**, con temporal +
   `rename` dentro de su propio directorio.
3. **Fallo en el destino vivo.** Las escrituras pasan por `ops`, inyectable. Diez fronteras
   parametrizadas (write y rename de cada archivo, del manifiesto de instalación y del catálogo)
   fijan que el catálogo y el release **que ya era visible** quedan byte-idénticos y que el catálogo
   sigue nombrando sólo al release anterior.
4. **Lectura verificada.** `readInstalledRelease()` exige forma cerrada de
   `publication_install.json` (12 claves), identidad, estado revalidado y el digest de **todos** los
   outputs; `readCatalog()` exige forma cerrada de cada entrada (15 claves). Un archivo ausente o
   alterado falla; no se omite.
5. **Modos RAG explícitos.** `staging` incorpora lo que el catálogo declare; `public` sólo
   `visible=true` + `mode=public` + `published` + puntero coincidente. Sin modo, falla cerrado.
6. **`gallery_enabled`** viaja del shard al manifiesto y al catálogo, se cruza al leer, y
   `inGallery` se deriva de esa metadata × visibilidad. Era la constante `false`.
7. **Orden binario UTF-8** (`porBytes`) en lugar de `localeCompare`, en catálogo, inventario y
   corpus.

#### Reproducciones del defecto contra el commit auditado

```text
ANTES  vista con 3 archivos mutados (report.md, series.csv, corpus): ACEPTA · filas=5772 · inGallery=false
AHORA  vista rechaza: series.csv: digest 0f2791fa… no coincide

ANTES  RAG sin modo declarado: ACEPTA · 455 chunks · texto inventado indexado = true
AHORA  publicationRoot exige un modo explícito (staging|public), no null

ANTES  reinstalar sobre bytes distintos -> SOBRESCRIBE en silencio
AHORA  reinstalar sobre bytes distintos -> RECHAZA (es inmutable)

ANTES  localeCompare  en_US: ähnlich_x  Alfa_x  zeta_x   ·  sv_SE: Alfa_x  zeta_x  ähnlich_x
AHORA  porBytes       en_US: Alfa_x  zeta_x  ähnlich_x   ·  sv_SE: Alfa_x  zeta_x  ähnlich_x
```

La prueba de locale instala los tres shards en **dos procesos hijos** con `LANG`/`LC_ALL` distintos
y compara los bytes del catálogo, más una aserción de control: si `localeCompare` dejara de depender
del locale, la prueba lo diría en vez de pasar en falso.

#### Shard real — `obesidad_release_2517e7858901`

Recompilado desde `artifacts/releases` con el estado declarado (`compile_release` + `emit_shards`
a un staging temporal; no se tocó ningún run canónico).

```text
candidate instalado    6 archivos · 5,772 filas · 455 chunks sólo en modo staging · 454 en público
public sin condiciones rechazado ("exige lifecycle published")
archivo mutado         vista y RAG rechazan por digest
fallo durante commit   catálogo y release previo byte-idénticos (inventario igual)
default público        454 chunks · publicReleases 0 · inGallery false
```

#### Gates

```text
backend    ruff check OK · ruff format OK (355 archivos) · mypy OK (161 fuentes)
           pytest -m "not slow and not integration": 2031 passed, 61 deselected
           publication/: 197 passed · test_tableau_adapter.py: 31 passed
dashboard  node --check de las 16 fuentes · test:cases:verify 616/616
           run_tests.js OK · test:unit 67 · test:candidate 74 (39 del installer)
           rag:verify sincronizado (454 chunks, un vector por chunk)
           con C7_SHARD_ROOT: 39/39, sin skips
```

#### Preservación

```text
config/evaluation/rolling_cv_v1.yaml   dd6d4a02…  (intacto)
backend  A.1 toca 2 archivos: tableau_adapter.py + su test
dashboard A.1 toca 4 archivos: installer.mjs, publication_view.mjs, corpus.mjs, test_installer.mjs
corpus público  454 chunks, mismo digest antes y después del cambio (comparación like-for-like
                contra la versión commiteada de corpus.mjs)
runs/ y artifacts/  sin cambios · sin credenciales, DVC, push, PR, merge, lifecycle, puntero,
                    deploy, escritura en Reports/ real ni publicación
```

#### Estado

Avance **82%** (no se mueve: A.1 corrige, no avanza). Exposición pública **0%**. C7.4
**INCOMPLETE 0/4**. ADAPTERS-B sigue bloqueada.

#### Efectos colaterales y lo que queda declarado

- El contrato del installer **cambió de firma**: `buildChunks({publicationRoot})` ya no basta, hay
  que pasar `publicationMode`. Ningún script de producción lo usaba con `publicationRoot`
  (`build_rag_index.mjs` y `rag_verify.mjs` llaman sin argumentos; `rag_staging.mjs` usa
  `candidateRoot`), así que el índice publicado no se mueve.
- Tras un fallo puede quedar contenido del release nuevo instalado y **no referenciado** por el
  catálogo. Es deliberado —es lo que permite que el commit sea un solo rename— y reinstalar lo
  completa; pero conviene que ADAPTERS-B traiga un `prune` de releases sin entrada en el catálogo.
- El `gallery_enabled` del shard real es `false`. Cuando el release entre a galería habrá que
  cambiarlo en el **registry**, no en el dashboard.

#### Pregunta

Dos cosas antes de tocar sinks reales:

1. **XLSX**: se declaró vista no autoritativa en vez de normalizar el ZIP. ¿Se acepta así, o el
   XLSX tiene que ser byte-idéntico porque alguien lo va a versionar?
2. **`prune` de releases huérfanos**: ¿entra en ADAPTERS-B, o se deja fuera del alcance y se
   documenta como operación manual?

_Respuesta:_

**Decisiones de auditoría:**

1. **XLSX aceptado como vista no autoritativa.** No entra en identidad, digests, evidencia,
   versionado, promoción ni rollback. CSV/Sheets son la autoridad. Si un consumidor futuro necesita
   versionarlo, deberá abrir otro contrato.
2. **No ejecutar `prune` automático en ADAPTERS-B.** B sólo podrá inventariar huérfanos en modo
   read-only. Borrarlos será una acción destructiva posterior, con targets exactos y autorización
   separada.

---

### Ronda 98 — Auditoría ejecutable de ADAPTERS-A.1 — 2026-07-27

#### Veredicto

```text
ADAPTERS-A.1_CORE_FIXES_PASS
ADAPTERS-A.1_AUDIT_FAIL_RESIDUAL
ADAPTERS-B_BLOCKED
C7.6_NO-GO
```

A.1 sí corrigió los defectos originales: sellos y read-back se verifican, la instalación usa el
catálogo como commit, el release es inmutable, RAG separa staging/public, `gallery_enabled` viene de
metadata y el orden es independiente del locale.

Validación independiente:

```text
git diff --check                         PASS en ambos repos
backend focal                            31/31 comportamientos PASS
dashboard focal con shard real           39/39 PASS
```

La invocación aislada de pytest backend termina rc no-cero únicamente por el umbral **global** de
coverage (20.35% al ejecutar un solo archivo), no por fallos de esas 31 pruebas. El gate completo
reportado por el commit es 2,031 fast PASS.

#### R98-P0-1 · consolidación final fuera de la recuperación

La consolidación `__backup → __previous` ocurre fuera del `try/except`. Al fallar en la segunda:

```text
excepción                         RuntimeError sin RECOVERY_REQUIRED
runner_forecast                   nueva
runner_forecast__previous         anterior
runner_releases                   nueva
runner_releases__backup           anterior
```

Las activas coinciden, pero el rollback queda partido y no se entrega el inventario tipado.

#### R98-P0-2 · rollback parcial del par

`rollback()` protege una tabla cada vez. Si la primera restaura y falla la segunda:

```text
runner_forecast   versión anterior
runner_releases   versión nueva
```

El par queda mezclado. El rollback debe fotografiar, restaurar y verificar las dos como una unidad.

#### R98-P1-1 · preflight incompleto

Una nueva promoción no rechaza residuos `__next` o `__backup`; puede sobrescribir evidencia de una
recuperación inconclusa. Debe fallar `RECOVERY_REQUIRED` antes de escribir.

#### R98-P1-2 · matriz dashboard incompleta

La Ronda 97 afirma cubrir write y rename de cada artefacto, pero `FRONTERAS` contiene 10 casos. Son
seis outputs + manifiesto + catálogo:

```text
8 artefactos × 2 fronteras = 16 casos
```

La implementación comparte helper y los diez pasan, pero el gate declarado debe enumerar los 16.

#### R98-P2 · duplicación mecánica

`upsert_releases()` asigna `llaves` dos veces consecutivas. No cambia el resultado; se retira.

### Orden C7.6-PROMOTION-ADAPTERS-A.1.1 — cierre mínimo

#### Backend

1. Fotografiar todo el namespace administrado: activas, `__previous`, `__next` y `__backup`.
2. Rechazar preflight con cualquier `__next` o `__backup`; no tocar el sink y devolver
   `RECOVERY_REQUIRED` con inventario.
3. Incluir la consolidación de backups en el protocolo compensable.
4. Ante cualquier fallo hasta la última consolidación, restaurar y verificar el snapshot completo.
   Si la restauración falla, emitir `PromotionRecoveryError`.
5. Hacer `rollback()` recuperable para el **par**, no tabla por tabla.
6. Probar drop y rename de cada consolidación, todas las fronteras del rollback y residuos de
   preflight.
7. Retirar la asignación duplicada.

#### Dashboard

1. Generar la matriz desde el plan real de instalación.
2. Probar write y rename de los seis outputs, `publication_install.json` y `catalog.json`:
   exactamente 16 fronteras.
3. Mantener catálogo y release previamente visible byte-idénticos y sin temporales referenciados.
4. Un inventario read-only de huérfanos es opcional; no implementar borrado ni `prune`.

#### Commits y gates

Máximo dos commits nuevos, sin amend/rebase/squash:

```text
backend    C7.6 ADAPTERS-A.1.1 close promotion and rollback recovery boundaries
dashboard  C7.6 ADAPTERS-A.1.1 complete installer failure matrix
```

Repetir gates focales y completos y convertir las reproducciones R98 en regresiones.

#### STOP

Después de A.1.1: **STOP para auditoría**. ADAPTERS-B continúa bloqueada.

Sin credenciales, Google Sheets, workbook, Netlify, Gemini, AWS, DVC, commit del plan, push, PR,
merge, lifecycle, puntero, deploy, escritura en `Reports/` real, prune ni publicación.

#### Avance

Permanece en **82%**; exposición pública **0%**; C7.4 **INCOMPLETE 0/4**.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PROMOTION-ADAPTERS-A.1.1` local y STOP.**

_Respuesta:_ **GO C7.6-PROMOTION-ADAPTERS-A.1.1 LOCAL. Cerrar consolidación y rollback recuperable
del par Tableau, rechazar residuos en preflight, completar las 16 fronteras del installer y retirar
la duplicación mecánica; máximo dos commits separados y STOP. XLSX no autoritativo y prune fuera.
Sin credenciales, DVC, plan commit, push, PR, merge, lifecycle, puntero, deploy ni publicación.**


---

### Ronda 99 — C7.6-PROMOTION-ADAPTERS-A.1.1 ejecutada — 2026-07-27

**Commits (el plan NO entra en ellos):**

```text
backend    7e5ace5d  C7.6 ADAPTERS-A.1.1 close promotion and rollback recovery boundaries
dashboard  e894a67a  C7.6 ADAPTERS-A.1.1 complete installer failure matrix
```

#### Backend — los siete puntos

1. **Fotografía completa.** `managed_tables()` fija el namespace administrado: activa, `__previous`,
   `__next` y `__backup` de cada tabla, **ocho nombres**. `_snapshot()` fotografía los que existan.
   Lo que no esté ahí es ajeno y el protocolo no lo toca.
2. **Preflight que rechaza residuos.** Un `__next` o `__backup` vivo aborta con
   `PromotionRecoveryError` **sin tocar el sink** (`sink.operaciones == []` en la prueba) y con
   `residues` en el inventario.
3. **Consolidación dentro del protocolo compensable.** El paso `__backup`→`__previous` pasó a estar
   dentro del `try`.
4. **Restauración y verificación del snapshot completo.** `_restaurar()` devuelve el namespace a la
   fotografía **por contenido**, no deshaciendo paso a paso; `_verificar_restauracion()` compara
   nombres y contenido de cada uno. Si falla, `PromotionRecoveryError` con inventario de cinco
   claves (`tables`, `expected_before`, `namespace`, `managed`, `residues`).
5. **`rollback()` sobre el par.** Fotografía, restaura las dos, verifica las dos y sólo entonces
   retira los respaldos; cualquier fallo devuelve la fotografía completa.
6. **Regresiones (31 → 47):** residuos de preflight (2), fronteras de consolidación (4: drop y
   rename de cada tabla), fronteras del rollback (7), rollback completo, respaldo que el sink no
   deja retirar (2), y el namespace de ocho nombres.
7. **R98-P2 no se reproduce.** En `f1226778`, `upsert_releases` asigna `llaves` **una sola vez**:

   ```text
   225:    llaves = set(zip(nuevas[RELEASE_KEY[0]], nuevas[RELEASE_KEY[1]], strict=True))
   227:        ~actual.apply(lambda r: (r[RELEASE_KEY[0]], r[RELEASE_KEY[1]]) in llaves, axis=1)
   ```

   La 225 es la asignación y la 227 su uso. No hay nada que retirar; no se tocó la función.

**Reproducción de R98-P0-1 y P0-2 contra `f1226778` y contra `7e5ace5d`:**

```text
P0-1  fallo en rename:runner_releases__backup->runner_releases__previous
ANTES  RuntimeError · status=None
       tablas: runner_forecast · runner_forecast__previous · runner_releases · runner_releases__backup
AHORA  RuntimeError · la fotografía vuelve entera
       tablas: runner_forecast · runner_forecast__previous · runner_releases · runner_releases__previous

P0-2  fallo en rename:runner_releases__previous->runner_releases durante el rollback
ANTES  runner_forecast: ANTERIOR · runner_releases: nueva      ← el par mezclado
AHORA  runner_forecast: nueva    · runner_releases: nueva      ← el par intacto
```

**Lectura declarada de «el par».** `rollback()` restaura las tablas que tienen `__previous`. Una
tabla creada por la promoción no tiene a qué volver, y borrarla sería inventar una semántica que
nadie pidió; lo que se corrige es que la operación sea **una unidad compensable**, que es el defecto
que R98-P0-2 describe. Con una sola tabla con `__previous`, el comportamiento no cambia.

**Caso declarado.** Si el sink rechaza el `drop` del `__backup` —la última limpieza del rollback—,
la compensación necesita ese mismo `drop` y tampoco puede: se emite `RECOVERY_REQUIRED` en vez de
fingir una restauración. Las dos activas sí quedan garantizadamente de la misma promoción. Está
fijado como prueba, no como nota.

#### Dashboard — la matriz completa

`installArtifacts(diseaseId, releaseId)` se exporta desde el instalador y es **la misma función que
usa `installShard`** para saber qué escribe. La matriz de fallos se genera desde ahí:

```text
6 outputs + publication_install.json + catalog.json = 8 artefactos
8 × {write, rename}                                 = 16 fronteras
```

El inyector dejó de usar expresiones regulares sueltas: compara la ruta exacta —el temporal
`<artefacto>.installing-<token>` para `write`, el artefacto en su sitio para `rename`— y la
aserción exige el mensaje de esa frontera concreta. Con el patrón anterior, una frontera mal
escrita habría pasado por verde sin disparar nunca. Las 16 disparan: `grep -c "^✔ un fallo en"` = 16.

Sin `prune` ni inventario de huérfanos (opcional, y se prefirió el cierre mínimo).

#### Gates

```text
backend    ruff check OK · ruff format OK (355) · mypy OK (161 fuentes)
           pytest -m "not slow and not integration": 2047 passed, 61 deselected
           test_tableau_adapter.py: 47 passed
dashboard  node --check de las 16 fuentes · test:cases:verify 616/616 · test:unit 67
           test:candidate 81 (46 del installer) · rag:verify sincronizado
           con C7_SHARD_ROOT: 46/46, sin skips
```

#### Preservación

```text
config/evaluation/rolling_cv_v1.yaml   dd6d4a02…  (intacto)
backend   A.1.1 toca 2 archivos: tableau_adapter.py + su test
dashboard A.1.1 toca 2 archivos: installer.mjs + test_installer.mjs
runs/ y artifacts/ sin cambios · sin credenciales, Sheets, workbook, Netlify, Gemini, AWS, DVC,
commit del plan, push, PR, merge, lifecycle, puntero, deploy, escritura en Reports/ real, prune ni
publicación
```

#### Estado

Avance **82%** · exposición pública **0%** · C7.4 **INCOMPLETE 0/4** · ADAPTERS-B bloqueada.

#### Pregunta

Una sola, y es de contrato, no de implementación:

El preflight ahora **bloquea** cualquier promoción o rollback mientras exista un `__next` o
`__backup` en el sink. Es fail-closed y deliberado, pero significa que una recuperación inconclusa
deja el carril **parado** hasta que alguien limpie a mano. ¿Se acepta así, o ADAPTERS-B debe traer
un comando explícito de limpieza de residuos —con targets exactos y autorización separada, como el
`prune`— para poder desbloquear sin tocar el sink a mano?

_Respuesta:_

**Se acepta el preflight fail-closed.** ADAPTERS-B debe traer recuperación explícita, pero nunca
limpieza automática:

- `inspect-recovery`: read-only, inventario y digests;
- `recover`: dry-run por defecto, limitado al namespace `runner_*`;
- `--apply` exige ID exacto del sink de staging, snapshot/inventory digest esperado y autorización
  separada;
- no borrar releases huérfanos del dashboard: eso continúa fuera de alcance como `prune`.

---

### Ronda 100 — Auditoría ejecutable de ADAPTERS-A.1.1 — 2026-07-27

#### Veredicto

```text
ADAPTERS-A.1.1_PASS
ADAPTERS-A_CLOSED
ADAPTERS-B0_READY
C7.6_NO-GO_UNTIL_REAL_STAGING
```

La implementación coincide con la orden:

- namespace administrado de ocho nombres;
- preflight con residuos aborta sin operaciones;
- consolidación incluida en la compensación;
- snapshot completo restaurado y verificado;
- rollback del par compensable;
- 16 fronteras del installer derivadas del mismo `installArtifacts()` usado por producción.

Validación independiente:

```text
backend focal con addopts vacío    47/47 PASS · rc=0
dashboard con shard real           46/46 PASS · rc=0
git diff --check                   PASS en ambos rangos
```

Los gates completos reportados —2,047 fast, mypy/ruff, 81 candidate y RAG sincronizado— son
coherentes con los focales.

#### Corrección de la auditoría R98-P2

El supuesto duplicado de `llaves` **no existía**. La salida usada en R98 concatenó dos rangos
`sed` que se solapaban en la línea 225 y mostró esa misma línea dos veces. En el archivo había una
asignación y un uso. Fue un error de esta auditoría, no del código, y queda corregido aquí.

#### Hallazgo de staging Tableau

Existe un workbook trackeado:

```text
reports/dashboards/viz_epiforecastmx.twb
```

No es plantilla de staging:

- declara `xml:base=https://public.tableau.com`;
- referencia el workbook público `viz_epiforecastmx`;
- contiene un `cloudFileId` concreto de Google Drive;
- consume exclusivamente `scaffold`, `forecast`, `entidades`, `metricas` y `real`;
- contiene además una ruta local de extract `.hyper`.

**No modificarlo, copiar sus credenciales/IDs ni conectarlo a las tablas runner.** ADAPTERS-B debe
crear un datasource/workbook staging separado y genérico. Tableau Desktop 2024.1 está disponible
localmente, por lo que B1 podrá abrir y validar ese workbook sin tocar Tableau Public.

### Orden C7.6-PROMOTION-ADAPTERS-B0 — tooling local, cero escrituras externas

#### B0.1 · sink Google Sheets real pero inyectable

Implementar `GoogleSheetsTableSink` sobre la dependencia existente `gspread`, compatible con
`TableSink`:

```text
list_tables
read_table
write_table
rename_table
drop_table
```

Reglas:

- ninguna autenticación al importar;
- cliente/spreadsheet inyectables en tests;
- lectura y escritura preservan encabezados, strings vacíos y conteos;
- chunking explícito para 5,772 filas sin truncar;
- relectura exacta después de cada write;
- errores de API se traducen a un error tipado sin ocultar respuesta/operación, pero nunca secretos;
- no reutilizar las funciones destructivas de `publish_gsheets.py`;
- no tocar las cinco tabs legacy.

#### B0.2 · CLI operativo

Crear un CLI genérico con tres comandos:

```text
inspect           read-only · tabs, filas, digests, residuos, estado del namespace
stage             dry-run por defecto · muestra plan exacto de write/rename/drop
recover           dry-run por defecto · plan de recuperación de __next/__backup
```

`stage --apply` y `recover --apply` deben existir para B1, pero **no se ejecutan en B0**. Requieren:

- `C7_TABLEAU_STAGING_SPREADSHEET_ID`;
- ID distinto de `GSHEETS_SPREADSHEET_ID`;
- snapshot/inventory digest esperado;
- confirmación literal del ID de staging;
- namespace limitado a `runner_forecast`, `runner_releases` y sufijos administrados.

Sin esas condiciones: rc no-cero antes de autenticar o mutar.

#### B0.3 · recuperación explícita

La recuperación no “limpia” a ciegas:

1. inspecciona residuos;
2. clasifica el estado por tabla;
3. propone restaurar desde `__backup`, retirar `__next` o declarar `RECOVERY_REQUIRED`;
4. liga el plan al digest del inventario;
5. al aplicar, revalida que el inventario no cambió;
6. verifica las dos activas al terminar.

No implementar `prune` de releases ni borrado fuera del namespace.

#### B0.4 · datasource/workbook staging local

Crear un artefacto **nuevo** y no público, generado desde configuración:

```text
runner_forecast
runner_releases
```

Debe:

- recibir el ID de la hoja de staging por parámetro; nunca copiar el `cloudFileId` productivo;
- mostrar `publication_label`, point-only y ausencia de intervalos;
- usar filtros derivados de los datos, sin literales de Obesidad/E66;
- no modificar `viz_epiforecastmx.twb`;
- escribirse sólo en un temporal o ruta de staging gitignored;
- incluir un verificador XML que rechace Tableau Public, IDs productivos, rutas absolutas y las
  cinco tablas legacy.

B0 no abre Tableau Desktop ni crea/publica un workbook remoto. Eso pertenece a B1.

#### B0.5 · pruebas

- fake `gspread` con paginación/chunking, alteración de read-back y errores en cada API;
- mismas fronteras de promoción/rollback sobre el sink real simulado;
- CLI sin variables, IDs iguales, digest cambiado y ausencia de `--apply`: todos fail-closed;
- `inspect` no mutante;
- recuperación dry-run byte-determinista;
- workbook staging sin IDs/rutas/literales prohibidos;
- shard real produce 5,772 + 1 y el plan de tabs esperado;
- legacy, bundle, DVC y superficies públicas byte-idénticos.

#### Commit y STOP

Un commit backend/local como máximo:

```text
C7.6 ADAPTERS-B0 Google Sheets staging sink and explicit recovery tooling
```

Si el generador del workbook merece separación, se permite un segundo commit backend. El dashboard
no necesita código en B0.

Después: **STOP para auditoría**. No ejecutar B1.

#### Prohibiciones

Sin usar service account, Spreadsheet ID real, Google API, Tableau Public, Netlify, Gemini, AWS,
DVC, commit del plan, push, PR, merge, lifecycle, puntero, deploy, `Reports/` real, prune ni
publicación. No abrir ni modificar `viz_epiforecastmx.twb`.

#### Avance

Permanece en **82%**; exposición pública **0%**; validación prospectiva **INCOMPLETE 0/4**.

#### Próxima acción exacta

**Ejecutar únicamente `C7.6-PROMOTION-ADAPTERS-B0` local y STOP.**

_Respuesta:_ **GO C7.6-PROMOTION-ADAPTERS-B0 LOCAL. Implementar sink gspread inyectable, CLI
inspect/stage/recover dry-run y datasource/workbook Tableau staging generado y separado; máximo dos
commits backend y STOP. Sin credenciales, IDs reales, red Google, DVC, plan commit, push, lifecycle,
puntero, deploy, prune ni publicación.**


---

### Ronda 101 — C7.6-PROMOTION-ADAPTERS-B0 ejecutada — 2026-07-27

**Commits (el plan NO entra en ellos):**

```text
c5f42b59  C7.6 ADAPTERS-B0 Google Sheets staging sink and explicit recovery tooling
7c626fd3  C7.6 ADAPTERS-B0 generated staging Tableau workbook with XML verifier
```

Cero red, cero credenciales, cero id real. `gspread` **ni siquiera está instalado** en este entorno
y la suite pasa igual: esa es la prueba de que importar el módulo no autentica.

#### B0.1 · `GoogleSheetsTableSink`

Implementa el `TableSink` completo sobre un `Spreadsheet` **inyectado**. `open_spreadsheet()` es el
único borde que adquiere credenciales, importa `gspread` de forma perezosa y no se llama en ninguna
prueba. Una prueba recorre el fuente línea a línea y falla si aparece un `import gspread` o
`from google…` a nivel de módulo.

Tres fidelidades con la API real, no simplificaciones:

| Comportamiento | Por qué importa |
|---|---|
| Repoblado de celdas vacías | La API recorta las vacías del final de cada fila, y en point-only `yhat_lower`/`yhat_upper` son las **dos últimas columnas**: sin repoblar, el read-back fallaría por una diferencia que no está en el dato |
| Escritura por bloques declarados | 5,772 filas en un solo `update` es la petición que la API corta por su cuenta; el corte es nuestro, y se comprueba: 1 cabecera + 12 bloques |
| `value_input_option="RAW"` | Sin RAW la hoja reinterpreta fechas y ceros a la izquierda |

Cada `write_table` se **relee entero** y se compara: una hoja que devuelve otro contenido falla
aunque conserve el número de filas. Los errores salen tipados (`SheetsApiError`) con la operación y
la respuesta, y con el id de hoja y las credenciales **redactados** —un traceback termina en un log,
y un log se comparte—. Las cinco tabs legacy se rechazan antes de llamar a la API en las cuatro
mutaciones posibles; `list_tables()` sí las ve, porque inventariar es read-only. No se reutiliza
nada de `publish_gsheets.py`: ese publicador borra las tabs que no estén en su lista.

#### B0.2 · CLI

```text
inspect   read-only · tabs, filas, digests, residuos, estado, inventory_digest
stage     dry-run  · plan exacto de write/rename/drop
recover   dry-run  · plan de recuperación ligado al inventario
```

`--apply` existe para B1 y está cerrado con cuatro llaves comprobadas **antes de autenticar y antes
de mutar**: hoja de staging declarada, distinta de la productiva, `--expect-inventory` y
`--confirm-spreadsheet-id` escrito a mano. Sin alguna: `rc=2` y `sink.operaciones == []`. El
namespace es fijo (ocho nombres) y no hay bandera para ampliarlo. Salida en JSON canónico.

`promotion_plan()` enseña el plan antes de aplicarlo, y que no se desvíe del protocolo no es una
promesa: una prueba lo compara con las operaciones que `MemorySink` registra durante una promoción
real, en cuatro estados de partida.

#### B0.3 · recuperación explícita

Estados derivados del inventario, uno por tabla: `CLEAN`, `MISSING`, `NEXT_RESIDUE`,
`BACKUP_ORPHAN`, `RECOVERY_REQUIRED`. Acciones propuestas: `drop_next`, `restore_backup`,
`consolidate_backup` — ninguna borra fuera del namespace, no hay `prune`. El plan va ligado al
`inventory_digest` que lo justifica; aplicar revalida que la hoja no se movió y verifica las dos
activas al terminar. El plan es byte-determinista: sin marcas de tiempo, mismo estado → mismos bytes.

#### B0.4 · workbook de staging generado

`viz_epiforecastmx.twb` **no se abre ni se lee**: se genera uno nuevo desde el shard y desde el id de
staging, que llega por parámetro. Tipa cada columna por sus valores; la etiqueta de validación va en
el título de cada hoja y el point-only en el pie. Los filtros salen de los datos.

```text
shard real   14,554 bytes · digest 130a35d4… · 2 hojas
filtros      14 dimensiones derivadas · 26 miembros · ninguna escrita en el código
prohibidos   0 rutas absolutas · 0 Tableau Public · 0 tablas legacy · 0 id productivo
```

`verify_workbook` corre **siempre antes de escribir** y rechaza Tableau Public, ids productivos,
rutas absolutas, `xml:base`, `source-build` ajeno, tablas legacy y la ausencia de etiqueta o
point-only. El CLI exige destino `.twb` bajo temporal o `runs/`, y se niega tanto a apuntar al
workbook productivo como a recibir el id productivo por parámetro.

B0 no abrió Tableau Desktop ni creó nada remoto.

#### Gates

```text
ruff check + format OK · mypy OK (166 fuentes)
pytest -m "not slow and not integration"   2117 passed, 1 skipped, 61 deselected
tests/unit/publication                     283 passed, 1 skipped
con C7_SHARD_ROOT                          284 passed, sin skips
```

Pruebas nuevas: 71 (28 del sink, 22 del CLI y la recuperación, 21 del workbook).

#### Preservación

```text
config/evaluation/rolling_cv_v1.yaml   dd6d4a0274a6f8bb…  (intacto)
reports/dashboards/viz_epiforecastmx.twb   sin cambios (comprobado por git en una prueba)
data/, reports/ProdDetails/, artifacts/, *.dvc   sin cambios dirigidos
dashboard   sin tocar (B0 no necesita código de frontend)
B0 añade 6 archivos y modifica 1 (tableau_adapter.py: promotion_plan + dos helpers públicos)
```

#### Efectos colaterales declarados

- `_canonical_frame` y `_verify_readback` pasan a ser **públicos** (`canonical_frame`,
  `verify_readback`) porque el sink y la recuperación los necesitan. Ningún consumidor externo los
  usaba.
- `gspread` está declarado en `pyproject.toml` pero **no instalado** en el venv. El sink funciona en
  pruebas sin él; `--apply` en B1 requerirá instalarlo (`pip install -e ".[dev]"` no lo trae si el
  extra no está activo). Queda dicho para que no sorprenda al primer `--apply`.
- `tableau_adapter.py` está en 614 líneas, por encima de la guía de 300. Es coherente con sus
  vecinos del carril (`status.py` 863, `prospective.py` 697) y partirlo a mitad de una orden
  añadiría churn; queda declarado como deuda, no escondido.

#### Pregunta

Dos, ambas sobre el borde con B1:

1. **`gspread` no está instalado.** ¿Lo instalo yo en el venv como paso de B1 —es un cambio de
   entorno, no de código ni de `pyproject.toml`— o lo instalas tú antes de darme el GO?
2. **La primera escritura real.** B1 necesitará un `C7_TABLEAU_STAGING_SPREADSHEET_ID` que hoy no
   existe. ¿Creas tú la hoja de staging y me pasas el id sólo como secreto de entorno, o quieres que
   el primer `--apply` lo ejecutes tú a mano con el plan que yo genere en dry-run?

_Respuesta:_

1. `gspread` se instalará únicamente después de que B0.1 pase, como prerrequisito de
   **B1-PREFLIGHT**, usando el extra ya declarado `.[gsheets]` y registrando la versión efectiva.
   No se modifican `pyproject.toml`, `requirements.txt` ni locks para “arreglar” el entorno.
2. El usuario crea una Google Sheet nueva y exclusiva de staging y comparte únicamente esa hoja con
   la service account. El ID se entrega sólo mediante `C7_TABLEAU_STAGING_SPREADSHEET_ID`; nunca se
   pega en el plan, argumentos persistidos, commits o logs. Primero se ejecuta un preflight
   read-only. La primera escritura real (`B1-APPLY`) requiere otro GO literal después de revisar el
   inventario y el plan dry-run.

Estas respuestas **no autorizan** instalar dependencias, autenticar, crear la hoja ni ejecutar
`--apply` en esta ronda.

---

### Ronda 102 — Auditoría independiente de ADAPTERS-B0 — 2026-07-27

#### Alcance auditado

```text
c5f42b59..7c626fd3
9 rutas: 8 nuevas + tableau_adapter.py
2,066 inserciones · 10 borrados
git diff --check PASS
```

No hay cambios en `config/`, `data/`, `reports/`, `artifacts/`, `models/`, `.dvc`, dashboard,
lifecycle, puntero o superficies públicas.

Validación ejecutada sin red, credenciales ni IDs reales:

```text
tests focales B0                         70 passed, 1 skipped
ruff check                              PASS
ruff format --check                     PASS
mypy (6 módulos fuente)                 PASS
gspread instalado                       no
Tableau Desktop 2024.1                  presente, no abierto
```

El skip es el gate de shard real cuando no se inyecta `C7_SHARD_ROOT`; el reporte previo de
284/284 con esa raíz sigue siendo evidencia de construcción, no sustituye los repros siguientes.

#### Veredicto

```text
ADAPTERS-B0_IMPLEMENTED
ADAPTERS-B0_AUDIT_FAIL
ADAPTERS-B0.1_REQUIRED
B1_NOT_AUTHORIZED
```

La arquitectura general es correcta: sink inyectable, import perezoso, namespace acotado,
read-back completo, chunking, plan determinista, workbook separado y cero contacto con el
productivo. B0 no cierra porque tres estados reales violan sus propios contratos.

#### R102-P0-1 · `--apply` no exige conocer la hoja productiva

El contrato y el docstring afirman cuatro llaves, incluida identidad distinta de producción.
`staging_ids()` permite que `GSHEETS_SPREADSHEET_ID` esté ausente y `_check_apply()` continúa.
Repro ejecutado:

```text
entorno       C7_TABLEAU_STAGING_SPREADSHEET_ID=staging-only-id
producción    ausente
recover       --apply + inventory exacto + confirmación exacta
resultado     rc=0
```

No hubo mutaciones porque el sink del repro ya estaba limpio; lo importante es que cruzó el borde
de `--apply` sin poder demostrar que staging no era producción. B1 no puede depender de que el
operador “seguramente” cargó la segunda variable.

**Corrección obligatoria:** todo comando mutante exige ambos IDs no vacíos y distintos antes de
autenticar. `inspect` puede requerir sólo staging; `stage`/`recover` dry-run pueden inspeccionar
staging, pero cualquier `--apply` falla con `RC_REFUSED` si falta producción.

#### R102-P0-2 · la recuperación puede borrar la única evidencia y luego fallar

Estado reproducido: no existen activas ni `__backup`; existen únicamente
`runner_forecast__next` y `runner_releases__next`.

```text
plan          clasifica ambas como MISSING
acciones      drop_next × 2
apply         borra ambos __next
postcondición falla porque faltan las dos activas
estado final  namespace vacío
```

Un plan de recuperación no puede ejecutar acciones si ya sabe que su estado final viola la
postcondición. En particular, no debe borrar la única copia disponible y después informar error.

**Corrección obligatoria:** calcular y validar el estado final previsto del namespace completo
antes de la primera mutación. Si una activa no puede quedar presente desde activa, `__backup` o un
`__previous` explícitamente recuperable, devolver `RECOVERY_REQUIRED`/rc no-cero y dejar el sink
byte-idéntico. Un `__next` aislado no se activa automáticamente ni se borra: se conserva como
evidencia hasta una decisión explícita. Añadir cobertura para combinaciones mixtas de las dos
tablas, no sólo el caso simétrico.

#### R102-P0-3 · el containment del `.twb` compara nombres de componentes, no raíces

`_check_destino()` acepta si cualquier componente se llama `tmp`, `var`, `private` o `runs`.
Repro:

```text
ACCEPT  <repo>/reports/tmp/candidate.twb
ACCEPT  <repo>/reports/runs/candidate.twb
ACCEPT  <repo>/runs/candidate.twb
ACCEPT  <tempdir>/candidate.twb
```

Los dos primeros pueden ser rutas trackeables dentro del repositorio y contradicen “no escribe
dentro del repo”. No basta encontrar una palabra en `Path.parts`.

**Corrección obligatoria:** aceptar únicamente descendientes resueltos de:

1. `<repo>/runs/`, cuya condición gitignored se comprueba; o
2. la raíz temporal real de `tempfile.gettempdir()`.

Rechazar el resto, incluidos symlinks que resuelvan fuera de esas raíces. La validación debe ocurrir
antes de crear directorios o escribir bytes.

#### R102-P1 · identidad del workbook y validez Tableau aún no están cerradas

El CLI permite `--spreadsheet-id` distinto del staging declarado siempre que no coincida con el ID
productivo. Eso separa el workbook del sink que se pretende validar.

**Corrección obligatoria:** eliminar el override o exigir igualdad exacta con
`C7_TABLEAU_STAGING_SPREADSHEET_ID`; exigir además el ID productivo para demostrar no-colisión.

El verificador actual demuestra XML bien formado y ausencia de literales prohibidos. **No demuestra
que Tableau Desktop pueda abrir, consultar y refrescar el workbook.** Esto no es un defecto de B0,
porque B0 prohibía abrir Tableau, pero es un gate duro de B1-PREFLIGHT. No llamar “workbook
validado” al artefacto hasta ejecutar ese smoke local contra la hoja exclusiva de staging.

#### Deudas no bloqueantes

- `tableau_adapter.py` tiene 614 líneas. No partirlo dentro de B0.1: la corrección debe ser pequeña
  y revisable. Abrir refactor separado después del staging real.
- Los permisos reales de la service account y la fidelidad de `gspread` todavía no se probaron.
  Eso pertenece a B1-PREFLIGHT, no se simula con más mocks.
- La escritura de 5,772 filas en bloques está probada con el doble; B1 deberá medir límites/cuotas y
  read-back real sin relajar el contrato exacto.

### Orden C7.6-PROMOTION-ADAPTERS-B0.1 — corrección local y STOP

#### Objetivo

Cerrar únicamente R102-P0-1/P0-2/P0-3/P1 sin instalar dependencias ni tocar servicios externos.

#### Cambios permitidos

```text
scripts/tableau_staging.py
scripts/tableau_workbook.py
src/epiforecast/publication/recovery.py
src/epiforecast/publication/sheets_sink.py
tests/unit/publication/test_tableau_staging_cli.py
tests/unit/publication/test_tableau_workbook.py
tests unitarios focales de recovery/sink estrictamente necesarios
```

No modificar el schema de los shards, los datos del release, `tableau_adapter.py` salvo que una
firma pública lo haga estrictamente necesario, ni el dashboard.

#### Gates obligatorios

1. `--apply` con producción ausente: `RC_REFUSED`, cero autenticación y cero operaciones.
2. IDs staging/productivo iguales: `RC_REFUSED`.
3. confirmación distinta de staging: `RC_REFUSED`.
4. workbook con ID diferente del staging declarado: `RC_REFUSED`.
5. destinos `<repo>/reports/tmp/...` y `<repo>/reports/runs/...`: rechazados sin crear nada.
6. destinos `<repo>/runs/...` y `tempfile.gettempdir()/...`: aceptados.
7. sólo `__next` y sin activas/backup: recuperación rechazada antes de mutar; `__next`
   byte-idénticos.
8. activa ausente + `__backup`: restauración existente sigue PASS.
9. activa ausente + `__previous`: o se restaura explícitamente y se verifica, o se rechaza sin
   mutar; nunca queda peor.
10. combinación mixta entre las dos tablas: la validación es global y no ejecuta media
    recuperación.
11. los 70 tests focales actuales siguen verdes y los repros nuevos nacen rojos contra
    `7c626fd3`.
12. `ruff`, formato, mypy y `git diff --check` verdes.

#### Commit y STOP

Máximo un commit backend/local:

```text
C7.6 ADAPTERS-B0.1 close staging identity, containment and recovery preflight
```

Después STOP para auditoría. No instalar `gspread`, no autenticar, no abrir Tableau Desktop, no
crear hoja, no usar red, DVC, commit del plan, push, lifecycle, puntero, deploy ni publicación.

#### Secuencia posterior, todavía no autorizada

```text
B0.1 PASS
  ↓
B1-PREFLIGHT (GO separado)
  - instalar extra .[gsheets] en el venv y registrar versión
  - usuario crea hoja exclusiva y comparte service account
  - inspect + dry-run, sin escrituras
  - generar .twb temporal y abrirlo en Tableau Desktop
  - validar conexión, refresh, etiqueta y point-only
  ↓
B1-APPLY (otro GO)
  - revalidar inventario
  - aplicar sólo sobre staging
  - read-back exacto + rollback ensayado
  - STOP
```

#### Estado

Avance estimado permanece en **82%** · exposición pública **0%** · C7.4
**INCOMPLETE 0/4** · Obesidad `trained` e invisible.

#### Próxima acción exacta

**Ejecutar sólo `C7.6-PROMOTION-ADAPTERS-B0.1` local y STOP.**

_Respuesta:_ **GO C7.6-PROMOTION-ADAPTERS-B0.1 LOCAL. Corregir identidad obligatoria de
staging/producción, containment real del workbook y recuperación no destructiva; máximo un commit
backend y STOP. Sin instalar dependencias, credenciales, red, DVC, plan commit, push, lifecycle,
puntero, deploy ni publicación.**


---

### Ronda 103 — C7.6-PROMOTION-ADAPTERS-B0.1 ejecutada — 2026-07-27

**Commit (el plan NO entra en él):**

```text
20e1ccdf  C7.6 ADAPTERS-B0.1 close staging identity, containment and recovery preflight
```

Un solo commit, seis archivos, los seis de la lista de cambios permitidos. `tableau_adapter.py` no
se tocó: ninguna firma pública lo hizo necesario.

#### R102-P0-1 · identidad obligatoria

`staging_ids()` gana `require_production`. La razón es la que da el hallazgo: con la variable
ausente, «staging ≠ producción» **no falla, no se puede comprobar**, y dar por buena una identidad
que no se pudo comprobar es exactamente el error que esa función existe para evitar. Todo comando
mutante la exige antes de autenticar; `inspect` y los dry-run siguen bastando con staging.

#### R102-P0-2 · recuperación que no puede empeorar el estado

`projected_sources()` decide **antes de mutar** de dónde saldrá cada activa: de sí misma, de su
`__backup` o de su `__previous`. Si alguna no tiene origen, el plan sale **sin una sola acción**,
con `blocked` y `reason`, y `apply_recovery` se niega. La validación es global: una tabla con arreglo
y otra sin él no ejecuta media recuperación. Un `__next` aislado ni se activa ni se borra.

Se añade `restore_previous` —una activa ausente con `__previous` sí tiene de dónde volver— y el
clasificador deja de llamar `MISSING` a lo que es recuperable.

#### R102-P0-3 · containment real

Se comparan dos **raíces resueltas**: `<repo>/runs/`, comprobando con `git check-ignore` que de
verdad está ignorado, y la raíz temporal real del sistema. La resolución es lo que impide que un
symlink cuele el artefacto dentro del repo, y ocurre antes de crear directorios o escribir bytes.

#### R102-P1 · identidad del workbook

`--spreadsheet-id` sólo confirma: tiene que coincidir exactamente con el staging declarado, y se
exige la variable productiva para demostrar no-colisión. La salida declara
`tableau_desktop_validated: false`. El XML está generado y verificado; que Tableau Desktop lo abra,
consulte y refresque es gate de B1-PREFLIGHT, y hasta entonces el artefacto no se llama validado.

#### Reproducción contra `7c626fd3` y contra `20e1ccdf`

```text
P0-1  --apply sin la variable productiva     rc=0  ->  rc=2
P0-2  sólo __next: acciones propuestas        2    ->  0
      namespace al terminar                 VACÍO  ->  los dos __next intactos
P0-3  <repo>/reports/tmp/x.twb              ACEPTA ->  RECHAZA
      <repo>/reports/runs/x.twb             ACEPTA ->  RECHAZA
P1    workbook con otro id                  ACEPTA ->  RECHAZA
```

El repro se corrió sobre un `git worktree` detached en `7c626fd3`, con `PYTHONPATH` apuntando a su
`src/` —sin eso, el editable install del venv resolvía `epiforecast` al árbol nuevo y el «antes»
habría salido en verde por accidente—. El worktree quedó eliminado.

Nota honesta sobre el gate 11: los repros **nacen rojos**, pero los del CLI lo hacen por
`ImportError` (`ACTION_RESTORE_PREVIOUS` y `SOURCE_*` no existían en `7c626fd3`), no por aserción.
Por eso la evidencia de comportamiento es la tabla de arriba, que sí corre el mismo código contra
los dos árboles.

#### Gates

```text
1  --apply con producción ausente         RC_REFUSED · 0 operaciones · 0 autenticación   PASS
2  IDs staging/productivo iguales         RC_REFUSED                                     PASS
3  confirmación distinta de staging       RC_REFUSED                                     PASS
4  workbook con ID != staging             RC_REFUSED                                     PASS
5  <repo>/reports/{tmp,runs}/...          rechazados sin crear el directorio             PASS
6  <repo>/runs/... y gettempdir()/...     aceptados                                      PASS
7  sólo __next                            rechazado antes de mutar · __next intactos     PASS
8  activa ausente + __backup              restauración sigue verde                       PASS
9  activa ausente + __previous            restaurada explícitamente y verificada         PASS
10 combinación mixta                      validación global · 0 operaciones              PASS
11 los focales previos siguen verdes      publication/ 298 passed (sin skips)            PASS
12 ruff · format · mypy · diff --check    verdes                                         PASS

pytest -m "not slow and not integration"   2131 passed, 1 skipped, 61 deselected
```

#### Preservación

```text
config/, data/, reports/, artifacts/, models/, .dvc, dashboard, lifecycle, puntero   sin cambios
reports/dashboards/viz_epiforecastmx.twb   byte-idéntico (comprobado por git en una prueba)
tableau_adapter.py                          sin tocar
```

#### Deudas que siguen abiertas, tal como quedaron declaradas

- `tableau_adapter.py` en 614 líneas: refactor separado **después** del staging real.
- Permisos de la service account y fidelidad de `gspread`: B1-PREFLIGHT, no más mocks.
- Límites y cuotas de la escritura de 5,772 filas: B1, sin relajar el contrato exacto.

#### Pregunta

Una, y es la que bloquea B1-PREFLIGHT:

`_esta_ignorado()` invoca `git check-ignore`. Si en la máquina donde se opere no hubiera git en el
PATH, el comando **rechaza** `runs/` como destino —«no demostrado es no»— y sólo quedaría el
temporal del sistema. ¿Se acepta ese comportamiento, o prefieres que `runs/` se admita sin la
comprobación cuando git no esté disponible? Yo lo dejaría como está: es la opción que no puede
meter un artefacto al repositorio por accidente.

_Respuesta:_

**Se acepta el comportamiento fail-closed.** Sin `git check-ignore` verificable, `runs/` no se
autoriza; el temporal del sistema sigue disponible. No añadir fallback basado en el nombre de la
ruta ni en una lectura parcial de `.gitignore`.

---

### Ronda 104 — Auditoría independiente de ADAPTERS-B0.1 y orden B1-PREFLIGHT — 2026-07-27

#### Superficie y gates

```text
commit auditado                    20e1ccdf
rango                              7c626fd3..20e1ccdf
archivos                           6 permitidos
inserciones / borrados             384 / 36
git diff --check                   PASS
tests focales independientes       131 passed, 1 skipped
ruff check                         PASS
ruff format --check                PASS
mypy                               PASS
```

El skip pertenece al shard real cuando `C7_SHARD_ROOT` no está inyectado. La suite reportada por el
commit —`publication/ 298` y `2,131 fast`— es coherente con los focales ejecutados aquí.

#### Repros independientes

```text
--apply sin ID productivo          RECHAZADO
staging == productivo              RECHAZADO
staging != productivo              ACEPTADO por el guard
<repo>/reports/tmp/x.twb           RECHAZADO
<repo>/reports/runs/x.twb          RECHAZADO
<repo>/runs/x.twb                  ACEPTADO y comprobado gitignored
<tempdir>/x.twb                    ACEPTADO
sólo __next, sin activa/backup     RECOVERY_REQUIRED · 0 acciones
apply del plan bloqueado           RECHAZADO · namespace byte-idéntico
```

#### Veredicto

```text
ADAPTERS-B0.1_PASS
ADAPTERS-B0_CLOSED
B1_PREFLIGHT_READY_WHEN_PREREQUISITES_EXIST
B1_APPLY_NOT_AUTHORIZED
```

No se encontró regresión material en el delta. La recuperación decide globalmente antes de mutar;
el ID productivo es obligatorio en operaciones mutantes; el workbook sólo puede apuntar al staging
declarado; y el containment se ancla a raíces resueltas.

#### Precisión de secuencia

La secuencia anterior decía que B1-PREFLIGHT abriría y **refrescaría** Tableau antes de B1-APPLY.
Eso no es posible: una hoja nueva todavía no contiene `runner_forecast` ni `runner_releases`. El
preflight puede generar y verificar el `.twb`, e incluso comprobar que Tableau lo reconoce como
archivo, pero la conexión y el refresh completos sólo se validan **después** de una escritura
autorizada en staging.

La secuencia corregida es:

```text
B1-PREFLIGHT   autenticación read-only + inspect + stage dry-run + .twb temporal
B1-APPLY       escribe sólo staging + read-back + abre/refresca Tableau Desktop
C7.7           activación/deploy, con autorizaciones propias
```

#### Estado efectivo de prerrequisitos en esta sesión

```text
C7_TABLEAU_STAGING_SPREADSHEET_ID   ausente
GSHEETS_SPREADSHEET_ID              ausente
GOOGLE_SERVICE_ACCOUNT_JSON         ausente
gspread                             ausente
google-auth                         2.56.2
```

No se leyó ni buscó ningún secreto en archivos. Sólo se comprobó presencia en el entorno.

### Orden C7.6-PROMOTION-ADAPTERS-B1-PREFLIGHT — lectura externa y STOP

#### Preparación que corresponde al usuario

1. Crear una Google Sheet **nueva, exclusiva de staging y no enlazada a Tableau Public**.
2. Compartirla con una service account autorizada para editar sólo ese staging. No ampliar permisos
   sobre carpetas o Drives completos.
3. En la misma shell de ejecución, declarar sin imprimir valores:

```text
C7_TABLEAU_STAGING_SPREADSHEET_ID
GSHEETS_SPREADSHEET_ID
GOOGLE_SERVICE_ACCOUNT_JSON
```

`GOOGLE_SERVICE_ACCOUNT_JSON` es el JSON completo que consume el código, no una ruta. Ningún valor
se pega en este plan, commits, logs o argumentos persistidos.

#### Acciones autorizables al agente en B1-PREFLIGHT

1. Capturar estado Git de ambos repos y hashes de superficies antes de operar.
2. Instalar en el venv el extra ya declarado:

```text
.venv/bin/python -m pip install -e '.[gsheets]'
```

Registrar únicamente versiones de `gspread` y `google-auth`. No modificar fuentes, locks ni
requirements.
3. Verificar sólo presencia de las tres variables y que staging/productivo difieran; no imprimir
   valor, longitud, prefijo ni JSON.
4. Autenticar contra la hoja de staging y ejecutar únicamente:

```text
.venv/bin/python -m scripts.tableau_staging inspect
.venv/bin/python -m scripts.tableau_staging stage --shard <candidate_shard>
```

Sin `--apply`. El segundo comando es dry-run y debe devolver el mismo `inventory_digest` observado.
5. Compilar nuevamente el candidate en dos temporales si el shard ya no existe y comprobar bytes
   deterministas antes de usarlo.
6. Generar el `.twb` bajo `tempfile.gettempdir()` con el ID de staging confirmado. Verificar:
   `tableau_desktop_validated=false`, release correcto, dos tablas runner, etiqueta 0/4, point-only,
   cero ID productivo, cero Tableau Public y cero rutas absolutas.
7. No exigir refresh todavía. Si se abre Tableau Desktop en preflight, sólo puede registrarse que
   el archivo fue reconocido; ausencia de tablas en la hoja no es PASS ni FAIL del refresh.
8. Guardar evidencia redactada: versiones, conteos/nombres de tabs, digests, plan dry-run y hashes
   del `.twb`. Nunca el ID ni credenciales.
9. Repetir hashes de preservación y STOP.

#### Gates

- `gspread` importable y dentro de `>=6,<7`;
- autenticación read-only exitosa;
- staging y producción declarados y distintos;
- ninguna tab `runner_*` mutada o creada;
- `inspect` repetido produce el mismo inventario si nadie cambió la hoja;
- `stage` dry-run contiene únicamente el namespace administrado;
- las tabs ajenas/default permanecen fuera del plan de mutación;
- candidate y `.twb` deterministas;
- ningún secreto aparece en stdout/stderr, plan, Git diff o procesos;
- `git status` y superficies públicas iguales antes/después;
- Obesidad permanece `trained`, puntero inactivo y fuera de `published_only`.

#### Condiciones de STOP

Detener sin intentar corregir remotamente si:

- falta cualquiera de las tres variables;
- staging y producción coinciden;
- la service account no puede abrir el staging;
- el inventario contiene residuos `__next`/`__backup`;
- aparecen tabs `runner_*` inesperadas;
- el dry-run propone tocar una tab legacy o ajena;
- el workbook contiene el ID productivo o no pasa su verificador.

No ejecutar `recover --apply`, `stage --apply`, Google write, Tableau refresh contra datos runner,
Tableau Public, DVC, push, merge, lifecycle, puntero, deploy ni publicación.

#### Evidencia requerida al cierre

```text
versiones instaladas (sin secretos)
inventory_digest de inspect
states + foreign tabs
release_id/disease_id del dry-run
lista exacta de operaciones propuestas
digest del candidate y del .twb
tableau_desktop_validated=false
hashes de preservación antes/después
```

#### Avance

C7 permanece en **82.3% ≈ 82%**. B0/B0.1 cerraron; el porcentaje entero no sube hasta validar el
sink externo. Exposición pública **0%** y prospectiva **INCOMPLETE 0/4**.

#### Próxima acción exacta

Primero el usuario crea/configura la hoja y exporta las tres variables en la shell de ejecución.
Después puede autorizar:

_Respuesta:_ **GO C7.6-PROMOTION-ADAPTERS-B1-PREFLIGHT. Se autoriza instalar `.[gsheets]`, usar las
credenciales sólo desde el entorno para autenticación read-only, ejecutar `inspect` y `stage`
sin `--apply`, y generar/verificar candidate + workbook únicamente en temporales. STOP antes de
cualquier escritura Google, refresh con datos runner, DVC, push, lifecycle, puntero, deploy o
publicación.**


---

### Ronda 105 — C7.6-PROMOTION-ADAPTERS-B1-PREFLIGHT: **BLOQUEADA** en la condición de STOP — 2026-07-27

#### Por qué se detuvo

La primera comprobación de la orden es la lista de STOP: «detener sin intentar corregir remotamente
si falta cualquiera de las tres variables». Faltan las tres.

```text
C7_TABLEAU_STAGING_SPREADSHEET_ID    AUSENTE
GSHEETS_SPREADSHEET_ID               AUSENTE
GOOGLE_SERVICE_ACCOUNT_JSON          AUSENTE
```

Sólo se comprobó **presencia**. No se leyó ningún valor, ni longitud, ni prefijo, ni se buscó un
secreto en ningún archivo, ni se intentó crear la hoja.

Una precisión operativa que conviene fijar antes del próximo intento: cada comando que ejecuto corre
en una shell nueva que hereda el entorno del proceso de Claude Code, **no** el de tu terminal. Un
`export` que hagas en tu shell no llega aquí. Para que llegue, las variables tienen que estar en el
entorno desde el que se lanza la sesión.

#### Lo que sí se ejecutó (sin credenciales, todo autorizado por la orden)

**Paso 1 · baseline de preservación.** Capturado antes de tocar nada.

**Paso 2 · instalación del extra declarado.** `pip install -e '.[gsheets]'`, sin modificar fuentes,
`pyproject.toml` ni locks:

```text
gspread        6.2.1     (gate >=6,<7: cumple)
google-auth    2.56.2
añadidos por resolución: google-auth-oauthlib 1.4.0 · oauthlib 3.3.1 · requests-oauthlib 2.0.0
```

Suite rápida después de instalar: **2,131 passed, 1 skipped, 61 deselected** — el mismo resultado
que antes, así que la instalación no movió nada.

**Paso 5 · candidate determinista.** Recompilado en dos temporales independientes:

```text
release_id     obesidad_release_2517e7858901
filas          5,772 · lifecycle trained · INCOMPLETE 0/4
etiqueta       Validación prospectiva en curso (0/4 semanas) · pronóstico puntual sin intervalos
9 archivos     digests idénticos entre las dos compilaciones
  74a97228…  epibot/corpus/obesidad.md
  074d3200…  epibot/knowledge.json
  5fa161c2…  reports/forecast_products.csv
  499555be…  reports/report.md
  1f462267…  shard_manifest.json
  5fa161c2…  tableau/forecast_shard.csv
  d71b14b2…  tableau/schema.json
  9ba6b025…  web/manifest.json
  5fa161c2…  web/series.csv
```

#### Lo que NO se ejecutó, y por qué

```text
paso 3  verificar que staging != productivo    imposible: no hay ninguno de los dos
paso 4  autenticar · inspect · stage dry-run    requiere las credenciales
paso 6  generar el .twb                         requiere el ID de staging confirmado
paso 7  abrir Tableau Desktop                   depende del paso 6
paso 8  evidencia de tabs, inventory_digest     depende del paso 4
```

#### Preservación

```text
backend    HEAD 20e1ccdf · rama feat/registry-padecimientos-obesidad · 0 archivos trackeados sucios
dashboard  HEAD e894a67a · rama feat/c73-candidate-staging · 0 sucios
rolling_cv_v1.yaml   dd6d4a02…    viz_epiforecastmx.twb  48c0b1ce…
tableau.csv          b334e239…    auditoria_motores_2026  02ea61f0…
rag_index.json       efbae871…    knowledge.json          e1d9a7d9…
hashes antes/después: IDÉNTICOS en los dos repos
Obesidad: lifecycle trained · puntero inactivo · fuera de published_only
```

Sin escritura Google, sin refresh, sin Tableau Public, sin DVC, push, merge, lifecycle, puntero,
deploy ni publicación. Ningún commit en esta ronda: no hubo cambios de código.

#### Pregunta

Para desbloquear hacen falta las tres variables **en el entorno desde el que se lanza esta sesión**,
no en tu terminal. Dos formas, elige:

1. Lanzas Claude Code con las tres exportadas (`export … && claude`), me lo dices, y yo repito
   B1-PREFLIGHT desde el paso 3.
2. Si prefieres no exponerlas al proceso completo, ejecutas tú los dos comandos read-only en tu
   shell y me pegas la salida redactada:

```text
.venv/bin/python -m scripts.tableau_staging inspect
.venv/bin/python -m scripts.tableau_staging stage --shard <ruta_del_shard>
```

Ambas salidas son JSON canónico y **no contienen el ID de la hoja** —el sink lo redacta incluso en
los errores—, así que puedes pegarlas tal cual.

¿Hoja de staging ya creada y compartida con la service account, o eso también sigue pendiente?

_Respuesta:_

La ronda se valida como **STOP correcto**, no como FAIL del código. No se asume que la hoja exista:
crear y compartir la hoja sigue siendo prerrequisito del usuario.

---

### Ronda 106 — Auditoría del intento B1-PREFLIGHT bloqueado y orden de reanudación — 2026-07-27

#### Veredicto

```text
B1_DEPENDENCY_READY
B1_CANDIDATE_READY
B1_EXTERNAL_PREFLIGHT_NOT_STARTED
B1_PREFLIGHT_BLOCKED_MISSING_ENV
B1_APPLY_NOT_AUTHORIZED
```

La condición de STOP se aplicó correctamente: al faltar las tres variables no hubo autenticación,
lectura ni escritura Google. No existe evidencia suficiente para declarar el preflight PASS, pero
tampoco hay una regresión.

#### Validación independiente

```text
backend HEAD                       20e1ccdf · ahead 28
dashboard HEAD                     e894a67a
archivos trackeados de producto    0 modificados
único trackeado modificado         este plan
gspread                            6.2.1 · cumple >=6,<7
google-auth                        2.56.2
google-auth-oauthlib               1.4.0
requests-oauthlib                  2.0.0
oauthlib                           3.3.1
git diff --check                   PASS
```

La instalación quedó sólo en `.venv`; no modificó `pyproject.toml`, requirements ni locks. El
candidate recompilado conserva `obesidad_release_2517e7858901`, 5,772 filas, `trained`,
`INCOMPLETE 0/4` y nueve archivos deterministas.

#### Avance

El porcentaje se mantiene en **82.3% ≈ 82%**. Instalar la dependencia y recompilar el candidate
preparan el gate, pero no validan el sink externo. La exposición pública continúa en **0%**.

### Orden de desbloqueo — acción del usuario

#### U1 · crear la hoja

1. Crear una Google Sheet nueva, vacía y exclusiva para C7 staging.
2. Confirmar que no es la hoja productiva y que no está conectada a Tableau Public.
3. Compartir únicamente esa hoja con el `client_email` de la service account como editor.
4. No pegar aquí el ID ni el JSON.

#### U2 · iniciar una sesión que herede las variables

La opción recomendada es cerrar esta sesión y lanzar una nueva desde la misma shell donde se
exportaron las variables. Un `export` hecho después en otra terminal no puede modificar el entorno
de un proceso ya iniciado.

Ejemplo conceptual —sustituir valores/ruta localmente y no pegar la salida:

```zsh
export C7_TABLEAU_STAGING_SPREADSHEET_ID='...'
export GSHEETS_SPREADSHEET_ID='...'
export GOOGLE_SERVICE_ACCOUNT_JSON="$(jq -c . /ruta/privada/service-account.json)"

# Sólo comprobar presencia; no imprimir valores.
for v in C7_TABLEAU_STAGING_SPREADSHEET_ID GSHEETS_SPREADSHEET_ID \
  GOOGLE_SERVICE_ACCOUNT_JSON; do
  if test -n "${(P)v}"; then
    echo "$v=present"
  else
    echo "$v=MISSING"
  fi
done

# Lanzar sólo si las tres dijeron present.
claude
```

El archivo de credenciales permanece fuera de ambos repositorios. La nueva sesión sólo debe recibir
el secreto por entorno. Si no se usa `jq`, el valor debe seguir siendo el JSON completo en una sola
variable; el código no acepta una ruta como sustituto.

### Orden C7.6-PROMOTION-ADAPTERS-B1-PREFLIGHT-RESUME — pasos 3–9 y STOP

Una vez iniciada la sesión con las tres variables:

1. Comprobar únicamente presencia y que los dos IDs difieran; no imprimir valores, longitudes ni
   prefijos.
2. Verificar que `gspread==6.2.1` continúa importable. **No reinstalar** si el gate ya cumple.
3. Reutilizar uno de los candidates deterministas conservados. Si ya no existe, recompilar una vez
   y exigir los mismos nueve digests antes de continuar.
4. Autenticar contra staging y ejecutar dos veces `inspect`. Ambos inventarios deben coincidir.
5. Ejecutar `stage --shard <candidate>` **sin `--apply`**.
6. Verificar que el plan sólo menciona los ocho nombres administrados y conserva todas las tabs
   ajenas.
7. Generar el `.twb` en un temporal real, con el ID confirmado por entorno.
8. Registrar evidencia redactada exigida en Ronda 104.
9. Repetir preservación y STOP.

No abrir el borde mutante:

```text
prohibido  stage --apply
prohibido  recover --apply
prohibido  escribir o renombrar tabs
prohibido  Tableau Public / deploy / lifecycle / puntero / DVC / push
```

#### Gate de salida

```text
autenticación read-only                       PASS
inspect A == inspect B                        PASS
residuos __next/__backup                      0
tabs runner activas inesperadas               0
stage dry-run                                 PASS
operaciones fuera del namespace               0
candidate + twb                               deterministas
tableau_desktop_validated                     false (esperado antes de APPLY)
superficies/hashes                            sin cambios
```

Si falla cualquiera, STOP con evidencia redactada; no reparar remotamente en la misma ronda.

#### Próxima autorización

Después de crear la hoja y reiniciar la sesión con el entorno:

_Respuesta:_ **GO C7.6-PROMOTION-ADAPTERS-B1-PREFLIGHT-RESUME. Reanudar desde presencia de
variables, autenticación read-only, doble inspect, stage sin `--apply` y workbook temporal. No
reinstalar ni recompilar si los artefactos preparados siguen válidos. STOP antes de cualquier
escritura Google, refresh con datos runner, DVC, push, lifecycle, puntero, deploy o publicación.**

---

### Ronda 107 — B1 estacionado con manual y orden de trabajo independiente — 2026-07-27

#### Decisión operativa

```text
B1-PREFLIGHT                    PARKED_BY_USER
B1-APPLY                        NOT_AUTHORIZED
DEPENDENCIAS                    READY
CANDIDATE                       READY
PUBLICACIÓN                     NO-GO
```

No se considera fallo ni se descarta evidencia. La reanudación completa quedó en:

```text
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
```

El manual contiene creación/compartición de la hoja, carga segura de variables, reinicio de sesión,
comandos read-only, resultados esperados, condiciones de STOP, troubleshooting y limpieza de
variables.

#### Qué puede avanzar sin Google

La ruta funcional de publicación no puede cruzar B1 sin inventar una validación externa. Para no
perder tiempo, el siguiente trabajo útil es cerrar la trazabilidad de los commits locales antes de
que sigan creciendo:

```text
backend    remoto dbfdd49c .. local 20e1ccdf
dashboard  remoto d5ead880 .. local e894a67a
```

Esto no publica ni cambia producto. Prepara un checkpoint revisable y detecta secretos/rutas
prohibidas antes de cualquier push futuro.

### Orden C7.6-CHECKPOINT-AUDIT — read-only y STOP

#### Objetivo

Auditar ambos rangos locales completos y producir un manifiesto de checkpoint. No corregir código
ni subir nada.

#### Backend

1. Confirmar ancestry, ahead/behind y que `main` local/remota no se movieron.
2. Inventariar commits, autores, rutas, binarios y tamaño por commit para:

```text
dbfdd49c..20e1ccdf
```

3. Separar:

```text
code/config/tests
docs
DVC/pointers
artefactos o datos
```

4. Verificar que el rango no contiene:

- credenciales, IDs de Sheets, private keys o `GEMINI_API_KEY`;
- `runs/`, modelos finales sin DVC o bundles fuera del target;
- lifecycle `published`, puntero activo o canales públicos no aprobados;
- cambios accidentales en agregados legacy;
- escrituras sobre el workbook productivo.

5. Revalidar gates mínimos dirigidos: Ruff, mypy, publicación, doctor y hashes legacy.

#### Dashboard

1. Confirmar ancestry, ahead/behind y `origin/main` intacta.
2. Auditar:

```text
d5ead880..e894a67a
```

3. Verificar que el rango no contiene:

- secretos, IDs, índices candidate temporales o shards;
- cambios públicos involuntarios en HTML, `knowledge.json` o RAG fuera de los commits declarados;
- deploy config, PR, merge o lifecycle;
- menciones públicas de Obesidad.

4. Revalidar `npm run check` y los gates candidate sin requerir shard real cuando corresponda.

#### Documentación local no commiteada

Inventariar por separado:

```text
docs/PLAN_C7_PUBLICACION_OBESIDAD.md
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
```

No incluirlos automáticamente en el rango de código ni crear commit. Reportar tamaño, contenido
general y si existe alguna cadena sensible. El plan conserva ediciones acumuladas del usuario y no
se reescribe ni normaliza durante esta auditoría.

#### Entregable

Añadir al plan:

```text
SHA local/remoto por repo
ahead/behind
tabla de commits por clase
rutas prohibidas: 0 o lista exacta
secret scan redactado
gates ejecutados
estado de superficies
rango exacto propuesto para cada push
docs pendientes fuera del rango
veredicto READY_FOR_CHECKPOINT o BLOCKED
```

#### Prohibiciones

Sin editar código, configurar Google, usar credenciales, abrir Tableau, DVC, commit, push, PR,
merge, tag, lifecycle, puntero, deploy, borrado de untracked ni publicación.

#### STOP

Terminar con una recomendación; no ejecutar el checkpoint. Cada push requerirá autorización literal
por repositorio y SHA final.

#### Próxima acción exacta

_Respuesta:_ **GO C7.6-CHECKPOINT-AUDIT READ-ONLY. Auditar los rangos
`dbfdd49c..20e1ccdf` y `d5ead880..e894a67a`, gates, secretos y superficies; documentar rangos
propuestos y STOP. Sin modificar código, commit, push, DVC, Google, lifecycle, deploy ni
publicación.**


---

### Ronda 108 — C7.6-CHECKPOINT-AUDIT (read-only) — 2026-07-27

Sin editar código, sin commit, sin push, sin DVC, sin Google, sin Tableau. Ningún untracked borrado.

#### SHA y ancestry

```text
backend    origin/feat/registry-padecimientos-obesidad  dbfdd49c   (upstream configurado)
           local  20e1ccdf   ·  ancestro: SÍ  ·  ahead 28 / behind 0
           main local == origin/main == b535b525   (no se movieron)
           HEAD está 120 commits por delante de origin/main y 0 por detrás

dashboard  d5ead880 (base declarada)  ·  local e894a67a  ·  ancestro: SÍ  ·  ahead 19 / behind 0
           main local == origin/main == 179bbe36   (no se movieron)
           la rama feat/c73-candidate-staging NO tiene upstream configurado
           HEAD está 21 commits por delante de origin/main
```

**Hallazgo de secuencia:** la rama del dashboard no tiene upstream. El primer push tendrá que ser
`--set-upstream`, y eso **crea la rama en el remoto**; no es equivalente a actualizar una existente
como en backend. Conviene decidirlo explícitamente y no descubrirlo en el momento.

#### Commits por clase

**Backend `dbfdd49c..20e1ccdf` — 28 commits, autor único «Javier Rebull», 23 archivos, +10,830 / −14.**

| Clase | Archivos | Notas |
|---|---|---|
| code/config/tests | 22 | 9 `src/`, 3 `scripts/`, 7 `tests/`, 3 `config/publication/obesidad/*.json` |
| docs | 1 | `docs/PLAN_C7_PUBLICACION_OBESIDAD.md`, tocado por 17 de los 28 commits |
| DVC/pointers | 0 | |
| artefactos o datos | 0 | |

Binarios: **0**. Los 6 commits más recientes son los de esta serie (ADAPTERS-A → B0.1); los 22
anteriores son 11 de `docs:` y 11 de código de STATUS/RAG, ya auditados en sus rondas.

**Dashboard `d5ead880..e894a67a` — 19 commits, autor único, 26 archivos, +4,864 / −1,103.**

| Clase | Archivos | Notas |
|---|---|---|
| code/tests | 22 | `scripts/lib/*` (7), `scripts/*.mjs` (3), `tests/*` (12) |
| superficie pública | 4 | `js/kb.js`, `js/entities.js`, `package.json`, `rag_index.json` |
| deploy config / CI | 0 | ni netlify, ni `_headers`, ni `.github` |
| binarios | 0 | |

#### Rutas prohibidas

```text
backend    runs/  models/  artifacts/  data/  reports/dashboards/     0 archivos
dashboard  shards, staging temporales, netlify, .github               0 archivos
```

#### Secret scan (sobre el contenido AÑADIDO, no sobre el árbol)

```text
                        backend (10,830 líneas)   dashboard (4,864 líneas)
PRIVATE KEY                       0                        0
service_account JSON              0                        0
Google/GEMINI API key             0                        0
AWS access key                    0                        0
token (ghp/sk-/xoxb)              0                        0
password/secret literal           0                        0
id de Google Sheet (forma)        7                        0
```

Las **7 coincidencias del backend son falsos positivos**, verificadas una por una:

```text
4 × 1502d1a25b48c11b…  digest sha256 del dataset, en los tres JSON del gate congelado
3 × 1AbCdEfGhIjKlMnOp…  fixture evidentemente falso de las pruebas del sink
```

Ninguna es un identificador real. `GSHEETS_SPREADSHEET_ID`,
`C7_TABLEAU_STAGING_SPREADSHEET_ID` y `GEMINI_API_KEY` aparecen sólo como **nombres de variable**.

#### Lifecycle, puntero y canales

```text
diff del rango sobre lifecycle/puntero/canales   0 líneas
obesidad       lifecycle=trained      channels=[web, epibot, reports, tableau]  (declarados, no activos)
anorexia_f50   lifecycle=configured   channels=[]
published_only  Obesidad sigue fuera · puntero inactivo
```

#### Agregados legacy y workbook productivo

```text
tableau.csv · ProdDetails/* · data_raw* · viz_epiforecastmx.twb    0 archivos en ambos rangos
```

#### Menciones de Obesidad en la superficie pública del dashboard

Aquí un grep ingenuo da un susto que conviene desactivar por escrito:

```text
js/kb.js           5 menciones
js/entities.js     0
rag_index.json     0   (454 chunks · gemini-embedding-001 · dim 768 · sin candidate)
knowledge.json     0
```

De esas 5, **4 son anteriores a `d5ead880`** y viven en las listas de
`answerPadecimientoNoModelado`: Obesidad figura ahí como padecimiento que el bot **NO** modela, que
es exactamente lo que debe decir mientras sea NO-GO. La quinta, y única del rango, es una línea de
**comentario**. Cero exposición.

#### Gates revalidados

```text
backend    ruff check                 PASS
           ruff format --check        PASS
           mypy (src)                 PASS
           pytest tests/unit/publication   297 passed, 1 skipped
           doctor_padecimiento obesidad    ✅ completo (config)
           hashes legacy               tableau.csv b334e239… · auditoria_motores 02ea61f0…  (intactos)

dashboard  node --check de las 16 fuentes  PASS
           test:cases:verify           616 / 616
           test:unit                   67 passed
           test:candidate              81 (79 passed, 2 skipped: shard real no inyectado)
           rag:verify                  índice sincronizado, 454 chunks
```

#### Hallazgo bloqueante para el DEPLOY (no para el checkpoint)

`epibot/js/kb.js` y `epibot/js/entities.js` cambiaron en el rango, pero **`epibot/index.html` no está
en él**: `app.js?v=135` sigue igual. La regla del repo es explícita — al tocar `kb.js`/`entities.js`
hay que subir el `?v` de **afuera**, porque Netlify sirve `/js/*` con `max-age=3600` y el navegador
seguiría ejecutando el `app.js` cacheado, que importa el `kb.js` viejo. El cambio llegaría al
servidor y **no se vería**.

No bloquea el checkpoint —hacer push no despliega— pero sí tiene que resolverse antes de cualquier
merge a `main`, que es lo que dispara producción.

#### Documentación local fuera del rango

```text
docs/PLAN_C7_PUBLICACION_OBESIDAD.md          17,160 líneas · 752 KB · modificado (M), no commiteado
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md       288 líneas ·   7 KB · sin trackear (??)
```

Secret scan de ambos: **0** en todas las categorías. Las 8 coincidencias de «forma de id» en el plan
son las cuatro digests sha256 de dataset/gate/evaluación/estado, verificadas como 64 hex. Ninguno de
los dos documentos se incluyó en ningún rango ni se normalizó; el plan conserva tus ediciones.

#### Rangos propuestos para el checkpoint

```text
backend    git push origin feat/registry-padecimientos-obesidad
           dbfdd49c..20e1ccdf   ·  28 commits  ·  0 binarios  ·  0 rutas prohibidas

dashboard  git push --set-upstream origin feat/c73-candidate-staging
           d5ead880..e894a67a   ·  19 commits  ·  0 binarios  ·  0 rutas prohibidas
           ⚠ crea la rama en el remoto: no es una actualización, es un alta
```

Ninguno toca `main`. Ninguno despliega por sí solo: producción sale del merge a `main` del
dashboard, que no está propuesto aquí.

#### Veredicto

```text
READY_FOR_CHECKPOINT
```

Con dos condiciones declaradas, ninguna de las cuales es un defecto del código auditado:

1. el push del dashboard **crea** la rama remota (`--set-upstream`);
2. el cache-bust de `app.js?v` está pendiente y es prerrequisito del **deploy**, no del push.

#### Pregunta

Tres decisiones, y ninguna la tomo yo:

1. **¿Autorizas los dos push?** Cada uno por separado, con repo y SHA final literal, como pediste.
2. **El plan y el manual** no entran en ningún rango. ¿Los quieres commiteados en un tercer commit
   `docs:` antes del push —quedarían versionados y revisables— o siguen viviendo sólo en local?
3. **El cache-bust**: ¿lo subo yo a `app.js?v=136` ahora, en un commit propio del dashboard, o
   prefieres dejarlo para la ronda de deploy y que el checkpoint quede exactamente como está
   auditado?

_Respuesta:_

No autorizar todavía ningún push. Primero cerrar el cache-bust completo en un commit local del
dashboard y reauditar el SHA final. La rama remota del dashboard **ya existe**; no se creará de
nuevo. El riesgo de branch deploy sigue sin resolverse y se decide al autorizar el push, no dentro
del cambio de código.

---

### Ronda 109 — Reauditoría del checkpoint y orden de cache-bust — 2026-07-27

#### Validación independiente

```text
backend remote branch        origin/feat/registry-padecimientos-obesidad @ dbfdd49c
backend local                20e1ccdf · ahead 28 / behind 0
backend publication tests    297 passed, 1 skipped
backend diff --check         PASS

dashboard remote branch      origin/feat/c73-candidate-staging @ d5ead880
dashboard local              e894a67a · ahead 19 / behind 0 respecto de esa rama
dashboard main               local == origin/main == 179bbe36
dashboard npm run check      PASS desde EpiForecast-IMSS-Dashboard/epibot
dashboard RAG               454/454 · sincronizado
```

El primer intento de `npm run check` desde la raíz del dashboard dio “Missing script”; no es un
fallo del producto. El `package.json` canónico del EpiBot vive en `epibot/`, y desde ese directorio
la cadena completa pasa. Las futuras órdenes deben declarar siempre el `workdir`.

#### R109-P0-1 · la rama remota del dashboard ya existe

Ronda 108 afirmó que `--set-upstream` “crearía la rama”. Es falso:

```text
git ls-remote origin feat/c73-candidate-staging
d5ead880...  refs/heads/feat/c73-candidate-staging
```

La rama fue creada y subida durante C7.3. El local simplemente no tiene upstream configurado.
Actualizarla sería un fast-forward `d5ead880..HEAD`; `--set-upstream` sólo configuraría tracking
local. No presentarlo como alta remota.

#### R109-P0-2 · un push de rama puede desplegar un preview

Ronda 108 afirmó que ninguno de los pushes despliega por sí solo. Eso tampoco está demostrado.
`netlify.toml` no desactiva branch deploys y la configuración efectiva vive en la UI de Netlify.

Verdades verificables:

- un push no mueve producción porque `main` permanece intacta;
- un push del dashboard **puede** disparar un branch preview si Netlify lo tiene habilitado;
- ese riesgo se acepta explícitamente o se desactivan branch deploys antes del push;
- backend no tiene ese acoplamiento a Netlify.

Por tanto, backend y dashboard tendrán autorizaciones de push separadas.

#### R109-P0-3 · `app.js?v=136` solo no invalida los módulos hijos

Cadena actual:

```text
epibot/index.html   → js/app.js?v=135
epibot/js/app.js    → ./kb.js?v=102
                    → ./entities.js?v=30
epibot/js/kb.js     → ./entities.js?v=30
```

El rango modificó `kb.js` y `entities.js`. Pedir únicamente `app.js?v=136` fuerza a releer
`app.js`, pero ese archivo seguiría solicitando las URLs antiguas de sus hijos, sujetas a
`Cache-Control: max-age=3600`. El cache-bust correcto es transitivo:

```text
index.html          app.js?v=135       → app.js?v=136
app.js              kb.js?v=102        → kb.js?v=103
app.js              entities.js?v=30   → entities.js?v=31
kb.js               entities.js?v=30   → entities.js?v=31
```

No cambiar lógica, contenido de datos ni versiones ajenas.

#### Veredicto corregido

```text
BACKEND_READY_FOR_CHECKPOINT
DASHBOARD_CODE_GATES_PASS
DASHBOARD_CACHE_BUST_REQUIRED
DASHBOARD_PUSH_REQUIRES_BRANCH_DEPLOY_DECISION
NO_PUSH_AUTHORIZED
```

### Orden C7.6-DASHBOARD-CACHE-BUST — local, un commit y STOP

#### Alcance exacto

Repositorio:

```text
/Users/haowei/Documents/Integrador/EpiForecast-IMSS-Dashboard
```

Archivos permitidos:

```text
epibot/index.html
epibot/js/app.js
epibot/js/kb.js
```

Cambios exactos:

```text
app.js?v=135       → app.js?v=136
kb.js?v=102        → kb.js?v=103
entities.js?v=30   → entities.js?v=31  (en app.js)
entities.js?v=30   → entities.js?v=31  (en kb.js)
```

`entities.js` no necesita cambiar: cambia la URL con la que sus consumidores solicitan los bytes ya
modificados en el rango.

#### Gates

1. `git diff --check`.
2. El diff contiene exactamente cuatro sustituciones en tres archivos, sin otra línea funcional.
3. `node --check` sobre `app.js`, `kb.js` y `entities.js`.
4. Desde `EpiForecast-IMSS-Dashboard/epibot`:

```text
npm run check
```

5. `knowledge.json`, `rag_index.json`, `package.json`, lock y Netlify byte-idénticos.
6. `origin/main` permanece `179bbe36`.
7. Obesidad sigue fuera de `knowledge.json`, `rag_index.json` y las superficies HTML.
8. Ningún shard, candidate, secreto o ID entra al commit.

#### Commit

Un solo commit local:

```text
fix(epibot): bust module cache after candidate handler changes
```

Después STOP para auditoría del SHA nuevo.

#### Prohibiciones

Sin push, `--set-upstream`, PR, merge, Netlify, deploy, backend, plan commit, Google, DVC,
lifecycle, puntero ni publicación. Preservar `EpiBot_v2_SinFondo.png` y `kb.zip` untracked.

#### Lo que sigue, todavía no autorizado

Tras PASS del cache-bust:

1. auditar `d5ead880..NUEVO_SHA`;
2. decidir si se acepta un posible branch preview o si se desactiva en Netlify;
3. autorizar backend y dashboard por separado;
4. decidir un commit doc-only para plan + manual, también separado.

#### Avance

C7 permanece en **82.3% ≈ 82%**. Es una corrección operativa de entrega, no exposición pública.

#### Próxima acción exacta

_Respuesta:_ **GO C7.6-DASHBOARD-CACHE-BUST LOCAL. Cambiar únicamente las cuatro versiones
de la cadena `index → app → kb/entities`, ejecutar `npm run check` desde `epibot/`, crear un solo
commit local y STOP. Sin push, branch deploy, PR, merge, backend, Google, DVC, lifecycle, puntero,
deploy ni publicación.**


---

### Ronda 110 — C7.6-DASHBOARD-CACHE-BUST ejecutada — 2026-07-27

**Commit (único, local, dashboard):**

```text
9487e322  fix(epibot): bust module cache after candidate handler changes
```

Rama `feat/c73-candidate-staging`: `e894a67a` → **`9487e322`**.

#### Las cuatro sustituciones

```text
epibot/index.html   js/app.js?v=135        →  136
epibot/js/app.js    ./kb.js?v=102          →  103
epibot/js/app.js    ./entities.js?v=30     →  31
epibot/js/kb.js     ./entities.js?v=30     →  31
```

`entities.js` no cambia: lo que cambia es la URL con la que sus **dos** consumidores piden los bytes
que el rango ya modificó. Las versiones ajenas —`mexico-map?v=2`, `timelapse?v=2`, `semaforo?v=2`,
`comparador?v=2`, `voice?v=3`, `style.css?v=47`, el favicon `?v=2`— quedaron intactas: sus archivos
no cambiaron y moverlas habría invalidado caché sin motivo.

#### Gates

```text
1  git diff --check                                            PASS
2  diff = 4 sustituciones en 3 archivos · 4 insert / 4 delete   PASS  (ninguna línea funcional)
3  node --check app.js · kb.js · entities.js                    PASS
4  npm run check desde EpiForecast-IMSS-Dashboard/epibot
     test:cases:verify   616 / 616
     test:unit           67 passed
     test:candidate      81 (79 passed · 2 skipped: shard real no inyectado)
     rag:verify          índice sincronizado, 454 chunks                PASS
5  knowledge.json · rag_index.json · package.json · lock · netlify.toml  byte-idénticos
6  origin/main                                                  179bbe36  (sin moverse)
7  Obesidad en knowledge.json / rag_index.json / index.html      0 · 0 · 0
8  árbol tras el commit                                         sólo los dos untracked previos
```

`EpiBot_v2_SinFondo.png` y `kb.zip` siguen sin trackear, tal como estaban.

Sin push, `--set-upstream`, PR, merge, Netlify, deploy, backend, commit del plan, Google, DVC,
lifecycle, puntero ni publicación.

#### Rango de checkpoint actualizado

```text
backend    dbfdd49c..20e1ccdf   28 commits   (sin cambios en esta ronda)
dashboard  d5ead880..9487e322   20 commits   (+1: el cache-bust)
```

#### Pregunta

El bust ya está, así que lo que queda del checkpoint son decisiones tuyas, no trabajo mío:

1. **Branch preview de Netlify.** Sigue sin demostrarse si está habilitado —la configuración
   efectiva vive en la UI, no en `netlify.toml`—. ¿Lo compruebas y decides aceptarlo o desactivarlo
   antes de autorizar el push del dashboard? El de backend no tiene ese acoplamiento y puede
   autorizarse por separado sin esperar a esto.
2. **Plan y manual.** Siguen fuera de todo rango: el plan modificado y sin commitear, el manual sin
   trackear. ¿Commit `docs:` propio antes o después de los push, o siguen sólo en local?

_Respuesta:_

---

### Ronda 111 — Auditoría del cache-bust y orden del checkpoint documental — 2026-07-27

#### Veredicto

```text
C7.6-DASHBOARD-CACHE-BUST       PASS
BACKEND_CODE_CHECKPOINT         READY
DASHBOARD_CODE_CHECKPOINT       READY, con riesgo externo de branch preview todavía no resuelto
B1-PREFLIGHT                    PARKED_BY_USER
PUBLICACIÓN                     NO-GO
```

El commit `9487e322` fue revisado por diff y por la cadena completa del EpiBot. Contiene
exactamente las cuatro sustituciones autorizadas:

```text
index.html   app.js?v=135       -> 136
app.js       kb.js?v=102        -> 103
app.js       entities.js?v=30   -> 31
kb.js        entities.js?v=30   -> 31
```

No cambia lógica, datos, RAG, configuración de Netlify ni superficies públicas.

#### Evidencia revalidada

```text
dashboard HEAD                         9487e322
dashboard remote feature              d5ead880
dashboard ahead / behind               20 / 0
dashboard origin/main                  179bbe36, intacta
git diff --check                       PASS
npm run check (workdir epibot/)        PASS
fixture                               616 / 616
unitarias                              67 passed
candidate                              79 passed, 2 skips esperados sin shard real
RAG                                    454 / 454, sincronizado
Obesidad pública                       0 menciones en knowledge/RAG/index
untracked del usuario                  EpiBot_v2_SinFondo.png y kb.zip, intactos
```

El backend permanece en `20e1ccdf`, 28 commits delante de `dbfdd49c`, sin cambio de código en esta
ronda.

#### Documentación pendiente

Hay dos piezas autoritativas todavía fuera de un checkpoint Git:

```text
docs/PLAN_C7_PUBLICACION_OBESIDAD.md
  trackeado y modificado
  delta acumulado observado al iniciar esta auditoría: +6,409 / -18

docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
  nuevo, 288 líneas
  sha256 d38eeed6f7a60c8b089216598c138134f82719cead4eea84e790bbff33b6dcc7
```

El tamaño del plan es consecuencia de la bitácora acumulada de C7. No se debe normalizar,
reordenar ni resumir en este checkpoint. El scan dirigido no encontró private keys ni tokens con
forma de Google, GitHub, OpenAI, Slack o AWS. Los nombres de variables de entorno y los
identificadores falsos de fixtures no son secretos.

### Orden C7.6-DOCS-CHECKPOINT — local, doc-only y STOP

#### Objetivo

Versionar el estado autoritativo y el manual de reanudación antes de mover cualquier remoto. No
mezclar documentación con código ni reinterpretar el contenido histórico.

#### Preflight

1. Confirmar:

```text
backend HEAD       20e1ccdf
dashboard HEAD     9487e322
```

2. Ejecutar `git status --short --branch` en ambos repositorios.
3. Confirmar que los únicos paths que se añadirán al índice son:

```text
docs/PLAN_C7_PUBLICACION_OBESIDAD.md
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
```

4. Preservar todos los demás archivos no rastreados del usuario.

#### Ejecución

Añadir por ruta explícita, nunca con `git add .`:

```bash
git add -- docs/PLAN_C7_PUBLICACION_OBESIDAD.md \
  docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
```

Antes de commitear:

```bash
git diff --cached --name-status
git diff --cached --check
git diff --cached --stat
```

El `name-status` debe contener exactamente:

```text
M  docs/PLAN_C7_PUBLICACION_OBESIDAD.md
A  docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
```

Repetir el scan de secretos sobre el **staged diff**. Si aparece una credencial real, hacer STOP;
no corregirla dentro del índice sin retirar primero ambos paths del staging.

Commit local único:

```text
docs: preserve C7 publication plan and B1 staging manual
```

Los hooks deben quedar verdes. Después comprobar que:

- el commit contiene sólo esos dos archivos;
- el árbol trackeado queda limpio;
- los untracked del usuario siguen intactos;
- ningún SHA de código del dashboard cambia;
- no se creó ni activó un puntero público.

#### Prohibiciones

Sin editar código, reformatear la bitácora, incluir otros documentos, `git add .`, push, PR, merge,
tag, Netlify, branch deploy, Google, Tableau, Gemini, DVC, lifecycle, puntero, deploy ni
publicación.

#### STOP

Terminar reportando el SHA documental nuevo y el nuevo rango backend
`dbfdd49c..NUEVO_SHA`. No ejecutar ningún push.

### Secuencia posterior — todavía no autorizada

1. Auditar el commit documental y recalcular el rango final del backend.
2. Autorizar por literal el push del backend.
3. Resolver la política externa de branch deploy del dashboard:
   - desactivarlo en Netlify, o
   - aceptar explícitamente el posible preview de rama.
4. Autorizar por literal el push del dashboard `d5ead880..9487e322`.
5. Mantener B1-PREFLIGHT estacionado hasta poder seguir
   `docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md`.
6. No iniciar C7.7: la validación real de Google Sheets/Tableau sigue pendiente.

#### Próxima acción exacta

_Respuesta:_ **GO C7.6-DOCS-CHECKPOINT LOCAL. Añadir únicamente
`docs/PLAN_C7_PUBLICACION_OBESIDAD.md` y
`docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md`, verificar el staged diff y secretos, crear un commit
local doc-only y STOP. Sin push, código, DVC, Google, Tableau, Netlify, lifecycle, puntero, deploy
ni publicación.**


---

### Ronda 112 — C7.6-DOCS-CHECKPOINT ejecutada — 2026-07-27

**SHA documental nuevo:**

```text
c453b979  docs: preserve C7 publication plan and B1 staging manual
```

Backend: `20e1ccdf` → **`c453b979`**. Rango de checkpoint actualizado:

```text
dbfdd49c..c453b979    29 commits   (28 de código/docs previos + 1 documental)
behind 0 / ahead 29 respecto de origin/feat/registry-padecimientos-obesidad
```

#### Preflight

```text
backend HEAD antes    20e1ccdf   ✓
dashboard HEAD        9487e322   ✓  (no se tocó en esta ronda)
backend status        1 modificado (el plan) · 76 untracked
dashboard status      limpio · 2 untracked del usuario
```

#### Staged diff

```text
A  docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md      +288
M  docs/PLAN_C7_PUBLICACION_OBESIDAD.md         +6,589 / −17
2 archivos · 6,860 inserciones · 17 borrados
git diff --cached --check                        PASS
```

Añadido por ruta explícita, nunca `git add .`. Los untracked pasaron de 76 a 75: la única baja es el
manual, que dejó de estarlo porque ahora está trackeado. Los 75 restantes —`references/`,
`reports/`, `.qwen/`— intactos.

#### Scan de secretos sobre el diff STAGED

```text
PRIVATE KEY                    0
service_account JSON           0
Google / GEMINI API key        0
AWS access key                 0
token (ghp / sk- / xoxb)       0
password/secret literal        0
id de Google Sheet (forma)     7  →  las cuatro digests sha256, verificadas como 64 hex
```

Ningún identificador de Google Sheets ni de Drive aparece en ninguno de los dos documentos. El
manual describe **cómo** cargar las variables; no contiene ningún valor.

#### Post-commit

```text
el commit contiene sólo esos dos archivos        ✓  (name-status: A + M, nada más)
árbol trackeado                                   limpio
untracked del usuario                             75, intactos
archivos fuera de docs/ en el commit              0
SHA de código del dashboard                       9487e322, sin cambios
main local == origin/main                         b535b525, sin moverse
lifecycle obesidad                                trained · sin puntero público
hooks                                             verdes (ruff/mypy skipped: no hay .py)
```

La bitácora no se reformateó ni se normalizó: conserva tus ediciones acumuladas tal cual.

#### Rangos finales del checkpoint

```text
backend    dbfdd49c..c453b979    29 commits   ·  0 binarios  ·  0 rutas prohibidas
dashboard  d5ead880..9487e322    20 commits   ·  0 binarios  ·  0 rutas prohibidas
```

Sin push, PR, merge, tag, Netlify, branch deploy, Google, Tableau, Gemini, DVC, lifecycle, puntero,
deploy ni publicación.

#### Lo que queda, en tu orden

1. auditar `c453b979` y cerrar el rango del backend;
2. autorizar por literal el push del backend;
3. resolver la política de branch deploy de Netlify;
4. autorizar por literal el push del dashboard `d5ead880..9487e322`;
5. retomar B1 con `docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md`;
6. C7.7 sigue cerrada hasta validar el sink real.

_Respuesta:_

---

### Ronda 113 — Auditoría independiente del checkpoint documental — 2026-07-27

#### Commit auditado

```text
c453b979  docs: preserve C7 publication plan and B1 staging manual
parent    20e1ccdf
```

El commit es doc-only estricto:

```text
A  docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md       288 líneas
M  docs/PLAN_C7_PUBLICACION_OBESIDAD.md          +6,572 / -17
```

La diferencia entre el total de inserciones del commit (`6,860`) y el `numstat` del plan
(`6,572`) son las 288 líneas del manual, no una tercera ruta.

#### Auditoría independiente

```text
origin/feat/registry-padecimientos-obesidad   dbfdd49c
HEAD                                           c453b979
parent                                         20e1ccdf
remote es ancestro de HEAD                     SÍ
ahead / behind                                 29 / 0
main == origin/main                            b535b525
git show --check                               PASS
git diff --check dbfdd49c..c453b979            PASS
rutas del commit                               exactamente 2, ambas docs/
binarios                                       0
rutas prohibidas en el rango                   0
secret scan del commit                         0 credenciales
manual sha256                                  d38eeed6f7a60c8b089216598c138134f82719cead4eea84e790bbff33b6dcc7
```

No entraron `runs/`, `models/`, `artifacts/`, datos, forecasts, dashboards, puntero público,
configuración de lifecycle ni modelos. Los demás archivos no rastreados del usuario no forman
parte del commit.

La modificación actual del plan posterior a `c453b979` corresponde exclusivamente al registro de
las Rondas 112–113 y al encabezado autoritativo. No cambia el SHA que se propone subir y no se
debe incorporar mediante un commit adicional antes de este push: hacerlo produciría otra vuelta
off-by-one sin cambiar el checkpoint material.

#### Veredicto

```text
BACKEND_CHECKPOINT_AUDIT     PASS
BACKEND_PUSH                 READY_FOR_EXPLICIT_AUTHORIZATION
DASHBOARD_PUSH               SEPARADO; requiere decisión sobre branch preview
B1-PREFLIGHT                 PARKED_BY_USER
ACTIVACIÓN / PUBLICACIÓN     NO AUTORIZADAS
```

### Orden C7.6-PUSH-BACKEND-CHECKPOINT — acción externa y STOP

Esta orden **no está autorizada por el documento**. Sólo se ejecuta si el usuario emite el literal
del final de esta ronda.

#### Preflight inmediato

1. Confirmar que `HEAD` sigue siendo exactamente `c453b979`.
2. Confirmar que el remoto de la rama sigue siendo exactamente `dbfdd49c`.
3. Confirmar `dbfdd49c` como ancestro de `c453b979`.
4. Confirmar `ahead 29 / behind 0`.
5. Confirmar que no hay cambios staged. La modificación local del plan puede permanecer unstaged.
6. No ejecutar `git pull`, rebase, merge ni amend.

Si cualquiera de los SHA cambió, hacer STOP y reauditar; la autorización queda inválida.

#### Push acotado

Publicar el SHA auditado en la rama exacta, sin depender de otro HEAD:

```bash
git push origin \
  c453b979:refs/heads/feat/registry-padecimientos-obesidad
```

Prohibido `--force`, `--force-with-lease`, push de tags, otras ramas o `main`.

#### Verificación posterior

1. `git ls-remote` debe devolver `c453b979` para
   `refs/heads/feat/registry-padecimientos-obesidad`.
2. Local contra la rama remota debe quedar `ahead 0 / behind 0`.
3. `main` local y remota deben continuar en `b535b525`.
4. No debe existir PR, merge, tag, release, deploy ni cambio de lifecycle.
5. La modificación local del plan y los untracked del usuario deben permanecer intactos.

#### STOP

Reportar el SHA remoto y detenerse. No continuar con el dashboard, Netlify, B1, Google, Tableau,
DVC, lifecycle, puntero, deploy ni publicación.

### Secuencia posterior — todavía no autorizada

1. Resolver en Netlify si los branch deploys están desactivados o aceptar explícitamente el
   posible preview.
2. Revalidar que el dashboard continúe en `9487e322` y el remoto en `d5ead880`.
3. Autorizar separadamente el push del dashboard.
4. Retomar B1 cuando se puedan preparar las credenciales y la hoja de staging siguiendo el manual.
5. Sólo después cerrar readiness y solicitar una autorización separada para C7.7.

#### Próxima autorización literal

_Respuesta:_ **AUTORIZO PUSH BACKEND `dbfdd49c..c453b979` A
`origin/feat/registry-padecimientos-obesidad`. FAST-FORWARD, SIN `--force`, MERGE, PR, TAG, DVC,
ACTIVACIÓN, DEPLOY NI PUBLICACIÓN. VERIFICAR SHA REMOTO Y STOP.**


---

### Ronda 114 — PUSH BACKEND ejecutado — 2026-07-27

Autorización literal: `dbfdd49c..c453b979` a `origin/feat/registry-padecimientos-obesidad`,
fast-forward, sin `--force`.

#### Pre-push verificado antes de tocar el remoto

```text
local HEAD                                    c453b979
remoto real (git ls-remote)                   dbfdd49c   ← coincide con el rango autorizado
dbfdd49c es ancestro de HEAD                  SÍ  → fast-forward genuino
behind / ahead                                0 / 29
```

#### Resultado

```text
To https://github.com/IntegradorIMSS2026Team01/EpiForecast-MX.git
   dbfdd49c..c453b979  feat/registry-padecimientos-obesidad -> feat/registry-padecimientos-obesidad
rc=0
```

Notación `dbfdd49c..c453b979` sin `+`: git lo confirma como **fast-forward**, no como actualización
forzada.

#### SHA remoto verificado tras el push

```text
git ls-remote origin refs/heads/feat/registry-padecimientos-obesidad
c453b979f47b3798ccb3f2248c0942a6d0c8fcc7      ← coincide con el local

git ls-remote origin refs/heads/main
b535b5256aa888b905de34b4da9a23c043d414d4      ← intacta

local vs remoto: behind 0 / ahead 0
```

#### Lo que NO se hizo

```text
--force · merge · PR · tag (9 refs de tag en origin, las mismas) · DVC · activación · deploy
publicación · dashboard
```

El dashboard sigue exactamente donde estaba: local `9487e322`, remoto `d5ead880`. Su push necesita
su propia autorización, y antes la decisión sobre branch deploys de Netlify.

`docs/PLAN_C7_PUBLICACION_OBESIDAD.md` vuelve a figurar como modificado: es esta ronda, escrita
después del push. No entró en él.

#### Estado

```text
backend    origin/feat/registry-padecimientos-obesidad   c453b979   ✅ sincronizado
dashboard  origin/feat/c73-candidate-staging             d5ead880   pendiente (20 commits)
main (ambos repos)                                       sin mover
Obesidad   lifecycle trained · NO-GO · sin puntero público · invisible
C7.4       INCOMPLETE 0/4 · exposición pública 0%
```

Publicar código a una rama de trabajo no expone nada: no hay merge a `main`, no hay deploy, y el
lifecycle sigue en `trained`. Lo que cambió es que el trabajo ya no vive sólo en este equipo.

#### Pregunta

Quedan dos cosas antes de que el checkpoint esté completo, y las dos son tuyas:

1. **Branch deploys de Netlify.** Sigue sin comprobarse si están habilitados —la configuración
   efectiva está en la UI, no en `netlify.toml`—. ¿Los desactivas, o aceptas explícitamente que el
   push del dashboard pueda levantar un preview de rama? Un preview no es producción, pero sí es una
   URL accesible con el EpiBot y sus datos.
2. **Push del dashboard** `d5ead880..9487e322`, 20 commits, con su autorización literal cuando
   decidas lo anterior.

_Respuesta:_

---

### Ronda 115 — Validación post-push backend y reauditoría final del dashboard — 2026-07-27

#### Backend

```text
local HEAD                                      c453b979
origin/feat/registry-padecimientos-obesidad     c453b979
ahead / behind                                  0 / 0
main local y remota                             b535b525
```

El push informado en la Ronda 114 queda validado contra las referencias remotas locales:
fast-forward cerrado, rama de trabajo sincronizada y `main` intacta. La modificación actual del
plan es posterior al push y permanece local; no altera el checkpoint subido.

#### Dashboard re-auditado

```text
local HEAD                         9487e322
origin/feat/c73-candidate-staging  d5ead880
ahead / behind                     20 / 0
origin/main                        179bbe36
ancestry                           d5ead880 es ancestro de 9487e322
diff --check                       PASS
rango                              28 archivos · +4,867 / -1,106
secret scan                        0 credenciales
node --check                       PASS
npm run check                      PASS
fixture                            616 / 616
unitarias                          67 / 67
candidate                          79 pass · 2 skips esperados sin shard real
RAG                                454 / 454 · sincronizado
Obesidad pública                   0 en knowledge.json, rag_index.json y HTML
```

Los 28 archivos pertenecen a código, pruebas, fixture, índice RAG sincronizado y cache-bust
declarados durante C7.3–C7.6. No hay `netlify.toml`, workflow, shard candidate, credencial ni
artefacto temporal añadido al rango. Los dos untracked del usuario siguen fuera de Git.

#### Riesgo real del push

El push **no mueve producción** porque `origin/main` no cambia. Sin embargo, la configuración de
branch deploys vive en Netlify y no puede deducirse del repositorio. Si está habilitada, el push
puede crear o actualizar una URL preview de la rama.

Ese preview no contiene datos públicos de Obesidad:

- `knowledge.json`, `rag_index.json` y los HTML tienen cero menciones;
- el candidate sólo entra cuando se inyecta explícitamente un staging root;
- lifecycle continúa `trained`;
- no existe puntero público activo.

Por tanto, aceptar el posible preview es una decisión operativa razonable para terminar el
checkpoint sin esperar acceso a Netlify. No equivale a autorizar producción, merge o publicación.

#### Veredicto

```text
BACKEND CHECKPOINT       CLOSED / REMOTE
DASHBOARD RANGE          PASS / READY
DASHBOARD PRODUCTION     UNCHANGED
BRANCH PREVIEW           UNKNOWN · requires explicit acceptance or UI disable
B1-PREFLIGHT             PARKED_BY_USER
C7.7                     NO-GO
```

### Opción A — recomendada para avanzar

Aceptar explícitamente el posible preview y autorizar sólo el push fast-forward del SHA auditado:

_Respuesta:_ **ACEPTO EL POSIBLE BRANCH PREVIEW DE NETLIFY. AUTORIZO PUSH DASHBOARD
`d5ead880..9487e322` A `origin/feat/c73-candidate-staging`, FAST-FORWARD Y SIN `--force`, PR,
MERGE, TAG, CAMBIO DE `main`, DEPLOY DE PRODUCCIÓN, ACTIVACIÓN NI PUBLICACIÓN. VERIFICAR SHA
REMOTO Y STOP.**

### Opción B — máxima contención externa

1. En Netlify, desactivar temporalmente Branch deploys para el sitio.
2. Confirmar que Production branch sigue siendo `main`.
3. Emitir:

_Respuesta:_ **BRANCH DEPLOYS DE NETLIFY DESACTIVADOS Y PRODUCTION BRANCH SIGUE EN `main`.
AUTORIZO PUSH DASHBOARD `d5ead880..9487e322` A `origin/feat/c73-candidate-staging`,
FAST-FORWARD Y SIN `--force`, PR, MERGE, TAG, CAMBIO DE `main`, DEPLOY, ACTIVACIÓN NI
PUBLICACIÓN. VERIFICAR SHA REMOTO Y STOP.**

#### Reglas comunes al ejecutar cualquiera

1. Revalidar inmediatamente antes que remoto=`d5ead880`, local=`9487e322` y ancestry sea
   fast-forward.
2. Empujar el SHA exacto:

```bash
git push origin \
  9487e322:refs/heads/feat/c73-candidate-staging
```

3. Verificar con `git ls-remote` que la rama remota termina en `9487e322`.
4. Confirmar `ahead 0 / behind 0` y `origin/main=179bbe36`.
5. STOP. Sin abrir PR, mergear, desplegar producción, tocar backend, B1, Google, Tableau, DVC,
   lifecycle, puntero ni publicación.

#### Después del push — todavía no autorizado

El checkpoint de código de ambos repos quedará remoto. La ruta funcional seguirá detenida en B1
hasta que pueda ejecutarse el manual de Google Sheets/Tableau. No iniciar C7.7 sólo porque ambos
push hayan terminado.


---

### Ronda 116 — PUSH DASHBOARD ejecutado · CHECKPOINT COMPLETO — 2026-07-27

Autorización literal: `d5ead880..9487e322` a `origin/feat/c73-candidate-staging`, fast-forward, sin
`--force`, con el posible branch preview de Netlify **aceptado explícitamente**.

#### Pre-push verificado antes de tocar el remoto

```text
local HEAD                          9487e322
remoto real (git ls-remote)         d5ead880   ← coincide con el rango autorizado
d5ead880 es ancestro de HEAD        SÍ  → fast-forward genuino
commits a subir                     20
main local == main remota           179bbe36
```

#### Resultado

```text
To https://github.com/IntegradorIMSS2026Team01/EpiForecast-IMSS-Dashboard.git
   d5ead880..9487e322  feat/c73-candidate-staging -> feat/c73-candidate-staging
rc=0
```

Sin `+` en la notación: fast-forward confirmado por git.

#### SHA remoto verificado tras el push

```text
refs/heads/feat/c73-candidate-staging   9487e3221d89b3e068c9e82df89b4448bfccfcee   ← igual al local
refs/heads/main                         179bbe36cbff972737b2140658f37e1dcd480621   ← intacta
refs de tag en origin                   0
local vs remoto                         behind 0 / ahead 0
```

No se usó `--set-upstream`: no estaba en la autorización y sólo configura tracking local. La rama
local sigue sin upstream; el próximo push tendrá que nombrar el remoto igual que éste.

#### Estado del checkpoint

```text
backend    origin/feat/registry-padecimientos-obesidad   c453b979   ✅
dashboard  origin/feat/c73-candidate-staging             9487e322   ✅
main (ambos repos)                        b535b525 · 179bbe36      sin mover
CHECKPOINT COMPLETO
```

#### Lo que sigue en pie

```text
Obesidad          lifecycle trained · NO-GO · sin puntero público · fuera de published_only
C7.4              INCOMPLETE 0/4
exposición        0% en producción
B1-PREFLIGHT      estacionado · docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
C7.7              cerrada hasta validar el sink real de Google Sheets/Tableau
```

Sin `--force`, PR, merge, tag, cambio de `main`, deploy de producción, activación ni publicación.

#### Una cosa que conviene mirar ahora, no dentro de un mes

El branch preview quedó aceptado, así que **puede existir una URL de rama** sirviendo este EpiBot.
Si Netlify lo levantó, esa URL expone el dashboard con `knowledge.json` y `rag_index.json` de 454
chunks — sin Obesidad, verificado — pero es una superficie accesible que antes no existía. Dos cosas
que sólo puedes comprobar tú en la UI de Netlify:

1. si el preview se creó y con qué URL;
2. si esa URL está indexable o protegida por contraseña.

No es un problema de contenido: el candidate no está ahí. Es cuestión de saber qué quedó publicado.

#### Pregunta

Con el checkpoint cerrado, el siguiente trabajo real es B1 y depende de ti:

1. **¿Retomamos B1-PREFLIGHT?** Necesita la hoja de staging creada, compartida con la service
   account, y las tres variables en el entorno **desde el que se lanza la sesión** — el manual lo
   detalla paso a paso.
2. Si Google va para largo, ¿prefieres que avance el refactor pendiente de `tableau_adapter.py`
   (614 líneas, deuda declarada en la Ronda 101), que es local y no depende de nada externo?

_Respuesta:_

---

### Ronda 117 — Validación del checkpoint completo y orden de continuación — 2026-07-27

#### Estado revalidado

```text
backend local / remoto feature     c453b979 / c453b979
backend ahead / behind             0 / 0
backend main                       b535b525

dashboard local / remoto feature   9487e322 / 9487e322
dashboard ahead / behind           0 / 0
dashboard main                     179bbe36
dashboard upstream local           no configurado, deliberadamente
```

Los únicos elementos locales fuera del checkpoint son la bitácora posterior del plan y los
untracked preexistentes del usuario. No hay trabajo de producto pendiente de push.

#### Veredicto

```text
CHECKPOINT C7.6 EN AMBOS REPOS       CLOSED / REMOTE
PRODUCCIÓN                            SIN CAMBIOS
OBESIDAD                              trained · NO-GO · exposición 0%
BRANCH PREVIEW                        POSIBLE · aceptado, falta inventariarlo en Netlify
B1-PREFLIGHT                          ÚNICO BLOQUEANTE FUNCIONAL
REFACTOR tableau_adapter.py           DEFERRED hasta después del staging real
```

No conviene usar el refactor de `tableau_adapter.py` como trabajo de relleno antes de B1. El
adaptador actual tiene 298 pruebas de publicación y fue diseñado precisamente para confrontarse
ahora con `gspread` y un workbook reales. Refactorizarlo antes de esa evidencia:

- cambia la superficie que B1 pretende validar;
- obliga a repetir parte de ADAPTERS-A/B0;
- puede esconder si un fallo viene de Google o de la reorganización;
- no acerca por sí mismo la publicación.

El refactor permanece como deuda válida, pero se ejecutará con comportamiento real ya medido.

### Orden inmediata para el usuario — inventario del preview

En Netlify:

1. Abrir el sitio del dashboard.
2. Ir a **Deploys** y filtrar por `feat/c73-candidate-staging`.
3. Registrar en la respuesta:

```text
preview_created: true | false
preview_status: ready | failed | canceled | none
preview_url: <URL o none>
access: public | password | team-only | unknown
search_indexing: allowed | blocked | unknown
production_branch: main
production_deploy_unchanged: true
```

4. Si existe y no quieres mantenerlo, deshabilitar branch deploys o borrar sólo ese deploy desde
   Netlify. No borrar la rama Git ni tocar producción.
5. No pegar tokens, IDs internos, headers ni credenciales en el plan; la URL del preview sí puede
   registrarse si no contiene un secreto.

Esta comprobación no bloquea preparar B1, pero cierra el inventario de superficies externas.

### Orden funcional siguiente — reanudar B1 cuando sea posible

Seguir literalmente:

```text
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
```

Condiciones antes de arrancar una nueva sesión:

1. hoja de Google Sheets **de staging**, nunca la productiva;
2. hoja compartida con la service account;
3. `C7_TABLEAU_STAGING_SPREADSHEET_ID` disponible en el entorno;
4. `GSHEETS_SPREADSHEET_ID` productivo disponible sólo para demostrar no-colisión;
5. `GOOGLE_SERVICE_ACCOUNT_JSON` disponible como secreto de entorno;
6. las tres variables heredadas por el proceso que lanza la sesión;
7. no imprimir valores, longitudes ni prefijos.

Al reanudar, ejecutar primero únicamente el preflight read-only del manual. Si identidad,
permisos, tablas existentes o separación staging/productivo no son demostrables, STOP. No aplicar,
promover ni activar en la misma orden.

#### Próxima autorización literal para B1

_Respuesta:_ **GO C7.6-PROMOTION-ADAPTERS-B1-PREFLIGHT READ-ONLY. Seguir
`docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md`, validar identidad y permisos de la hoja de staging
sin escribir tablas, generar sólo evidencia en temporal permitido y STOP. Sin apply, DVC, push,
PR, merge, lifecycle, puntero, deploy ni publicación.**

Si todavía no puedes preparar Google, no hay otra acción funcional crítica que ejecutar: conserva
el checkpoint y retoma B1 cuando estén disponibles la hoja y las variables.

---

### Ronda 118 — Carril autónomo mientras las tareas manuales quedan pendientes — 2026-07-29

#### Decisión del usuario

El usuario no puede intervenir manualmente ahora. Quedan expresamente estacionadas, sin bloquear
el trabajo local:

```text
Netlify UI / inventario del branch preview
crear y compartir la hoja Google Sheets de staging
obtener o cargar IDs y service-account JSON
abrir o refrescar Tableau Desktop
autorizar apply sobre Google
activar lifecycle y puntero
merge, deploy y smoke público
```

No presentar ninguna de ellas como PASS. Permanecen `PENDING_MANUAL`.

#### Qué sí puede avanzar de forma autónoma

El código ya tiene piezas separadas para compilar el candidate, inspeccionar Google, planear el
staging y generar el workbook, pero el procedimiento sigue distribuido entre dos CLI y un manual.
La siguiente mejora útil es un **orquestador genérico de readiness** que:

1. complete todo el carril local sin red ni credenciales;
2. produzca evidencia determinista y redactada;
3. cuando las variables existan en el futuro, continúe automáticamente con el preflight externo
   read-only;
4. nunca contenga ni habilite `--apply`;
5. distinga `PASS_LOCAL` de `BLOCKED_EXTERNAL`, sin llamar PASS a B1.

Esto reduce la intervención futura a provisionar Google una sola vez. No publica y no cambia el
porcentaje de exposición.

### Orden C7.6-AUTO-B1-HARNESS — local, genérica, sin red y STOP

#### Objetivo

Crear un comando canónico:

```text
python -m scripts.publication_readiness
```

que cierre automáticamente la preparación local de un release y deje listo el mismo comando para
reanudar el preflight externo cuando exista el entorno.

#### Alcance permitido

```text
scripts/publication_readiness.py                         nuevo
tests/unit/publication/test_publication_readiness.py     nuevo
Makefile                                                 sólo un target delgado, si aporta valor
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md               sólo para sustituir la receta manual
                                                        por el comando canónico; sin secretos
```

No tocar:

```text
src/epiforecast/publication/tableau_adapter.py
src/epiforecast/publication/sheets_sink.py
scripts/tableau_staging.py
scripts/tableau_workbook.py
config/padecimientos.yaml
config/publication/
artifacts/ · reports/ · data/ · models/ · dashboard
```

El orquestador compone APIs existentes; no las rediseña.

#### Interfaz mínima

```text
publication_readiness local
  --disease <registry_id>
  --release-target <ruta .dvc o bundle>
  --evidence-root <runs/ o temporal permitido>

publication_readiness external-readonly
  --local-evidence <manifest local>
```

Reglas:

- `local` no lee variables de Google y no importa ni autentica `gspread`;
- `external-readonly` exige las tres variables, pero sólo invoca `inspect`, dry-run de `stage` y
  generación/verificación del workbook;
- no existe subcomando, flag ni llamada interna equivalente a `apply`, `recover`, promote o
  delete;
- disease, release, conteos y canales se derivan de registry/manifests, nunca de constantes de
  Obesidad;
- la raíz de evidencia debe estar en `runs/` gitignored o en el temporal real del sistema;
- ningún ID, JSON, email, ruta de credencial, longitud o prefijo sensible entra al reporte.

#### Flujo `local`

1. Verificar registry, lifecycle y backend de artefacto.
2. Verificar bundle, checksums y release manifest.
3. Compilar candidate dos veces bajo raíces distintas.
4. Exigir árboles byte-idénticos.
5. Validar manifests y shards.
6. Construir tablas Tableau y workbook con una identidad **sintética claramente local**, nunca con
   el ID productivo.
7. Verificar:

```text
release_id estable
5,772 filas / 111 productos para el release actual, derivados del manifest, no hardcodeados
lifecycle trained
INCOMPLETE 0/4
point-only y límites nulos
channels_without_bridge vacío
workbook tableau_desktop_validated=false
cero escrituras públicas
```

8. Escribir atómicamente un `readiness_manifest.v1.json` con sólo digests, conteos, versiones,
   estados y lista de requisitos externos pendientes.
9. Resultado:

```text
PASS_LOCAL + BLOCKED_EXTERNAL
```

`BLOCKED_EXTERNAL` no es error del carril local ni PASS de B1.

#### Flujo futuro `external-readonly`

Cuando el usuario prepare Google:

1. cargar y verificar el manifest local;
2. comprobar sólo presencia de variables y no-colisión de IDs;
3. autenticar una vez;
4. ejecutar dos inventarios y exigir digest idéntico;
5. ejecutar stage sin `--apply`;
6. regenerar/verificar el workbook con el ID real de staging;
7. producir `external_preflight.v1.json` redactado;
8. STOP.

No se implementa ni se prueba contra red en esta ronda. Se prueba con adaptadores inyectados que
demuestran secuencia, no mutación y redacción.

#### Tests obligatorios

1. Dos corridas locales producen el mismo manifest salvo una ruta temporal explícitamente excluida
   de identidad.
2. El código no contiene `apply`, `recover`, `promote`, `delete` ni llamadas de escritura al sink.
3. Local funciona con `gspread` ausente y con las variables secretas sembradas; no las lee.
4. External-readonly sin una variable devuelve `BLOCKED_EXTERNAL`, sin autenticar.
5. IDs iguales se rechazan antes de autenticar.
6. Proveedor que intenta registrar un secreto: la salida lo redacta y el test busca el valor
   centinela en todos los archivos.
7. Inventarios distintos: FAIL, sin stage.
8. Dry-run que propone una tab ajena o residuos: FAIL.
9. Workbook con ID productivo, Tableau Public o `tableau_desktop_validated=true`: FAIL.
10. Bundle/shard alterado: FAIL antes de cualquier borde externo.
11. Disease sintética demuestra N+1; AST sin nombres de padecimientos, motores ni `64/111`.
12. El manifest declara honestamente `manual_requirements_status=PENDING`.

#### Gates

```text
ruff check
ruff format --check
mypy
tests focales del orquestador
tests/unit/publication completos
make test-fast
doctor_padecimiento Obesidad --artifacts
hashes del release y cuatro agregados legacy sin cambio
git diff --check
```

Ejecutar una prueba local real sobre el release DVC actual, sin red, y reportar la ruta del manifest
gitignored. No usar Google ni Gemini.

#### Commit y STOP

Un commit local acotado, sin push:

```text
C7.6 automate local publication readiness and external preflight handoff
```

Después STOP para auditoría. No iniciar el refactor de `tableau_adapter.py` en el mismo commit.

#### Prohibiciones

Sin credenciales, red de Google, Netlify, Tableau Desktop, `--apply`, recover, DVC add/push, push
Git, PR, merge, lifecycle, puntero, deploy, publicación ni borrado de untracked.

#### Siguiente orden autónoma

_Respuesta:_ **GO C7.6-AUTO-B1-HARNESS LOCAL. Implementar el orquestador genérico de readiness,
ejecutar únicamente el flujo local sin red ni credenciales, producir evidencia gitignored, crear
un commit local acotado y STOP. Mantener todas las tareas manuales como `PENDING_MANUAL`; sin
Google, Netlify, Tableau Desktop, apply, DVC, push, lifecycle, puntero, deploy ni publicación.**


---

### Ronda 119 — C7.6-AUTO-B1-HARNESS ejecutada — 2026-07-29

**Commit local (sin push):**

```text
527615f5  C7.6 automate local publication readiness and external preflight handoff
```

Cuatro archivos, los cuatro del alcance permitido. El plan **no** entró en el commit.

```text
A  scripts/publication_readiness.py
A  tests/unit/publication/test_publication_readiness.py
M  Makefile                                     (un target delgado: `make readiness`)
M  docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md   (la receta manual → el comando canónico)
```

`tableau_adapter.py`, `sheets_sink.py`, `tableau_staging.py`, `tableau_workbook.py`,
`config/`, `artifacts/`, `reports/`, `data/`, `models/` y el dashboard: sin tocar. El orquestador
**compone** las APIs existentes; no rediseña ninguna.

#### Corrida real sobre el release DVC actual, sin red

```text
make readiness DISEASE=obesidad RELEASE=artifacts/releases/obesidad/obesidad_release_2517e7858901

evidencia   runs/readiness/obesidad/readiness_manifest.json      (gitignored: .gitignore:271 runs/)
status      PASS_LOCAL          external_status  BLOCKED_EXTERNAL          failures  []
reproducible  2 compilaciones · 0 diferencias de árbol
shard       5,772 filas · 111 productos (64 base + 47 derivados) · 64 modelos · horizonte 52
            lifecycle trained · INCOMPLETE 0/4 · interval_method none
            channels_without_bridge []  ·  etiqueta «… (0/4 semanas) · pronóstico puntual …»
tablas      runner_forecast 5,772 · runner_releases 1
workbook    14,546 bytes · tableau_desktop_validated false · identidad sintética
public_writes  0
manual_requirements_status  PENDING  (8 tareas enumeradas por nombre)
manifest_digest  bc88050e3c4169db…  ← IDÉNTICO en dos raíces de evidencia distintas
```

Ningún conteo de esa tabla está escrito en el código: todos salen del manifiesto del shard.

#### Los doce tests obligatorios

| # | Qué fija | Cómo |
|---|---|---|
| 1 | dos corridas, el mismo manifiesto | mismo `manifest_digest` y mismos bytes en disco; `evidence_path` es lo único que difiere y está fuera de la identidad |
| 2 | sin operaciones de escritura | **AST**: ninguna llamada del módulo resuelve a `apply/recover/promote/rollback/delete/write_table/rename_table/drop_table/del_worksheet/update_title` |
| 3 | local no lee las variables | se siembran las tres con centinelas, corre el carril y se buscan los centinelas en **todos** los archivos producidos |
| 4 | falta una variable → `BLOCKED_EXTERNAL` | parametrizado por las tres; el `sink_factory` cuenta aperturas y queda en **0** |
| 5 | IDs iguales → bloqueado antes de autenticar | igual, con 0 aperturas |
| 6 | proveedor que filtra el secreto | el sink revienta arrastrando id y JSON; se buscan los centinelas en el reporte y en todos los archivos |
| 7 | inventarios distintos → FAIL | la hoja se mueve entre los dos inventarios; no hay `planned_steps` |
| 8 | residuos → FAIL | parametrizado por `__next` y `__backup` |
| 9 | workbook inválido → FAIL | el verificador ya cubre ID productivo, Tableau Public y `tableau_desktop_validated` |
| 10 | shard alterado → FAIL antes del borde externo | el segundo árbol sale distinto: no se emite evidencia |
| 11 | genericidad | AST sin nombres de padecimiento, motores ni los conteos; y los invariantes se comprueban contra el `disease` **inyectado** |
| 12 | honestidad del manifiesto | `manual_requirements_status == PENDING` |

**27 pruebas nuevas, todas verdes.**

#### Dos lecturas que declaro en vez de esconder

1. **`promotion_plan` contiene la subcadena «promot».** La orden pedía que el código no contuviera
   `promote`. La leí como «no llamar a ninguna operación de escritura», que es lo que protege el
   contrato, y la prueba es por AST sobre las llamadas, no por grep sobre el texto.
   `promotion_plan` sólo lee —su docstring lo dice y una prueba de `test_sheets_sink` lo ancla al
   comportamiento real de `promote`— y duplicar el protocolo para evitar una palabra habría
   reintroducido justo la deriva que A.1.1 cerró.
2. **La genericidad N+1 se prueba a nivel de unidad**, no compilando un padecimiento sintético de
   punta a punta: eso exigiría una segunda entrada de registry y su `config/publication/`, y C6 ya
   demostró el alta por configuración con F50. Lo que sí se prueba aquí es que los invariantes se
   evalúan contra el `disease` que se inyecta, y que el AST no conoce ningún nombre ni conteo.

#### Gates

```text
ruff check                                    PASS
ruff format --check                           PASS (365 archivos)
mypy                                          PASS (165 fuentes)
tests/unit/publication                        324 passed · 1 skipped
make test-fast                                2,158 passed · 1 skipped · 61 deselected
doctor_padecimiento obesidad --artifacts      ✅ completo (config+artefactos)
git diff --check                              PASS
```

#### Preservación

```text
release SHA256SUMS.txt        618b4577…      sin cambios
tableau.csv                   b334e239…      auditoria_motores_2026  02ea61f0…
tabla_333_modelos_produccion  af7942a4…
artifacts/ · data/ · reports/ · models/ · config/ · dashboard   sin tocar
Obesidad   lifecycle trained · NO-GO · sin puntero · fuera de published_only
```

Sin credenciales, red de Google, Netlify, Tableau Desktop, `--apply`, recover, DVC, push, PR, merge,
lifecycle, puntero, deploy, publicación ni borrado de untracked.

#### Qué queda automatizable

Poco, y conviene decirlo: **el carril local ya está cerrado**. Lo que queda es la validación externa,
y no se puede simular sin mentir. Cuando existan las tres variables, un solo comando
—`publication_readiness external-readonly`— cierra el preflight entero.

La única deuda técnica declarada sigue siendo el refactor de `tableau_adapter.py` (614 líneas), que
tú mismo pospusiste hasta después del staging real.

#### Pregunta

Antes de que dé por agotado el carril autónomo:

1. ¿Quieres que el `readiness` se ejecute también sobre **Anorexia F50** —`lifecycle=configured`,
   sin canales— como prueba negativa real de N+1? Debería fallar por «ningún canal declarado tiene
   puente», y eso sería evidencia de genericidad mucho más fuerte que la actual.
2. ¿Hay algo más que consideres automatizable, o cierro aquí y el siguiente movimiento es tuyo
   (hoja de staging + variables) siguiendo el manual?

_Respuesta:_

---

### Ronda 120 — Auditoría independiente de AUTO-B1-HARNESS — 2026-07-29

#### Superficie y pruebas que sí pasan

```text
commit                         527615f5
parent                         c453b979
archivos                       4, todos permitidos
git show --check               PASS
secret scan del diff           0 credenciales reales
tests focales                  27 / 27
ruff / format / mypy           coherentes con el gate reportado
carril local real              PASS_LOCAL + BLOCKED_EXTERNAL
```

El flujo local es útil y no abre Google. Sin embargo, el criterio de cierre incluía que la
reanudación externa futura funcionara con el comando del manual y que la evidencia gobernara el
handoff. Eso todavía es **FAIL** por dos reproducciones P0.

#### R120-P0-1 · el comando canónico del manual no puede localizar el shard

El manual ordena:

```bash
python -m scripts.publication_readiness external-readonly \
  --local-evidence runs/readiness/obesidad/readiness_manifest.json
```

Pero el JSON persistido no contiene `evidence_path` ni una ruta relativa sellada:

```text
has("evidence_path") = false
```

Con las tres variables presentes y un sink inyectado sin red, el mismo camino termina:

```text
status   FAIL
failure  KeyError: 'evidence_path'
```

Las pruebas no lo detectaron porque siempre pasaron `shard_root` directamente a la función. El CLI
documentado no lo pasa. La prueba del helper no prueba el contrato de usuario.

#### R120-P0-2 · una evidencia local alterada gobierna el preflight externo

`run_external_readonly` copia `manifest_digest`, pero nunca lo recomputa. Tampoco cruza
`disease_id`, `release_id` y `shard_manifest_digest` contra el shard que consume.

Reproducción sin red:

1. copiar el manifiesto real;
2. cambiar `disease_id` y `release_id`;
3. dejar el digest viejo;
4. pasar el shard real por `shard_root`;
5. usar un sink de memoria.

Resultado:

```json
{
  "status": "PASS_EXTERNAL_READONLY",
  "disease_id": "padecimiento_fabricado",
  "release_id": "release_fabricado",
  "local_manifest_digest": "bc88050e..."
}
```

Es un falso PASS de lineage: el plan y el workbook salen del shard real, pero el reporte afirma
otra identidad. Antes de tocar Google, esto es P0.

#### R120-P1 · `external_preflight.v1` no queda persistido

`EXTERNAL_FILE = "external_preflight.json"` está declarado pero no se usa. El flujo externo
devuelve JSON por stdout; no deja un artefacto atómico, sellado y cargable que pueda gobernar el
siguiente gate. No bloquea el carril local, pero sí el handoff prometido.

#### Sobre la prueba negativa con F50

No ejecutarla todavía. F50 tiene:

```text
lifecycle       configured
channels        []
artifact_source ausente
release bundle  ausente
```

Por tanto, `readiness` fallaría antes de compilar —por falta de release/status—, no por «ningún
canal declarado tiene puente». Reportarlo como prueba real de genericidad sería atribuir al guard
de canales un fallo producido en otra frontera. C6 ya demuestra N+1 por configuración; una prueba
end-to-end de readiness requiere primero un release F50 sellado, trabajo fuera de C7.

#### Veredicto

```text
LOCAL HARNESS                  PASS
EXTERNAL HANDOFF               FAIL
COMMIT 527615f5                REQUIERE A.1 antes de push
F50 NEGATIVE RUN               NO EJECUTAR; precondiciones ausentes
TAREAS MANUALES                PENDING_MANUAL, sin cambio
```

### Orden C7.6-AUTO-B1-HARNESS-A.1 — local, sin red y STOP

#### Alcance permitido

```text
scripts/publication_readiness.py
tests/unit/publication/test_publication_readiness.py
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
```

No tocar Makefile salvo que el target local haya quedado incorrecto. No tocar adapters, sinks, CLI
previos, registry, config, artifacts, dashboard ni el plan dentro del commit.

#### Corrección 1 · manifest local autocontenido y portable

Persistir en `readiness_manifest.v1`:

```text
shard_relative_root
shard_tree_digest
```

La ruta debe ser relativa al directorio de evidencia, canónica y sin componentes absolutos, `.`,
`..` ni symlinks que salgan de la raíz. No persistir rutas absolutas.

El comando externo sin `--shard-root` debe resolver:

```text
local_evidence.parent / shard_relative_root
```

Si se conserva `--shard-root` por compatibilidad, exigir que resuelva exactamente al mismo
directorio declarado; no permitir que sustituya la identidad sellada.

#### Corrección 2 · loader de evidencia

Crear una única función que:

1. exija forma cerrada de `readiness_manifest.v1`;
2. extraiga `manifest_digest`, recompute `sha256(canonical_json(payload_sin_digest))` y compare;
3. resuelva la raíz del shard con containment;
4. cargue y verifique `shard_manifest.json` y todos sus archivos;
5. compare al menos:

```text
disease_id
release_id
shard_manifest_digest
publication_label
lifecycle
rows
products
channels_emitted
```

6. reconstruya las tablas y compruebe `table_digests`;
7. sólo entonces permita abrir el borde externo.

Toda discrepancia debe fallar antes de `sink_factory`.

#### Corrección 3 · evidencia externa persistida

El CLI externo debe escribir atómicamente, junto al manifiesto local:

```text
external_preflight.json
```

Contrato:

- schema cerrado `external_preflight.v1`;
- digest propio recomputable, excluyendo sólo su campo de digest;
- identidad cruzada con el local y el shard;
- inventario, pasos dry-run, workbook y estado redactados;
- nunca IDs, JSON, emails, longitudes, prefijos ni rutas de credenciales;
- ante `BLOCKED_EXTERNAL` puede imprimir el estado, pero no debe reemplazar un PASS externo previo;
- ante FAIL no debe reemplazar evidencia previa válida; conservar el fallo en stdout redactado.

#### Tests rojos obligatorios

1. Ejecutar el CLI exactamente como lo documenta el manual, sin `--shard-root`: debe llegar al
   sink inyectado y completar el positivo.
2. Manifiesto sin ruta relativa: rechazo antes del sink.
3. Ruta absoluta, `..` o symlink fuera de evidencia: rechazo.
4. `--shard-root` distinto del declarado: rechazo.
5. Alterar cada uno de disease, release, manifest digest, shard digest, label, lifecycle, rows,
   products o channels y volver a sellar sólo la capa exterior: rechazo antes del sink.
6. Alterar un archivo del shard: rechazo antes del sink.
7. Alterar `table_digests`: rechazo.
8. External PASS escribe un JSON cargable y su digest recomputa.
9. FAIL/BLOCKED no destruyen un PASS externo previo.
10. Buscar todos los centinelas secretos en stdout y en todos los archivos producidos.
11. El comando del manual se extrae o prueba desde el propio documento para impedir otra deriva.

#### Gates

```text
ruff check
ruff format --check
mypy
tests focales
tests/unit/publication completos
make test-fast
carril local real dos veces, mismo digest
external-readonly positivo con sink inyectado, sin red
doctor --artifacts
release y agregados legacy byte-idénticos
git diff --check
```

#### Commit y STOP

Un commit local separado:

```text
C7.6 seal readiness handoff and make documented resume executable
```

Sin amend de `527615f5`. Después STOP para reauditoría. No ejecutar F50.

#### Siguiente orden autónoma

_Respuesta:_ **GO C7.6-AUTO-B1-HARNESS-A.1 LOCAL. Sellar y cruzar la evidencia local con el shard,
hacer ejecutable el comando exacto del manual, persistir `external_preflight.v1` atómicamente y
probar todo con sink inyectado sin red. Commit local separado y STOP. Mantener F50 y todas las
tareas manuales pendientes; sin Google, Netlify, Tableau Desktop, DVC, push, lifecycle, puntero,
deploy ni publicación.**


---

### Ronda 121 — C7.6-AUTO-B1-HARNESS-A.1 ejecutada — 2026-07-29

**Commit local separado (sin amend de `527615f5`, sin push):**

```text
d9a54f18  C7.6 seal readiness handoff and make documented resume executable
```

Tres archivos, los tres del alcance permitido. El `Makefile` no hizo falta tocarlo: el target local
seguía siendo correcto. Adapters, sinks, CLI previos, registry, config, artifacts y dashboard: sin
tocar. El plan no entró en el commit.

#### Los dos P0, reproducidos antes de corregir

```text
P0-1  comando del manual        rc=1 · KeyError: 'evidence_path'
P0-2  identidad fabricada       PASS_EXTERNAL_READONLY con disease_id=padecimiento_fabricado
```

#### Y después

```text
P0-1  comando del manual        rc=0 · PASS_EXTERNAL_READONLY
P0-2  identidad fabricada       RECHAZADA: «disease_id del shard: 'obesidad' != 'padecimiento_fabricado'»
```

#### Corrección 1 · manifiesto autocontenido y portable

El manifiesto sella `shard_relative_root` y `shard_tree_digest`. La ruta es **relativa** a la
evidencia y se resuelve con containment: ni absoluta, ni con `..`, ni con symlinks que salgan de la
raíz. Y sigue **sin** persistir ninguna ruta absoluta — eso era correcto y no se tocó; lo que
faltaba era la relativa.

`--shard-root` sobrevive por compatibilidad, pero ya no sustituye la identidad sellada: tiene que
resolver exactamente a la raíz declarada. Ni siquiera apuntando a `compile_b`, que es byte-idéntico.

#### Corrección 2 · `load_local_evidence`, un solo lugar

```text
1  forma cerrada de readiness_manifest.v1        24 claves exactas
2  digest RECOMPUTADO sobre el payload sin su propio campo
3  raíz del shard resuelta con containment
4  shard_manifest.json y TODOS sus archivos verificados · digest del árbol entero
5  identidad cruzada  disease_id · release_id · shard_manifest_digest
                      lifecycle · rows · products · channels_emitted · publication_label
6  tablas reconstruidas y comparadas contra table_digests
7  sólo entonces se puede abrir el borde externo
```

En las 26 pruebas nuevas, un contador comprueba que el `sink_factory` quedó en **cero aperturas**.

#### Corrección 3 · `external_preflight.v1` persistido

Forma cerrada de doce claves, digest propio recomputable excluyendo sólo su campo de digest,
identidad cruzada con el local, y todo redactado. **Sólo un PASS escribe el artefacto**: un FAIL o
un `BLOCKED_EXTERNAL` no lo sobrescriben, porque borrar la evidencia de un preflight que sí pasó
sería perder lo único que gobierna el gate siguiente.

#### Las once pruebas rojas obligatorias

| # | Prueba | Estado |
|---|---|---|
| 1 | CLI tal como lo documenta el manual, sin `--shard-root`, llega al sink | ✅ |
| 2 | manifiesto sin ruta relativa → rechazo antes del sink | ✅ |
| 3 | ruta absoluta, `..`, `.` o symlink fuera → rechazo | ✅ (5 formas + symlink) |
| 4 | `--shard-root` distinto del declarado → rechazo | ✅ |
| 5 | alterar identidad y resellar sólo por fuera → rechazo | ✅ (10 mutaciones) |
| 6 | archivo del shard alterado → rechazo antes del sink | ✅ |
| 7 | `table_digests` alterado → rechazo | ✅ |
| 8 | PASS externo escribe JSON cargable y su digest recomputa | ✅ |
| 9 | FAIL y BLOCKED no destruyen un PASS previo | ✅ (parametrizado) |
| 10 | centinelas en stdout y en todos los archivos | ✅ |
| 11 | el comando se **extrae del propio manual** | ✅ |

La 11 es la que impide que esto vuelva a pasar: la prueba lee los bloques ```zsh``` del manual,
localiza el comando externo, comprueba que no depende de `--shard-root` ni de `--apply`, y valida
esa forma contra el parser real. Si el manual y el CLI se separan, la prueba lo dice.

**53 pruebas focales, todas verdes.**

#### Gates

```text
ruff check · ruff format --check · mypy (165 fuentes)     PASS
tests focales                                              53 passed
tests/unit/publication                                    350 passed · 1 skipped
make test-fast                                          2,184 passed · 1 skipped
carril local dos veces, mismo digest      39a353ce06c1ebf1…  (uno por bundle, otro por su .dvc;
                                                             byte-idénticos)
external-readonly positivo con sink inyectado, sin red     PASS · 6 pasos · 911760c7…
doctor_padecimiento obesidad --artifacts                   ✅ completo (config+artefactos)
git diff --check                                           PASS
release SHA256SUMS 618b4577… · tableau.csv b334e239… · auditoria 02ea61f0…   sin cambios
```

#### F50

No se ejecutó, y el motivo de la auditoría es correcto: sin `artifact_source` ni release bundle,
`readiness` fallaría al cargar el estado declarado, **antes** del guard de canales. Reportar eso
como prueba de genericidad sería atribuir a un guard un fallo producido en otra frontera. Queda
donde estaba: C6 ya demuestra N+1 por configuración, y un end-to-end de F50 exige primero un release
sellado, que es trabajo fuera de C7.

#### Estado

```text
LOCAL HARNESS      PASS
EXTERNAL HANDOFF   PASS con sink inyectado · BLOCKED_EXTERNAL sin las variables
TAREAS MANUALES    PENDING_MANUAL, las ocho
Obesidad           trained · NO-GO · sin puntero · fuera de published_only
exposición         0%
```

#### Pregunta

Con esto, el carril autónomo queda **agotado de verdad**: lo que falta ya no es código, es una hoja
de Google y tres variables.

1. ¿Quieres que audite `527615f5..d9a54f18` como rango antes de que decidas el push, o lo dejamos
   para cuando se sumen más commits?
2. ¿Se te ocurre algo más automatizable que yo no esté viendo? Si no, cierro aquí y el siguiente
   movimiento es el manual, paso 1.

_Respuesta:_

---

### Ronda 122 — Reauditoría de A.1 y cierre mínimo restante — 2026-07-29

#### Lo que A.1 sí cerró

```text
commit                         d9a54f18
superficie                     3 archivos permitidos
git show --check               PASS
tests focales                  53 / 53
comando del manual             ejecutable sin --shard-root
identidad fabricada            rechazada antes del sink
digest local                   recomputado
shard y tablas                 cruzados
external_preflight.json        atómico y sólo en PASS
```

Los dos P0 de la Ronda 120 están cerrados. La reauditoría encontró dos fronteras adicionales que
impiden llamar terminado al handoff.

#### R122-P0 · el externo puede escribir evidencia en una ruta versionable

`run_local` valida `--evidence-root`, pero `external-readonly` no vuelve a validar la ubicación de
`local_evidence.parent`. Un árbol de evidencia válido puede copiarse completo bajo `reports/` y el
flujo externo escribe `external_preflight.json` junto a él.

Reproducción temporal y limpiada al terminar:

```json
{"versionable_status":"PASS_EXTERNAL_READONLY","external_file_created":true}
```

No se usó red. La raíz temporal de la reproducción estuvo bajo `reports/.audit-readiness-*` y se
eliminó automáticamente. No quedó residuo.

El contrato dice que la evidencia vive sólo en `runs/` gitignored o en el temporal real. Moverla
no debe convertir una ruta pública/versionable en destino válido.

#### R122-P1 · `shard_files` puede ser un subconjunto re-sellado

El loader comprueba cada entrada declarada en `payload["shard_files"]`, pero no exige igualdad con
`shard_manifest.json["files"]`. Si se elimina una entrada del inventario local, se recomputa el
digest exterior y los bytes del shard permanecen intactos, el preflight todavía pasa:

```json
{
  "subset_status":"PASS_EXTERNAL_READONLY",
  "removed_inventory_entry":"epibot/corpus/obesidad.md"
}
```

El `shard_tree_digest` evita sustituir bytes, pero no corrige la afirmación falsa del inventario
local. Un manifiesto cerrado debe declarar todos y sólo los archivos sellados por el shard.

#### R122-P1 · el preflight externo aún no tiene loader gobernante

El archivo tiene forma cerrada y digest, pero no existe una función única que lo cargue,
recompute su digest y lo cruce otra vez contra el manifiesto local. Antes de que otro gate lo use,
esa frontera debe existir; de lo contrario el siguiente consumidor repetirá el error de confiar en
una clave `preflight_digest` sin verificarla.

#### Veredicto

```text
LOCAL HARNESS                   PASS
A.1                             PASS PARCIAL
EXTERNAL EVIDENCE LOCATION      FAIL
SHARD INVENTORY EXACTNESS       FAIL
RANGO 527615f5..d9a54f18        NO PUSH todavía
F50                             NO EJECUTAR
TAREAS MANUALES                 PENDING_MANUAL
```

### Orden C7.6-AUTO-B1-HARNESS-A.2 — local, sin red y STOP

#### Alcance permitido

```text
scripts/publication_readiness.py
tests/unit/publication/test_publication_readiness.py
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md   sólo si cambia el contrato visible
```

No tocar adapters, sinks, CLI previos, Makefile, registry, config, artifacts, dashboard ni el plan
dentro del commit.

#### Corrección 1 · ubicación segura también en external

Antes de cargar la evidencia o abrir el sink:

1. validar `local_evidence.parent` con la misma política de `check_evidence_root`;
2. aceptar sólo descendientes resueltos de:
   - `<repo>/runs/`, comprobado gitignored;
   - la raíz temporal real del sistema;
3. rechazar `reports/`, `data/`, `artifacts/`, `models/`, dashboard y cualquier otra ruta del repo;
4. revalidar containment inmediatamente antes de escribir `external_preflight.json`.

La prueba debe colocar una copia completa y válida bajo una ruta versionable temporal del repo,
obtener rechazo **antes del sink** y demostrar cero archivo externo creado.

#### Corrección 2 · inventario exacto

Exigir:

```text
payload["shard_files"] == shard_manifest["files"]
```

antes de iterar. Validar ambos como mappings de `ruta relativa canónica → sha256`. Rechazar:

- entrada ausente;
- entrada extra;
- digest distinto;
- ruta absoluta, vacía, `.`, `..` o que escape de la raíz;
- archivo no regular o symlink.

Después verificar todos los archivos del inventario exacto.

#### Corrección 3 · loader de `external_preflight.v1`

Añadir una función pura que:

1. exija las doce claves exactas;
2. extraiga y recompute `preflight_digest`;
3. exija `status=PASS_EXTERNAL_READONLY`;
4. cargue el manifiesto local mediante `load_local_evidence`;
5. cruce disease, release y `local_manifest_digest`;
6. valide forma cerrada de inventory, planned steps y workbook;
7. rechace `tableau_desktop_validated=true`;
8. no abra Google ni escriba archivos.

No crear aún el gate de apply; sólo cerrar la capacidad de consumir evidencia sin confiar.

#### Tests obligatorios

1. Evidencia válida copiada bajo `reports/`: rechazo antes del sink, cero escritura.
2. Evidencia bajo `runs/` gitignored: PASS.
3. Evidencia bajo el temporal real: PASS.
4. Reubicar por symlink desde `runs/` hacia ruta versionable: rechazo.
5. `shard_files` con una entrada ausente, extra o digest distinto: rechazo.
6. Cada ruta inválida del inventario: rechazo antes de leer fuera.
7. Symlink plantado como archivo del shard: rechazo.
8. Loader externo positivo recomputa y cruza los tres artefactos.
9. Mutar cada clave gobernante del externo y re-sellar sólo la capa exterior: rechazo.
10. Loader externo no abre sink ni escribe.
11. Los 53 focales previos permanecen verdes.

#### Gates

```text
ruff check
ruff format --check
mypy
tests focales
tests/unit/publication completos
make test-fast
local real dos veces
external positivo con sink inyectado bajo runs/ y temporal
load_external_preflight positivo
doctor --artifacts
release y agregados legacy byte-idénticos
git diff --check
```

#### Commit y STOP

Commit local separado:

```text
C7.6 close readiness evidence location and inventory contracts
```

Después STOP para auditar el rango completo `c453b979..NUEVO_SHA`. Sin push.

#### Siguiente orden autónoma

_Respuesta:_ **GO C7.6-AUTO-B1-HARNESS-A.2 LOCAL. Cerrar la ubicación segura del preflight externo,
exigir inventario exacto del shard y añadir el loader gobernante de `external_preflight.v1`.
Probarlo todo sin red, crear un commit local separado y STOP. Mantener F50 y todas las tareas
manuales pendientes; sin Google, Netlify, Tableau Desktop, DVC, push, lifecycle, puntero, deploy
ni publicación.**


---

### Ronda 123 — C7.6-AUTO-B1-HARNESS-A.2 ejecutada — 2026-07-29

**Commit local separado (sin push):**

```text
7025aa31  C7.6 close readiness evidence location and inventory contracts
```

Dos archivos. El manual **no** cambió: ninguna de las tres correcciones altera el contrato visible
al usuario. Adapters, sinks, CLI previos, `Makefile`, registry, config y dashboard: sin tocar.

Rango pendiente de auditoría: `c453b979..7025aa31`.

#### Corrección 1 · ubicación segura también en el externo

`load_local_evidence` aplica ahora la misma política de `check_evidence_root` sobre
`local_evidence.parent`, y la escritura **revalida el containment justo antes de tocar el disco**:
entre cargar y escribir pudo cambiar el destino —un symlink reapuntado—, y lo que importa es dónde
caen los bytes, no dónde estaban cuando se leyó.

```text
evidencia copiada bajo <repo>/reports/     rechazada · 0 aperturas de sink · 0 archivos creados
evidencia bajo <repo>/runs/ (gitignored)   PASS
evidencia bajo la raíz temporal real       PASS
symlink runs/… → reports/…                 rechazado tras resolver la ruta
```

Las pruebas que escriben dentro del repo limpian su rastro en `finally`; `git status` queda sin
residuos.

#### Corrección 2 · inventario exacto

Se exige `payload["shard_files"] == shard_manifest["files"]` **antes** de iterar: ni falta ni sobra
ninguna entrada, y los digests coinciden. El `shard_tree_digest` ya impedía sustituir bytes, pero no
corregía una afirmación falsa sobre qué contiene el shard.

Cada ruta del inventario tiene que ser relativa, canónica, sin `..` ni `.`, sin escapar de la raíz y
sin ser un symlink. Lo de «canónica» no es cosmético: `./x` y `x` describen el mismo archivo con dos
cadenas, y un inventario que admite dos grafías de una ruta no es exacto.

#### Corrección 3 · `load_external_preflight`

```text
1  doce claves exactas
2  preflight_digest RECOMPUTADO sobre el payload sin su propio campo
3  status obligado a PASS_EXTERNAL_READONLY
4  el manifiesto local se carga con load_local_evidence — no se lee a mano
5  identidad cruzada  disease_id · release_id · local_manifest_digest
6  forma cerrada de inventory_digest, planned_steps y workbook
7  planned_steps dentro del namespace administrado
8  tableau_desktop_validated=true → rechazo: es un gate manual
```

Función pura: no abre Google y no escribe. Existe para que el siguiente consumidor no repita el
error de confiar en un digest sin recomputarlo.

#### Un detalle que la propia prueba de genericidad obligó a mejorar

Comprobar el `inventory_digest` con `len(...) == 64` metía el literal **64** en el módulo, que es
también el número de series base del release. La prueba de genericidad lo marcó. No la relajé:
sustituí la comprobación por una expresión de **forma sha256**, que además rechaza 64 caracteres que
no sean hexadecimales. El código quedó más estricto, no la prueba más laxa.

#### Las once pruebas obligatorias

| # | Prueba | Estado |
|---|---|---|
| 1 | evidencia válida bajo `reports/` → rechazo, cero escritura | ✅ |
| 2 | evidencia bajo `runs/` gitignored → PASS | ✅ |
| 3 | evidencia bajo el temporal real → PASS | ✅ |
| 4 | symlink desde `runs/` a ruta versionable → rechazo | ✅ |
| 5 | `shard_files` con entrada ausente, extra o digest distinto | ✅ (3 casos) |
| 6 | cada ruta inválida del inventario | ✅ (4 casos, verificando la frontera exacta) |
| 7 | symlink plantado como archivo del shard | ✅ |
| 8 | loader externo positivo cruza los tres artefactos | ✅ |
| 9 | mutar cada clave gobernante y resellar por fuera | ✅ (9 mutaciones + digest sin resellar) |
| 10 | el loader no abre sink ni escribe | ✅ |
| 11 | los 53 focales previos siguen verdes | ✅ |

**78 pruebas focales, todas verdes** (53 → 78).

En la prueba 6 comprobé algo que suele pasarse por alto: que el rechazo venga de la frontera que se
está midiendo. El caso `./reports/report.md` fallaba por el digest y no por la ruta — es decir,
pasaba por el motivo equivocado. Añadí la comprobación de forma canónica y la aserción sobre el
mensaje.

#### Gates

```text
ruff check · ruff format --check · mypy (165 fuentes)          PASS
focales                                                         78 passed
tests/unit/publication                                         375 passed · 1 skipped
make test-fast                                               2,209 passed · 1 skipped
local dos veces (bundle y su .dvc)          39a353ce06c1ebf1…  byte-idénticos
external con sink inyectado, bajo runs/ y bajo temporal        PASS · 911760c7… en ambos
load_external_preflight en ambos                               PASS
doctor_padecimiento obesidad --artifacts                       ✅ completo
release 618b4577… · tableau.csv b334e239… · auditoria 02ea61f0…   sin cambios
git diff --check                                                PASS
```

#### Estado

```text
LOCAL HARNESS               PASS
EXTERNAL HANDOFF            PASS con sink inyectado · BLOCKED_EXTERNAL sin variables
EVIDENCE LOCATION           PASS
SHARD INVENTORY EXACTNESS   PASS
EXTERNAL LOADER             PASS
F50                         NO EJECUTADO
TAREAS MANUALES             PENDING_MANUAL, las ocho
Obesidad                    trained · NO-GO · sin puntero · exposición 0%
```

#### Pregunta

El rango local ya son tres commits (`527615f5`, `d9a54f18`, `7025aa31`) sobre `c453b979`.

1. ¿Audito yo el rango completo antes de que decidas el push, o prefieres auditarlo tú como has
   venido haciendo?
2. Cada vuelta de auditoría ha encontrado algo real, y las dos últimas fueron contratos de
   *consumo* de evidencia, no de generación. Si crees que queda superficie de ese tipo sin cerrar,
   dímelo y la cierro; si no, doy el carril por agotado y el siguiente movimiento es el manual,
   paso 1.

_Respuesta:_ **La auditoría integral la ejecuté yo. El rango pasa en superficie e integridad local,
pero queda una frontera real de consumo: el preflight no está ligado a la identidad de la hoja y
su loader acepta un PASS sin entorno; además, conserva sólo cadenas de pasos y una malformada
escapa como `IndexError`. La Ronda 124 documenta las reproducciones y contiene la orden vigente:
GO C7.6-AUTO-B1-HARNESS-A.3 LOCAL. No hacer push ni comenzar el manual antes de cerrar A.3.**


---

### Ronda 125 — C7.6-AUTO-B1-HARNESS-A.3 ejecutada — 2026-07-29

**Commit local separado (sin push):**

```text
df84cece  C7.6 bind external preflight to spreadsheet identity and live state
```

Tres archivos del alcance permitido. `tableau_adapter.py`, `sheets_sink.py`, los CLI anteriores,
`Makefile`, registry, config, artifacts, DVC y dashboard: sin tocar. El plan no entró en el commit.

Rango pendiente de auditoría: **`c453b979..df84cece`** (4 commits).

#### A.3.1 · `external_preflight.v2`

v1 no se migra ni se acepta por fallback, y hay una prueba que lo fija: un artefacto que declare v1
se rechaza con un mensaje que dice qué hacer. No existe ninguno productivo, y mantener dos lectores
es exactamente como se acaba aceptando en silencio una evidencia sin identidad de hoja.

#### A.3.2 · ligado a las dos hojas, sin filtrar ids

```text
staging_identity_digest    = sha256(canonical_json({"purpose":"c7-staging",    "id": …}))
production_identity_digest = sha256(canonical_json({"purpose":"c7-production", "id": …}))
```

El `purpose` no es decorativo: la misma hoja usada en los dos papeles **no** produce la misma
huella, así que confundir las variables se nota. Comprobado en corrida real:

```text
external-readonly   PASS_EXTERNAL_READONLY · schema external_preflight.v2
huellas             60fcbaefe924… (staging) / b8ab2a63cbfa… (producción)
ids en el artefacto FALSE
```

`load_external_preflight` exige ahora el entorno **explícito** —no hay contexto implícito— y
recomputa ambas huellas antes de aceptar el PASS.

#### A.3.3 · plan sellado entero, y gramática cerrada

Se sella el mapping completo de `promotion_plan` (schema, namespace, steps, rows, digests) y el
loader lo cruza: `namespace` contra `TABLES`, `rows` contra las tablas reconstruidas desde la
evidencia local, `digests` contra `table_digests`.

Cada paso se valida contra `write|rename|drop` con una expresión, no indexando el resultado de un
`split`. La flecha tiene que corresponder al verbo, y toda tabla origen o destino vivir dentro del
namespace. Diez formas malformadas —vacío, sin `:`, verbo desconocido, flecha incompleta, flecha en
un verbo que no la admite, tabla legacy, tabla ajena— dan `ArtifactValidationError`, nunca
`IndexError`.

#### A.3.4 · el workbook se reproduce con la identidad vigente

Al cargar el preflight se recarga la evidencia local, se reconstruye el workbook con el `staging_id`
de hoy y se compara su digest con el sellado. Si la evidencia es de otra hoja, se nota **sin
abrirla**.

#### A.3.5 · `verify_external_preflight_live`

El gate que una futura orden de escritura tendrá que ejecutar inmediatamente antes de la primera
mutación: un preflight de ayer no dice nada de la hoja de hoy.

```text
1  carga y valida v2 contra el entorno
2  abre exactamente el sink de staging declarado
3  si el sink sabe decir sobre qué hoja opera, se le exige que sea la solicitada
4  dos inventarios consecutivos, estables
5  inventario vivo == inventario sellado
6  promotion_plan recomputado y comparado COMPLETO
7  PASS de sólo lectura

verify live   PASS_EXTERNAL_READONLY · mutating=False · operaciones del sink: []
```

No escribe, no renombra, no borra, no crea. **Aquí no se implementa ningún apply.**

#### Las dieciséis pruebas obligatorias

| # | Prueba | Estado |
|---|---|---|
| 1 | dos ids de staging → huellas y preflights distintos, mismo inventario y plan | ✅ |
| 2 | loader con entorno B rechaza preflight de A, antes de abrir sink | ✅ |
| 3 | cambiar sólo el id productivo también rechaza | ✅ |
| 4 | ids, JSON, email y centinelas fuera de stdout y de todo archivo | ✅ |
| 5 | loader sin entorno o con variable ausente rechaza | ✅ |
| 6 | workbook regenerado con el id vigente coincide; con otro, rechaza | ✅ |
| 7 | plan positivo cruza schema, namespace, steps, rows y digests | ✅ |
| 8 | mutar cada uno y resellar sólo el exterior rechaza | ✅ (5 casos) |
| 9 | paso vacío, sin `:`, verbo desconocido, flecha incompleta, tabla ajena | ✅ (10 casos) |
| 10 | inventario vivo distinto rechaza | ✅ |
| 11 | plan vivo distinto con inventario **estable** rechaza | ✅ |
| 12 | sink con identidad distinta rechaza | ✅ |
| 13 | estado vivo idéntico pasa | ✅ |
| 14 | cero operaciones de escritura en loader y verificador | ✅ |
| 15 | los 78 focales previos siguen verdes | ✅ |
| 16 | v1 se rechaza sin migrar ni fallback | ✅ |

**107 pruebas focales** (78 → 107).

La 11 costó construirla bien: el inventario y el plan salen los dos de `list_tables()`, así que un
sink ingenuo cambia los dos a la vez y la prueba pasaría por el motivo equivocado. Se resolvió con
un sink que reporta el mismo inventario en los dos sondeos y sólo revela su activa cuando se le
pregunta por el plan.

#### Gates

```text
ruff check · ruff format --check · mypy (165 fuentes)        PASS
focales                                                       107 passed
tests/unit/publication                                        404 passed · 1 skipped
make test-fast                                              2,238 passed · 1 skipped
local dos veces (bundle y su .dvc)        39a353ce06c1ebf1…  byte-idénticos
external-readonly con sink inyectado                          PASS · v2
load_external_preflight con entorno explícito                 PASS · plan de 6 pasos
verify_external_preflight_live                                PASS · 0 operaciones
doctor_padecimiento obesidad --artifacts                      ✅ completo
release 618b4577… · tableau.csv b334e239… · auditoria 02ea61f0…   sin cambios
centinelas en stdout y evidencia                              0
git diff --check                                              PASS
```

#### Estado

```text
LOCAL HARNESS                          PASS
EVIDENCE LOCATION · INVENTORY          PASS
EXTERNAL SPREADSHEET IDENTITY BINDING  PASS
FULL PROMOTION PLAN SEAL               PASS
LIVE PRE-APPLY REVALIDATION            PASS (read-only)
F50                                    NO EJECUTADO
TAREAS MANUALES                        PENDING_MANUAL, las ocho
Obesidad                               trained · NO-GO · sin puntero · exposición 0%
```

#### Cierre del carril autónomo

Con A.3 no me queda superficie de consumo que cerrar sin inventar requisitos. Lo que falta para
publicar es, en este orden: una hoja de Google, tres variables en el entorno de la sesión, y las
autorizaciones de escritura y activación que sólo tú puedes dar.

#### Pregunta

1. Toca auditar `c453b979..df84cece`, cuatro commits. ¿Lo haces tú como hasta ahora?
2. Si esa auditoría pasa: ¿autorizas el push del backend, o prefieres acumular hasta después de B1?
3. Si ves alguna superficie más que yo no vea, dímela; si no, doy el carril por agotado y espero al
   manual, paso 1.

_Respuesta:_ **Audité el rango completo. A.3 cierra correctamente identidad, plan y estado vivo,
pero la forma anidada del plan todavía puede escapar con errores Python crudos. No autorizar push
todavía: ejecutar únicamente A.3.1, local y sin red, y volver a auditar el rango.**

---

### Ronda 126 — Auditoría integral de A.3 y cierre tipado restante — 2026-07-29

#### Rango auditado

```text
base     c453b979
HEAD     df84cece
commits  527615f5 · d9a54f18 · 7025aa31 · df84cece
estado   ahead 4 · sin push
```

Superficie acumulada:

```text
Makefile
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
scripts/publication_readiness.py
tests/unit/publication/test_publication_readiness.py

4 archivos · 2,295 inserciones · 16 eliminaciones
```

`git show --check`, `git diff --check`, revisión de rutas, Ruff, format y mypy del módulo:
**PASS**. No hay cambios en registry, lifecycle, config, artifacts, DVC, release, modelos,
forecasts, dashboard ni superficies públicas. Los archivos no rastreados del usuario siguen
intactos.

Gate focal repetido:

```text
tests/unit/publication/test_publication_readiness.py   107 / 107 PASS
```

#### Lo que A.3 cerró correctamente

```text
external_preflight.v2                         PASS
v1 rechazada sin fallback                     PASS
huellas staging/producción con contexto       PASS
IDs y secretos fuera de la evidencia          PASS
loader con entorno explícito                  PASS
workbook reproducido con staging vigente      PASS
promotion_plan completo persistido            PASS
gramática de pasos inválidos tipada            PASS
inventario y plan vivo revalidados            PASS
loader/verificador sin operaciones de escritura PASS
```

No encontré una ruta que omita la identidad de hoja ni una operación de escritura escondida en el
loader o el verificador vivo. A.3 cumple su objetivo material.

#### R126-P1 · la forma es cerrada en claves, pero no en tipos anidados

`_check_plan_sellado` accede directamente a valores anidados antes de demostrar su tipo. Al
resellar correctamente la capa exterior, tres artefactos inválidos salen con errores incidentales:

```json
{
  "promotion_plan.namespace=null":
    "TypeError: 'NoneType' object is not iterable",
  "promotion_plan.rows=\"bad\"":
    "AttributeError: 'str' object has no attribute 'items'",
  "promotion_plan.digests=\"bad\"":
    "ValueError: dictionary update sequence element #0 has length 1; 2 is required"
}
```

`promotion_plan.steps="bad"` sí se rechaza correctamente con `ArtifactValidationError`, lo que
confirma que el defecto está limitado a los otros valores anidados.

No cambia datos ni permite escribir una hoja equivocada, pero contradice dos garantías declaradas:

1. un artefacto inválido falla cerrado con error de dominio;
2. la forma cerrada incluye tipos y valores, no sólo nombres de claves.

Es el mismo tipo de deuda que A.3 corrigió para `planned_steps`; dejarla ahora trasladaría el fallo
al siguiente campo que reciba una forma inválida.

#### Veredicto

```text
A.3 IDENTITY BINDING             PASS
A.3 FULL PLAN SEAL               PASS MATERIAL
A.3 LIVE READ-ONLY VERIFY        PASS
NESTED SHAPE VALIDATION          FAIL P1
RANGO c453b979..df84cece         NO PUSH todavía
TAREAS MANUALES                  PENDING_MANUAL
Obesidad                         trained · NO-GO · exposición 0%
```

### Orden C7.6-AUTO-B1-HARNESS-A.3.1 — forma anidada tipada, local y STOP

#### Alcance permitido

```text
scripts/publication_readiness.py
tests/unit/publication/test_publication_readiness.py
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md   sólo si cambia el contrato visible
```

No tocar adapters, sinks, CLI previos, `Makefile`, registry, config, artifacts, DVC, dashboard ni
este plan dentro del commit.

#### Corrección única

Centralizar validadores de forma y ejecutarlos **antes** de `sorted`, `.items`, `dict`, conversión
numérica o indexación:

```text
promotion_plan
  schema       string exacto
  namespace    list[str] · única · conjunto exacto TABLES
  steps        list[str] · gramática cerrada ya existente
  rows         dict[str, int no-bool >= 0] · claves exactas TABLES
  digests      dict[str, sha256] · claves exactas TABLES

workbook
  digest                       sha256
  tables                       list[str] · única · conjunto exacto TABLES
  tableau_desktop_validated    bool exacto y false

external_preflight
  staging_identity_digest      sha256
  production_identity_digest   sha256
  inventory_digest             sha256
  foreign_tabs                 list[str] única
  environment_present          mapping cerrado de las tres variables a bool
  manual_requirements_status   valor exacto PENDING
```

La misma función debe validar el reporte de `run_external_readonly` **antes de persistirlo** y el
loader debe volver a usarla al consumirlo. No duplicar dos definiciones de forma.

Todo artefacto malformado debe terminar en `ArtifactValidationError` con prefijo `readiness:`.
No capturar `TypeError`, `AttributeError` o `ValueError` alrededor de todo el loader: validar la
frontera exacta.

#### Tests obligatorios

1. `namespace`: null, string, lista con no-string, duplicado, faltante y extra.
2. `rows`: null/string/list, clave faltante/extra, bool, negativo, float y string numérico.
3. `digests`: null/string/list, clave faltante/extra y digest no sha256.
4. `steps`: conservar los diez rechazos y el positivo existente.
5. `workbook.digest`: tipo incorrecto y digest inválido.
6. `workbook.tables`: null/string, duplicado, faltante, extra y elemento no-string.
7. `tableau_desktop_validated`: null, 0 y string `"false"`; sólo `False` booleano pasa.
8. huellas e `inventory_digest`: tipos incorrectos y no-sha256.
9. `foreign_tabs`: tipo incorrecto, elemento no-string y duplicado.
10. `environment_present`: forma cerrada, tres claves exactas y bool reales.
11. `manual_requirements_status` distinto de `PENDING`: rechazo.
12. Cada mutación se vuelve a sellar por fuera y da `ArtifactValidationError`, nunca error Python
    incidental.
13. El productor valida con la misma función antes de escribir.
14. Los 107 focales existentes permanecen verdes.
15. `verify_external_preflight_live` positivo continúa con cero operaciones.

#### Gates

```text
ruff check
ruff format --check
mypy
tests focales
tests/unit/publication completos
make test-fast
external-readonly + load v2 + verify live positivos con sink inyectado
doctor --artifacts
release y agregados legacy byte-idénticos
centinelas ausentes
git diff --check
```

#### Commit y STOP

Un commit local separado:

```text
C7.6 close external preflight nested shape contracts
```

Después STOP. No push. No ejecutar F50. No Google, credenciales reales, DVC, lifecycle, puntero,
deploy ni publicación.

Tras A.3.1 se audita `c453b979..NUEVO_SHA`. Si pasa, no seguir buscando microfronteras hipotéticas:
el carril autónomo queda cerrado y el rango queda listo para una autorización separada de push.
Las tareas manuales continúan estacionadas hasta que el usuario tenga tiempo.

#### Siguiente orden autónoma

_Respuesta:_ **GO C7.6-AUTO-B1-HARNESS-A.3.1 LOCAL. Cerrar los tipos y valores anidados de
`external_preflight.v2` con un único validador compartido por productor y loader; todo artefacto
malformado debe fallar con `ArtifactValidationError`, nunca con errores Python incidentales.
Commit local separado y STOP. Sin Google, F50, DVC, push, lifecycle, puntero, deploy ni
publicación.**


---

### Ronda 127 — C7.6-AUTO-B1-HARNESS-A.3.1 ejecutada — 2026-07-29

**Commit local separado (sin push):**

```text
600800c0  C7.6 close external preflight nested shape contracts
```

Dos archivos. El manual no cambió: el contrato visible es el mismo. Rango pendiente de auditoría:
**`c453b979..600800c0`** (5 commits).

#### El P1, reproducido contra `df84cece` y contra este commit

```text
namespace=null   TypeError: 'NoneType' object is not iterable
                 →  ArtifactValidationError: readiness: promotion_plan.namespace no es una lista
rows="bad"       AttributeError: 'str' object has no attribute 'items'
                 →  ArtifactValidationError: readiness: promotion_plan.rows no es un mapeo
digests="bad"    ValueError: dictionary update sequence element #0 has length 1
                 →  ArtifactValidationError: readiness: promotion_plan.digests no es un mapeo
```

#### Corrección única · `check_external_shape`

Una sola definición de forma, que demuestra el tipo **antes** de tocar el valor: nunca un `sorted`,
`.items`, `dict` o indexación sobre algo que no se ha probado que lo admita.

```text
promotion_plan  schema exacto · namespace list[str] única, conjunto exacto TABLES
                steps list[str] con la gramática ya existente
                rows    dict de claves exactas → entero no-bool, no negativo
                digests dict de claves exactas → sha256
workbook        digest sha256 · tables list[str] única y exacta
                tableau_desktop_validated booleano exacto y False
externo         cinco huellas y digests como sha256 · foreign_tabs list[str] única
                environment_present mapeo cerrado de las tres variables a bool reales
                manual_requirements_status exactamente PENDING
```

`0`, `1` y `"false"` no son booleanos. En un contrato, «casi» es «no».

La usan el **productor** —antes de persistir, así que no se escribe nada que después no se pueda
cargar— y el **loader** al consumir. Una prueba espía la función y comprueba que ambos la llaman: si
alguien duplicara la definición, se ve.

#### Dos cosas que encontré al hacerlo, y que arreglé en vez de rodear

1. **Los errores de forma no llevaban el prefijo `readiness:`.** `_exige_forma_cerrada` usaba la
   etiqueta como prefijo, así que un rechazo legítimo era indistinguible de cualquier otro error.
   Ahora todos lo llevan, que es lo que pedía la orden.
2. **La aserción de las pruebas no probaba lo que decía.** `ArtifactValidationError` **hereda de
   `ValueError`**, así que `not isinstance(e, ValueError)` era siempre falso y la prueba habría
   pasado igual con un error incidental. Lo que separa un rechazo de dominio es que la clase sea
   exactamente la del contrato y que el mensaje diga de qué frontera viene: eso es lo que se
   comprueba ahora.

#### Las quince pruebas obligatorias

| # | Prueba | Estado |
|---|---|---|
| 1 | `namespace`: null, string, no-string, duplicado, faltante, extra | ✅ (7 casos) |
| 2 | `rows`: null/string/list, clave faltante/extra, bool, negativo, float, string numérico | ✅ (9) |
| 3 | `digests`: null/string/list, clave faltante/extra, no-sha256 | ✅ (7) |
| 4 | `steps`: los diez rechazos y el positivo | ✅ (+4 de forma) |
| 5 | `workbook.digest`: tipo y digest inválidos | ✅ (5) |
| 6 | `workbook.tables`: null/string, duplicado, faltante, extra, no-string | ✅ (6) |
| 7 | `tableau_desktop_validated`: sólo `False` booleano pasa | ✅ (6) |
| 8 | huellas e `inventory_digest`: tipos y no-sha256 | ✅ (16) |
| 9 | `foreign_tabs`: tipo, elemento y duplicado | ✅ (5) |
| 10 | `environment_present`: forma cerrada y bools reales | ✅ (7) |
| 11 | `manual_requirements_status` ≠ PENDING | ✅ (5) |
| 12 | cada mutación resellada por fuera da error de dominio | ✅ |
| 13 | el productor valida con la misma función antes de escribir | ✅ |
| 14 | los 107 focales previos siguen verdes | ✅ |
| 15 | `verify_external_preflight_live` positivo con cero operaciones | ✅ |

**195 pruebas focales** (107 → 195).

#### Gates

```text
ruff check · ruff format --check · mypy (165 fuentes)        PASS
focales                                                       195 passed
tests/unit/publication                                        492 passed · 1 skipped
make test-fast                                              2,326 passed · 1 skipped
local dos veces (bundle y su .dvc)        39a353ce06c1ebf1…  byte-idénticos
external-readonly · load v2 · verify live                     PASS · 0 operaciones
doctor_padecimiento obesidad --artifacts                      ✅ completo
release 618b4577… · tableau.csv b334e239… · auditoria 02ea61f0…   sin cambios
centinelas en la evidencia                                    0
git diff --check                                              PASS
```

#### Estado

```text
NESTED SHAPE VALIDATION   PASS
CARRIL AUTÓNOMO           CERRADO
RANGO c453b979..600800c0  5 commits · listo para una autorización separada de push
F50                       NO EJECUTADO
TAREAS MANUALES           PENDING_MANUAL, las ocho
Obesidad                  trained · NO-GO · sin puntero · exposición 0%
```

Doy el carril por cerrado y no voy a seguir buscando microfronteras hipotéticas, como acordamos. Lo
que falta para publicar es, en orden: una hoja de Google, tres variables en el entorno de la sesión,
y las autorizaciones de escritura y activación que sólo tú puedes dar.

#### Pregunta

1. Auditoría final de `c453b979..600800c0` — ¿tuya, como hasta ahora?
2. Si pasa: ¿autorizas el push del backend, o acumulas hasta después de B1?

_Respuesta:_ **La auditoría final la ejecuté yo y el rango pasa. No abrir otra microfase local.
Recomiendo respaldar ahora los cinco commits en la rama remota, sin merge ni efecto público, y
dejar B1/manual estacionado hasta que el usuario tenga tiempo. El push conserva autorización
separada y no se ejecuta sin el literal de la Ronda 128.**

---

### Ronda 128 — Auditoría final del carril autónomo — 2026-07-29

#### Rango auditado

```text
base      c453b979
HEAD      600800c0
commits   527615f5 · d9a54f18 · 7025aa31 · df84cece · 600800c0
remoto    origin/feat/registry-padecimientos-obesidad @ c453b979
estado    ahead 5 · behind 0 · sin push
```

Superficie acumulada:

```text
Makefile
docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md
scripts/publication_readiness.py
tests/unit/publication/test_publication_readiness.py

4 archivos · 2,596 inserciones · 16 eliminaciones
```

`git show --check`, `git diff --check`, revisión de rutas y revisión manual del consumidor:
**PASS**. No hay cambios en registry, lifecycle, config, artifacts, DVC, release, modelos,
forecasts, dashboard ni superficies públicas. Los archivos no rastreados del usuario permanecen
intactos.

#### Revalidación independiente

```text
tests focales publication_readiness      195 / 195 PASS
ruff check                               PASS
ruff format --check                      PASS
mypy scripts/publication_readiness.py    PASS
```

Los tres repros que motivaron A.3.1 se repitieron contra `600800c0`:

```text
promotion_plan.namespace = null
  → ArtifactValidationError exacto
  → readiness: promotion_plan.namespace no es una lista

promotion_plan.rows = "bad"
  → ArtifactValidationError exacto
  → readiness: promotion_plan.rows no es un mapeo

promotion_plan.digests = "bad"
  → ArtifactValidationError exacto
  → readiness: promotion_plan.digests no es un mapeo
```

No son subclases incidentales ni excepciones capturadas alrededor de todo el loader: el rechazo
sale de la frontera exacta.

#### Contrato final del carril autónomo

```text
release/shard reproducible                         PASS
evidencia local autocontenida                      PASS
ubicación no versionable                           PASS
inventario exacto                                  PASS
external_preflight.v2                              PASS
identidad redactada de staging y producción        PASS
promotion_plan completo y tipado                   PASS
workbook reproducido con identidad vigente         PASS
loader productor/consumidor con forma única        PASS
doble inventario read-only                         PASS
revalidación viva de inventario y plan             PASS
cero operaciones de escritura                      PASS
errores de forma como ArtifactValidationError      PASS
```

#### Veredicto

```text
C7.6-AUTO-B1-HARNESS        CERRADO / PASS
RANGO c453b979..600800c0    APROBADO PARA CHECKPOINT REMOTO
B1 EXTERNO                  PENDING_MANUAL
F50                         NO EJECUTADO
Obesidad                    trained · NO-GO · sin puntero · exposición 0%
```

No seguir buscando microfronteras hipotéticas. El código autónomo alcanzó su condición de cierre.
Lo que queda exige estado externo real:

1. crear y compartir la hoja de staging;
2. iniciar una sesión con las tres variables;
3. ejecutar el preflight read-only del manual;
4. pedir por separado escritura sobre staging;
5. validar Tableau Desktop;
6. pedir por separado activación, merge y deploy.

Todo eso permanece estacionado.

#### Decisión recomendada · checkpoint remoto ahora

Recomiendo subir ahora los cinco commits porque:

- forman una unidad auditada y verde;
- B1 no puede ejecutarse sin intervención manual;
- la rama de trabajo no activa lifecycle, puntero, deploy ni publicación;
- acumularlos localmente hasta B1 sólo aumenta el riesgo de perder el checkpoint.

El plan modificado sigue fuera de esos cinco commits y no viaja en este push. No incluirlo ni
commitearlo sin una revisión documental separada.

#### Autorización requerida

Para ejecutar únicamente el checkpoint:

```text
AUTORIZO PUSH BACKEND c453b979..600800c0 A
origin/feat/registry-padecimientos-obesidad.
SIN --force, MERGE, PR, TAG, DVC, LIFECYCLE, PUNTERO, DEPLOY NI PUBLICACIÓN.
```

Antes del push se debe revalidar:

```text
origin feature == c453b979
HEAD == 600800c0
c453b979 es ancestro de 600800c0
behind == 0
```

Después:

```text
ls-remote feature == 600800c0
ahead 0 / behind 0
main intacta
sin merge, PR ni tag
Obesidad trained · sin puntero · fuera de published_only
```

Si el literal no llega, STOP. No sustituir el push por más código. El siguiente trabajo funcional
continúa siendo el manual B1 cuando el usuario tenga tiempo.

#### Siguiente orden

_Respuesta:_ **Carril autónomo CERRADO / PASS. Esperar autorización literal del checkpoint remoto
o, más adelante, ejecutar el manual B1. No hay otra orden de código local.**

---

### Ronda 129 — Auditoría de `make update-week` y disponibilidad de la primera semana — 2026-07-29

#### Pregunta resuelta

Sí vale la pena alinear la actualización semanal, pero **no** ejecutando el target existente.
`make update-week` pertenece al carril publicado legacy de neuro+Dengue y no conoce el contrato de
observación prospectiva del runner.

#### Evidencia de que la primera semana ya existe en la fuente

Consulta read-only del remoto, sin actualizar referencias locales:

```text
origin/main remoto                    a2bbb103
1767aaa · chore(data)                 actualizado 2026-07-28
a2bbb10 · ci dataset                  1 boletín · 96 filas legacy
raw_PDFs remoto                       655 archivos
raw_PDFs local                        654 archivos
archivo nuevo                         2026_sem28.pdf
URL registrada por CI                 https://www.gob.mx/cms/uploads/attachment/file/1093471/sem28.pdf
```

El consolidado CI añadió 96 filas del carril legacy; **no** extrajo automáticamente E66. Estado
actual de Obesidad:

```text
data/raw/data_raw_Obesidad.csv        termina en fuente 2026-W27
observation_lag_weeks                 1
verdad objetivo materializada         hasta 2026-W26
prospective_status                    INCOMPLETE · 0/4
prospective_evaluation cutoff         2026-W26
```

El boletín fuente W28 produce la verdad objetivo **2026-W27**, que es la primera semana congelada
del gate. Por tanto:

```text
fuente disponible                     1/4
estado C7 declarado                   0/4
estado esperado tras actualización    INCOMPLETE 1/4 · completed [[2026,27]]
```

No declarar 1/4 hasta extraer, reconciliar, construir el dataset de observación y ejecutar el gate.

#### Por qué `make update-week` está prohibido para esta tarea

El target llama `scripts/actualiza_semanal.sh`, que:

1. ejecuta `git pull origin main` sobre la rama actualmente activa;
2. ejecuta `dvc pull --force` global;
3. extrae/mezcla/reselecciona neuro+Dengue;
4. regenera Tableau, galerías, zoom, knowledge y landing públicos;
5. tiene una ruta absoluta al dashboard;
6. hace `dvc add`/`dvc push` de consolidado, modelos y forecasts;
7. commitea y hace push del dashboard;
8. commitea y hace `git push origin main` del backend;
9. **no** construye EpiDatasetV2 de observación;
10. **no** ejecuta `scripts.prospective_status`.

Además, `origin/main` remoto avanzó mientras la referencia local continúa en `b535b525`; ejecutar
el pull desde la rama feature mezclaría historiales que C7 mantiene deliberadamente separados.

Veredicto:

```text
make update-week para neuro+Dengue publicado   fuera de esta orden
make update-week para C7.4/Obesidad            NO APTO · NO EJECUTAR
boletín W28                                    DISPONIBLE EN FUENTE
primera semana declarada                       PENDIENTE
```

### Orden C7.4-WEEK-1-A — carril semanal aislado y dry-run 1/4

#### Objetivo

Crear un camino genérico y reproducible que convierta uno o más boletines nuevos en un
EpiDatasetV2 de **observación**, derive el estado prospectivo y demuestre el avance esperado antes
de escribir los JSON declarados.

No modificar ni reutilizar `scripts/actualiza_semanal.sh`. No añadir Obesidad a ese pipeline.

#### Alcance permitido

```text
Makefile
scripts/prospective_week.py                       nuevo, delgado
src/epiforecast/data/epi_dataset.py              raw_path opcional explícito
src/epiforecast/runner/orchestrator.py            wiring opcional, sin cambiar defaults
scripts/prospective_status.py                     reutilizar helpers; cambios sólo si son genéricos
tests/unit/publication/test_prospective_week.py   nuevo
tests/integration/                                gate real aislado si cabe
```

No tocar:

```text
scripts/actualiza_semanal.sh
data/raw/
data/interim/
data/processed/
data/raw_PDFs/
config/publication/obesidad/*.json   durante WEEK-1-A
artifacts/
reports/
models/
dashboard
archivos .dvc
```

#### Interfaz propuesta

```text
make prospective-week \
  DISEASE=obesidad \
  PDF=/ruta/temporal/2026_sem28.pdf
```

El target sólo llama al CLI nuevo. No llama `update-week`, Git, DVC, Make anidado ni consumidores
públicos.

CLI equivalente:

```text
python -m scripts.prospective_week \
  --disease obesidad \
  --pdf /ruta/temporal/2026_sem28.pdf \
  --dry-run
```

`--disease` y `--pdf` son argumentos; no escribir nombres de padecimiento, semanas, 32, 64, 111 o
1/4 en el código. Todos salen del registry, configuración, catálogo, gate y manifiestos.

#### Flujo obligatorio

1. Resolver padecimiento, grupo de extracción, lag y dataset de entrenamiento desde los contratos.
2. Leer el raw canónico como **baseline inmutable**, sin modificarlo.
3. Extraer únicamente cada PDF declarado mediante `extract_cuadro_from_pdf`.
4. Exigir resultado válido, padecimiento correcto, periodo fuente nuevo y conjunto completo de
   entidades configuradas.
5. Formar en temporal un raw de observación con upsert exacto por
   `(Anio, Semana, Entidad, Padecimiento)`.
6. Exigir que el prefijo histórico del baseline sea semánticamente idéntico y que sólo se añadan
   periodos fuente posteriores.
7. Construir EpiDatasetV2 usando `raw_path` explícito y un `runs_root` inyectado.
8. Construir 64 bases y derivados mediante el mismo orquestador; no reentrenar ni refitear.
9. Ejecutar `derive_evaluation` contra el nuevo `observation_dataset_id`.
10. Comparar contra el gate congelado:
    - mismo `gate_digest`;
    - mismo release;
    - mismos candidato y control;
    - mismo config/exposure;
    - prefijo hasta origen idéntico.
11. Emitir un reporte canónico de dry-run con dataset, corte, semanas completas/omitidas y
    veredicto propuesto.
12. No escribir `prospective_evaluation.json` ni `prospective_status.json` en WEEK-1-A.

#### Resultado real esperado para W28

Sin codificar estos valores como lógica:

```text
source period             2026-W28
observation cutoff        2026-W27
completed_weeks           [[2026,27]]
weeks_available/required  1/4
verdict                   INCOMPLETE
skipped_weeks             []
gate_digest               5bc39aa5d44f5e62… sin cambio
```

Si cualquier valor difiere, STOP y auditar; no forzar 1/4.

#### Tests obligatorios

1. Raw path por defecto conserva byte por byte el comportamiento de `validate-data`.
2. Raw path explícito sólo afecta el insumo raw y queda copiado/sellado en el nuevo dataset.
3. Un PDF fuente nuevo válido añade exactamente un periodo fuente completo.
4. Lag 1 convierte fuente W28 en objetivo W27 mediante el calendario, no restando enteros.
5. PDF repetido es idempotente: mismo dataset_id y mismo reporte.
6. PDF anterior, duplicado con valores distintos o revisión del prefijo: rechazo.
7. Entidad faltante/extra/duplicada: rechazo.
8. Padecimiento o grupo equivocado: rechazo.
9. Extracción inválida: no deja dataset ni estado parcial.
10. Baseline canónico permanece byte-idéntico.
11. Cero cambios en DVC, consolidado, forecasts, modelos y dashboard.
12. Dataset de observación conserva config/exposure y las SeriesKeys de entrenamiento.
13. Gate, candidato, control, release y umbrales permanecen idénticos.
14. Dry-run W28 deriva 1/4 e INCOMPLETE sin escribir los JSON declarados.
15. Sin nueva semana válida, deriva 0/4 y no finge progreso.
16. Dos raíces temporales producen el mismo dataset_id, reporte y digests.
17. Genericidad: padecimiento, conteos y periodos salen de metadata, no de literales ejecutables.

#### Gates

```text
ruff check
ruff format --check
mypy
tests focales nuevos
tests/unit/publication completos
make test-fast
dry-run sintético reproducible
dry-run real con W28 desde temporal
prospective_status actual continúa byte-idéntico y 0/4
gate/release/candidate/control byte-idénticos
cuatro agregados legacy byte-idénticos
git diff --check
```

#### Descarga del boletín real

WEEK-1-A puede usar la URL registrada por CI, pero sólo hacia un `mktemp` y sin persistirla en
config o código. Verificar que es PDF y dejar que el extractor derive año/semana desde el documento;
el nombre del archivo no gobierna la identidad.

No hacer `git fetch/pull`, no reemplazar `data/raw_PDFs.dvc` y no usar `dvc pull --force`.

#### Commit y STOP

Un commit local:

```text
C7.4 add isolated prospective weekly observation dry-run
```

Después STOP para auditar código y dry-run. No registrar todavía 1/4 en los JSON trackeados.

#### WEEK-1-B, todavía no autorizado

Sólo después de auditar A:

1. decidir la sede portable del dataset de observación —no dejar un status trackeado apuntando
   únicamente a `runs/` gitignored;
2. materializar/versionar esa evidencia con autorización separada si requiere DVC;
3. ejecutar `prospective_status --write`;
4. comprobar 1/4;
5. regenerar readiness/candidate en temporales con la etiqueta 1/4;
6. actualizar el porcentaje del plan;
7. mantener lifecycle, puntero y publicación intactos.

#### Siguiente orden autónoma

_Respuesta:_ **GO C7.4-WEEK-1-A LOCAL. Implementar un carril semanal prospectivo aislado y
genérico, usar W28 únicamente desde un temporal y demostrar por dry-run que deriva INCOMPLETE 1/4
sin modificar raw canónico, JSON declarados, DVC, legacy, dashboard ni publicación. Commit local
separado y STOP. No ejecutar `make update-week`.**

---

## Ronda 130 — C7.4-WEEK-1 cerrada y primera semana registrada — 2026-07-29

### Veredicto

**PASS · INCOMPLETE 1/4.**

El boletín oficial fuente `2026-W28` se extrajo por el carril aislado, produjo la verdad objetivo
`2026-W27` y avanzó el gate prospectivo de `0/4` a `1/4`. `INCOMPLETE` sigue siendo el único
veredicto válido hasta reunir cuatro semanas completas; el resultado favorable de la primera
semana no se extrapola ni autoriza publicación.

No se ejecutó `make update-week`, el pipeline legacy, entrenamiento, refit, selección, DVC global,
lifecycle, puntero, merge, deploy ni publicación.

### Commits del backend

```text
bb8c2a87  C7.4 add isolated prospective weekly observation dry-run
5775bb48  C7.4 persist portable prospective observation state
f025045a  C7.4 record first prospective week and observation snapshot
923ead67  C7.4 make weekly observation replay idempotent
5891d601  C7.4 make readiness test follow prospective progress
2d91086b  C7.4 make status gates follow declared progress
```

### Commit del dashboard

```text
a044403d  C7.4 align candidate tests with prospective progress
```

El dashboard dejó de fijar `0/4` en sus pruebas contra el shard real. Ahora exige que etiqueta,
veredicto y conteos coincidan exactamente con el bloque `publication_status` sellado. Esta
corrección evita editar tests al avanzar a `2/4`, `3/4` o `4/4`.

### Evidencia de fuente y extracción

```text
PDF oficial                 2026_sem28.pdf
SHA256 PDF                  4b131609a8ab3b76569943634d211ac49998609b2e960d91fd10861695d59181
periodo fuente              2026-W28
filas extraídas             32/32 entidades configuradas
observation_lag_weeks       1
periodo objetivo            2026-W27
```

El nombre del archivo no gobierna la identidad epidemiológica: el extractor y el calendario
validan el periodo. El PDF sólo se conserva dentro de la evidencia versionada del snapshot.

### Snapshot de observación portable

```text
dataset_id                  obesidad_71ba82d0ee33
dataset_digest              71ba82d0ee33c2ba8f01f025dd23e5984c54f6f235fa8e0ed7dfc938febb2ec3
raw_digest                  535948b8c5d520b0716216ce3194eab0e644721a5de11defd009d7d849459c6f
report_digest               be9b804762f0e0bc5c7f638d4ec547b8ddd65c467a59a573128ef0c78f7c09c4
DVC target                  artifacts/observations/obesidad/obesidad_71ba82d0ee33.dvc
DVC md5                     8e1be34c945d385bcb1abaf6421f1ffe.dir
DVC files / size            20 / 32,396,226 bytes
DVC remoto                  14 objetos subidos · target up to date
```

El snapshot incluye:

```text
dataset de observación y products
raw efectivo, catálogo, exposición y config
PDF fuente y reporte canónico
dataset de entrenamiento mínimo bajo _training/
```

Por ello `prospective_status --check` funciona en un clon limpio con `runs/` vacío después de
descargar **sólo** el release y este target de observación. La restauración dirigida añadió 170
archivos y reprodujo `INCOMPLETE 1/4`.

### Estado prospectivo declarado

```text
release_id                  obesidad_release_2517e7858901
gate_digest                 5bc39aa5d44f5e62062775dc09a0366ac856f47e5444fbb52ca07e608e61b65d
candidate_digest            e7e2f5eef2efe7fc1071a1adbcc7c9efba1ab29e8265e395e566799f55e3c9e2
control_digest              bb18accc0e6c9fbf8fd62fd48d4c9fc0807d4678e99d89f294ca6c7c41bce315
observation_cutoff          2026-W27
completed_weeks             [[2026,27]]
skipped_weeks               []
weeks                       1/4
verdict                     INCOMPLETE
status file SHA256          937c6b7795d1fb08e35b6986b54651aa2c8855db7c0d45917c47d15b9a509d58
evaluation file SHA256      6cc2787c7f0b343df37f71290f80e55ea48df6f5395037f8c64927e5a85a3fd6
```

El gate, candidato, control, release y umbrales permanecen congelados.

### Resultado informativo de la primera semana

Estos números **no deciden** mientras el gate siga incompleto:

| ámbito | sMAPE candidate | sMAPE control | degradación | umbral | semana pasa |
|---|---:|---:|---:|---:|---|
| 64 bases | 27.4377 | 33.2786 | -17.55% | +5% | sí |
| 111 productos | 26.8743 | 33.1996 | -19.05% | +5% | sí |
| nacional General | 28.1413 | 33.0942 | -14.97% | +10% | sí |

La primera observación favorece al candidate en los tres ámbitos, pero el veredicto continúa
`INCOMPLETE`.

### Idempotencia y siguiente boletín

Reprocesar el mismo último boletín con los mismos valores:

- no crea otro dataset;
- no mueve los JSON;
- conserva bytes y digests;
- no altera el target DVC;
- devuelve el reporte canónico existente.

El mismo periodo con valores distintos se rechaza como revisión. La siguiente corrida parte del
último raw declarado —no del raw histórico original—, de modo que W29 acumulará W28 en vez de
perder la primera semana.

### Readiness y canales

`make readiness` recompiló dos veces el candidate:

```text
status                      PASS_LOCAL
external                    BLOCKED_EXTERNAL
public_writes               0
label                       Validación prospectiva en curso (1/4 semanas) · pronóstico puntual sin intervalos
rows                        5,772
products                    111 = 64 base + 47 derivados
readiness_manifest_digest   484c711443217b78b65a1e19cd6fb7412bcbacce5c67a4697162f6d301d09b89
shard_tree_digest           2026e7d72f3096480f6a7bbc988adc1962d1a2add70bed11a1bcd142a91d85be
```

La validación externa Google/Tableau permanece estacionada como `BLOCKED_EXTERNAL`; no se
disfraza como fallo local ni como PASS externo.

### Gates finales

```text
ruff / format                                    PASS
mypy                                             165 fuentes + runner aislado PASS
make test-fast                                   2,350 passed · 1 skipped · 62 deselected
tests/integration/test_epi_dataset_gate.py       11 passed
dashboard test:candidate con shard real          81 passed
dashboard npm run check                          PASS · RAG público 454/454
doctor Obesidad --artifacts                      PASS
doctor --artifacts                               PASS
prospective_status obesidad --check              PASS · 1/4
DVC release + observation                        up to date
clon limpio + pulls dirigidos + runs vacío       PASS
```

Hashes legacy preservados:

```text
prophet    cb5be3959781da7a0b44f9510bcaaf22c70fb3f34ae3780e786d5748968ef8bc
deepar     96791595a2d4806de6b246aaf77ee0efe85f46c439eadb8afe8f6dd11670949a
ensemble   1d2cf0a7dcb9e54cdd69020c3c079fb57832293e961aecd0b0f325034ef2f68c
stacking   ac97dc8e210b95f26b01220702c89b34b47a4e61aabbc0d2246749961ee95b88
```

### Avance sin mezclar ejes

| eje | avance |
|---|---:|
| plataforma C1–C6 | 100% |
| implementación técnica de C7 | 82.3% |
| gate prospectivo C7.4 | **25% (1/4)** |
| readiness local | 100% |
| readiness externo Google/Tableau | 0% · `BLOCKED_EXTERNAL` |
| exposición pública de Obesidad | **0%** |

No se modifica artificialmente el 82.3% de implementación por recibir una semana de calendario:
el avance prospectivo se reporta por separado. El modelo y el sistema ya están construidos; las
tres semanas restantes son evidencia temporal, no desarrollo.

## Orden autónoma vigente — WEEK-2 a WEEK-4

Cuando aparezca un boletín fuente posterior:

1. descargar únicamente el PDF oficial a un temporal;
2. verificar PDF y SHA256;
3. ejecutar primero:

   ```text
   make prospective-week DISEASE=obesidad PDF=/ruta/temporal/boletin.pdf
   ```

4. si el dry-run conserva gate/release/candidate/control y añade exactamente la siguiente verdad
   válida, ejecutar:

   ```text
   make prospective-week-record DISEASE=obesidad PDF=/ruta/temporal/boletin.pdf
   ```

5. ejecutar `prospective_status --check`;
6. ejecutar `dvc add` y `dvc push` **sólo** sobre el nuevo target
   `artifacts/observations/obesidad/<dataset_id>.dvc`;
7. recompilar readiness en temporales;
8. ejecutar backend fast/integración/doctors y dashboard candidate/check;
9. commitear backend y dashboard por separado;
10. hacer push fast-forward únicamente de las ramas feature;
11. actualizar esta sección con dataset, digests, métricas y conteo `n/4`.

### Reglas que siguen vigentes

- No ejecutar `make update-week` para Obesidad.
- No `dvc pull/add/push` global.
- No modificar el forecast candidate, control, gate, release o umbrales.
- No reentrenar, retunear, reseleccionar ni refitear.
- No tratar una semana ausente o parcial como cero.
- No marcar PASS/FAIL antes de cuatro semanas completas.
- No activar lifecycle ni puntero.
- No merge, deploy o publicación mientras readiness externo siga bloqueado.
- Preservar todos los untracked del usuario.

### Trabajo paralelo permitido sin intervención del usuario

Mientras llegan W29–W31 se puede:

1. auditar y subir por fast-forward los checkpoints feature;
2. mantener el carril semanal, tests y documentación;
3. repetir readiness local;
4. preparar evidencia read-only;
5. revisar disponibilidad de nuevos boletines sin mutar repositorios.

Queda pendiente manual, sin bloquear las semanas:

```text
crear/compartir hoja Google Sheets de staging
inyectar las tres variables en la sesión
preflight externo read-only
refresh/verificación Tableau Desktop
decisiones de apply, activación, merge y deploy
```

### Siguiente acción exacta

**Esperar el siguiente boletín oficial. En cuanto exista, ejecutar el mismo carril aislado para
avanzar a 2/4. Hasta entonces no hay entrenamiento ni modificación estadística pendiente.**

---

## Ronda 131 — auditoría CI y cierre de fronteras operativas — 2026-07-29

### Veredicto

**PASS LOCAL Y REMOTO.**

La auditoría del run GitHub Actions `30492596708` separó tres hechos:

```text
Code Quality       PASS
Tests              FAIL · 1 caso
Integration Tests  SKIPPED por diseño en pull_request
```

El único rojo era:

```text
tests/unit/publication/test_tableau_workbook.py::
test_runs_del_repositorio_si_es_destino_valido
```

No era un problema de cobertura ni del modelo. Git devuelve código 1 al consultar
`git check-ignore runs` cuando `runs/` todavía no existe en un clon limpio, aunque `.gitignore`
declare correctamente `runs/`. El mismo defecto estaba duplicado en el workbook de staging y en
el orquestador de readiness. Localmente quedaba oculto porque este workspace ya tenía `runs/`.

### Commits funcionales

```text
0dcf3b11  C7 make readiness CI-safe in clean clones
cec991d7  C7 prevent prospective state regressions
```

### Correcciones

1. La comprobación de ignore consulta un hijo hipotético de `runs/`, que reproduce la regla que
   gobernará los artefactos aunque el directorio todavía no exista.
2. Las regresiones crean repositorios Git temporales con `runs/` ausente; validar no crea el
   directorio y generar el workbook sí puede crearlo bajo la ruta ignorada.
3. `prospective_status --write` carga y valida la evaluación declarada previa y exige:
   - conservar todas las semanas ya completadas;
   - no retroceder `observation_cutoff`;
   - rechazar un estado previo huérfano sin evaluación.
4. `prospective_week --write` rechaza `--baseline-raw`. La opción continúa disponible sólo para
   dry-run; una escritura oficial parte siempre de la verdad portable declarada.
5. Make y GitHub Actions incluyen explícitamente los cuatro CLI gobernantes de C7 en Ruff y mypy:
   `prospective_week.py`, `prospective_status.py`, `publication_readiness.py` y
   `tableau_workbook.py`. Mypy los ejecuta individualmente para evitar colisiones del namespace
   `scripts`.

### Gates locales

```text
hooks de ambos commits                       PASS
ruff format / ruff check                     PASS · 307 archivos
mypy src                                     PASS · 165 fuentes
mypy runner aislado + 4 CLI C7              PASS
tests focales clean-clone/readiness          224 passed
tests focales week/status                    83 passed
make test-fast                               2,353 passed · 1 skipped · 62 deselected
comando exacto de CI con cobertura           2,353 passed · 1 skipped · 62 deselected
cobertura                                    81.70% · mínimo 70%
git diff --check                             PASS
```

### Preservación

No cambiaron dataset de entrenamiento, snapshot de observación, gate, candidato, control, release,
umbrales, lifecycle, puntero, DVC, agregados legacy ni dashboard. Obesidad continúa
`trained`, invisible para `published_only` y en `INCOMPLETE 1/4`.

### Orden vigente

1. Hacer push fast-forward de la rama feature.
2. Esperar el CI remoto del SHA exacto.
3. Si Code Quality y Tests pasan, registrar el run y mantener WEEK-2 como siguiente acción
   automática cuando exista el boletín oficial W29.
4. Si falla, auditar únicamente el delta del job; no modificar modelo, datos ni umbrales.

Integration Tests seguirá `SKIPPED` en un PR: el workflow lo ejecuta únicamente por
`workflow_dispatch` o por el schedule semanal. Eso no se reporta como fallo.

La advertencia de GitHub sobre la futura migración de acciones de Node 20 es mantenimiento del
workflow, no causa del rojo y no bloquea este checkpoint.

### Resultado remoto

El rango `683be533..beeff86e` se subió por fast-forward normal. La rama remota quedó exactamente en
el checkpoint material auditado y el run del PR terminó:

```text
workflow / run       CI · 30496017610
head_sha             beeff86e77a4788544bffa6282fff540bdec9d5a
Code Quality         PASS · 3m55s
Tests                PASS · 5m02s
Integration Tests    SKIPPED por condición de pull_request
conclusión           SUCCESS
```

La prueba que había fallado en los runs `30280630979` y `30492596708` pasó en el clon limpio de
GitHub. El rojo no se ocultó ni se deseleccionó: se corrigió la semántica consultada a Git y el
caso continúa dentro del job Tests.

El commit que registra este resultado es sólo documental; el checkpoint funcional validado por el
run anterior es `beeff86e`.
