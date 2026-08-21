# Resultados Fase 1 — ablación del pool de candidatos

> ## ⚠ SUPERSEDIDO — evidencia histórica
>
> **Las cifras de este documento salieron de `all_forecast_*`, que NO es la fuente
> canónica.** La Tabla 2 del paper sale de `tableau.csv`, y tener dos fuentes de
> pronóstico en un mismo artículo es justo el defecto que este trabajo vino a corregir.
> Todo se recalculó desde `tableau.csv` el 20-ago-2026 (commit `6d23bb3a`).
>
> **Las cifras vigentes están en [`FASE4_CIFRAS.md`](FASE4_CIFRAS.md)** y en
> `fase4_cifras.json`. Lo que cambió:
>
> | n=99 | aquí (`all_forecast`) | vigente (**tableau**) |
> |---|---|---|
> | Prophet | 26,40 | **26,74** |
> | DeepAR | 27,92 | **27,38** |
> | Ensemble | 28,30 | **28,08** |
> | Stacking | 29,28 | 29,28 |
> | Reasignaciones que mejoran | 78,2 % | **76,4 %** |
> | Mediana dinámica final | 28,81 | **28,52** |
> | Ventana declarada | W02–W18 | **W03–W18** (derivada del dato) |
>
> Este documento se conserva sin editar el resto de su contenido: es el registro de
> cómo se llegó al hallazgo, y borrarlo escondería el error en vez de dejarlo trazable.


**Fecha:** 20 de agosto de 2026 · **Paquete:** `c13e7163` / `b43ebdf2`
**El paper sigue sin tocarse.** Contrato predeclarado antes de ver resultados.

> **v2** — corregida una conclusión inválida de la v1. Ver §7.

---

## 0. Cumplimiento del contrato

| Cláusula | Estado |
|---|---|
| Mapa regional sólo del `tableau.csv` sellado | ✔ columna `Region Socio-Urbana` |
| 32 estados, una región por estado, tamaños 4/7/6/15 | ✔ Metropolitana alta 4 · Rural/dispersa 7 · Sur-Sureste vulnerable 6 · Urbana media 15 |
| General = suma de `Casos_semana`; hombres/mujeres = incremento por estado y **luego** suma | ✔ |
| Distrito Federal → Ciudad de México | ✔ |
| Pronósticos regionales explícitos, nunca suma de estatales | ✔ las 4 series `Region *` existen en los cuatro motores |
| `semana_boletín = semana_ds + 1` siempre | ✔ |
| Selección estática con la regla publicada (banda 5 % → MASE → RMSE) | ✔ |
| Cada pool dos veces, n=99 y n=111 | ✔ |
| Dinámica con la definición auditada (mínimo sMAPE en W02–W11) | ✔ reproduce el 78,2 % |
| `region_membership.csv`, resultados y hashes | ✔ `resultados_fase1/` |

**Las 12 series regionales quedaron reconstruidas: 12/12 con OOS calculable.**

---

## 1. Confirmación independiente de la corrección de semana

Mediana de sMAPE fuera de muestra por serie, W02–W18:

| | Prophet | DeepAR | Ensemble | Stacking |
|---|---|---|---|---|
| publicada (`ds=w`) · n99 | 33,96 | 36,64 | 36,76 | 37,84 |
| **corregida (`ds=w+1`) · n99** | **26,40** | **27,92** | **28,30** | **29,28** |
| publicada · n111 | 31,64 | 33,69 | 34,00 | 36,31 |
| **corregida · n111** | **24,41** | **26,75** | **27,66** | **28,56** |

La corrección mejora a **los cuatro** entre 7 y 8 puntos. Una alineación equivocada no
mejora sistemáticamente a todos los candidatos a la vez.

---

## 2. El "45–48 %" del paper es de otra ventana

§4 y la Fig. 20 afirman una mediana por serie de **45–48 %**. Con W02–W18 no reproduce.
Barriendo ventanas con la alineación publicada:

| ventana | Prophet | DeepAR | Ensemble | Stacking |
|---|---|---|---|---|
| W02–W18 | 33,96 | 36,64 | 36,76 | 37,84 |
| W02–W14 | 36,39 | 38,08 | 36,76 | 39,43 |
| W02–W11 | 38,63 | 39,61 | 39,89 | 41,98 |
| **W02–W08** | **45,65** | **45,24** | **45,84** | **49,22** |

Reproduce en **W02–W08**, y el corte de producción de `c13e7163` es la semana 8. El paper
mezcla un análisis por serie a W08 (Fig. 20, §4) con un agregado a W18 (Tabla 2, §5).
**Acordado: unificar la Fig. 20 a W02–W18 corregida — 26,40 / 27,92 / 28,30 / 29,28 %.**

---

## 3. Ablación estática

Selección siempre sobre n=111. Comparaciones **pareadas** contra el pool completo
(Wilcoxon, dos colas, sobre las mismas series).

**Principal · n=99**

| Política | mediana | media | p vs pool completo |
|---|---|---|---|
| **los 4** | **27,92** | 30,01 | — |
| sin Prophet | 27,92 | 30,01 | 0,843 |
| sin DeepAR | 27,97 | 29,97 | 0,481 |
| sin Ensemble | 27,92 | 30,05 | 0,695 |
| sin Stacking | 27,92 | 30,01 | 1,000 |
| **sólo Prophet** | **26,40** | **28,96** | **0,075** |
| sólo DeepAR | 27,92 | 30,07 | 0,560 |
| sólo Ensemble | 28,30 | 31,27 | 0,566 |
| sólo Stacking | 29,28 | 34,49 | 0,007 |

**Sensibilidad · n=111**

| Política | mediana | media | p vs pool completo |
|---|---|---|---|
| **los 4** | **26,75** | 28,32 | — |
| sin Prophet | 26,75 | 28,33 | 0,851 |
| sin DeepAR | 26,71 | 28,13 | 0,289 |
| sin Ensemble | 26,75 | 28,36 | 0,710 |
| sin Stacking | 26,75 | 28,31 | 0,851 |
| **sólo Prophet** | **24,41** | **27,27** | **0,056** |
| sólo DeepAR | 26,75 | 28,37 | 0,714 |
| sólo Ensemble | 27,66 | 29,37 | 0,745 |
| sólo Stacking | 28,56 | 32,61 | 0,005 |

### Lectura

Quitar cualquiera de los cuatro no cambia nada: las cinco primeras filas caen dentro de
0,05 puntos y ningún contraste se acerca a la significancia. Prophet solo tiene la mejor
estimación puntual en los dos universos, pero **la diferencia no alcanza p<0,05**
(0,075 y 0,056).

**Formulación correcta:**

> El ranking de validación cruzada no se transporta a la ventana prospectiva; el modelo
> peor clasificado en CV obtiene el mejor desempeño OOS agregado, y **no encontramos
> evidencia de que la selección estática supere una política Prophet-only**.

---

## 4. Ablación dinámica

Reselección en W02–W11, puntuación en W12–W18. **Métricas globales sobre las mismas
series**; el porcentaje entre reasignadas es diagnóstico secundario.

**Principal · n=99** — despliegue histórico: mediana **32,62**

| Política | reasig. | % mejoran | **mediana global** | media | p vs pool completo |
|---|---|---|---|---|---|
| **los 4** | 55 | 78,2 % | **28,81** | 31,00 | — |
| sin Prophet | 46 | 76,1 % | 29,21 | 32,30 | 0,069 |
| sin DeepAR | 97 | 74,2 % | **26,93** | 29,72 | 0,032 |
| sin Ensemble | 52 | 73,1 % | 28,81 | 31,83 | 0,080 |
| sin Stacking | 53 | 79,2 % | **28,91** | 31,05 | 0,306 |
| Prophet fijo | 98 | 64,3 % | 27,54 | 30,92 | 0,887 |
| DeepAR fijo | 3 | 0,0 % | 32,62 | 35,75 | <0,001 |
| Ensemble fijo | 97 | 62,9 % | 31,60 | 33,17 | 0,056 |
| Stacking fijo | 99 | 50,5 % | 32,56 | 36,28 | <0,001 |

**Sensibilidad · n=111** — despliegue histórico: mediana **30,74**

| Política | reasig. | % mejoran | **mediana global** | media | p vs pool completo |
|---|---|---|---|---|---|
| **los 4** | 62 | 77,4 % | **26,59** | 29,46 | — |
| sin Prophet | 53 | 75,5 % | 27,52 | 30,60 | 0,109 |
| sin DeepAR | 109 | 75,2 % | **25,23** | 27,98 | 0,008 |
| sin Ensemble | 58 | 72,4 % | 26,94 | 30,21 | 0,096 |
| sin Stacking | 58 | 77,6 % | 27,16 | 29,66 | 0,201 |
| Prophet fijo | 110 | 66,4 % | 24,80 | 29,09 | 0,891 |
| DeepAR fijo | 3 | 0,0 % | 30,74 | 33,90 | <0,001 |
| Ensemble fijo | 109 | 63,3 % | 28,39 | 31,30 | 0,070 |
| Stacking fijo | 111 | 51,4 % | 29,81 | 34,41 | <0,001 |

### Lectura

**El mecanismo de revisión mejora con claridad frente al despliegue histórico:**
32,62 → 28,81 en n=99 y 30,74 → 26,59 en n=111.

Control de sanidad: *DeepAR fijo* reasigna sólo 3 series y reproduce exactamente el
despliegue histórico (32,62 / 30,74) — porque el despliegue era DeepAR en 108 de 111.

**El pool completo no supera a Prophet fijo** (28,81 contra 27,54; p=0,887 y 0,891).

*Sin DeepAR* obtiene los mejores valores leave-one-out (26,93 / 25,23, p=0,032 y 0,008),
pero es **una sensibilidad post-hoc y no se corona como configuración óptima**.

---

## 5. Lectura conjunta

| Afirmación | Veredicto |
|---|---|
| La regla revisable mejora frente al despliegue congelado | **Sostenida.** 32,62→28,81 (n=99) y 30,74→26,59 (n=111), en los dos universos |
| Los cuatro candidatos son necesarios | **No sostenida.** Ningún leave-one-out se separa del pool completo |
| La selección estática supera a un modelo único | **Sin evidencia.** Prophet-only p=0,075 y 0,056 |
| El ranking de CV se transporta fuera de muestra | **No.** El peor en CV es el mejor OOS agregado |

Lo defendible es **el mecanismo auditable de revisión, no la necesidad del pool**.

---

## 6. Encuadre acordado

Título **sin cambio**. Contribución central:

> El valor no reside en que cuatro modelos superen necesariamente a uno, sino en que un
> mecanismo auditable detecta cuándo una selección congelada deja de transportarse y
> permite revisar las asignaciones usando únicamente observaciones anteriores.

Cambios editoriales comprometidos:

- Quitar del abstract *"improves coverage across this heterogeneity"*.
- Declarar que la ablación **no** apoya la necesidad del pool completo.
- Presentar el beneficio dinámico **contra el despliegue histórico**, sin afirmar superioridad frente a Prophet.
- Métricas globales sobre las mismas 99/111 series; el % entre reasignadas queda como diagnóstico.
- Unificar la Fig. 20 a W02–W18 corregida.
- Incluir el resultado negativo como fortaleza de auditabilidad y límite de generalización de CV.
- n=99 como evidencia prospectiva principal; n=111 como sensibilidad derivada.

---

## 7. Corrección respecto de la v1 de este documento

La v1 concluía que **"quitar Stacking mejora"**. **Es inválido.** Esa lectura comparaba
`med_despues`, calculada sobre el subconjunto de series *reasignadas* de cada pool — 53
series para "sin Stacking" contra 55 para el pool completo. Son conjuntos distintos: no
es una comparación.

Sobre la métrica global comparable, *sin Stacking* termina **peor** que el pool completo
(28,91 contra 28,81 en n=99; 27,16 contra 26,59 en n=111).

La v1 también decía que el ranking de CV está **"invertido"**. Es más de lo que sostienen
los datos: las diferencias no alcanzan significancia. La formulación de §3 es la correcta.

---

## 8. Reproducir

```bash
../../.venv/bin/python fase1_ablacion.py
```

Salidas: `region_membership.csv`, `oos_por_serie.csv`, `estatica_por_serie.csv`,
`dinamica_por_serie.csv`, `ablacion_estatica.csv`, `ablacion_dinamica.csv`, `HASHES.json`.
