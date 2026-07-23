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

## Cierre formal de Fase 0 (brechas de la re-auditoría)

La re-auditoría confirmó la contención técnica en verde y señaló 4 brechas formales + 1 anomalía
legacy. Cerradas así:

1. ✅ **SHA256SUMS persistido.** `reports/_evidencia_regresion_ab201731/SHA256SUMS.txt` con los 4
   artefactos de evidencia; `shasum -c` verde.
2. ✅ **`produccion_obesidad.csv` fuera de la ruta canónica + estado honesto.** Movido a
   `reports/ProdDetails/_preliminar_NO_GO/produccion_obesidad_PRELIMINAR.csv` (con `README.md`).
   La etiqueta falsa `criterio_seleccion=rolling_cv_v1` se corrigió a
   `insample_cv_PRELIMINAR_NO_GO` (era CV **in-sample**, no rolling-origin OOS). El original
   byte-idéntico queda como evidencia forense. **Verificado que ningún código de producción lo
   descubre por glob** (`catalog.py`/`build_web_knowledge.py` leen `produccion_dengue.csv` por
   nombre exacto).
3. ✅ **Diagnóstico falso de deadlock corregido.** `OBESIDAD_PENDIENTES.md` y
   `PROGRESO_NOCTURNO_OBESIDAD.md`: se reemplazó "deadlock StudentT" por la causa real
   (**sobre-paralelización** `n_jobs_train=-2` → ~11-22 procesos + corridas simultáneas). Las
   instrucciones de entrenamiento/publicación de ambos docs quedaron marcadas **NO-GO / bloqueadas**
   (el `predice Obesidad` de esas recetas es justo lo que sobrescribió los agregados globales).
4. 🟡 **DVC global.** Se restauró la superficie **publicada** `data/processed/tableau_model.xlsx` a
   su puntero (`dvc checkout`; contenía **cero Obesidad**). Queda intencionalmente sucio, como
   **WIP aditivo de Obesidad NO pusheado y NO publicado**, lo siguiente:
   - `data/processed/dataset_boletin_epidemiologico.csv` — Obesidad mergeada (neuro 20896 c/u +
     Dengue 12768 **byte-idénticos**; Obesidad +20896). Es la extracción E66 (EPIC 2), la única
     parte que la auditoría **no** marcó rota.
   - `models/{prophet,deepar,ensemble,stacking}/Obesidad/` — modelos preliminares.
   - `data/raw/data_raw_Obesidad.csv` · `reports/figures/*Obesidad*.png` — WIP local.
   - `logs/` — efímero (se conserva por valor forense de esta sesión).

   **No se revierte** para no destruir la extracción E66 válida (se reutiliza en el re-onboarding).
   `reports/forecasts.dvc` y `tableau_model.xlsx.dvc` están **limpios**. Nada se `dvc push`eó.

   > ⚠️ **No hay comando de reversión global aquí, a propósito.** Un `dvc checkout` **sin target**
   > borraría la extracción E66 y los modelos WIP. Dejar el árbol prístino es una decisión
   > **destructiva y explícita del usuario**, y debe hacerse **por target concreto** (p. ej. solo
   > `dvc checkout models.dvc`), nunca en bloque.

## Anomalía legacy pre-existente (NO tocar — no es de Fase 0)

- **Stacking · Alzheimer termina una semana antes.** En `all_forecast_stacking.csv`, Alzheimer llega
  a `2027-01-18` (75,591 filas), mientras Depresión/Parkinson llegan a `2027-01-25` (75,702) — faltan
  **111 filas** (1 semana × 111 series) de Alzheimer. Está en el archivo **restaurado desde el puntero
  DVC**, o sea **precede a Obesidad** y **coincide con producción**. **No se corrige** aquí: alterarlo
  rompería la garantía byte-idéntico-al-puntero. Queda flageado para investigación en **Fase 1**.

## Primer contrato de Fase 1 (identificado, NO implementado aquí)

- **`scripts/produccion_padecimiento.py:104` ignora `lifecycle`.** Escribe
  `criterio_seleccion = d.selection_policy` (para Obesidad = `rolling_cv_v1`) en la **ruta canónica**
  `reports/ProdDetails/produccion_{slug}.csv` = `produccion_obesidad.csv`, sin verificar que el
  padecimiento esté `published`. Correrlo para Obesidad **recrearía** el CSV canónico con la etiqueta
  `rolling_cv_v1` (deshaciendo el fix de Fase 0).
  - **Mitigación actual (no código):** solo se dispara con invocación **explícita** `--disease Obesidad`
    (no está en ningún flujo neuro/Dengue automático) y la ruta canónica hoy está vacía.
  - **Contrato Fase 1:** el selector debe (a) respetar `lifecycle` (abortar/escribir a `_preliminar/`
    si no es `published`) y (b) no etiquetar `rolling_cv_v1` sin haber corrido un rolling-origin OOS
    real. Es la primera historia de código de Fase 1; **requiere OK formal**.
