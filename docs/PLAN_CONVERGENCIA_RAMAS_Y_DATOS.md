# Auditoría de estado y plan de convergencia a una sola rama

> Fecha: 2026-08-18 · Repo principal en `feat/registry-padecimientos-obesidad` @ `cc4e8e01`
> · Dashboard en `feat/c73-candidate-staging` @ `a044403d`.
> Objetivo: una sola rama por repositorio, datos sincronizados y `make update-week` operativo.
> Este documento es diagnóstico y plan. **No autoriza ejecutar nada.**

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
