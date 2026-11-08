# C7.11 — Cinco padecimientos del radar del boletín 42

**Estado al 8-nov-2026:** por orden del autor («incorpora» sobre la lista del radar) se dieron de alta cinco
padecimientos. Tres superaron el gate de 2025 y se publicaron desde sus releases; infecciones
respiratorias agudas (IRA) y gingivitis lo reprobaron. Ese mismo día, con las cifras a la vista, el autor
ordenó publicar su control estacional («ok hazlo»): están publicadas como control, nunca como validadas. El agregado
«Enfermedades infecciosas intestinales» no se incorporó: el radar lo marca como agregado y contiene el
bloque A04, A08-A09 ya incorporado.

| hecho | Intestinales (A04, A08-A09) | Vías urinarias (N30, N34, N39.0) | Úlceras, gastritis y duodenitis (K25-K29) | IRA (J00-J06, J20, J21) | Gingivitis (K05) |
| --- | --- | --- | --- | --- | --- |
| Cuadro y bloque | 4.x, último | 12, último | 13.4, primero | 5.1, primero | 13.3, último |
| Selección | `intestinales_a04_select_c67f5f47030c_435dcf36e477` | `ivu_n39_select_8e6d664f6cc0_b1bcdbd97ab8` | `ulceras_k25_select_adf3471f8685_476e9c38c6a0` | `ira_j00_select_2bfb1505366b_91989f59342e` | `gingivitis_k05_select_1fdc9c357556_3a8918964ab0` |
| Prueba 2025 | `intestinales_a04_benchmark_test_8ce753baf03f_3a8b760e0a27` | `ivu_n39_benchmark_test_54b3bf9e88bb_92509463391f` | `ulceras_k25_benchmark_test_4f733ed43a33_db592521e0de` | `ira_j00_benchmark_test_11d0b11ac60c_476ea7475f4d` | `gingivitis_k05_benchmark_test_b2a6d1a0a37f_4a28a7a32302` |
| sMAPE bases 2025 (control) | 15.0 (15.7) | 10.3 (11.2) | 14.3 (16.0) | 18.8 (14.2) | 20.5 (19.3) |
| sMAPE 111 series (control) | 14.2 (15.0) | 9.4 (9.9) | 13.1 (14.3) | 17.9 (13.5) | 19.5 (17.9) |
| sMAPE nacional (control) | 5.5 (8.7) | 4.4 (5.3) | 4.7 (4.8) | 14.0 (8.8) | 12.8 (8.5) |
| Veredicto | ACEPTADO | ACEPTADO | ACEPTADO | RECHAZADO | RECHAZADO |
| Release | `intestinales_a04_release_8f5baa0a6556` | `ivu_n39_release_7d2b810a3793` | `ulceras_k25_release_9d58ce6ad597` | `ira_j00_release_9669e8caafea` (control) | `gingivitis_k05_release_9a2bcab11a53` (control) |

Política `rolling_cv_v1` con siete motores (sin Prophet); el smoke pasó con ETS y Ridge en los cinco. Origen
2026-W41, 52 semanas, emitidos el 8-nov-2026 entre las 16:15 y las 16:17 UTC. Gate prospectivo 0/4
(W42-W45). A las 16:30 UTC de ese día, la página oficial del boletín listaba como último el 42
(`Boletin-4226.pdf`): el boletín 43 no existía al emitir.

IRA y gingivitis: la selección de 2021-2024 eligió sobre todo ETS y medias de cinco años (IRA: ETS en 26
bases, `seasonal_mean_5y` en 25; gingivitis: ETS en 34), y en 2025 ese portafolio empeoró al control
en los tres ámbitos. Tras el rechazo, `final_selection.csv` pone las 64 bases en `seasonal_naive_lag52`.

## Control de IRA y gingivitis (8-nov-2026)

Orden del autor tras ver las cifras: «ok hazlo» a «¿Publico el control estacional de IRA y gingivitis?».
`acceptance_fallback_run` apunta a los dos runs de prueba rechazados, commiteado antes del `refit`.

| hecho | IRA | Gingivitis |
| --- | --- | --- |
| Refit | `ira_j00_refit_final_9fe0414b00c7_5b4bd4056a06` | `gingivitis_k05_refit_final_9fe0414b00c7_f4154619fa62` |
| Pronóstico | `ira_j00_forecast_h52_5b4bd4056a06_c0e9d9538bad` | `gingivitis_k05_forecast_h52_f4154619fa62_038636600236` |
| Emitido (UTC) | 2026-11-08 20:29:32 | 2026-11-08 20:29:37 |
| Release | `ira_j00_release_9669e8caafea` | `gingivitis_k05_release_9a2bcab11a53` |
| Gate prospectivo | `f31a712e…`, W42-W45 | `6a4ce42b…`, W42-W45 |

Ambos releases llevan `acceptance_outcome: fallback_control` y la vista `caida_al_control` con las cifras
selladas de la tabla de arriba. Candidato y control del gate son idénticos: al llegar a cuatro semanas el
veredicto será `CONTROL_ONLY`, nunca `PASS`. Ninguna superficie dice «validación en curso».
A las 20:43 UTC de ese día la página oficial seguía listando como último el boletín 42
(`Boletin-4226.pdf`): el 43 no existía al emitir.

## Datos

669 boletines (2014_sem01 a 2026_sem42), dos corridas con el mismo sha256 en los cinco. W42 coincide con el
radar del boletín en las 32 entidades (semana, acumulado de hombres y de mujeres). Exclusiones:
`2014_sem01` (cierre anual) en los cinco y `2023_sem45` en gingivitis (renglón de Chiapas alterado en el
PDF, «Chiapas San Luis Potosí» con 11 valores, y camelot sin entidades reconocidas; el periodo se imputa).

El número de bloques vecinos cambia por año (8, 11 o 12 columnas), así que el extractor recorta el primer o
el último bloque por el conteo real de columnas (`first_block_columns`, `last_block_columns`). En
2014_sem28-31 el Cuadro 5.1 imprime «Michoacán *» por una fe de erratas: el extractor quitaba esa fila y
dejaba 31 entidades; ahora retira la llamada de nota.

Caída de 2020 en los cinco, con nivel posterior más bajo en IRA (unos 24 millones anuales en 2014-2019 y
16 a 17 millones en 2022-2025) y en úlceras-gastritis (1.4 millones frente a 0.9). Coincide con la
pandemia; no se midió si es menos enfermedad, menos consulta o menos registro. Los pliegues de 2021-2024 y
la prueba de 2025 quedan dentro del nivel nuevo.

Consolidado W42: `candidato_con_control`, que parte de `candidato_con_radar` (y éste de
`candidato_con_cardio`) con prefijo byte-idéntico; paridad PASS con los dieciséis en (2026, 42). Shards respaldados en `planes/respaldo_shards_2026-11-08/`.
