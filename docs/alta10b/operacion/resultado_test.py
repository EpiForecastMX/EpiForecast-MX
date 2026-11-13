"""Escribe RESULTADO_TEST_<id>.md desde el registro y los manifiestos (nunca a mano). Uso: resultado_test.py <id> <orden>"""
import csv, collections, glob, json, os, re, sys
B = '/tmp/epiforecast-alta10b-20261112'; i, n = sys.argv[1], sys.argv[2]
R = f'{B}/wt-be/runs'; reg = open(f'{B}/model/{i}/registro.txt', encoding='utf-8').read()
ab = re.findall(r'abre 2025: .*', reg)[-1]
tr = [os.path.basename(p) for p in glob.glob(f'{R}/{i}_benchmark_test_*')]; assert len(tr) == 1, tr; tr = tr[0]
m = json.load(open(f'{R}/{tr}/run_manifest.json')); a = json.load(open(f'{R}/{tr}/acceptance.json'))
L = [f'# Resultado de la prueba única de 2025: {i} (orden {n} de 16)', '', f'- {ab}',
     f'- Test {tr}: status {m["status"]}, exit_code {m.get("exit_code")}. accepted = {a["accepted"]}:']
for c in a['checks']:
    L.append(f'  - {c["scope"]} {c["portfolio"]:.2f} frente a {c["control"]:.2f} del control ({c["worse_pct"]:+.1f} %): {"pasa" if c["passed"] else "FALLA"}')
if a['accepted']:
    rf = re.findall(rf'{i}_refit_final_[0-9a-f_]+', reg)[-1]; fc = re.findall(rf'{i}_forecast_h52_[0-9a-f_]+', reg)[-1]
    sel = re.findall(rf'{i}_select_[0-9a-f_]+', reg)[-1]
    cnt = collections.Counter(r['selected_engine'] for r in csv.DictReader(open(f'{R}/{sel}/selection.csv')))
    L += [f'- Refit {rf} y forecast {fc} (manifest succeeded).',
          f'- Selección por motor en las bases: {dict(cnt)}' + (' (CONTROL_ONLY: todas lag52)' if set(cnt) == {'seasonal_naive_lag52'} else ' (portafolio real)')]
else:
    L.append('- Queda configured, sin refit ni control; no se reabre.')
open(f'{B}/RESULTADO_TEST_{i}.md', 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print('\n'.join(L))
