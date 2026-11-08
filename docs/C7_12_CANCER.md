# C7.12 — Cánceres del boletín 42

**Estado al 8-nov-2026.** El autor ordenó «publica todos los cancer». El Cuadro 15 (Displasias y Neoplasias)
y los siguientes traen 17 tumores malignos; sólo dos tienen historia desde 2013:

| grupo | padecimientos | historia | situación |
| --- | --- | --- | --- |
| Mama (C50) | 1 | 2013-W05 a hoy, con sexo | publicado con el control estacional |
| Cuello del útero (C53) | 1 | 2013-W05 a hoy, sin desglose por sexo | publicado: superó el gate de 2025 con 32 bases sin sexo |
| Pulmón, estómago, colon y recto, hígado, linfomas, leucemia, esófago, páncreas, SNC, huesos, riñón, próstata, cuerpo del útero, ovario | 15 | desde 2023-W01 | no alcanzan las 260 semanas de `min_train_weeks`; el autor pidió diseñar una política de historia corta, sujeta a su revisión antes de publicar |

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
