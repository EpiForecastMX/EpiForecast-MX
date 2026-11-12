# C7.16 · Lote alta10b: preparación, 0 publicados (12-nov-2026)

Orden del autor: incorporar diez padecimientos más (65 en el sitio, 61 del runner). **Estado: en preparación,
ninguno publicado.** El sitio sigue con 55 publicados y 51 del runner. Este cierre integra sólo código,
configuración en `configured`, pruebas y documentación; no activa ni promete ningún padecimiento.

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

## Decisiones del autor pendientes (no se toman aquí)

Preguntas nominales ya enviadas por el supervisor, sin respuesta:
- **A6**: control estacional (`seasonal_naive_lag52`, nunca validado) de desnutrición leve y de los cinco
  rechazos antiguos de alta20 (salmonelosis, tifoidea, escarlatina, hepatitis C, displasia severa):
  `docs/alta10b/PROPUESTA_CONTROL_LEVE.md`, `docs/alta10b/PROPUESTA_CONTROLES_RESERVA_5.md`.
- **B2**: política `rolling_cv_baja_incidencia_v1` para moderada y severa; **B14**: la misma para los otros
  catorce (`docs/alta10b/PROPUESTA_POLITICAS.md`).
Una autorización sólo vale en el formato de `docs/alta10b/ESQUEMA_AUTORIZACION.md`. Los datos agregados de
esta tanda sí están autorizados para el análisis por los modelos (respuesta del usuario del 12-nov, 22:03 UTC).

## Operación y evidencia

- Cápsula de guiones y pruebas sintéticas: `docs/alta10b/operacion/` (README con limitaciones).
- Dictámenes de Fable (plan, continuidad, pretest de leve, código v1-v3): `docs/alta10b/revisiones/`.
  El dictamen de código aprueba el código en este alcance; no es aprobación científica ni de publicación.
- Evidencia fuera del repo: `planes/alta10b_2026-11-12/` (raws canónicos, registros de cada pasada, QA,
  logs, coordinación; `SHA256SUMS_TODO`); runs y datasets de la tanda en `runs/` del checkout principal
  (`runs_persistidos.txt`, `runs_manifiestos.SHA256SUMS`). Sin DVC nuevo: no hay selección publicable.
