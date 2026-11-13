# C7.16 · Lote alta10b: diez publicados (12-nov-2026)

Orden del autor: incorporar diez padecimientos más. **Estado: publicados los diez.** El sitio pasa de 55 a 65
padecimientos y el runner de 51 a 61, sin retirar ninguno: cuatro portafolios aceptados en su prueba única de
2025 y seis controles estacionales no validados por autorización nominal del autor.

## Publicación (autorizaciones A6, B2 y B14 del 12-nov-2026)

El autor respondió en el chat «Autorizo A6, B2 y B14» (`docs/alta10b/AUTORIZACION_A6_B2_B14.md`, registro
`AUTORIZACION_A6_B2_B14_20261112.json`): A6, el control de desnutrición leve y de los cinco rechazos antiguos
de alta20 con su run de rechazo exacto; B2 y B14, la política `rolling_cv_baja_incidencia_v1` (cinco motores
estacionales, sin ETS ni Ridge) para los dieciséis candidatos. Los rechazos futuros no quedaron autorizados
como controles.

**Seis controles (A6), nunca validados.** `acceptance_fallback_run` commiteado antes del refit; releases con
`acceptance_outcome: fallback_control`; gates con candidato igual al control; línea base 0/4.

| id | release | rechazo de 2025 (total nacional, sMAPE) |
| --- | --- | --- |
| `desnutricion_leve_e441` | `desnutricion_leve_e441_release_30b1895c19bd` | 12.5 frente a 10.1 |
| `salmonelosis_a02` | `salmonelosis_a02_release_0f0ca5f81ea8` | 42.1 frente a 31.8 |
| `tifoidea_a01` | `tifoidea_a01_release_ea50e14a0371` | 43.8 frente a 36.0 |
| `escarlatina_a38` | `escarlatina_a38_release_82d03cfdfa0f` | 46.7 frente a 36.3 |
| `hepatitis_c_b17` | `hepatitis_c_b17_release_1b625a4d7f43` | 55.3 frente a 37.0 |
| `displasia_severa_n87` (sin sexo, 37 series) | `displasia_severa_n87_release_2046566a5794` | 24.2 frente a 21.3 |

**Cuatro aceptados.** Los dieciséis llegaron a selección congelada con cinco motores
(`docs/alta10b/MANIFIESTO_SELECCIONES_16.json`) y se abrieron uno por uno, cada uno con aprobación nominal del
supervisor, en el orden fijado antes de abrir 2025 (`docs/alta10b/orden_apertura_2025.json`, mediana semanal
nacional 2021-2024) y con tope de cuatro aceptados. Una prueba por id, sin reintentos ni reaperturas:

| orden | id | resultado | total nacional (sMAPE, portafolio frente a control) |
| --- | --- | --- | --- |
| 1 | `helmintiasis_b65` | rechazado | 27.07 frente a 21.19 |
| 2 | `ascariasis_b77` | **aceptado** | 13.66 frente a 15.00 |
| 3 | `desnutricion_moderada_e440` | rechazado | 39.19 frente a 18.45 |
| 4 | `enterobiasis_b80` | rechazado | 41.09 frente a 26.23 |
| 5 | `giardiasis_a071` | rechazado | 33.15 frente a 25.32 |
| 6 | `desnutricion_severa_e40` | rechazado | 49.93 frente a 22.73 |
| 7 | `hepatitis_a_b15` | **aceptado** | 53.82 frente a 72.78 |
| 8 | `calor_t67` | **aceptado** | 41.29 frente a 45.73 |
| 9 | `otras_hepatitis_b17` | **aceptado** | 35.03 frente a 33.63 (+4.2 %, umbral 10 %) |

Los cinco rechazados siguen `configured`, sin control. Los otros siete (brucelosis, fiebre reumática, bocio,
hepatitis B, rotavirus, absceso hepático y leptospirosis) no se abrieron. Los cuatro aceptados son
portafolios reales (bases con lag52: 9, 20, 7 y 3 de 64; candidato distinto del control en el gate, no
CONTROL_ONLY). Releases: `ascariasis_b77_release_f1406e8ab382`, `hepatitis_a_b15_release_6181173f5150`,
`calor_t67_release_39efd657d7d7`, `otras_hepatitis_b17_release_08de6f7ff77b`; validación prospectiva 0/4
(W43 a W46 de 2026). Se emitieron antes de que existiera el boletín 44: es prospectiva respecto de la
información publicada, no del calendario (al emitir, W43 y W44 ya habían concluido y W45 estaba en curso).
Aceptar significa no empeorar al control más de lo que permite la regla (5 % en bases y en el conjunto, 10 %
en el nacional); no es un error absoluto bajo: el sMAPE de las series por estado de estos portafolios en 2025
va de 65 a 98, y no califica precisión clínica.

**Paridad semanal.** Consolidado vigente de W42: `ingestion_observado_W43/candidato_con_alta10b`
(sha256 `be7abfa5…`), sobre `candidato_con_alta10b_controles6` (`c86ba374…`) y éste sobre
`candidato_con_alta20_controles10` (`fad3c95c…`), sólo añadiendo filas: 65 padecimientos, todos con corte en la semana fuente 2026-W43
(boletín 43; semana objetivo observada 2026-W42), sin problemas de cobertura. Es la base de la semana siguiente.

**Notas de las fichas.** Hepatitis C hereda dos picos aislados impresos en el boletín (Ciudad de México
2026-W04, 83 casos; Morelos 2026-W38, 124), fieles a la fuente y señalados en su página. Salmonelosis y
escarlatina llevan la errata de fuente de 2016_sem20 en la historia que usó el portafolio evaluado; no entra
en el control. En cinco controles el error del control por estado fue muy alto (sMAPE 73 a 99) y su página lo
advierte como referencia poco informativa.

## Historia: preparación (code-only, PR #70)

## Qué quedó hecho

- **Altas `configured`** (`config/padecimientos.yaml`, `config/data/cuadros.yaml`): desnutrición leve
  (E44.1), moderada (E44.0) y severa (E40-E43), otras hepatitis víricas (B17-B19 excepto B17.1 y B18.2), otras
  helmintiasis (B65-B67, B70-B76, B78, B79, B81-B83, excepto B73 y B75), brucelosis (A23), leptospirosis (A27), enteritis por rotavirus
  (A08.0), efectos del calor y de la luz (T67, X30), absceso hepático amebiano (A06.4) y bocio endémico (E01).
  Todas con `rolling_cv_v1`; ninguna `published`.
- **Extractor** (`src/epiforecast/data/extraction/`, con pruebas): valores con el primer dato en la columna
  del nombre o pegados al nombre (opt-in por grupo); reintento con el área de página completa sólo cuando
  faltan entidades. Configuración por periodo y anclas de los grupos nuevos.
- **Errata de fuente 2016_sem20** (bloques rotados, mismo criterio que diabetes y cardiovasculares):
  `keep_period` en hepatitis A y B, otras hepatitis, calor, fiebre reumática y rotavirus; bocio con
  exclusiones propias. Absceso: hasta 2015_sem01 sin año anterior (3 columnas).

## Resultados (no se reabren)

- **Desnutrición leve**: prueba única de 2025 rechazada en el total nacional (sMAPE 12.52 frente a 10.08 del
  control, +24.2 %; bases 37.49 frente a 46.28 y todas 32.15 frente a 39.45 pasan). Run
  `desnutricion_leve_e441_benchmark_test_6b07ee8c6316_dd8194504c84`. Queda `configured`, sin refit ni control.
- **Los otros dieciséis**: raw canónico de dos pasadas aisladas con el mismo CSV, revalidadas con el validador
  fijado; smoke de siete motores fallido en los dieciséis sólo por ETS y Ridge (EtsFitError/RidgeFitError;
  los cinco estacionales terminan). Con `rolling_cv_v1` ninguno puede seguir a full o selección.

| id | raw canónico (sha256) | snapshot | smoke 7 motores | bases con fallo ETS / Ridge (de 64) |
| --- | --- | --- | --- | --- |
| `absceso_hepatico_a064` | `ea66ddff309b…` | `a894a1c3` | `absceso_hepatico_a064_benchmark_smoke_a9de6a4dfd3f` | 55 / 30 |
| `ascariasis_b77` | `5f34ae699dba…` | `a894a1c3` | `ascariasis_b77_benchmark_smoke_46aa113bdd24` | 29 / 14 |
| `bocio_e01` | `59a2b16c6c82…` | `a894a1c3` | `bocio_e01_benchmark_smoke_a99f868dfe85` | 55 / 40 |
| `brucelosis_a23` | `ea2d2a5b1086…` | `a894a1c3` | `brucelosis_a23_benchmark_smoke_cf56497f7a72` | 61 / 52 |
| `calor_t67` | `6645f81ac2e9…` | `fe593a44` | `calor_t67_benchmark_smoke_54269513af65` | 60 / 37 |
| `desnutricion_moderada_e440` | `88b453d97de4…` | `a894a1c3` | `desnutricion_moderada_e440_benchmark_smoke_e167265b27d6` | 32 / 8 |
| `desnutricion_severa_e40` | `79048d43c588…` | `a894a1c3` | `desnutricion_severa_e40_benchmark_smoke_584df10f024b` | 33 / 10 |
| `enterobiasis_b80` | `3419e5effc87…` | `a894a1c3` | `enterobiasis_b80_benchmark_smoke_68f4c828768f` | 39 / 24 |
| `giardiasis_a071` | `24e0e606babf…` | `a894a1c3` | `giardiasis_a071_benchmark_smoke_a234f63330d8` | 37 / 17 |
| `helmintiasis_b65` | `8042fa33ebd7…` | `a894a1c3` | `helmintiasis_b65_benchmark_smoke_aab414ec74c9` | 5 / 3 |
| `hepatitis_a_b15` | `c6e2b477cfd7…` | `fe593a44` | `hepatitis_a_b15_benchmark_smoke_963cd234d0c9` | 59 / 29 |
| `hepatitis_b_b16` | `a01006d3e60c…` | `fe593a44` | `hepatitis_b_b16_benchmark_smoke_d53332fe2f36` | 52 / 28 |
| `leptospirosis_a27` | `4bc8e00d029b…` | `a894a1c3` | `leptospirosis_a27_benchmark_smoke_cc23fc379d25` | 30 / 38 |
| `otras_hepatitis_b17` | `1abc13cae510…` | `fe593a44` | `otras_hepatitis_b17_benchmark_smoke_d7374f701222` | 45 / 24 |
| `reumatica_i00` | `9bf02ef73823…` | `fe593a44` | `reumatica_i00_benchmark_smoke_4f0e4ea4c9c0` | 49 / 18 |
| `rotavirus_a080` | `0b3645e34410…` | `fe593a44` | `rotavirus_a080_benchmark_smoke_6ced20ed8793` | 60 / 54 |

## Decisiones del autor (respondidas el 12-nov-2026; historial de la pregunta)

Preguntas nominales enviadas por el supervisor, respondidas con «Autorizo A6, B2 y B14»:
- **A6**: control estacional (`seasonal_naive_lag52`, nunca validado) de desnutrición leve y de los cinco
  rechazos antiguos de alta20 (salmonelosis, tifoidea, escarlatina, hepatitis C, displasia severa):
  `docs/alta10b/PROPUESTA_CONTROL_LEVE.md`, `docs/alta10b/PROPUESTA_CONTROLES_RESERVA_5.md`.
- **B2**: política `rolling_cv_baja_incidencia_v1` para moderada y severa; **B14**: la misma para los otros
  catorce (`docs/alta10b/PROPUESTA_POLITICAS.md`).
El autor decide en el chat; root registra su respuesta auténtica (pregunta y respuesta literales) como JSON
con el esquema de `docs/alta10b/ESQUEMA_AUTORIZACION.md` para que las herramientas la consuman. El formato no
crea consentimiento ni revoca permisos ya otorgados (como la política de cinco motores de los 17 de alta20), y
no se vuelve a pedir una confirmación ya dada por falta del archivo. Los datos agregados de
esta tanda sí están autorizados para el análisis por los modelos (respuesta del usuario del 12-nov, 22:03 UTC).

## Operación y evidencia

- Cápsula de guiones y pruebas sintéticas: `docs/alta10b/operacion/` (README con limitaciones).
- Dictámenes de Fable (plan, continuidad, pretest de leve, código v1-v3): `docs/alta10b/revisiones/`.
  El dictamen de código aprueba el código en este alcance; no es aprobación científica ni de publicación.
- Evidencia fuera del repo: `planes/alta10b_2026-11-12/` (raws canónicos, registros de cada pasada, QA,
  logs, coordinación; `SHA256SUMS_TODO`); runs y datasets de la tanda en `runs/` del checkout principal
  (`runs_persistidos.txt`, `runs_manifiestos.SHA256SUMS`). Los releases y observaciones de los diez van por DVC selectivo.
