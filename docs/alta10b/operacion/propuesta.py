"""Regenera la tabla de PROPUESTA_POLITICAS.md desde qa/ (sólo candidatos con diagnóstico medido).

Un candidato entra a la propuesta sólo si (a) en el smoke fallaron únicamente ETS y Ridge y los cinco
estacionales salieron succeeded, y (b) el diagnóstico registra tipos de error y todos son EtsFitError o
RidgeFitError (escasez real). Cualquier otro error (p. ej. HarnessError por hueco en el train) excluye
al candidato: se repara la fuente, no se cambia la política."""
import json, glob, os, re
W = '/tmp/epiforecast-alta10b-20261112/wt-be/runs'
VALIDOS = {'EtsFitError', 'RidgeFitError'}
filas, fuera = [], []
INVALIDO = json.load(open('qa/raw_invalidado.json')) if os.path.exists('qa/raw_invalidado.json') else {}
for f in sorted(glob.glob('qa/diag_motores_*.json')):
    i = f[len('qa/diag_motores_'):-5]; d = json.load(open(f))
    if not os.path.exists(f'qa/{i}_estadisticas.json'):
        fuera.append(f'- `{i}`: sin raw canónico revalidado.'); continue
    q = json.load(open(f'qa/{i}_estadisticas.json'))
    jobs = json.load(open(f"{W}/{d['run_smoke']}/run_manifest.json"))['jobs']
    fallidos = {k for k, v in jobs.items() if v.get('status') != 'succeeded'}
    tipos = {}
    for mot in d['motores'].values():
        if 'tipos_de_error' not in mot:
            tipos = None; break
        tipos.update(mot['tipos_de_error'])
    motivo = f'raw del smoke invalidado: {INVALIDO[i]}' if i in INVALIDO else None
    if motivo:
        pass
    elif fallidos - {'ets_add_damped_log1p', 'ridge_harmonic_log1p'}:
        motivo = f'fallan además {sorted(fallidos - {"ets_add_damped_log1p", "ridge_harmonic_log1p"})}'
    elif tipos is None:
        motivo = 'diagnóstico sin tipos de error (repetir con diag_motores.py vigente)'
    elif set(tipos) - VALIDOS:
        motivo = f'errores que no son de escasez: {tipos}'
    if motivo:
        fuera.append(f'- `{i}` (`{d["run_smoke"]}`): {motivo}.'); continue
    ds = os.path.basename(d['dataset_dir']); e = d['motores']['ets_add_damped_log1p']; r = d['motores']['ridge_harmonic_log1p']
    m = q['mediana_estatal_2021_2024']; z = q['pct_semanas_cero_por_entidad_2021_2024']
    filas.append(f"| `{i}` | `{ds}` | `{d['run_smoke']}`, failed | ETS {e['bases_distintas_afectadas']} (por pliegue 2021-2024: {list(e['series_fallidas_por_pliegue'].values())}); Ridge {r['bases_distintas_afectadas']} ({list(r['series_fallidas_por_pliegue'].values())}); tipos {tipos} | {m['mediana']:.1f} ({m['p10']:.1f}, {m['min']:.0f}) | {z['mediana']:.1f}; {z['entidades_mas_de_50pct']} | {q['nacional_semanal_2021_2024']['mediana']:.0f} |")
s = open('PROPUESTA_POLITICAS.md').read()
cab = '| id | dataset | smoke 7 motores (run, estado) | bases con fallo de 64 en desarrollo y tipos de error medidos | mediana estatal semanal (p10, mín) | % semanas en cero (mediana por entidad; entidades >50 %) | nacional semanal (mediana) |\n| --- | --- | --- | --- | --- | --- | --- |\n'
s = re.sub(r'\| id \| dataset \|.*?\n\n', cab + '\n'.join(filas) + '\n\n', s, count=1, flags=re.S)
bloque = '## Fuera de la propuesta (error que no es de escasez)\n\n' + ('\n'.join(fuera) if fuera else 'Ninguno.') + '\n\n'
s = re.sub(r'## Fuera de la propuesta \(error que no es de escasez\)\n\n.*?\n\n', '', s, flags=re.S)
s = s.replace('Pendientes de medir', bloque + 'Pendientes de medir', 1)
open('PROPUESTA_POLITICAS.md', 'w').write(s); print(len(filas), 'filas;', len(fuera), 'fuera:', fuera)
