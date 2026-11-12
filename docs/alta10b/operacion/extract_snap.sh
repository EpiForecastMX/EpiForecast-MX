#!/bin/bash
# Extracción aislada sobre un snapshot congelado. Uso: extract_snap.sh <pasada> <sha> <id>...
# - worktree detached propio (snap/<pasada>) al commit <sha>; su data/interim es exclusivo de la
#   pasada (ningún otro extractor escribe ahí); no se edita nunca.
# - registra sha256 de config (cuadros.yaml, padecimientos.yaml) al inicio y al final de cada id;
#   si cambian, la corrida es inválida.
# - antes de cada id aparta (no borra) un output previo del mismo id, renombrado con su sha256.
# - valida el manifiesto: cubre exactamente el inventario de PDF del corte (sin duplicados ni omisiones), estados sólo ok/excluded, excluidos = source_exclusions exactas
#   del id (sin keep_period no hay fila; con keep_period sí), y que el CSV es fresco (mtime > inicio).
# - escribe extract/<pasada>/<id>_RUN.json (scripts/valida_extraccion.py) con todo lo anterior y el veredicto.
# - candado por snapshot: dos extractores no comparten su data/interim.
set -u
P=$1; SHA=$(git -C /tmp/epiforecast-alta10b-20261112/wt-be rev-parse "$2^{commit}") || exit 1; shift 2
B=/tmp/epiforecast-alta10b-20261112
S=$B/snap/$P
PY=/Users/haowei/Documents/Integrador/EpiForecast-MX/.venv/bin/python
mkdir -p $B/snap $B/extract/$P
if [ ! -d $S ]; then git -C $B/wt-be worktree add --detach $S $SHA > $B/logs/snap_$P.log 2>&1 || { echo "worktree FALLA" >> $B/logs/extract_$P.status; exit 1; }; fi
[ "$(git -C $S rev-parse HEAD)" = "$(git -C $B/wt-be rev-parse $SHA)" ] || { echo "snapshot no está en $SHA" >> $B/logs/extract_$P.status; exit 1; }
[ -z "$(git -C $S status --short)" ] || { echo "snapshot sucio" >> $B/logs/extract_$P.status; exit 1; }
cd $S; export PYTHONPATH=$S/src:$S
# un solo extractor por snapshot: el data/interim de la pasada no se comparte
mkdir $S/.lock_extract 2>/dev/null || { echo "snapshot $P ocupado por otro extractor" >> $B/logs/extract_$P.status; exit 1; }
trap 'rmdir $S/.lock_extract' EXIT
cfg() { shasum -a 256 config/data/cuadros.yaml config/padecimientos.yaml | cut -c1-64 | tr '\n' ' '; }
for id in "$@"; do
  mkdir -p data/interim
  for f in data/interim/${id}_boletin.csv data/interim/${id}_extraccion_manifest.csv; do
    [ -f $f ] && mv $f data/interim/apartado_$(shasum -a 256 $f | cut -c1-12)_$(basename $f)
  done
  c0=$(cfg); t0=$(date +%s); i0=$(date -u +%FT%TZ)
  $PY -m scripts.extrae_cuadro --disease $id --pdf-dir $B/pdfs --jobs 8 > $B/logs/extract_${P}_${id}.log 2>&1; rc=$?
  c1=$(cfg); i1=$(date -u +%FT%TZ)
  # M5: un RUN.json previo de este id se aparta (no se borra) antes de validar; la copia se comprueba
  for f in $B/extract/$P/${id}_RUN.json $B/extract/$P/${id}_boletin.csv $B/extract/$P/${id}_extraccion_manifest.csv; do
    [ -f $f ] && mv $f $(dirname $f)/apartado_$(shasum -a 256 $f | cut -c1-12)_$(basename $f)
  done
  cp data/interim/${id}_boletin.csv data/interim/${id}_extraccion_manifest.csv $B/extract/$P/ || echo "$id cp FALLA" >> $B/logs/extract_$P.status
  $PY $B/scripts/valida_extraccion.py "$id" "$rc" "$t0" "$c0" "$c1" "$i0" "$i1" "$SHA" "$P" "$B/extract/$P" "$B/pdfs" >> $B/logs/extract_$P.status || echo "$id validador rc=$? (RUN.json no válido)" >> $B/logs/extract_$P.status
  # el CSV copiado debe ser el que el validador registró
  $PY -c "import json,hashlib,sys;r=json.load(open('$B/extract/$P/${id}_RUN.json'));h=hashlib.sha256(open('$B/extract/$P/${id}_boletin.csv','rb').read()).hexdigest();sys.exit(0 if r['csv_sha256']==h else 1)" 2>/dev/null \
    || echo "$id copia distinta de lo validado" >> $B/logs/extract_$P.status
done
echo DONE >> $B/logs/extract_$P.status
