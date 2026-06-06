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

## Decisión

- **No adoptar** regionales nativos de Dengue. La galería conserva la agregación bottom-up.
- Se **revirtió** el experimento: gate `is_neuro` restaurado en `entrena.py`, modelos
  `*_region_*` de Dengue borrados, `reports/forecasts` restaurado vía `dvc checkout` (las
  corridas de `predice` para Dengue sobre-escriben el `all_forecast_<motor>.csv` combinado;
  hubo que regenerar el de NB-GLM tras el checkout).
- Si en el futuro se quiere reintentar (p.ej. DeepAR regional en SageMaker GPU): quitar el gate
  `is_neuro` del paso 1 del bloque híbrido y entrenar; pero el listón es la agregación, que hoy
  es mejor.

## Gotcha registrado

`scripts/predice.py` escribe el `all_forecast_<motor>.csv` COMPLETO con solo el padecimiento de
la corrida (`out.to_csv(out_file)`, sin merge). Correr `predice ... padecimiento.tipo=Dengue`
para un motor que también tiene neuro (Prophet/DeepAR/...) **borra las filas neuro** de ese CSV.
El flujo canónico debe re-publicar ambos cohortes; ante un accidente, `dvc checkout --force
reports/forecasts.dvc` restaura el último snapshot versionado.
