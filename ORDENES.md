## Orden vigente del autor: cierre sincronizado en main (5-nov-2026)

El autor ordenó: «no dejar nada en ramas, todo siempre sincronizado». Aplica a
EpiForecast-MX y EpiForecast-IMSS-Dashboard y prevalece sobre recetas históricas
que terminaban dejando el checkout en una rama de trabajo.

- Las ramas y worktrees de desarrollo son temporales. El trabajo terminado debe
  quedar integrado en `main` y enviado a `origin/main`; ambos checkouts principales
  deben terminar en `main`, sin cambios pendientes de la tarea y sin divergencia.
- Antes de integrar, inventariar ramas, worktrees, stashes y cambios locales.
  Respaldar y verificar por hash los cambios ajenos; resolver los conflictos sin
  descartarlos. Nunca usar `reset --hard`, `clean`, force-push ni borrar trabajo
  único para aparentar sincronización. Un stash o una etiqueta de respaldo no
  equivalen a integración ni a cierre.
- Tras integrar y verificar CI, retirar las ramas locales y remotas ya contenidas
  en `main` y los worktrees temporales propios; conservar antes sus runs y evidencia.
  Las ramas con commits únicos requieren revisión e integración; no se borran ni
  se fusionan a ciegas. No abandonar silenciosamente cambios ajenos pendientes.
- Verificar con red `fetch --prune`, `HEAD == main == origin/main`, el SHA real de
  `refs/heads/main` en origin, estado del árbol, ramas restantes y CI del SHA final.
  Comprobar backend y frontend como un par; el despliegue público requiere además
  comprobar la versión servida. No confundir una referencia remota local con red.
- Si falta red, acceso o una decisión sobre cambios ajenos, el cierre queda
  bloqueado con el motivo y los pendientes exactos. No afirmar «todo sincronizado»
  ni «cerrado» por tener una PR fusionada o por conservar una copia en /tmp.
- La sincronización no autoriza reentrenar, reabrir 2025, cambiar criterios de
  aceptación, publicar otro padecimiento ni modificar artefactos sellados.

# Órdenes a la mano

## Checkpoint OnePlus — 20-sep-2026

No usar el ZIP histórico `PLOS_build/latex.zip` (8-jul). Para revisión visual subir a
Overleaf `PLOS_build/envio_2026-09-18/manuscrito_plos_2026-09-18_OVERLEAF_PREVIEW.zip`
(manuscrito actual + cinco PNG). Para Editorial Manager usar su ZIP hermano
`manuscrito_plos_2026-09-18_PLOS_SUBMISSION.zip` (captions sin figuras); ambos están
sellados dentro del manifiesto A+B reemitido `c51b5f55…`. Validar primero la compilación
y las cinco figuras en Overleaf; no reemplazar los PDF históricos sellados.

Estado científico: C, D y A+B ampliada cerradas. Titulares: 288 estatales, sMAPE 53.2,
MASE 0.387, 267/288 (92.7 %); 333 sólo es cobertura. Pendientes humanos: revisión de
coautoras, traducción/versión de envío y autorización de envío. Pendiente técnico crítico
para el bot: reparar `scripts/build_tableau.py:134-138`, que mezcla banda DeepAR con
puntos de otros motores. No ejecutar W23 etapa B, AWS/S3, W34, snapshot, entrenamiento,
DVC, deploy ni cambios de dashboard sin nueva orden.

## Salida de sesión WCP — estado único vigente — 9-sep-2026

**Trabajo operativo cerrado por ratificación expresa del autor.** Póster inglés
cargado al WCP y web publicada. No repetir carga, rediseño o petición de ratificación.
Par EN ec5ebd80… / ES 8a0a9018… intacto; frontend f02d2d16656ca1365d2b0a351109fb3be396457e.
35 criterios registrados por hash; 46+52 controles y 22 de exportación correctos.
Sello 110 piezas; manifiesto documental 103. EN 24/24, ES 23/24+C03 aceptada.
Salida final: las nueve dependencias recuperadas ya están en RATIFICATION_FILES
del exportador y son obligatorias también al verificar. No reponerlas sólo a mano
ni regenerar desde el carril antiguo de 94 piezas. Evidencia exacta en
`poster/auditorias/ratificacion_2026-09-09/INVENTARIO_RECUPERADO.json` dentro de Mundial.
Índice de salida desde workspace: `planes/SALIDA_WCP_2026-09-09.md`.
Gobernante: 13 PASA, 3 EXC, 13 N/A y 4 FALLA por formularios nominales sin
respuestas/firmas; no confundir la ratificación global del autor con jueces
independientes. EXC y N/A nunca se suman como aprobaciones. No abrir tareas
automáticas por esa diferencia documental.

Desde la raíz del workspace, leer únicamente para reanudar:
- `EpiForecast-MX/Congresos/Mundial/ESTADO_ACTUAL_WCP.md`.
- `planes/PROMPT_REANUDAR_WCP_ENVIADO_2026-09-09.md`.
- `POSTER_WCP_2026/RATIFICACION_Y_CIERRE_2026-09-09.md`.

Los checkpoints WCP inferiores son históricos, incluso donde dicen «vigente»,
«sin ratificar», «no registrado», «no publicado» o manifiesto 93/94. No ejecutarlos.
No cambia la continuidad de Obesidad u otros carriles. Cambios de memoria locales;
sin commit/push/deploy en esta salida. Preservar árboles sucios y artefactos sellados.

## WCP — cierre ratificado por el autor — 9-sep-2026

Prevalece sobre los checkpoints WCP inferiores. El autor declaró «ya esta todo
ratificado y validado cierra todo ya pues». Esquema registrado: 35 criterios
G11/G12/G14/G15, ligados al par por SHA-256 y no por carpeta. No volver a pedir
ratificación, ejecutar planes históricos, rediseñar ni repetir la carga.
PDF EN ec5ebd80… / ES 8a0a9018… intactos; WCP cargado y web vigente f02d2d16.
Sello 97; manifiesto documental 103, con el anterior 94 conservado como antecedente.
46 controles históricos + 52 del registro correctos. Excepciones G2/G5/G19
aceptadas y separadas de PASS; C03 ES conserva su excepción. La declaración del
autor no se transforma en respuestas o firmas nominales de jueces no aportadas.
No afirmar certificación independiente ni abrir tareas automáticas por esa
distinción. Cierre: POSTER_WCP_2026/RATIFICACION_Y_CIERRE_2026-09-09.md.
Estado: EpiForecast-MX/Congresos/Mundial/ESTADO_ACTUAL_WCP.md.
Sin commit, push, despliegue o actuación en el portal en esta ratificación.

## WCP — carga registrada y web vigente comprobada — 8/9-sep-2026

**Prevalece para la continuidad WCP sobre las secciones históricas inferiores.**
El autor ya cargó el póster inglés #3134: el portal muestra
`WCP2026ePoster3134Rebull`, **09.09.2026 03:19**, E-POSTER VIEWING.
La subida no es pendiente. Capturas conservadas; no se descargó la copia del
portal ni se afirma aprobación editorial o carga ES.

El sitio del QR ya sirve el par vigente, verificado por descarga pública:
EN `ec5ebd80…` / ES `8a0a9018…`, inglés inicial,
`Reports/wcp2026/2026-09-08-8a0a9018/`.
Frontend HEAD y referencia local origin/main:
`f2141bbacbcd8b692fedda1199ace3b889a070a0`.
No listar como pendiente publicar este par. No se hizo push/deploy en este cierre.

Estado autoritativo y hashes completos, rutas desde la raíz del workspace:
- `EpiForecast-MX/Congresos/Mundial/ESTADO_ACTUAL_WCP.md`.
- `POSTER_WCP_2026/REGISTRO_SUBIDA_WCP_2026-09-09.md`.
- Handoff: `planes/PROMPT_REANUDAR_WCP_ENVIADO_2026-09-09.md`.

Preservar la entrega lema_congreso: EN 24/24; ES 23/24 más excepción de densidad
ligada al hash, no un PASS adicional. Sello 97 piezas; manifiesto 93 piezas.
Cuatro revisiones humanas y contrato interno 960×540/12 pt siguen sin cerrarse;
no se dispensan por la carga. No hubo financiamiento; título aceptado intacto,
siete apellidos con guion. No reabrir diseño ni ejecutar prompts de opciones 7–9.
La hoja sellada y las versiones históricas se conservan intactas; el nuevo estado
documenta los eventos posteriores. Ninguna nueva acción externa está autorizada
por esta actualización de memorias.

## WCP opción 9 — QR publicado y verificado — 2026-09-04

**Prevalece sobre los cierres WCP inferiores.** El usuario autorizó publicar únicamente
los materiales del QR. Publicado en https://epiforecast.mx/wcp2026.html mediante frontend
`c6e0bf9d7deb587df028a799da7139edc8fc401d`; ocho archivos WCP, ningún cambio ajeno.
Los PDF públicos EN/ES son byte-idénticos a los canónicos (hashes aec864d5… / 4c5911f8…).
Sello de 73 piezas intacto. Validación publicada **27/31**: G10c ya pasa; sólo restan
G11/G12/G14/G15 humanos, sin firmas. No se subió nada al congreso.

Evidencia: `EpiForecast-MX/Congresos/Mundial/poster/qa_opcion9/PUBLICACION_OPCION9.json`.
Portada equivalente tras Pretty URLs; news y knowledge iguales; corpus y vectores RAG
iguales, con sólo la fecha built actualizada por el build habitual de Netlify.
El checkpoint sellado anterior conserva su texto LOCAL_NO_PUBLICADO como historial;
no ejecutar su cierre ni interpretarlo como estado vigente.

Reanudar con `planes/PROMPT_REANUDAR_WCP_2026_OPCION9_PUBLICADA_2026-09-04.md`
desde la raíz del workspace. No reabrir financiamiento ni logos. No modificar PDF ni
firmar por humanos. Esta autorización no permite otras publicaciones ni la subida al congreso.


## WCP vigente — opción 9, correcciones de auditoría — 2026-09-04

Esta sección sustituye los cierres WCP inferiores. Diseño y WCP/WPA conservados; no hubo
financiamiento. Mapa corregido a los motores seleccionados: mediana estatal 21.6%,
máximo Tlaxcala 46.7%; Puebla 20.6%. Las cifras nacionales y las 52 semanas no cambiaron.
Revisiones G11/G12/G14/G15 reforzadas: criterios completos, ambos idiomas, veredicto de
aprobación y firmas fechadas; ninguna revisión real está firmada.

PDF EN 260819 B, `aec864d59318a8ce771bba7aa9a4499e104e9f88d01d239ea08c07421280cb10`.
PDF ES 260047 B, `4c5911f86be196a8811553930d6c2af6459d380273c409a3b909f0d60322cf08`.
Suite definitiva 89/89 (39 mutantes específicos, 45 negativos y 5 positivos).
Sello 73 piezas; validación verificada 26/31: cuatro revisiones humanas y G10c (QR público
desactualizado). No confundir disponibilidad HTTP 200 con versión publicada correcta.
Paquete QR LOCAL verificado: `Congresos/Mundial/poster/entrega_qr_opcion9/` en backend.
Evidencia definitiva: `Congresos/Mundial/poster/qa_opcion9/CIERRE_OPCION9.json`.

Handoff desde raíz del workspace:
`planes/PROMPT_REANUDAR_WCP_2026_OPCION9_2026-09-04.md`.
Usar `qa_opcion9/cierre.py`, no el cierre histórico de `qa_coautoras/`.
Sin commit, push, deploy, subida al congreso ni comunicaciones externas. Publicar el
paquete QR requiere autorización; no autoriza subir al congreso. El asistente no firma por
humanos ni acredita ceguera. Frontend y fuentes/modelos no fueron modificados.



> **WCP vigente: opción 8, 4-sep-2026 (coautoras).** Sustituye las instrucciones inferiores
> para reanudar opción 7. WCP/WPA se conservan por el encargo del autor; financiamiento cerrado:
> no hubo. PDF EN 260355 B, `76ff5bcf75ae7c5f9030c68c7dd03d0696e16209e57715c1319a3928a4610ed4`;
> ES 259591 B, `b434906b89d3d11f65318fcfd231a8bc8055242afe4d229e33a64dad89318226`.
> 25/29 en ambos, sello 64 piezas; cuatro hojas humanas actualizadas y sin firma. El horizonte
> corregido contiene 52 semanas hasta 1-feb-2027 en calendario de boletín. Handoff en
> `planes/PROMPT_REANUDAR_WCP_2026_OPCION8_2026-09-04.md` desde la raíz del workspace;
> resultados y defensa en `Congresos/Mundial/poster/qa_coautoras/CIERRE_OPCION8.json`.
> No reiniciar diseño ni reabrir el logo como bloqueo. No hacer acciones externas sin autorización.


## Reanudación siguiente — cierre del e-póster WCP 2026, opción 7

Copiar literalmente el bloque `## PROMPT`…`## FIN DEL PROMPT` de
`../planes/PROMPT_REANUDAR_WCP_2026_OPCION7_2026-09-04.md` (SHA256
`a4385a9f6019433cb3a77736b766fd1c3ec736ee515cc65b7a3345dc234eedd3`). La fase de plan ya
terminó. Estado: PDF EN `0467672…` (271,222 B), PDF ES `7f93a9a…` (266,742 B), 25/29 en
ambos, sello de 49 piezas; G11/G12/G14/G15 requieren revisión humana final. La suite de
mutación está ROTA 28/48 por veinte anclas rancias: cerrar primero G6 96 dpi y los cuatro
brazos de G22. Resolver antes si sale el logo WPA aislado del pie; conservar el lockup WCP.
**No hubo financiamiento**: no volver a pedir confirmación ni anotarlo como pendiente. No
mencionar como pendiente ningún correo a Kenes. Sin commit, push, deploy, subida ni acción
externa sin autorización explícita.

## 0 · P1 W33 y P1b publicadas (2-sep-2026); nada pendiente de merge

La fuente oficial 2026 fue comprobada el 2-sep-2026: contiene 33 boletines y el último
verificable es W33; W34 aún no está publicada. **P1 está publicada**: el sello
`882663dac1f1e39b` (W31 → W33, cuatro publicados en el mismo corte, 1,800 artefactos, 0
lápidas, `cifras` y `rag` PASS) se integró con merge commit `d7c9c6c2` en el backend (CI de
`main` run 33672251817 verde: 2,326 passed, 497 skips exactos, cobertura 77 %) y `72ae9e83`
en el frontend; Netlify desplegó https://epiforecast.mx con DATA_VERSION 20260825, knowledge
W33 (432/444), RAG 453, zoom 444 y los cuatro padecimientos con última fecha real 2026-08-10.

**Tanda correctiva P1b (2-sep-2026), integrada y publicada:** el smoke productivo encontró el
banner estático de novedades de `index.html` incoherente (titular del CALASS con fecha y
subtítulo de W33; lista secundaria en W31). Causa: `scripts/build_news_weekly.py` sólo
sustituía el titular si ya era una nota semanal. Corrección en `1ae477d5` (el bloque
`#newsBannerRow` se reescribe entero desde `news.json`, fallando en seco si falta) y gate
`cifras` reforzado en el frontend (`84536608`: el bloque estático debe coincidir con
`news.json`; contra el sitio publicado reporta cuatro desalineaciones). Re-sello
`89d70cc441ee255a` con ambos arreglos; backend PR #16 fusionada con merge commit `3bd67236`
(CI de `main` run 33677859434 verde: 2,329 passed, 497 skips exactos, cobertura 77 %,
Integration skipped) y frontend PR #12 fusionada con merge commit `8490e433`. Smoke productivo
completo en https://epiforecast.mx, con y sin JavaScript: banner estático y DOM renderizado
iguales a `news.json` (lead W33 · Datos · 2 de septiembre; CALASS y W31 en la lista
secundaria), W33 en los cuatro padecimientos (última fecha real 2026-08-10, 444 series),
DATA_VERSION 20260826, `app.js?v=140`, cifras 333/99/432/444, RAG 453 chunks, validación W33.
Checkpoint material P1b: backend `main@3bd67236`, frontend `main@8490e433`. El cierre
documental y de limpieza posterior llevó el backend vigente a `main@77dc2dcb`; las ramas
P0/P1/P1b se retiraron y el respaldo quedó como etiqueta local. W34 sólo cuando exista su
PDF oficial y los cuatro publicados avancen juntos.

**Limpieza one-shot (2-sep-2026, noche):** ambos repositorios quedan sólo con `main` local y
`origin/main` como rama remota activa; el backend conserva además la referencia remota de
archivo `respaldo/paper/micai-2026-camera-ready`. Cero worktrees adicionales (se retiraron
sin `--force` los dos del par de la
corrida 7). Ramas borradas tras verificar ancestría con `main`, locales con `-d` y remotas con
`push --delete`: backend `ci/skip-budget-ets-legacy`, `docs/p1b-publicada`,
`p0/namespace-e-inmutabilidad-del-sello`, `p1/actualizacion-semanal-2026-w33`,
`p1/release-backend-2026-w33-c6` (sólo local), `p1b/fallback-estatico-w33` y
`p1b/release-backend-c7` (sólo local); frontend `fix/frontend-deudas`,
`p1/actualizacion-semanal-2026-w33` y `p1b/fallback-estatico-w33`. La ref temporal
`auditoria/main` se retiró. El respaldo P0 pre-rebase vive ahora en la etiqueta LOCAL
`archive/p0-pre-rebase-584cf72d-2026-09-02` (no publicada). Se retiraron sólo los temporales
`_trabajo*` y `_release` del scratchpad; sellos,
clon, DVC, PDFs, modelos y evidencia (`planes/p1_2026-w33_2026-09-02/`, con
`limpieza/inventario_antes.txt`) se conservan. Producción sigue en W33; W34, DVC, datos y
despliegue intactos.

Regla de operación: resolver del HEAD todos los `lifecycle=published` y exigir exactamente
el mismo `(año, semana)` para cada uno en consolidado, salidas y superficies. Si uno no
llega, **abortar todo el lote**; nunca publicar a los demás, conservar uno atrasado ni
ocultarlo de `--padecimientos`. W34 se procesa únicamente cuando exista el PDF oficial y
los cuatro publicados puedan llegar juntos a W34.

## 0a · Historial P0 — no usar como estado vigente

Estado al 2-sep-2026 (tercera tanda): rama `p0/namespace-e-inmutabilidad-del-sello` con
**26 commits rebased sobre `16476a98`** (tip `f88a065e`), árbol limpio, enviada a `origin`.
PR **#14** (https://github.com/EpiForecastMX/EpiForecast-MX/pull/14) **fusionada en `main`** con merge commit `5da24116` (padres `16476a98` y `d6e7a181`); CI del push a `main` `33645677062` verde: Code Quality PASS, Tests PASS (2 324 passed, 497 skipped exactos, 66 deselected, cobertura 77,00 %), Integration skipped por diseño. **Sin DVC, sin publicación ni deploy.** P1 en curso en `p1/actualizacion-semanal-2026-w33` desde `main@5da24116`. `make update-week` aborta en preflight hasta la autorización de P1. No usar
`update-week-apply` sobre los repositorios canónicos, no descargar W32/W33, no ejecutar DVC
y no publicar; el merge de la PR es una decisión aparte.

Para retomar, leer la sección P0 de `AGENTS.md` (workspace) y `CLAUDE.md`. Receta local,
en este orden y sólo con datos sintéticos o el ensayo en clones locales:

1. `materialize --trabajo <nuevo> --repo-backend . --head-backend <sha> --repo-dashboard
   <repo> --head-dashboard <sha>` (escribe `materializacion.json`);
2. `hydrate --trabajo <trabajo> --repo-backend . --head-backend <sha> --padecimientos
   "Alzheimer,Depresión,Parkinson,Dengue" --boletin nombre:url:bytes:sha256 ...`;
3. generadores en `<trabajo>.sandbox/EpiForecast-MX` con `--out` hacia
   `<trabajo>/outputs`; `bump-cache --trabajo --destino-dashboard --head-dashboard`;
   `run-gates --trabajo --head-backend --destino-backend --destino-dashboard`; `seal` con
   `--destino-backend`, `--destino-dashboard`, `--semana-anterior`/`--semana-nueva`
   (= cortes reales) y `--padecimientos`;
4. `make update-week-apply MANIFEST=<run>/manifest.json DESTINOS=<raíz nueva>` (sólo
   sobre clones o worktrees desechables) y `make update-week-discard MANIFEST=… DESTINOS=…`.

Rollback: descartar el par y el sandbox; el sello y su evidencia se conservan. La tabla
333 ya está reparada; el bloqueo vigente es la autorización de P1 (red: pull, DVC,
GEMINI_API_KEY para el índice RAG).

Plan auditado, que no debe reescribirse durante el handoff:
`../planes/PLAN_ACTUALIZACION_SEMANAL_UNIFICADA_2026-09-01_v4.md`, SHA256
`5cfdf5a4a2d8e5ed1acf004e8c90a00e929dfd217ba051fff925e742fe9e233d`.

Comandos verificados de la sesión del 19-20 de agosto de 2026. Todos se ejecutan desde la
raíz del repositorio salvo donde se indique.

```bash
cd /Users/haowei/Documents/Integrador/EpiForecast-MX
```

---

## 1 · Presentación CALASS 2026

### Reconstruir el mazo — EL FLUJO REAL, en este orden

> Cada paso existe porque saltárselo ya produjo un fallo. `imprime_documentos.py` **sólo copia**
> los PDF de las láminas: no los construye. Si tocas `construye.py` y no corres Chrome, el
> sellado usará el PDF anterior — y el conteo de páginas no lo delata, porque el viejo también
> tiene 15. Hoy la guardia se niega a sellar y te recuerda el comando; antes, no.

```bash
cd EpiForecast-MX/Congresos/CALASS2026

# 1 · Figuras, si cambió su fuente o los datos
python3 figuras/fig_mapa_motores.py            # lámina 8 · «Modelo ganador»
python3 figuras/captura_comparador.py          # lámina 6 · recaptura del sitio, con gate de tilde
python3 figuras/fig_validacion_prospectiva.py  # lámina 10

# 2 · HTML de las láminas
cd diapositivas && python3 construye.py && cd ..

# 3 · PDF canónicos — ESTE PASO ES APARTE Y SE OLVIDA
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
cd diapositivas && for i in fr es; do
  "$CHROME" --headless --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="calass2026_$i.pdf" --virtual-time-budget=20000 \
    "file://$PWD/calass2026_$i.html"; done && cd ..

# 4 · Sellado completo: mazos, guion, preguntas, respaldos, tarjetas, LEEME y HASHES
python3 imprime_documentos.py

# 5 · Validar. Sin verde, no se lleva a ninguna memoria.
python3 valida.py
bash USB/verifica.command      # ahora devuelve código 1 si algo no cuadra
```

**Y míralo.** Los gates no ven maquetación: renderiza y observa antes de sellar.

```bash
pdftoppm -png -r 70 USB/1_PRESENTACION_fr_PROYECTAR.pdf /tmp/rev
```

### Regenerar las figuras

```bash
cd Congresos/CALASS2026/figuras
../../../.venv/bin/python fig_validacion_prospectiva.py   # validación (lámina 10)
../../../.venv/bin/python fig_mapa_motores.py             # mapa (lámina 8)
../../../.venv/bin/python fig_recursos.py                 # QR y recortes
```

### Validar

```bash
cd Congresos/CALASS2026
../../.venv/bin/python valida.py
```

Comprueba cifras entre las cuatro superficies, frases vetadas, valores de la alineación
vieja, tipografía francesa, número de láminas, duración del guion y **que el USB coincida
por hash con los mazos canónicos**.

### Rehacer el paquete USB

```bash
cd Congresos/CALASS2026
../../.venv/bin/python imprime_documentos.py
```

Copia los mazos canónicos y reimprime guion y preguntas. **Correr siempre después de tocar
`GUION_ES.md` o `PREGUNTAS.md`**, o el validador falla.

### Verificar una copia del USB (en la memoria, antes de proyectar)

Doble clic en `USB/verifica.command`, o:

```bash
cd Congresos/CALASS2026/USB && ./verifica.command
```

### Detectar desbordes y colisiones en las láminas

```bash
cd Congresos/CALASS2026/diapositivas
../../.venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
from pathlib import Path
JS = """() => { const out=[];
document.querySelectorAll('section.slide').forEach((s,i)=>{const pie=s.querySelector('.pie'),
pr=pie.getBoundingClientRect(),sr=s.getBoundingClientRect(),pb=[];
s.querySelectorAll('*').forEach(e=>{if(pie.contains(e))return;const r=e.getBoundingClientRect();
if(!r.width||!r.height||getComputedStyle(e).position==='absolute')return;
if(r.bottom-sr.bottom>1.5||r.right-sr.right>1.5)pb.push('desborda '+(e.className||e.tagName));
if(e.children.length===0&&(e.textContent||'').trim()&&r.bottom>pr.top+1&&r.top<pr.bottom&&r.left<pr.right&&r.right>pr.left)
pb.push('pisa el pie');});if(pb.length)out.push({l:i+1,pb:[...new Set(pb)]});});return out;}"""
with sync_playwright() as p:
    b=p.chromium.launch()
    for i in ("fr","es"):
        pg=b.new_page(viewport={'width':1400,'height':900})
        pg.goto(f"file://{Path(f'calass2026_{i}.html').resolve()}", wait_until="load", timeout=120000)
        pg.wait_for_timeout(3000); r=pg.evaluate(JS)
        print(f"  {i.upper()}: " + ("limpias" if not r else str(r)))
        pg.close()
    b.close()
PY
```

---

## 2 · Tableau y Google Sheets

### Estado actual — no volver a publicar la hoja

Google Sheets productivo **ya quedó actualizado** el 2026-08-20 y fue releído contra el XLSX:

- `scaffold` 227,106 × 5 con `fecha_boletin`;
- `real` 72,705 × 6;
- `forecast` 227,106 × 5;
- `metricas` 333 × 10;
- `entidades` 37 × 12;
- `meta.updated = 2026-08-19 23:06:32 CST`;
- 2,711,102 celdas y tipos numéricos preservados.

**No correr otra vez `scripts.publish_gsheets`.** El siguiente paso es manual en Tableau
Desktop/Public Edition. No publicar `viz_epiforecastmx_W31_PUENTE.twb` ni
`viz_epiforecastmx_W31_REPARADO.twb`: el primero sólo tiene una worksheet; el segundo apunta al
XLSX local y todavía usa `ds` en las superficies visibles.

Estado completo y pendientes: `docs/ESTADO_TABLEAU_W31_2026-08-20.md`.

### Cargar credenciales

```bash
export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat ~/Documents/Keys/gen-lang-client-0524709190-70b572b126c9.json)"
export GSHEETS_SPREADSHEET_ID="1MahkA5xEsJwWdn9swge-h4pvQ3J3VePq1otT4xKjiYQ"
```

Comprobar sin imprimir la llave:

```bash
echo "$GSHEETS_SPREADSHEET_ID"
python3 -c 'import os,json; print(json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])["client_email"])'
```

### Ensayo de credencial (no escribe nada)

```bash
.venv/bin/python respaldos_gsheets/verifica_gsheets.py
```

### Regenerar el XLSX y pasar su gate

```bash
.venv/bin/python -m scripts.build_tableau
.venv/bin/python scripts/verifica_tableau_fecha_boletin.py
```

`build_tableau.py` **no acepta argumentos**: `--help` lo ignora y corre el build completo.
Solo escribe el archivo local; nunca toca Google Sheets.

### Respaldar la hoja ANTES de publicar

```bash
.venv/bin/python respaldos_gsheets/respalda_gsheets.py \
  respaldos_gsheets/$(date +%F)_pre_publicacion
```

Guarda JSON **tipado**. Nunca respaldar con CSV: convierte los números en texto y rompería
Tableau.

### Publicar

```bash
.venv/bin/python -m scripts.publish_gsheets
```

⚠️ **Se cae por cuota** (`429 write requests per minute`) y deja pestañas a medias, sin
reintento ni transacción. Si pasa: esperar 65 s y completar solo lo que falte; restaurar
2.7 M de celdas chocaría con la misma cuota.

### Releer y validar lo publicado

```bash
.venv/bin/python respaldos_gsheets/verifica_publicacion.py
```

### Restaurar si algo salió mal

```bash
.venv/bin/python respaldos_gsheets/restaura_gsheets.py <carpeta_respaldo>              # ensayo
.venv/bin/python respaldos_gsheets/restaura_gsheets.py <carpeta_respaldo> --ejecutar   # de verdad
```

Se niega si el ID del destino no coincide con el del respaldo.

---

## 3 · Comprobar el portal en vivo

```bash
curl -fsSL https://epiforecast.mx/epibot/knowledge.json \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['boletin']['meta']; print(d['max_semana'], d['total_registros'])"

curl -fsSL https://epiforecast.mx/news.json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('items') or d)[0])"
```

Esperado: `31  63072` y la novedad de la semana 31.

---

## 4 · Calidad del repositorio

```bash
.venv/bin/ruff check --no-cache <archivos>
.venv/bin/ruff format --check --no-cache <archivos>
make lint && make typecheck && make test-fast
```

---

## Rutas que se usan seguido

| Qué | Dónde |
| --- | --- |
| Presentación | `Congresos/CALASS2026/` |
| Paquete USB | `Congresos/CALASS2026/USB/` |
| Mazos viejos, no proyectar | `Congresos/CALASS2026/diapositivas/_archivo/` |
| Respaldos de la hoja | `respaldos_gsheets/` y `~/Documents/Respaldos_EpiForecast/` |
| Llave de Google | `~/Documents/Keys/gen-lang-client-...json` |
| Manual de publicación | `docs/MANUAL_B1_PREFLIGHT_GOOGLE_TABLEAU.md` |

**Los cuatro scripts de la hoja** viven juntos en `respaldos_gsheets/`:
`verifica_gsheets.py` (¿sirve la credencial?), `respalda_gsheets.py` (respaldo tipado),
`restaura_gsheets.py` (rollback sobre el mismo ID) y `verifica_publicacion.py` (relectura
tras publicar). Los tres primeros están además copiados fuera del repositorio.
