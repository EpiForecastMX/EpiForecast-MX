import json, sys
sys.path[:0] = ['wt-ctl/src']
from epiforecast.data import epi_calendar as cal
items = [('absceso_hepatico_a064', 'México', (2026, 1)), ('bocio_e01', 'Morelos', (2026, 24)),
         ('leptospirosis_a27', 'Veracruz', (2025, 44)), ('leptospirosis_a27', 'Veracruz', (2025, 45)), ('leptospirosis_a27', 'Veracruz', (2025, 46)),
         ('reumatica_i00', 'Querétaro', (2026, 23)), ('desnutricion_severa_e40', 'Jalisco', (2026, 34)),
         ('desnutricion_severa_e40', 'Querétaro', (2026, 37)), ('desnutricion_moderada_e440', 'Oaxaca', (2025, 52)),
         ('enterobiasis_b80', 'Tlaxcala', (2026, 10))]
for d, ent, (y, w) in items:
    v = json.load(open(f'wt-fe/publication/{d}/vista.json'))
    s = next(x for k, x in v['series'].items() if k.startswith('estado') and k.endswith('|general') and x['nombre'] == ent)
    nac = v['series']['nacional|mx|general']
    ds_obs = str(cal.ds_for(y, w))[:10]
    obs = dict((a, b) for a, b in s['observado']).get(ds_obs)
    ty, tw = cal.shift(y, w, 52); ds_t = str(cal.ds_for(ty, tw))[:10]
    pr = dict((a, b) for a, b in s['pronostico']).get(ds_t); pn = dict((a, b) for a, b in nac['pronostico']).get(ds_t)
    print(f'{d} {ent} obs {y}-W{w:02d} ({ds_obs})={obs}  -> pronóstico {ty}-W{tw:02d} ({ds_t})={pr}  nacional={pn}')
