# C7.18 · Piloto Carbon (`sifilis_adquirida_a51`, `configured`, 0 publicados), desarrollo `policy5` (`8bbb72da`) y guardas semanales / de selección (16-nov-2026)

## Checkpoint A51 (`A51-A53`) — Corte post-test 16 nov 2026 (antes de decisión de control)

> **Vigencia (`A51` solamente):** Las referencias inferiores a `0 tests`, cierre pretest o prueba pendiente son **historia pretest exclusiva de `A51`**, superada por este resultado (no generalizar a otros IDs).

- **Corrida única:** Sífilis adquirida `A51` (`configured` `0/1`, sitio `85`/runner `81`), `test_2025` **CONSUMIDA y RECHAZADA** (run `sifilis_adquirida_a51_benchmark_test_73490ea8b2b5_749316ac335e`, fuente `8bbb72da8faffbdf0319f6c721618a3989f87af7`, dataset `sifilis_adquirida_a51_0cc942faddb8`).
- **Resultados:** Nacional `25.4877` vs `19.9564` (`+27.7169%` > límite `10%`). El portafolio mejora frente al control `12.9918%` en `64` bases (`peor_pct` `-12.991767%`) y `4.8410%` en `111` productos (`peor_pct` `-4.841037%`). `MASE > 1` del control en `64/64` bases.
- **Auditoría `fable` y `D1`:** Recomputación CSV con diferencia `0` (`47` archivos, `24` SHA). Cinco motores cubrieron con pronósticos las `53` semanas MMWR de `test_2025`; `horizon=52` en `job_context` es contexto y **no truncó la evaluación** (el forecast futuro de 52 semanas sigue sin ejecutarse). `D1` retrospectiva no ciega (total 2025 visible antes). Riesgos: sexo, errata `2015`, imputados `2016`, `12` headers raster.
- **Gobernanza y evidencia:** Autorización sólo para test, sin autorizaciones heredadas (`fable` no autoriza control). Nueva pregunta nominal de ROOT sobre `seasonal_naive_lag52` **sin respuesta al corte**; prohibidos `refit`, `forecast`, `control`, publicación, `retest` 2025, reselección, cambio de criterios y exportar baselines privados. Evidencia: `planes/piloto_carbon_alta1_2026-11-15/test2025_autorizado_20261116/RESULTADO_TEST2025.json` y `planes/piloto_carbon_alta1_2026-11-15/test2025_autorizado_20261116/fable_posttest/FABLE_POSTTEST.json` (`.md`).


> **Estado real al 16-nov-2026: guía operativa y registro intermedio; NO es cierre del piloto, aceptación ni alta publicada.**
> Al corte fechado del 15-nov-2026 producción sirve **85 padecimientos publicados** (4 legacy + 81
> releases del runner, `docs/C7_17_ALTA20C.md`; la lista autoritativa sale siempre de
> `registry.published_members()`). El candidato del piloto (`sifilis_adquirida_a51`, Sífilis adquirida
> `A51-A53`, `CUADRO 6`, `observation_lag_weeks: 1`) se mantiene en **`lifecycle: configured`**
> (`0 / 1` publicado) y con **0 pruebas de 2025 abiertas o consumidas**. Antes de cualquier fusión en
> `main` se solicitará revisión final independiente de Fable sobre el `HEAD` exacto y verificación de CI
> remoto (ninguna se preafirma aquí).
>
> **Nota post-merge de PR `#74` / `#75` y desarrollo autorizado `policy5` en `8bbb72da` (16-nov-2026, `delta = 0` publicados):**
> las condiciones procedimentales de fusión técnica se cumplieron primero sobre el `HEAD` exacto
> `7b42e4d893588239380b32debfb2da711aa88e31` (revisión de código y docs `FABLE_FINAL_REVIEW`, CI remoto de PR
> run `43902888808` en `SUCCESS` con `2,874 passed, 496 skipped, 66 deselected` y aprobación final
> independiente `FABLE_FINAL_APPROVED_TECHNICAL_ONLY`), integrándose PR `#74` (`TECHNICAL_ONLY_PR74`) en
> **`main` backend `919159e8b0856aa3e59866715cd7063ffa070e63`** con **CI remoto de `main` run `43905851850`
> en `SUCCESS`** (`2,874 passed, 496 skipped, 66 deselected`, `integracion_tecnica_480/CI_MAIN_919_FINAL.json`),
> seguida de PR `#75` documental en **`main` backend `d46effa6e754ef5a98abd70c52968a8d3ac664db`** con **CI
> remoto de `main` run `43917609205` en `SUCCESS`** (`integracion_docs_postmerge/CI_MAIN_D46_FINAL.json`). Se
> preservan `main` frontend `73079eeb` sin cambios, catálogo servido HTTP 200 byte-idéntico (`85` en el
> sitio / `81` del runner; base semanal verificada en `ROOT_WEEKLY_PATHS_ACTUAL.json`), las `97` entradas
> previas del registry (`0` artefactos antiguos modificados), los `119` artefactos científicos materializados
> con todos sus hashes verificados en el checkout principal junto con sus respaldos previos verificados, y los
> pines científicos `98675bb0` / `373ea5f6` (no requirieron repetir la extracción ni reescribir manifiestos por
> los cambios de guardas, comentarios o documentación ya integrados —ni por avances de `HEAD` o HTML web— que no
> alteraron fuentes efectivas ni `raw`; cambios materiales del extractor, configuración fuente o
> `source_exclusions` que afecten `raw` sí requieren doble extracción y QA nuevas, sin reabrir pruebas
> consumidas). La revisión `v3` del skill `padecimiento-epiforecast` (`6` archivos aprobados en
> `fable_skill_v3_delta/FABLE_SKILL_V3_DELTA.{json,md}`, `ROOT_SKILL_INSTALACION_FINAL.json`) y el ajuste
> documental ulterior de `1` línea sobre la fuente del rezago en `references/paso_semanal.md` (`75886c87…`,
> `ROOT_SKILL_INSTALACION_LAG.json`, revisión de lectura `FABLE_LAG_SOURCE.json`) quedaron instalados con copia
> canónica y espejo idénticos (`diff = 0`, `quick_validate` `rc=0`; las sondas focales se acreditan por
> versión evaluada —`V2` `22/23` rúbricas + `3/3` contratos con `semana-11` `FAIL` conservado sin retro-`PASS`
> en `fable_skill_evals_final/EVAL_RESULTADOS.{json,md}`—). Por separado, en
> `fable_eval_weekly_v3_final/EVAL_SEMANAL_V3.{json,md}` Fable calificó una corrida nueva de `semana-siguiente`
> con `v3` en `12/12` `PASS` y recalificó aparte `A07` sobre la `alta.md` original contra el grader `07` de `v3`
> en `1/1` `PASS` (mediciones distintas sin afirmar un `23/23` único, sin convertir en `PASS` el `S11` `FAIL`
> original, ni equivaler a la suite nativa completa o a `PASS` científico). Posteriormente, el autor respondió
> directamente **`«si autorizo»`** (`carbon_policy5_authorized/AUTORIZACION_AUTOR.json`, sha256 `da3b72f4…`, sin
> delegación de `alta20c`) a la propuesta nominal `v2` (`a4d0544d…`), autorizando **únicamente el desarrollo
> `smoke5`, `full5` y `select5`** bajo `rolling_cv_baja_incidencia_v1` (`6d2350be…`). Sobre el commit fuente
> científico `8bbb72da8faffbdf0319f6c721618a3989f87af7` (`1` línea en `config/padecimientos.yaml:3172` sobre
> `d46effa6`, mantenido quieto en su worktree científico; dictamen Fable
> `FUENTE_Y_ALCANCE_CONFORMES_CON_1_ERROR_REAL_NO_CIENTIFICO` y corrección técnica separada de `E1` en
> `tests/unit/test_piloto_carbon_alta1_validator.py:227`, ya medida `1 failed` antes en `jobs/test_E1_before_8bbb` y
> `1 passed` después en `jobs/test_E1_after_policy5`, `ccf5fddd…`, ya con commit técnico E1 `75152360b105af196079d9e954d22143e3a429cf` en `worktrees/policy5_integration`),
> los **`4` digests autorizados** coincidieron con `sifilis_adquirida_a51_0cc942faddb8`, se respaldaron `102` archivos y
> se materializaron los `91` archivos nuevos de corrida en el checkout principal sin sobrescribir contextos previos, y
> terminaron **`succeeded`** `smoke5` (`b2b6e5bc21ba`), `full5` (`57698d37e134`) y `select5`
> (`57698d37e134_b41ca5664941`, **`64` selecciones**, estado `DEVELOPMENT_COMPLETED_NOT_ACCEPTANCE` — **no es aceptación
> ni `PASS` científico**). Fable completó la revisión pretest independiente
> (`fable_pretest_policy5_8bbb/FABLE_PRETEST_POLICY5.{json,md}`, `a3f61df2…` / `3232dd9e…`) con veredicto
> **`CONDICIONAL`** (`0` defectos técnicos; riesgo medido en desarrollo `2021–2024`: nacional General **`+50.05 %` peor
> que el control** `51.97` vs `34.63`, límite `10 %`, fuera en `3/4` pliegues, con bases `−9.98 %` y `111` productos
> `−9.19 %`; divulgación `D1` sobre visibilidad del nivel anual público de `2025` en `QA_COMPLETA.md` §3 y divulgaciones
> `K6` previas a cualquier publicación). **Siguen NO autorizados `test` de 2025, `refit`, `forecast`, control estacional
> de respaldo y publicación**; el piloto sigue en `0 / 1` publicado (`configured`, `0` pruebas de 2025), y la **nueva
> pregunta nominal al autor para abrir 2025** (`carbon_policy5_authorized/ROOT_TEST2025_QUESTION_SENT.json`, propuesta
> `485075c5…`) permanece **`PENDING` sin respuesta** (distinta de `«si autorizo»`).

## 1. Historia técnica y científica ejecutada (`98675bb0` → `373ea5f6` → `480a0347` → `d46effa6` → `8bbb72da`) y compuertas pendientes

### 1.1 Medición científica e instantánea histórica en `373ea5f6`

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

### 1.3 Antecedente de propuesta nominal `v2` (`a4d0544d…`) e integración técnica PR `#74` / `#75` (`d46effa6`)

- **Detención gobernada previa tras `full7_373` (`propuesta ≠ autorización`):** tras el fallo real de `ETS` y
  `Ridge` en `full7_373`, se detuvo el flujo científico sin abrir `select`, `full5`, control estacional ni
  `test` 2025 (las delegaciones de `alta20c` no se heredan), formulándose la propuesta nominal `v2`
  (`PROPUESTA_POLITICA_NOMINAL_v2.{json,md}`, sha256 `a4d0544dc50843f1631cc78e75ad71124600041d2a165008db3aa9522cfcdb21`)
  con las precisiones del contraste con Opus y su addendum (`ROOT_REVIEWS_RESET_VERIFICADOS.json`):
  - `C2`: si el autor autorizaba desarrollo con 5 motores y más adelante se autorizara 2025, la prueba
    de 2025, el `refit` y el `forecast` quedarían igualmente restringidos a esos 5 motores estacionales;
  - `C3`: coste descriptivo medido en `smoke` (`development_2024`, `root_opus_medidas_373/RESULTADO.json`),
    donde `ETS` (`29`) o `Ridge` (`23`) mejoran **en más de `5 %` (`> 5 %` estricto) sobre el mejor de
    los 5 motores estacionales** en **`38 / 64` series base** (un único pliegue; no anticipa los 4 pliegues
    ni 2025);
  - `C4`: hipótesis causal calibrada únicamente al primer fallo observado por motor en `development_2021`
    (`ETS` en `01` hombres, base `1/64`; `Ridge` en `17` mujeres, base `34/64`), sin extrapolar a pliegues
    no ejecutados (`2022` y `2023`) ni inferir baja incidencia nacional (`9,523 / 14,368 / 17,854 / 17,206`
    casos anuales en `2021–2024`);
  - `C5`: reclamo inicial de Opus sobre subconjuntos de `incumbents` descartado por addendum al existir
    ya la guarda en `selection.py`.
- **Integración técnica PR `#74` (`919159e8`) y documental PR `#75` (`d46effa6`, `delta = 0` publicados):**
  cumplidos el dictamen final independiente de Fable (`FABLE_FINAL_APPROVED_TECHNICAL_ONLY`) y el CI remoto
  del SHA exacto `7b42e4d8` (`43902888808` `SUCCESS`), se fusionaron PR `#74` en `main` `919159e8` (CI
  `43905851850` `SUCCESS`) y PR `#75` en `main` `d46effa6` (`5ed4441c…`, `4` archivos `.md`, CI `43917609205`
  `SUCCESS`, `ROOT_FINAL_TECHNICAL_PROOF.json`), dejando ambos checkouts principales limpios y sincronizados
  mientras se esperaba la respuesta del autor a la propuesta `v2`.

### 1.4 Autorización acotada («si autorizo»), fuente científica `8bbb72da`, desarrollo `smoke5` / `full5` / `select5` y compuerta pretest de 2025

- **Respuesta directa del autor y alcance estricto (`AUTORIZACION_AUTOR.json`, sha256 `da3b72f492d63f69d2ba23b4ae8766da4d557aaa3fb099e176a2ec56cc90a977`):**
  el autor respondió literalmente **`«si autorizo»`** (`recorded_at = 2026-11-16T18:09:29.652123+00:00`,
  autoridad directa sin delegación de `alta20c`) sobre la propuesta `v2` (`a4d0544d…`) y la política
  `config/evaluation/rolling_cv_baja_incidencia_v1.yaml` (`6d2350be2f1b7735ad5b6350fe4360faf63c7afda8b7c4a2c973c8e2f593dbad`),
  autorizando **únicamente las tres etapas de desarrollo `smoke5`, `full5` y `select5`**.
  - **Exclusiones expresas (NO autorizadas por esta respuesta):** **`test` de 2025 (`test2025`), `refit`,
    `forecast` (excluido por `C2` de la propuesta y precisado en `O3` de Fable), control estacional de
    respaldo y publicación.**
  - **Preflight independiente de Opus (`OPUS_POLICY5_PREFLIGHT.{json,md}`, `5935fcd4…` / `796a0730…`, verificado en `ROOT_PREFLIGHT_VERIFICADO.json` `fadb588c…`):**
    `blocking_findings = 0`, contrato de política recomputado igual (`seed = 20260724`, `min_train_weeks = 260`,
    pliegues `2021..2024`, test `2025` de `53` semanas, banda `5 %`, gate `5/5/10` contra
    `seasonal_naive_lag52`, `5` incumbents y `0` challengers) y sondeo de fuente SINAVE sin efecto sobre `raw`.
- **Commit fuente científico `8bbb72da8faffbdf0319f6c721618a3989f87af7` (mantenido fijo en su worktree científico) y dictamen `FABLE_POLICY5_SOURCE`:**
  - Creado sobre padre único `d46effa6e754ef5a98abd70c52968a8d3ac664db` (`tree = 2bd08302bcf89717cc94db2b78385655e15ff046`),
    con diff exacto de **`1` línea** en `config/padecimientos.yaml:3172` (`selection_policy: rolling_cv_v1` →
    `rolling_cv_baja_incidencia_v1`, sha256 `5db1f16a828e40673b0c995de1f606f6718047f2e28914df066faf774ed7aaf5`),
    preservando las otras `97` entradas byte a byte, manteniendo `sifilis_adquirida_a51` invisible
    (`lifecycle: configured`, `channels: []`, `training_engines: []`, `eligible_engines: []`,
    `gallery_enabled: false`) y conservando `profile: aguda_conteos` (`O5`: precedente Asma; el nombre de la
    política no describe epidemiológicamente a la sífilis; `O2`: quien autoriza es el autor y el commit sólo
    aplica, sin reescribir `8bbb72da` por ser el `code_commit` de las corridas).
  - En `fable_policy5_source_8bbb/FABLE_POLICY5_SOURCE.{json,md}` (`2026-11-16T18:31:03Z`), Fable emitió el
    veredicto **`FUENTE_Y_ALCANCE_CONFORMES_CON_1_ERROR_REAL_NO_CIENTIFICO`** (no es revisión pretest de 2025,
    aceptación ni `PASS`): `0` bloqueantes para `smoke5`/`full5`/`select5` y **`1` error real no científico
    `E1`** en `tests/unit/test_piloto_carbon_alta1_validator.py:227` (`spec.selection_policy == "rolling_cv_v1"`),
    corregido a `"rolling_cv_baja_incidencia_v1"` en `worktrees/policy5_integration` (padre `8bbb72da`, ya
    medido `1 failed` antes en `jobs/test_E1_before_8bbb/command_completed.json` `rc=1` y `1 passed` después en
    `jobs/test_E1_after_policy5/command_completed.json` `rc=0`, `stdout` `ccf5fddd…`, ya con commit técnico E1 `75152360b105af196079d9e954d22143e3a429cf`) sin mover ni
    enmendar `8bbb72da`.
- **Resultados reales de desarrollo verificados sobre `8bbb72da` (`ROOT_RESULTADOS_SELECT5_VERIFICADOS.json`, estado `DEVELOPMENT_COMPLETED_NOT_ACCEPTANCE`):**
  - **Reproducción exacta del dataset (`sifilis_adquirida_a51_0cc942faddb8`) y preservación sin sobrescritura:** los
    **`4` digests autorizados** coincidieron bit a bit (`raw: 7fc521b717c723e4a0625c5910c1585d10461b9ee8f95ba14b943c83aa3ec0f9`,
    `exposure: d1453197abfc18b52955fbc7e86c4750e4f1ec9f1c9987a02a293139d70be3e2`,
    `config: d545a3d5e99e0acab68d3e06ba2238d0a7ad19ddd74a9424356332c60c694375`,
    `dataset: 0cc942faddb89b7fcbf83a784858b88f37d23d8b048cd1a49d113083349bfb31`), y se respaldaron `102` archivos y
    materializaron los `91` archivos nuevos de corrida (`smoke5`/`full5`/`select5`) en el checkout principal (`runs/`,
    ignorado por Git) con los mismos hashes y **sin sobrescribir ningún contexto antiguo** (`0` corridas de `test` en
    ambos árboles).
  - **`smoke5` (`sifilis_adquirida_a51_benchmark_smoke_b2b6e5bc21ba`):** **`succeeded`**
    (`manifest_sha256 = 376d08433ffa52f6133d1a1d909401a6867edbc096b625406f267f1ee641ebaf`, `20` artefactos
    verificados; `5,772` filas de `forecast.csv` y `111` filas de `metrics.csv` por cada uno de los `5` motores
    estacionales en `development_2024`).
  - **`full5` (`sifilis_adquirida_a51_benchmark_full_57698d37e134`):** **`succeeded`**
    (`manifest_sha256 = b1f3d41bbbd7620707d3bc09af6560b632bf50c443463d4e7a23be4dbeb4cf98`, `20` artefactos
    verificados; `23,088` filas de `forecast.csv` y `444` filas de `metrics.csv` por motor en
    `development_2021..2024`).
  - **`select5` (`sifilis_adquirida_a51_select_57698d37e134_b41ca5664941`):** **`succeeded`**
    (`manifest_sha256 = 708f2e7062d9149231b799c4524eb835f60896b8bb0b016e8a8e6a403c9c7776`,
    `selection_digest = 73490ea8b2b51a416fe1ce9cfc779bf914ce0fa53a7865ccb82543d8f939b4bd`, `4` artefactos
    verificados: `selection.csv` `324021fd…`, `portfolio_development.csv` `80297a44…`, `selection_report.md`
    `e8854cef…`; `code_commit = benchmark_code_commit = 8bbb72da8faffbdf0319f6c721618a3989f87af7`).
    - **Distribución en las `64` series base (`engines_selected = 5`, `challengers = 0`):**
      `seasonal_mean_3y = 22`, `seasonal_median_5y = 16`, `seasonal_naive_lag52 = 13`,
      `seasonal_mean_5y = 10`, `seasonal_median_3y = 3`.
    - **Métricas descriptivas de desarrollo (`2021–2024`; NO es prueba de 2025, aceptación ni `PASS`):**
      `smape_nacional_general = 51.965748`, `smape_all = 78.205128`, `smape_bases = 85.564430`,
      `mase_all = 1.558029`, `mase_bases = 1.470477`.
- **Dictamen pretest independiente de Fable completado (`CONDICIONAL`, NO pendiente de revisión) y decisión nominal del autor para 2025 `PENDING`:**
  - En `fable_pretest_policy5_8bbb/FABLE_PRETEST_POLICY5.{json,md}` (`2026-11-16T18:40:38Z`, `json`
    `a3f61df2f57dec26a7734c8bfacca996b42614979df5d715a2c31c8f701f72a8`, `md`
    `3232dd9e3b8e0f08f961b82be09330181af595b7bd6c2e1ac4b9b33261e6da84`), Fable emitió el veredicto
    **`CONDICIONAL`** (`blocking_technical_defects = 0`, `0` defectos de integridad, recómputo independiente con
    `0` diferencias en las `64` selecciones y barrido de `1,169` manifiestos con `0` pruebas previas de `A51`;
    **no abre 2025, no amplía autorización y no es aceptación ni `PASS`**).
  - **Riesgo científico medido en desarrollo (`P9` / `P8`, descriptivo sobre `2021–2024`):** aplicando la misma
    fórmula del gate a desarrollo, el portafolio congelado mejora al control `seasonal_naive_lag52` en las **`64`
    bases (`−9.98 %`, `85.56` vs `95.05`, límite `5 %`)** y en los **`111` productos (`−9.19 %`, `78.21` vs
    `86.12`, límite `5 %`)**, pero queda **`+50.05 %` peor que el control en `nacional General` (`51.97` vs
    `34.63`, límite `10 %`)**, fuera de límite en **`3 / 4` pliegues** (`2022: +42.56 %`, `2023: +78.29 %`,
    `2024: +18.76 %`; `2021: −25.98 %`). La subpredicción observada es compatible con el cambio de nivel nacional `2021–2023` (interpretación descriptiva, no prueba causal formal) (`×2.58` en
    `2024` frente a `2019`): los motores de ventana (`3` y `5` años) subpredicen mientras el nivel sube y la suma
    nacional hereda esa subpredicción (no predice `2025`).
  - **Divulgación de exposición `D1` (`K5`):** `QA_FINAL_373ea5f6/QA_COMPLETA.md` §3 incluye la fila anual
    nacional reconciliada pública de `2025` (y `2026` parcial), por lo que la evaluación **no es ciega al nivel
    anual público de `2025`**; no existen ni se usaron pronósticos, errores ni métricas de `2025`, la selección
    `select5` es determinista exclusivamente sobre métricas de desarrollo `2021–2024` (`epi_year <= 2024`), y
    ese nivel anual no debe usarse para decidir entre portafolio y control.
  - **Condiciones `K1–K5` antes de abrir 2025 y pregunta al autor `PENDING` (`ROOT_TEST2025_QUESTION_SENT.json`):**
    se envió al autor una **nueva pregunta nominal específica para abrir 2025** (`2026-11-16T18:46:17Z`,
    `proposal_sha256 = 485075c5ee78473876a93539149cda550d62baa57d22b0222a2cd70a2ee7e773`, estado **`PENDING`
    sin respuesta**, que no debe confundirse con `«si autorizo»` de desarrollo). Antes de ejecutar `test` de 2025
    deben cumplirse `K1–K5`: **(1)** nueva autorización expresa del autor para 2025 con el riesgo `+50.05 %` y la
    consecuencia del rechazo a la vista (`K2`, `K3`: hoy **no hay control estacional autorizado** para `A51`, por
    lo que un `REJECTED` en 2025 deja `lifecycle: configured`, piloto `0 / 1` publicado y la prueba única de 2025
    **consumida**, sin control de respaldo, `refit`, cambio de política/motores/umbrales ni retest), **(2)**
    compuerta nominal de `root` fijando `8bbb72da…`, dataset `0cc942faddb8` (`4` digests), política `6d2350be…`,
    `full5` `57698d37e134`, `select5` `57698d37e134_b41ca5664941` (`selection_digest` `73490ea8…`,
    `selection.csv` `324021fd…`), el dictamen pretest por SHA-256 y `D1` (`K1`, `K5`), y **(3)** ejecución única
    sobre `8bbb72da` limpio sin `--allow-dirty` (`K4`; cumplidas `K1–K5` sin cambiar ningún pin, no requiere otra
    corrida pretest de Fable).
  - **Divulgaciones obligatorias previas a cualquier eventual publicación (`K6`, no antes del test):** errata
    `2015_sem40.pdf` (desglose por sexo no fiable en `2015-W39` y `2015-W40` y posible arrastre en ventana de `13`
    semanas), peso de `sex_fallback_state_13w` (`18.8 %`) y `sex_delta_total_mismatch` (`14.9 %`), imputaciones
    de `2016_sem20` y Querétaro `2016_sem50`, que el nombre «baja incidencia» de la política no describe a la
    sífilis (`9,523..17,854` casos anuales), `MASE > 1` en `57 / 64` series en desarrollo, exclusión de `ETS` y
    `Ridge` tras fallo real en `full7` (`38 / 64` bases con mejora `> 5 %` en `2024`), `12` encabezados ráster
    sin automatizar en QA, registro `D1`, integración de `E1`/docs y revisión final independiente de Fable.
  - Producción continúa en **`85` publicados en el sitio / `81` del runner**, y el piloto en **`0 / 1`
    publicado** (`lifecycle: configured`, `0` pruebas de 2025).

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
  `fable_skill_v3_delta/FABLE_SKILL_V3_DELTA.{json,md}`,
  `fable_eval_weekly_v3_final/EVAL_SEMANAL_V3.{json,md}`, `ROOT_SKILL_INSTALACION_FINAL.json` y
  `opus_memory_current_audit/AUDITORIA_MEMORIAS.{json,md}`.
- Cierre documental PR `#75` (`d46effa6`), autorización nominal «si autorizo», fuente `8bbb72da`, desarrollo `smoke5`/`full5`/`select5`, remedio `E1`, dictamen pretest `CONDICIONAL` de Fable y pregunta nominal `2025` pendiente:
  `integracion_docs_postmerge/{CI_MAIN_D46_FINAL,SKIP_DELTA_MAIN_D46}.json`, `ROOT_FINAL_TECHNICAL_PROOF.json`,
  `fable_lag_source_precision/FABLE_LAG_SOURCE.json`, `ROOT_SKILL_INSTALACION_LAG.json`,
  `carbon_policy5_authorized/AUTORIZACION_AUTOR.json`,
  `opus_policy5_authorization_preflight/OPUS_POLICY5_PREFLIGHT.{json,md}`,
  `carbon_policy5_authorized/ROOT_PREFLIGHT_VERIFICADO.json`,
  `carbon_policy5_execution_fresh/ROOT_COMMIT_READY.json`,
  `fable_policy5_source_8bbb/FABLE_POLICY5_SOURCE.{json,md}`,
  `carbon_policy5_authorized/ROOT_RESULTADOS_SELECT5_VERIFICADOS.json`,
  `jobs/test_E1_before_8bbb/command_completed.json`,
  `jobs/test_E1_after_policy5/command_completed.json`,
  `fable_pretest_policy5_8bbb/FABLE_PRETEST_POLICY5.{json,md}` y
  `carbon_policy5_authorized/ROOT_TEST2025_QUESTION_SENT.json`.
