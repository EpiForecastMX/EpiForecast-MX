# C7.17 · Lote alta20c: veinte publicados (14-15 nov 2026)

Orden del autor (14-nov-2026): incorporar veinte padecimientos más. El 15-nov el autor delegó literalmente «todo lo
pendiente preguntarte a fable y él decide nada puede quedar pendiente» (registro de root
`DELEGACION_AUTOR_FABLE_20261115.json`, sha256 0fdf327a…). Las decisiones de gobierno de la tanda (controles tras
rechazo, política tras fallo medido, sensibilidad y comparabilidad) son dictámenes delegados de Fable 5.2, **no firmas
humanas ni revisión clínica**: `FABLE_DECISIONES_DELEGADAS_20261115` (7832594e…), `FABLE_DECISION_PLAGUICIDAS_20261115`
(19e61453…) y `FABLE_CONTROLES5_DECISION_20261115` (64e8ab05…).

## Resultado

Veinte nuevos (sitio 65 → 85; runner 61 → 81): diecisiete controles estacionales (`seasonal_naive_lag52`) **no
validados** y tres portafolios aceptados en su prueba única de 2025 (validación prospectiva 0/4 en curso, nunca PASS).

- **Aceptados:** fiebre paratifoidea (A01.1-A01.4), mal del pinto (A67) y vulvovaginitis (N76, sin desglose por sexo).
  Aceptar significa no empeorar al control más de lo que permite la regla (5 % bases, 5 % conjunto, 10 % nacional); no
  es precisión: el sMAPE nacional de mal del pinto en 2025 fue 111.3 frente a 115.8 del control.
- **Controles (12 del dictamen base):** brucelosis, fiebre reumática, bocio, hepatitis B (aguda B16), rotavirus,
  absceso hepático amebiano y leptospirosis (los siete reutilizables de alta10b, rechazados en su prueba única) y
  helmintiasis, desnutrición moderada y severa, enterobiasis y giardiasis (rechazos de alta10b).
- **Controles (5 del dictamen complementario, por orden v3):** síndrome coqueluchoide y tos ferina (rezago impreso 0:
  origen 2026-W43), intoxicación por plaguicidas e intoxicación por monóxido de carbono (la serie no distingue
  intención; crisis vigente), síndrome meníngeo (G00-G03 excepto G00.0 y G00.1).
- **Fuera de cupo (configured, prueba consumida, sin control):** conjuntivitis hemorrágica, toxoplasmosis,
  cisticercosis, hipotermia, teniasis, triquinosis y tracoma.
- **Bloqueadas:** influenza y febril exantemática (Sem «-1» impreso en 2025: total imputado en el año de prueba).

Base semanal vigente (W42): `ingestion_observado_W43/candidato_con_alta20c_final20` (sha256 8c21883a…), encadenada sólo
añadiendo filas sobre `candidato_con_alta10b` (be7abfa5…) → `candidato_con_alta20c_controles12` (3afd7545…) →
`_paratifoidea` (b2d979d1…) → `_aceptados3` (60f5391c…) → `_final20`; 85 padecimientos con corte fuente 2026-W43.

## Pruebas únicas de 2025

| orden v3 | id | resultado | sMAPE nacional portafolio / control |
|---|---|---|---|
| 1 | brucelosis_a23 | rechazado | 48.0502 / 31.6657 |
| 2 | reumatica_i00 | rechazado | 95.5198 / 52.3446 |
| 3 | bocio_e01 | rechazado | 70.1775 / 56.9672 |
| 4 | hepatitis_b_b16 | rechazado | 100.9351 / 40.7062 |
| 5 | rotavirus_a080 | rechazado | 80.9840 / 50.1932 |
| 6 | absceso_hepatico_a064 | rechazado | 121.3221 / 51.0647 |
| 7 | leptospirosis_a27 | rechazado | 133.0418 / 55.6292 |
| 9 | coqueluchoide_u99 | rechazado | 140.4725 / 97.1835 |
| 10 | paratifoidea_a011 | aceptado | 22.7498 / 27.5685 |
| 11 | plaguicidas_t60 | rechazado | 30.1154 / 23.1836 |
| 12 | tos_ferina_a37 | rechazado | 169.6501 / 108.7482 |
| 13 | sindrome_meningeo_g00 | rechazado | 98.1716 / 43.3653 |
| 16 | monoxido_t58 | rechazado | 158.8617 / 62.3471 |
| 20 | conjuntivitis_hemorragica_b303 | rechazado | 139.3065 / 97.9123 |
| 21 | toxoplasmosis_b58 | rechazado | 151.6221 / 87.9340 |
| 22 | cisticercosis_b69 | rechazado | 159.8562 / 90.0436 |
| 24 | hipotermia_t68 | rechazado | 149.1043 / 79.0765 |
| 25 | teniasis_b68 | rechazado | 156.3881 / 97.5126 |
| 26 | mal_del_pinto_a67 | aceptado | 111.3208 / 115.8216 |
| 28 | triquinosis_b75 | rechazado | 46.2264 / 66.6667 |
| 29 | tracoma_a71 | rechazado | 30.1887 / 45.2830 |
| 30 | vulvovaginitis_n76 | aceptado | 8.8796 / 11.4357 |

Los siete primeros se abrieron con la selección de alta10b (política B14); los demás con selección de esta tanda,
en el orden fijado antes de cualquier prueba (`ORDEN_APERTURA_ALTA20C.json` v3, b825423f…), con aprobación nominal de
root por id. Prerregistros sellados antes de abrir (hipotermia 2025-W16, plaguicidas 2025-W44): el rechazo de
plaguicidas no depende de esa semana.

## Métodos y guardas de la tanda

- Extracción por clusters con doble pasada aislada y validador fijado (e1ed53a6…); QA por boletín, renglón TOTAL,
  vecinos de cuadro, rezago impreso por boletín (título de página y excepciones nominales; 12 títulos de 2025-2026 en
  imagen) y Σ Sem frente al acumulado.
- Rezago impreso 0 constante es configuración normal (`observation_lag_weeks: 0`); la paridad compara la semana fuente.
  Rezago variable no se modela (meningitis tuberculosa, lepra, tuberculosis respiratoria, fiebre manchada, otras
  rickettsiosis, paludismo vivax, leishmaniasis cutánea).
- Reparaciones: bloques reimpresos como `keep_period` (tos ferina), errata de Sem de influenza 2014-W03..W08
  (`keep_period`), reparación opt-in del extractor para síndrome meníngeo 2014_sem02-03 (cc660929).
- Comparabilidad formal por los formatos SUIVE-1 2014/2019 (paratifoidea renglón 178; síndrome meníngeo renglón 41).
- Guarda de 0 totales imputados en el año de prueba; configuración efectiva con equivalencia por dependencia opt-in
  (revisada por Fable); autoridad enlazada a los dictámenes por sha256.
- Fichas: semana del boletín y primera semana fuera de muestra con `semanaMas` (MMWR) en todas las fichas; avisos de
  picos y retiros de la fuente (absceso México 2026-W01, bocio Morelos 2026-W24, desnutrición moderada Oaxaca 2025-W52,
  plaguicidas México 2026-W16, y conservados) en ficha, EpiBot y corpus; nota general medida de bajas del acumulado.

## Evidencia

Base de la tanda `/tmp/epiforecast-alta20c-20261114` (PROGRESS.md); durable en `planes/alta20c_2026-11-14/`,
respaldos de shards en `planes/respaldo_shards_2026-11-15_alta20c_*`; cápsula de guiones en `docs/alta20c/operacion/`.
