"""Pone al día los conteos escritos en las pruebas del frontend desde publication/catalog.json y el catálogo del
dashboard generado (npm run build:dashboard). Uso: fe_conteos.py <frontend>"""
import json, re, sys
fe = sys.argv[1]
R = len(json.load(open(f'{fe}/publication/catalog.json'))['releases']); N = 4 + R
dash = json.load(open(f'{fe}/assets/dashboard/catalog.json'))
S = sum(d['nSeries'] for d in dash['diseases'])
print('N', N, 'R', R, 'S', S)
def ed(p, pares):
    s = open(f'{fe}/{p}', encoding='utf-8').read(); s0 = s
    for pat, rep in pares:
        s, n = re.subn(pat, rep, s); assert n >= 1, (p, pat)
    if s != s0: open(f'{fe}/{p}', 'w', encoding='utf-8').write(s)
ed('tests/galeria_controller.test.mjs', [
    (r"inicio: sólo el catálogo, \d+ padecimientos", f"inicio: sólo el catálogo, {N} padecimientos"),
    (r"(gDiseases'\)\.children\.length, )[6-9]\d\)", rf"\g<1>{N})"),
    (r"\^\d+ padecimientos · [\d,]+ series\$", f"^{N} padecimientos · {S:,} series$"),
    (r"i < \d+ && pend\.length", f"i < {N} && pend.length"),
    (r"\d+ de \d+ padecimientos cargados · 1 con error", f"{N-1} de {N} padecimientos cargados · 1 con error"),
    (r"0 de \d+ padecimientos cargados · \d+ con error", f"0 de {N} padecimientos cargados · {N} con error"),
    (r"assert\.equal\(lines\.length, \d+\)", f"assert.equal(lines.length, {N})")])
ed('tests/home.test.mjs', [(r"catálogo: \d+ tarjetas", f"catálogo: {N} tarjetas"), (r"assert\.equal\(cards\.length, \d+\)", f"assert.equal(cards.length, {N})")])
ed('tests/home_preview_controller.test.mjs', [
    (r"\d+ opciones y la serie", f"{N} opciones y la serie"), (r"assert\.equal\(opts\.length, \d+\)", f"assert.equal(opts.length, {N})"),
    (r"length, \d+, '«Elige un padecimiento» \+ \d+ releases'", f"length, {R+1}, '«Elige un padecimiento» + {R} releases'"),
    (r"querySelectorAll\('option'\)\.length, \d+\);", f"querySelectorAll('option').length, {N});")])
ed('epibot/tests/test_obesidad_galeria.mjs', [(r'(class="condition-card"/g\) \|\| \[\]\)\.length, )\d+\)', rf'\g<1>{N})')])
