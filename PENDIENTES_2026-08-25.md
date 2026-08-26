# Pendientes al 25 de agosto de 2026

> Un solo lugar para lo que quedó abierto en los dos carriles de estos días: la
> presentación de CALASS y el arreglo de las cifras públicas. Nada de esto bloquea al otro.
>
> Estado de fondo: **el mazo está cerrado y listo para proyectarse**; el arreglo de las cifras
> está **mergeado y en producción desde el 25-ago**.
>
> **Corregido el 25-ago tras la auditoría externa:** este documento se commiteó a `main` con su
> texto anterior, que ya era falso — decía que producción respondía 435 y que había tres PR en
> borrador. Los seis PR del Dashboard y los tres de MX están mergeados.

---

## 1. CALASS 2026 · lo que no depende de la máquina

El congreso es el **27-29 de agosto**; la sesión 4.1, el jueves 27 a las 11:30.
Paquete vigente: `Congresos/CALASS2026/USB/` — 15 láminas, guion de 14.5 min.

| # | Pendiente | De quién |
| --- | --- | --- |
| 1 | **Dos ensayos cronometrados bajo 15:00.** El margen de 31 s es teórico. Atención a los dos traspasos de voz: láminas **5 y 11**. | Ruth y Javier |
| 2 | **Escanear el QR con un teléfono real.** Se decodifica desde el PNG y desde las dos láminas renderizadas, pero nadie lo ha apuntado con una cámara. | quien viaje |
| 3 | **Dos memorias USB**, no una, más copia en la nube. | quien viaje |
| 4 | **Confirmar con el comité que la proyección es 16:9.** El PDF está en ese formato exacto. | comité |

### Deuda de diseño que se dejó fuera a propósito

- **La lámina 9 sigue oscura fuera del bloque 4-7.** El sistema visual pedía un solo bloque
  oscuro; ponerla en claro exige reconstruir esa figura desde los datos. Es un salto de
  ritmo, no un error.
- **La captura del tablero (lámina 4) conserva el panel derecho truncado**, por el
  responsive de la propia aplicación al viewport en que se tomó.
- **En la lámina 5, en letra pequeña**, sobreviven la columna `CONFIANZA` con porcentajes y
  la frase «posición #28 de **37 entidades**», que debería decir *geografías* (32 entidades
  + 4 regiones + nacional). **Se corrige en el producto, no en la imagen.**

---

## 2. Dashboard · desplegado

**Producción dice 432.** Verificado contra el sitio en vivo: la portada, el EpiBot y
`knowledge.json` están dentro del contrato, y una auditoría externa lo confirmó de forma
independiente el 25-ago.

| # | Qué hizo | Estado |
| --- | --- | --- |
| #1 | 435 → 432 en toda la superficie pública | mergeado |
| #2 | las vistas dejan de enseñar «Nuevo Leon» | mergeado |
| #3 | ignora los 6 MB que un `add -A` barrería | mergeado |
| #4 | las diez vistas apuntan al workbook propio de Tableau | mergeado |
| #5 | la fecha de actualización decía marzo | mergeado |
| #6 | README al día | mergeado |

En MX el hotfix vive en `hotfix/cifras-432` ([PR #3 de MX](https://github.com/EpiForecastMX/EpiForecast-MX/pull/3)).
Contrato normativo: `docs/CONTRATO_VOCABULARIO_CIFRAS.md`.

### El número de caché (resuelto)

Se mergearon las dos ramas **antes** de desplegar, así que `app.js?v=137` cubrió ambos cambios.
Producción sirve v137, verificado. La nota original se conserva abajo porque el razonamiento
sigue valiendo para el próximo despliegue.

### ⚠️ La trampa, para la próxima vez: el número de caché

`hotfix/cifras-432` y `fix/ortografia-entidades` **salen las dos de `main` (v136) y las dos
dejan `app.js?v=137`**. Git no marca conflicto —es el mismo cambio textual—, así que el
riesgo es silencioso: si se despliega el hotfix a v137 y **después** se mergea la
ortografía, el número ya no sube y los navegadores con v137 en caché **no vuelven a pedir
`app.js`**.

**Mergear las dos antes de desplegar** (v137 cubre ambas), o **subir a 138 antes del
segundo despliegue**. Producción no se ha desplegado nunca con v137: la vía limpia sigue
abierta.

### Lo que falta decidir

1. ~~¿Se promueven a producción?~~ **Hecho el 25-ago**, autorizado por el usuario.
2. ~~El árbol sucio de `paper/micai-2026-camera-ready`.~~ **Resuelto el 25-ago**: se verificó
   archivo por archivo, se rescataron los dos únicos que eran trabajo real (`build_tableau.py`
   con `fecha_boletin`, y `empaqueta_envio.py`) y la rama se mergeó a `main` en el PR #6.
3. **El gate de cifras sólo mira `knowledge.json`.** Hallazgo de la auditoría externa del
   25-ago: `epibot/scripts/cifras_verify.mjs` abre ese archivo y ninguno más, así que **no puede
   atrapar un 435 reintroducido en `index.html`, `bento.json` o `EpiDashboard.html`**, que son
   las superficies que ve el público. El contrato se cumple hoy, pero no está defendido.
   Ampliarlo es tarea posterior al congreso.
4. **Nota histórica del árbol sucio (se conserva el razonamiento).** **Corrección importante: la
   versión anterior de esta nota decía que los nueve archivos estaban duplicados y que se
   limpiaran con `git checkout --`. Se verificó archivo por archivo y no era exacto.** De
   los nueve, sólo cuatro son idénticos al hotfix; los otros cinco difieren —aunque **sólo
   en el salto de línea final**, así que el trabajo sí está salvado en `hotfix/cifras-432`.
   Aun así **no se limpiaron**, por dos razones:
   - `catalogo_canonico.csv` y `catalogo_canonico_counts.json` son **artefactos generados**;
     restaurar la versión de la rama del paper dejaría en disco un **manifiesto rancio**,
     que es justo lo que la prueba `test_manifiesto_en_disco_no_esta_rancio` existe para
     atrapar.
   - `scripts/build_tableau.py` y `scripts/paper_micai_2026/empaqueta_envio.py` **no están
     salvados en ninguna rama**: son trabajo previo de otra ronda. Tocarlos sería perderlo.

### Mejoras identificadas y no hechas

- **`cifras:verify && rag:ci` cortocircuita.** Si falla el primero, Netlify solo reporta ese
  fallo. Bloquea correctamente el despliegue, pero conviene un runner que acumule códigos.
- **`_fixCohortStats` (`epibot/js/kb.js`) quedó redundante**, no dañina. Retirarla es tarea
  posterior al congreso, y **sólo tras comprobar que produce exactamente lo mismo**.
- **`bento.json` sigue siendo un snapshot de junio** presentado con un punto verde de «en
  vivo». Regenerarlo exige un generador que no existe.
- **El comparador enseña «Depresión · ?»**: el motor viene vacío por esa vía de datos.
- **Las tildes de las entidades siguen ausentes en los datos** (`knowledge.json` guarda
  «Nuevo Leon» y seis más). Es correcto —son claves— pero conviene que el generador emita
  además un campo de presentación, para no depender de un mapa en el frontend.

## 3. Lo que sigue abierto de antes, y no se tocó estos días

- **Autoría del programa.** La portada lleva 7 autores y 4 afiliaciones; la sumisión
  registrada tiene 6 y 3. Se decidió que **los 7 son correctos** y la portada se queda, pero
  el programa del congreso imprimirá lo registrado. Nadie ha escrito al comité.
- **Tableau Public sigue sin cerrarse.** Los borradores locales no deben publicarse. Memoria
  del carril: `docs/ESTADO_TABLEAU_W31_2026-08-20.md`.
- **MICAI 2026**: entregado el 23-ago; falta el registro de un autor.
