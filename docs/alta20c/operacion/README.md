# Cápsula de la publicación de alta20c (15-nov-2026)

Guiones con los que se preparó la publicación (F4) de los veinte de alta20c: primero los doce controles del dictamen
delegado de Fable (§1), después los tres aceptados y los cinco controles del dictamen complementario (secciones de
abajo). No son código de producción: el CI no los ejecuta. Rutas por omisión de la tanda (historia: esos worktrees ya
se retiraron; ver la nota final): base `/tmp/epiforecast-alta20c-20261114`, worktrees `wt-ctl` (backend) y `wt-fe`
(frontend).

- `consolida_controles12.py`: consolidado de paridad `candidato_con_alta20c_controles12`, sólo añadiendo filas
  sobre `candidato_con_alta10b` (sha256 `be7abfa5…`), prefijo byte-igual y `revisa_consolidado` sin problemas.
- `gen_fichas_alta20c.py`: copia del generador de fichas (plantilla de control `neumonias_j12.html`, semanaMas).
- `postedita_controles12.py`: avisos y notas medidas (valores retirados, picos conservados, reparto por sexo de
  respaldo, semanas en cero, rótulo de helmintiasis, alcance de hepatitis B, autorización delegada). Cada cifra
  se recalcula del raw sellado, del dataset v2 y de la vista, y aborta si no coincide con la cotejada a mano.
- `qa_retiros_controles12.py`: busca, en la ventana del control, acumulados impresos que caen en el boletín
  siguiente (ojo: la transición `2026_sem01` → `2026_sem02` es el cambio de año, no un retiro).
- `coteja_avisos12.py`: valor observado, valor repetido por el control y total nacional de cada aviso.
- `radar_update_controles12.py`: marca los doce como «Control publicado» en el radar vigente.
- `fe_radar_estatico.mjs`: reescribe los `data-radar` estáticos de `boletin.html` con `textosRadar`.
- `fe_regen_rag_list.mjs`: regenera la lista esperada de `test_rag_alcance.mjs` desde el catálogo.

`SHA256SUMS` registra los archivos de esta carpeta.

## Revisión delegada de PUB12 (15-nov-2026)

- `avisos_controles12.py` **sustituye** a la parte de avisos de `postedita_controles12.py` (no volver a correr ésta para
  avisos: reinsertaría el texto anterior). Genera desde los raws sellados, las vistas y `indices/registro.txt` los avisos
  nominales (dictamen §1 y picos heredados, con «conservado» o «retirado» y sus acumulados), la nota general de bajas del
  acumulado y la evidencia del índice posterior a la emisión, en las doce fichas y en `epibot/js/avisos_fuente.js`, que
  leen el EpiBot, la función RAG y el corpus. `--check` falla si algo difiere de lo generado.
  `python avisos_controles12.py --fe <wt-fe> --be <wt-ctl> --indice <base>/indices/registro.txt [--check]`
- `qa_retiros_ventana.py`: barrido sin umbral de bajas del acumulado (misma ventana y mismo criterio de año objetivo); su
  número de bajas por id es el que usa la nota general (242 en total).

## Prueba retrospectiva de los tres aceptados en sus fichas (15-nov-2026)

- `prueba2025.py`: nota con rótulo «Error en la prueba de 2025» desde el `acceptance.json` sellado, localizado por la cadena
  del `release_manifest` del backend (release_id de la vista) y verificado por su sha256; sMAPE nacional y de las series
  frente al control, límites de la regla y la advertencia de que es una métrica retrospectiva sobre semanas de 2025
  ya observadas y no se presenta como desempeño fuera de muestra del pronóstico publicado. Aborta si la cifra
  nacional redondeada no coincide con la cotejada a mano o si el manifiesto no liga.
- `postedita_paratifoidea.py` (ahora con `--be <wt-ctl> --runs <runs>`) y `postedita_aceptados2.py` (ahora con
  `--be <wt-ctl>`) la añaden a paratifoidea (22.7 frente a 27.6) y vulvovaginitis (8.9 frente a 11.4). El mal del pinto
  ya la tenía en «Error alto aunque aceptado» (111.3 frente a 115.8) y no se duplica.
- Reproducción de las tres fichas, byte a byte, en un frontend temporal (copias, no enlaces): `gen_fichas_alta20c.py`
  → `postedita_paratifoidea.py` → `postedita_aceptados2.py` → `picos_heredados.mjs` (`revisa(<fe>, true)`) →
  `avisos_controles12.py`. Runs de las pruebas: `<base>/wt-be/runs`.

## Cinco controles nuevos, revisión focal de su publicación y conteos (15-nov-2026)

- `postedita_controles5.py`: post-edición medida de las fichas de los cinco controles del dictamen complementario
  (coqueluchoide, plaguicidas, tos ferina, síndrome meníngeo, monóxido) sobre la salida de `gen_fichas_alta20c.py`:
  condiciones comunes y por id, «salto de 2025» de tos ferina con sus cifras y rótulo de carga «Cargando el estado…».
  Cadena reproducible: `gen_fichas_alta20c.py` → `postedita_controles5.py` → `avisos_controles12.py` →
  `picos_heredados.mjs` (`revisa(<fe>, true)`) → `avisos_controles12.py` otra vez (idempotente).
- `avisos_controles12.py` cubre ya los diecisiete controles (rezago por id) y, para plaguicidas y monóxido, añade a
  `avisos_fuente.js` la nota D7 «No distingue intención» (estado `alcance`, no se pinta en la ficha) y las cifras de
  retiro que usa la nota de pico heredado.
- `radar_update_paratifoidea.py`, `radar_update_aceptados2.py`, `radar_update_controles5.py`: marcan en el radar vigente
  los releases publicados del registry («Publicada» o «Control publicado»), uno por etapa de la tanda.
- `fe_conteos.py <frontend>`: conteos escritos en las pruebas del frontend desde `publication/catalog.json` y el
  catálogo del dashboard generado.
- `fe_fixtures.py <frontend> <backend>`: listas de las pruebas del frontend que dependen de los releases instalados.

**Rutas por omisión, historia.** Los worktrees `wt-be`, `wt-ctl` y `wt-fe` de `/tmp/epiforecast-alta20c-20261114` se
retiraron tras la publicación; los runs están en el checkout principal (`runs/`) y los respaldos en
`planes/alta20c_2026-11-14/` (`worktrees_ignorados_pre_retiro_20261115`, `git_bundles_20261115*`). Para volver a correr
un guion, pasar rutas explícitas a un checkout de `main` (o restaurar una rama desde los bundles, que fijan el SHA de
cada etapa) y comprobar antes que sus valores cotejados a mano siguen valiendo: no correrlos con las rutas por omisión.
