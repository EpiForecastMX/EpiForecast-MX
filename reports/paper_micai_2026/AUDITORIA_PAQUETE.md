# Auditoría del paquete — MICAI 2026, ponencia #12

**20 de agosto de 2026** · `Envio/012.zip` · sha256 `83c1a737…b78078`
Reproducible: `.venv/bin/python scripts/paper_micai_2026/auditoria_paquete.py`

---

## Veredicto

**El paquete es técnicamente correcto y se puede subir.** 41 comprobaciones automáticas
en verde, cero fallos, las 20 páginas revisadas a ojo.

**Pero hay una promesa del paper que hoy no se cumple**, y depende de una acción fuera del
repositorio. Va primero.

---

## 1. RESUELTO — el material prometido ya está publicado

> **Cerrado el 21-ago-2026**, commit `73800d1` del repo público. Se publicó
> `data/per_series_out_of_sample_2026.csv` (111 series, sMAPE y MASE por modelo,
> W03–W18), se añadió la corrección de Holm a `analysis/statistical_tests.py`, se
> documentó el desfase de semana en el README y en el docstring, y se retiró el
> encuadre de doble ciego, que seguía ahí pese a la aceptación. La tabla publicada
> es byte-idéntica a la local. **Las tres promesas del paper se cumplen.**

### El problema, tal como se encontró


El artículo dice tres veces que hay material liberado con el código:

| Dónde | Qué promete |
|---|---|
| §3.3, *Code availability* | «the model-selection, evaluation, and analysis code supporting this study is publicly available at…» |
| §4.2 | «the per-state out-of-sample errors for every entity… are **released with the source code as supplementary material**» |
| Apéndice A | «the configuration files, the model-selection pseudocode, and **the per-state out-of-sample table** are released with the source code» |

`github.com/IntegradorIMSS2026Team01/per-series-model-selection2026` responde **HTTP 200**,
es público, y contiene:

```
src/selection.py · src/metrics.py · src/cross_validation.py
analysis/baselines.py · analysis/reconciliation.py · analysis/statistical_tests.py
README.md · requirements.txt · LICENSE
```

**9 KB, sin tocar desde el 24 de mayo.** La primera promesa se sostiene. **La segunda y la
tercera no: la tabla por estado no está ahí.**

Y ese hueco lo abrimos nosotros: la tabla era el Apéndice B, la quitamos en Fase 2 para
ganar página, y redirigimos las tres referencias al repo. Si un lector abre el enlace
buscándola, no la encuentra.

Hay una segunda arista: `analysis/statistical_tests.py` es de mayo, es decir, **reproduce
el Diebold–Mariano viejo** —el que salía de `knowledge.json`— y no los valores corregidos
con Holm que ahora imprime el paper. Quien lo corra obtendrá otros números.

**Qué hace falta**, y es una acción pública que no ejecuto sin tu visto bueno:

1. subir `reports/paper_micai_2026/resultados/oos_por_serie.csv` como tabla por estado;
2. actualizar `statistical_tests.py` a la versión con alineación corregida y Holm;
3. añadir al README una nota de que las cifras vigentes son las del camera-ready.

Alternativa si no quieres tocar el repo antes del domingo: **suavizar las dos frases** para
que prometan sólo lo que hay. Cuesta dos ediciones y no mueve páginas.

---

## 2. Lo conocido, que no bloquea el envío

**CMT no coincide con la portada.** Cinco apellidos sin guion y `ITESM` como afiliación,
que el propio lineamiento del Tec prohíbe. Springer toma las afiliaciones del PDF, así que
no arrastra al artículo publicado, pero el índice de autores sale de CMT: sin guion,
`Pérez Hernández` puede quedar indexado como segundo nombre + apellido.

**La tensión del título.** El artículo se llama *Multi-Model Framework* y su propia
ablación concluye que el pool no mejora la exactitud. Está encuadrado con honestidad —el
valor es el mecanismo auditable de revisión— y así se acordó. Lo dejo anotado porque es el
único punto donde un revisor hostil puede apretar, y conviene que lo tengas presente para
la presentación oral en Chihuahua.

---

## 3. Las 41 comprobaciones en verde

**Paquete** — ZIP íntegro, sin basura de macOS, **un solo `.tex`**, con `llncs.cls`,
`splncs04.bst` y **exactamente las 3 figuras referenciadas, ni una de más**.

**Reglas de LNCS** — clase `llncs[runningheads]`; **sin `geometry`, `fullpage`, `setspace`
ni `times`**, o sea sin tocar el trim que Springer rechaza; ningún flotante con `[h]`; sin
`\vspace` negativos; las **4 tablas con caption arriba** y las **4 figuras con caption
abajo**; **un solo autor de correspondencia**; los **5 ORCID**; `authorrunning` definido;
alt-text en las 4 figuras.

**Restos de la versión ciega** — cero. Ni `Anonymous`, ni `withheld`, ni bloques activos.

**Bibliografía** — 28 bibitems sin duplicados, **todas citadas**, **todas las citas con
bibitem**, **en orden alfabético**, 23 de 28 con DOI o URL.

**Numeración** — figuras 1–4 y tablas 1–4, consecutivas y sin huecos.

**PDF** — **A4 real**, 20 páginas, **las ligaduras se extraen bien** (`cutoff`, no `cuto`),
**sin `ITESM`**, con `Tecnologico de Monterrey` conforme a TEC-II-05, los 5 ORCID impresos.

**Abstract** — ~236 palabras contra un límite de 250.

**Gates heredados** — ninguna cifra retirada viva; ventanas coherentes entre JSON, `.tex`,
pies y el rótulo dentro de la Figura 4; el paquete compila desde el propio ZIP.

---

## 4. Lo que verifiqué de más

**`llncs.cls` y `splncs04.bst` son byte-idénticas a las del template oficial**
(`a3cfe775…`). Veníamos asumiéndolo desde el principio sin comprobarlo.

**Las diez cifras por estado de §4.2 cuadran a la centésima** con el paquete sellado —
Michoacán 1,03 · Morelos 1,40 · Guanajuato 1,94 · Baja California 2,09 · Coahuila 2,15 ·
Nuevo León 7,91 · Querétaro 9,75 · Tlaxcala 11,47 · Durango 12,91 · Puebla 16,28 — y el
`MASE below 0.5 throughout` se sostiene: el máximo es **0,419**.

Nunca las había verificado: venían de antes de que empezáramos.

---

## 5. Revisión visual

Las 20 páginas, una por una. Composición correcta, sin huecos donde se retiraron la
Figura 2 y la Figura 3, sin títulos huérfanos, tablas alineadas, la Figura 3 con la
etiqueta de W14 ya despejada del título, y el documento cierra en la página 20 con la
referencia 28.
