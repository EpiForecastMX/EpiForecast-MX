"""Consolidado de paridad candidato_con_alta20c_controles12: sólo añade filas sobre candidato_con_alta10b."""
import csv, hashlib, json
from pathlib import Path
from epiforecast import registry
from epiforecast.publication.consolidado_base import diferencias_base
from epiforecast.publication.contratos_datos import ContratoCobertura, revisa_consolidado
from scripts.paso_semanal import filas_de_semana

ING = Path('/Users/haowei/Documents/Integrador/planes/oneplus_actualizacion_2026-10-01/sesion_20261002T141558/ingestion_observado_W43')
base = ING / 'candidato_con_alta10b' / 'dataset_boletin_epidemiologico.csv'
sh = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
assert sh(base) == 'be7abfa5a9135d98900cbc6dc2a8ebf0834fae0bebbdb20268db0686a7330dfc', sh(base)
OUTROOT = Path('/Users/haowei/Documents/Integrador/planes/alta20c_2026-11-14/ingestion_observado_W43')
outdir = OUTROOT / 'candidato_con_alta20c_controles12'
assert not outdir.exists() or not any(outdir.iterdir()), outdir
outdir.mkdir(parents=True, exist_ok=True)
out = outdir / 'dataset_boletin_epidemiologico.csv'
new = ['brucelosis_a23', 'reumatica_i00', 'bocio_e01', 'hepatitis_b_b16', 'rotavirus_a080',
       'absceso_hepatico_a064', 'leptospirosis_a27', 'helmintiasis_b65', 'desnutricion_moderada_e440',
       'desnutricion_severa_e40', 'enterobiasis_b80', 'giardiasis_a071']
btxt = open(base, encoding='utf-8').read(); assert btxt.endswith('\n')
nombres_base = {r['Padecimiento'] for r in csv.DictReader(open(base, encoding='utf-8'))}
raws = {}; add = []; por_id = {}
for d in new:
    r = registry.require(d)
    assert r.lifecycle == 'published', (d, r.lifecycle)
    obs = [p for p in Path(f'artifacts/observations/{d}').iterdir() if p.is_dir()]; assert len(obs) == 1, obs
    raw = next((obs[0] / 'inputs').glob('data_raw_*.csv')); raws[d] = raw
    assert r.data_name not in nombres_base, d
    periodos = sorted({(int(x['Anio']), int(x['Semana'])) for x in csv.DictReader(open(raw, encoding='utf-8'))})
    n0 = len(add)
    for a, s in periodos:
        add += filas_de_semana(raw, a, s)
    por_id[d] = {'obs': obs[0].name, 'raw': str(raw), 'raw_sha256': sh(raw), 'periodos': len(periodos),
                 'ultimo': list(periodos[-1]), 'filas': len(add) - n0}
open(out, 'w', encoding='utf-8').write(btxt + ''.join(l + '\n' for l in add))
assert open(out, 'rb').read().startswith(open(base, 'rb').read())
dif = diferencias_base(out, raws, (2026, 43)); print('diferencias', dif)
c = ContratoCobertura.canonico(); res = revisa_consolidado(out, c, c.padecimientos)
print(res)
print('padecimientos en contrato', len(c.padecimientos), 'release', len(c.release))
print('filas', len(add), 'sha', sh(out))
json.dump({'base': str(base), 'base_sha256': sh(base), 'out': str(out), 'out_sha256': sh(out),
           'filas_añadidas': len(add), 'por_id': por_id, 'diferencias': repr(dif),
           'revisa_consolidado': repr(res), 'padecimientos_contrato': len(c.padecimientos)},
          open(OUTROOT / 'consolidado_controles12.json', 'w'), ensure_ascii=False, indent=1)
