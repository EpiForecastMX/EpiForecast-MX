"""Guarda P1 de model_test.sh: la apertura única de 2025 exige aprobación NOMINAL.

FABLE_PLAN_APPROVED.md debe contener la línea exacta «AUTORIZABLE_PRETEST <id>» y
APROBACION_TEST_<id>.json debe coincidir campo a campo con la identidad congelada. Una aprobación
de un id no habilita otro. Uso: guarda_aprobacion.py <fable_md> <aprobacion_json> <id> <dataset_id>
<raw_sha256> <politica> <selection_run>   (rc 0 = aprobado)
"""
from __future__ import annotations

import json
import os
import sys

CAMPOS = ('id', 'dataset_id', 'raw_sha256', 'selection_policy', 'selection_run')


def verificar(fable_md: str, aprobacion: str, esperado: dict) -> list[str]:
    """Lista de motivos de rechazo; vacía = aprobado."""
    if not os.path.exists(fable_md):
        return ['sin FABLE_PLAN_APPROVED.md']
    lineas = {l.rstrip('\n') for l in open(fable_md, encoding='utf-8')}
    motivos = []
    if f"AUTORIZABLE_PRETEST {esperado['id']}" not in lineas:
        motivos.append(f"FABLE_PLAN_APPROVED.md no nombra {esperado['id']}")
    if not os.path.exists(aprobacion):
        return motivos + [f'sin {os.path.basename(aprobacion)}']
    a = json.load(open(aprobacion, encoding='utf-8'))
    motivos += [f'{k}: aprobado {a.get(k)!r} != actual {esperado[k]!r}' for k in CAMPOS if a.get(k) != esperado[k]]
    return motivos


if __name__ == '__main__':
    md, ap, *vals = sys.argv[1:]
    m = verificar(md, ap, dict(zip(CAMPOS, vals)))
    print('aprobación nominal OK' if not m else 'RECHAZO: ' + '; '.join(m))
    sys.exit(0 if not m else 1)
