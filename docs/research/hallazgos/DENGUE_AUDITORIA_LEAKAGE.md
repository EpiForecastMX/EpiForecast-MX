# Auditoría de Data Leakage — Dengue (y nota aplicable a neuro)

Fecha: 2026-06-05
Autor: auditoría de código (revisión solicitada: "¿estamos seguros que no tenemos data leak en Dengue?")

## Resumen ejecutivo

Hay que distinguir **dos evaluaciones distintas**, con veredictos distintos:

1. **Evidencia científica (backtest NBGLM): LIMPIA.** El número que sostiene
   "NBGLM es el mejor motor" (SMAPE 52 vs Prophet+ENSO 76 vs Prophet 102) es
   metodológicamente honesto.
2. **Métrica de selección de producción (`smape_real_2026`): TIENE FUGA in-sample.**
   El motor productivo por serie se elige comparando el *ajuste in-sample* de 2026
   contra el real de 2026. Es optimista y con sesgo de selección.

**Decisión tomada (2026-06-05):** se deja como está y se valida hacia adelante
(prospectivo OOS) en vez de corregir ahora con el corte MICAI. Ver "Plan".

---

## 1. Backtest NBGLM — SIN leak (evidencia)

`scripts/research/dengue_backtest.py`:

- **Split honesto (leave-one-epidemic-out):** entrena hasta *antes* del año
  epidémico evaluado (2019, 2024) y pronostica 52 semanas. El año evaluado NO
  está en el entrenamiento.
- **ONI sin leak:** NBGLM y Prophet usan `enso.oni_for_dates(..., as_of=cutoff)`,
  que trunca el ONI al corte y extrapola el futuro con persistencia amortiguada.
  No lee clima observado del futuro.
- El escenario `"perfect"` (ONI futuro observado) existe pero está etiquetado como
  diagnóstico ("¿tiene valor la covariable?"), NO es el número reportado. El
  reportado es `"realista"`.

Conclusión: la afirmación "NBGLM gana en backtest" se sostiene sin leakage.

---

## 2. Selección de producción — FUGA in-sample (evidencia)

| Hecho | Evidencia |
|---|---|
| El modelo final de producción se entrena sobre la **serie completa** (incluye 2026 H1) | `prophet/model.py` `run()`: `self.fit(self.serie, best_params)`; `prophet/data_prep.py` `crea_train_test` devuelve `serie` SIN truncar (solo `train_data`/`test_data` se parten para CV) |
| NBGLM no aplica ningún corte en el ajuste final | `nbglm/model.py` `run()`: `self.fit(self.serie)` |
| `FECHA_CORTE_ENTRENAMIENTO=2025-01-01` se usa SOLO para métricas CV/overfitting, no para el ajuste productivo | `config/models/prophet.yaml:88` |
| `predict()` emite el **ajuste in-sample** de 2026 H1 (los CSV cubren 2018→2026 continuo + futuro a 2027) | `reports/forecasts/{prophet,deepar,nbglm}/all_forecast_*.csv`: 52 filas en 2026 por motor |
| `produccion_dengue.py` elige motor comparando esos valores ajustados in-sample contra el real 2026 | `produccion_dengue.py` `build_real(anio=2026)` vs forecast, SMAPE por semana ISO |

Implicación:

- La columna **`smape_real_2026` NO es error out-of-sample**: es el error del
  ajuste sobre las mismas ~20 semanas que el modelo ya vio al estimar coeficientes.
- Encima se elige el **mejor de 3-4 motores** sobre ese mismo periodo (sesgo de
  selección sobre el set de evaluación).
- Un motor flexible (NBGLM con Fourier+lags+ONI, o DeepAR) puede ganar series por
  **sobreajuste reciente**, no necesariamente por mejor pronóstico.

**No es exclusivo de Dengue.** El mismo patrón aplica a `reselect_motor_2026.py`
de neuro (333 series): re-entrena con 2026 y puntúa el ajuste in-sample. El sesgo
es compartido.

### Lo que NO es

- No rompe el producto: los forecasts siguen siendo la mejor estimación del modelo.
- Como heurística operativa viva ("qué motor sigue mejor el boletín hasta hoy"),
  comparar ajuste-a-la-fecha vs real es defendible y está documentado como
  "selección revisable".
- Lo único en juego es la **honestidad del número** `smape_real_2026`: no debe
  reportarse como precisión OOS.

---

## Plan (decisión 2026-06-05): validación prospectiva, no corrección ahora

Razón: las semanas entrantes (W21, W22…) NO están en el entrenamiento, así que
comparar pronóstico vs boletín en esas semanas es OOS honesto, gratis, sin
re-arquitectura. El backtest (limpio) ya dice que NBGLM debería ganar; las
próximas semanas lo confirman o desmienten con datos reales. Corregir ahora con
el refit a corte fin-2025 es caro y cambiaría el motor productivo en Dengue y en
las 333 series neuro, sin saber aún si el sesgo cambia algo material.

**Condición técnica para que la validación sea válida:** el pipeline canónico
re-entrena cada semana. Para no contaminar la prueba, hay que **congelar el
forecast vigente** (snapshot con su fecha de corte) y comparar los boletines
entrantes contra ese forecast congelado durante 4-8 semanas ANTES de dejar que el
re-entrenamiento lo sobreescriba. (Es la disciplina del "forecast bloqueado" de
MICAI, aplicada hacia adelante.)

**HECHO (2026-06-05): la herramienta de congelado ya existe.**
`scripts/pronostico_congelado.py` (targets `make congela-pronostico` /
`make valida-prospectivo`), cubre los 4 padecimientos:
- `freeze`: guarda el pronóstico del motor productivo por serie SOLO para la cola
  futura (ds > corte = no vista) en `reports/ProdDetails/congelado/forecast_congelado_<fecha>.csv`
  (+ puntero `forecast_congelado_latest.txt`). Snapshot inicial: corte 2026-W20
  (2026-05-11), 396 series, 16,032 filas futuras (W21+).
- `validar`: confronta el congelado contra el boletín vigente y reporta SMAPE/MAE
  OOS por serie y nacional (`validacion_prospectiva.html` + `.csv`). Solo puntúa
  semanas posteriores al corte. Hoy reporta 0 (aún no llega boletín > W20): correcto.

**Operación semanal:** tras el próximo boletín, correr `make valida-prospectivo`
ANTES de re-entrenar para acumular el desempeño OOS. NO re-congelar cada semana
(eso reiniciaría la prueba); re-congelar solo cuando se quiera fijar un nuevo punto
de partida.

**Criterio de decisión:**
- Si en 4-8 semanas no vistas el SMAPE OOS se mantiene cerca del in-sample
  (p.ej. DeepAR nacional ~10 in-sample → OOS < 15): nos quedamos así.
- Si el SMAPE OOS se dispara (> 2x el in-sample): invertir en el refit con corte
  MICAI (selección sobre forecast bloqueado entrenado hasta fin-2025, o selección
  por SMAPE de CV rolling `smape_prod` que ya es honesta).

---

## Fix honesto (si se decide corregir más adelante)

Para que la selección 2026 sea genuinamente OOS, el pronóstico con el que se
puntúa 2026 debe venir de un modelo entrenado con corte ANTES de 2026:

1. **Selección por SMAPE de CV rolling** (`smape_prod`, ya honesta) en lugar de
   `smape_real_2026`, o
2. **Forecast bloqueado** (corte = fin 2025) y puntuar 2026 contra ese (OOS real).
