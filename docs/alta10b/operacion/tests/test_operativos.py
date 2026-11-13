"""Pruebas operativas de los guiones del lote alta10b. Sólo datos SINTÉTICOS creados aquí: ningún
valor deriva de boletines, CSV, manifiestos, datasets o releases reales.

Ejecutar: PYTHONPATH=<wt-be>/src:<wt-be> <venv>/bin/python -m pytest scripts/tests -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import subprocess as sp
from types import SimpleNamespace

S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S))
import autoridad as au  # noqa: E402
import guarda_aprobacion as ga  # noqa: E402
import valida_extraccion as ve  # noqa: E402

# ---------------------------------------------------------------- valida_extraccion (sintético)


def _filas(n=670, excluidos=('2014_sem01.pdf',), extra=None):
    f = [{'file': f'sint_{k:03d}.pdf', 'status': 'ok'} for k in range(n - len(excluidos))]
    f += [{'file': e, 'status': 'excluded'} for e in excluidos]
    if extra:
        f[0]['status'] = extra
    return f


@pytest.fixture
def frescos(tmp_path):
    t0 = time.time() - 5
    c, m = tmp_path / 'x_boletin.csv', tmp_path / 'x_extraccion_manifest.csv'
    c.write_text('a,b\n1,2\n'); m.write_text('file,status\n')
    return t0, str(c), str(m)


def _f(frescos, **kw):
    t0, c, m = frescos
    base = dict(rc=0, cfg0='h1 h2', cfg1='h1 h2', t0=t0, csv_path=c, man_path=m,
                filas=_filas(), decl=['2014_sem01.pdf'], previstos=[r['file'] for r in _filas()])
    base.update(kw)
    return ve.fallas(**base)[0]


def test_corrida_valida(frescos):
    assert _f(frescos) == []


def test_rc_distinto_de_cero(frescos):
    assert _f(frescos, rc=1) == ['rc=1']


def test_config_cambiada_durante_la_extraccion(frescos):
    assert 'config cambió durante la extracción' in _f(frescos, cfg1='h1 OTRO')


def test_csv_rancio_no_cuenta(frescos):
    t0, c, m = frescos
    os.utime(c, (t0 - 100, t0 - 100))  # copia vieja: anterior al inicio de la corrida
    assert any('no es fresco' in x for x in _f(frescos))


def test_manifiesto_incompleto(frescos):
    assert any('no cubre el inventario' in x for x in _f(frescos, filas=_filas()[1:]))


def test_inventario_variable_no_fija_670(frescos):
    filas = _filas(n=12)  # un corte sintético de 12 PDF es válido si el manifiesto lo cubre
    assert _f(frescos, filas=filas, previstos=[r['file'] for r in filas]) == []


def test_manifiesto_con_duplicados(frescos):
    filas = _filas(); filas.append(dict(filas[0]))
    assert any('duplicados' in x for x in _f(frescos, filas=filas))


@pytest.mark.parametrize('estado', ['error', 'invalid', 'no_page'])
def test_estados_no_validos(frescos, estado):
    assert any('estados no válidos' in x for x in _f(frescos, filas=_filas(extra=estado)))


def test_exclusion_no_declarada(frescos):
    filas = _filas(excluidos=('2014_sem01.pdf', 'sint_extra.pdf'))
    assert any('!= declarados' in x for x in _f(frescos, filas=filas))


def test_declarados_por_id():
    cu = {'cuadro_groups': {'g': {'diseases': [{'id': 'a'}, {'id': 'b'}], 'source_exclusions': [
        {'file': 'p1.pdf', 'diseases': ['a', 'b']}, {'file': 'p2.pdf', 'diseases': ['b']}]}}}
    assert ve.declarados(cu, 'a') == ['p1.pdf'] and ve.declarados(cu, 'b') == ['p1.pdf', 'p2.pdf']

# ---------------------------------------------------------------- guarda_aprobacion (sintético)


ESP = {'id': 'sint_a', 'dataset_id': 'sint_a_000000000000', 'raw_sha256': '0' * 64,
       'selection_policy': 'rolling_cv_v1', 'selection_run': 'sint_a_select_x'}


def _aprob(tmp_path, linea='AUTORIZABLE_PRETEST sint_a', **cambios):
    md, ap = tmp_path / 'FABLE_PLAN_APPROVED.md', tmp_path / 'APROBACION_TEST_sint_a.json'
    md.write_text(f'# aprobación\n\n{linea}\n')
    ap.write_text(json.dumps({**ESP, **cambios}))
    return str(md), str(ap)


def test_aprobacion_nominal_correcta(tmp_path):
    assert ga.verificar(*_aprob(tmp_path), ESP) == []


def test_aprobacion_de_otro_id_no_habilita(tmp_path):
    assert ga.verificar(*_aprob(tmp_path, linea='AUTORIZABLE_PRETEST sint_b'), ESP)


def test_aprobacion_con_raw_distinto(tmp_path):
    m = ga.verificar(*_aprob(tmp_path, raw_sha256='1' * 64), ESP)
    assert m and m[0].startswith('raw_sha256')


def test_linea_debe_ser_exacta(tmp_path):
    assert ga.verificar(*_aprob(tmp_path, linea='AUTORIZABLE_PRETEST sint_a (borrador)'), ESP)


def test_sin_archivos(tmp_path):
    assert ga.verificar(str(tmp_path / 'no.md'), str(tmp_path / 'no.json'), ESP) == ['sin FABLE_PLAN_APPROVED.md']



@pytest.mark.parametrize('campo', ['dataset_id', 'raw_sha256', 'selection_policy', 'selection_run'])
def test_aprobacion_cada_campo_cuenta(tmp_path, campo):
    m = ga.verificar(*_aprob(tmp_path, **{campo: 'otro'}), ESP)
    assert m and m[0].startswith(campo)

# ---------------------------------------------------------------- autoridad (sintético)


def _aut(**cambios):
    r = {'schema': 'autorizacion_autor.v1', 'registrado_por': 'root', 'recibida_utc': '2030-01-02T03:04:05+00:00',
         'canal': 'chat del supervisor', 'pregunta_literal': '¿Autorizas el control de sint_c con el run sint_c_benchmark_test_a?',
         'respuesta_literal': 'Autorizo el control de sint_c', 'alcance': [{'tipo': 'control', 'id': 'sint_c', 'test_run': 'sint_c_benchmark_test_a'}]}
    r.update(cambios); return r


def _escribe_aut(base: Path, nombre: str, reg) -> Path:
    (base / 'autorizaciones').mkdir(exist_ok=True)
    f = base / 'autorizaciones' / nombre; f.write_text(reg if isinstance(reg, str) else json.dumps(reg)); return f


def test_autoridad_valida_y_registra_sha(tmp_path):
    f = _escribe_aut(tmp_path, 'a.json', _aut())
    r = au.autoriza(str(tmp_path), 'control', 'sint_c', 'sint_c_benchmark_test_a')
    import hashlib
    assert r and r['sha256'] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert au.autoriza(str(tmp_path), 'control', 'sint_c', 'sint_c_benchmark_test_b') is None


@pytest.mark.parametrize('cambio', [
    {'respuesta_literal': ''}, {'respuesta_literal': '<respuesta del usuario>'}, {'pregunta_literal': 'EJEMPLO de pregunta'},
    {'registrado_por': 'opus'}, {'recibida_utc': '2030-01-02T03:04:05'}, {'schema': 'otro'}, {'extra': 1},
    {'alcance': []}, {'alcance': [{'tipo': 'control', 'id': 'sint_c', 'test_run': 'otro_benchmark_test_a'}]},
    {'alcance': [{'tipo': 'politica', 'id': 'sint_c', 'politica': 'inventada_v9'}]},
    {'alcance': [{'tipo': 'refit', 'id': 'sint_c'}]}])
def test_autoridad_rechaza_registros_defectuosos(tmp_path, cambio):
    _escribe_aut(tmp_path, 'a.json', _aut(**cambio))
    assert au.autoriza(str(tmp_path), 'control', 'sint_c', 'sint_c_benchmark_test_a') is None
    assert au.cargar(str(tmp_path))[1]


def test_md_y_ok_vacio_no_autorizan(tmp_path):
    (tmp_path / 'autorizaciones').mkdir()
    (tmp_path / 'AUTORIZACION_AUTOR_x.md').write_text('```\nAUTORIZA_CONTROL sint_c sint_c_benchmark_test_a\n```\n')
    (tmp_path / 'autorizaciones' / 'ejemplo.md').write_text(json.dumps(_aut()))
    (tmp_path / 'AUTORIZACION_POLITICA_sint_c.ok').write_text('')
    assert au.autoriza(str(tmp_path), 'control', 'sint_c', 'sint_c_benchmark_test_a') is None
    assert au.autoriza(str(tmp_path), 'politica', 'sint_c', 'rolling_cv_baja_incidencia_v1') is None


def test_politica_exige_id_y_politica_exactos(tmp_path):
    _escribe_aut(tmp_path, 'p.json', _aut(alcance=[{'tipo': 'politica', 'id': 'sint_c', 'politica': 'rolling_cv_baja_incidencia_v1'}]))
    assert au.autoriza(str(tmp_path), 'politica', 'sint_c', 'rolling_cv_baja_incidencia_v1')
    assert au.autoriza(str(tmp_path), 'politica', 'sint_d', 'rolling_cv_baja_incidencia_v1') is None
    assert au.autoriza(str(tmp_path), 'politica', 'sint_c', 'rolling_cv_historia_corta_2023_v1') is None

# ---------------------------------------------------------------- lista_publicables: linaje en disco


def _run(runs: Path, rid: str, ds='sint_ds', status='succeeded', exit_code=0, **archivos):
    (runs / rid).mkdir(parents=True)
    (runs / rid / 'run_manifest.json').write_text(json.dumps({'run_id': rid, 'status': status, 'exit_code': exit_code, 'dataset_id': ds}))
    for n, c in archivos.items():
        (runs / rid / n.replace('__', '.')).write_text(json.dumps(c))


def _prueba(base: Path, i: str, accepted: bool, **kw):
    tr = f'{i}_benchmark_test_aaaa_bbbb'
    (base / 'model' / i).mkdir(parents=True)
    _run(base / 'runs', tr, acceptance__json={'accepted': accepted, 'provenance': {'run_id': tr},
                                               'checks': [{'scope': 'smape_nacional_general', 'passed': accepted}]}, **kw)
    import hashlib
    return tr, hashlib.sha256((base / 'runs' / tr / 'acceptance.json').read_bytes()).hexdigest()


def _lista(base: Path):
    env = {**os.environ, 'ALTA10B_BASE': str(base), 'ALTA10B_RUNS': str(base / 'runs')}
    out = sp.run([sys.executable, str(S / 'lista_publicables.py')], env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def _estado(r, i):
    for k in ('publicables', 'rechazados', 'pendientes'):
        for x in r[k]:
            if x['id'] == i:
                return k, x


def test_aceptado_con_linaje_completo_es_publicable(tmp_path):
    tr, dig = _prueba(tmp_path, 'sint_ok', True)
    _run(tmp_path / 'runs', 'sint_ok_refit_final_x', refit_summary__json={'provenance': {'acceptance_run_id': tr, 'acceptance_digest': dig}})
    _run(tmp_path / 'runs', 'sint_ok_forecast_h52_x', lineage__json={'refit_run_id': 'sint_ok_refit_final_x'})
    k, x = _estado(_lista(tmp_path), 'sint_ok')
    assert k == 'publicables' and x['tipo'] == 'aceptado' and x['forecast_run'] == 'sint_ok_forecast_h52_x'


def test_aceptado_control_only_se_marca(tmp_path):
    tr, dig = _prueba(tmp_path, 'sint_co', True)
    _run(tmp_path / 'runs', 'sint_co_refit_final_x', refit_summary__json={'engines': {'seasonal_naive_lag52': 64},
         'provenance': {'acceptance_run_id': tr, 'acceptance_digest': dig}})
    _run(tmp_path / 'runs', 'sint_co_forecast_h52_x', lineage__json={'refit_run_id': 'sint_co_refit_final_x'})
    k, x = _estado(_lista(tmp_path), 'sint_co')
    assert k == 'publicables' and x['tipo'] == 'aceptado_control_only'


def test_log_ok_aceptado_sin_runs_no_publica(tmp_path):
    tr, _ = _prueba(tmp_path, 'sint_log', True)
    (tmp_path / 'model' / 'sint_log' / 'registro.txt').write_text(f'OK aceptado: test={tr} refit=sint_log_refit_final_x forecast=sint_log_forecast_h52_x\n')
    assert _estado(_lista(tmp_path), 'sint_log')[0] == 'pendientes'


@pytest.mark.parametrize('defecto', ['digest', 'dataset', 'refit_fallido', 'forecast_de_otro_refit'])
def test_linaje_roto_no_publica(tmp_path, defecto):
    tr, dig = _prueba(tmp_path, 'sint_l', True)
    _run(tmp_path / 'runs', 'sint_l_refit_final_x', ds='otro_ds' if defecto == 'dataset' else 'sint_ds',
         status='failed' if defecto == 'refit_fallido' else 'succeeded',
         refit_summary__json={'provenance': {'acceptance_run_id': tr, 'acceptance_digest': '0' * 64 if defecto == 'digest' else dig}})
    _run(tmp_path / 'runs', 'sint_l_forecast_h52_x', lineage__json={'refit_run_id': 'otro' if defecto == 'forecast_de_otro_refit' else 'sint_l_refit_final_x'})
    assert _estado(_lista(tmp_path), 'sint_l')[0] == 'pendientes'


def test_prueba_fallida_con_acceptance_no_cuenta(tmp_path):
    _prueba(tmp_path, 'sint_f', False, status='failed', exit_code=1)
    _escribe_aut(tmp_path, 'a.json', _aut(alcance=[{'tipo': 'control', 'id': 'sint_f', 'test_run': 'sint_f_benchmark_test_aaaa_bbbb'}]))
    assert _estado(_lista(tmp_path), 'sint_f')[0] == 'pendientes'


def test_dos_aperturas_no_publican(tmp_path):
    _prueba(tmp_path, 'sint_2', False)
    _run(tmp_path / 'runs', 'sint_2_benchmark_test_cccc_dddd', acceptance__json={'accepted': False, 'provenance': {'run_id': 'sint_2_benchmark_test_cccc_dddd'}, 'checks': []})
    assert _estado(_lista(tmp_path), 'sint_2')[0] == 'pendientes'


def test_control_sólo_con_autorizacion_estructurada_y_linaje(tmp_path):
    tr, dig = _prueba(tmp_path, 'sint_c', False)
    (tmp_path / 'AUTORIZACION_AUTOR_sint.md').write_text(f'AUTORIZA_CONTROL sint_c {tr}\n')
    assert _estado(_lista(tmp_path), 'sint_c')[0] == 'rechazados'            # un .md no autoriza
    _escribe_aut(tmp_path, 'a.json', _aut(alcance=[{'tipo': 'control', 'id': 'sint_c', 'test_run': tr}]))
    k, x = _estado(_lista(tmp_path), 'sint_c')
    assert k == 'pendientes' and 'sin refit' in x['motivo']                 # la autorización sola no publica
    _run(tmp_path / 'runs', 'sint_c_refit_final_x', refit_summary__json={'provenance': {'acceptance_run_id': tr, 'acceptance_digest': dig}})
    _run(tmp_path / 'runs', 'sint_c_forecast_h52_x', lineage__json={'refit_run_id': 'sint_c_refit_final_x'})
    k, x = _estado(_lista(tmp_path), 'sint_c')
    assert k == 'publicables' and x['tipo'] == 'control' and x['forecast_run'] == 'sint_c_forecast_h52_x'
    assert len(x['autorizacion']['sha256']) == 64


def test_control_con_refit_de_otro_rechazo_no_publica(tmp_path):
    tr, dig = _prueba(tmp_path, 'sint_c', False)
    _escribe_aut(tmp_path, 'a.json', _aut(alcance=[{'tipo': 'control', 'id': 'sint_c', 'test_run': tr}]))
    _run(tmp_path / 'runs', 'sint_c_refit_final_x', refit_summary__json={'provenance': {'acceptance_run_id': 'otro', 'acceptance_digest': dig}})
    _run(tmp_path / 'runs', 'sint_c_forecast_h52_x', lineage__json={'refit_run_id': 'sint_c_refit_final_x'})
    assert _estado(_lista(tmp_path), 'sint_c')[0] == 'pendientes'


def test_ids_de_controles_en_carpetas_ctrl(tmp_path):
    tr, dig = _prueba(tmp_path, 'sint_k', False)
    (tmp_path / 'model' / 'sint_k').rename(tmp_path / 'model' / 'ctrl_sint_k')
    assert _estado(_lista(tmp_path), 'sint_k')[0] == 'rechazados'

# ---------------------------------------------------------------- guarda_orden (sintético)


def _orden(tmp_path, orden=('a_x', 'b_x', 'c_x', 'd_x', 'e_x', 'f_x')):
    import hashlib
    runs = tmp_path / 'runs'; runs.mkdir(exist_ok=True)
    items = []
    for n, i in enumerate(orden, 1):
        sel = f'{i}_select_s'; (runs / sel).mkdir(parents=True, exist_ok=True)
        (runs / sel / 'selection.csv').write_text(f'selected_engine\nseasonal_mean_3y\n{i}\n')
        items.append({'orden': n, 'id': i, 'selection_run': sel,
                      'selection_csv_sha256': hashlib.sha256((runs / sel / 'selection.csv').read_bytes()).hexdigest()})
    m = tmp_path / 'MANIFIESTO_SELECCIONES_16.json'; m.write_text(json.dumps({'orden_apertura': list(orden), 'items': items}))
    (tmp_path / 'MANIFIESTO_SELECCIONES_16.sha256').write_text(hashlib.sha256(m.read_bytes()).hexdigest() + '\n')
    return runs


def _test(runs, i, accepted=None):
    d = runs / f'{i}_benchmark_test_t'; d.mkdir()
    if accepted is not None:
        (d / 'acceptance.json').write_text(json.dumps({'accepted': accepted}))


def _go(tmp_path, runs, i):
    return sp.run([sys.executable, str(S / 'guarda_orden.py'), i, str(runs), str(tmp_path)], capture_output=True, text=True)


def test_orden_primero_pasa_y_segundo_espera(tmp_path):
    runs = _orden(tmp_path)
    assert _go(tmp_path, runs, 'a_x').returncode == 0
    assert _go(tmp_path, runs, 'b_x').returncode == 1          # a_x sin prueba sellada


def test_orden_tope_de_cuatro_aceptados(tmp_path):
    runs = _orden(tmp_path)
    for i, acc in zip(('a_x', 'b_x', 'c_x', 'd_x'), (True, True, False, True)):
        _test(runs, i, acc)
    assert _go(tmp_path, runs, 'e_x').returncode == 0           # 3 aceptados
    _test(runs, 'e_x', True)
    r = _go(tmp_path, runs, 'f_x')
    assert r.returncode == 1 and 'aceptados' in r.stdout


def test_orden_fallo_tecnico_bloquea_sin_decision(tmp_path):
    runs = _orden(tmp_path); _test(runs, 'a_x', None)
    r = _go(tmp_path, runs, 'b_x')
    assert r.returncode == 1 and 'fallo técnico' in r.stdout


def test_orden_no_reabre_ni_acepta_seleccion_alterada(tmp_path):
    runs = _orden(tmp_path); _test(runs, 'a_x', False)
    assert _go(tmp_path, runs, 'a_x').returncode == 1           # ya abierto
    (runs / 'b_x_select_s' / 'selection.csv').write_text('selected_engine\nseasonal_naive_lag52\n')
    assert _go(tmp_path, runs, 'b_x').returncode == 1           # selección distinta de la congelada


def test_orden_manifiesto_alterado(tmp_path):
    runs = _orden(tmp_path)
    m = tmp_path / 'MANIFIESTO_SELECCIONES_16.json'; m.write_text(m.read_text().replace('a_x', 'z_x', 1))
    assert _go(tmp_path, runs, 'a_x').returncode == 1


# ---------------------------------------------------------------- gen_fichas: tipo, calendario y disponibilidad


import gen_fichas as gf  # noqa: E402  (requiere epiforecast en PYTHONPATH: sin él, la prueba falla, no se salta)


def _vista(origen=(2030, 10), emitida='2030-04-01T18:00:00+00:00'):
    return {'origin': list(origen), 'weeks_required': 4, 'forecast_emitted_at': emitida}


def test_calendario_mmwr_explicito():
    gf.LAG = 1
    tw, bol, cola = gf.calendario(_vista())
    assert tw == [(2030, 11), (2030, 12), (2030, 13), (2030, 14)] and bol == [(2030, 12), (2030, 13), (2030, 14), (2030, 15)]
    assert cola == ', aunque en el calendario W11, W12, W13 ya habían concluido y W14 estaba en curso.'


def test_cruce_de_anio_no_produce_semana_53_falsa():
    from epiforecast.data import epi_calendar as cal
    gf.LAG = 1
    y = 2026; ultima = cal.weeks_in_year(y)
    tw, bol, _ = gf.calendario(_vista(origen=(y, ultima - 2), emitida=f'{y}-12-20T18:00:00+00:00'))
    assert all(1 <= w <= cal.weeks_in_year(a) for a, w in tw + bol)
    assert bol[-1][0] == y + 1 and gf.rango_boletines(bol).endswith(f'de {y + 1}')


def _ns(tmp_path, indice=None, procedencia=None, d='sint_d', vista=None):
    """procedencia: dict de bulletin_provenance propio del id (se escribe en be/config/publication/<id>/)."""
    be = tmp_path / 'be_ns'
    if procedencia is not None:
        (be / 'config/publication' / d).mkdir(parents=True, exist_ok=True)
        (be / 'config/publication' / d / 'bulletin_provenance.json').write_text(json.dumps(procedencia))
    gf.a = SimpleNamespace(indice=indice, be=str(be))


def test_sin_evidencia_no_se_afirma_prospectividad(tmp_path):
    gf.LAG = 1; _ns(tmp_path)
    assert gf.prospectiva(_vista()) == '' and 'no existían' not in gf.semanas_objetivo(_vista())


def test_indice_tras_emitir_permite_afirmar(tmp_path):
    gf.LAG = 1
    f = tmp_path / 'registro.txt'; f.write_text('20300401T190000Z http=200 adjuntos=11 ultimo=11 sha=x\n')
    _ns(tmp_path, indice=str(f))
    assert gf.prospectiva(_vista()).startswith('Es prospectiva') and 'no existían' in gf.semanas_objetivo(_vista())


@pytest.mark.parametrize('linea', ['20300401T170000Z http=200 adjuntos=11 ultimo=11 sha=x',  # antes de emitir
                                   '20300401T190000Z http=200 adjuntos=12 ultimo=12 sha=x',  # el boletín 12 ya existía
                                   '20300401T190000Z http=000 adjuntos=0 ultimo=0 sha=x'])   # sin red
def test_indice_insuficiente_no_afirma(tmp_path, linea):
    gf.LAG = 1
    f = tmp_path / 'registro.txt'; f.write_text(linea + '\n'); _ns(tmp_path, indice=str(f))
    assert gf.prospectiva(_vista()) == ''


def _prov(v, d='sint_d', **c):
    base = {'schema': 'bulletin_provenance.v1', 'disease_id': d, 'release_id': 'sint_d_release_x',
            'forecast_emitted_at': v['forecast_emitted_at'], 'bulletins': [{'name': 'sem12.pdf', 'after_emission': {'first_available': False}}]}
    base.update(c); return base


def test_procedencia_propia_contradictoria_aborta(tmp_path):
    gf.LAG = 1; v = {**_vista(), 'release_id': 'sint_d_release_x'}
    f = tmp_path / 'registro.txt'; f.write_text('20300401T190000Z http=200 adjuntos=11 ultimo=11 sha=x\n')
    _ns(tmp_path, indice=str(f), procedencia=_prov(v))
    with pytest.raises(AssertionError):
        gf.prospectiva(v, 'sint_d')


@pytest.mark.parametrize('campo,valor', [('disease_id', 'otro_id'), ('release_id', 'otro_release'), ('forecast_emitted_at', '2030-03-01T00:00:00+00:00')])
def test_procedencia_de_otro_release_aborta(tmp_path, campo, valor):
    gf.LAG = 1; v = {**_vista(), 'release_id': 'sint_d_release_x'}
    _ns(tmp_path, procedencia=_prov(v, **{campo: valor, 'bulletins': []}))
    with pytest.raises(AssertionError):
        gf.prospectiva(v, 'sint_d')


def test_procedencia_de_otro_id_no_se_usa(tmp_path):
    """La procedencia se carga sólo de config/publication/<id>/: la de otro id no veta ni autoriza."""
    gf.LAG = 1; v = {**_vista(), 'release_id': 'sint_d_release_x'}
    f = tmp_path / 'registro.txt'; f.write_text('20300401T190000Z http=200 adjuntos=11 ultimo=11 sha=x\n')
    _ns(tmp_path, indice=str(f), procedencia=_prov(v, d='otro_id', disease_id='otro_id'), d='otro_id')
    assert gf.prospectiva(v, 'sint_d').startswith('Es prospectiva')


class _Reg(SimpleNamespace):
    pass


def _release(tmp_path, d='sint_d', rel='sint_d_release_x', outcome='accepted', control_only=None, flags=None,
             fallback_run=None, acc_alterado=False, ptr_rel=None, shard=None, gate_rel=None, rm_origin=None):
    """Fixture completo: shard FE, puntero, release_manifest.v2, acceptance sellado y gate prospectivo."""
    import hashlib
    fe, be, runs = tmp_path / 'fe', tmp_path / 'be', tmp_path / 'runs'
    origin, verdict = [2030, 10], 'INCOMPLETE'
    sh = {'schema': 'publication_shard.v1', 'disease_id': d, 'release_id': rel, 'origin': origin, 'lifecycle': 'published',
          'publication_status': {'verdict': verdict}}
    sh.update(shard or {})
    (fe / 'publication' / d / rel).mkdir(parents=True); (fe / 'publication' / d / rel / 'manifest.json').write_text(json.dumps(sh))
    (be / 'config/publication' / d).mkdir(parents=True)
    (be / 'config/publication' / d / 'public_release_pointer.json').write_text(json.dumps({'disease_id': d, 'release_id': ptr_rel or rel}))
    control = outcome == 'fallback_control'
    co = control if control_only is None else control_only
    (be / 'config/publication' / d / 'prospective_gate.json').write_text(json.dumps(
        {'disease_id': d, 'release_id': gate_rel or rel, 'candidate_forecast_digest': 'c' * 64, 'control_forecast_digest': ('c' if co else 'k') * 64}))
    tr = f'{d}_benchmark_test_aaaa'; (runs / tr).mkdir(parents=True)
    acc = runs / tr / 'acceptance.json'; acc.write_text(json.dumps({'accepted': outcome == 'accepted'}))
    dig = hashlib.sha256(acc.read_bytes()).hexdigest()
    if acc_alterado:
        acc.write_text(json.dumps({'accepted': outcome == 'accepted', 'x': 1}))
    ch = {'acceptance_run_id': tr, 'acceptance_digest': dig}
    if outcome != 'accepted':
        ch['acceptance_outcome'] = outcome
    (be / 'artifacts/releases' / d / rel).mkdir(parents=True)
    (be / 'artifacts/releases' / d / rel / 'release_manifest.json').write_text(json.dumps(
        {'schema': 'release_manifest.v2', 'disease_id': d, 'release_id': rel, 'chain': ch, 'calendar': {'origin': rm_origin or origin}}))
    vista_ctrl, reg_ctrl = flags if flags is not None else (control, control)
    v = {'release_id': rel, 'origin': origin, 'verdict': verdict, 'series': {'01|hombres': 1}}
    if vista_ctrl:
        v['caida_al_control'] = {'comprobaciones': []}
    r = _Reg(acceptance_fallback_run=(fallback_run or tr) if reg_ctrl else None)
    return (d, r, v, str(fe), str(be), str(runs))


def test_aceptado_control_only_es_estado_propio(tmp_path):
    with pytest.raises(AssertionError, match='aceptado_control_only'):
        gf.tipo_de_publicacion(*_release(tmp_path, control_only=True))


def test_tipo_aceptado_y_control_legitimos(tmp_path):
    assert gf.tipo_de_publicacion(*_release(tmp_path / 'a')) == 'aceptado'
    assert gf.tipo_de_publicacion(*_release(tmp_path / 'c', outcome='fallback_control')) == 'control'


@pytest.mark.parametrize('caso', [
    dict(outcome='fallback_control', flags=(False, False)),   # control real sin marcas: no puede salir «aceptado»
    dict(outcome='accepted', flags=(True, True)),             # marcas de control sobre un aceptado
    dict(outcome='fallback_control', flags=(True, False)),
    dict(outcome='fallback_control', fallback_run='otro_benchmark_test_b'),   # registry autoriza otro rechazo
    dict(acc_alterado=True),                                  # acceptance.json distinto del sellado
    dict(ptr_rel='sint_d_release_otro'),                      # puntero público a otro release
    dict(outcome='mixto'),
    dict(control_only=True),                                  # aceptado con candidato = control
    dict(outcome='fallback_control', control_only=False),     # control con candidato distinto del control
    dict(shard={'release_id': 'sint_d_release_otro'}),
    dict(shard={'lifecycle': 'configured'}),
    dict(shard={'origin': [2030, 9]}),
    dict(shard={'publication_status': {'verdict': 'PASS'}}),
    dict(shard={'schema': 'otro'}),
    dict(gate_rel='sint_d_release_otro'),
    dict(rm_origin=[2030, 11]),
])
def test_tipo_discordante_aborta(tmp_path, caso):
    with pytest.raises(AssertionError):
        gf.tipo_de_publicacion(*_release(tmp_path, **caso))


# ---------------------------------------------------------------- config_efectiva sobre un repo git sintético


def test_config_efectiva_detecta_exclusion_y_extractor(tmp_path):
    g = lambda *x: sp.run(['git', '-C', str(tmp_path), *x], check=True, capture_output=True, text=True).stdout.strip()
    g('init', '-q'); g('config', 'user.email', 's@s'); g('config', 'user.name', 's')
    (tmp_path / 'config' / 'data').mkdir(parents=True); (tmp_path / 'src/epiforecast/data/extraction').mkdir(parents=True); (tmp_path / 'scripts').mkdir()
    cu = {'cuadro_groups': {'g': {'diseases': [{'id': 'sint_a'}], 'source_exclusions': []}, 'h': {'diseases': [{'id': 'sint_b'}]}}}
    reg = {'padecimientos': [{'id': 'sint_a'}, {'id': 'sint_b'}]}
    import yaml
    def escribe(c):
        (tmp_path / 'config/data/cuadros.yaml').write_text(yaml.safe_dump(c)); (tmp_path / 'config/padecimientos.yaml').write_text(yaml.safe_dump(reg))
    escribe(cu); (tmp_path / 'src/epiforecast/data/extraction/x.py').write_text('a = 1\n'); (tmp_path / 'scripts/extrae_cuadro.py').write_text('')
    g('add', '-A'); g('commit', '-qm', 'base'); c0 = g('rev-parse', 'HEAD')
    cu['cuadro_groups']['g']['source_exclusions'] = [{'file': 'x.pdf', 'diseases': ['sint_a'], 'keep_period': True}]
    escribe(cu); g('commit', '-qam', 'exclusion'); c1 = g('rev-parse', 'HEAD')
    (tmp_path / 'src/epiforecast/data/extraction/x.py').write_text('a = 2\n'); g('commit', '-qam', 'extractor'); c2 = g('rev-parse', 'HEAD')
    ce = lambda s, h, i: sp.run([sys.executable, str(S / 'config_efectiva.py'), str(tmp_path), s, h, i], capture_output=True).returncode
    assert ce(c0, c1, 'sint_a') == 1          # cambió la exclusión del id
    assert ce(c0, c1, 'sint_b') == 0          # otro grupo intacto
    assert ce(c1, c2, 'sint_b') == 1          # cambió el código del extractor: afecta a todos
    assert ce(c1, c1, 'sint_a') == 0

# ---------------------------------------------------------------- validador: código de salida


def test_validador_devuelve_1_si_la_corrida_no_vale(tmp_path, monkeypatch):
    import yaml
    (tmp_path / 'data/interim').mkdir(parents=True); (tmp_path / 'config/data').mkdir(parents=True); (tmp_path / 'pdfs').mkdir(); (tmp_path / 'out').mkdir()
    (tmp_path / 'config/data/cuadros.yaml').write_text(yaml.safe_dump({'cuadro_groups': {'g': {'diseases': [{'id': 'sint'}], 'source_exclusions': []}}}))
    for n in ('a.pdf', 'b.pdf'):
        (tmp_path / 'pdfs' / n).write_text('')
    t0 = time.time() - 5
    (tmp_path / 'data/interim/sint_boletin.csv').write_text('x\n')
    (tmp_path / 'data/interim/sint_extraccion_manifest.csv').write_text('file,status\na.pdf,ok\nb.pdf,ok\n')
    monkeypatch.chdir(tmp_path)
    args = ['sint', '0', str(t0), 'h', 'h', 'i0', 'i1', 'sha', 'P', str(tmp_path / 'out'), str(tmp_path / 'pdfs')]
    assert ve.main(args) == 0
    (tmp_path / 'data/interim/sint_extraccion_manifest.csv').write_text('file,status\na.pdf,ok\na.pdf,ok\n')
    assert ve.main(args) == 1 and json.loads((tmp_path / 'out/sint_RUN.json').read_text())['valida'] is False


def test_config_efectiva_por_fases(tmp_path):
    import yaml
    g = lambda *x: sp.run(['git', '-C', str(tmp_path), *x], check=True, capture_output=True, text=True).stdout.strip()
    g('init', '-q'); g('config', 'user.email', 's@s'); g('config', 'user.name', 's')
    for d in ('config/data', 'src/epiforecast/data/extraction', 'scripts', 'config/evaluation'):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    (tmp_path / 'config/data/cuadros.yaml').write_text(yaml.safe_dump({'cuadro_groups': {'g': {'diseases': [{'id': 'sint_a'}]}}}))
    (tmp_path / 'src/epiforecast/registry.py').write_text('x = 1\n'); (tmp_path / 'config/evaluation/p.yaml').write_text('a: 1\n')
    e = {'id': 'sint_a', 'data_name': 'Sint', 'selection_policy': 'rolling_cv_v1', 'lifecycle': 'configured', 'web': {'label': 'S'}}
    def commit(**c):
        (tmp_path / 'config/padecimientos.yaml').write_text(yaml.safe_dump({'padecimientos': [{**e, **c}]}))
        g('add', '-A'); g('commit', '-qm', 'c', '--allow-empty'); return g('rev-parse', 'HEAD')
    c0 = commit()
    ce = lambda a, b, f: sp.run([sys.executable, str(S / 'config_efectiva.py'), str(tmp_path), a, b, 'sint_a', f], capture_output=True).returncode
    c_web = commit(lifecycle='published', web={'label': 'Otra'})
    assert ce(c0, c_web, 'fuente') == 0 and ce(c0, c_web, 'seleccion') == 0      # editorial: no invalida
    c_pol = commit(selection_policy='rolling_cv_baja_incidencia_v1')
    assert ce(c0, c_pol, 'fuente') == 0 and ce(c0, c_pol, 'seleccion') == 1      # política: raw intacto, selección no
    c_sexo = commit(selection_policy='rolling_cv_baja_incidencia_v1', sex_breakdown=False)
    assert ce(c_pol, c_sexo, 'fuente') == 1                                       # cambia la lectura
    (tmp_path / 'src/epiforecast/registry.py').write_text('x = 2\n'); g('commit', '-qam', 'reg'); c_reg = g('rev-parse', 'HEAD')
    assert ce(c_sexo, c_reg, 'fuente') == 1
    (tmp_path / 'config/evaluation/p.yaml').write_text('a: 2\n'); g('commit', '-qam', 'pol'); c_ev = g('rev-parse', 'HEAD')
    assert ce(c_reg, c_ev, 'fuente') == 0 and ce(c_reg, c_ev, 'seleccion') == 1

# ---------------------------------------------------------------- revalida_run: revalidación sin reextraer


def _base_revalida(tmp_path):
    import hashlib, shutil, yaml
    B = tmp_path / 'base'; (B / 'scripts').mkdir(parents=True)
    shutil.copy(S / 'valida_extraccion.py', B / 'scripts'); shutil.copy(S / 'revalida_run.py', B / 'scripts')
    (B / 'scripts/VALIDADOR.sha256').write_text(hashlib.sha256((B / 'scripts/valida_extraccion.py').read_bytes()).hexdigest() + '\n')
    (B / 'pdfs').mkdir()
    for n in ('a.pdf', 'b.pdf', 'c.pdf'):
        (B / 'pdfs' / n).write_text('')
    snap = B / 'snap/P'; (snap / 'config/data').mkdir(parents=True); (snap / 'data/interim').mkdir(parents=True)
    g = lambda *x: sp.run(['git', '-C', str(snap), *x], check=True, capture_output=True, text=True).stdout.strip()
    g('init', '-q'); g('config', 'user.email', 's@s'); g('config', 'user.name', 's')
    (snap / 'config/data/cuadros.yaml').write_text(yaml.safe_dump({'cuadro_groups': {'g': {'diseases': [{'id': 'sint'}],
        'source_exclusions': [{'file': 'c.pdf', 'diseases': ['sint']}]}}}))
    (snap / 'config/padecimientos.yaml').write_text('padecimientos: []\n')
    (snap / '.gitignore').write_text('data/\n'); g('add', '-A'); g('commit', '-qm', 's'); sha = g('rev-parse', 'HEAD')
    t0 = time.time() - 10
    (snap / 'data/interim/sint_boletin.csv').write_text('x\n1\n')
    (snap / 'data/interim/sint_extraccion_manifest.csv').write_text('file,status\na.pdf,ok\nb.pdf,ok\nc.pdf,excluded\n')
    (B / 'extract/P').mkdir(parents=True)
    for n in ('sint_boletin.csv', 'sint_extraccion_manifest.csv'):
        shutil.copy(snap / 'data/interim' / n, B / 'extract/P' / n)
    h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    cfg = [h(snap / 'config/data/cuadros.yaml'), h(snap / 'config/padecimientos.yaml')]
    from datetime import datetime, timezone
    (B / 'extract/P/sint_RUN.json').write_text(json.dumps({'snapshot_sha': sha[:8], 'rc': 0, 'valida': True,
        'inicio_utc': datetime.fromtimestamp(t0, timezone.utc).isoformat(), 'config_sha256_inicio': cfg, 'config_sha256_fin': cfg,
        'csv_sha256': h(B / 'extract/P/sint_boletin.csv'), 'manifiesto_sha256': h(B / 'extract/P/sint_extraccion_manifest.csv')}))
    return B, snap


def _revalida(B):
    r = sp.run([sys.executable, str(B / 'scripts/revalida_run.py'), 'P', 'sint', str(B)], capture_output=True, text=True)
    out = B / 'extract/P/sint_RUN_v2.json'
    return r.returncode, (json.loads(out.read_text()) if out.exists() else None)


def test_revalida_valida_y_resuelve_sha40(tmp_path):
    B, _ = _base_revalida(tmp_path)
    rc, r = _revalida(B)
    assert rc == 0 and r['valida'] and len(r['snapshot_sha']) == 40 and r['validador']['version'] == 'valida_extraccion.v2'
    assert r['run_original']['sha256'] and r['inventario']['pdf'] == 3


def test_revalida_csv_alterado(tmp_path):
    B, _ = _base_revalida(tmp_path)
    (B / 'extract/P/sint_boletin.csv').write_text('x\n2\n')
    assert _revalida(B)[0] == 1


def test_revalida_interim_sobrescrito(tmp_path):
    B, snap = _base_revalida(tmp_path)
    (snap / 'data/interim/sint_boletin.csv').write_text('x\n9\n')
    assert _revalida(B)[0] == 1


def test_revalida_config_del_snapshot_cambiada(tmp_path):
    B, snap = _base_revalida(tmp_path)
    (snap / 'config/padecimientos.yaml').write_text('padecimientos: [1]\n')
    assert _revalida(B)[0] == 1


def test_revalida_validador_no_fijado(tmp_path):
    B, _ = _base_revalida(tmp_path)
    (B / 'scripts/valida_extraccion.py').write_text((B / 'scripts/valida_extraccion.py').read_text() + '\n# cambio\n')
    rc, r = _revalida(B)
    assert rc != 0 and r is None


def test_revalida_inventario_incompleto(tmp_path):
    B, _ = _base_revalida(tmp_path)
    (B / 'pdfs/d.pdf').write_text('')
    assert _revalida(B)[0] == 1
