# Dengue — investigación de mejoras (Fase 4)

**Fecha:** 2026-06-04 · **Motivación:** los pronósticos de Dengue no convencen (la *magnitud* del próximo brote, no el ciclo anual). Se investigaron 4 vías: usar datos desde 2014, modelos nuevos, verosimilitud correcta y covariables climáticas.

## Diagnóstico (3 causas de raíz)
1. **Verosimilitud equivocada:** el DeepAR de Dengue ajustaba **StudentT** (continua, simétrica, masa en negativos) a **conteos con ~44% de ceros**. NegBin es la correcta para conteos sobredispersos (baseline estándar en la literatura de dengue).
2. **Sin drivers climáticos:** modelos puramente autorregresivos. El ciclo inter-anual vive en **El Niño/ENSO**, no en los conteos recientes (México: ciclo ~5-6 años sincronizado con ENSO; brotes 2014, 2019, 2024 = años El Niño).
3. **Solo ~2 ciclos** en la serie de producción (2018-2026) → el ciclo largo no es aprendible desde la propia serie.

## Backtest leave-one-epidemic-out (serie NACIONAL, `scripts/research/dengue_backtest.py`)
Entrenar hasta antes del año y pronosticar 52 sem. ONI = índice El Niño (NOAA), rezagado 16 sem.

| Corte | Modelo | SMAPE | ratio pico (pred/real) |
|---|---|---|---|
| 2023 | Prophet (actual) | 142.6 | 0.07 (predijo plano) |
| 2023 | Prophet+ONI (perfect) | **88.6** | 0.85 |
| 2023 | Prophet+ONI (realista) | 127.8 | 0.16 |
| 2024 | Prophet (actual) | 62.3 | 1.61 (sobre-disparó) |
| 2024 | Prophet+ONI (perfect) | **53.2** | 0.38 |
| 2024 | Prophet+ONI (realista) | 54.1 | 2.03 |
| — | **NB-GLM Fourier** | 106.8-119.3 | ~0.14-0.34 |

**SMAPE medio:** Prophet+ONI perfect **70.9** · realista **91.0** · Prophet actual **102.4** · NB-GLM **113.0**.

### Hallazgos
- **El Niño (ONI) es el lever.** Aun con ONI *realista* (observado donde el rezago ya lo entrega + persistencia para la cola, sin trampa) baja el SMAPE 102 → 91. Con pronósticos ENSO de IRI (mejores que persistencia) el número real queda entre 71 y 91. La ganancia se concentra en los años de *build-up* epidémico — el punto débil exacto.
- **NB-GLM Fourier solo NO gana** (lags iterativos se desinflan, SMAPE 113). **PERO NB-GLM + ONI es el MEJOR modelo de todos** (backtest leave-one-epidemic-out, métrica consistente): SMAPE medio **52.0** vs Prophet+ENSO 76.4 vs Prophet actual 102.4. En 2024 SMAPE 27.3 (ratio 0.73), en 2023 76.7 (vs Prophet+ENSO 121.3). El Negative-Binomial (count-correcto) + Fourier (extrapola sin divergencia de árboles) + lags + **ONI (ciclo inter-anual)** + determinista (sin estocasticidad de DeepAR). **PRODUCTIZADO como motor `nbglm`** (`src/epiforecast/models/nbglm/`): con la métrica CONSISTENTE de `produccion_dengue` (smape_real 2026) gana **31/99 series** (distribución DeepAR 46, NBGLM 31, Prophet 22; Nacional sigue DeepAR porque 2026 es año bajo). Fallback constante para series degeneradas (CDMX/Tlaxcala). En vivo.
- **Bridge a 2014: PROBADO, EMPEORA.** Serie puenteada A90/A91+A97.x con indicador de régimen (`scripts/research/dengue_bridge2014.py`): SMAPE medio 76.4 (solo 2018+) → **84.7** (con 2014). El periodo 2014-2017 (otra definición, meseta hiperendémica) jala el modelo hacia el régimen viejo; ni con dummy de régimen ayuda. Habilita backtest 2019 pero lo predice mal (ratio 0.14). Descartado.
- **DeepAR NegBin: PROBADO, SIN MEJORA CLARA → no se despliega.** Se implementó NegBin en espacio de conteos enteros (cohort-aware: sin tasa + redondeo de la interpolación de huecos, porque NegBin solo admite enteros >=0). Re-entrenado el nacional. **Comparación confundida:** mi smape ad-hoc daba NegBin 28.3 vs el `produccion_dengue` 20.4 del student-t desplegado — métodos distintos. Con MÉTRICA CONSISTENTE (mismo método): NegBin **28.3** vs student-t recién re-entrenado **28.4** = empate; además DeepAR es estocástico (re-entrenar mueve el número). Conclusión honesta: **NegBin no mostró mejora reproducible** y añade restricciones (target entero, bug "Only one live display" si falla un fold). Se conserva **student-t+tasa** (config desplegada y validada). Live intacto (NO se regeneró all_forecast_deepar). Lección: usar SIEMPRE la misma métrica de eval y controlar la estocasticidad antes de concluir.
- **Bridge a 2014:** la forma estacional empalma (corr 0.958, mismo pico W43) pero el nivel salta ~2x (cambio de definición confirmado→todas-severidades) y 2014-2017 es meseta hiperendémica, no un pico limpio. Útil para FORMA (normalización por proporción anual o indicador de régimen), no para magnitud cruda. Habilitaría un backtest de 2019 (hoy se salta por falta de historia previa).

## Próximos pasos (orden recomendado)
1. **Productizar ONI en Prophet de Dengue** (cohort-gated, `is_count_log_cohort`): regresor `oni` rezagado ~16 sem; ONI futuro = observado + **pronóstico IRI/CPC** para la cola (mejor que persistencia). Re-validar OOS con leave-one-epidemic-out.
2. **Re-entrenar flota DeepAR Dengue con NegBin** y re-correr `produccion_dengue.py` para medir el cambio.
3. **Bridge 2014** (normalizado/régimen) para habilitar backtest 2019 + más historia de forma.
4. Explorar NB-GLM+ONI y DeepAR con `feat_dynamic_real`=ONI.

## Datos / artefactos
- `data/external/oni.ascii.txt` — ONI NOAA (1950-2026), descargable de cpc.ncep.noaa.gov.
- `scripts/research/dengue_backtest.py` — banco de pruebas reproducible.
- Fuentes clima/ENSO y modelos: ver investigación en el historial del proyecto (NASA POWER, ERA5-Land, CHIRPS, IRI ENSO plume; GluonTS TFT/PatchTST/DLinear/TiDE ya disponibles).
</content>
