"""Guardas del paquete histórico del paper MICAI 2026.

El paquete de datos (~500 MB) no se versiona; estas pruebas se saltan solas si no está
materializado. Lo que sí se versiona —código, MANIFEST, raíz de confianza y resultados—
se verifica siempre.

Materializar el paquete:  python scripts/paper_micai_2026/sella_bundle.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "scripts/paper_micai_2026"
REPORTES = RAIZ / "reports/paper_micai_2026"
sys.path.insert(0, str(SCRIPTS))


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _bundle():
    """Importa bundle o salta la prueba si el paquete no está materializado."""
    try:
        import bundle as b
    except (FileNotFoundError, ImportError) as e:
        pytest.skip(f"paquete no materializado: {e}")
    if not (b.BASE / "MANIFEST.json").exists():
        pytest.skip("paquete no materializado")
    return b


# --------------------------------------------------------------- raíz de confianza
def test_raiz_de_confianza_coincide_con_el_manifest():
    """El SHA-256 registrado en Git debe describir al MANIFEST versionado."""
    esperado = (REPORTES / "RAIZ_SHA256.txt").read_text().split()[0]
    assert _sha256(REPORTES / "MANIFEST.json") == esperado


def test_el_manifest_nombra_los_commits_del_paper():
    m = json.loads((REPORTES / "MANIFEST.json").read_text())
    assert m["commit_modelos"] == "c13e7163"
    assert m["commit_observaciones"] == "b43ebdf2"
    assert len(m["piezas"]) == 7


# --------------------------------------------------------------- resultados versionados
def test_los_resultados_coinciden_con_sus_hashes():
    d = REPORTES / "resultados"
    registrados = json.loads((d / "HASHES.json").read_text())["archivos"]
    for nombre, sha in registrados.items():
        assert _sha256(d / nombre) == sha, f"{nombre} cambió sin actualizar HASHES.json"


def test_la_particion_regional_es_la_del_contrato():
    m = pd.read_csv(REPORTES / "resultados/region_membership.csv")
    assert len(m) == 32
    assert not m.entidad.duplicated().any()
    assert m.region.value_counts().to_dict() == {
        "Urbana media": 15,
        "Rural / dispersa": 7,
        "Sur-Sureste vulnerable": 6,
        "Metropolitana alta": 4,
    }


# --------------------------------------------------------------- guardas del paquete
def test_las_siete_piezas_verifican():
    b = _bundle()
    fallan = [n for n, ok in b.verifica_todo() if not ok]
    assert not fallan, f"piezas con SHA-256 distinto: {fallan}"


@pytest.mark.parametrize(
    "viva",
    [
        "data/processed/tableau.csv",
        "data/processed/dataset_boletin_epidemiologico.csv",
        "reports/ProdDetails/tabla_333_modelos_produccion.xlsx",
        "reports/forecasts/deepar/all_forecast_deepar.csv",
    ],
)
def test_las_rutas_vivas_estan_prohibidas(viva):
    """Las cifras del paper no pueden salir del árbol de trabajo: hoy dan otros números."""
    b = _bundle()
    with pytest.raises(b.FueraDelPaqueteError):
        b.prohibe_rutas_vivas(RAIZ / viva)


def test_una_pieza_inexistente_no_se_sirve():
    b = _bundle()
    with pytest.raises(b.FueraDelPaqueteError):
        b.ruta("no_existe.csv")


# --------------------------------------------------------------- reproducción mínima
def test_la_tabla_2_publicada_reproduce():
    """sMAPE 6,63 % y desviación +4,40 % — lo impreso en el paper, sin corregir."""
    b = _bundle()
    import numpy as np

    obs = b.observado()
    obs = obs[(obs.Padecimiento == "Depresión") & (obs.Anio == 2026)]
    y_s = obs.groupby("Semana")["Casos_semana"].sum()

    t = b.tableau()
    d = t[
        (t.padecimiento == "Depresión") & (t.meta_modo == "general") & (t.entidad == "Nacional")
    ].copy()
    d["ds"] = pd.to_datetime(d.ds)
    d = d[d.ds.dt.isocalendar().year == 2026]
    d["w"] = d.ds.dt.isocalendar().week.astype(int)
    f_s = d.set_index("w")["yhat_ensemble"]

    W = [w for w in range(2, 19) if w in y_s.index and w in f_s.index]
    y, f = y_s[W].values.astype(float), f_s[W].values.astype(float)
    smape = 100 * np.mean(np.abs(y - f) / ((np.abs(y) + np.abs(f)) / 2))
    assert round(smape, 2) == 6.63
    assert round(100 * (f.sum() - y.sum()) / y.sum(), 2) == 4.40
    assert y.sum() == 48300


def test_el_desfase_de_semana_esta_confirmado():
    """incrementos_total(ds=w) sigue al boletín de w+1, no al de w."""
    b = _bundle()
    t = b.tableau()
    d = t[
        (t.padecimiento == "Depresión") & (t.meta_modo == "general") & (t.entidad == "Jalisco")
    ].copy()
    d["ds"] = pd.to_datetime(d.ds)
    d = d[d.ds.dt.isocalendar().year == 2025]
    d["w"] = d.ds.dt.isocalendar().week.astype(int)
    modelo = d.set_index("w")["incrementos_total"]

    o = b.observado()
    o = o[(o.Padecimiento == "Depresión") & (o.Anio == 2025)]
    o["Entidad"] = o["Entidad"].replace({"Distrito Federal": "Ciudad de México"})
    bol = o[o.Entidad == "Jalisco"].set_index("Semana")["Casos_semana"]

    ws = [w for w in range(2, 50) if w in modelo.index and w in bol.index and w + 1 in bol.index]
    con_w = sum(abs(modelo[w] - bol[w]) < 0.5 for w in ws)
    con_w1 = sum(abs(modelo[w] - bol[w + 1]) < 0.5 for w in ws)
    assert con_w1 > 5 * max(con_w, 1), f"coincidencias w={con_w} w+1={con_w1}"


# --------------------------------------------------------------- gate de compilacion
#
# Sin esto la suite queda verde aunque LaTeX falle: `nonstopmode` escribe un PDF
# igualmente, así que contar páginas no basta. Aquí se exige código de salida 0 y cero
# errores '!'. El master sí se versiona (excepción explícita en .gitignore), así que su
# ausencia es un fallo, no un skip; lo único que se salta es la falta de pdflatex.

MASTER = RAIZ / "Congresos/MICAI/paper_camera_ready.tex"


DEPENDENCIAS = [
    "paper_camera_ready.tex",
    "llncs.cls",
    "splncs04.bst",
    "Figures/fig01_temporal_distribution.pdf",
    "Figures/fig19_validation_2026.pdf",
    "Figures/fig20_oos_perstate.pdf",
]


def test_el_master_y_sus_dependencias_estan_versionados():
    """Un clon limpio tiene que poder reconstruir el camera-ready.

    Esto NO se salta: si el master no está, la suite debe ponerse roja. Antes se saltaba,
    y eso dejaba a CI en verde sin paper.
    """
    faltan = [d for d in DEPENDENCIAS if not (MASTER.parent / d).exists()]
    assert not faltan, (
        f"faltan del árbol: {faltan}. El camera-ready se versiona por una excepción "
        "explícita de .gitignore; si desapareció, la excepción se rompió."
    )


def _compila(tmp_path):
    import shutil
    import subprocess

    assert MASTER.exists(), f"el master no está en {MASTER}"
    if shutil.which("pdflatex") is None:
        pytest.skip("pdflatex no disponible en esta máquina")
    orig = MASTER.parent
    for n in ("llncs.cls", "splncs04.bst", MASTER.name):
        shutil.copy(orig / n, tmp_path / n)
    shutil.copytree(orig / "Figures", tmp_path / "Figures", dirs_exist_ok=True)
    rc = 0
    for _ in range(3):
        r = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", MASTER.name],
            cwd=tmp_path,
            capture_output=True,
            timeout=300,
            check=False,
        )
        rc = r.returncode or rc
    log = (tmp_path / MASTER.with_suffix(".log").name).read_text(encoding="latin-1")
    return rc, log


@pytest.fixture(scope="module")
def compilacion(tmp_path_factory):
    return _compila(tmp_path_factory.mktemp("latex"))


def test_el_master_compila_sin_errores(compilacion):
    rc, log = compilacion
    errores = [ln for ln in log.splitlines() if ln.startswith("!")]
    assert rc == 0, f"pdflatex salió con {rc}"
    assert not errores, "errores de LaTeX:\n" + "\n".join(errores[:5])


def test_no_quedan_referencias_sin_resolver(compilacion):
    import re

    _, log = compilacion
    assert not re.findall(r"[Uu]ndefined (?:citation|reference|control)", log)


def test_ningun_overfull_grave(compilacion):
    import re

    _, log = compilacion
    graves = [
        float(v) for v in re.findall(r"Overfull \\[hv]box \(([0-9.]+)pt", log) if float(v) > 15
    ]
    assert not graves, f"overfull > 15pt: {graves}"


def test_el_master_cabe_en_el_limite_de_micai(compilacion):
    """MICAI: hasta 20 páginas; más exige contactar a los organizadores."""
    import re

    _, log = compilacion
    pg = re.findall(r"Output written on .*?\((\d+) pages", log)
    assert pg, "pdflatex no escribió PDF"
    assert int(pg[0]) <= 20, f"{pg[0]} páginas, el techo de MICAI es 20"


def test_el_gate_de_compilacion_bloquea_por_exceso_de_paginas(tmp_path):
    """compila.sh debe FALLAR con más de 20 páginas, no sólo imprimir el número.

    Prueba destructiva sobre una copia: se rellena el master hasta desbordar el techo
    y se exige que el script salga distinto de cero. Un gate que imprime la cifra pero
    no la aplica no es un gate.
    """
    import shutil
    import subprocess

    guion = MASTER.parent / "compila.sh"
    if not guion.exists():
        pytest.skip("compila.sh no está en este árbol")
    if shutil.which("pdflatex") is None:
        pytest.skip("pdflatex no disponible en esta máquina")

    for n in ("llncs.cls", "splncs04.bst", "compila.sh", MASTER.name):
        shutil.copy(MASTER.parent / n, tmp_path / n)
    shutil.copytree(MASTER.parent / "Figures", tmp_path / "Figures", dirs_exist_ok=True)

    roto = tmp_path / MASTER.name
    roto.write_text(
        roto.read_text().replace(
            "\\end{document}", "\\clearpage\\null\\clearpage\\null\n\\end{document}"
        )
    )
    r = subprocess.run(
        ["./compila.sh"], cwd=tmp_path, capture_output=True, text=True, timeout=600, check=False
    )
    assert r.returncode != 0, f"el gate dejó pasar un master sobre el techo:\n{r.stdout}"
    assert "FALLA" in r.stdout


# --------------------------------------------------------------- cifras obsoletas
def test_ninguna_cifra_retirada_sobrevive():
    """Toda cifra de la validación cambió al corregir la alineación de semanas.

    Este control mira el .tex sin comentarios y también el PDF, porque una cifra
    puede entrar por una figura y no por el fuente.
    """
    import valores_retirados

    if not valores_retirados.TEX.exists():
        pytest.skip("el master no está en este árbol")
    hallazgos = valores_retirados.revisa()
    assert not hallazgos, "cifras retiradas vivas:\n" + "\n".join(
        f"  [{e}] {c[:120]}" for e, c, _ in hallazgos[:8]
    )


def test_las_ventanas_no_se_contradicen():
    """El análisis por serie corre sobre una ventana distinta a la del agregado.

    Ya se contradijo una vez: el rótulo dentro de la Figura 4 decía una ventana y su
    pie decía otra. La ventana se deriva del dato y debe coincidir en JSON, .tex,
    pies y figura.
    """
    import ventanas_coherentes

    if not (ventanas_coherentes.JSON.exists() and ventanas_coherentes.TEX.exists()):
        pytest.skip("faltan el JSON de cifras o el master")
    fallos = ventanas_coherentes.revisa()
    assert not fallos, "ventanas incoherentes:\n" + "\n".join(f"  {x}" for x in fallos)


def test_ninguna_letra_de_figura_baja_de_6pt():
    """Springer: «lettering in figures should not use font sizes smaller than 6 pt».

    Se mide sobre el PDF ENSAMBLADO. La primera versión de este control sólo miraba
    los archivos cargados con \\includegraphics, así que el diagrama TikZ le era
    invisible: daba verde mientras ese diagrama iba a 3,2 pt.
    """
    import tipografia_figuras

    if not tipografia_figuras.PDF.exists():
        pytest.skip("no hay PDF compilado")
    filas = tipografia_figuras.revisa()
    assert filas, "el gate no encontró ninguna figura: no está midiendo nada"
    bajas = [(fig, mn, n) for _, fig, mn, n in filas if n]
    assert not bajas, "figuras por debajo de 6 pt: " + ", ".join(
        f"{fig} ({mn:.2f} pt, {n} glifos)" for fig, mn, n in bajas
    )


def test_las_referencias_no_llevan_flotantes_intercalados():
    """La bibliografía debe ser contigua: 1..28 sin saltos ni repeticiones."""
    import re
    import subprocess

    pdf = RAIZ / "Congresos/MICAI/paper_camera_ready.pdf"
    if not pdf.exists():
        pytest.skip("no hay PDF compilado")
    txt = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=False
    ).stdout
    nums = [int(n) for n in re.findall(r"^ *(\d+)\. [A-Z][a-z]", txt, re.M)]
    # la secuencia de la bibliografía es la cola creciente que llega a 28
    biblio = nums[nums.index(1, 1) :] if nums.count(1) > 1 else nums
    assert biblio == list(range(1, len(biblio) + 1)), f"referencias no contiguas: {biblio[:12]}"


def _sello():
    """Carga sello_sincronizado.py, que vive junto a los demás scripts del paper."""
    sys.path.insert(0, str(RAIZ / "scripts/paper_micai_2026"))
    import sello_sincronizado

    return sello_sincronizado


def test_un_hash_cientifico_no_se_confunde_con_el_del_paquete():
    """La atribución tiene que ser explícita, no una etiqueta genérica.

    Con `sha256` a secas como marcador, una línea tan normal como «SHA-256 del CSV
    de ablación:» contaba como si el hash fuese el del paquete. Peor: `propaga()`
    lo habría reescrito al resellar, destruyendo un hash científico con el
    mecanismo que existe justamente para cuidar los sellos.
    """
    s = _sello()
    ajeno = "217192fa570e3f2e52e12c10d5ae239ff7385e80da3b3576bf454e894f9d88f4"
    for etiqueta in (
        "SHA-256 del CSV de ablación:",
        "sha256 de los resultados publicados:",
        "Hash determinista de data/ablation_results.csv",
    ):
        texto = f"# Nota\n\n{etiqueta}\n`{ajeno}`\n"
        assert s.hashes_del_paquete(texto) == [], f"atribuido de más con «{etiqueta}»"
        assert ajeno in s.propaga(texto, "0" * 64), f"propaga() pisó el hash con «{etiqueta}»"


def test_el_hash_del_paquete_si_se_reconoce_en_sus_tres_formas():
    """Las tres formas que usan de verdad los documentos del envío."""
    s = _sello()
    h = "bc4ad509fbc8c14a1de59835fb0cc4702b1c908aefe79b1868661e1353894e03"
    for contexto in (
        f"- Archivo: `Congresos/MICAI/Envio/012.zip`.\n- SHA-256: `{h}`.",
        f"Paquete camera-ready MICAI 2026 · ponencia #12\n\n  sha256  {h}",
        f"Ese archivo tiene el sha256 del paquete:\n\n```\n{h}\n```",
    ):
        assert s.hashes_del_paquete(contexto) == [h], f"no reconocido en: {contexto[:44]}"
        assert s.propaga(contexto, "0" * 64).count("0" * 64) == 1
