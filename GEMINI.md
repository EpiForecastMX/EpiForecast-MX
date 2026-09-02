# GEMINI.md — Contexto operativo de EpiForecast-MX

> Actualizado contra `p0/namespace-e-inmutabilidad-del-sello` sobre
> `a9a694c8fb1b93c616e2b179a5b24d095d3de9ce` el 1-sep-2026.
> Guía para Gemini CLI dentro de `EpiForecast-MX`; no sustituye las órdenes del
> workspace ni autoriza acciones externas.

## 0. Trabajo activo: P0 del flujo semanal

Backend en `p0/namespace-e-inmutabilidad-del-sello` con 26 commits rebased sobre el
`main` remoto `16476a98` (tip `f88a065e`; 2-sep, tercera tanda correctiva: runner,
worktrees, sello atado al HEAD, allowlist v2, contrato profundo, tabla 333 reparada, causa
raíz en `merge_all_models`, orquestador, auditoría final), árbol limpio y rama enviada a
`origin`. PR **#14** (https://github.com/EpiForecastMX/EpiForecast-MX/pull/14) **fusionada en `main`** con merge commit `5da24116` (padres `16476a98` y `d6e7a181`); CI del push a `main` `33645677062` verde: Code Quality PASS, Tests PASS (2 324 passed, 497 skipped exactos, 66 deselected, cobertura 77,00 %), Integration skipped por diseño. **Sin DVC, sin publicación ni deploy.** P1 en curso en `p1/actualizacion-semanal-2026-w33` desde `main@5da24116`. `origin/main` local sigue en `a9a694c8` (sin pull). El frontend
`main@0e777995c9e53cdd08b6d25ad58b65928a25b88b` está intacto.

`make update-week` sigue bloqueado en preflight hasta la autorización de P1 (red y
decisión de publicar). Flujo: `materialize → hydrate → generadores (--out) → bump-cache →
run-gates → seal → prepare-worktrees → apply → check-completeness → discard-worktrees
--manifiesto`, todo atado al mismo par de HEAD y política por `materializacion.json`.
`CONFINAMIENTO_LISTO = True`; P0.11 = opción C.

Gate local: 902 pruebas de publicación; `make test-fast` 2,820 passed, 1 skipped, 66
deselected; Ruff, mypy, `bash -n`, `git diff --check` verdes; 85 mutaciones vistas caer.
Ensayo real del 2-sep (`planes/ensayo_P012_2026-09-02/`): la cadena de generación entera corre sin red en el sandbox; `run-gates` da `rag` FAIL porque el índice RAG exige GEMINI_API_KEY (red) para reconstruirse (fallo cerrado, sin sello); el tramo sello→par desechable pasa sobre la composición real con composición aplicada == sellada. Pendiente: `WEEKS_LIMIT` (decisión), auditoría del avance remoto con red, y P1
con autorización. Plan auditado:
`../planes/PLAN_ACTUALIZACION_SEMANAL_UNIFICADA_2026-09-01_v4.md`, SHA256
`5cfdf5a4a2d8e5ed1acf004e8c90a00e929dfd217ba051fff925e742fe9e233d`.

## 1. Precedencia y forma de trabajo

Antes de actuar:

1. leer `/Users/haowei/Documents/Integrador/AGENTS.md` completo;
2. leer este archivo;
3. para Obesidad/C7, consultar `docs/PLAN_C7_PUBLICACION_OBESIDAD.md` y resolver el
   estado efectivo desde el registry y los JSON de `config/publication/obesidad/`;
4. ejecutar `git status --short --branch` en backend y frontend;
5. preservar archivos no rastreados y cambios ajenos;
6. auditar sólo el delta si el checkpoint cambió.

Orden de autoridad: instrucciones explícitas del usuario → `AGENTS.md` → este archivo →
README y bitácoras históricas. El plan C7 es cronológico y conserva rondas supersedidas:
una frase antigua `INCOMPLETE 1/4` no vence al estado canónico verificado.

No inferir autorización para `git push`, PR, merge, deploy, publicación, entrenamiento,
`dvc add/push/pull/fetch`, escrituras S3 o Google Sheets. Cada acción externa se autoriza
por separado. Para revisar o diagnosticar, no implementar ni mutar salvo petición expresa.

## 2. Estado operativo vigente

### Repositorios

- Backend: `EpiForecast-MX`, rama de trabajo
  `p0/namespace-e-inmutabilidad-del-sello` sobre `a9a694c8`; worktree P0 sin commit.
- Frontend: `EpiForecast-IMSS-Dashboard`, `main` en `0e777995`; worktree limpio e intacto
  durante P0.
- Quedan dos ramas ya mergeadas, locales y remotas: `ci/skip-budget-ets-legacy` y
  `fix/frontend-deudas`. Ambas puntas son ancestros comprobados de `main`; no confundir
  «main activo» con «una sola rama» hasta borrarlas de forma explícita.
- El remoto local `respaldo` conserva una referencia de archivo MICAI: no borrarla.
- Mantener backend y frontend en commits y PR separados.

### CI semanal

El incidente «CI falla los lunes» está arreglado en `main` mediante PR #12, merge
`59488c57`. La tanda de deuda/compatibilidad entró después por PR #13. Run vigente de
push a `main` `33467472543`:

- Code Quality: PASS;
- Tests: PASS;
- Integration Tests: SKIPPED;
- 2,509 colectadas = 1,946 passed + 497 skipped + 66 deselected;
- cobertura 74.50%; gate canónico único `fail_under = 70`.

`--cov` no vive en `pytest.addopts`: el job `Tests` declara el alcance y toma el
umbral de `[tool.coverage.report]`. `scripts/compliance_check.py` usa
`--cov-fail-under=0`: es diagnóstico con mínimos propios, no el gate canónico.

El cron corre lunes 06:00 UTC. Quality y Tests corren; Integration es legacy y sólo se
ejecuta por `workflow_dispatch`. En push, PR y schedule debe aparecer **SKIPPED**, no
verde. La concurrencia separa eventos por `github.event_name` y no cancela schedules.

El cierre operativo espera el schedule del 7-sep-2026. Hasta entonces: «arreglado y
verificado en push/PR; schedule aún no observado».

### Deuda de skips

El job verde contiene 497 skips en Ubuntu, exactamente el presupuesto configurado. El
universo D2 histórico auditado tiene 552 nodeids:

- 81 passed y 471 skipped;
- 460 nodeids en 156 grupos usan la cadena sellada;
- 6 tienen dependencia implícita confirmada;
- los 4 agregados legacy antes doblemente guardados viven ahora en `tests/integration/`:
  el job normal los deselecciona y el manual falla si falta un CSV;
- 1 prueba es mixta y debe dividirse.

Los 44 despertados son 15 `unit` + 29 `contract`, movidos y verificados en clon
limpio. No llamar «460 grupos» a lo pendiente. El job Tests limita ahora los skips a 497;
cuatro controles nuevos elevan la colección del árbol de trabajo a 2,509. Falta la política
del carril manual. Orden vigente: política de Integration → prototipo de cadena sintética
→ sólo si es viable, los 156 grupos.
La cola contrastada y las memorias supersedidas están en `docs/DEUDAS_VIGENTES.md`.

## 3. Padecimientos y lifecycle

`config/padecimientos.yaml` es la fuente canónica de identidad, perfiles, engines,
lifecycle y canales. Sólo `published` llega a consumidores `published_only`.

| ID | Estado | Carril | Visibilidad |
| --- | --- | --- | --- |
| `depresion` | `published` | legacy neuro | pública |
| `parkinson` | `published` | legacy neuro | pública |
| `alzheimer` | `published` | legacy neuro | pública |
| `dengue` | `published` | legacy standalone | pública |
| `obesidad` | `trained` | runner/release C7 | **NO-GO** |
| `anorexia_f50` | `configured` | demostración N+1 | **NO-GO** |

### Neuro y Dengue publicados

El pipeline legacy usa `ForecastModel` + factory para Prophet, DeepAR, Ensemble,
Stacking y NBGLM. No importar clases concretas desde scripts; usar `create_model()`
cuando el carril legacy lo requiera.

- Neuro = Depresión, Parkinson y Alzheimer: 333 productos.
- Dengue es standalone, no parte de los 333 neuro.
- Dengue entrena Prophet, DeepAR, Ensemble, Stacking y NBGLM.
- Sólo Prophet, DeepAR y NBGLM son elegibles; los árboles no son productivos.
- La selección legacy 2026 tiene caveat in-sample. No presentarla como OOS; el backtest
  leave-one-epidemic-out de NBGLM sí es OOS.

### Obesidad E66 — gate 4/4, publicación NO-GO

Obesidad está `trained`, `gallery_enabled: false`, sin engines legacy autorizados y
con backend `runner_release`:

- release `obesidad_release_2517e7858901`;
- puntero `artifacts/releases/obesidad/obesidad_release_2517e7858901.dvc`;
- 64 modelos base + 47 derivados = 111 productos;
- forecast puntual de 52 semanas, 5,772 filas, sin intervalos;
- lifecycle y puntero público inactivos.

Estado prospectivo verificado en lectura:

```text
.venv/bin/python -m scripts.prospective_status obesidad --check
PASS 4/4 · semanas 2026-W27..W30
observation_dataset_id = obesidad_0eaccbfa62ff
```

La evaluación conserva release, gate, candidato, control y umbrales congelados. El
candidato supera al control en bases, 111 productos y nacional General.

**4/4 no autoriza publicar.** El `runs/readiness/obesidad/readiness_manifest.json`
existente es anterior y todavía declara 1/4: es evidencia local obsoleta. El preflight
Google/Tableau sigue `BLOCKED_EXTERNAL`.

**Compatibilidad ETS cerrada en local y Ubuntu (1-sep).** SciPy 1.18
añadió `_xp` al estado de `LinearOperator`; los pickles sellados anteriores no lo traen.
El loader intenta primero el pickle normal y sólo ante ese `KeyError` exacto usa un
unpickler local para `LbfgsInvHessProduct`; no parchea clases globales ni oculta otros
errores. Los 16 modelos ETS reproducen sus 832 valores canónicos con error máximo
`2.27e-13`; las 54 pruebas focales, el carril local completo y el run de `main`
`33467472543` quedan verdes. El shim sigue siendo deuda temporal: depende de privados de
SciPy y debe retirarse cuando exista un estado ETS portable versionado.

Antes de activar hacen falta, con permisos separados:

1. regenerar readiness local contra 4/4, sin promover;
2. staging externo y preflight;
3. Tableau Desktop y smoke test;
4. autorización de apply;
5. flip de lifecycle/puntero;
6. merge, deploy y smoke público.

No ejecutar `make update-week` para Obesidad. No reentrenar, retunear, reseleccionar,
refitear ni modificar gate, candidato, control, release o umbrales.

### Anorexia F50

F50 probó N+1 por configuración. Permanece `configured`, `channels: []`,
`training_engines: []`, `eligible_engines: []` y `gallery_enabled: false`. Un
smoke funcional no es una afirmación productiva.

## 4. Dos arquitecturas que no deben mezclarse

### Legacy publicado

- Modelos: `src/epiforecast/models/`.
- Factory: `src/epiforecast/models/factory.py`.
- Artefactos: `models/`, `reports/forecasts/`, `reports/ProdDetails/`.
- Consumidores: Tableau legacy, web, EpiBot y validación semanal.
- Targets históricos: `train-*`, `predict-*`, `tableau`, `update-week`.

Esos targets existen, pero no son recetas universales ni son aptos para Obesidad. Varios
escriben rutas canónicas, DVC, S3 o superficies públicas.

### Runner/release genérico

- Datos: `epi_calendar.py`, `epi_geo_exposure.py`, `epi_reconcile.py`,
  `epi_dataset.py`, `epi_aggregate.py`.
- Contratos y manifests: `src/epiforecast/runner/`.
- Engines: seasonal naive/windows, ETS, Ridge armónico y Prophet count/rate.
- Publicación: `src/epiforecast/publication/`.
- Releases: `artifacts/releases/<disease>/<release_id>`.
- Observaciones: `artifacts/observations/<disease>/<dataset_id>`.

El runner entrena 64 bases (32 entidades × 2 sexos) y deriva 47 productos. Nunca
entrenar directamente generales, regiones o nacional. Los outputs viven por run/release;
no deben caer en rutas legacy por la existencia accidental de un PKL.

## 5. Comandos y autorización

### Lectura y diagnóstico seguro

```bash
git status --short --branch
git diff --check
git log --oneline --decorate -10
.venv/bin/python -m scripts.prospective_status obesidad --check
make lint
make typecheck
make test-fast
```

Validar proporcionalmente. Un cambio documental no requiere suite completa. Al reportar
CI, distinguir runner limpio de local hidratado con `runs/` y bundle.

### Escribe evidencia local; requiere alcance explícito

```bash
make readiness DISEASE=obesidad \
  RELEASE=artifacts/releases/obesidad/obesidad_release_2517e7858901.dvc
```

`readiness` no publica ni usa red, pero escribe bajo `runs/readiness/`; no ejecutarlo
en auditoría read-only. Hoy debe regenerarse porque la evidencia conserva 1/4.

### Prohibido sin autorización separada

- push, PR, merge, tag, deploy o publicación;
- `dvc add/push/pull/fetch`, global o dirigido;
- `make data-*`, `models-push`, `forecast-push`, `s3-sync`,
  `model-pipeline`;
- `make train*`, `predict*`, `tableau`, `update-week*` para Obesidad;
- escrituras Google Sheets, S3, Tableau o web pública;
- activar lifecycle, puntero o `gallery_enabled`;
- borrar, mover, añadir o sobrescribir untracked del usuario;
- `dvc checkout --force` global;
- reset o force-push de `main`.

Rollback público: rama nueva + `git revert` + PR. Nunca reescribir historia.

## 6. Tests y gates

- Pytest: 136 archivos test, 2,509 nodeids; run vigente de `main`: 1,946 passed,
  497 skipped y 66 deselected.
- Markers: `unit`, `contract`, `slow`, `integration`.
- `--strict-markers` activo.
- Umbral único: `fail_under = 70`.
- Job normal: `not slow and not integration`, cobertura explícita.
- Integration legacy: manual; exige cadena y omite la mayoría en runner limpio.
- CI instala `ghostscript` y `poppler-utils` tras `apt-get update`.

Un gate debe poder fallar. El control negativo de cobertura elevó temporalmente el
umbral a 99 y terminó con código 1 aunque las pruebas pasaron. No leer `$?` después de
un pipe: sería el estado de `tail`, no de pytest.

## 7. Datos, DVC y artefactos

- Git gobierna código, configuración, manifests y punteros `.dvc`.
- DVC/S3 gobierna datos y artefactos pesados.
- `runs/` es gitignored y no es una fuente portable por sí sola.
- Releases y observaciones tienen targets DVC dedicados.
- «DVC verde» debe ser por target explícito; el estado global puede incluir WIP ajeno.
- Nunca restaurar todo con checkout DVC global.
- Antes de operar: resolver target, revisar diff, preservar evidencia y obtener permiso.

Los borradores Tableau `.twb`, `.twbr` y `.hyper` no rastreados son del usuario. No
borrar, mover, añadir ni sobrescribir. Ver
`docs/ESTADO_TABLEAU_W31_2026-08-20.md` y `ORDENES.md`.

## 8. Calidad de código

- Python 3.12; Ruff line-length 99; imports stdlib → terceros → locales.
- Mypy cubre `src/`, runner aislado y cuatro CLI C7 en CI.
- Logging con `loguru` según la infraestructura existente.
- No ampliar god-modules sin necesidad.
- Usar `apply_patch` y revisar `git diff`.
- No añadir condicionales por enfermedad si registry/perfiles resuelven el contrato.
- Metadata/manifests gobiernan identidad; no inferirla del filename salvo adaptador
  legacy explícito.
- `published_only` es la frontera pública; probar inclusión y exclusión.

## 9. Archivos gobernantes

- Workspace: `/Users/haowei/Documents/Integrador/AGENTS.md`.
- Contexto amplio: `CLAUDE.md`.
- Registry: `config/padecimientos.yaml`.
- Política OOS: `config/evaluation/rolling_cv_v1.yaml` — no editar comentarios: mueve
  su digest.
- C7: `docs/PLAN_C7_PUBLICACION_OBESIDAD.md`.
- Arquitectura: `docs/PLAN_BRUTAL_OBESIDAD_N_PLUS_1.md`.
- Tableau: `docs/ESTADO_TABLEAU_W31_2026-08-20.md`.
- Órdenes manuales: `ORDENES.md`.
- CI: `.github/workflows/ci.yml` y `pyproject.toml`.

## 10. Cómo retomar

1. Confirmar worktrees y HEAD.
2. Resolver C7 con `prospective_status --check`, no con una ronda vieja.
3. Recordar: 4/4 no equivale a publicación; readiness está desfasado y externo bloqueado.
4. Para CI, esperar el schedule del 7-sep y aplicar el árbol de decisión.
5. Para skips: dobles guardas → política → fabricador sintético → D1.
6. Para Obesidad: no reentrenar ni publicar; pedir la autorización exacta faltante.
7. No mezclar artefactos legacy con runner releases.
8. Actualizar esta guía si cambian lifecycle, gate, readiness, CI o ramas.
