# C7.12 — Cánceres del boletín 42

**Estado al 8-nov-2026.** El autor ordenó «publica todos los cancer». El Cuadro 15 (Displasias y Neoplasias)
y los siguientes traen 17 tumores malignos; sólo dos tienen historia desde 2013:

| grupo | padecimientos | historia | situación |
| --- | --- | --- | --- |
| Mama (C50) | 1 | 2013-W05 a hoy, con sexo | publicado con el control estacional |
| Cuello del útero (C53) | 1 | 2013-W05 a hoy, sin desglose por sexo | requiere soporte de un solo sexo en el runner |
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
