# Auditoría ciega del paper — MICAI 2026, ponencia #12

**21 de agosto de 2026.** Lectura del PDF de principio a fin como si no lo hubiera visto
antes, sin apoyarme en lo que sé del proceso, más verificación aritmética independiente de
cada cifra publicada.

**Nueve hallazgos. Dos son de contenido y ambos vienen de nuestro propio proceso.**

---

## A. Contenido

### A1 — La Discusión y las Conclusiones nunca se actualizaron para la ablación

**El más serio.** El resumen promete:

> «A leave-one-model-out ablation shows that **the candidate pool is not what carries the
> result** […] The contribution is therefore **not that several models beat one**, but that
> an auditable mechanism detects when a frozen assignment stops transporting…»

§5.1 lo demuestra y lo dice sin rodeos. Pero **§6 abre así**:

> «Combining forecasters with complementary inductive biases and selecting one model per
> series through a transparent, revisable rule provides a principled way to forecast a
> heterogeneous panel…»

y **§7 cierra así**:

> «…comparing a structural model, a global probabilistic recurrent network, and two
> tree-based hybrids under a deterministic, auditable, and revisable selection rule.»

**Ni la Discusión ni las Conclusiones mencionan la ablación.** Las dos conservan el
encuadre anterior, en el que el aporte es el pool multi-modelo. Un revisor que lea resumen
→ conclusiones encuentra una promesa que el cierre no entrega, y la impresión es que el
resultado negativo se enterró al final.

Es exactamente lo que acordamos en el encuadre de Fase 1 —«el valor no reside en que cuatro
modelos superen a uno»— y sólo llegó al resumen y a §5.1.

**Arreglo:** dos párrafos. Uno al inicio de §6 y una frase en §7 que trasladen la
contribución al mecanismo de revisión. No mueve páginas si se sustituye texto existente.

### A2 — «Locked for 107 of 111» convive con un despliegue de 108, sin declararlo

§4.1 dice que la regla **«is locked for 107 of 111 combinations (96.4%)»**, y que la
excepción regional es Stacking. Es correcto **para la regla que el paper describe**.

Pero §5.1 usa como línea base **«the frozen deployment—the assignment actually locked
before 2026»**, que es el despliegue real: **DeepAR en 108**, porque en esa serie regional
producción desempató por RMSE y no por MASE, como sí hace la regla publicada.

El paper usa **«locked» con dos significados distintos** —la elección de la regla y la
asignación desplegada— sin advertirlo. Lo detectamos en Fase 0 y quedó acordado cambiar
«locked» por «selected by the primary rule» y declarar la discrepancia. **Nunca se aplicó.**

Importa porque el artículo se apoya en que el registro de selección es auditable: la única
serie donde el registro y el despliegue difieren es la que no se menciona.

**Arreglo:** cambiar el verbo y añadir una frase. Dos líneas.

---

## B. Presentación

### B3 — El PDF sale con las cajas de enlace de `hyperref`

El preámbulo carga `\usepackage{hyperref}` sin opciones, así que **cada cita y cada URL
llevan un recuadro de color**. Se ve en todo el documento.

Lo comprobé compilando una variante con `[hidelinks]` y comparando el mismo renglón:

```
actual        den on public health systems [25] . In Mexico…   ← recuadro verde y hueco
hidelinks     den on public health systems [25]. In Mexico…    ← limpio
```

El paper **ya se preocupa por esto a medias**: la línea siguiente del preámbulo pone las
URL en negro con `\renewcommand\UrlFont`. Faltó apagar los bordes.

**Arreglo:** `\usepackage[hidelinks]{hyperref}`. Una palabra.

### B4 — La Figura 3 no tiene los rótulos (a) y (b) que su pie promete

El pie dice **«(a) Late-2025 context…»** y **«(b) Per-week deviation…»**, pero la figura
no lleva ninguna marca: el lector tiene que deducir cuál es cuál. La Figura 1 sí los lleva,
como títulos de subgráfico, así que la inconsistencia salta.

### B5 — El acumulado reconciliado no cuadra con su propia columna

La nota al pie de la Tabla 2 dice **reconciliado 50 261**. Sumando la columna impresa dan
**50 262**. La diferencia es de redondeo —el total se calcula sin redondear y las celdas se
redondean una a una—, pero quien sume la columna encuentra un caso de diferencia.

**Arreglo:** una nota de que los agregados se computan sobre valores sin redondear.

---

## C. Afirmaciones más fuertes que su evidencia

### C6 — «Over 150,000 new cases per year» contra la propia Figura 1

La introducción afirma que SINAVE registra **más de 150 000 casos nuevos al año**. La
Figura 1(a), en la página siguiente, muestra los últimos años completos: **151 612 ·
148 188 · 149 402**. Sólo uno de los tres supera la cifra.

Está citado a [11], así que puede venir de la fuente, pero **el lector tiene la figura
enfrente**. Bastaría «about 150,000» o «around 150,000».

### C7 — «The first eighteen epidemiological weeks of 2026»

La introducción cierra diciendo que el hallazgo está sustentado por **las primeras dieciocho
semanas epidemiológicas de 2026**. La evaluación real es **W02–W18, diecisiete semanas** en
el agregado nacional y **W03–W18, dieciséis** por serie — y el propio pie de la Tabla 2
explica que W01 no es evaluable.

---

## D. Superficie de ataque, sin acción

### D8 — El presupuesto de ajuste no es parejo, y ahora pesa más

§3.3 admite que **no se iguala el número de configuraciones**: Prophet recibe una rejilla
de 12 puntos, DeepAR queda fijo en la configuración de un solo pliegue. Eso era defendible
cuando DeepAR ganaba la validación cruzada — ganaba con menos ajuste.

Con la ablación, el modelo **más ajustado es el que gana fuera de muestra**. Un revisor
puede decir que la comparación no es pareja justo en la dirección del resultado. No hay
tiempo de rehacer el ajuste, y el paper ya declara la asimetría; sólo conviene que llegues
preparado a Chihuahua.

### D9 — El recuadro de la regla de selección repite la regla formal

Justo debajo de la formulación matemática hay un recuadro en texto plano que dice lo mismo
en prosa. Son ~8 líneas redundantes. No sobra, pero es lo primero que cortaría si alguna
vez hace falta espacio.

---

## E. Lo que verifiqué y está bien

**Toda la aritmética de la Tabla 2**, recalculada desde los valores impresos:
las 17 desviaciones semanales, el observado acumulado (48 300), el predicho (49 482), la
desviación (+2,45 %), el sMAPE (7,40 %), el MAE (205), la mediana de desviación (4,4 %), la
peor semana (+23,8 % en W14) y el sMAPE de W15–W18 (2,7 %). **Todo cuadra.**

**Los agregados demográficos de §4.3**: 116 047 + 43 500 = 159 547 contra 155 966 del
estrato general → +2,30 %, que es el «∼2,3 %» que §6 vuelve a citar. Y el reparto del
pronóstico 2026, 72,7 %/27,3 %, coincide con el «73 %/27 %» de la Discusión.

**La Tabla 1**: las cuatro cuotas de selección (96,4 · 0,9 · 1,8 · 0,9) suman 100 % y
corresponden a 107 + 1 + 2 + 1 = 111.

**El panel**: 626 = 10×52 + 2×53, y 37×3 = 111.

**La comprobación de fuga**: 26,3 → 24,9 es el «∼5 %» que declara.

**Estructura**: figuras 1–4 y tablas 1–4 consecutivas, todas citadas antes de aparecer;
28 referencias, todas citadas, en orden alfabético; sin restos de la versión ciega.

---

## Recomendación

**A1 es el único que cambiaría la lectura de un revisor.** Los demás son de acabado.

Si sólo hubiera tiempo para tres: **A1** (Discusión y Conclusiones), **A2** (el verbo
«locked») y **B3** (`hidelinks`, una palabra). Los tres juntos son media hora y ninguno
mueve el conteo de páginas.
