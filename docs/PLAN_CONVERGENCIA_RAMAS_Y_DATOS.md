# Auditoría de estado y plan de convergencia a una sola rama

> **HISTÓRICO, NO OPERATIVO.** Esta bitácora documenta la convergencia del 18-ago-2026.
> Sus ramas, estado prospectivo 1/4 y acciones siguientes quedaron superados. Consultar
> `docs/DEUDAS_VIGENTES.md`, `GEMINI.md` y el estado canónico actual antes de actuar.

> Fecha: 2026-08-18 · Repo principal en `feat/registry-padecimientos-obesidad` @ `cc4e8e01`
> · Dashboard en `feat/c73-candidate-staging` @ `a044403d`.
> Objetivo: una sola rama por repositorio, datos sincronizados y `make update-week` operativo.
>
> **ESTADO 2026-08-18: fases 0, 1, 2 y 3 EJECUTADAS; fase 5 parcial. Falta la fase 4.**
> Auditado de forma independiente el mismo día: la convergencia es válida y C7 permanece intacto,
> pero **el flujo semanal sigue siendo NO-GO**. Las correcciones de esa auditoría están incorporadas
> en la bitácora, marcadas como tales. Ambos repositorios tienen ya una única rama
> remota, `main`, con la integración continua en verde. Quedan pendientes la **fase 3** (reparar el
> flujo semanal) y la **fase 4** (publicar las semanas 28 a 30). Bitácora al final del documento.

---

## 1. Veredicto en una línea

No hay pérdida de datos ni corrupción: lo que hay es **una bifurcación de tres semanas que nadie
cerró**, más un flujo semanal escrito para una rama en la que ya no estamos. Se arregla en un orden
concreto. **Pero hay un riesgo latente que debe cerrarse primero**, en §3.

---

## 2. Estado verificado

### 2.1 Repositorio principal

```text
rama actual   feat/registry-padecimientos-obesidad @ cc4e8e01   (sincronizada con su remoto)
main          origin/main @ 48749a08                            (local desactualizado en 6)
base común    b535b525 · 2026-07-21
divergencia   137 commits solo en la feature · 6 commits solo en main
```

Los **6 commits de main son exclusivamente del scraper automatizado** y tocan tres archivos:
`dataset_boletin_epidemiologico.csv.dvc`, `raw_PDFs.dvc` y `data/registry.json`.

**Intersección de archivos tocados por ambos lados: vacía. El merge no tiene conflictos.**

### 2.2 Repositorio del dashboard

```text
rama actual   feat/c73-candidate-staging @ a044403d
main          origin/main @ 179bbe36 · 2026-07-22   ← ES LA RAMA QUE SIRVE EL SITIO
divergencia   23 commits solo en la feature · 0 en main
```

Los 23 commits son todos del carril C7 y se concentran en `epibot/` (pruebas, índice RAG,
instalador, estado de publicación). Como `main` no ha avanzado desde el 22 de julio, **el sitio
público lleva casi cuatro semanas congelado**.

### 2.3 Datos

```text
DVC cache ↔ remoto s3remote        EN SINCRONÍA
consolidado local                   hasta 2026-W30 (neuro) · W27 (dengue, obesidad)
sitio público                       2026-W27 · knowledge.json generado el 2026-07-21
outs con cambios locales            models · logs · data/raw · consolidado · figures · forecasts
```

### 2.4 Lo que **no** está roto

Conviene decirlo porque cambia el tamaño del problema:

- **El almacenamiento remoto está sano.** Todo lo versionado está en S3.
- **El merge no tiene conflictos.** Verificado por intersección de archivos.
- **El gate de publicación funciona por configuración, no por rama.** Obesidad está en
  `lifecycle: trained` con `gallery_enabled: false`, y anorexia en `configured` con `channels: []`.
  **Fusionar el código a main no publica ninguna de las dos.**
- **El carril C7 está aislado de los datos semanales por diseño.** `raw_path_for()` lee
  `data/raw/data_raw_Obesidad.csv`, **no** el consolidado. Actualizar el boletín cada semana **no
  puede mover** el digest de entrenamiento congelado.
- **La integración continua está verde** en la rama feature.

---

## 3. 🔴 El riesgo que hay que cerrar primero

**Tres archivos de datos existen únicamente en este disco y no están respaldados en ningún lado:**

```text
data/raw/data_raw_Obesidad.csv        1,035,106 bytes   insumo de entrenamiento de C7
data/raw/data_raw_Anorexia_F50.csv      863,239 bytes   demostración N+1
data/raw/data_raw_Dengue.csv            511,224 bytes   insumo del cuarto padecimiento
```

DVC los reporta como *added*: presentes en el árbol, ausentes del puntero versionado. **Cualquier
`dvc pull --force` sobre `data/raw.dvc` los borra**, y el flujo semanal ejecuta exactamente esa
orden en su paso 2. Es la bala que estuvo a punto de dispararse hoy.

Son regenerables desde los boletines en PDF y la extracción es determinista, así que la pérdida
sería de tiempo, no irreversible. Pero regenerar significa reprocesar 654 archivos y volver a
verificar digests. **No es aceptable dejarlo así una semana más.**

Lo mismo aplica, con menos gravedad, a `models/`, `reports/forecasts/` y el consolidado: tienen
cambios locales no versionados.

---

## 4. Por qué `make update-week` no puede correr hoy

El flujo fue escrito cuando el trabajo vivía en `main`. Hoy hay cuatro supuestos rotos:

| # | Paso | Supuesto roto | Consecuencia |
| --- | --- | --- | --- |
| 1 | `git pull origin main` | Que estamos en main | Inyecta un merge de main dentro de la rama feature auditada |
| 2 | `dvc pull --force` | Que no hay trabajo local sin versionar | **Borra los tres CSV de §3** |
| 3 | `dvc add` + `dvc push` del consolidado | Que el consolidado es solo neuro y dengue | Publica también las filas de obesidad, sin decidirlo |
| 4 | `git add/commit/push` en el dashboard | Que el dashboard está en main | **Publica en la rama feature, que Netlify no sirve: el sitio no cambiaría** |

El paso 4 es el más engañoso: el flujo terminaría anunciando éxito y el sitio seguiría en W27.

> **Sobre "el otro script":** solo existe `scripts/actualiza_semanal.sh`. Lo que probablemente
> recuerdas es el flujo anterior `make data-weekly PDF=…` (`data-add` + `data-commit`), que agrega un
> boletín suelto y sigue en el Makefile. Fue reemplazado por `update-week`, que unifica los once
> pasos. El **carril paralelo** que sí existe es `make prospective-week`, pero pertenece a C7,
> es deliberadamente aislado y **solo aplica a obesidad**: no actualiza neuro ni dengue ni publica.

---

## 5. La decisión de fondo

Todo depende de una sola pregunta: **¿el código de C7 se integra a `main`?**

**Recomiendo que sí, y con cierta urgencia.** Argumentos:

1. **La rama no es lo que protege.** Lo que mantiene invisibles a obesidad y anorexia es el gate de
   lifecycle, que es configuración y viaja con el código. Integrar no publica nada. Está verificado
   en §2.4.
2. **La divergencia se encarece sola.** Van 137 commits y tres semanas. `main` recibe datos cada
   lunes por su cuenta, así que la brecha crece aunque nadie trabaje.
3. **El flujo semanal está bloqueado mientras dure la bifurcación**, y con él la publicación del
   sitio. Ya cuesta cuatro semanas de atraso público.
4. **La integración continua está verde** y el merge no tiene conflictos. Nunca va a ser más barato.

**Riesgo real de integrar:** el plan de C7 reserva el merge a una autorización explícita, y la
verificación prospectiva de obesidad está en 1 de 4 semanas. Integrar el **código** no adelanta esa
verificación ni publica el padecimiento, pero sí significa que `main` deja de ser el estado
"pre-C7". Si algo de C7 resultara defectuoso, revertir en `main` es más ruidoso que abandonar una
rama.

**Alternativa si prefieres no integrar todavía (opción B):** traer `main` **hacia** la feature,
reparar el flujo semanal para que publique en el `main` del dashboard, y operar desde la feature.
Desbloquea el sitio sin decidir sobre C7. Cuesta que la bifurcación siga creciendo y que la decisión
regrese en unas semanas, más cara.

---

## 6. Plan

### Fase 0 — Asegurar lo insustituible ⚠️ **antes de cualquier otra cosa**

1. Copiar los tres CSV de §3 fuera del árbol, a un respaldo fechado.
2. Decidir si se versionan en DVC. Recomendado: sí para dengue (es productivo); obesidad y anorexia
   pueden quedarse como respaldo local mientras el carril siga siendo NO-GO.
3. Verificar que el respaldo abre y tiene el número de filas esperado.

*Sin operaciones de red. Reversible. Es la única fase que sostengo que no debe posponerse.*

### Fase 1 — Unificar el repositorio principal

1. Traer `origin/main` a la feature. Sin conflictos previstos; se confirma antes de confirmar el merge.
2. Verificar que nada de C7 se movió: digests de dataset y de gate, lifecycle, agregados legacy.
3. Ejecutar la batería completa de calidad y pruebas.
4. Integrar la feature a `main` mediante solicitud de cambios, esperando la integración continua.
5. `main` queda como única rama de trabajo.

### Fase 2 — Unificar el dashboard

1. Mismo patrón con los 23 commits.
2. **Verificación obligatoria antes de publicar:** que el sitio construido no exponga obesidad ni
   anorexia por ninguna ruta.
3. Confirmar en vivo que Netlify publicó desde `main`.

### Fase 3 — Reparar el flujo semanal

Cuatro correcciones, una por supuesto roto:

1. Detectar la rama actual en lugar de asumir `main`, y **abortar** si no es la esperada.
2. Sustituir `dvc pull --force` por una descarga selectiva y no destructiva, con un **guard que
   aborte si hay archivos locales sin versionar** en la ruta de destino. Este guard es la lección
   de §3 convertida en código.
3. Que el paso de versionado declare explícitamente qué padecimientos entran al consolidado.
4. Que el paso de publicación verifique que el dashboard está en la rama que sirve el sitio, y
   aborte si no.

Se prueba con una corrida en seco antes de cualquier corrida real.

### Fase 4 — Publicar el atraso

1. Correr el flujo ya reparado para las semanas 28, 29 y 30.
2. Actualizar dengue, que sigue en W27 y necesita los PDF nuevos.
3. Verificar **en vivo** con una consulta al sitio, no solo en local.

### Fase 5 — Higiene

Cuatro ramas locales sobreviven a repositorios que ya no las tienen: `Fork/aws-training-comparison-R5KGp`,
`claude/aws-training-comparison-R5KGp`, `refactor/mlops-structure` y `chore/patent-bundle-mechanical-fixes`.
Se borran tras confirmar que no guardan trabajo único.

---

## 7. Orden e interacción con CALASS

Faltan nueve días para el congreso y la presentación es el compromiso con fecha externa.

- **La Fase 0 se hace ya**: son minutos y elimina el único riesgo de pérdida.
- **Las fases 1 a 4 no bloquean la presentación.** Las cifras ya están congeladas en
  `Congresos/CALASS2026/CIFRAS_VERIFICADAS.md` y no dependen de publicar el sitio.
- La única intersección real es que **el sitio muestra W27 mientras la presentación habla de W30**.
  Se resuelve publicando (fases 1 a 4) o no dependiendo del sitio en la sala.

**Recomendación:** Fase 0 hoy. Fases 1 a 4 en un bloque dedicado, no intercaladas con la
presentación, porque tocan publicación en vivo y merecen atención completa.


---

## 8. Bitácora de ejecución — 2026-08-18

### Fase 0 · asegurar lo insustituible — **hecha**

Respaldo en `_backups/2026-08-18_pre-merge-main/`, verificado byte a byte contra los originales.
El digest de anorexia (`2a7bb815…`) coincide con el documentado en CLAUDE.md, lo que confirma que
es la extracción determinista ya validada.

### Fase 1 · unificar el repositorio principal — **hecha**

```text
merge origin/main -> feature      sin conflictos, tres archivos
estado C7 antes vs después        diff vacío · ver la precisión abajo
prospective_status --check        rc=0 · 1/4 semanas · verdad observada intacta
lint · typecheck                  PASS
test-fast                         2,353 passed · 1 skipped · 62 deselected
main                              fast-forward a a6acf301, publicado
```

**Precisión sobre la comparación de C7 (auditoría del 2026-08-18):** reporté "48 digests sin
cambios". La cifra mezclaba tres secciones de un mismo volcado: digests de artefactos, líneas de
lifecycle y agregados legacy; y la captura usaba `head -30`, de modo que cubrió **30 de los 35**
digests existentes. El diff salió vacío sobre lo comparado, y el chequeo prospectivo con rc=0 y los
hashes congelados corroboran materialmente que C7 no cambió, pero **la afirmación era más amplia que
la evidencia**. La línea base completa de los 35, con el comando que la reproduce, quedó persistida
en `_backups/2026-08-18_pre-merge-main/c7_digests_linea_base.txt`.

### Fase 2 · unificar el dashboard — **hecha**

```text
menciones en lo servido               5 de obesidad + 1 de anorexia; listas de "NO modelado" y un comentario
npm test                              67/67
main                                  fast-forward a a044403d, publicado
sitio en vivo                         landing, epibot y knowledge.json responden 200
obesidad en el sitio                  0 menciones
```

### Incidente · integración continua roja tras el primer envío, **resuelto**

El typecheck falló en `main` con 14 errores en cinco archivos, **ninguno provocado por un cambio de
código**. El flujo instala con `pip install -e ".[dev]"` sin fijar versiones y trajo mypy 1.20.2,
numpy 2.5.2 y prophet 1.4.0, posteriores a las locales (1.19.1, 2.4.6, 1.3.0). Prophet 1.4 declara
sus parámetros como `Literal`, así que pasar una cadena leída de configuración pasa a ser error; y
numpy 2.5 con mypy 1.20 endurecen los operandos de union sobre `ExtensionArray`.

Se fijaron las tres por debajo de esas versiones, siguiendo el precedente de `ruff`. **La razón no
es solo el typecheck:** los 435 artefactos serializados en producción se generaron con prophet 1.3.x
y numpy 2.4.x, de modo que permitir versiones futuras arbitrarias era un riesgo de reproducibilidad
que nadie había declarado. Es el mismo patrón que rompió el flujo en junio.

**Deuda registrada:** adaptar el código a las firmas nuevas para poder levantar los techos.

```text
CI tras el arreglo    Code Quality 4m37s PASS · Tests 5m02s PASS
```

**Matiz sobre el alcance del verde remoto:** en un clon limpio la integración continua ejecuta
**1,825 pruebas y omite 529** que dependen de artefactos locales bajo `runs/` y `releases/`, con
cobertura del 74.11 %. El gate local con artefactos presentes sí selecciona las 2,353 esperadas.
**Verde remoto no equivale a gate local completo**, y ninguno de los dos sustituye al otro.

### Fase 5 · higiene — **hecha en parte**

Se borraron, tras verificar que `main` las contenía por completo, las dos ramas de trabajo
(`feat/registry-padecimientos-obesidad` y `feat/c73-candidate-staging`) en local y en remoto, y
`chore/patent-bundle-mechanical-fixes`, que no tenía ningún commit propio.

**Ambos repositorios tienen ahora una única rama remota: `main`.**

Quedan tres ramas **solo locales**, de febrero, presumibles residuos del reescrito de historial de
junio: `Fork/aws-training-comparison-R5KGp`, `claude/aws-training-comparison-R5KGp` y
`refactor/mlops-structure`.

**Corrección (auditoría del 2026-08-18):** afirmé que sus commits eran los mismos cambios con otro
identificador. **Eso no está demostrado.** `git cherry` marca **11, 11 y 19 parches sin equivalencia
exacta en `main`**. Pueden estar absorbidos por combinaciones de commits o por versiones
posteriores, pero mientras no se demuestre parche por parche, **no se borran**. Quedan como están.

### Hallazgo adicional · el scraper falló hoy

La ejecución programada `Scrape Boletines SINAVE` de hoy terminó en fallo.

**Corrección (auditoría del 2026-08-18):** dije que por eso "no existe" una semana 31. **Sí existe.**
El scraper la localizó y falló al descargarla:

```text
Descargando: https://www.gob.mx/cms/uploads/attachment/file/1098440/sem31.pdf
requests.exceptions.HTTPError: 403 Client Error: Forbidden
```

El diagnóstico correcto no es ausencia de publicación sino **denegación en la descarga**, coherente
con el muro anti-robot de gob.mx ya documentado. Incorporar la W31 exige reparar la descarga; las
semanas 28 a 30 no dependen de ello.

### Estado al cierre

```text
principal    main @ cdb72853   CI verde
dashboard    main @ a044403d   sitio sano, obesidad invisible
datos        boletín neuro hasta 2026-W30 · dengue y obesidad en W27
C7           intacto · obesidad trained · prospectiva 1/4
sitio        sigue mostrando W27: falta la fase 4
```


---

## 9. Auditoría independiente — 2026-08-18

Revisión de solo lectura sobre lo ejecutado. **Veredicto: la convergencia es válida y C7 permanece
intacto; el flujo semanal sigue siendo NO-GO y `make update-week` no debe ejecutarse hasta cerrar
la fase 3.**

### Correcciones incorporadas

| # | Afirmación previa | Corrección |
| --- | --- | --- |
| 3 | Los commits de las tres ramas locales son los mismos con otro identificador | **No demostrado.** `git cherry` marca 11, 11 y 19 parches sin equivalencia. No se borran |
| 4 | "CI verde" | El clon limpio corre **1,825 pruebas y omite 529** dependientes de artefactos locales; cobertura 74.11 %. Verde remoto ≠ gate local |
| 5 | "48 digests sin cambios" | Mezclaba tres secciones y truncaba a 30 de 35. Línea base completa ya persistida |
| 6 | 6 menciones de obesidad en `kb.js` | **5** de obesidad y 1 de anorexia |
| 7 | El fallo del scraper explica que "no exista" la W31 | **Sí existe**; la descarga devuelve **403 Forbidden** |

Ninguna altera el veredicto: C7 no se movió y el sitio no expone obesidad. Corrigen el alcance de lo
que quedó afirmado por escrito.

### Confirmaciones de la auditoría

```text
backend / dashboard      main, idénticos a origin/main · una sola rama remota en ambos
merge 20fc1b96           contiene cc4e8e01 y el antiguo main 48749a08, sin conflictos
respaldos                los cuatro coinciden byte a byte con los originales
C7                       trained · gallery false · sin puntero activo · rc=0 · 1/4
                         gate_digest 5bc39aa5… · release y observación en s3remote
legacy                   cb5be395 · 96791595 · 1d2cf0a7 · ac97dc8e
dashboard                npm run check PASS · 616/616 · 67/67 · RAG 454/454
sitio                    200 en landing, epibot y knowledge.json · cero obesidad · sigue en W27
```

### Riesgos vigentes

1. **`actualiza_semanal.sh` sin reparar:** conserva `dvc pull --force`, versiona y publica el
   consolidado completo junto con `models` y `reports/forecasts`, hace envíos directos en ambos
   repositorios y **carece de modo en seco y de comprobaciones efectivas de rama y árbol**. Que hoy
   ambos repos estén en `main` desactiva dos de los supuestos rotos **por circunstancia, no porque
   el script los verifique**.
2. **DVC no está globalmente verde:** siete objetivos con modificaciones (`models`, `logs`,
   `data/raw`, `data/raw_PDFs`, consolidado, `reports/figures`, `reports/forecasts`). Los tres CSV
   respaldados siguen fuera del puntero y **un pull forzado puede retirarlos**.

### Orden de reanudación

1. **Fase 3** — reparar el flujo semanal.
2. **Corrida en seco** verificable.
3. **Fases 28 a 30** — publicar el atraso.
4. **W31** — solo tras reparar la descarga bloqueada con 403.

C7 permanece congelado en 1/4 durante todo lo anterior.


---

## 10. Fase 3 · ejecutada — 2026-08-18

### 3a · scraper

Causa aislada y corregida: gob.mx responde 403 al User-Agent por defecto de `requests`.
Selenium ya navegaba con uno de navegador y por eso encontraba el boletín; la descarga
directa no, así que lo localizaba y moría al pedirlo. El agente pasa a ser una constante
única compartida. La descarga es ahora atómica (temporal contiguo, renombrado solo al
validar), exige la firma `%PDF-` y un tamaño mínimo, y no deja residuos ni al fallar.

Verificado contra el boletín real: **2,492,888 bytes, sha256 `4657affc…`**. Diez pruebas
nuevas; se omiten donde no está el extra `scraping`.

### 3b · flujo semanal

El modo predeterminado pasa a ser **en seco**: prepara, calcula y escribe un manifiesto
de lo que cambiaría, sin versionar ni publicar. Publicar es un comando aparte,
`make update-week-apply`.

El preflight aborta antes de tocar nada si algún repositorio no está en la rama que sirve
el sitio, si hay cambios rastreados sin confirmar, si falta upstream, si hay archivos sin
versionar en las rutas que sus descargas retirarían, o —solo al publicar— si el
consolidado trae padecimientos fuera de la lista autorizada sin declarar
`ALLOW_EXTRA_DISEASES=1`. Las descargas son dirigidas y sin forzar, el `git pull` es
`--ff-only`, y se quitaron los `|| true` de las operaciones críticas.

**Dos ajustes salidos de probarlo en ejecución, no de escribirlo:**

1. El guard abortaba por los CSV de `data/raw/`, ruta que el flujo rediseñado **ya no
   descarga**. Bloquear por un riesgo que el propio rediseño eliminó convierte al guard en
   algo que la gente aprende a saltarse. Ahora aborta por lo que sus descargas pueden
   retirar y **avisa** del resto: 793 archivos, de los cuales **790 son artefactos de
   modelos de obesidad sin versionar ni respaldar**, un riesgo mayor que los tres CSV que
   ya se respaldaron y que conviene resolver aparte.
2. La lista de padecimientos bloqueaba también en seco, cuando solo concierne al
   versionado.

### 3c · sincronización del consolidado, pieza que faltaba

`dvc pull` se negaba a bajar el consolidado y **tenía razón**: el archivo local es una
superposición de lo versionado y de filas que solo existen en este disco. La orden que
"arregla" ese error es `--force`, y lo que hace es borrar el trabajo local.

`scripts/sincroniza_consolidado.py` hace lo contrario: trae la versión versionada a un
temporal, exige que las filas compartidas coincidan y agrega solo las que faltan. Si una
fila ya existente cambió de valor, se detiene: eso es una corrección de la fuente, no una
semana nueva, y no le toca decidirlo a un script que corre solo. Ocho pruebas.

### Corrida en seco completa

```text
preflight              PASS · avisos legibles
consolidado            fusión aditiva, obesidad preservada
dengue                 avanzó W27 -> W30 por sí solo
neuro                  W30
artefactos             galería, zoom, knowledge, índice y novedades regenerados
publicado              NADA
manifiesto             runs/_refresh/refresh_20260818_184029.txt
```

### Hallazgo colateral · un golden que medía datos

`test_seleccion_productiva_legacy_congelada` congelaba `(disease, entidad, sexo, motor)`.
El motor se re-selecciona con cada boletín, así que el hash cambiaba cada semana sin que
nadie tocara el código: al incorporar las semanas 28 a 30 las 432 series quedaron
idénticas en estructura y solo se movió la asignación.

Se separó en dos: se congela la **estructura** (lo que un refactor del selector no puede
cambiar) y se comprueba que cada motor pertenezca al conjunto válido de su cohorte. Lo
segundo atrapa además un error que el hash no distinguía, porque un hash distinto no
decía si el cambio era legítimo: asignar a dengue un motor de árboles, excluido por no
extrapolar.

### Estado al cierre de la fase 3

```text
suite                  2,372 pruebas · lint y typecheck PASS
flujo semanal          OPERATIVO en seco; publicar sigue siendo un paso aparte
pendiente              fase 4: correr --apply y verificar el sitio en vivo
                       (requiere ALLOW_EXTRA_DISEASES=1 mientras obesidad esté en el consolidado)
```


---

## 11. Auditoría NO-GO de la fase 4 y su remediación — 2026-08-18

**Veredicto acatado: NO-GO.** No se ejecutó `--apply`, ni `--allow-dirty`, ni
`ALLOW_EXTRA_DISEASES=1`, ni ninguna operación DVC global.

### El bloqueante que importaba

El knowledge.json **preparado para publicar** contenía los casos históricos reales de
obesidad (2,719,585 hombres · 4,884,368 mujeres · 7,603,953) bajo `stats.demo_historica`.
El roster sí filtraba por lifecycle; la demografía se calculaba sobre todo el consolidado.

**Por qué no lo detecté:** verifiqué "cero obesidad" contra el sitio **ya desplegado**, que
no tenía el archivo nuevo, en vez de contra el artefacto **que se iba a desplegar**. El
gate del dashboard sí lo vio. Es la diferencia entre comprobar lo que hay publicado y
comprobar lo que se va a publicar, y solo la segunda protege de algo.

### Estado de los siete bloqueantes

| # | Bloqueante | Estado |
| --- | --- | --- |
| 1 | Obesidad filtrada al knowledge público | **Cerrado.** Filtro desde el registry, no lista a mano. Cuatro pruebas, incluida una sobre el artefacto del dashboard |
| 2 | Dry-run y apply incompatibles; manifiesto sin sellar | **ABIERTO.** Es el que falta para reabrir la fase 4 |
| 3 | Apply arrastraría los 790 artefactos WIP | **Cerrado.** Versionado acotado al consolidado; los 790 respaldados con manifiesto SHA256 |
| 4 | Publicación partida (dashboard primero) | **Cerrado.** Orden invertido: almacenamiento y backend primero, dashboard al final |
| 5 | CI no cubría las pruebas del scraper | **Cerrado.** Los jobs de pruebas instalan el extra `scraping`; las diez corren |
| 6 | Escritura no atómica del consolidado | **Cerrado.** Temporal contiguo y renombrado, con prueba |
| 7 | Afirmación falsa sobre el índice RAG | **Corregido y convertido en gate.** Ver abajo |

### Sobre el índice RAG

Mi reporte decía que se había regenerado; no era cierto. Además, comprobado con el
knowledge.json anterior de `main`, **el gate ya fallaba antes de este refresh**: la
desincronización es previa, el refresh la agrava. El dashboard no tiene integración
continua, y por eso pasó inadvertida.

El flujo no puede regenerarlo solo porque `rag:build` necesita una credencial externa, así
que ahora **comprueba y se niega a publicar** si el índice no corresponde al corpus.
Publicar así deja al asistente respondiendo desde un corpus que ya no existe.

### Lo que falta para reabrir la fase 4

1. **Staging sellado** (bloqueante 2): que el dry-run produzca un manifiesto con HEAD y
   digests, y que `apply` consuma exactamente ese staging en vez de reejecutar el
   preflight sobre un árbol que él mismo ensució.
2. **Regenerar el índice RAG** con la credencial, y `npm run check` completamente verde.
3. **Dry-run en clon limpio** con el gate completo: roster 432, dengue 99, cero obesidad
   y anorexia en superficies públicas, cero cambios DVC en modelos y agregados
   congelados, W31 incorporada.
4. Solo entonces publicar, y hacer prueba de humo en vivo.

C7 sigue en **1/4** y no se toca hasta que lo anterior esté cerrado.


---

## 12. Fase 1 cerrada · staging sellado integrado y validado — 2026-08-18

### Lo que cambió

El módulo del sello existía pero no gobernaba nada. Ahora el flujo **solo prepara y
sella**: siembra el staging clonando el destino (varios generadores leen lo que ya
existe), redirige a él todos los generadores —incluidos los de dengue, que apuntaban al
sitio por variables del Makefile— y al terminar retira lo que no cambió, para que el
inventario diga qué cambió esta semana en vez de repetir los casi dos mil archivos del
sitio. En APFS la siembra usa `clonefile`: instantánea y sin duplicar espacio.

**El guion ya no contiene ninguna operación de publicación:** cero `git push`, cero
`dvc push`, cero `dvc add`. Instalar es `make update-week-apply MANIFEST=…`, que exige
el manifiesto explícitamente, verifica HEAD, inventario y digest de cada artefacto, y
copia esos bytes sin regenerar.

**Excepción declarada:** el consolidado sí se actualiza en su ruta canónica, porque es
la entrada de la que leen todos los generadores y no un artefacto publicable. Su digest
queda sellado en el manifiesto.

### Recuperación ante fallo a mitad de los renombrados

Cada publicación aparta el archivo previo y recuerda con qué lo reemplazó; un fallo
deshace en orden inverso todo lo ya publicado. **La prueba destapó un defecto que no
había previsto:** el registro se anotaba después de ambos renombrados, así que el hueco
entre apartar y publicar quedaba sin registrar y el destino perdía una versión que sí
existía. El registro se adelantó.

### Corrida real contra clon limpio

```text
staging sellado    709b400e874feff6 · 1,794 artefactos
sitio de trabajo   CERO archivos tocados
clon limpio        cero cambios durante la preparación
instalación        1,794 artefactos · sin residuos · idempotente
knowledge          2026-W30 · cero obesidad · IDÉNTICO byte a byte al sellado
suite              2,397 pruebas · lint y typecheck PASS
```

### Dos ajustes salidos de la corrida

1. El preflight leía la ruta del dashboard antes de definirla, porque esa variable pasó
   a apuntar al staging. Ahora inspecciona el repositorio real y la generación escribe
   en el staging.
2. El preflight abortaba si un repositorio no estaba en `main`. Eso protegía la
   publicación, que este guion ya no hace, y el gate en clon limpio se corre justamente
   sobre worktrees en HEAD suelto. Pasa a informar; **quien publica es el apply**, y allí
   la comprobación es más fuerte que la rama: exige que el HEAD sea el sellado.

### Siguiente

W31 (aún no está en la ruta canónica) → regenerar el índice RAG con la credencial →
gate en clon limpio → checkpoint humano → publicación → smoke. C7 sigue en 1/4.
