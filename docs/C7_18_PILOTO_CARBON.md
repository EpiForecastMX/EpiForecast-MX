# C7.18 · Piloto Carbon (`sifilis_adquirida_a51`, `configured`, 0 publicados) y guarda idempotente semanal (16-nov-2026)

> **Estado real: guía operativa y registro intermedio; NO es cierre del piloto ni alta publicada.**
> Al corte fechado del 15-nov-2026 producción sirve **85 padecimientos publicados** (4 legacy + 81
> releases del runner, `docs/C7_17_ALTA20C.md`; la lista autoritativa sale siempre de
> `registry.published_members()`). El candidato del piloto (`sifilis_adquirida_a51`, Sífilis adquirida
> `A51-A53`, `CUADRO 6`, `observation_lag_weeks: 1`) permanece **`lifecycle: configured`** (`0 / 1`
> publicado), con **0 pruebas de 2025 abiertas o consumidas** y sin fusión en `main`.

## 1. Historia ejecutada en `373ea5f6` frente a estado nominal pendiente

### 1.1 Historia técnica ya medida (rama QA `373ea5f6833473f26f80bb998ed2ecbfe1da334f`)

- **Extracción canónica doble `C / D` (`98675bb07f6eefab6e8e2e2e6e91881fed3a34cb`, sin reextracción posterior):**
  sobre el inventario sellado de `670` boletines (`ROOT_PDF_INVENTORY.json`, sha256 `b857cef9…`),
  las pasadas aisladas `C` y `D` produjeron `668 ok` y `2 excluded` (`2014_sem01.pdf` por corte
  `2013-W52` y `2016_sem20.pdf` con `keep_period=true`), `21,408` filas e igualdad byte a byte en
  `sifilis_adquirida_a51_boletin.csv` (`7fc521b717c723e4a0625c5910c1585d10461b9ee8f95ba14b943c83aa3ec0f9`).
  Las pasadas iniciales `A / B` sobre `a15725a1` (`641 ok / 2 excluded / 27 invalid`, CSV `e9121e04…`)
  se conservan íntegras sin canonizar. La reparación opt-in de los `27` boletines en `cuadro_6_sifilis_adquirida`
  (`15` con `reintento_row_tol: 4` y `12` con `bloque_sin_prev_en_capa_texto: {11: [4, 3, 4]}`) mantuvo
  exactos en valor (`Decimal`) y `NA` los `641` boletines previos (revisión `L1` de Fable: cambio
  únicamente de formato `"X.0"` → `"X"` en `Acumulado_anio_anterior`, columna no modelada).
- **Medición `QA_FINAL_373ea5f6` y dataset reconciliado (`sifilis_adquirida_a51_0cc942faddb8`):**
  `64` series base × `669` semanas (`2014-W01..2026-W42`, `42,816` filas, `111` productos; digest de
  dataset `0cc942faddb89b7fcbf83a784858b88f37d23d8b048cd1a49d113083349bfb31`; mínimo `366` frames /
  `364` observadas antes de `2021` frente a `min_train_weeks: 260` de `rolling_cv_v1`; `53 / 53`
  semanas MMWR en 2025 con `total_imputed = 0`).
  - `0 / 85,504` diferencias celda a celda contra `A51-A53` (`1` `Sem` ausente en `2016_sem50.pdf`
    Querétaro `n.e.`, señalada en fila nacional por `sem_missing_states=1`, y `384` `NA` opcionales de
    año anterior en imagen).
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
- **Revisión técnica focal de Fable sobre `373ea5f6` (`FABLE_IO_QA_373_RESET.{json,md}`):**
  tras el límite semanal previo (`ROOT_FABLE_PROVIDER_373.json`), tanto Fable como Opus completaron sus
  sesiones con `rc=0` sin `is_error` (sin `429` activo). Fable emitió dictamen
  **`APTO_TECNICO_FOCAL_IO_QA_373_CON_OBSERVACIONES_MENORES`** (partición SRP `297/275/250` líneas y
  lector QA correctos, sin hallazgos bloqueantes; observaciones menores `R1-R3` atendidas en un
  contexto externo separado y **aún no integradas** en `373ea5f6`). No es PASS científico ni autoriza
  política de 5 motores, selección, 2025, control o publicación.
- **`smoke` y `full` con los 7 motores explícitos sobre `373ea5f6`:**
  - `sifilis_adquirida_a51_benchmark_smoke_f7bc088ceb95`: **`7 / 7` motores `succeeded`** (`30`
    artefactos verificados por SHA-256).
  - `sifilis_adquirida_a51_benchmark_full_0419b6adfda7`: **`FAILED` (`EngineJobsFailed`, `rc=1`)** en
    etapa `development` (preservado íntegro): los **`5` motores estacionales terminaron `succeeded`**,
    **`ets_add_damped_log1p` falló** en entidad `01` `hombres` (`development` `2021`, predicción
    negativa `-0.0715996` primaria / `-0.071725` reintento) y **`ridge_harmonic_log1p` falló** en
    entidad `17` `mujeres` (`development` `2021`, ningún conteo utilizable).

### 1.2 Estado nominal pendiente y guardas de selección (`propuesta ≠ autorización`)

- **Ninguna etapa posterior está autorizada hoy:** tras el fallo real de `ETS` y `Ridge` en `full7_373`,
  **no** están autorizados `select`, un `full` de 5 motores (`full5`), un control estacional ni la
  apertura de `test` 2025. Las decisiones delegadas históricas de `alta20c` no se heredan.
- **Propuesta nominal y guardas de `select`:** otro contexto actualiza la propuesta nominal de política
  para `sifilis_adquirida_a51`, cuya autorización por el autor sigue **pendiente** (excluyendo 2025,
  control y publicación). En el código actual (`373ea5f6`), `select_for_series`
  (`src/epiforecast/runner/selection.py:144-147`, cubierto por `tests/unit/runner/test_selection.py:123-126`)
  **sí exige que todos los motores `incumbent` de la política estén disponibles** por serie (`C5` ya
  existente), mientras que la verificación de `policy_digest` en `orchestrator.run_selection` (`C1`
  señalado por Opus) se prepara como parche externo separado y **aún no está integrada** en `373ea5f6`.
- **Puertas pendientes de Fable:** la revisión pretest (antes de abrir 2025) y la revisión final (antes
  de integrar en `main` o publicar) siguen siendo requisitos bloqueantes pendientes.

## 2. Guarda idempotente de dataset `0444` y procedimiento semanal

El primer intento de `smoke` en `935642c6` (`jobs/smoke7_935`) falló **antes de crear `RunManifest` o
ejecutar motores** por `PermissionError` al invocar `shutil.copy2` sobre el insumo `0444` de sólo
lectura ya copiado en `runs/<dataset_id>/inputs/` por `validate_data`. La corrección integrada en
`373ea5f6` divide responsabilidades respetando el tope SRP de `<= 300` líneas por módulo:
`src/epiforecast/data/epi_dataset.py` (`297` líneas), `src/epiforecast/data/epi_dataset_guard.py`
(`275` líneas) y `src/epiforecast/data/epi_dataset_io.py` (`250` líneas).

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
4. **Remedio ante colisión o residuos (sin inventar flags CLI y preservando trazabilidad):**
   cualquier divergencia de bytes/digests, sello incompleto, symlink, artefacto de corrida
   (`run_manifest.json`, `jobs`) o temporal/sistema (`.tmp`, `.DS_Store`) falla cerrado sin `chmod`,
   sobrescritura ni borrado automático.
   - **Opción preferida:** ejecutar en un **worktree limpio nuevo** (para CLI de `scripts/disease_run.py`,
     que **no tiene** `--dataset-id` ni `--runs-root`) o pasar un **`runs_root` limpio** por API Python
     (`build_epi_dataset_v2` / `orchestrator`, expuesto como `--runs-root` en `scripts/prospective_week.py`).
   - **Si se mueve manualmente un contexto inactivo a `runs/_quarantine/`:** inventariar y registrar
     antes por SHA-256 el respaldo del directorio previo y tener presente que **las corridas previas
     (`benchmark` / `select`) que referenciaban ese `dataset_id` quedan invalidadas sin su dataset**;
     nunca autoeliminar ni sustituir silenciosamente en sitio (`R2` de Fable afina este aviso en un
     parche externo pendiente).

### 2.2 Invariantes conservados del paso semanal de producción

El carril semanal (`scripts/paso_semanal.py`) mantiene intactos sus comandos y reglas generales:

- `make semana-revisa` → `make semana-observa PDF=<boletin.pdf> SALIDA=<dir> [WRITE=1 FIRST_AVAILABLE='<ISO|evidencia>']`
  → `python -m scripts.paso_semanal consolida` → `make semana-vistas N=<boletin> FE=<checkout_fe>`.
- Todos los miembros de **`registry.published_members()`** (con `observa`/`vistas` iterando
  `registry.release_published()`; `85` totales / `81` del runner al corte del 15-nov-2026) avanzan
  juntos a la misma semana **fuente** `W`, calculando el periodo objetivo MMWR una sola vez mediante
  `epi_calendar.target_period(year, week, observation_lag_weeks)`.
- Un veredicto `FAIL` (`rc=3`), un prerrequisito ausente o una paridad rota en `revisa_consolidado`
  **detienen la publicación semanal para todos**; nunca se publica una semana parcial ni se omiten
  padecimientos previamente publicados.

## 3. Cobertura de pruebas locales sobre `373ea5f6` (software local, no CI remoto)

- **Interacción del llamador `prospective_week` (`17` pruebas en `tests/unit/publication/test_prospective_week.py`):**
  cubre la validación de extracción por boletín (`32` entidades, periodo y padecimiento con `4`
  mutaciones `fail-closed`), la fusión `merge_observation_raw` preservando prefijo histórico e
  idempotencia al repetir el último corte, el contrato de `run_week` pasando `runs_root` y `raw_path`
  explícitos y deterministas a `orchestrator.validate_data` (monkeypatched en la frontera unitaria del
  llamador), `_baseline_from_declared_state`, `FAIL → rc=3`, el rechazo de `--baseline-raw` con
  `--write` y `bulletin_provenance`.
- **Guardas sintéticas en disco y lector QA (`tests/unit/test_piloto_carbon_dataset_readonly_guard.py` + `test_piloto_carbon_alta1_qa_total_header.py`):**
  prueban sobre archivos reales temporales el árbol completo de `build_epi_dataset_v2` (incluidos
  permisos `0444`, `verified_noop`, `completed_partial` en pre-stage sin marcadores de sellado, orden
  `manifest.json` al final y rechazos `fail-closed` con mismo o distinto `dataset_id`), la reentrada
  de `orchestrator.validate_data` entre commits y el lector de `TOTAL`/encabezados (la interrupción a
  mitad de escritura `R1` se añade en parche externo separado). Suite focal en
  `planes/piloto_carbon_alta1_2026-11-15/root_checks_IO_QA_final/RESULTADO.json`: **`106 passed`**,
  `ruff check` `0`, `ruff format --check` `0` (`6` archivos) y `mypy` `0` (`184` módulos en
  `src/epiforecast/` + `7` helpers/tests).
- **Suite canónica local completa (`planes/piloto_carbon_alta1_2026-11-15/ROOT_VERIFICACION_SOFTWARE_373.json`):**
  **`2,867 passed, 491 skipped, 66 deselected` (`rc=0`)**, dentro del techo vigente `--max-skips=497`.
  Es verificación local de software en snapshot limpio; **no equivale a CI remoto ni a certificación
  científica**.

## 4. Evidencia externa de referencia

Toda la evidencia operativa del piloto vive fuera del árbol del repositorio bajo
`planes/piloto_carbon_alta1_2026-11-15/`:

- Plan y bitácora aditiva: `PLAN_CARBON_ALTA1.md`, `PROGRESS.md` y `ROOT_FEEDBACK.md`.
- Extracción canónica y QA: `extraccion_qa/canonico_98675bb0/sifilis_adquirida_a51_CANON_RAW.json` y
  `QA_FINAL_373ea5f6/QA_COMPLETA.{json,md}`.
- Revisión focal de Fable sobre `373ea5f6`:
  `fable_reset_373_20261116T144834Z/FABLE_IO_QA_373_RESET.{json,md}` (antecedente `429` en
  `ROOT_FABLE_PROVIDER_373.json`).
- Guardas y suite local: `root_checks_IO_QA_final/RESULTADO.json`,
  `root_real_guard_373/RESULTADO.json` y `ROOT_VERIFICACION_SOFTWARE_373.json`.
- Corridas y pregunta nominal pendiente: `ROOT_AUTH_SMOKE7_373.json`, `ROOT_AUTH_FULL7_373.json`,
  `jobs/smoke7_373/command_completed.json`, `jobs/full7_373/command_completed.json` y
  `ROOT_PROPUESTA_NOMINAL_SNAPSHOT.json`.
