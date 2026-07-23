# Obesidad (E66) — Estado de cierre y pendientes

## Estado: Fase 0 CERRADA · Obesidad NO-GO (no productiva) · Siguiente: Fase 1 (lifecycle gate del selector)

> **CORRECCIÓN:** una auditoría posterior encontró regresiones graves (forecasts globales
> sobrescritos, Prophet ~4.6× bajo por expm1, rolling_cv_v1 nunca corrió, exposición prematura
> en el dashboard). Obesidad está **NO-GO** y se contuvo en Fase 0. Ver `FASE_0_CONTENCION.md`
> y el plan `PLAN_BRUTAL_OBESIDAD_N_PLUS_1.md`. Lo de abajo describe el intento preliminar, NO
> un cierre válido.

## Intento preliminar (NO productivo)

Obesidad quedó integrada end-to-end por la maquinaria genérica del registry (1 entrada +
1 grupo de cuadro), **sin fork**:

- **Datos:** extraída del Cuadro 14.1 (653 boletines, 20,896 filas, contrato exacto),
  mergeada al consolidado (neuro+Dengue byte-idénticos), prep INEGI (32 estados, 4 regiones).
- **Modelos:** Prophet / Ensemble / Stacking **111 c/u** (Nacional + 32 estados + 4 regiones × 3 sexos).
- **Selección** (preliminar, movida a `reports/ProdDetails/_preliminar_NO_GO/produccion_obesidad_PRELIMINAR.csv`):
  111 series → **Ensemble 62 / Prophet 26 / Stacking 23**. Nacional = Ensemble (3 sexos).
  ⚠️ El `criterio_seleccion` era `rolling_cv_v1` pero fue **CV in-sample**, no OOS real (relabelado
  `insample_cv_PRELIMINAR_NO_GO`).
- **Lectura preliminar (métricas CV, in-sample):** Ensemble el mejor motor (MASE mediana 0.87);
  77% de las series le ganan al naive estacional; **el nacional es el foco amarillo (MASE 1.07–1.23:
  ningún motor supera al naive a nivel país).**

## PENDIENTE 1 — DeepAR (incompleto)

> ⚠️ **NO ejecutar los comandos de abajo como están.** Obesidad es **NO-GO** (ver
> `FASE_0_CONTENCION.md`). Cualquier reentrenamiento/publicación va **solo** dentro del
> re-onboarding por fases de `PLAN_BRUTAL_OBESIDAD_N_PLUS_1.md`, con contratos de artefactos
> y upsert atómico — NO sobre los scripts actuales que sobrescriben agregados globales.

**Diagnóstico corregido (auditoría):** el DeepAR de Obesidad NO se colgó por un "deadlock StudentT".
Lo que ocurrió fue **sobre-paralelización**: `n_jobs_train=-2` lanzó ~11-22 procesos concurrentes y,
además, corridas simultáneas, saturando la máquina. Se alcanzaron **59/111** artefactos antes de
abortar. (El caveat de MPS/concurrencia en CLAUDE.md es real y se debe respetar, pero **no** fue la
causa aquí.)

**Cómo cerrarlo:** NO es "correr SageMaker + `predice`". El camino autoritativo es el
**protocolo D0–D3** de `PLAN_BRUTAL_OBESIDAD_N_PLUS_1.md` (§4.4–4.7): **D0** harness reproducible,
**D1** matriz de dispositivo/distribución, **D2** tamaño/estabilidad, **D3** rediseño global — recién
tras pasarlo se decide dispositivo (CPU `n_jobs_train=1` vs SageMaker GPU/CUDA). El `predice` posterior
requiere primero el fix expm1 del loader **y** el upsert atómico por-enfermedad (no sobrescribir
agregados globales). La selección de 4 motores debe ser OOS **real**, no in-sample. Todo esto queda
tras el **OK formal de Fase 1**.

**Caveat de comparación:** DeepAR es autorregresivo → su "ajuste" in-sample eco-a la realidad
(sMAPE 0 trivial). Para compararlo justo NO usar el ajuste in-sample; usar **CV** o **pronóstico
congelado OOS** (entrenar hasta 2023, pronosticar 2024 a ciegas).

## PENDIENTE 2 — Probar otros modelos / afinar

- **Re-tunear el grid de Prophet** de Obesidad (hoy es v1: additive/multiplicative, cps 0.01/0.03/0.05,
  sps 0.05/0.1/0.5). Prophet queda en MASE ~1.01 (subajuste) — hay margen.
- **NB-GLM** (hoy exclusivo de Dengue) podría ayudar en el nivel/estacionalidad crónica — evaluar.
- **El foco amarillo del nacional:** ningún motor le gana al naive estacional a nivel país. Explorar
  regresor exógeno estable, o aceptar el naive como baseline nacional y quedarse con el valor que el
  modelo sí aporta a nivel estatal (77% > naive).
- **Selección OOS honesta** (`rolling_cv_v1` real con 4 holdouts, o pronóstico congelado) en vez de
  las métricas CV in-sample actuales, antes de declarar números "sin asterisco".

## PENDIENTE 3 — Publicación formal (BLOQUEADA)

> Obesidad estuvo brevemente visible en el EpiBot y **se revirtió en Fase 0** (NO-GO). Hoy es
> **invisible** en toda superficie publicada.

La publicación formal (`dvc add/push` del consolidado + modelos a S3, deploy productivo, refactor JS
data-driven de EPIC 4, flip a `lifecycle=published`) queda **bloqueada** hasta completar el
re-onboarding por fases del plan: baseline verde con tests que detecten producción rota, contratos de
artefactos, shards + upsert atómico, evaluación OOS honesta y recién entonces re-modelar. El flip a
`published` ocurre **dentro del mismo commit de deploy** que contiene todos los artefactos.
