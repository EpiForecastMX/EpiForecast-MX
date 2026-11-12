# Segundo dictamen de Fable sobre la implementación del lote alta20 (12-nov-2026)

Revisor: **Fable 5.2, esfuerzo medium**, lectura de código del frontend (rama `claude/alta20-publicacion` en
`c7977281`) y de dos documentos del backend, sin ejecutar pruebas ni consultar el sitio. Se conserva el texto
del dictamen; se omiten los metadatos de la sesión y de la cuenta.

## Verificación y correcciones (Opus 5.5 medium)

Cada hallazgo se reprodujo con una prueba que falla en `c7977281` y pasa con la corrección (frontend
`5100be4e`, 28 pruebas nuevas en `epibot/tests/test_alcance_cie.mjs`; regresión de cronología en
`tests/fichas.test.mjs`).

| Hallazgo | ¿Real? | Corrección |
| --- | --- | --- |
| 1. «presión arterial baja en el embarazo» resolvía a O10-O16 | Sí (confirmado también por el supervisor) | Con presión baja no se reescribe nada y `mencionaNoModelada` la detecta antes de retirar alias |
| 2. Diabetes del embarazo perdía su aviso en consultas mixtas | Sí | Con «diabet» en la consulta no se reescribe; se conserva «diabetes gestacional» o «diabetes en el embarazo» y no se responde con O10-O16 |
| 3. La consulta sugerida de vehículos no era alias | Sí | `consulta: 'accidentes en vehiculos con motor'`; prueba de que la consulta de cada release y cada botón del panel resuelven a su release. También los botones de amebiasis usaban «amebiasis» a secas |
| 4. Variantes de amebiasis, otitis y conjuntivitis sin guarda | Sí | Ampliadas; la fuente imprime A06.4 (absceso hepático amebiano), B30.3 y V01-V09 como categorías propias. Lo demás se nombra sin inventar clasificación |
| Alias genéricos «otitis», «otitis media» | Sí | Sin decisión nueva del autor (indicación del supervisor): «otitis», «otitis media», «h65», «amebiasis» y «a06» a secas piden precisar sin cifras, en el KB y en la función RAG |
| Menor: «obesidad en ciclistas», «asma en peatones» | Sí | Peatón y ciclista sólo son subtipo ajeno con contexto de accidente o transporte |
| Menor: «a06 4 semanas», «h65 2 semanas» | Sí | Un número seguido de semanas, días, meses o años no se lee como subcódigo |
| Menor: numerales hasta «cuarenta» | Sí | Se componen hasta noventa y nueve en `kb.js` y `rag.mjs` |
| Menor: «quince» frente a diecisiete detenidos y tabla incompleta | Sí | Corregido con cifras medidas en `docs/C7_15_ALTA20.md` y `DECISIONES_PENDIENTES.md` |

Fallo adicional que Fable no vio y verificó el supervisor en el navegador: las cinco fichas nuevas heredaban
de su plantilla el origen W41, la emisión del 8-nov y la ventana W42-W45 en el HTML estático. Corregido a W42,
12-nov-2026 y W43-W46 (los gates sellados), con prueba contra el manifiesto y la vista de cada release.

## Texto del dictamen

**Dictamen: sin bloqueantes de publicación en lo leído, pero con cuatro fallos de alcance reales en el EpiBot que conviene corregir antes de dar por cerrado el arreglo de A06.4/H65.2.** Todo sale de lectura de código: no ejecuté pruebas ni consultas, así que cada reproducción es el resultado esperado según el código y falta confirmarla con un caso de prueba.

## Fallos concretos

**1. Regresión: «presión arterial baja en el embarazo» recibe cifras de O10-O16** (`epibot/js/release_catalog.js:393-399`)
- `HTA_TERMINO` incluye «presion arterial» y «tension arterial» a secas, y `hipertensionDelEmbarazo` las borra antes de que `mencionaNoModelada` busque «presion arterial baja».
- La consulta queda como «baja en el trastornos hipertensivos del embarazo» y resuelve al release.
- Reproducción: `mencionaNoModelada(norm('presión arterial baja en el embarazo'))` debería dar `null`, y `pregunta(...)` la marca `EMBARAZO_HIPERTENSIVOS_O10`. Igual con «tensión arterial baja en embarazadas».
- Antes del lote respondía «no modela presión arterial baja».

**2. Regresión: consultas mixtas con diabetes del embarazo pierden su guarda** (`release_catalog.js:394-398`, `:425`)
- `EMBARAZO_TERMINO` borra «embarazo» y «gestacional», así que «diabetes gestacional» y «diabetes en el embarazo» ya no coinciden con `noModeladas`.
- Reproducción: «diabetes gestacional e hipertensión en Jalisco» e «hipertensión y diabetes en el embarazo» deberían devolver la ficha O10-O16 sin avisar que la diabetes del embarazo no se modela.
- En la primera, además, la hipertensión nombrada es la arterial (I10-I15), no la del embarazo.
- El punto 9 del plan pedía justo esta prueba mixta; `test_alcance_cie.mjs` no la tiene.

**3. Las sugerencias del propio bot para vehículos no llegan al release** (`release_catalog.js:321`)
- `consulta: 'accidentes de transito'` no es alias, a propósito, pero con él se arman las sugerencias (`app.js:3835-3839`) y los textos (`obesidad_charts.js:92-96`, `obesidad_kb.js:219-220`).
- Reproducción: tras «accidente de transporte en vehículos con motor en Jalisco», pulsar «Zoom semanal» envía «zoom accidentes de transito».
- Sin alias, la toma `answerRadarBoletin` (`radar_boletin.js:58`) y respondería «Peatón lesionado… no modela», porque vehículos ya tiene `platform_id` y queda fuera de las candidatas.
- `test_sin_tabla_neuro.mjs:112` fija ese comportamiento para «accidentes de transito en sonora».
- Arreglo natural: `consulta: 'accidentes en vehiculos con motor'`, más una prueba de que la `consulta` de cada release resuelve a su propio release.

**4. Negativos no cubiertos por `SUBTIPOS_AJENOS`** (`release_catalog.js:473-490`): reciben cifras del bloque vecino.
- **Amebiasis:** «amibiasis hepática», «amibiasis extraintestinal», «amoebiasis hepática», «amebiasis del hígado». La expresión de `:476` sólo reconoce «amebiasis», pero «amibiasis» y «amoebiasis» son alias y prefijos.
- **Otitis:** «otitis supurativa» (el ejemplo que citan `entities.js:269` y `rag.mjs:280`), «otitis media aguda supurativa» (H66.0), «otitis purulenta», «otitis interna». La expresión de `:478` exige «otitis media» seguido del adjetivo.
- **Conjuntivitis:** «conjuntivitis vírica», «conjuntivitis por adenovirus», «conjuntivitis adenoviral», «conjuntivitis aguda epidémica hemorrágica» (otro orden), «conjuntivitis gonocócica», «conjuntivitis neonatal».
- **RAG:** como esos casos no dan `subtipoAjeno`, la función tampoco corta en `rag.mjs:592`.

## Para decisión del autor

- **Alias genéricos de otitis** (`release_catalog.js:297-298`): «otitis» y «otitis media» a secas, y el prefijo `otitis`, responden con H65.0-H65.1. La otitis media sin especificar es H66.9, fuera del bloque. Es el mismo criterio por el que se excluyó «accidente de tránsito» a secas, y contradice el comentario de `:296`.

## Menores

- `subtipoAjeno` se aplica a cualquier consulta: «obesidad en ciclistas» o «asma en peatones» pasan a «no modela».
- «a06 4 semanas» y «h65 2 semanas» se leen como A06.4 y H65.2.
- `NUMERALES` (`rag.mjs:441`, `kb.js:629`) termina en «cuarenta», que es exactamente el total actual. El siguiente alta cae a dígitos y rompe las pruebas que fijan el numeral.
- `docs/C7_15_ALTA20.md:6` dice «quince candidatos detenidos», pero la sección y `DECISIONES_PENDIENTES.md` listan 17.
- La tabla de incidencia de `DECISIONES_PENDIENTES.md` no trae candidiasis, las dos displasias, diabetes en el embarazo ni hepatitis C.

## Revisado sin hallazgos

- **Embarazo sin sexo:** el corpus y `report.md` dicen 32 modelos y 37 productos. La ficha replica la plantilla de cuello del útero y `obesidad_kb.js:141-149` avisa y descarta el sexo pedido.
- **0/4:** los cinco figuran `INCOMPLETE` 0/4 en `publication/catalog.json` y en el corpus, nunca como PASS.
- **Rechazados:** quemaduras, insuficiencia venosa e hiperplasia no aparecen en fichas, catálogo, noticias ni bot. La única «Rechazada» del radar es una categoría anterior al lote.
- **Radar:** `platform_published` es 40 y los cinco tienen `platform_id`.
- **Caché:** las versiones `?v=` son coherentes entre portada, bot y módulos.
- **RAG:** el corte por subtipo ajeno ocurre antes de pedir la clave.

No verifiqué red, CI, el sitio servido, la disponibilidad del boletín 44 al emitir, los `vista.json`, `rag_index.json` ni el backend fuera de los dos documentos.
