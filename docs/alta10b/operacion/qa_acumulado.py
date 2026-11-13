"""Boletines con acumulado nacional (H+M) fuera de orden dentro del año fuente: el acumulado de la
semana N debe quedar entre el de N-1 y N+1 (tolerancia: revisiones retroactivas pequeñas, 2 %).
Un acumulado que «salta y vuelve» indica bloque rotado o errata de la fuente; se coteja con el PDF
antes de declarar keep_period. Uso: qa_acumulado.py <id> <csv>  Salida: qa/<id>_acumulado.json"""
import collections, csv, json, sys
i, p = sys.argv[1], sys.argv[2]
f = lambda x: float(x) if x not in ('', 'nan') else 0.0
ac = collections.defaultdict(float); se = collections.defaultdict(float)
for x in csv.DictReader(open(p)):
    k = (int(x['Anio']), int(x['Semana'])); ac[k] += f(x['Acumulado_hombres']) + f(x['Acumulado_mujeres']); se[k] += f(x['Casos_semana'])
malos = []
for (y, w) in sorted(ac):
    a, b, c = ac.get((y, w - 1)), ac[(y, w)], ac.get((y, w + 1))
    if a is None or c is None or a == 0:
        continue
    if b < a * 0.98 or b > c * 1.02 + 5:
        if not (c < a * 0.98):  # si el vecino posterior también cae, la revisión es retroactiva, no salto
            malos.append({'boletin': f'{y}_sem{w:02d}', 'acum_prev_actual_sig': [int(a), int(b), int(c)],
                          'semana_prev_actual_sig': [int(se.get((y, w - 1), 0)), int(se[(y, w)]), int(se.get((y, w + 1), 0))]})
json.dump({'id': i, 'csv': p, 'fuera_de_orden': malos}, open(f'qa/{i}_acumulado.json', 'w'), ensure_ascii=False, indent=1)
print(i, len(malos), [m['boletin'] for m in malos][:12])
