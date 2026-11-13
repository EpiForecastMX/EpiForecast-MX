import csv,hashlib,json
from pathlib import Path
from epiforecast import registry
from epiforecast.publication.consolidado_base import diferencias_base
from epiforecast.publication.contratos_datos import ContratoCobertura, revisa_consolidado
from scripts.paso_semanal import filas_de_semana
ING=Path('/Users/haowei/Documents/Integrador/planes/oneplus_actualizacion_2026-10-01/sesion_20261002T141558/ingestion_observado_W43')
base=ING/'candidato_con_alta20_controles10'/'dataset_boletin_epidemiologico.csv'
sh=lambda p: hashlib.sha256(open(p,'rb').read()).hexdigest()
assert sh(base).startswith('fad3c95c'), sh(base)
outdir=ING/'candidato_con_alta10b_controles6'; assert not outdir.exists() or not any(outdir.iterdir()); outdir.mkdir(exist_ok=True)
out=outdir/'dataset_boletin_epidemiologico.csv'
new=['desnutricion_leve_e441','salmonelosis_a02','tifoidea_a01','escarlatina_a38','hepatitis_c_b17','displasia_severa_n87']
btxt=open(base,encoding='utf-8').read(); assert btxt.endswith('\n')
nombres_base={r['Padecimiento'] for r in csv.DictReader(open(base,encoding='utf-8'))}
raws={}; add=[]
for d in new:
    r=registry.require(d); obs=[p for p in Path(f'artifacts/observations/{d}').iterdir() if p.is_dir()]; assert len(obs)==1
    raw=next((obs[0]/'inputs').glob('data_raw_*.csv')); raws[d]=raw
    assert r.data_name not in nombres_base, d
    periodos=sorted({(int(x['Anio']),int(x['Semana'])) for x in csv.DictReader(open(raw,encoding='utf-8'))})
    for a,s in periodos: add+=filas_de_semana(raw,a,s)
open(out,'w',encoding='utf-8').write(btxt+''.join(l+'\n' for l in add))
assert open(out,'rb').read().startswith(open(base,'rb').read())
dif=diferencias_base(out,raws,(2026,43)); print('diferencias',dif)
c=ContratoCobertura.canonico(); res=revisa_consolidado(out,c,c.padecimientos)
print(res)
print('filas',len(add),'sha',sh(out))
json.dump({'base_sha':sh(base),'out_sha':sh(out),'filas_añadidas':len(add),'diferencias':dif},open('/tmp/epiforecast-alta10b-20261112/consolidado_controles6.json','w'))
