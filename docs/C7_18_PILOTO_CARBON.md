# C7.18 · Piloto Carbon (`sifilis_adquirida_a51`, `configured`, 0 publicados) y guardas semanales / de selección (16-nov-2026)

> **Estado real al 16-nov-2026: guía operativa y registro intermedio; NO es cierre del piloto ni alta publicada.**
> Al corte fechado del 15-nov-2026 producción sirve **85 padecimientos publicados** (4 legacy + 81
> releases del runner, `docs/C7_17_ALTA20C.md`; la lista autoritativa sale siempre de
> `registry.published_members()`). El candidato del piloto (`sifilis_adquirida_a51`, Sífilis adquirida
> `A51-A53`, `CUADRO 6`, `observation_lag_weeks: 1`) se mantiene en **`lifecycle: configured`**
> (`0 / 1` publicado) y con **0 pruebas de 2025 abiertas o consumidas**. Antes de cualquier fusión en
> `main` se solicitará revisión final independiente de Fable sobre el `HEAD` exacto y verificación de CI
> remoto (ninguna se preafirma aquí).
>
> **Nota actual post-merge de PR `#74` (16-nov-2026, `TECHNICAL_ONLY_PR74`, `delta = 0` publicados):** las
> condiciones procedimentales de fusión indicadas arriba ya se cumplieron sobre el `HEAD` exacto
> `7b42e4d893588239380b32debfb2da711aa88e31` (revisión de código y docs `FABLE_FINAL_REVIEW`, CI remoto de PR
> run `43902888808` en `SUCCESS` con `2,874 passed, 496 skipped, 66 deselected` y aprobación final
> independiente `FABLE_FINAL_APPROVED_TECHNICAL_ONLY`), integrándose PR `#74` en **`main` backend
> `919159e8b0856aa3e59866715cd7063ffa070e63`** con **CI remoto de `main` run `43905851850` en `SUCCESS`**
> (`2,874 passed, 496 skipped, 66 deselected`, `integracion_tecnica_480/CI_MAIN_919_FINAL.json`). Se
> preservan `main` frontend `73079eeb` sin cambios, catálogo servido HTTP 200 byte-idéntico (`85` en el
> sitio / `81` del runner; base semanal verificada en `ROOT_WEEKLY_PATHS_ACTUAL.json`), las `97` entradas
> previas del registry (`0` artefactos antiguos modificados), los `119` artefactos científicos materializados
> con todos sus hashes verificados en el checkout principal junto con sus respaldos previos verificados, y los
> pines científicos `98675bb0` / `373ea5f6` (sin reextraer `raw` ni reescribir manifiestos por commits
> posteriores de código o documentación). La revisión `v3` del skill `padecimiento-epiforecast` (`6` archivos
> aprobados en `fable_skill_v3_delta/FABLE_SKILL_V3_DELTA.{json,md}`) quedó instalada con copia canónica y
> espejo idénticos (`diff = 0`, `quick_validate` `rc=0`, `ROOT_SKILL_INSTALACION_FINAL.json`; las sondas
> focales se acreditan por versión evaluada —`V2` `22/23` rúbricas + `3/3` contratos con `semana-11` `FAIL` en
> `fable_skill_evals_final/EVAL_RESULTADOS.{json,md}`— sin equivaler a suite nativa completa ni a `PASS`
> científico). **El piloto permanece incompleto únicamente por las puertas científicas pendientes** (sin
> declarar «todo cerrado»): `sifilis_adquirida_a51` sigue `configured` (`0 / 1` publicado, `smoke7`
> `succeeded`, `full7` `ETS`/`Ridge` `FAILED`, `0` pruebas de 2025) y la propuesta nominal `v2` de 5 motores
> continúa sin respuesta del autor.

## 1. Historia técnica ejecutada (`98675bb0` → `373ea5f6` → `480a0347`) frente a estado nominal pendiente

### 1.1 Medición científica e historial en `373ea5f6` (sin reextracción ni nuevas corridas después)

- **Extracción canónica doble `C / D` (`98675bb07f6eefab6e8e2e2e6e91881fed3a34cb`; las 8 fuentes de extracción permanecieron byte-idénticas hasta `480a0347`, y el único cambio ulterior en `config/padecimientos.yaml` es de comentario `D3` con `7 / 8` fuentes byte-idénticas e igualdad semántica `yaml.safe_load` completa probada, sin efecto en extracción y conservando intactos los pines `98675bb0`/`373ea5f6`/`480a0347`, `raw` `7fc521b7…` y los 4 digests sin reextraer ni retroeditar manifiestos):**
  sobre el inventario sellado de `670` boletines (`ROOT_PDF_INVENTORY.json`, sha256 `b857cef9…`),
  las pasadas aisladas `C` y `D` produjeron `668 ok` y `2 excluded` (`2014_sem01.pdf` por corte
  `2013-W52` y `2016_sem20.pdf` con `keep_period=true`), `21,408` filas e igualdad byte a byte en
  `sifilis_adquirida_a51_boletin.csv` (`7fc521b717c723e4a0625c5910c1585d10461b9ee8f95ba14b943c83aa3ec0f9`).
  Las pasadas iniciales `A / B` sobre `a15725a1` (`641 ok / 2 excluded / 27 invalid`, CSV `e9121e04…`)
  se conservan íntegras sin canonizar. La reparación opt-in de los `27` boletines en `cuadro_6_sifilis_adquirida`
  (`15` con `reintento_row_tol: 4` y `12` con `bloque_sin_prev_en_capa_texto: {11: [4, 3, 4]}`) mantuvo
  exactos en valor (`Decimal`) y `NA` los `641` boletines previos (revisión `L1` de Fable: cambio
  únicamente de formato `"X.0"` → `"X"` en `Acumulado_anio_anterior`, columna no modelada).
- **Medición `QA_FINAL_373ea5f6` (ejecutada en `373ea5f6833473f26f80bb998ed2ecbfe1da334f`) y dataset reconciliado (`sifilis_adquirida_a51_0cc942faddb8`):**
  `64` series base × `669` semanas (`2014-W01..2026-W42`, `42,816` filas, `111` productos; digest de
  dataset `0cc942faddb89b7fcbf83a784858b88f37d23d8b048cd1a49d113083349bfb31`; mínimo `366` frames /
  `364` observadas antes de `2021` frente a `min_train_weeks: 260` de `rolling_cv_v1`; `53 / 53`
  semanas MMWR en 2025 con `total_imputed = 0`).
  - Posiciones de `4` columnas comparadas contra `A51-A53` (`668 × 32 × 4 = 85,504` posiciones totales):
    compuestas por **`85,120` posiciones de texto extraíble** y **`384` posiciones opcionales de
    `Acumulado_anio_anterior` (`NA`) en imagen** (`12 × 32`), con **`1` celda `Casos_semana` `n.e.`
    (`NA`) en `2016_sem50.pdf` Querétaro contada aparte** (`sem_missing_states=1` en fila nacional).
    Se midieron **`0` discrepancias entre CSV canónico y PDF (`difieren = 0`), lo que NO equivale a un
    `ALL PASS` de calidad de fuente**: subsisten la errata impresa de `2015_sem40.pdf` y los `12`
    encabezados raster no extraíbles por texto.
  - Renglón `TOTAL` impreso: **`667 / 668` coinciden** directamente en el lector QA (`655` de 12
    columnas + `12` de 11 columnas `sin_prev`) y **`1` difiere por errata real de fuente** en
    `2015_sem40.pdf` (pág. 23, `Acumulado_hombres`: imprime `18` en Aguascalientes y `121` en las
    otras `31` entidades, suma `3,769` vs `1,697` impreso, mientras `Sem=63`, `M=1,151` y `prev=3,102`
    cuadran). El contrato vigente de `epi_reconcile` preserva los totales semanales observados sin
    nueva excepción, pero deja **no fiable el desglose por sexo de `2015-W39` y `2015-W40`** (declaración
    obligatoria si algún día se publicara).
  - Cortes impresos (`lag=1`): `656` verificados automáticamente en capa de texto (`0` discrepancias) +
    `12` encabezados en imagen mantenidos como `None` automatizado (sin OCR) y comprobados visualmente
    uno a uno contra `A50` (`N` vs objetivo `epi_calendar.target_period`).
- **`smoke` y `full` con los 7 motores explícitos sobre `373ea5f6`:**
  - `sifilis_adquirida_a51_benchmark_smoke_f7bc088ceb95`: **`7 / 7` motores `succeeded`** (`30`
    artefactos verificados por SHA-256).
  - `sifilis_adquirida_a51_benchmark_full_0419b6adfda7`: **`FAILED` (`EngineJobsFailed`, `rc=1`)** en
    etapa `development` (preservado íntegro): los **`5` motores estacionales terminaron `succeeded`**,
    **`ets_add_damped_log1p` falló** en entidad `01` `hombres` (`development` `2021`, predicción
    negativa `-0.0715996` primaria / `-0.071725` reintento) y **`ridge_harmonic_log1p` falló** en
    entidad `17` `mujeres` (`development` `2021`, ningún conteo utilizable).

### 1.2 Checkpoint de guardas técnicas integradas (`480a034704c45ac9c65a2e45d7dee853eabfd20a`)

Tras restablecerse el acceso de Fable y Opus (`rc=0`, `is_error=false` en
`ROOT_REVIEWS_RESET_VERIFICADOS.json`, superando el `429` semanal previo de
`ROOT_FABLE_PROVIDER_373.json`), Fable emitió sobre `373ea5f6` el dictamen
**`APTO_TECNICO_FOCAL_IO_QA_373_CON_OBSERVACIONES_MENORES`** (`FABLE_IO_QA_373_RESET.{json,md}`). A
continuación se integraron tres commits técnicos limpios sin tocar fuentes de extracción, `raw` ni
políticas:

1. **`5200777286b42402018f50861d1e771387b64b68`:** documentación del procedimiento semanal y registro
   inicial `C7.18`.
2. **`757f1e7db377277dd773d59a28f28eb4d1c3951a` (Guarda `C1` en `select`):**
   `orchestrator.run_selection` (`src/epiforecast/runner/orchestrator.py:385-391`) exige coincidencia
   exacta `bench.policy_digest == policy.digest` antes de leer métricas, complementando la guarda `C5`
   ya existente en `select_for_series` (`src/epiforecast/runner/selection.py:139-141`, cubierta por
   `tests/unit/runner/test_selection.py:123-126`) que exige todos los motores `incumbent` por serie.
   La auditoría de metadatos de los `81` releases vigentes dio **`MATCH = 81, errors = []`**
   (`ROOT_SELECT_POLICY_COMPATIBILITY_81.json`).
3. **`480a034704c45ac9c65a2e45d7dee853eabfd20a` (Observaciones `R1–R3` de Fable, dictamen `FABLE_TECNICO_480` y verificación posterior de CI remoto por root):**
   añade la prueba de recuperación tras interrupción a mitad de escritura (`R1`), precisa en
   `epi_dataset_guard.py:38-43` el requisito de inventario/respaldo SHA-256 y la invalidación de
   corridas/selecciones dependientes al mover a `runs/_quarantine/` (`R2`), y persiste por PDF
   `total_measurement_method` y `total_measurement_fallback_reason` en
   `scripts/piloto_carbon_alta1/qa_serie_extraida.py` (`R3`). **No se ha ejecutado una QA completa nueva
   con la traza `R3`**: `QA_FINAL_373ea5f6` es anterior a `480a0347` y no debe afirmarse retroactivamente
   que los `655` boletines de 12 columnas se midieron por geometría `pdfplumber`; en el contador agregado
   `total_measurement_method_counts` del resumen QA (`qa_serie_extraida.py`, esquema de filas vigente
   `piloto_carbon_alta1.qa_por_pdf.v2`), la categoría `"unspecified"` (`T1`) indica filas previas cuyo
   campo `total_measurement_method` está ausente/`None` (no es un literal persistido en la fila previa ni
   un fallo de método probado, sin inventar método retroactivo ni hacer reanudaciones mixtas), y
   `pdfplumber_exception` (`T4`) conserva el texto crudo de excepción si ocurriese un fallo de lectura.
   Fable revisó PR `#74` en `480a0347` (`fable_tecnico_PR74_480/FABLE_TECNICO_480.{json,md}`) con
   dictamen **`APTO_TECNICO_FOCAL_C1_R123_480_CON_OBSERVACIONES_MENORES`** (sin bloqueantes; observaciones
   documentales `D1–D3`), sin consultar el CI remoto en ese dictamen (sólo leyó
   `ESTADO_PREPUBLICACION.json`, donde `Code Quality` figuraba `IN_PROGRESS`). Por separado, root verificó
   posteriormente que el CI remoto de `480a0347` terminó en **`SUCCESS`** (run `43896392431`,
   `integracion_tecnica_480/CI_480_FINAL.json` y `CI_480_TESTS.log`: `Code Quality` `PASS`, `Tests` `PASS`
   con `2,874 passed, 496 skipped, 66 deselected` y cobertura `81 %`, `Integration Tests` `SKIPPED` por
   diseño, e idénticos `496` nodeids omitidos con `added_skips = []` frente al baseline `30cb7b4f` en
   `SKIP_DELTA.json`; ello certificó `480a0347`, sin preafirmar entonces un `HEAD` posterior).

### 1.3 Estado nominal pendiente (`propuesta ≠ autorización`)

- **Ninguna etapa científica posterior está autorizada al 16-nov-2026:** tras el fallo real de `ETS` y
  `Ridge` en `full7_373`, **no** están autorizados `select`, un `full` de 5 motores (`full5`), un
  control estacional ni la apertura de `test` 2025. Las delegaciones de `alta20c` no se heredan.
- **Propuesta nominal `v2` (`PROPUESTA_POLITICA_NOMINAL_v2.{json,md}`, sha256 `a4d0544d…`):** incorpora
  las precisiones del contraste con Opus y su addendum (`ROOT_REVIEWS_RESET_VERIFICADOS.json`):
  - `C2`: si el autor autorizara desarrollo con 5 motores y más adelante se autorizara 2025, la prueba
    de 2025, el `refit` y el `forecast` quedarían igualmente restringidos a esos 5 motores estacionales;
  - `C3`: coste descriptivo medido en `smoke` (`development_2024`, `root_opus_medidas_373/RESULTADO.json`),
    donde `ETS` (`29`) o `Ridge` (`23`) mejoran **en más de `5 %` (`> 5 %` estricto) sobre el mejor de
    los 5 motores estacionales** en **`38 / 64` series base**;
  - `C4`: hipótesis causal calibrada únicamente al primer fallo observado por motor, sin extrapolar a
    pliegues no ejecutados;
  - `C5`: reclamo inicial de Opus sobre subconjuntos de `incumbents` descartado por addendum al existir
    ya la guarda en `selection.py:139-141`.
  La pregunta asíncrona actualizada al autor permanece **pendiente sin respuesta**.
- **Condiciones de integración técnica de PR `#74` (`delta = 0` publicados) y puertas del piloto:** para
  fusionar PR `#74` en `main` se requiere verificación de Fable sobre el `HEAD` final exacto y CI remoto
  verde del SHA final (condición procedimental de software, sin preafirmar su emisión ni su ausencia, y sin
  constituir PASS científico ni aprobar 2025). El paso científico sobre desarrollo con 5 motores **sí
  sigue pendiente de decisión del autor**, y cualquier futura apertura de 2025 requiere además revisión
  pretest independiente de Fable y autorización nominal explícita.
  - *Nota post-merge (16-nov-2026):* las condiciones procedimentales de fusión de PR `#74` ya se
    cumplieron sobre `7b42e4d8` → `main` `919159e8` (`TECHNICAL_ONLY_PR74`, `delta = 0`, Fable final +
    CI PR `43902888808` y CI `main` `43905851850` en `SUCCESS`) y el skill `v3` quedó instalado
    (`ROOT_SKILL_INSTALACION_FINAL.json`; ver nota inicial). El piloto **permanece incompleto únicamente por
    las puertas científicas posteriores pendientes** (`0 / 1` publicado, `full7` `FAILED`, propuesta nominal
    de 5 motores sin respuesta y `0` pruebas de 2025).

## 2. Guarda idempotente de dataset `0444` y procedimiento semanal

El primer intento de `smoke` en `935642c6` (`jobs/smoke7_935`) falló **antes de crear `RunManifest` o
ejecutar motores** por `PermissionError` al invocar `shutil.copy2` sobre el insumo `0444` de sólo
lectura ya copiado en `runs/<dataset_id>/inputs/` por `validate_data`. La partición SRP integrada desde
`373ea5f6` y afinada en `480a0347` respeta el tope de `<= 300` líneas por módulo en `src/`:
`src/epiforecast/data/epi_dataset.py` (`297` líneas), `src/epiforecast/data/epi_dataset_guard.py`
(`277` líneas) y `src/epiforecast/data/epi_dataset_io.py` (`250` líneas).

### 2.1 Alcance exacto de los 6 artefactos del builder frente a `orchestrator.validate_data`

1. **`verified_noop` sobre los 6 artefactos del builder vs reescritura de derivados en `validate_data`:**
   - `preflight_dataset_context` audita `runs/<dataset_id>/` en sólo lectura: comprueba compatibilidad
     de `manifest.json` y `dataset_manifest.json` existentes (exigiendo mismos `dataset_id`,
     `disease_id`, `digests` y hashes válidos de `products.csv`/`lineage.json`, mientras permite que
     `code_commit` y `created_at` difieran entre commits) y verifica byte a byte y por SHA-256 los
     **`6` artefactos del builder** (`4` insumos en `inputs/`, `epi_dataset_v2.csv` y `manifest.json`).
   - Si los `6` artefactos ya existen idénticos, `stage_dataset_run` retorna **`verified_noop`** sin
     tocar esos `6` archivos. A continuación, cuando el llamador es `orchestrator.validate_data`
     (`src/epiforecast/runner/orchestrator.py:141-170`), el orquestador **sí recalcula y reescribe
     `products.csv`, `lineage.json` y `dataset_manifest.json`** (actualizando `code_commit` y
     `created_at`), por lo que `dataset_manifest.json` no permanece byte-idéntico entre commits ni se
     conserva el `mtime`/`inode` de los 9 archivos del directorio.
   - En `planes/piloto_carbon_alta1_2026-11-15/root_real_guard_373/RESULTADO.json`, la prueba sobre
     datos reales tras repetir `validate-data` demuestra conservación exacta de **hash, `inode`, `mtime`
     y `mode`** en los **`4` archivos de `inputs/`** (incluido `data_raw_*.csv` en modo `0444`) e
     igualdad de los **`4` digests** (`raw`, `exposure`, `config`, `dataset`, coherente con el digest
     intacto de `epi_dataset_v2.csv` y `manifest.json`).
2. **Parcial no sellado recuperable (`completed_partial`) frente a sellado incompleto (`fail-closed`):**
   - Si `runs/<dataset_id>/` contiene un subconjunto de artefactos cuyos bytes coinciden con los
     esperados y **no existe ningún marcador de sellado** (`manifest.json`, `dataset_manifest.json`,
     `products.csv`, `lineage.json`), el preflight acepta el directorio parcial y `stage_dataset_run`
     escribe de forma exclusiva únicamente las piezas faltantes (**`completed_partial`**), publicando
     siempre **`manifest.json` al final** (`O_CREAT | O_EXCL` + `fsync` + SHA-256 + `hardlink_to`).
   - Por el contrario, si **ya existe algún marcador de sellado** y falta cualquiera de los `6`
     artefactos del builder, el preflight **rechaza en seco (`fail-closed`)** el contexto sellado
     incompleto.
3. **Nota operativa (`raw_digest ≢ dataset_id`):** `dataset_id` (`<disease_id>_<dataset_digest[:12]>`)
   depende del digest de `epi_dataset_v2.csv` reconciliado. Incorporar observaciones semanales que
   cambian el **contenido modelado** produce un nuevo `dataset_id` (`runs/<nuevo_dataset_id>/`); en
   cambio, un cambio en `raw` **sólo de formato o en columnas no modeladas** (p. ej. `"X.0"` vs `"X"`
   en `Acumulado_anio_anterior`) puede conservar el **mismo `dataset_id`** con distinto `raw_digest`,
   provocando rechazo `fail-closed` si `runs/<dataset_id>/` ya existía con el otro `raw`.
4. **Remedio ante colisión o residuos (sin inventar flags CLI y preservando trazabilidad, `R2` en `480a0347`):**
   cualquier divergencia de bytes/digests, sello incompleto, symlink, artefacto de corrida
   (`run_manifest.json`, `jobs`) o temporal/sistema (`.tmp`, `.DS_Store`) falla cerrado sin `chmod`,
   sobrescritura ni borrado automático.
   - **Opción preferida:** ejecutar en un **worktree limpio nuevo** (para CLI de `scripts/disease_run.py`,
     que **no tiene** `--dataset-id` ni `--runs-root`) o pasar un **`runs_root` aislado** por API Python
     (`build_epi_dataset_v2` / `orchestrator`, expuesto como `--runs-root` en `scripts/prospective_week.py`).
   - **Si se mueve manualmente un contexto inactivo a `runs/_quarantine/`:** hacerlo sólo sin procesos
     activos y tras inventariar y respaldar por SHA-256 el contexto previo, advirtiendo que **las
     corridas y selecciones dependientes de ese `dataset_id` pierden su contexto y quedan invalidadas**
     (`epi_dataset_guard.py:38-43`); nunca autoeliminar ni sustituir silenciosamente en sitio.

### 2.2 Invariantes conservados del paso semanal de producción

El paso semanal mantiene intactos sus comandos por carril y su regla global de paridad:

- `scripts/paso_semanal.py` (`make semana-revisa` → `make semana-observa PDF=<boletin.pdf> SALIDA=<dir> [WRITE=1 FIRST_AVAILABLE='<ISO|evidencia>']`
  → `python -m scripts.paso_semanal consolida` → `make semana-vistas N=<boletin> FE=<checkout_fe>`)
  ejecuta **únicamente `registry.release_published()`** (`81` releases del runner al corte del
  15-nov-2026, calculando cada periodo objetivo MMWR una sola vez mediante
  `epi_calendar.target_period(year, week, observation_lag_weeks)`), mientras el productor v5 avanza los
  `4` padecimientos legacy.
- La regla global de publicación (`revisa_consolidado`) exige paridad en la misma semana **fuente** `W`
  para todos los miembros de **`registry.published_members()`** (`85` al corte del 15-nov-2026).
- Un veredicto `FAIL` (`rc=3`), un prerrequisito ausente o una paridad rota en `revisa_consolidado`
  **detienen la publicación semanal para todos**; nunca se publica una semana parcial ni se omiten
  padecimientos previamente publicados.

## 3. Cobertura de pruebas locales verificada sobre `480a0347` (software local, no CI remoto)

- **Interacción del llamador `prospective_week` (`17` pruebas en `tests/unit/publication/test_prospective_week.py`):**
  cubre la validación de extracción por boletín (`32` entidades, periodo y padecimiento con `4`
  mutaciones `fail-closed`), la fusión `merge_observation_raw` preservando prefijo histórico e
  idempotencia al repetir el último corte, el contrato de `run_week` pasando `runs_root` y `raw_path`
  explícitos y deterministas a `orchestrator.validate_data` (monkeypatched en la frontera unitaria del
  llamador), `_baseline_from_declared_state`, `FAIL → rc=3`, el rechazo de `--baseline-raw` con
  `--write` y `bulletin_provenance`.
- **Guardas de dataset (`R1–R2`), selección (`C1`) y traza QA (`R3`) en `480a0347`:**
  - `tests/unit/runner/test_select_policy_digest_guard.py` + suite de `runner` en `757f1e7d`: `76 passed`
    y calidad en `0`, más compatibilidad `81 / 81` `MATCH` en `ROOT_SELECT_POLICY_COMPATIBILITY_81.json`.
  - `tests/unit/test_piloto_carbon_dataset_readonly_guard.py` (incluyendo fallo inyectado a mitad de
    escritura y recuperación `completed_partial` con `manifest.json` al final, `R1`, y aviso `R2`) +
    `tests/unit/test_piloto_carbon_qa_total_trace.py` (`R3`) en
    `planes/piloto_carbon_alta1_2026-11-15/root_checks_R123/RESULTADO.json`: **`118 passed` en `46.79 s`**,
    `ruff check` `0`, `ruff format --check` `0` y `mypy` `0` (`184` módulos en `src/epiforecast/` + `9`
    helpers/tests).
- **Suite canónica local completa sobre `480a0347` (`planes/piloto_carbon_alta1_2026-11-15/jobs/unit_ci_480a0347/command_completed.json`):**
  **`2,879 passed, 491 skipped, 66 deselected` (`rc=0`, `204.80 s`, `stdout` `d0583fde…`)**, dentro del
  techo vigente `--max-skips=497` (antecedente en `373ea5f6`: `2,867 passed, 491 skipped, 66 deselected`
  en `ROOT_VERIFICACION_SOFTWARE_373.json`). Es verificación **local** de software; **no equivale a CI
  remoto ni a certificación científica**.

## 4. Evidencia externa de referencia

Toda la evidencia operativa del piloto vive fuera del árbol del repositorio bajo
`planes/piloto_carbon_alta1_2026-11-15/`:

- Plan, bitácora y propuesta nominal `v2`: `PLAN_CARBON_ALTA1.md`, `PROGRESS.md`, `ROOT_FEEDBACK.md` y
  `carbon_propuesta_politica_v2/PROPUESTA_POLITICA_NOMINAL_v2.{json,md}` (`a4d0544d…`).
- Extracción canónica y QA (`373ea5f6`): `extraccion_qa/canonico_98675bb0/sifilis_adquirida_a51_CANON_RAW.json`
  y `QA_FINAL_373ea5f6/QA_COMPLETA.{json,md}`.
- Revisiones independientes verificadas: `ROOT_REVIEWS_RESET_VERIFICADOS.json`,
  `fable_reset_373_20261116T144834Z/FABLE_IO_QA_373_RESET.{json,md}` y
  `fable_tecnico_PR74_480/FABLE_TECNICO_480.{json,md}`.
- Guardas, paridad de extracción, compatibilidad y suites locales (`373ea5f6` y `480a0347`):
  `ROOT_EXTRACTION_PARITY_480.json`, `root_real_guard_373/RESULTADO.json`,
  `ROOT_SELECT_POLICY_COMPATIBILITY_81.json`, `root_checks_R123/RESULTADO.json`,
  `ROOT_VERIFICACION_SOFTWARE_373.json`, `ROOT_VERIFICACION_SOFTWARE_480.json` y
  `jobs/unit_ci_480a0347/command_completed.json`.
- Corridas y mediciones descriptivas: `ROOT_AUTH_SMOKE7_373.json`, `ROOT_AUTH_FULL7_373.json`,
  `jobs/smoke7_373/command_completed.json`, `jobs/full7_373/command_completed.json` y
  `root_opus_medidas_373/RESULTADO.json`.
- Seguimiento final Fable, integración técnica PR `#74`, CI, instalación del skill `v3` y preservación post-merge (`7b42e4d8` → `main` `919159e8`):
  `fable_final_PR74_7b42/FABLE_FINAL_REVIEW.{json,md}`,
  `fable_final_PR74_7b42_CI/FABLE_FINAL_APPROVED.{json,md}`,
  `integracion_tecnica_480/{CI_480_FINAL,CI_7b42_FINAL,PR74_MERGED,CI_MAIN_919_FINAL}.json`,
  `root_served_after_PR74/RESULTADO.json`, `ROOT_WEEKLY_PATHS_ACTUAL.json`,
  `ROOT_MAIN_PRESERVACION_PREVIOS.json`, `ROOT_PERSISTENCIA_CIENTIFICA_MAIN.json`,
  `materializacion_principal_373/MANIFEST.json`, `backup_final_worktrees_7b42/MANIFEST.json`,
  `RETIREMENT_OLD_PILOT_COMPLETED.json`, `fable_skill_evals_final/EVAL_RESULTADOS.{json,md}`,
  `fable_skill_v3_delta/FABLE_SKILL_V3_DELTA.{json,md}`, `ROOT_SKILL_INSTALACION_FINAL.json` y
  `opus_memory_current_audit/AUDITORIA_MEMORIAS.{json,md}`.
