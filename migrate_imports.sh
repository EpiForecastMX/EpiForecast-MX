#!/bin/bash
# =============================================================================
# EpiForecast-MX — Fase 2B: Actualizar imports en src/epiforecast/
# Ejecutar desde la raíz del repo: bash scripts/migrate_imports.sh
# =============================================================================
set -e

echo "🔄 EpiForecast-MX — Fase 2B: Actualizando imports..."
echo "====================================================="
echo ""

TARGET="src/epiforecast"

# ─── Función helper para sed multiplataforma (macOS vs Linux) ─────────────────
sedi() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

# ─── 1. Import principal: config_params → utils.config ───────────────────────
echo "  [1/7] config_params → utils.config"
find "$TARGET" -name '*.py' -exec grep -l 'src\.configuraciones\.config_params' {} \; | while read f; do
    sedi 's/from src\.configuraciones\.config_params import/from src.epiforecast.utils.config import/g' "$f"
    sedi 's/from src\.configuraciones import config_params/from src.epiforecast.utils import config/g' "$f"
    sedi 's/import src\.configuraciones\.config_params/import src.epiforecast.utils.config/g' "$f"
    echo "    ✓ $f"
done

# ─── 2. directory_manager → utils.paths ──────────────────────────────────────
echo "  [2/7] directory_manager → utils.paths"
find "$TARGET" -name '*.py' -exec grep -l 'src\.utils.*directory_manager\|from src\.utils import directory_manager' {} \; | while read f; do
    # "from src.utils import directory_manager" → keep as alias for compatibility
    sedi 's/from src\.utils import directory_manager/from src.epiforecast.utils import paths as directory_manager/g' "$f"
    sedi 's/from src\.utils\.directory_manager import/from src.epiforecast.utils.paths import/g' "$f"
    echo "    ✓ $f"
done

# ─── 3. graficos → visualization.base ────────────────────────────────────────
echo "  [3/7] graficos → visualization.base"
find "$TARGET" -name '*.py' -exec grep -l 'src\.utils\.graficos' {} \; | while read f; do
    sedi 's/from src\.utils\.graficos import/from src.epiforecast.visualization.base import/g' "$f"
    echo "    ✓ $f"
done

# ─── 4. datos (helpers) → utils.dataframe_helpers ────────────────────────────
echo "  [4/7] datos (helpers) → utils.dataframe_helpers"
find "$TARGET" -name '*.py' -exec grep -l 'src\.utils\.datos' {} \; | while read f; do
    sedi 's/from src\.utils\.datos import/from src.epiforecast.utils.dataframe_helpers import/g' "$f"
    echo "    ✓ $f"
done

# ─── 5. reporte_PDF → visualization.reporters ────────────────────────────────
echo "  [5/7] reporte_PDF → visualization.reporters"
find "$TARGET" -name '*.py' -exec grep -l 'src\.utils\.reporte_PDF' {} \; | while read f; do
    sedi 's/from src\.utils\.reporte_PDF import/from src.epiforecast.visualization.reporters import/g' "$f"
    echo "    ✓ $f"
done

# ─── 6. src.extraccion.* → src.epiforecast.data.extraction.* ────────────────
echo "  [6/7] extraccion → data.extraction"
find "$TARGET" -name '*.py' -exec grep -l 'src\.extraccion' {} \; | while read f; do
    sedi 's/from src\.extraccion\.pipeline import/from src.epiforecast.data.extraction.pdf_extractor import/g' "$f"
    sedi 's/from src\.extraccion\.merge_datasets import/from src.epiforecast.data.extraction.merger import/g' "$f"
    sedi 's/from src\.extraccion\.inegi import/from src.epiforecast.data.ingestion.inegi_utils import/g' "$f"
    sedi 's/from src\.extraccion\.inegi_eda import/from src.epiforecast.visualization.inegi_plots import/g' "$f"
    sedi 's/from src\.extraccion import/from src.epiforecast.data.extraction import/g' "$f"
    echo "    ✓ $f"
done

# ─── 7. src.modelado.* → src.epiforecast.models.* ───────────────────────────
echo "  [7/7] modelado → models"
find "$TARGET" -name '*.py' -exec grep -l 'src\.modelado' {} \; | while read f; do
    sedi 's/from src\.modelado\.prophet import/from src.epiforecast.models.prophet.model import/g' "$f"
    sedi 's/from src\.modelado\.forecast import/from src.epiforecast.models.prediction import/g' "$f"
    sedi 's/from src\.modelado\.mapea_inegi import/from src.epiforecast.features.demographic import/g' "$f"
    sedi 's/from src\.modelado import/from src.epiforecast.models import/g' "$f"
    echo "    ✓ $f"
done

echo ""

# ─── Verificación: buscar imports legacy residuales ──────────────────────────
echo "🔍 Verificando imports legacy residuales en $TARGET..."
echo ""

RESIDUAL=$(grep -rn \
    -e 'from src\.configuraciones' \
    -e 'from src\.datos\.' \
    -e 'from src\.utils\.' \
    -e 'from src\.extraccion\.' \
    -e 'from src\.modelado\.' \
    "$TARGET" --include='*.py' 2>/dev/null || true)

if [ -z "$RESIDUAL" ]; then
    echo "   ✅ No quedan imports legacy — migración completa!"
else
    echo "   ⚠️  Imports legacy residuales encontrados (revisar manualmente):"
    echo "$RESIDUAL"
fi

echo ""
echo "====================================================="
echo "🎉 Fase 2B completada!"
echo ""
echo "Próximos pasos:"
echo "  1. Revisar cambios: git diff src/epiforecast/"
echo "  2. Commit: git add -A && git commit -m 'Refactor: actualizar imports a src.epiforecast (Fase 2B)'"
echo ""
