# Propuesta nominal (para que root la agrupe): control estacional de los cinco rechazos antiguos

Es una propuesta, no una autorización. No se reabre 2025, no hay prueba nueva, ni refit, ni release
hasta una orden nominal del autor posterior a estas cifras. Las cinco identidades no están entre los 51
del runner de `baseline_catalog.json` ni en el sitio: si el autor las autoriza, cuentan como identidades
nuevas del lote alta10b. No se confunden con los veinte de alta20 (ya publicados).

## Qué son y de dónde salen

Las cinco rechazaron en la prueba única de 2025 del lote alta20 (12-nov-2026, commit `89ae90ae`), con la
política `rolling_cv_baja_incidencia_v1` (cinco motores estacionales) que el autor autorizó por nombre
para el lote 17 (`docs/alta20/AUTORIZACION_POLITICA_17.md`). Desde entonces siguen `configured`, sin
`acceptance_fallback_run` y sin control (`docs/C7_15_ALTA20.md`, «Siguen sin publicar»). Cifras leídas de los
artefactos sellados `runs/<test_run>/acceptance.json` del checkout principal; el raw actual de cada una
coincide con el `raw` de su `dataset_manifest.json` (sha256 en la tabla). Datasets 2014-W01 a 2026-W42
(corte vigente: boletín 43).

| id | padecimiento (CIE-10) | sexo | run de la prueba de 2025 | raw (sha256) |
| --- | --- | --- | --- | --- |
| `salmonelosis_a02` | Otras salmonelosis (A02) | por sexo, 64 bases / 111 | `salmonelosis_a02_benchmark_test_75d53be6359d_87e5e12dc46a` | `3544e9b62046…` |
| `tifoidea_a01` | Fiebre tifoidea (A01.0) | por sexo, 64 / 111 | `tifoidea_a01_benchmark_test_4510e3cd424e_28c71501a392` | `31e1776d823a…` |
| `escarlatina_a38` | Escarlatina (A38) | por sexo, 64 / 111 | `escarlatina_a38_benchmark_test_fd6d4b0c510d_57d3b1ad9b6a` | `df19bc873bbd…` |
| `hepatitis_c_b17` | Hepatitis vírica C (B17.1, B18.2) | por sexo, 64 / 111 | `hepatitis_c_b17_benchmark_test_dc3594e102bf_63c4ba3b7395` | `35a77feb4db1…` |
| `displasia_severa_n87` | Displasia cervical severa y cáncer cervicouterino in situ (N87.2, D06) | sin sexo, 32 / 37 | `displasia_severa_n87_benchmark_test_c9f925d40d4c_ab071604cd0a` | `b932164e08a6…` |

## Prueba de 2025 (sMAPE; portafolio frente a `seasonal_naive_lag52`)

| id | bases | todas las series | nacional general | ámbito que falla | motores en el portafolio |
| --- | ---: | ---: | ---: | --- | --- |
| `salmonelosis_a02` | 74.78 / 76.18 | 67.18 / 67.92 | 42.10 / 31.81 | nacional (+32.3 %) | 5 estacionales |
| `tifoidea_a01` | 63.61 / 73.46 | 62.86 / 71.70 | 43.78 / 36.05 | nacional (+21.4 %) | 5 estacionales |
| `escarlatina_a38` | 59.75 / 72.96 | 74.21 / 76.73 | 46.70 / 36.28 | nacional (+28.7 %) | 4 (sin media 5 años) |
| `hepatitis_c_b17` | 81.89 / 91.02 | 81.68 / 88.35 | 55.31 / 37.00 | nacional (+49.5 %) | 5 estacionales |
| `displasia_severa_n87` | 88.97 / 99.07 | 79.27 / 90.44 | 24.18 / 21.28 | nacional (+13.6 %) | 4 (sin mediana 3 años) |

Umbrales de la regla (sin cambios): 5 % en bases, 5 % en todas, 10 % en el nacional. En las cinco el
portafolio fue mejor que el control en estados y en el conjunto, y peor en el total nacional.

## Qué significaría autorizar

Publicar el control `seasonal_naive_lag52` de cada run por `acceptance_fallback_run`, con
`acceptance_outcome: fallback_control`, igual que los diez controles de alta20: refit del control, forecast de
52 semanas desde W42, release y gate con candidato igual al control (`CONTROL_ONLY`): nunca validado ni PASS.
La ficha diría «control estacional, no validado» (generador `scripts/gen_fichas.py`, modo control).

## Limitaciones que el autor debe ver antes de decidir

- **El control repite el año anterior.** Su error en 2025 fue alto en estados y en el conjunto (sMAPE de 67.9 a
  99.1): es una referencia poco informativa por estado, sobre todo en hepatitis C y displasia severa.
- **Errata de fuente en 2016_sem20** (bloques rotados, el mismo boletín que ya se excluye para diabetes y
  cardiovasculares): presente en el raw sellado de escarlatina (semana 3 766 frente a 61 y 76) y de
  salmonelosis (acumulado 19 frente a 26 820 y 30 259), sin exclusión declarada (`qa/<id>_reserva_acumulado.json`).
  Está en el desarrollo (2016) y no entra en el pronóstico del control (que usa las últimas 52 semanas), pero
  sí estuvo en el entrenamiento del portafolio ya evaluado; no se reevalúa (no se reabre 2025). Tifoidea, hepatitis
  C y displasia severa no muestran esa errata.
- **Picos aislados** que el control hereda: revisar con el aviso de picos de `gen_fichas.py` y el PDF antes de
  redactar la ficha, según la regla vigente (no se corrige el dato).
- **Displasia severa** se publica sin desglose por sexo (32 bases, 37 productos), como displasia leve.
- **Sensibilidad:** la revisión del alta20 no marcó a ninguna como sensible. Hepatitis C tiene transmisión
  sanguínea y sexual y la displasia severa es un diagnóstico oncológico ginecológico; si el autor quiere un
  tratamiento editorial distinto, es su decisión. No se propone excluirlas.

## Forma de la orden, si el autor decide

Para que `scripts/lista_publicables.py` la lea, el archivo `AUTORIZACION_AUTOR*.md` debe contener una línea
exacta por cada id autorizado: `AUTORIZA_CONTROL <id> <test_run>`. Una autorización parcial es válida; sin
esa línea el id queda `configured`.
