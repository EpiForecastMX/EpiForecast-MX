"""Guarda de orden y tope para la apertura de 2025 de los dieciséis de B2/B14.

Aborta (rc 1) si: el id no está en el manifiesto congelado (MANIFIESTO_SELECCIONES_16.json, cuyo sha256
debe coincidir con MANIFIESTO_SELECCIONES_16.sha256); su selección o dataset difieren de lo congelado (sha256
de selection.csv); algún id anterior en el orden no tiene su prueba sellada; ya hay cuatro aceptados entre
los abiertos; o alguno anterior terminó en fallo técnico sin decisión de root (test sin acceptance.json).
Uso: guarda_orden.py <id> <runs_dir> <base>
"""
import glob, hashlib, json, os, sys

i, runs, B = sys.argv[1:4]
META = 4
h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
man_p = f'{B}/MANIFIESTO_SELECCIONES_16.json'
esperado = open(f'{B}/MANIFIESTO_SELECCIONES_16.sha256').read().split()[0]
if h(man_p) != esperado:
    sys.exit('manifiesto de selecciones alterado')
man = json.load(open(man_p))
items = {x['id']: x for x in man['items']}
if i not in items:
    sys.exit(f'{i} no está en el manifiesto congelado')
x = items[i]
if h(f"{runs}/{x['selection_run']}/selection.csv") != x['selection_csv_sha256']:
    sys.exit('selección distinta de la congelada')
aceptados, motivos = 0, []
for o in man['orden_apertura']:
    tests = glob.glob(f'{runs}/{o}_benchmark_test_*')
    if o == i:
        if tests:
            motivos.append(f'{i} ya tiene prueba de 2025: {tests}')
        break
    if not tests:
        motivos.append(f'{o} (anterior en el orden) no tiene prueba sellada')
        continue
    acc = f'{tests[0]}/acceptance.json'
    if len(tests) > 1 or not os.path.exists(acc):
        motivos.append(f'{o}: fallo técnico o varias aperturas; requiere decisión de root')
        continue
    aceptados += bool(json.load(open(acc))['accepted'])
if aceptados >= META:
    motivos.append(f'ya hay {aceptados} aceptados: no se abren más')
if motivos:
    print('ALTO orden/tope:', '; '.join(motivos)); sys.exit(1)
print(f'orden y tope OK: {i} es el siguiente, {aceptados} aceptados antes')
