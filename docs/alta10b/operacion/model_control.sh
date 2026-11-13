#!/bin/bash
# Refit + forecast del CONTROL autorizado (A6) para <id>. No abre 2025: usa el run rechazado que nombran la
# autorización estructurada y el registry. Árbol limpio, test succeeded, accepted=false, índice antes de emitir.
set -u
id=$1
B=/tmp/epiforecast-alta10b-20261112
M=/Users/haowei/Documents/Integrador/EpiForecast-MX
cd $B/wt-be; export PYTHONPATH=$PWD/src:$PWD; PY=$M/.venv/bin/python
L=$B/model/ctrl_$id; mkdir -p $L
T=$(date -u +%Y%m%dT%H%M%SZ)   # sufijo: los logs de intentos previos no se sobrescriben
alto() { echo "ALTO: $*" | tee -a $L/registro.txt; exit "${2:-1}"; }
[ -z "$(git status --short --untracked-files=no)" ] || alto "ARBOL SUCIO" 9
TR=$($PY -c "from epiforecast import registry;print(registry.require('$id').acceptance_fallback_run)")
[ -n "$TR" ] && [ "$TR" != "None" ] || alto "sin acceptance_fallback_run en el registry" 5
ALTA10B_BASE=$B $PY $B/scripts/autoridad.py control "$id" "$TR" >> $L/registro.txt || alto "sin autorización estructurada de control para $TR" 5
$PY - "$TR" <<'PYEOF' || alto "el run no es un rechazo sellado y succeeded" 5
import json, sys
tr = sys.argv[1]
m = json.load(open(f'runs/{tr}/run_manifest.json')); a = json.load(open(f'runs/{tr}/acceptance.json'))
ok = m['status'] == 'succeeded' and m.get('exit_code') == 0 and a['accepted'] is False and a['provenance']['run_id'] == tr
print('rechazo sellado', ok); sys.exit(0 if ok else 1)
PYEOF
echo "refit control $id $TR commit=$(git rev-parse HEAD) $(date -u +%FT%TZ)" | tee -a $L/registro.txt
$PY -m scripts.disease_run refit $id --acceptance-run $TR > $L/refit_$T.log 2>&1; rc=$?
RF=$(grep -oE "${id}_refit_final_[0-9a-f_]+" $L/refit_$T.log | tail -1); echo "refit rc=$rc run=$RF" | tee -a $L/registro.txt
[ "$rc" = "0" ] && [ -n "$RF" ] || alto "refit falló" 23
$B/scripts/check_index.sh >> $L/registro.txt || alto "INDICE antes de emitir: boletín nuevo o sin red; no se emite" 7
$PY -m scripts.disease_run forecast $id --refit-run $RF --horizon 52 > $L/forecast_$T.log 2>&1; rc=$?
FC=$(grep -oE "${id}_forecast_h52_[0-9a-f_]+" $L/forecast_$T.log | tail -1); echo "forecast rc=$rc run=$FC" | tee -a $L/registro.txt
[ "$rc" = "0" ] && [ -n "$FC" ] || alto "forecast falló" 24
# los manifiestos, no los logs: refit y forecast succeeded, mismo dataset que el rechazo, linaje exacto
$PY - "$TR" "$RF" "$FC" <<'PYEOF' || alto "refit/forecast sin manifiesto succeeded o sin linaje al rechazo" 25
import hashlib, json, sys
tr, rf, fc = sys.argv[1:]
t = json.load(open(f'runs/{tr}/run_manifest.json')); r = json.load(open(f'runs/{rf}/run_manifest.json')); f = json.load(open(f'runs/{fc}/run_manifest.json'))
prov = json.load(open(f'runs/{rf}/refit_summary.json'))['provenance']; lin = json.load(open(f'runs/{fc}/lineage.json'))
dig = hashlib.sha256(open(f'runs/{tr}/acceptance.json', 'rb').read()).hexdigest()
ok = (r['status'] == f['status'] == 'succeeded' and r.get('exit_code') == f.get('exit_code') == 0
      and r['dataset_id'] == f['dataset_id'] == t['dataset_id'] and prov['acceptance_run_id'] == tr
      and prov['acceptance_digest'] == dig and lin['refit_run_id'] == rf)
print('manifiestos y linaje', ok); sys.exit(0 if ok else 1)
PYEOF
echo "OK control: test=$TR refit=$RF forecast=$FC" | tee -a $L/registro.txt
