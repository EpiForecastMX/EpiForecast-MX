"""Ficha <id>.html de un padecimiento publicado, desde los metadatos de su release y su vista.

Genérico para el lote alta10b (fusiona gen_fichas17.py y gen_controles10.py de alta20):
  aceptado -> plantilla otitis_h65.html (con sexo) o embarazo_hipertensivos_o10.html (sin sexo);
  control  -> plantilla neumonias_j12.html (control estacional, nunca validado).
No copia cronología, política ni cuadro: sale de publication/<id>/vista.json, del manifiesto del
release, del registry y de meta_publicacion_alta10b.json.

El tipo (aceptado o control) se DERIVA del release_manifest congelado del backend
(chain.acceptance_outcome), ligado a la vista y al puntero público por release_id y al acceptance.json
sellado por su sha256; las marcas de la vista y del registry deben coincidir. Un tipo o release pedido
en la CLI sólo se acepta si coincide. Un aceptado CONTROL_ONLY (portafolio = control) aborta. El sexo se coteja contra las series de la vista en ambos modos.
Sólo se describen las dos políticas conocidas; otra aborta.

La frase «los boletines ... aún no existían al emitir» sólo se escribe con evidencia: una consulta del
índice oficial (--indice, formato de indices/registro.txt) hecha DESPUÉS de la emisión, con http=200 y
un último boletín anterior al primero que trae las semanas objetivo, del mismo año. Si la procedencia
propia del id (config/publication/<id>/bulletin_provenance.json, ligada a la vista por disease_id,
release_id y forecast_emitted_at) dice que alguno de esos boletines ya estaba disponible al emitir, aborta. Sin evidencia, la frase se omite (no se afirma). Los boletines se calculan con el rezago
del grupo y el calendario MMWR canónico (cruza de año).

Uso: gen_fichas.py --fe <frontend> --be <backend> --runs <runs_root> --meta <json> --out <dir>
                   [--indice <registro.txt>]
                   <id>[=<aceptado|control>][:<release_id>] ...
--out permite escribir fuera del frontend (autoprueba contra fichas ya publicadas).
"""
import argparse, csv, json, re, sys
from datetime import datetime
from zoneinfo import ZoneInfo

a = None  # argumentos de la CLI; se fijan en main()

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre']
AMB = {'smape_bases': lambda s: 'las series por estado' if s else 'las series por estado y sexo',
       'smape_all': lambda s: 'el conjunto de las series publicadas',
       'smape_nacional_general': lambda s: 'el total nacional'}
POL = {'rolling_cv_v1': 'compitieron siete motores (cinco estacionales, ETS y regresión armónica)',
       'rolling_cv_baja_incidencia_v1': 'compitieron sólo los cinco motores estacionales (sin ETS ni regresión armónica, por decisión nominal del autor)'}
f1 = lambda x: f'{x:.1f}'
lista = lambda p: p[0] if len(p) == 1 else ', '.join(p[:-1]) + ' y ' + p[-1]


def sub(s, x, y, n=1):
    assert s.count(x) == n, (x[:80], s.count(x)); return s.replace(x, y)


def cie_de(r):
    nc = r.web['nombre_completo']; return nc[nc.rindex('(') + 1:-1]


def fechas(s, v, man=None):
    e = datetime.fromisoformat(v['forecast_emitted_at']).astimezone(ZoneInfo('America/Mexico_City'))
    og = v['origin']
    s, n1 = re.subn(r'id="originTxt">[^<]*<', f'id="originTxt">W{og[1]} de {og[0]}<', s)
    s, n2 = re.subn(r'id="emitTxt">[^<]*<', f'id="emitTxt">{e.day} de {MESES[e.month - 1]} de {e.year}<', s)
    assert n1 == 1 and n2 == 1, ('anclas de fecha', n1, n2)
    return s


def aceptado(d, r, v, m):
    sexo = r.sex_breakdown is not False
    assert sexo == any(k.endswith('|hombres') for k in v['series']), (d, 'sexo del registry distinto del de la vista')
    assert r.selection_policy in POL, (d, f'política sin texto: {r.selection_policy}')
    tpl = 'otitis_h65' if sexo else 'embarazo_hipertensivos_o10'
    T = {'otitis_h65': dict(titulo='Otitis media aguda (H65.0-H65.1)', meta='otitis media aguda (CIE-10 H65.0-H65.1)', corto='Otitis media aguda',
                            lead='la <strong>otitis media aguda (CIE-10 H65.0-H65.1)</strong>', nom='otitis media aguda', cuadro='Cuadro 5'),
         'embarazo_hipertensivos_o10': dict(titulo='Edema, proteinuria y trastornos hipertensivos en el embarazo, parto y puerperio (O10-O16)',
                            meta='edema, proteinuria y trastornos hipertensivos en el embarazo, parto y puerperio (CIE-10 O10-O16)', corto='Hipertensión en el embarazo',
                            lead='el <strong>edema, la proteinuria y los trastornos hipertensivos en el embarazo, parto y puerperio (CIE-10 O10-O16)</strong>',
                            nom='edema, proteinuria y trastornos hipertensivos en el embarazo, parto y puerperio', cuadro='Cuadro 13.5')}[tpl]
    s = open(f'{a.fe}/{tpl}.html', encoding='utf-8').read()
    cie = cie_de(r); titulo = f'{r.display_name} ({cie})'
    reps = [(T['lead'], f"{m['art']} <strong>{m['low']} (CIE-10 {cie})</strong>"), (T['titulo'], titulo),
            (T['meta'], f"{m['low']} (CIE-10 {cie})"),
            (f'aria-label="{T["corto"]} en otras', f'aria-label="{r.web["label"]} en otras'),
            (f'aria-current="page">{T["corto"]}<', f'aria-current="page">{r.web["label"]}<'),
            (f'<h4>{T["cuadro"]} del boletín</h4>', f"<h4>Cuadro {m['cuadro']} del boletín</h4>"), (tpl, d)]
    for x, y in reps:
        assert x in s, (d, x); s = s.replace(x, y)
    s = s.replace(T['nom'], m['low'])
    s = fechas(s, v)
    tw = calendario(v)[0]
    s, n = re.subn(r'\(W\d+ a W\d+ de \d{4}\)', f'({rango_semanas(tw)})', s)
    assert n == 1, (d, 'ancla de semanas objetivo', n)
    if r.selection_policy != 'rolling_cv_v1':
        assert m.get('falla_motores') and m.get('fecha_orden'), (d, 'faltan falla_motores/fecha_orden de la orden del autor')
        pol = (f'El motor de cada serie se eligió con la política <code>{r.selection_policy}</code>: cuatro años de pliegues temporales de 52 semanas en los que el modelo nunca ve el periodo que pronostica. '
               f"Compiten sólo los cinco motores estacionales: en el desarrollo, {m['falla_motores']} no {'produjeron' if ' y ' in m['falla_motores'] else 'produjo'} un pronóstico utilizable en algunas series estatales, y el autor decidió el {m['fecha_orden']} aplicar esta política sin ETS ni Ridge. "
               'El nombre de la política no significa que el padecimiento sea de baja incidencia. El portafolio combina <span id="mtEngines">varios motores</span>.')
        s, n = re.subn(r'El motor de cada serie se eligió con la política <code>[a-z_0-9]+</code>[^:]*:.*?El portafolio combina <span id="mtEngines">varios motores</span>\.', pol, s, flags=re.S)
        assert n == 1, (d, 'politica')
        s = sub(s, 'Superó la prueba de 2025 frente al control estacional.', 'Superó la prueba de 2025 frente al control estacional con la política de cinco motores.')
    rows = list(csv.DictReader(open(f"{a.runs}/{v['observation_dataset_id']}/epi_dataset_v2.csv")))
    if sexo:
        r25 = [x for x in rows if x['epi_year'] == '2025']; est25 = sum(1 for x in r25 if x['quality_flags'].startswith('sex_fallback'))
        x = 'Los totales por sexo se reconcilian para que hombres más mujeres sumen exactamente el total.'
        s = sub(s, x, x + f' Cuando el boletín no permite separar la semana por sexo, el reparto se estima a partir de los acumulados: en 2025 ocurre en {est25:,} de {len(r25):,} registros entidad-sexo-semana.')
    else:
        imput = sum(1 for x in rows if x['observed'] != 'True')
        x = 'las semanas sin dato se imputan de forma causal.'
        s = sub(s, x, f'las semanas sin dato se imputan de forma causal ({imput} de {len(rows):,} registros entidad-semana).')
    p = prospectiva(v, d)
    s = sub(s, ' semanas observadas. Hasta completarlas no se afirma que haya superado la validación.</p>', ' semanas observadas. Hasta completarlas no se afirma que haya superado la validación.' + (' ' + p if p else '') + '</p>')
    left = [w for w in ['otitis', 'Otitis', 'H65', 'embarazo_hipertensivos', 'O10-O16', 'proteinuria', 'Cuadro 5 '] if w in s]
    assert not left, (d, left)
    return s


LAG = 1  # rezago del grupo (observation_lag_weeks); main() lo fija por id


def calendario(v):
    """Semanas objetivo, boletines (año, número) que las traen y estado MMWR al emitir."""
    from datetime import timedelta
    from epiforecast.data import epi_calendar as cal
    oy, ow = v['origin']; tw = [cal.shift(oy, ow, k) for k in range(1, int(v.get('weeks_required', 4)) + 1)]
    bol = [cal.shift(y, w, LAG) for y, w in tw]
    e = datetime.fromisoformat(v['forecast_emitted_at']).astimezone(ZoneInfo('America/Mexico_City')).date()
    fin = [w for w in tw if cal.week_start(*w) + timedelta(days=7) <= e]
    cur = [w for w in tw if cal.week_start(*w) <= e < cal.week_start(*w) + timedelta(days=7)]
    partes = []
    if fin:
        partes.append(('W' + ' y W'.join(str(w[1]) for w in fin) if len(fin) <= 2 else ', '.join(f'W{w[1]}' for w in fin)) + (' ya habían concluido' if len(fin) > 1 else ' ya había concluido'))
    if cur:
        partes.append(f'W{cur[0][1]} estaba en curso')
    cola = (', aunque en el calendario ' + ' y '.join(partes) if partes else '') + '.'
    return tw, bol, cola


def rango_semanas(tw):
    a, b = tw[0], tw[-1]
    return f'W{a[1]} a W{b[1]} de {b[0]}' if a[0] == b[0] else f'W{a[1]} de {a[0]} a W{b[1]} de {b[0]}'


def rango_boletines(bol):
    a, b = bol[0], bol[-1]
    return f'{a[1]} a {b[1]}' if a[0] == b[0] else f'{a[1]} de {a[0]} a {b[1]} de {b[0]}'


def procedencia(v, d):
    """bulletin_provenance.json propio del id (config/publication/<id>/), ligado a la vista."""
    import os
    p = f'{a.be}/config/publication/{d}/bulletin_provenance.json' if d else None
    if not p or not os.path.exists(p):
        return None
    pr = json.load(open(p))
    for k in ('disease_id', 'release_id', 'forecast_emitted_at'):
        esperado = d if k == 'disease_id' else v[k]
        assert pr.get(k) == esperado, (d, f'procedencia con {k} {pr.get(k)!r}, la vista dice {esperado!r}')
    return pr


def disponibilidad(v, d=None):
    """True sólo si hay evidencia de que ningún boletín objetivo existía al emitir: una consulta del
    índice oficial posterior a la emisión. Aborta si la procedencia propia del id lo contradice.
    False = sin evidencia (no se afirma nada)."""
    _, bol, _ = calendario(v)
    emit = datetime.fromisoformat(v['forecast_emitted_at'])
    pr = procedencia(v, d)
    if pr:
        nombres = {f'sem{w:02d}.pdf' for y, w in bol} | {f'{y}_sem{w:02d}.pdf' for y, w in bol}
        for b in pr.get('bulletins', []):
            if b['name'] in nombres and b['after_emission'].get('first_available') is False:
                raise AssertionError(f"{b['name']} ya estaba disponible al emitir (bulletin_provenance de {d})")
    if not a.indice:
        return False
    for linea in open(a.indice):
        p = linea.split()
        if len(p) < 4 or not p[1] == 'http=200':
            continue
        ts = datetime.strptime(p[0], '%Y%m%dT%H%M%SZ').replace(tzinfo=ZoneInfo('UTC'))
        ultimo = int(p[3].split('=')[1])
        if ts >= emit and all(y == ts.year for y, _ in bol) and ultimo < bol[0][1]:
            return True
    return False


def semanas_objetivo(v, d=None):
    tw, bol, cola = calendario(v)
    base = f'Esas semanas ({rango_semanas(tw)}) llegan con los boletines {rango_boletines(bol)}'
    return base + (', que no existían al emitir' + cola if disponibilidad(v, d) else '.')


def prospectiva(v, d=None):
    tw, bol, cola = calendario(v)
    if not disponibilidad(v, d):
        return ''
    return f'Es prospectiva respecto de la información publicada: al emitir, los boletines {rango_boletines(bol)}, que traerán esas semanas, aún no existían' + cola


def picos(d, v):
    """Aviso (no texto automático): el control lag52 repite cualquier pico de las últimas 52
    semanas observadas. Lista semanas estatales > 5 veces la mediana y > 3 veces ambas vecinas para
    que se redacte, si procede, una nota «pico heredado» revisada contra el PDF."""
    import pandas as pd
    df = pd.read_csv(f"{a.runs}/{v['observation_dataset_id']}/epi_dataset_v2.csv")
    col = 'y_cases'
    gcols = [c for c in ('geography_id', 'cve_ent') if c in df.columns][:1]
    df = df.groupby(gcols + ['epi_year', 'epi_week'], as_index=False)[col].sum().sort_values(gcols + ['epi_year', 'epi_week'])
    ult = df.groupby(gcols).tail(54)
    for g, x in ult.groupby(gcols):
        y = x[col].to_numpy(); med = max(float(pd.Series(y).median()), 1.0)
        for k in range(1, len(y) - 1):
            if y[k] > 5 * med and y[k] > 3 * max(y[k - 1], y[k + 1], 1):
                print(f'  AVISO pico heredado {d} {g} {int(x.epi_year.iloc[k])}-W{int(x.epi_week.iloc[k])}: {int(y[k])} (mediana {med:.0f}); revisar PDF y redactar nota')


def control(d, r, v, m):
    s = open(f'{a.fe}/neumonias_j12.html', encoding='utf-8').read()
    sinsexo = r.sex_breakdown is False
    assert sinsexo == (not any(k.endswith('|hombres') for k in v['series'])), (d, 'sexo')
    nc = r.web['nombre_completo']; cie = cie_de(r); lab = r.web['label']; low = m['low']
    cc = v['caida_al_control']; comp = {c['ambito']: c for c in cc['comprobaciones']}
    fall = [f"{AMB[x](sinsexo)} (sMAPE {f1(c['portafolio'])} frente a {f1(c['control'])} del control)" for x, c in comp.items() if not c['pasa']]
    errc = lista([f"{f1(comp[x]['control'])} en {AMB[x](sinsexo)}" for x in ('smape_bases', 'smape_all', 'smape_nacional_general')])
    s = sub(s, 'Neumonías y bronconeumonías (J12-J18) · Pronóstico semanal', f'{nc} · Pronóstico semanal', 2)
    s = sub(s, 'neumonías y bronconeumonías (CIE-10 J12-J18 excepto J18.2, J13 y J14) reportados al SINAVE para las 32 entidades de México, por sexo, a 52 semanas. Se publica el control estacional, sin intervalos de incertidumbre.',
            f"{low} (CIE-10 {cie}) reportados al SINAVE para las 32 entidades de México{'' if sinsexo else ', por sexo'}, a 52 semanas. Se publica el control estacional, no validado, sin intervalos de incertidumbre.")
    s = sub(s, 'aria-label="Neumonías en otras herramientas"', f'aria-label="{lab} en otras herramientas"')
    s = sub(s, 'aria-current="page">Neumonías<', f'aria-current="page">{lab}<')
    s = s.replace('neumonias_j12', d)
    s = sub(s, """incorpora las <strong>neumonías y bronconeumonías (CIE-10 J12-J18 excepto J18.2, J13 y J14)</strong>. Publicamos los casos semanales esperados para las <strong>32 entidades, por sexo</strong>, con un horizonte de <strong>52 semanas</strong>. <strong>Es un pronóstico de control:</strong> cada semana repite los casos de 52 semanas antes, porque el portafolio de modelos no superó la prueba de 2025.""",
            f"""incorpora {m['art']} <strong>{low} (CIE-10 {cie})</strong>. Publicamos los casos semanales esperados para las <strong>32 entidades{'' if sinsexo else ', por sexo'}</strong>, con un horizonte de <strong>52 semanas</strong>. <strong>Es un control estacional, no validado:</strong> cada semana repite los casos de 52 semanas antes, porque el portafolio de modelos no superó la prueba de 2025 y el autor autorizó publicar el control.""")
    s = fechas(s, v)
    s = sub(s, 'Casos semanales de neumonías y bronconeumonías observados', f'Casos semanales de {low} observados')
    p1 = re.search(r'<div class="step"><div class="n">01 · Datos</div>.*?</div>\n', s).group(0)
    datos = (f"La serie semanal de {low} por entidad se extrae del Boletín Epidemiológico del SINAVE desde 2014; el boletín no la desglosa por sexo." if sinsexo else
             f"La serie semanal de {low} por entidad y sexo se extrae del Boletín Epidemiológico del SINAVE desde 2014. Los totales por sexo se reconcilian para que hombres más mujeres sumen exactamente el total; cuando el boletín no separa la semana por sexo, el reparto se reconstruye a partir de los acumulados.")
    s = s.replace(p1, f"<div class=\"step\"><div class=\"n\">01 · Datos</div><h4>Cuadro {m['cuadro']} del boletín</h4><p>{datos}</p></div>\n")
    if sinsexo:
        p2 = re.search(r'<div class="step"><div class="n">02 · Modelos</div>.*?</div>\n', s).group(0)
        s = s.replace(p2, '<div class="step"><div class="n">02 · Modelos</div><h4>32 modelos, uno por entidad</h4><p>Cada entidad tiene su propio modelo. Las <span id="mtProducts">37</span> series publicadas (32 entidades, 4 regiones y el nacional) incluyen las regiones y el nacional, que se derivan sumando las entidades y nunca se modelan por separado.</p></div>\n')
        s = sub(s, '<div class="v" id="stModels">64</div>', '<div class="v" id="stModels">32</div>'); s = sub(s, '<div class="v" id="stProducts">111</div>', '<div class="v" id="stProducts">37</div>')
        s = sub(s, 'Elige una geografía y un sexo.', 'Elige una geografía.')
        blk = re.search(r'        <div class="ctl">\n          <span>Sexo</span>.*?</div>\n        </div>\n', s, re.S).group(0); s = s.replace(blk, '')
        s = sub(s, 'Las series estatales por sexo tienen menos casos', 'Las series estatales tienen menos casos')
    assert r.selection_policy in POL, (d, f'política sin texto: {r.selection_policy}')
    if r.selection_policy == 'rolling_cv_v1':
        pol_txt = POL[r.selection_policy]
    else:
        assert m.get('fecha_orden'), (d, 'falta fecha_orden de la orden del autor')
        pol_txt = f"compitieron sólo los cinco motores estacionales (sin ETS ni regresión armónica, por decisión del autor del {m['fecha_orden']})"
    picos(d, v)
    p3 = re.search(r'<div class="step"><div class="n">03 · Selección y rechazo</div>.*?</div>\n', s).group(0)
    s = s.replace(p3, f'<div class="step"><div class="n">03 · Selección y rechazo</div><h4>El portafolio no pasó la prueba de 2025</h4><p>Con la política <code>{r.selection_policy}</code> {pol_txt} en pliegues de 2021 a 2024. '
                      f'En 2025, con la selección ya congelada, el portafolio empeoró {lista(fall)} más de lo que permite la regla (5 % en las series base y en el conjunto, 10 % en el total nacional). Basta un ámbito reprobado para rechazar el portafolio, y la regla, fijada antes de abrir 2025, deja entonces el motor de control: <span id="mtEngines">naive estacional</span>. '
                      f'Error del control en esa prueba (sMAPE): {errc}.</p></div>\n')
    s = sub(s, 'no de prevalencia de neumonías y bronconeumonías en la población', f'no de la frecuencia de {low} en la población')
    s = sub(s, 'No se pudieron cargar los datos de neumonías y bronconeumonías.', f'No se pudieron cargar los datos de {low}.')
    if not sinsexo:
        rows = list(csv.DictReader(open(f"{a.runs}/{v['observation_dataset_id']}/epi_dataset_v2.csv")))
        r25 = [x for x in rows if x['epi_year'] == '2025']; est25 = sum(1 for x in r25 if x['quality_flags'].startswith('sex_fallback'))
        s = sub(s, 'el reparto se reconstruye a partir de los acumulados.</p>', f'el reparto se reconstruye a partir de los acumulados: en 2025 ocurre en {est25:,} de {len(r25):,} registros entidad-sexo-semana.</p>')
    s = sub(s, ' semanas registradas.</p>', ' semanas registradas. ' + semanas_objetivo(v, d) + '</p>')
    s = re.sub(r"      const rechazo = V\.caida_al_control\.comprobaciones\.find\(\(c\) => c\.ambito === 'smape_nacional_general'\);\n      \$\('rejPortafolio'\)\.textContent = nf1\.format\(rechazo\.portafolio\);\n      \$\('rejControl'\)\.textContent = nf1\.format\(rechazo\.control\);\n", '', s)
    left = [x for x in ['eumon', 'J12', 'J18', '5.1 y 5.2', 'rejPortafolio', 'rejControl'] if x in s]
    assert not left, (d, left)
    return s


def tipo_de_publicacion(d, r, v, fe, be=None, runs=None):
    """Estado comunicativo del release, desde las fuentes canónicas, ligadas entre sí:
      release_manifest.v2 congelado (artifacts/releases/<id>/<release>/): chain.acceptance_outcome,
        acceptance_run_id/digest (sha256 del acceptance.json sellado), calendar.origin;
      shard FE (publication_shard.v1): mismo release_id, disease_id, origin, lifecycle published y
        veredicto igual al de la vista; puntero público al mismo release;
      prospective_gate.v1 (config/publication/<id>/): CONTROL_ONLY si el pronóstico candidato es el
        del control (candidate_forecast_digest == control_forecast_digest, como status.py).
    Tres estados: «aceptado» (contraste propio), «aceptado_control_only» (aceptación retrospectiva con
    portafolio idéntico al control: no es rechazo ni tiene validación propia; sin plantilla, aborta) y
    «control» (caída al control tras rechazo, acceptance_fallback_run = chain.acceptance_run_id).
    Las marcas de vista y registry deben concordar. Cualquier discordancia aborta."""
    import hashlib
    import os
    be = be or a.be; runs = runs or a.runs
    rel = v['release_id']
    fe_p = f"{fe}/publication/{d}/{rel}/manifest.json"
    assert os.path.exists(fe_p), (d, 'release de la vista sin shard propio')
    sh = json.load(open(fe_p))
    assert sh.get('schema') == 'publication_shard.v1' and sh.get('disease_id') == d and sh.get('release_id') == rel, (d, 'shard de otro release')
    assert sh.get('lifecycle') == 'published', (d, f"shard con lifecycle {sh.get('lifecycle')}")
    assert list(sh.get('origin', [])) == list(v['origin']), (d, 'origen del shard distinto del de la vista')
    assert sh.get('publication_status', {}).get('verdict') == v.get('verdict'), (d, 'veredicto del shard distinto del de la vista')
    ptr = json.load(open(f'{be}/config/publication/{d}/public_release_pointer.json'))
    assert ptr['release_id'] == rel and ptr['disease_id'] == d, (d, 'puntero público y vista con releases distintos')
    rm_p = f'{be}/artifacts/releases/{d}/{rel}/release_manifest.json'
    assert os.path.exists(rm_p), (d, f'sin release_manifest congelado {rm_p}')
    rm = json.load(open(rm_p)); ch = rm['chain']
    assert rm.get('schema') == 'release_manifest.v2' and rm['release_id'] == rel and rm['disease_id'] == d, (d, 'release_manifest de otro release')
    assert list(rm['calendar']['origin']) == list(v['origin']), (d, 'origen del release distinto del de la vista')
    salida = ch.get('acceptance_outcome', 'accepted')
    assert salida in ('accepted', 'fallback_control'), (d, f'resultado desconocido {salida}')
    acc_p = f"{runs}/{ch['acceptance_run_id']}/acceptance.json"
    assert os.path.exists(acc_p), (d, f'sin acceptance.json sellado de {ch["acceptance_run_id"]}')
    assert hashlib.sha256(open(acc_p, 'rb').read()).hexdigest() == ch['acceptance_digest'], (d, 'acceptance.json distinto del sellado')
    assert json.load(open(acc_p))['accepted'] == (salida == 'accepted'), (d, 'acceptance.json y release_manifest discrepan')
    gate = json.load(open(f'{be}/config/publication/{d}/prospective_gate.json'))
    assert gate['release_id'] == rel and gate['disease_id'] == d, (d, 'gate prospectivo de otro release')
    control_only = gate['candidate_forecast_digest'] == gate['control_forecast_digest']
    control = salida == 'fallback_control'
    en_vista = 'caida_al_control' in v
    en_registry = bool(getattr(r, 'acceptance_fallback_run', None))
    assert en_vista == control and en_registry == control, (d, f'release dice control={control}, vista={en_vista}, registry={en_registry}')
    if control:
        assert r.acceptance_fallback_run == ch['acceptance_run_id'], (d, 'acceptance_fallback_run no es el run del release')
        assert control_only, (d, 'caída al control con candidato distinto del control')
        return 'control'
    if control_only:
        raise AssertionError((d, 'aceptado_control_only: aceptación retrospectiva con portafolio igual al control, sin validación propia; no hay plantilla y no se narra como rechazo ni como validación en curso'))
    return 'aceptado'


def main(argv=None):
    global a
    ap = argparse.ArgumentParser()
    for k in ('--fe', '--be', '--runs', '--meta', '--out'):
        ap.add_argument(k, required=True)
    ap.add_argument('--indice')
    ap.add_argument('items', nargs='+')
    a = ap.parse_args(argv)
    sys.path[:0] = [f'{a.be}/src', a.be]
    from epiforecast import registry
    import yaml
    global LAG
    META = json.load(open(a.meta))
    cu = yaml.safe_load(open(f'{a.be}/config/data/cuadros.yaml'))['cuadro_groups']
    for it in a.items:
        d, _, rest = it.partition('='); pedido, _, rel = rest.partition(':')
        if ':' in d:
            d, rel = d.split(':', 1)
        r = registry.require(d); v = json.load(open(f'{a.fe}/publication/{d}/vista.json'))
        kind = tipo_de_publicacion(d, r, v, a.fe)
        assert not pedido or pedido == kind, (d, f'se pidió {pedido} y la vista/registry dicen {kind}')
        assert not rel or rel == v['release_id'], (d, f'release pedido {rel} distinto del de la vista {v["release_id"]}')
        g = next(n for n, sp in cu.items() if any(x['id'] == d for x in sp.get('diseases', [])))
        assert 'observation_lag_weeks' in cu[g], (d, 'grupo sin observation_lag_weeks')
        LAG = int(cu[g]['observation_lag_weeks'])
        m = dict(META[d])
        s = (aceptado if kind == 'aceptado' else control)(d, r, v, m)
        open(f'{a.out}/{d}.html', 'w', encoding='utf-8').write(s)
        print(d, kind, 'ok')


if __name__ == '__main__':
    main()
