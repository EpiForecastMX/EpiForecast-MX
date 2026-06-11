#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# actualiza_semanal.sh  (UNIFICADO)
#
# Refresh semanal COMPLETO tras un boletin nuevo, SIN reentrenar modelos:
# extiende el dato real, reselecciona el motor productivo, regenera las
# tablas/validacion, la galeria /reports/ (neuro + Dengue), el zoom y el
# knowledge.json del EpiBot, actualiza la barra de fechas (auto, sin
# hardcodes) y publica en el dashboard + versiona en DVC/S3.
#
# NO reentrena (eso es make train / dengue-train-*, infrecuente). Aqui los
# pronosticos quedan congelados y solo avanza la realidad: es la vista de
# validacion semanal honesta (real vs pronostico bloqueado).
#
# Uso:
#   make update-week
#   bash scripts/actualiza_semanal.sh
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DASHBOARD_ROOT="/Users/haowei/Documents/Integrador/EpiForecast-IMSS-Dashboard"
REPORTS="${DASHBOARD_ROOT}/Reports"
EPIBOT="${DASHBOARD_ROOT}/epibot"
PYTHON="${REPO_ROOT}/.venv/bin/python"
CONSOLIDADO="data/processed/dataset_boletin_epidemiologico.csv"

cd "$REPO_ROOT"

echo ">>> [1/11] Git pull (commits del CI scraper)..."
git pull origin main

echo ">>> [2/11] DVC pull --force (PDFs + dataset nuevos)..."
dvc pull --force

ULTIMA=$(tail -1 "$CONSOLIDADO" | cut -d',' -f1,2)
ANIO=$(echo "$ULTIMA" | cut -d',' -f1)
SEM=$(echo "$ULTIMA" | cut -d',' -f2)
echo "    Consolidado: $(wc -l < "$CONSOLIDADO") filas | ultima semana neuro: ${ANIO}/sem${SEM}"

# ── Dengue (best-effort): vive en una tabla aparte del boletin (Cuadro 7.2) y
#    su extractor puede romperse si cambia el layout del PDF. Si falla, NO debe
#    tumbar el refresh neuro; se avisa y se sigue con el Dengue previo.
echo ">>> [3/11] Dengue: extract -> merge -> prep (best-effort)..."
DENGUE_OK=1
set +e
(
  set -e
  make dengue-extract ARGS="--incremental"
  make dengue-merge
  # El consolidado (DVC-tracked) cambio -> versionar ANTES de commitear (push primero).
  dvc add "$CONSOLIDADO"
  dvc push
  make dengue-prep
)
if [ $? -ne 0 ]; then
  DENGUE_OK=0
  echo "    !! Dengue extract/merge fallo (¿layout del boletin?). Se continua con el Dengue previo."
fi
set -e

echo ">>> [4/11] Reseleccion de motor productivo en 2026 real..."
# tabla-produccion (backtest CV de los 333 modelos, ~19 min) NO corre cada semana:
# sus metricas CV dependen solo del historico 2014-2025 y de los modelos CONGELADOS,
# no del boletin nuevo -> son identicas hasta el proximo RETRAIN. La tabla persiste y
# reselect_motor_2026 la lee y re-scorea solo el 2026 real (barato). Para refrescar el
# backtest tras reentrenar:  RETRAIN=1 make update-week  (o make tabla-produccion).
if [ "${RETRAIN:-0}" = "1" ] || [ ! -f reports/ProdDetails/tabla_333_modelos_produccion.xlsx ]; then
  echo "    (RETRAIN=1 o tabla ausente) -> regenerando backtest CV con make tabla-produccion..."
  make tabla-produccion
else
  echo "    (refresh) se reutiliza el backtest CV existente; solo se re-scorea 2026."
fi
$PYTHON scripts/reselect_motor_2026.py

echo ">>> [5/11] Tableau + validacion semanal..."
$PYTHON scripts/build_tableau.py
$PYTHON scripts/genera_validacion_semanal.py
# La validacion_semanal.html se enlaza desde el landing y varias paginas del sitio;
# copiarla al Dashboard para que no quede stale (genera_validacion solo escribe en
# reports/ProdDetails/). Es neuro-only por diseno.
cp reports/ProdDetails/validacion_semanal.html "$DASHBOARD_ROOT/validacion_semanal.html"

echo ">>> [6/11] Galeria neuro (333 graficos + zoom_data_neuro.json)..."
$PYTHON -m scripts.build_neuro_gallery --out "$REPORTS"

echo ">>> [7/11] Dengue: produccion + web (galeria + forecast + knowledge)..."
if [ "$DENGUE_OK" -eq 1 ] || [ -f reports/forecasts/nbglm/all_forecast_nbglm.csv ]; then
  make dengue-produccion
  make dengue-web
else
  echo "    !! Se omite Dengue web (sin datos/forecast NBGLM). Revisa make dengue-pipeline manual."
fi

# El zoom del EpiBot fusiona neuro + Dengue: regenerarlo DESPUES de dengue-web
# para que no quede stale con el Dengue viejo.
echo ">>> [8/11] Zoom del EpiBot (estado x sexo, neuro + Dengue fresco)..."
$PYTHON scripts/build_epibot_zoom.py --reports "$REPORTS" --out "$EPIBOT"

echo ">>> [9/11] Knowledge.json del EpiBot -> epibot/..."
$PYTHON scripts/build_web_knowledge.py
cp web_dashboard/knowledge.json "${EPIBOT}/knowledge.json"

echo ">>> [10/11] Barra de fechas de Reports/index.html (auto, sin hardcodes)..."
$PYTHON scripts/actualiza_barra_fechas.py \
  --index "${REPORTS}/index.html" \
  --zoom  "${REPORTS}/zoom_data_neuro.json"

echo ">>> [11/11] Publicar dashboard + versionar artefactos..."
# --- Dashboard (galeria, zoom, knowledge, index.html) ---
cd "$DASHBOARD_ROOT"
git add Reports/ epibot/ validacion_semanal.html
if git diff --cached --quiet; then
  echo "    Dashboard sin cambios."
else
  git commit -q -m "reports+epibot: refresh semanal sem ${SEM}/${ANIO} (galeria, zoom, knowledge, barra de fechas)"
  git push
  echo "    Dashboard publicado."
fi

# --- Repo principal: versionar consolidado/forecasts (DVC) + tablas de produccion (git) ---
cd "$REPO_ROOT"
# Consolidado (Dengue lo cambia) + nbglm/forecasts; push ANTES de commit.
dvc add "$CONSOLIDADO" models reports/forecasts >/dev/null 2>&1 || true
dvc push
# Punteros .dvc + tablas de produccion TRACKED-EN-GIT que el refresh regenera
# (tabla_333, produccion_dengue, validacion_semanal.html, auditoria_motores).
git add "${CONSOLIDADO}.dvc" models.dvc reports/forecasts.dvc reports/ProdDetails/ 2>/dev/null || true
if git diff --cached --quiet; then
  echo "    Repo principal sin cambios."
else
  _msg="data/prod: refresh semanal sem ${SEM}/${ANIO} (consolidado, tablas, validacion)"
  # pre-commit reformatea validacion_semanal.html (whitespace) y aborta el 1er intento;
  # re-stage y reintenta una vez para incluir el archivo ya corregido por el hook.
  git commit -q -m "$_msg" \
    || { git add "${CONSOLIDADO}.dvc" reports/ProdDetails/; git commit -q -m "$_msg"; }
  git push origin main
  echo "    Repo principal publicado."
fi

echo ""
echo ">>> Refresh semanal COMPLETO (sem ${SEM}/${ANIO}). Dengue_OK=${DENGUE_OK}."
echo "    /reports/ y EpiBot actualizados; artefactos versionados en S3."
[ "$DENGUE_OK" -eq 0 ] && echo "    NOTA: Dengue quedo en su version previa; corre 'make dengue-pipeline' a mano si el boletin trae datos nuevos."
exit 0
