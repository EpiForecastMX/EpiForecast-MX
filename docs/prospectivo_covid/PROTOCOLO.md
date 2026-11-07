# Protocolo prospectivo de `ultimo` para Covid-19

Aprobado por el autor el 7-nov-2026, antes de recibir el boletín 43. No publica nada.

- **Emisión:** por cada boletín nuevo, antes de leer el siguiente, un archivo
  `docs/prospectivo_covid/emisiones/<año>-W<ss>.json` con los pronósticos a 1-4 semanas, el dato de
  entrada, su fuente y el sha256 del raw, y su commit en GitHub como registro fechado. Una emisión no
  se reescribe.
- **Referencias:** `ultimo` (último valor observado publicado) y `lag52` (52 semanas antes).
- **Objetivos:** semanas 2026-W43 en adelante, total nacional general, horizontes 1 a 4.
- **Revisiones:** cada objetivo se puntúa contra su primera publicación y, por separado, contra el valor
  del boletín cuatro semanas posterior. Conservar cada versión del PDF y del raw.
- **Imputaciones:** una semana sin boletín o imputada no se puntúa, se registra y no se rellena.
- **Evaluación:** tras 26 objetivos observados a h=1, sin mirar antes el resultado acumulado.
- **Criterio de éxito:** sMAPE medio de `ultimo` en h=1..4 al menos 25 % menor que `lag52`, y
  sMAPE de `ultimo` a h=1 no mayor que 40. Cumplirlo habilita discutir una referencia de corto plazo,
  no publicar un modelo ni resolver 52 semanas.
