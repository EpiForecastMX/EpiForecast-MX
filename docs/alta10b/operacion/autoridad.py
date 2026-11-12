"""Autorizaciones nominales del autor, en una sola fuente estructurada (ESQUEMA_AUTORIZACION.md).

Sólo cuentan los JSON de <base>/autorizaciones/*.json con schema «autorizacion_autor.v1». Los .md
(propuestas, resúmenes, ejemplos en bloques de código) nunca autorizan. Cada registro lo escribe root
con la pregunta y la respuesta literales del usuario; este validador no autentica a una persona: evita
que un texto accidental (ejemplo, propuesta, archivo vacío) cuente como decisión, y registra el sha256
del archivo que se leyó.

CLI: autoridad.py politica <id> <politica>      rc 0 si hay autorización para ese id y esa política
     autoridad.py control <id> <test_run>        rc 0 si hay autorización de control para ese run
     autoridad.py lista                          imprime los registros válidos y los rechazados
Base: env ALTA10B_BASE (por omisión /tmp/epiforecast-alta10b-20261112).
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime

SCHEMA = 'autorizacion_autor.v1'
CLAVES = {'schema', 'registrado_por', 'recibida_utc', 'canal', 'pregunta_literal', 'respuesta_literal',
          'alcance', 'evidencia'}
OBLIGATORIAS = CLAVES - {'evidencia'}
POLITICAS = {'rolling_cv_v1', 'rolling_cv_baja_incidencia_v1', 'rolling_cv_historia_corta_2023_v1'}
ID = re.compile(r'^[a-z][a-z0-9_]*[a-z0-9]$')
MARCAS_DE_EJEMPLO = ('<', '>', 'EJEMPLO', 'ejemplo', 'TODO', 'xxx', '...')


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def validar(reg: dict) -> list[str]:
    """Motivos por los que un registro no autoriza nada; vacío = válido."""
    m = []
    if not isinstance(reg, dict):
        return ['no es un objeto JSON']
    if reg.get('schema') != SCHEMA:
        m.append(f'schema distinto de {SCHEMA}')
    if set(reg) - CLAVES:
        m.append(f'claves desconocidas {sorted(set(reg) - CLAVES)}')
    for k in sorted(OBLIGATORIAS - {'alcance'}):
        v = reg.get(k)
        if not isinstance(v, str) or not v.strip():
            m.append(f'{k} vacío o ausente')
        elif k in ('pregunta_literal', 'respuesta_literal') and any(x in v for x in MARCAS_DE_EJEMPLO):
            m.append(f'{k} parece plantilla o ejemplo')
    if reg.get('registrado_por') != 'root':
        m.append('registrado_por debe ser «root»')
    try:
        t = datetime.fromisoformat(str(reg.get('recibida_utc')))
        if t.tzinfo is None:
            m.append('recibida_utc sin zona horaria')
    except ValueError:
        m.append('recibida_utc no es ISO 8601')
    al = reg.get('alcance')
    if not isinstance(al, list) or not al:
        return m + ['alcance vacío o ausente']
    for n, a in enumerate(al):
        if not isinstance(a, dict) or not ID.match(str(a.get('id', ''))):
            m.append(f'alcance[{n}]: id inválido'); continue
        if a.get('tipo') == 'control':
            if set(a) != {'tipo', 'id', 'test_run'} or not str(a['test_run']).startswith(f"{a['id']}_benchmark_test_"):
                m.append(f'alcance[{n}]: control exige exactamente id y test_run de ese id')
        elif a.get('tipo') == 'politica':
            if set(a) != {'tipo', 'id', 'politica'} or a['politica'] not in POLITICAS:
                m.append(f'alcance[{n}]: política exige id y una política conocida')
        else:
            m.append(f'alcance[{n}]: tipo desconocido {a.get("tipo")!r}')
    return m


def cargar(base: str) -> tuple[list[dict], list[dict]]:
    """(válidos, rechazados). Cada válido lleva archivo y sha256 de lo leído."""
    ok, mal = [], []
    for f in sorted(glob.glob(f'{base}/autorizaciones/*.json')):
        try:
            reg = json.load(open(f, encoding='utf-8'))
        except (OSError, ValueError) as e:
            mal.append({'archivo': f, 'motivos': [f'JSON ilegible: {e}']}); continue
        motivos = validar(reg)
        (mal if motivos else ok).append({'archivo': f, 'sha256': _sha(f), 'motivos': motivos, 'registro': reg})
    return ok, mal


def autoriza(base: str, tipo: str, i: str, valor: str) -> dict | None:
    """El primer registro válido cuyo alcance nombra exactamente (tipo, id, valor), o None."""
    clave = 'test_run' if tipo == 'control' else 'politica'
    for r in cargar(base)[0]:
        for a in r['registro']['alcance']:
            if a['tipo'] == tipo and a['id'] == i and a[clave] == valor:
                return {'archivo': r['archivo'], 'sha256': r['sha256'], 'recibida_utc': r['registro']['recibida_utc']}
    return None


if __name__ == '__main__':
    base = os.environ.get('ALTA10B_BASE', '/tmp/epiforecast-alta10b-20261112')
    if sys.argv[1:2] == ['lista']:
        ok, mal = cargar(base)
        print(json.dumps({'validas': [{k: r[k] for k in ('archivo', 'sha256')} | {'alcance': r['registro']['alcance']} for r in ok],
                          'rechazadas': mal}, ensure_ascii=False, indent=1))
        sys.exit(0)
    tipo, i, valor = sys.argv[1:4]
    if tipo not in ('politica', 'control'):
        sys.exit(f'tipo desconocido {tipo}')
    r = autoriza(base, tipo, i, valor)
    print(json.dumps(r, ensure_ascii=False) if r else f'SIN AUTORIZACIÓN {tipo} {i} {valor}')
    sys.exit(0 if r else 1)
