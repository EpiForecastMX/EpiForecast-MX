# PRELIMINAR / NO-GO — Obesidad (E66)

> **NO es producción.** Este directorio contiene artefactos preliminares de Obesidad que la
> auditoría marcó **NO-GO** (ver `docs/FASE_0_CONTENCION.md`). Se sacaron de la raíz canónica
> `reports/ProdDetails/` para que **ningún proceso ni humano los confunda con producción**.

## `produccion_obesidad_PRELIMINAR.csv`

- Copia del `produccion_obesidad.csv` original con la etiqueta corregida.
- **`criterio_seleccion` era `rolling_cv_v1` — ERA FALSO.** La selección usó métricas de CV
  **in-sample** (de `_completo.csv`), NO un rolling-origin OOS real. Se relabeló a
  `insample_cv_PRELIMINAR_NO_GO` (estado honesto, machine-readable).
- Ningún código de producción lo descubre por glob: `catalog.py` y `build_web_knowledge.py`
  referencian `produccion_dengue.csv` por **nombre exacto**, nunca `produccion_*.csv`.
- El original **byte-idéntico** (con la etiqueta falsa) queda como evidencia forense en
  `reports/_evidencia_regresion_ab201731/produccion_obesidad.csv` (hash en `SHA256SUMS.txt`).

## Por qué NO-GO (resumen)

Prophet ~4.6× bajo (expm1 sin invertir), `rolling_cv_v1` nunca corrió de verdad, DeepAR incompleto
(sobre-paralelización, no deadlock), forecasts globales sobrescritos (ya contenido). El
re-onboarding correcto sigue las fases de `docs/PLAN_BRUTAL_OBESIDAD_N_PLUS_1.md`.
