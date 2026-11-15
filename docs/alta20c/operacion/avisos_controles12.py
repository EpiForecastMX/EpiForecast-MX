"""Avisos de la fuente de los doce controles de alta20c: fichas y EpiBot desde una sola medición.

Revisión delegada de Fable sobre PUB12 (FABLE_REANUDACION_PUB12_REVISION.md), correcciones 1 a 5. No toca datos,
releases, vistas ni shards: lee los raws sellados de cada observación (Anio/Semana = boletín, rezago 1), la vista
publicada en el frontend y el registro de consultas del índice oficial de boletines.

Escribe:
  - en cada ficha <id>.html, los párrafos <p class="aviso-fuente"> (se reemplazan todos los anteriores) antes de
    #releaseMeta: los avisos nominales y la nota general medida; y la evidencia del índice posterior a la emisión;
  - <frontend>/epibot/js/avisos_fuente.js (generado; no editar a mano), que leen la respuesta determinista del EpiBot
    (obesidad_kb.js), la función RAG (rag.mjs) y el corpus del índice RAG (corpus.mjs).

Avisos nominales: sólo las celdas del dictamen §1 y las que marca picos_heredados (enterobiasis, Tlaxcala). Cada uno
dice si la fuente conservó o retiró el valor, con los acumulados; cada cifra se recalcula del raw y debe coincidir con
la cotejada a mano contra el texto del PDF (txt/), o el guion aborta.

Nota general (definición exacta, la misma que el JSON de la revisión de Fable): boletines 2025_sem45..2026_sem43
(objetivos 2025-W44..2026-W42, que el control repite 52 semanas después); pares de boletines consecutivos por entidad
cuyo acumulado es del mismo año OBJETIVO (no se cuenta el reinicio anual; 2026_sem01 trae 2025-W53); «baja» = el
acumulado H+M del boletín siguiente es menor; «retiro bruto» de una baja = caída del acumulado + casos nuevos (Sem) del
boletín siguiente. El número de bajas coincide con qa/retiros_ventana_controles12.tsv (qa_retiros_ventana.py).

Uso: avisos_controles12.py --fe <frontend> --be <backend> --indice <registro.txt> [--check]
"""
import argparse, csv, glob, json, re, sys
from datetime import datetime, timezone

ap = argparse.ArgumentParser()
ap.add_argument('--fe', required=True); ap.add_argument('--be', required=True); ap.add_argument('--indice', required=True)
ap.add_argument('--check', action='store_true')
a = ap.parse_args()
sys.path[:0] = [f'{a.be}/src']
from epiforecast.data import epi_calendar as cal  # noqa: E402

IDS = ['brucelosis_a23', 'reumatica_i00', 'bocio_e01', 'hepatitis_b_b16', 'rotavirus_a080', 'absceso_hepatico_a064',
       'leptospirosis_a27', 'helmintiasis_b65', 'desnutricion_moderada_e440', 'desnutricion_severa_e40',
       'enterobiasis_b80', 'giardiasis_a071']
VENTANA = ((2025, 45), (2026, 43))
f = lambda x: float(x) if x not in ('', None) else 0.0
bol = lambda k: f'{k[0]}_sem{k[1]:02d}'
sem = lambda k: f'{k[0]}-W{k[1]:02d}'
miles = lambda n: f'{int(n):,}'


def raw(d):
    p = glob.glob(f'{a.be}/artifacts/observations/{d}/*/inputs/data_raw_*.csv'); assert len(p) == 1, p
    out = {}
    for r in csv.DictReader(open(p[0], encoding='utf-8')):
        out[(int(r['Anio']), int(r['Semana']), r['Entidad'])] = r
    return out


def acum(r):
    return int(f(r['Acumulado_hombres']) + f(r['Acumulado_mujeres']))


def casos(r):
    return int(f(r['Casos_semana']))


def vista(d):
    return json.load(open(f'{a.fe}/publication/{d}/vista.json'))


def repetido(d, ent, y, w):
    """Valor que el control repite 52 semanas después en la entidad y total nacional de esa semana."""
    v = vista(d)
    s = next(x for k, x in v['series'].items() if k.startswith('estado|') and k.endswith('|general') and x['nombre'] == ent)
    t = cal.shift(y, w, 52); ds = str(cal.ds_for(*t))[:10]
    return t, int(dict(s['pronostico'])[ds]), int(dict(v['series']['nacional|mx|general']['pronostico'])[ds])


def de(nombre):
    return 'del ' + nombre[3:] if nombre.startswith('el ') else 'de ' + nombre


def retirado(d, ent, nombre, y, w, esperado):
    """Valor impreso y retirado en el boletín siguiente. esperado = (casos, acum, acum_sig, sem_sig, acum_fin)."""
    R = raw(d); b = cal.shift(y, w, 1); s = cal.shift(*b, 1)
    r1, r2, rf = R[b + (ent,)], R[s + (ent,)], R[VENTANA[1] + (ent,)]
    # El acumulado al cierre de la ventana sólo es comparable si el pico es del mismo año que 2026_sem43.
    medido = (casos(r1), acum(r1), acum(r2), casos(r2), acum(rf) if b[0] == VENTANA[1][0] else None)
    assert medido == esperado, (d, ent, medido, esperado)
    c, a1, a2, s2, af = medido
    neto = a1 - a2 + s2
    t, est, nac = repetido(d, ent, y, w); assert est == c, (d, est)
    parte = f'{neto} de los {c} de esa semana' if neto <= c else f'{neto} casos, más que los {c} de esa semana'
    fin = '' if b[0] != VENTANA[1][0] else f' En {bol(VENTANA[1])} el acumulado anual era {miles(af)}.'
    return {'clave': f'{ent}|{sem((y, w))}', 'estado': 'retirado', 'titulo': 'Un valor que la propia fuente retiró.',
            'texto': f'El boletín {bol(b)} imprimió {c} casos {de(nombre)} en la semana {sem((y, w))}, con un acumulado anual de '
                     f'{miles(a1)}; el boletín siguiente, {bol(s)}, imprimió un acumulado de {miles(a2)} con {s2} casos nuevos: '
                     f'un retiro neto de {parte}.{fin} El control repite lo impreso 52 semanas antes y no hay un criterio vigente '
                     f'para excluir un valor impreso y luego retirado: el pronóstico de {sem(t)} trae esos {c} casos {de(nombre)}, '
                     f'de {miles(nac)} nacionales. Esa semana no debe leerse como un aumento esperado. El dato y el pronóstico se '
                     'publican sin modificar.'}


def conservado(d, ent, nombre, y, w, esperado, transitoria=None):
    """Pico que sigue en el acumulado hasta el último boletín de la ventana. esperado = (casos, antes, con, fin)."""
    R = raw(d); b = cal.shift(y, w, 1); p = cal.shift(*b, -1)
    medido = (casos(R[b + (ent,)]), acum(R[p + (ent,)]), acum(R[b + (ent,)]), acum(R[VENTANA[1] + (ent,)]))
    assert medido == esperado, (d, ent, medido, esperado)
    c, a0, a1, af = medido
    t, est, nac = repetido(d, ent, y, w); assert est == c, (d, est)
    extra = ''
    if transitoria:
        kb, (h, m), kr, ar = transitoria
        assert (int(f(R[kb + (ent,)]['Acumulado_hombres'])), int(f(R[kb + (ent,)]['Acumulado_mujeres']))) == (h, m), (d, kb)
        assert acum(R[kr + (ent,)]) == ar, (d, kr)
        extra = (f' El boletín {bol(kb)} imprimió un acumulado de {h + m} ({h} en hombres y {m} en mujeres), pero {bol(kr)} volvió '
                 f'a {ar}: fue una baja transitoria.')
    return {'clave': f'{ent}|{sem((y, w))}|sostenido', 'estado': 'conservado', 'titulo': 'Un pico que la fuente conserva.',
            'texto': f'Los {c} casos {de(nombre)} en {sem((y, w))} siguen en el acumulado anual: {miles(a0)} antes, {miles(a1)} con '
                     f'esa semana y {miles(af)} en {bol(VENTANA[1])}, el último boletín de la ventana.{extra} El control los repite '
                     f'en {sem(t)}: {c} de {miles(nac)} casos nacionales.'}


def lepto():
    d, ent = 'leptospirosis_a27', 'Veracruz'; R = raw(d)
    sems = [(2025, 44, 130), (2025, 45, 65), (2025, 46, 29)]
    for y, w, c in sems:
        assert casos(R[cal.shift(y, w, 1) + (ent,)]) == c, (y, w)
    prev = casos(R[cal.shift(2025, 43, 1) + (ent,)])
    a0, a3 = acum(R[cal.shift(2025, 43, 1) + (ent,)]), acum(R[cal.shift(2025, 46, 1) + (ent,)])
    fin_b = (2026, 1); assert cal.target_period(*fin_b, 1).epi_year == 2025
    af = acum(R[fin_b + (ent,)])
    assert (prev, a0, a3, af) == (21, 126, 350, 378), (prev, a0, a3, af)
    t, est, nac = repetido(d, ent, 2025, 44); assert (sem(t), est) == ('2026-W43', 130)
    return {'clave': f'{ent}|2025-W44..W46', 'estado': 'conservado', 'titulo': 'Picos que la fuente conserva.',
            'texto': f'El boletín imprimió 130, 65 y 29 casos de Veracruz en 2025-W44, W45 y W46, frente a {prev} en la semana anterior; '
                     f'el acumulado anual de Veracruz pasó de {a0} a {a3} y cerró 2025 en {af} ({bol(fin_b)}, que trae la semana 53): '
                     'la fuente no los retiró. Como 2025 tuvo 53 semanas, el control los repite en 2026-W43, W44 y W45, las primeras '
                     f'semanas del horizonte: en 2026-W43 son {est} de los {nac} casos nacionales pronosticados. Esas semanas no deben '
                     'leerse como un brote esperado.'}


NOMINALES = {
    'absceso_hepatico_a064': lambda: [retirado('absceso_hepatico_a064', 'México', 'el Estado de México', 2026, 1, (125, 125, 1, 0, 8))],
    'bocio_e01': lambda: [retirado('bocio_e01', 'Morelos', 'Morelos', 2026, 24, (22, 55, 9, 1, 11))],
    'desnutricion_moderada_e440': lambda: [retirado('desnutricion_moderada_e440', 'Oaxaca', 'Oaxaca', 2025, 52, (139, 490, 364, 2, None))],
    'leptospirosis_a27': lambda: [lepto()],
    'reumatica_i00': lambda: [conservado('reumatica_i00', 'Querétaro', 'Querétaro', 2026, 23, (52, 6, 58, 66),
                                         transitoria=((2026, 29), (1, 6), (2026, 30), 59))],
    'desnutricion_severa_e40': lambda: [conservado('desnutricion_severa_e40', 'Jalisco', 'Jalisco', 2026, 34, (152, 316, 469, 571)),
                                        conservado('desnutricion_severa_e40', 'Querétaro', 'Querétaro', 2026, 37, (91, 12, 104, 111))],
    'enterobiasis_b80': lambda: [conservado('enterobiasis_b80', 'Tlaxcala', 'Tlaxcala', 2026, 10, (73, 0, 73, 112))],
}


def nota_general(d):
    R = raw(d); ents = sorted({k[2] for k in R})
    bajas = []
    for e in ents:
        ks = sorted(k[:2] for k in R if k[2] == e)
        for k1, k2 in zip(ks, ks[1:]):
            if not (VENTANA[0] <= k1 <= VENTANA[1]):
                continue
            if cal.target_period(*k1, 1).epi_year != cal.target_period(*k2, 1).epi_year:
                continue
            a1, a2 = acum(R[k1 + (e,)]), acum(R[k2 + (e,)])
            if a2 < a1:
                s2 = casos(R[k2 + (e,)])
                bajas.append({'ent': e, 'b1': k1, 'b2': k2, 'a1': a1, 'a2': a2, 's2': s2, 'caida': a1 - a2, 'bruto': a1 - a2 + s2})
    n = len(bajas); bruto = sum(x['bruto'] for x in bajas)
    m = sorted(bajas, key=lambda x: (-x['caida'], x['b1'], x['ent']))[0]
    mb = sorted(bajas, key=lambda x: (-x['bruto'], x['b1'], x['ent']))[0]
    texto = (f'Entre los boletines {bol(VENTANA[0])} y {bol(VENTANA[1])}, cuyas semanas (2025-W44 a 2026-W42) repite este control, el '
             f'acumulado anual impreso de alguna entidad bajó {n} veces de un boletín al siguiente (se compara cada boletín con el '
             f'siguiente dentro del mismo año epidemiológico; no se cuenta el reinicio anual). En esas bajas la fuente quitó en bruto '
             f'{miles(bruto)} casos, contados como la baja del acumulado más los casos nuevos del boletín siguiente; la cifra incluye '
             f'bajas transitorias que después se restituyen. La mayor baja fue en {m["ent"]}: acumulado {miles(m["a1"])} a '
             f'{miles(m["a2"])} entre {bol(m["b1"])} y {bol(m["b2"])}.')
    if mb is not m:
        texto += (f' El mayor retiro en un solo boletín fue en {mb["ent"]}: acumulado {miles(mb["a1"])} a {miles(mb["a2"])} con '
                  f'{mb["s2"]} casos nuevos ({miles(mb["bruto"])} casos), entre {bol(mb["b1"])} y {bol(mb["b2"])}.')
    texto += ' El control repite el valor semanal impreso en cada boletín y no descuenta estas correcciones posteriores.'
    return {'clave': 'bajas-acumulado', 'estado': 'nota', 'titulo': 'Correcciones de la fuente en la ventana que repite el control.',
            'texto': texto, 'bajas': n, 'retiro_bruto': bruto}


def indice(d):
    """Primera consulta del índice oficial (http=200) posterior a la emisión, con su último boletín."""
    e = datetime.fromisoformat(vista(d)['forecast_emitted_at'])
    for linea in open(a.indice):
        p = linea.split()
        if len(p) < 4 or p[1] != 'http=200':
            continue
        ts = datetime.strptime(p[0], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        if ts >= e:
            ult = int(p[3].split('=')[1]); assert ult == 43, (d, linea)
            return ts, e, ult
    raise AssertionError(f'{d}: sin consulta del índice posterior a la emisión')


def html_p(x):
    return f'        <p class="aviso-fuente" data-aviso="{x["clave"]}"><strong>{x["titulo"]}</strong> {x["texto"]}</p>\n'


ANCLA = '        <p class="mono-meta" id="releaseMeta"></p>\n'
VIEJOS = re.compile(r'^        <p class="aviso-fuente"[^\n]*</p>\n', re.M)
SEMANAS_SIN = 'Esas semanas (W43 a W46 de 2026) llegan con los boletines 44 a 47.</p>'
SEMANAS_CON = ('Esas semanas (W43 a W46 de 2026) llegan con los boletines 44 a 47, que no existían al emitir, aunque en el calendario '
               'W43, W44 y W45 ya habían concluido y W46 estaba en curso.')
EVID = re.compile(r' <span class="evidencia-indice">[^<]*</span>')

datos = {}; cambios = []
for d in IDS:
    nom = NOMINALES.get(d, lambda: [])(); nota = nota_general(d)
    ts, emi, ult = indice(d)
    evid = (f'Lo comprueba la consulta del índice oficial de boletines del {ts.day} de noviembre de {ts.year} a las '
            f'{ts:%H:%M:%S} UTC, posterior a la emisión ({emi:%H:%M:%S} UTC), que listaba como último el boletín {ult}.')
    datos[d] = {'avisos': [{k: x[k] for k in ('clave', 'estado', 'titulo', 'texto')} for x in nom],
                'nota': {k: nota[k] for k in ('clave', 'titulo', 'texto', 'bajas', 'retiro_bruto')},
                'indice_posterior': {'consulta': f'{ts:%Y-%m-%dT%H:%M:%SZ}', 'emision': vista(d)['forecast_emitted_at'], 'ultimo_boletin': ult}}
    p = f'{a.fe}/{d}.html'; s0 = open(p, encoding='utf-8').read()
    s = VIEJOS.sub('', s0)
    assert s.count(ANCLA) == 1, (d, 'ancla')
    s = s.replace(ANCLA, ''.join(html_p(x) for x in [*nom, nota]) + ANCLA)
    if SEMANAS_SIN in s:
        s = s.replace(SEMANAS_SIN, SEMANAS_CON + '</p>')
    s = EVID.sub('', s)
    anc = 'W46 estaba en curso.'
    assert s.count(anc) == 1, (d, 'frase de semanas objetivo')
    s = s.replace(anc, anc + f' <span class="evidencia-indice">{evid}</span>')
    if s != s0:
        cambios.append(f'{d}.html')
        if not a.check:
            open(p, 'w', encoding='utf-8').write(s)
    print(d, f'bajas={nota["bajas"]}', f'bruto={nota["retiro_bruto"]}', f'nominales={len(nom)}', f'indice={ts:%H:%M:%S}')

js = ('// Generado por docs/alta20c/operacion/avisos_controles12.py (backend EpiForecast-MX); no editar a mano.\n'
      '// Avisos de la fuente de los doce controles de alta20c: nominales (dictamen §1 y picos heredados) y nota general\n'
      '// medida de bajas del acumulado en la ventana que repite el control. Los leen obesidad_kb.js, rag.mjs y corpus.mjs.\n'
      '(function (g) {\n  g.EPI_AVISOS_FUENTE = Object.freeze(' + json.dumps(datos, ensure_ascii=False, indent=2).replace('\n', '\n  ') + ');\n'
      '})(globalThis);\n')
pj = f'{a.fe}/epibot/js/avisos_fuente.js'
try:
    viejo = open(pj, encoding='utf-8').read()
except FileNotFoundError:
    viejo = None
if viejo != js:
    cambios.append('epibot/js/avisos_fuente.js')
    if not a.check:
        open(pj, 'w', encoding='utf-8').write(js)
print('cambios:', cambios or 'ninguno')
if a.check and cambios:
    sys.exit(1)
