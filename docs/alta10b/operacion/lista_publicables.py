"""Lista de publicables del lote alta10b; nunca autoriza por su cuenta ni lee logs de texto.

Para cada id (subcarpetas de <base>/model/), todo se verifica en los manifiestos de <runs>:
  prueba    exactamente un <id>_benchmark_test_*; manifest succeeded con exit_code 0; acceptance.json
            cuyo provenance.run_id es ese run; dataset_id del manifest;
  aceptado  (o aceptado_control_only si el refit es sólo seasonal_naive_lag52: aceptación retrospectiva
            sin validación propia) accepted=True y un refit_final con manifest succeeded, mismo dataset, y
            refit_summary.provenance.acceptance_run_id/acceptance_digest = ese test y el sha256 de su
            acceptance.json; y un forecast_h52 con manifest succeeded, mismo dataset y
            lineage.refit_run_id = ese refit;
  control   accepted=False, autorización estructurada (scripts/autoridad.py) de control para ese
            test_run y, como un aceptado, refit y forecast succeeded ligados al rechazo (la autorización sola
            no hace publicable); se registra el archivo y su sha256;
  rechazado accepted=False sin autorización: queda configured, sin release;
  pendiente sin prueba, con varias aperturas, o con linaje incompleto (motivo explícito).
Uso: lista_publicables.py [--json salida]. Env: ALTA10B_BASE, ALTA10B_RUNS.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import autoridad  # noqa: E402

B = os.environ.get('ALTA10B_BASE', '/tmp/epiforecast-alta10b-20261112')
RUNS = os.environ.get('ALTA10B_RUNS', f'{B}/wt-be/runs')


def _j(p):
    return json.load(open(p, encoding='utf-8'))


def _ok(run):
    m = _j(f'{RUNS}/{run}/run_manifest.json')
    return m.get('status') == 'succeeded' and m.get('exit_code') == 0, m


def evaluar(i: str) -> tuple[str, dict]:
    tests = sorted(os.path.basename(p) for p in glob.glob(f'{RUNS}/{i}_benchmark_test_*'))
    if not tests:
        return 'pendiente', {'id': i, 'motivo': 'sin prueba de 2025 abierta'}
    if len(tests) > 1:
        return 'pendiente', {'id': i, 'motivo': f'varias aperturas de 2025: {tests}'}
    tr = tests[0]
    ok, mt = _ok(tr)
    acc_p = f'{RUNS}/{tr}/acceptance.json'
    if not ok or not os.path.exists(acc_p):
        return 'pendiente', {'id': i, 'motivo': f'{tr}: manifest no succeeded o sin acceptance.json'}
    acc = _j(acc_p)
    if acc.get('provenance', {}).get('run_id') != tr:
        return 'pendiente', {'id': i, 'motivo': f'{tr}: acceptance.json de otro run'}
    ds = mt['dataset_id']
    dig = hashlib.sha256(open(acc_p, 'rb').read()).hexdigest()
    refits = []
    for p in glob.glob(f'{RUNS}/{i}_refit_final_*'):
        r = os.path.basename(p); rok, rm = _ok(r)
        prov = _j(f'{p}/refit_summary.json').get('provenance', {}) if os.path.exists(f'{p}/refit_summary.json') else {}
        if rok and rm['dataset_id'] == ds and prov.get('acceptance_run_id') == tr and prov.get('acceptance_digest') == dig:
            refits.append(r)
    fcs = []
    if len(refits) == 1:
        for p in glob.glob(f'{RUNS}/{i}_forecast_h52_*'):
            f = os.path.basename(p); fok, fm = _ok(f)
            lin = _j(f'{p}/lineage.json') if os.path.exists(f'{p}/lineage.json') else {}
            if fok and fm['dataset_id'] == ds and lin.get('refit_run_id') == refits[0]:
                fcs.append(f)
    ligado = len(refits) == 1 and len(fcs) == 1
    if acc['accepted']:
        if not ligado:
            return 'pendiente', {'id': i, 'motivo': f'aceptado con {len(refits)} refits y {len(fcs)} forecasts ligados a {tr}'}
        motores = _j(f'{RUNS}/{refits[0]}/refit_summary.json').get('engines', {})
        tipo = 'aceptado_control_only' if set(motores) == {'seasonal_naive_lag52'} else 'aceptado'
        return 'publicable', {'id': i, 'tipo': tipo, 'test_run': tr, 'dataset_id': ds,
                              'refit_run': refits[0], 'forecast_run': fcs[0], 'acceptance_sha256': dig}
    aut = autoridad.autoriza(B, 'control', i, tr)
    if aut and ligado:
        return 'publicable', {'id': i, 'tipo': 'control', 'test_run': tr, 'dataset_id': ds, 'autorizacion': aut,
                              'refit_run': refits[0], 'forecast_run': fcs[0], 'acceptance_sha256': dig}
    if aut:
        return 'pendiente', {'id': i, 'motivo': f'control autorizado sin refit y forecast ligados a {tr}'}
    return 'rechazado', {'id': i, 'test_run': tr, 'fallas': [c['scope'] for c in acc['checks'] if not c['passed']],
                         'control_autorizado': False}


def main() -> dict:
    out = {'publicables': [], 'rechazados': [], 'pendientes': []}
    ids = sorted({os.path.basename(d.rstrip('/')).removeprefix('ctrl_') for d in glob.glob(f'{B}/model/*/')})
    for i in ids:
        k, v = evaluar(i)
        out[{'publicable': 'publicables', 'rechazado': 'rechazados', 'pendiente': 'pendientes'}[k]].append(v)
    out['autorizaciones_rechazadas'] = autoridad.cargar(B)[1]
    return out


if __name__ == '__main__':
    r = main(); s = json.dumps(r, ensure_ascii=False, indent=1)
    if '--json' in sys.argv:
        open(sys.argv[sys.argv.index('--json') + 1], 'w').write(s)
    print(s)
