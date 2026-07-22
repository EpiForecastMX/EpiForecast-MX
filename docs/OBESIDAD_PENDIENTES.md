# Obesidad (E66) — Estado de cierre y pendientes

## Estado: NO-GO / CONTENIDA (Fase 0) — NO cerrada

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
- **Selección** (`reports/ProdDetails/produccion_obesidad.csv`): 111 series →
  **Ensemble 62 / Prophet 26 / Stacking 23**. Nacional = Ensemble (3 sexos).
- **Lectura preliminar (métricas CV, in-sample):** Ensemble el mejor motor (MASE mediana 0.87);
  77% de las series le ganan al naive estacional; **el nacional es el foco amarillo (MASE 1.07–1.23:
  ningún motor supera al naive a nivel país).**

## PENDIENTE 1 — DeepAR en SageMaker GPU (no local)

**Por qué:** DeepAR local se **deadlockea intermitentemente en Apple Silicon** (sampling StudentT;
limitación documentada en CLAUDE.md). Se probó secuencial (`n_jobs_train=1`, load bajo) y aun así
cuelga el `fit()` de ciertos estados (Jalisco, Nayarit, Nuevo León). Se alcanzó **59/111** (Nacional
3/3 completo) antes de abandonar el intento local.

**Cómo cerrarlo:** correr DeepAR en **SageMaker GPU** — el camino que el proyecto ya usa:
`make train-sagemaker` (o `make dengue-train` como referencia) con `padecimiento.tipo='Obesidad'`.
Ahí no hay deadlock (CUDA, no MPS). Luego `predice` + re-correr `produccion_padecimiento --disease
Obesidad` para la selección de **4 motores** y ver si DeepAR mueve el nacional.

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

## PENDIENTE 3 — Publicación formal

Obesidad se hace visible en el EpiBot para revisión (ver abajo), pero la publicación formal
(`dvc add/push` del consolidado + modelos a S3, deploy productivo, refactor JS data-driven completo
de EPIC 4) queda para cuando cierre DeepAR y la selección de 4 motores.
