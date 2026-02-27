#!/bin/bash
# scripts/imss.sh
# Sincronización rápida IMSS: desactiva ambientes, activa integrador, pull código y datos
# Uso: source scripts/imss.sh

echo "══════════════════════════════════════════════════════════"
echo ">>> [1/4] Desactivando ambientes virtuales previos..."
echo "══════════════════════════════════════════════════════════"

# Desactivar conda si está activo
if command -v conda &> /dev/null && [ "${CONDA_SHLVL:-0}" -gt 0 ]; then
    # Desactivar todos los ambientes conda (incluyendo base)
    for i in $(seq ${CONDA_SHLVL} -1 1); do
        conda deactivate 2>/dev/null
    done
fi

# Desactivar venv si está activo
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate 2>/dev/null
fi

echo ">>> [2/4] Activando entorno del proyecto (.venv)..."
source .venv/bin/activate

echo ">>> [3/4] Sincronizando código desde GitHub..."
git pull origin main

echo ">>> [4/4] Sincronizando datos desde S3..."
# Limpiar .DS_Store antes de dvc pull (macOS los genera y bloquean DVC)
find . -name ".DS_Store" -delete 2>/dev/null
dvc pull --force

echo "══════════════════════════════════════════════════════════"
echo ">>> ✅ Sincronización IMSS completada."
echo ">>> Entorno activo: $VIRTUAL_ENV"
echo "══════════════════════════════════════════════════════════"
