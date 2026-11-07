# C7.10 — Hipertensión arterial, enfermedad isquémica y cerebrovascular

**Estado al 7-nov-2026:** publicadas por orden del autor («incorpora todos estos padecimientos»). Sólo
hipertensión superó el gate de 2025. Ideación suicida (R45.8) no se incorporó.

| hecho | Hipertensión (I10-I15) | Isquémica (I20, I25) | Cerebrovascular (I60-I67, I69) |
| --- | --- | --- | --- |
| Política | `rolling_cv_v1`, 7 motores | `rolling_cv_baja_incidencia_v1` | `rolling_cv_baja_incidencia_v1` |
| Selección | `hipertension_i10_select_0faccaf0609c_fabcb9ea227c` | `isquemica_i20_select_86b30e13aa58_af1330350bd2` | `cerebrovascular_i60_select_437124ca339b_86ae953bdd64` |
| sMAPE bases 2025 (control) | 18.2 (21.4), pasa | 48.1 (44.6), falla | 40.0 (45.9), pasa |
| sMAPE 111 series (control) | 15.6 (19.6), pasa | 40.0 (36.2), falla | 33.9 (34.6), pasa |
| sMAPE nacional (control) | 7.5 (7.3), pasa | 27.1 (10.5), falla | 18.4 (12.8), falla |
| Veredicto | ACEPTADO | RECHAZADO | RECHAZADO |
| Publicado | portafolio | control | control |
| Release | `hipertension_i10_release_053505b088df` | `isquemica_i20_release_791553dfcf93` | `cerebrovascular_i60_release_9831f39d074e` |

Origen 2026-W41, 52 semanas, emitidos el 7-nov-2026. Las dos caídas al control siguen la ruta de F50
(`acceptance_fallback_run`, `CONTROL_ONLY`): se publicaron sin una segunda consulta porque el autor pidió
incorporarlas sin detenerse y el control tuvo un error nacional bajo en 2025. El autor lo confirmó
expresamente después de revisarlo, el 7-nov-2026. La confirmación mantiene ambas publicadas con el
control y no las convierte en aceptadas ni validadas.

## Datos

Cuadro 13.2, 669 boletines, tres bloques de cuatro columnas. Totales de W42 iguales al radar del boletín.
Dos corridas dieron el mismo sha256. Exclusiones: `2014_sem01` (cierre anual), `2016_sem20` (valores
rotados en el PDF) y `2019_sem28` (31 de 32 entidades).

El extractor leía como ceros 68 boletines de 2014-2015 con estado `ok`: camelot separaba valores y
entidad en dos renglones. `alinea_renglones` lo corrige; el estado `ok` no lo detectaba.

## Ideación suicida

El bloque existe desde 2023-W02. Ninguna política tiene pliegues de desarrollo previos a 2025 con esa
historia: cambiar el año de prueba o crear un gate más débil es decisión del autor. Además, un
pronóstico público por estado requiere revisión clínica y de comunicación. No se dio de alta.
