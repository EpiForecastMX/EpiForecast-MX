# OPUS_ALLPAGES_FIX_REPORT — cierre visual de todas las páginas

Todo se hizo en los clones de R. No hubo red, commit, push, deploy, instalación, subagentes ni
servidores propios. Las pruebas de navegador usaron el servidor de Root que ya estaba levantado
(`127.0.0.1:8765`, que sirve el clon) y el original (`8766`) sólo para comparar. `GEMINI_API_KEY` no
estuvo definida en ninguna corrida. Los originales siguen limpios (FE `580d0486`, BE `81bcb828`,
`git status` vacío).

**Estado: congelado, en espera de Root + Fable.** Los gates de EPI no están en verde, y no lo
afirmo: `rag:verify`, `npm run check` (354/355) y `deploy:verify` fallan sólo por el índice 577 ≠
corpus 575. Eso lo resuelve la poda offline que hará Root (`READY_FOR_RAG.md`).

## Código congelado

`evidence/fix_allpages/digest_codigo.json` (sha256 de «ruta\tsha256» de cada archivo modificado o
nuevo respecto a HEAD):

- FE (101 archivos): `0a1943e78005349e8f5ec0f454dce29adb40c405b5e6fc150a3dc92ba92f90f7`
- BE (22 archivos): `0565abecc20301b944776beed901fb00c6b42c5b222c92d2bcb366f5755f81fb`
- Recibo de navegador de Root (`receipt.mjs`), idéntico en las 6 corridas finales:
  `539e1e453b8784065a4219897869545e51c9bed9d1b27c2c82d9f8c8a4a9bf24`

## Correcciones

Todo lo de las páginas pasa por el transformador único
`src/epiforecast/publication/editorial_chrome.py`. Las 22 páginas se regeneraron con
`tools/migra_editoriales.py` y `scripts/site_shell.mjs` (`work/fix/regen.sh`):

- 21 se regeneran desde HEAD.
- `novedades.html` se re-adapta desde su versión actual, para conservar el archivo y su JS.

`migra --check` sólo marca `calass.html`, que es lo esperado: `site_shell.mjs` le pone
`aria-current`. No hay `!important` nuevo ni contenido oculto.

| # | Causa | Corrección |
|---|---|---|
| Fable 10 | El parser `_bloques` pegaba al selector o al `@media` siguiente un comentario precedido de espacio. Resultado: `@media` sin recorrer, `header{}` sin acotar, comentarios reescritos y un riesgo de borrar reglas. | Espacios y comentarios van como piezas propias. Las llaves dentro de comentarios o cadenas no cuentan. `@import …;` se trata bien. Los selectores contradictorios (`footer:not(.site-footer).site-footer`) se retiran en vez de quedar muertos. |
| Fable 11 | El colofón conservaba la clase `site-footer`. | El colofón ya no lleva `site-footer` ni `footer`: 12 colofones `class="legacy-colophon"`. |
| Fable 1 / Root 3 | `.editorial-page a`, y el `a{…!important}` / `p{…!important}` de novedades, llegaban al pie común (ratio 1). | Los enlaces de contenido usan `:where(.editorial-page) a`. El transformador acota los selectores sólo de tipo (`a`, `p`, `*`…) con `:not(:where(.site-header, .site-footer) *)`: misma especificidad, ningún efecto en el chrome. `site.css` aísla el pie y la marca de la cabecera con `footer.site-footer …`. |
| Fable 2 | El «MX» del pie tenía ratio 1.46. | `footer.site-footer .site-brand__mx` pasa a `--brand-gold`. Afecta a todas las rutas. |
| Fable 3 / Root 1 | En Avance, las barras locales eran pegajosas en `top:0` con z 100/90 y tapaban el menú Congresos. Otras barras sumaban los 64/56 px de la barra fija vieja. | `site-nav.js` v4 publica `--site-header-h` en `:root` (68 px si la cabecera es fija, 0 si no). El transformador coloca las barras pegajosas propias (no las de tabla) en `calc(var(--site-header-h)+X)` y comprime su z-index a 21–29, por debajo de la cabecera (50/30), conservando el orden entre ellas. En los visores PDF, la barra del documento se desplaza con la página y la del visor queda fija justo bajo la cabecera, para que no se solapen. |
| Fable 4 | La carga y el error de Avance quedaban en blanco sobre claro. | `.state-msg` pasa a `--body` y el spinner a `--line`/`--green`. Probado con un 503 del PDF real: 2/2. |
| Fable 5 / Root 4 | Los héroes eran híbridos: `#1a2844`, `#1B1733`, glows y texto blanco. | `:is(.hero,.header,.dash-hero)` se aclara sin `::before/::after` y sin `text-shadow`. La malla decorativa de Tableau se retira. Los degradados oscuros se mapean en la paleta. |
| Fable 6 / Root 4 | Pasteles para fondo oscuro, sintaxis de código y bloques `.code-block` oscuros. | Se añaden a `PALETA_HEX` con la misma semántica y sin fundir series: Ensemble `#c2410c` ≠ NB-GLM; LightGBM `#3d6b1f` ≠ DeepAR. `.code-block` pasa a claro. Los tokens oscuros o «crema» usados como fondo pasan a `--tint`, sólo en la propiedad `background`. `color-scheme:dark` → `light`. Rondas, pipeline, rechazados, hiperparámetros y ficha Prophet quedan corregidos. Las insignias en línea con blanco por debajo de 4.5 pasan a tinta, conservando el fondo: Ensemble 2.79 → 7+. |
| Fable 7 / Root 3 | Auditoría tenía 64 px vacíos por el `body{padding-top:64px}` heredado. | El transformador lo retira. La cabecera queda en top 0 en 124/124 renders. |
| Fable 8 / Root 2 | Tablas sueltas, código, rejillas en línea `1fr 1fr` (columnas de 25 px) e identificadores largos desbordaban. | Las tablas sin contenedor se envuelven en `div.tabla-desplazable`, con scroll local. Las rejillas en línea de N columnas iguales pasan a `auto-fit/minmax(min(100%,max(12rem,…)))`. Además: `overflow-wrap` en el texto y el código en línea, `min-width:0` de baja especificidad, `.threshold` envuelve y `.edl-headline` corta palabras con guion. Nada se oculta ni se reduce. |
| Fable 9 / Root 5 | Faltaba `novedades.html#hero`. | Alias en la cabecera real del archivo: `section#archivo > div#hero`, con fecha, H1 «Novedades» y entradilla. Se conserva `#archivo`. Se quitó el enlace de salto viejo duplicado. |
| Fable 12 / Root 6 | En EPI había tres iconos de hamburguesa y dos manejadores del cajón (en línea y en `ux.js`). | El panel lleva el rótulo visible «Herramientas» con icono de panel. El compositor usa una bombilla. Un solo manejador en `ux.js` (v3) cubre abrir/cerrar, capa, Escape, foco, trampa de Tab, acciones rápidas y cierre en móvil. `shell.css` v5. |
| Root 7 | Censo: las 2 superficies JSON del shell no estaban declaradas. | Están añadidas exactamente a `politica_censo.json`, con la prueba `test_la_politica_censa_las_superficies_json_del_shell_comun`, que además comprueba que sigue fallando cerrado. La deuda previa (434 sobrantes y `bento.json`) queda en `docs/DEUDAS_VIGENTES.md`; no se reconcilió. |
| Root 8 | Plantilla de `genera_reporte`. | Se regeneró desde HEAD con el mismo algoritmo (conserva los 8 tokens `__…__`). Se refrescó el fixture BE y su README (ahora es copia literal e idéntica del FE). |

Versiones con caché:

- `site.css` 5, `site-nav.js` 4 y `editorial.css` 4 en las 61 páginas.
- EPI `ux.js?v=3` y `shell.css?v=5`, en la cadena real (las versiones difieren de HEAD).

## Pruebas (evidencia en `evidence/fix_allpages/`)

| Suite | Resultado |
|---|---|
| Navegación de Root, 124 renders (con el scroll de Avance, sin forzar el clic) | **124/124** |
| Responsive de Root (360, reflujo a 640 y texto al 200 %) | **60/60**: scrollWidth igual al viewport y sin recortes |
| Contraste profundo de Root (72 renders, 29 584 textos) | **4 señalamientos**, todos en `wcp2026.html` (4.44): vienen del `Reports/wcp2026/wcp.css` sellado, existían igual en el original y no se tocaron |
| Flujos editoriales de Root (arnés actualizado por Root a las 05:02) | **8/8**: 35 notas sin JS y con fallo de red, `#hero`, WCP, MICAI, error de PDF ×2, y alias 301 configurado |
| Core flows de Root | **12/12**, incluido EPI móvil (cajón, foco, Escape, consultas) |
| `work/fix/chrome_top.mjs` | 124/124: cabecera en top 0, enlaces del pie `#fff`, MX dorado, ningún colofón como pie |
| FE `test:site` / `test:dashboard` / `test:boletin` / `check:wcp` | 103 / 131 / 22 / 27, sin fallos ni skips. `site_shell --check`: 63 al día |
| EPI `cifras:test`, `cifras:verify`, `test:candidate`, `npm test` | PASS (80 + 2 skips ya existentes), 616/616 |
| EPI unitarias | 354/355 (falla el RAG conocido) |
| BE pytest (publicación, noticias, hero, generadores, validación, reporte, visualización, seguimiento, dengue) | **1214 passed, 227 skipped** (los mismos skips de antes). Incluye 8 pruebas nuevas del transformador con CSS real y la prueba de censo |
| BE `ruff check`, `ruff format --check` (src, tests, scripts) y `mypy src` | Limpios |

Regeneraciones reales en `work/fix/regen/`:

- **Reporte de resultados:** sale idéntico a la página del FE salvo la fecha, y la copia local es
  igual a la del dashboard.
- **Validación semanal:** con el CSV real, sale idéntica salvo el sello «Generado», y es idempotente.
- **Noticias:** `build_news_weekly --solo-estaticos` no produce cambios.
- **Texto visible frente a HEAD:** 24/25 páginas iguales. En `novedades.html` sólo falta el enlace de
  salto viejo duplicado.
- **Datos:** las huellas no cambian, incluido `catalog.json` (`d498d2f6…`). En el BE sólo cambia
  `politica_censo.json`.

RAG: 575 chunks con id y texto idénticos. Faltan sólo los 2 chunks de Avance ya acordados, sin deriva
nueva.

## Límites concretos

- No ejecuté la poda RAG ni los gates EPI finales: están en manos de Root, por acuerdo con Fable.
- La medición de contraste es la de Root: extremos de los degradados, y los fondos con imagen quedan
  como desconocidos. No es una certificación WCAG.
- Quedan sin tocar:
  - el `wcp.css` sellado (4.44);
  - los avisos de Tableau, que son del proveedor;
  - el contenido de la bitácora y de la comparación de modelos (D1).
- Root debe correr `make test-fast` completo y `revisa_universos` sobre el árbol integrado.
- Hay que revertir en pareja: se añadió una sección a `evidence/REVERSION_PAREADA.md`.
