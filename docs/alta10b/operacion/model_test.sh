#!/bin/bash
# Abre 2025 UNA vez para <id>; si se acepta, refit + forecast. Uso: model_test.sh <id> <pass1> <pass2>
#
# Guardas (FABLE_PRETEST_LEVE_REVISION.md, P1-P7; ROOT_FEEDBACK.md):
#  P1 aprobación NOMINAL: FABLE_PLAN_APPROVED.md con la línea exacta «AUTORIZABLE_PRETEST <id>» y
#     APROBACION_TEST_<id>.json con id, dataset_id, raw_sha256, selection_policy y selection_run que
#     deben coincidir con lo congelado. Una aprobación de un id no habilita otro.
#  P3 diff acotado vacío entre el commit de la selección y HEAD (núcleo) y entradas de config del id
#     y de su grupo de cuadro idénticas; A3: además el snapshot de extracción contra HEAD (config_efectiva.py).
#  P4 pass1 = pass2 = raw, ambas con RUN.json válido del mismo snapshot, dataset de la selección = dataset del raw actual, digest config igual.
#  P5 índice oficial consultado en esta ejecución (43 adjuntos, último 43).
#  P6 ninguna apertura previa de 2025 (salida guardada).
#  P7 una sola apertura: rc != 0, manifest no succeeded o sin acceptance.json -> se detiene y
#     reporta; sin reintentos. Igual para refit y forecast (exit + manifest succeeded).
set -u
id=$1; P1=$2; P2=$3
B=/tmp/epiforecast-alta10b-20261112
M=/Users/haowei/Documents/Integrador/EpiForecast-MX
cd $B/wt-be
export PYTHONPATH=$PWD/src:$PWD
PY=$M/.venv/bin/python
L=$B/model/$id
AP=$B/APROBACION_TEST_$id.json
alto() { echo "ALTO: $*" | tee -a $L/registro.txt; exit "${2:-1}"; }

# --- P1 aprobación nominal ---------------------------------------------------------------
[ -z "$(git status --short --untracked-files=no)" ] || alto "ARBOL SUCIO" 9
pol=$($PY -c "from epiforecast import registry;print(registry.require('$id').selection_policy)")
[ "$pol" = "rolling_cv_v1" ] || ALTA10B_BASE=$B $PY $B/scripts/autoridad.py politica "$id" "$pol" >> $L/registro.txt \
    || alto "POLITICA $pol SIN AUTORIZACIÓN ESTRUCTURADA (autorizaciones/*.json)" 4
ak=$($PY -c "from epiforecast import registry;print(registry.require('$id').artifact_key)")
SEL=$(grep -oE "${id}_select_[0-9a-f_]+" $L/select.log | tail -1); [ -n "$SEL" ] || alto "sin selección" 5
hr=$(shasum -a 256 data/raw/data_raw_${ak}.csv | cut -c1-64)
DS=$($PY -c "import json;print(json.load(open('runs/$SEL/run_manifest.json'))['dataset_id'])")
SC=$($PY -c "import json;print(json.load(open('runs/$SEL/run_manifest.json'))['code_commit'])")
$PY $B/scripts/guarda_aprobacion.py $B/FABLE_PLAN_APPROVED.md $AP "$id" "$DS" "$hr" "$pol" "$SEL" \
    || alto "APROBACION NOMINAL ausente o distinta de la identidad congelada" 10

# --- P4 identidad -------------------------------------------------------------------------
h1=$(shasum -a 256 $B/extract/$P1/${id}_boletin.csv | cut -c1-64); h2=$(shasum -a 256 $B/extract/$P2/${id}_boletin.csv | cut -c1-64)
[ "$h1" = "$h2" ] && [ "$h1" = "$hr" ] || alto "DETERMINISMO/RAW NO VERIFICADO $h1 $h2 $hr" 8
# las dos pasadas deben venir de extract_snap.sh: snapshot congelado, 670 PDF, sólo ok/excluded,
# excluidos = declarados, CSV fresco y config sin cambios durante la corrida (RUN.json válido)
for PP in $P1 $P2; do
  $PY -c "import json,sys;r=json.load(open('$B/extract/$PP/${id}_RUN_v2.json'));pin=open('$B/scripts/VALIDADOR.sha256').read().split()[0];sys.exit(0 if r['valida'] and r['csv_sha256']=='$hr' and r['validador']['sha256']==pin and len(r['snapshot_sha'])==40 else 1)" 2>/dev/null \
    || alto "PASADA $PP sin RUN.json válido o con otro CSV (manifiesto/snapshot no verificado)" 8
done
S1=$($PY -c "import json;print(json.load(open('$B/extract/$P1/${id}_RUN_v2.json'))['snapshot_sha'])"); S2=$($PY -c "import json;print(json.load(open('$B/extract/$P2/${id}_RUN_v2.json'))['snapshot_sha'])")
[ "$S1" = "$S2" ] || alto "pasadas en snapshots distintos $S1 $S2" 8
# A3: la config efectiva del id (grupo con exclusiones, registry, extractor) debe ser la misma en el
# snapshot de extracción, en el commit de la selección y en HEAD; source_exclusions no entra en el digest
$PY $B/scripts/config_efectiva.py $B/wt-be $S1 HEAD "$id" >> $L/registro.txt 2>&1 || alto "A3: snapshot $S1 con config del id distinta de HEAD" 11
$PY $B/scripts/config_efectiva.py $B/wt-be $SC HEAD "$id" seleccion >> $L/registro.txt 2>&1 || alto "A3: selección ($SC) con config del id distinta de HEAD" 11
CFG0=$($PY -c "import json;print(json.load(open('runs/$DS/dataset_manifest.json'))['digests']['config'])" 2>/dev/null \
    || grep -oE '"config": "[0-9a-f]{64}"' runs/$DS/dataset_manifest.json | head -1 | grep -oE '[0-9a-f]{64}')
$PY -m scripts.disease_run validate-data $id > $L/validate_pretest.log 2>&1 || alto "validate FAIL" 1
DS2=$(grep -oE "${id}_[0-9a-f]{12}" $L/validate_pretest.log | head -1)
[ "$DS" = "$DS2" ] || alto "DATASET CAMBIÓ: selección $DS, raw actual $DS2" 7
CFG1=$(grep -oE '"config": "[0-9a-f]{64}"' runs/$DS2/dataset_manifest.json | head -1 | grep -oE '[0-9a-f]{64}')
[ -n "$CFG0" ] && [ "$CFG0" = "$CFG1" ] || alto "DIGEST CONFIG CAMBIÓ $CFG0 $CFG1" 7

# --- P3 diff acotado ----------------------------------------------------------------------
git diff --stat $SC..HEAD -- config/evaluation config/engines src/epiforecast/runner \
    'src/epiforecast/data/epi_*.py' config/exposicion.yaml config/geografia > $L/P3_diff_core_pretest.txt
[ ! -s $L/P3_diff_core_pretest.txt ] || alto "P3: núcleo cambió desde $SC (ver P3_diff_core_pretest.txt)" 11
# la entrada del id y su grupo se comparan por fase (config_efectiva.py seleccion, arriba en A3):
# un cambio sólo editorial (web, lifecycle) no invalida; política, motores, exposición o fuente sí

# --- P5 índice ----------------------------------------------------------------------------
$B/scripts/check_index.sh || alto "INDICE: boletín nuevo o sin red" 7

# --- P6 apertura previa -------------------------------------------------------------------
{ ls $M/runs runs 2>/dev/null; find /tmp /private/tmp /Users/haowei/Documents/Integrador/planes \
    -maxdepth 6 -type d -name "${id}_benchmark_test_*" 2>/dev/null; } | grep "${id}_benchmark_test_" \
    > $L/P6_busqueda_pretest.txt
prev=$(wc -l < $L/P6_busqueda_pretest.txt | tr -d ' ')
[ "$prev" = "0" ] || alto "2025 YA ABIERTO ($prev coincidencias)" 6

# nivel 2024 -> 2025 registrado ANTES de abrir
$PY - <<PYEOF | tee -a $L/registro.txt
import pandas as pd
d=pd.read_csv('data/raw/data_raw_${ak}.csv'); d['Casos_semana']=pd.to_numeric(d['Casos_semana'],errors='coerce')
a=d.groupby('Anio')['Casos_semana'].sum()
print('nivel_antes_de_abrir', {int(y):int(a[y]) for y in range(2019,2026) if y in a.index})
PYEOF

# --- apertura única (P7) ------------------------------------------------------------------
manifest_ok() { $PY -c "import json,sys;m=json.load(open('runs/$1/run_manifest.json'));sys.exit(0 if m['status']=='succeeded' and m.get('exit_code')==0 else 1)" 2>/dev/null; }
echo "abre 2025: $id sel=$SEL ds=$DS raw=$hr commit=$(git rev-parse HEAD) $(date -u +%FT%TZ)" | tee -a $L/registro.txt
$PY -m scripts.disease_run benchmark $id --stage test --selection $SEL > $L/test.log 2>&1; rc=$?
echo "test rc=$rc" | tee -a $L/registro.txt
TR=$(grep -oE "${id}_benchmark_test_[0-9a-f_]+" $L/test.log | tail -1); echo "test_run=$TR" | tee -a $L/registro.txt
[ "$rc" = "0" ] || alto "test rc=$rc: se detiene sin reintento (P7)" 20
[ -n "$TR" ] && [ -f runs/$TR/acceptance.json ] || alto "test sin acceptance.json: se detiene sin reintento (P7)" 21
manifest_ok $TR || alto "test: manifest no succeeded (P7)" 22
$PY -c "
import json;a=json.load(open('runs/$TR/acceptance.json'));print('accepted=',a['accepted']);[print(c['scope'],round(c['portfolio'],2),'vs',round(c['control'],2),'worse%',round(c['worse_pct'],1),'ok' if c['passed'] else 'FALLA') for c in a['checks']]" | tee -a $L/registro.txt
acc=$($PY -c "import json;print(json.load(open('runs/$TR/acceptance.json'))['accepted'])")
[ "$acc" = "True" ] || { echo "RECHAZADO: queda configured, run conservado, sin refit ni control" | tee -a $L/registro.txt; exit 0; }
$PY -m scripts.disease_run refit $id --acceptance-run $TR > $L/refit.log 2>&1; rc=$?
RF=$(grep -oE "${id}_refit_final_[0-9a-f_]+" $L/refit.log | tail -1); echo "refit rc=$rc refit_run=$RF" | tee -a $L/registro.txt
[ "$rc" = "0" ] && [ -n "$RF" ] && manifest_ok $RF || alto "refit falló (rc=$rc, run=$RF): se detiene" 23
$PY -m scripts.disease_run forecast $id --refit-run $RF --horizon 52 > $L/forecast.log 2>&1; rc=$?
FC=$(grep -oE "${id}_forecast_h52_[0-9a-f_]+" $L/forecast.log | tail -1); echo "forecast rc=$rc forecast_run=$FC" | tee -a $L/registro.txt
[ "$rc" = "0" ] && [ -n "$FC" ] && manifest_ok $FC || alto "forecast falló (rc=$rc, run=$FC): se detiene" 24
echo "OK aceptado: test=$TR refit=$RF forecast=$FC" | tee -a $L/registro.txt
