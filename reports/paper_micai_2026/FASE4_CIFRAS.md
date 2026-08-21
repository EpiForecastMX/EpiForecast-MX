# Fase 4 — juego completo de cifras

**Paquete sellado** `c13e7163` / `b43ebdf2` · ventana **W02–W18** · alineación corregida
`semana_boletín = semana_ds + 1` · n=99 principal, n=111 sensibilidad.
Fuente única: `tableau.csv` sellado. Datos en `fase4_cifras.json`.
**El paper todavía no se ha editado.**

---

## 1. Control previo: la alineación publicada reproduce lo impreso

8 de 9. sMAPE 6,63 · desviación +4,40 · acumulados 48 300 / 50 424 · MAE 184,1 ·
p(Prophet) 0,101 · p(Stacking) 0,026 — todos exactos.

El noveno no cuadra por una razón que importa: **el Diebold–Mariano publicado no salió de
`tableau.csv`.** `stat_tests_dm.py` lo calculó desde `knowledge.json` del dashboard. Es una
**tercera fuente de pronóstico** en el paper, además de tableau (Tabla 2) y `all_forecast_*`
(held-out). De ahí que el estadístico dé −1,476 en vez de −1,515 (p 0,159 contra 0,149).
Bajo la regla de fuente única, el recálculo desde tableau es el que rige.

---

## 2. Todo lo que cambia

| Cifra | Publicado | Corregido |
|---|---|---|
| sMAPE W02–W18 | 6,63 % | **7,40 %** |
| Desviación acumulada | +4,40 % | **+2,45 %** |
| MAE semanal | 184 | **205** |
| Predicho acumulado | 50 424 | **49 482** |
| Reconciliado acumulado | 51 216 | **50 261** |
| Desviación acumulada reconciliada | +6,0 % | **+4,1 %** |
| Mediana de desviación semanal | 3,8 % | **4,4 %** |
| Mayor desviación | +26,5 % (W14) | **+23,8 % (W14)** |
| sMAPE W15–W18 | 2,9 % | **2,7 %** |
| Devianza de Poisson | Ens 21,7 · Prp 31,9 · Dpr 31,5 · Stk 87,6 | **Ens 25,3 · Prp 30,4 · Dpr 57,9 · Stk 104,9** |
| Mediana OOS por serie (n=99) | 45–48 % (¡de W02–W08!) | **Prp 26,4 · Dpr 27,9 · Ens 28,3 · Stk 29,3** |
| Reasignaciones | «73 de 111» | **55 de 99** (62 de 111) |
| Held-out: mejoran | 69,4 % | **78,2 %** |
| Held-out: mediana global | 32,62 % | **28,81 %** |

La Tabla 2 completa, semana a semana, está en el JSON.

**Lo que se sostiene:** el error OOS sigue por debajo del de CV del mismo estrato
(7,40 < 8,75); la desviación acumulada sigue dentro de ±5 % y mejora; W14 sigue siendo el
mayor desvío; y **el Ensemble bloqueado sigue siendo el mejor de los cuatro por devianza de
Poisson** (25,3).

---

## 3. Dos afirmaciones que la corrección rompe

### 3.1 La cobertura del intervalo al 80 % se cae

| | Publicado | Corregido |
|---|---|---|
| Semanas cubiertas | 15/17 (**88 %**) | **10/17 (59 %)** |
| Ancho del intervalo | 679 casos | **423 casos** |
| Residual histórico mediano | 153 | **96** |
| Residual 2026 mediano | 112 | 135 |

**Y el motivo confirma la corrección.** Con la alineación correcta el modelo ajusta el
histórico mucho mejor —el residual mediano baja de 153 a 96 casos—, así que el intervalo
calibrado sobre ese histórico se estrecha de 679 a 423. Pero los residuales de 2026 no se
estrechan igual. Resultado: **un intervalo calibrado en histórico es demasiado angosto fuera
de muestra.**

El paper hoy dice que el intervalo *«cubre 15 de 17 semanas (88 %), enmarcando el nivel
nominal»*. Eso ya no se sostiene.

Es un resultado **en contra del paper, y a favor de su tesis**: el artículo sostiene
exactamente que la evidencia in-sample no se transporta. La cobertura es un caso más.
Recomiendo reportarlo así, no quitarlo.

### 3.2 El Diebold–Mariano cambia de veredicto

| Comparación | Publicado | Corregido |
|---|---|---|
| Ensemble vs **DeepAR** | −1,48, p=0,159 (no concluyente) | **−2,67, p=0,017 — Ensemble mejor** |
| Ensemble vs **Prophet** | −1,74, p=0,101 (no concluyente) | −0,81, **p=0,433** (nada) |
| Ensemble vs **Stacking** | −2,46, p=0,026 | **−2,64, p=0,018** |

Aquí la corrección **favorece** al paper: el pronóstico bloqueado pasa a ser significativamente
más exacto que DeepAR, no sólo que Stacking. El párrafo de *Pairwise comparison* hay que
reescribirlo entero: hoy dice que no se separa de DeepAR ni de Prophet.

---

## 4. Una cifra sin base en el paquete

El paper afirma **«reasigna 73 de las 111 series»**, en §4 y en el caption de la Figura 4.
Ese conteo venía de la columna `criterio_seleccion` del XLSX **vivo**, que el artefacto
histórico no tiene. No es reproducible desde el paquete sellado.

Lo defendible, declarando ventana y universo: **55 de 99** reasignadas al reseleccionar en
W02–W11 (62 de 111 en la sensibilidad).

---

## 5. Lo que falta

Decidir la redacción de 3.1, y luego editar: Tabla 2, Figuras 3 y 4 (regenerar), todo §5,
Discussion, Limitations, Conclusions y captions. Después: control de valores retirados sobre
`.tex` y PDF, `compila.sh`, pruebas, 20 páginas y revisión visual.
