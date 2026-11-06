## Orden vigente del autor: cierre sincronizado en main (5-nov-2026)

El autor ordenó: «no dejar nada en ramas, todo siempre sincronizado». Aplica a
EpiForecast-MX y EpiForecast-IMSS-Dashboard y prevalece sobre recetas históricas
que terminaban dejando el checkout en una rama de trabajo.

- Las ramas y worktrees de desarrollo son temporales. El trabajo terminado debe
  quedar integrado en `main` y enviado a `origin/main`; ambos checkouts principales
  deben terminar en `main`, sin cambios pendientes de la tarea y sin divergencia.
- Antes de integrar, inventariar ramas, worktrees, stashes y cambios locales.
  Respaldar y verificar por hash los cambios ajenos; resolver los conflictos sin
  descartarlos. Nunca usar `reset --hard`, `clean`, force-push ni borrar trabajo
  único para aparentar sincronización. Un stash o una etiqueta de respaldo no
  equivalen a integración ni a cierre.
- Tras integrar y verificar CI, retirar las ramas locales y remotas ya contenidas
  en `main` y los worktrees temporales propios; conservar antes sus runs y evidencia.
  Las ramas con commits únicos requieren revisión e integración; no se borran ni
  se fusionan a ciegas. No abandonar silenciosamente cambios ajenos pendientes.
- Verificar con red `fetch --prune`, `HEAD == main == origin/main`, el SHA real de
  `refs/heads/main` en origin, estado del árbol, ramas restantes y CI del SHA final.
  Comprobar backend y frontend como un par; el despliegue público requiere además
  comprobar la versión servida. No confundir una referencia remota local con red.
- Si falta red, acceso o una decisión sobre cambios ajenos, el cierre queda
  bloqueado con el motivo y los pendientes exactos. No afirmar «todo sincronizado»
  ni «cerrado» por tener una PR fusionada o por conservar una copia en /tmp.
- La sincronización no autoriza reentrenar, reabrir 2025, cambiar criterios de
  aceptación, publicar otro padecimiento ni modificar artefactos sellados.

# GEMINI.md — Contexto operativo de EpiForecast-MX

## Continuidad OnePlus — 20-sep-2026

El artículo PLOS ONE ya tiene C, D y A+B ampliada aplicadas y selladas; aún no está
enviado. Usar `Congresos/OnePlus/PLOS_build/latex/manuscrito_plos.tex` para revisión y
`manuscrito_plos_SUBMISSION.tex` para Editorial Manager. Las cifras primarias son 53.2
sMAPE, 0.387 MASE y 267/288 (92.7 %) en 288 estatales; 333 es sólo cobertura del sistema
(288 estatales, 36 regionales, 9 nacionales). Reparto H3: Ensemble 110, Stacking 109,
Prophet 87, DeepAR 27. Los resultados/tablas/figuras históricas heterogéneas fueron
retirados del manuscrito, no borrados del disco.

Para retomar: primero subir `PLOS_build/envio_2026-09-18/manuscrito_plos_2026-09-18_OVERLEAF_PREVIEW.zip`
a Overleaf y revisar sus cinco figuras. El ZIP administrativo compañero no contiene
figuras porque PLOS las recibe aparte. No usar `latex.zip` de 8-jul: es obsoleto.
No compilar localmente la variante de envío hasta resolver `changepage.sty` o usar
Overleaf. No enviar ni desplegar sin autorización explícita.

El bot continúa con el defecto de `scripts/build_tableau.py:134-138`: conserva bandas de
DeepAR al reasignar puntos de otros motores. W23 sigue en cápsula: etapa B, W34, snapshot,
entrenamiento, DVC y despliegue siguen bloqueados. Preservar el árbol sucio preexistente.

## Salida de sesión WCP — estado único vigente — 9-sep-2026

**Trabajo operativo cerrado por ratificación expresa del autor.** Póster inglés
cargado al WCP y web publicada. No repetir carga, rediseño o petición de ratificación.
Par EN ec5ebd80… / ES 8a0a9018… intacto; frontend f02d2d16656ca1365d2b0a351109fb3be396457e.
35 criterios registrados por hash; 46+52 controles y 22 de exportación correctos.
Sello 110 piezas; manifiesto documental 103. EN 24/24, ES 23/24+C03 aceptada.
Salida final: las nueve dependencias recuperadas ya están en RATIFICATION_FILES
del exportador y son obligatorias también al verificar. No reponerlas sólo a mano
ni regenerar desde el carril antiguo de 94 piezas. Evidencia exacta en
`poster/auditorias/ratificacion_2026-09-09/INVENTARIO_RECUPERADO.json` dentro de Mundial.
Índice de salida desde workspace: `planes/SALIDA_WCP_2026-09-09.md`.
Gobernante: 13 PASA, 3 EXC, 13 N/A y 4 FALLA por formularios nominales sin
respuestas/firmas; no confundir la ratificación global del autor con jueces
independientes. EXC y N/A nunca se suman como aprobaciones. No abrir tareas
automáticas por esa diferencia documental.

Desde la raíz del workspace, leer únicamente para reanudar:
- `EpiForecast-MX/Congresos/Mundial/ESTADO_ACTUAL_WCP.md`.
- `planes/PROMPT_REANUDAR_WCP_ENVIADO_2026-09-09.md`.
- `POSTER_WCP_2026/RATIFICACION_Y_CIERRE_2026-09-09.md`.

Los checkpoints WCP inferiores son históricos, incluso donde dicen «vigente»,
«sin ratificar», «no registrado», «no publicado» o manifiesto 93/94. No ejecutarlos.
No cambia la continuidad de Obesidad u otros carriles. Cambios de memoria locales;
sin commit/push/deploy en esta salida. Preservar árboles sucios y artefactos sellados.

## WCP — cierre ratificado por el autor — 9-sep-2026

Prevalece sobre los checkpoints WCP inferiores. El autor declaró «ya esta todo
ratificado y validado cierra todo ya pues». Esquema registrado: 35 criterios
G11/G12/G14/G15, ligados al par por SHA-256 y no por carpeta. No volver a pedir
ratificación, ejecutar planes históricos, rediseñar ni repetir la carga.
PDF EN ec5ebd80… / ES 8a0a9018… intactos; WCP cargado y web vigente f02d2d16.
Sello 97; manifiesto documental 103, con el anterior 94 conservado como antecedente.
46 controles históricos + 52 del registro correctos. Excepciones G2/G5/G19
aceptadas y separadas de PASS; C03 ES conserva su excepción. La declaración del
autor no se transforma en respuestas o firmas nominales de jueces no aportadas.
No afirmar certificación independiente ni abrir tareas automáticas por esa
distinción. Cierre: POSTER_WCP_2026/RATIFICACION_Y_CIERRE_2026-09-09.md.
Estado: EpiForecast-MX/Congresos/Mundial/ESTADO_ACTUAL_WCP.md.
Sin commit, push, despliegue o actuación en el portal en esta ratificación.

## WCP — carga registrada y web vigente comprobada — 8/9-sep-2026

**Prevalece para la continuidad WCP sobre las secciones históricas inferiores.**
El autor ya cargó el póster inglés #3134: el portal muestra
`WCP2026ePoster3134Rebull`, **09.09.2026 03:19**, E-POSTER VIEWING.
La subida no es pendiente. Capturas conservadas; no se descargó la copia del
portal ni se afirma aprobación editorial o carga ES.

El sitio del QR ya sirve el par vigente, verificado por descarga pública:
EN `ec5ebd80…` / ES `8a0a9018…`, inglés inicial,
`Reports/wcp2026/2026-09-08-8a0a9018/`.
Frontend HEAD y referencia local origin/main:
`f2141bbacbcd8b692fedda1199ace3b889a070a0`.
No listar como pendiente publicar este par. No se hizo push/deploy en este cierre.

Estado autoritativo y hashes completos, rutas desde la raíz del workspace:
- `EpiForecast-MX/Congresos/Mundial/ESTADO_ACTUAL_WCP.md`.
- `POSTER_WCP_2026/REGISTRO_SUBIDA_WCP_2026-09-09.md`.
- Handoff: `planes/PROMPT_REANUDAR_WCP_ENVIADO_2026-09-09.md`.

Preservar la entrega lema_congreso: EN 24/24; ES 23/24 más excepción de densidad
ligada al hash, no un PASS adicional. Sello 97 piezas; manifiesto 93 piezas.
Cuatro revisiones humanas y contrato interno 960×540/12 pt siguen sin cerrarse;
no se dispensan por la carga. No hubo financiamiento; título aceptado intacto,
siete apellidos con guion. No reabrir diseño ni ejecutar prompts de opciones 7–9.
La hoja sellada y las versiones históricas se conservan intactas; el nuevo estado
documenta los eventos posteriores. Ninguna nueva acción externa está autorizada
por esta actualización de memorias.

## WCP opción 9 — QR publicado y verificado — 2026-09-04

**Prevalece sobre los cierres WCP inferiores.** El usuario autorizó publicar únicamente
los materiales del QR. Publicado en https://epiforecast.mx/wcp2026.html mediante frontend
`c6e0bf9d7deb587df028a799da7139edc8fc401d`; ocho archivos WCP, ningún cambio ajeno.
Los PDF públicos EN/ES son byte-idénticos a los canónicos (hashes aec864d5… / 4c5911f8…).
Sello de 73 piezas intacto. Validación publicada **27/31**: G10c ya pasa; sólo restan
G11/G12/G14/G15 humanos, sin firmas. No se subió nada al congreso.

Evidencia: `EpiForecast-MX/Congresos/Mundial/poster/qa_opcion9/PUBLICACION_OPCION9.json`.
Portada equivalente tras Pretty URLs; news y knowledge iguales; corpus y vectores RAG
iguales, con sólo la fecha built actualizada por el build habitual de Netlify.
El checkpoint sellado anterior conserva su texto LOCAL_NO_PUBLICADO como historial;
no ejecutar su cierre ni interpretarlo como estado vigente.

Reanudar con `planes/PROMPT_REANUDAR_WCP_2026_OPCION9_PUBLICADA_2026-09-04.md`
desde la raíz del workspace. No reabrir financiamiento ni logos. No modificar PDF ni
firmar por humanos. Esta autorización no permite otras publicaciones ni la subida al congreso.


## WCP vigente — opción 9, correcciones de auditoría — 2026-09-04

Esta sección sustituye los cierres WCP inferiores. Diseño y WCP/WPA conservados; no hubo
financiamiento. Mapa corregido a los motores seleccionados: mediana estatal 21.6%,
máximo Tlaxcala 46.7%; Puebla 20.6%. Las cifras nacionales y las 52 semanas no cambiaron.
Revisiones G11/G12/G14/G15 reforzadas: criterios completos, ambos idiomas, veredicto de
aprobación y firmas fechadas; ninguna revisión real está firmada.

PDF EN 260819 B, `aec864d59318a8ce771bba7aa9a4499e104e9f88d01d239ea08c07421280cb10`.
PDF ES 260047 B, `4c5911f86be196a8811553930d6c2af6459d380273c409a3b909f0d60322cf08`.
Suite definitiva 89/89 (39 mutantes específicos, 45 negativos y 5 positivos).
Sello 73 piezas; validación verificada 26/31: cuatro revisiones humanas y G10c (QR público
desactualizado). No confundir disponibilidad HTTP 200 con versión publicada correcta.
Paquete QR LOCAL verificado: `Congresos/Mundial/poster/entrega_qr_opcion9/` en backend.
Evidencia definitiva: `Congresos/Mundial/poster/qa_opcion9/CIERRE_OPCION9.json`.

Handoff desde raíz del workspace:
`planes/PROMPT_REANUDAR_WCP_2026_OPCION9_2026-09-04.md`.
Usar `qa_opcion9/cierre.py`, no el cierre histórico de `qa_coautoras/`.
Sin commit, push, deploy, subida al congreso ni comunicaciones externas. Publicar el
paquete QR requiere autorización; no autoriza subir al congreso. El asistente no firma por
humanos ni acredita ceguera. Frontend y fuentes/modelos no fueron modificados.



> **WCP vigente: opción 8, 4-sep-2026 (coautoras).** Sustituye las instrucciones inferiores
> para reanudar opción 7. WCP/WPA se conservan por el encargo del autor; financiamiento cerrado:
> no hubo. PDF EN 260355 B, `76ff5bcf75ae7c5f9030c68c7dd03d0696e16209e57715c1319a3928a4610ed4`;
> ES 259591 B, `b434906b89d3d11f65318fcfd231a8bc8055242afe4d229e33a64dad89318226`.
> 25/29 en ambos, sello 64 piezas; cuatro hojas humanas actualizadas y sin firma. El horizonte
> corregido contiene 52 semanas hasta 1-feb-2027 en calendario de boletín. Handoff en
> `planes/PROMPT_REANUDAR_WCP_2026_OPCION8_2026-09-04.md` desde la raíz del workspace;
> resultados y defensa en `Congresos/Mundial/poster/qa_coautoras/CIERRE_OPCION8.json`.
> No reiniciar diseño ni reabrir el logo como bloqueo. No hacer acciones externas sin autorización.


> Actualizado al cierre de limpieza: backend `main@77dc2dcb`, frontend `main@8490e433`,
> ambos alineados con `origin/main`, el 2-sep-2026.
> Guía para Gemini CLI dentro de `EpiForecast-MX`; no sustituye las órdenes del
> workspace ni autoriza acciones externas.

Próxima tarea deliberada: cerrar técnicamente la **opción 7** del e-póster WCP 2026. Usar
`../planes/PROMPT_REANUDAR_WCP_2026_OPCION7_2026-09-04.md` (SHA256
`a4385a9f6019433cb3a77736b766fd1c3ec736ee515cc65b7a3345dc234eedd3`) y copiar el bloque
entre `## PROMPT` y `## FIN DEL PROMPT`. No volver al plan del 2-sep. Estado: 25/29 en
ambos idiomas, sello de 49 piezas, cuatro revisiones humanas caducadas y suite de mutación
ROTA 28/48 por veinte anclas rancias. Única decisión visual abierta: el logo WPA aislado;
se recomienda retirarlo conservando el lockup WCP. **No hubo financiamiento** y no se
reabre como duda o pendiente. No hacer commit, push, deploy, subida ni comunicación externa.

## 0. Estado: P1 W33 y P1b publicadas; W34 sólo con PDF oficial

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
Checkpoint material P1b: backend `main@3bd67236`, frontend `main@8490e433`. El cierre
documental y de limpieza posterior llevó el backend vigente a `main@77dc2dcb`; las ramas
P0/P1/P1b se retiraron y el respaldo quedó como etiqueta local. W34 sólo cuando exista su
PDF oficial y los cuatro publicados avancen juntos.

**Limpieza one-shot (2-sep-2026, noche):** ambos repositorios quedan sólo con `main` local y
`origin/main` como rama remota activa; el backend conserva además la referencia remota de
archivo `respaldo/paper/micai-2026-camera-ready`. Cero worktrees adicionales (se retiraron
sin `--force` los dos del par de la
corrida 7). Ramas borradas tras verificar ancestría con `main`, locales con `-d` y remotas con
`push --delete`: backend `ci/skip-budget-ets-legacy`, `docs/p1b-publicada`,
`p0/namespace-e-inmutabilidad-del-sello`, `p1/actualizacion-semanal-2026-w33`,
`p1/release-backend-2026-w33-c6` (sólo local), `p1b/fallback-estatico-w33` y
`p1b/release-backend-c7` (sólo local); frontend `fix/frontend-deudas`,
`p1/actualizacion-semanal-2026-w33` y `p1b/fallback-estatico-w33`. La ref temporal
`auditoria/main` se retiró. El respaldo P0 pre-rebase vive ahora en la etiqueta LOCAL
`archive/p0-pre-rebase-584cf72d-2026-09-02` (no publicada). Se retiraron sólo los temporales
`_trabajo*` y `_release` del scratchpad; sellos,
clon, DVC, PDFs, modelos y evidencia (`planes/p1_2026-w33_2026-09-02/`, con
`limpieza/inventario_antes.txt`) se conservan. Producción sigue en W33; W34, DVC, datos y
despliegue intactos.

Regla gobernante: todos los miembros `published` del registry comparten un corte público
único. Uno faltante, adelantado, atrasado o sin cobertura exacta bloquea el lote completo;
no se publica al resto ni se reduce el conjunto por flags. Obesidad y Anorexia siguen
fuera por lifecycle, pero una promoción futura las somete a la misma paridad. No anticipar
W34: validar primero el PDF oficial y después llevar juntos a todos los publicados.

## 0a. Historial: P0 del flujo semanal

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
  `p1/actualizacion-semanal-2026-w33`, checkpoint material `e8f7ba0a`, abierta como PR
  P1 fusionada (`d7c9c6c2`) y P1b fusionada (`3bd67236`, CI de `main` 33677859434 verde).
- Frontend canónico: `EpiForecast-IMSS-Dashboard`, `main@8490e433` (P1 y P1b publicadas;
  banner estático correcto en producción).
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
