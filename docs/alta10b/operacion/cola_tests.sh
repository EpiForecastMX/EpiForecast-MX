#!/bin/bash
# Recorre el orden fijo: espera la aprobación nominal de root de CADA id (no la crea), abre su única prueba y
# escribe el resultado. Se detiene con cuatro aceptados o si model_test.sh devuelve rc != 0 (sin reintento).
B=/tmp/epiforecast-alta10b-20261112; cd $B
n=4
for id in giardiasis_a071 desnutricion_severa_e40 hepatitis_a_b15 calor_t67 otras_hepatitis_b17 brucelosis_a23 reumatica_i00 bocio_e01 hepatitis_b_b16 rotavirus_a080 absceso_hepatico_a064 leptospirosis_a27; do
  n=$((n+1)); touch READY_ROOT_SIGUIENTE_$id
  until [ -f APROBACION_TEST_$id.json ] && grep -q "AUTORIZABLE_PRETEST $id\$" FABLE_PLAN_APPROVED.md; do sleep 15; done
  case $id in hepatitis_a_b15|calor_t67|otras_hepatitis_b17|reumatica_i00|hepatitis_b_b16|rotavirus_a080) P1=snapC; P2=snapD;; *) P1=snapA; P2=snapB;; esac
  bash scripts/model_test.sh $id $P1 $P2 >logs/model_test_${id}_$(date -u +%Y%m%dT%H%M%SZ).log 2>&1; rc=$?
  if [ $rc != 0 ]; then echo "- $(date -u +%FT%TZ) $id model_test rc=$rc: ALTO sin reintento (ver model/$id/registro.txt)" >> PROGRESS.md; touch ALTO_$id; exit $rc; fi
  python3 scripts/resultado_test.py $id $n > /dev/null
  echo "- $(date -u +%FT%TZ) $id: $(grep -m1 'accepted =' RESULTADO_TEST_$id.md | sed 's/.*accepted = //')  (RESULTADO_TEST_$id.md)" >> PROGRESS.md
  grep -q "accepted = True" RESULTADO_TEST_$id.md && [ "$(grep -l 'accepted = True' RESULTADO_TEST_*.md | wc -l)" -ge 4 ] && { echo "- 4 aceptados: cola terminada" >> PROGRESS.md; exit 0; }
done
