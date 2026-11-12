"""Revalida una pasada ya extraída con el validador vigente, SIN reextraer ni modificar nada.

Entradas fijas: extract/<P>/<id>_boletin.csv y _extraccion_manifest.csv, el RUN.json original
(se conserva intacto) y el worktree del snapshot snap/<P>. Comprueba que:
  - CSV y manifiesto copiados tienen los sha256 que registró el RUN original, y los originales del
    interim del snapshot son los mismos archivos, escritos durante esa corrida (mtime >= inicio);
  - el snapshot está en el commit registrado (resuelto a 40 caracteres), limpio, y su config tiene los
    sha256 de inicio y fin registrados;
  - el validador vigente (scripts/valida_extraccion.py, sha256 fijado en scripts/VALIDADOR.sha256)
    acepta la corrida contra el inventario de PDF y las exclusiones declaradas en el snapshot.
Escribe extract/<P>/<id>_RUN_v2.json (schema run_extraccion_revalidado.v1). Uso:
  revalida_run.py <pasada> <id> [<base>]     rc 0 = válida
"""
import csv, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone

P, i = sys.argv[1], sys.argv[2]
B = sys.argv[3] if len(sys.argv) > 3 else '/tmp/epiforecast-alta10b-20261112'
sys.path.insert(0, f'{B}/scripts')
import valida_extraccion as ve  # noqa: E402
import yaml  # noqa: E402

h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest() if os.path.exists(p) else None
VAL = f'{B}/scripts/valida_extraccion.py'
pin = open(f'{B}/scripts/VALIDADOR.sha256').read().split()[0]
falla = []
if h(VAL) != pin:
    sys.exit(f'validador {h(VAL)} distinto del fijado {pin}: no se revalida con código cambiante')
run1_p = f'{B}/extract/{P}/{i}_RUN.json'
run1 = json.load(open(run1_p))
S = f'{B}/snap/{P}'
csv_c, man_c = f'{B}/extract/{P}/{i}_boletin.csv', f'{B}/extract/{P}/{i}_extraccion_manifest.csv'
csv_o, man_o = f'{S}/data/interim/{i}_boletin.csv', f'{S}/data/interim/{i}_extraccion_manifest.csv'
if h(csv_c) != run1['csv_sha256'] or h(man_c) != run1['manifiesto_sha256']:
    falla.append('copia en extract/ distinta de lo registrado en el RUN original')
if h(csv_o) != run1['csv_sha256'] or h(man_o) != run1['manifiesto_sha256']:
    falla.append('interim del snapshot distinto del registrado (otra corrida lo sobrescribió)')
t0 = datetime.fromisoformat(run1['inicio_utc'].replace('Z', '+00:00')).timestamp()
for p in (csv_o, man_o):
    if os.path.exists(p) and os.path.getmtime(p) < t0:
        falla.append(f'{os.path.basename(p)} anterior al inicio de la corrida')
sha40 = subprocess.check_output(['git', '-C', S, 'rev-parse', run1['snapshot_sha']]).decode().strip()
if subprocess.check_output(['git', '-C', S, 'rev-parse', 'HEAD']).decode().strip() != sha40:
    falla.append('snapshot fuera del commit registrado')
if subprocess.check_output(['git', '-C', S, 'status', '--short', '--untracked-files=no']).strip():
    falla.append('snapshot con cambios')
cfg = [h(f'{S}/config/data/cuadros.yaml'), h(f'{S}/config/padecimientos.yaml')]
if cfg != run1['config_sha256_inicio'] or cfg != run1['config_sha256_fin']:
    falla.append('config del snapshot distinta de la registrada')
filas = list(csv.DictReader(open(man_c))) if os.path.exists(man_c) else []
decl = ve.declarados(yaml.safe_load(open(f'{S}/config/data/cuadros.yaml')), i)
previstos = ve.inventario(f'{B}/pdfs')
f2, estados, excl = ve.fallas(rc=run1['rc'], cfg0='a', cfg1='a', t0=0.0, csv_path=csv_c, man_path=man_c,
                              filas=filas, decl=decl, previstos=previstos)
falla += f2
out = {'schema': 'run_extraccion_revalidado.v1', 'id': i, 'pasada': P, 'snapshot_sha': sha40,
       'run_original': {'archivo': os.path.basename(run1_p), 'sha256': h(run1_p), 'valida': run1['valida']},
       'csv_sha256': h(csv_c), 'manifiesto_sha256': h(man_c),
       'inventario': {'pdf': len(previstos), 'sha256': hashlib.sha256('\n'.join(previstos).encode()).hexdigest()},
       'estados': estados, 'excluidos': excl, 'declarados': decl,
       'validador': {'version': ve.VERSION, 'sha256': pin},
       'revalidado_utc': datetime.now(timezone.utc).isoformat(), 'valida': not falla, 'fallas': falla}
json.dump(out, open(f'{B}/extract/{P}/{i}_RUN_v2.json', 'w'), ensure_ascii=False, indent=1)
print(i, P, 'VALIDA' if not falla else f'FALLA {falla}')
sys.exit(0 if not falla else 1)
