#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# actualiza_semanal.sh  —  PREPARA y SELLA el refresh semanal
#
# Extiende el dato real tras un boletin nuevo, reselecciona el motor productivo y
# regenera tablas, validacion, galeria (neuro + Dengue), zoom, knowledge y barra de
# fechas. NO reentrena: los pronosticos siguen congelados y solo avanza la realidad.
#
# ESTE GUION NO PUBLICA. Genera todo bajo runs/_refresh/<run_id>/outputs y lo sella con
# un manifiesto. Instalar esos bytes es una orden aparte, que recibe el manifiesto de
# forma explicita:
#
#   make update-week                        # prepara y sella
#   make update-week-apply MANIFEST=<ruta>  # instala lo sellado
#
# Antes preparaba escribiendo directamente en ambos repositorios y despues decidia si
# publicar. Eso tenia dos consecuencias: el propio modo en seco ensuciaba el arbol y la
# publicacion abortaba por su culpa; y lo que se publicaba no era necesariamente lo
# revisado, porque entre una cosa y otra el pipeline volvia a correr.
#
# El staging se siembra clonando el destino (varios generadores leen lo que ya existe) y
# al sellar se retira lo que no cambio, de modo que el inventario diga que cambio esta
# semana y no repita los casi dos mil archivos del sitio.
#
# EXCEPCION DECLARADA: el consolidado del boletin SI se actualiza en su ruta canonica.
# Es la entrada de la que leen todos los generadores, no un artefacto publicable, y su
# digest queda sellado en el manifiesto para que la instalacion sepa sobre que dato se
# preparo.
#
# Uso:
#   bash scripts/actualiza_semanal.sh [--allow-dirty]
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

ALLOW_DIRTY=0
for arg in "$@"; do
  case "$arg" in
    --allow-dirty) ALLOW_DIRTY=1 ;;
    *) echo "Uso: $0 [--allow-dirty]" >&2; exit 2 ;;
  esac
done
MODE="prepare"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Parametrizable para poder preparar contra un clon limpio sin tocar el sitio de trabajo.
DASHBOARD_REAL="${DASHBOARD_REAL:-/Users/haowei/Documents/Integrador/EpiForecast-IMSS-Dashboard}"
PYTHON="${REPO_ROOT}/.venv/bin/python"
CONSOLIDADO="data/processed/dataset_boletin_epidemiologico.csv"
REFRESH_DIR="${REPO_ROOT}/runs/_refresh"
TRABAJO="${REFRESH_DIR}/_trabajo"
RAMA_ESPERADA="main"

# Padecimientos que el refresh semanal puede versionar y publicar. Cualquier otro
# presente en el consolidado se informa: la frontera efectiva la aplica el filtro por
# lifecycle del generador de conocimiento, no una variable de entorno.
PADECIMIENTOS_PUBLICABLES="Alzheimer Depresión Parkinson Dengue"

cd "$REPO_ROOT"

fatal() { echo "" >&2; echo "ABORTA: $*" >&2; exit 1; }
paso()  { echo ""; echo ">>> $*"; }

# ─────────────────────────────────────────────────────────────────────
# 1. PREFLIGHT — todo falla cerrado
# ─────────────────────────────────────────────────────────────────────
paso "PREFLIGHT · productor bloqueado hasta P1"
# El cableado de abajo —materialize → generadores → run-gates → seal, y después
# prepare-worktrees → apply → check-completeness— está probado con repositorios
# sintéticos, nunca contra datos reales. Antes de que este guion vuelva a correr de
# verdad faltan tres cierres de P0 y una autorización:
#
#   P0.1  hidratación por allowlist de lo que los generadores leen (forecasts, modelos,
#         PDFs, consolidado) con control positivo de cobertura 333/99/432;
#   P0.2  copia inmutable de los inputs (PDFs y consolidado) bajo el staging, con
#         digest antes y candidato;
#   P0.8  Dengue fail-closed: hoy el paso [3/10] es best-effort y el [7/10] publicaría
#         un Dengue rancio si la extracción falla.
#
# La decisión P0.11 ya está tomada: opción C. Esta ronda actualiza superficies públicas y
# deja el dataset DVC pendiente; el manifiesto no autoriza ninguna operación DVC.
# La puesta al día (P1: W32, W33 y lo que haya) exige autorización aparte.
#
# Se aborta AQUI, antes de la preparación cara, en vez de dejar que falle al final tras
# cuarenta minutos de trabajo tirado.
fatal "el productor semanal sigue BLOQUEADO a propósito. El cableado materialize → run-gates
    → seal → prepare-worktrees → apply → check-completeness está probado sólo con
    repositorios sintéticos; faltan P0.1 (hidratación por allowlist), P0.2 (inputs bajo el
    staging) y P0.8 (Dengue fail-closed). Decisión P0.11: opción C, superficies públicas
    al día y dataset DVC pendiente. La puesta al día (P1) exige autorización aparte."

paso "PREFLIGHT (modo: ${MODE})"

[ -x "$PYTHON" ] || fatal "no existe el interprete del entorno: $PYTHON"
command -v dvc >/dev/null || fatal "dvc no esta en el PATH"
[ -d "$DASHBOARD_REAL" ] || fatal "no existe el repositorio del dashboard: $DASHBOARD_REAL"

# P1 · rama de cada repositorio. Solo se informa: este guion ya NO publica, y el gate en
# clon limpio se corre precisamente sobre worktrees en HEAD suelto. Quien publica es el
# apply, y alli la comprobacion es mas fuerte que la rama: exige que el HEAD sea
# exactamente el que se sello.
for par in "principal:${REPO_ROOT}" "dashboard:${DASHBOARD_REAL}"; do
  nombre="${par%%:*}"; ruta="${par#*:}"
  rama="$(git -C "$ruta" rev-parse --abbrev-ref HEAD)"
  if [ "$rama" = "$RAMA_ESPERADA" ]; then
    echo "    ${nombre}: rama ${rama}"
  else
    echo "    ${nombre}: rama ${rama} (no es ${RAMA_ESPERADA}; se prepara igual, no se publica)"
  fi
done

# P2 · arbol rastreado limpio: un refresh sobre cambios a medio hacer los publica.
if [ "$ALLOW_DIRTY" -eq 0 ]; then
  for par in "principal:${REPO_ROOT}" "dashboard:${DASHBOARD_REAL}"; do
    nombre="${par%%:*}"; ruta="${par#*:}"
    if [ -n "$(git -C "$ruta" status --porcelain --untracked-files=no)" ]; then
      git -C "$ruta" status --short --untracked-files=no >&2
      fatal "el repositorio ${nombre} tiene cambios rastreados sin confirmar. Confirmalos o usa --allow-dirty si sabes lo que haces."
    fi
  done
  echo "    ambos arboles rastreados: limpios"
fi

# P3 · upstream configurado y sin divergencia: publicar sobre un remoto adelantado falla tarde.
for par in "principal:${REPO_ROOT}" "dashboard:${DASHBOARD_REAL}"; do
  nombre="${par%%:*}"; ruta="${par#*:}"
  if git -C "$ruta" rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1; then
    git -C "$ruta" fetch --quiet origin "$RAMA_ESPERADA"
    detras="$(git -C "$ruta" rev-list --count "HEAD..origin/${RAMA_ESPERADA}")"
    echo "    ${nombre}: ${detras} commit(s) por detras del remoto"
  else
    echo "    ${nombre}: sin upstream (HEAD suelto); se prepara igual"
  fi
done

# P4 · GUARD: archivos sin versionar en las rutas que ESTE flujo descarga.
# Leccion del 2026-08-18: `dvc pull --force` retira sin aviso lo que no esta en un
# puntero, y data/raw/ contiene CSV que existen SOLO en disco. Este flujo ya no
# descarga data/raw/ ni fuerza nada, asi que ahi solo se avisa; se aborta unicamente
# por lo que sus propias descargas pueden retirar. Un guard que bloquea por algo que
# no puede ocurrir termina siendo un guard que la gente aprende a saltarse.
paso "PREFLIGHT · archivos sin versionar en rutas DVC"
sin_versionar="$("$PYTHON" - <<'PYGUARD'
import json, subprocess, sys

DESCARGA = ("data/processed/", "data/raw_PDFs/")   # lo que este flujo baja -> ABORTA
AVISO = ("data/raw/", "models/", "reports/forecasts/")  # el resto -> solo informa
try:
    out = subprocess.run(
        ["dvc", "data", "status", "--granular", "--json"],
        capture_output=True, text=True, timeout=300,
    ).stdout
    estado = json.loads(out or "{}")
except Exception as exc:  # noqa: BLE001
    print(f"ERROR_GUARD: no se pudo consultar dvc data status: {exc}")
    sys.exit(0)
anadidos = [p for p in (estado.get("uncommitted", {}).get("added", []) or []) if isinstance(p, str)]
for p in sorted(p for p in anadidos if p.startswith(DESCARGA)):
    print(f"BLOQUEA:{p}")

# El aviso se agrupa por directorio: listar cientos de artefactos de modelos uno a
# uno vuelve ilegible el preflight y esconde lo que si importa.
from collections import Counter  # noqa: E402

grupos = Counter()
for p in (p for p in anadidos if p.startswith(AVISO)):
    partes = p.split("/")
    grupos["/".join(partes[:-1]) + "/" if len(partes) > 1 else p] += 1
for carpeta, n in sorted(grupos.items()):
    print(f"AVISA:{carpeta}|{n}")
PYGUARD
)"
if echo "$sin_versionar" | grep -q '^ERROR_GUARD:'; then
  fatal "$(echo "$sin_versionar" | sed 's/^ERROR_GUARD: //')"
fi
bloquean="$(echo "$sin_versionar" | grep '^BLOQUEA:' | sed 's/^BLOQUEA://' || true)"
avisan="$(echo "$sin_versionar" | grep '^AVISA:' | sed 's/^AVISA://' || true)"
if [ -n "$avisan" ]; then
  total_avisos="$(echo "$avisan" | awk -F'|' '{s+=$2} END {print s+0}')"
  echo "    AVISO · ${total_avisos} archivo(s) sin versionar fuera de las rutas de descarga."
  echo "            Este flujo no los toca, pero un pull forzado a mano si los retiraria:"
  echo "$avisan" | awk -F'|' '{printf "      %-46s %6d\n", $1, $2}'
fi
# Si hay archivos sin versionar en una ruta que este flujo descarga, la descarga los
# retiraria. La respuesta segura no es abortar sino OMITIR esa descarga: solo sirve para
# traer lo que falte, y omitirla nunca destruye nada. Se declara, porque el precio es que
# si el flujo automatizado subio algo nuevo, esta corrida no lo vera.
OMITIR_PULL_PDFS=0
OMITIR_PULL_CONSOLIDADO=0
if [ -n "$bloquean" ]; then
  echo "    sin versionar en rutas de descarga (se omitira su descarga para no retirarlos):"
  echo "$bloquean" | sed 's/^/      /'
  echo "$bloquean" | grep -q '^data/raw_PDFs/' && OMITIR_PULL_PDFS=1
  echo "$bloquean" | grep -q '^data/processed/' && OMITIR_PULL_CONSOLIDADO=1
else
  echo "    ninguna ruta de descarga en riesgo"
fi

# P5 · padecimientos presentes frente a la lista autorizada.
paso "PREFLIGHT · padecimientos en el consolidado"
extras="$("$PYTHON" - "$CONSOLIDADO" "$PADECIMIENTOS_PUBLICABLES" <<'PYPAD'
import sys
import pandas as pd
ruta, permitidos = sys.argv[1], set(sys.argv[2].split())
presentes = set(pd.read_csv(ruta, usecols=["Padecimiento"])["Padecimiento"].unique())
print("PRESENTES:" + ",".join(sorted(presentes)))
sobrantes = presentes - permitidos
if sobrantes:
    print("EXTRAS:" + ",".join(sorted(sobrantes)))
PYPAD
)"
echo "    $(echo "$extras" | grep '^PRESENTES:' | sed 's/^PRESENTES://')"
lista_extras="$(echo "$extras" | grep '^EXTRAS:' | sed 's/^EXTRAS://' || true)"
if [ -n "$lista_extras" ]; then
  echo "    fuera de la lista autorizada: ${lista_extras}"
  echo "    (este guion no publica; el filtro por lifecycle los mantiene fuera del sitio)"
fi

# P6 · commits de datos del flujo automatizado, y los HEAD se FIJAN aquí. Un pull a
# mitad de corrida cambiaba el HEAD entre la siembra y el sello.
paso "PREFLIGHT · commits de datos y HEAD fijados"
# --ff-only: si el remoto divergio, aborta en vez de fabricar un merge.
git pull --ff-only origin "$RAMA_ESPERADA"
HEAD_BACKEND="$(git -C "$REPO_ROOT" rev-parse HEAD)"
HEAD_DASHBOARD="$(git -C "$DASHBOARD_REAL" rev-parse HEAD)"
echo "    backend   @ ${HEAD_BACKEND}"
echo "    dashboard @ ${HEAD_DASHBOARD}"

echo ""
echo ">>> PREFLIGHT COMPLETO"

# ─────────────────────────────────────────────────────────────────────
# 2. MATERIALIZAR EL CANDIDATO — el arbol administrado COMPLETO desde los HEAD fijados
# ─────────────────────────────────────────────────────────────────────
paso "MATERIALIZAR CANDIDATO (41/41 superficies, desde git archive)"
# `materialize` exige un directorio nuevo: un candidato no se pisa. El anterior, si lo
# hay, se aparta con marca de tiempo en vez de borrarse.
if [ -e "$TRABAJO" ]; then
  mv "$TRABAJO" "${TRABAJO}.previo.$(date +%Y%m%dT%H%M%S)"
fi
$PYTHON -m scripts.refresh_staging materialize \
  --trabajo "$TRABAJO" \
  --repo-backend "$REPO_ROOT" --head-backend "$HEAD_BACKEND" \
  --repo-dashboard "$DASHBOARD_REAL" --head-dashboard "$HEAD_DASHBOARD"

# ─────────────────────────────────────────────────────────────────────
# 2b. HIDRATAR — sandbox del backend con SOLO las entradas de la allowlist (P0.1/P0.2)
# ─────────────────────────────────────────────────────────────────────
# Los PDF nuevos se traen ANTES (dirigido, sin forzar) para poder declararlos al hidratar
# con bytes y SHA256; el consolidado se copia tal cual está (es el «antes»), y los
# generadores lo actualizan dentro del sandbox, nunca en el arbol real. La hidratacion
# exige el contrato exacto de cobertura (32 entidades, 432 series, paridad de corte)
# antes de que corra ningun generador: una allowlist corta no genera un candidato chico
# y plausible, aborta aqui.
paso "TRAER PDF · dvc pull dirigido (nunca --force)"
if [ "$OMITIR_PULL_PDFS" -eq 1 ]; then
  echo "    se omite data/raw_PDFs.dvc: hay PDFs locales sin versionar que la descarga retiraria"
else
  dvc pull data/raw_PDFs.dvc
fi
BOLETINES_ARGS=()
for pdf in $(ls -1 data/raw_PDFs/*.pdf | sort | tail -n 2); do
  nombre="$(basename "$pdf")"
  BOLETINES_ARGS+=(--boletin "${nombre}:local://data/raw_PDFs/${nombre}:$(stat -f %z "$pdf"):$(shasum -a 256 "$pdf" | cut -d' ' -f1)")
done
paso "HIDRATAR · sandbox por allowlist + contrato de cobertura"
$PYTHON -m scripts.refresh_staging hydrate \
  --trabajo "$TRABAJO" \
  --repo-backend "$REPO_ROOT" --head-backend "$HEAD_BACKEND" \
  --padecimientos "$(echo "$PADECIMIENTOS_PUBLICABLES" | tr ' ' ',')" \
  "${BOLETINES_ARGS[@]}"
SANDBOX="${TRABAJO}.sandbox/EpiForecast-MX"
# Los generadores corren DENTRO del sandbox: su codigo y sus entradas son los del HEAD
# fijado mas la allowlist; el interprete es el venv real, pero PYTHONPATH pone primero el
# src del sandbox para que importe ese codigo y no el del arbol de trabajo.
export PYTHONPATH="${SANDBOX}/src${PYTHONPATH:+:$PYTHONPATH}"

# A partir de aqui, los generadores escriben en el staging y NO en el sitio.
DASHBOARD_ROOT="$TRABAJO/outputs/dashboard"
REPORTS="${DASHBOARD_ROOT}/Reports"
EPIBOT="${DASHBOARD_ROOT}/epibot"

# ─────────────────────────────────────────────────────────────────────
# 3. PREPARAR — datos y computo. No publica.
# ─────────────────────────────────────────────────────────────────────
_semana_de() { tail -1 "$CONSOLIDADO" | cut -d',' -f1,2; }
ANTES="$(_semana_de)"
DIGEST_CONSOLIDADO_ANTES="$(shasum -a 256 "$CONSOLIDADO" | cut -d' ' -f1)"

paso "[1/10] Commits de datos"
echo "    ya traidos en el preflight; los HEAD quedaron fijados y no cambian a mitad de corrida"

paso "[2/10] Consolidado: sincronizacion aditiva DENTRO del sandbox"
# Los PDF ya se trajeron antes de hidratar. El consolidado NO se descarga: se fusiona. Es
# una superposicion del archivo versionado y de filas que hoy solo viven en local, asi que
# `dvc pull` lo ve modificado y se niega, y `--force` lo resolveria borrando el trabajo
# local. La sincronizacion aditiva agrega solo las semanas nuevas y falla cerrado si el
# origen corrigio una fila ya existente. Corre en el sandbox: el consolidado del arbol
# real (el «antes», ya copiado bajo inputs/) no se toca; el candidato queda en el sandbox
# y `seal` lo copia y lo sella como «candidato».
if [ "$OMITIR_PULL_CONSOLIDADO" -eq 1 ]; then
  echo "    se omite la sincronizacion: hay datos locales sin versionar en data/processed/"
else
  (cd "$SANDBOX" && $PYTHON -m scripts.sincroniza_consolidado)
fi
CONSOLIDADO="${SANDBOX}/${CONSOLIDADO}"

ULTIMA="$(_semana_de)"
ANIO="$(echo "$ULTIMA" | cut -d',' -f1)"
SEM="$(echo "$ULTIMA" | cut -d',' -f2)"
echo "    Consolidado: $(wc -l < "$CONSOLIDADO") filas | ultima semana neuro: ${ANIO}/sem${SEM}"

# ── Dengue: vive en una tabla aparte del boletin (Cuadro 7.2) y su extractor puede
#    romperse si cambia el layout del PDF. Antes era best-effort y el sitio publicaba
#    un Dengue rancio sin que nada lo declarara (P0.8). Ahora falla cerrado: sin Dengue
#    nuevo no hay candidato, y `seal` exige ademas paridad de corte entre los cuatro
#    padecimientos publicados sobre el consolidado candidato.
paso "[3/10] Dengue: extract -> merge -> prep (fail-closed)"
( set -e
  make -C "$SANDBOX" PYTHON="$PYTHON" dengue-extract ARGS="--incremental"
  make -C "$SANDBOX" PYTHON="$PYTHON" dengue-merge
  make -C "$SANDBOX" PYTHON="$PYTHON" dengue-prep ) \
  || fatal "Dengue extract/merge/prep fallo (¿layout del boletin?). No se publica un Dengue rancio: revisa el extractor y repite."
DENGUE_OK=1
$PYTHON - "$CONSOLIDADO" <<'PYDENGUE'
import hashlib, sys
import pandas as pd
ruta = sys.argv[1]
df = pd.read_csv(ruta, usecols=["Anio", "Semana", "Entidad", "Padecimiento"], low_memory=False)
d = df[df["Padecimiento"] == "Dengue"]
if d.empty:
    sys.exit("ABORTA: el consolidado candidato no tiene filas de Dengue")
anio, semana = int(d["Anio"].max()), int(d[d["Anio"] == d["Anio"].max()]["Semana"].max())
ultima = d[(d["Anio"] == anio) & (d["Semana"] == semana)]
print(f"    Dengue candidato: corte {anio}-W{semana} | {len(d):,} filas | {ultima['Entidad'].nunique()} entidades en la ultima semana")
print(f"    digest consolidado candidato: {hashlib.sha256(open(ruta, 'rb').read()).hexdigest()[:16]}...")
PYDENGUE

paso "[4/10] Reseleccion de motor productivo en 2026 real"
# tabla-produccion (backtest CV de los 333 modelos, ~19 min) NO corre cada semana:
# sus metricas CV dependen solo del historico y de los modelos CONGELADOS, no del
# boletin nuevo. Para refrescarlo tras reentrenar: RETRAIN=1 make update-week-apply
# Todo lo que sigue corre con cwd=$SANDBOX: lee las entradas hidratadas y escribe sus
# subproductos en el sandbox (scratch), y sus salidas publicables van con --out al
# candidato. El arbol real no se toca.
if [ "${RETRAIN:-0}" = "1" ] || [ ! -f "$SANDBOX/reports/ProdDetails/tabla_333_modelos_produccion.xlsx" ]; then
  echo "    (RETRAIN=1 o tabla ausente) -> regenerando backtest CV..."
  make -C "$SANDBOX" PYTHON="$PYTHON" tabla-produccion
else
  echo "    (refresh) se reutiliza el backtest CV existente; solo se re-scorea 2026."
fi
(cd "$SANDBOX" && $PYTHON scripts/reselect_motor_2026.py)

paso "[5/10] Tableau + validacion semanal"
(cd "$SANDBOX" && $PYTHON scripts/build_tableau.py --out "$SANDBOX/data/processed")
# La validacion escribe el HTML y la COPIA actualizada del Excel en el candidato del
# backend (prefijo administrado reports/ProdDetails/); el Excel del sandbox y el real
# quedan intactos.
(cd "$SANDBOX" && $PYTHON scripts/genera_validacion_semanal.py --out "$TRABAJO/outputs/backend/reports/ProdDetails")
cp "$TRABAJO/outputs/backend/reports/ProdDetails/validacion_semanal.html" "$DASHBOARD_ROOT/validacion_semanal.html"

paso "[6/10] Galeria neuro (graficos + zoom_data_neuro.json)"
(cd "$SANDBOX" && $PYTHON -m scripts.build_neuro_gallery --out "$REPORTS")

paso "[7/10] Dengue: produccion + web"
# Ya no hay escape por el CSV viejo: si [3/10] no produjo Dengue nuevo, el guion aborto.
make -C "$SANDBOX" PYTHON="$PYTHON" dengue-produccion
# Se redirigen explicitamente: por defecto apuntan al sitio real.
make -C "$SANDBOX" PYTHON="$PYTHON" dengue-web \
  DASHBOARD_DENGUE="${REPORTS}/dengue" \
  DASHBOARD_EPIBOT="${EPIBOT}"

# El zoom del EpiBot fusiona neuro + Dengue: DESPUES de dengue-web para que no
# quede desfasado con el Dengue anterior.
paso "[8/10] Zoom del EpiBot (neuro + Dengue fresco)"
(cd "$SANDBOX" && $PYTHON scripts/build_epibot_zoom.py --reports "$REPORTS" --out "$EPIBOT")

paso "[9/10] Knowledge.json del EpiBot"
(cd "$SANDBOX" && $PYTHON scripts/build_web_knowledge.py --out "${EPIBOT}/knowledge.json")

paso "[10/10] Barra de fechas + Novedades de la landing"
(cd "$SANDBOX" && $PYTHON scripts/actualiza_barra_fechas.py \
  --index "${REPORTS}/index.html" \
  --zoom  "${REPORTS}/zoom_data_neuro.json")
(cd "$SANDBOX" && $PYTHON scripts/build_news_weekly.py --dashboard "$DASHBOARD_ROOT")

# El backend aporta al candidato las tablas que el refresh regenera y que viven en git.
# Se copian desde el SANDBOX (donde las escribieron reselect y dengue-produccion), no
# desde el arbol real; la validacion y su Excel ya fueron directo al candidato con --out.
mkdir -p "$TRABAJO/outputs/backend/reports/ProdDetails"
for f in reports/ProdDetails/auditoria_motores_2026.xlsx \
         reports/ProdDetails/produccion_dengue.csv \
         reports/ProdDetails/produccion_dengue.xlsx; do
  [ -f "$SANDBOX/$f" ] && cp "$SANDBOX/$f" "$TRABAJO/outputs/backend/reports/ProdDetails/"
done

# ─────────────────────────────────────────────────────────────────────
# 4. GATES — sobre el arbol candidato COMPLETO, antes de podar
# ─────────────────────────────────────────────────────────────────────
# Los gates (cifras, rag) los define la politica del HEAD del backend como argv exactos;
# `run-gates` los ejecuta sin shell dentro del candidato y deja la evidencia en
# $TRABAJO/gates. Un gate que falle —o que mute un byte— impide sellar. El indice RAG
# desfasado ya no es un aviso: es un FAIL del gate `rag`, y se regenera ANTES de sellar
# con GEMINI_API_KEY=... npm run rag:build dentro del candidato, no en el sitio real.
paso "GATES · run-gates sobre la composicion candidata"
$PYTHON -m scripts.refresh_staging run-gates \
  --trabajo "$TRABAJO" \
  --head-backend "$HEAD_BACKEND" \
  --destino-backend "$REPO_ROOT" \
  --destino-dashboard "$DASHBOARD_REAL"

# ─────────────────────────────────────────────────────────────────────
# 5. SELLAR — inventario y manifiesto de lo producido
# ─────────────────────────────────────────────────────────────────────
paso "SELLAR STAGING"

$PYTHON -m scripts.refresh_staging seal \
  --trabajo "$TRABAJO" \
  --semilla "$TRABAJO/semilla.json" \
  --head-backend "$HEAD_BACKEND" \
  --head-dashboard "$HEAD_DASHBOARD" \
  --semana-anterior "$ANTES" \
  --semana-nueva "${ANIO},${SEM}" \
  --padecimientos "$(echo "$PADECIMIENTOS_PUBLICABLES" | tr ' ' ',')"

echo ""
echo ">>> PREPARACION COMPLETA (sem ${SEM}/${ANIO}). Dengue fail-closed: OK=${DENGUE_OK}."
echo "    NADA se publico: los artefactos estan sellados bajo runs/_refresh/."
echo "    El sandbox ${TRABAJO}.sandbox es scratch: retiralo cuando el sello este revisado."
echo "    Revisa el manifiesto y despues instala SOLO en un par de worktrees desechables:"
echo "      make update-week-apply MANIFEST=runs/_refresh/<run_id>/manifest.json DESTINOS=runs/_release/<run_id>"
echo "    Decision P0.11 (opcion C): el manifiesto no autoriza ninguna operacion DVC."
exit 0
