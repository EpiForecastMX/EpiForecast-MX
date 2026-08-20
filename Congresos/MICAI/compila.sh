#!/bin/bash
# Gate de compilacion del master MICAI 2026. Tres pasadas de pdflatex.
#
# BLOQUEA por: codigo de salida != 0, cualquier error '!' de LaTeX, referencias sin
# resolver, overfull > 15pt, o mas de 20 paginas (el techo de MICAI).
#
# Dos trampas que este script existe para no repetir:
#   - `nonstopmode` escribe PDF aunque LaTeX haya fallado, asi que contar paginas no
#     basta: hay que mirar el codigo de salida y las lineas '!'.
#   - el .log viene en latin-1; leerlo con grep directo falla en silencio.
#
# Compila en un directorio temporal propio y, si el gate PASA, deja el PDF junto al
# master para que el canonico nunca se quede atras del .tex.
#
# Uso:  ./compila.sh            (build limpio en un temporal)
#       BUILD=/ruta ./compila.sh   (reutiliza un directorio, util para inspeccionar)

set -u
AQUI="$(cd "$(dirname "$0")" && pwd)"
D="${BUILD:-$(mktemp -d)}"
LIMPIAR=0
[ -z "${BUILD:-}" ] && LIMPIAR=1

mkdir -p "$D"
cp -f "$AQUI/llncs.cls" "$AQUI/splncs04.bst" "$AQUI/paper_camera_ready.tex" "$D/" || exit 2
cp -rf "$AQUI/Figures" "$D/" 2>/dev/null
cd "$D" || exit 2

rc=0
for _ in 1 2 3; do
  pdflatex -interaction=nonstopmode paper_camera_ready.tex >/dev/null 2>&1 || rc=$?
done

RC=$rc python3 - <<'PY'
import os, re, sys
t = open("paper_camera_ready.log", encoding="latin-1").read()
err = [l for l in t.splitlines() if l.startswith("!")]
ov  = [float(x) for x in re.findall(r"Overfull \\[hv]box \(([0-9.]+)pt", t)]
und = len(re.findall(r"[Uu]ndefined (?:citation|reference|control)", t))
pg  = re.findall(r"Output written on .*?\((\d+) pages", t)
rc  = int(os.environ.get("RC", "0"))
graves  = [v for v in ov if v > 15]
paginas = int(pg[0]) if pg else None
print(f"  paginas    : {paginas if paginas is not None else '??'}"
      + ("  <-- SOBRE EL TECHO DE 20" if paginas and paginas > 20 else ""))
print(f"  rc pdflatex: {rc}")
print(f"  errores '!': {len(err)}")
for l in err[:5]:
    print(f"     {l[:95]}")
print(f"  undefined  : {und}")
print(f"  overfull   : {len(ov)}  (>15pt: {len(graves)}" + (f", peor {max(ov):.2f}pt)" if ov else ")"))
malo = (rc != 0 or err or und or graves
        or paginas is None or paginas > 20)   # <- el limite de paginas SI bloquea
print("  GATE       :", "FALLA" if malo else "PASA")
sys.exit(1 if malo else 0)
PY
gate=$?

# el PDF canonico sigue al master, no al reves
[ $gate -eq 0 ] && cp -f "$D/paper_camera_ready.pdf" "$AQUI/paper_camera_ready.pdf"
[ $LIMPIAR -eq 1 ] && rm -rf "$D"
exit $gate
