# Rescate de los controles: naive coherente (22-nov-2026)

Orden del autor: revisar todos los padecimientos que no pudimos dar por buenos e investigar técnicas
para meterlos. Este documento cubre los **97 publicados sólo con el control** (87 controles tras
rechazo en la prueba de 2025 y 10 controles por construcción) y explica por qué las 33 categorías
sin pronóstico del runner siguen fuera. **No publica, no reentrena, no toca releases ni reabre
2025**: todo se mide en años de desarrollo y lo único que se congela es una sombra nueva (v4).

## Qué fallaba

La compuerta de aceptación compara contra el naive lag 52 tres ámbitos a la vez: el sMAPE del
nacional General (hasta 10 % peor), la mediana del sMAPE de las 64 bases (hasta 5 %) y la mediana
del sMAPE de los 111 productos (hasta 5 %; 32 bases y 37 productos sin desglose por sexo). Hay un
conflicto entre ellos:

- En una base rala, una semana con verdad 0 y pronóstico positivo vale 200 % de sMAPE. El naive
  copia los ceros del año anterior, así que es difícil de superar en la mediana de las bases.
- Los motores que suavizan (nivel × perfil, top-down ETS) le ganan al naive en el nacional, pero
  reparten masa positiva en bases ralas. En desarrollo, nivel × perfil por base mejora el nacional
  −13 % y empeora la mediana de las bases +55 % en los controles: pasa la compuerta en 28 % de los
  pliegues.

## Mesa de expertos

Cuatro dictámenes independientes, con búsqueda de literatura: pronóstico de conteos, reconciliación
jerárquica, epidemiología de vigilancia y aprendizaje automático. Coincidieron en tres puntos:

1. No tocar los ceros de las bases (Kolassa, 2016, *IJF*: el pronóstico puntual óptimo depende de
   la métrica) y corregir sólo el agregado.
2. Reconciliar desde arriba con el nacional como pronóstico inmutable y escalado proporcional
   (Athanasopoulos, Ahmed y Hyndman, 2009, *IJF*; Zhang et al., 2023, *EJOR*). MinT, OLS y WLS
   estructural reparten masa a bases ralas y se descartaron.
3. Combinar con pesos iguales en el agregado (Claeskens et al., 2016, *IJF*; Petropoulos y
   Svetunkov, 2020, *IJF*) y fijar una sola configuración global: el banco ya había mostrado que
   ajustar por padecimiento sobreajusta.

Lo que no ayudó y quedó descartado: reglas por clase epidemiológica con umbrales elegidos en años
internos (80 rescatados frente a 82 sin ellas, en el prototipo), una clase «rara» con mediana de
ventana, el crecimiento amortiguado del nivel aplicado a todos y el LightGBM global.

## El método: naive coherente (`src/epiforecast/banco/coherente.py`)

1. **Bases = el control.** Naive lag 52 por serie, con el calendario MMWR del runner.
2. **Forma nacional combinada.** Cuatro miembros calculados sólo con la historia previa al origen:
   el naive nacional, nivel × perfil (configuración por defecto del banco), ETS amortiguado sobre
   log1p y la media de la misma semana en 3 años. Cada miembro se reescala al mismo nivel (media de
   las últimas 52 semanas) y se toma la mediana semana a semana. Combinar formas y no niveles evita
   que los miembros con años viejos arrastren el nivel en las series en recuperación post-COVID
   (quemaduras, isquémica, cáncer de mama).
3. **Reparto multiplicativo.** Cada semana, todas las bases se multiplican por un mismo factor,
   acotado a [0.5, 2], para que sumen el nacional combinado. Un cero del naive sigue en cero.
4. **Redondeo controlado.** Bases enteras que suman el redondeo del nacional de cada semana (mayor
   residuo); los 111 productos siguen siendo sumas exactas. El control también es entero.

El factor anual solo no sirve: el nivel de nivel × perfil es la media de las últimas 52 semanas, que
es el total que ya copia el naive. Toda la ganancia viene de la forma semanal.

## Resultados en desarrollo (`make banco-rescate`)

Banco de rescate (`src/epiforecast/banco/rescate.py`, `scripts/banco_rescate.py`): la compuerta
completa, con los límites leídos de la política de cada release, en cada año de desarrollo. Un
pliegue es positivo si pasa los tres ámbitos y mejora el nacional; un padecimiento queda *rescatado
en desarrollo* si pasa en todos sus años externos (2023 y 2024; 2025 en historia corta) y su mejora
nacional media es negativa.

| Evaluación | Controles rescatados | Pasan sin mejora | No pasan | Mejora nacional (mediana) | Bases / productos |
|---|---|---|---|---|---|
| Selección anidada entre 10 variantes | **73 / 97** | 7 | 17 | −10.2 % | 0.0 % / 0.0 % |
| Variante fija f4 (la de la sombra v4) | **80 / 97** | 5 | 12 | −13.2 % | 0.0 % / 0.0 % |

- **Diez controles no pueden pasar con ningún método:** chikungunya, fiebre manchada, *Haemophilus*,
  leishmaniasis cutánea, meningocócica, paludismo por *P. vivax*, tétanos, tifo murino, tracoma y
  triquinosis. La mediana del sMAPE del control vale 0 en las bases o en los productos, y el runner
  reprueba toda comprobación con el control en 0 (`acceptance.evaluate_gate`). De los 87 restantes,
  la variante fija rescata 80 y la anidada 73.
- **Lectura correcta:** el método mejora el nacional sin mover las bases. Tras el reparto acotado y
  el redondeo, muchas bases quedan iguales al control: la diferencia en bases es exactamente 0 en
  37 % de los pliegues y en productos en 34 %. Las comprobaciones de bases y productos casi no se
  ponen a prueba.
- **Selección anidada** (la cifra honesta): para el año externo O se elige la variante con más
  pliegues positivos en los años anteriores a O; eligió `comb4` (mediana de valores) en 2023 y 2024
  y `f4` (mediana de formas) para la historia corta. Aun así es optimista: las 10 variantes, los
  límites [0.5, 2] y los miembros se diseñaron mirando estos mismos años.
- **Variante fija:** `f4` se fijó **después** de ver los años de desarrollo; su cifra es optimista.
  Pasa 154 de 175 pliegues externos y mejora el nacional en 144.
- No se reportan valores p: los padecimientos comparten años y no son independientes.
- 19 controles se juzgan con un solo pliegue (2025, historia corta) y 4 con dos.
- En los 51 portafolios aceptados el naive coherente también le gana al control (47 de 51 con la
  variante fija). No se comparó contra sus portafolios publicados.

Auditoría adversaria independiente (22-nov-2026): sin fuga de datos (historia truncada al último año
de desarrollo; todos los miembros usan sólo el entrenamiento), matriz de productos y control iguales
a los del runner. Encontró que la primera versión aprobaba los casos con control y variante en 0
(el runner los reprueba) e inflaba las cifras a 88 y 81; se corrigió. El comentario de
`config/sombra/sombra_v4.yaml` conserva la cifra de 88 porque su hash quedó en el índice de la
emisión; la cifra vigente es la de esta tabla. Diferencia menor declarada: `perfil_eb` parte la
historia en bloques de 52 semanas (no la usa la variante f4).

Veredictos por padecimiento: `docs/rescate_controles/fijo.csv` y `veredictos.csv`; resumen y
procedencia junto a ellos.

### Los siete posibles que la variante fija no rescata

- ESAVI, mordedura de serpiente coralillo, tos ferina y viruela símica: raros, con sMAPE nacional
  semanal ≥ 100 %; pasan la compuerta sin mejorar el nacional (+0.3 a +6.3 %). Con tan pocos casos
  el sMAPE semanal no distingue métodos.
- Tifoidea pasa con +4.4 % en el nacional.
- Anorexia no pasa (2024, +27 % nacional) y neumonías no pasa por las bases en 2023 (+8 %), aunque
  mejora el nacional −7 %.

## Las 33 categorías sin pronóstico del runner

No son un problema de técnica. 7 no tienen desglose estatal y 14 no tienen casos (o tres o menos en
el país): no hay serie que modelar ni prueba posible. Influenza y enfermedad febril exantemática
tienen el total de 2025 imputado («Sem −1»). Nueve tienen bloque propio desde 2025 o 2026: el naive
coherente funciona con un año de historia (es lo que ya se midió en los 10 controles por
construcción), así que podrán entrar cuando tengan un año completo y un pliegue de desarrollo.
Enfermedades infecciosas intestinales es un agregado de componentes ya publicados.

## Cómo se meten: sombra v4

Congelada `sombra_v4_20261122_7c5f823426` (22-nov-2026, 23:37 UTC, 18:37 en hora del este; commit
`365527c1`, configuración `974be1d4…`, índice `7932ba00…`). Un solo motor para los 148
(`naive_coherente_f4`, `seleccion.fijo`), origen W43 en 125 y W44 en 23, intervalos 80/95 con
cuantiles nominales del residuo log1p de desarrollo. Retroprueba en desarrollo (ventana creciente,
114 padecimientos): mediana nacional 24.36 frente a 28.30 del control (v3: 25.92); mejor que el
control en 106 y dentro del 10 % en los 114; cobertura 82.3 % y 93.9 %. La validación prospectiva
ahora reporta también la mediana del sMAPE de los 111 productos, el tercer ámbito de la compuerta.

```bash
python -m scripts.sombra_v2 --politica sombra_v4 valida sombra_v4_20261122_7c5f823426
```

Adoptarlo requiere autorización del autor. La prueba de 2025 ya se consumió y no se reabre: la
evidencia de aceptación sólo puede venir de semanas de 2026 no vistas al emitir. Criterio sugerido,
sin decidir aquí: tras al menos 8 semanas, que la sombra v4 pase los tres ámbitos de la compuerta
frente al control en la mayoría de los 97 y que la cobertura quede cerca de la nominal.
