#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# build_patent_bundle.sh
#
# Construye un ARBOL CURADO con SOLO el codigo de la invencion (el "patent
# bundle"), dejando fuera notebooks, reportes, referencias, datos clinicos y
# binarios. Reproducible: borra y reconstruye dist/patent_bundle/ cada vez, y
# genera un MANIFEST + tarball + SHA-256 para fijar exactamente lo entregado.
#
# Uso:
#   bash scripts/build_patent_bundle.sh
#
# Salida:
#   dist/patent_bundle/                  arbol curado (~2.5 MB)
#   dist/patent_bundle/MANIFEST.txt      lista de archivos con tamanos
#   dist/epiforecast-patent-bundle.tar.gz  tarball del arbol
#   dist/epiforecast-patent-bundle.sha256  checksum del tarball
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="dist/patent_bundle"
TARBALL="dist/epiforecast-patent-bundle.tar.gz"

# Patrones que nunca deben entrar (caches, artefactos, sistema operativo).
EXCLUDES=(
  --exclude '__pycache__' --exclude '*.pyc' --exclude '*.pyo'
  --exclude '.DS_Store'   --exclude '.pytest_cache' --exclude '.ruff_cache'
  --exclude '*.ckpt'      --exclude '*.pkl'  --exclude '*.log'
  --exclude 'oneoff'      # scripts/oneoff: scripts de un solo uso, fuera del invento
)

echo "→ Limpiando $OUT"
rm -rf "$OUT"
mkdir -p "$OUT"

# ── Directorios del invento (codigo + config + pruebas) ───────────────────────
for d in src scripts config epi_modules tests; do
  echo "→ Copiando $d/"
  rsync -a "${EXCLUDES[@]}" "$d/" "$OUT/$d/"
done

# ── Documentacion tecnica curada (solo lo relevante a la invencion) ───────────
mkdir -p "$OUT/docs/model_cards" "$OUT/docs/research"
rsync -a "${EXCLUDES[@]}" docs/model_cards/ "$OUT/docs/model_cards/"
cp docs/research/INFORME_ARQUITECTURA_MULTIMODELO.md "$OUT/docs/research/" 2>/dev/null || true

# ── Archivos raiz (build, dependencias, licencia, contrato de calidad) ────────
for f in pyproject.toml requirements.txt Makefile README.md LICENSE \
         .pre-commit-config.yaml .python-version epi.py; do
  [ -f "$f" ] && cp "$f" "$OUT/$f"
done

# La documentacion del bundle (bilingue + diagrama) se versiona aparte y se copia.
[ -f docs/PATENT_BUNDLE_README.md ] && cp docs/PATENT_BUNDLE_README.md "$OUT/README_BUNDLE.md"

# ── Manifiesto + checksum reproducible ────────────────────────────────────────
echo "→ Generando MANIFEST.txt"
( cd "$OUT" && find . -type f -not -name MANIFEST.txt | sort \
    | while read -r p; do printf "%10s  %s\n" "$(wc -c <"$p")" "${p#./}"; done ) \
  > "$OUT/MANIFEST.txt"

NFILES=$(grep -c . "$OUT/MANIFEST.txt" || true)
SIZE=$(du -sh "$OUT" | cut -f1)

echo "→ Empaquetando $TARBALL"
tar -czf "$TARBALL" -C dist patent_bundle
shasum -a 256 "$TARBALL" | tee "dist/epiforecast-patent-bundle.sha256"

echo
echo "✓ Bundle listo: $OUT  ($NFILES archivos, $SIZE)"
echo "  Tarball: $TARBALL"
