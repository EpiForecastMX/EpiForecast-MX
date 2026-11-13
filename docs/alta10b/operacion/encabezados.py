"""Muestras citables del encabezado impreso: semana 10 de cada año, más las fronteras `desde` de
los periodos de la config y el boletín anterior a cada frontera. Uso: encabezados.py <id> <anclas>"""
import sys, yaml
B = '/tmp/epiforecast-alta10b-20261112'
i, anclas = sys.argv[1], sys.argv[2].lower().split(',')
cu = yaml.safe_load(open(f'{B}/wt-be/config/data/cuadros.yaml'))['cuadro_groups']
g, spec = next((g, s) for g, s in cu.items() if any(x['id'] == i for x in s.get('diseases', [])))
fr = []
for p in spec.get('periodos') or []:
    y, w = map(int, str(p['desde']).split('_sem')); fr += [f'{y}_sem{w:02d}', f'{y}_sem{w-1:02d}' if w > 1 else f'{y-1}_sem52']
muestras = sorted(set([f'{y}_sem10' for y in range(2014, 2027)] + fr + ['2026_sem43']))
out = [f'# {i} (grupo {g}); anclas {anclas}; muestras: semana 10 de cada año, fronteras de periodo y 2026_sem43\n']
for f in muestras:
    try: pages = open(f'{B}/txt/{f}.txt', errors='ignore').read().split('\f')
    except FileNotFoundError: continue
    ps = [(n, p) for n, p in enumerate(pages) if all(a in p.lower() for a in anclas) and 'zacatecas' in p.lower()]
    if not ps: out.append(f'== {f}: sin página\n'); continue
    n, p = ps[0]; ls = p.splitlines()
    k = next((j for j, l in enumerate(ls) if l.strip().startswith('Aguascal')), 12)
    tot = [l.rstrip() for l in ls if l.strip().upper().startswith('TOTAL')][:1]
    out.append(f'== {f} (página pdftotext {n+1})\n' + '\n'.join(l.rstrip()[:240] for l in ls[max(0,k-12):k+1] if l.strip()) + '\n' + '\n'.join(tot) + '\n')
open(f'{B}/qa/encabezados/{i}.txt', 'w').write('\n'.join(out)); print(i, len(muestras))
