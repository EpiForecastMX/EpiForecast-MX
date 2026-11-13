# Propuesta nominal al autor: control estacional para desnutrición leve (E44.1)

Esto es una propuesta, no una autorización. Ningún control se publica sin una orden nominal del autor
posterior a estas cifras. La prueba de 2025 se abrió una vez y no se reabre.

## Resultado de la prueba única de 2025 (12-nov-2026, 21:36 UTC; 16:36 hora del este)

- Run: `desnutricion_leve_e441_benchmark_test_6b07ee8c6316_dd8194504c84` @ `e3ba3666`, selección
  `desnutricion_leve_e441_select_f114ac85adf5_fe2324b2e0e7`, dataset `desnutricion_leve_e441_e211223d9d39`,
  raw `d88a5327…`, política `rolling_cv_v1` (siete motores), 53 semanas.
- Veredicto: **rechazado** en el total nacional.

| ámbito | portafolio | control `seasonal_naive_lag52` | diferencia | máximo | resultado |
| --- | ---: | ---: | ---: | ---: | --- |
| sMAPE 64 bases | 37.49 | 46.28 | -19.0 % | 5 % | pasa |
| sMAPE 111 productos | 32.15 | 39.45 | -18.5 % | 5 % | pasa |
| sMAPE nacional general | 12.52 | 10.08 | +24.2 % | 10 % | falla |
| MASE 64 bases | 0.587 | 0.722 | | | |
| MASE 111 productos | 0.566 | 0.687 | | | |

## Qué se propone y qué significaría

Publicar desnutrición leve con el control `seasonal_naive_lag52` (`acceptance_fallback_run` = el run de
arriba, `acceptance_outcome: fallback_control`), igual que los diez controles de alta20: nunca presentado
como validado ni como PASS; el gate prospectivo compararía el control contra sí mismo (`CONTROL_ONLY`).
El portafolio fue mejor en estados y productos, pero el gate se decide por los tres ámbitos y no se cambia.

Sin orden nominal: queda `configured`, run conservado, sin refit ni release.
