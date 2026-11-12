"""Identidad del bloque por el encabezado impreso (pdftotext -layout), independiente del extractor.

Para cada boletín: página con las anclas y «zacatecas»; en el encabezado (líneas antes del primer
estado) localiza el rótulo del padecimiento (regex propio, no la config) y el renglón de códigos
CIE (el renglón del encabezado con más grupos de código). La posición del bloque es el índice del
grupo de código más cercano a la columna del rótulo; se informa con el número de bloques, el
texto del código impreso y los rótulos vecinos. Resume por periodos contiguos con la misma firma.
Uso: qa_identidad.py <id> <anclas> <regex_rotulo>   Salida: qa/<id>_identidad.json
"""
import json, os, re, sys

B = '/tmp/epiforecast-alta10b-20261112'
i, anclas, rx = sys.argv[1], sys.argv[2].lower().split(','), re.compile(sys.argv[3], re.I)
COD = re.compile(r'(?:^|(?<=\s))([A-Z]\d{2}(?:\.\d)?[A-Z0-9.,\- ]*?)(?=\s{2,}|$)')
EST = re.compile(r'^\s*(Aguascalientes|Baja California)\b')


def firma(f):
    pages = open(f'{B}/txt/{f}', errors='ignore').read().split('\f')
    ps = [p for p in pages if all(a in p.lower() for a in anclas) and 'zacatecas' in p.lower()]
    if not ps:
        return {'estado': 'sin_pagina'}
    ls = ps[0].splitlines()
    k = next((j for j, l in enumerate(ls) if EST.match(l)), None)
    if k is None:
        return {'estado': 'sin_estados'}
    enc = ls[max(0, k - 14):k]
    rot = [(j, m.start()) for j, l in enumerate(enc) for m in rx.finditer(l)]
    if not rot:
        return {'estado': 'sin_rotulo'}
    cods = [(j, [(m.start(), m.end(), m.group(1).strip()) for m in COD.finditer(l)]) for j, l in enumerate(enc)]
    cods = [c for c in cods if c[1]]
    if not cods:
        return {'estado': 'sin_codigos'}
    j, grupos = max(cods, key=lambda c: len(c[1]))
    x = rot[0][1]
    # el rótulo suele estar centrado sobre su bloque: el código cuyo intervalo queda más cerca
    pos = min(range(len(grupos)), key=lambda g: 0 if grupos[g][0] <= x <= grupos[g][1]
              else min(abs(x - grupos[g][0]), abs(x - grupos[g][1])))
    return {'estado': 'ok', 'bloques': len(grupos), 'posicion': pos, 'codigo': grupos[pos][2],
            'codigos': [g[2] for g in grupos]}


filas = []
for f in sorted(os.listdir(f'{B}/txt')):
    if f.endswith('.txt'):
        filas.append((f[:-4], firma(f)))
periodos = []
for f, s in filas:
    clave = (s['estado'], s.get('bloques'), s.get('posicion'), s.get('codigo'))
    if periodos and periodos[-1]['clave'] == clave:
        periodos[-1]['hasta'] = f; periodos[-1]['n'] += 1
    else:
        periodos.append({'clave': clave, 'desde': f, 'hasta': f, 'n': 1, 'codigos': s.get('codigos')})
out = {'id': i, 'anclas': anclas, 'rotulo_regex': sys.argv[3], 'boletines': len(filas),
       'periodos': [{'desde': p['desde'], 'hasta': p['hasta'], 'n': p['n'], 'estado': p['clave'][0],
                     'bloques': p['clave'][1], 'posicion': p['clave'][2], 'codigo_impreso': p['clave'][3],
                     'codigos_de_la_pagina': p['codigos']} for p in periodos]}
json.dump(out, open(f'{B}/qa/{i}_identidad.json', 'w'), ensure_ascii=False, indent=1)
print(i, len(filas), 'periodos', len(periodos))
for p in out['periodos']:
    if p['n'] >= 3 or p['estado'] != 'ok':
        print(' ', p['desde'], p['hasta'], p['n'], p['estado'], p['bloques'], p['posicion'], p['codigo_impreso'])
