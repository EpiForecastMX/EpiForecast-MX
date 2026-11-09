# C7.13 — Asma (J45, J46)

**Estado al 9-nov-2026.** Por orden del autor («integra estos padecimientos: Asma — J45/J46») se dio de
alta, superó el gate de 2025 y está publicada desde su release, con validación prospectiva en curso
(0/4). Son treinta padecimientos del runner en la paridad semanal y treinta y cuatro en el sitio.

| hecho | valor |
| --- | --- |
| Cuadro y bloque | 13.3, bloque intermedio (entre insuficiencia venosa periférica y gingivitis) |
| Dataset | `asma_j45_1635a7484519` (64 bases, 111 productos, 2014-W01 a 2026-W41) |
| Política | `rolling_cv_baja_incidencia_v1` (decisión del autor, ver abajo) |
| Benchmark de desarrollo | `asma_j45_benchmark_full_da7d86af13c6` |
| Selección | `asma_j45_select_da7d86af13c6_9fc12b12744f` |
| Prueba 2025 | `asma_j45_benchmark_test_72499fe75fa8_026b34106678` |
| sMAPE bases 2025 (control) | 29.2 (33.7) |
| sMAPE 111 series (control) | 26.2 (28.7) |
| sMAPE nacional (control) | 7.3 (10.7) |
| Veredicto | ACEPTADO en los tres ámbitos |
| Refit | `asma_j45_refit_final_a6da6e7705d0_08aa2ad1ad02` |
| Pronóstico | `asma_j45_forecast_h52_08aa2ad1ad02_3803b15e8d7f`, emitido el 2026-11-09 22:27:14 UTC |
| Release | `asma_j45_release_28da01ab0b42` |
| Gate prospectivo | `637cde34…`, W42-W45, 0/4 |

Portafolio: `seasonal_mean_5y` en 29 bases, `seasonal_mean_3y` en 17, `seasonal_naive_lag52` en 17 y
`seasonal_median_5y` en 1. En desarrollo (2021-2024) la mediana de sMAPE del portafolio fue 36.7 en las
bases y 16.2 en el nacional: los pliegues de 2021 y 2022 caen en la recuperación tras la pandemia.

## Política: decisión del autor antes de abrir 2025

Con `rolling_cv_v1` y siete motores el smoke pasó, pero en el benchmark completo ETS falló cerrado en 2 de
256 ajustes de desarrollo: Tlaxcala hombres y mujeres en el pliegue de 2021, con pronósticos mínimos de
-0.008 y -0.016 casos (mediana de 2.5 y 3 casos semanales en las 104 semanas previas). Ridge no falló en
ninguno. Ese run quedó `failed` (`asma_j45_benchmark_full_3942cfc95e5c`) y no se seleccionó nada con él.

Asma **no** es de baja incidencia: la mediana semanal por serie base en 2021-2025 es 26 (mínimo 3, Tlaxcala
hombres; 6 de 64 bases por debajo de 10) y el nacional ronda los 2,600 casos semanales. Con esas cifras a la
vista el autor eligió `rolling_cv_baja_incidencia_v1`, que deja sólo los cinco motores estacionales y
excluye también a Ridge. La decisión se tomó sin mirar las métricas de desarrollo de los seis motores que sí
terminaron, y antes de abrir 2025, que se abrió una sola vez.

## La semana 42 no es prospectiva respecto de la información

El boletín 43, que trae la semana 2026-W42, apareció en el índice oficial el 9-nov-2026
(`sem43.pdf`, `Last-Modified: Mon, 09 Nov 2026 18:53:35 GMT`), tres horas y media **antes** de la emisión
(22:27:14 UTC). No se usó: el entrenamiento salió de los 669 boletines verificados por md5 contra
`data/raw_PDFs.dvc`, que terminan en `2026_sem42.pdf`. El autor decidió publicar con el mismo corte que los
demás y declararlo. Por tanto:

- W42 se evaluará fuera de muestra, pero **no** cuenta como prospectiva respecto de la información;
  W43 a W45 sí. Al registrar el boletín 43, `bulletin_provenance.json` debe llevar esa fecha de primera
  disponibilidad (`after_emission.first_available: false`).
- La página, la noticia, el EpiBot y el corpus del RAG lo dicen (campo `cronologia` de la fila de
  `release_catalog.js`). Ninguna superficie afirma cuatro semanas prospectivas.
- La comprobación del índice se hizo después de abrir 2025; debió hacerse antes de modelar.

## Datos

669 boletines (2014_sem01 a 2026_sem42): 668 válidos con 32 entidades y dos corridas con el mismo sha256
(`33fdf2b1…`). La única exclusión es `2014_sem01` (cierre anual, sin columna Sem). W42 coincide con el radar
del boletín en las 32 entidades. Frente a gingivitis, su vecino de cuadro, coinciden 7 de 64,128 celdas
(0.01 %).

El bloque es intermedio, así que el extractor lo recorta por conteo real de columnas
(`inner_block_columns`): con 11 columnas (hasta 2015_sem01, cuando el primer bloque no trae año anterior) y
con 12, son las cuatro columnas previas a las cuatro de gingivitis.

`2023_sem45` **no** se excluye. Un renglón alterado («Chiapas San Luis Potosí») hace que camelot pegue el
primer valor al nombre de la entidad en toda la tabla; gingivitis lo declaró exclusión con periodo
imputado. Para asma las cuatro columnas son legibles: el extractor separa nombre y valor
(`despega_primera_columna`, sólo para bloques que no empiezan en la primera columna) y las sumas coinciden
con el renglón TOTAL impreso (3,008 · 54,056 · 72,098 · 108,105).

Hallazgos de la fuente, sin corregir:

- **Nivel.** Entre 234 mil y 291 mil casos anuales en 2014-2019; 135 mil en 2020, 93 mil en 2021 y entre
  133 mil y 152 mil en 2022-2025. Coincide con la pandemia; no se midió si es menos enfermedad, menos
  consulta o menos registro. Los pliegues de 2021-2024 y la prueba de 2025 quedan dentro del nivel nuevo.
- **2016-W19.** El boletín 20 de 2016 imprime 691 casos nacionales (unos 4,000 en las semanas vecinas) y un
  acumulado que baja de 95 mil a 15 mil para volver la semana siguiente. El renglón TOTAL impreso dice lo
  mismo: es el dato de la fuente, no un fallo de lectura.
- Una celda sin valor semanal (Querétaro, boletín 2016_sem50): un total estado-periodo imputado, dos filas
  base, fuera de los pliegues y de la prueba. El sexo se estimó con la proporción del estado en 318 de
  41,792 filas base (`sex_fallback_state_13w`).

## Publicación

Consolidado W42: `ingestion_observado_W42/candidato_con_asma`, que parte de `candidato_reevaluado`
(`373d01e5…`) con prefijo byte-idéntico y añade las 21,376 filas de asma (sha256 `0f589d50…`); paridad PASS
con los treinta y cuatro en (2026, 42) y sin diferencias frente a las observaciones vigentes. Es la base
vigente para el paso del boletín 43. Shard original respaldado en `planes/respaldo_shards_2026-11-09_asma/`.
