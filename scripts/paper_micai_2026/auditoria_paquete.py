#!/usr/bin/env python3
"""Auditoria del paquete que se sube a CMT. Todo lo que se puede comprobar sin ojos.

No repite los gates que ya existen (compilacion, cifras retiradas, ventanas): los invoca
y ademas revisa lo que ninguno cubre -- reglas de LNCS, bibliografia, flotantes, restos
de la version anonima, capa de texto y contenido del ZIP.

Uso:  .venv/bin/python scripts/paper_micai_2026/auditoria_paquete.py
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

RAIZ = Path(__file__).resolve().parents[2]
MICAI = RAIZ / "Congresos/MICAI"
ZIP = MICAI / "Envio" / "012.zip"
TEX = MICAI / "paper_camera_ready.tex"
PDF = MICAI / "paper_camera_ready.pdf"

fallos: list[str] = []
avisos: list[str] = []
oks: list[str] = []


def check(cond: bool, ok: str, mal: str, grave: bool = True) -> bool:
    if cond:
        oks.append(ok)
    elif grave:
        fallos.append(mal)
    else:
        avisos.append(mal)
    return cond


def sin_comentarios(t: str) -> str:
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", ln) for ln in t.splitlines())


# ------------------------------------------------------------------ 1. el ZIP
def audita_zip() -> None:
    check(ZIP.exists(), "el paquete existe", f"NO existe {ZIP}")
    if not ZIP.exists():
        return
    with zipfile.ZipFile(ZIP) as z:
        nombres = z.namelist()
        malo = z.testzip()
    check(malo is None, "el ZIP no esta corrupto", f"miembro corrupto: {malo}")
    basura = [
        n for n in nombres if "__MACOSX" in n or n.endswith(".DS_Store") or n.startswith("._")
    ]
    check(not basura, "sin basura de macOS", f"basura en el ZIP: {basura}")
    texs = [n for n in nombres if n.endswith(".tex")]
    check(
        len(texs) == 1, f"un solo .tex ({texs[0] if texs else '?'})", f".tex encontrados: {texs}"
    )
    check(any(n.endswith("llncs.cls") for n in nombres), "lleva llncs.cls", "falta llncs.cls")
    check(any(n.endswith(".bst") for n in nombres), "lleva el .bst", "falta splncs04.bst")
    # las figuras del ZIP deben ser exactamente las referenciadas
    refs = set(re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", TEX.read_text()))
    enzip = {Path(n).name for n in nombres if n.startswith("Figures/")}
    check(
        refs == enzip,
        f"las {len(refs)} figuras referenciadas, ni una mas",
        f"figuras: referenciadas {refs}, en el ZIP {enzip}",
    )


# ------------------------------------------------------------------ 2. reglas de LNCS
def audita_lncs(tex: str) -> None:
    t = sin_comentarios(tex)
    check(
        "\\documentclass[runningheads]{llncs}" in t,
        "clase llncs con runningheads",
        "la clase no es llncs[runningheads]",
    )
    for paq in ("geometry", "fullpage", "setspace", "times"):
        check(
            f"\\usepackage{{{paq}}}" not in t
            and "\\usepackage[" not in t.split(f"{{{paq}}}")[0][-40:],
            f"sin {paq} (no se tocan los margenes)",
            f"carga {paq}: Springer rechaza tocar el trim",
        )
    check(
        not re.search(r"\\begin\{(figure|table)\}\[[^\]]*h", t),
        "ningun flotante usa [h]",
        "hay flotantes con [h]; LNCS pide [t] o [b]",
    )
    check(
        not re.search(r"\\vspace\*?\{-", t),
        "sin \\vspace negativos",
        "hay \\vspace negativos: LNCS los rechaza como hack de espaciado",
        grave=False,
    )
    # captions: tabla ARRIBA, figura ABAJO
    tablas = re.findall(r"\\begin\{table\}.*?\\end\{table\}", t, re.S)
    mal_t = [
        i
        for i, b in enumerate(tablas, 1)
        if "\\caption" in b and b.index("\\caption") > b.index("\\begin{tabular}")
    ]
    check(
        not mal_t,
        f"las {len(tablas)} tablas llevan caption arriba",
        f"tablas con caption abajo: {mal_t}",
    )
    figs = re.findall(r"\\begin\{figure\}.*?\\end\{figure\}", t, re.S)
    mal_f = [
        i
        for i, b in enumerate(figs, 1)
        if "\\caption" in b
        and "\\includegraphics" in b
        and b.index("\\caption") < b.index("\\includegraphics")
    ]
    check(
        not mal_f,
        f"las {len(figs)} figuras llevan caption abajo",
        f"figuras con caption arriba: {mal_f}",
    )
    # El marcador ya no es (\Envelope): con las fuentes de LNCS salia como un
    # glifo roto en la primera pagina. Ahora es una nota al pie \thanks, que
    # compone igual en cualquier instalacion. Sigue teniendo que haber UNO.
    marcas = t.count("\\thanks{Corresponding author.}")
    check(
        marcas == 1,
        "exactamente un autor de correspondencia",
        f"marcadores de correspondencia: {marcas}",
    )
    check(
        t.count("\\orcidID") == 5, "los cinco ORCID", f"ORCID encontrados: {t.count('\\orcidID')}"
    )
    check("\\authorrunning" in t, "authorrunning definido", "falta \\authorrunning")
    check("\\email{" in t, "correo del autor de correspondencia", "falta el correo")
    alt = len(re.findall(r"% ALT-TEXT", tex))
    check(
        alt >= len(figs),
        f"alt-text en las {len(figs)} figuras",
        f"alt-text {alt} para {len(figs)} figuras (accesibilidad, EU Accessibility Act)",
        grave=False,
    )


# ------------------------------------------------------------------ 3. restos de la version ciega
def audita_anonimato(tex: str) -> None:
    t = sin_comentarios(tex)
    for token in ("Anonymous", "withheld for double-blind", "Affiliations withheld"):
        check(
            token not in t,
            f"sin restos de la version ciega ({token!r})",
            f"queda texto de doble ciego ACTIVO: {token!r}",
        )


# ------------------------------------------------------------------ 4. bibliografia
def audita_bibliografia(tex: str) -> None:
    t = sin_comentarios(tex)
    claves = re.findall(r"\\bibitem\{([^}]+)\}", t)
    check(
        len(claves) == len(set(claves)),
        f"{len(claves)} bibitems, sin duplicados",
        "hay bibitems duplicados",
    )
    citadas = set()
    for m in re.findall(r"\\cite\{([^}]+)\}", t):
        citadas |= {c.strip() for c in m.split(",")}
    huerfanas = sorted(set(claves) - citadas)
    check(
        not huerfanas, "toda la bibliografia esta citada", f"bibitems nunca citados: {huerfanas}"
    )
    faltantes = sorted(citadas - set(claves))
    check(not faltantes, "toda cita tiene bibitem", f"citas sin bibitem: {faltantes}")
    # orden alfabetico por apellido del primer autor
    cuerpo = t[t.index("\\begin{thebibliography}") :]
    entradas = re.findall(r"\\bibitem\{[^}]+\}\s*\n([A-ZÀ-Þ][^,\n]*)", cuerpo)
    check(
        entradas == sorted(entradas, key=str.casefold),
        f"las {len(entradas)} referencias van en orden alfabetico",
        "la bibliografia NO esta en orden alfabetico",
    )
    con_doi = len(re.findall(r"\\url\{https?://(doi\.org|dx\.doi)", cuerpo))
    check(
        con_doi >= len(claves) * 0.7,
        f"{con_doi}/{len(claves)} referencias con DOI/URL",
        f"solo {con_doi}/{len(claves)} con DOI",
        grave=False,
    )


# ------------------------------------------------------------------ 5. numeracion y orden de citas
def audita_flotantes(aux: str) -> None:
    etiquetas = dict(re.findall(r"\\newlabel\{(fig:[^}]+)\}\{\{(\d+)\}", aux))
    nums = [int(v) for v in etiquetas.values()]
    check(
        sorted(nums) == list(range(1, len(nums) + 1)),
        f"figuras numeradas 1..{len(nums)} sin huecos",
        f"numeracion de figuras: {sorted(nums)}",
    )
    tabs = dict(re.findall(r"\\newlabel\{(tab:[^}]+)\}\{\{(\d+)\}", aux))
    tn = [int(v) for v in tabs.values()]
    check(
        sorted(tn) == list(range(1, len(tn) + 1)),
        f"tablas numeradas 1..{len(tn)} sin huecos",
        f"numeracion de tablas: {sorted(tn)}",
    )


# ------------------------------------------------------------------ 6. capa de texto y PDF
def audita_pdf() -> None:
    info = subprocess.run(
        ["pdfinfo", str(PDF)], capture_output=True, text=True, check=False
    ).stdout
    check("595.276 x 841.89" in info, "A4 real", "el PDF NO es A4")
    pg = re.search(r"Pages:\s+(\d+)", info)
    n = int(pg.group(1)) if pg else 0
    check(0 < n <= 20, f"{n} paginas (techo de MICAI: 20)", f"{n} paginas, el techo es 20")
    txt = subprocess.run(
        ["pdftotext", str(PDF), "-"], capture_output=True, text=True, check=False
    ).stdout
    rotas = re.findall(r"\b(dierent|justied|cuto|nding|staf|eciency|signicant)\b", txt)
    check(
        not rotas,
        "la capa de texto extrae bien las ligaduras",
        f"ligaduras rotas al extraer: {set(rotas)}",
    )
    check("ITESM" not in txt, "sin 'ITESM' (prohibido por TEC-II-05)", "el PDF dice 'ITESM'")
    check(
        "Tecnologico de Monterrey" in txt,
        "afiliacion del Tec conforme a TEC-II-05",
        "la afiliacion del Tec no aparece en la forma exigida",
    )
    orcids = re.findall(r"\d{4}[-\u2212]\d{4}[-\u2212]\d{4}[-\u2212]\d{3}[\dX]", txt)
    check(len(orcids) >= 5, f"{len(orcids)} ORCID impresos", f"ORCID impresos: {len(orcids)}")


# ------------------------------------------------------------------ 7. abstract
def audita_abstract(tex: str) -> None:
    cuerpo = tex[tex.index("\\begin{abstract}") : tex.index("\\keywords")]
    limpio = re.sub(r"\\[a-zA-Z]+", " ", cuerpo).replace("---", " ")
    limpio = re.sub(r"[{}~$\\]", " ", limpio)
    n = len(limpio.split()) - 1
    check(
        n <= 250,
        f"abstract de ~{n} palabras (limite 250)",
        f"abstract de ~{n} palabras, el limite es 250",
    )


# ------------------------------------------------------------------ 8. gates ya existentes
def audita_gates() -> None:
    for nombre, guion in [
        ("cifras retiradas", "valores_retirados.py"),
        ("coherencia de ventanas", "ventanas_coherentes.py"),
        ("paquete compila desde el ZIP", "empaqueta_envio.py --verifica"),
        # Estos dos van DESPUES de empaquetar: uno mira el PDF ya ensamblado y el
        # otro el ZIP recien escrito, asi que solo tienen sentido en ese orden.
        ("bibliografia y citas ordenadas", "bibliografia_intacta.py"),
        ("fuentes del PDF sin Type 3", "fuentes_pdf.py"),
        ("sello sincronizado", "sello_sincronizado.py"),
    ]:
        r = subprocess.run(
            [sys.executable, str(Path(__file__).parent / guion.split()[0]), *guion.split()[1:]],
            capture_output=True,
            text=True,
            check=False,
        )
        check(r.returncode == 0, f"gate: {nombre}", f"gate FALLA: {nombre}\n{r.stdout[-300:]}")


if __name__ == "__main__":
    tex = TEX.read_text()
    aux_dir = tempfile.mkdtemp()
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-output-directory", aux_dir, str(TEX)],
        cwd=MICAI,
        capture_output=True,
        check=False,
    )
    aux_p = Path(aux_dir) / "paper_camera_ready.aux"
    aux = aux_p.read_text() if aux_p.exists() else ""

    audita_zip()
    audita_lncs(tex)
    audita_anonimato(tex)
    audita_bibliografia(tex)
    if aux:
        audita_flotantes(aux)
    audita_pdf()
    audita_abstract(tex)
    audita_gates()

    print("=" * 78)
    print("AUDITORIA DEL PAQUETE — MICAI 2026, ponencia #12")
    print("=" * 78)
    print(f"\n  {len(oks)} comprobaciones en verde\n")
    for o in oks:
        print(f"     OK   {o}")
    if avisos:
        print(f"\n  {len(avisos)} avisos (no bloquean):\n")
        for a in avisos:
            print(f"     ~    {a}")
    if fallos:
        print(f"\n  {len(fallos)} FALLOS:\n")
        for f in fallos:
            print(f"     !!   {f}")
    print("\n" + "=" * 78)
    print("VEREDICTO:", "NO ENVIAR" if fallos else "LISTO PARA ENVIAR")
    print("=" * 78)
    raise SystemExit(1 if fallos else 0)
