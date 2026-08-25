# Contrato de vocabulario — cifras públicas de EpiForecast-MX

> Congelado el **2026-08-24**. Vinculante para el sitio público, el EpiBot, el corpus RAG,
> las diapositivas de congreso y cualquier texto derivado.
>
> Existe porque el 24-ago-2026 se encontró que el sitio publicado respondía **435** donde
> las diapositivas decían **333** y el manifiesto canónico decía **432**: tres cifras
> verdaderas contando cosas distintas, más una cuarta que era sencillamente falsa.

---

## 1. Las cuatro cifras, y qué cuenta cada una

| Cifra | Nombre canónico | Qué cuenta exactamente |
| ---: | --- | --- |
| **333** | series neuro productivas | 3 padecimientos × 37 geografías × 3 sexos |
| **99** | series de dengue productivas | 33 geografías × 3 sexos (32 entidades + nacional) |
| **432** | **series productivas totales** | 333 + 99 |
| **444** | **gráficos publicados en la galería** | 333 neuro + 111 dengue |

**Los 12 de diferencia entre 99 y 111** son las cuatro regiones de dengue por tres sexos.
La galería las dibuja **agregando sus estados**; no tienen modelo propio
(`build_dengue_gallery.py:74`). Por eso dengue publica 111 gráficos base pero solo 99
vistas de comparación de motores: la comparación solo existe donde hubo competencia.

## 2. La palabra «motores»

**«Motor» designa una familia algorítmica, nunca una serie.** No se cuentan series por
motor y se llama al resultado «motores». Los motores son:

- **Cohorte neuro:** Prophet, DeepAR, Ensemble, Stacking. Son **4**.
- **Cohorte dengue:** Prophet, DeepAR, NBGLM. Son **3**. Ensemble y Stacking **no son
  elegibles** para dengue (los árboles no extrapolan la dinámica epidémica).

Un desglose por motor es una *distribución*, y siempre suma el total de su cohorte.

## 3. Cifras prohibidas

| Cifra | De dónde venía | Por qué es falsa |
| ---: | --- | --- |
| **435** | `stats.total_modelos`, derivado de `tabla_333_modelos_produccion.xlsx` | Cuenta **dos veces** las 3 series `Dengue · Nacional`, una por Prophet y otra por DeepAR, en los tres sexos. No son 3 modelos de más: es la misma serie duplicada. |
| **102** | dengue en `tabla_333_modelos_produccion.xlsx` | Los 3 duplicados de arriba, más 13 selecciones de Ensemble/Stacking que no son elegibles, y **sin NBGLM**. Es una selección previa al selector vigente. |
| **145** | `stats.por_sexo` | Consecuencia del 435. El valor correcto es **144**. |
| **15** | nacionales | Consecuencia del 435. El valor correcto es **12** = 9 neuro + 3 dengue. |
| «111 × 3 = 435» | texto del EpiBot | Ecuación falsa: 111 × 3 = **333**. Mezclaba el desglose neuro con el total inflado. |

## 4. Fuente única

El catálogo canónico manda, y se regenera desde las fuentes vigentes:

```
.venv/bin/python -m scripts.build_catalogo_canonico
```

- Escribe `reports/ProdDetails/catalogo_canonico.csv` (432 filas, clave única) y
  `catalogo_canonico_counts.json`.
- Sale con código ≠ 0 si hay duplicados o motores no elegibles.
- Lee neuro de `tabla_333_modelos_produccion.xlsx` **filtrado a la cohorte neuro**, y
  dengue de `produccion_dengue.csv` (nunca de la tabla 333).

> ⚠️ **El manifiesto puede quedar más viejo que su fuente.** El 24-ago-2026 el
> `catalogo_canonico_counts.json` vigente se había construido el 18-ago a las 15:31 y
> `produccion_dengue.csv` se regeneró ese mismo día a las 22:30: **siete horas después**.
> El manifiesto seguía publicando la distribución de dengue `DeepAR 30 · NBGLM 30 ·
> Prophet 39` cuando la real era `Prophet 46 · DeepAR 27 · NBGLM 26`. Los totales
> coincidían, así que ningún conteo lo delataba. **Regenerar el catálogo es obligatorio
> después de cualquier corrida que toque `produccion_dengue.csv` o la tabla 333.**

## 5. Ninguna reparación en el navegador es fuente de verdad

El cliente **no** corrige cifras. Si el JSON publicado trae un número equivocado, se
corrige el **generador** y se vuelve a publicar. Reparar en `kb.js` deja el JSON, el
corpus RAG y el respaldo generativo diciendo otra cosa, y produce un verde falso: la
respuesta local se ve bien mientras la tarjeta recuperada dice 435.

## 6. Gate de aplicación

Se comprueban las nueve, y las nueve deben pasar:

1. 432 claves únicas `(disease_id, entidad, sexo)`.
2. Dengue = 99.
3. Neuro = 333.
4. Dengue sin Ensemble ni Stacking.
5. Dengue con NBGLM presente.
6. Por sexo = 144 cada uno.
7. Nacional = 12, repartido 9 neuro + 3 dengue.
8. La distribución global de motores suma 432.
9. `motor_dist` del manifiesto **es igual** a la del CSV vivo (atrapa el manifiesto rancio).

Y, sobre lo publicado: **ninguna respuesta, tarjeta RAG, fixture ni texto derivado
conserva 435, 102, 145 ni el nacional 15.**

## 7. Redacción autorizada

- «**432** series productivas · **444** gráficos publicados.»
- «Los 12 adicionales son vistas regionales de dengue agregadas, **no modelos**.»
- «**333** modelos neuro en producción, repartidos en **37** geografías: 32 entidades,
  4 regiones y el nacional.»
- Para la lámina 7 de CALASS: «uno por serie publicada — 333 neuronales y 111 de dengue».

---

## 8. Bitácora de aplicación — 24-ago-2026

### Lo que estaba roto, y por qué ningún control lo veía

Tres no-ops encadenados, cada uno invisible por separado:

1. **`filter_neuro` no filtraba.** Su columna por defecto era `"Padecimiento"` con
   mayúscula; el consolidado del boletín la escribe así, pero
   `tabla_333_modelos_produccion.xlsx` y `produccion_dengue.csv` la escriben en minúscula.
   La comparación exacta caía en la rama «la columna no existe» y **devolvía el frame
   entero**. Corregido con pliegue de mayúsculas **y de tildes**: los nombres canónicos
   llevan `Depresión` con tilde y el workbook escribe `Depresion`, así que arreglar sólo
   la mayúscula habría descartado las 111 filas de depresión en silencio (222 en vez de
   435, peor que el bug original).
2. **`build_prod_models` no filtraba en absoluto.** Su docstring prometía 333 y exportaba
   435. De ahí salía el `dengue n=102` del `knowledge.json` publicado.
3. **`rag_verify` no leía el contenido.** Comprobaba que cada chunk tuviera un vector
   válido, nunca lo que el chunk decía. El índice estaba perfectamente sincronizado y
   perfectamente equivocado: 454 vectores válidos, cinco tarjetas afirmando 435 modelos.

### El corolario para los gates

Un control que compara textos tiene que compartir la convención de escritura del dato:
punto contra coma decimal, mayúscula contra minúscula, con tilde contra sin tilde. Y una
aguja numérica sin contexto no identifica una celda — en este mismo corpus «102» aparece
de forma legítima como SMAPE del backtest de NB-GLM. Por eso el gate persigue la **forma**
(«102 modelos») y no la cifra suelta.

### La reparación en el navegador

`_fixCohortStats` (`epibot/js/kb.js:80-181`) re-derivaba las stats sobre la cohorte neuro
en el cliente y fijaba `total_modelos = 333`. Por eso el navegador enseñaba 333 mientras el
JSON decía 435 — y por eso la ruta generativa (`netlify/functions/rag.mjs:373-381`), que lee
el JSON **crudo** bajo el rótulo «CIFRAS CLAVE DEL PROYECTO (usar como verdad)», afirmaba
435. Con el generador corregido la reparación quedó redundante; **retirarla es tarea
posterior al congreso**, y sólo tras comprobar que produce exactamente lo mismo que el JSON.

### Diferencias legítimas que NO se deben «corregir»

- La distribución de dengue de la **galería** (`Prophet 54 · NBGLM 24 · DeepAR 21` sobre 99
  gráficos) difiere de la **productiva** (`Prophet 46 · DeepAR 27 · NBGLM 26`) porque
  `build_dengue_gallery.py:958` propaga el motor de la serie *general* a los tres sexos.
  Es por diseño.
- `dengue_en_tabla_333: 102` y `nacionales_duplicados: 3` en
  `catalogo_canonico_counts.json` son **diagnósticos deliberados**: documentan lo que se
  descartó. No son cifras publicables ni deben retirarse.
