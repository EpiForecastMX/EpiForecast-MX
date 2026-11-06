# C7.8 — Publicación de Diabetes tipo I y tipo II

**Estado al 5-nov-2026:** ambas están `published` con OK del autor, desde sus releases sellados, en
`web`, `epibot` y `reports`, sin Tableau. La validación prospectiva está **en curso**: el veredicto
es `INCOMPLETE` (0 de 4 semanas) y nunca se presenta como PASS.

| hecho | Diabetes tipo I (E10) | Diabetes tipo II (E11-E14) |
| --- | --- | --- |
| Release | `diabetes_t1_release_2c4a288ee348` | `diabetes_t2_release_e0153e391d08` |
| Datos de entrenamiento | hasta W41 de 2026 (boletín 42) | hasta W41 de 2026 (boletín 42) |
| Emisión del pronóstico (UTC) | 2026-11-06 03:44:32 | 2026-11-06 03:44:45 |
| Política | `rolling_cv_baja_incidencia_v1` | `rolling_cv_v1`, siete motores |
| Portafolio en 2025, mediana sMAPE de las 64 bases | 88.9 (control 96.1) | 18.7 (control 22.9) |
| Portafolio en 2025, sMAPE nacional | 21.2 (control 21.3) | 11.8 (control 10.9, tolerancia 10 %) |
| Pronóstico nacional a 52 semanas | 3,623 casos | 560,299 casos |
| Gate | `2cfbb870…` | `4a8e4403…` |

## Decisiones

- **Baja incidencia.** En tipo I, ETS falla en el smoke (series casi en cero con pronósticos
  negativos), igual que en F50. `rolling_cv_baja_incidencia_v1` conserva folds, semilla, métrica,
  banda y aceptación de `rolling_cv_v1` y deja sólo los cinco motores estacionales. El runner ahora
  lee la política del registry. F50 también la usa y su smoke pasa.
- **Tipo II sin Prophet.** Sus hiperparámetros congelados son los de Obesidad y el stage 2025 ya se
  abrió: añadir Prophet exigiría otra apertura.
- **Publicación condicionada.** Un pronóstico recién emitido no puede tener semanas prospectivas.
  `VERDICTS_PUBLICABLES` admite `INCOMPLETE`; las superficies dicen «en curso» y no muestran
  desempeño fuera de muestra hasta que existan semanas observadas.
- **Observación de línea base.** `artifacts/observations/<id>/<dataset>` guarda el dataset de
  entrenamiento como observación portable 0/4, para que la vista se reconstruya desde DVC.

## Lectura correcta

- El error de tipo I por estado y sexo es alto: esas series tienen muy pocos casos por semana. El
  nacional es el nivel útil; lo estatal se lee como orden de magnitud.
- Las semanas objetivo son W42 a W45, publicadas en los boletines 43 a 46, posteriores a la emisión.

## Cada boletín

Igual que Obesidad, para cada `<id>`: `make prospective-week-record DISEASE=<id> PDF=…`, `dvc add` y
`dvc push` de la observación, filas al consolidado, vista desde el shard original
(`runs/publication/<id>/compile_a/<id>/<release_id>`) y reinstalación. Si cualquiera de las dos se
queda atrás, la paridad falla cerrada.
