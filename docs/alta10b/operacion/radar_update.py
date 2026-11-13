"""Marca en el radar vigente los releases publicados del registry (Publicada / Control publicado)."""
import csv,hashlib,io,json,sys
sys.path[:0]=['wt-be/src','wt-be']
from epiforecast import registry
FE='wt-fe'; REG='wt-be/config/padecimientos.yaml'
ACEPT={'ascariasis_b77':'Carga parasitaria intestinal; publicada tras superar la prueba de 2025 con la política de cinco motores.',
 'hepatitis_a_b15':'Prevenible por vacunación con señal territorial amplia; publicada tras superar la prueba de 2025 con la política de cinco motores.',
 'calor_t67':'Señal estacional marcada; publicada tras superar la prueba de 2025 con la política de cinco motores.',
 'otras_hepatitis_b17':'Publicada tras superar la prueba de 2025 con la política de cinco motores.'}
CTRL='Su portafolio no superó la prueba de 2025; por autorización del autor se publica el control estacional, no validado.'
ids=sys.argv[1:]
a=json.load(open(f'{FE}/assets/boletin/actual.json')); car=f"{FE}/{a['carpeta']}"
d=json.load(open(f'{car}/data.json'))
def norm(s): return ' '.join(s.lower().replace('°','').split())
for i in ids:
    r=registry.require(i); assert r.lifecycle=='published',(i,r.lifecycle)
    ctrl=bool(r.acceptance_fallback_run)
    FUENTE={}
    hits=[e for e in d['diseases'] if norm(e['name'])==norm(FUENTE.get(i,r.data_name))]
    assert len(hits)==1,(i,r.data_name,len(hits))
    e=hits[0]; assert e['platform_id'] in (None,i)
    e.update(platform_id=i,status='Control publicado' if ctrl else 'Publicada',reason=CTRL if ctrl else ACEPT[i],priority='Seguimiento',score=None)
n=len({e['platform_id'] for e in d['diseases'] if e['platform_id']})
d['meta']['platform_published']=n; d['meta']['registry_sha256']=hashlib.sha256(open(REG,'rb').read()).hexdigest()
open(f'{car}/data.json','w').write(json.dumps(d,ensure_ascii=False,separators=(',',':')))
v=json.load(open(f'{car}/verification.json')); v['published_platform_entries']=n
open(f'{car}/verification.json','w').write(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
# catálogo
rows=list(csv.reader(open(f'{car}/catalogo.csv',encoding='utf-8'))); h=rows[0]
ix={k:h.index(k) for k in h}
byname={norm(e['name']):e for e in d['diseases']}
for row in rows[1:]:
    e=byname.get(norm(row[0]))
    if e and e['platform_id'] in ids:
        row[ix['estado_plataforma']]=e['status']; row[ix['prioridad']]='Seguimiento'; row[ix['puntaje']]=''
buf=io.StringIO(); csv.writer(buf,lineterminator='\n').writerows(rows); open(f'{car}/catalogo.csv','w',encoding='utf-8').write(buf.getvalue())
print('plataforma',n)
