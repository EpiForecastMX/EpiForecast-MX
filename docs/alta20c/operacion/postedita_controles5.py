"""Post-edición medida de las fichas de los cinco controles nuevos de alta20c (dictamen delegado complementario
FABLE_CONTROLES5_DECISION_20261115.json), sobre la salida de gen_fichas_alta20c.py. No toca datos.

Condiciones comunes: autorización y política por dictamen bajo delegación del autor (no el autor por nombre); el
control repite lo observado 52 semanas antes, incluidos picos y valores retirados; reparto por sexo de respaldo en el
dataset y en la ventana (flag que contiene «sex_fallback», la definición del dictamen); «W43, W44 y W45».
Condiciones por id: error nacional y salto o nivel (coqueluchoide, tos ferina), definición sindrómica frente a A37,
D7 (plaguicidas y monóxido: no distingue intención), alcance exacto del síndrome meníngeo y la baja de Tamaulipas,
series escasas (tos ferina y monóxido). Cada cifra se recalcula del dataset v2, la vista o el raw y aborta si no
coincide con la del dictamen. Idempotente.

Uso: postedita_controles5.py --fe <frontend> --be <backend> --runs <runs>
"""
import argparse, collections, csv, glob, json, statistics

ap = argparse.ArgumentParser()
for k in ('--fe', '--be', '--runs'):
    ap.add_argument(k, required=True)
a = ap.parse_args()

LAG = {'coqueluchoide_u99': 0, 'plaguicidas_t60': 1, 'tos_ferina_a37': 0, 'sindrome_meningeo_g00': 1, 'monoxido_t58': 1}
SEXO = {'coqueluchoide_u99': (74.9, 77.8), 'plaguicidas_t60': (43.9, 41.0), 'tos_ferina_a37': (89.9, 91.9),
        'sindrome_meningeo_g00': (73.7, 70.0), 'monoxido_t58': (88.2, 83.4)}
ANCLA = '        <p class="mono-meta" id="releaseMeta"></p>\n'
FIN03 = ' en el total nacional.</p></div>\n        <div class="step"><div class="n">04 · Seguimiento</div>'
FIN01 = ' registros entidad-sexo-semana.</p></div>\n'


def sub(s, x, y):
    if y in s and x not in s:
        return s
    assert s.count(x) == 1, (x[:80], s.count(x)); return s.replace(x, y)


def medir(d):
    v = json.load(open(f'{a.fe}/publication/{d}/vista.json'))
    rows = list(csv.DictReader(open(f"{a.runs}/{v['observation_dataset_id']}/epi_dataset_v2.csv", encoding='utf-8')))
    L = LAG[d]; lo, hi = (2025, 44 + (1 - L)), (2026, 42 + (1 - L))
    an = collections.Counter(); wk = collections.Counter(); fb = fbw = nw = 0
    for r in rows:
        y, w = int(r['epi_year']), int(r['epi_week']); c = float(r['y_cases']); an[y] += c
        f = 'sex_fallback' in r['quality_flags']; fb += f
        if lo <= (y, w) <= hi:
            wk[(y, w)] += c; nw += 1; fbw += f
    assert len(wk) == 52, (d, len(wk))
    return v, {k: int(round(x)) for k, x in an.items()}, int(round(sum(wk.values()))), statistics.median(wk.values()), \
        round(100 * fb / len(rows), 1), round(100 * fbw / nw, 1), (lo, hi)


def comp(v):
    c = {x['ambito']: x for x in v['caida_al_control']['comprobaciones']}['smape_nacional_general']
    return round(c['portafolio'], 1), round(c['control'], 1)


def p(clase, texto):
    return f'        <p class="{clase}">{texto}</p>\n'


for d in LAG:
    f = f'{a.fe}/{d}.html'; s = open(f, encoding='utf-8').read()
    v, an, vent, med, fb, fbw, (lo, hi) = medir(d)
    assert (fb, fbw) == SEXO[d], (d, fb, fbw)
    pn, cn = comp(v)
    s = sub(s, 'no superó la prueba de 2025 y el autor autorizó publicar el control.',
            'no superó la prueba de 2025 y un dictamen tomado bajo delegación del autor autorizó publicar el control.')
    s = sub(s, 'por decisión del autor del 15 de noviembre de 2026)', 'por un dictamen tomado bajo delegación del autor del 15 de noviembre de 2026)')
    if 'W43, W44, W45 ya habían concluido' in s:
        s = s.replace('W43, W44, W45 ya habían concluido', 'W43, W44 y W45 ya habían concluido')
    s = sub(s, FIN01, f' registros entidad-sexo-semana. En toda la serie, el reparto por sexo de {fb} % de las filas base sale de ese respaldo '
            f'({fbw} % en las semanas que repite el control): en esas filas el desglose por sexo no es un dato observado.</p></div>\n')
    ventana = f'{lo[0]}-W{lo[1]:02d} a {hi[0]}-W{hi[1]:02d}'
    extra03 = (f' El control repite lo observado 52 semanas antes ({ventana}), incluidos sus picos y los valores que la fuente retiró '
               'después; el portafolio de modelos fue rechazado en su única prueba de 2025.')
    notas = []
    if d == 'coqueluchoide_u99':
        assert (an[2024], an[2025], an[2026], vent) == (1756, 5289, 1224, 1483), (an, vent)
        assert (pn, cn) == (140.5, 97.2)
        extra03 += (f' En el total nacional de 2025 el control tuvo sMAPE {cn} (el portafolio, {pn}; MASE del control, 2.11): no anticipó '
                    'el salto de 2025 y no anticipa brotes.')
        notas.append(f'<strong>Definición sindrómica.</strong> El síndrome coqueluchoide es una definición de vigilancia por síntomas, '
                     'distinta de la tos ferina confirmada (A37), que tiene su propia serie y su propio control: las dos no se suman.')
        notas.append(f'<strong>Salto de 2025.</strong> Se notificaron {an[2025]:,} casos en 2025, frente a {an[2024]:,} en 2024; en 2026, '
                     f'hasta el boletín 43, {an[2026]:,}. Las semanas que repite el control suman {vent:,}.')
    if d == 'tos_ferina_a37':
        assert (an[2024], an[2025], an[2026], vent, med) == (461, 1600, 204, 258, 4.0), (an, vent, med)
        assert (pn, cn) == (169.7, 108.7)  # la vista sellada redondea 108.75 a 108.7
        extra03 += (f' En el total nacional de 2025 el control tuvo sMAPE {cn} (el portafolio, {pn}; MASE del control, 2.27), el mayor error '
                    'de los controles de esta tanda: no anticipó el brote de 2025 y no anticipa brotes, así que los valores bajos del horizonte '
                    'no significan que no se espere uno.')
        notas.append('<strong>Serie distinta del síndrome coqueluchoide.</strong> La tos ferina (A37) y el síndrome coqueluchoide (U99) son '
                     'series distintas del boletín: no se suman.')
        notas.append(f'<strong>Serie escasa.</strong> En las semanas que repite el control, la mediana nacional fue de {med:.0f} casos por semana '
                     f'({vent} en 52 semanas) y la mayoría de las semanas estatales valen cero. Se notificaron {an[2025]:,} casos en 2025, frente a '
                     f'{an[2024]:,} en 2024; en 2026, hasta el boletín 43, {an[2026]:,}.')
    if d == 'monoxido_t58':
        assert (vent, med) == (483, 8.0), (vent, med)
        notas.append(f'<strong>Serie escasa.</strong> En las semanas que repite el control, la mediana nacional fue de {med:.0f} casos por semana '
                     f'({vent} en 52 semanas) y la mayoría de las semanas estatales valen cero.')
    if d in ('plaguicidas_t60', 'monoxido_t58'):
        cod = 'T60' if d == 'plaguicidas_t60' else 'T58'
        notas.append(f'<strong>No distingue intención.</strong> El código {cod} describe la naturaleza de la lesión, no si fue accidental, '
                     'laboral, autoinfligida o por agresión: la serie cuenta intoxicaciones notificadas de cualquier intención. Esta página no '
                     'describe mecanismos, productos ni dosis. Si estás pensando en hacerte daño, llama a la Línea de la Vida, gratis y las '
                     '24 horas: 800 911 2000, o al 911 en una emergencia.')
    if d == 'sindrome_meningeo_g00':
        R = glob.glob(f'{a.be}/artifacts/observations/{d}/*/inputs/data_raw_*.csv')[0]
        T = {(int(r['Anio']), int(r['Semana'])): r for r in csv.DictReader(open(R, encoding='utf-8')) if r['Entidad'] == 'Tamaulipas'}
        ac = lambda r: int(float(r['Acumulado_hombres'] or 0) + float(r['Acumulado_mujeres'] or 0))
        assert (ac(T[(2025, 46)]), ac(T[(2025, 47)]), int(float(T[(2025, 47)]['Casos_semana']))) == (118, 62, 4) or \
               (ac(T[(2025, 46)]), ac(T[(2025, 47)])) == (118, 62), (ac(T[(2025, 46)]), ac(T[(2025, 47)]))
        notas.append('<strong>Alcance exacto.</strong> La serie es el renglón del boletín «síndrome meníngeo» (G00-G03, excepto G00.0 y G00.1). '
                     'No es la meningitis meningocócica, ni la causada por Haemophilus influenzae (G00.0) o por neumococo (G00.1), ni la '
                     'tuberculosa, ni el total de meningitis: cada una se notifica en otro renglón.')
        notas.append('<strong>Una corrección de la fuente anterior a la ventana.</strong> Entre los boletines 2025_sem46 y 2025_sem47 el acumulado '
                     'anual de Tamaulipas bajó de 118 a 62: la fuente retiró casos de semanas de 2025 anteriores a las que repite el control. '
                     'El control no los repite, pero la verdad de 2025 con la que se probaron portafolio y control los contenía por igual. '
                     'Se declara y no se recalcula.')
    cb = {x['ambito']: x for x in v['caida_al_control']['comprobaciones']}['smape_bases']['control']
    if cb >= 70:  # mismo umbral y texto que los controles anteriores (controlEstatalPocoInformativo en el EpiBot)
        extra03 += f' Por estado es una referencia poco informativa: su error en las series por estado y sexo fue sMAPE {cb:.1f} en esa prueba.'
    s = sub(s, FIN03, ' en el total nacional.' + extra03 + FIN03[len(' en el total nacional.'):])
    for n in notas:
        bloque = p('nota-alcance', n)
        if bloque not in s:
            assert s.count(ANCLA) == 1; s = s.replace(ANCLA, bloque + ANCLA)
    open(f, 'w', encoding='utf-8').write(s)
    print(d, 'ok', fb, fbw, pn, cn)
