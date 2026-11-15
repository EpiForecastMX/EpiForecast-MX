"""Post-edición medida de la ficha de fiebre paratifoidea (aceptada en su prueba única de 2025), sobre la salida de
gen_fichas_alta20c.py. No toca datos: lee el dataset v2 de la observación y el registro del índice oficial.

- La política de cinco motores la decidió un dictamen tomado bajo delegación del autor, no el autor por nombre.
- Comparabilidad (D9, D9_COMPARABILIDAD_SUIVE.md): renglón 178 del formato SUIVE-1, A01.1-A01.4 en 2014 y 2019.
- Tendencia anual medida, descrita sin causalidad.
- Evidencia del índice posterior a la emisión.
- Error en la prueba retrospectiva de 2025 (sMAPE nacional y por series, frente al control), desde el acceptance.json
  sellado que liga el release_manifest del backend (prueba2025.py).
Uso: postedita_paratifoidea.py --ficha <html> --dataset <epi_dataset_v2.csv> --vista <vista.json> --indice <registro.txt>
                               --be <backend> --runs <runs>
"""
import argparse, collections, csv, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prueba2025 import nota_prueba  # noqa: E402
from datetime import datetime, timezone

ap = argparse.ArgumentParser()
for k in ('--ficha', '--dataset', '--vista', '--indice', '--be', '--runs'):
    ap.add_argument(k, required=True)
a = ap.parse_args()


def sub(s, x, y):
    assert s.count(x) == 1, (x[:80], s.count(x)); return s.replace(x, y)


s = open(a.ficha, encoding='utf-8').read()
s = sub(s, 'y el autor decidió el 15 de noviembre de 2026 aplicar esta política',
        'y un dictamen tomado bajo delegación del autor decidió el 15 de noviembre de 2026 aplicar esta política')
s = sub(s, 'W43, W44, W45 ya habían concluido', 'W43, W44 y W45 ya habían concluido')

anual = collections.Counter()
for r in csv.DictReader(open(a.dataset, encoding='utf-8')):
    anual[int(r['epi_year'])] += float(r['y_cases'])
anual = {k: int(round(v)) for k, v in anual.items()}
assert (anual[2014], anual[2017], anual[2022], anual[2025]) == (13194, 12286, 6189, 3796), anual
fin_datos = 'registros entidad-sexo-semana.</p></div>'
s = sub(s, fin_datos,
        'registros entidad-sexo-semana. En el formato oficial de notificación SUIVE-1 (ediciones de 2014 y de 2019) la fiebre '
        'paratifoidea es el renglón 178, con alcance A01.1-A01.4; el boletín imprimió sólo «A01.1» en 2014_sem02-2017_sem01 y '
        '2018_sem14-2024_sem05 y «A01.1 - A01.4» en los demás boletines, abreviaturas del mismo renglón. '
        f'Los casos notificados por año bajaron de {anual[2014]:,} en 2014 a {anual[2025]:,} en 2025, con repuntes en 2017 '
        f'({anual[2017]:,}) y 2022 ({anual[2022]:,}); son notificaciones y no permiten atribuir la baja a una causa.</p></div>')

v = json.load(open(a.vista)); e = datetime.fromisoformat(v['forecast_emitted_at'])
QUE = 'La comparación con lo observado se actualizará con cada boletín nuevo sin reentrenar los modelos.</p>'
nota, run = nota_prueba(a.be, a.runs, v, (22.7, 27.6))
s = sub(s, QUE, QUE[:-4] + nota + '</p>')
for linea in open(a.indice):
    p = linea.split()
    if len(p) >= 4 and p[1] == 'http=200':
        ts = datetime.strptime(p[0], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        if ts >= e:
            ult = int(p[3].split('=')[1]); assert ult == 43; break
else:
    raise AssertionError('sin consulta posterior a la emisión')
s = sub(s, 'W46 estaba en curso.</p>',
        f'W46 estaba en curso. <span class="evidencia-indice">Lo comprueba la consulta del índice oficial de boletines del '
        f'{ts.day} de noviembre de {ts.year} a las {ts:%H:%M:%S} UTC, posterior a la emisión ({e:%H:%M:%S} UTC), que listaba '
        f'como último el boletín {ult}.</span></p>')
assert ' y el autor decidió' not in s
open(a.ficha, 'w', encoding='utf-8').write(s)
print('ok', ts.isoformat(), run)
