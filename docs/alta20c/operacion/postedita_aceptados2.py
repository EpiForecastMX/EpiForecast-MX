"""Post-edición medida de las fichas de mal del pinto (A67) y vulvovaginitis (N76), aceptados en su prueba única de
2025, sobre la salida de gen_fichas_alta20c.py. No toca datos: lee el dataset v2 de cada observación, la vista, el
acceptance.json sellado y el registro del índice oficial. Cada cifra se recalcula y aborta si no coincide.

- Mal del pinto (D10, dictamen delegado §2): sMAPE absoluto alto (aceptar = no empeorar al control) y el cambio de
  nivel de 2024 en casi todas las entidades, sin leerlo como menor incidencia; política decidida por el dictamen.
- Vulvovaginitis: continuidad del rótulo «Vulvovaginitis Inespecífica A76.0» a N76 desde 2017_sem02.
- Ambas: evidencia del índice posterior a la emisión y «W43, W44 y W45».
Uso: postedita_aceptados2.py --fe <frontend> --runs <runs> --indice <registro.txt>
"""
import argparse, collections, csv, json, statistics
from datetime import datetime, timezone

ap = argparse.ArgumentParser()
for k in ('--fe', '--runs', '--indice'):
    ap.add_argument(k, required=True)
a = ap.parse_args()


def sub(s, x, y):
    assert s.count(x) == 1, (x[:80], s.count(x)); return s.replace(x, y)


def evidencia(s, v):
    e = datetime.fromisoformat(v['forecast_emitted_at'])
    for linea in open(a.indice):
        p = linea.split()
        if len(p) >= 4 and p[1] == 'http=200':
            ts = datetime.strptime(p[0], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            if ts >= e:
                ult = int(p[3].split('=')[1]); assert ult == 43; break
    else:
        raise AssertionError('sin consulta posterior a la emisión')
    s = sub(s, 'W43, W44, W45 ya habían concluido', 'W43, W44 y W45 ya habían concluido')
    return sub(s, 'W46 estaba en curso.</p>',
               f'W46 estaba en curso. <span class="evidencia-indice">Lo comprueba la consulta del índice oficial de boletines del '
               f'{ts.day} de noviembre de {ts.year} a las {ts:%H:%M:%S} UTC, posterior a la emisión ({e:%H:%M:%S} UTC), que '
               f'listaba como último el boletín {ult}.</span></p>'), ts


def filas(v):
    return list(csv.DictReader(open(f"{a.runs}/{v['observation_dataset_id']}/epi_dataset_v2.csv", encoding='utf-8')))


QUE = 'La comparación con lo observado se actualizará con cada boletín nuevo sin reentrenar los modelos.</p>'

# --- Mal del pinto ---
d = 'mal_del_pinto_a67'; p = f'{a.fe}/{d}.html'; s = open(p, encoding='utf-8').read(); v = json.load(open(f'{a.fe}/publication/{d}/vista.json'))
s = sub(s, 'y el autor decidió el 15 de noviembre de 2026 aplicar esta política',
        'y un dictamen tomado bajo delegación del autor decidió el 15 de noviembre de 2026 aplicar esta política')
acc = json.load(open(f'{a.runs}/mal_del_pinto_a67_benchmark_test_b2b88f1c5d00_467678f0469e/acceptance.json'))
nac = next(c for c in acc['checks'] if c['scope'] == 'smape_nacional_general')
pn, cn = round(nac['portfolio'], 1), round(nac['control'], 1)
assert (pn, cn) == (111.3, 115.8), (pn, cn)
R = filas(v)
anual = collections.Counter(); ent = collections.defaultdict(collections.Counter); cero = collections.defaultdict(list)
for r in R:
    y = int(r['epi_year']); c = float(r['y_cases']); anual[y] += c; ent[r['entidad_canonica']][y] += c
    if y == 2025: cero[(r['cve_ent'], r['sexo'])].append(c == 0)
anual = {k: int(round(x)) for k, x in anual.items()}
con23 = [e for e, c in ent.items() if c[2023] > 0]; bajan = [e for e in con23 if ent[e][2024] < ent[e][2023]]
med0 = statistics.median(sum(x) / len(x) for x in cero.values())
assert (anual[2023], anual[2024], anual[2025], len(con23), len(bajan)) == (280, 133, 78, 30, 25), (anual, len(con23), len(bajan))
s = sub(s, QUE, QUE[:-4] + (
    f' <strong>Error alto aunque aceptado:</strong> en la prueba de 2025 su error en el total nacional fue sMAPE {pn}, frente a {cn} '
    'del control estacional. Aceptarlo significa que no empeoró al control más de lo que permite la regla, no que el pronóstico '
    'sea preciso: con unos dos casos por semana en todo el país, el error semanal relativo es muy grande. En las series por estado '
    f'y sexo, la mediana de semanas en cero en 2025 fue {100 * med0:.0f} %, y una semana en que lo observado y lo pronosticado valen '
    'cero cuenta como error nulo, así que su error estatal bajo no demuestra precisión.</p>\n'
    f'        <p><strong>Cambio de nivel en 2024.</strong> La suma de los casos semanales notificados pasó de {anual[2023]} en 2023 a {anual[2024]} en 2024 '
    f'y {anual[2025]} en 2025; la cifra de 2024 fue menor que la de 2023 en {len(bajan)} de las {len(con23)} entidades con casos en '
    '2023. El renglón, el código y el rótulo del boletín no cambiaron y la columna de año anterior de la propia fuente confirma el '
    'nivel nuevo, pero no se certifica que la serie sea comparable antes y después de 2024: esa caída no debe leerse como menor '
    'incidencia. La prueba de 2025 cae entera en el nivel nuevo.</p>'))
s, ts1 = evidencia(s, v)
assert ' y el autor decidió' not in s
open(p, 'w', encoding='utf-8').write(s); print(d, 'ok', ts1)

# --- Vulvovaginitis ---
d = 'vulvovaginitis_n76'; p = f'{a.fe}/{d}.html'; s = open(p, encoding='utf-8').read(); v = json.load(open(f'{a.fe}/publication/{d}/vista.json'))
s = sub(s, 'registros entidad-semana).</p></div>',
        'registros entidad-semana). Hasta 2017_sem01 el boletín imprime el renglón como «Vulvovaginitis Inespecífica» con el código '
        'A76.0; desde 2017_sem02, «Vulvovaginitis» con N76. La serie es continua en ese cambio de rótulo y no se mide un cambio de '
        'definición en el total nacional. La candidiasis urogenital (B37.3-B37.4) y la tricomoniasis se notifican aparte.</p></div>')
s, ts2 = evidencia(s, v)
open(p, 'w', encoding='utf-8').write(s); print(d, 'ok', ts2)
