# C7.14 — Neumonías y bronconeumonías (J12-J18 excepto J18.2, J13 y J14)

**Estado al 10-nov-2026.** Por orden del autor («publica Neumonías y bronconeumonías: J12–J18, excepto
J18.2, J13 y J14») se dio de alta y se llevó a la prueba de 2025, que **rechazó** el portafolio en el total
nacional. Con las cifras a la vista el autor ordenó publicar el control («Publica el control»). Está
publicada desde su release con el control estacional, **nunca como validada** (`CONTROL_ONLY` al
completar). Son treinta y un padecimientos del runner en la paridad semanal y treinta y cinco en el sitio.

| hecho | valor |
| --- | --- |
| Cuadro y bloque | 5.1 tras IRA hasta 2024_sem06; 5.2, primer bloque antes de Covid-19, desde 2024_sem07 |
| Dataset | `neumonias_j12_1c7577d9ee20` (64 bases, 111 productos, 2014-W01 a 2026-W42) |
| Política | `rolling_cv_v1`, siete motores (sin Prophet) |
| Benchmark de desarrollo | `neumonias_j12_benchmark_full_ed0f1a9acd5d` |
| Selección | `neumonias_j12_select_ed0f1a9acd5d_b4a806e73a20` |
| Prueba 2025 | `neumonias_j12_benchmark_test_6e4224ea51c8_9f5d2f8fd1a6` |
| sMAPE bases 2025 (control) | 36.3 (37.4): pasa |
| sMAPE 111 series (control) | 33.1 (32.3): pasa, +2.6 % con un máximo de 5 % |
| sMAPE nacional (control) | 18.0 (13.4): **falla**, +33.9 % con un máximo de 10 % |
| Veredicto | RECHAZADO; control `seasonal_naive_lag52` publicado por orden del autor |
| Refit | `neumonias_j12_refit_final_9fe0414b00c7_dc007321409a` |
| Pronóstico | `neumonias_j12_forecast_h52_dc007321409a_4e880f5255b7`, emitido el 2026-11-10 15:43:32 UTC |
| Release | `neumonias_j12_release_5814ddca1860` (`acceptance_outcome: fallback_control`) |
| Gate prospectivo | `69d97338…`, W43-W46, 0/4; candidato y control idénticos |

Portafolio de desarrollo (2021-2024): ETS en 30 bases, Ridge en 15, `seasonal_mean_5y` en 8,
`seasonal_median_5y` en 8, `seasonal_naive_lag52` en 2 y `seasonal_median_3y` en 1; mediana de sMAPE 40.1 en
las bases y 18.0 en el nacional. ETS y Ridge no fallaron en ningún ajuste.

En 2025 el portafolio quedó por debajo de lo observado en el nacional: sesgo de -484 casos por semana. El año
tuvo 157 mil casos frente a 137 mil en 2024 y 127 mil en 2023. Que el subpronóstico se deba a ese aumento es
una explicación probable, no medida. No se reabrió 2025, no se cambió de política ni se eligió otro motor con
los resultados de la prueba.

## Cronología

El índice oficial se consultó **antes** de modelar (2026-11-10 15:30 UTC): el último boletín publicado era el
43 (`sem43.pdf`, sha256 `f24aea93…842f3c8a`, `Last-Modified: Mon, 09 Nov 2026 18:53:35 GMT`), con datos
hasta W42, y el entrenamiento lo usó. El boletín 44 no existía al emitir, así que las cuatro semanas del gate
(W43 a W46) son posteriores a la emisión respecto de la información. Como el pronóstico es el control, ese
seguimiento sólo registra su error: no valida nada.

## Datos

670 boletines (669 de `data/raw_PDFs.dvc`, verificados por md5, más `2026_sem43.pdf`): 669 válidos con 32
entidades y dos corridas con el mismo sha256 (`8dea8046…`). La única exclusión es `2014_sem01` (cierre anual,
sin columna Sem). W42 coincide con el radar del boletín 43 (3,021 casos, 126,983 acumulados, 126,878 del año
anterior) y 2014_sem10 con el TOTAL impreso. Frente a los bloques vecinos coinciden 0 de 85,503 celdas con
IRA y 27 de 44,672 (0.06 %) con Covid-19.

El rótulo cambió de «J12, J15-J18 excepto J18.2» a «J12-J18 excepto J18.2, J13 y J14»: es el mismo conjunto.
El bloque cambia de cuadro y de posición con el mismo ancho de 8 columnas, así que el grupo de cuadro declara
`periodos` (`spec_del_periodo` en `cuadro_reparaciones.py`): hasta 2024_sem06 se recorta como bloque
intermedio (8, 11 o 12 columnas) y desde 2024_sem07 como primer bloque. El ancla «bronconeumon» con los
marcadores de entidad encuentra una sola página por boletín: 527 en el 5.1 y 142 en el 5.2.

Hallazgos de la fuente, sin corregir:

- **Nivel.** Entre 110 mil y 165 mil casos anuales en 2014-2025, sin el salto de la pandemia (148 mil en
  2020); 2017-2018 y 2022 son los años más bajos.
- **Acumulados.** En 2014-W34/W35 y 2017-W34/W35 el acumulado baja y sube en semanas consecutivas; se
  compensan y el renglón semanal es el impreso.
- Una celda sin valor semanal (Querétaro, boletín 2016_sem50): un total estado-periodo imputado, dos filas
  base. El sexo se estimó con la proporción del estado en 440 de 42,816 filas base (`sex_fallback_state_13w`).

## Publicación

Consolidado W42: `ingestion_observado_W43/candidato_con_neumonias` (sha256 `3e3cf0fd…`), que parte de
`candidato_completo` (`be9883bc…`) con prefijo byte-idéntico y añade las 21,408 filas de neumonías; paridad
PASS con los treinta y cinco en (2026, 43) y sin diferencias frente a las observaciones vigentes. Es la base
vigente para el paso del boletín 44. `paso_semanal consolida` sólo añade la semana nueva de cada publicado:
para incorporar uno nuevo se añade su historia completa, como se hizo con Asma. Shard original respaldado en
`planes/respaldo_shards_2026-11-10_neumonias/`.
