# Fase 4 — juego completo de cifras

**Paquete sellado** `c13e7163` / `b43ebdf2` · alineación corregida `semana_boletín = semana_ds + 1`
**Fuente única: `tableau.csv` sellado**, también para el análisis por serie.
Datos con precisión completa en `fase4_cifras.json`.

**Estado: el paper ya está editado con estas cifras.** Este documento es la evidencia
materializada de la que salieron, no una lista de pendientes.

---

## 0. Ventanas, derivadas del dato

| Análisis | Ventana | Semanas | Por qué |
|---|---|---|---|
| Agregado nacional (Tabla 2, Figura 3) | **W02–W18** | 17 | la serie nacional de tableau tiene pronóstico desde la semana de boletín 2 |
| Por serie (Figura 4, ablación, reselección) | **W03–W18** | 16 | es la intersección común a las 111 series: la primera fecha `ds` de 2026 cae en semana ISO 2, que con el corrimiento va a la 3 |
| Reselección dinámica | W03–W11 → W12–W18 | 9 → 7 | ventana temprana y semanas no usadas |

Ninguna se fija a mano: salen de `sem_min`/`sem_max` de `oos_por_serie.csv`, y
`ventanas_coherentes.py` falla si el JSON, el `.tex`, los pies y el rótulo dentro de la
Figura 4 dejan de coincidir.

## 0.1 Sobre la fuente

El análisis por serie salía de `all_forecast_*` mientras la Tabla 2 salía de `tableau.csv`
— dos fuentes en un mismo paper, que es justo el defecto que este trabajo vino a corregir.
Ya está recalculado todo desde tableau. El cambio no es cosmético:

| n=99 | antes (`all_forecast`) | ahora (**tableau**) |
|---|---|---|
| Prophet | 26,40 | **26,74** |
| DeepAR | 27,92 | **27,38** |
| Ensemble | 28,30 | **28,08** |
| Stacking | 29,28 | **29,28** |
| Reasignaciones que mejoran | 78,2 % | **76,4 %** |
| Mediana dinámica final | 28,81 | **28,52** |

---

## 1. Control previo: la alineación publicada reproduce lo impreso

8 de 9. sMAPE 6,63 · desviación +4,40 · acumulados 48 300 / 50 424 · MAE 184,1 ·
p(Prophet) 0,101 · p(Stacking) 0,026 — exactos.

El noveno no cuadra porque **el Diebold–Mariano publicado no salió de `tableau.csv`**:
`stat_tests_dm.py` lo calculó desde `knowledge.json` del dashboard. Era una **tercera
fuente de pronóstico** en el paper. De ahí −1,476 en vez de −1,515. Descartada.

---

## 2. Agregado nacional: publicado contra corregido

| Cifra | Publicado | Corregido |
|---|---|---|
| sMAPE W02–W18 | 6,63 % | **7,40 %** |
| Desviación acumulada | +4,40 % | **+2,45 %** |
| MAE semanal | 184 | **205** |
| Predicho acumulado | 50 424 | **49 482** |
| Reconciliado acumulado | 51 216 | **50 261** |
| Desviación reconciliada | +6,0 % | **+4,1 %** |
| Mediana de desviación semanal | 3,8 % | **4,4 %** |
| Mayor desviación | +26,5 % (W14) | **+23,8 % (W14)** |
| sMAPE W15–W18 | 2,9 % | **2,7 %** |
| Devianza de Poisson | Ens 21,7 · Prp 31,9 · Dpr 31,5 · Stk 87,6 | **Ens 25,3 · Prp 30,4 · Dpr 57,9 · Stk 104,9** |

**Se sostiene:** el error OOS sigue bajo el de CV del mismo estrato (7,40 < 8,75); la
desviación acumulada sigue dentro de ±5 % y mejora; W14 sigue siendo el mayor desvío; y el
Ensemble bloqueado sigue siendo el mejor de los cuatro por devianza de Poisson.

---

## 3. Por serie (W03–W18, n=99 principal · n=111 sensibilidad)

| | Prophet | DeepAR | Ensemble | Stacking |
|---|---|---|---|---|
| Mediana sMAPE, n=99 | **26,74** | 27,38 | 28,08 | 29,28 |
| Mediana sMAPE, n=111 | **24,57** | 26,76 | 27,71 | 28,63 |
| MASE, estrato masculino | 0,74 | 0,76 | 0,86 | 0,90 |

El **«45–48 %»** del paper era de la ventana **W02–W08**, el corte de producción de
`c13e7163`. A W03–W18 son las medianas de arriba.

El MASE masculino publicado —**0,45–0,50, «el doble de exacto que la persistencia»**— no se
reproduce: es **0,74–0,90**. Mejor que la persistencia, por un margen mucho más estrecho.

**Reselección:** 55 de 99 reasignadas, 76,4 % mejoran, mediana global **32,74 → 28,52**
(n=111: 62 reasignadas, 75,8 %, 31,04 → 26,44). El **«73 de 111»** del paper venía de una
columna del XLSX vivo que el paquete no tiene; no era reproducible.

---

## 4. Diebold–Mariano, con precisión completa

Tres comparaciones exploratorias sobre las mismas 17 semanas. Los $p$ crudos van **sin
ajustar**; Holm corrige por multiplicidad.

| Comparación | DM (HLN) | $p$ crudo | $p$ Holm | ¿<0,05? |
|---|---|---|---|---|
| Ensemble vs DeepAR | −2,6707 | **0,016747** | **0,050241** | **no** |
| Ensemble vs Stacking | −2,6421 | **0,017752** | **0,050241** | **no** |
| Ensemble vs Prophet | −0,8046 | **0,432849** | 0,432849 | no |

**Ninguna sobrevive al 5 % tras el ajuste.** El paper lo redacta como *evidencia nominal de
menor pérdida cuadrática*, no como diferencia establecida. La versión publicada afirmaba
que el Ensemble era más exacto que Stacking con $p=0{,}03$; esa afirmación tampoco habría
sobrevivido a Holm.

---

## 5. Cobertura del intervalo al 80 %

| | Publicado | Corregido |
|---|---|---|
| Semanas cubiertas | 15/17 (88,2 %) | **10/17 (58,8 %)** |
| Percentiles 10/90 de los residuales | — | **−213,5 / +209,0** |
| Ancho de la banda | — | **422,5 casos** |
| Residual histórico mediano (n=256) | — | **96,5** |
| Residual 2026 mediano | — | **135,0** |

Los diagnósticos explican la subcobertura: la banda se calibra sobre residuales históricos
de mediana 96,5 casos, y los de 2026 son de 135. **La distribución histórica no se
transporta a W02–W18.** El paper lo reporta como tal y añade la limitación correspondiente:
revisar asignaciones puntuales no calibra la incertidumbre.

*(El contraste contra la alineación inválida —679→423 y 153→96— pertenece a la auditoría,
no al resultado publicado, y no aparece en el paper.)*

---

## 6. Reproducir

```bash
.venv/bin/python scripts/paper_micai_2026/fase1_ablacion.py       # por serie y ablación
.venv/bin/python scripts/paper_micai_2026/fase4_cifras.py         # juego completo -> JSON
.venv/bin/python scripts/paper_micai_2026/fase4_figuras.py        # Figuras 3 y 4
.venv/bin/python scripts/paper_micai_2026/valores_retirados.py    # ninguna cifra vieja viva
.venv/bin/python scripts/paper_micai_2026/ventanas_coherentes.py  # ventanas coherentes
.venv/bin/python -m pytest tests/paper_micai_2026 -q --no-cov     # 20 pruebas
```
