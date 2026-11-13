"""¿Equivale la configuración efectiva de <id> entre dos commits, para una fase dada?

Fases (separadas: un cambio editorial o una política autorizada no invalida un raw intacto):
  fuente     lo que determina el raw extraído: el grupo de cuadro completo del id (mapa, periodos,
             anclas, source_exclusions; éstas no entran en el digest del dataset), los campos del
             registry que lee la extracción (data_name, extraction_group, sex_breakdown, con sus
             valores por omisión de registry.py) y el código de extracción (scripts/extrae_cuadro.py,
             src/epiforecast/data/extraction/, src/epiforecast/registry.py).
  seleccion  lo anterior más lo que gobierna desarrollo y selección: selection_policy, perfil,
             motores, exposición y la definición de las políticas y motores (config/evaluation,
             config/engines). Web, lifecycle, canales y textos no cuentan.
rc 0 = equivalente. Uso: config_efectiva.py <repo> <commit_a> <commit_b> <id> [fuente|seleccion]
"""
import subprocess
import sys

import yaml

CAMPOS_FUENTE = {'data_name': None, 'extraction_group': '', 'sex_breakdown': True}
CAMPOS_SELECCION = {'selection_policy': None, 'profile': None, 'training_engines': None,
                    'eligible_engines': None, 'exposure_source_id': None}
CODIGO_FUENTE = ['scripts/extrae_cuadro.py', 'src/epiforecast/data/extraction', 'src/epiforecast/registry.py']
CODIGO_SELECCION = ['config/evaluation', 'config/engines']


def comparar(repo: str, a: str, b: str, i: str, fase: str = 'fuente') -> list[str]:
    def show(rev, path):
        return yaml.safe_load(subprocess.check_output(['git', '-C', repo, 'show', f'{rev}:{path}']))

    def grupo(rev):
        cu = show(rev, 'config/data/cuadros.yaml')['cuadro_groups']
        return next((g, s) for g, s in cu.items() if any(x['id'] == i for x in s.get('diseases', [])))

    def campos(rev, cs):
        e = next(d for d in show(rev, 'config/padecimientos.yaml')['padecimientos'] if d['id'] == i)
        return {k: e.get(k, v) for k, v in cs.items()}

    dif = []
    if grupo(a) != grupo(b):
        dif.append('grupo de cuadro (mapa, periodos o exclusiones)')
    if campos(a, CAMPOS_FUENTE) != campos(b, CAMPOS_FUENTE):
        dif.append('campos del registry que lee la extracción')
    rutas = list(CODIGO_FUENTE)
    if fase == 'seleccion':
        if campos(a, CAMPOS_SELECCION) != campos(b, CAMPOS_SELECCION):
            dif.append('política, perfil, motores o exposición del registry')
        rutas += CODIGO_SELECCION
    if subprocess.check_output(['git', '-C', repo, 'diff', '--stat', a, b, '--', *rutas]).strip():
        dif.append('código o definiciones de ' + ('extracción' if fase == 'fuente' else 'extracción o evaluación'))
    return dif


if __name__ == '__main__':
    repo, a, b, i = sys.argv[1:5]
    fase = sys.argv[5] if len(sys.argv) > 5 else 'fuente'
    assert fase in ('fuente', 'seleccion'), fase
    dif = comparar(repo, a, b, i, fase)
    print(f'{i} [{fase}] {a[:8]} vs {b[:8]}: ' + ('equivalente' if not dif else 'DISTINTA: ' + ', '.join(dif)))
    sys.exit(1 if dif else 0)
