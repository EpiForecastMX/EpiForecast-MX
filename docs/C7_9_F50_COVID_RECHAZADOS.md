# C7.9 — Anorexia/bulimia (F50) y Covid-19: rechazados por el gate de 2025

**Estado al 6-nov-2026:** el gate de 2025 rechazó ambos portafolios. El autor pidió publicar F50 con
el control (`seasonal_naive_lag52`) y dejar Covid-19 sin publicar. El stage 2025 ya se abrió para
ambos y no se reabre.

| hecho | Anorexia, bulimia (F50) | Covid-19 (U07.1) |
| --- | --- | --- |
| Datos | 2014-W02 a boletín 42 de 2026 | 2020-W08 a boletín 42 de 2026 |
| Política | `rolling_cv_baja_incidencia_v1` | `rolling_cv_historia_corta_v1` (nueva, antes de abrir 2025) |
| Selección | `anorexia_f50_select_fb8b8179d4d9_4aaab5fc0a51` | `covid_19_select_bc96406cf2de_ac2957800551` |
| Stage test | `anorexia_f50_benchmark_test_55217549bb4e_066db81a313d` | `covid_19_benchmark_test_effc1d95aa18_cc0cc27ec02b` |
| sMAPE bases 2025 (control) | 85.1 (97.8), pasa | 112.0 (111.0), pasa |
| sMAPE nacional 2025 (control) | 40.5 (18.1), **+123.6 %** | 104.8 (87.7), **+19.5 %** |
| Veredicto | RECHAZADO | RECHAZADO |

## Por qué

- **F50:** los casos anuales se multiplicaron desde 2022 (2,965 en 2021, 8,591 en 2023, 5,330 en
  2025). Las ventanas de varios años bajan la suma de los estados frente al nivel reciente; mejoran
  estado por sexo, pero degradan el nacional, que es el nivel que el público leería primero.
- **Covid-19:** tiene un cambio de régimen, no estacionalidad: 3.1 millones de casos en 2022,
  14,239 en 2024 y 7,421 en 2025. Incluso el control tiene sMAPE nacional de 87.7, así que tampoco
  sirve como pronóstico. Además, la última semana de cada boletín llega incompleta (75 casos en W41
  y 13 en W42 de 2026).

## F50 publicada con el control

La política ya declaraba que un portafolio rechazado cae al control, pero `refit` se negaba. Ahora:

- `refit` acepta un rechazo sólo si `acceptance_fallback_run` del registry nombra ESE run y las 64
  bases están en el control (`acceptance.fallback_problem`). Sin eso sigue negándose.
- `validate_acceptance` aplica la misma regla y la cadena del release declara
  `acceptance_outcome: fallback_control`; los releases aceptados no cambian de identidad.
- La etiqueta pública dice «Control estacional publicado…», nunca «Validación prospectiva en curso».
- El candidato ES el control (digests idénticos): el gate prospectivo no puede dar PASS comparándolo
  consigo mismo. Con las cuatro semanas el veredicto es `CONTROL_ONLY`, no `PASS`.

Release `anorexia_f50_release_173404ea4ef0`, origen 2026-W41, 52 semanas, 64 modelos del control,
emitido 2026-11-06T13:51:05Z. Refit `anorexia_f50_refit_final_9fe0414b00c7_558c30c685eb`, forecast
`anorexia_f50_forecast_h52_558c30c685eb_dcb6224a5dfc`. Pronóstico nacional a 52 semanas: 5,014 casos.

Límites que hay que decir siempre: es la misma semana del año anterior, sin intervalos; en 2025 su
sMAPE fue 18.1 en el nacional y 97.8 en la mediana de las bases, así que no sirve para leer una
entidad con sexo concreto como cifra precisa.

## Lo que sí queda

Extracción de F50 hasta el boletín 42 y de Covid-19 (349 boletines, 11,168 filas, totales iguales al
renglón nacional en las semanas comprobadas), grupo `enfermedades_respiratorias`,
`last_block_columns` y política de historia corta. Los runs se conservan en `runs/` del checkout
principal.
