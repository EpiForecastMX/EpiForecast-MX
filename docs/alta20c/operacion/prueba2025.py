"""Nota con rótulo del error de un aceptado en su prueba única de 2025, desde su acceptance.json sellado.

La ficha de un aceptado decía «Superó la prueba de 2025» sin las cifras de esa prueba (ROOT_FEEDBACK, hallazgos RAG
de la preview 98). El acceptance.json se localiza por la cadena del release_manifest congelado del backend (ligado a la
vista por release_id) y se verifica por su sha256 (chain.acceptance_digest); el resultado debe ser aceptado y pasar
todas sus comprobaciones. Las cifras salen de las comprobaciones `smape_nacional_general` y `smape_bases`, redondeadas a
un decimal como el resto de la ficha, y el que llama coteja las nacionales contra las leídas a mano (aborta si difieren).
Es una métrica retrospectiva sobre semanas de 2025 ya observadas: no se presenta como desempeño fuera de muestra del
pronóstico publicado, que sigue en la validación prospectiva de la vista.
"""
import hashlib, json

AMB_BASES = {True: 'las series por estado', False: 'las series por estado y sexo'}


def checks_prueba(be, runs, vista):
    d, rid = vista['disease_id'], vista['release_id']
    man = json.load(open(f'{be}/artifacts/releases/{d}/{rid}/release_manifest.json'))
    assert man['release_id'] == rid and man['disease_id'] == d, (d, 'manifiesto ajeno a la vista')
    ch = man['chain']
    assert ch.get('acceptance_outcome', 'accepted') == 'accepted', (d, 'no es un aceptado')
    p = f"{runs}/{ch['acceptance_run_id']}/acceptance.json"
    raw = open(p, 'rb').read()
    assert hashlib.sha256(raw).hexdigest() == ch['acceptance_digest'], (d, 'acceptance.json distinto del sellado')
    acc = json.loads(raw)
    assert acc['accepted'] is True and all(c['passed'] for c in acc['checks']), (d, 'prueba no superada')
    return ch['acceptance_run_id'], {c['scope']: c for c in acc['checks']}


def nota_prueba(be, runs, vista, nacional_esperado):
    """Fragmento HTML (empieza con espacio) para el primer párrafo de «Qué significa y qué no»."""
    run, c = checks_prueba(be, runs, vista)
    nac, bas = c['smape_nacional_general'], c['smape_bases']
    pn, cn = round(nac['portfolio'], 1), round(nac['control'], 1)
    assert (pn, cn) == nacional_esperado, (vista['disease_id'], (pn, cn), nacional_esperado)
    sinsexo = not any(k.endswith('|hombres') for k in vista.get('series', {}))
    lim = lambda x: f"{x['max_worse_pct']:g} %"
    return (f' <strong>Error en la prueba de 2025:</strong> en esa prueba retrospectiva su error en el total nacional fue '
            f'sMAPE {pn}, frente a {cn} del control estacional, y en {AMB_BASES[sinsexo]}, {bas["portfolio"]:.1f} frente a '
            f'{bas["control"]:.1f}. La regla pedía no empeorar al control más de {lim(nac)} en el total nacional ni más de '
            f'{lim(bas)} en las series. Son errores sobre semanas de 2025 que ya estaban observadas, no el desempeño del '
            'pronóstico publicado: ése se medirá con las semanas posteriores al origen.'), run
