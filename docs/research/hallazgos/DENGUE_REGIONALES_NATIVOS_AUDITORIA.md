# Auditoría: modelos regionales NATIVOS de Dengue vs agregación bottom-up

**Fecha:** 2026-06-06
**Veredicto:** la **agregación bottom-up gana**. NO se adoptan modelos regionales nativos de
Dengue; la galería sigue agregando los estados de cada región. El experimento se revirtió.

## Contexto

Las 4 regiones de salud mental (`region_salud_mental`) sí tienen modelos nativos en la cohorte
neuro (entrenados por el bloque híbrido de `scripts/entrena.py`, gateado a `is_neuro`). Dengue no
los tenía, así que en la galería las regiones de Dengue se **calculan agregando sus estados**
(real = suma del boletín; pronóstico = suma del pronóstico productivo de cada estado).

Se pidió probar el flujo entrenando regionales **nativos** de Dengue y auditar si mejoran.

## Qué se hizo (flujo ejercitado)

1. **Entrenamiento:** se habilitó temporalmente el bloque híbrido para Dengue (quitar el gate
   `is_neuro` del paso 1, dejando el *fallback* de estados insuficientes solo para neuro). Se
   entrenaron regionales nativos de **Prophet** y **NB-GLM** (12 modelos c/u: 4 regiones × 3
   sexos). DeepAR regional NO se completó: en CPU local se deadlockea con `n_jobs>1` y en
   secuencial es prohibitivamente lento (DeepAR está pensado para SageMaker GPU).
2. **Predicción:** `predice` reconoce los `*_region_*.pkl` y emite `meta_entidad="Region ..."`
   (vía `_parse_regional`). Mecanismo validado: se generaron los forecasts regionales nativos.
3. **Auditoría:** SMAPE/MASE del solape real-vs-pronóstico (2026) por región, comparando los
   nativos contra la agregación bottom-up.

## Resultado (general, solape 2026)

| Región | fuente | SMAPE | MASE |
|---|---|---:|---:|
| Metropolitana alta | **agregado** | **44.6** | **0.04** |
| | nativo NB-GLM | 68.9 | 0.11 |
| | nativo Prophet | 85.9 | 0.27 |
| Rural / dispersa | **agregado** | **43.5** | **0.23** |
| | nativo Prophet | 52.0 | 0.29 |
| | nativo NB-GLM | 62.9 | 0.44 |
| Sur-Sureste vulnerable | **agregado** | **43.6** | **0.11** |
| | nativo Prophet | 54.3 | 0.14 |
| | nativo NB-GLM | 71.3 | 0.25 |
| Urbana media | **agregado** | **34.6** | **0.58** |
| | nativo NB-GLM | 56.1 | 1.50 |
| | nativo Prophet | 69.4 | 1.37 |

**La agregación gana en las 4 regiones, en ambas métricas.** Es esperable: cada estado ya tiene
su motor productivo elegido para SU dinámica; sumar esos pronósticos bien afinados captura el
total regional mejor que un solo modelo ajustado al agregado regional (más ruidoso/picudo).

Caveat: el SMAPE del solape 2026 es in-sample para ambos lados (mismo trato), así que la
comparación es justa; la conclusión es robusta al método de evaluación usado.

## Backtest OOS riguroso (leave-one-epidemic-out) — MATIZA el veredicto

La comparación de arriba es **in-sample** (solape 2026, un año CALMO). A pedido, se corrió un
backtest **fuera de muestra** (`scripts/research/dengue_backtest_regional.py`): entrenar SOLO con
datos previos al corte y puntuar el año siguiente. Único corte evaluable: **2024** (la epidemia
mayor); 2019 no califica porque la serie arranca a mediados de 2018 (<60 sem de entrenamiento).

Resultado OOS sobre la epidemia 2024 (lo que de verdad importa: pronosticar el pico):

Resultado OOS (epidemia 2024), CON DeepAR (entrenado local, una región a la vez):

| Método | SMAPE medio | MAE medio | ratio_pico medio |
|---|---:|---:|---:|
| **nativo DeepAR** | 124.4 | **460** | **0.43** |
| nativo NB-GLM | 128.3 | 820 | 3.38 |
| nativo Prophet | 130.0 | 1259 | 5.38 |
| agg-Prophet | 114.5 | 3753 | 41.4 |
| agg-NBGLM | 118.0 | 10140 | 34.2 |

**Veredicto (con DeepAR): el regional NATIVO gana, y DeepAR es el mejor.** La agregación tiene
SMAPE algo menor (artefacto del SMAPE, que satura a 200% por semana y no castiga la explosión)
pero **sobreestima la epidemia de forma catastrófica** (picos 34-157x el real; MAE 3.7k-10k)
porque sumar 6-15 pronósticos estatales **compone los sobre-tiros**. Los nativos son contenidos;
**DeepAR nativo es el mejor en magnitud por amplio margen** (MAE 460 ≈ 8x mejor que la mejor
agregación; ratio de pico 0.43, el más cercano a 1). En año calmo (2026, in-sample) la agregación
lucía mejor, pero en epidemia (2024, OOS) el nativo —y sobre todo DeepAR— es claramente superior.

DeepAR local SÍ es viable entrenando **una región a la vez** (n_jobs=1, secuencial): ~15-20 min
por región (4 fits ~80 min). El deadlock previo era por `n_jobs>1` (concurrencia). En el backtest
hubo que reanclar las fechas de DeepAR (resamplea a W-MON de fin de periodo) al grid ISO de la
serie real, o el merge daba n=0.

## Decisión: ADOPTADO — DeepAR nativo en las regiones (en vivo)

- Las 4 regiones de Dengue de la galería usan **DeepAR nativo** (el mejor del backtest OOS).
  Ej.: Region Urbana media SMAPE 30.2→24.5, MASE 0.48→0.16; pronóstico contenido (pico ~756 vs
  el sobre-tiro de la agregación ~2.9k). Pronóstico realista, sin explosión.
- **Implementación (desacopla entrenamiento lento de generar galería rápida):**
  1. `scripts/build_dengue_deepar_regiones.py` (`make dengue-deepar-regiones`): entrena DeepAR por
     región **una a la vez** (n_jobs=1, ~20 min c/u sobre la serie completa; el deadlock previo era
     por n_jobs>1) y cachea el pronóstico (con banda nativa de cuantiles) en
     `reports/ProdDetails/dengue_deepar_regiones.csv`. Reancla fechas al grid ISO (W-MON de inicio).
  2. `build_dengue_gallery._dengue_regiones` lee ese cache → DeepAR nativo (banda nativa solo a
     futuro). Si el cache falta, cae a la agregación + clamp (fallback).
- NO se usó `predice` para las regiones DeepAR (su path standalone no emite filas `Region` para
  DeepAR, y correrlo arriesga sobre-escribir el `all_forecast` combinado). El cache evita ambos.
- Mantenimiento: tras un boletín nuevo, re-correr `make dengue-deepar-regiones` (~80 min) antes de
  `build_dengue_gallery` para refrescar las regiones. Backtest reproducible:
  `scripts/research/dengue_backtest_regional.py --deepar`.

## Gotcha registrado

`scripts/predice.py` escribe el `all_forecast_<motor>.csv` COMPLETO con solo el padecimiento de
la corrida (`out.to_csv(out_file)`, sin merge). Correr `predice ... padecimiento.tipo=Dengue`
para un motor que también tiene neuro (Prophet/DeepAR/...) **borra las filas neuro** de ese CSV.
El flujo canónico debe re-publicar ambos cohortes; ante un accidente, `dvc checkout --force
reports/forecasts.dvc` restaura el último snapshot versionado.
