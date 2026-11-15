"""Post-edición medida de las fichas de los doce controles de alta20c (dictamen delegado de Fable §1).

Añade, sin tocar datos ni pronósticos:
  - avisos de valores retirados por la propia fuente (absceso hepático, Estado de México, 2026-W01; bocio,
    Morelos, 2026-W24; desnutrición moderada, Oaxaca, 2025-W52, hallazgo de este paso fuera del dictamen);
  - avisos de picos sostenidos en el acumulado (leptospirosis en Veracruz, fiebre reumática en Querétaro,
    desnutrición severa en Jalisco y Querétaro);
  - el porcentaje de filas base con reparto por sexo de respaldo en las siete series escasas;
  - la nota de rótulo 2014-2016 de otras helmintiasis y el alcance de hepatitis B (sólo aguda, B16).
Cada cifra se mide aquí contra el raw sellado de la observación, el dataset v2 y la vista; si no coincide con la
cifra cotejada a mano contra el texto del PDF (txt/), aborta. Idempotente: si el aviso ya está, no lo repite.

Uso: postedita_controles12.py --fe <frontend> --be <backend>
"""
import argparse, csv, glob, json, sys

ap = argparse.ArgumentParser(); ap.add_argument('--fe', required=True); ap.add_argument('--be', required=True)
a = ap.parse_args()
sys.path[:0] = [f'{a.be}/src']
from epiforecast.data import epi_calendar as cal  # noqa: E402

ANCLA = '        <p class="mono-meta" id="releaseMeta"></p>\n'
ESC = ['brucelosis_a23', 'reumatica_i00', 'bocio_e01', 'hepatitis_b_b16', 'rotavirus_a080',
       'absceso_hepatico_a064', 'leptospirosis_a27']


def raw(d):
    p = glob.glob(f'{a.be}/artifacts/observations/{d}/*/inputs/data_raw_*.csv'); assert len(p) == 1, p
    return {(int(r['Anio']), int(r['Semana']), r['Entidad']): r for r in csv.DictReader(open(p[0], encoding='utf-8'))}


def acum(r):
    f = lambda x: float(x) if x not in ('', None) else 0.0
    return int(f(r['Acumulado_hombres']) + f(r['Acumulado_mujeres']))


def vista(d):
    return json.load(open(f'{a.fe}/publication/{d}/vista.json'))


def pron(d, ent, y, w):
    """Valor del pronóstico estatal y nacional 52 semanas después de (y, w)."""
    v = vista(d)
    s = next(x for k, x in v['series'].items() if k.startswith('estado|') and k.endswith('|general') and x['nombre'] == ent)
    ty, tw = cal.shift(y, w, 52); ds = str(cal.ds_for(ty, tw))[:10]
    est = dict(s['pronostico'])[ds]; nac = dict(v['series']['nacional|mx|general']['pronostico'])[ds]
    return (ty, tw), int(est), int(nac)


def boletin(y, w):
    """Boletín que trae la semana objetivo (y, w): rezago 1 en los doce grupos."""
    return cal.shift(y, w, 1)


def de(nombre):
    return 'del ' + nombre[3:] if nombre.startswith('el ') else 'de ' + nombre


def p(clase, clave, titulo, texto):
    return f'        <p class="{clase}" data-aviso="{clave}"><strong>{titulo}</strong> {texto}</p>\n'


def retiro(d, ent, nombre, y, w, casos, acum_pub, acum_sig):
    R = raw(d); by, bw = boletin(y, w); sy, sw = cal.shift(by, bw, 1)
    r1, r2 = R[(by, bw, ent)], R[(sy, sw, ent)]
    assert int(float(r1['Casos_semana'])) == casos and acum(r1) == acum_pub and acum(r2) == acum_sig, (d, ent, r1, r2)
    (ty, tw), est, nac = pron(d, ent, y, w)
    assert est == casos, (d, ent, est)
    return p('aviso-fuente', f'{ent}|{y}-W{w:02d}', 'Un valor que la propia fuente retiró.',
             f'El boletín {by}_sem{bw:02d} imprimió {casos} casos {de(nombre)} en la semana {y}-W{w:02d}, con un acumulado anual de {acum_pub}; '
             f'el boletín siguiente, {sy}_sem{sw:02d}, imprimió un acumulado de {acum_sig}, así que la fuente retiró ese valor. '
             f'El control repite lo impreso 52 semanas antes y no tiene un criterio vigente para excluir un valor impreso y luego retirado: '
             f'el pronóstico de {ty}-W{tw:02d} trae esos {casos} casos {de(nombre)}, de {nac} nacionales. Esa semana no debe leerse como un aumento esperado. '
             'El dato y el pronóstico se publican sin modificar.')


def sostenido(d, ent, nombre, y, w, casos):
    R = raw(d); by, bw = boletin(y, w); py, pw = cal.shift(by, bw, -1); sy, sw = cal.shift(by, bw, 1)
    r0, r1, r2 = R[(py, pw, ent)], R[(by, bw, ent)], R[(sy, sw, ent)]
    assert int(float(r1['Casos_semana'])) == casos, (d, ent, r1)
    assert acum(r1) - acum(r0) >= casos - 2 and acum(r2) >= acum(r1) - 2, (d, ent, acum(r0), acum(r1), acum(r2))
    return p('aviso-fuente', f'{ent}|{y}-W{w:02d}|sostenido', 'Un pico que la fuente conserva.',
             f'Los {casos} casos {de(nombre)} en {y}-W{w:02d} siguen en el acumulado anual de los boletines siguientes '
             f'({acum(r0)} antes, {acum(r1)} con esa semana y {acum(r2)} en {sy}_sem{sw:02d}): la fuente no los retiró.')


def lepto():
    d, ent = 'leptospirosis_a27', 'Veracruz'; R = raw(d)
    sem = [(2025, 44, 130), (2025, 45, 65), (2025, 46, 29)]
    pr = []
    for y, w, c in sem:
        by, bw = boletin(y, w); assert int(float(R[(by, bw, ent)]['Casos_semana'])) == c, (y, w)
        pr.append(pron(d, ent, y, w))
    by0, bw0 = boletin(2025, 43); prev = int(float(R[(by0, bw0, ent)]['Casos_semana']))
    a0, a3 = acum(R[boletin(2025, 43) + (ent,)]), acum(R[boletin(2025, 47) + (ent,)])
    assert [x[1] for x in pr] == [c for _, _, c in sem], pr
    (t1, _, n1) = pr[0]
    return p('aviso-fuente', f'{ent}|2025-W44..W46', 'Picos que la fuente conserva.',
             f'El boletín imprimió 130, 65 y 29 casos de Veracruz en 2025-W44, W45 y W46, frente a {prev} en la semana anterior; '
             f'el acumulado anual de Veracruz pasó de {a0} a {a3} y no se retiró. Como 2025 tuvo 53 semanas, el control los repite en '
             f'2026-W43, W44 y W45, las primeras semanas del horizonte: en 2026-W43 son {pr[0][1]} de los {n1} casos nacionales pronosticados. '
             'Esas semanas no deben leerse como un brote esperado.')


def fallback_pct(d):
    v = vista(d)
    rows = list(csv.DictReader(open(f"{a.be}/runs/{v['observation_dataset_id']}/epi_dataset_v2.csv")))
    n = sum(r['quality_flags'].startswith('sex_fallback') for r in rows)
    return n, len(rows)


AVISOS = {
    'absceso_hepatico_a064': [lambda: retiro('absceso_hepatico_a064', 'México', 'el Estado de México', 2026, 1, 125, 125, 1)],
    'bocio_e01': [lambda: retiro('bocio_e01', 'Morelos', 'Morelos', 2026, 24, 22, 55, 9)],
    'desnutricion_moderada_e440': [lambda: retiro('desnutricion_moderada_e440', 'Oaxaca', 'Oaxaca', 2025, 52, 139, 490, 364)],
    'leptospirosis_a27': [lepto],
    'reumatica_i00': [lambda: sostenido('reumatica_i00', 'Querétaro', 'Querétaro', 2026, 23, 52)],
    'desnutricion_severa_e40': [lambda: sostenido('desnutricion_severa_e40', 'Jalisco', 'Jalisco', 2026, 34, 152),
                                lambda: sostenido('desnutricion_severa_e40', 'Querétaro', 'Querétaro', 2026, 37, 91)],
}

FIN_DATOS = ' registros entidad-sexo-semana.</p></div>\n'

for d in sorted(set(AVISOS) | set(ESC) | {'helmintiasis_b65', 'hepatitis_b_b16'}):
    f = f'{a.fe}/{d}.html'; s = open(f, encoding='utf-8').read(); s0 = s
    for mk in AVISOS.get(d, []):
        bloque = mk()
        if bloque not in s:
            assert s.count(ANCLA) == 1, (d, 'ancla releaseMeta')
            s = s.replace(ANCLA, bloque + ANCLA)
    extra = ''
    if d in ESC:
        n, tot = fallback_pct(d)
        extra += (f' En toda la serie, {n:,} de {tot:,} filas base ({100 * n / tot:.0f} %) toman el reparto por sexo de ese respaldo '
                  'y no de un dato impreso por sexo: las series por sexo deben leerse con esa reserva.')
    if d == 'helmintiasis_b65':
        extra += (' Nota de rótulo: desde 2017 el boletín escribe «excepto B73 y B75» (oncocercosis y triquinosis, con renglón y cuadro propios); '
                  'para 2014-2016 no hay una fuente oficial fechada que acredite textualmente esa exclusión, así que la comparabilidad de esos años no está certificada. '
                  'El control sólo repite semanas de 2025 y 2026, con el rótulo explícito.')
    if d == 'hepatitis_b_b16':
        extra += (' La serie es sólo la hepatitis vírica B aguda (B16); la crónica (B18.0 y B18.1) se cuenta dentro de «Otras hepatitis víricas» '
                  '(B17-B19, excepto B17.1 y B18.2).')
    if extra and extra not in s:
        assert s.count(FIN_DATOS) == 1, (d, 'fin del paso 01')
        s = s.replace(FIN_DATOS, ' registros entidad-sexo-semana.' + extra + '</p></div>\n')
    if s != s0:
        open(f, 'w', encoding='utf-8').write(s)
    print(d, 'editada' if s != s0 else 'sin cambios')

# Paso 03: referencia estatal poco informativa (error del control por estado >= 70, mismo texto que alta10b y que
# rag.mjs con controlEstatalPocoInformativo) y, en las siete escasas, semanas en cero que abaratan el sMAPE estatal.
import statistics  # noqa: E402
POCO = {'desnutricion_moderada_e440', 'desnutricion_severa_e40', 'enterobiasis_b80', 'giardiasis_a071'}
FIN03 = ' en el total nacional.</p></div>\n        <div class="step"><div class="n">04 · Seguimiento</div>'
for d in sorted(POCO | set(ESC)):
    f = f'{a.fe}/{d}.html'; s = open(f, encoding='utf-8').read(); s0 = s
    v = vista(d); comp = {c['ambito']: c for c in v['caida_al_control']['comprobaciones']}
    c = comp['smape_bases']['control']
    if d in POCO:
        assert c >= 70, (d, c)
        extra = f' Por estado es una referencia poco informativa: su error en las series por estado y sexo fue sMAPE {c:.1f} en esa prueba.'
    else:
        assert c < 70, (d, c)
        rows = [r for r in csv.DictReader(open(f"{a.be}/runs/{v['observation_dataset_id']}/epi_dataset_v2.csv")) if r['epi_year'] == '2025']
        by = {}
        for r in rows:
            by.setdefault((r['cve_ent'], r['sexo']), []).append(float(r['y_cases']))
        assert len(by) == 64
        med = statistics.median(sum(x == 0 for x in xs) / len(xs) for xs in by.values())
        extra = (f' Ese error estatal bajo no demuestra que el control funcione por estado: en 2025, la mediana de semanas en cero por serie estatal y sexo fue {100 * med:.0f} %, '
                 'y una semana en la que el valor observado y el pronosticado valen cero cuenta como error nulo.')
    if extra not in s:
        assert s.count(FIN03) == 1, (d, 'fin del paso 03')
        s = s.replace(FIN03, ' en el total nacional.' + extra + FIN03[len(' en el total nacional.'):])
    if s != s0:
        open(f, 'w', encoding='utf-8').write(s)
    print(d, 'paso 03', 'editada' if s != s0 else 'sin cambios')

# La publicación de estos doce controles no la autorizó el autor por nombre: la decidió un dictamen tomado bajo su
# delegación literal (DELEGACION_AUTOR_FABLE_20261115.json). La plantilla dice «el autor autorizó».
VIEJA = 'no superó la prueba de 2025 y el autor autorizó publicar el control.'
NUEVA = 'no superó la prueba de 2025 y un dictamen tomado bajo delegación del autor autorizó publicar el control.'
for d in ESC + ['helmintiasis_b65', 'desnutricion_moderada_e440', 'desnutricion_severa_e40', 'enterobiasis_b80', 'giardiasis_a071']:
    f = f'{a.fe}/{d}.html'; s = open(f, encoding='utf-8').read()
    if NUEVA not in s:
        assert s.count(VIEJA) == 1, (d, 'frase de autorización')
        s = s.replace(VIEJA, NUEVA); open(f, 'w', encoding='utf-8').write(s); print(d, 'autorización delegada')
