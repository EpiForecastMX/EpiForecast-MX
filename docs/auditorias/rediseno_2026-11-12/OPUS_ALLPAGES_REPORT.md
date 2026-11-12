# OPUS_ALLPAGES_REPORT — Hito 3: todas las páginas restantes

Implementado sólo en los clones de R (`/private/tmp/epiforecast-redesign-DkByiE`). Sin red, commit,
push, deploy, instalación, servidores ni navegador. `GEMINI_API_KEY` ausente en todas las corridas
(`env -u`). Originales intactos: FE `580d0486`, BE `81bcb828`, `git status` limpio en ambos. Nada está
publicado, integrado ni probado en CI pública.

**Estado: congelado para auditoría Root + Fable**, con **un bloqueo que requiere a Root** (RAG,
§6): el corpus pasa de 577 a 575 chunks y `rag:verify` / `deploy:verify` / `epibot npm run check`
fallan por eso. Todo lo demás pasa.

Digest del código congelado (`evidence/hito3/digest_codigo.json`, sha256 sobre ruta+hash de cada
archivo modificado o nuevo):
- FE: 101 archivos · `81843e16541183e00fe186c46c9c56a72ae40ba97d70011d40619259db6c86c8`
- BE: 19 archivos · `b3dc1520415fe5a532c8b21840660a4d07862f288aaa3eb50870479a4e415acb`

## 1. Alcance completado

Inventario (`evidence/hito3/inventario_rutas.json`, `tools/inventario_hito3.py`): **62/62 rutas
migradas** (2 en el hito 1, 35 en el hito 2, 25 en el hito 3); **0 pendientes**. Cada ruta registra
canónica/alias, familia, variante, página actual, generador del HTML, excepción, meta CSP, idioma del
documento y del chrome, y hojas cargadas.

| Familia (shell.config.json) | Páginas | Página actual |
|---|---|---|
| `editorial` | Avance1, Avance2, auditoría, bitácora, comparación de modelos, comparación de rondas, conclusiones, construcción del dashboard, ficha Prophet, hiperparámetros, metodología Dengue, pipeline EDA, rechazados, referencias, resultados, validación semanal | ninguna |
| `noticias` | novedades.html | Noticias, `page` |
| `congresos` | calass, helix, future_health, micai.html | Congresos, `section` (botón y rótulo móvil con `data-current`; el enlace a la propia página, si está en el grupo, lleva `aria-current="page"`) |
| `micrositio-congreso` (variante `micrositio`) | wcp2026, micai2026, micai2026-guion | Congresos, `section` |
| `archivo` | EpiDashboard-tableau.html | Dashboard, `section` |

- **Sistema común**: `assets/site/site.css` + `editorial.css` nuevo (claro, sin ningún `!important`, la
  única mención está en un comentario). Mapea los tokens del template viejo (`--bg-*`, `--text-*`,
  `--cream`, `--teal`…) al sistema claro, `min-width: 0` en los contenedores, tablas con scroll
  contenido (`.table-wrapper/.table-wrap/.table-scroll`), controles del contenido con 44 px de alto,
  acento serif en `h1/h2 em`. La paleta oscura literal en `<style>`, `style=""` y `<script>` se traduce
  a la clara (AA: muted `#53675e`/`#5b6f66`, serie azul `#2f5f9e`, etc.).
- **Retirado de las 22 páginas editoriales, de noticias, de congresos y de archivo**: barra vieja
  `nav.nav#nav`, menú móvil `#navMobile`, Google Fonts, `editorial.css?v=1` y las reglas CSS de la
  barra vieja. Los selectores de elemento `nav/header/footer` del CSS propio se acotan con
  `:not(.site-…)` para que no alcancen al chrome.
- **Contenido**: `tools/texto_hito3.py` compara el texto visible de HEAD con el del clon quitando sólo el
  chrome: **25 de 25 iguales** (`evidence/hito3/texto_fase3.json`). Los 12 pies que forman parte del
  corpus del EpiBot quedan como colofón visible (`div.legacy-colophon`), con texto **idéntico** al pie
  de HEAD. En las demás el pie viejo se retira, porque su contenido lo cubre el pie común.
  Las cifras protegidas no cambian: `53.2`/`0.387`/`267 de 288` no aparecen en el HTML de la raíz ni en
  HEAD ni en el clon (viven en Reports/micai2026, sellado). Aparecen 2 «333» más en `novedades.html`, y
  son literales de `news.json` dentro del archivo estático.
- **Idioma**: los documentos conservan su `lang` (los 3 micrositios siguen en `en`); la cabecera y el
  pie comunes llevan `lang="es"` dentro del documento en inglés.
- **Accesibilidad estructural**: hay enlace de salto a un id que existe en cada página (comprobado
  por test), el chrome es compatible con CSP (sin `on*=`, `style=` ni `<script>`), el menú móvil
  declara `aria-expanded` y, sin JS, el chrome sigue siendo estático. Contraste y foco medidos en
  pantalla: los mide Root (§8).

## 2. Noticias

- `novedades.html` lleva el **archivo estático completo** entre `<!-- noticias:archivo:start/end -->`
  dentro de `#newsGrid`: 35 notas, una por item de `news.json`, en orden, con el marcado de la función
  `ih` de la página y el **id estable de `nota-ancla.js`** (`tabindex="-1"`). Sin JS la página no queda
  vacía.
- El JS de la página carga `assets/site/nota-ancla.js?v=1` y **repinta con los mismos id**. Al llegar con
  un ancla (`novedades.html#nota-…`), le da scroll y foco. Si el fetch falla (503 o sin red) o falta
  `EpiNotas`, **conserva el archivo estático** (probado).
- Los 3 destacados estáticos de la portada apuntan, en orden, a las 3 primeras anclas del archivo. La
  ruta antigua `#hero` vivía en el pie viejo de novedades («Inicio», copiado de la portada) y ya no
  existe; el alias `index.html#hero` sigue en la portada.
- **Filtros, búsqueda y paginación**: HEAD no los tenía, así que no hay nada que conservar.
- **Productor**: `build_news_weekly.py` (BE) escribe el archivo en `bump_static_html` (refresh semanal)
  y en el modo nuevo `--solo-estaticos` (banner de portada + archivo desde el `news.json` vigente, sin
  leer datos ni red). Sobre la plantilla vieja (sin marcadores) no hace nada; con dos bloques falla.
  Es idempotente.

## 3. Productores reales del backend

Transformador único `src/epiforecast/publication/editorial_chrome.py`. Es el mismo algoritmo que
migró el frontend (`tools/migra_editoriales.py`), así que una regeneración no puede reintroducir la
barra vieja ni el tema oscuro. `publica_editorial(html, dashboard, exigir=…)` decide según el caso:

- **Con fragmentos** (`--dashboard` o `$EPIFORECAST_DASHBOARD`): adapta y estampa con
  `site_shell.estampa`, y sincroniza `?v=` con `assets` del manifiesto.
- **Falla cerrado** (`ShellError`) si se exige (el generador escribe en un dashboard) o si la variable
  de entorno apunta a un dashboard sin `shell.fragments.json`.
- **Sin dashboard** (copia local del backend): adapta y deja los marcadores vacíos, y avisa por stderr.
  `site_shell.mjs --check` rechazaría esa página si llegara al sitio.
- **Idempotente**: sobre una página ya migrada sólo re-estampa. Re-adaptar las 22 páginas del FE con
  sus fragmentos no cambia un byte (probado).

| Productor | Cambio | Regeneración real (temporal R `work/regen/`) |
|---|---|---|
| `scripts/genera_validacion_semanal.py` (refresh semanal) | `--dashboard` opcional; por defecto `$EPIFORECAST_DASHBOARD`, que exporta `actualiza_semanal.sh` | Con `reports/ProdDetails/seguimiento_post_corte.csv` real y `--out` temporal: **idéntica byte a byte a `validacion_semanal.html` del FE salvo el sello «Generado:»**. Idempotente. Los hooks no tienen nada que normalizar. |
| `scripts/genera_reporte.py` + `scripts/templates/reporte_resultados.tmpl.html` | Plantilla migrada (los tokens `__…__` se conservan); `--dashboard` exige el chrome; `--local` nuevo para el confinamiento | Con la tabla 333 y producción Dengue reales: **idéntica byte a byte a `reporte_resultados.html` del FE salvo la fecha de generación** (09/11 → 12/11). La copia local es igual a la del dashboard. Idempotente. |
| `scripts/genera_bitacora.py` | `main(argv)` con `--out` y `--dashboard`; retira su barra vieja `<nav>` con logo | Generada en temporal: chrome común, colofón y `editorial.css?v=3`. Ver la discrepancia D1. |
| `epiforecast.visualization.comparison_report` | La escritura pasa por `publica_editorial` | Test con CSV de modelos en `tmp_path`: chrome común, sin fuentes externas. Ver D1. |

`site_shell.mjs --check` ahora exige que **cada página con `productor.chrome`** (validación,
resultados, bitácora y comparación) tenga una cabecera y un pie renderizados **idénticos** al
fragmento de su familia, que es lo que estampa el backend. La portada (`productor.chrome: false`) sí
difiere del proxy (`href="#congresos"`): hay un test que lo afirma, y declararla `chrome: true` hace
fallar al generador. Esta guarda detectó en esta misma ronda una regresión real: la marca de página
actual en el pie de `reporte_resultados.html` se corrigió antes de congelar.

## 4. Fichas: estado desde la vista

- `assets/site/estado-ficha.js` (v1) aplica la regla de `statusFromView` del catálogo con los rótulos
  de `STATUS_SHORT` de la Galería. La regla:
  - `PASS` → `pass`.
  - `CONTROL_ONLY` → `control`.
  - `INCOMPLETE` → `control` si la etiqueta publicada dice «control estacional»; si no, `pending`.
  - FAIL o un veredicto desconocido no reciben color.

  El script pone `data-verdict` (literal) y `data-publication-kind` en `#statusCard`, y muestra el
  rótulo corto explícito (`#pubKind`) seguido del detalle literal de la etiqueta. No cambia criterios,
  veredictos ni datos.
- Las 31 fichas usan `EpiEstadoFicha.aplica($('statusCard'), V)`. Se retiró la clase estática
  `body.disease-control`. `disease.css` (v `20261112h3`) colorea con los mismos colores que las
  insignias del Dashboard:
  - superada: verde
  - en curso: azul `#eef3fa/#24497a`
  - control: ocre
  - cargando, error o desconocido: neutro
- Resultado sobre las 31 vistas publicadas, idéntico al catálogo: 1 pass (obesidad), 12 control
  (anorexia, próstata… todas con veredicto `INCOMPLETE` y caída al control) y 18 pending (asma…).
- **Productor**: no existe plantilla en el backend; las fichas se dan de alta copiando una ficha base,
  y la base ya lleva la llamada. Está documentado en el README del FE.

## 5. Caché y manifiesto

- Los `assets` de `shell.config.json` son la única versión por recurso común en todas las páginas de la
  raíz y de Reports (test): `site.css` 4, `site-nav.js` 3, `editorial.css` 3, `estado-ficha.js` 1 y
  `nota-ancla.js` 1. EpiBot carga los compartidos con `../` sin `?v` y Netlify los revalida
  (`must-revalidate` en `/assets/site/*`). `cadena_cache` no se tocó; su test BE corre ahora con fixture.
- Validación de la config: rechaza `current`/`currentKind` por página, `currentKind` inválido,
  `current` desconocido, páginas repetidas, `productor` mal formado y productores que estampan fuera de
  la raíz. Las familias `noticias` y `congresos` son explícitas.
- `node scripts/site_shell.mjs --check` → `63 archivos al día` (62 rutas + fragmentos).

## 6. RAG: el bloqueo que requiere a Root

- `work/corpus_diff.mjs` (HEAD reconstruido frente al clon): **575 de 577 chunks idénticos** en id y
  texto. Faltan `Avance1.Equipo01#0` y `Avance2_Equipo01#0` (índice: `6538c018090e`,
  `b3b5347b06c0`).
- Causa (`evidence/hito3/rag_chunks_retirados.json`): esos dos chunks eran **sólo la barra vieja,
  duplicada (escritorio y móvil), más los controles del visor PDF** («◀ — / — ▶ − + ↔ Ajustar
  Cargando documento…»). Las páginas Avance no tienen otro texto HTML: su contenido es el PDF. Sin la
  barra, el resto no llega a `MIN_WORDS = 25` y el chunk desaparece.
- **No lo maquillé**:
  - no conservé la barra vieja;
  - no añadí texto oculto ni colofón artificial;
  - no apunté el corpus a copias históricas;
  - no toqué `corpus.mjs` para esto;
  - no ejecuté `rag:build`.
- Consecuencias en este momento:
  - `rag:verify`: rc=1 («count 577 ≠ 575», 2 chunks extra).
  - `deploy:verify`: `rag:ci` FAIL.
  - `epibot npm run check`: 354/355, el que falla es `test_micai_current` «covers the new corpus»; por
    eso `check` no llega a `rag:verify`, que corrí por separado.
  - **El gate `rag` de `config/publication/politica_censo.json` del refresh semanal también fallaría**
    si el FE se integra sin resolverlo.
- **Decisión que pido a Root**: un `rag:build` coordinado (con clave, en su entorno). `buildIndex`
  reutiliza embeddings por contenido, así que debería resultar en «575 reusados, 0 nuevos»: una poda,
  sin re-embeber nada. Se integra en la misma ventana que el FE. Alternativa: aceptar la pérdida como
  excepción documentada y no integrar las páginas Avance hasta decidir.

## 7. Discrepancias y decisiones

- **D1. Bitácora y comparación de modelos no reproducen la página publicada.** Sus páginas del FE se
  editaron a mano desde junio. En HEAD, el generador de la bitácora difiere en 503 líneas de la
  página, y la comparación publicada retiró el ranking que su generador aún emite. Ninguno de los dos
  escribe en el dashboard (sólo `reports/forecasts/`). Lo que sí garantizo es la paridad del chrome
  (fragmento de la familia, comprobado en `--check`) y que no regresan el tema ni la barra viejos. No
  reescribí su contenido científico para igualarlo.
- **D2.** `micai2026-guion.html` conserva su `<style>` y sus fuentes Atkinson/Plex: es la excepción de
  identidad académica del micrositio. Encontré que `site.css` iba **después** de su `<style>` y le pisaba
  `--ink/--muted/--line` y el modo oscuro. Lo moví **antes**: el diff del archivo frente a HEAD son
  sólo inserciones del chrome.
- **D3.** `micai.html` (alias 301) cambió su destino de salto a `#main`, que existe en ambos lados del
  alias. El auditor resuelve la ancla en el destino y con `#contenido` contaba un falso roto.
- **D4.** `tools/migra_editoriales.py --check` reproduce desde HEAD 22 de 25 páginas. Las otras 3
  tienen diferencias esperadas:
  - `novedades.html`: el archivo estático.
  - `micai.html`: D3.
  - `calass.html`: `aria-current="page"` en su enlace del grupo Congresos; `calass` no tiene productor.
- **D5. Tests existentes ajustados (ninguno debilitado).**
  - `home.test`: «tableau contiene `index.html#pipeline`» pasa a ser «todo enlace a
    `index.html#x` de las 62 rutas apunta a un id existente», porque ese enlace vivía en la barra
    vieja retirada.
  - `wcp.test`: separaba `?` pero no `#`, y trataba `index.html#congresos` como archivo; ahora
    comprueba el archivo **y** el id.
  - `fichas.test`: «clase estática = catálogo» se sustituye por un test más estricto (vista → atributos
    = `statusFromView`, en las 31).
  - `site_shell`/`herramientas`: aceptan `lang="es"` en la cabecera.
- **D6.** Encontré y retiré `EpiForecast-IMSS-Dashboard/work/corpus_head/`, una copia temporal mía
  dentro del clon. Antes comprobé que era un subconjunto byte a byte de `R/work/corpus_head`. Estaba
  sin rastrear y ensuciaba la auditoría de enlaces.
- **Scripts viejos conservados** (contadores, revelado, toc): siguen en las páginas, pero sus selectores
  (`.nav-group-toggle`, `.nav-hamburger`, clase `show`/`scrolled`) no coinciden con el shell, y ni
  `site.css` ni `site-nav.js` leen esas clases. Hay un test que lo vigila. Ninguna página tiene un botón
  que invoque `toggleMobileNav`.
- **EPI**: la limpieza del hito 2 está completa. No hice cambios nuevos en EPI en este hito. La
  convivencia del botón «Menú» del sitio con el botón de panel de EPI a 360 px no se puede validar sin
  navegador: queda como hook de QA. `obesidad_galeria.js` sigue como compatibilidad documentada.

## 8. Excepciones acotadas

- `micrositio-congreso` (wcp2026, micai2026, micai2026-guion): llevan chrome común (cabecera
  `site-header--static`, no fija, y pie). Conservan sus hojas propias (`wcp.css`, `micai.css`, el
  `<style>` del guion), que van después de `site.css`; el cuerpo, el póster y el visor; y `lang="en"`.
  Reports/wcp2026/** y Reports/micai2026/** no se tocaron.
- `micai.html`: alias 301 → micai2026.html (Netlify), conservado; el archivo lleva chrome por si se
  abre directo.
- `EpiDashboard-tableau.html`: rotulado como histórico (corte W31) en 12 sitios. La carga diferida, el
  consentimiento y las acciones no se tocaron (el texto visible es igual al de HEAD).
- `epibot/index.html`: variante app, sin pie.

## 9. Pruebas (evidencia en `evidence/hito3/*.txt`)

| Suite | Resultado |
|---|---|
| FE `npm run test:site` | **99/99**, 0 skips. Incluye `noticias.test` nuevo (5) y `site_shell` (20) |
| FE `npm run test:dashboard` | 131/131 |
| FE `npm run test:boletin` | 22/22 |
| FE `npm run check:wcp` | 27/27 |
| EPI `cifras:test` / `cifras:verify` | ✔ / ✔ («banner estático de novedades alineado con news.json») |
| EPI `npm run check` | 354/355: el fallo es el de §6 |
| EPI `test:candidate` | pasa (2 skips, los mismos que en el hito 2) |
| EPI `rag:verify` / `deploy:verify` | **FAIL** por §6 (`cifras:verify` PASS dentro de deploy) |
| BE pytest (publication, news, hero, generadores_out, validación ×2, reporte, visualization, seguimiento, dengue) | **1173 passed, 227 skipped**. Los skips son preexistentes, en archivos no tocados (compiler_shards 20, readiness 72, status 12, tableau 2). `test_site_shell.py` ya no tiene ningún skip: 7 tests con fixture autocontenido |
| BE `test_editorial_chrome.py` (nuevo) | 11 tests: transformador, idempotencia, contenido y cifras, paleta, fail-closed, y los 4 productores reales (validación con CSV real, reporte con plantilla real, bitácora `main`, comparación con CSV de fixture) |
| ruff check / ruff format --check (12 archivos) / mypy de los módulos de publicación | limpios. Los errores mypy de `scripts/genera_*` son los mismos que en HEAD (33 y 1) |
| `audit_links.py` | **0 problemas** en 62 páginas, frente a 2 en HEAD (tableau→`index#pipeline` y novedades→`#hero`, ambos resueltos) |

**Fixture BE** `tests/fixtures/site_shell/`: copia literal del FE (config, fragmentos, asma_j45,
reporte_resultados y la cabecera de epibot), con la misma disposición que un dashboard y un README que
explica cómo regenerarla. Los tests comprueban dos cosas:
- la página real es el estampado de su versión vaciada;
- el `aria-current` de cada familia es el que declara la config.

La paridad con el FE vivo la vigila el propio FE (`--check` + test por productor). No añadí ningún
test que dependa del repo hermano.

## 10. Integridad de datos

- `tools/huellas.py` frente a `evidence/fase0`: ningún cambio en `publication/`, `Reports/publication/`,
  `Reports/wcp2026/**`, `Reports/micai2026/**`, PDFs, PNGs, `news.json`, `knowledge.json`,
  `zoom_series.json`, `rag_index.json`, `hero_series.json` ni en `assets/dashboard/catalog.json`
  (`d498d2f6…`, igual a fase0 y al original).
- BE: los 9 tracked modificados son código, plantilla o tests (`build_hero_series.py` y su test vienen del hito 1; `build_news_weekly.py` y su test, de los hitos 1 y 3). No cambió ningún dato,
  `reports/` ni modelo. Las regeneraciones escribieron sólo en `R/work/regen/`.
- No se ejecutó `rag:build`, ninguna ingestión ni nada con red.

## 11. Para integrar (Root)

1. Resolver primero el RAG (§6), en la misma ventana que el FE.
2. Rastrear en git `assets/site/shell.config.json`, `shell.fragments.json` y `estado-ficha.js`. El
   staging semanal se materializa con `git archive` de `dashboard/`, y sin los fragmentos rastreados la
   validación semanal falla cerrado.
3. Confirmar con `politica_censo.json` el trato de los `.json` del shell como superficie. El hito 3 no
   añade rutas `.html` ni `.json` nuevas; los `.json` del shell vienen de los hitos 1 y 2.
4. Revertir en pareja, primero BE y después FE: `evidence/REVERSION_PAREADA.md`, sección «Hito 3».

## 12. Hooks de QA visual (Root, con navegador)

- **Noticias** (móvil y escritorio): las 35 notas sin JS; llegada a `novedades.html#nota-2026-11-09-el-asma…`
  desde la portada con foco y scroll; simular un 503 de `news.json`.
- **Editoriales con tabla** (reporte_resultados, hiperparametros, comparacion_rondas): scroll de la
  tabla contenido a 360 px, sin scroll horizontal de la página; heros claros; colofón visible.
- **Avance1/2**: el visor PDF bajo el chrome común.
- **Congresos**: la cabecera estática de WCP/MICAI no choca con `.site-header` propio; el guion con modo
  oscuro del sistema (su `:root` gana); los menús Congresos y Más abren y cierran con teclado y Escape.
- **Fichas**: asma en azul «Validación prospectiva en curso», anorexia en ocre «Control estacional
  publicado», obesidad en verde, error de red en neutro.
- **EPI a 360 px**: el botón «Menú» del sitio frente al botón de panel; drawer por puntero y teclado.
- **Tableau**: la carga diferida y el consentimiento siguen funcionando.
- **Contraste y objetivos de 44 px**: los cuento como «no medido» hasta tener capturas, no como
  aprobado.
