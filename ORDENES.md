# Órdenes a la mano

## 0 · P1 W33 — todos los publicados avanzan juntos

Fuente oficial validada el 2-sep-2026: 33 boletines disponibles, máximo W33; W34 aún no
existe. Sello candidato `2ae89151e88aa92a`: W31→W33, Alzheimer + Depresión + Parkinson +
Dengue en corte común, `cifras` y `rag` PASS. PRs draft: backend #15 en `6ab8a079` y
frontend #11 en `a35bdfb3` (preview verde). No confundir candidato con publicación.

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
