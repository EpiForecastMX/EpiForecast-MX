#!/usr/bin/env python3
"""Arma el ZIP de camera-ready para MICAI 2026 y lo VERIFICA compilandolo desde el ZIP.

MICAI acepta LaTeX solo como .zip con el .tex, la clase, los estilos y las imagenes.
Springer pide nombres cortos, asi que el paquete usa el numero de ponencia: 012.

Lo que hace distinto a comprimir una carpeta: extrae el ZIP en un directorio limpio y
compila desde ahi. Un paquete que no compila fuera de la maquina del autor es el modo
de fallo clasico de esta entrega, y ya nos costo una vez.

Uso:  .venv/bin/python scripts/paper_micai_2026/empaqueta_envio.py
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

RAIZ = Path(__file__).resolve().parents[2]
MICAI = RAIZ / "Congresos/MICAI"
MASTER = MICAI / "paper_camera_ready.tex"
NUMERO = "012"
DESTINO = MICAI / "Envio" / f"{NUMERO}.zip"


def figuras_referenciadas(tex: str) -> list[str]:
    return sorted(set(re.findall(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", tex)))


def construye() -> tuple[Path, list[str]]:
    tex = MASTER.read_text()
    figs = figuras_referenciadas(tex)
    faltan = [f for f in figs if not (MICAI / "Figures" / f).exists()]
    if faltan:
        raise SystemExit(f"faltan figuras referenciadas: {faltan}")

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{NUMERO}.tex", tex)  # un solo .tex, con el numero de ponencia
        z.write(MICAI / "llncs.cls", "llncs.cls")
        z.write(MICAI / "splncs04.bst", "splncs04.bst")
        for f in figs:
            z.write(MICAI / "Figures" / f, f"Figures/{f}")
        z.write(MICAI / "paper_camera_ready.pdf", f"{NUMERO}.pdf")
    return DESTINO, figs


def verifica(zip_path: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(d)
        nombres = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
        texs = [n for n in nombres if n.endswith(".tex")]
        if len(texs) != 1:
            raise SystemExit(f"el paquete debe llevar UN solo .tex, lleva {texs}")
        if shutil.which("pdflatex") is None:
            return {"nombres": nombres, "compila": "sin pdflatex"}
        rc = 0
        for _ in range(3):
            r = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", texs[0]],
                cwd=d,
                capture_output=True,
                timeout=300,
                check=False,
            )
            rc = r.returncode or rc
        log = (d / texs[0]).with_suffix(".log").read_text(encoding="latin-1")
        err = [x for x in log.splitlines() if x.startswith("!")]
        pg = re.findall(r"Output written on .*?\((\d+) pages", log)
        und = len(re.findall(r"[Uu]ndefined (?:citation|reference|control)", log))
        ov = [float(v) for v in re.findall(r"Overfull \\[hv]box \(([0-9.]+)pt", log)]
        info = subprocess.run(
            ["pdfinfo", str((d / texs[0]).with_suffix(".pdf"))],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        a4 = "595.276 x 841.89" in info
        return {
            "nombres": nombres,
            "rc": rc,
            "errores": len(err),
            "undefined": und,
            "paginas": int(pg[0]) if pg else None,
            "overfull_graves": sum(1 for v in ov if v > 15),
            "a4": a4,
        }


if __name__ == "__main__":
    z, figs = construye()
    v = verifica(z)
    print("=" * 72)
    print(f"PAQUETE DE ENVIO — {z.relative_to(RAIZ)}")
    print("=" * 72)
    print(
        f"  {z.stat().st_size / 1024:.0f} KB · sha256 {hashlib.sha256(z.read_bytes()).hexdigest()[:16]}"
    )
    print("  contenido:")
    for n in v["nombres"]:
        print(f"     {n}")
    if v.get("compila") == "sin pdflatex":
        print("\n  pdflatex no disponible: no se pudo verificar la compilacion")
        sys.exit(0)
    print(
        f"\n  compilado DESDE EL ZIP: {v['paginas']} paginas · rc={v['rc']} · "
        f"{v['errores']} errores · {v['undefined']} undefined · "
        f"{v['overfull_graves']} overfull >15pt · A4 {'si' if v['a4'] else 'NO'}"
    )
    malo = (
        v["rc"]
        or v["errores"]
        or v["undefined"]
        or v["overfull_graves"]
        or not v["a4"]
        or v["paginas"] is None
        or v["paginas"] > 20
    )
    print("  VEREDICTO:", "FALLA" if malo else "PASA")
    sys.exit(1 if malo else 0)
