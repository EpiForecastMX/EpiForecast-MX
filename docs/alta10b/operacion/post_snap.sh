#!/bin/bash
# Tras dos pasadas aisladas (PA/PB, por omisión snapA/snapB): para cada id, espera ambos RUN.json; si los dos son válidos
# y el CSV es idéntico, congela el raw canónico (extract/canon/<id>_boletin.csv + RAW.json), corre el
# cotejo TOTAL por terna, y desarrollo: si ya existe un smoke de un dataset con ese mismo raw, se
# reutiliza (no se reentrena); si no, model_dev.sh (smoke 7 -> sólo si succeeded full + select).
# Si el smoke falla, diag_motores con tipo real de error. Uso: post_snap.sh <id>...
set -u
B=/tmp/epiforecast-alta10b-20261112; cd $B
PA=${PA:-snapA}; PB=${PB:-snapB}   # pasadas a comparar (env)
PY=/Users/haowei/Documents/Integrador/EpiForecast-MX/.venv/bin/python
mkdir -p extract/canon
log() { echo "$(date -u +%H:%M:%SZ) $*" >> logs/post_snap.status; }
anc() { (cd $B/wt-be && $PY -c "
import yaml;cu=yaml.safe_load(open('config/data/cuadros.yaml'))['cuadro_groups'];print(','.join(next(s['page_anchors'] for g,s in cu.items() if any(x['id']=='$1' for x in s.get('diseases',[])))))"); }
for id in "$@"; do
  until [ -f extract/$PA/${id}_RUN_v2.json ] && [ -f extract/$PB/${id}_RUN_v2.json ]; do sleep 30; done
  v=$($PY - $id $PA $PB <<'EOF'
import json, sys
i, pa, pb = sys.argv[1:4]
a = json.load(open(f'extract/{pa}/{i}_RUN_v2.json')); b = json.load(open(f'extract/{pb}/{i}_RUN_v2.json'))
pin = open('scripts/VALIDADOR.sha256').read().split()[0]
ok = (a['valida'] and b['valida'] and a['csv_sha256'] == b['csv_sha256'] and a['snapshot_sha'] == b['snapshot_sha']
      and a['validador']['sha256'] == pin == b['validador']['sha256'] and len(a['snapshot_sha']) == 40)
if ok:
    json.dump({'id': i, 'raw_sha256': a['csv_sha256'], 'snapshot_sha': a['snapshot_sha'],
               'pasadas': {pa: a, pb: b}}, open(f'extract/canon/{i}_RAW.json', 'w'), ensure_ascii=False, indent=1)
print('OK' if ok else f"NO a={a['valida']} b={b['valida']} csvA={a['csv_sha256']} csvB={b['csv_sha256']}")
EOF
)
  if [ "${v%% *}" != "OK" ]; then log "$id pasadas no concordantes: $v"; continue; fi
  # la config efectiva del id en el snapshot debe ser la de HEAD (las exclusiones no cambian el digest)
  SNAP=$($PY -c "import json;print(json.load(open('extract/canon/${id}_RAW.json'))['snapshot_sha'])")
  if ! $PY scripts/config_efectiva.py wt-be $SNAP HEAD $id >> logs/post_snap_config.log 2>&1; then
    mv extract/canon/${id}_RAW.json extract/canon/${id}_RAW_INVALIDO_config_${SNAP:0:8}.json
    log "$id snapshot ${SNAP:0:8} con config distinta de HEAD: no se congela"; continue; fi
  cp extract/$PA/${id}_boletin.csv extract/canon/${id}_boletin.csv || { log "$id cp canónico FALLA"; continue; }
  raw=$(shasum -a 256 extract/canon/${id}_boletin.csv | cut -c1-64)
  esp=$($PY -c "import json;print(json.load(open('extract/canon/${id}_RAW.json'))['raw_sha256'])")
  if [ "$raw" != "$esp" ]; then log "$id canónico ${raw:0:12} distinto de lo validado ${esp:0:12}: no se modela"; continue; fi
  (cd wt-be && PYTHONPATH=$PWD/src:$PWD $PY ../scripts/qa_total_terna.py $id ../extract/canon/${id}_boletin.csv "$(anc $id)" >> ../logs/post_snap_terna.log 2>&1)
  # ¿smoke previo sobre un dataset con exactamente este raw?
  prev=$(cd wt-be && for m in runs/${id}_benchmark_smoke_*/run_manifest.json; do [ -f "$m" ] || continue
           ds=$($PY -c "import json;print(json.load(open('$m'))['dataset_id'])"); f=runs/$ds/dataset_manifest.json
           [ -f "$f" ] && grep -q "$raw" $f && echo "$(dirname $m | cut -d/ -f2)"; done | tail -1)
  if [ -n "$prev" ]; then
    st=$($PY -c "import json;print(json.load(open('wt-be/runs/$prev/run_manifest.json'))['status'])")
    log "$id raw=${raw:0:12} canónico; smoke previo con el mismo raw: $prev ($st), no se reentrena"
    if [ "$st" = "failed" ]; then
      (cd wt-be && PYTHONPATH=$PWD/src:$PWD $PY ../scripts/diag_motores.py runs/$prev ../qa/diag_motores_$id.json > /dev/null 2>&1); log "$id diag $prev rc=$?"
      continue
    fi
    # M6: sólo se reutiliza una selección succeeded del mismo dataset que el smoke con este raw
    dsp=$($PY -c "import json;print(json.load(open('wt-be/runs/$prev/run_manifest.json'))['dataset_id'])")
    sel=$(for x in wt-be/runs/${id}_select_*/run_manifest.json; do [ -f "$x" ] || continue
            $PY -c "import json,sys;m=json.load(open('$x'));sys.exit(0 if m['status']=='succeeded' and m['dataset_id']=='$dsp' else 1)" && basename $(dirname $x); done | tail -1)
    [ -n "$sel" ] && { log "$id ya tiene selección $sel del dataset $dsp"; continue; }
  fi
  scripts/model_dev.sh $id canon > model/dev_$id.out 2>&1; rc=$?; log "$id model_dev rc=$rc ($(tail -1 model/dev_$id.out))"
  if [ $rc -eq 2 ] && grep -q "SMOKE NO SUCCEEDED" model/dev_$id.out; then
    r=$(grep -oE "${id}_benchmark_smoke_[0-9a-f]+" model/$id/smoke.log | tail -1)
    (cd wt-be && PYTHONPATH=$PWD/src:$PWD $PY ../scripts/diag_motores.py runs/$r ../qa/diag_motores_$id.json > /dev/null 2>&1); log "$id diag $r rc=$?"
  fi
done
log DONE
