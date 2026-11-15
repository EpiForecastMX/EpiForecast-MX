"""Busca picos de la ventana del control (objetivos 2025-W44..2026-W42 = boletines 2025_sem45..2026_sem43)
cuyo acumulado impreso cae en el boletín siguiente (retiro por la propia fuente). Sólo lectura."""
import csv, glob, sys
ids = sys.argv[1:]
for d in ids:
    R = glob.glob(f'wt-ctl/artifacts/observations/{d}/*/inputs/data_raw_*.csv')[0]
    rows = [r for r in csv.DictReader(open(R, encoding='utf-8'))]
    by = {}
    for r in rows:
        by.setdefault(r['Entidad'], []).append(r)
    for ent, rs in by.items():
        rs.sort(key=lambda r: (int(r['Anio']), int(r['Semana'])))
        f = lambda x: float(x) if x not in ('', None) else 0.0
        for i in range(len(rs) - 1):
            a, b = rs[i], rs[i + 1]
            ka = (int(a['Anio']), int(a['Semana']))
            if not ((2025, 45) <= ka <= (2026, 43)):
                continue
            c = f(a['Casos_semana'])
            acc_a = f(a['Acumulado_hombres']) + f(a['Acumulado_mujeres'])
            acc_b = f(b['Acumulado_hombres']) + f(b['Acumulado_mujeres'])
            mismo = a['Anio'] == b['Anio'] or (ka == (2025, 53))
            if c >= 10 and mismo and acc_b < acc_a - 0.5 * c:
                print(f'{d}\t{ent}\tboletin {a["Anio"]}_sem{a["Semana"]}\tSem {c:.0f}\tacum {acc_a:.0f} -> {acc_b:.0f} en {b["Anio"]}_sem{b["Semana"]}')
