# C7.12 — Cánceres del boletín 42

**Estado al 8-nov-2026.** El autor ordenó «publica todos los cancer». El Cuadro 15 (Displasias y Neoplasias)
y los siguientes traen 17 tumores malignos; sólo dos tienen historia desde 2013:

| grupo | padecimientos | historia | situación |
| --- | --- | --- | --- |
| Mama (C50) | 1 | 2013-W05 a hoy, con sexo | publicado con el control estacional |
| Cuello del útero (C53) | 1 | 2013-W05 a hoy, sin desglose por sexo | publicado: superó el gate de 2025 con 32 bases sin sexo |
| Pulmón, estómago, colon y recto, hígado, linfomas, leucemia, esófago, páncreas, SNC, huesos, riñón, próstata, cuerpo del útero, ovario | 15 | desde 2023-W01 | `rolling_cv_historia_corta_2023_v1`: los 10 aceptados están publicados («publica», 8-nov-2026); los 5 rechazados siguen `configured` |

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
`candidato_con_cancer_corto`: paridad PASS con los veintiocho. Los cinco rechazados (riñón, próstata, huesos,
hígado, esófago) siguen `configured`: publicar su control exige orden expresa con el run nombrado.

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
