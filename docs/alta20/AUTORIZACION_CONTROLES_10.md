# Autorización nominal de diez controles estacionales (12-nov-2026)

El autor respondió «Autorizar estos diez controles» a la pregunta nominal que enumeraba los diez runs rechazados
en la prueba de 2025, con las cifras de portafolio y control en bases, en las 111 series (o 37 sin sexo) y en el
total nacional (respuesta registrada a las 17:44 UTC; sha256 de la propuesta `e46b76e304c3…`).

Alcance exacto: publicar el control estacional (`seasonal_naive_lag52`) de cada run por `acceptance_fallback_run`.
No cubre los otros cinco rechazos (displasia severa, salmonelosis, tifoidea, escarlatina, hepatitis C), ni
padecimientos sensibles nuevos, ni cambios de umbrales, ni repetir 2025. Ningún rechazo se modifica: cada
`acceptance.json` sigue con `accepted: false` y la política del candidato es la misma con la que se rechazó.

Rótulo público: «Control estacional publicado tras el rechazo de 2025, no validado». El gate prospectivo compara
el control contra sí mismo (`CONTROL_ONLY`): no es una validación en curso ni puede dar PASS.

| Padecimiento | Run rechazado | sMAPE nacional portafolio / control | Bases | Todas |
| --- | --- | --- | --- | --- |
| Quemaduras (`quemaduras_t20`) | `quemaduras_t20_benchmark_test_3ee23b369061_7fd183fca72f` | 8.63 / 6.97 | 29.11 / 32.87 | 24.76 / 30.13 |
| Insuficiencia venosa periférica (`ivp_i87`) | `ivp_i87_benchmark_test_86b795779321_7a69e6966bcb` | 9.03 / 7.30 | 22.82 / 26.58 | 19.76 / 22.98 |
| Hiperplasia de la próstata (`hiperplasia_prostata_n40`) | `hiperplasia_prostata_n40_benchmark_test_4a45876cb639_6a1049adb802` | 9.50 / 8.34 | 24.98 / 25.03 | 22.34 / 23.73 |
| Escabiosis (`escabiosis_b86`) | `escabiosis_b86_benchmark_test_f757ff2af8bc_89ef62587a7c` | 13.37 / 10.46 | 51.65 / 59.96 | 44.61 / 44.62 |
| Otras infecciones intestinales debidas a protozoarios (`protozoarios_a07`) | `protozoarios_a07_benchmark_test_60c51f1b0a1a_6e4ed0a35dea` | 13.01 / 11.16 | 63.58 / 71.04 | 58.38 / 62.83 |
| Faringitis y amigdalitis estreptocócicas (`faringitis_j02`) | `faringitis_j02_benchmark_test_b3be128c1aba_bbdda2490c60` | 17.42 / 12.80 | 48.98 / 45.13 | 41.51 / 41.51 |
| Peatón lesionado en accidente de transporte (`peaton_v01`) | `peaton_v01_benchmark_test_e57ad653f75b_4f91a630c610` | 26.29 / 12.95 | 80.55 / 84.76 | 74.22 / 77.23 |
| Displasia cervical leve y moderada (`displasia_leve_n87`) | `displasia_leve_n87_benchmark_test_541e5a8aff9a_0719c523962f` | 28.34 / 13.87 | 61.73 / 62.72 | 58.65 / 52.36 |
| Varicela (`varicela_b01`) | `varicela_b01_benchmark_test_8309f5910745_d751580feeaa` | 27.65 / 16.73 | 46.71 / 46.82 | 42.86 / 39.22 |
| Parotiditis infecciosa (`parotiditis_b26`) | `parotiditis_b26_benchmark_test_6a754a997a97_37028dd91872` | 36.28 / 19.17 | 90.19 / 97.30 | 85.53 / 89.31 |

Las métricas de bases y de todas las series incluyen ceros y el reparto por sexo reconstruido cuando el boletín
no lo separa; no son una certificación clínica.

## Ejecución (12-nov-2026)

`acceptance_fallback_run` se commiteó en `1e5602ce` antes de cualquier refit; los veinte manifests de refit y
pronóstico registran ese `code_commit`. Ningún benchmark de test se abrió de nuevo. Índice oficial comprobado
(sem43) antes de emitir cada pronóstico y antes de congelar los gates.

| Padecimiento | Refit | Pronóstico | Release |
| --- | --- | --- | --- |
| `quemaduras_t20` | `quemaduras_t20_refit_final_9fe0414b00c7_27f30c8a4d7a` | `quemaduras_t20_forecast_h52_27f30c8a4d7a_3bc2f693f43a` | `quemaduras_t20_release_5913e2fa576b` |
| `ivp_i87` | `ivp_i87_refit_final_9fe0414b00c7_494905741dc9` | `ivp_i87_forecast_h52_494905741dc9_d91d6d4b6564` | `ivp_i87_release_0b4b7fb06127` |
| `hiperplasia_prostata_n40` | `hiperplasia_prostata_n40_refit_final_30e6b4ef89df_b75a59c06b37` | `hiperplasia_prostata_n40_forecast_h52_b75a59c06b37_a586b18aaf3f` | `hiperplasia_prostata_n40_release_7078e93866c5` |
| `escabiosis_b86` | `escabiosis_b86_refit_final_9fe0414b00c7_49303fdeec36` | `escabiosis_b86_forecast_h52_49303fdeec36_cab22387abbf` | `escabiosis_b86_release_55c69e88b18a` |
| `protozoarios_a07` | `protozoarios_a07_refit_final_9fe0414b00c7_9a28a3d3d00d` | `protozoarios_a07_forecast_h52_9a28a3d3d00d_7e033fec2967` | `protozoarios_a07_release_f2efbad8fcea` |
| `faringitis_j02` | `faringitis_j02_refit_final_9fe0414b00c7_bbb188de53b3` | `faringitis_j02_forecast_h52_bbb188de53b3_785544542479` | `faringitis_j02_release_2733559c9175` |
| `peaton_v01` | `peaton_v01_refit_final_9fe0414b00c7_75712d57e01c` | `peaton_v01_forecast_h52_75712d57e01c_bd93fcf87e18` | `peaton_v01_release_59de3df5aba6` |
| `displasia_leve_n87` | `displasia_leve_n87_refit_final_30e6b4ef89df_7223bba1daed` | `displasia_leve_n87_forecast_h52_7223bba1daed_a546339278f8` | `displasia_leve_n87_release_df5afab4a165` |
| `varicela_b01` | `varicela_b01_refit_final_9fe0414b00c7_773ae56e9f11` | `varicela_b01_forecast_h52_773ae56e9f11_05f4961e437f` | `varicela_b01_release_1233ee2e330c` |
| `parotiditis_b26` | `parotiditis_b26_refit_final_9fe0414b00c7_a26ee2d5434b` | `parotiditis_b26_forecast_h52_a26ee2d5434b_80c9a8baae6f` | `parotiditis_b26_release_703a6ec438ef` |

El digest de la autorización (`proposal_sha256` e46b76e3…) liga `PROPUESTA_CONTROLES_10.json`; el Markdown de
la propuesta (f7fbf4f0…) se conserva sin editar. Evidencia (propuesta, autorización, índices consultados, logs
de refit y pronóstico, incluida la corrida aparte de quemaduras): `planes/alta20_controles10_2026-11-12/`, con
SHA256SUMS, fuera del repositorio.
