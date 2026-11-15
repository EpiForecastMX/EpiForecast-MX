# Cápsula de la publicación de los doce controles de alta20c (15-nov-2026)

Guiones con los que se preparó la publicación (F4) de los doce controles autorizados por el dictamen delegado de
Fable (§1). No son código de producción: el CI no los ejecuta. Rutas por omisión de la tanda: base
`/tmp/epiforecast-alta20c-20261114`, worktrees `wt-ctl` (backend) y `wt-fe` (frontend).

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
  frente al control, límites de la regla y la advertencia de que no es desempeño fuera de muestra. Aborta si la cifra
  nacional redondeada no coincide con la cotejada a mano o si el manifiesto no liga.
- `postedita_paratifoidea.py` (ahora con `--be <wt-ctl> --runs <runs>`) y `postedita_aceptados2.py` (ahora con
  `--be <wt-ctl>`) la añaden a paratifoidea (22.7 frente a 27.6) y vulvovaginitis (8.9 frente a 11.4). El mal del pinto
  ya la tenía en «Error alto aunque aceptado» (111.3 frente a 115.8) y no se duplica.
- Reproducción de las tres fichas, byte a byte, en un frontend temporal (copias, no enlaces): `gen_fichas_alta20c.py`
  → `postedita_paratifoidea.py` → `postedita_aceptados2.py` → `picos_heredados.mjs` (`revisa(<fe>, true)`) →
  `avisos_controles12.py`. Runs de las pruebas: `<base>/wt-be/runs`.
