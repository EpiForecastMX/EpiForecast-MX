# VEREDICTO — alineación de semanas (Fase 0)

**Fecha:** 20 de agosto de 2026
**Paquete:** modelos `c13e7163` · observaciones `b43ebdf2` · árbol DVC de forecasts `2844e4f1…`
**Alcance:** decidir si la sección de validación del paper #12 cruza observación y pronóstico con una semana de desfase. **No se modificó el paper.**

---

## Veredicto

**CONFIRMADO.** La correspondencia real es

```
semana_boletín = semana_ds + 1
```

La Tabla 2 del paper cruza la observación del boletín de la semana W contra el
pronóstico almacenado en `ds` de semana W. Ese pronóstico corresponde al boletín de la
semana **W+1**.

---

## 1. La causa, en el código

`src/epiforecast/data/preprocessing/transformer.py::_ajusta_semanas`, línea 58:

```python
# Para los que NO son semana 1: restar 1
self.df.loc[filas_no_semana_1, "Semana"] = self.df.loc[filas_no_semana_1, "Semana"] - 1
```

Toda fila que no sea semana 1 baja una posición. La fila que el modelo aprende con
etiqueta N lleva la medición que el boletín publicó como N+1. El pronóstico hereda esa
numeración; al puntuarlo contra el boletín hay que devolverlo sumando 1.

## 2. La traza, a nivel de fila

`incrementos_total` de `tableau.csv` es el observado **tal como lo ve el modelo**,
indexado por `ds`. Si el desfase existe, debe coincidir con el boletín de `w+1`.

**Jalisco · general · 2025:**

| ds ISO | `incrementos_total` | boletín(w) | boletín(w+1) |
|---|---|---|---|
| 2025-W10 | 265 | 169 | **264** |
| 2025-W11 | 278 | 264 | **278**  <-- IGUAL |
| 2025-W12 | 153 | 278 | **153**  <-- IGUAL |
| 2025-W13 | 257 | 153 | **256** |
| 2025-W14 | 120 | 256 | **120**  <-- IGUAL |
| 2025-W15 | 255 | 120 | **255**  <-- IGUAL |

Cuatro coincidencias exactas de seis; las dos restantes difieren en **1 caso**
(revisión posterior del boletín), no en una semana. Contra `boletín(w)` no se acerca
en ninguna.

**Barrido de 5 entidades × 2 años (500 semanas):**

| alineación | coincidencias exactas |
|---|---|
| `incrementos_total(ds=w)` vs `boletín(w)` | **6 / 500 (1,2 %)** |
| `incrementos_total(ds=w)` vs `boletín(w+1)` | **218 / 500 (43,6 %)** |

La tasa no llega a 100 % porque el boletín revisa cifras históricas. La asimetría
—36× a favor de `w+1`— no admite otra lectura.

---

## 3. Antes de corregir: el paquete reproduce lo publicado

Requisito previo. Si el paquete no devolviera lo impreso, el problema sería el paquete.

```
FASE 0 · PASO 2 — reproducir lo publicado, SIN corregir
  [OK] sMAPE Tabla 2 ........................ publicado 6.63    obtenido 6.63
  [OK] desviación acumulada ................. publicado 4.40    obtenido 4.40
  [OK] observado acumulado .................. publicado 48300   obtenido 48300
  [OK] predicho acumulado ................... publicado 50424   obtenido 50424
  [OK] MAE semanal .......................... publicado 184     obtenido 184.12
  [OK] semanas evaluadas .................... publicado 17      obtenido 17
  [OK] DeepAR por la regla primaria ......... publicado 107     obtenido 107
  [OK] DeepAR desplegado .................... publicado 108     obtenido 108
  [OK] % de reasignadas que mejoran ......... publicado 69      obtenido 69.35
  [OK] mediana held-out antes ............... publicado 32.0    obtenido 31.98
  [OK] mediana held-out después ............. publicado 26.4    obtenido 26.38

VEREDICTO: 11/11
```

---

## 4. Efecto de la corrección

### Tabla 2 · nacional general, W02–W18

| | publicado | corregido |
|---|---|---|
| sMAPE | **6,63 %** | **7,40 %** |
| Desviación acumulada | **+4,40 %** | **+2,45 %** |
| MAE semanal | 184 | 205 |
| Predicho acumulado | 50 424 | 49 482 |
| Semanas dentro de ±5 % | 9/17 | 9/17 |
| Mayor desviación | +26,5 % (W14) | +23,8 % (W14) |

**Las dos afirmaciones que sostienen la sección siguen en pie:**

- el error fuera de muestra sigue por debajo del de CV del mismo estrato — 7,40 % < 8,75 %;
- la desviación acumulada sigue dentro de la tolerancia de ±5 % — y **mejora**, de +4,40 % a +2,45 %.

### Held-out · reselección en W02–W11, puntuación en W12–W18

| | publicado | corregido |
|---|---|---|
| Series evaluadas | 99 | 99 |
| Reasignadas | 62 | **55** |
| De esas, mejoran | 43 | 43 |
| **% que mejoran** | **69,4 %** | **78,2 %** |
| Mediana antes | 32,0 % | 33,7 % |
| Mediana después | 26,4 % | 26,1 % |

**El mecanismo de revisión sale más fuerte con la alineación correcta**, no más débil:
reasigna menos series (55 en vez de 62) y acierta en una proporción mayor (78 % contra 69 %).

---

## 5. Lo que hay que reescribir además de las cifras

| Afirmación del paper | Bajo corrección |
|---|---|
| W08 se desvía **+0,2 %** ("hito de planeación") | **−4,4 %.** La frase del hito hay que reescribirla o quitarla |
| W02 **+13,1 %**, W03 **+1,8 %** | −8,9 % y −10,9 %: cambia el relato del arranque de año |
| "las cuatro semanas siguientes W15–W18 vuelven a sMAPE 2,9 %" | Recalcular |
| Diebold–Mariano W02–W18 (p=0,15 / 0,10 / 0,03) | Recalcular sobre las pérdidas corregidas |
| Cobertura del intervalo 80 % (15 de 17) | Recalcular |
| Poisson deviance (21,7 / 31,9 / 32,0 / 87,5) | Recalcular |

---

## 6. Hallazgo colateral: el 107 contra el 108

No es lo que suponíamos ninguno de los dos. **No interviene el fallback regional**: en
las 111 series de Depresión, `tipo_modelo` es `propio` en las 111 y `region_asignada`
está vacía en las 111. El fallback nunca se activó.

La diferencia es **una sola serie**, `region_Sur-Sureste vulnerable · general`:

| | Stacking | DeepAR |
|---|---|---|
| sMAPE | **11,001** | 11,471 |
| MASE | **0,664** | 0,690 |
| RMSE | 46,92 | **45,40** |

Los dos caen dentro de la banda del 5 % (umbral 11,551), así que hay empate. **La regla
del paper desempata por MASE y elige Stacking. Producción desempató por RMSE y desplegó
DeepAR** — y la propia `justificacion` de esa fila dice *"DeepAR elegido por desempate
MASE/RMSE"*, cuando su MASE es el peor de los dos.

De ahí: **107 por la regla publicada, 108 desplegado.** El paper llama "locked" al
reparto de la regla, que es correcto para la regla que describe, pero no es lo que
corrió en producción.

**Acción:** cambiar "locked for 107 of 111" por *"selected by the primary rule"* y
declarar explícitamente la discrepancia de la serie regional. Es una nota de una línea
y es exactamente el tipo de trazabilidad que el paper dice ofrecer.

---

## 7. Composición de las 111 series

32 estados + 1 nacional + **4 regiones** = 37 entidades × 3 estratos = **111**.

Las **12 series regionales** (4 × 3) no tienen observación directa en el boletín: por eso
toda evaluación fuera de muestra corre sobre **n = 99**. Cualquier tabla de ablación debe
declararlo o construir las agregaciones regionales.

---

## 8. Reproducir esto

```bash
cd Congresos/MICAI
../../.venv/bin/python sella_bundle.py       # sella el paquete y escribe el MANIFEST
../../.venv/bin/python fase0_reproduce.py    # 11/11 contra lo publicado
../../.venv/bin/python fase0_corrige.py      # publicado vs corregido, lado a lado
```

`bundle.py` verifica el SHA-256 de las siete piezas en cada lectura y aborta si alguien
apunta a una ruta viva del árbol de trabajo.
