#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# actualiza_semanal.sh
# Flujo semanal: baja boletin nuevo del CI, regenera knowledge.json
# y actualiza el dashboard.
#
# Uso:
#   make update-week
#   # o directamente:
#   bash scripts/actualiza_semanal.sh
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DASHBOARD_ROOT="/Users/haowei/Documents/Integrador/EpiForecast-IMSS-Dashboard"
PYTHON="${REPO_ROOT}/.venv/bin/python"

cd "$REPO_ROOT"

echo ">>> [1/5] Git pull (traer commits del CI scraper)..."
git pull origin main

echo ">>> [2/5] DVC pull --force (descargar PDFs y dataset nuevos)..."
dvc pull --force

# Detectar ultima semana en el dataset
ULTIMA=$(tail -1 data/processed/dataset_boletin_epidemiologico.csv | cut -d',' -f1,2)
ANIO=$(echo "$ULTIMA" | cut -d',' -f1)
SEM=$(echo "$ULTIMA" | cut -d',' -f2)
TOTAL=$(wc -l < data/processed/dataset_boletin_epidemiologico.csv)
echo "    Dataset: ${TOTAL} filas, ultima semana: ${ANIO}/sem${SEM}"

echo ">>> [3/5] Regenerar knowledge.json..."
$PYTHON scripts/build_web_knowledge.py

echo ">>> [4/5] Copiar knowledge.json al dashboard..."
cp web_dashboard/knowledge.json "${DASHBOARD_ROOT}/epibot/knowledge.json"

echo ">>> [5/5] Commit y push en dashboard..."
cd "$DASHBOARD_ROOT"
git add epibot/knowledge.json
if git diff --cached --quiet; then
    echo "    Sin cambios en knowledge.json, nada que commitear."
else
    git commit -m "data: actualizar knowledge.json con datos semana ${SEM}/${ANIO}"
    git push
    echo "    Dashboard pusheado."
fi

echo ""
echo ">>> Actualizacion semanal completada (semana ${SEM}/${ANIO})."
