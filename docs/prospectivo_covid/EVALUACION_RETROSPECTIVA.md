# Referencias recientes de Covid-19: resultado

Selección con 2023 y 2024 y evaluación retrospectiva en 2026 previamente visto, 7-nov-2026. Resultado
exploratorio reproducible. No publica nada.

| sMAPE nacional | control `lag52` | `ultimo` |
| --- | ---: | ---: |
| Selección 2023 y 2024, media h=1..4 | 147.7 | 47.4 |
| Reservado 2026, h=1 | 103.5 | 32.4 |
| Reservado 2026, h=2 | 103.5 | 44.9 |
| Reservado 2026, h=3 | 103.5 | 56.2 |
| Reservado 2026, h=4 | 103.5 | 63.5 |
| Reservado 2026, media | 103.5 | 49.2 |
| 2026 sin W42, media | 103.1 | 46.8 |
| 2025, solo descriptivo | 88.5 | 37.8 |

Mejora media en 2026: 54.2 puntos de sMAPE. Intervalo exploratorio, no preregistrado, por bootstrap
circular de 5,000 réplicas: 19.2 a 92.1 con bloques de 4 semanas, 11.0 a 102.9 con 8 y 9.6 a 108.2 con
13. Mediana de 32 entidades en 2026: 128.92 frente a 76.59.

Candidatas en selección: {'lag52': 147.74, 'ultimo': 47.43, 'media_4': 62.25, 'media_8': 80.16, 'media_13': 93.71, 'mediana_13': 90.64}.

Lectura: resultado favorable a congelar `ultimo` como referencia de corto plazo. No acredita un modelo
publicable ni resuelve 52 semanas.

## Salvedades de la auditoría del 7-nov-2026

- `evalua.py` calculaba las seis candidatas en 2026 y sólo guardaba dos. No hubo reselección, pero
  contradecía el preregistro. `evalua_v2.py` exige candidatas explícitas y da las mismas cifras
  (`reservado_v2.json`). El original se conserva intacto.
- Es un backtest cronológico: no reconstruye qué versión de cada dato existía en cada fecha.
- Los hashes acreditan integridad, no que 2026 se abriera una sola vez.
- `lag52` son 52 semanas antes; tras un año de 53 no es la misma semana epidemiológica.
- La discrepancia a 52 semanas queda resuelta: es la W39 de 2024, imputada. Con ella, 163.624 y 87.654;
  sin ella, 163.802 y 86.992.
