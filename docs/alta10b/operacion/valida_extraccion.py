"""Validación de una corrida de extracción aislada (inventario = PDF del corte, no un número fijo) (sin leer valores clínicos: sólo estados del
manifiesto, nombres de archivo, hashes y tiempos).

Uso CLI (desde extract_snap.sh, en el worktree del snapshot):
  valida_extraccion.py <id> <rc> <t0> <cfg_inicio> <cfg_fin> <inicio_utc> <fin_utc> <sha> <pasada> <dir_salida>
Escribe <dir_salida>/<id>_RUN.json e imprime una línea VALIDA/FALLA sin cifras de casos.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys

VERSION = 'valida_extraccion.v2'  # inventario exacto del corte, sin duplicados (M4)
ESTADOS_VALIDOS = {'ok', 'excluded'}


def sha256(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def declarados(cuadros: dict, i: str) -> list[str]:
    """Archivos de source_exclusions que nombran al id en su grupo de cuadro."""
    g = next(s for s in cuadros['cuadro_groups'].values()
             if any(x['id'] == i for x in s.get('diseases', [])))
    return sorted(e['file'] for e in g.get('source_exclusions', []) if i in e['diseases'])


def inventario(pdf_dir: str) -> list[str]:
    """PDF previstos para el corte: los presentes en el directorio de la corrida."""
    return sorted(f for f in os.listdir(pdf_dir) if f.endswith('.pdf'))


def fallas(*, rc: int, cfg0: str, cfg1: str, t0: float, csv_path: str, man_path: str,
           filas: list[dict], decl: list[str], previstos: list[str]) -> tuple[list[str], dict, list[str]]:
    """Devuelve (fallas, conteo de estados, excluidos). Lista vacía = corrida válida."""
    out = []
    if rc != 0:
        out.append(f'rc={rc}')
    if cfg0 != cfg1:
        out.append('config cambió durante la extracción')
    for p in (csv_path, man_path):
        if not os.path.exists(p) or os.path.getmtime(p) < t0:
            out.append(f'{os.path.basename(p)} no es fresco')
    estados: dict[str, int] = {}
    for r in filas:
        estados[r['status']] = estados.get(r['status'], 0) + 1
    vistos = [r['file'] for r in filas]
    if len(vistos) != len(set(vistos)):
        out.append('manifiesto con PDF duplicados')
    if set(vistos) != set(previstos):
        faltan, sobran = sorted(set(previstos) - set(vistos)), sorted(set(vistos) - set(previstos))
        out.append(f'manifiesto no cubre el inventario del corte: faltan {faltan[:5]} ({len(faltan)}), sobran {sobran[:5]} ({len(sobran)})')
    if set(estados) - ESTADOS_VALIDOS:
        out.append(f'estados no válidos {sorted(set(estados) - ESTADOS_VALIDOS)}')
    excl = sorted(r['file'] for r in filas if r['status'] == 'excluded')
    if excl != decl:
        out.append(f'excluidos {excl} != declarados {decl}')
    return out, estados, excl


def main(argv: list[str]) -> int:
    import yaml
    i, rc, t0, c0, c1, i0, i1, sha, pasada, salida = argv[:10]
    pdf_dir = argv[10] if len(argv) > 10 else '/tmp/epiforecast-alta10b-20261112/pdfs'
    csv_path, man_path = f'data/interim/{i}_boletin.csv', f'data/interim/{i}_extraccion_manifest.csv'
    filas = list(csv.DictReader(open(man_path))) if os.path.exists(man_path) else []
    decl = declarados(yaml.safe_load(open('config/data/cuadros.yaml')), i)
    f, estados, excl = fallas(rc=int(rc), cfg0=c0, cfg1=c1, t0=float(t0), csv_path=csv_path,
                              man_path=man_path, filas=filas, decl=decl, previstos=inventario(pdf_dir))
    run = {'id': i, 'pasada': pasada, 'snapshot_sha': sha, 'inicio_utc': i0, 'fin_utc': i1, 'rc': int(rc),
           'config_sha256_inicio': c0.split(), 'config_sha256_fin': c1.split(), 'manifiesto_pdf': len(filas), 'pdf_previstos': len(inventario(pdf_dir)),
           'estados': estados, 'excluidos': excl, 'csv_sha256': sha256(csv_path),
           'manifiesto_sha256': sha256(man_path), 'valida': not f, 'fallas': f}
    json.dump(run, open(f'{salida}/{i}_RUN.json', 'w'), ensure_ascii=False, indent=1)
    print(f"{i} {'VALIDA' if not f else 'FALLA'} csv={str(run['csv_sha256'])[:12]} {f}")
    return 0 if not f else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
