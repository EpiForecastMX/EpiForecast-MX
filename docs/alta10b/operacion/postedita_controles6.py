"""Post-edición editorial mínima sobre las fichas v3 (scripts/gen_fichas.py) de los seis controles A6.
Sólo añade dos frases medidas, sin tocar cifras ni narrativa generadas:
  - errata de fuente 2016_sem20 (salmonelosis y escarlatina; qa/<id>_reserva_acumulado.json);
  - aviso de referencia estatal poco informativa (error del control por estado >= 70 en la prueba de 2025),
    el mismo texto que rag.mjs da con controlEstatalPocoInformativo.
Uso: postedita_controles6.py <dir_v3> <dir_salida>"""
import json, re, sys
src, out = sys.argv[1:3]
ERRATA = {'salmonelosis_a02', 'escarlatina_a38'}
POCO = {'salmonelosis_a02', 'tifoidea_a01', 'escarlatina_a38', 'hepatitis_c_b17', 'displasia_severa_n87'}
FE = '/tmp/epiforecast-alta10b-20261112/wt-fe'
for d in ['desnutricion_leve_e441', 'salmonelosis_a02', 'tifoidea_a01', 'escarlatina_a38', 'hepatitis_c_b17', 'displasia_severa_n87']:
    s = open(f'{src}/{d}.html', encoding='utf-8').read()
    v = json.load(open(f'{FE}/publication/{d}/vista.json'))
    comp = {c['ambito']: c for c in v['caida_al_control']['comprobaciones']}
    sinsexo = not any(k.endswith('|hombres') for k in v['series'])
    if d in ERRATA:
        a = '</p></div>\n        <div class="step"><div class="n">02 · Modelos</div>'
        assert s.count(a) == 1, d
        s = s.replace(a, ' El boletín de la semana 20 de 2016 trae rotados los bloques de este cuadro; esa errata de fuente quedó en la historia de 2016 con la que se evaluó el portafolio, pero no entra en el control, que sólo repite las últimas 52 semanas.' + a)
    if d in POCO:
        c = comp['smape_bases']['control']; assert c >= 70, (d, c)
        amb = 'las series por estado' if sinsexo else 'las series por estado y sexo'
        a = ' en el total nacional.</p></div>\n        <div class="step"><div class="n">04 · Seguimiento</div>'
        assert s.count(a) == 1, d
        s = s.replace(a, f' en el total nacional. Por estado es una referencia poco informativa: su error en {amb} fue sMAPE {c:.1f} en esa prueba.</p></div>\n        <div class="step"><div class="n">04 · Seguimiento</div>')
    open(f'{out}/{d}.html', 'w', encoding='utf-8').write(s); print(d, 'ok')
