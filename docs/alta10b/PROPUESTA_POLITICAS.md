# Propuesta de política por candidato (lote alta10b) — NO es autorización

Pregunta al autor, una decisión nominal por padecimiento: ¿autoriza `rolling_cv_baja_incidencia_v1`
(cinco motores estacionales: lag52, media y mediana de 3 y 5 años; sin ETS ni Ridge; mismos pliegues
2021-2024, semilla, banda y aceptación: 5 % bases, 5 % todas las series, 10 % nacional frente a
`seasonal_naive_lag52`) para el candidato nombrado? La autorización de los 17 de alta20 no se extiende.
Sin orden nominal no se corre full ni prueba de 2025 con esa política.

Advertencias que el autor debe ver:
- Con cinco motores, el portafolio puede quedar formado sólo por estacionales y, en series donde la
  selección elige el propio `seasonal_naive_lag52` en las 64 bases, candidato y control serían
  idénticos: entonces el gate prospectivo sale `CONTROL_ONLY`, nunca una validación propia.
- La política expulsa también a Ridge aunque en algunas bases sí ajuste (trampa 16).
- Rechazo posible: en alta20 aceptaron 5 de 17 con esta política.

Estado de la consulta: root ya preguntó al autor por moderada y severa (B2, en
`runs/alta10b_root_20261112/DECISIONES_AUTOR_A6_B2.md`), sin respuesta. Los otros catorce quedan medidos
aquí para que root decida si y cuándo agruparlos en una sola pregunta; no se ha preguntado por ellos.

Mediciones sobre el raw canónico (dos pasadas aisladas revalidadas con el validador fijado, mismo CSV;
`extract/canon/<id>_RAW.json`), estadísticas 2021-2024 en `qa/<id>_estadisticas.json` y fallos del smoke
de siete motores con su tipo real en `qa/diag_motores_<id>.json`. En los dieciséis sólo fallan ETS y Ridge
(EtsFitError/RidgeFitError) y los cinco estacionales terminan `succeeded`:

| id | dataset | smoke 7 motores (run, estado) | bases con fallo de 64 en desarrollo y tipos de error medidos | mediana estatal semanal (p10, mín) | % semanas en cero (mediana por entidad; entidades >50 %) | nacional semanal (mediana) |
| --- | --- | --- | --- | --- | --- | --- |
| `absceso_hepatico_a064` | `absceso_hepatico_a064_d5ac40e1a65d` | `absceso_hepatico_a064_benchmark_smoke_a9de6a4dfd3f`, failed | ETS 55 (por pliegue 2021-2024: [39, 42, 37, 40]); Ridge 30 ([22, 22, 22, 18]); tipos {'EtsFitError': 158, 'RidgeFitError': 84} | 0.0 (0.0, 0) | 83.9; 30 | 9 |
| `ascariasis_b77` | `ascariasis_b77_a19f446056a4` | `ascariasis_b77_benchmark_smoke_46aa113bdd24`, failed | ETS 29 (por pliegue 2021-2024: [22, 16, 20, 17]); Ridge 14 ([11, 9, 11, 13]); tipos {'EtsFitError': 75, 'RidgeFitError': 44} | 3.5 (0.0, 0) | 7.0; 6 | 418 |
| `bocio_e01` | `bocio_e01_0fd229f0dc96` | `bocio_e01_benchmark_smoke_a99f868dfe85`, failed | ETS 55 (por pliegue 2021-2024: [37, 44, 38, 33]); Ridge 40 ([26, 26, 24, 24]); tipos {'EtsFitError': 152, 'RidgeFitError': 100} | 0.0 (0.0, 0) | 79.3; 29 | 16 |
| `brucelosis_a23` | `brucelosis_a23_f2ebf644e428` | `brucelosis_a23_benchmark_smoke_cf56497f7a72`, failed | ETS 61 (por pliegue 2021-2024: [55, 54, 47, 43]); Ridge 52 ([44, 48, 47, 43]); tipos {'EtsFitError': 199, 'RidgeFitError': 182} | 0.0 (0.0, 0) | 74.3; 24 | 19 |
| `calor_t67` | `calor_t67_daed95767476` | `calor_t67_benchmark_smoke_54269513af65`, failed | ETS 60 (por pliegue 2021-2024: [49, 44, 41, 25]); Ridge 37 ([30, 34, 32, 32]); tipos {'EtsFitError': 159, 'RidgeFitError': 128} | 0.0 (0.0, 0) | 52.2; 17 | 50 |
| `desnutricion_moderada_e440` | `desnutricion_moderada_e440_fd2ef44a4613` | `desnutricion_moderada_e440_benchmark_smoke_e167265b27d6`, failed | ETS 32 (por pliegue 2021-2024: [31, 15, 7, 7]); Ridge 8 ([5, 8, 7, 4]); tipos {'EtsFitError': 60, 'RidgeFitError': 24} | 4.5 (1.0, 1) | 5.3; 0 | 180 |
| `desnutricion_severa_e40` | `desnutricion_severa_e40_b958de06dd18` | `desnutricion_severa_e40_benchmark_smoke_584df10f024b`, failed | ETS 33 (por pliegue 2021-2024: [30, 25, 15, 12]); Ridge 10 ([9, 7, 5, 5]); tipos {'EtsFitError': 82, 'RidgeFitError': 26} | 2.0 (0.1, 0) | 20.4; 4 | 91 |
| `enterobiasis_b80` | `enterobiasis_b80_576961f53369` | `enterobiasis_b80_benchmark_smoke_68f4c828768f`, failed | ETS 39 (por pliegue 2021-2024: [29, 28, 25, 25]); Ridge 24 ([19, 19, 23, 23]); tipos {'EtsFitError': 107, 'RidgeFitError': 84} | 2.0 (0.0, 0) | 22.1; 12 | 116 |
| `giardiasis_a071` | `giardiasis_a071_23d5d9e15daa` | `giardiasis_a071_benchmark_smoke_a234f63330d8`, failed | ETS 37 (por pliegue 2021-2024: [23, 28, 22, 27]); Ridge 17 ([11, 11, 9, 10]); tipos {'EtsFitError': 100, 'RidgeFitError': 41} | 1.5 (0.0, 0) | 21.4; 8 | 104 |
| `helmintiasis_b65` | `helmintiasis_b65_251617083535` | `helmintiasis_b65_benchmark_smoke_aab414ec74c9`, failed | ETS 5 (por pliegue 2021-2024: [5, 3, 2, 1]); Ridge 3 ([2, 2, 2, 3]); tipos {'EtsFitError': 11, 'RidgeFitError': 9} | 24.0 (7.1, 0) | 0.0; 1 | 1322 |
| `hepatitis_a_b15` | `hepatitis_a_b15_8984658283fd` | `hepatitis_a_b15_benchmark_smoke_963cd234d0c9`, failed | ETS 59 (por pliegue 2021-2024: [52, 48, 30, 21]); Ridge 29 ([16, 22, 24, 22]); tipos {'EtsFitError': 151, 'RidgeFitError': 84} | 1.0 (0.0, 0) | 27.6; 7 | 89 |
| `hepatitis_b_b16` | `hepatitis_b_b16_b7a50a59ec73` | `hepatitis_b_b16_benchmark_smoke_d53332fe2f36`, failed | ETS 52 (por pliegue 2021-2024: [43, 39, 31, 24]); Ridge 28 ([25, 23, 22, 13]); tipos {'EtsFitError': 137, 'RidgeFitError': 83} | 0.0 (0.0, 0) | 76.9; 28 | 13 |
| `leptospirosis_a27` | `leptospirosis_a27_53cf7e5705d3` | `leptospirosis_a27_benchmark_smoke_cc23fc379d25`, failed | ETS 30 (por pliegue 2021-2024: [24, 21, 16, 13]); Ridge 38 ([34, 34, 31, 26]); tipos {'EtsFitError': 74, 'RidgeFitError': 125} | 0.0 (0.0, 0) | 97.4; 30 | 5 |
| `otras_hepatitis_b17` | `otras_hepatitis_b17_3d4b3d92218c` | `otras_hepatitis_b17_benchmark_smoke_d7374f701222`, failed | ETS 45 (por pliegue 2021-2024: [40, 37, 28, 21]); Ridge 24 ([17, 19, 15, 15]); tipos {'EtsFitError': 126, 'RidgeFitError': 66} | 0.0 (0.0, 0) | 57.5; 19 | 37 |
| `reumatica_i00` | `reumatica_i00_6f3866cdcba8` | `reumatica_i00_benchmark_smoke_4f0e4ea4c9c0`, failed | ETS 49 (por pliegue 2021-2024: [36, 36, 30, 34]); Ridge 18 ([13, 15, 15, 9]); tipos {'EtsFitError': 136, 'RidgeFitError': 52} | 0.0 (0.0, 0) | 72.8; 29 | 16 |
| `rotavirus_a080` | `rotavirus_a080_8a78480b5009` | `rotavirus_a080_benchmark_smoke_6ced20ed8793`, failed | ETS 60 (por pliegue 2021-2024: [57, 46, 43, 38]); Ridge 54 ([45, 46, 49, 46]); tipos {'EtsFitError': 184, 'RidgeFitError': 186} | 0.0 (0.0, 0) | 84.6; 28 | 13 |

Errores exactos del primer fallo de cada motor en el smoke (`run_manifest.json`): moderada, ETS en
`estado/03/hombres/development_2024` («ninguna variante ETS produjo un pronóstico utilizable», mínimos
-0.170 y -0.168), Ridge en `estado/01/hombres/development_2024` («ningún candidato Ridge produjo conteos
utilizables»); severa, mismos tipos de error.

## Fuera de la propuesta (error que no es de escasez)

Ninguno.

Pendientes de medir: ninguno de la cartera de dieciséis. Notas de fuente: efectos del calor conserva la
definición «T67, X30» desde el formato SUIVE-1 de 2014 (`qa/calor_fuente_suive.json`, sin quiebre de nivel
en 2016-2017); helmintiasis, comparabilidad 2016-2017 cerrada por el formato SUIVE-1; hepatitis A y B, otras
hepatitis, calor, fiebre reumática y rotavirus llevan la exclusión `keep_period` de 2016_sem20 (bloques
rotados, mismo criterio que diabetes y cardiovasculares).
