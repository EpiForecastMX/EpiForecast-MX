# Deudas vigentes — índice canónico

> Actualizado el 2-sep-2026 tras publicar P1 W33 y P1b: backend `main@3bd67236` y frontend
> `main@8490e433`.
> Este archivo separa
> trabajo vigente de bitácoras históricas. Una deuda que aparezca sólo en un documento
> antiguo no se ejecuta hasta contrastarla aquí y en el código.

## Activa — deudas tras publicar P1 W33 y P1b (2-sep-2026)

La fuente oficial 2026 fue comprobada el 2-sep-2026: contiene 33 boletines y el último
verificable es W33; W34 aún no está publicada. **P1 está publicada**: el sello
`882663dac1f1e39b` (W31 → W33, cuatro publicados en el mismo corte, 1,800 artefactos, 0
lápidas, `cifras` y `rag` PASS) se integró con merge commit `d7c9c6c2` en el backend (CI de
`main` run 33672251817 verde: 2,326 passed, 497 skips exactos, cobertura 77 %) y `72ae9e83`
en el frontend; Netlify desplegó https://epiforecast.mx con DATA_VERSION 20260825, knowledge
W33 (432/444), RAG 453, zoom 444 y los cuatro padecimientos con última fecha real 2026-08-10.

**Tanda correctiva P1b (2-sep-2026), integrada y publicada:** el smoke productivo encontró el
banner estático de novedades de `index.html` incoherente (titular del CALASS con fecha y
subtítulo de W33; lista secundaria en W31). Causa: `scripts/build_news_weekly.py` sólo
sustituía el titular si ya era una nota semanal. Corrección en `1ae477d5` (el bloque
`#newsBannerRow` se reescribe entero desde `news.json`, fallando en seco si falta) y gate
`cifras` reforzado en el frontend (`84536608`: el bloque estático debe coincidir con
`news.json`; contra el sitio publicado reporta cuatro desalineaciones). Re-sello
`89d70cc441ee255a` con ambos arreglos; backend PR #16 fusionada con merge commit `3bd67236`
(CI de `main` run 33677859434 verde: 2,329 passed, 497 skips exactos, cobertura 77 %,
Integration skipped) y frontend PR #12 fusionada con merge commit `8490e433`. Smoke productivo
completo en https://epiforecast.mx, con y sin JavaScript: banner estático y DOM renderizado
iguales a `news.json` (lead W33 · Datos · 2 de septiembre; CALASS y W31 en la lista
secundaria), W33 en los cuatro padecimientos (última fecha real 2026-08-10, 444 series),
DATA_VERSION 20260826, `app.js?v=140`, cifras 333/99/432/444, RAG 453 chunks, validación W33.
Estado vigente: backend `main@3bd67236`, frontend `main@8490e433`; ramas P0/P1/P1b y respaldo
conservados. W34 sólo cuando exista su PDF oficial y los cuatro publicados avancen juntos.

**Limpieza one-shot (2-sep-2026, noche):** ambos repositorios quedan sólo con `main` local y
`origin/main`; cero worktrees adicionales (se retiraron sin `--force` los dos del par de la
corrida 7). Ramas borradas tras verificar ancestría con `main`, locales con `-d` y remotas con
`push --delete`: backend `ci/skip-budget-ets-legacy`, `docs/p1b-publicada`,
`p0/namespace-e-inmutabilidad-del-sello`, `p1/actualizacion-semanal-2026-w33`,
`p1/release-backend-2026-w33-c6` (sólo local), `p1b/fallback-estatico-w33` y
`p1b/release-backend-c7` (sólo local); frontend `fix/frontend-deudas`,
`p1/actualizacion-semanal-2026-w33` y `p1b/fallback-estatico-w33`. La ref temporal
`auditoria/main` se retiró. El respaldo P0 pre-rebase vive ahora en la etiqueta LOCAL
`archive/p0-pre-rebase-584cf72d-2026-09-02` (no publicada); `respaldo/paper/micai-2026-camera-ready`
no se tocó. Se retiraron sólo los temporales `_trabajo*` y `_release` del scratchpad; sellos,
clon, DVC, PDFs, modelos y evidencia (`planes/p1_2026-w33_2026-09-02/`, con
`limpieza/inventario_antes.txt`) se conservan. Producción sigue en W33; W34, DVC, datos y
despliegue intactos.

Política permanente: todos los padecimientos `published` del registry tienen un único
corte público. Si cualquiera falta o difiere en año/semana, no se sella ni publica ningún
padecimiento. No se admite publicación parcial, arrastre de una semana anterior ni una
lista del operador que omita miembros. Obesidad y Anorexia siguen excluidas por lifecycle;
si se promueven, entran en el gate. W34 queda pendiente de existencia y validación oficial,
y deberá mover juntos a los cuatro publicados.

P1b quedó cerrada con los merges `3bd67236`/`8490e433` y el smoke productivo. Siguen abiertas: NBGLM de Dengue Aguascalientes desbordado; `EpiDashboard.html`
y `hero_series.json` del frontend se mantienen a mano (siguen en W31 / 2026-05-18); motores Dengue
incoherentes entre tabla 333, `produccion_dengue.csv` y zoom; dataset DVC sin versionar (opción C);
Google Sheets y Tableau conservan sus carriles manuales.

## Cerrada — P0 del flujo de actualización semanal

El plan vigente es `../../planes/PLAN_ACTUALIZACION_SEMANAL_UNIFICADA_2026-09-01_v4.md`
(SHA256 `5cfdf5a4a2d8e5ed1acf004e8c90a00e929dfd217ba051fff925e742fe9e233d`). La rama
`p0/namespace-e-inmutabilidad-del-sello` lleva 26 commits rebased sobre el `main` remoto
`16476a98` (tip `f88a065e`), enviada a `origin`. PR **#14** (https://github.com/EpiForecastMX/EpiForecast-MX/pull/14) **fusionada en `main`** con merge commit `5da24116` (padres `16476a98` y `d6e7a181`); CI del push a `main` `33645677062` verde: Code Quality PASS, Tests PASS (2 324 passed, 497 skipped exactos, 66 deselected, cobertura 77,00 %), Integration skipped por diseño. **Sin DVC, sin publicación ni deploy.** P1 en curso en `p1/actualizacion-semanal-2026-w33` desde `main@5da24116`.

Cerrado (1 y 2-sep, con controles negativos y 85 mutaciones del código vistas caer):

- P0.9 runner real de gates (solape por prefijos administrados, marcador y huérfanos,
  residuos apartados, digest del ejecutable, `chmod` es mutación, timeout con gracia);
  P0.6 apply confinado (registro atómico, rollback de prepare, discard ligado,
  composición del par también en el no-op); composición 41/41; completitud exacta;
  P0.11 opción C;
- `--out` en los tres generadores; P0.1 hidratación por allowlist `entradas/2` (44
  entradas reales, patrones glob, directorios scratch, entradas rastreadas desde el HEAD)
  con contrato del HEAD (catálogo, registry, profundidad 52 contigua MMWR, aditivo base ⊆
  candidato, forecasts sin series repetidas, alias no ambiguos);
- P0.2 `weekly_staging/3` con `entrada.lista`, inmutables verificadas al sellar, semanas
  atadas a los cortes y al EpiBot; materialización exigida por todos los pasos;
- P0.8 Dengue fail-closed y paridad entre todos los publicados; NB-GLM re-lanza errores
  de E/S (sin red no publica una constante);
- P0.10 cadena de caché fail-closed con imports anidados y `bump-cache`;
- datos: tabla 333 reparada (432 filas) y causa raíz en `merge_all_models`.

Gate: 902 pruebas de publicación; `make test-fast` = 2,820 passed, 1 skipped, 66
deselected; Ruff, mypy, `bash -n`, `git diff --check` verdes.

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

Deuda posterior, en orden:

1. **Publicación P1 W33**: candidato sellado y PRs draft abiertos; faltan CI/revisión final
   y autorización de merge/publicación. Nunca publicar si los cuatro `published` dejan de
   compartir W33;
2. `WEEKS_LIMIT = 15` en `reselect_motor_2026.py`: decisión pendiente (ningún contrato
   canónico fija la ventana; cambiarla re-selecciona motores);
3. ~~auditoría del avance remoto `a9a694c8 → 16476a98`~~ hecha el 2-sep: dos commits de
   datos del CI (registry W33 y punteros W33 de neuro, sin Dengue), sin solape con el
   delta P0; integrados por rebase; queda el merge de la PR #14 (decisión aparte);
4. bajos de la auditoría final, documentados y no corregidos: el aditivo no vigila
   padecimientos no publicados ni columnas fuera de `COLUMNAS_VALOR`; `ventana_semanas`
   de entidades por semana fijo en 52; `DATA_VERSION` con forma de fecha se incrementa
   (+1) salvo `--data-version`; el zoom del EpiBot nombra `mexico` y `estado de mexico`.

Límites declarados: ni runner ni sello son sandbox; los digests no son firma; sin
atomicidad entre repositorios; la identidad del huérfano exige `ps` con `lstart`.

## Cerradas o retiradas en esta auditoría

- **Gate de cifras públicas:** cerrado antes de esta ronda. `cifras:verify` ya recorre la
  superficie publicada completa, no sólo `knowledge.json`; su prueba negativa cubre HTML,
  JSON, subdirectorios y exenciones. Verificación actual: 41 archivos y 453 chunks, PASS.
- **Comparador «Depresión · ?»:** corregido en el frontend. El payload conserva ahora el
  motor de cada padecimiento; hay una prueba Node dedicada y se incrementó el cache-bust de
  `app.js` a v138.
- **Diagnóstico Netlify cortocircuitado:** corregido en el frontend. `deploy:verify`
  ejecuta `cifras:verify` y `rag:ci` aunque el primero falle, muestra ambos códigos y
  conserva un veredicto rojo si falla cualquiera. Tres controles unitarios cubren primer
  fallo, segundo fallo y doble PASS.
- **`bento.json` presentado como vivo:** retirado. La portada ya no contenía el mosaico;
  sólo quedaba un script muerto que descargaba el snapshot de junio sin tener nodos donde
  pintarlo. Se eliminó la petición y una prueba impide reintroducirla. El JSON se conserva
  como snapshot histórico.
- **`_fixCohortStats` supuestamente redundante:** deuda retirada por evidencia contraria.
  Al comparar `knowledge.json` crudo con `loadKnowledge()`, la función todavía corrige
  `por_motor`, el orden de `bottom5_smape` y la construcción de `dist_motor`. Quitarla hoy
  cambiaría cifras públicas. La deuda real es corregir el generador y demostrar igualdad
  antes de retirar la compatibilidad.
- **C7 prospectivo 1/4:** estado histórico superado. El estado efectivo es PASS 4/4 para
  `2026-W27..W30`; Obesidad continúa `trained` y NO-GO.
- **44 pruebas innecesariamente condicionadas:** cerrada por D2.3-A: 15 unit + 29 contract
  corren en clon limpio.
- **Cuatro agregados legacy con doble guarda:** cerrada. Los checks se movieron a
  `tests/integration/`, conservan los cuatro casos, llevan marker `integration` y no
  contienen ningún `skip`. El job normal los deselecciona; el carril manual los ejecuta y
  la ausencia de un CSV es FAIL explícito.
- **Presupuesto de skips del job Tests:** cerrado en alcance inicial. El workflow pasa
  `--max-skips=497` mediante un plugin propio; un control subprocess demuestra que 1 skip
  con presupuesto 0 termina en rc=1. El límite parte del último Ubuntu (501) menos los
  cuatro agregados ahora deseleccionados. Sus controles, junto con los dos de compatibilidad
  ETS, elevan la colección de 2,505 a 2,509. El run de `main` `33467472543` confirmó
  exactamente 497 skips: el presupuesto está calibrado sin holgura.
- **Pickle ETS incompatible con SciPy 1.18:** cerrado en local y Ubuntu.
  El loader normal sigue siendo la primera ruta; sólo ante `KeyError('_xp')` un unpickler
  local completa el namespace NumPy de `LbfgsInvHessProduct`. No hay parche global y otro
  `KeyError` sigue fallando. Los 16 modelos del release reprodujeron 832 valores canónicos
  con error máximo `2.27e-13`; 54 pruebas focales, el carril completo y el run de `main`
  `33467472543` pasan.

## Prioridad 0 — siguiente trabajo local seguro

1. **Política de skips del carril manual.** El job Tests ya tiene presupuesto; falta decidir
   qué debe poder omitir Integration cuando se lanza expresamente por `workflow_dispatch`.
2. **Readiness de Obesidad rancio.** El manifiesto local conserva 1/4 aunque el status
   canónico da 4/4. El loader ETS ya pasó CI: regenerarlo localmente es el siguiente paso
   seguro, pero no autoriza preflight, apply, lifecycle, puntero, publicación ni DVC.

## Prioridad 1 — requiere un microplan propio

- **Cadena sellada sintética:** prototipo acotado antes de clasificar D1. Quedan 460
  nodeids en 156 grupos que consumen cadena; no llamarlos «460 grupos».
- **Retiro del shim ETS:** depende de `LbfgsInvHessProduct` y `_xp`, privados de SciPy.
  Mantenerlo mientras el release vigente use `statsmodels_pickle`; retirarlo sólo después
  de migrar a un estado ETS portable con schema versionado y equivalencia demostrada.
- **Generador de `knowledge.json`:** debe emitir las mismas estadísticas neuro que hoy
  recompone `_fixCohortStats` en runtime. Criterio: igualdad profunda de todos los campos
  afectados antes de borrar la compatibilidad.
- **Publicador legacy de Sheets:** `scripts/publish_gsheets.py` aún carece de retry/backoff y
  resume. No confundirlo con `GoogleSheetsTableSink`, que administra sólo `runner_*`, protege
  las cinco tabs legacy y tiene promoción/rollback compensado. El script legacy toca la hoja
  productiva y requiere diseño y pruebas antes de cambiarlo.

## Externas o manuales — no resolver desde código

- **Tableau Public W31:** sigue NO-GO hasta repuntar las 20 worksheets a
  `fecha_boletin`, publicar con la cuenta propietaria y hacer smoke test. Ver
  `ESTADO_TABLEAU_W31_2026-08-20.md`.
- **MICAI 2026:** falta resolver el registro de un autor; requiere coordinación humana.
- **CALASS:** el congreso terminó. Los pendientes de viaje expiraron; las observaciones de
  láminas son deuda de diseño histórica, no trabajo operativo urgente.

## Documentos históricos

- `OBESIDAD_PENDIENTES.md`: intento preliminar anterior a C1-C7; no es plan vigente.
- `PLAN_BRUTAL_OBESIDAD_N_PLUS_1.md`: conserva la cadena de auditoría; usar el plan C7 y
  el estado efectivo para operar.
- `PLAN_CONVERGENCIA_RAMAS_Y_DATOS.md`: bitácora de la convergencia del 18-ago; sus ramas,
  estado 1/4 y siguientes acciones quedaron superados.
- `PENDIENTES_2026-08-25.md`: bitácora CALASS/cifras; sus ítems vigentes se reflejan aquí.
- `RONDA_128_AUDITORIA_PENDIENTE_DE_PEGAR.md`: evidencia de una ronda, no cola de trabajo.

## Regla de cierre

Una deuda se cierra sólo con: cambio identificable, control positivo, control negativo cuando
aplique y actualización de este índice. Un documento antiguo no se borra para ocultar el
historial; se marca como supersedido y se enlaza a este índice.
