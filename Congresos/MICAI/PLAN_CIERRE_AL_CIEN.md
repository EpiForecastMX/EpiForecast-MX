# Plan de cierre — dejar el paper al cien

**21 de agosto de 2026** · nueve hallazgos de la auditoría ciega · deadline **domingo 23, AoE**

---

## La restricción que ordena todo

**Medido por sondeo directo, no estimado** — añadiendo texto real a un párrafo existente y
recompilando hasta que rompe:

| Variante | Presupuesto antes de llegar a 21 páginas |
|---|---|
| Como está hoy | **menos de 20 palabras** |
| Retirando el recuadro redundante (D9) | **entre 20 y 39 palabras** |
| D9 + comprimir *Search budget* | **igual: el recorte gana cero** |

Tres cosas que esto cambia respecto de la versión anterior del plan:

1. **La línea base no tiene margen.** El «+4 líneas» que escribí venía de una medición
   anterior a los últimos cambios. Con 20 palabras de más, el paper ya son 21 páginas.
2. **D9 compra ~3 líneas**, no 7. La recomposición absorbe el resto del recuadro.
3. **Comprimir *Search budget* no sirve.** Lo probé encima de D9: la página 20 se queda en
   las mismas 47 líneas. Sale de la lista de contingencias.

### La regla que sustituye al presupuesto

Como A2, B5 y D8 juntas piden unas 85 palabras y sólo hay ~30, el plan deja de apoyarse en
un presupuesto global:

> **Cada cambio paga lo suyo dentro de su propio párrafo.** Toda frase que entra desplaza
> texto de extensión parecida en el mismo bloque. Las ~30 palabras que libera D9 **no se
> gastan**: quedan de reserva para la recomposición.

Es más trabajo de redacción que añadir al final, pero es lo único que mantiene el conteo
bajo control sin tocar márgenes ni tipografía.

## Fase 1 · Los gratis (15 min)

Cuatro cambios que no tocan una sola línea de composición. Se hacen primero porque no
tienen riesgo y dejan el resto medible.

### B3 — apagar las cajas de enlace

```diff
- \usepackage{hyperref}
+ \usepackage[hidelinks]{hyperref}
```

Comprobado en A/B: elimina el recuadro de color de cada cita y URL, y el hueco que dejaba
antes del punto. **No mueve nada de layout.**

### C6 — «over» → «about»

```diff
- records over 150,000 new cases of depressive episode (CIE-10 F32) per year
+ records about 150,000 new cases of depressive episode (CIE-10 F32) per year
```

La Figura 1, en la página siguiente, muestra 151 612 · 148 188 · 149 402. «About» es lo que
la propia figura sostiene.

### C7 — la ventana real

```diff
- substantiated by the first eighteen epidemiological weeks of 2026.
+ substantiated by the 2026 bulletins published since the training cutoff.
```

Evita comprometerse con un conteo que el pie de la Tabla 2 contradice.

### B4 — rótulos (a) y (b) en la Figura 3

En `fase4_figuras.py`, anteponer `(a)` y `(b)` a los títulos de cada panel, como ya hace la
Figura 1. Se regenera la figura; **la proporción no cambia**, así que el presupuesto tampoco.

**Gate:** `compila.sh` → 20 páginas. Si se movió algo, es B4 y se revisa antes de seguir.

---

## Fase 2 · Liberar espacio (10 min)

### D9 — retirar el recuadro redundante de la regla de selección

Justo debajo de la formulación matemática de la regla hay un recuadro en texto plano que
repite lo mismo en prosa. Son **9 líneas de `.tex`, 7 impresas**.

No se pierde información: la regla queda enunciada formalmente arriba, y el
pseudocódigo está liberado con el código, cosa que el Apéndice A ya declara.

Es además lo que pidió el Revisor #1 —*«sections and objects that do not add much value»*—
y el único bloque del paper que dice dos veces lo mismo.

**Gate:** recompilar y confirmar **19 páginas** o 20 con la última página a ~40 líneas.
Sin esa holgura confirmada, la Fase 3 no arranca.

---

## Fase 3 · Los de contenido (45 min)

### A1 — llevar la ablación a la Discusión y a las Conclusiones

**Lo que hay que sustituir en §6**, apertura actual:

> Combining forecasters with complementary inductive biases and selecting one model per
> series through a transparent, revisable rule provides a principled way to forecast a
> heterogeneous panel: it preserves the simpler model when an aggregate series favors it
> and reselects models as live data accumulate. […]

**Por algo de la misma extensión que diga lo que el paper realmente encontró:** que la
diversidad del pool no explica el resultado, que la señal de validación cruzada no se
transporta, y que lo que sí sobrevive es el mecanismo de revisión contra el despliegue
congelado (32,7 % → 28,5 %). El registro auditable deja de ser un adorno y pasa a ser lo
que permite detectar que la asignación dejó de servir.

**Y en §7**, sustituir el cierre para que la contribución declarada sea la del resumen: no
que cuatro modelos ganen a uno, sino que un mecanismo auditable detecta cuándo una
selección congelada deja de transportarse y la revisa con observaciones anteriores.

**Regla de oro de esta fase: cada párrafo nuevo sustituye a uno existente.** Si el conteo de
líneas sube, se recorta ahí mismo, no después.

### A2 — «locked» deja de significar dos cosas

En §4.1:

```diff
- Under the selection strategy it is locked for 107 of 111 combinations (96.4%)
+ Under the selection strategy it is selected by the primary rule for 107 of 111
+ combinations (96.4%)
```

Y una frase que declare la discrepancia: en la serie regional *Sur-Sureste vulnerable ·
general*, Stacking y DeepAR empatan dentro de la banda del 5 %; la regla publicada desempata
por MASE y elige Stacking, mientras el sistema desplegado desempató por RMSE y fijó DeepAR.
De ahí que §5.1 tome **108** como línea base congelada y §4.1 reporte **107**.

Dos líneas, y cierran el único punto donde el registro auditable y el despliegue difieren
sin decirlo.

### B5 — nota de redondeo en la Tabla 2

Añadir al final de la nota acumulada: que los agregados se computan sobre valores sin
redondear, por lo que la suma de la columna reconciliada puede diferir en un caso.

### D8 — el ajuste desigual, como limitación

§3.3 ya declara que no se iguala el presupuesto de ajuste. Con la ablación, eso pesa más:
**el modelo más ajustado es el que gana fuera de muestra**. Conviene decirlo antes de que lo
diga un revisor.

Una limitación nueva, breve: el presupuesto de búsqueda no es parejo entre candidatos, así
que las comparaciones fuera de muestra entre Prophet y el resto no son estrictamente
como-por-como, y el resultado de la ablación debe leerse con esa reserva.

**Gate:** `compila.sh` → **≤20 páginas**, 0 errores, 0 undefined, ningún overfull >15 pt.

---

## Fase 4 · Verificación (20 min)

1. `auditoria_paquete.py` — las 41 comprobaciones.
2. `valores_retirados.py` — ninguna cifra vieja resucitada.
3. `ventanas_coherentes.py` — la Figura 3 regenerada no rompió las ventanas.
4. `pytest tests/paper_micai_2026 --no-cov` — las 20 pruebas.
5. **Relectura de §6 y §7 completas**, no en diagonal: son las que se reescriben, y es
   donde un empalme mal hecho se nota.
6. Revisión visual de las páginas que se movieron.
7. `empaqueta_envio.py` — rehace el ZIP y lo compila desde dentro.
8. Actualizar `Envio/HASH_ENVIO.txt` con el sha256 nuevo.

---

## Si aun así llega a 21 páginas

En este orden, y sin pasar al siguiente hasta agotar el anterior:

1. Comprimir el párrafo *Search budget* de §3.3 (~4 líneas de prosa densa).
2. Comprimir el pie de la Figura 3, que hoy explica el código de colores barra por barra.
3. Acortar la nota al pie de la Tabla 1, que son 8 líneas de letra chica.

**No tocar**: márgenes, tipografía, la clase LNCS, ni retirar la Figura 4.

---

## Lo que NO se cambia

- **El título.** Ya se decidió conservarlo, y §5.1 lo matiza dentro del texto.
- **Los números.** Nada de esto los toca; el paquete sellado no se vuelve a abrir.
- **La cabecera.** Autores, afiliaciones y ORCID quedaron cerrados contra CMT y TEC-II-05.

---

## Riesgos

| Riesgo | Prob. | Mitigación |
|---|---|---|
| A1 crece de más y rompe el techo | media | regla de sustitución; se mide después de cada párrafo |
| B4 cambia la proporción de la Figura 3 | baja | sólo se tocan los títulos; se verifica el aspecto antes de recompilar |
| Un empalme deja §6 incoherente | media | relectura completa de §6 y §7 en la Fase 4, no sólo gates |
| Se resucita una cifra vieja al reescribir | baja | `valores_retirados.py` la caza |

---

## Total: unas 90 minutos

Y quedan dos días de margen sobre el deadline. Lo que de verdad aprieta no es esto: es
**CMT, la licencia firmada y el registro**, que dependen de terceros.
