"""Diagnóstico: cuántas series base fallan ETS y Ridge por pliegue de desarrollo (sin escribir runs).
Uso (PYTHONPATH del worktree): diag_motores.py <run_dir_smoke> <salida.json>"""
import json, sys, warnings
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
from epiforecast.runner import contracts as ct
from epiforecast.runner.engines import harness, ets, ridge_harmonic
from epiforecast.runner.policy import load_policy
from epiforecast.data.sex_scheme import base_mask
from epiforecast.data.epi_dataset_spec import COL_GEO_ID, COL_SEX
warnings.filterwarnings('ignore')
rd = Path(sys.argv[1]); job = json.loads((rd / 'job_context.json').read_text())
products = pd.read_csv(Path(job['dataset_dir']) / 'products.csv')
policy = load_policy(job['policy_name'])
folds = policy.folds_for_stage('full')
base = products[base_mask(products)]
res = {'run_smoke': rd.name, 'dataset_dir': job['dataset_dir'], 'policy': job['policy_name'], 'motores': {}}
for name, pred in (('ets_add_damped_log1p', ets.make_predictor(ets.load_ets_config())),
                   ('ridge_harmonic_log1p', ridge_harmonic.make_predictor(ridge_harmonic.load_ridge_config()))):
    ctx = harness.EngineContext(engine=name, disease_id=job['disease_id'], dataset_digest=str(job['dataset_digest']),
                                policy_name=job['policy_name'], policy_digest=policy.digest, seed=int(job['seed']),
                                transform=ct.log1p_transform(job['disease_id'], name), params={}, resource_limits={})
    porfold = {}; bases = set(); ejemplo = None; tipos = Counter()
    for f in folds:
        fallas = 0
        for cve, sexo, req in harness.series_requests(base, f, ctx):
            try:
                out = pred(req); harness.validate_predictions(out, req)
            except Exception as e:  # noqa: BLE001
                fallas += 1; bases.add((cve, sexo)); tipos[type(e).__name__] += 1; ejemplo = ejemplo or f'{cve}/{sexo}/{f.fold_id}: {type(e).__name__}: {str(e)[:160]}'
        porfold[f.fold_id] = fallas
    res['motores'][name] = {'series_fallidas_por_pliegue': porfold, 'bases_distintas_afectadas': len(bases),
                            'bases_totales': int(base.groupby([COL_GEO_ID, COL_SEX]).ngroups), 'tipos_de_error': dict(tipos), 'ejemplo': ejemplo}
json.dump(res, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False)[:900])
