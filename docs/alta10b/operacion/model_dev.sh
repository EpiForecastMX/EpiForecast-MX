#!/bin/bash
# Desarrollo SIN abrir 2025: validate-data -> smoke -> (sólo si smoke succeeded) full -> select.
# Uso: model_dev.sh <id> <pass_raw>   (pass_raw: carpeta de extract/ con el raw ya verificado ×2)
set -u
id=$1; P=$2
B=/tmp/epiforecast-alta10b-20261112
cd $B/wt-be
export PYTHONPATH=$PWD/src:$PWD
PY=/Users/haowei/Documents/Integrador/EpiForecast-MX/.venv/bin/python
L=$B/model/$id; mkdir -p $L
[ -z "$(git status --short --untracked-files=no)" ] || { echo "ARBOL SUCIO"; exit 9; }
pol=$($PY -c "from epiforecast import registry;print(registry.require('$id').selection_policy)")
if [ "$pol" = "rolling_cv_v1" ]; then ENG="--engines seasonal_naive_lag52,seasonal_mean_3y,seasonal_median_3y,seasonal_mean_5y,seasonal_median_5y,ets_add_damped_log1p,ridge_harmonic_log1p"; else
  ALTA10B_BASE=$B $PY $B/scripts/autoridad.py politica "$id" "$pol" >> $L/registro.txt || { echo "POLITICA $pol SIN AUTORIZACIÓN ESTRUCTURADA ($id)"; exit 4; }; ENG=""; fi
ak=$($PY -c "from epiforecast import registry;print(registry.require('$id').artifact_key)")
SRC=$B/extract/$P/${id}_boletin.csv
[ -f $SRC ] || { echo "SIN RAW $SRC"; exit 3; }
# M5: el raw que se modela debe ser el validado. Con la pasada «canon» se exige RAW.json y su sha256.
[ "$P" = "canon" ] || { echo "M5: sólo se modela el raw canónico validado (extract/canon + RAW.json)"; exit 3; }
if [ "$P" = "canon" ]; then
  esp=$($PY -c "import json;print(json.load(open('$B/extract/canon/${id}_RAW.json'))['raw_sha256'])" 2>/dev/null) || { echo "SIN RAW.json canónico"; exit 3; }
  [ "$(shasum -a 256 $SRC | cut -c1-64)" = "$esp" ] || { echo "RAW canónico distinto de lo validado"; exit 3; }
fi
cp $SRC data/raw/data_raw_${ak}.csv || { echo "cp FALLA"; exit 3; }
[ "$(shasum -a 256 data/raw/data_raw_${ak}.csv | cut -c1-64)" = "$(shasum -a 256 $SRC | cut -c1-64)" ] || { echo "raw copiado distinto"; exit 3; }
echo "$(date -u +%FT%TZ) raw=$(shasum -a 256 data/raw/data_raw_${ak}.csv | cut -c1-64) pol=$pol head=$(git rev-parse --short HEAD)" >> $L/registro.txt
$PY -m scripts.disease_run validate-data $id > $L/validate.log 2>&1 || { echo "validate FAIL"; exit 1; }
$PY -m scripts.disease_run benchmark $id --stage smoke $ENG > $L/smoke.log 2>&1; rc=$?
SM=$(grep -oE "${id}_benchmark_smoke_[0-9a-f]+" $L/smoke.log | tail -1)
st=$($PY -c "import json;print(json.load(open('runs/$SM/run_manifest.json'))['status'])" 2>/dev/null)
echo "smoke rc=$rc run=$SM status=$st" | tee -a $L/registro.txt
[ "$st" = "succeeded" ] || { echo "SMOKE NO SUCCEEDED: no se corre el full"; exit 2; }
$PY -m scripts.disease_run benchmark $id --stage full $ENG > $L/full.log 2>&1; rc=$?
BR=$(grep -oE "${id}_benchmark_full_[0-9a-f]+" $L/full.log | tail -1)
st=$($PY -c "import json;print(json.load(open('runs/$BR/run_manifest.json'))['status'])" 2>/dev/null)
echo "full rc=$rc run=$BR status=$st" | tee -a $L/registro.txt
[ "$st" = "succeeded" ] || exit 2
$PY -m scripts.disease_run select $id --benchmark-run $BR > $L/select.log 2>&1; rc=$?
SL=$(grep -oE "${id}_select_[0-9a-f_]+" $L/select.log | tail -1)
echo "select rc=$rc run=$SL" | tee -a $L/registro.txt
# M6: la selección vale sólo con rc 0, manifest succeeded y el mismo dataset que el benchmark full
[ "$rc" = "0" ] && [ -n "$SL" ] || { echo "SELECT FALLA"; exit 2; }
$PY - "$SL" "$BR" <<'PYEOF' || { echo "SELECT sin linaje válido"; exit 2; }
import json, sys
sl, br = sys.argv[1:]
s = json.load(open(f'runs/{sl}/run_manifest.json')); b = json.load(open(f'runs/{br}/run_manifest.json'))
ok = s['status'] == 'succeeded' and s.get('exit_code') == 0 and s['dataset_id'] == b['dataset_id'] and s.get('policy_digest') == b.get('policy_digest')
print('select ligado', ok, s['dataset_id']); sys.exit(0 if ok else 1)
PYEOF
echo "$SL" | tee -a $L/registro.txt
