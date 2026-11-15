"""Pone al día las listas de las pruebas del frontend que dependen de qué releases están instalados: fixture de
políticas (desde el registry del backend, sólo ids del catálogo instalado), galería de test_release_catalogo y lista
de releases de test_rag_alcance. Uso: fe_fixtures.py <frontend> <backend>"""
import json, re, subprocess, sys
fe, be = sys.argv[1:3]
sys.path[:0] = [f'{be}/src', be]
from epiforecast import registry
cat = [r['disease_id'] for r in json.load(open(f'{fe}/publication/catalog.json'))['releases']]
pol = {d.id: d.selection_policy for d in registry.release_published() if d.id in cat}
assert set(pol) == set(cat), set(cat) - set(pol)
p = f'{fe}/tests/fixtures/politica_por_release.json'; old = json.load(open(p))
for k, v in old.items(): assert pol[k] == v, k
json.dump(dict(sorted(pol.items())), open(p, 'w'), indent=1, ensure_ascii=False); open(p, 'a').write('\n')
# galería: el orden de instancias es el de release_catalog.js
rc = open(f'{fe}/epibot/js/release_catalog.js', encoding='utf-8').read()
ids = re.findall(r"^      id: '([a-z0-9_]+)'", rc, re.M)
p = f'{fe}/epibot/tests/test_release_catalogo.mjs'; s = open(p, encoding='utf-8').read()
m = re.search(r"(assert\.deepEqual\(\[\.\.\.ctx\.window\.GaleriasRelease\]\.map\(\(g\) => g\.id\),\n)(.*?)(\]\);)", s, re.S)
lin, cur = [], "    ["
for x in ids + ['sintetico_x']:
    t = f"'{x}', "
    if len(cur) + len(t) > 112: lin.append(cur.rstrip()); cur = "      "
    cur += t
lin.append(cur.rstrip().rstrip(','))
s = s[:m.start(2)] + '\n'.join(lin) + s[m.start(3):]
open(p, 'w', encoding='utf-8').write(s)
print('releases', len(cat), 'galería', len(ids))
