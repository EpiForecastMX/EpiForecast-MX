# C7.12 — Cánceres del boletín 42

**Estado al 8-nov-2026.** El autor ordenó «publica todos los cancer». El Cuadro 15 (Displasias y Neoplasias)
y los siguientes traen 17 tumores malignos; sólo dos tienen historia desde 2013:

| grupo | padecimientos | historia | situación |
| --- | --- | --- | --- |
| Mama (C50) | 1 | 2013-W05 a hoy, con sexo | publicado con el control estacional |
| Cuello del útero (C53) | 1 | 2013-W05 a hoy, sin desglose por sexo | publicado: superó el gate de 2025 con 32 bases sin sexo |
| Pulmón, estómago, colon y recto, hígado, linfomas, leucemia, esófago, páncreas, SNC, huesos, riñón, próstata, cuerpo del útero, ovario | 15 | desde 2023-W01 | `rolling_cv_historia_corta_2023_v1`: los 10 aceptados están publicados («publica», 8-nov-2026) y los 5 rechazados, con el control («autorizo») |

## Tumor maligno de la mama (C50)

Cuadro 15, primer bloque (Sem, H, M, año anterior; 7 u 8 columnas en total). 666 de 669 boletines; dos
corridas con el mismo sha256 (`7b3b616c…`). W42 coincide con el radar en las 32 entidades; contra el bloque
vecino (cuello del útero) sólo 1 de 32 semanas coincide (522 frente a 74 casos nacionales). Exclusiones:
`2014_sem01` (cierre anual) y `2014_sem07`/`2014_sem08` con `keep_period`: una nota editorial sobre
tumor maligno de mama en hombres precede al cuadro y el extractor toma la primera página con las anclas.

Política `rolling_cv_baja_incidencia_v1` (cinco motores estacionales): las series de hombres son casi nulas.

| hecho | valor |
| --- | --- |
| Dataset | `cancer_mama_c50_2be16e7b2c1c` |
| Benchmark | `cancer_mama_c50_benchmark_full_6c746b74612e` |
| Selección | `cancer_mama_c50_select_6c746b74612e_44653f03f90b` (medianas y medias de 3 y 5 años) |
| Prueba 2025 | `cancer_mama_c50_benchmark_test_e44ce18e1b64_0e469c4fcc08` |
| sMAPE bases / 111 / nacional | 45.5 / 47.4 / 16.0, control 51.6 / 54.1 / 11.9 |
| Veredicto | RECHAZADO en el nacional (+34 %) |
| Release | `cancer_mama_c50_release_ee47f3dfc962` (control) |
| Emitido | 2026-11-08 21:47:50 UTC; a las 21:51 UTC gob.mx seguía listando el boletín 42 |

Con las cifras a la vista, el autor ordenó publicar el control. Gate 0/4 (W42-W45); al completar será
`CONTROL_ONLY`. Consolidado W42 `candidato_con_cancer`: paridad PASS con los diecisiete.

## Padecimientos sin desglose por sexo y cuello del útero (C53)

El autor eligió el refactor completo («2»): el runner ya no asume 64 bases. El registry declara
`sex_breakdown: false` cuando el boletín sólo da el total; `SexScheme` (`epi_dataset_spec`) fija la
partición y `sex_scheme.py` la consulta desde el registry o la infiere de un frame. Sin desglose, la
base es el total reconciliado de cada entidad como serie «general» con la exposición total del CPV:
32 bases, 4 regiones, 1 nacional, 37 productos. Ningún módulo inventa hombres ni mujeres. Con
desglose, el dataset de vías urinarias sale byte a byte igual al publicado (`ivu_n39_0683429134d9`),
y la suite completa pasa sin cambiar ningún conteo existente.

Cuello del útero: Cuadro 15, último bloque (Sem, acumulado y año anterior); 666 de 669 boletines,
las mismas tres exclusiones que mama, determinista (`8530cccef216…`); W42 igual al radar en las 32
entidades y sólo 1 de 32 semanas igual a mama.

| hecho | valor |
| --- | --- |
| Dataset | `cancer_cuello_utero_c53_4ad50c282abf` (32 series, 668 periodos) |
| Selección | `cancer_cuello_utero_c53_select_15758701c65e_60ac551e9441` (medias y medianas de 3 y 5 años) |
| Prueba 2025 | `cancer_cuello_utero_c53_benchmark_test_1241d3b04626_5382fe5f63bf` |
| sMAPE bases / 37 / nacional | 83.0 / 79.2 / 21.7, control 96.9 / 86.9 / 20.9 |
| Veredicto | ACEPTADO (nacional +3.6 %, dentro del 10 %) |
| Release | `cancer_cuello_utero_c53_release_a2dd2900a980` |
| Emitido | 2026-11-08 22:43:37 UTC; el boletín 43 no existía |

Las series estatales tienen pocos casos (unas 71 semanales en todo el país) y su sMAPE es alto; el
total nacional es la lectura útil. El paso semanal acepta el raw sin sexo (`prospective_week`,
ensayado en seco con un boletín simulado) y `une_consolidado.sh` lo proyecta al consolidado con
hombres y mujeres vacíos. Consolidado W42 `candidato_con_cuello`: paridad PASS con los dieciocho.

## Quince cánceres desde 2023: política de historia corta (8-nov-2026)

El autor pidió diseñarla («de una vez») y revisarla antes de publicar nada. Los Cuadros 15.2 a 15.6 existen
desde el boletín 2023_sem02 (serie desde 2023-W01), así que ninguna política vigente aplica: exigen 260
semanas previas. Con 2023 como único año previo, un pliegue 2024 sólo admitiría el naive, porque cualquier
ventana de varios años cae a él.

`rolling_cv_historia_corta_2023_v1` (distinta de `rolling_cv_historia_corta_v1`, la de Covid-19, que no
cambia):

- desarrollo: un pliegue, 2025 completo (53 semanas MMWR), con 104 semanas previas; la política lo declara
  con `allow_53_week_development`;
- prueba bloqueada: 2026-W01 a W41 (fold `partial: true`), nunca vista al elegir;
- candidatos: `seasonal_naive_lag52` (control) y `seasonal_mean_2y`, la única ventana distinta con dos años;
  ETS y Ridge fallan cerrado en series de pocos casos;
- aceptación idéntica a las demás políticas (5 % bases y todos los productos, 10 % nacional).

Es evidencia más débil que la de las series largas: un solo pliegue de desarrollo y 41 semanas de prueba, y
el portafolio es casi siempre el propio control (el naive gana la mayoría de las series), así que «aceptado»
significa sobre todo que la media de dos años no empeoró al naive. Los errores estatales son altos (sMAPE de
32 a 99) porque son pocos casos por semana; el nacional es la lectura útil.

Extracción: 198 boletines (2023_sem02 a 2026_sem42, `--pdf-dir` con sólo esos), semana 42 igual al radar en
las 32 entidades de los quince, determinista (uno por cuadro, dos corridas con el mismo sha256). Próstata,
cuerpo del útero y ovario vienen sin desglose por sexo (`sex_breakdown: false`, 32 bases). Exclusiones con
periodo conservado donde camelot pierde renglones de estados (la fuente se lee completa con pdftotext):
`2026_sem09` (15.3 y 15.5), `2024_sem23` y `2026_sem20` (15.4), `2025_sem11` (15.5); dos de ellas caen en la
prueba de 2026 y su verdad es imputada.

| padecimiento | sMAPE bases | todos | nacional (portafolio / control) | veredicto | selección (naive / media 2 años) |
| --- | --- | --- | --- | --- | --- |
| Pulmón (C33-C34) | 73.2 / 73.2 | 73.2 / 73.2 | 27.4 / 31.2 | ACEPTADO | 50 / 14 |
| Estómago (C16) | 92.7 / 92.0 | 87.8 / 87.8 | 20.4 / 20.3 | ACEPTADO | 47 / 17 |
| Colon y recto (C18-C21) | 92.0 / 96.4 | 84.7 / 88.2 | 21.7 / 20.2 | ACEPTADO | 39 / 25 |
| Linfoma de Hodgkin (C81) | 43.9 / 43.9 | 58.5 / 58.5 | 39.8 / 39.5 | ACEPTADO | 52 / 12 |
| Linfoma no Hodgkin (C82-C85) | 86.3 / 87.9 | 81.4 / 82.9 | 28.0 / 25.8 | ACEPTADO | 48 / 16 |
| Leucemia (C91-C95) | 77.1 / 78.0 | 74.4 / 77.1 | 17.8 / 17.6 | ACEPTADO | 46 / 18 |
| Páncreas (C26) | 63.4 / 63.9 | 72.1 / 69.9 | 22.7 / 27.6 | ACEPTADO | 54 / 10 |
| Encéfalo y SNC (C70-C72) | 53.7 / 53.7 | 65.7 / 63.4 | 27.4 / 31.0 | ACEPTADO | 56 / 8 |
| Cuerpo del útero (C54), sin sexo | 98.7 / 99.6 | 89.4 / 94.9 | 32.2 / 29.7 | ACEPTADO | 21 / 11 |
| Ovario (C56), sin sexo | 96.7 / 100.7 | 93.0 / 99.1 | 23.0 / 21.1 | ACEPTADO | 19 / 13 |
| Riñón (C64) | 88.9 / 84.0 | 82.9 / 79.7 | 23.9 / 24.3 | RECHAZADO | 49 / 15 |
| Próstata (C61), sin sexo | 76.0 / 89.4 | 74.2 / 84.1 | 27.7 / 24.6 | RECHAZADO | 10 / 22 |
| Huesos (C40-C41) | 39.0 / 39.0 | 53.7 / 52.0 | 43.1 / 38.6 | RECHAZADO | 54 / 10 |
| Hígado (C22) | 78.9 / 79.7 | 79.7 / 80.0 | 29.3 / 26.1 | RECHAZADO | 54 / 10 |
| Esófago (C15) | 32.5 / 32.5 | 48.8 / 44.8 | 40.0 / 42.0 | RECHAZADO | 46 / 18 |

Runs de prueba: `<id>_benchmark_test_*` en `runs/` del backend (conservados).

### Publicación de los diez aceptados

Con los resultados a la vista, el autor ordenó «publica». Refit y pronóstico a 52 semanas con origen
2026-W41; el boletín 43 no existía al emitir. Gates prospectivos 0/4 (W42-W45). Consolidado W42
`candidato_con_cancer_corto`: paridad PASS con los veintiocho. Los cinco rechazados se publicaron después con el control (sección siguiente).

| padecimiento | release | emitido (UTC) |
| --- | --- | --- |
| `cancer_pulmon_c33` | `cancer_pulmon_c33_release_7f3634aa0f22` | 2026-11-09 01:36:09 |
| `cancer_estomago_c16` | `cancer_estomago_c16_release_bcb7311dcd13` | 2026-11-09 01:36:12 |
| `cancer_colon_c18` | `cancer_colon_c18_release_30b04f3b5815` | 2026-11-09 01:36:16 |
| `linfoma_hodgkin_c81` | `linfoma_hodgkin_c81_release_9b738cbb8583` | 2026-11-09 01:36:19 |
| `linfoma_no_hodgkin_c82` | `linfoma_no_hodgkin_c82_release_77a32affcf0d` | 2026-11-09 01:36:23 |
| `leucemia_c91` | `leucemia_c91_release_927f100c33f3` | 2026-11-09 01:36:26 |
| `cancer_pancreas_c26` | `cancer_pancreas_c26_release_22b93205d12a` | 2026-11-09 01:36:30 |
| `cancer_encefalo_c70` | `cancer_encefalo_c70_release_0de6f44f8bfd` | 2026-11-09 01:36:33 |
| `cancer_cuerpo_utero_c54` | `cancer_cuerpo_utero_c54_release_3523a60b29ef` | 2026-11-09 01:36:37 |
| `cancer_ovario_c56` | `cancer_ovario_c56_release_bc43fe23e398` | 2026-11-09 01:36:40 |

### Control de los cinco rechazados

Con la tabla de resultados a la vista, el autor respondió «autorizo» a publicar el control de riñón, próstata,
huesos, hígado y esófago. `acceptance_fallback_run` apunta a cada run de prueba rechazado (commiteado antes
del refit). Releases con `fallback_control`, gates 0/4 (W42-W45) con candidato igual al control: al completar
serán `CONTROL_ONLY`, nunca `PASS`. Ámbitos que reprobaron: riñón en las bases (88.9 frente a 84.0), esófago
en todos los productos (48.8 frente a 44.8), y próstata, huesos e hígado en el nacional. Consolidado W42
`candidato_con_cancer_control`: paridad PASS con los treinta y tres.

| padecimiento | prueba rechazada | release (control) | emitido (UTC) |
| --- | --- | --- | --- |
| `cancer_rinon_c64` | `cancer_rinon_c64_benchmark_test_6f85ddda7aa1_b46f5e8a0fae` | `cancer_rinon_c64_release_2cbedc349fbf` | 2026-11-09 02:44:32 |
| `cancer_prostata_c61` | `cancer_prostata_c61_benchmark_test_4ef016e56f8f_56f68de1cdc5` | `cancer_prostata_c61_release_433d60a37c6a` | 2026-11-09 02:44:34 |
| `cancer_huesos_c40` | `cancer_huesos_c40_benchmark_test_42bc72d33354_3c32f13e2cb3` | `cancer_huesos_c40_release_4448e9604b95` | 2026-11-09 02:44:37 |
| `cancer_higado_c22` | `cancer_higado_c22_benchmark_test_f3c5e961cd52_0f0275e364ff` | `cancer_higado_c22_release_0340c3e974c5` | 2026-11-09 02:44:40 |
| `cancer_esofago_c15` | `cancer_esofago_c15_benchmark_test_2a83a6e8a70f_33cd417d156d` | `cancer_esofago_c15_release_9b1f38c2dea0` | 2026-11-09 02:44:43 |

## Auditoría del 9-nov-2026: verdad imputada en la prueba de 2026

La auditoría independiente encontró que nueve cánceres de historia corta (Cuadros 15.3 a 15.5) se
evaluaron con 1,008 filas producto × semana imputadas en la prueba 2026-W01..W41, aunque el PDF sí
trae los datos: camelot perdía renglones de estados en 2026_sem09 y 2026_sem20 (y en 2024_sem23 y
2025_sem11, fuera de la prueba), y las exclusiones con `keep_period` los imputaron. Ejemplo: colon W08
usó 86 casos frente a 132 impresos. La evaluación cuenta las filas imputadas como observadas.

- **Extracción corregida:** el extractor reintenta con `edge_tol=500` cuando faltan estados y las cinco
  exclusiones se retiraron; las 32 entidades de cada página recuperada cuadran con su renglón TOTAL
  impreso (pulmón, estómago y colon W08: 45, 43 y 132).
- **Sensibilidad (auditoría):** excluyendo las filas imputadas se conservan los 10 aceptados y los 5
  rechazados; colon queda en +9.945 % nacional frente al control, con límite de +10 %.
- **Releases sellados de la primera corrida:** sus datasets conservan la imputación. Se conservan como
  evidencia en DVC; el autor ordenó reevaluar («re-evalúa obvio») y la sección siguiente los reemplaza.

## Reevaluación del 9-nov-2026 con la verdad recuperada

Por orden del autor («re-evalúa obvio») se reextrajeron los nueve cánceres de los Cuadros 15.3 a 15.5
(198 boletines, 6,336 filas cada uno, sin exclusiones) y se repitió la cadena completa con la misma
política, los mismos candidatos y los mismos criterios: `validate-data`, benchmark smoke y full,
`select`, prueba 2026-W01..W41, refit y pronóstico. Los raws nuevos difieren de los publicados sólo en las
semanas recuperadas (comparación numérica): 2026-W09 en pulmón, estómago, colon, leucemia, esófago y
páncreas; 2026-W20 en hígado y los dos linfomas; 2024-W23 y 2025-W11 fuera de la prueba. La semana 42 no
cambia. Los otros seis cánceres de historia corta no tenían filas imputadas y siguen igual.

**Ningún veredicto cambia.** Los siete aceptados lo siguen siendo y hígado y esófago vuelven a reprobar;
su `acceptance_fallback_run` apunta ahora a la prueba nueva (commiteado antes del refit), bajo la misma orden
de publicar el control. Colon, el más cercano al límite, queda en +8.64 % nacional frente al control (límite
10 %).

| padecimiento | bases (antes → ahora) | todos | nacional (portafolio / control) | veredicto |
| --- | --- | --- | --- | --- |
| Pulmón | 73.2 / 73.2 → 73.2 / 73.2 | 73.2 / 73.2 → 73.2 / 73.2 | 27.4 / 31.2 → 26.3 / 30.2 | ACEPTADO |
| Estómago | 92.7 / 92.0 → 93.5 / 93.5 | 87.8 / 87.8 → 89.4 / 90.3 | 20.4 / 20.3 → 19.5 / 19.5 | ACEPTADO |
| Colon y recto | 92.0 / 96.4 → 91.8 / 97.7 | 84.7 / 88.2 → 83.3 / 91.2 | 21.7 / 20.2 → 20.8 / 19.2 | ACEPTADO |
| Linfoma de Hodgkin | 43.9 / 43.9 → 41.5 / 41.5 | 58.5 / 58.5 → 60.2 / 58.5 | 39.8 / 39.5 → 40.4 / 39.8 | ACEPTADO |
| Linfoma no Hodgkin | 86.3 / 87.9 → 89.2 / 90.6 | 81.4 / 82.9 → 82.9 / 82.9 | 28.0 / 25.8 → 27.4 / 26.0 | ACEPTADO |
| Leucemia | 77.1 / 78.0 → 78.0 / 78.0 | 74.4 / 77.1 → 75.4 / 76.3 | 17.8 / 17.6 → 17.7 / 17.5 | ACEPTADO |
| Páncreas | 63.4 / 63.9 → 63.9 / 64.2 | 72.1 / 69.9 → 68.3 / 68.3 | 22.7 / 27.6 → 22.8 / 27.9 | ACEPTADO |
| Hígado | 78.9 / 79.7 → 78.6 / 80.5 | 79.7 / 80.0 → 79.7 / 81.3 | 29.3 / 26.1 → 28.4 / 25.5 | RECHAZADO, control |
| Esófago | 32.5 / 32.5 → 32.5 / 32.5 | 48.8 / 44.8 → 47.4 / 44.2 | 40.0 / 42.0 → 40.1 / 42.0 | RECHAZADO, control |

Releases nuevos con origen 2026-W41 (el boletín 43 no existía al emitir), dos builds con el mismo
`release_id`, gates prospectivos congelados de nuevo (0/4, W42-W45; los de hígado y esófago con candidato
igual al control, `CONTROL_ONLY` al completar) y baselines nuevas. Los releases anteriores siguen en DVC.
Consolidado W42 `candidato_reevaluado` (sha256 `373d01e5…`): difiere de `candidato_con_cancer_control`
sólo en las 15 semanas-padecimiento recuperadas (32 filas cada una) y la paridad pasa con los treinta y
tres. Shards respaldados en `planes/respaldo_shards_2026-11-09_reevaluacion/`.

| padecimiento | prueba | release | emitido (UTC) |
| --- | --- | --- | --- |
| `cancer_pulmon_c33` | `cancer_pulmon_c33_benchmark_test_2d2d31a7c68a_7347dec5a3ac` | `cancer_pulmon_c33_release_0bfb82648d55` | 2026-11-09 05:14:30 |
| `cancer_estomago_c16` | `cancer_estomago_c16_benchmark_test_0bc8d3ba0d7e_ab74589b67ce` | `cancer_estomago_c16_release_94460da48374` | 2026-11-09 05:14:34 |
| `cancer_colon_c18` | `cancer_colon_c18_benchmark_test_8b0ab407ba06_55d3c0049b72` | `cancer_colon_c18_release_5da7b90e5db1` | 2026-11-09 05:14:38 |
| `linfoma_hodgkin_c81` | `linfoma_hodgkin_c81_benchmark_test_7dfe1d52767d_c0e66ac80d8c` | `linfoma_hodgkin_c81_release_4ea7e36a6ed6` | 2026-11-09 05:14:44 |
| `linfoma_no_hodgkin_c82` | `linfoma_no_hodgkin_c82_benchmark_test_325bc498b4e3_06114effc08d` | `linfoma_no_hodgkin_c82_release_f13bb4b27953` | 2026-11-09 05:14:48 |
| `leucemia_c91` | `leucemia_c91_benchmark_test_5a82891edd36_bef2f6d272be` | `leucemia_c91_release_0aa2412f36a6` | 2026-11-09 05:14:51 |
| `cancer_pancreas_c26` | `cancer_pancreas_c26_benchmark_test_c330418f2b55_53c86c8d0696` | `cancer_pancreas_c26_release_b7eeb1352582` | 2026-11-09 05:14:58 |
| `cancer_higado_c22` | `cancer_higado_c22_benchmark_test_f4d4974a5710_fff4aa718d8a` | `cancer_higado_c22_release_b4a6f8ab36bb` | 2026-11-09 05:14:41 |
| `cancer_esofago_c15` | `cancer_esofago_c15_benchmark_test_1d27e82840b1_f184e9927821` | `cancer_esofago_c15_release_5c6a6bc1f3da` | 2026-11-09 05:14:54 |

## Segunda auditoría del 9-nov-2026 (R1 a R6) y ensayo de la semana

Datos recuperados, releases, gates y archivos públicos verificados por la auditoría; quedaron seis
hallazgos operativos, corregidos aquí y en el frontend:

- **R1, base del consolidado:** `paso_semanal consolida` compara la historia de cada publicado en la base
  con el raw de su observación vigente en todas las semanas anteriores a N y falla si una fila difiere,
  falta o sobra (`epiforecast.publication.consolidado_base`). Rechaza `candidato_con_cancer_control` en las
  480 filas corregidas y acepta `candidato_reevaluado` en los 29.
- **R2, FAIL en seco:** con un FAIL se registra igual a todos con `WRITE=1`; el retiro llega después y el
  consolidado cierra con los demás (prueba de la ruta literal en `test_paso_semanal.py`).
- **R3 a R6 (frontend):** el corpus del bot nombra la primera y la última semana pronosticadas y distingue el
  corte de datos; la noticia separa siete validaciones prospectivas de dos controles sin contraste; las
  cifras estáticas de cada página se prueban contra su vista (próstata decía 64/111); cada página
  reevaluada explica la sustitución del release y su carácter retrospectivo.

Ensayo de punta a punta en clones desechables con un boletín 43 simulado (detalle en el historial del
skill): además de R1 y R2, destapó que la tarjeta nacional de un control perdía su aviso al registrar la
primera semana y dos pruebas de Diabetes ancladas a 0/4. El productor legacy v5 no se ensayó: exige el
boletín real.

Observación de fuente, sin cambio: el boletín 2025_sem44 imprime 213 casos semanales de linfoma de Hodgkin
en Morelos (TOTAL nacional 229, frente a unos 20 habituales) y el acumulado de hombres salta de 91 a 303.
Es dato impreso, no error de extracción, y el pronóstico estacional lo repite: 227 casos nacionales en
2026-W42. Estómago conserva dos bases imputadas en Chiapas 2026-W39 por celda vacía en la fuente; excluirlas
no cambia la aceptación (auditoría).

## Tercera auditoría del 9-nov-2026 (A1 a A3)

Las seis correcciones de la segunda ronda quedaron confirmadas. La tercera encontró dos escapes del
validador de la base, reproducidos sólo en copias sintéticas (no hay tal alteración en los datos), y
una observación de comunicación científica.

- **A1, duplicados.** `diferencias_base` indexaba por clave y la última fila ocultaba a la primera:
  una fila falsa seguida de la correcta pasaba. Ahora exige que cada clave (año, semana, entidad)
  aparezca una sola vez en toda la historia, en la base y en el raw, antes de comparar.
- **A2, sexo inventado.** Para una serie sin desglose se vaciaban H/M tanto en el raw como en la
  base. Ahora sólo se proyecta el raw; la base debe traer H/M vacíos.
- Comprobación sobre datos reales: la base vigente `373d01e5…` sigue sin diferencias en los 29
  publicados, la sustituida sigue rechazada (15 semanas) y las dos copias sintéticas de la auditoría
  (`SINTETICA_base_duplicate_old_wrong_first`, `SINTETICA_base_nonsex_invented_sex`) se rechazan en
  Obesidad 2014-W02 y cuello del útero 2026-W42. Nueve pruebas nuevas fallan con el código anterior.
- **A3, picos heredados de la fuente.** El barrido de las 29 vistas encontró seis releases cuyo
  pronóstico repite (o promedia) una semana aislada impresa en el boletín. Los seis valores se
  cotejaron contra el PDF:

| Release | Entidad | Semana epi. | PDF (sha256) | Impreso (nacional) | Pronóstico heredado (nacional) |
|---|---|---|---|---|---|
| Linfoma de Hodgkin | Morelos | 2025-W43 | 2025_sem44 `3519f61f…` | 213 (229) | 213 en 2026-W42 (227) |
| Páncreas | Jalisco | 2026-W01 | 2026_sem02 `0762ffd6…` | 147 (172) | 78 en 2027-W01 (101.5) |
| Pulmón | Sonora | 2026-W04 | 2026_sem05 `c777132b…` | 171 (209) | 171 en 2027-W04 (205.5) |
| Próstata | Puebla | 2026-W08 | 2026_sem09 `337e0a0e…` | 116 (252) | 116 en 2027-W08 (252) |
| Ovario | Puebla | 2026-W17 | 2026_sem18 `46fd5712…` | 211 (262) | 106.5 en 2027-W17 (151.5) |
| Cerebrovascular (control) | Hidalgo | 2026-W38 | 2026_sem39 `c112674e…` | 1,150 (2,606) | 1,150 en 2027-W38 (2,606) |

  La causa de esos valores no está establecida y no se califican de errata. El dato y los releases
  no se tocan. La página y el corpus del RAG llevan una nota derivada de la vista
  (`epibot/scripts/lib/picos_heredados.mjs`): semana aislada de al menos 50 casos, 10 veces la
  mediana de la entidad y 5 veces la mayor vecina, que el pronóstico de 364 días después repite con al
  menos 5 veces esa mediana. `node epibot/scripts/picos_heredados.mjs --write` regenera las notas y
  `--check` corre en `deploy:verify`, así que un release nuevo con un pico sin nota no se despliega.

## Cuarta auditoría del 9-nov-2026 (B1 a B3)

Los tres hallazgos de la tercera ronda quedaron confirmados y las seis notas de picos se cotejaron otra vez
contra PDF, raw, dataset y pronóstico.

- **B2, semanas fraccionarias.** `int(float("2.5"))` daba 2: una semana fraccionaria pasaba por la de su
  parte entera. `consolidado_base.entero` acepta `2` y `2.0` y rechaza fracciones, vacíos y no finitos;
  `consolida` falla con rc 2 si una clave de la base o del raw no es entera. La base vigente sigue sin
  diferencias en los 29 publicados.
- **B3, rezago de 52 semanas.** La nota de picos decía «misma semana de años anteriores» también para el
  ingenuo estacional, que desplaza 52 semanas (364 días): Hodgkin enlaza 2025-W43 con 2026-W42 porque
  2025 tuvo 53 semanas MMWR. La explicación sale ahora del motor de las series base de la entidad (ingenuo:
  52 semanas antes; medias estacionales: misma semana epidemiológica de años anteriores).
- **B1** está en el preparador de evals del skill (`scripts/prepara_evals.sh`), fuera de este repositorio.
