# C7 — Plan operativo de publicación de Obesidad

> **Estado autoritativo (2026-07-26): C7.2-A, C7.2-B Y C7.2-C1 CERRADAS.** C7.2-A está respaldada
> en Git remoto `827de945`. C7.2-B está en `c6a2e713` y el cierre documental de C1 en `be143338`;
> la rama está `ahead 3` antes de commitear esta auditoría. El target DVC está sincronizado y fue
> restaurado desde S3 con caché vacía. El rango Git fue auditado: contiene puntero, código/tests,
> registry y plan, pero no el bundle ni targets legacy. No hubo Git push de C7.2-B, deploy ni
> publicación.
>
> **Orden vigente:** congelar esta auditoría en un último commit doc-only, comprobar `ahead 4` y
> solicitar autorización explícita para C7.2-C2: push Git fast-forward de
> `827de945..HEAD`. Ese push no autoriza C7.3, lifecycle, canales, frontend o publicación. La Ronda
> 29 contiene las órdenes autoritativas.
> Obesidad continúa `trained`, NO-GO e invisible para `published_only`.
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
| Gate prospectivo | 4 semanas epidemiológicas consecutivas, sin retuning |
| Activación | lifecycle + puntero de release público; ambos deben coincidir |
| Rollback | restaurar puntero y versiones públicas anteriores; no borrar el bundle |

No se publicará como “preliminar” para saltarse el gate prospectivo. Una excepción requeriría una
decisión formal distinta y una modificación explícita de este plan.

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
ejecuta antes de publicar, pero eso no lo convierte automáticamente en un canal habilitado.

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
    C --> G["C7.4<br/>Forecast y control congelados"]
    G --> H{"4 semanas<br/>prospectivas PASS"}
    F1 --> I["C7.5<br/>Gates de consumidores"]
    F2 --> I
    F3 --> I
    F4 --> I
    H --> I
    I --> J["C7.6<br/>Paquete de aprobación"]
    J --> K{"OK explícito<br/>por acción externa"}
    K --> L["Subir bundle oscuro"]
    L --> M["Activar puntero + lifecycle"]
    M --> N["Deploy coordinado"]
    N --> O["Smoke público + vigilancia"]
    O --> P{"PASS"}
    P -->|sí| Q["Release publicado"]
    P -->|no| R["Rollback de puntero y deploy"]
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

Esperar cuatro semanas objetivo consecutivas con boletín utilizable:

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

- **PASS:** habilita C7.5.
- **FAIL:** Obesidad permanece `trained`; no hay retuning automático. Abrir un plan de diagnóstico
  separado.
- **INCOMPLETE:** faltan semanas válidas; C7 espera.

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
| Calidad | aceptación 2025 PASS + prospectivo C7.4 PASS |
| Point-only | etiqueta consistente; ninguna banda inventada |
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
- resultado prospectivo;
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

Solo se ejecuta con C7.1–C7.6 PASS y las autorizaciones anteriores.

Orden:

1. subir el bundle DVC como artefacto oscuro y verificar restauración remota;
2. integrar el código genérico mientras Obesidad sigue `trained`;
3. guardar los punteros y versiones públicas actuales para rollback;
4. activar el release público y cambiar Obesidad a `published` en el mismo paquete de release;
5. generar los cuatro outputs públicos desde el release activo;
6. desplegar frontend/EpiBot y promover Tableau;
7. ejecutar smoke público;
8. observar errores, integridad y consistencia durante la ventana acordada;
9. declarar C7 PASS o ejecutar rollback.

El gate de activación exige:

- `published_members(channel)` incluye Obesidad exactamente para los cuatro canales;
- F50 sigue ausente;
- el puntero activo resuelve al mismo `release_id` declarado por el registry;
- el bundle se restaura desde remoto;
- las cifras públicas muestreadas coinciden con el forecast sellado;
- no existe pérdida ni cambio numérico en los cuatro padecimientos previos;
- las superficies declaran point-only;
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
| 6 | C7.4 prospective gate | ninguno |
| 7 | C7.5 gates y paquete de release | ninguno |
| 8 | C7.7 flip/puntero, tras autorización | publicación |

Backend y frontend permanecen en commits/repos separados. Los outputs materiales y sus punteros no
se mezclan con cambios de lógica.

---

## 14. Criterio final de éxito

C7 termina únicamente cuando:

- el doctor valida el backend real y no los PKL preliminares;
- el release se restaura desde Git + DVC en un entorno limpio;
- 64 modelos y 111 productos conservan identidad, digests y reconciliación;
- cuatro semanas prospectivas pasan la regla congelada;
- Reports, Tableau, web y EpiBot consumen manifests/shards genéricos;
- la UI declara honestamente que el forecast es puntual;
- Obesidad aparece solo en los cuatro canales autorizados;
- galería, weekly validation y prospective validation públicos siguen diferidos;
- F50 continúa oculta;
- legacy permanece byte-idéntico;
- existe rollback probado por puntero/versiones;
- todas las promociones externas tienen aprobación registrada.

Hasta entonces:

```text
Obesidad = trained · NO-GO · no publicada
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
