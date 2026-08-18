#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# actualiza_semanal.sh  (UNIFICADO, con preflight y modo en seco)
#
# Refresh semanal COMPLETO tras un boletin nuevo, SIN reentrenar modelos:
# extiende el dato real, reselecciona el motor productivo, regenera las
# tablas/validacion, la galeria /reports/ (neuro + Dengue), el zoom y el
# knowledge.json del EpiBot, actualiza la barra de fechas y publica.
#
# NO reentrena (eso es make train / dengue-train-*, infrecuente). Aqui los
# pronosticos quedan congelados y solo avanza la realidad: es la vista de
# validacion semanal honesta (real vs pronostico bloqueado).
#
#   MODO EN SECO (default):  prepara y calcula; NO publica nada.
#   MODO APLICAR:            lo anterior y ademas versiona y publica.
#
# Uso:
#   make update-week           # en seco
#   make update-week-apply     # publica
#   bash scripts/actualiza_semanal.sh [--dry-run|--apply] [--allow-dirty]
#
# Historia: hasta 2026-08-18 este script hacia `git pull`, `dvc pull --force`,
# versionado global y envios automaticos sin comprobar nada. Con el trabajo de
# C7 fuera de main, eso podia inyectar merges en una rama auditada, BORRAR los
# CSV de obesidad/anorexia/dengue que viven solo en disco, y publicar en una
# rama que el sitio no sirve, anunciando exito sin cambiar nada. El preflight
# de abajo existe para que esos cuatro casos aborten en vez de ocurrir.
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Argumentos ───────────────────────────────────────────────────────
MODE="dry-run"
ALLOW_DIRTY=0
for arg in "$@"; do
  case "$arg" in
    --apply)       MODE="apply" ;;
    --dry-run)     MODE="dry-run" ;;
    --allow-dirty) ALLOW_DIRTY=1 ;;
    *) echo "Uso: $0 [--dry-run|--apply] [--allow-dirty]" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DASHBOARD_ROOT="/Users/haowei/Documents/Integrador/EpiForecast-IMSS-Dashboard"
REPORTS="${DASHBOARD_ROOT}/Reports"
EPIBOT="${DASHBOARD_ROOT}/epibot"
PYTHON="${REPO_ROOT}/.venv/bin/python"
CONSOLIDADO="data/processed/dataset_boletin_epidemiologico.csv"
MANIFEST_DIR="${REPO_ROOT}/runs/_refresh"
RAMA_ESPERADA="main"

# Padecimientos que el refresh semanal puede versionar y publicar. Cualquier otro
# presente en el consolidado obliga a declararlo con ALLOW_EXTRA_DISEASES=1: no se
# versiona sin querer el insumo de un carril que sigue sin autorizacion.
PADECIMIENTOS_PUBLICABLES="Alzheimer Depresión Parkinson Dengue"

cd "$REPO_ROOT"

fatal() { echo "" >&2; echo "ABORTA: $*" >&2; exit 1; }
paso()  { echo ""; echo ">>> $*"; }

# ─────────────────────────────────────────────────────────────────────
# 1. PREFLIGHT — todo falla cerrado
# ─────────────────────────────────────────────────────────────────────
paso "PREFLIGHT (modo: ${MODE})"

[ -x "$PYTHON" ] || fatal "no existe el interprete del entorno: $PYTHON"
command -v dvc >/dev/null || fatal "dvc no esta en el PATH"
[ -d "$DASHBOARD_ROOT" ] || fatal "no existe el repositorio del dashboard: $DASHBOARD_ROOT"

# P1 · ambos repositorios en la rama que sirve el sitio.
for par in "principal:${REPO_ROOT}" "dashboard:${DASHBOARD_ROOT}"; do
  nombre="${par%%:*}"; ruta="${par#*:}"
  rama="$(git -C "$ruta" rev-parse --abbrev-ref HEAD)"
  [ "$rama" = "$RAMA_ESPERADA" ] || fatal \
    "el repositorio ${nombre} esta en '${rama}' y se esperaba '${RAMA_ESPERADA}'. Publicar desde otra rama deja el sitio sin cambios y el flujo anunciando exito."
  echo "    ${nombre}: rama ${rama}"
done

# P2 · arbol rastreado limpio: un refresh sobre cambios a medio hacer los publica.
if [ "$ALLOW_DIRTY" -eq 0 ]; then
  for par in "principal:${REPO_ROOT}" "dashboard:${DASHBOARD_ROOT}"; do
    nombre="${par%%:*}"; ruta="${par#*:}"
    if [ -n "$(git -C "$ruta" status --porcelain --untracked-files=no)" ]; then
      git -C "$ruta" status --short --untracked-files=no >&2
      fatal "el repositorio ${nombre} tiene cambios rastreados sin confirmar. Confirmalos o usa --allow-dirty si sabes lo que haces."
    fi
  done
  echo "    ambos arboles rastreados: limpios"
fi

# P3 · upstream configurado y sin divergencia: publicar sobre un remoto adelantado falla tarde.
for par in "principal:${REPO_ROOT}" "dashboard:${DASHBOARD_ROOT}"; do
  nombre="${par%%:*}"; ruta="${par#*:}"
  git -C "$ruta" rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1 \
    || fatal "el repositorio ${nombre} no tiene upstream configurado en ${RAMA_ESPERADA}"
  git -C "$ruta" fetch --quiet origin "$RAMA_ESPERADA"
  detras="$(git -C "$ruta" rev-list --count "HEAD..origin/${RAMA_ESPERADA}")"
  echo "    ${nombre}: ${detras} commit(s) por detras del remoto"
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
if [ -n "$bloquean" ]; then
  echo "$bloquean" | sed 's/^/      /' >&2
  fatal "hay archivos sin versionar en rutas que este flujo descarga. La descarga los retiraria. Versionalos o muevelos antes de continuar."
fi
echo "    ninguna ruta de descarga en riesgo"

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
  if [ "${ALLOW_EXTRA_DISEASES:-0}" != "1" ]; then
    fatal "el consolidado contiene padecimientos fuera de la lista autorizada (${lista_extras}). Versionarlo los sube al almacenamiento remoto. Declara ALLOW_EXTRA_DISEASES=1 si es lo que quieres."
  fi
  echo "    ALLOW_EXTRA_DISEASES=1: se versionaran tambien"
fi

echo ""
echo ">>> PREFLIGHT COMPLETO"

# ─────────────────────────────────────────────────────────────────────
# 2. PREPARAR — datos y computo. No publica.
# ─────────────────────────────────────────────────────────────────────
_semana_de() { tail -1 "$CONSOLIDADO" | cut -d',' -f1,2; }
ANTES="$(_semana_de)"

paso "[1/10] Traer commits de datos del flujo automatizado"
# --ff-only: si el remoto divergio, aborta en vez de fabricar un merge.
git pull --ff-only origin "$RAMA_ESPERADA"

paso "[2/10] Descargar los objetivos DVC necesarios"
# Dirigido y sin forzar: no puede retirar nada que no este en estos punteros.
dvc pull "${CONSOLIDADO}.dvc" data/raw_PDFs.dvc

ULTIMA="$(_semana_de)"
ANIO="$(echo "$ULTIMA" | cut -d',' -f1)"
SEM="$(echo "$ULTIMA" | cut -d',' -f2)"
echo "    Consolidado: $(wc -l < "$CONSOLIDADO") filas | ultima semana neuro: ${ANIO}/sem${SEM}"

# ── Dengue: vive en una tabla aparte del boletin (Cuadro 7.2) y su extractor
#    puede romperse si cambia el layout del PDF. Se declara best-effort a
#    proposito, pero el resultado se registra en el manifiesto y se informa al
#    final; nunca se silencia.
paso "[3/10] Dengue: extract -> merge -> prep (best-effort declarado)"
DENGUE_OK=1
if ! ( set -e
       make dengue-extract ARGS="--incremental"
       make dengue-merge
       make dengue-prep ); then
  DENGUE_OK=0
  echo "    !! Dengue extract/merge/prep fallo (¿layout del boletin?). Se continua con el Dengue previo."
fi

paso "[4/10] Reseleccion de motor productivo en 2026 real"
# tabla-produccion (backtest CV de los 333 modelos, ~19 min) NO corre cada semana:
# sus metricas CV dependen solo del historico y de los modelos CONGELADOS, no del
# boletin nuevo. Para refrescarlo tras reentrenar: RETRAIN=1 make update-week-apply
if [ "${RETRAIN:-0}" = "1" ] || [ ! -f reports/ProdDetails/tabla_333_modelos_produccion.xlsx ]; then
  echo "    (RETRAIN=1 o tabla ausente) -> regenerando backtest CV..."
  make tabla-produccion
else
  echo "    (refresh) se reutiliza el backtest CV existente; solo se re-scorea 2026."
fi
$PYTHON scripts/reselect_motor_2026.py

paso "[5/10] Tableau + validacion semanal"
$PYTHON scripts/build_tableau.py
$PYTHON scripts/genera_validacion_semanal.py
cp reports/ProdDetails/validacion_semanal.html "$DASHBOARD_ROOT/validacion_semanal.html"

paso "[6/10] Galeria neuro (graficos + zoom_data_neuro.json)"
$PYTHON -m scripts.build_neuro_gallery --out "$REPORTS"

paso "[7/10] Dengue: produccion + web"
if [ "$DENGUE_OK" -eq 1 ] || [ -f reports/forecasts/nbglm/all_forecast_nbglm.csv ]; then
  make dengue-produccion
  make dengue-web
else
  echo "    !! Se omite Dengue web (sin datos/forecast NBGLM). Revisa make dengue-pipeline manual."
fi

# El zoom del EpiBot fusiona neuro + Dengue: DESPUES de dengue-web para que no
# quede desfasado con el Dengue anterior.
paso "[8/10] Zoom del EpiBot (neuro + Dengue fresco)"
$PYTHON scripts/build_epibot_zoom.py --reports "$REPORTS" --out "$EPIBOT"

paso "[9/10] Knowledge.json del EpiBot"
$PYTHON scripts/build_web_knowledge.py
cp web_dashboard/knowledge.json "${EPIBOT}/knowledge.json"

paso "[10/10] Barra de fechas + Novedades de la landing"
$PYTHON scripts/actualiza_barra_fechas.py \
  --index "${REPORTS}/index.html" \
  --zoom  "${REPORTS}/zoom_data_neuro.json"
$PYTHON scripts/build_news_weekly.py --dashboard "$DASHBOARD_ROOT"

# ─────────────────────────────────────────────────────────────────────
# 3. MANIFIESTO — que cambiaria, antes de decidir publicarlo
# ─────────────────────────────────────────────────────────────────────
paso "MANIFIESTO DE CAMBIOS"
mkdir -p "$MANIFEST_DIR"
MANIFEST="${MANIFEST_DIR}/refresh_$(date +%Y%m%d_%H%M%S).txt"
{
  echo "modo                 ${MODE}"
  echo "fecha                $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "semana antes         ${ANTES}"
  echo "semana despues       ${ANIO},${SEM}"
  echo "dengue               $([ "$DENGUE_OK" -eq 1 ] && echo ok || echo 'fallo, se conservo el previo')"
  echo "padecimientos        $(echo "$extras" | grep '^PRESENTES:' | sed 's/^PRESENTES://')"
  echo ""
  echo "== repositorio principal (rastreado) =="
  git -C "$REPO_ROOT" status --short --untracked-files=no || true
  echo ""
  echo "== dashboard (rastreado) =="
  git -C "$DASHBOARD_ROOT" status --short --untracked-files=no || true
} | tee "$MANIFEST"
echo ""
echo "    manifiesto -> ${MANIFEST}"

if [ "$MODE" != "apply" ]; then
  echo ""
  echo ">>> MODO EN SECO: no se versiono ni publico nada."
  echo "    Los artefactos locales SI se regeneraron; revisa el manifiesto de arriba."
  echo "    Para publicar:  make update-week-apply"
  [ "$DENGUE_OK" -eq 0 ] && echo "    NOTA: Dengue quedo en su version previa."
  exit 0
fi

# ─────────────────────────────────────────────────────────────────────
# 4. PUBLICAR — solo con --apply
# ─────────────────────────────────────────────────────────────────────
paso "PUBLICAR · dashboard"
# Cache-bust: el EpiBot carga knowledge.json con ?v=DATA_VERSION. Sin subirlo, el
# navegador sirve el knowledge.json anterior tras cada refresh.
_DV_TODAY="$(date +%Y%m%d)"
if [ -f "${DASHBOARD_ROOT}/epibot/js/kb.js" ]; then
  perl -i -pe "s/const DATA_VERSION = '[0-9]+';/const DATA_VERSION = '${_DV_TODAY}';/" \
    "${DASHBOARD_ROOT}/epibot/js/kb.js"
  echo "    cache-bust: DATA_VERSION -> ${_DV_TODAY}"
fi
git -C "$DASHBOARD_ROOT" add Reports/ epibot/ validacion_semanal.html news.json index.html novedades.html
if git -C "$DASHBOARD_ROOT" diff --cached --quiet; then
  echo "    Dashboard sin cambios."
else
  git -C "$DASHBOARD_ROOT" commit -q -m "reports+epibot: refresh semanal sem ${SEM}/${ANIO} (galeria, zoom, knowledge, barra de fechas, novedades)"
  git -C "$DASHBOARD_ROOT" push
  echo "    Dashboard publicado."
fi

paso "PUBLICAR · repositorio principal"
# Sin `|| true`: si el versionado falla, el flujo debe detenerse, no seguir y
# confirmar punteros que no corresponden a lo que hay en el almacenamiento.
dvc add "$CONSOLIDADO" models reports/forecasts
dvc push
git add "${CONSOLIDADO}.dvc" models.dvc reports/forecasts.dvc reports/ProdDetails/
if git diff --cached --quiet; then
  echo "    Repo principal sin cambios."
else
  _msg="data/prod: refresh semanal sem ${SEM}/${ANIO} (consolidado, tablas, validacion)"
  # El hook reformatea validacion_semanal.html y aborta el primer intento;
  # se re-agrega y se reintenta UNA vez con el archivo ya corregido.
  git commit -q -m "$_msg" \
    || { git add "${CONSOLIDADO}.dvc" reports/ProdDetails/; git commit -q -m "$_msg"; }
  git push origin "$RAMA_ESPERADA"
  echo "    Repo principal publicado."
fi

echo ""
echo ">>> REFRESH SEMANAL PUBLICADO (sem ${SEM}/${ANIO}). Dengue_OK=${DENGUE_OK}."
echo "    manifiesto: ${MANIFEST}"
[ "$DENGUE_OK" -eq 0 ] && echo "    NOTA: Dengue quedo en su version previa; corre 'make dengue-pipeline' a mano."
exit 0
