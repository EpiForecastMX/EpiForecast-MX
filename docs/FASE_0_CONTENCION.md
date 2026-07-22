# Fase 0 — Contención de la regresión de Obesidad

> Veredicto de auditoría: **Obesidad NO-GO.** Este doc registra el daño y las acciones de
> contención ejecutadas. El plan completo N+1 está en `PLAN_BRUTAL_OBESIDAD_N_PLUS_1.md`.

## Regresiones detectadas (varias introducidas en la sesión de "cierre" de Obesidad)

1. **Forecasts globales sobrescritos.** Correr `predice padecimiento.tipo='Obesidad'` para
   Prophet/Ensemble/Stacking **sobrescribió** `reports/forecasts/<motor>/all_forecast_<motor>.csv`
   dejándolos con SOLO Obesidad (se perdieron neuro+Dengue en el working tree).
2. **Prophet Obesidad ~4.6× bajo (expm1).** El loader recibe `padecimiento=None` para Obesidad
   (no es count-log), y el forecaster recomputa `log_transform` con el trait de `None` → no invierte
   el log → forecast en escala comprimida. (Fix real = fase posterior; ver plan.)
3. **rolling_cv_v1 nunca se ejecutó de verdad.** `produccion_obesidad.csv` etiqueta
   `criterio_seleccion=rolling_cv_v1` pero usó las métricas CV de `_completo.csv`, no un
   rolling-origin OOS real. Es PRELIMINAR.
4. **Obesidad se expuso en el dashboard público** estando `lifecycle=configured`.
5. **DeepAR: no fue deadlock.** Hubo sobre-paralelización (`n_jobs_train=-2` → ~11-22 procesos
   concurrentes) y corridas simultáneas; 59/111 artefactos. El diagnóstico previo de "deadlock
   StudentT" fue incorrecto.
6. Calendario con claves duplicadas / semanas sumadas (pendiente de auditar en el consolidado).

## Acciones de contención ejecutadas (Fase 0)

- ✅ **Evidencia preservada**: forecasts Obesidad-only + `produccion_obesidad.csv` copiados a
  `reports/_evidencia_regresion_ab201731/` con hashes SHA256 registrados.
- ✅ **Forecasts legacy restaurados** vía `dvc checkout reports/forecasts.dvc --force`. Verificado:
  Prophet/Ensemble/Stacking vuelven con Alzheimer/Depresión/Parkinson/Dengue.
- ✅ **Obesidad retirada del dashboard público**: revert de los 2 commits del EpiBot
  (`answerObesidad`, aliases, zoom) + cache-bust forward (app.js?v=135). Deploy limpio.
- ✅ **Guard en `predice`** (temporal): aborta si un padecimiento único sobrescribiría el agregado
  global multi-padecimiento. Probado: `predice Obesidad` aborta y el legacy queda intacto.
- ✅ **Sin procesos huérfanos** (verificado).

## NO ejecutado en Fase 0 (por diseño)

- NO `dvc add` / `dvc push` · NO entrenamiento · NO regenerar Tableau/Reports/web.

## Estado

- Baseline legacy (neuro+Dengue) recuperado y verificado.
- Obesidad NO visible como published.
- `produccion_obesidad.csv` y los modelos de Obesidad quedan como **PRELIMINAR / no productivo**.
- Siguiente: fases del plan (baseline verde, contratos de artefactos, shards+upsert, evaluación
  común OOS, y recién entonces re-onboarding de Obesidad).
