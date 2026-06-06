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

| Método | SMAPE medio | MAE medio | ratio_pico medio |
|---|---:|---:|---:|
| agg-Prophet | **114.5** | 3753 | sobreestima fuerte |
| agg-NBGLM | 118.0 | 10140 | sobreestima brutal |
| nativo NB-GLM | 128.3 | **820** | contenido |
| nativo Prophet | 130.0 | 1259 | contenido |

**Veredicto dividido y revelador:** la agregación tiene SMAPE algo mejor, pero **sobreestima la
epidemia de forma catastrófica** (picos pronosticados 5x-157x el real; MAE 3,700-10,000) porque
sumar 6-15 pronósticos estatales independientes **compone los sobre-tiros**. Los modelos
regionales **nativos** son mucho más contenidos (MAE 820-1,259, ~4-12x menor). O sea: en un año
calmo (2026, in-sample) la agregación luce mejor, pero **en una epidemia (2024, OOS) explota**, y
ahí el nativo es claramente más fiel en MAGNITUD.

DeepAR nativo regional: su backtest local resultó impracticable (>50 min de CPU para 4 fits,
abortado) — es un trabajo a escala SageMaker, consistente con que el patrón "nativo = contenido"
ya se ve en Prophet/NB-GLM.

## Decisión (matizada por el backtest OOS)

- **No cambiar lo desplegado AHORA:** la galería conserva la agregación bottom-up. Estamos en un
  año calmo (2026) donde la agregación NO explota; el riesgo de sobre-tiro compuesto solo aparece
  en años epidémicos.
- **Pendiente / mejora recomendada:** la agregación tiene un defecto real en epidemias (compone
  los sobre-tiros estatales → picos 5x-157x). La mejor jugada NO es "agregación vs nativo" puro,
  sino **acotar la agregación** (clamp a la envolvente histórica / al nivel del modelo regional
  nativo) para matar la explosión sin perder su buen SMAPE en años calmos. Alternativa: usar el
  regional **nativo** como pronóstico de magnitud en años epidémicos.
- El experimento de entrenamiento se revirtió en el repo (gate `is_neuro` restaurado en
  `entrena.py`, modelos `*_region_*` de Dengue borrados, `reports/forecasts` restaurado vía
  `dvc checkout --force`; hubo que regenerar el `all_forecast_nbglm.csv`). El backtest
  (`scripts/research/dengue_backtest_regional.py`) queda versionado para reproducir/extender.
- Reintentar DeepAR regional: en SageMaker GPU (local es impracticable). Quitar el gate
  `is_neuro` del paso 1 del bloque híbrido para entrenar.

## Gotcha registrado

`scripts/predice.py` escribe el `all_forecast_<motor>.csv` COMPLETO con solo el padecimiento de
la corrida (`out.to_csv(out_file)`, sin merge). Correr `predice ... padecimiento.tipo=Dengue`
para un motor que también tiene neuro (Prophet/DeepAR/...) **borra las filas neuro** de ese CSV.
El flujo canónico debe re-publicar ambos cohortes; ante un accidente, `dvc checkout --force
reports/forecasts.dvc` restaura el último snapshot versionado.
