#!/usr/bin/env python3
"""Control de cifras obsoletas sobre el .tex activo y el PDF compilado.

Toda cifra de la seccion de validacion cambio al corregir la alineacion de semanas.
Este control existe para que ninguna sobreviva escondida en una frase, un caption o
una nota al pie. Se revisa el .tex (sin comentarios) y tambien el PDF, porque una
cifra puede entrar por una figura y no por el fuente.

Uso:  .venv/bin/python scripts/paper_micai_2026/valores_retirados.py
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess

RAIZ = Path(__file__).resolve().parents[2]
TEX = RAIZ / "Congresos/MICAI/paper_camera_ready.tex"
PDF = RAIZ / "Congresos/MICAI/paper_camera_ready.pdf"

# (etiqueta, patron sobre el texto normalizado, que lo reemplazo)
RETIRADOS = [
    # Los patrones van anclados a su contexto: una cifra suelta como "26,5" tambien
    # aparece en la lista de lags {1,2,4,8,13,26,52} y en un eje de la Figura 1, y un
    # control que grita en falso se acaba ignorando.
    ("sMAPE prospectivo 6,63 %", r"6[.,]63\\?%", "7,40 %"),
    ("desviacion acumulada +4,40 %", r"\+4[.,]40\\?%", "+2,45 %"),
    ("MAE 184", r"=\s*184\$|\b184 cases", "205"),
    ("predicho acumulado 50 424", r"50\{,\}424", "49 482"),
    ("reconciliado 51 219", r"51\{,\}219", "50 261"),
    ("desviacion reconciliada +6,0 %", r"\+6[.,]0\\%", "+4,1 %"),
    ("mediana semanal 3,7 %", r"3[.,]7\\% median|of 3[.,]7\\%", "4,4 %"),
    ("W14 +26,5 %", r"\+26[.,]5\\%", "+23,8 %"),
    ("W15-W18 sMAPE 2,9 %", r"\\smape\\? of 2[.,]9\\%", "2,7 %"),
    ("hito W08 +0,2 %", r"\+0[.,]2\\%|W08.{0,80}saturation", "W08 = -4,4 %, sin hito"),
    ("Poisson 21,7 / 87,5", r"\$21[.,]7\$|\$87[.,]5\$", "25,3 / 104,9"),
    ("cobertura 15 de 17 / 88 % / 76 %", r"15 of 17|\(88\\%|76\\% under", "10 de 17 (58,8 %)"),
    (
        "DM sin ajustar y sin Holm",
        r"does not reject equal\s+accuracy|\$p=0[.,]15\$|\$p=0[.,]10\$",
        "0,0167 / 0,4328 / 0,0178 + Holm",
    ),
    ("convergencia 45-48 %", r"45\$?-+\$?48", "26,4 / 27,9 / 28,3 / 29,3"),
    ("73 de las 111 series", r"73 of the 111", "55 de 99 (62 de 111)"),
    ("held-out 69 %", r"69\\% of the reassigned|\b69[.,]35", "78,2 %"),
    ("held-out 32,0 -> 26,4 %", r"32[.,]0\\% to\s+26[.,]4\\%", "33,7 -> 26,1 %"),
    ("robustez 61-78 %", r"61--78\\%", "retirado"),
    ("ventana W01-W18", r"W01--W18", "W02-W18"),
]


def texto_tex() -> str:
    lineas = []
    for ln in TEX.read_text().splitlines():
        sin = re.sub(r"(?<!\\)%.*$", "", ln)  # fuera comentarios, respetando \%
        lineas.append(sin)
    return "\n".join(lineas)


def texto_pdf() -> str:
    if not PDF.exists():
        return ""
    r = subprocess.run(["pdftotext", str(PDF), "-"], capture_output=True, text=True, check=False)
    return r.stdout


def revisa() -> list[tuple[str, str, str]]:
    fuentes = {"tex": texto_tex(), "pdf": texto_pdf()}
    hallazgos = []
    for etiqueta, patron, reemplazo in RETIRADOS:
        for donde, cuerpo in fuentes.items():
            if not cuerpo:
                continue
            for m in re.finditer(patron, cuerpo):
                ini = max(0, m.start() - 60)
                ctx = " ".join(cuerpo[ini : m.end() + 60].split())
                hallazgos.append((etiqueta, f"{donde}: …{ctx}…", reemplazo))
    return hallazgos


if __name__ == "__main__":
    h = revisa()
    print("=" * 78)
    print(f"CONTROL DE CIFRAS RETIRADAS — {len(RETIRADOS)} patrones sobre .tex y PDF")
    print("=" * 78)
    if not h:
        print("\n  Ninguna cifra retirada sobrevive.")
        raise SystemExit(0)
    actual = None
    for etiqueta, ctx, reemplazo in h:
        if etiqueta != actual:
            print(f"\n  [{etiqueta}]  -> deberia decir {reemplazo}")
            actual = etiqueta
        print(f"      {ctx[:150]}")
    print(f"\n  {len(h)} apariciones por revisar")
    raise SystemExit(1)
