"""Cotejo del raw con el renglón TOTAL impreso SIN mapa de columnas.

Para cada boletín toma la suma nacional del raw (Sem., Acum. H, Acum. M), la escribe como la
imprime el boletín (miles con espacio, cero como «-») y la busca como terna contigua en el renglón
TOTAL de la página anclada (pdftotext). Resultados por boletín:
  coincide   la terna aparece exactamente una vez;
  ambigua    aparece más de una vez o es «- - -» (no discrimina);
  no_aparece la terna no está: posible error de lectura del raw (o renglón partido en dos líneas);
  sin_total  no hay página/renglón TOTAL.
Uso: qa_total_terna.py <id> <csv> <ancla1,ancla2>   Salida: qa/<id>_total_terna.json
"""
import collections, json, re, sys
import pandas as pd

B = '/tmp/epiforecast-alta10b-20261112'
i, csvp, anclas = sys.argv[1], sys.argv[2], sys.argv[3].lower().split(',')
d = pd.read_csv(csvp, dtype={'Semana': str})
cols = ['Casos_semana', 'Acumulado_hombres', 'Acumulado_mujeres']
d['Acumulado_anio_anterior'] = pd.to_numeric(d.get('Acumulado_anio_anterior'), errors='coerce')
for c in cols:
    d[c] = pd.to_numeric(d[c], errors='coerce')
g = d.groupby(['Anio', 'Semana'])[cols + ['Acumulado_anio_anterior']].sum(min_count=1)


def imp(v):
    if v != v:
        return None
    v = int(v)
    return '-' if v == 0 else f'{v:,}'.replace(',', ' ')


res = collections.Counter(); por_anio = collections.defaultdict(collections.Counter); no = []; inv = []; cuatro = collections.Counter()
for (y, w), fila in g.iterrows():
    y, w = int(y), int(w)
    try:
        pages = open(f'{B}/txt/{y}_sem{w:02d}.txt', errors='ignore').read().split('\f')
    except FileNotFoundError:
        res['sin_total'] += 1; por_anio[y]['sin_total'] += 1; continue
    ps = [p for p in pages if all(a in p.lower() for a in anclas) and 'zacatecas' in p.lower()]
    tl = [l for l in ps[0].splitlines() if l.strip().upper().startswith('TOTAL')] if ps else []
    if not tl:
        res['sin_total'] += 1; por_anio[y]['sin_total'] += 1; continue
    terna = [imp(fila[c]) for c in cols]
    if None in terna:
        res['raw_nan'] += 1; por_anio[y]['raw_nan'] += 1; continue
    linea = ' ' + re.sub(r'\s+', ' ', tl[0].strip()[5:]) + ' '
    pat = r'(?<= )' + r' '.join(re.escape(t) for t in terna) + r'(?= )'
    n = len(re.findall(pat, linea))
    k = 'ambigua' if (n > 1 or terna == ['-', '-', '-']) and n else ('coincide' if n == 1 else 'no_aparece')
    res[k] += 1; por_anio[y][k] += 1
    # invariante: la semana está contenida en el acumulado del año (nacional)
    if fila['Casos_semana'] > fila['Acumulado_hombres'] + fila['Acumulado_mujeres']:
        inv.append([y, w, terna])
    # cuarta columna (año anterior) si el raw la trae: la cuaterna también debe ser contigua
    pa = fila['Acumulado_anio_anterior']
    if k == 'coincide' and pa == pa:
        p4 = r'(?<= )' + r' '.join(re.escape(t) for t in terna + [imp(pa)]) + r'(?= )'
        cuatro['coincide' if re.search(p4, linea) else 'no_aparece'] += 1
    if k == 'no_aparece':
        no.append([y, w, terna])
out = {'id': i, 'csv': csvp, 'anclas': anclas, 'boletines': int(len(g)), 'resumen': dict(res),
       'por_anio_fuente': {y: dict(c) for y, c in sorted(por_anio.items())}, 'no_aparece': no,
       'cuaterna_con_anio_anterior': dict(cuatro), 'viola_sem_le_acum': inv}
json.dump(out, open(f'{B}/qa/{i}_total_terna.json', 'w'), ensure_ascii=False, indent=1)
print(i, len(g), dict(res), 'cuaterna', dict(cuatro), 'viola_sem<=acum', len(inv), inv[:3], 'no_aparece:', no[:3])
