"""Cambia en config/padecimientos.yaml el bloque de cada id para la fase de release, sin tocar otros bloques.
  trained <id> <refit_run> <forecast_run>   lifecycle trained + artifact_source runner_runs (digests de los runs)
  release <id> <release_id>                 artifact_source runner_release con el release promovido
Uso (en el worktree): registry_fase.py <modo> ...   Los digests salen de los manifiestos, nunca a mano."""
import hashlib, json, sys
modo = sys.argv[1]
p = 'config/padecimientos.yaml'; L = open(p, encoding='utf-8').read().split('\n')


def bloque(i):
    s = L.index(f'  - id: {i}')
    e = next((k for k in range(s + 1, len(L)) if L[k].startswith('  - id: ')), len(L))
    return s, e


def sin_artifact(blk):
    out, skip = [], False
    for l in blk:
        if l.startswith('    artifact_source:'):
            skip = True; continue
        if skip and l.startswith('      '):
            continue
        skip = False; out.append(l)
    return out


if modo == 'trained':
    i, rf, fc = sys.argv[2:5]
    rm = json.load(open(f'runs/{rf}/run_manifest.json')); fm = json.load(open(f'runs/{fc}/run_manifest.json'))
    assert rm['status'] == fm['status'] == 'succeeded' and rm['disease_id'] == fm['disease_id'] == i
    lin = json.load(open(f'runs/{fc}/lineage.json')); assert lin['refit_run_id'] == rf
    prov = json.load(open(f'runs/{rf}/refit_summary.json'))['provenance']
    fs = f"runs/{prov['acceptance_run_id']}/final_selection.csv"
    art = ['    artifact_source:', '      backend: runner_runs', f'      refit_run_id: {rf}', f'      forecast_run_id: {fc}',
           f"      policy_digest: {rm['policy_digest']}", f"      final_selection_digest: {hashlib.sha256(open(fs, 'rb').read()).hexdigest()}"]
    s, e = bloque(i); blk = sin_artifact(L[s:e])
    k = next(n for n, l in enumerate(blk) if l.strip().startswith('lifecycle:'))
    assert blk[k].strip() in ('lifecycle: configured', 'lifecycle: trained'), blk[k]
    blk[k] = '    lifecycle: trained'
    j = next(n for n, l in enumerate(blk) if l.strip().startswith('selection_policy:'))
    blk[j + 1:j + 1] = art
    L[s:e] = blk
elif modo == 'release':
    i, rel = sys.argv[2:4]
    s, e = bloque(i); blk = sin_artifact(L[s:e])
    j = next(n for n, l in enumerate(blk) if l.strip().startswith('selection_policy:'))
    blk[j + 1:j + 1] = ['    artifact_source:', '      backend: runner_release', f'      release_id: {rel}']
    L[s:e] = blk
else:
    sys.exit(f'modo desconocido {modo}')
open(p, 'w', encoding='utf-8').write('\n'.join(L)); print(modo, sys.argv[2], 'ok')
