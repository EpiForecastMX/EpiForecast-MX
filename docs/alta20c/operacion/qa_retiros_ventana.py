"""Barrido SIN umbrales de retiros de la fuente en la ventana que repite el control (objetivos 2025-W44..2026-W42 =
boletines 2025_sem45..2026_sem43, rezago 1). Un «retiro» es una caída del acumulado impreso (H+M) de una entidad entre un
boletín y el siguiente cuyo acumulado es del mismo año OBJETIVO (rezago 1: el boletín AAAA_sem01 trae la última semana del año anterior). Para cada uno: Sem impreso en el boletín previo a la caída, caída,
fracción retirada de esa Sem (min(1, caída/Sem)), y el total nacional de esa semana (el control repite ambos 52 semanas
después). Sólo lectura de los raws sellados de la observación.
Uso: qa_retiros_ventana.py --be <backend> <id>... > tsv   (por omisión, el backend que contiene este archivo)"""
import argparse, csv, glob, sys
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument('--be', default=str(Path(__file__).resolve().parents[3]), help='raíz del backend EpiForecast-MX')
ap.add_argument('ids', nargs='+')
args = ap.parse_args()
sys.path.insert(0, f'{args.be}/src')
from epiforecast.data import epi_calendar as ec  # noqa: E402
print('\t'.join(['id', 'entidad', 'boletin', 'sem_impreso', 'acum', 'acum_siguiente', 'caida', 'fraccion_retirada', 'nacional_semana']))
for d in args.ids:
    R = glob.glob(f'{args.be}/artifacts/observations/{d}/*/inputs/data_raw_*.csv')[0]
    rows = list(csv.DictReader(open(R, encoding='utf-8')))
    f = lambda x: float(x) if x not in ('', None) else 0.0
    nat = {}
    for r in rows:
        k = (int(r['Anio']), int(r['Semana'])); nat[k] = nat.get(k, 0) + f(r['Casos_semana'])
    by = {}
    for r in rows: by.setdefault(r['Entidad'], []).append(r)
    for ent, rs in sorted(by.items()):
        rs.sort(key=lambda r: (int(r['Anio']), int(r['Semana'])))
        for a, b in zip(rs, rs[1:]):
            ka = (int(a['Anio']), int(a['Semana']))
            ta = ec.target_period(*ka, 1); tb = ec.target_period(int(b['Anio']), int(b['Semana']), 1)
            if not ((2025, 45) <= ka <= (2026, 43)) or ta.epi_year != tb.epi_year:  # mismo año OBJETIVO (2026_sem01 trae 2025-W53)
                continue
            acc = lambda r: f(r.get('Acumulado_hombres')) + f(r.get('Acumulado_mujeres')) if r.get('Acumulado_hombres') not in (None, '') else f(r.get('Acumulado_total'))
            ca, cb = acc(a), acc(b)
            if cb < ca:
                s = f(a['Casos_semana']); caida = ca - cb
                frac = min(1.0, caida / s) if s > 0 else None
                print('\t'.join(map(str, [d, ent, f"{a['Anio']}_sem{int(a['Semana']):02d}", int(s), int(ca), int(cb), int(caida),
                                          '' if frac is None else round(frac, 2), int(nat[ka])])))
