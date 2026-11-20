# C7.19 · Lote alta_b44: sesenta y seis publicados del boletín 44 (19-20 nov 2026)

Orden del autor (19-nov-2026, chat directo): «integra todos los padecimientos faltantes del boletin auditas con sol
medium de codex». Alcance aceptado: «Todas con datos», es decir, las categorías «Por incorporar» del catálogo del
radar `2026-w44` con casos y los configurados con prueba de 2025 ya consumida. Las decisiones de gobierno las tomó el
autor nominalmente, con las cifras a la vista (sección «Decisiones del autor»). Ninguna es dictamen delegado.

## Resultado

Sesenta y seis nuevos: **sitio 86 → 152; runner 82 → 148** (los cuatro legacy no cambian). Fuente de verdad:
`config/padecimientos.yaml` (`lifecycle: published`) y `publication/catalog.json` del frontend (148 releases, servido
byte a byte igual al de `main` el 20-nov-2026).

- **15 portafolios aceptados en su prueba única de 2025** (validación prospectiva 0/4, nunca PASS): intoxicación por
  picadura de alacrán, infección gonocócica, herpes genital, tricomoniasis urogenital, intoxicación aguda por
  alcohol, envenenamiento autoinfligido por analgésicos (X60) y por psicotrópicos (X61), lesión autoinfligida por
  ahorcamiento (X70), por objeto cortante (X78) y al saltar desde un lugar elevado (X80), violencia intrafamiliar,
  Chagas aguda, enfermedad invasiva por neumococo, herida por arma de fuego y tuberculosis respiratoria.
- **41 controles estacionales no validados tras un rechazo** (`acceptance_fallback_run` con el run rechazado; con
  cuatro semanas el veredicto será `CONTROL_ONLY`, nunca PASS): mordeduras por perro y por otros mamíferos,
  toxoplasmosis, teniasis, cisticercosis, triquinosis, conjuntivitis hemorrágica, tracoma, hipotermia, tétanos,
  viruela símica, VPH, linfogranuloma venéreo, chancro blando, parálisis flácida aguda, IAAS, enfermedad alcohólica
  del hígado, anencefalia, encefalocele, microcefalia, espina bífida, labio y paladar hendido, cirrosis hepática
  alcohólica, chikungunya, lesión autoinfligida por disparo de arma corta, intento de suicidio (Z91.5), ideación
  suicida (R45.8), tuberculosis otras formas, tifo murino, sífilis congénita, ESAVI, meningitis meningocócica,
  Haemophilus influenzae invasiva, Chagas crónica, VIH, meningitis tuberculosa, lepra, fiebre manchada, otras
  rickettsiosis, leishmaniasis cutánea y paludismo por P. vivax. Siete de ellos (conjuntivitis hemorrágica,
  toxoplasmosis, cisticercosis, hipotermia, teniasis, triquinosis y tracoma) son los rechazos de alta20c que quedaron
  `configured` fuera de cupo: su prueba de 2025 ya consumida no se reabrió.
- **10 controles por construcción** (`rolling_cv_historia_corta_2024_v1`: bloque propio desde 2024, un año de
  historia; el portafolio es el control y la vista lo declara con `portafolio_igual_al_control`): arañas viuda negra,
  violinista y otras; abeja; avispa; otros artrópodos; otros animales ponzoñosos; serpientes de cascabel, coral y
  otras.

Ningún control se presenta como validado ni como «validación en curso». Los 86 padecimientos ya publicados no
cambiaron (releases, `artifact_source` y `acceptance_fallback_run` intactos; verificado por la auditoría Codex).

## Base semanal y paridad

Base semanal vigente: `planes/alta_b44_2026-11-19/consolidado_W44/dataset_boletin_epidemiologico.csv` (fuera del
repositorio), sha256 `819796694c1993e0012fc1cbb6dc489df2fdd3d4b0e43900f3af290c397468de`, 157,883,990 B. Se formó
sólo añadiendo filas: el consolidado previo de 86 en `2026-W44` (`0f6252f9…`, 92,155,130 B) es su prefijo byte a byte
(recomprobado el 20-nov-2026). Los 152 están en la semana fuente `2026-W44` (boletín 44); el periodo objetivo de cada
uno depende de su `observation_lag_weeks`. **El paso siguiente usa la semana fuente 45, una sola vez, para los 152.**

## Integradas sin pronóstico (32)

Por decisión del autor (`planes/alta_b44_2026-11-19/DECISIONES_AUTOR_14.json`), las 32 categorías de abajo se
integraron al sitio **sin pronóstico** (frontend PR #103, `main` `2d2c3ffe`, 20-nov-2026): el radar del boletín 44 las
marca «No modelable» con su motivo medido, `no_modelables.html` las lista con las cifras impresas del boletín y el
EpiBot y la función RAG responden por nombre y código con «sin pronóstico», motivo y cifras impresas. Sarampión y
P. falciparum se rotulan «casos insuficientes o no publicados»: el guion del cuadro estatal significa «no publicado» y
las notas del boletín reportan casos. Auditoría Codex `gpt-6.1-sol` (medium) de esa rama: 5 rondas corregidas,
veredicto final APTO sobre `1cde388a`. No se crearon pronósticos ni controles para ellas.

## Opción «Pronóstico» en el radar: cobertura 100 % (20-nov-2026)

Por orden del autor («quiero todos todos los padecimientos… que pueda darme el forecast»;
`planes/alta_b44_2026-11-19/DECISIONES_AUTOR_15.json`), el radar del boletín tiene una opción «Pronóstico» junto a la
serie para las 187 categorías no agregadas (frontend PR #104, `main` `7553966e`): 154 muestran su pronóstico
publicado (vista del release o serie legacy, con su etiqueta) y 33 un **pronóstico exploratorio, no validado**,
nacional de 52 semanas y generado offline (`scripts/radar_pronostico_exploratorio.mjs`): 28 con la media de la misma
semana de hasta tres años previos, 3 con nivel reciente sin estacionalidad y 2 (sarampión y P. falciparum) con un
nivel derivado del acumulado nacional impreso en las notas del boletín (`scripts/radar_notas_acumulados.mjs`, con
evidencia por boletín). No pasan por el runner, no tienen prueba de desempeño ni intervalos y no cuentan como
publicados. Auditoría Codex `gpt-6.1-sol` (medium): 4 rondas, APTO sobre `a37651e7`, más una verificación acotada del
cambio de redacción.

## Por qué no tienen pronóstico

El runner exige 32 entidades, casos, rezago impreso fijo o declarado por periodo, total no imputado en el año de
prueba y al menos un pliegue de desarrollo. Ninguna guarda se relajó. Siguen fuera:

- **Sin desglose estatal** (sólo resumen nacional): peste, difteria, poliomielitis, fiebre amarilla, fiebre por virus
  Mayaro, encefalitis equina venezolana y enfermedad por virus Ébola.
- **Sin casos** (acumulado 2025 y 2026 vacío o de tres o menos en el país): sarampión, rubéola, rubéola congénita,
  cólera, tifo epidémico, fiebre del oeste del Nilo, Zika, paludismo por P. falciparum, rabia humana silvestre y
  urbana, oncocercosis, leishmaniasis visceral, tétanos neonatal y meningoencefalitis amebiana primaria. La prueba
  única daría sMAPE 0/0 y un control que pronostica cero.
- **«Sem -1» impreso en 2025** (total imputado en el año de prueba): influenza y enfermedad febril exantemática.
- **Sin pliegues** (bloque propio desde 2025 o 2026): miasis, depleción del volumen, envenenamiento accidental por
  sustancias nocivas, contacto traumático con animales y plantas venenosas, exposición al humo y fuego, contacto con
  calor y sustancias calientes, asfixia, ahogamiento no mortal y quemaduras solares.
- **Agregado:** enfermedades infecciosas intestinales (sus componentes ya están publicados).

Sí entraron, con código nuevo y decisión del autor, categorías que el borrador inicial de exclusiones daba por
bloqueadas: las de **rezago impreso variable** (meningitis tuberculosa, tuberculosis respiratoria y otras formas,
lepra, fiebre manchada, otras rickettsiosis, leishmaniasis cutánea, meningocócica, Haemophilus, neumococo y ESAVI),
con el rezago declarado por periodo; **cirrosis alcohólica** con serie desde 2016; y **P. vivax**, con suma de sexos
desde 2021 y serie desde 2015. Evidencia: `planes/alta_b44_2026-11-19/EXCLUSIONES.md` (borrador inicial) y
`frag/c*/<id>.qa.md`.

## Código nuevo (todo opt-in por grupo, con no regresión demostrada)

- `une_renglones_parciales`: unión de renglones partidos por camelot, que rechaza las tablas ambiguas.
- `epi_lag_schedule`: rezago impreso declarado por periodo, en lugar de uno fijo por bloque.
- Reparación declarada de acumulados e `inicio_serie` por grupo.
- `correcciones_celda`: correcciones de celda declaradas (valor o imputación), que fallan cerradas si la celda
  extraída no coincide con lo esperado.
- `estadios_por_sexo` (VIH) y `suma_sexos` (P. vivax), validados contra el TOTAL impreso.
- Política `rolling_cv_historia_corta_2024_v1` y campo `portafolio_igual_al_control` en la vista.

Un grupo que no declara estas claves queda byte-idéntico (comparación independiente contra `origin/main` en la
auditoría, ronda 3).

## Decisiones del autor (registros JSON fuera del repositorio, `planes/alta_b44_2026-11-19/`)

| Archivo | Decisión | sha256 |
|---|---|---|
| `AUTORIZACION_AUTOR.json` | Alcance «Todas con datos», prueba de 2025 y política de cinco motores, control tras rechazo, sensibles incluidos, salud de menores como vigilancia normal | `c473df77…` |
| `DECISIONES_AUTOR_2.json` | Siete controles (rechazos de alta20c) | `0bbfe019…` |
| `DECISIONES_AUTOR_3.json` | Saltos de nivel modelados con aviso; cirrosis desde 2016; reparación declarada de alacrán | `a12bbb26…` |
| `DECISIONES_AUTOR_4.json` | Trece controles | `b31ab999…` |
| `DECISIONES_AUTOR_5.json` | Siete controles | `26012e64…` |
| `DECISIONES_AUTOR_6.json` | Siete controles | `ec4a63b0…` |
| `DECISIONES_AUTOR_7.json` | Embeddings en Google Gemini (sólo texto público) y publicación al cerrar | `5185b27d…` |
| `DECISIONES_AUTOR_8.json` | Control de VIH | `6b1f478d…` |
| `DECISIONES_AUTOR_9.json` | Tuberculosis respiratoria con aviso del pico 2019-2020; código de suma de sexos para P. vivax | `bf60195b…` |
| `DECISIONES_AUTOR_10.json` | Cinco controles | `65e393bb…` |
| `DECISIONES_AUTOR_11.json` | P. vivax desde 2015 con `inicio_serie` | `f3add314…` |
| `DECISIONES_AUTOR_12.json` | Control de P. vivax | `c778ada6…` |
| `DECISIONES_AUTOR_13.json` | Imputación del hueco 2017-W01 de P. vivax, con aviso en ficha | `fecbea91…` |

Categorías sensibles (autolesión, ideación, violencia, arma de fuego, alcohol, VIH): OK nominal del autor **sin
revisión clínica acreditada**. La respuesta de crisis (Línea de la Vida, 800 911 2000, sin cifras ni gráfica) vive en
el frontend.

## Auditorías independientes (Codex `gpt-6.1-sol`, esfuerzo medium)

- **Backend:** cinco rondas: tres NO_APTO, corregidas con pruebas que fallan con el código anterior; APTO en la cuarta
  sobre `3fce9c84` y, tras el código de P. vivax, veredicto final **APTO** sobre `ee0151f1`: 66 releases verificados contra sus manifiestos (9,414 archivos por
  SHA-256). Limitación declarada por el auditor: pruebas sintéticas en memoria, sin suite completa ni extracción real.
- **Frontend:** dieciocho rondas NO_APTO corregidas; veredicto final **APTO** sobre `5b76b1d9`. Sin verificar
  producción ni la generación remota con Gemini.
- Evidencia: `planes/alta_b44_2026-11-19/codex/`.

**Coste aceptado por el autor:** 41 de 616 casos funcionales del EpiBot (preguntas en primera persona plural o que
tutean al bot) reciben ahora la respuesta de apoyo en lugar de la cifra.

## Integración y cierre

- Backend PR #79 (`bdfd03bb`, CI de `main` 44667657252 en verde: Code Quality y Tests); frontend PR #102 (`4a9fdba1`),
  desplegado y verificado en vivo (148 releases, 152 padecimientos). Artefactos en DVC con `dvc push` (139 objetivos
  del lote en sincronía con el remoto, comprobado el 20-nov-2026).
- Runs, shards de publicación, releases y observaciones materializados en el checkout principal sin sobrescribir
  ninguno existente (49,898 archivos verificados por SHA-256; siete `dataset_manifest.json` previos de alta20c difieren
  sólo en `code_commit` y `created_at` y se conservó el de `main`). Inventario en
  `planes/alta_b44_2026-11-19/materializacion/` y evidencia única de los worktrees en `worktrees_evidencia/`.
- Ramas del lote retiradas; las integradas por cherry-pick quedan como etiquetas locales `archive/b44-*`.

## Pendientes

- Semana fuente 45 para los 152 juntos, cuando exista el boletín 45 (`references/paso_semanal.md` del skill).
- Las categorías de «Lo que no se integró» siguen fuera hasta que cambie su condición técnica (por ejemplo, un año de
  historia para las que empiezan en 2025).
- Revisión clínica y de comunicación de las categorías sensibles: no acreditada; el OK fue nominal del autor.
- Mantenimiento previo no bloqueante: O1 a O3 de `docs/DEUDAS_VIGENTES.md`.
